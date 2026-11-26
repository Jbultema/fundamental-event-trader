"""Small, explicitly biased event-return pilots, isolated from strategy admission.

This is not the broad historical research runner. It cannot emit portfolio targets,
CAGR, an admission decision, or an exact SEC acceptance timestamp.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from fundamental_event_trader.sec import DataGateError, sha

KIND = "exploratory_vendor_sample_not_broad_strategy_validation"
FAMILIES = ("cash_conversion_improvement", "executed_net_common_repurchase")
LIMITATIONS = [
    "current_survivor_sample_not_historical_membership",
    "small_hand_selected_roster_not_general_equity_evidence",
    "vendor_as_reported_dates_not_independent_original_filing_verification",
    "date_only_delayed_availability_not_exact_acceptance_or_vendor_ingestion",
    "no_failed_security_terminal_settlement_validation",
    "matched_returns_not_an_executable_portfolio_or_CAGR",
    "overlapping_events_and_controls_not_independent_trials",
    "same_year_controls_can_overlap_subsequent_disclosures",
    "no_untouched_holdout_or_multiple_testing_adjusted_significance",
    "net_common_financing_is_not_gross_repurchase_execution_or_authorization",
]


def delayed_date_cutoff(value: str) -> pd.Timestamp:
    """After filing-date end plus a full calendar day of assumed processing."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise DataGateError("An explicit publication date, not an invented acceptance time, is required")
    day = pd.Timestamp(value)
    if pd.isna(day) or str(day.date()) != value:
        raise DataGateError("Invalid publication date")
    return (day + pd.Timedelta(days=2)).tz_localize("America/New_York").tz_convert("UTC")


def bound_file(root: Path, relative: str, expected: str) -> Path:
    if not isinstance(relative, str) or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise DataGateError("Source paths and SHA256 bindings required")
    file = (root / relative).resolve()
    if not file.is_relative_to(root.resolve()) or not file.is_file() or sha(file) != expected:
        raise DataGateError("Pilot source integrity failed")
    return file


