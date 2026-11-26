"""Offline ingestion of byte-preserved official SEC bulk archives and filing history."""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import numpy as np
import pandas as pd

from fundamental_event_trader.features import accounting_features
from fundamental_event_trader.sec import (
    DataGateError,
    normalize_facts,
    normalize_submissions,
    sha,
    timestamp,
)

OFFICIAL_BULK = {
    "submissions": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
    "companyfacts": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
}


def extract_issuer(submissions: Path, facts: Path, cik: str, output: Path, *, captured_at) -> Path:
    """Import official archives already obtained legitimately; never retry blocked access.

    This is an issuer capture, not a survivor-free universe or original-filing-vintage
    certification. Full archive hashes preserve the exact acquired revision.
    """
    capture_time = timestamp(captured_at)
    if capture_time > pd.Timestamp.now(tz="UTC"):
        raise DataGateError("Archive capture timestamp cannot be in the future")
    if not cik.isdigit() or not 0 < int(cik) < 10**10:
        raise DataGateError("Positive issuer CIK required")
    cik = cik.zfill(10)
    extracted = {}
    source = []
    for kind, archive in (("submissions", submissions), ("companyfacts", facts)):
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            if len(names) != len(set(names)):
                raise DataGateError("Duplicate archive members prohibited")
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name:
                    raise DataGateError("Unsafe archive path")
            expected = f"CIK{cik}.json"
            if expected not in names:
                raise DataGateError("Issuer missing from declared official bulk archive")
            selected = [expected]
            if kind == "submissions":
                if z.getinfo(expected).file_size > 20_000_000:
                    raise DataGateError("Oversized issuer submission payload")
                root = json.loads(z.read(expected))
                if str(root.get("cik", "")).zfill(10) != cik:
                    raise DataGateError("Archive issuer mismatch")
                declared = [r["name"] for r in root.get("filings", {}).get("files", [])]
                if any(not re.fullmatch(rf"CIK{cik}-submissions-\d+\.json", n) for n in declared):
                    raise DataGateError("Invalid archived submission reference")
                missing = set(declared) - set(names)
                if missing:
                    raise DataGateError("Bulk archive omits declared older submission files")
                selected += declared
            for name in selected:
                info = z.getinfo(name)
                if (
                    info.file_size > 20_000_000
                    or info.compress_size == 0
                    or info.file_size / info.compress_size > 1000
                ):
                    raise DataGateError("Oversized or suspicious compressed SEC document")
                content = z.read(name)
                json.loads(content)
                filename = (
                    "submissions.json"
                    if kind == "submissions" and name == expected
                    else "companyfacts.json"
                    if kind == "companyfacts"
                    else name
                )
                extracted[filename] = content
            source.append(
                {"kind": kind, "source_url": OFFICIAL_BULK[kind], "archive_sha256": sha(archive)}
            )
    output.mkdir(parents=True, exist_ok=False)
    for name, content in extracted.items():
        (output / name).write_bytes(content)
    payload = {
        "schema_version": 1,
        "cik": cik,
        "source": "official_sec_edgar_bulk_import",
        "captured_at_utc": capture_time.isoformat(),
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "status": "access_passed_not_universe_qualified",
        "source_archives": source,
        "documents": [
            {"path": name, "sha256": sha(output / name), "passed": True} for name in extracted
        ],
        "archived_submission_paths": [name for name in extracted if name.startswith("CIK")],
        "historical_strategy_authorized": False,
        "action_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return output / "manifest.json"


def all_submissions(folder: Path, meta: dict) -> pd.DataFrame:
    for document in meta["documents"]:
        file = (folder / document["path"]).resolve()
        if not file.is_relative_to(folder.resolve()) or sha(file) != document["sha256"]:
            raise DataGateError("Captured SEC bytes changed")
    root = json.loads((folder / "submissions.json").read_text())
    frames = [normalize_submissions(root, meta["captured_at_utc"])]
    declared = {r["name"] for r in root.get("filings", {}).get("files", [])}
    bound = {d["path"] for d in meta["documents"]}
    for name in meta.get("archived_submission_paths", []):
        if name not in declared or name not in bound:
            raise DataGateError("Archived submission is not declared and hash-bound")
        history = json.loads((folder / name).read_text())
        frames.append(
            normalize_submissions(
                {"cik": root["cik"], "filings": {"recent": history}}, meta["captured_at_utc"]
            )
        )
    combined = pd.concat(frames, ignore_index=True)
    for _, group in combined.groupby("accession"):
        if len(group.drop_duplicates()) != 1:
            raise DataGateError("Conflicting archived filing acceptance evidence")
    return combined.drop_duplicates("accession").sort_values(["accepted_at", "accession"])


def normalize(folder: Path, output: Path) -> Path:
    meta = json.loads((folder / "manifest.json").read_text())
    if meta["status"] != "access_passed_not_universe_qualified":
        raise DataGateError("Official acquisition did not pass")
    filings = all_submissions(folder, meta)
    raw_facts = json.loads((folder / "companyfacts.json").read_text())
    facts = normalize_facts(raw_facts, filings)
    events = annual_events(facts, filings, meta["cik"], sha(folder / "companyfacts.json"))
    output.mkdir(parents=True, exist_ok=False)
    filings.to_parquet(output / "filings.parquet", index=False)
    facts.to_parquet(output / "facts.parquet", index=False)
    events.to_parquet(output / "issuer_features.parquet", index=False)
    shutil.copyfile(folder / "companyfacts.json", output / "companyfacts.json")
    report = {
        "source_manifest_sha256": sha(folder / "manifest.json"),
        "filings": len(filings),
        "facts": len(facts),
        "accounting_events": len(events),
        "authority": "research_only",
        "historical_strategy_authorized": False,
        "limitations": [
            "Historical security mapping and survivor-free universe remain required.",
            "Current Company Facts archive is not independent proof of preserved original filing vintages.",
            "Annual same-duration accounting only; no inferred quarterly cash flows.",
        ],
        "artifacts": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return output / "manifest.json"


def annual_events(facts, filings, cik, source_sha256):
    """New annual content only; amendments do not refresh stale annual scores."""
    rows, emitted, latest_period = [], {}, None
    annual = filings[filings.form.isin(["10-K", "10-K/A"])].sort_values(["accepted_at", "accession"])
    for filing in annual.itertuples():
        if not filing.report_date:
            continue
        period = pd.Timestamp(filing.report_date)
        if pd.isna(period) or period.tzinfo is not None:
            raise DataGateError("Annual report date must be an unambiguous fiscal date")
        if latest_period is not None and period < latest_period:
            continue
        latest_period = period
        current_facts = facts[facts.accession.eq(filing.accession)]
        values = accounting_features(current_facts, filing.accepted_at, cik, period_end=period)
        prior = facts[
            (pd.to_datetime(facts.end) - period).dt.days.between(-400, -300)
            & pd.to_datetime(facts.accepted_at, utc=True).le(filing.accepted_at)
            & facts.cik.eq(str(cik).zfill(10))
            & facts.tag.isin(["NetIncomeLoss", "ProfitLoss"])
        ]
        previous = np.nan
        if not prior.empty:
            previous = accounting_features(
                facts, filing.accepted_at, cik, period_end=pd.to_datetime(prior.end).max()
            )["profitability"]
        measures = {
            "profitability_change": values.get("profitability", np.nan) - previous,
            "cash_conversion": values.get("cash_conversion", np.nan),
            "net_repurchase": values.get("net_repurchase", np.nan),
        }
        if not any(np.isfinite(value) for value in measures.values()):
            continue
        signature = tuple(float(v) if np.isfinite(v) else None for v in measures.values())
        if emitted.get(period) == signature:
            continue
        emitted[period] = signature
        rows.append({
            "cik": str(cik).zfill(10), "accession": filing.accession,
            "accepted_at": filing.accepted_at, "available_at": filing.accepted_at,
            "fiscal_period_end": str(period.date()), **measures, "source_sha256": source_sha256,
        })
    return pd.DataFrame(rows, columns=[
        "cik", "accession", "accepted_at", "available_at", "fiscal_period_end",
        "profitability_change", "cash_conversion", "net_repurchase", "source_sha256",
    ])
