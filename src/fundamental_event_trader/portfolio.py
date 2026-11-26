"""Long-only, self-financing next-open portfolios; no event-average CAGR claims."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fundamental_event_trader.sec import DataGateError
from fundamental_event_trader.strategy import session_schedule


@dataclass
class Replay:
    returns: pd.Series
    equity: pd.Series
    weights: pd.DataFrame
    cash: pd.Series
    turnover: pd.Series
    fees: pd.Series
    fills: pd.DataFrame


def replay(
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    targets: pd.DataFrame,
    cash_returns: pd.Series,
    *,
    cost_bps=10.0,
    lag=1,
    terminal_events: pd.DataFrame | None = None,
) -> Replay:
    """Decision at close t, fill open t+lag; existing holdings bear overnight moves.

    Costs apply to each side's traded notional and are funded from NAV. Targets remain
    fixed until changed; holdings drift. A missing held quote is an error, not a free
    exit. Verified terminal cash can settle worthless or delisted shares explicitly.
    Cash yield is a known accrual, split by elapsed time into overnight and intraday
    portions. Cash deployed at the open cannot also earn that day's intraday interest.
    """
    schedule = session_schedule(opens.index)
    if (
        not closes.index.equals(opens.index)
        or not targets.index.equals(opens.index)
        or not opens.columns.equals(closes.columns)
        or not opens.columns.is_unique
        or not targets.columns.is_unique
        or not set(targets) <= set(opens)
        or not cash_returns.index.equals(opens.index)
    ):
        raise DataGateError("Portfolio prices, targets and cash must align exactly")
    if (
        isinstance(lag, bool)
        or not isinstance(lag, int)
        or lag < 1
        or not np.isfinite(cost_bps)
        or not 0 <= cost_bps <= 100
    ):
        raise DataGateError("Invalid execution lag or transaction costs")
    for frame in (opens, closes):
        if np.isinf(frame.to_numpy(float)).any() or frame.le(0).any().any():
            raise DataGateError("Observed prices must be finite and positive")
    if (
        not np.isfinite(targets.to_numpy(float)).all()
        or targets.lt(0).any().any()
        or targets.sum(axis=1).gt(1 + 1e-10).any()
        or not np.isfinite(cash_returns.to_numpy(float)).all()
        or cash_returns.le(-1).any()
    ):
        raise DataGateError("Finite long-only self-financing targets and cash required")
    terminals = {}
    if terminal_events is not None and not terminal_events.empty:
        required = {"security_id", "settlement_at", "value_per_adjusted_share"}
        if not required <= set(terminal_events) or terminal_events.security_id.duplicated().any():
            raise DataGateError("Unique verified terminal settlements required")
        for row in terminal_events.itertuples():
            stamp = pd.Timestamp(row.settlement_at)
            if (
                pd.isna(stamp)
                or stamp.tzinfo is None
                or not np.isfinite(row.value_per_adjusted_share)
                or row.value_per_adjusted_share < 0
                or row.security_id not in opens
            ):
                raise DataGateError("Invalid terminal settlement")
            terminals[row.security_id] = (stamp.tz_convert("UTC"), row.value_per_adjusted_share)
    desired = targets.reindex(columns=opens.columns, fill_value=0.0).shift(lag).fillna(0.0)
    shares = np.zeros(len(opens.columns))
    cash = nav = 1.0
    previous = np.zeros(len(shares))
    records, returns, cash_weights, turnover, fees, fills = [], [], [], [], [], []
    for i, stamp in enumerate(opens.index):
        prior_nav = nav
        growth = 1 + float(cash_returns.iloc[i])
        span = (schedule.close.iloc[i] - schedule.close.iloc[i - 1]).total_seconds() if i else 0.0
        overnight_fraction = (
            (stamp - schedule.close.iloc[i - 1]).total_seconds() / span if i else 0.0
        )
        cash *= growth**overnight_fraction
        price = opens.iloc[i].to_numpy(float)
        mark = closes.iloc[i].to_numpy(float)
        target = desired.iloc[i].to_numpy(float).copy()
        for j, security in enumerate(opens.columns):
            if security in terminals and terminals[security][0] <= stamp:
                if shares[j] > 0:
                    proceeds = shares[j] * terminals[security][1]
                    cash += proceeds
                    fills.append(
                        {
                            "session": stamp,
                            "security_id": security,
                            "kind": "terminal_settlement",
                            "notional": proceeds,
                        }
                    )
                    shares[j] = 0.0
                # Settlement cancels stale targets; it does not provide a discretionary
                # pre-delisting exit or assume recovery of the last quoted market value.
                target[j] = 0.0
        held = shares > 1e-12
        if np.any(held & ~np.isfinite(price)):
            raise DataGateError(f"Unpriced overnight holding at {stamp}; terminal cash required")
        dollars = np.where(held, shares * price, 0.0)
        pre = cash + dollars.sum()
        if pre == 0:
            records.append(np.zeros_like(shares))
            cash_weights.append(1.0)
            returns.append(-1.0 if prior_nav > 0 else 0.0)
            turnover.append(0.0)
            fees.append(0.0)
            nav = 0.0
            previous = target
            continue
        traded = fee = 0.0
        if not np.allclose(target, previous, atol=1e-12, rtol=0):
            if np.any(((target > 1e-12) | held) & ~np.isfinite(price)):
                raise DataGateError("Unpriced trade; no survivor substitution")
            post = pre
            for _ in range(24):
                post = pre - cost_bps / 10000 * np.abs(target * post - dollars).sum()
            assets = target * post
            delta = assets - dollars
            traded = float(np.abs(delta).sum() / pre)
            fee = float((pre - post) / pre)
            shares = np.divide(assets, price, out=np.zeros_like(assets), where=assets > 1e-12)
            cash = float(post - assets.sum())
            for j in np.flatnonzero(np.abs(delta) > 1e-12):
                fills.append(
                    {
                        "session": stamp,
                        "security_id": opens.columns[j],
                        "kind": "buy" if delta[j] > 0 else "sell",
                        "notional": float(delta[j]),
                    }
                )
        cash *= growth ** (1 - overnight_fraction)
        for j, security in enumerate(opens.columns):
            if (
                security in terminals
                and stamp < terminals[security][0] <= schedule.close.iloc[i]
                and shares[j] > 1e-12
            ):
                proceeds = shares[j] * terminals[security][1]
                remaining = (
                    (schedule.close.iloc[i] - terminals[security][0]).total_seconds() / span
                    if i
                    else 0.0
                )
                cash += proceeds * growth**remaining
                fills.append(
                    {
                        "session": stamp,
                        "security_id": security,
                        "kind": "terminal_settlement",
                        "notional": proceeds,
                    }
                )
                shares[j] = 0.0
        held = shares > 1e-12
        if np.any(held & ~np.isfinite(mark)):
            raise DataGateError("Unpriced closing holding; missing terminal path")
        values = np.where(held, shares * mark, 0.0)
        nav = float(cash + values.sum())
        if not np.isfinite(nav) or nav < 0 or cash < -1e-9:
            raise DataGateError("Self-financing NAV invariant failed")
        records.append(values / nav if nav > 0 else np.zeros_like(values))
        cash_weights.append(cash / nav if nav > 0 else 1.0)
        returns.append(nav / prior_nav - 1 if prior_nav > 0 else 0.0)
        turnover.append(traded)
        fees.append(fee)
        previous = target
    idx = opens.index
    r = pd.Series(returns, index=idx, name="return")
    return Replay(
        r,
        r.add(1).cumprod(),
        pd.DataFrame(records, index=idx, columns=opens.columns),
        pd.Series(cash_weights, index=idx),
        pd.Series(turnover, index=idx),
        pd.Series(fees, index=idx),
        pd.DataFrame(fills, columns=["session", "security_id", "kind", "notional"]),
    )


def metrics(result: Replay, start=None, end=None) -> dict:
    r = result.returns.loc[start:end]
    if r.empty:
        raise DataGateError("No returns in evaluation interval")
    nav = (1 + r).cumprod()
    peak = nav.cummax().clip(lower=1.0)
    vol = float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 else 0.0
    return {
        "sessions": len(r),
        "cagr": float(nav.iloc[-1] ** (252 / len(r)) - 1),
        "max_drawdown": float((nav / peak - 1).min()),
        "total_return": float(nav.iloc[-1] - 1),
        "volatility": vol,
        "sharpe": float(r.mean() * 252 / vol) if vol > 1e-12 else 0.0,
        "average_equity_exposure": float(1 - result.cash.loc[r.index].mean()),
        "annual_turnover": float(result.turnover.loc[r.index].mean() * 252),
        "cumulative_cost_fraction": float(result.fees.loc[r.index].sum()),
    }
