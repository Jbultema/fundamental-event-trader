"""Post-pilot portfolio falsification on a fixed survivor sample. Never trading authority."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from fundamental_event_trader import event_sample_pilot, portfolio, sec, strategy
from fundamental_event_trader.event_sample_pilot import FAMILIES, features, load_sample
from fundamental_event_trader.portfolio import metrics, replay
from fundamental_event_trader.sec import DataGateError, sha
from fundamental_event_trader.strategy import session_schedule

KIND = "conditional_survivor_sample_portfolio_falsification_not_admitted_strategy"


def code_hashes():
    return {Path(module.__file__).name: sha(Path(module.__file__))
            for module in (event_sample_pilot, portfolio, sec, strategy)} | {
                Path(__file__).name: sha(Path(__file__))}


def specifications():
    candidates = [
        {"name": f"{family}_h{horizon}_{'price_confirmed' if price_gate else 'event_only'}",
         "family": family, "horizon": horizon, "price_gate": price_gate, "role": "candidate"}
        for family, horizon, price_gate in product(FAMILIES, (21, 63, 126), (False, True))
    ]
    controls = [
        {"name": "equal_weight_buy_hold", "role": "control"},
        {"name": "price_only_sma126", "role": "control"},
        {"name": "all_disclosures_h63", "role": "control"},
        {"name": "cash", "role": "control"},
        *[{"name": f"opposite_{family}_h63", "family": family, "horizon": 63,
           "opposite": True, "price_gate": False, "role": "falsification"} for family in FAMILIES],
    ]
    return candidates + controls


def freeze(root: Path, output: Path):
    source, facts, prices, evidence = load_sample(root)
    if not (prices.index[0].date() < pd.Timestamp("2023-01-03").date()
            and prices.index[-1].date() > pd.Timestamp("2025-12-31").date()):
        raise DataGateError("Frozen portfolio follow-up requires the original multi-year sample")
    output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "kind": KIND, "created_at_utc": datetime.now(UTC).isoformat(),
        "prior_event_return_results_inspected": True, "genuine_untouched_holdout": False,
        "amendment": "original narrow event-return pilot unchanged; separate conditional simulation adds no trading or broad qualification authority",
        "source_root": str(root.resolve()), "source_manifest_sha256": sha(root / "acquisition.json"),
        "source_protocol_sha256": sha(root / "protocol.json"), "evidence": evidence,
        "roster": source["roster"], "financial_observations": len(facts),
        "code_hashes": code_hashes(), "policies": specifications(),
        "development": ["2023-01-03", "2024-06-28"],
        "purge": "2024-07-01 through 2024-12-31; more than 126 trading sessions before evaluation",
        "evaluation": ["2025-01-02", str(prices.index[-1].date())],
        "windows": "calendar close-to-close returns with carried-in causal positions; not reset/selected on evaluation outcomes",
        "decision": "first regular close on/after assumed date-only processing cutoff; fill next/second/fifth regular open; one session later than prior midnight-to-open event study convention",
        "holding": "fixed 21/63/126 decision-session life from latest qualifying release; nonqualifying releases do not refresh; price confirmation can remove/reinstate within the fixed active life",
        "slot_weight": 1 / len(source["roster"]),
        "rebalancing": "target changes rebalance the basket; unchanged targets drift; no daily constant-weight or phantom monthly rebalance",
        "price_gate": "current adjusted close above trailing 126-session adjusted-close simple mean; no cross-stock ranking",
        "exposure_control": "each candidate's development average realized exposure, fit separately per cost/delay/cash scenario, held in equal-weight basket only after development cutoff; no evaluation fit",
        "cash": "primary 0% interest assumption; fixed 4% annual calendar-time accrual is a sensitivity, not observed historical money-fund returns",
        "primary_scenarios": [{"lag": lag, "cost_bps": cost, "cash_yield": 0.0}
                              for lag, cost in product((1, 2, 5), (10, 25, 50))],
        "cash_sensitivity_scenarios": [
            {"lag": 1, "cost_bps": 25, "cash_yield": .04},
            {"lag": 5, "cost_bps": 50, "cash_yield": .04}],
        "uncertainty": "2000 paired calendar-block bootstrap repetitions; blocks 21 and 63; simultaneous max-absolute-mean null across 12 current candidates only; not whole-program selection correction",
        "followup_round": "second accounting-family diagnostic after matching audit; stop threshold tuning on this sample",
        "limitations": [
            "fixed_current_survivors_not_historical_investable_universe", "ten_issuers_and_short_development_evaluation_windows",
            "vendor_AR_dates_and_vintages_not_independently_verified_original_filings",
            "no_failed_security_settlement_paths", "assumed_cash_yield_not_observed_account_yield",
            "no_costed_SPY_open_close_benchmark_or_actual_top_strategy_comparison",
            "already_inspected_historical_period_not_new_holdout", "no_signal_family_combination_after_failed_standalone_evidence"],
        "strategy_promotion_allowed": False, "portfolio_allocation_allowed": False,
    }
    file = output / "protocol.json"
    file.write_text(json.dumps(protocol, indent=2, allow_nan=False) + "\n")
    (output / "protocol.sha256").write_text(sha(file) + "\n")
    return protocol


def load_closes(root, prices):
    acquisition = json.loads((root / "acquisition.json").read_text())
    closes = pd.DataFrame(index=prices.index)
    for row in acquisition["checks"]:
        if row["table"] == "stocks":
            file = event_sample_pilot.bound_file(root, row["path"], row["sha256"])
            data = pd.read_csv(file).sort_values("date")
            closes[row["ticker"]] = data.closeadj.to_numpy(float)
    closes = closes[prices.columns]
    if not np.isfinite(closes.to_numpy()).all() or closes.le(0).any().any():
        raise DataGateError("Complete adjusted closes required for actual portfolio accounting")
    return closes


def policy_targets(event_features, closes, spec):
    """Close-known allocations only. A missing/old comparison never becomes a signal."""
    schedule = session_schedule(closes.index)
    n = len(closes.columns)
    zero = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    price_gate = closes.gt(closes.rolling(126, min_periods=126).mean())
    name = spec["name"]
    if name == "cash":
        return zero
    if name == "equal_weight_buy_hold":
        return zero + 1 / n
    if name == "price_only_sma126":
        return price_gate.astype(float) / n
    if name == "all_disclosures_h63":
        selected = event_features.drop_duplicates(["ticker", "filing_date", "reportperiod"])
        horizon = 63
    else:
        subset = event_features[event_features.family.eq(spec["family"])]
        if spec.get("opposite"):
            subset = subset[subset.feature_status.eq("observed") & ~subset.selected]
        else:
            subset = subset[subset.selected]
        selected = subset
        horizon = spec["horizon"]
    for event in selected.itertuples():
        available = pd.Timestamp(event.date_only_available_after)
        if available.tzinfo is None or event.ticker not in closes:
            raise DataGateError("Source availability and original roster required")
        first = int(schedule.close.searchsorted(available, side="left"))
        # Old disclosures do not receive a fresh holding life at the panel boundary.
        if available < schedule.open.iloc[0] or first >= len(closes):
            continue
        zero.iloc[first:min(first + horizon, len(closes)), zero.columns.get_loc(event.ticker)] = 1 / n
    return zero.where(price_gate, 0.0) if spec.get("price_gate") else zero


def cash_accrual(index, annual_yield):
    if not np.isfinite(annual_yield) or annual_yield < 0:
        raise DataGateError("Cash sensitivity must be a nonnegative explicit assumption")
    closes = session_schedule(index).close
    years = closes.diff().dt.total_seconds().fillna(0) / (365.25 * 86400)
    return (1 + annual_yield) ** years - 1


def window_metrics(result, pair):
    dates = result.returns.index.tz_convert("America/New_York").strftime("%Y-%m-%d")
    mask = (dates >= pair[0]) & (dates <= pair[1])
    actual = result.returns.index[mask]
    if not len(actual):
        raise DataGateError("Empty frozen evaluation window")
    return metrics(result, actual[0], actual[-1])


def uncertainty(book, controls, *, reps=2000, block=21, seed=20261126):
    """Paired resampling preserves date covariance; not whole-research selection proof."""
    names = sorted(book)
    if not names or set(names) != set(controls):
        raise DataGateError("One aligned unchanged control per candidate required")
    reference = book[names[0]].index
    if any(not book[n].index.equals(reference) or not controls[n].index.equals(reference) for n in names):
        raise DataGateError("Bootstrap candidate/control dates must match")
    values = np.column_stack([(book[n] - controls[n]).to_numpy(float) for n in names])
    if len(values) < block * 3 or not np.isfinite(values).all():
        raise DataGateError("Insufficient finite paired return observations")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values) - block + 1, size=(reps, int(np.ceil(len(values) / block))))
    indices = (indices[..., None] + np.arange(block)).reshape(reps, -1)[:, :len(values)]
    sampled = values[indices].mean(axis=1) * 252
    observed = values.mean(axis=0) * 252
    # Center each strategy under a zero-mean null, with identical resampled dates.
    null_max = np.abs(sampled - observed).max(axis=1)
    return [{"policy": n, "block_sessions": block, "observations": len(values),
             "annualized_arithmetic_excess": float(observed[i]),
             "lower_95": float(np.quantile(sampled[:, i], .025)),
             "upper_95": float(np.quantile(sampled[:, i], .975)),
             "within_round_max_abs_mean_p": float((1 + (null_max >= abs(observed[i])).sum()) / (reps + 1)),
             "not_whole_program_selection_corrected": True} for i, n in enumerate(names)]


def run(root: Path, output: Path):
    protocol_file = output / "protocol.json"
    if (output / "summary.json").exists() or (output / "registry.json").exists():
        raise FileExistsError("Frozen output cannot be overwritten or resumed over partial results")
    if sha(protocol_file) != (output / "protocol.sha256").read_text().strip():
        raise DataGateError("Frozen protocol changed")
    protocol = json.loads(protocol_file.read_text())
    if (protocol.get("kind") != KIND or protocol.get("policies") != specifications()
            or protocol.get("code_hashes") != code_hashes()
            or protocol.get("source_manifest_sha256") != sha(root / "acquisition.json")
            or protocol.get("source_protocol_sha256") != sha(root / "protocol.json")
            or protocol.get("portfolio_allocation_allowed") is not False):
        raise DataGateError("Frozen research source/code/specification mismatch")
    source, facts, prices, evidence = load_sample(root)
    if evidence != protocol["evidence"] or source["roster"] != protocol["roster"]:
        raise DataGateError("Source census changed")
    closes = load_closes(root, prices)
    event_features = features(facts)
    specs = protocol["policies"]
    targets = {spec["name"]: policy_targets(event_features, closes, spec) for spec in specs}
    (output / "registry.json").write_text(json.dumps({"policies": specs, "source_evidence": evidence,
        "conditional_simulation_only": True, "portfolio_allocation_allowed": False}, indent=2) + "\n")
    shutil.copyfile(__file__, output / "auditor.py")
    event_features.to_parquet(output / "features.parquet", index=False)
    periods = {"development": protocol["development"], "evaluation": protocol["evaluation"]}
    rows, fits, uncertainty_rows, daily_columns = [], [], [], {}
    evaluation_start = pd.Timestamp(protocol["evaluation"][0], tz="America/New_York")
    for scenario in protocol["primary_scenarios"] + protocol["cash_sensitivity_scenarios"]:
        lag, cost, cash_yield = scenario["lag"], scenario["cost_bps"], scenario["cash_yield"]
        suffix = f"lag{lag}_cost{cost}_cash{cash_yield:.2f}"
        cash = cash_accrual(prices.index, cash_yield)
        results = {name: replay(prices, closes, target, cash, lag=lag, cost_bps=cost)
                   for name, target in targets.items()}
        candidate_names = [s["name"] for s in specs if s["role"] == "candidate"]
        for name in candidate_names:
            dev = window_metrics(results[name], periods["development"])
            exposure = dev["average_equity_exposure"]
            matched_target = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
            known = prices.index.tz_convert("America/New_York").strftime("%Y-%m-%d") > protocol["development"][1]
            matched_target.loc[known, :] = exposure / len(prices.columns)
            control_name = f"exposure_control_{name}"
            results[control_name] = replay(prices, closes, matched_target, cash, lag=lag, cost_bps=cost)
            fits.append({"policy": name, **scenario, "development_exposure": exposure,
                         "fit_window_end": protocol["development"][1], "evaluation_used_for_fit": False})
        for name, result in results.items():
            for period, pair in periods.items():
                if name.startswith("exposure_control_") and period == "development":
                    continue
                row = {"policy": name, "period": period, **scenario, **window_metrics(result, pair)}
                rows.append(row)
            if cash_yield == 0 and cost == 25 and lag in (1, 5):
                daily_columns[f"{name}__{suffix}"] = result.returns
                if name in candidate_names:
                    folder = output / "audit_paths" / f"{name}__{suffix}"
                    folder.mkdir(parents=True)
                    result.fills.to_csv(folder / "fills.csv", index=False)
                    result.weights.to_parquet(folder / "realized_weights.parquet")
                    targets[name].to_parquet(folder / "close_known_targets.parquet")
        if cash_yield == 0 and cost == 25 and lag in (1, 5):
            book = {name: results[name].returns.loc[prices.index >= evaluation_start] for name in candidate_names}
            for control_kind in ("price_only_sma126", "equal_weight_buy_hold", "exposure_matched"):
                controls = {name: results[f"exposure_control_{name}" if control_kind == "exposure_matched" else control_kind].returns.loc[book[name].index]
                            for name in candidate_names}
                for block in (21, 63):
                    uncertainty_rows.extend([r | {**scenario, "control": control_kind}
                                             for r in uncertainty(book, controls, block=block)])
        print(json.dumps({"completed_scenario": scenario, "portfolio_paths": len(results)}), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "performance.csv", index=False)
    pd.DataFrame(fits).to_csv(output / "development_exposure_fits.csv", index=False)
    pd.DataFrame(uncertainty_rows).to_csv(output / "uncertainty.csv", index=False)
    daily = pd.DataFrame(daily_columns)
    daily.to_parquet(output / "daily_returns.parquet")
    yearly = []
    for name, returns in daily.items():
        for year, group in returns.groupby(returns.index.year):
            equity = (1 + group).cumprod()
            yearly.append({"path": name, "year": year, "sessions": len(group),
                           "total_return": float(equity.iloc[-1] - 1),
                           "drawdown_within_year": float((equity / equity.cummax().clip(lower=1) - 1).min())})
    pd.DataFrame(yearly).to_csv(output / "yearly.csv", index=False)
    summary = {"kind": KIND, "created_at_utc": datetime.now(UTC).isoformat(),
        "candidate_rules": 12, "unchanged_or_falsification_control_rules": 6,
        "development_fitted_exposure_controls_per_scenario": 12,
        "execution_cash_cost_scenarios": 11, "conditional_portfolio_paths": 330,
        "qualified_broad_portfolio_strategies": 0, "portfolio_allocation_allowed": False,
        "strategy_promotion_allowed": False, "not_genuine_unseen_holdout": True,
        "evaluation": protocol["evaluation"], "limitations": protocol["limitations"],
        "conclusion": "inspect_fixed_comparisons_and_uncertainty_no_automatic_selection_or_admission"}
    if code_hashes() != protocol["code_hashes"] or sha(root / "acquisition.json") != protocol["source_manifest_sha256"]:
        raise DataGateError("Frozen code or sources changed during the run")
    load_sample(root)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps({"kind": KIND, "source_root": str(root.resolve()),
        "source_evidence": evidence, "code_hashes": protocol["code_hashes"],
        "artifacts": {str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()}}, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "run"))
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = freeze(args.sources, args.output) if args.command == "freeze" else run(args.sources, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
