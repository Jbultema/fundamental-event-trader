"""Export conditional event probes for isolated comparison, never specialist admission."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fundamental_event_trader import event_sample_portfolio as baseline
from fundamental_event_trader import event_structural_research as structural
from fundamental_event_trader.event_sample_pilot import bound_file, features, load_sample
from fundamental_event_trader.sec import DataGateError, sha


def verified_report(root):
    manifest = json.loads((root / "manifest.json").read_text())
    for name, digest in manifest["artifacts"].items():
        bound_file(root, name, digest)
    summary = json.loads((root / "summary.json").read_text())
    if summary.get("portfolio_allocation_allowed") is not False:
        raise DataGateError("Conditional research cannot carry allocation authority")
    for name, digest in manifest["code_hashes"].items():
        if sha(Path(__file__).parent / name) != digest:
            raise DataGateError("Source policy changed since the cited conditional study")
    return manifest, summary


def export(original_sources, structural_sources, original_report, structural_report, output):
    first_meta, first_summary = verified_report(original_report)
    next_meta, next_summary = verified_report(structural_report)
    protocol, facts, prices, evidence = load_sample(original_sources)
    _, next_facts, next_prices, next_evidence = structural.source_check(structural_sources, original_sources)
    if evidence != first_meta["source_evidence"] or next_evidence != next_meta["sources"]:
        raise DataGateError("Studies and exported inputs do not share the same sources")
    if not prices.equals(next_prices):
        raise DataGateError("Conditional studies use different price vintages")
    closes = baseline.load_closes(original_sources, prices)
    targets, experts = {}, []
    for prefix, rows, specs in (
        ("event", features(facts), baseline.specifications()),
        ("structural", structural.structural_features(next_facts), structural.specs()),
    ):
        for spec in specs:
            if spec["role"] != "candidate":
                continue
            name = f"{prefix}__{spec['name']}"
            target = baseline.policy_targets(rows, closes, spec)
            if prefix == "structural":
                target["JPM"] = 0.
            target.index = target.index.tz_convert("America/New_York").normalize().tz_localize(None)
            targets[name] = target
            experts.append({"id": name, "weights_file": f"{name}.parquet", "specification": spec,
                "evaluation_start": "2023-01-03", "evidence_status": "conditional_survivor_sample_not_admitted",
                "target_semantics": "close_known_risky_budgets", "portfolio_allocation_allowed": False})
    closes.index = closes.index.tz_convert("America/New_York").normalize().tz_localize(None)
    output.mkdir(parents=True, exist_ok=False)
    closes.to_parquet(output / "prices.parquet")
    for name, target in targets.items():
        target.to_parquet(output / f"{name}.parquet")
    summary = {"source_summaries": [first_summary, next_summary], "conditional_portfolio_paths": 520,
               "qualified_broad_strategies": 0, "portfolio_allocation_allowed": False,
               "not_all_ten_event_families_tested": True}
    (output / "research_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {"schema_version": 1, "kind": "conditional_event_probes_v1", "system": "fundamental-event-trader",
        "authority": "isolated_conditional_research_only", "portfolio_allocation_allowed": False,
        "automatic_promotion_allowed": False, "admitted_specialist": False,
        "experts": experts, "data_end": str(closes.index[-1].date()),
        "limitations": ["current_survivors", "ten_stocks_only", "unverified_original_release_vintages",
                        "not_qualified_for_main_allocator", "previously_inspected_returns", "no_failed_security_paths"],
        "source_reports": [{"path": str(p.resolve()), "manifest_sha256": sha(p / "manifest.json")}
                           for p in (original_report, structural_report)],
        "source_inputs": evidence + next_evidence,
        "exporter_sha256": sha(Path(__file__)),
        "artifacts": {p.name: sha(p) for p in output.iterdir() if p.is_file()}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"output": str(output), "probes": len(experts), "portfolio_allocation_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-sources", type=Path, required=True)
    parser.add_argument("--structural-sources", type=Path, required=True)
    parser.add_argument("--original-report", type=Path, required=True)
    parser.add_argument("--structural-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.original_sources, args.structural_sources,
                            args.original_report, args.structural_report, args.output)))


if __name__ == "__main__":
    main()
