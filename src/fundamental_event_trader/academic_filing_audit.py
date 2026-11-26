"""Return-blind content pilot on pinned, independently published filing-corpus shards.

Filing dates are not acceptance timestamps. This module intentionally exports neither
accepted_at/available_at nor directional_signal and cannot supply a qualified event dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd
import pyarrow.parquet as pq

from fundamental_event_trader.features import parse_form4
from fundamental_event_trader.sec import ACCESSION, DataGateError, sha


def decode_object(value, expected):
    for _ in range(3):
        if isinstance(value, expected):
            return value
        if not isinstance(value, str):
            break
        value = json.loads(value)
    raise DataGateError("Corpus metadata is not the required structured JSON type")


def filing_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
        raise DataGateError("Corpus requires an explicit YYYYMMDD filing date")
    date = pd.to_datetime(value, format="%Y%m%d", errors="raise")
    return date, (date + pd.Timedelta(days=1)).tz_localize("America/New_York").tz_convert("UTC")


def extract_row(row, *, source_hash, row_number, shard):
    accession = row.get("metadata_accession-number")
    if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
        raise DataGateError("Missing original accession")
    date, ceiling = filing_date(row.get("metadata_filing-date"))
    docs = decode_object(row.get("metadata_documents"), list)
    if len(docs) != 1 or not isinstance(docs[0], dict):
        raise DataGateError("A unique document is required; no arbitrary attachment choice")
    form = docs[0].get("type")
    if form not in {"4", "4/A", "8-K", "8-K/A"}:
        raise DataGateError("Unexpected document family in selected corpus shard")
    body = row.get("content")
    if not isinstance(body, str) or not body or len(body.encode()) > 5_000_000:
        raise DataGateError("Missing or oversized source content")
    base = {
        "accession": accession, "filing_date": str(date.date()),
        "date_only_model_cutoff": ceiling.isoformat(),
        "cutoff_is_verified_acceptance": False,
        "form": form, "source_shard": shard, "source_row": row_number,
        "source_sha256": source_hash, "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "historical_strategy_allowed": False,
    }
    if form.startswith("4"):
        raw = body.encode()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise DataGateError("Entity-bearing XML prohibited")
        tree = ElementTree.fromstring(raw)
        if tree.tag != "ownershipDocument":
            raise DataGateError("Original ownership XML missing")
        base |= {"issuer_cik": tree.findtext("issuer/issuerCik", "").zfill(10),
                 "as_filed_ticker": tree.findtext("issuer/issuerTradingSymbol", ""),
                 "owner_count": len(tree.findall("reportingOwner"))}
        # The date-only ceiling is used only to check XML transaction chronology. It
        # is never exported as a real acceptance time or used to execute an order.
        transactions = parse_form4(raw, ceiling).rename(columns={"accepted_at": "date_only_model_cutoff"})
        if len(transactions):
            if pd.to_datetime(transactions.transaction_date).gt(date).any():
                raise DataGateError("Transaction follows the corpus filing date")
            transactions["accession"] = accession
            transactions["source_sha256"] = source_hash
            transactions["source_row"] = row_number
            transactions["source_shard"] = shard
            transactions["content_sha256"] = base["content_sha256"]
            transactions["cutoff_is_verified_acceptance"] = False
            transactions["historical_strategy_allowed"] = False
        base["purchase_sale_rows"] = len(transactions)
        base["content_status"] = "parsed_content_only_not_timing_or_universe_qualified"
        return base, transactions
    filer = decode_object(row.get("metadata_filer"), dict)
    company = filer.get("company-data", {})
    issuer = company.get("cik", "")
    if not isinstance(issuer, str) or not issuer.isdigit() or not 0 < int(issuer) < 10**10:
        raise DataGateError("Missing historical filing issuer CIK")
    base |= {"issuer_cik": issuer.zfill(10), "as_filed_ticker": None, "owner_count": None,
             "purchase_sale_rows": None, "content_status": "indexed_only_directional_content_unverified"}
    return base, pd.DataFrame()


def verify_acquisition(root):
    meta = json.loads((root / "acquisition.json").read_text())
    if meta.get("kind") != "pinned_academic_filing_shards_not_performance" or meta.get("action_authorized") is not False:
        raise DataGateError("Wrong academic acquisition type")
    if not meta.get("checks"):
        raise DataGateError("No acquired source shards")
    for item in meta["checks"]:
        file = (root / item.get("path", "")).resolve()
        if (item.get("status") != "acquired_integrity_verified_not_strategy_qualified"
                or not file.is_relative_to(root.resolve()) or not file.is_file()
                or file.stat().st_size != item["expected_bytes"]
                or sha(file) != item["expected_sha256"] or sha(file) != item["sha256"]):
            raise DataGateError("Academic shard does not match pinned publisher metadata")
        if not re.fullmatch(r"[0-9a-f]{40}", item.get("revision", "")):
            raise DataGateError("Immutable dataset revision required")
    return meta


def run(root: Path, output: Path):
    acquisition = verify_acquisition(root)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output / "auditor.py")
    shutil.copyfile(root / "acquisition.json", output / "acquisition.json")
    filings, transaction_frames, errors, summaries = [], [], [], []
    for item in acquisition["checks"]:
        counts = Counter()
        file = root / item["path"]
        cursor = 0
        for batch in pq.ParquetFile(file).iter_batches(batch_size=128):
            for row in batch.to_pylist():
                counts["source_rows"] += 1
                try:
                    record, transactions = extract_row(row, source_hash=item["sha256"], row_number=cursor, shard=item["path"])
                    filings.append(record)
                    if len(transactions):
                        transaction_frames.append(transactions)
                    counts["content_rows_parsed_or_indexed"] += 1
                    counts["purchase_sale_transaction_rows"] += len(transactions)
                except (DataGateError, ElementTree.ParseError, ValueError, TypeError, KeyError) as exc:
                    reason = f"{type(exc).__name__}: {str(exc)[:180]}"
                    errors.append({"source_shard": item["path"], "source_row": cursor,
                                   "accession": row.get("metadata_accession-number"), "reason": reason})
                    counts["rejected_rows"] += 1
                cursor += 1
        summaries.append({"source_shard": item["path"], "publisher_dataset_path": item["dataset_path"], **counts})
    frame = pd.DataFrame(filings)
    frame.to_parquet(output / "filing_content_pilot.parquet", index=False)
    transactions = pd.concat(transaction_frames, ignore_index=True) if transaction_frames else pd.DataFrame()
    transactions.to_parquet(output / "form4_content_pilot.parquet", index=False)
    pd.DataFrame(errors, columns=["source_shard", "source_row", "accession", "reason"]).to_csv(output / "rejections.csv", index=False)
    summary = {
        "kind": "return_blind_historical_filing_content_pilot",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_shards": summaries,
        "source_rows": sum(r["source_rows"] for r in summaries),
        "parsed_or_indexed_rows": len(frame), "rejected_rows": len(errors),
        "distinct_accessions_parsed": int(frame.accession.nunique()) if len(frame) else 0,
        "duplicate_accessions_parsed": int(frame.accession.duplicated().sum()) if len(frame) else 0,
        "filing_date_min": str(frame.filing_date.min()) if len(frame) else None,
        "filing_date_max": str(frame.filing_date.max()) if len(frame) else None,
        "parsed_issuer_ciks": int(frame.issuer_cik.nunique()) if len(frame) else 0,
        "form_counts": {str(k): int(v) for k, v in frame.form.value_counts().items()} if len(frame) else {},
        "purchase_sale_transactions": len(transactions),
        "purchase_transactions": int(transactions.code.eq("P").sum()) if len(transactions) else 0,
        "sale_transactions": int(transactions.code.eq("S").sum()) if len(transactions) else 0,
        "positive_dollar_purchase_transactions": int((transactions.code.eq("P") & transactions.dollars.gt(0)).sum()) if len(transactions) else 0,
        "purchase_scope": "open_market_or_private_not_verified_open_market_only",
        "rejection_reasons": dict(Counter(r["reason"] for r in errors)),
        "qualified_strategy_tests": 0,
        "historical_event_study_allowed": False,
        "portfolio_allocation_allowed": False,
        "limitations": [
            "three_selected_shards_not_complete_or_representative_census",
            "filing_dates_not_exact_public_acceptance_or_observed_times",
            "no_historical_security_mapping_or_price_and_terminal_paths",
            "no_post_filing_returns_or_strategy_performance_evaluated",
            "eightk_content_indexed_not_validated_directional_events",
            "rejected_source_rows_retained_as_coverage_gaps_not_dropped_in_silence",
            "purchase_code_does_not_establish_discretionary_open_market_scope",
            "no_insider_cluster_signal_from_incomplete_filing_census",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    manifest = {"kind": summary["kind"], "source_root": str(root.resolve()), "action_authorized": False,
                "source_shards": {r["path"]: r["sha256"] for r in acquisition["checks"]},
                "artifacts": {str(p.relative_to(output)): sha(p) for p in output.iterdir() if p.is_file()}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.sources, args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in {"rejection_reasons"}}, indent=2))


if __name__ == "__main__":
    main()
