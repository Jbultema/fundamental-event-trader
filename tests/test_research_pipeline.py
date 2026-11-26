import json
import shutil

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.operating import daily, status, verify_report
from fundamental_event_trader.research import bootstrap_excess, load_dataset, run
from fundamental_event_trader.sec import DataGateError, sha


@pytest.fixture(scope="module")
def historical_fixture(tmp_path_factory):
    root = tmp_path_factory.mktemp("explicit_synthetic_history")
    cal = xcals.get_calendar("XNYS", start="2000-01-01", end="2013-01-01")
    days = cal.sessions_in_range("2000-01-03", "2012-12-31")
    idx = pd.DatetimeIndex([cal.session_open(day) for day in days])
    names = [f"S{i:03}" for i in range(100)]
    opens = pd.DataFrame(100.0, index=idx, columns=[*names, "SPY"])
    opens.S000 = 100 * np.exp(np.arange(len(idx)) * 0.0002)
    opens.SPY = 100 * np.exp(np.arange(len(idx)) * 0.0001)
    closes = opens.copy()
    terminal = pd.Timestamp("2010-01-04T14:30:00Z")
    opens.loc[opens.index >= terminal, "S099"] = np.nan
    closes.loc[closes.index >= terminal, "S099"] = np.nan
    identity = pd.DataFrame(
        {
            "security_id": names,
            "cik": [str(i + 1).zfill(10) for i in range(100)],
            "known_at": "1998-01-01T00:00:00Z",
            "valid_from": "1998-01-01T00:00:00Z",
            "valid_until": ["2030-01-01T00:00:00Z"] * 99 + [terminal.isoformat()],
            "delisted": [False] * 99 + [True],
            "terminal_treatment_verified": True,
        }
    )
    (root / "source_fixture.json").write_text(
        '{"synthetic_fixture":true,"not_investment_evidence":true}'
    )
    source = sha(root / "source_fixture.json")
    event_days = idx[100::63]
    accepted = event_days + pd.Timedelta(hours=1)
    events = pd.DataFrame(
        {
            "security_id": "S000",
            "cik": "0000000001",
            "accepted_at": accepted,
            "available_at": accepted,
            "directional_signal": 1.0,
            "profitability_change": 0.06,
            "source_sha256": source,
            "accession": [f"0000000001-00-{i:06}" for i in range(len(event_days))],
        }
    )
    settlements = pd.DataFrame(
        {
            "security_id": ["S099"],
            "settlement_at": [terminal],
            "value_per_adjusted_share": [0.0],
            "source_sha256": [source],
        }
    )
    for name, frame in (
        ("prices", opens),
        ("close_prices", closes),
        ("identity", identity),
        ("events", events),
        ("terminal_events", settlements),
    ):
        frame.to_parquet(root / f"{name}.parquet")
    pd.DataFrame({"cash_return": 0.0}, index=idx).to_parquet(root / "cash_returns.parquet")
    from fundamental_event_trader.qualification import CRITERIA

    meta = {
        "data_kind": "synthetic_fixture",
        "criteria": {
            c: {"passed": True, "evidence_artifact": "source_fixture.json"} for c in CRITERIA
        },
        "artifacts": {p.name: sha(p) for p in root.iterdir()},
    }
    (root / "manifest.json").write_text(json.dumps(meta))
    return root


@pytest.fixture(scope="module")
def fixture_report(historical_fixture, tmp_path_factory):
    return run(
        historical_fixture,
        tmp_path_factory.mktemp("research_parent") / "fixture_report",
        fixture_only=True,
    )


def test_real_data_pipeline_rejects_test_fixtures(historical_fixture):
    with pytest.raises(DataGateError, match="synthetic"):
        load_dataset(historical_fixture)


@pytest.mark.parametrize("change", [None, "invented_return", "future_window", "wrong_price_source"])
def test_post_filing_features_reconcile_to_their_completed_price_window(
    historical_fixture, tmp_path, change
):
    from fundamental_event_trader.strategy import session_schedule

    root = tmp_path / "dataset"
    shutil.copytree(historical_fixture, root)
    events = pd.read_parquet(root / "events.parquet")
    closes = pd.read_parquet(root / "close_prices.parquet")
    schedule = session_schedule(closes.index)
    events["post_filing_return"] = np.nan
    events["price_window_end"] = pd.Series(pd.NaT, index=events.index, dtype="datetime64[ns, UTC]")
    events["post_filing_price_sha256"] = sha(root / "close_prices.parquet")
    events.loc[0, "post_filing_return"] = closes.S000.iloc[105] / closes.S000.iloc[100] - 1
    events.loc[0, "price_window_end"] = schedule.close.iloc[105]
    events.loc[0, "available_at"] = schedule.close.iloc[105]
    if change == "invented_return":
        events.loc[0, "post_filing_return"] = 99.0
    elif change == "future_window":
        events.loc[0, "available_at"] = schedule.close.iloc[104]
    elif change == "wrong_price_source":
        events.loc[0, "post_filing_price_sha256"] = "0" * 64
    events.to_parquet(root / "events.parquet")
    meta = json.loads((root / "manifest.json").read_text())
    meta["artifacts"]["events.parquet"] = sha(root / "events.parquet")
    (root / "manifest.json").write_text(json.dumps(meta))
    if change:
        with pytest.raises(DataGateError, match="[Pp]ost-filing"):
            load_dataset(root, fixture_only=True)
    else:
        assert len(load_dataset(root, fixture_only=True).events) == len(events)


