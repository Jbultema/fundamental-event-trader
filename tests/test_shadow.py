import json
from types import SimpleNamespace

import exchange_calendars as xcals
import pandas as pd
import pytest

from fundamental_event_trader.sec import DataGateError
from fundamental_event_trader.shadow import evaluate, record, summary


def observation(session="2026-11-23", captured="2026-11-23T21:16:00Z"):
    return {
        "status": "research_shadow", "fresh": True, "as_of_session": session,
        "captured_at_utc": captured, "code_sha256": "a" * 64,
        "research_manifest_sha256": "b" * 64, "dataset_manifest_sha256": "c" * 64,
        "policy": {"name": "synthetic_test_only"}, "target_holdings": {"TEST": .1},
    }


def test_blocked_or_stale_cannot_start_prospective_track_record(tmp_path):
    for change in ({"status": "blocked"}, {"fresh": False}):
        assert record(tmp_path, observation() | change, now="2026-11-23T21:17Z")["status"] == "not_recorded"
    assert not (tmp_path / "data").exists()
    assert summary(tmp_path, {}, now="2026-11-23T21:17Z")["status"] == "not_started"


@pytest.mark.parametrize("clock", ["2026-11-23T21:14:00Z", "2026-11-24T14:30:00Z", "2026-11-25T22:00:00Z"])
def test_late_reconstructed_or_too_early_forecasts_get_no_credit(tmp_path, clock):
    item = observation(captured=clock)
    result = record(tmp_path, item, now=clock)
    assert result["status"] == "not_recorded"
    assert not (tmp_path / "data").exists()


def test_forward_capture_immutable_idempotent_and_not_a_profitability_claim(tmp_path):
    item = observation()
    result = record(tmp_path, item, now="2026-11-23T21:17Z")
    assert result["status"] == "recorded"
    assert record(tmp_path, item, now="2026-11-23T22:00Z")["status"] == "already_recorded"
    assert record(tmp_path, item | {"captured_at_utc": "2026-11-23T22:01Z"}, now="2026-11-23T22:01Z")["sha256"] == result["sha256"]
    value = summary(tmp_path, item, now="2026-11-23T22:02Z")
    assert value["consecutive_sessions"] == value["recorded_sessions"] == 1
    assert value["profitability_established"] is False
    with pytest.raises(DataGateError, match="changed"):
        record(tmp_path, item | {"target_holdings": {"TEST": .2}}, now="2026-11-23T22:03Z")


def test_missing_session_breaks_streak_instead_of_being_backfilled(tmp_path):
    first = observation()
    record(tmp_path, first, now="2026-11-23T21:17Z")
    later = observation("2026-11-25", "2026-11-25T21:17Z")
    record(tmp_path, later, now="2026-11-25T21:17Z")
    value = summary(tmp_path, later, now="2026-11-25T21:18Z")
    assert value["recorded_sessions"] == 2
    assert value["consecutive_sessions"] == 1
    assert value["missing_sessions"] == ["2026-11-24"]
    # The Thanksgiving holiday is not an expected observation.
    value = summary(tmp_path, later, now="2026-11-27T17:00Z")
    assert value["missing_sessions"] == ["2026-11-24"]
    assert value["consecutive_sessions"] == 1


def test_half_day_deadline_uses_next_actual_open(tmp_path):
    item = observation("2026-11-27", "2026-11-27T18:16Z")
    assert record(tmp_path, item, now="2026-11-28T18:00Z")["status"] == "recorded"
    assert summary(tmp_path, item, now="2026-11-29T18:00Z")["consecutive_sessions"] == 1
    assert record(tmp_path, item, now="2026-11-30T14:30Z")["status"] == "not_recorded"


def test_future_captured_status_rejected(tmp_path):
    with pytest.raises(DataGateError, match="future"):
        record(tmp_path, observation(), now="2026-11-23T21:15Z")


@pytest.mark.parametrize("targets", [{"A": float("nan")}, {"A": -1}, {"A": 1.1}, {"A": True}, {"A": "0.1"}])
def test_invalid_targets_cannot_poison_journal(tmp_path, targets):
    with pytest.raises(DataGateError, match="[Tt]arget"):
        record(tmp_path, observation() | {"target_holdings": targets}, now="2026-11-23T21:17Z")
    assert not (tmp_path / "data").exists()


def test_code_change_starts_separate_cohort(tmp_path):
    item = observation()
    record(tmp_path, item, now="2026-11-23T21:17Z")
    newer = item | {"code_sha256": "d" * 64}
    assert summary(tmp_path, newer, now="2026-11-23T22:00Z")["status"] == "not_started"


