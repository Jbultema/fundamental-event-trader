"""New accounting-information tests on an explicitly unqualified fixed public sample."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from fundamental_event_trader import event_sample_portfolio as engine
from fundamental_event_trader.event_sample_pilot import delayed_date_cutoff, load_sample
from fundamental_event_trader.portfolio import replay
from fundamental_event_trader.sec import DataGateError, sha

FAMILIES = ("working_capital_repair", "self_funded_repurchase", "liquidity_repair")
EXTRA = ["receivables", "inventory", "revenue", "debt", "cashneq"]
KIND = "new_information_conditional_accounting_portfolio_not_broad_validation"


def structural_features(facts):
    if not set(EXTRA) <= set(facts):
        raise DataGateError("New accounting fields required; no substitute price signal")
    rows = []
    for ticker, group in facts.groupby("ticker", sort=True):
        seen = set()
        for row in group.sort_values(["date", "reportperiod"]).itertuples():
            base = {"ticker": ticker, "filing_date": row.date, "reportperiod": row.reportperiod,
                    "source_sha256": row.source_sha256,
                    "date_only_available_after": delayed_date_cutoff(row.date)}
            period = pd.Timestamp(row.reportperiod)
            prior = group[(group.date < row.date) & pd.to_datetime(group.reportperiod).between(
                period - pd.Timedelta(days=430), period - pd.Timedelta(days=300))].sort_values(["reportperiod", "date"])
            repeated = row.reportperiod in seen
            seen.add(row.reportperiod)
            status = "observed"
            if ticker == "JPM":
                status = "bank_accounting_excluded_before_returns"
            elif repeated:
                status = "repeated_period_excluded"
            elif prior.empty:
                status = "left_censored_prior_year_missing"
            current = {key: float(getattr(row, key)) for key in EXTRA}
            previous = prior.iloc[-1] if len(prior) else None
            if any(np.isfinite(current[k]) and current[k] < 0 for k in EXTRA):
                raise DataGateError("Negative accounting stock/revenue inputs require review")
            for family in FAMILIES:
                required = {"working_capital_repair": ["receivables", "inventory", "revenue"],
                            "self_funded_repurchase": ["debt"], "liquidity_repair": ["debt", "cashneq"]}[family]
                family_status, score, selected = status, None, False
                if status == "observed" and (not np.isfinite([current[k] for k in required]).all()
                        or not np.isfinite(previous[required].to_numpy(float)).all()
                        or (family == "working_capital_repair" and min(row.revenue, previous.revenue) <= 0)):
                    family_status = "missing_or_nonpositive_required_accounting_input"
                if family_status == "observed":
                    if family == "working_capital_repair":
                        score = float((previous.receivables + previous.inventory) / previous.revenue
                            - (row.receivables + row.inventory) / row.revenue)
                        selected = score > 0 and row.revenue >= previous.revenue and row.netinc > 0
                    elif family == "self_funded_repurchase":
                        score = float((row.ncfo + row.ncfcommon) / row.assets)
                        selected = row.ncfcommon < 0 and row.netinc > 0 and row.ncfo + row.ncfcommon >= 0 and row.debt <= previous.debt
                    else:
                        score = float((row.cashneq - row.debt) / row.assets - (previous.cashneq - previous.debt) / previous.assets)
                        selected = score > 0 and row.debt / row.assets < previous.debt / previous.assets and row.ncfo > 0
                rows.append(base | {"family": family, "score": score, "selected": bool(selected),
                    "feature_status": family_status, "prior_publication_date": previous.date if family_status == "observed" else None})
    return pd.DataFrame(rows)


def specs():
    return [{"name": f"{family}_h{horizon}", "family": family, "horizon": horizon,
             "price_gate": False, "role": "candidate"} for family, horizon in product(FAMILIES, (63, 126))] + [
        {"name": f"{family}_h21_falsification", "family": family, "horizon": 21,
         "price_gate": False, "role": "holding_life_falsification"} for family in FAMILIES] + [
        {"name": name, "role": "control"} for name in (
            "equal_weight_buy_hold", "price_only_sma126", "all_disclosures_h63", "cash")]


def source_check(root, previous):
    protocol, facts, prices, evidence = load_sample(root)
    acquisition = json.loads((root / "acquisition.json").read_text())
    if acquisition.get("prior_acquisition_sha256") != sha(previous / "acquisition.json"):
        raise DataGateError("Frozen original sample binding missing")
    old_protocol, old_facts, old_prices, _ = load_sample(previous)
    if protocol["roster"] != old_protocol["roster"]:
        raise DataGateError("No new return-selected roster")
    keys = ["ticker", "date", "reportperiod"]
    columns = keys + ["assets", "ncfo", "netinc", "ncfcommon"]
    pd.testing.assert_frame_equal(facts[columns].sort_values(keys).reset_index(drop=True),
                                 old_facts[columns].sort_values(keys).reset_index(drop=True), check_exact=True)
    pd.testing.assert_frame_equal(prices, old_prices)
    followup = protocol.get("structural_followup", {})
    if (set(followup.get("families", {})) != set(FAMILIES)
            or followup.get("eligibility_exclusions") != {"JPM": "bank_cash_flow_working_capital_and_debt_are_not_comparable_to_nonfinancial_companies"}
            or followup.get("portfolio_allocation_allowed") is not False):
        raise DataGateError("Frozen new-information rules or eligibility changed")
    for column in EXTRA:
        facts[column] = pd.to_numeric(facts[column], errors="raise")
    return protocol, facts, prices, evidence


def code_hashes():
    return engine.code_hashes() | {Path(__file__).name: sha(Path(__file__)),
                                  Path(engine.__file__).name: sha(Path(engine.__file__))}


def freeze(root, previous, output):
    source, facts, _, evidence = source_check(root, previous)
    structural_features(facts)
    output.mkdir(parents=True, exist_ok=False)
    protocol = {"kind": KIND, "created_at_utc": datetime.now(UTC).isoformat(),
        "mechanisms": source["structural_followup"], "policies": specs(), "code_hashes": code_hashes(),
        "sources": evidence, "source_protocol_sha256": sha(root / "protocol.json"),
        "source_acquisition_sha256": sha(root / "acquisition.json"),
        "conditional_only_no_unseen_holdout": True, "portfolio_allocation_allowed": False,
        "cash_yields": [0., .04], "nonfinancial_slots": "original 10percent slots; JPM slot cash in every control",
        "initial_lags_costs": [[lag, cost] for lag, cost in product((1, 2, 5), (10, 25, 50))],
        "cash_sensitivity": {"lag": 1, "cost_bps": 25, "cash_yield": .04},
        "short_life_falsifiers": "also report each mechanism at 21 sessions so prior weak short-life results do not disappear from this follow-up; fixed before structural return evaluation",
        "development": source["structural_followup"]["development"],
        "evaluation": source["structural_followup"]["evaluation"],
        "limitations": ["same_ten_current_survivors", "only_nine_comparable_nonfinancial_companies",
            "funding_coverage_not_proof_of_cash_allocation", "balance_sheet_ratios_not_discrete_financing_event_content",
            "working_capital_ratios_can_change_with_acquisitions_and_business_mix", "assumed_cash_yield",
            "vendor_AR_vintages_not_independently_verified", "no_failure_paths_or_whole_program_selection_correction"]}
    file = output / "protocol.json"
    file.write_text(json.dumps(protocol, indent=2) + "\n")
    (output / "protocol.sha256").write_text(sha(file) + "\n")
    return {"kind": KIND, "candidate_rules": 6, "base_controls": 4, "short_life_falsifiers": 3,
            "portfolio_allocation_allowed": False, "output": str(output)}


def run(root, previous, output):
    if (output / "registry.json").exists():
        raise FileExistsError("Do not overwrite a started frozen research run")
    file = output / "protocol.json"
    if sha(file) != (output / "protocol.sha256").read_text().strip():
        raise DataGateError("Frozen protocol changed")
    protocol = json.loads(file.read_text())
    if protocol["code_hashes"] != code_hashes() or protocol["source_protocol_sha256"] != sha(root / "protocol.json") or protocol["source_acquisition_sha256"] != sha(root / "acquisition.json"):
        raise DataGateError("Frozen code or source changed")
    _, facts, prices, evidence = source_check(root, previous)
    closes = engine.load_closes(root, prices)
    signals = structural_features(facts)
    targets = {}
    for spec in specs():
        target = engine.policy_targets(signals, closes, spec)
        target["JPM"] = 0.
        targets[spec["name"]] = target
    (output / "registry.json").write_text(json.dumps(specs(), indent=2) + "\n")
    signals.to_parquet(output / "features.parquet", index=False)
    shutil.copyfile(__file__, output / "auditor.py")
    rows, fits, intervals, daily = [], [], [], {}
    scenarios = [{"lag": lag, "cost_bps": cost, "cash_yield": 0.} for lag, cost in protocol["initial_lags_costs"]] + [protocol["cash_sensitivity"]]
    for scenario in scenarios:
        cash = engine.cash_accrual(prices.index, scenario["cash_yield"])
        args = {"lag": scenario["lag"], "cost_bps": scenario["cost_bps"]}
        book = {name: replay(prices, closes, target, cash, **args) for name, target in targets.items()}
        candidates = [s["name"] for s in specs() if s["role"] == "candidate"]
        for name in candidates:
            exposure = engine.window_metrics(book[name], protocol["development"])["average_equity_exposure"]
            target = prices * 0.
            after = prices.index.tz_convert("America/New_York").strftime("%Y-%m-%d") > protocol["development"][1]
            target.loc[after, [c for c in prices if c != "JPM"]] = exposure / 9
            book[f"exposure_control_{name}"] = replay(prices, closes, target, cash, **args)
            fits.append({"policy": name, **scenario, "development_exposure": exposure, "evaluation_used": False})
        for name, result in book.items():
            for period in ("development", "evaluation"):
                if period == "development" and name.startswith("exposure_control_"):
                    continue
                rows.append({"policy": name, **scenario, "period": period,
                             **engine.window_metrics(result, protocol[period])})
        if scenario["cash_yield"] == 0 and scenario["cost_bps"] == 25 and scenario["lag"] in (1, 5):
            suffix = f"lag{scenario['lag']}_cost25"
            evaluation = prices.index >= pd.Timestamp(protocol["evaluation"][0], tz="America/New_York")
            for name, result in book.items():
                daily[f"{name}__{suffix}"] = result.returns
            for control_kind in ("equal_weight_buy_hold", "price_only_sma126", "exposure_matched"):
                for block in (21, 63):
                    intervals += [r | scenario | {"control": control_kind} for r in engine.uncertainty(
                        {n: book[n].returns.loc[evaluation] for n in candidates},
                        {n: book[f"exposure_control_{n}" if control_kind == "exposure_matched" else control_kind].returns.loc[evaluation] for n in candidates}, block=block)]
        print(json.dumps({"completed_scenario": scenario, "portfolio_paths": len(book)}), flush=True)
    pd.DataFrame(rows).to_csv(output / "performance.csv", index=False)
    pd.DataFrame(fits).to_csv(output / "exposure_fits.csv", index=False)
    pd.DataFrame(intervals).to_csv(output / "uncertainty.csv", index=False)
    pd.DataFrame(daily).to_parquet(output / "daily_returns.parquet")
    source_check(root, previous)
    if protocol["code_hashes"] != code_hashes():
        raise DataGateError("Code changed during the run")
    summary = {"kind": KIND, "mechanisms": 3, "candidate_rules": 6, "short_life_falsifiers": 3,
        "conditional_portfolio_paths": 190,
        "qualified_broad_strategies": 0, "portfolio_allocation_allowed": False,
        "feature_status_counts": signals.feature_status.value_counts().to_dict(),
        "selected_events": signals[signals.selected].family.value_counts().to_dict(),
        "limitations": protocol["limitations"], "not_genuine_unseen_holdout": True}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps({"kind": KIND, "sources": evidence,
        "code_hashes": protocol["code_hashes"],
        "artifacts": {p.name: sha(p) for p in output.iterdir() if p.is_file()}}, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "run"))
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps((freeze if args.command == "freeze" else run)(args.sources, args.previous, args.output), indent=2))


if __name__ == "__main__":
    main()