def test_complete_fixture_exercises_portfolio_pipeline_without_claiming_alpha(fixture_report):
    selection = json.loads((fixture_report / "selection.json").read_text())
    assert selection["fixture_only"] is True
    assert selection["registered"] == 48 and selection["tested"] == 6
    assert selection["portfolio_allocation_allowed"] is False
    text = (fixture_report / "readout.md").read_text()
    assert "SYNTHETIC FIXTURE ONLY" in text
    perf = pd.read_csv(fixture_report / "performance.csv")
    assert set(perf.period) == {"development", "validation", "lockbox"}
    assert {"buy_hold_SPY", "cash"} <= set(perf.name)
    stress = pd.read_csv(fixture_report / "execution_stress.csv")
    assert len(stress) == 9
    walk = pd.read_csv(fixture_report / "walk_forward.csv")
    assert (
        pd.to_datetime(walk.selection_outcomes_through, utc=True)
        < pd.to_datetime(walk.test_start, utc=True)
    ).all()
    returns = pd.read_parquet(fixture_report / "walk_forward_returns.parquet")
    assert returns["return"].notna().all()


def test_fixture_report_cannot_become_a_real_daily_signal(fixture_report, historical_fixture):
    with pytest.raises(DataGateError, match="synthetic"):
        verify_report(fixture_report)
    result = status(historical_fixture.parent, dataset=historical_fixture, report=fixture_report)
    assert result["status"] == "blocked" and result["target_holdings"] == {}
    assert result["tested_on_real_data"] == 0


def test_last_close_signal_without_any_fill_is_not_a_tested_strategy(historical_fixture, tmp_path):
    from fundamental_event_trader.strategy import session_schedule

    root = tmp_path / "last_close_fixture"
    shutil.copytree(historical_fixture, root)
    opens = pd.read_parquet(root / "prices.parquet")
    event = pd.read_parquet(root / "events.parquet").iloc[:1].copy()
    event["accepted_at"] = event["available_at"] = session_schedule(opens.index).close.iloc[-1] - pd.Timedelta(hours=1)
    event.to_parquet(root / "events.parquet")
    meta = json.loads((root / "manifest.json").read_text())
    meta["artifacts"]["events.parquet"] = sha(root / "events.parquet")
    (root / "manifest.json").write_text(json.dumps(meta))
    report = run(root, tmp_path / "no_execution_report", fixture_only=True)
    selection = json.loads((report / "selection.json").read_text())
    assert selection["tested"] == 0 and selection["policy"] is None
    statuses = pd.read_csv(report / "hypothesis_status.csv")
    assert len(statuses[statuses.status.eq("no_observed_execution")]) == 6


def test_blocked_daily_capture_is_explicit_and_immutable(tmp_path):
    root = daily(tmp_path, tmp_path / "observation")
    captured = json.loads((root / "status.json").read_text())
    assert captured["status"] == "blocked"
    assert captured["errors"] == ["no_qualified_historical_dataset"]
    assert captured["prospective_shadow"]["recorded_sessions"] == 0
    assert "| Content family |" in (root / "readout.md").read_text()
    with pytest.raises(FileExistsError):
        daily(tmp_path, root)


def test_bootstrap_is_deterministic_and_keeps_pairs_together():
    candidate = pd.Series(np.sin(np.arange(200)) * 0.01 + 0.001)
    benchmark = candidate - 0.0005
    a = bootstrap_excess(candidate, benchmark, reps=100)
    assert a == bootstrap_excess(candidate, benchmark, reps=100)
    assert a["lower_95"] == pytest.approx(0.0005 * 252)
    assert a["upper_95"] == pytest.approx(0.0005 * 252)
    assert (
        bootstrap_excess(candidate.iloc[:10], benchmark.iloc[:10])["status"]
        == "insufficient_observations"
    )


@pytest.mark.parametrize("change", [None, "returns", "fills", "realized_weights", "performance"])
def test_native_audit_recomputes_results_not_only_hashes(
    historical_fixture, fixture_report, tmp_path, monkeypatch, change
):
    import fundamental_event_trader.operating as operating

    report = tmp_path / "report"
    shutil.copytree(fixture_report, report)
    frozen = json.loads((report / "registry.json").read_text())
    selected = json.loads((report / "selection.json").read_text())
    manifest = json.loads((report / "manifest.json").read_text())
    # Explicit test-only adapters reach the semantic audit; production still rejects fixtures.
    monkeypatch.setattr(operating, "verify_report", lambda _: {"manifest": manifest, "frozen": frozen, "selection": selected})
    monkeypatch.setattr(operating, "load_dataset", lambda root: load_dataset(root, fixture_only=True))
    if change == "returns":
        path = report / "returns.parquet"
        frame = pd.read_parquet(path)
        frame.loc[frame.index[-1], selected["policy"]["name"]] += .1
        frame.to_parquet(path)
    elif change in {"fills", "realized_weights"}:
        path = report / f"selected_{change}.parquet"
        frame = pd.read_parquet(path)
        if change == "fills":
            frame.loc[0, "notional"] += .1
        else:
            frame.iloc[-1, 0] += .1
        frame.to_parquet(path)
    elif change == "performance":
        path = report / "performance.csv"
        frame = pd.read_csv(path)
        frame.loc[frame.name.eq(selected["policy"]["name"]), "cagr"] += .1
        frame.to_csv(path, index=False)
    if change:
        with pytest.raises((DataGateError, AssertionError)):
            operating.audit_report(report)
    else:
        assert operating.audit_report(report)["status"] == "passed_research_integrity"