def test_chain_detects_changed_prior_observation(tmp_path):
    item = observation()
    captured = record(tmp_path, item, now="2026-11-23T21:17Z")
    later = observation("2026-11-24", "2026-11-24T21:17Z")
    record(tmp_path, later, now="2026-11-24T21:17Z")
    file = next(tmp_path.glob("data/prospective/*/2026-11-23.json"))
    payload = json.loads(file.read_text())
    payload["target_holdings"] = {"TEST": .2}
    file.write_text(json.dumps(payload))
    with pytest.raises(DataGateError, match="chain"):
        summary(tmp_path, item, now="2026-11-24T22:00Z")
    assert captured["sha256"]


def test_last_record_is_also_bound_by_the_committed_head(tmp_path):
    item = observation()
    record(tmp_path, item, now="2026-11-23T21:17Z")
    file = next(tmp_path.glob("data/prospective/*/2026-11-23.json"))
    payload = json.loads(file.read_text())
    payload["target_holdings"] = {"TEST": .2}
    file.write_text(json.dumps(payload))
    with pytest.raises(DataGateError, match="head changed"):
        summary(tmp_path, item, now="2026-11-23T22:00Z")


def test_unrecorded_session_does_not_count_after_next_open(tmp_path):
    item = observation()
    record(tmp_path, item, now="2026-11-23T21:17Z")
    before_deadline = summary(tmp_path, item, now="2026-11-24T22:00Z")
    assert before_deadline["consecutive_sessions"] == 1
    after_deadline = summary(tmp_path, item, now="2026-11-25T14:30Z")
    assert after_deadline["consecutive_sessions"] == 0
    assert after_deadline["missing_sessions"] == ["2026-11-24"]


def test_naive_timestamp_is_not_prospective_evidence(tmp_path):
    with pytest.raises(DataGateError, match="timezone"):
        record(tmp_path, observation(), now=pd.Timestamp("2026-11-23T22:00"))


def outcome_data(tmp_path):
    cal = xcals.get_calendar("XNYS")
    days = cal.sessions_in_range("2026-11-23", "2026-11-27")
    index = pd.DatetimeIndex([cal.session_open(day) for day in days])
    (tmp_path / "manifest.json").write_text('{"synthetic_test_fixture": true}')
    return SimpleNamespace(
        root=tmp_path,
        opens=pd.DataFrame({"TEST": [100., 100., 120., 130.], "SPY": 100.}, index=index),
        closes=pd.DataFrame({"TEST": [100., 110., 120., 130.], "SPY": 100.}, index=index),
        cash=pd.Series(0., index=index), terminals=pd.DataFrame(),
    )


def test_forward_outcomes_use_only_recorded_decisions_and_completed_prices(tmp_path):
    item = observation()
    record(tmp_path, item, now="2026-11-23T21:17Z")
    data = outcome_data(tmp_path)
    initial = evaluate(tmp_path, item, data, now="2026-11-23T22:00Z")
    assert initial["status"] == "not_scored"
    before = evaluate(tmp_path, item, data, now="2026-11-24T22:00Z")
    assert before["status"] == "recorded_decisions_marked"
    assert before["performance"][0]["sessions"] == 1
    assert before["performance"][0]["total_return"] > 0
    assert "cagr" not in before["performance"][0]
    assert before["performance"][2]["total_return"] == 0
    data.closes.loc[data.closes.index[-1], "TEST"] = 1e6
    assert evaluate(tmp_path, item, data, now="2026-11-24T22:00Z") == before
    missing = evaluate(tmp_path, item, data, now="2026-11-25T22:00Z")
    assert missing["status"] == "not_scored"
    assert "missing_pre_execution" in missing["reason"]


def test_contiguous_forward_decisions_can_be_marked_without_reselecting_policy(tmp_path):
    item = observation()
    record(tmp_path, item, now="2026-11-23T21:17Z")
    second = observation("2026-11-24", "2026-11-24T21:17Z")
    record(tmp_path, second, now="2026-11-24T21:17Z")
    result = evaluate(tmp_path, second, outcome_data(tmp_path), now="2026-11-25T22:00Z")
    assert result["status"] == "recorded_decisions_marked"
    assert result["performance"][0]["sessions"] == 2
    assert result["performance"][0]["total_return"] > .019
    assert result["action_authorized"] is result["automatic_promotion_allowed"] is False
