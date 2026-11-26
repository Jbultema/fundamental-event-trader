import json

import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.news_vintage_audit import audit
from fundamental_event_trader.news_vintage_research import features, parse_vintage
from fundamental_event_trader.sec import DataGateError, sha


def make_screen(root, mutation):
    root.mkdir()
    (root / "sources/raw").mkdir(parents=True)
    (root / "targets").mkdir()
    dates = pd.date_range("2017-01-01", "2019-01-15")
    raw = pd.DataFrame({"observation_date": dates.strftime("%Y-%m-%d"),
                        "USEPUINDXD_20190115": 100 + np.sin(np.arange(len(dates)) / 20) * 10}).to_csv(index=False).encode()
    raw_file = root / "sources/raw/release.csv"
    raw_file.write_bytes(raw)
    f = features(parse_vintage(raw, "2019-01-15"))
    row = {"vintage": "2019-01-15", "assumed_available_at": "2019-01-17T00:00:00+00:00",
           "vintage_sha256": sha(raw_file), **f}
    if mutation == "feature":
        row["z"] += 1
    pd.DataFrame([row]).to_parquet(root / "vintage_features.parquet", index=False)
    policy = {"id": "test_SPY", "rule": "price_confirms", "risk_asset": "SPY", "floor": 0.}
    registry = {"source_definitions": {"uncertainty": {"vintages": ["2019-01-15"]}}, "policies": [policy]}
    (root / "registry.json").write_text(json.dumps(registry))
    source_date = "2020-01-15" if mutation == "source" else "2019-01-15"
    acquisition = {"requests": [{"sha256": sha(raw_file), "path": "raw/release.csv", "http_status": 200,
                                 "url": f"https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=USEPUINDXD&vintage_date={source_date}"}]}
    (root / "sources/acquisition.json").write_text(json.dumps(acquisition))
    index = pd.bdate_range("2019-01-14", "2019-01-18")
    prices = pd.DataFrame({"SPY": 100., "SHY": 100.}, index=index)
    prices.to_parquet(root / "prices.parquet")
    from fundamental_event_trader.news_vintage_research import state

    budget = pd.Series(1., index=index)
    budget.loc["2019-01-17":] = state(policy["rule"], f, False)
    if mutation == "early_target":
        budget.iloc[0] = 0
    pd.DataFrame({"SPY": budget, "SHY": 1 - budget}).to_parquet(root / "targets/test_SPY_lag0.parquet")
    (root / "manifest.json").write_text(json.dumps({"artifacts": {
        str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}}))


@pytest.mark.parametrize("mutation", [None, "source", "feature", "early_target"])
def test_released_vintage_reconstruction_detects_consistent_but_false_metadata(tmp_path, mutation):
    root = tmp_path / "fixture_only"
    make_screen(root, mutation)
    if mutation is None:
        result = audit(root, tmp_path / "audit.json")
        assert result["verified_vintages"] == 1
        assert result["rss_article_strategy_qualified"] is False
    else:
        with pytest.raises(DataGateError):
            audit(root, tmp_path / "audit.json")
