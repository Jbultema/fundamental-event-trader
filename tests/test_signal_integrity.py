import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.archive import annual_events
from fundamental_event_trader.features import accounting_features, insider_cluster, parse_form4
from fundamental_event_trader.sec import DataGateError


def annual_source(*, amendment=None, later_period=False):
    filings, rows = [], []

    def append(accession, accepted, fiscal_year, income, cash):
        filings.append({"accession": accession, "accepted_at": pd.Timestamp(accepted),
                        "form": "10-K" if len(filings) == 0 or fiscal_year == 2021 else "10-K/A",
                        "report_date": f"{fiscal_year}-12-31"})
        for year, earnings, flow in ((fiscal_year - 1, 10., 15.), (fiscal_year, income, cash)):
            for tag, value in (("Assets", 100.), ("NetIncomeLoss", earnings),
                               ("NetCashProvidedByUsedInOperatingActivities", flow),
                               ("PaymentsForRepurchaseOfCommonStock", 3.),
                               ("ProceedsFromIssuanceOfCommonStock", 1.)):
                rows.append({"cik": "0000000123", "tag": tag, "unit": "USD",
                             "start": pd.NaT if tag == "Assets" else pd.Timestamp(f"{year}-01-01"),
                             "end": pd.Timestamp(f"{year}-12-31"), "value": value,
                             "accession": accession, "accepted_at": pd.Timestamp(accepted)})

    append("0000000123-21-000001", "2021-02-01T22:00Z", 2020, 20., 25.)
    if amendment is not None:
        append("0000000123-21-000002", "2021-03-01T22:00Z", 2020,
               30. if amendment == "changed" else 20., 35. if amendment == "changed" else 25.)
        if amendment == "no_facts":
            rows = [row for row in rows if row["accession"] != "0000000123-21-000002"]
    if later_period:
        append("0000000123-22-000001", "2022-02-01T22:00Z", 2021, 40., 45.)
        append("0000000123-22-000002", "2022-04-01T22:00Z", 2020, 60., 65.)
    return pd.DataFrame(rows), pd.DataFrame(filings)


@pytest.mark.parametrize("amendment", ["no_facts", "identical"])
def test_amendment_cannot_refresh_old_annual_evidence(amendment):
    facts, filings = annual_source(amendment=amendment)
    events = annual_events(facts, filings, "123", "a" * 64)
    assert len(events) == 1
    assert events.available_at.iloc[0] == pd.Timestamp("2021-02-01T22:00Z")
    assert events.profitability_change.iloc[0] == pytest.approx(.1)


def test_restatement_compares_to_prior_year_not_previous_filing():
    facts, filings = annual_source(amendment="changed")
    events = annual_events(facts, filings, "123", "a" * 64)
    assert len(events) == 2
    assert events.profitability_change.tolist() == pytest.approx([.1, .2])
    assert events.available_at.iloc[-1] == pd.Timestamp("2021-03-01T22:00Z")


def test_old_year_amendment_does_not_become_latest_annual_signal():
    facts, filings = annual_source(later_period=True)
    events = annual_events(facts, filings, "123", "a" * 64)
    assert events.fiscal_period_end.tolist() == ["2020-12-31", "2021-12-31"]


def test_matching_year_end_is_not_enough_for_mismatched_duration_ratios():
    facts, _ = annual_source()
    facts.loc[facts.tag.eq("NetCashProvidedByUsedInOperatingActivities"), "start"] -= pd.Timedelta(days=20)
    result = accounting_features(facts, "2021-03-01T22:00Z", "123", period_end="2020-12-31")
    assert np.isnan(result["cash_conversion"])
    assert result["net_repurchase"] == pytest.approx(.02)


def form4(owner="555", date="2020-01-01", extra_owner=""):
    return f"""<ownershipDocument><issuer><issuerCik>123</issuerCik></issuer>
    <reportingOwner><reportingOwnerId><rptOwnerCik>{owner}</rptOwnerCik></reportingOwnerId></reportingOwner>{extra_owner}
    <nonDerivativeTable><nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding>
    <transactionDate><value>{date}</value></transactionDate><transactionAmounts><transactionShares><value>100</value></transactionShares>
    <transactionPricePerShare><value>10</value></transactionPricePerShare></transactionAmounts>
    </nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>""".encode()


@pytest.mark.parametrize("kwargs", [{"owner": ""}, {"owner": "0"}, {"date": "2021-01-01"},
                                    {"extra_owner": "<reportingOwner><reportingOwnerId><rptOwnerCik>666</rptOwnerCik></reportingOwnerId></reportingOwner>"}])
def test_ambiguous_owner_or_future_transaction_is_not_insider_evidence(kwargs):
    with pytest.raises(DataGateError):
        parse_form4(form4(**kwargs), "2020-01-02T22:00Z")


def test_form4_purchase_code_does_not_prove_exchange_open_market_execution():
    parsed = parse_form4(form4(), "2020-01-02T22:00Z")
    assert parsed.purchase_scope.iloc[0] == "open_market_or_private"
    assert parsed.owner_cik.iloc[0] == "0000000555"


def test_zero_cost_or_derivative_transactions_cannot_inflate_buyer_count():
    rows = pd.DataFrame({"cik": "123", "owner_cik": ["555", "666", "777"],
                         "accepted_at": "2020-01-02T22:00Z", "code": "P",
                         "dollars": [100., 0., 100.], "derivative_transaction": [False, False, True]})
    result = insider_cluster(rows, "2020-01-03T22:00Z")
    assert result.distinct_buyers.iloc[0] == 1
    assert result.purchase_dollars.iloc[0] == 100.
    assert insider_cluster(rows.assign(dollars=0.), "2020-01-03T22:00Z").empty
