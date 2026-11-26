# Ten-Family Research: First Execution Pass

Date: November 25, 2026, America/Denver. The source receipt timestamps are November 26 UTC.

## Decision

Final goal-state update: [blocked audit](event_program_blocked_20261125.md). The investment
research remains incomplete; missing qualified data is not evidence of no economic benefit.

Continuation update: the [academic corpus follow-up](event_program_academic_followup_20261125.md)
partly resolves historical filing and listing access. The initial six-request results below
remain accurate records, but are not the complete current source inventory. Daily price,
terminal settlement, historical identity and full-family qualification gates remain unmet.

The ten-family goal is not achieved. Data-feasibility checks were executed; no new
company-event investment-performance tests could legitimately run. The hypotheses are
blocked or unresolved, not rejected. Research opportunities have not been exhausted.

The existing 132 news-index policy variants are a separate experiment. They are not
evidence that company-specific guidance, financing or article-reading policies were tested.
The new registry contains thirty formulation specifications, not thirty implemented or
backtested strategies. Family-specific extraction and execution remain work after data access.

## New Evidence

Six bounded unauthenticated public-source requests, each with raw bytes and a SHA-256 receipt:

| Source | Observed Result | Consequence |
|---|---|---|
| SEC issuer submissions | HTTP 403, undeclared automated tool response | No original filing acceptance/content acquisition |
| SEC financial-statement quarterly archive | HTTP 403, rate-threshold response | No historical financial-statement acquisition |
| FDA drug enforcement API | HTTP 200, 100-record earliest-report sample | Source can be investigated, but not yet historically version-qualified |
| CourtListener search | HTTP 401 | Authorized access is required before acquisition |
| Guardian access terms | HTTP 200 | Documentation only; not a licensed article archive or evidence of permission for this use |
| Nasdaq listing directory | HTTP 200, 5,609 rows | Current membership only, not a survivor-free historical census |

No denied request was retried with another identity, no access-controlled content was obtained
through a proxy/mirror, and no account balances, personal holdings or credentials were transmitted.
The SEC response titles describe the returned pages; they do not establish the underlying
network cause or prove that changing a user-agent string would fix access.

The FDA sample covers report dates June 20-August 22, 2012. It is a deterministic earliest-date
sample, not representative of all years or all FDA datasets. Its API metadata reports 18,194
records in the queried dataset and a November 18, 2026 update date.

- 100 product rows share 64 distinct event IDs, across 49 recalling firms. Repeated IDs cannot
  be counted as independent event evidence. Correct announcement grouping still needs review.
- All 100 recall initiation dates precede the report date. Initiation is not proof of when
  the public could act on the information.
- 99 termination dates are later than the report date. Those future dates and eventual recall
  duration cannot be used as onset-time features.
- There are no explicit ticker, CIK, permanent-security, first-publication-version or historical
  observation-version fields in the sampled records.
- FDA documents that past reports can be corrected. The present API response is not evidence
  of what the original historical report contained. The source also cautions against treating
  the API as a recall lifecycle tracker.

FDA documentation: https://open.fda.gov/apis/drug/enforcement/
Guardian access terms: https://open-platform.theguardian.com/access/

## Per-Family Disposition

All ten families additionally lack a qualified historical stock census, historical identity
mapping, independently reviewed adjusted open/close prices and failed-security terminal treatment.
A read-only search of the four trading projects' data trees found no `events.parquet`,
`identity.parquet` or `terminal_events.parquet` dataset tables satisfying the existing contract.
Current stock snapshots and ETF price panels cannot silently stand in for these tables.

| Family | Additional Missing Evidence | Performance Conclusion |
|---|---|---|
| Guidance changes | Original releases, metric-matched prior guidance, validated extractor | Untested |
| Cash conversion | Original financials with matched accounting durations and historical classifications | Untested |
| Financing stress | Original funding events and then-known liquidity, including failed issuers | Untested |
| Insider clusters | Original ownership/transaction details and public availability; not transaction dates alone | Untested |
| Executed capital returns | Original authorization/execution/issuance/funding disclosures | Untested |
| Customer propagation | Historically known customer-supplier edges and dated customer events | Untested |
| Operational disruptions | Original disruption and resolution versions, public-parent mapping | Untested; FDA structure pilot only |
| Governance/accounting | Original contextual disclosures and validated content labels | Untested |
| Regulatory/legal | Authorized original decisions, then-public prior circumstances and release times | Untested |
| Original reporting | Permitted versioned article archive, original/syndicated attribution and entity mapping | Untested |

## What Was Implemented And Checked

- A frozen common research protocol and ten-family, thirty-formulation specification registry.
- A reproducible source audit and per-family decision table, with unavailable benefit estimates
  stored as null rather than fabricated zero returns or negative findings.
- Reconstruction of FDA and listing diagnostics from preserved source bytes.
- Adversarial tests reject altered bytes, path escapes, false strategy counts, fake benefit
  estimates, rehashed false source diagnostics and removal of simultaneous execution/cost stress.
- The source-audit tool cannot promote a policy, authorize allocation, run the unrelated legacy
  48-policy engine as a substitute, or claim a registered specification is an investment test.

Software checks validate these controls; they do not demonstrate investment performance.

## Resume Conditions

1. Obtain the needed original public-source archives through legitimate authorized access or a
   supplied local archive. CourtListener credentials or a news key alone do not resolve pricing,
   survivorship, historical-version or use-permission requirements.
2. Independently qualify the historical issuer/security census, original versions, publication
   times, adjusted opens/closes, cash returns and explicit terminal settlements.
3. Validate family-specific extraction, then run event studies, executable portfolios and the
   frozen cost/delay/transport tests. Only tested survivors justify follow-up or combinations.
4. Integrate survivors natively into unchanged top Trade Bot controls, then conduct prospective
   review. Existing historical periods are diagnostic, not a newly untouched lockbox.

The bottleneck is obtaining qualified inputs, not a need for another parameter search. It would
be misleading to close the goal as completed, say there is no benefit, or count these access
checks as execution of the ten investment hypotheses.

## Reproduction

```sh
.venv/bin/python -m fundamental_event_trader.event_program_audit audit \
  --receipts /path/to/preserved/source_receipts \
  --protocol docs/event_program_protocol_20261125.md \
  --output reports/event_program_new_audit
.venv/bin/python -m fundamental_event_trader.event_program_audit verify \
  --report reports/event_program_new_audit
```

The output must not already exist. A source audit does not download, request credentials or
run a strategy. Raw source receipts, rather than this narrative alone, support the findings.
