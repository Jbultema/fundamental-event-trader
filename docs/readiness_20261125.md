# Readiness: November 25, 2026

## Verified implementation

The project has an independent package, CLI, source contracts, pinned tested dependency snapshot,
CI configuration, and offline tests. It reuses Swing Trader SEC metadata through a verified
file import; no existing Swing Trader ranking or portfolio state is modified.

Safeguards cover publication timestamps, amended versus original facts, issuer identity,
annual versus quarterly denominators, unmatched cashflow years, accounting-tag changes,
insider transaction types, XML entities, missing event securities, historical membership,
delisted terminal intervals, source-byte integrity and unmatured outcomes.

Forty-eight hypotheses are registered, not backtested on qualified real data. Matched event-study machinery is separate
from the new tradable portfolio replay, and neither can authorize allocation. Content-dependent 13D/13G
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
- Run the implemented event-study and self-financing portfolio research pipelines on qualified
  real data; seek Portfolio Lab admission only if they provide defensible incremental evidence.

No successful SEC download, strategy alpha, portfolio CAGR or live readiness is claimed.

## Cleanup Followup

Dataset qualification now also rejects empty tables, invalid identity intervals, nonfinite
signals/prices and missing benchmark marks. Event-study paths validate security and benchmark
observations throughout the holding interval. These are additional software safeguards, not
real-data hypothesis results. The cross-system review is maintained in Portfolio Lab under
`docs/system_assessment_20261125.md`; its verifier runs this repository's isolated environment.

## Portfolio And Operating Implementation

The follow-up adds content-specific fixed policies, a regular-session next-open portfolio engine,
development-only candidate selection, purged chronological validation and lockbox diagnostics,
annual expanding walk-forward replay with actual switch accounting, latency/cost stresses,
regime diagnostics and paired block intervals. Software tests exercise the complete research
path on explicit synthetic fixtures; fixtures cannot configure a real-data running specialist.

The operational interface now includes hash-bound daily observations, frozen-policy continuity
checks, native report audits and a Portfolio Lab comparative export. The common engine also
supports terminal cash, including bankruptcy, so an eventual event specialist will not silently
drop failed companies. Portfolio Lab has a dedicated Event research workspace and an explicit
fourth-specialist comparative admission path.

The new official request in `data/captures/readiness_20261125_implementation` again returned
HTTP 403. No qualified dataset or real-data strategy results were created. The current operating
status remains blocked with zero real-data hypotheses tested. [Operations](operations.md) documents
the input contract, commands and remaining evidence gates. No live-readiness claim is made.

## Earlier Local Verification

- Final event-repository suite: 93 passed; Ruff and whitespace checks passed.
- Evidence: `reports/verification/implementation_release_20261125.xml`.
- Source identity: `83387923d77fedf0342ddbe5801bac89c32c4751b3bf2b571889bc06912a3cf3`.
- Synthetic end-to-end tests exercise six available fixture policies, all three chronological
  partitions, nine execution stresses and stitched expanding walk-forward accounting. These
  are not six real-data strategies or evidence of profitable CAGR.
- The real-data CLI was exercised and returned a structured blocked result for the absent
  qualified dataset. It did not publish fabricated real-data research.
- Portfolio Lab's final integration suite passed 147 tests. Its seven-workspace desktop/mobile
  browser acceptance passed, including the dedicated event view and downloaded readout.

Implementation and integration progressed. Real-data validation, prospective shadow evidence
and allocation readiness remain incomplete.

## Current Follow-Up

The [readiness continuation](readiness_continuation_20261125.md) supersedes those implementation
counts. The latest suites passed 133 native event tests and 158 Portfolio Lab tests. Source access,
real-data hypothesis testing and allocation admission remain blocked, not completed by those tests.