def load_sample(root: Path):
    acquisition = json.loads((root / "acquisition.json").read_text())
    if acquisition.get("kind") != KIND or acquisition.get("purchase_made") is not False or acquisition.get("account_credentials_used") is not False:
        raise DataGateError("Expected a public free-sample acquisition, not a subscription or account feed")
    protocol_file = bound_file(root, "protocol.json", acquisition.get("protocol_sha256"))
    protocol = json.loads(protocol_file.read_text())
    roster = protocol.get("roster")
    if (protocol.get("kind") != KIND or not isinstance(roster, list) or not roster
            or len(roster) != len(set(roster)) or any(not re.fullmatch(r"[A-Z]{1,5}", str(t)) for t in roster)
            or set(protocol.get("features", {})) != set(FAMILIES)
            or protocol.get("horizons") != [21, 63, 126]
            or protocol.get("execution_lags") != [1, 2, 5]
            or protocol.get("cost_bps_per_side") != [10, 25, 50]
            or protocol.get("portfolio_allocation_allowed") is not False
            or protocol.get("no_threshold_selection") is not True
            or not protocol.get("biases")):
        raise DataGateError("Frozen pilot specification missing or unsupported")
    start, end = pd.Timestamp(protocol["from"]), pd.Timestamp(protocol["to"])
    if start >= end or end.date() >= datetime.now(UTC).date():
        raise DataGateError("Pilot requires a completed historical date interval")
    cal = xcals.get_calendar("XNYS", start=start - pd.Timedelta(days=7), end=end + pd.Timedelta(days=7))
    sessions = cal.sessions_in_range(start, end)
    opens = pd.DatetimeIndex([cal.session_open(day) for day in sessions])
    if len(opens) < 200:
        raise DataGateError("Pilot price history too short for its fixed horizons")
    expected = {(table, ticker) for table in ("stocks", "fundamentals") for ticker in roster}
    checks = acquisition.get("checks", [])
    if len(checks) != len(expected) or {(r["table"], r["ticker"]) for r in checks} != expected:
        raise DataGateError("Every frozen roster member must be retained, including failed acquisitions")
    fundamentals, price_series, evidence = [], [], []
    for item in checks:
        ticker, table = item["ticker"], item["table"]
        query = item.get("query", {})
        if (item.get("status") != "acquired_not_qualified" or query.get("api_key") != "test-api-key"
                or query.get("ticker") != ticker or query.get("from") != protocol["from"]
                or query.get("to") != protocol["to"] or query.get("limit") != 1500):
            raise DataGateError("Acquisition failed or differs from the frozen free sample")
        file = bound_file(root, item["path"], item["sha256"])
        if file.stat().st_size != item["bytes"]:
            raise DataGateError("Source byte length mismatch")
        frame = pd.read_csv(file)
        if frame.empty or len(frame) >= query["limit"] or "ticker" not in frame or not frame.ticker.eq(ticker).all():
            raise DataGateError("Empty, truncated, or wrong-security sample")
        if "date" not in frame:
            raise DataGateError("Source observation dates missing")
        dates = frame.date.map(lambda v: pd.Timestamp(v) if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else pd.NaT)
        if dates.isna().any() or not dates.between(start, end).all():
            raise DataGateError("Source observation outside the frozen date interval")
        if table == "stocks":
            required = ["open", "close", "closeadj", "volume"]
            if not set(required) <= set(frame):
                raise DataGateError("OHLC adjustment inputs missing")
            numeric = frame[required].apply(pd.to_numeric, errors="coerce")
            if not np.isfinite(numeric).all().all() or numeric[["open", "close", "closeadj"]].le(0).any().any() or numeric.volume.le(0).any():
                raise DataGateError("Invalid or untradeable observed prices")
            if dates.duplicated().any() or set(dates.dt.date) != set(opens.date):
                raise DataGateError("All actual sessions required; no missing-price imputation")
            frame = frame.assign(_date=dates, _adjusted_open=numeric.open * numeric.closeadj / numeric.close).sort_values("_date")
            price_series.append(pd.Series(frame._adjusted_open.to_numpy(), index=opens, name=ticker))
        else:
            required = {"dimension", "reportperiod", "assets", "ncfo", "netinc", "ncfcommon"}
            if not required <= set(frame) or not frame.dimension.eq("ART").all() or query.get("dimension") != "ART":
                raise DataGateError("Only as-reported trailing-year accounting inputs allowed")
            numeric = frame[["assets", "ncfo", "netinc", "ncfcommon"]].apply(pd.to_numeric, errors="coerce")
            periods = pd.to_datetime(frame.reportperiod, errors="coerce")
            if not np.isfinite(numeric).all().all() or numeric.assets.le(0).any() or periods.isna().any() or periods.gt(dates).any() or frame.duplicated(["date", "reportperiod"]).any():
                raise DataGateError("Invalid, duplicate, or future-period financial observation")
            frame[numeric.columns] = numeric
            frame["source_sha256"] = item["sha256"]
            fundamentals.append(frame)
        evidence.append({"path": item["path"], "sha256": item["sha256"], "rows": len(frame)})
    return protocol, pd.concat(fundamentals, ignore_index=True), pd.concat(price_series, axis=1)[roster], evidence


