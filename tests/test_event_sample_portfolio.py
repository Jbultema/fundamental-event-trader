import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader import event_sample_portfolio as study
from fundamental_event_trader.event_sample_pilot import FAMILIES, delayed_date_cutoff
from fundamental_event_trader.portfolio import metrics, replay
from fundamental_event_trader.sec import DataGateError
from fundamental_event_trader.strategy import session_schedule


@pytest.fixture
def market():
    cal = xcals.get_calendar("XNYS", start="2022-12-20", end="2025-01-10")
    days = cal.sessions_in_range("2023-01-03", "2024-12-31")
    index = pd.DatetimeIndex([cal.session_open(d) for d in days])
    prices = pd.DataFrame({"A": np.linspace(100., 150., len(index)), "B": 100.}, index=index)
    event = pd.DataFrame({"ticker": ["A", "A", "B"],
        "filing_date": ["2023-06-01", "2023-06-15", "2023-06-01"],
        "reportperiod": ["2023-03-31", "2023-03-31", "2023-03-31"],
        "date_only_available_after": [delayed_date_cutoff(v) for v in ["2023-06-01", "2023-06-15", "2023-06-01"]],
        "family": FAMILIES[0], "selected": [True, False, False],
        "feature_status": ["observed", "observed", "left_censored_prior_year_missing"]})
    return prices, event


def spec(horizon=21, price_gate=False):
    return {"name": "candidate", "family": FAMILIES[0], "horizon": horizon, "price_gate": price_gate}


def test_registry_has_fixed_candidates_and_separate_falsifiers():
    specs = study.specifications()
    assert sum(s["role"] == "candidate" for s in specs) == 12
    assert sum(s["role"] == "falsification" for s in specs) == 2
    assert len(specs) == 18
    assert len({s["name"] for s in specs}) == 18
    assert not any("combined_family" in s["name"] for s in specs)


def test_targets_wait_for_actual_close_after_availability_and_expire(market):
    prices, events = market
    target = study.policy_targets(events, prices, spec())
    schedule = session_schedule(prices.index)
    first = schedule.close.searchsorted(events.iloc[0].date_only_available_after)
    assert target.A.iloc[:first].eq(0).all()
    assert target.A.iloc[first:first + 21].eq(.5).all()
    assert target.A.iloc[first + 21:].eq(0).all()
    assert target.B.eq(0).all()
    assert target.sum(axis=1).le(1).all()
    for lag in (1, 2, 5):
        result = replay(prices, prices, target, pd.Series(0., index=prices.index), lag=lag, cost_bps=0.)
        assert result.fills.iloc[0].session == prices.index[first + lag]
        assert result.fills.iloc[0].session > events.iloc[0].date_only_available_after
        assert result.fills.iloc[-1].session == prices.index[first + 21 + lag]


def test_repeated_positive_refreshes_but_negative_does_not(market):
    prices, events = market
    one = study.policy_targets(events, prices, spec())
    positive = events.copy()
    positive.loc[1, "selected"] = True
    refreshed = study.policy_targets(positive, prices, spec())
    assert refreshed.A.sum() > one.A.sum()
    assert one.A.sum() == pytest.approx(21 * .5)


def test_opposite_signal_excludes_missing_comparisons(market):
    prices, events = market
    inverted = spec() | {"opposite": True}
    target = study.policy_targets(events, prices, inverted)
    assert target.A.gt(0).any()
    assert target.B.eq(0).all()


def test_future_events_and_prices_cannot_rewrite_prior_allocations(market):
    prices, events = market
    original = study.policy_targets(events, prices, spec(price_gate=True))
    changed_prices = prices.copy()
    changed_prices.iloc[250:, :] *= .1
    future = events.iloc[:1].copy()
    future["date_only_available_after"] = prices.index[300]
    changed = study.policy_targets(pd.concat([events, future]), changed_prices, spec(price_gate=True))
    pd.testing.assert_frame_equal(original.iloc[:250], changed.iloc[:250])


