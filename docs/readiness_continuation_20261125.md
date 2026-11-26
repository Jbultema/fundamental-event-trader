# Event Research Readiness: Continuation

## Acquisition Finding

On November 25 the follow-up checked three separately documented official SEC downloads using
the application's declared research identity. Each returned HTTP 403, HTML rather than ZIP bytes:

- `https://www.sec.gov/files/dera/data/financial-statement-data-sets/2026q3.zip`
- `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`
- `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip`

This was an access feasibility check, not a successful acquisition or qualification. The latest
byte-preserved API failure remains under `data/captures/readiness_20261125_implementation`.
No identity rotation, unofficial mirror, restricted-access workaround or synthetic investment
dataset was substituted. No `SEC_USER_AGENT` override was configured in the process or relevant
repo `.env` files at this inspection. Its absence does not establish the cause of HTTP 403, and
adding a contact does not guarantee access.

The SEC API documentation names the official bulk interfaces:
[SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
The separately published quarterly dataset covers as-filed statement information:
[SEC Financial Statement Data Sets](https://www.sec.gov/dera/data/financial-statement-data-sets.html).
Neither interface, even if downloadable, supplies verified historical security identities and
complete adjusted prices with terminal treatment for delisted companies.

## Correctness Changes

- Configuration now recomputes the native audit rather than only checking report hashes.
- The native audit reconciles saved fills and realized holdings as well as returns and metrics.
- A signal without an observed portfolio buy is reported as unexecuted, not a tested strategy.
- Annual amendments cannot recycle old content as a new annual signal. Fiscal-year comparisons
  and accounting-period starts/ends are explicit.
- Form 4 ownership attribution and purchase counts reject ambiguous/missing owners, future
  transactions and zero-dollar/derivative buyer inflation. Code P includes private purchases;
  see the [SEC Form 4 instructions](https://www.sec.gov/files/form4.pdf).
- Recent-event reporting uses a trailing 30-calendar-day window, not the final 20 records from
  the entire database.
- A pre-execution prospective journal separates genuine forward observations from backfills,
  reports gaps and never converts observation counts into alpha or allocation permission.
- Portfolio Lab validates the event context during whole-archive auditing, not only when the
  Event research workspace is opened.
- Both daily reports and the dashboard expose the actual content-family and prospective evidence.

## Still Not Ready For Allocation

1. Obtain legitimate official filing data. Download access is currently blocked.
2. Assemble and independently review the historical security census, original filing evidence,
   adjusted opens/closes, cash returns and explicit delisted settlements. None is qualified here.
3. Run the registered research against that real dataset, audit it, and evaluate development,
   chronological validation, lockbox diagnostics, execution stresses and incremental contribution.
4. Record genuine subsequent prospective observations. Neither the 40-session desk reconstruction
   nor synthetic unit tests count toward this history.
5. Complete explicit admission review before enabling any portfolio allocation. A 60-session
   review minimum alone is not sufficient.

Ownership-change and 8-K directional content parsers remain unimplemented; those hypotheses
must stay unavailable rather than borrowing another family's signals. A subset of supported
families can be researched once its own data is qualified, without pretending the full registry
was executed. At this point 48 variants are registered and zero have been tested on qualified
real historical data. No investment-performance improvement is claimed.

## Local Verification

- Native event suite: 133 passed. Evidence:
  `reports/verification/event_readiness_final_v2_20261125.xml`.
- Portfolio Lab suite: 158 passed. Evidence in that repo:
  `reports/verification/event_readiness_final_20261125.xml`.
- Native source identity:
  `a877f6512f346a065c7c50288dcf19a0b53c0250976e690694858dccd4824bca`.
- Both repositories passed Ruff. Adversarial cases altered saved returns, fills, holdings and
  metrics; exercised late/backfilled/future-dated shadow entries and chain/head corruption; and
  checked stale annual amendments and invalid insider evidence. These are software tests.
- Final daily desk archive: Portfolio Lab `reports/market_desk_event_readiness_final_20261125`,
  October 1 through November 25, forty completed trading sessions.
- Desk manifest SHA256:
  `b66e9ba3e96eaf36fa0b56f8f0ef86b276ee3e6dab67c7d4b7f02c6dffae0960`.
- Its market timeline and outcome table exactly match the preceding published archive. The
  event specialist remains an inactive, explicit research context, not another market vote.
- The existing common portfolio control still passes its research-integrity audit. Financial
  policy code was not modified in this continuation.
- No remote CI, live trading authorization or successful real-data event backtest is claimed.
