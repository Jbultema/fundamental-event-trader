import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader import event_sample_pilot as pilot
from fundamental_event_trader.qualification import qualify
from fundamental_event_trader.sec import DataGateError, sha


def sample(root):
    root.mkdir()
    protocol = {
        "kind": pilot.KIND, "roster": ["TEST"], "from": "2021-01-01", "to": "2023-12-31",
        "features": dict.fromkeys(pilot.FAMILIES, "fixture feature"),
        "horizons": [21, 63, 126], "execution_lags": [1, 2, 5],
        "cost_bps_per_side": [10, 25, 50], "no_threshold_selection": True,
        "portfolio_allocation_allowed": False, "biases": ["synthetic_test_fixture"],
    }
    (root / "protocol.json").write_text(json.dumps(protocol))
    calendar = xcals.get_calendar("XNYS", start="2020-12-24", end="2024-01-08")
    days = calendar.sessions_in_range(protocol["from"], protocol["to"])
    prices = pd.DataFrame({"ticker": "TEST", "date": days.strftime("%Y-%m-%d"),
        "open": np.linspace(100, 120, len(days)), "close": np.linspace(101, 121, len(days)),
        "closeadj": np.linspace(50.5, 60.5, len(days)), "volume": 10000})
    prices.to_csv(root / "stocks_TEST.csv", index=False)
    facts = pd.DataFrame({"ticker": "TEST", "date": ["2021-02-01", "2022-02-01", "2022-05-02", "2023-12-28"],
        "reportperiod": ["2020-12-31", "2021-12-31", "2022-03-31", "2023-09-30"],
        "dimension": "ART", "assets": 100, "ncfo": [11, 15, 16, 9], "netinc": 10,
        "ncfcommon": -3, "lastupdated": "2023-12-29"})
    facts.to_csv(root / "fundamentals_TEST.csv", index=False)
    seal(root)
    return root


def seal(root):
    checks = []
    protocol = json.loads((root / "protocol.json").read_text())
    for table in ("stocks", "fundamentals"):
        file = root / f"{table}_TEST.csv"
        checks.append({"table": table, "ticker": "TEST", "path": file.name,
            "sha256": sha(file), "bytes": file.stat().st_size, "status": "acquired_not_qualified",
            "query": {"api_key": "test-api-key", "ticker": "TEST", "from": protocol["from"], "to": protocol["to"],
                      "limit": 1500, "dimension": "ART"}})
    (root / "acquisition.json").write_text(json.dumps({"kind": pilot.KIND, "purchase_made": False,
        "account_credentials_used": False, "protocol_sha256": sha(root / "protocol.json"), "checks": checks}))


@pytest.mark.parametrize("day,expected", [
    ("2026-03-06", "2026-03-08T05:00:00+00:00"),
    ("2026-03-07", "2026-03-09T04:00:00+00:00"),
    ("2026-11-25", "2026-11-27T05:00:00+00:00"),
])
def test_date_only_delay_respects_local_midnight_and_dst(day, expected):
    assert pilot.delayed_date_cutoff(day).isoformat() == expected


@pytest.mark.parametrize("value", [None, "2026-02-30", "2026-11-01T12:00:00Z", "11/01/2026", "2026-1-01"])
def test_invalid_or_invented_acceptance_timestamps_fail(value):
    with pytest.raises((DataGateError, ValueError)):
        pilot.delayed_date_cutoff(value)


def test_pilot_never_unlocks_legacy_validation_or_allocation(tmp_path):
    root = sample(tmp_path / "sample")
    status = pilot.qualify_pilot(root)
    assert status["exploratory_event_study_allowed"] is True
    assert status["historical_event_study_allowed"] is False
    assert status["strategy_promotion_allowed"] is False
    assert status["portfolio_allocation_allowed"] is False
    assert qualify(root)["historical_event_study_allowed"] is False
    _, _, prices, _ = pilot.load_sample(root)
    assert prices.iloc[0, 0] == 50.0


@pytest.mark.parametrize("kind", ["tamper", "missing_member", "missing_session", "mr_dimension", "wrong_ticker",
    "nonpositive_price", "no_volume", "future_period", "duplicate_fact", "absolute_escape", "changed_grid", "unbound_protocol"])
