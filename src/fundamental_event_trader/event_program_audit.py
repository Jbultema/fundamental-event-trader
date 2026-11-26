"""Auditable ten-family research feasibility; no fabricated strategy-performance results."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from fundamental_event_trader.qualification import qualify
from fundamental_event_trader.sec import DataGateError, sha

FAMILIES = (
    ("guidance", "Guidance revisions", ("own_prior_revision", "material_revision", "repeated_revision"),
     "original_guidance_releases_and_metric_matched_prior_guidance"),
    ("cash_conversion", "Cash conversion deterioration", ("cash_earnings_gap", "industry_working_capital", "persistence_and_repair"),
     "original_matched_duration_financials_and_historical_industry"),
    ("financing", "Financing stress and relief", ("event_category", "liquidity_scaled_severity", "relief_reentry"),
     "original_funding_disclosures_and_then_known_liquidity"),
    ("insider_clusters", "Insider purchase clusters", ("verified_purchases", "distinct_owner_commitment", "cluster_price_repair"),
     "original_form4_ownership_transaction_and_publication_evidence"),
    ("capital_returns", "Executed capital returns", ("authorization_vs_execution", "net_share_reduction", "funding_quality"),
     "original_execution_issuance_and_funding_disclosures"),
    ("customer_propagation", "Customer to supplier propagation", ("customer_event", "historical_exposure_scaled", "sector_propagation"),
     "historically_known_relationship_graph_and_original_customer_events"),
    ("disruptions", "Operational disruption and resolution", ("interruption_category", "measured_persistence", "documented_resolution"),
     "original_disruption_versions_and_resolution_publication_times"),
    ("governance", "Governance and accounting warnings", ("event_category", "documented_adverse_context", "remediation_reentry"),
     "original_governance_or_accounting_event_and_context"),
    ("regulatory_legal", "Regulatory and legal outcomes", ("procedural_stage", "prior_public_circumstances", "sector_implementation"),
     "original_decisions_prior_circumstances_and_release_times"),
    ("original_reporting", "Original financial reporting", ("original_vs_syndicated", "incremental_novelty", "corroboration_price_control"),
     "licensed_versioned_historical_article_corpus_with_entity_mapping"),
)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def verify_receipt(folder: Path):
    receipt = json.loads((folder / "probe.json").read_text())
    if receipt.get("kind") != "source_feasibility_not_performance":
        raise DataGateError("Wrong source receipt type")
    if receipt.get("action_authorized") is not False:
        raise DataGateError("Source feasibility cannot authorize allocation")
    for row in receipt["checks"]:
        if row.get("path"):
            file = (folder / row["path"]).resolve()
            if not file.is_relative_to(folder.resolve()) or sha(file) != row["sha256"]:
                raise DataGateError("Source receipt bytes changed or escaped the capture")
    return receipt


def fda_sample(body: bytes):
    payload = json.loads(body)
    records = payload["results"]
    if not records or not isinstance(records, list):
        raise DataGateError("Nonempty FDA sample required")
    frame = pd.DataFrame(records)
    reports = pd.to_datetime(frame.report_date, format="%Y%m%d", errors="coerce")
    initiated = pd.to_datetime(frame.get("recall_initiation_date"), format="%Y%m%d", errors="coerce")
    terminated = pd.to_datetime(frame.get("termination_date"), format="%Y%m%d", errors="coerce")
    ids = frame.event_id.replace("", pd.NA).dropna() if "event_id" in frame else pd.Series(dtype=str)
    duplicate_products = int(ids.duplicated().sum())
    if reports.isna().any():
        raise DataGateError("FDA sample has invalid or missing report dates")
    return {
        "kind": "source_structure_diagnostic_not_event_strategy",
        "sample_records": len(frame),
        "reported_total_records": payload.get("meta", {}).get("results", {}).get("total"),
        "source_last_updated": payload.get("meta", {}).get("last_updated"),
        "sample_first_report": str(reports.min().date()),
        "sample_last_report": str(reports.max().date()),
        "sample_unique_firms": int(frame.recalling_firm.nunique()),
        "sample_unique_event_ids": int(ids.nunique()),
        "duplicate_event_id_products": duplicate_products,
        "initiation_precedes_report": int(initiated.lt(reports).sum()) if initiated is not None else None,
        "termination_after_report": int(terminated.gt(reports).sum()) if terminated is not None else None,
        "security_id_fields_present": sorted(set(frame) & {"security_id", "cik", "ticker"}),
        "historical_version_fields_present": sorted(set(frame) & {"first_published_at", "version_at", "first_observed_at"}),
        "not_valid_onset_features": ["termination_date", "final_status", "eventual_duration"],
        "source_documented_revisions": True,
        "source_documentation": "https://open.fda.gov/apis/drug/enforcement/",
        "historical_strategy_qualified": False,
        "sample_is_not_random_or_representative": True,
        "required_followups": [
            "deduplicate_product_rows_into_announced_events",
            "verify_original_publication_and_historical_versions",
            "map_then_known_public_parent_security_including_failed_parents",
            "obtain_adjusted_prices_and_terminal_treatment",
            "validate_each_historical_feature_against_original_release",
        ],
    }


def current_listing(body: bytes):
    lines = body.decode().splitlines()
    data = list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|"))
    rows = [row for row in data if not row.get("Symbol", "").startswith("File Creation Time")]
    return {
        "kind": "current_listing_not_historical_membership",
        "rows": len(rows),
        "file_creation_record": next((line for line in lines if line.startswith("File Creation Time")), None),
        "historical_universe_qualified": False,
        "limitations": ["no_past_membership_intervals", "no_failed_security_terminal_settlements", "no_point_in_time_issuer_mapping"],
    }


def program(protocol: Path):
    return {
        "schema_version": 1,
        "kind": "ten_family_company_event_program",
        "decision_date": "2026-11-25",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "protocol_sha256": sha(protocol),
        "families": [
            {"id": key, "name": name, "required_content_evidence": requirement,
             "formulations": [{"id": f"{key}.{variant}", "status": "registered_not_implemented_not_tested"} for variant in variants]}
            for key, name, variants, requirement in FAMILIES
        ],
        "historical_text_extraction": "rules_or_return_blind_verified_labels_no_uncontrolled_future_model_knowledge",
        "holding_windows_sessions": [21, 63, 126],
        "primary_window_sessions": 63,
        "execution_lags_sessions": [1, 2, 5],
        "costs_bps_per_side": [10, 25, 50],
        "simultaneous_stress": [{"lag": 5, "cost_bps": 25}, {"lag": 5, "cost_bps": 50}],
        "max_followup_rounds_before_new_protocol": 2,
        "minimum_screening_coverage": {"issuer_event_clusters": 100, "issuers": 30, "years": 5},
        "promotion_screen": {"return_improvement": .01, "max_drawdown_worsening": .02, "drawdown_improvement_alternative": .05, "max_cagr_sacrifice_alternative": .01},
        "source_checks_are_performance_tests": False,
        "portfolio_allocation_allowed": False,
    }


def real_data_qualification(dataset: Path | None):
    state = qualify(dataset)
    if state["historical_event_study_allowed"]:
        from fundamental_event_trader.research import load_dataset

        try:
            load_dataset(dataset)
        except (DataGateError, OSError, KeyError, TypeError) as exc:
            state = dict(state, status="blocked", historical_event_study_allowed=False,
                         errors=[*state["errors"], f"real_portfolio_input_gate:{str(exc)[:200]}"])
    return state


def audit(receipt_folder: Path, protocol: Path, output: Path, *, dataset: Path | None = None):
    # Verify before creating an output so corrupted input cannot leave a success-shaped report.
    receipt = verify_receipt(receipt_folder)
    if output.exists():
        raise DataGateError("Research audit output must be new and immutable")
    frozen = program(protocol)
    state = real_data_qualification(dataset)
    if state["historical_event_study_allowed"]:
        # This tool is only a source audit; it must never silently call the unrelated
        # legacy 48-policy engine or claim the new 30 specifications were executed.
        dataset_state = "base_dataset_qualified_family_extraction_and_execution_still_required"
    else:
        dataset_state = "historical_dataset_not_qualified"
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(protocol, output / "protocol.md")
    shutil.copyfile(__file__, output / "auditor.py")
    shutil.copytree(receipt_folder, output / "source_receipts")
    write_json(output / "registry.json", frozen)
    write_json(output / "dataset_qualification.json", state)
    source_rows = {row["source"]: row for row in receipt["checks"]}
    if source_rows.get("fda_enforcement", {}).get("http_status") == 200:
        row = source_rows["fda_enforcement"]
        if row.get("truncated") is True:
            raise DataGateError("Truncated FDA source is not an auditable sample")
        write_json(output / "fda_structure_audit.json", fda_sample((receipt_folder / row["path"]).read_bytes()))
    if source_rows.get("nasdaq_current_list", {}).get("http_status") == 200:
        row = source_rows["nasdaq_current_list"]
        write_json(output / "current_listing_audit.json", current_listing((receipt_folder / row["path"]).read_bytes()))
    rows = []
    for key, name, variants, requirement in FAMILIES:
        rows.append({
            "family": key, "name": name, "registered_formulations": len(variants),
            "status": "blocked_data" if not state["historical_event_study_allowed"] else "awaiting_family_content_and_runner_validation",
            "dataset_status": dataset_state,
            "missing_family_evidence": requirement,
            "qualified_real_data_strategies_tested": 0,
            "negative_performance_finding": False,
            "benefit_estimate": None,
            "next_gate": "legitimately_obtain_and_qualify_required_source_census_prices_then_validate_extractor",
        })
    write_json(output / "family_decisions.json", rows)
    pd.DataFrame(rows).to_csv(output / "family_decisions.csv", index=False)
    result = {
        "status": "blocked_data" if not state["historical_event_study_allowed"] else "source_audit_only_not_performance",
        "families_registered": len(rows),
        "formulations_registered": sum(len(f[2]) for f in FAMILIES),
        "source_requests": len(receipt["checks"]),
        "qualified_real_data_strategies_tested": 0,
        "performance_scenarios_tested": 0,
        "research_hypotheses_rejected": 0,
        "research_options_exhausted": False,
        "portfolio_allocation_allowed": False,
        "conclusion": "Data feasibility was executed. Company-event profitability remains untested, not disproven.",
        "artifacts": {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()},
    }
    write_json(output / "manifest.json", result)
    return result


def verify_audit(output: Path):
    manifest = json.loads((output / "manifest.json").read_text())
    for relative, expected in manifest["artifacts"].items():
        file = (output / relative).resolve()
        if not file.is_relative_to(output.resolve()) or not file.is_file() or sha(file) != expected:
            raise DataGateError("Event program audit artifact changed")
    registry = json.loads((output / "registry.json").read_text())
    if sha(output / "protocol.md") != registry["protocol_sha256"]:
        raise DataGateError("Program protocol mismatch")
    expected_registry = program(output / "protocol.md")
    if any(registry.get(key) != value for key, value in expected_registry.items() if key != "frozen_at_utc"):
        raise DataGateError("Frozen research specification changed")
    receipt = verify_receipt(output / "source_receipts")
    checks = {row["source"]: row for row in receipt["checks"]}
    for name, artifact, derive in (
        ("fda_enforcement", "fda_structure_audit.json", fda_sample),
        ("nasdaq_current_list", "current_listing_audit.json", current_listing),
    ):
        if checks.get(name, {}).get("http_status") == 200:
            file = output / "source_receipts" / checks[name]["path"]
            if json.loads((output / artifact).read_text()) != derive(file.read_bytes()):
                raise DataGateError("Source diagnostic does not reconstruct from raw bytes")
    state = json.loads((output / "dataset_qualification.json").read_text())
    decisions = json.loads((output / "family_decisions.json").read_text())
    expected_status = "blocked_data" if not state["historical_event_study_allowed"] else "awaiting_family_content_and_runner_validation"
    if (
        len(decisions) != len(FAMILIES)
        or [row["family"] for row in decisions] != [row[0] for row in FAMILIES]
        or any(row["status"] != expected_status or row["qualified_real_data_strategies_tested"] != 0
               or row["negative_performance_finding"] is not False or row["benefit_estimate"] is not None for row in decisions)
    ):
        raise DataGateError("Source-only family decision or performance count is invalid")
    if (
        manifest["qualified_real_data_strategies_tested"] != 0
        or manifest["performance_scenarios_tested"] != 0
        or manifest["research_hypotheses_rejected"] != 0
        or manifest["research_options_exhausted"] is not False
        or manifest["portfolio_allocation_allowed"] is not False
        or manifest["families_registered"] != len(FAMILIES)
        or manifest["formulations_registered"] != sum(len(f[2]) for f in FAMILIES)
        or manifest["source_requests"] != len(receipt["checks"])
    ):
        raise DataGateError("A source audit cannot claim performance or allocation authority")
    return {"verified": True, "source_audit_only": True, "portfolio_allocation_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("audit")
    create.add_argument("--receipts", type=Path, required=True)
    create.add_argument("--protocol", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--dataset", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "audit":
        print(json.dumps(audit(args.receipts, args.protocol, args.output, dataset=args.dataset), indent=2))
    else:
        print(json.dumps(verify_audit(args.report), indent=2))


if __name__ == "__main__":
    main()