def test_price_confirmation_cannot_borrow_future_warmup(market):
    prices, events = market
    target = study.policy_targets(events, prices, {"name": "price_only_sma126"})
    assert target.iloc[:125].eq(0).all().all()
    assert target.A.iloc[125:].eq(.5).all()
    assert target.B.eq(0).all()


def test_disclosure_control_does_not_require_good_event_label(market):
    prices, events = market
    control = study.policy_targets(events, prices, {"name": "all_disclosures_h63"})
    assert control.B.gt(0).any()


def test_old_events_do_not_receive_fresh_holding_life(market):
    prices, events = market
    events.loc[0, "date_only_available_after"] = pd.Timestamp("2020-01-01", tz="UTC")
    target = study.policy_targets(events, prices, spec())
    assert target.eq(0).all().all()


def test_cash_assumption_compounds_actual_elapsed_time(market):
    prices, _ = market
    cash = study.cash_accrual(prices.index, .04)
    closes = session_schedule(prices.index).close
    years = (closes.iloc[-1] - closes.iloc[0]).total_seconds() / (365.25 * 86400)
    assert (1 + cash).prod() == pytest.approx(1.04 ** years)
    assert study.cash_accrual(prices.index, 0.).eq(0).all()
    with pytest.raises(DataGateError):
        study.cash_accrual(prices.index, -1.)


def test_equal_weight_buy_hold_is_not_daily_rebalanced(market):
    prices, events = market
    target = study.policy_targets(events, prices, {"name": "equal_weight_buy_hold"})
    result = replay(prices, prices, target, pd.Series(0., index=prices.index), cost_bps=0.)
    assert len(result.fills) == 2
    assert result.weights.A.iloc[-1] > .5
    report = study.window_metrics(result, ["2023-01-03", "2023-12-29"])
    assert report == metrics(result, "2023-01-03", "2023-12-29")


def test_bootstrap_preserves_dates_and_identical_controls(market):
    prices, _ = market
    values = prices.A.pct_change().fillna(0.)
    result = study.uncertainty({"A": values}, {"A": values}, reps=100, block=21)[0]
    assert result["annualized_arithmetic_excess"] == 0
    assert result["lower_95"] == 0
    assert result["upper_95"] == 0
    assert result["within_round_max_abs_mean_p"] == 1
    assert result["not_whole_program_selection_corrected"] is True
    with pytest.raises(DataGateError):
        study.uncertainty({"A": values}, {"A": values.iloc[1:]})


def test_frozen_authority_flags_and_tampering_rejected(tmp_path, monkeypatch, market):
    prices, _ = market
    # Exercise the protocol boundary without pretending a fixture is investment data.
    root = tmp_path / "source"
    root.mkdir()
    (root / "protocol.json").write_text("{}")
    (root / "acquisition.json").write_text("{}")
    extended = prices.copy()
    cal = xcals.get_calendar("XNYS", start="2021-12-20", end="2026-01-10")
    days = cal.sessions_in_range("2022-01-03", "2026-01-06")
    index = pd.DatetimeIndex([cal.session_open(d) for d in days])
    extended = pd.DataFrame(100., index=index, columns=["A", "B"])
    monkeypatch.setattr(study, "load_sample", lambda root: ({"roster": ["A", "B"]}, pd.DataFrame(), extended, []))
    output = tmp_path / "result"
    protocol = study.freeze(root, output)
    assert protocol["prior_event_return_results_inspected"] is True
    assert protocol["genuine_untouched_holdout"] is False
    assert protocol["portfolio_allocation_allowed"] is False
    with pytest.raises(FileExistsError):
        study.freeze(root, output)
    protocol["portfolio_allocation_allowed"] = True
    (output / "protocol.json").write_text(json.dumps(protocol))
    with pytest.raises(DataGateError, match="protocol changed"):
        study.run(root, output)
