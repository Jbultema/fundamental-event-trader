from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fundamental_event_trader.features import registry
from fundamental_event_trader.sec import DataGateError, sha, timestamp

CRITERIA = (
    "official_public_free_sources",
    "historical_membership_including_delisted",
    "security_identity_intervals_verified",
    "terminal_prices_or_delisting_returns",
    "acceptance_timestamp_complete",
    "original_filing_vintages_preserved",
    "independent_price_quality_review",
)


def qualify(dataset: Path | None = None) -> dict:
    errors = []
    metadata = {}
    if dataset is None or not (dataset / "manifest.json").is_file():
        errors.append("no_qualified_historical_dataset")
    else:
        try:
            metadata = json.loads((dataset / "manifest.json").read_text())
            for criterion in CRITERIA:
                evidence = metadata.get("criteria", {}).get(criterion, {})
                if evidence.get("passed") is not True or not evidence.get("evidence_artifact"):
                    errors.append(f"missing_evidence:{criterion}")
            for filename, expected in metadata.get("artifacts", {}).items():
                file = (dataset / filename).resolve()
                if (
                    not file.is_relative_to(dataset.resolve())
                    or not file.is_file()
                    or sha(file) != expected
                ):
                    errors.append(f"integrity:{filename}")
            required = {"events.parquet", "identity.parquet", "prices.parquet"}
            if not required <= metadata.get("artifacts", {}).keys():
                errors.append("missing_required_tables")
            evidence_names = {
                e.get("evidence_artifact") for e in metadata.get("criteria", {}).values()
            }
            if not evidence_names <= metadata.get("artifacts", {}).keys():
                errors.append("unbound_qualification_evidence")
            if not errors:
                validate_dataset(dataset)
        except (OSError, KeyError, ValueError, TypeError) as exc:
            errors.append(f"dataset_validation:{type(exc).__name__}:{str(exc)[:200]}")
    return {
        "schema_version": 1,
        "status": "qualified_for_retrospective_event_study" if not errors else "blocked",
        "historical_event_study_allowed": not errors,
        "strategy_promotion_allowed": False,
        "portfolio_allocation_allowed": False,
        "errors": errors,
        "registered_hypotheses": len(registry()),
        "unimplemented_content_gates": [
            "ownership_change_requires_content_verified_stake_change",
            "eight_k_event_requires_content_not_filing_count",
        ],
        "action": "NO ACTION",
    }


def validate_dataset(dataset: Path):
    events = pd.read_parquet(dataset / "events.parquet")
    identity = pd.read_parquet(dataset / "identity.parquet")
    prices = pd.read_parquet(dataset / "prices.parquet")
    if events.empty or identity.empty or prices.empty:
        raise DataGateError("Nonempty events, identities and prices required")
    if (
        not isinstance(prices.index, pd.DatetimeIndex)
        or prices.index.tz is None
        or prices.index.hasnans
        or prices.index.has_duplicates
        or not prices.index.is_monotonic_increasing
        or not prices.columns.is_unique
        or "SPY" not in prices
    ):
        raise DataGateError("Require unique timestamped adjusted-open prices")
    values = prices.to_numpy(dtype=float)
    if (
        np.isinf(values).any() or (values <= 0).any()
        or prices["SPY"].isna().any()
    ):
        raise DataGateError("Observed prices must be finite and positive with complete SPY coverage")
    required = {"security_id", "cik", "valid_from", "valid_until", "known_at"}
    if not required <= set(identity) or not {
        "security_id",
        "cik",
        "accepted_at",
        "directional_signal",
    } <= set(events):
        raise DataGateError("Historical identity/event columns missing")
    if (
        events[["security_id", "cik", "accepted_at", "directional_signal"]].isna().any().any()
        or identity[list(required)].isna().any().any()
        or not np.isfinite(pd.to_numeric(events.directional_signal, errors="coerce")).all()
    ):
        raise DataGateError("Missing or nonfinite event/identity values")
    valid_from = pd.to_datetime(identity.valid_from, utc=True)
    valid_until = pd.to_datetime(identity.valid_until, utc=True)
    known_at = pd.to_datetime(identity.known_at, utc=True)
    if (
        valid_from.isna().any() or valid_until.isna().any() or known_at.isna().any()
        or (valid_until <= valid_from).any()
    ):
        raise DataGateError("Invalid historical identity intervals")
    if (
        not {"delisted", "terminal_treatment_verified"} <= set(identity)
        or not pd.api.types.is_bool_dtype(identity.delisted)
        or not pd.api.types.is_bool_dtype(identity.terminal_treatment_verified)
        or identity[["delisted", "terminal_treatment_verified"]].isna().any().any()
        or not identity.terminal_treatment_verified.all()
    ):
        raise DataGateError("Terminal-treatment census incomplete")
    if not identity.delisted.any():
        raise DataGateError("Historical stock universe contains no delisted securities")
    if not set(events.security_id) <= set(prices):
        raise DataGateError("Events contain securities missing from the historical price panel")
    for row in identity[identity.delisted].itertuples():
        terminal = timestamp(row.valid_until)
        if terminal > prices.index.max() or row.security_id not in prices:
            raise DataGateError("Delisted identity lacks an observed historical terminal interval")
        if prices.loc[prices.index >= terminal, row.security_id].notna().any():
            raise DataGateError("Permanent security id has prices after its terminal interval")
    if (
        prices.index.max() - prices.index.min()
    ).days < 365 * 10 or identity.security_id.nunique() < 100:
        raise DataGateError(
            "Historical coverage insufficient; need >=10 years and >=100 security identities"
        )
    for event in events.itertuples():
        accepted = timestamp(event.accepted_at)
        eligible = identity[
            (identity.security_id == event.security_id)
            & (identity.cik.astype(str).str.zfill(10) == str(event.cik).zfill(10))
        ]
        eligible = eligible[
            (pd.to_datetime(eligible.valid_from, utc=True) <= accepted)
            & (pd.to_datetime(eligible.valid_until, utc=True) > accepted)
            & (pd.to_datetime(eligible.known_at, utc=True) <= accepted)
        ]
        if len(eligible) != 1:
            raise DataGateError("Event has ambiguous, future-known, or missing historical identity")
    return events, prices