def test_adversarial_samples_fail_closed(tmp_path, kind):
    root = sample(tmp_path / "sample")
    if kind in {"tamper", "missing_session", "nonpositive_price", "no_volume"}:
        file = root / "stocks_TEST.csv"
        prices = pd.read_csv(file)
        if kind == "missing_session":
            prices = prices.iloc[1:]
        elif kind == "nonpositive_price":
            prices.loc[0, "open"] = 0
        elif kind == "no_volume":
            prices.loc[0, "volume"] = 0
        else:
            prices.loc[0, "open"] = 500
        prices.to_csv(file, index=False)
        if kind != "tamper":
            seal(root)
    elif kind in {"mr_dimension", "wrong_ticker", "future_period", "duplicate_fact"}:
        file = root / "fundamentals_TEST.csv"
        facts = pd.read_csv(file)
        if kind == "mr_dimension":
            facts["dimension"] = "MRT"
        elif kind == "wrong_ticker":
            facts["ticker"] = "OTHER"
        elif kind == "future_period":
            facts.loc[0, "reportperiod"] = "2022-12-31"
        else:
            facts = pd.concat([facts, facts.iloc[:1]], ignore_index=True)
        facts.to_csv(file, index=False)
        seal(root)
    elif kind == "changed_grid":
        file = root / "protocol.json"
        protocol = json.loads(file.read_text())
        protocol["execution_lags"] = [0]
        file.write_text(json.dumps(protocol))
        seal(root)
    else:
        file = root / "acquisition.json"
        acquisition = json.loads(file.read_text())
        if kind == "missing_member":
            acquisition["checks"].pop()
        elif kind == "absolute_escape":
            acquisition["checks"][0]["path"] = "/etc/passwd"
        else:
            acquisition["protocol_sha256"] = "0" * 64
        file.write_text(json.dumps(acquisition))
    assert pilot.qualify_pilot(root)["exploratory_event_study_allowed"] is False


def test_features_use_only_previously_released_comparison_and_retain_censoring(tmp_path):
    root = sample(tmp_path / "sample")
    _, facts, _, _ = pilot.load_sample(root)
    out = pilot.features(facts)
    cash = out[out.family.eq(pilot.FAMILIES[0])]
    assert cash.iloc[0].feature_status == "left_censored_prior_year_missing"
    assert not cash.iloc[0].selected
    row = cash[cash.filing_date.eq("2022-02-01")].iloc[0]
    assert row.selected
    assert row.score == pytest.approx(0.04)
    assert row.prior_publication_date == "2021-02-01"
    assert "accepted_at" not in out
    assert "available_at" not in out
    future = facts.iloc[[0]].copy()
    future["date"] = "2022-03-01"
    future["ncfo"] = -999
    after = pilot.features(pd.concat([facts, future], ignore_index=True))
    compare = after[(after.family == pilot.FAMILIES[0]) & after.filing_date.eq("2022-02-01")].iloc[0]
    assert compare.score == row.score


def test_cost_delay_math_censoring_and_control_identity(tmp_path):
    root = sample(tmp_path / "sample")
    protocol, facts, prices, _ = pilot.load_sample(root)
    out = pilot.evaluate(pilot.features(facts), prices, protocol)
    assert "right_censored_no_complete_horizon" in set(out.status)
    measured = out[out.status.eq("measured")]
    assert len(measured)
    for row in measured.itertuples():
        entry, exit_at = pd.Timestamp(row.entry_at), pd.Timestamp(row.exit_at)
        assert entry >= pd.Timestamp(row.available_after)
        assert prices.index.get_loc(exit_at) - prices.index.get_loc(entry) == row.horizon_sessions
        assert row.ticker == "TEST"
        factor = (1 - row.cost_bps_per_side / 10000) / (1 + row.cost_bps_per_side / 10000)
        expected = prices.loc[exit_at, row.ticker] / prices.loc[entry, row.ticker] * factor - 1
        assert row.event_net_return == pytest.approx(expected)
    group = measured[(measured.family == pilot.FAMILIES[1]) & measured.filing_date.eq("2022-02-01") & measured.horizon_sessions.eq(21)]
    entries = {lag: pd.Timestamp(group[group.lag_sessions.eq(lag)].iloc[0].entry_at) for lag in (1, 2, 5)}
    assert prices.index.get_loc(entries[5]) - prices.index.get_loc(entries[1]) == 4
    one = group[group.lag_sessions.eq(1)].sort_values("cost_bps_per_side")
    assert one.event_net_return.is_monotonic_decreasing


def test_run_is_immutable_and_cannot_emit_targets_or_cagr(tmp_path):
    root = sample(tmp_path / "sample")
    output = tmp_path / "result"
    report = pilot.run(root, output)
    assert report["qualified_portfolio_strategies_tested"] == 0
    assert report["portfolio_allocation_allowed"] is False
    assert report["event_return_scenarios_measured"] <= 54
    assert not any("target" in p.name for p in output.iterdir())
    assert "cagr" not in report
    manifest = json.loads((output / "manifest.json").read_text())
    assert all(sha(output / name) == digest for name, digest in manifest["artifacts"].items())
    with pytest.raises(FileExistsError):
        pilot.run(root, output)
