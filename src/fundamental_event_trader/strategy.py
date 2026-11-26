"""Content-derived, fixed-specification event policies. No price-momentum substitute."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from fundamental_event_trader.features import registry
from fundamental_event_trader.sec import DataGateError

FEATURES = {
    "profitability_change": "profitability_change",
    "cash_conversion": "cash_conversion",
    "net_repurchase": "net_repurchase",
    "insider_cluster": "distinct_buyers",
    "post_filing_drift": "post_filing_return",
    "ownership_change": "stake_change",
    "eight_k_event": "verified_event_score",
}
COMBINATIONS = {
    "profitability_plus_cash": ("profitability_change", "cash_conversion"),
    "repurchase_plus_profitability": ("net_repurchase", "profitability_change"),
    "insider_plus_filing": ("distinct_buyers", "post_filing_return"),
}


@dataclass(frozen=True)
class Policy:
    name: str
    family: str
    threshold: float
    horizon: int
    slots: int = 10
    max_weight: float = 0.1

    def __post_init__(self):
        if (
            self.family not in FEATURES | COMBINATIONS
            or self.horizon not in (21, 63)
            or isinstance(self.slots, bool)
            or not isinstance(self.slots, int)
            or self.slots < 1
            or not np.isfinite(self.threshold)
            or not np.isfinite(self.max_weight)
            or not 0 < self.max_weight <= 1
        ):
            raise DataGateError("Invalid event policy")

    def specification(self):
        return asdict(self)


def policies() -> list[Policy]:
    return [Policy(**item) for item in registry()]


def session_schedule(index: pd.DatetimeIndex) -> pd.DataFrame:
    if (
        not isinstance(index, pd.DatetimeIndex)
        or index.tz is None
        or index.hasnans
        or index.has_duplicates
        or not index.is_monotonic_increasing
        or index.empty
    ):
        raise DataGateError("Unique increasing timezone-aware regular opens required")
    cal = xcals.get_calendar("XNYS", start=str(index[0].date()), end=str(index[-1].date()))
    sessions = cal.sessions_in_range(index[0].date(), index[-1].date())
    opens = pd.DatetimeIndex([cal.session_open(day) for day in sessions])
    if not opens.equals(index.tz_convert("UTC")):
        raise DataGateError("Prices must include every actual NYSE regular-session open")
    return pd.DataFrame(
        {"open": opens, "close": [cal.session_close(day) for day in sessions]}, index=opens
    )


def eligible_events(events: pd.DataFrame, policy: Policy) -> pd.DataFrame:
    """A family cannot borrow an unrelated precomputed directional_signal column."""
    required = {"security_id", "cik", "accepted_at", "available_at", "accession", "source_sha256"}
    if not required <= set(events):
        raise DataGateError("Content-bound event identity, publication and availability required")
    out = events.copy()
    for col in ("accepted_at", "available_at"):
        for value in out[col]:
            stamp = pd.Timestamp(value)
            if pd.isna(stamp) or stamp.tzinfo is None:
                raise DataGateError("Event timestamps require explicit timezones")
        out[col] = pd.to_datetime(out[col], utc=True)
    if (out.available_at < out.accepted_at).any():
        raise DataGateError("A feature cannot be available before its source filing")
    if out[list(required)].isna().any().any():
        raise DataGateError("Missing source-bound event evidence")
    if not out.source_sha256.astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
        raise DataGateError("Content evidence requires SHA256 identities")
    if out.duplicated(["security_id", "accession", "available_at"]).any():
        raise DataGateError("Duplicate source event; amendments need distinct accessions")
    components = COMBINATIONS.get(policy.family, (FEATURES.get(policy.family),))
    if any(col not in out for col in components):
        raise DataGateError(f"Unimplemented or unavailable content features: {policy.family}")
    valid = pd.Series(True, index=out.index)
    scores = []
    for col in components:
        value = pd.to_numeric(out[col], errors="coerce")
        if np.isinf(value).any():
            raise DataGateError("Infinite content-derived feature")
        cutoff = policy.threshold
        if policy.family in COMBINATIONS:
            cutoff = 2 if col == "distinct_buyers" else 0
        valid &= value.ge(cutoff) if col == "distinct_buyers" else value.gt(cutoff)
        scores.append(value)
    if policy.family in {"ownership_change", "eight_k_event"}:
        flag = (
            "ownership_content_verified"
            if policy.family == "ownership_change"
            else "eight_k_content_verified"
        )
        if flag not in out or out[flag].dtype != bool:
            raise DataGateError("Content verification flags required, not filing counts")
        valid &= out[flag]
    if "distinct_buyers" in components:
        if "purchase_dollars" not in out:
            raise DataGateError("Insider clusters require verified purchase dollars")
        dollars = pd.to_numeric(out.purchase_dollars, errors="coerce")
        buyers = pd.to_numeric(out.distinct_buyers, errors="coerce")
        if np.isinf(dollars).any() or ((buyers.dropna() % 1) != 0).any() or buyers.lt(0).any():
            raise DataGateError("Invalid distinct-owner counts or purchase dollars")
        valid &= dollars.gt(0)
    if "post_filing_return" in components:
        if "price_window_end" not in out:
            raise DataGateError("Unimplemented or unavailable post-filing price-window timestamps")
        for value in out.price_window_end.dropna():
            if pd.Timestamp(value).tzinfo is None:
                raise DataGateError("Price-window timestamps require timezones")
        end = pd.to_datetime(out.price_window_end, utc=True)
        if (end > out.available_at).any() or (end.notna() & end.le(out.accepted_at)).any():
            raise DataGateError("Post-filing prices cannot be known before their window ends")
        valid &= end.notna()
    out["score"] = pd.concat(scores, axis=1).min(axis=1)
    return out.loc[valid].sort_values(["available_at", "security_id", "accession"])


def targets(
    events: pd.DataFrame, opens: pd.DatetimeIndex, identity: pd.DataFrame, policy: Policy
) -> pd.DataFrame:
    """Close-known targets, next-open execution; fixed holding life since latest signal.

    Portfolio slots are not backfilled with the best future survivors. Unused slots stay
    in cash. Repeated filings can refresh an existing position, not create duplicate bets.
    """
    schedule = session_schedule(opens)
    qualified = eligible_events(events, policy)
    required = {"security_id", "cik", "known_at", "valid_from", "valid_until"}
    if not required <= set(identity) or identity[list(required)].isna().any().any():
        raise DataGateError("Point-in-time security identities required")
    identities = identity.copy()
    for col in ("known_at", "valid_from", "valid_until"):
        identities[col] = pd.to_datetime(identities[col], utc=True)
    universe = sorted(set(identities.security_id))
    if not set(qualified.security_id) <= set(universe):
        raise DataGateError("Events have unmapped historical securities")
    weights = pd.DataFrame(0.0, index=opens, columns=universe)
    active = {}
    cursor = 0
    rows = list(qualified.itertuples())
    for i, close in enumerate(schedule.close):
        while cursor < len(rows) and rows[cursor].available_at <= close:
            row = rows[cursor]
            cursor += 1
            matched = identities[
                identities.security_id.eq(row.security_id)
                & identities.cik.astype(str).str.zfill(10).eq(str(row.cik).zfill(10))
                & identities.known_at.le(row.available_at)
                & identities.valid_from.le(row.available_at)
                & identities.valid_until.gt(row.available_at)
            ]
            if len(matched) != 1:
                raise DataGateError("Ambiguous, future-known, or wrong-issuer event identity")
            # Old events before the price panel are not fresh entries at its left boundary.
            event_position = schedule.close.searchsorted(row.available_at, side="left")
            if row.available_at < schedule.open.iloc[0]:
                continue
            active[row.security_id] = (float(row.score), int(event_position) + policy.horizon)
        active = {security: detail for security, detail in active.items() if i < detail[1]}
        selected = sorted(active, key=lambda s: (-active[s][0], s))[: policy.slots]
        if selected:
            weights.loc[opens[i], selected] = min(1 / policy.slots, policy.max_weight)
    return weights
