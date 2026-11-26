import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.portfolio import metrics, replay
from fundamental_event_trader.sec import DataGateError


@pytest.fixture
def market():
    cal = xcals.get_calendar("XNYS")
    dates = cal.sessions_in_range("2020-01-02", "2020-03-02")
    index = pd.DatetimeIndex([cal.session_open(day) for day in dates])
    opens = pd.DataFrame(100.0, index=index, columns=["A", "SPY"])
    closes = opens.copy()
    target = opens * 0.0
    cash = pd.Series(0.0, index=index)
    return opens, closes, target, cash


def test_next_open_fill_does_not_earn_the_signal_days_return(market):
    opens, closes, target, cash = market
    closes.iloc[0, 0] = 150.0
    opens.iloc[1, 0] = 200.0
    closes.iloc[1:, 0] = 220.0
    opens.iloc[2:, 0] = 220.0
    target.A = 1.0
    result = replay(opens, closes, target, cash, cost_bps=0.0)
    assert result.equity.iloc[0] == 1.0
    assert result.equity.iloc[-1] == pytest.approx(1.1)
    assert result.fills.iloc[0].session == opens.index[1]


def test_previous_holdings_bear_overnight_gap_and_intraday_loss(market):
    opens, closes, target, cash = market
    target.A = 1.0
    opens.iloc[2:, 0] = 80.0
    closes.iloc[2:, 0] = 70.0
    target.iloc[1:, 0] = 0.0
    result = replay(opens, closes, target, cash, cost_bps=0.0)
    assert result.equity.iloc[-1] == pytest.approx(0.8)


def test_costs_are_funded_from_nav_without_daily_rebalancing(market):
    opens, closes, target, cash = market
    target.A = 0.5
    result = replay(opens, closes, target, cash, cost_bps=10.0)
    assert result.equity.iloc[-1] == pytest.approx(1 / 1.0005)
    assert len(result.fills) == 1
    assert (result.cash >= 0).all()
    assert np.allclose(result.cash + result.weights.sum(axis=1), 1.0)


def test_cash_invested_at_open_does_not_also_earn_intraday_interest(market):
    from fundamental_event_trader.strategy import session_schedule

    opens, closes, target, cash = market
    target.A = 1.0
    cash[:] = 0.01
    schedule = session_schedule(opens.index)
    fraction = (opens.index[1] - schedule.close.iloc[0]) / (
        schedule.close.iloc[1] - schedule.close.iloc[0]
    )
    result = replay(opens, closes, target, cash, cost_bps=0.0)
    assert result.equity.iloc[-1] == pytest.approx(1.01 ** (1 + fraction))
    all_cash = replay(opens, closes, target * 0.0, cash, cost_bps=0.0)
    assert all_cash.equity.iloc[-1] == pytest.approx(1.01 ** len(opens))


def test_initial_loss_counts_in_maximum_drawdown(market):
    opens, closes, target, cash = market
    target.A = 1.0
    result = replay(opens, closes, target, cash, cost_bps=100.0)
    assert metrics(result)["max_drawdown"] == pytest.approx(1 / 1.01 - 1)


def test_bankruptcy_settlement_is_a_loss_not_a_free_cash_exit(market):
    opens, closes, target, cash = market
    target.A = 0.5
    opens.iloc[2:, 0] = np.nan
    closes.iloc[2:, 0] = np.nan
    terminal = pd.DataFrame(
        {"security_id": ["A"], "settlement_at": [opens.index[2]], "value_per_adjusted_share": [0.0]}
    )
    result = replay(opens, closes, target, cash, cost_bps=0.0, terminal_events=terminal)
    assert result.equity.iloc[-1] == pytest.approx(0.5)
    assert result.weights.A.iloc[-1] == 0.0
    assert result.fills.kind.eq("terminal_settlement").sum() == 1


def test_delisting_cash_recovery_is_explicit(market):
    opens, closes, target, cash = market
    target.A = 0.5
    opens.iloc[2:, 0] = np.nan
    closes.iloc[2:, 0] = np.nan
    terminal = pd.DataFrame(
        {
            "security_id": ["A"],
            "settlement_at": [opens.index[2]],
            "value_per_adjusted_share": [40.0],
        }
    )
    result = replay(opens, closes, target, cash, cost_bps=0.0, terminal_events=terminal)
    assert result.equity.iloc[-1] == pytest.approx(0.7)


def test_intraday_terminal_cash_cannot_fund_a_trade_at_the_prior_open(market):
    opens, closes, target, cash = market
    target.A = 0.5
    target.loc[target.index[2:], "SPY"] = 0.5
    closes.iloc[2:, 0] = np.nan
    opens.iloc[3:, 0] = np.nan
    terminal = pd.DataFrame(
        {
            "security_id": ["A"],
            "settlement_at": [opens.index[2] + pd.Timedelta(hours=2)],
            "value_per_adjusted_share": [40.0],
        }
    )
    result = replay(opens, closes, target, cash, cost_bps=0.0, terminal_events=terminal)
    assert result.equity.iloc[2] == pytest.approx(0.7)
    assert result.weights.SPY.iloc[2] == 0.0


def test_total_bankruptcy_stays_zero_without_recapitalizing(market):
    opens, closes, target, cash = market
    target.A = 1.0
    opens.iloc[2:, 0] = np.nan
    closes.iloc[2:, 0] = np.nan
    terminal = pd.DataFrame(
        {"security_id": ["A"], "settlement_at": [opens.index[2]], "value_per_adjusted_share": [0.0]}
    )
    result = replay(opens, closes, target, cash, cost_bps=0.0, terminal_events=terminal)
    assert result.returns.iloc[2] == -1.0
    assert result.equity.iloc[-1] == 0.0
    assert metrics(result)["max_drawdown"] == -1.0


def test_missing_held_price_fails_instead_of_substituting_a_survivor(market):
    opens, closes, target, cash = market
    target.A = 0.5
    opens.iloc[2, 0] = np.nan
    with pytest.raises(DataGateError, match="Unpriced overnight"):
        replay(opens, closes, target, cash)


def test_prefix_returns_do_not_change_when_future_prices_change(market):
    opens, closes, target, cash = market
    target.A = 0.5
    original = replay(opens, closes, target, cash)
    opens.iloc[20:, 0] *= 0.5
    closes.iloc[20:, 0] *= 0.4
    changed = replay(opens, closes, target, cash)
    pd.testing.assert_series_equal(original.returns.iloc[:20], changed.returns.iloc[:20])


@pytest.mark.parametrize("lag,cost", [(0, 10.0), (True, 10.0), (1, -1.0), (1, np.inf)])
def test_invalid_execution_parameters(market, lag, cost):
    with pytest.raises(DataGateError):
        replay(*market, lag=lag, cost_bps=cost)


def test_missing_exchange_session_is_not_a_zero_return(market):
    opens, closes, target, cash = market
    dates = opens.index.delete(3)
    with pytest.raises(DataGateError, match="every actual NYSE"):
        replay(opens.loc[dates], closes.loc[dates], target.loc[dates], cash.loc[dates])
