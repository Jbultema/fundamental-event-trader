import pandas as pd
import pytest

from fundamental_event_trader.operating import configure
from fundamental_event_trader.readiness import coverage
from fundamental_event_trader.sec import DataGateError


def test_registry_variants_are_not_mistaken_for_tested_families():
    rows = coverage()
    assert len(rows) == 10
    assert sum(row["registered_variants"] for row in rows) == 48
    assert all(row["tested_variants"] == row["variants_with_features"] == 0 for row in rows)
    assert all(row["limitations"] == ["no_qualified_historical_dataset"] for row in rows)
    assert "not implemented" in next(row["content"] for row in rows if row["family"] == "ownership_change")


def test_actual_available_content_is_separate_from_tested_strategies():
    frame = pd.DataFrame({
        "security_id": ["A"], "cik": ["1"], "accepted_at": ["2020-01-02T22:00Z"],
        "available_at": ["2020-01-02T22:00Z"], "accession": ["0000000001-20-000001"],
        "source_sha256": ["a" * 64], "profitability_change": [.1],
    })
    row = next(row for row in coverage(frame) if row["family"] == "profitability_change")
    assert row["variants_with_features"] == 6
    assert row["tested_variants"] == 0
    assert row["eligible_events_at_least_restrictive_threshold"] == 1


def test_configure_cannot_skip_native_performance_audit(tmp_path, monkeypatch):
    import fundamental_event_trader.operating as operating

    monkeypatch.setattr(operating, "load_dataset", lambda _: object())
    monkeypatch.setattr(operating, "frozen_policy", lambda *_: object())

    def failed_audit(_):
        raise DataGateError("native audit failed")

    monkeypatch.setattr(operating, "audit_report", failed_audit)
    with pytest.raises(DataGateError, match="native audit failed"):
        configure(tmp_path, tmp_path / "dataset", tmp_path / "report")
    assert not (tmp_path / "data/runtime.json").exists()
