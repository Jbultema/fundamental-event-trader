from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from fundamental_event_trader.sec import DataGateError, facts_as_of, timestamp

TAGS = {
    "assets": ("Assets",),
    "income": ("NetIncomeLoss", "ProfitLoss"),
    "cashflow": ("NetCashProvidedByUsedInOperatingActivities",),
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "repurchase": ("PaymentsForRepurchaseOfCommonStock",),
    "issuance": ("ProceedsFromIssuanceOfCommonStock",),
}


def accounting_features(facts: pd.DataFrame, as_of, cik: str, *, period_end=None) -> dict:
    """Conservative same-duration annual comparisons, no quarterly/YTD mixing."""
    known = facts_as_of(facts, as_of)
    known = known[known.cik.eq(str(cik).zfill(10)) & known.unit.eq("USD")]
    if period_end is not None:
        known = known[pd.to_datetime(known.end).eq(pd.Timestamp(period_end))]
    values = {}
    for label, tags in TAGS.items():
        group = known[known.tag.isin(tags)].copy()
        if label != "assets":
            duration = (pd.to_datetime(group.end) - pd.to_datetime(group.start)).dt.days
            group = group[duration.between(330, 400)]
        if group.empty:
            values[label] = np.nan
            continue
        # Alias priority is deterministic and never sums synonymous concepts.
        group["alias_priority"] = group.tag.map({tag: i for i, tag in enumerate(tags)})
        group = group.sort_values(["end", "alias_priority"], ascending=[False, True])
        latest = group.iloc[0]
        values[label] = float(latest.value)
        values[f"{label}_period_end"] = str(pd.Timestamp(latest.end).date())
        values[f"{label}_period_start"] = (
            str(pd.Timestamp(latest.start).date()) if pd.notna(latest.start) else None
        )
        older = group[
            (pd.to_datetime(group.end) - pd.Timestamp(latest.end)).dt.days.between(-400, -300)
            & group.tag.eq(latest.tag)
        ]
        values[f"{label}_growth"] = (
            float(latest.value / abs(older.iloc[0].value) - np.sign(older.iloc[0].value))
            if len(older) and older.iloc[0].value != 0
            else np.nan
        )

    def ratio(numerator):
        end = values.get(f"{numerator}_period_end")
        matching_assets = (
            known[known.tag.eq("Assets") & pd.to_datetime(known.end).eq(pd.Timestamp(end))]
            if end
            else known.iloc[:0]
        )
        if len(matching_assets) != 1 or matching_assets.value.iloc[0] <= 0:
            return np.nan
        return values.get(numerator, np.nan) / float(matching_assets.value.iloc[0])

    values["profitability"] = ratio("income")
    values["profitability_period_end"] = values.get("income_period_end")
    def same_period(left, right):
        return (values.get(f"{left}_period_start"), values.get(f"{left}_period_end")) == (
            values.get(f"{right}_period_start"), values.get(f"{right}_period_end")
        )

    values["cash_conversion"] = (
        ratio("cashflow") - ratio("income")
        if same_period("cashflow", "income")
        else np.nan
    )
    values["net_repurchase"] = (
        ratio("repurchase") - ratio("issuance")
        if same_period("repurchase", "issuance")
        else np.nan
    )
    values["as_of"] = timestamp(as_of).isoformat()
    return values


def parse_form4(xml_content: bytes, accepted_at) -> pd.DataFrame:
    from xml.etree import ElementTree

    if (
        len(xml_content) > 5_000_000
        or b"<!DOCTYPE" in xml_content.upper()
        or b"<!ENTITY" in xml_content.upper()
    ):
        raise DataGateError("Oversized or entity-bearing XML prohibited")
    root = ElementTree.fromstring(xml_content)
    if root.tag != "ownershipDocument":
        raise DataGateError("Not a Form 4 ownership document")
    cik = root.findtext("issuer/issuerCik", "").zfill(10)
    if not cik.isdigit() or not 0 < int(cik) < 10**10:
        raise DataGateError("Missing issuer CIK")
    owners = root.findall("reportingOwner/reportingOwnerId/rptOwnerCik")
    if len(owners) != 1 or not (owners[0].text or "").isdigit() or not 0 < int(owners[0].text) < 10**10:
        raise DataGateError("Unique identified reporting owner required; joint reports are ambiguous")
    owner = owners[0].text.zfill(10)
    accepted = timestamp(accepted_at)
    rows = []
    for node in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = node.findtext("transactionCoding/transactionCode", "")
        if code not in {"P", "S"}:
            continue
        shares = float(node.findtext("transactionAmounts/transactionShares/value", "nan"))
        price = float(node.findtext("transactionAmounts/transactionPricePerShare/value", "nan"))
        if not np.isfinite([shares, price]).all() or min(shares, price) < 0:
            raise DataGateError("Invalid insider transaction amount")
        date = node.findtext("transactionDate/value", "")
        try:
            date_stamp = pd.Timestamp(date)
        except ValueError as exc:
            raise DataGateError("Invalid insider transaction date") from exc
        if (pd.isna(date_stamp) or date_stamp.tzinfo is not None
                or date != str(date_stamp.date())
                or date_stamp.date() > accepted.tz_convert("America/New_York").date()):
            raise DataGateError("Transaction date cannot follow public acceptance")
        acquisition = node.findtext("transactionAmounts/transactionAcquiredDisposedCode/value")
        if acquisition is not None and acquisition != ("A" if code == "P" else "D"):
            raise DataGateError("Transaction direction conflicts with the reported code")
        rows.append(
            {
                "cik": cik,
                "accepted_at": accepted,
                "transaction_date": date,
                "code": code,
                "dollars": shares * price,
                "direction": 1 if code == "P" else -1,
                "owner_cik": owner,
                "derivative_transaction": False,
                "purchase_scope": "open_market_or_private",
            }
        )
    return pd.DataFrame(rows, columns=[
        "cik", "accepted_at", "transaction_date", "code", "dollars", "direction",
        "owner_cik", "derivative_transaction", "purchase_scope",
    ])


