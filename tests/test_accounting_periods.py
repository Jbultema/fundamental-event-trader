import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.features import accounting_features


def facts(observations):
    return pd.DataFrame(
        [
            {
                "cik": "0000000123",
                "tag": tag,
                "unit": "USD",
                "start": pd.Timestamp(start) if start else pd.NaT,
                "end": pd.Timestamp(end),
                "value": value,
                "accession": f"known-{i}",
                "accepted_at": pd.Timestamp("2022-01-01T20:00:00Z"),
            }
            for i, (tag, start, end, value) in enumerate(observations)
        ]
    )


def test_annual_profitability_uses_matching_annual_assets_not_latest_quarter():
    table = facts(
        [
            ("Assets", None, "2020-12-31", 100),
            ("Assets", None, "2021-09-30", 200),
            ("NetIncomeLoss", "2020-01-01", "2020-12-31", 20),
        ]
    )
    result = accounting_features(table, "2022-01-02T20:00:00Z", "123")
    assert result["profitability"] == pytest.approx(0.2)
    assert result["profitability_period_end"] == "2020-12-31"


def test_different_year_cashflow_is_not_subtracted_from_latest_income():
    table = facts(
        [
            ("Assets", None, "2020-12-31", 100),
            ("Assets", None, "2021-12-31", 100),
            ("NetIncomeLoss", "2021-01-01", "2021-12-31", 20),
            ("NetCashProvidedByUsedInOperatingActivities", "2020-01-01", "2020-12-31", 30),
        ]
    )
    assert np.isnan(accounting_features(table, "2022-01-02T20:00:00Z", "123")["cash_conversion"])


def test_option_exercise_proceeds_are_not_an_alias_for_total_common_issuance():
    table = facts(
        [
            ("Assets", None, "2021-12-31", 100),
            ("PaymentsForRepurchaseOfCommonStock", "2021-01-01", "2021-12-31", 5),
            ("ProceedsFromStockOptionsExercised", "2021-01-01", "2021-12-31", 1),
            ("ProceedsFromIssuanceOfCommonStock", "2021-01-01", "2021-12-31", 2),
        ]
    )
    assert accounting_features(table, "2022-01-02T20:00:00Z", "123")[
        "net_repurchase"
    ] == pytest.approx(0.03)


def test_revenue_accounting_tag_change_is_not_growth_evidence():
    table = facts(
        [
            ("Revenues", "2020-01-01", "2020-12-31", 100),
            (
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "2021-01-01",
                "2021-12-31",
                150,
            ),
        ]
    )
    assert np.isnan(accounting_features(table, "2022-01-02T20:00:00Z", "123")["revenue_growth"])
