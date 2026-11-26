"""Predeclared source-maturity follow-up, using only already released histories."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fundamental_event_trader.news_research import _write, parse_source
from fundamental_event_trader.news_vintage_research import features, parse_vintage, state
from fundamental_event_trader.sec import DataGateError, sha

TRANSFORMS = ("mature7", "mature14", "mean7")
RULES = ("z1", "z15", "improving21", "price_confirms")


def transform(series, vintage, mode):
    if mode == "mature7":
        return series.loc[:pd.Timestamp(vintage) - pd.Timedelta(days=7)]
    if mode == "mature14":
        return series.loc[:pd.Timestamp(vintage) - pd.Timedelta(days=14)]
    if mode == "mean7":
        return series.rolling("7D", min_periods=5).mean().dropna()
    raise DataGateError("Unregistered news-maturity transform")


def freeze(parent: Path, output: Path):
    if not (parent / "manifest.json").is_file():
        raise DataGateError("Sealed released-vintage parent required")
    registry = json.loads((parent / "registry.json").read_text())
    registry["frozen_at_utc"] = datetime.now(UTC).isoformat()
    registry["study"] = "released_news_observation_maturity_followup"
    registry["parent_screen"] = str(parent.resolve())
    registry["parent_manifest_sha256"] = sha(parent / "manifest.json")
    registry["followup_reason"] = "Material provisional latest-observation revisions; fixed maturity/averaging transforms, no threshold optimization"
    registry["policies"] = [{"id": f"epu_{mode}_{rule}_{asset}_floor50", "transform": mode, "rule": rule,
                             "risk_asset": asset, "floor": .5, "kind": "risk_budget"}
                            for mode in TRANSFORMS for rule in RULES for asset in ("SPY", "QQQ")]
    registry["limitations"] += ["Source-quality follow-up prompted by revision audit; not an independent discovery or new untouched holdout."]
    output.mkdir(exist_ok=False, parents=True)
    _write(output / "registry.json", registry)
    return output / "registry.json"


def build(registry_path: Path):
    root = registry_path.parent
    initial = sha(Path(__file__))
    registry = json.loads(registry_path.read_text())
    parent = Path(registry["parent_screen"])
    meta = json.loads((parent / "manifest.json").read_text())
    if sha(parent / "manifest.json") != registry["parent_manifest_sha256"]:
        raise DataGateError("Released-vintage parent changed")
    for name, expected in meta["artifacts"].items():
        file = (parent / name).resolve()
        if not file.is_relative_to(parent.resolve()) or sha(file) != expected:
            raise DataGateError("Historical source artifact changed")
    if (root / "manifest.json").exists():
        raise DataGateError("Maturity study already sealed")
    shutil.copytree(parent / "sources", root / "sources")
    for name in ("prices.parquet", "vintage_features.parquet"):
        shutil.copyfile(parent / name, root / name)
    (root / "generator.py.source.txt").write_bytes(Path(__file__).read_bytes())
    prices = pd.read_parquet(root / "prices.parquet")
    vintages = pd.read_parquet(root / "vintage_features.parquet")
    acquisition = json.loads((root / "sources/acquisition.json").read_text())
    requests = {r["sha256"]: r for r in acquisition["requests"] if r.get("http_status") == 200}
    latest_request = next(r for r in reversed(acquisition["requests"])
                          if r.get("http_status") == 200 and r["url"] == "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv")
    latest = parse_source("uncertainty", (root / "sources" / latest_request["path"]).read_bytes())
    cache = {}
    for mode in (0, 1):
        for method in TRANSFORMS:
            rows = []
            for row in vintages.to_dict("records"):
                request = requests[row["vintage_sha256"]]
                series = (parse_vintage((root / "sources" / request["path"]).read_bytes(), row["vintage"], allow_stale=True)
                          if mode == 0 else latest.loc[:row["last_observation"]])
                f = features(transform(series, row["vintage"], method))
                cache[(mode, method, row["vintage"])] = f
                rows.append({"vintage": row["vintage"], "data_status": row["data_status"], **f})
            pd.DataFrame(rows).to_parquet(root / f"features_mode{mode}_{method}.parquet", index=False)
    target_dir = root / "targets"
    target_dir.mkdir()
    trend = prices.SPY.ge(prices.SPY.rolling(200).mean())
    statuses = []
    for mode in (0, 1):
        for policy in registry["policies"]:
            values = pd.Series(np.nan, index=prices.index)
            for row in vintages.to_dict("records"):
                if row["data_status"] != "fresh":
                    continue
                available = pd.Timestamp(row["assumed_available_at"]).tz_convert(None).normalize()
                i = prices.index.searchsorted(available)
                if i < len(prices):
                    f = cache[(mode, policy["transform"], row["vintage"])]
                    values.iloc[i] = state(policy["rule"], f, bool(trend.iloc[i]))
            budget = .5 + .5 * values.ffill().fillna(1.)
            w = prices * 0.
            w[policy["risk_asset"]], w["SHY"] = budget, 1 - budget
            w.to_parquet(target_dir / f"{policy['id']}_lag{mode}.parquet")
            statuses.append({"id": policy["id"], "publication_lag": mode, "status": "historical_vintage_maturity_screen", "coverage": 1.})
    _write(root / "status.json", statuses)
    if sha(Path(__file__)) != initial:
        raise DataGateError("Maturity generator changed during execution")
    _write(root / "manifest.json", {"kind": "news_proxy_etf_screen", "authority": "research_only", "action_authorized": False,
                                    "point_in_time_qualified": False, "rss_strategy_backtest": False,
                                    "uses_historical_released_vintages": True, "generator_sha256": initial,
                                    "registry_sha256": sha(registry_path), "parent_manifest_sha256": registry["parent_manifest_sha256"],
                                    "artifacts": {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}})
    return root
