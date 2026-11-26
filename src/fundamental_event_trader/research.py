"""Immutable, leakage-checked portfolio experiments over a qualified event census."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fundamental_event_trader.portfolio import Replay, metrics, replay
from fundamental_event_trader.qualification import qualify, validate_dataset
from fundamental_event_trader.sec import DataGateError, sha, timestamp
from fundamental_event_trader.strategy import (
    eligible_events,
    policies,
    session_schedule,
    targets,
)


def code_hash() -> str:
    digest = hashlib.sha256()
    for file in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(file.name.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


@dataclass
class Dataset:
    root: Path
    manifest: dict
    events: pd.DataFrame
    identity: pd.DataFrame
    opens: pd.DataFrame
    closes: pd.DataFrame
    cash: pd.Series
    terminals: pd.DataFrame


def load_dataset(root: Path, *, fixture_only=False) -> Dataset:
    status = qualify(root)
    if not status["historical_event_study_allowed"]:
        raise DataGateError("Historical data qualification failed: " + "; ".join(status["errors"]))
    meta = json.loads((root / "manifest.json").read_text())
    if meta.get("data_kind") != "real_historical" and not fixture_only:
        raise DataGateError("Real-data research cannot use synthetic or unspecified datasets")
    if fixture_only and meta.get("data_kind") != "synthetic_fixture":
        raise DataGateError("Fixture mode is restricted to explicitly synthetic datasets")
    if not fixture_only:
        for criterion, evidence in meta["criteria"].items():
            attestation = json.loads((root / evidence["evidence_artifact"]).read_text())
            if not isinstance(attestation, dict):
                raise DataGateError("Source-review evidence must be an object")
            sources = attestation.get("source_artifacts", [])
            if (
                attestation.get("criterion") != criterion
                or attestation.get("reviewed") is not True
                or attestation.get("review_scope") != "real_sources_not_test_fixtures"
                or not isinstance(attestation.get("reviewer"), str)
                or not attestation["reviewer"].strip()
                or attestation.get("fixture_only") is not False
                or not sources
                or not set(sources) <= set(meta["artifacts"])
            ):
                raise DataGateError(
                    "Real-source review evidence required for each qualification criterion"
                )
    required = {"close_prices.parquet", "cash_returns.parquet", "terminal_events.parquet"}
    if not required <= meta["artifacts"].keys():
        raise DataGateError(
            "Portfolio research requires bound closes, cash and terminal settlements"
        )
    events, opens = validate_dataset(root)
    session_schedule(opens.index)
    identity = pd.read_parquet(root / "identity.parquet")
    closes = pd.read_parquet(root / "close_prices.parquet")
    cash = pd.read_parquet(root / "cash_returns.parquet")["cash_return"]
    terminals = pd.read_parquet(root / "terminal_events.parquet")
    if not closes.index.equals(opens.index) or not closes.columns.equals(opens.columns):
        raise DataGateError("Open and close panels must match securities and actual sessions")
    if not cash.index.equals(opens.index) or not np.isfinite(cash).all() or cash.le(-1).any():
        raise DataGateError("Verified historical cash returns must align")
    if np.isinf(closes.to_numpy(float)).any() or closes.le(0).any().any():
        raise DataGateError("Invalid adjusted closing price")
    if closes.SPY.isna().any():
        raise DataGateError("Missing benchmark close")
    required_events = {"available_at", "accession", "source_sha256"}
    if not required_events <= set(events):
        raise DataGateError("Source-bound feature availability required")
    source_hashes = set(meta["artifacts"].values())
    if not set(events.source_sha256) <= source_hashes:
        raise DataGateError("Event content hashes must bind actual source artifacts")
    if "post_filing_return" in events and events.post_filing_return.notna().any():
        required_window = {"price_window_end", "post_filing_price_sha256"}
        if not required_window <= set(events):
            raise DataGateError("Post-filing returns require a bound observed price window")
        closes_at = session_schedule(opens.index).close
        for row in events[events.post_filing_return.notna()].itertuples():
            end = timestamp(row.price_window_end)
            available = timestamp(row.available_at)
            start = closes_at.searchsorted(timestamp(row.accepted_at), side="right")
            finish = closes_at.searchsorted(end, side="left")
            if (
                finish >= len(closes_at)
                or start >= finish
                or closes_at.iloc[finish] != end
                or end > available
                or row.post_filing_price_sha256 != meta["artifacts"]["close_prices.parquet"]
            ):
                raise DataGateError("Invalid or future post-filing price window")
            values = closes.iloc[[start, finish]][row.security_id]
            if not np.isfinite(values).all() or not np.isclose(
                values.iloc[1] / values.iloc[0] - 1, row.post_filing_return, rtol=1e-8, atol=1e-10
            ):
                raise DataGateError("Post-filing feature does not reconcile to observed prices")
    # Terminal-treatment booleans alone are not enough for portfolio execution.
    required_terminal = {
        "security_id",
        "settlement_at",
        "value_per_adjusted_share",
        "source_sha256",
    }
    if not required_terminal <= set(terminals):
        raise DataGateError("Explicit terminal cash and source evidence required")
    dead = set(identity.loc[identity.delisted, "security_id"])
    if not dead <= set(terminals.security_id) or terminals.security_id.duplicated().any():
        raise DataGateError("Every delisted identity needs one terminal cash settlement")
    if not set(terminals.source_sha256) <= source_hashes:
        raise DataGateError("Unbound terminal settlement evidence")
    if set(terminals.security_id) - set(identity.security_id):
        raise DataGateError("Unknown terminal security")
    # Validate all available family semantics before any performance is viewed.
    for policy in policies():
        columns = {
            "profitability_change",
            "cash_conversion",
            "net_repurchase",
            "distinct_buyers",
            "post_filing_return",
            "stake_change",
            "verified_event_score",
        } & set(events)
        if columns:
            try:
                eligible_events(events, policy)
            except DataGateError as exc:
                if not str(exc).startswith(
                    (
                        "Unimplemented or unavailable",
                        "Content verification flags",
                        "Insider clusters require",
                    )
                ):
                    raise
    return Dataset(root, meta, events, identity, opens, closes, cash, terminals)


def bootstrap_excess(candidate, benchmark, *, reps=1000, block=21, seed=20261125):
    """Paired moving-block interval; not independent-event significance."""
    excess = candidate.sub(benchmark).dropna().to_numpy(float)
    if len(excess) < block * 3:
        return {"status": "insufficient_observations", "observations": len(excess)}
    rng = np.random.default_rng(seed)
    starts = rng.integers(
        0, len(excess) - block + 1, size=(reps, int(np.ceil(len(excess) / block)))
    )
    offsets = np.arange(block)
    samples = excess[(starts[..., None] + offsets).reshape(reps, -1)[:, : len(excess)]]
    averages = samples.mean(axis=1) * 252
    return {
        "status": "descriptive_paired_block_interval",
        "observations": len(excess),
        "block": block,
        "repetitions": reps,
        "annual_mean_excess": float(excess.mean() * 252),
        "lower_95": float(np.quantile(averages, 0.025)),
        "upper_95": float(np.quantile(averages, 0.975)),
        "not_multiple_testing_corrected": True,
    }


def run(root: Path, output: Path, *, fixture_only=False) -> Path:
    initial = code_hash()
    data = load_dataset(root, fixture_only=fixture_only)
    index = data.opens.index
    # Fixed chronological partitions and a full holding-horizon purge at boundaries.
    n = len(index)
    a, b, purge = int(n * 0.6), int(n * 0.8), 63
    if min(a, b - a - purge, n - b - purge) < 252:
        raise DataGateError("Insufficient independent development/validation/lockbox intervals")
    periods = {
        "development": (index[0], index[a - 1]),
        "validation": (index[a + purge], index[b - 1]),
        "lockbox": (index[b + purge], index[-1]),
    }
    output.mkdir(parents=True, exist_ok=False)
    frozen = {
        "policies": [p.specification() for p in policies()],
        "partitions": {k: [str(v) for v in pair] for k, pair in periods.items()},
        "purge_sessions": purge,
        "selection": "highest development excess CAGR minus excess drawdown penalty; lexical tie break",
        "holdout_use": "retrospective chronological diagnostic; never runner selection or automatic promotion; not claimed previously unseen",
        "dataset_root": str(root.resolve()),
        "data_manifest_sha256": sha(root / "manifest.json"),
        "code_sha256": initial,
        "fixture_only": fixture_only,
    }
    (output / "registry.json").write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    benchmark_target = pd.DataFrame(0.0, index=index, columns=data.opens.columns)
    benchmark_target["SPY"] = 1.0
    benchmark = replay(
        data.opens, data.closes, benchmark_target, data.cash, terminal_events=data.terminals
    )
    cash = replay(
        data.opens, data.closes, benchmark_target * 0.0, data.cash, terminal_events=data.terminals
    )
    results: dict[str, Replay] = {"buy_hold_SPY": benchmark, "cash": cash}
    target_book, specs, status_rows, rows = {}, {}, [], []
    for policy in policies():
        try:
            eligible = eligible_events(data.events, policy)
        except DataGateError as exc:
            if str(exc).startswith(
                (
                    "Unimplemented or unavailable",
                    "Content verification flags",
                    "Insider clusters require",
                )
            ):
                status_rows.append(
                    {"name": policy.name, "status": "unavailable_features", "reason": str(exc)}
                )
                continue
            raise
        if eligible.empty:
            status_rows.append({"name": policy.name, "status": "no_qualifying_events", "events": 0})
            continue
        weight = targets(data.events, index, data.identity, policy)
        result = replay(data.opens, data.closes, weight, data.cash, terminal_events=data.terminals)
        if not result.fills.kind.eq("buy").any():
            status_rows.append({
                "name": policy.name, "status": "no_observed_execution", "events": len(eligible), "fills": 0,
            })
            continue
        results[policy.name], target_book[policy.name], specs[policy.name] = result, weight, policy
        status_rows.append(
            {
                "name": policy.name,
                "status": "tested",
                "events": len(eligible),
                "fills": len(result.fills),
            }
        )
    for name, result in results.items():
        for period, (start, end) in periods.items():
            rows.append({"name": name, "period": period, **metrics(result, start, end)})
    performance = pd.DataFrame(rows)
    performance.to_csv(output / "performance.csv", index=False)
    pd.DataFrame(status_rows).to_csv(output / "hypothesis_status.csv", index=False)
    return_frame = pd.DataFrame({name: result.returns for name, result in results.items()})
    return_frame.to_parquet(output / "returns.parquet")
    chosen = None
    if target_book:
        dev = performance[performance.period.eq("development")].set_index("name")
        base = dev.loc["buy_hold_SPY"]
        scores = {
            name: float(
                dev.loc[name, "cagr"]
                - base.cagr
                - max(0.0, abs(dev.loc[name, "max_drawdown"]) - abs(base.max_drawdown))
            )
            for name in target_book
        }
        chosen = sorted(scores, key=lambda name: (-scores[name], name))[0]
    stress_rows, regime_rows, walk_rows = [], [], []
    uncertainty = {}
    if chosen:
        selected = results[chosen]
        for lag in (1, 2, 5):
            for cost in (10.0, 25.0, 50.0):
                stressed = replay(
                    data.opens,
                    data.closes,
                    target_book[chosen],
                    data.cash,
                    cost_bps=cost,
                    lag=lag,
                    terminal_events=data.terminals,
                )
                stress_rows.append(
                    {
                        "name": chosen,
                        "lag": lag,
                        "cost_bps_per_side": cost,
                        **metrics(stressed, *periods["lockbox"]),
                    }
                )
        close = data.closes.SPY
        prior = close.shift(1)
        volatility = close.pct_change(fill_method=None).rolling(21).std().shift(1) * np.sqrt(252)
        state = pd.Series(
            np.where(prior < close.rolling(200).mean().shift(1), "below_200ma", "above_200ma"),
            index=index,
        )
        state[volatility > 0.25] = "high_volatility"
        state[close.rolling(200).count().shift(1).fillna(0) < 200] = "warmup"
        lock = selected.returns.loc[periods["lockbox"][0] :]
        for regime in sorted(set(state.loc[lock.index])):
            idx = lock.index[state.loc[lock.index].eq(regime)]
            regime_rows.append(
                {
                    "regime": regime,
                    "sessions": len(idx),
                    "mean_daily_return": float(lock.loc[idx].mean()),
                    "mean_daily_SPY_return": float(benchmark.returns.loc[idx].mean()),
                    "note": "conditional daily observations, not stitched regime CAGR",
                }
            )
        uncertainty = bootstrap_excess(lock, benchmark.returns.loc[lock.index])
        # Expanding selection sees only outcomes before the year's purged start.
        walk_targets = pd.DataFrame(0.0, index=index, columns=data.opens.columns)
        for year in sorted(set(index.year))[3:]:
            test = index[index.year == year]
            before = index[index < test[0]]
            if len(before) < 756 + purge or len(test) < 126:
                continue
            train_end = before[-purge - 1]
            train = performance_candidates(results, target_book, index[0], train_end)
            winner = sorted(train, key=lambda name: (-train[name], name))[0]
            walk_targets.loc[test, target_book[winner].columns] = target_book[winner].loc[test]
            walk_rows.append(
                {
                    "year": year,
                    "selected": winner,
                    "selection_outcomes_through": str(train_end),
                    "test_start": str(test[0]),
                    "test_end": str(test[-1]),
                }
            )
        walk_result = replay(
            data.opens, data.closes, walk_targets, data.cash, terminal_events=data.terminals
        )
        for row in walk_rows:
            row.update(metrics(walk_result, row["test_start"], row["test_end"]))
        walk_result.returns.to_frame("return").to_parquet(output / "walk_forward_returns.parquet")
        target_book[chosen].to_parquet(output / "selected_targets.parquet")
        selected.fills.to_parquet(output / "selected_fills.parquet", index=False)
        selected.weights.to_parquet(output / "selected_realized_weights.parquet")
    pd.DataFrame(stress_rows).to_csv(output / "execution_stress.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(output / "regimes.csv", index=False)
    pd.DataFrame(walk_rows).to_csv(output / "walk_forward.csv", index=False)
    selection = {
        "selected_research_policy": chosen,
        "policy": specs[chosen].specification() if chosen else None,
        "tested": len(target_book),
        "registered": len(policies()),
        "fixture_only": fixture_only,
        "portfolio_allocation_allowed": False,
        "automatic_promotion_allowed": False,
        "action": "NO ACTION",
        "uncertainty": uncertainty,
        "limits": [
            "Development selected; validation and lockbox are reporting-only, not retuning inputs.",
            "One dataset and one retrospective lockbox do not establish future profitability.",
            "Paired block intervals do not correct for testing multiple hypotheses.",
            "A prospective shadow record and explicit admission review are still required.",
        ],
    }
    (output / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    (output / "readout.md").write_text(readout(selection, performance))
    if code_hash() != initial or sha(root / "manifest.json") != frozen["data_manifest_sha256"]:
        raise DataGateError("Research source or dataset changed during execution")
    manifest = {
        "schema_version": 1,
        "system": "fundamental-event-trader",
        "kind": "portfolio_research",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "data_end": str(index[-1].date()),
        "code_sha256": initial,
        "dataset_manifest_sha256": frozen["data_manifest_sha256"],
        "data_kind": data.manifest.get("data_kind"),
        "fixture_only": fixture_only,
        "authority": "research_only",
        "action_authorized": False,
        "artifacts": {
            str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return output


def performance_candidates(results, targets_by_name, start, end):
    base = metrics(results["buy_hold_SPY"], start, end)
    return {
        name: metrics(results[name], start, end)["cagr"]
        - base["cagr"]
        - max(
            0.0, abs(metrics(results[name], start, end)["max_drawdown"]) - abs(base["max_drawdown"])
        )
        for name in targets_by_name
    }


def readout(selection, frame):
    lines = ["# Fundamental Event Trader: Portfolio Research", ""]
    if selection["fixture_only"]:
        lines += [
            "SYNTHETIC FIXTURE ONLY. These figures are software-test outputs, not investment evidence.",
            "",
        ]
    lines += [
        f"Registered hypotheses: {selection['registered']}. Actually tested: {selection['tested']}.",
        f"Development-selected research policy: {selection['selected_research_policy'] or 'none'}.",
        "",
        "| Policy | Period | CAGR | Maximum drawdown | Average equity exposure |",
        "|---|---|---:|---:|---:|",
    ]
    for row in frame.itertuples():
        if row.name in {selection["selected_research_policy"], "buy_hold_SPY", "cash"}:
            lines.append(
                f"| {row.name} | {row.period} | {row.cagr:.2%} | {row.max_drawdown:.2%} | {row.average_equity_exposure:.1%} |"
            )
    lines += ["", *selection["limits"], "", "No trading or automatic promotion is authorized.", ""]
    return "\n".join(lines)
