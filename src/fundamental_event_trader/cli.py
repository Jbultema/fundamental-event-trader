from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from fundamental_event_trader.features import accounting_features, event_study, registry
from fundamental_event_trader.qualification import qualify, validate_dataset
from fundamental_event_trader.sec import (
    capture,
    import_swing_sidecar,
    normalize_facts,
    normalize_submissions,
    sha,
)


def normalize_capture(folder: Path, output: Path):
    metadata = json.loads((folder / "manifest.json").read_text())
    if metadata["status"] != "access_passed_not_universe_qualified":
        raise ValueError("Official data capture did not pass access/schema gates")
    for document in metadata["documents"]:
        if sha(folder / document["path"]) != document["sha256"]:
            raise ValueError("Captured official source changed")
    submissions = normalize_submissions(
        json.loads((folder / "submissions.json").read_text()), metadata["captured_at_utc"]
    )
    facts = normalize_facts(json.loads((folder / "companyfacts.json").read_text()), submissions)
    output.mkdir(parents=True, exist_ok=False)
    submissions.to_parquet(output / "filings.parquet", index=False)
    facts.to_parquet(output / "facts.parquet", index=False)
    features = accounting_features(facts, metadata["captured_at_utc"], metadata["cik"])
    # Missing concepts are explicit nulls, never zero-valued bullish signals.
    (output / "features.json").write_text(pd.Series(features).to_json(indent=2) + "\n")
    manifest = {
        "source_manifest_sha256": sha(folder / "manifest.json"),
        "filings": len(submissions),
        "facts": len(facts),
        "capture_time": metadata["captured_at_utc"],
        "authority": "research_only",
        "historical_strategy_authorized": False,
        "limitation": "Only accessions in the recent submissions payload are admitted; older facts are omitted until archived submissions are acquired.",
        "artifacts": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Public-data fundamental/event research; fail-closed"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("capture")
    p.add_argument("--cik", required=True)
    p.add_argument("--output", required=True, type=Path)
    p = sub.add_parser("normalize")
    p.add_argument("--capture", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p = sub.add_parser("import-swing-sidecar")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p = sub.add_parser("qualify")
    p.add_argument("--dataset", type=Path)
    p.add_argument("--output", type=Path)
    p = sub.add_parser("registry")
    p.add_argument("--output", type=Path)
    p = sub.add_parser("research")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "capture":
        path = capture(args.cik, args.output)
        print(path)
        if json.loads(path.read_text())["status"] == "blocked":
            raise SystemExit(2)
    elif args.command == "normalize":
        normalize_capture(args.capture, args.output)
    elif args.command == "import-swing-sidecar":
        print(import_swing_sidecar(args.manifest, args.output))
    elif args.command == "registry":
        encoded = (
            json.dumps(
                {
                    "hypotheses": registry(),
                    "tested_on_real_data": False,
                    "action_authorized": False,
                },
                indent=2,
            )
            + "\n"
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as handle:
                handle.write(encoded)
        else:
            print(encoded)
    elif args.command == "qualify":
        result = qualify(args.dataset)
        encoded = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as handle:
                handle.write(encoded)
        print(encoded)
        if not result["historical_event_study_allowed"]:
            raise SystemExit(2)
    else:
        status = qualify(args.dataset)
        if not status["historical_event_study_allowed"]:
            print(json.dumps(status, indent=2))
            raise SystemExit(2)
        events, prices = validate_dataset(args.dataset)
        args.output.mkdir(parents=True, exist_ok=False)
        # Event studies are not portfolio backtests; overlapping observations
        # must not be annualized as tradable CAGR or treated as independent.
        for horizon in (5, 21, 63):
            for cost in (20, 50, 100):
                event_study(events, prices, horizon=horizon, roundtrip_bps=cost).to_parquet(
                    args.output / f"events_h{horizon}_c{cost}.parquet", index=False
                )
        (args.output / "manifest.json").write_text(
            json.dumps(
                {
                    "dataset_manifest_sha256": sha(args.dataset / "manifest.json"),
                    "authority": "event_study_only",
                    "strategy_promoted": False,
                    "portfolio_cagr_claim_allowed": False,
                    "clustered_uncertainty_required_before_inference": True,
                    "artifacts": {p.name: sha(p) for p in args.output.iterdir()},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
