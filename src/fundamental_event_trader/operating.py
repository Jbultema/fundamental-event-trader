"""Verified research status, frozen-policy daily observations and common-contract exports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from fundamental_event_trader.features import registry
from fundamental_event_trader.news import status as news_status
from fundamental_event_trader.portfolio import metrics, replay
from fundamental_event_trader.qualification import CRITERIA, qualify
from fundamental_event_trader.readiness import coverage
from fundamental_event_trader.research import code_hash, load_dataset
from fundamental_event_trader.sec import DataGateError, sha, timestamp
from fundamental_event_trader.shadow import evaluate as evaluate_shadow
from fundamental_event_trader.shadow import record as record_shadow
from fundamental_event_trader.shadow import summary as shadow_summary
from fundamental_event_trader.strategy import Policy, eligible_events, session_schedule, targets


def verify_report(report: Path) -> dict:
    meta = json.loads((report / "manifest.json").read_text())
    if (
        meta.get("system") != "fundamental-event-trader"
        or meta.get("kind") != "portfolio_research"
        or meta.get("fixture_only") is not False
        or meta.get("data_kind") != "real_historical"
        or meta.get("action_authorized") is not False
        or meta.get("code_sha256") != code_hash()
    ):
        raise DataGateError("Research report is stale, synthetic, or lacks current-code provenance")
    required = {
        "registry.json",
        "selection.json",
        "performance.csv",
        "returns.parquet",
        "selected_targets.parquet",
        "selected_fills.parquet",
        "selected_realized_weights.parquet",
        "hypothesis_status.csv",
    }
    if not required <= set(meta.get("artifacts", {})):
        raise DataGateError("Incomplete portfolio research report")
    for name, expected in meta["artifacts"].items():
        file = (report / name).resolve()
        if not file.is_relative_to(report.resolve()) or not file.is_file() or sha(file) != expected:
            raise DataGateError("Research report artifact integrity failure")
    frozen = json.loads((report / "registry.json").read_text())
    selection = json.loads((report / "selection.json").read_text())
    if (
        frozen["code_sha256"] != meta["code_sha256"]
        or frozen["data_manifest_sha256"] != meta["dataset_manifest_sha256"]
        or selection.get("portfolio_allocation_allowed") is not False
        or selection.get("automatic_promotion_allowed") is not False
        or selection.get("fixture_only") is not False
        or not selection.get("policy")
    ):
        raise DataGateError("Research selection or authority mismatch")
    if selection["policy"] not in frozen["policies"]:
        raise DataGateError("Selected policy was not in the frozen experiment registry")
    return {"manifest": meta, "frozen": frozen, "selection": selection}


def frozen_policy(data, report: Path):
    verified = verify_report(report)
    original_root = Path(verified["frozen"]["dataset_root"])
    if sha(original_root / "manifest.json") != verified["manifest"]["dataset_manifest_sha256"]:
        raise DataGateError("Frozen research dataset changed")
    original = load_dataset(original_root)
    if sha(data.root / "manifest.json") != sha(original_root / "manifest.json"):
        cutoff = session_schedule(original.opens.index).close.iloc[-1]
        for old, new in ((original.opens, data.opens), (original.closes, data.closes)):
            if not set(old) <= set(new) or not old.index.isin(new.index).all():
                raise DataGateError("Daily dataset omits frozen securities or sessions")
            pd.testing.assert_frame_equal(old, new.loc[old.index, old.columns], check_freq=False)
        pd.testing.assert_series_equal(
            original.cash, data.cash.loc[original.cash.index], check_freq=False
        )
        for label in ("events", "identity", "terminals"):
            old, new = getattr(original, label), getattr(data, label)
            if label == "events":
                old = old[pd.to_datetime(old.available_at, utc=True) <= cutoff]
                new = new[pd.to_datetime(new.available_at, utc=True) <= cutoff]
            elif label == "identity":
                old = old[pd.to_datetime(old.known_at, utc=True) <= cutoff]
                new = new[pd.to_datetime(new.known_at, utc=True) <= cutoff]
            else:
                old = old[pd.to_datetime(old.settlement_at, utc=True) <= cutoff]
                new = new[pd.to_datetime(new.settlement_at, utc=True) <= cutoff]
            keys = sorted(old.columns)
            pd.testing.assert_frame_equal(
                old[keys].sort_values(keys).reset_index(drop=True),
                new[keys].sort_values(keys).reset_index(drop=True),
                check_dtype=False,
            )
    return Policy(**verified["selection"]["policy"]), verified


def resolve_config(root: Path, dataset=None, report=None):
    config_path = root / "data/runtime.json"
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    resolved = []
    for key, supplied in (("dataset", dataset), ("report", report)):
        if supplied is not None:
            resolved.append(Path(supplied).resolve())
            continue
        entry = config.get(key)
        if not entry:
            resolved.append(None)
            continue
        path = Path(entry["path"]).resolve()
        if sha(path / "manifest.json") != entry["manifest_sha256"]:
            raise DataGateError("Configured source identity changed")
        resolved.append(path)
    return tuple(resolved)


def latest_source_access(root: Path):
    captures = []
    for path in (root / "data/captures").glob("*/manifest.json"):
        meta = json.loads(path.read_text())
        if meta.get("source") not in {"official_sec_edgar", "official_sec_edgar_bulk_import"}:
            continue
        for doc in meta.get("documents", []):
            if doc.get("path"):
                file = (path.parent / doc["path"]).resolve()
                if not file.is_relative_to(path.parent.resolve()) or sha(file) != doc["sha256"]:
                    raise DataGateError("Official capture evidence changed")
        captures.append((timestamp(meta["captured_at_utc"]), path, meta))
    if not captures:
        return {"status": "not_captured"}
    _, path, meta = max(captures, key=lambda row: row[0])
    return {
        "status": meta["status"],
        "captured_at_utc": meta["captured_at_utc"],
        "manifest_sha256": sha(path),
        "requests": [
            {"url": d.get("url"), "http_status": d.get("http_status"), "passed": d["passed"]}
            for d in meta.get("documents", [])
        ],
    }


def status(root: Path, *, dataset=None, report=None, now=None) -> dict:
    clock = timestamp(now or datetime.now(UTC))
    payload = {
        "schema_version": 2,
        "system": "fundamental-event-trader",
        "captured_at_utc": clock.isoformat(),
        "status": "blocked",
        "stage": "data_acquisition",
        "authority": "research_only",
        "action": "NO ACTION",
        "action_authorized": False,
        "portfolio_allocation_allowed": False,
        "automatic_promotion_allowed": False,
        "registered_hypotheses": len(registry()),
        "tested_on_real_data": 0,
        "errors": [],
        "target_holdings": {},
        "recent_events": [],
        "performance": [],
        "news": news_status(root, now=clock),
        "hypothesis_coverage": coverage(),
        "prospective_shadow": shadow_summary(root, {}, now=clock),
        "source_access": {},
        "code_sha256": code_hash(),
        "remaining_gates": [
            "Qualified historical data",
            "Costed portfolio validation",
            "Prospective shadow evidence",
            "Explicit allocation admission",
        ],
        "mandate": "Fundamentals and company events; public financial news observed separately from allocation decisions",
    }
    try:
        payload["source_access"] = latest_source_access(root)
        dataset, report = resolve_config(root, dataset, report)
        gate = qualify(dataset)
        payload["data_qualification"] = gate
        payload["criteria"] = [{"criterion": c, "passed": False} for c in CRITERIA]
        if dataset is None or not gate["historical_event_study_allowed"]:
            payload["errors"] = gate["errors"]
            return payload
        data = load_dataset(dataset)
        payload["hypothesis_coverage"] = coverage(data.events)
        payload["stage"] = "portfolio_validation"
        payload["criteria"] = [{"criterion": c, "passed": True} for c in CRITERIA]
        payload["dataset_manifest_sha256"] = sha(dataset / "manifest.json")
        payload["as_of_session"] = str(data.opens.index[-1].date())
        payload["coverage"] = {
            "sessions": len(data.opens),
            "securities": data.identity.security_id.nunique(),
            "events": len(data.events),
            "delisted": int(data.identity.delisted.sum()),
        }
        if report is None:
            payload["errors"] = ["no_validated_portfolio_research"]
            return payload
        policy, checked = frozen_policy(data, report)
        payload["hypothesis_coverage"] = coverage(data.events, report)
        schedule = session_schedule(data.opens.index)
        if schedule.close.iloc[-1] + pd.Timedelta(minutes=15) > clock:
            raise DataGateError("Latest supplied close is not completed")
        weights = targets(data.events, data.opens.index, data.identity, policy)
        current = weights.iloc[-1].copy()
        for row in data.terminals.itertuples():
            if timestamp(row.settlement_at) <= schedule.close.iloc[-1]:
                current.loc[row.security_id] = 0.0
        cal = xcals.get_calendar(
            "XNYS",
            start=str((clock - pd.Timedelta(days=30)).date()),
            end=str((clock + pd.Timedelta(days=10)).date()),
        )
        completed = [
            d
            for d in cal.sessions_in_range((clock - pd.Timedelta(days=20)).date(), clock.date())
            if cal.session_close(d) + pd.Timedelta(minutes=15) <= clock
        ]
        fresh = bool(completed and str(completed[-1].date()) == payload["as_of_session"])
        recent = eligible_events(data.events, policy)
        recent = recent[
            recent.available_at.between(
                schedule.close.iloc[-1] - pd.Timedelta(days=30), schedule.close.iloc[-1]
            )
        ].tail(20)
        payload |= {
            "status": "research_shadow" if fresh else "stale_research",
            "stage": "prospective_shadow",
            "research_manifest_sha256": sha(report / "manifest.json"),
            "fresh": fresh,
            "tested_on_real_data": checked["selection"]["tested"],
            "policy": policy.specification(),
            "target_holdings": {k: float(v) for k, v in current.items() if v > 1e-12},
            "cash": float(1 - current.sum()),
            "performance": pd.read_csv(report / "performance.csv")
            .query("name == @policy.name or name == 'buy_hold_SPY' or name == 'cash'")
            .to_dict("records"),
            "recent_events": [
                {
                    "security_id": row.security_id,
                    "cik": str(row.cik).zfill(10),
                    "accession": row.accession,
                    "available_at": row.available_at.isoformat(),
                    "score": float(row.score),
                    "source_sha256": row.source_sha256,
                }
                for row in recent.itertuples()
            ],
            "remaining_gates": ["Prospective shadow evidence", "Explicit allocation admission"],
        }
        if not fresh:
            payload["errors"].append("dataset_behind_latest_completed_session")
        payload["prospective_shadow"] = shadow_summary(root, payload, now=clock)
        payload["prospective_outcomes"] = evaluate_shadow(root, payload, data, now=clock)
    except (OSError, ValueError, TypeError, KeyError, AssertionError) as exc:
        payload["errors"].append(f"{type(exc).__name__}:{str(exc)[:240]}")
        payload["status"] = "blocked"
        payload["target_holdings"] = {}
        payload["recent_events"] = []
        payload["performance"] = []
    return payload


def daily(root: Path, output: Path, *, dataset=None, report=None, refresh_news=False) -> Path:
    news_error = None
    if refresh_news:
        from fundamental_event_trader.news import refresh_if_due

        try:
            refresh_if_due(root)
        except (OSError, ValueError, TypeError) as exc:
            news_error = str(exc)[:200]
    result = status(root, dataset=dataset, report=report)
    if news_error:
        result["news"]["refresh_error"] = news_error
    result["shadow_recording"] = record_shadow(root, result, now=datetime.now(UTC))
    result["prospective_shadow"] = shadow_summary(root, result, now=datetime.now(UTC))
    output.mkdir(parents=True, exist_ok=False)
    (output / "status.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    lines = ["# Fundamental Event Trader", "",
             f"Stage: {result['stage']}. Status: {result['status']}.", "",
             f"Registered hypotheses: {result['registered_hypotheses']}; tested on real data: {result['tested_on_real_data']}.", ""]
    lines.extend(f"- {error}" for error in result["errors"])
    news = result["news"]
    lines += ["", "## Current Financial News", "",
              f"News monitor: {news['status']}. Article bodies read: {news['article_bodies_read']}. Captured: {news.get('captured_at_utc', 'not collected')}.",
              "News observations are separate from the strategy-validation status and historical decisions.", ""]
    for item in news["items"][:12]:
        label = item["display_title"].replace("[", "(").replace("]", ")")
        lines += [f"- [{label}]({item['url']}) / {item['source']} / {item['coverage']} / {item['published_at_utc']}."]
    lines += ["", "## Content Evidence", "",
              "| Content family | Registered variants | Features available | Tested variants |",
              "|---|---:|---:|---:|"]
    for row in result["hypothesis_coverage"]:
        lines.append(f"| {row['family'].replace('_', ' ')} | {row['registered_variants']} | {row['variants_with_features']} | {row['tested_variants']} |")
    progress = result["prospective_shadow"]
    lines += ["", "## Prospective Evidence", "",
              f"Status: {progress['status']}. On-time observations: {progress['recorded_sessions']}; consecutive sessions: {progress['consecutive_sessions']}.",
              "The 60-session minimum opens an evidence review. It does not establish alpha or authorize an allocation.", ""]
    outcomes = result.get("prospective_outcomes", {})
    if outcomes.get("status") == "recorded_decisions_marked":
        lines += ["| Recorded decision model | Completed execution sessions | Total return | Maximum drawdown |",
                  "|---|---:|---:|---:|"]
        for row in outcomes["performance"]:
            lines.append(f"| {row['name']} | {row['sessions']} | {row['total_return']:.2%} | {row['max_drawdown']:.2%} |")
        lines += ["", outcomes["limits"], ""]
    lines += ["Research observation only. No account holdings, orders, or automatic promotion.", ""]
    (output / "readout.md").write_text("\n".join(lines))
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "daily_observation",
                "system": "fundamental-event-trader",
                "created_at_utc": result["captured_at_utc"],
                "code_sha256": result["code_sha256"],
                "action_authorized": False,
                "artifacts": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
            },
            indent=2,
        )
        + "\n"
    )
    return output


def configure(root: Path, dataset: Path, report: Path):
    data = load_dataset(dataset)
    frozen_policy(data, report)
    audit_report(report)
    payload = {
        key: {"path": str(path.resolve()), "manifest_sha256": sha(path / "manifest.json")}
        for key, path in (("dataset", dataset), ("report", report))
    }
    target = root / "data/runtime.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(target)
    return target


def audit_report(report: Path):
    checked = verify_report(report)
    data = load_dataset(Path(checked["frozen"]["dataset_root"]))
    policy, _ = frozen_policy(data, report)
    weight = targets(data.events, data.opens.index, data.identity, policy)
    pd.testing.assert_frame_equal(weight, pd.read_parquet(report / "selected_targets.parquet"))
    result = replay(data.opens, data.closes, weight, data.cash, terminal_events=data.terminals)
    saved = pd.read_parquet(report / "returns.parquet")[policy.name]
    np.testing.assert_allclose(result.returns, saved, rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(
        result.fills, pd.read_parquet(report / "selected_fills.parquet"), check_dtype=False
    )
    if "selected_realized_weights.parquet" not in checked["manifest"]["artifacts"]:
        raise DataGateError("Research report omits realized holdings")
    pd.testing.assert_frame_equal(
        result.weights, pd.read_parquet(report / "selected_realized_weights.parquet")
    )
    frame = pd.read_csv(report / "performance.csv")
    for period, (start, end) in checked["frozen"]["partitions"].items():
        expected = metrics(result, start, end)
        actual = frame[frame.name.eq(policy.name) & frame.period.eq(period)].iloc[0]
        for key, value in expected.items():
            if not np.isclose(actual[key], value, rtol=1e-9, atol=1e-12):
                raise DataGateError("Saved performance does not reconcile to native replay")
    return {
        "status": "passed_research_integrity",
        "authority": "research_only",
        "action_authorized": False,
    }
