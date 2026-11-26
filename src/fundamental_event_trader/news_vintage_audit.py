"""Reconstruct primary historical-vintage features and targets from bound release bytes."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from fundamental_event_trader.news_vintage_research import features, parse_vintage, state
from fundamental_event_trader.sec import DataGateError, sha


def audit(root: Path, output: Path, *, latest_screen: Path | None = None):
    manifest = json.loads((root / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        file = (root / name).resolve()
        if not file.is_relative_to(root.resolve()) or sha(file) != expected:
            raise DataGateError("Vintage evidence failed artifact readback")
    registry = json.loads((root / "registry.json").read_text())
    acquisition = json.loads((root / "sources/acquisition.json").read_text())
    requests = {r["sha256"]: r for r in acquisition["requests"] if r.get("http_status") == 200}
    stored = pd.read_parquet(root / "vintage_features.parquet")
    expected = registry["source_definitions"]["uncertainty"]["vintages"]
    if stored.vintage.tolist() != expected:
        raise DataGateError("Historical release census incomplete")
    reconstructed = []
    released_histories = {}
    revision_rows = []
    latest = None
    if latest_screen is not None:
        latest_file = latest_screen / "sources/uncertainty.parquet"
        latest_manifest = json.loads((latest_screen / "manifest.json").read_text())
        if latest_manifest["artifacts"].get("sources/uncertainty.parquet") != sha(latest_file):
            raise DataGateError("Unbound latest-vintage revision comparison")
        latest = pd.read_parquet(latest_file).uncertainty
    for row in stored.to_dict("records"):
        request = requests[row["vintage_sha256"]]
        url = urlsplit(request["url"])
        if (url.scheme != "https" or url.hostname != "alfred.stlouisfed.org"
                or parse_qs(url.query).get("vintage_date") != [row["vintage"]]
                or parse_qs(url.query).get("id") != ["USEPUINDXD"]):
            raise DataGateError("Release bytes do not bind the requested source/vintage")
        body = (root / "sources" / request["path"]).read_bytes()
        series = parse_vintage(body, row["vintage"], allow_stale="stale_vintage_policy" in registry)
        released_histories[row["vintage"]] = series
        age = (pd.Timestamp(row["vintage"]) - series.index[-1]).days
        if row.get("data_status", "fresh") != ("fresh" if age <= 7 else "stale_no_target_update"):
            raise DataGateError("Incorrect stale-release classification")
        result = features(series)
        for key in ("level", "z", "change21", "change63"):
            if not np.isclose(result[key], row[key], atol=1e-12, rtol=1e-12):
                raise DataGateError("Stored feature does not reproduce from historical release bytes")
        if result["last_observation"] != row["last_observation"]:
            raise DataGateError("Historical source observation cutoff changed")
        if latest is not None:
            pair = pd.concat([series.rename("released"), latest.rename("latest")], axis=1).dropna()
            changed = pair.released.sub(pair.latest).abs().gt(1e-8)
            revised_features = features(latest.loc[:row["last_observation"]].iloc[-801:])
            revision_rows.append({"vintage": row["vintage"], "matched_observations": len(pair),
                                  "revised_observations": int(changed.sum()),
                                  "largest_absolute_revision": float(pair.released.sub(pair.latest).abs().max()),
                                  "released_final_level": result["level"], "latest_final_level": revised_features["level"],
                                  "released_z": result["z"], "latest_z": revised_features["z"]})
        reconstructed.append(row)
    prices = pd.read_parquet(root / "prices.parquet")
    calendar = xcals.get_calendar("XNYS", start=str(prices.index[0].date()), end=str(prices.index[-1].date()))
    if not prices.index.equals(calendar.sessions_in_range(prices.index[0], prices.index[-1])):
        raise DataGateError("Missing or non-exchange sessions in price inputs")
    market_trend = prices.SPY.ge(prices.SPY.rolling(200).mean())
    for policy in registry["policies"]:
        budget = pd.Series(np.nan, index=prices.index)
        for row in reconstructed:
            if row.get("data_status", "fresh") != "fresh":
                continue
            expected_available = pd.Timestamp(row["vintage"], tz="UTC") + pd.Timedelta(days=2)
            if pd.Timestamp(row["assumed_available_at"]) != expected_available:
                raise DataGateError("Premature/changed historical availability")
            i = prices.index.searchsorted(expected_available.tz_convert(None).normalize())
            if i < len(prices):
                policy_features = row
                if "transform" in policy:
                    from fundamental_event_trader.news_maturity_research import transform

                    policy_features = features(transform(released_histories[row["vintage"]], row["vintage"], policy["transform"]))
                budget.iloc[i] = state(policy["rule"], policy_features, bool(market_trend.iloc[i]))
        budget = policy["floor"] + (1 - policy["floor"]) * budget.ffill().fillna(1.)
        targets = pd.read_parquet(root / "targets" / f"{policy['id']}_lag0.parquet")
        if not np.allclose(targets[policy["risk_asset"]], budget, atol=1e-12, rtol=1e-12):
            raise DataGateError("Primary historical-vintage targets do not reproduce")
        if (not np.isfinite(targets).all().all() or targets.lt(0).any().any()
                or not np.allclose(targets.sum(axis=1), 1., atol=1e-12)):
            raise DataGateError("Invalid long-only historical-vintage allocation")
    result = {"status": "passed_source_feature_and_target_reconstruction", "action_authorized": False,
              "uses_historical_released_vintages": True, "verified_vintages": len(stored),
              "reconstructed_primary_policies": len(registry["policies"]),
              "stale_vintages_no_target_update": int(stored.get("data_status", pd.Series(dtype=str)).eq("stale_no_target_update").sum()),
              "source_manifest_sha256": sha(root / "manifest.json"),
              "scope": "Primary released-vintage mode only; latest-vintage sensitivity is not given this historical-source validation",
              "rss_article_strategy_qualified": False, "audit_code_sha256": sha(Path(__file__))}
    output.parent.mkdir(parents=True, exist_ok=True)
    if revision_rows:
        revisions = pd.DataFrame(revision_rows)
        revision_file = output.with_suffix(".revisions.csv")
        if revision_file.exists():
            raise DataGateError("Revision audit output already exists")
        revisions.to_csv(revision_file, index=False)
        result["revision_diagnostic"] = {"path": str(revision_file), "sha256": sha(revision_file),
                                          "vintages_with_any_revision": int(revisions.revised_observations.gt(0).sum()),
                                          "latest_comparison_manifest_sha256": sha(latest_screen / "manifest.json")}
    with output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result
