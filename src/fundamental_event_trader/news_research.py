"""Frozen ETF screening of historical news proxies, never RSS-strategy admission."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from fundamental_event_trader.news_io import Reader
from fundamental_event_trader.sec import DataGateError, sha

SOURCES = {
    "sentiment": {
        "url": "https://www.frbsf.org/wp-content/uploads/news-sentiment-chart-1.csv",
        "host": "www.frbsf.org",
        "description": "SF Fed newspaper-derived daily sentiment, rounded chart CSV; weekly publication",
        "publication_start": "2020-04-14",
    },
    "uncertainty": {
        "url": "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv",
        "host": "www.policyuncertainty.com",
        "description": "Baker/Bloom/Davis daily US newspaper economic-policy uncertainty",
        "publication_start": "2014-03-27",
    },
}
ASSETS = ["SPY", "QQQ", "SHY", "IEF", "GLD", "XLK", "XLY", "XLI", "XLF", "XLP", "XLV", "XLU"]
RULES = [
    "sentiment_level", "sentiment_improving21", "sentiment_improving63",
    "sentiment_shock1", "sentiment_shock15", "sentiment_repair",
    "price_confirms_news", "news_repairs_price", "price_and_news",
    "uncertainty_shock1", "uncertainty_shock15", "uncertainty_improving",
    "dual_warning", "dual_repair", "dual_confirmation", "staged_evidence",
]
CYCLICAL = ["XLK", "XLY", "XLI", "XLF"]
DEFENSIVE = ["XLP", "XLV", "XLU"]


def policies():
    rows = [
        {"id": f"{rule}_{asset}_floor{int(floor * 100)}", "rule": rule,
         "risk_asset": asset, "floor": floor, "kind": "risk_budget"}
        for rule in RULES for asset in ("SPY", "QQQ") for floor in (.0, .5)
    ]
    rows += [{"id": f"sector_{rule}", "rule": rule, "risk_asset": "SPY",
              "floor": 0., "kind": "sector_rotation"}
             for rule in ("sentiment_improving21", "sentiment_repair", "dual_warning", "dual_confirmation")]
    return rows


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def freeze(bundle: Path, output: Path):
    """Seal hypothesis/selection/lag/partition choices without computing performance."""
    meta = json.loads((bundle / "manifest.json").read_text())
    for name in ("prices.parquet", "cash_returns.parquet"):
        if meta["artifacts"][name] != sha(bundle / name):
            raise DataGateError("Input bundle integrity failed")
    output.mkdir(parents=True, exist_ok=False)
    registry = {
        "kind": "news_proxy_etf_screen", "authority": "research_only",
        "action_authorized": False, "rss_strategy_backtest": False,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "bundle": str(bundle.resolve()), "bundle_manifest_sha256": sha(bundle / "manifest.json"),
        "source_definitions": SOURCES, "policies": policies(), "assets": ASSETS,
        "partitions": {"development": ["2006-01-01", "2014-12-31"],
                       "validation": ["2015-01-01", "2021-12-31"],
                       "holdout_diagnostic": ["2022-01-01", "2026-11-25"]},
        "warmup_sessions": 252, "purge_sessions": 63,
        "calendar_publication_lags": [14, 28],
        "scenarios": [{"id": "base", "publication_lag": 14, "execution_lag": 1, "cost_bps": 10.},
                      {"id": "execution2", "publication_lag": 14, "execution_lag": 2, "cost_bps": 10.},
                      {"id": "execution5", "publication_lag": 14, "execution_lag": 5, "cost_bps": 10.},
                      {"id": "cost25", "publication_lag": 14, "execution_lag": 1, "cost_bps": 25.},
                      {"id": "publication28", "publication_lag": 28, "execution_lag": 1, "cost_bps": 10.},
                      {"id": "combined_stress", "publication_lag": 28, "execution_lag": 5, "cost_bps": 25.}],
        "selection": "development excess CAGR + 0.25 * max-drawdown improvement vs own risk-asset buy-hold; lexical tie-break; no holdout reselection",
        "rebalance": "first available close of each ISO week; fills subsequent session close; P&L after fill",
        "defensive_asset": "SHY", "cash": "zero uninvested yield; SHY is an investable short-Treasury ETF",
        "primary_start": "2006-01-01", "primary_end": "2026-11-25",
        "limitations": [
            "Latest-vintage news series: historical revision/availability has not been proven point-in-time.",
            "Assumed 14/28-calendar-day publication delays are sensitivity assumptions, not recovered release timestamps.",
            "Pre-publication history is backcast, not a then-tradable public signal.",
            "No claim of an untouched historical holdout: dates and market episodes are known.",
            "ETF screen avoids selecting surviving individual companies but uses a small predeclared surviving ETF menu.",
            "This does not test earnings, guidance, individual news stories or the newly collected RSS article reader.",
            "Price history is a reused research-provider snapshot, not independently reconciled exchange data.",
            "No live promotion, tax model, capacity assertion or broker execution.",
        ],
        "regimes": {
            "financial_crisis": ["2007-10-09", "2009-03-09"],
            "euro_debt": ["2011-07-07", "2011-10-03"],
            "china_oil": ["2015-06-01", "2016-02-11"],
            "tightening2018": ["2018-09-20", "2018-12-24"],
            "covid": ["2020-02-19", "2020-03-23"],
            "inflation2022": ["2022-01-03", "2022-10-12"],
            "recent2026": ["2026-06-01", "2026-11-25"],
        },
        "statistical_test": "paired 63-session moving-block bootstrap; centered maximum-mean-excess family check; descriptive, not proof of alpha",
        "success_hurdle": "holdout CAGR >= own buy-hold +1pp; drawdown no worse than 2pp; beat price-only timing; survive combined stress; no promotion without PIT news",
    }
    _write(output / "registry.json", registry)
    return output / "registry.json"


def parse_source(name: str, raw: bytes):
    frame = pd.read_csv(io.BytesIO(raw))
    if name == "sentiment":
        if list(frame) != ["date", "Daily news sentiment"]:
            raise DataGateError("Unknown sentiment source schema")
        dates = pd.to_datetime(frame.date, format="%m/%d/%Y", errors="raise")
        values = pd.to_numeric(frame.iloc[:, 1], errors="raise")
    elif name == "uncertainty":
        frame.columns = [str(c).strip() for c in frame]
        required = {"year", "month", "day", "daily_policy_index"}
        if not required <= set(frame):
            raise DataGateError(f"Unknown uncertainty source schema: {list(frame)}")
        dates = pd.to_datetime(frame[["year", "month", "day"]], errors="raise")
        values = pd.to_numeric(frame.daily_policy_index, errors="raise")
    else:
        raise DataGateError("Unknown news source")
    series = pd.Series(values.to_numpy(float), index=pd.DatetimeIndex(dates), name=name).sort_index()
    if series.index.has_duplicates or not np.isfinite(series).all():
        raise DataGateError("Duplicate dates or invalid news values")
    if name == "uncertainty" and series.lt(0).any():
        raise DataGateError("Negative uncertainty counts")
    return series


def acquire(registry_path: Path):
    registry = json.loads(registry_path.read_text())
    root = registry_path.parent
    source_dir = root / "sources"
    source_dir.mkdir(exist_ok=False)
    reader = Reader(source_dir, budget=60.)
    sources = {}
    for name, spec in registry["source_definitions"].items():
        try:
            body, _ = reader.get(spec["url"], (spec["host"],))
            series = parse_source(name, body)
            series = series.loc[:registry["primary_end"]]
            if len(series) < 2520:
                raise DataGateError("Insufficient news-history coverage")
            series.to_frame().to_parquet(source_dir / f"{name}.parquet")
            sources[name] = {"status": "available_latest_vintage", "rows": len(series),
                             "first": str(series.index[0].date()), "last": str(series.index[-1].date())}
        except (DataGateError, ValueError) as exc:
            sources[name] = {"status": "unavailable", "error": str(exc)}
    _write(source_dir / "acquisition.json", {"captured_at_utc": datetime.now(UTC).isoformat(),
                                             "sources": sources, "requests": reader.requests,
                                             "point_in_time_qualified": False})
    _write(source_dir / "manifest.json", {"registry_sha256": sha(registry_path),
                                          "artifacts": {str(p.relative_to(source_dir)): sha(p)
                                                        for p in sorted(source_dir.rglob("*")) if p.is_file()}})
    return sources


def aligned_features(source_dir: Path, sessions: pd.DatetimeIndex, lag: int):
    if lag not in (14, 28) or sessions.tz is not None or sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise DataGateError("Invalid assumed publication lag or session clock")
    calendar = xcals.get_calendar("XNYS", start=str(sessions[0].date()), end=str(sessions[-1].date()))
    closes = pd.DatetimeIndex(calendar.schedule.loc[sessions, "close"])
    pieces = []
    for name in SOURCES:
        file = source_dir / f"{name}.parquet"
        if not file.exists():
            continue
        s = pd.read_parquet(file)[name]
        daily = s.reindex(pd.date_range(s.index[0], s.index[-1])).ffill(limit=7)
        level = daily if name == "sentiment" else np.log1p(daily)
        mean = level.shift(1).rolling(252, min_periods=126).mean()
        std = level.shift(1).rolling(252, min_periods=126).std()
        features = pd.DataFrame({name: level, f"{name}_change21": level - level.shift(21),
                                 f"{name}_change63": level - level.shift(63),
                                 f"{name}_z": (level - mean) / std.where(std.gt(1e-12)),
                                 f"{name}_observation_date": daily.index})
        # End-of-day availability ensures the observation's calendar day is complete.
        features.index = features.index.tz_localize("UTC") + pd.Timedelta(days=lag + 1)
        features[f"{name}_assumed_available_at"] = features.index
        joined = features.reindex(closes, method="ffill", tolerance=pd.Timedelta(days=7))
        joined.index = sessions
        pieces.append(joined)
    return pd.concat(pieces, axis=1) if pieces else pd.DataFrame(index=sessions)


def risk_state(features, prices, rule):
    s = features.get("sentiment", pd.Series(np.nan, index=prices.index))
    d = features.get("sentiment_change21", s * np.nan)
    z = features.get("sentiment_z", s * np.nan)
    u = features.get("uncertainty_z", s * np.nan)
    ud = features.get("uncertainty_change21", s * np.nan)
    trend = prices.SPY.ge(prices.SPY.rolling(200, min_periods=200).mean())
    required = [s, d, z]
    if rule.startswith("uncertainty"):
        required = [u, ud]
    elif rule.startswith("dual") or rule == "staged_evidence":
        required += [u, ud]
    rules = {
        "sentiment_level": s.ge(0), "sentiment_improving21": d.gt(0),
        "sentiment_improving63": features.get("sentiment_change63", s * np.nan).gt(0),
        "sentiment_shock1": z.gt(-1), "sentiment_shock15": z.gt(-1.5),
        "sentiment_repair": s.ge(0) | d.gt(0),
        "price_confirms_news": s.ge(0) | trend, "news_repairs_price": trend | d.gt(0),
        "price_and_news": trend & (s.ge(0) | d.gt(0)),
        "uncertainty_shock1": u.lt(1), "uncertainty_shock15": u.lt(1.5),
        "uncertainty_improving": ud.lt(0), "dual_warning": s.ge(0) | u.lt(1),
        "dual_repair": d.gt(0) | ud.lt(0), "dual_confirmation": d.gt(0) & ud.lt(0),
        "staged_evidence": 1. - .5 * (s.lt(0).astype(float) + u.ge(1).astype(float)),
    }
    if rule not in rules:
        raise DataGateError("Unregistered news rule")
    valid = pd.concat(required, axis=1).notna().all(axis=1)
    if rule in {"price_confirms_news", "news_repairs_price", "price_and_news"}:
        valid &= prices.SPY.rolling(200, min_periods=200).mean().notna()
    return rules[rule].astype(float).where(valid)


def weekly_targets(prices: pd.DataFrame, state: pd.Series, spec: dict):
    """Close-known targets; missing source observations revert to the declared neutral control."""
    week = prices.index.to_period("W-SUN")
    rebalance = ~week.duplicated()
    state = state.fillna(1.).where(rebalance).ffill().fillna(1.)
    weights = pd.DataFrame(0., index=prices.index, columns=ASSETS)
    if spec["kind"] == "risk_budget":
        budget = spec["floor"] + (1 - spec["floor"]) * state
        weights[spec["risk_asset"]] = budget
        weights.SHY = 1 - budget
    else:
        for asset in CYCLICAL:
            weights[asset] = state / len(CYCLICAL)
        for asset in DEFENSIVE:
            weights[asset] = (1 - state) / len(DEFENSIVE)
    return weights


def build(registry_path: Path):
    root = registry_path.parent
    registry = json.loads(registry_path.read_text())
    source_root = root / "sources"
    source_meta = json.loads((source_root / "manifest.json").read_text())
    if source_meta["registry_sha256"] != sha(registry_path):
        raise DataGateError("Frozen news protocol changed")
    for name, expected in source_meta["artifacts"].items():
        file = (source_root / name).resolve()
        if not file.is_relative_to(source_root.resolve()) or sha(file) != expected:
            raise DataGateError("Historical news source integrity failed")
    bundle = Path(registry["bundle"])
    if sha(bundle / "manifest.json") != registry["bundle_manifest_sha256"]:
        raise DataGateError("Price bundle changed after protocol freeze")
    bm = json.loads((bundle / "manifest.json").read_text())
    prices_file = bundle / "prices.parquet"
    if sha(prices_file) != bm["artifacts"]["prices.parquet"]:
        raise DataGateError("Unbound price history")
    prices = pd.read_parquet(prices_file)[ASSETS]
    calendar = xcals.get_calendar("XNYS", start=str(prices.index[0].date()), end=str(prices.index[-1].date()))
    actual = calendar.sessions_in_range(prices.index[0], prices.index[-1])
    if not prices.index.equals(actual) or prices.isna().any().any() or not np.isfinite(prices).all().all() or prices.le(0).any().any():
        raise DataGateError("Complete actual-session ETF prices required; no forward/backward filling")
    prices = prices.loc[:registry["primary_end"]]
    target_dir = root / "targets"
    target_dir.mkdir(exist_ok=False)
    prices.to_parquet(root / "prices.parquet")
    status = []
    for lag in registry["calendar_publication_lags"]:
        features = aligned_features(source_root, prices.index, lag)
        features.to_parquet(root / f"features_lag{lag}.parquet")
        for spec in registry["policies"]:
            state = risk_state(features, prices, spec["rule"])
            relevant = state.loc[registry["primary_start"]:]
            coverage = float(relevant.notna().mean())
            if coverage < .95:
                status.append({"id": spec["id"], "publication_lag": lag, "status": "unavailable_coverage", "coverage": coverage})
                continue
            weekly_targets(prices, state, spec).to_parquet(target_dir / f"{spec['id']}_lag{lag}.parquet")
            status.append({"id": spec["id"], "publication_lag": lag, "status": "ready_for_proxy_screen", "coverage": coverage})
    _write(root / "status.json", status)
    _write(root / "manifest.json", {
        "kind": "news_proxy_etf_screen", "authority": "research_only", "action_authorized": False,
        "point_in_time_qualified": False, "rss_strategy_backtest": False,
        "registry_sha256": sha(registry_path),
        "artifacts": {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*"))
                      if p.is_file() and p.name != "manifest.json"},
        "source_manifest_sha256": sha(source_root / "manifest.json"),
    })
    return root
