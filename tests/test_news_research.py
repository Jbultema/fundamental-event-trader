from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.news_io import Reader
from fundamental_event_trader.news_research import (
    ASSETS,
    aligned_features,
    parse_source,
    policies,
    risk_state,
    weekly_targets,
)
from fundamental_event_trader.sec import DataGateError


def test_registry_has_unique_fixed_policies_and_no_individual_stock_universe():
    specs = policies()
    assert len(specs) == len({p["id"] for p in specs}) == 68
    assert set(ASSETS) == {"SPY", "QQQ", "SHY", "IEF", "GLD", "XLK", "XLY", "XLI", "XLF", "XLP", "XLV", "XLU"}


@pytest.mark.parametrize("raw", [b"date,Daily news sentiment\n01/01/2020,0.1\n01/01/2020,0.2\n",
                               b"date,Daily news sentiment\n01/01/2020,inf\n",
                               b"wrong,columns\n2020-01-01,0.1\n"])
def test_bad_sentiment_source_rejected(raw):
    with pytest.raises((DataGateError, ValueError)):
        parse_source("sentiment", raw)


def test_source_parsers():
    s = parse_source("sentiment", b"date,Daily news sentiment\n01/02/2020,-0.1\n")
    u = parse_source("uncertainty", b"day,month,year,daily_policy_index\n2,1,2020,10\n")
    assert s.index[0] == u.index[0] == pd.Timestamp("2020-01-02")
    assert s.iloc[0] == -.1 and u.iloc[0] == 10


def test_release_lag_and_future_mutations_do_not_change_earlier_features(tmp_path: Path):
    index = pd.date_range("2017-01-01", "2020-12-31")
    s = pd.Series(np.sin(np.arange(len(index)) / 21), index=index, name="sentiment")
    s.to_frame().to_parquet(tmp_path / "sentiment.parquet")
    dates = pd.bdate_range("2020-01-06", "2020-01-10")
    a = aligned_features(tmp_path, dates, 14)
    assert (pd.to_datetime(a.sentiment_observation_date) < dates - pd.Timedelta(days=14)).all()
    assert (pd.to_datetime(a.sentiment_assumed_available_at) <= dates.tz_localize("UTC") + pd.Timedelta(hours=21)).all()
    s.loc["2020-01-01":] = 1000
    s.to_frame().to_parquet(tmp_path / "sentiment.parquet")
    b = aligned_features(tmp_path, dates, 14)
    pd.testing.assert_frame_equal(a, b)


def test_missing_source_is_not_neutral_signal():
    index = pd.bdate_range("2020-01-01", periods=10)
    prices = pd.DataFrame(100., index=index, columns=ASSETS)
    state = risk_state(pd.DataFrame(index=index), prices, "dual_warning")
    assert state.isna().all()


def test_targets_wait_for_week_and_missing_news_reverts_to_control():
    index = pd.bdate_range("2020-01-06", periods=10)
    prices = pd.DataFrame(100., index=index, columns=ASSETS)
    state = pd.Series([1, 0, 0, 0, 0, np.nan, 0, 0, 0, 0], index=index)
    spec = {"kind": "risk_budget", "risk_asset": "SPY", "floor": .5}
    w = weekly_targets(prices, state, spec)
    assert w.SPY.eq(1.).all()
    assert w.sum(axis=1).eq(1).all()


def test_sector_targets_are_long_only_unlevered_and_prefix_causal():
    index = pd.bdate_range("2020-01-06", periods=20)
    prices = pd.DataFrame(100., index=index, columns=ASSETS)
    state = pd.Series(np.where(np.arange(20) < 10, 0., 1.), index=index)
    spec = {"kind": "sector_rotation"}
    full = weekly_targets(prices, state, spec)
    short = weekly_targets(prices.iloc[:12], state.iloc[:12], spec)
    pd.testing.assert_frame_equal(full.iloc[:12], short)
    assert (full >= 0).all().all() and np.allclose(full.sum(axis=1), 1)


def test_unregistered_lag_rejected(tmp_path):
    with pytest.raises(DataGateError):
        aligned_features(tmp_path, pd.bdate_range("2020-01-06", periods=5), 0)


@pytest.mark.parametrize("timeout", [0, -1, True, 61, float("nan"), "30"])
def test_historical_request_timeout_remains_bounded(tmp_path, timeout):
    with pytest.raises(DataGateError):
        Reader(tmp_path, request_timeout=timeout)
