# Readiness: November 25, 2026

## Verified implementation

The project has an independent package, CLI, source contracts, pinned tested dependency snapshot,
CI configuration, and offline tests. It reuses Swing Trader SEC metadata through a verified
file import; no existing Swing Trader ranking or portfolio state is modified.

Safeguards cover publication timestamps, amended versus original facts, issuer identity,
annual versus quarterly denominators, unmatched cashflow years, accounting-tag changes,
insider transaction types, XML entities, missing event securities, historical membership,
delisted terminal intervals, source-byte integrity and unmatured outcomes.

Forty-eight hypotheses are registered, not backtested. Matched event-study machinery is separate
from a tradable portfolio CAGR, and neither can authorize allocation. Content-dependent 13D/13G
and 8-K hypotheses remain disabled; filing metadata is not a directional signal.

## Actual source evidence

Official SEC request: `https://data.sec.gov/submissions/CIK0000320193.json`.
The November 25 probe returned HTTP 403. The response bytes and SHA256 are preserved under
`data/captures/access_probe_20261125/`; there was no retry around access controls, no unofficial
mirror and no substitute current-winner backtest. Company Facts acquisition was not attempted
after the blocked submissions request.

The historical-dataset qualification remains blocked. No survivor-free price/identity panel
including delisted companies has passed the required evidence gates. Synthetic fixtures verify
that a complete contract can pass and that future identities, wrong issuers, fabricated terminal
paths and unbound evidence fail. Those fixtures provide software evidence only, not investment
performance evidence.

## Remaining work requiring real data

- Establish reliable official-source access or import an independently obtained, byte-preserved
  official public archive under the same provenance contract.
- Acquire archived submissions to bind older fact accessions to exact public acceptance times.
- Qualify historical security identity, membership, delisting and adjusted price coverage.
- Finish content-specific ownership-change and 8-K interpretation, then register exact event
  definitions before viewing their economic outcomes.
- Run clustered/matched event studies, then build a self-financing portfolio policy for Portfolio
  Lab admission only if it provides defensible incremental evidence.

No successful SEC download, strategy alpha, portfolio CAGR or live readiness is claimed.

## Cleanup Followup

Dataset qualification now also rejects empty tables, invalid identity intervals, nonfinite
signals/prices and missing benchmark marks. Event-study paths validate security and benchmark
observations throughout the holding interval. These are additional software safeguards, not
real-data hypothesis results. The cross-system review is maintained in Portfolio Lab under
`docs/system_assessment_20261125.md`; its verifier runs this repository's isolated environment.
