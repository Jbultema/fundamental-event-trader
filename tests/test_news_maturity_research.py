import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.news_maturity_research import freeze, transform
from fundamental_event_trader.sec import DataGateError


@pytest.mark.parametrize("mode,days", [("mature7", 7), ("mature14", 14)])
def test_maturity_never_uses_provisional_recent_observations(mode, days):
    index = pd.date_range("2019-01-01", "2019-03-01")
    s = pd.Series(np.arange(len(index)), index=index)
    result = transform(s, "2019-02-28", mode)
    assert result.index.max() == pd.Timestamp("2019-02-28") - pd.Timedelta(days=days)


def test_trailing_news_average_is_prefix_causal():
    index = pd.date_range("2019-01-01", "2019-03-01")
    s = pd.Series(np.arange(len(index)), index=index, dtype=float)
    first = transform(s, "2019-03-01", "mean7")
    s.loc["2019-02-01":] = 10000
    second = transform(s, "2019-03-01", "mean7")
    pd.testing.assert_series_equal(first.loc[:"2019-01-31"], second.loc[:"2019-01-31"])


def test_unregistered_maturity_transform_rejected():
    with pytest.raises(DataGateError):
        transform(pd.Series(dtype=float), "2019-01-01", "pick_best_day")


def test_maturity_requires_sealed_parent_before_freezing(tmp_path):
    with pytest.raises(DataGateError):
        freeze(tmp_path / "missing", tmp_path / "output")
