"""Historical released newspaper-uncertainty vintages; monthly ETF timing research."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import numpy as np
import pandas as pd

from fundamental_event_trader.news_io import Reader
from fundamental_event_trader.news_research import ASSETS, _write
from fundamental_event_trader.news_research import freeze as freeze_proxy
from fundamental_event_trader.sec import DataGateError, sha

RULES = ["low100", "z1", "z15", "improving21", "improving63", "contrarian1",
         "contrarian2", "price_confirms", "price_repair", "staged"]


def freeze(bundle: Path, output: Path):
    path = freeze_proxy(bundle, output)
    registry = json.loads(path.read_text())
    registry.update({
        "study": "monthly_alfred_released_epu_vintages", "uses_historical_released_vintages": True,
        "stale_vintage_policy": {"maximum_observation_age_days": 7,
                                  "action": "no_target_update_hold_previous",
                                  "recorded_at_utc": datetime.now(UTC).isoformat()},
        "policies": [{"id": f"epu_vintage_{rule}_{asset}_floor{int(floor * 100)}", "rule": rule,
                      "risk_asset": asset, "floor": floor, "kind": "risk_budget"}
                     for rule in RULES for asset in ("SPY", "QQQ") for floor in (0., .5)],
        "source_definitions": {"uncertainty": {
            "url": "https://alfred.stlouisfed.org/graph/alfredgraph.csv", "series": "USEPUINDXD",
            "vintages": [str(d.date()) for d in pd.date_range("2014-04-30", "2026-10-31", freq="ME")],
            "request_lookback_days": 800,
            "availability": "vintage calendar date +2 days at 00:00 UTC; first following NYSE decision close; fill later close",
        }},
        "partitions": {"development": ["2014-05-01", "2018-12-31"],
                       "validation": ["2019-01-01", "2021-12-31"],
                       "holdout_diagnostic": ["2022-01-01", "2026-11-25"]},
        "primary_start": "2014-05-01", "public_signal_start": "2014-05-01",
        "calendar_publication_lags": [0, 1],
        "lag_key_semantics": "0=historical released vintage; 1=latest-vintage matched-clock sensitivity, NOT calendar-day latency",
        "rebalance": "monthly historical vintage; decision after vintage date +2 calendar days; fill close t+lag; P&L after fill",
        "scenarios": [{"id": "base", "publication_lag": 0, "execution_lag": 1, "cost_bps": 10.},
                      {"id": "execution2", "publication_lag": 0, "execution_lag": 2, "cost_bps": 10.},
                      {"id": "execution5", "publication_lag": 0, "execution_lag": 5, "cost_bps": 10.},
                      {"id": "cost25", "publication_lag": 0, "execution_lag": 1, "cost_bps": 25.},
                      {"id": "latest_vintage_control", "publication_lag": 1, "execution_lag": 1, "cost_bps": 10.}],
        "limitations": [
            "Uses official historical ALFRED vintages, not the newly collected RSS articles or individual company events.",
            "Only monthly vintage decisions are tested; this does not validate fast intraday news reaction.",
            "The series first entered ALFRED in March 2014; earlier observations only form historical feature windows.",
            "Two-calendar-day vintage delay is conservative, but the source archive is not an independent audit of historical feed delivery.",
            "All rules and dates are retrospective research; the 2022+ partition is not claimed previously unseen.",
            "Small predeclared surviving ETF menu; reused provider-adjusted closes, no independent exchange reconciliation.",
            "No account data, live allocation authority, taxes, individual-stock profitability claim or article-sentiment validation.",
        ],
    })
    _write(path, registry)
    return path


def parse_vintage(body, vintage, *, allow_stale=False):
    frame = pd.read_csv(io.BytesIO(body), dtype=str)
    expected = f"USEPUINDXD_{pd.Timestamp(vintage).strftime('%Y%m%d')}"
    if list(frame) != ["observation_date", expected]:
        raise DataGateError("ALFRED did not return the requested historical vintage")
    dates = pd.to_datetime(frame.observation_date, format="%Y-%m-%d", errors="raise")
    values = pd.to_numeric(frame[expected].replace({".": None, "": None}), errors="raise")
    series = pd.Series(values.to_numpy(float), index=pd.DatetimeIndex(dates), name="uncertainty")
    if series.index.has_duplicates or not series.index.is_monotonic_increasing or series.index.max() > pd.Timestamp(vintage):
        raise DataGateError("Future or duplicate observations in historical vintage")
    series = series.dropna()
    if len(series) < 252 or not np.isfinite(series).all() or series.lt(0).any():
        raise DataGateError("Insufficient or invalid released uncertainty history")
    if not allow_stale and (pd.Timestamp(vintage) - series.index[-1]).days > 7:
        raise DataGateError("Stale historical vintage")
    return series


def amend_freshness(registry_path: Path):
    """Before return evaluation, specify behavior for observed but stale releases."""
    root = registry_path.parent
    if (root / "manifest.json").exists():
        raise DataGateError("Cannot amend a sealed study")
    registry = json.loads(registry_path.read_text())
    if "stale_vintage_policy" in registry:
        raise DataGateError("Freshness amendment already registered")
    original = root / "registry_original.json"
    with original.open("xb") as handle:
        handle.write(registry_path.read_bytes())
    registry["stale_vintage_policy"] = {"maximum_observation_age_days": 7,
                                        "action": "no_target_update_hold_previous",
                                        "recorded_at_utc": datetime.now(UTC).isoformat()}
    _write(root / "protocol_amendment.json", {
        "reason": "Two complete historical release responses contain stale last observations; no vintage-study return evaluation has run.",
        "original_registry_sha256": sha(original),
        "change": registry["stale_vintage_policy"], "thresholds_and_selection_unchanged": True,
        "no_missing_vintage_omission": True,
    })
    _write(registry_path, registry)
    return registry_path


def features(series):
    s = np.log1p(series)
    prior = s.iloc[-253:-1]
    if len(prior) < 252 or not np.isfinite(prior).all() or prior.std() <= 1e-12:
        raise DataGateError("Insufficient nonconstant historical feature window")
    return {"level": float(series.iloc[-1]),
            "z": float((s.iloc[-1] - prior.mean()) / prior.std()),
            "change21": float(s.iloc[-1] - s.iloc[-22]),
            "change63": float(s.iloc[-1] - s.iloc[-64]),
            "last_observation": str(series.index[-1].date())}


def state(rule, row, trend):
    z, delta = row["z"], row["change21"]
    options = {"low100": row["level"] < 100, "z1": z < 1, "z15": z < 1.5,
               "improving21": delta < 0, "improving63": row["change63"] < 0,
               "contrarian1": z > 1, "contrarian2": z > 2,
               "price_confirms": z < 1 or trend,
               "price_repair": delta < 0 or trend,
               "staged": 1. - .5 * (int(z >= 1) + int(delta >= 0))}
    if rule not in options:
        raise DataGateError("Unknown frozen vintage rule")
    return float(options[rule])


def build(registry_path: Path, *, resume=False):
    root = registry_path.parent
    initial_code = sha(Path(__file__))
    if (root / "manifest.json").exists():
        raise DataGateError("Historical vintage study is already sealed")
    (root / "generator.py.source.txt").write_bytes(Path(__file__).read_bytes())
    registry = json.loads(registry_path.read_text())
    source_dir = root / "sources"
    source_dir.mkdir(exist_ok=resume)
    previous = {}
    cached = {}
    if resume:
        previous = json.loads((source_dir / "acquisition.json").read_text())
        if any(r.get("http_status") in (401, 403, 429) for r in previous["requests"]):
            raise DataGateError("Denied access recorded; automatic acquisition retry withheld")
        for request in previous["requests"]:
            url = urlsplit(request["url"])
            query = parse_qs(url.query)
            if (request.get("http_status") == 200 and url.hostname == "alfred.stlouisfed.org"
                    and query.get("id") == ["USEPUINDXD"] and "vintage_date" in query):
                file = (source_dir / request["path"]).resolve()
                if not file.is_relative_to(source_dir.resolve()) or sha(file) != request["sha256"]:
                    raise DataGateError("Cached release bytes changed")
                cached[query["vintage_date"][0]] = (file, request["sha256"])
        backup = source_dir / f"acquisition_before_resume_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        _write(backup, previous)
    reader = Reader(source_dir, budget=1500., request_timeout=30.)
    reader.requests.extend(previous.get("requests", []))
    rows, audit = [], []
    spec = registry["source_definitions"]["uncertainty"]
    for vintage in spec["vintages"]:
        start = pd.Timestamp(vintage) - pd.Timedelta(days=spec["request_lookback_days"])
        url = spec["url"] + "?" + urlencode({"id": spec["series"], "cosd": str(start.date()),
                                               "coed": vintage, "vintage_date": vintage})
        try:
            if vintage in cached:
                raw = cached[vintage][0].read_bytes()
                body_hash = cached[vintage][1]
            else:
                raw, _ = reader.get(url, ("alfred.stlouisfed.org",))
                body_hash = reader.requests[-1]["sha256"]
            series = parse_vintage(raw, vintage, allow_stale="stale_vintage_policy" in registry)
            age = (pd.Timestamp(vintage) - series.index[-1]).days
            rows.append({"vintage": vintage, "assumed_available_at": (pd.Timestamp(vintage, tz="UTC") + pd.Timedelta(days=2)).isoformat(),
                         "vintage_sha256": body_hash, "observation_age_days": age,
                         "data_status": "fresh" if age <= 7 else "stale_no_target_update", **features(series)})
            audit.append({"vintage": vintage, "status": "verified_requested_vintage" if age <= 7 else "stale_released_vintage_no_target_update",
                          "rows": len(series), "last_observation": str(series.index[-1].date()), "age_days": age})
        except (DataGateError, ValueError) as exc:
            audit.append({"vintage": vintage, "status": "unavailable", "error": str(exc)})
            # Stop on explicit denied access; do not retry or change identities.
            if reader.requests[-1].get("http_status") in (401, 403, 429):
                break
        if len(audit) % 12 == 0:
            print(json.dumps({"vintages_checked": len(audit), "usable": len(rows)}), flush=True)
    acquisition = {"captured_at_utc": datetime.now(UTC).isoformat(), "sources": {"uncertainty": {
        "status": "historical_released_vintages", "expected_vintages": len(spec["vintages"]),
        "preserved_vintages": len(rows), "usable_vintages": sum(r["data_status"] == "fresh" for r in rows),
        "stale_no_target_update": sum(r["data_status"] != "fresh" for r in rows)}},
        "audit": audit, "requests": reader.requests, "point_in_time_article_strategy_qualified": False}
    _write(source_dir / "acquisition.json", acquisition)
    if len(rows) != len(spec["vintages"]):
        raise DataGateError(f"Incomplete historical release census: {len(rows)}/{len(spec['vintages'])}; no silent skipping")
    vintage_features = pd.DataFrame(rows)
    vintage_features.to_parquet(root / "vintage_features.parquet", index=False)
    bundle = Path(registry["bundle"])
    bm = json.loads((bundle / "manifest.json").read_text())
    if sha(bundle / "manifest.json") != registry["bundle_manifest_sha256"] or sha(bundle / "prices.parquet") != bm["artifacts"]["prices.parquet"]:
        raise DataGateError("Price bundle changed after freeze")
    prices = pd.read_parquet(bundle / "prices.parquet")[ASSETS].loc[:registry["primary_end"]]
    if prices.isna().any().any() or not np.isfinite(prices).all().all() or prices.le(0).any().any():
        raise DataGateError("Missing ETF prices in released-vintage study")
    prices.to_parquet(root / "prices.parquet")
    trend_by_date = prices.SPY.ge(prices.SPY.rolling(200).mean())
    # Latest-vintage comparison uses the same historical observation cutoff and rebalance clock.
    raw, _ = reader.get("https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv", ("www.policyuncertainty.com",))
    from fundamental_event_trader.news_research import parse_source

    latest = parse_source("uncertainty", raw)
    target_dir = root / "targets"
    target_dir.mkdir(exist_ok=resume)
    status = []
    for mode in registry["calendar_publication_lags"]:
        for policy in registry["policies"]:
            values = pd.Series(np.nan, index=prices.index)
            for row in rows:
                if row["data_status"] != "fresh":
                    continue
                available = pd.Timestamp(row["assumed_available_at"]).tz_convert(None)
                # Availability at 00:00 UTC precedes the decision session's US close.
                offset = prices.index.searchsorted(available.normalize(), side="left")
                if offset >= len(prices):
                    continue
                current = row if mode == 0 else features(latest.loc[:row["last_observation"]].iloc[-801:])
                trend = bool(trend_by_date.iloc[offset])
                values.iloc[offset] = state(policy["rule"], current, trend)
            budget = policy["floor"] + (1 - policy["floor"]) * values.ffill().fillna(1.)
            w = prices * 0.
            w[policy["risk_asset"]] = budget
            w.SHY = 1 - budget
            w.to_parquet(target_dir / f"{policy['id']}_lag{mode}.parquet")
            status.append({"id": policy["id"], "publication_lag": mode, "status": "historical_vintage_targets", "coverage": 1.})
    _write(root / "status.json", status)
    # Include the latest-vintage control request too, not only the primary release census.
    acquisition["requests"] = reader.requests
    _write(source_dir / "acquisition.json", acquisition)
    if initial_code != sha(Path(__file__)):
        raise DataGateError("Historical news generator changed during execution")
    _write(root / "manifest.json", {"kind": "news_proxy_etf_screen", "authority": "research_only", "action_authorized": False,
                                    "point_in_time_qualified": False, "rss_strategy_backtest": False,
                                    "uses_historical_released_vintages": True, "registry_sha256": sha(registry_path),
                                    "generator_sha256": initial_code,
                                    "artifacts": {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}})
    return root