def qualify_pilot(root: Path) -> dict:
    errors = []
    try:
        protocol, facts, prices, _ = load_sample(root)
        scope = {"securities": len(protocol["roster"]), "financial_observations": len(facts), "price_sessions": len(prices)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(f"{type(exc).__name__}: {str(exc)[:200]}")
        scope = {}
    return {
        "research_stage": "exploratory_sample_only",
        "status": "pilot_allowed_not_validated" if not errors else "blocked",
        "exploratory_event_study_allowed": not errors,
        "historical_event_study_allowed": False,
        "strategy_promotion_allowed": False, "portfolio_allocation_allowed": False,
        "action": "NO ACTION", "limitations": LIMITATIONS, "errors": errors, **scope,
    }


def features(facts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, group in facts.groupby("ticker", sort=True):
        # Repeated period versions are retained in the audit but cannot masquerade
        # as a fresh first report. Only earlier public dates may supply comparisons.
        group = group.sort_values(["date", "reportperiod"]).copy()
        seen = set()
        for row in group.itertuples():
            period, release = pd.Timestamp(row.reportperiod), pd.Timestamp(row.date)
            repeated = row.reportperiod in seen
            seen.add(row.reportperiod)
            prior = group[
                (group.date < row.date)
                & (pd.to_datetime(group.reportperiod).between(period - pd.Timedelta(days=430), period - pd.Timedelta(days=300)))
            ].sort_values(["reportperiod", "date"])
            score = None
            prior_date = None
            if not repeated and len(prior):
                previous = prior.iloc[-1]
                score = float((row.ncfo - row.netinc) / row.assets - (previous.ncfo - previous.netinc) / previous.assets)
                prior_date = previous.date
            base = {
                "ticker": ticker, "filing_date": str(release.date()),
                "reportperiod": row.reportperiod, "source_sha256": row.source_sha256,
                "date_only_available_after": delayed_date_cutoff(row.date),
                "availability_is_assumed_delayed_date_not_acceptance": True,
            }
            rows.append(base | {"family": FAMILIES[0], "score": score, "prior_publication_date": prior_date,
                "selected": score is not None and score > 0,
                "feature_status": "repeated_period_excluded" if repeated else ("observed" if score is not None else "left_censored_prior_year_missing")})
            rows.append(base | {"family": FAMILIES[1], "score": float(-row.ncfcommon / row.assets),
                "prior_publication_date": None,
                "selected": not repeated and row.ncfcommon < 0 and row.netinc > 0,
                "feature_status": "repeated_period_excluded" if repeated else "observed"})
    return pd.DataFrame(rows)


def evaluate(event_features, prices, protocol):
    results = []
    for family, lag, horizon in product(FAMILIES, protocol["execution_lags"], protocol["horizons"]):
        selected = event_features[event_features.family.eq(family) & event_features.selected].sort_values(["date_only_available_after", "ticker", "reportperiod"])
        excluded = {}
        for ticker in prices:
            # Any report's delayed entry is not an eligible non-event entry, even
            # when that report failed the positive signal threshold.
            dates = event_features.loc[event_features.ticker.eq(ticker), "date_only_available_after"]
            excluded[ticker] = {int(prices.index.searchsorted(v, side="left")) + lag - 1 for v in dates}
        used = {ticker: set() for ticker in prices}
        for event in selected.itertuples():
            start = int(prices.index.searchsorted(event.date_only_available_after, side="left")) + lag - 1
            record = {"family": family, "ticker": event.ticker, "filing_date": event.filing_date,
                      "reportperiod": event.reportperiod, "lag_sessions": lag, "horizon_sessions": horizon,
                      "available_after": event.date_only_available_after.isoformat(), "source_sha256": event.source_sha256}
            if start + horizon >= len(prices):
                results.append(record | {"status": "right_censored_no_complete_horizon"})
                continue
            if start < 64:
                results.append(record | {"status": "left_censored_momentum_window"})
                continue
            values = prices[event.ticker].to_numpy()
            momentum = values[start - 1] / values[start - 64] - 1
            pool = [j for j in range(64, len(prices) - horizon)
                    if prices.index[j].year == prices.index[start].year
                    and j not in excluded[event.ticker] and j not in used[event.ticker]]
            if not pool:
                results.append(record | {"status": "no_matched_non_event_entry"})
                continue
            match = min(pool, key=lambda j: (abs(values[j - 1] / values[j - 64] - 1 - momentum), j))
            used[event.ticker].add(match)
            event_gross = float(values[start + horizon] / values[start])
            control_gross = float(values[match + horizon] / values[match])
            for cost_bps in protocol["cost_bps_per_side"]:
                # Both legs incur identical entry/exit costs. This is return on
                # initial cash, not a subtraction of bps from a compounded price.
                factor = (1 - cost_bps / 10000) / (1 + cost_bps / 10000)
                results.append(record | {
                    "status": "measured", "cost_bps_per_side": cost_bps,
                    "entry_at": prices.index[start].isoformat(), "exit_at": prices.index[start + horizon].isoformat(),
                    "control_entry_at": prices.index[match].isoformat(), "control_exit_at": prices.index[match + horizon].isoformat(),
                    "event_net_return": event_gross * factor - 1,
                    "control_net_return": control_gross * factor - 1,
                    "matched_excess_return": (event_gross - control_gross) * factor,
                    "entry_momentum_gap": float(abs(values[match - 1] / values[match - 64] - 1 - momentum)),
                })
    return pd.DataFrame(results)


def run(root: Path, output: Path) -> dict:
    initial = {name: sha(root / name) for name in ("protocol.json", "acquisition.json")}
    protocol, facts, prices, evidence = load_sample(root)
    initial |= {r["path"]: r["sha256"] for r in evidence}
    event_features = features(facts)
    outcomes = evaluate(event_features, prices, protocol)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output / "auditor.py")
    shutil.copyfile(root / "protocol.json", output / "protocol.json")
    event_features.to_parquet(output / "pilot_features.parquet", index=False)
    outcomes.to_csv(output / "event_returns.csv", index=False)
    measured = outcomes[outcomes.status.eq("measured")]
    keys = ["family", "lag_sessions", "horizon_sessions", "cost_bps_per_side"]
    summary_rows = []
    if len(measured):
        for key, group in measured.groupby(keys, sort=True):
            summary_rows.append(dict(zip(keys, key, strict=True)) | {
                "event_count": len(group), "issuers": group.ticker.nunique(),
                "mean_event_net_return": float(group.event_net_return.mean()),
                "median_event_net_return": float(group.event_net_return.median()),
                "mean_matched_excess_return": float(group.matched_excess_return.mean()),
                "median_matched_excess_return": float(group.matched_excess_return.median()),
                "positive_excess_fraction": float(group.matched_excess_return.gt(0).mean()),
                "median_entry_momentum_gap": float(group.entry_momentum_gap.median()),
            })
        measured.groupby(keys + ["ticker"]).agg(events=("matched_excess_return", "size"), mean_excess=("matched_excess_return", "mean")).to_csv(output / "issuer_breakdown.csv")
    pd.DataFrame(summary_rows).to_csv(output / "scenarios.csv", index=False)
    if any(sha(root / name) != digest for name, digest in initial.items()):
        raise DataGateError("Source evidence changed during pilot evaluation")
    summary = {
        "kind": KIND, "created_at_utc": datetime.now(UTC).isoformat(),
        "scope": qualify_pilot(root), "frozen_roster": protocol["roster"],
        "securities": len(prices.columns), "price_sessions": len(prices),
        "price_start": prices.index[0].isoformat(), "price_end": prices.index[-1].isoformat(),
        "financial_observations": len(facts),
        "feature_status_counts": event_features.feature_status.value_counts().to_dict(),
        "selected_events_by_family": event_features[event_features.selected].family.value_counts().to_dict(),
        "event_return_scenarios_measured": len(summary_rows),
        "qualified_portfolio_strategies_tested": 0, "portfolio_allocation_allowed": False,
        "outcome_status_counts": outcomes.status.value_counts().to_dict(),
        "counting_note": "costs_lags_horizons_are_correlated_scenarios_not_new_independent_hypotheses; censored_rows_recorded_once_per_event_lag_horizon",
        "limitations": LIMITATIONS, "conclusion": "descriptive_pilot_only_no_strategy_selection_or_admission",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    manifest = {"kind": KIND, "source_root": str(root.resolve()), "source_hashes": initial,
                "source_evidence": evidence, "action_authorized": False,
                "artifacts": {p.name: sha(p) for p in output.iterdir() if p.is_file()}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.sources, args.output), indent=2))


if __name__ == "__main__":
    main()
