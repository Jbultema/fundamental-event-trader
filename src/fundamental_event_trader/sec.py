from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

USER_AGENT = (
    "fundamental-event-trader research https://github.com/Jbultema/fundamental-event-trader"
)
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")


class DataGateError(ValueError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise DataGateError("Acceptance and as-of timestamps must include a timezone")
    return stamp.tz_convert("UTC")


def capture(cik: str, output: Path, *, user_agent: str = USER_AGENT, session=None) -> Path:
    if not cik.isdigit() or len(cik) > 10 or int(cik) == 0:
        raise DataGateError("CIK must be a positive integer of at most 10 digits")
    if "@" not in user_agent and "https://" not in user_agent:
        raise DataGateError("Declare a research contact in the SEC user agent")
    output.mkdir(parents=True, exist_ok=False)
    cik = cik.zfill(10)
    client = session or requests.Session()
    documents = []
    for kind, url in (
        ("submissions", f"https://data.sec.gov/submissions/CIK{cik}.json"),
        ("companyfacts", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"),
    ):
        path = output / f"{kind}.json"
        status, error = None, None
        try:
            response = client.get(
                url,
                headers={
                    "User-Agent": user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            status = response.status_code
            path.write_bytes(response.content)
            response.raise_for_status()
            payload = response.json()
            if int(payload.get("cik", -1)) != int(cik):
                raise DataGateError("SEC document issuer identity mismatch")
            if kind == "submissions":
                normalize_submissions(payload, datetime.now(UTC))
            elif not payload.get("facts"):
                raise DataGateError("SEC Company Facts document is empty")
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            error = f"{type(exc).__name__}: {str(exc)[:250]}"
        documents.append(
            {
                "kind": kind,
                "url": url,
                "http_status": status,
                "path": path.name if path.exists() else None,
                "sha256": sha(path) if path.exists() else None,
                "passed": error is None,
                "error": error,
            }
        )
        if error:
            break  # Do not retry around access controls or substitute unofficial mirrors.
        time.sleep(0.25)
    payload = {
        "schema_version": 1,
        "cik": cik,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "source": "official_sec_edgar",
        "documents": documents,
        "status": "access_passed_not_universe_qualified"
        if len(documents) == 2 and all(d["passed"] for d in documents)
        else "blocked",
        "historical_strategy_authorized": False,
        "action_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return output / "manifest.json"


def normalize_submissions(payload: dict, captured_at) -> pd.DataFrame:
    recent = payload.get("filings", {}).get("recent", {})
    required = ("accessionNumber", "acceptanceDateTime", "form", "filingDate", "reportDate")
    if any(k not in recent for k in required) or len({len(recent[k]) for k in required}) != 1:
        raise DataGateError("Malformed SEC submission arrays")
    capture_time = timestamp(captured_at)
    rows = []
    seen = set()
    for i, accession in enumerate(recent["accessionNumber"]):
        if not ACCESSION.fullmatch(accession) or accession in seen:
            raise DataGateError("Invalid or duplicate accession")
        seen.add(accession)
        accepted = timestamp(recent["acceptanceDateTime"][i])
        if accepted > capture_time:
            continue
        rows.append(
            {
                "cik": str(payload["cik"]).zfill(10),
                "accession": accession,
                "accepted_at": accepted,
                "form": recent["form"][i],
                "report_date": recent["reportDate"][i],
                "filing_date": recent["filingDate"][i],
                "amendment": recent["form"][i].endswith("/A"),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "cik",
            "accession",
            "accepted_at",
            "form",
            "report_date",
            "filing_date",
            "amendment",
        ],
    )


def normalize_facts(payload: dict, submissions: pd.DataFrame) -> pd.DataFrame:
    issuer = str(payload["cik"]).zfill(10)
    if len(submissions) and not submissions.cik.eq(issuer).all():
        raise DataGateError("Cross-issuer facts/submission join prohibited")
    acceptance = submissions.set_index("accession").accepted_at.to_dict()
    rows = []
    for taxonomy, concepts in payload.get("facts", {}).items():
        if taxonomy != "us-gaap":
            continue
        for tag, detail in concepts.items():
            for unit, observations in detail.get("units", {}).items():
                for fact in observations:
                    accession = fact.get("accn")
                    value = fact.get("val")
                    if (
                        accession not in acceptance
                        or not isinstance(value, (int, float))
                        or not np.isfinite(value)
                    ):
                        continue
                    end = pd.Timestamp(fact["end"])
                    start = pd.Timestamp(fact["start"]) if fact.get("start") else pd.NaT
                    if end.date() > acceptance[accession].date() or (
                        pd.notna(start) and start > end
                    ):
                        raise DataGateError(
                            "Fact period cannot end after public acceptance or before its start"
                        )
                    rows.append(
                        {
                            "cik": issuer,
                            "tag": tag,
                            "unit": unit,
                            "start": start,
                            "end": end,
                            "value": float(value),
                            "accession": accession,
                            "accepted_at": acceptance[accession],
                        }
                    )
    return pd.DataFrame(
        rows, columns=["cik", "tag", "unit", "start", "end", "value", "accession", "accepted_at"]
    )


def facts_as_of(
    facts: pd.DataFrame, as_of, *, amendment_policy: str = "latest_known"
) -> pd.DataFrame:
    if amendment_policy not in {"latest_known", "first_reported"}:
        raise DataGateError("Unknown fact vintage policy")
    cutoff = timestamp(as_of)
    eligible = facts[pd.to_datetime(facts.accepted_at, utc=True) <= cutoff].copy()
    keys = ["cik", "tag", "unit", "start", "end"]
    # Conflicting facts in one accession cannot be chosen by arbitrary JSON order.
    duplicates = eligible.groupby([*keys, "accession"], dropna=False).value.nunique()
    if (duplicates > 1).any():
        raise DataGateError("Ambiguous fact context within an accession")
    return eligible.sort_values(["accepted_at", "accession"]).drop_duplicates(
        keys, keep="last" if amendment_policy == "latest_known" else "first"
    )


def import_swing_sidecar(manifest_path: Path, output: Path) -> Path:
    metadata = json.loads(manifest_path.read_text())
    filename = metadata["data_file"]
    source = (manifest_path.parent / filename).resolve()
    if (
        not source.is_relative_to(manifest_path.parent.resolve())
        or sha(source) != metadata["data_file_sha256"]
    ):
        raise DataGateError("Swing SEC sidecar failed file integrity")
    if (
        metadata.get("record_type") != "candidate_bound_sec_filing_event_snapshot"
        or metadata.get("event_data_gate_passed") is not True
    ):
        raise DataGateError("Swing SEC sidecar is not qualified filing metadata")
    frame = pd.read_parquet(source)
    accepted = pd.to_datetime(frame.accepted_at_utc, utc=True)
    if (accepted > timestamp(metadata["captured_at_utc"])).any():
        raise DataGateError("Sidecar includes future filings")
    output.mkdir(parents=True, exist_ok=False)
    frame.to_parquet(output / "events.parquet", index=False)
    payload = {
        "schema_version": 1,
        "source_manifest_sha256": sha(manifest_path),
        "events_sha256": sha(output / "events.parquet"),
        "role": "filing_metadata_only_not_directional_alpha",
        "historical_strategy_authorized": False,
        "action_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return output / "manifest.json"
