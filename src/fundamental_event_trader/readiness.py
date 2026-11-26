"""Content-family evidence counts, not a count of configuration variants as discoveries."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from fundamental_event_trader.sec import DataGateError
from fundamental_event_trader.strategy import eligible_events, policies

CONTENT = {
    "profitability_change": "Annual as-filed profitability changes",
    "cash_conversion": "Annual cash conversion from matched accounting periods",
    "net_repurchase": "Annual net repurchases from matched accounting periods",
    "insider_cluster": "Parsed Form 4 market-or-private purchases by identified owners",
    "post_filing_drift": "Completed, price-reconciled post-filing window",
    "ownership_change": "Verified ownership content; automatic parser not implemented",
    "eight_k_event": "Verified 8-K event content; automatic parser not implemented",
    "profitability_plus_cash": "Joint profitability and cash-conversion evidence",
    "repurchase_plus_profitability": "Joint repurchase and profitability evidence",
    "insider_plus_filing": "Joint insider purchase and post-filing price evidence",
}


def coverage(events=None, report=None):
    tested = set()
    if report is not None:
        frame = pd.read_csv(report / "hypothesis_status.csv")
        tested = set(frame.loc[frame.status.eq("tested"), "name"])
    families = defaultdict(list)
    for policy in policies():
        families[policy.family].append(policy)
    result = []
    for family, variants in families.items():
        available, counts, reasons = 0, [], set()
        if events is not None:
            for policy in variants:
                try:
                    eligible = eligible_events(events, policy)
                    available += 1
                    counts.append(len(eligible))
                except DataGateError as exc:
                    reasons.add(str(exc))
        else:
            reasons.add("no_qualified_historical_dataset")
        result.append({
            "family": family, "content": CONTENT[family],
            "registered_variants": len(variants), "variants_with_features": available,
            "tested_variants": sum(p.name in tested for p in variants),
            "eligible_events_at_least_restrictive_threshold": max(counts, default=0),
            "limitations": sorted(reasons),
        })
    return result