def insider_cluster(transactions: pd.DataFrame, as_of, *, days: int = 30) -> pd.DataFrame:
    cutoff = timestamp(as_of)
    required = {"cik", "accepted_at", "code", "owner_cik", "dollars", "derivative_transaction"}
    if not required <= set(transactions) or isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise DataGateError("Source-identified, non-derivative insider transactions required")
    accepted = transactions.accepted_at.map(timestamp)
    if transactions.derivative_transaction.dtype != bool:
        raise DataGateError("Explicit derivative flags required")
    known = transactions[
        (accepted <= cutoff)
        & (accepted > cutoff - pd.Timedelta(days=days))
        & transactions.code.eq("P")
        & transactions.dollars.gt(0)
        & ~transactions.derivative_transaction
    ].copy()
    if known.empty:
        return pd.DataFrame(columns=["distinct_buyers", "purchase_dollars"]).rename_axis("cik")
    for column in ("cik", "owner_cik"):
        value = known[column].astype(str)
        if not value.str.fullmatch(r"[0-9]{1,10}").all() or value.eq("0").any() or value.str.fullmatch("0+").any():
            raise DataGateError("Identified issuers and distinct reporting owners required")
        known[column] = value.str.zfill(10)
    if not np.isfinite(known.dollars).all():
        raise DataGateError("Finite insider purchase dollars required")
    return known.groupby("cik").agg(
        distinct_buyers=("owner_cik", "nunique"), purchase_dollars=("dollars", "sum")
    )


@dataclass(frozen=True)
class Hypothesis:
    name: str
    family: str
    threshold: float
    horizon: int


def registry() -> list[dict]:
    output = []
    for family in (
        "profitability_change",
        "cash_conversion",
        "net_repurchase",
        "insider_cluster",
        "post_filing_drift",
        "ownership_change",
        "eight_k_event",
    ):
        thresholds = (
            (0.0, 0.02, 0.05)
            if family not in {"insider_cluster", "post_filing_drift"}
            else ((2, 3, 4) if family == "insider_cluster" else (0.0, 0.01, 0.03))
        )
        for threshold in thresholds:
            for horizon in (21, 63):
                output.append(
                    asdict(
                        Hypothesis(f"{family}_t{threshold}_h{horizon}", family, threshold, horizon)
                    )
                )
    for family in (
        "profitability_plus_cash",
        "repurchase_plus_profitability",
        "insider_plus_filing",
    ):
        for horizon in (21, 63):
            output.append(asdict(Hypothesis(f"{family}_h{horizon}", family, 0.0, horizon)))
    return output


def event_study(
    events: pd.DataFrame,
    adjusted_open: pd.DataFrame,
    *,
    horizon: int = 21,
    roundtrip_bps: float = 50,
) -> pd.DataFrame:
    """Matched event paths, not an overlapping-event portfolio CAGR."""
    required = {"security_id", "accepted_at", "directional_signal"}
    if (
        not required <= set(events)
        or "SPY" not in adjusted_open
        or not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1
        or not np.isfinite(roundtrip_bps) or roundtrip_bps < 0
    ):
        raise DataGateError("Incomplete event-study inputs")
    if (
        not isinstance(adjusted_open.index, pd.DatetimeIndex)
        or adjusted_open.index.tz is None
        or adjusted_open.index.hasnans
        or not adjusted_open.columns.is_unique
        or adjusted_open.index.has_duplicates
        or not adjusted_open.index.is_monotonic_increasing
    ):
        raise DataGateError("Actual timezone-aware regular-session opens required")
    rows = []
    for event in events.itertuples():
        accepted = timestamp(event.accepted_at)
        entry = adjusted_open.index.searchsorted(accepted, side="right")
        exit_position = entry + horizon
        if event.security_id not in adjusted_open:
            raise DataGateError("Missing event security price history; no survivor substitution")
        if exit_position >= len(adjusted_open):
            continue
        values = adjusted_open.iloc[[entry, exit_position]][[event.security_id, "SPY"]]
        if not np.isfinite(values.to_numpy()).all() or values.le(0).any().any():
            raise DataGateError("Missing event/benchmark endpoint or delisting treatment")
        path = adjusted_open.iloc[entry : exit_position + 1][[event.security_id, "SPY"]]
        if not np.isfinite(path.to_numpy(dtype=float)).all() or path.le(0).any().any():
            raise DataGateError("Event path has unmodeled terminal or missing prices")
        raw = float(values.iloc[1, 0] / values.iloc[0, 0] - 1)
        benchmark = float(values.iloc[1, 1] / values.iloc[0, 1] - 1)
        rows.append(
            {
                "security_id": event.security_id,
                "accepted_at": accepted,
                "entry_at": adjusted_open.index[entry],
                "exit_at": adjusted_open.index[exit_position],
                "horizon": horizon,
                "event_return_net": raw - roundtrip_bps / 10000,
                "benchmark_return_net": benchmark - roundtrip_bps / 10000,
                "excess_return": raw - benchmark,
                "directional_signal": event.directional_signal,
            }
        )
    return pd.DataFrame(rows)
