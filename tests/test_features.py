import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.features import (
    accounting_features,
    event_study,
    insider_cluster,
    parse_form4,
    registry,
)
from fundamental_event_trader.qualification import qualify
from fundamental_event_trader.sec import DataGateError


def test_unqualified_data_cannot_unlock_research():
    result = qualify()
    assert result["status"] == "blocked"
    assert result["historical_event_study_allowed"] is False
    assert result["portfolio_allocation_allowed"] is False


def test_no_current_survivor_universe_substitution(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    (root / "manifest.json").write_text('{"criteria":{},"artifacts":{}}')
    result = qualify(root)
    assert "missing_required_tables" in result["errors"]


def test_registry_is_hypotheses_not_performance_claim():
    rows = registry()
    assert len(rows) == 48
    assert len({r["name"] for r in rows}) == 48


def test_event_after_close_fills_next_actual_open_not_acceptance_day():
    dates = pd.date_range("2020-01-02 14:30", periods=5, freq="B", tz="UTC")
    prices = pd.DataFrame({"A": [100, 200, 220, 242, 266.2], "SPY": [100] * 5}, index=dates)
    events = pd.DataFrame(
        {"security_id": ["A"], "accepted_at": ["2020-01-02T21:05:00Z"], "directional_signal": [1]}
    )
    result = event_study(events, prices, horizon=2, roundtrip_bps=50)
    assert result.entry_at.iloc[0] == dates[1]
    assert result.event_return_net.iloc[0] == pytest.approx(0.205)


def test_event_price_gap_is_not_silently_zero_return():
    dates = pd.date_range("2020-01-02 14:30", periods=5, freq="B", tz="UTC")
    prices = pd.DataFrame({"A": [100, 200, np.nan, 242, 266.2], "SPY": [100] * 5}, index=dates)
    events = pd.DataFrame(
        {"security_id": ["A"], "accepted_at": ["2020-01-02T21:05:00Z"], "directional_signal": [1]}
    )
    with pytest.raises(DataGateError):
        event_study(events, prices, horizon=2)


def test_unmatured_event_outcomes_are_not_filled():
    dates = pd.date_range("2020-01-02 14:30", periods=5, freq="B", tz="UTC")
    prices = pd.DataFrame(100, index=dates, columns=["A", "SPY"])
    events = pd.DataFrame(
        {"security_id": ["A"], "accepted_at": [dates[-1]], "directional_signal": [1]}
    )
    assert event_study(events, prices, horizon=2).empty


def test_form4_purchase_is_not_an_option_award():
    xml = b"""<ownershipDocument><issuer><issuerCik>123</issuerCik></issuer><reportingOwner><reportingOwnerId><rptOwnerCik>555</rptOwnerCik></reportingOwnerId></reportingOwner><nonDerivativeTable><nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionDate><value>2020-01-01</value></transactionDate><transactionAmounts><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>10</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction><nonDerivativeTransaction><transactionCoding><transactionCode>A</transactionCode></transactionCoding></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
    result = parse_form4(xml, "2020-01-02T21:00:00Z")
    assert len(result) == 1 and result.dollars.iloc[0] == 1000
    assert result.derivative_transaction.eq(False).all()


def test_insider_cluster_counts_distinct_owners_by_publication_not_transaction_date():
    rows = pd.DataFrame(
        {
            "cik": ["123"] * 3,
            "accepted_at": ["2020-01-01T20:00:00Z", "2020-01-02T20:00:00Z", "2020-02-01T20:00:00Z"],
            "code": ["P"] * 3,
            "owner_cik": ["a", "a", "b"],
            "dollars": [100.0, 200.0, 500.0],
        }
    )
    result = insider_cluster(rows, "2020-01-10T20:00:00Z")
    assert result.distinct_buyers.iloc[0] == 1
    assert result.purchase_dollars.iloc[0] == 300


def test_missing_or_mismatched_accounting_periods_never_become_zero():
    facts = pd.DataFrame(
        [
            {
                "cik": "0000000123",
                "tag": "Assets",
                "unit": "USD",
                "start": pd.NaT,
                "end": pd.Timestamp("2019-12-31"),
                "value": 100,
                "accession": "a",
                "accepted_at": pd.Timestamp("2020-01-01T20:00:00Z"),
            }
        ]
    )
    result = accounting_features(facts, "2020-02-01T20:00:00Z", "123")
    assert np.isnan(result["profitability"])
