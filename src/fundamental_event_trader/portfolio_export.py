"""Portfolio Lab comparative-research contract, never a live allocation authorization."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from fundamental_event_trader.operating import audit_report, frozen_policy, resolve_config
from fundamental_event_trader.research import code_hash, load_dataset
from fundamental_event_trader.sec import DataGateError, sha, timestamp
from fundamental_event_trader.strategy import session_schedule, targets


def export(root: Path, output: Path, *, dataset=None, report=None) -> Path:
    initial = code_hash()
    dataset, report = resolve_config(root, dataset, report)
    if dataset is None or report is None:
        raise DataGateError("No configured qualified dataset and frozen portfolio research")
    audit_report(report)
    data = load_dataset(dataset)
    policy, _ = frozen_policy(data, report)
    weight = targets(data.events, data.opens.index, data.identity, policy)
    closes = session_schedule(data.opens.index).close
    for row in data.terminals.itertuples():
        weight.loc[closes.ge(timestamp(row.settlement_at)), row.security_id] = 0.0
    if (weight.gt(0) & data.closes.reindex(columns=weight.columns).isna()).any().any():
        raise DataGateError("Unpriced comparative target, including terminal treatments")
    output.mkdir(parents=True, exist_ok=False)
    dates = data.opens.index.tz_convert("America/New_York").normalize().tz_localize(None)
    price = data.closes.copy()
    price.index = dates
    weight.index = dates
    cash = data.cash.copy()
    cash.index = dates
    price.to_parquet(output / "prices.parquet")
    weight.to_parquet(output / "weights.parquet")
    cash.to_frame("cash_return").to_parquet(output / "cash_returns.parquet")
    settlements = []
    for row in data.terminals.itertuples():
        position = closes.searchsorted(timestamp(row.settlement_at), side="left")
        if position < len(dates):
            settlements.append(
                {
                    "security_id": row.security_id,
                    "settlement_session": str(dates[position].date()),
                    "value_per_adjusted_share": float(row.value_per_adjusted_share),
                }
            )
    (output / "terminal_events.json").write_text(json.dumps(settlements, indent=2) + "\n")
    qualification = {
        "schema_version": 1,
        "qualified_real_dataset": True,
        "native_research_audit": "passed_research_integrity",
        "dataset_manifest_sha256": sha(dataset / "manifest.json"),
        "research_manifest_sha256": sha(report / "manifest.json"),
        "code_sha256": initial,
        "data_kind": "real_historical",
        "fixture_only": False,
        "source_census_includes_delisted": True,
        "explicit_terminal_cash_exported": True,
        "portfolio_allocation_allowed": False,
        "automatic_promotion_allowed": False,
        "common_execution_difference": "Common close-known/next-close comparison; native research fills next open",
    }
    (output / "qualification.json").write_text(json.dumps(qualification, indent=2) + "\n")
    manifest = {
        "schema_version": 1,
        "system": "fundamental-event-trader",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "authority": "research_only",
        "automatic_promotion_allowed": False,
        "native_execution": "close-known event targets; next regular-session open; drift and costs; explicit terminal cash",
        "code_sha256": initial,
        "data_end": str(dates[-1].date()),
        "source_inputs": {
            "dataset_manifest": sha(dataset / "manifest.json"),
            "research_manifest": sha(report / "manifest.json"),
        },
        "primary_expert": f"fundamental-event-trader:{policy.name}",
        "experts": [
            {
                "id": f"fundamental-event-trader:{policy.name}",
                "role": "primary",
                "family": "fundamental_event",
                "weights_file": "weights.parquet",
                "target_semantics": "close_known_risky_budgets",
                "evidence_status": "retrospective_research",
                "evaluation_start": str(dates[0].date()),
            }
        ],
        "artifacts": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
    }
    if code_hash() != initial:
        raise DataGateError("Source changed during export")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        print(export(Path.cwd(), args.output, dataset=args.dataset, report=args.report))
    except (OSError, ValueError, KeyError, AssertionError) as exc:
        print(json.dumps({"status": "blocked", "action_authorized": False, "error": str(exc)}))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
