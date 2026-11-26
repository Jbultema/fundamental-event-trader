"""Append-only, pre-execution observations. Backfills never become forward evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from fundamental_event_trader.sec import DataGateError, sha, timestamp

PROTOCOL = {
    "version": 1,
    "minimum_consecutive_sessions_for_review": 60,
    "decision": "completed close plus 15 minutes, recorded before next regular open",
    "execution": "next regular open; 10bps per side; no orders",
    "gaps": "missing sessions break the consecutive observation count",
    "promotion": "never automatic; observation minimum is not profitability evidence",
}


def _identity(payload):
    fields = ("code_sha256", "research_manifest_sha256", "policy")
    value = {key: payload[key] for key in fields}
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _window(session):
    day = pd.Timestamp(session)
    if str(day.date()) != session:
        raise DataGateError("Shadow session must be an ISO exchange date")
    cal = xcals.get_calendar(
        "XNYS", start=str((day - pd.Timedelta(days=10)).date()),
        end=str((day + pd.Timedelta(days=10)).date()),
    )
    if not cal.is_session(day):
        raise DataGateError("Shadow observation is not an exchange session")
    return cal.session_close(day) + pd.Timedelta(minutes=15), cal.session_open(cal.next_session(day))


def _weights(value):
    if not isinstance(value, dict) or any(not isinstance(k, str) or not k for k in value):
        raise DataGateError("Invalid shadow target identities")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) for v in value.values()):
        raise DataGateError("Invalid shadow target weights")
    values = np.array(list(value.values()), dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or values.sum() > 1 + 1e-10:
        raise DataGateError("Shadow targets must be finite, unlevered and long only")
    return value


def _load(folder: Path, identity: str):
    if not folder.exists():
        return []
    meta = json.loads((folder / "protocol.json").read_text())
    if meta != {"cohort": identity, "protocol": PROTOCOL}:
        raise DataGateError("Prospective shadow protocol changed")
    previous, records = None, []
    for path in sorted(folder.glob("????-??-??.json")):
        row = json.loads(path.read_text())
        if (
            row.get("schema_version") != 1
            or row.get("cohort") != identity
            or _identity(row) != identity
            or row.get("previous_sha256") != previous
            or row.get("action_authorized") is not False
            or row.get("session") != path.stem
        ):
            raise DataGateError("Prospective shadow chain or identity changed")
        for key in ("code_sha256", "research_manifest_sha256", "dataset_manifest_sha256"):
            value = row.get(key)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise DataGateError("Shadow source identities require SHA256")
        earliest, deadline = _window(row["session"])
        captured = timestamp(row["recorded_at_utc"])
        if not earliest <= captured < deadline or row.get("execution_at_utc") != deadline.isoformat():
            raise DataGateError("Late or future-dated shadow observation")
        if records and timestamp(records[-1]["recorded_at_utc"]) >= captured:
            raise DataGateError("Shadow observations must be chronological")
        _weights(row.get("target_holdings"))
        previous = sha(path)
        records.append(row)
    head = json.loads((folder / "head.json").read_text())
    if head != {"latest_session": records[-1]["session"] if records else None, "sha256": previous}:
        raise DataGateError("Prospective shadow head changed or append was interrupted")
    return records


def summary(root: Path, payload: dict, *, now) -> dict:
    result = {
        "status": "not_started", "recorded_sessions": 0, "consecutive_sessions": 0,
        "missing_sessions": [], "minimum_sessions_for_review": 60,
        "action_authorized": False, "automatic_promotion_allowed": False,
        "profitability_established": False,
    }
    if not payload.get("policy") or not payload.get("research_manifest_sha256"):
        result["reason"] = "qualified_frozen_research_required"
        return result
    identity = _identity(payload)
    folder = root / "data/prospective" / identity
    rows = _load(folder, identity)
    result["cohort"] = identity
    if not rows:
        result["reason"] = "no_pre_execution_observations"
        return result
    clock = timestamp(now)
    if any(timestamp(row["recorded_at_utc"]) > clock for row in rows):
        raise DataGateError("Prospective ledger contains future observations")
    first, last = rows[0]["session"], rows[-1]["session"]
    cal = xcals.get_calendar("XNYS", start=first, end=str((clock + pd.Timedelta(days=10)).date()))
    completed = [
        day for day in cal.sessions_in_range(first, clock.date())
        if cal.session_close(day) + pd.Timedelta(minutes=15) <= clock
    ]
    observed = {row["session"] for row in rows}
    # A still-open recording window is not a missed forecast yet.
    required = [day for day in completed if cal.session_open(cal.next_session(day)) <= clock]
    missing = [str(day.date()) for day in required if str(day.date()) not in observed]
    consecutive = 0
    for day in reversed(completed):
        session = str(day.date())
        if session not in observed:
            if cal.session_open(cal.next_session(day)) > clock:
                continue
            break
        consecutive += 1
    minimum = PROTOCOL["minimum_consecutive_sessions_for_review"]
    result |= {
        "status": "minimum_recorded_review_required" if consecutive >= minimum else "collecting",
        "recorded_sessions": len(rows), "consecutive_sessions": consecutive,
        "missing_sessions": missing, "first_session": first, "latest_session": last,
        "latest_record_sha256": sha(folder / f"{last}.json"),
        "protocol_sha256": sha(folder / "protocol.json"),
        "minimum_sessions_for_review": minimum,
        "reason": "observation_count_only_not_alpha_or_allocation_approval",
    }
    return result


def record(root: Path, payload: dict, *, now) -> dict:
    if payload.get("status") != "research_shadow" or payload.get("fresh") is not True:
        return {"status": "not_recorded", "reason": "fresh_qualified_research_required"}
    clock = timestamp(now)
    captured = timestamp(payload["captured_at_utc"])
    if captured > clock:
        raise DataGateError("Cannot record a future-dated status")
    earliest, deadline = _window(payload["as_of_session"])
    if not earliest <= captured <= clock < deadline:
        return {"status": "not_recorded", "reason": "outside_pre_execution_window"}
    identity = _identity(payload)
    folder = root / "data/prospective" / identity
    rows = _load(folder, identity)
    row = {
        "schema_version": 1, "cohort": identity, "session": payload["as_of_session"],
        "recorded_at_utc": clock.isoformat(), "execution_at_utc": deadline.isoformat(),
        "code_sha256": payload["code_sha256"], "policy": payload["policy"],
        "research_manifest_sha256": payload["research_manifest_sha256"],
        "dataset_manifest_sha256": payload["dataset_manifest_sha256"],
        "target_holdings": _weights(payload["target_holdings"]),
        "action_authorized": False,
        "previous_sha256": sha(folder / f"{rows[-1]['session']}.json") if rows else None,
    }
    for key in ("code_sha256", "research_manifest_sha256", "dataset_manifest_sha256"):
        value = row[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise DataGateError("Shadow source identities require SHA256")
    file = folder / f"{row['session']}.json"
    if file.is_file():
        previous = json.loads(file.read_text())
        volatile = {"recorded_at_utc", "previous_sha256"}
        if {k: v for k, v in row.items() if k not in volatile} != {k: v for k, v in previous.items() if k not in volatile}:
            raise DataGateError("Same-session prospective observation changed; cannot overwrite")
        return {"status": "already_recorded", "path": str(file), "sha256": sha(file)}
    if rows and row["session"] <= rows[-1]["session"]:
        raise DataGateError("Historical backfills cannot enter prospective shadow")
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / "protocol.json").open("x") as handle:
            handle.write(json.dumps({"cohort": identity, "protocol": PROTOCOL}, indent=2) + "\n")
    with file.open("x") as handle:
        handle.write(json.dumps(row, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary = folder / "head.tmp"
    temporary.write_text(json.dumps({"latest_session": row["session"], "sha256": sha(file)}, indent=2) + "\n")
    temporary.replace(folder / "head.json")
    _load(folder, identity)
    return {"status": "recorded", "path": str(file), "sha256": sha(file)}


def evaluate(root: Path, payload: dict, data, *, now) -> dict:
    """Mark only decisions already captured before execution, using subsequently known prices."""
    from fundamental_event_trader.portfolio import metrics, replay
    from fundamental_event_trader.strategy import session_schedule

    progress = summary(root, payload, now=now)
    result = {"status": "not_scored", "action_authorized": False, "automatic_promotion_allowed": False}
    if progress["recorded_sessions"] == 0:
        return result | {"reason": "no_pre_execution_observations"}
    identity = _identity(payload)
    rows = _load(root / "data/prospective" / identity, identity)
    schedule = session_schedule(data.opens.index)
    completed = schedule.close.add(pd.Timedelta(minutes=15)).le(timestamp(now))
    session_dates = schedule.index.tz_convert("America/New_York").strftime("%Y-%m-%d")
    keep = completed & (session_dates >= rows[0]["session"])
    index = schedule.index[keep]
    if len(index) < 2:
        return result | {"reason": "awaiting_first_completed_execution_session"}
    days = {str(day.date()): stamp for stamp, day in zip(index, index.tz_convert("America/New_York"), strict=True)}
    if any(day not in days for day in progress["missing_sessions"] if day < str(index[-1].date())):
        return result | {"reason": "missing_pre_execution_observations_no_performance_claim"}
    decisions = {row["session"]: row for row in rows}
    required = list(days)[:-1]
    if not set(required) <= decisions.keys():
        return result | {"reason": "missing_pre_execution_observations_no_performance_claim"}
    weights = pd.DataFrame(0., index=index, columns=data.opens.columns)
    for day, stamp in days.items():
        row = decisions.get(day)
        if row is None:
            continue  # Final close cannot affect an already completed execution.
        if not set(row["target_holdings"]) <= set(weights):
            raise DataGateError("Recorded shadow security missing from outcome panel")
        for security, value in row["target_holdings"].items():
            weights.loc[stamp, security] = value
    outcomes = []
    for name, target in (("recorded_policy", weights), ("buy_hold_SPY", weights * 0), ("cash", weights * 0)):
        if name == "buy_hold_SPY":
            target["SPY"] = 1.
        replayed = replay(
            data.opens.loc[index], data.closes.loc[index], target, data.cash.loc[index],
            cost_bps=10., lag=1, terminal_events=data.terminals,
        )
        figures = metrics(replayed, index[1], index[-1])
        # A few forward sessions do not justify an annualized performance headline.
        if figures["sessions"] < 252:
            figures.pop("cagr")
        figures.pop("sharpe")
        figures.pop("annual_turnover")
        outcomes.append({"name": name, **figures})
    return result | {
        "status": "recorded_decisions_marked", "start": str(index[1].date()),
        "end": str(index[-1].date()), "performance": outcomes,
        "outcome_dataset_manifest_sha256": sha(data.root / "manifest.json"),
        "cost_bps_per_side": 10., "execution_lag": 1,
        "limits": "Modeled next-open fills, not broker fills. Local-clock evidence, not a trusted timestamp service. Minimum observation count does not establish alpha.",
    }
