# Event Research Operating Contract

## Current Gate

The November 25, 2026 implementation includes portfolio research and an operating interface.
The new official-source attempt under `data/captures/readiness_20261125_implementation` returned
HTTP 403. No qualified real historical dataset exists in this checkout. Consequently there are
zero real-data strategy results, no configured active policy and no authorized trading allocation.

The infrastructure being executable is not evidence that its investment hypotheses work.

## Data Inputs

Preserve the existing qualification criteria, minimum ten years, at least one hundred historical
security identities and delisted-security coverage. Never replace the historical census with
current index constituents. Add these hash-bound artifacts to the dataset manifest:

| Artifact | Required Meaning |
|---|---|
| `prices.parquet` | Every actual NYSE regular-session adjusted open; timezone-aware index |
| `close_prices.parquet` | Same rows/securities, adjusted close for each corresponding session |
| `cash_returns.parquet` | `cash_return`, source-reviewed prior-close-to-close cash accrual |
| `terminal_events.parquet` | Permanent ID, timezone-aware `settlement_at`, nonnegative `value_per_adjusted_share`, `source_sha256` |
| `events.parquet` | Permanent ID, CIK, accession, acceptance time, feature `available_at`, raw-content `source_sha256`, applicable feature columns |
| `identity.parquet` | Verified historical identity intervals and known-at times, including delisted securities |

Original raw sources, not only derived tables, must be included in the artifact map. Every event
and settlement source hash must match an actual bound source artifact. Each existing criterion's
review JSON contains its exact `criterion`, `reviewed: true`, a named `reviewer`,
`review_scope: real_sources_not_test_fixtures`, `fixture_only: false` and nonempty `source_artifacts`
referencing bound files. These attestations record a real source review; writing the fields alone
does not establish historical completeness or grant independent approval.

`data_kind` must be `real_historical`. Only tests can use the explicit `synthetic_fixture` path;
that path cannot be configured or admitted by the real-data operating/export interfaces.

## Features And Execution

The policy engine uses actual profitability changes, cash conversion, net repurchases, distinct
identified insider buyers, post-filing returns or verified ownership/event content, as applicable. It cannot
substitute the generic `directional_signal` column for a family's missing features. Registered
policies lacking their required content are reported unavailable, not counted as tested.

Accounting extraction currently emits annual filing events. It does not relabel stale annual
figures as new quarterly accounting information. Post-filing features require a completed price
window before availability. Ownership/8-K scores require content verification; there is no
automatic inference from counts or an unvalidated language-model opinion.

Annual features require new facts from the triggering accession for its declared fiscal period.
Profitability changes compare to the previous fiscal year as known at the filing, not the
previous filing (which could be an amendment of the same year). Identical amendments and old-year
amendments after a newer annual report do not refresh positions. Ratios require matching starts
and ends for both flow measures, not merely matching year ends.

Form 4 P/S codes include private as well as market transactions. The parser does not label code P
as proof of exchange execution. Missing or joint owner attribution, future transaction dates,
and conflicting acquisition/disposition codes fail closed. Zero-dollar and derivative
transactions do not inflate distinct purchase-buyer counts. Joint reports need a separate,
reviewed ownership-allocation implementation before they can enter the cluster evidence.

Targets become known at a session close and fill at the next actual regular-session open. A filing
after the close cannot affect that close's target. Unused slots remain in cash. Positions have a
fixed event life; repeat events refresh one position rather than creating duplicate issuer bets.
Missing held prices fail the replay unless a bound terminal settlement accounts for the shares.
Terminal recovery can be zero; bankruptcy cannot turn into a free sale at the last quoted price.
Cash inputs must represent a source-reviewed, known short-cash accrual, not an unpredictable
bond-fund return. The modeled accrual is split by elapsed overnight/intraday time so cash deployed
at the opening fill does not also earn a full day's cash yield.

## Evaluation

Freeze the registry before computing performance. Use chronological 60/20/20 development,
validation and lockbox partitions with 63-session boundary purges. Only development results
select the candidate. These are retrospective diagnostics, not proof of an untouched or blind
holdout. Reusing a lockbox for later manual tuning invalidates an untouched-holdout claim.

Annual expanding walk-forward selection uses outcomes ending before a 63-session purge. The
stitched target book is replayed with actual switch costs; annual statistics do not splice
independently capitalized portfolios. Report cash and costed SPY, equity exposure, turnover,
1/2/5-session execution delays, 10/25/50bps per-side costs, lagged trend/volatility regimes and a
paired moving-block interval. Regime-conditional daily averages are not regime portfolio CAGR.
The bootstrap does not correct for the full multiple-testing history or demonstrate causal alpha.

An immutable native report must reconcile its selected targets, returns and performance through
`audit-research` before configuration or comparative export.

## Daily Operation

`configure` binds the dataset and audited report by manifest hash. Daily processing uses the
frozen selected policy, never today's best hindsight candidate. New datasets must preserve the
entire frozen price, cash, historical identity and event prefix; revisions block the observation
for review instead of silently changing its history. Missing, stale or synthetic evidence cannot
become a current positioning recommendation.

Portfolio Lab records each event daily capture, including failures, and copies its verified status
into the desk archive. Current event targets and completed research results are withheld from
historical session selections. The specialist does not become a fourth market-wide confirmation
vote merely because it supplies company-level evidence.

Comparative exports preserve explicit terminal cash and distinguish native next-open execution
from the common engine's next-close convention. Portfolio Lab admits only the three core bots
and a qualified event-research bundle; it never substitutes an empty event specialist for cash.

All outputs remain research-only and deny automatic promotion and execution. Prospective shadow
evidence and explicit admission review remain necessary; historical backtests cannot manufacture
that elapsed forward evidence.

## Prospective Journal

A fresh qualified `daily` observation records the frozen close-known target only after the
completed close plus 15 minutes and before the next actual regular-session open. The append-only
cohort under `data/prospective/` binds policy, code and native research identity, with a hash chain
and committed head. Re-running the same observation is idempotent; changing a recorded decision
or backfilling an expired forecast window is rejected. New code or policy starts a separate cohort.

The status reports total on-time observations, the current consecutive-session streak and missed
exchange sessions. A 60-session minimum is an administrative evidence-review threshold, not a
statistical power calculation, profitability test or automatic promotion. It is fixed before any
real-data forward observations. This machine currently has none.

Outcome marking replays only pre-recorded decisions against subsequently completed prices,
including next-open costs and terminal settlements. Missing execution decisions suppress the
performance claim. Short histories show total return and drawdown, not an annualized CAGR headline.
This is modeled shadow performance, not actual broker execution. Local clocks and local files are
not a trusted timestamp authority; independent archival/operational review remains necessary.
