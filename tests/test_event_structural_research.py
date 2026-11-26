import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader import event_structural_research as study
from fundamental_event_trader.sec import DataGateError


@pytest.fixture
def facts():
    return pd.DataFrame({"ticker": "TEST", "date": ["2023-02-01", "2024-02-01"],
        "reportperiod": ["2022-12-31", "2023-12-31"], "source_sha256": "0" * 64,
        "assets": 100., "receivables": [10., 9.], "inventory": [10., 9.],
        "revenue": [100., 110.], "debt": [40., 30.], "cashneq": [10., 20.],
        "ncfo": 30., "ncfcommon": -8., "netinc": 10.})


def second(out):
    return out[out.filing_date.eq("2024-02-01")].set_index("family")


def test_new_information_rules_require_real_inputs_and_prior_year(facts):
    out = study.structural_features(facts)
    assert out[out.filing_date.eq("2023-02-01")].feature_status.eq("left_censored_prior_year_missing").all()
    assert second(out).selected.all()
    assert set(second(out).prior_publication_date) == {"2023-02-01"}
    assert "accepted_at" not in out
    with pytest.raises(DataGateError, match="New accounting fields"):
        study.structural_features(facts.drop(columns="inventory"))


@pytest.mark.parametrize("column,value,family", [
    ("inventory", 100., "working_capital_repair"),
    ("revenue", 99., "working_capital_repair"),
    ("debt", 50., "self_funded_repurchase"),
    ("ncfo", 5., "self_funded_repurchase"),
    ("ncfcommon", 8., "self_funded_repurchase"),
    ("cashneq", 0., "liquidity_repair"),
    ("debt", 45., "liquidity_repair"),
    ("ncfo", -1., "liquidity_repair"),
])
def test_economic_failure_conditions_do_not_trigger(facts, column, value, family):
    facts.loc[1, column] = value
    assert not second(study.structural_features(facts)).loc[family, "selected"]


def test_missing_inventory_does_not_disable_unrelated_funding_rule(facts):
    facts.loc[1, "inventory"] = np.nan
    out = second(study.structural_features(facts))
    assert out.loc["working_capital_repair", "feature_status"] == "missing_or_nonpositive_required_accounting_input"
    assert out.loc["self_funded_repurchase", "selected"]
    assert out.loc["liquidity_repair", "selected"]


def test_bank_exclusion_is_explicit_not_silently_dropped(facts):
    facts["ticker"] = "JPM"
    out = study.structural_features(facts)
    assert len(out) == 6
    assert out.feature_status.eq("bank_accounting_excluded_before_returns").all()
    assert not out.selected.any()


def test_new_future_filing_cannot_rewrite_prior_feature(facts):
    original = second(study.structural_features(facts))
    later = facts.iloc[:1].copy()
    later["date"] = "2024-03-01"
    later["cashneq"] = 1000.
    after = second(study.structural_features(pd.concat([facts, later], ignore_index=True)))
    pd.testing.assert_frame_equal(original, after)


def test_repeated_period_does_not_create_fresh_event(facts):
    later = facts.iloc[1:].copy()
    later["date"] = "2024-03-01"
    out = study.structural_features(pd.concat([facts, later], ignore_index=True))
    repeat = out[out.filing_date.eq("2024-03-01")]
    assert repeat.feature_status.eq("repeated_period_excluded").all()
    assert not repeat.selected.any()


def test_negative_accounting_stock_requires_source_review(facts):
    facts.loc[1, "debt"] = -1.
    with pytest.raises(DataGateError, match="Negative accounting"):
        study.structural_features(facts)


def test_registry_does_not_search_thresholds_or_combine_failed_families():
    specs = study.specs()
    assert len(specs) == 13
    assert sum(row["role"] == "candidate" for row in specs) == 6
    assert {row["horizon"] for row in specs if row["role"] == "candidate"} == {63, 126}
    assert sum(row["role"] == "holding_life_falsification" for row in specs) == 3
    assert all(not row.get("price_gate") for row in specs)
