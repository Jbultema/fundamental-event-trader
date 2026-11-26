# Event Research: Academic Corpus And Market-Data Follow-Up

Decision date: November 25, 2026 (America/Denver). Receipts use November 26 UTC.

## Result

The first pass's broad source-access blocker was partly resolved. An independently published
filing corpus and the existing authorized market-data integration supply real historical inputs.
There is still no qualified company-event portfolio backtest and no new investment-performance
finding. The original ten-family objective is not complete, nor are its economic ideas exhausted.

## Independently Published Corpora

The TeraflopAI/SEC-EDGAR dataset publisher declares Apache-2.0, supplies raw filing-document
content and parsed text, and distributes original accessions and filing-date metadata. The pilot
pins dataset revision `43de32c4c3cd4a56c26757345a4ec6db04fccda0` and verifies all three source
shards against their publisher LFS hashes and byte lengths. It does not retry SEC requests,
rotate identity, proxy a denied SEC URL or use account credentials to retrieve this corpus.

Source: https://huggingface.co/datasets/TeraflopAI/SEC-EDGAR

The public rows endpoint failed because its own Parquet scan exceeded a service limit. The
documented cached first-rows endpoint was accessible, but all ten preview rows truncated
important content/metadata fields. Those previews were not parsed as complete original filings.
Instead, three complete, small shards (about 89 MB total) were acquired from the publisher's
revision-pinned distribution through its normal public hosting redirects.

This is a content-feasibility sample, not a random or comprehensive investment universe. Shard
selection used file numbering and size, never future investment returns. Numbered shards are
not chronological: first/last numbered shards must not be described as earliest/latest filings.

| Source | Source Rows | Parsed Or Indexed | Rejected |
|---|---:|---:|---:|
| Form 4 shard 0 | 24,570 | 23,741 | 829 |
| Form 4 shard 75 | 43,298 | 42,433 | 865 |
| One 8-K shard | 2,804 | 2,792 | 12 |
| Total | 70,672 | 68,966 | 1,706 |

The parsed/indexed sample has 68,966 distinct accessions and 2,357 issuer CIKs, with filing dates
from May 1996 to July 2025. A range spanning decades is not evidence of continuous coverage.

The existing XML extractor identified 43,042 non-derivative purchase/sale transaction rows:
7,475 purchase rows and 35,567 sale rows, including 7,413 positive-dollar purchases. Code P means
open-market OR private purchase; these are not all verified discretionary open-market buys.
The 8-K rows were indexed, not labeled as verified directional business events.

Most exclusions are ambiguous joint reporting owners (1,158) or invalid/unresolved transaction
amounts (436). Direction conflicts, future transaction dates, malformed content and ambiguous
documents also remain explicit rejections. None was silently repaired to increase coverage.

Critically, these shards lack exact acceptance timestamps. The importer uses an explicitly
named date-only convention only for content chronology checks; it exports no `accepted_at`,
`available_at` or `directional_signal`. No incomplete-sample insider clusters were constructed.
Source counts, parsed rows and XML transactions are not strategy tests.

EDGAR-CORPUS was also accessible, with full text in a ten-row sample, but its explicit schema
contains CIK, report year and sections rather than an actual publication timestamp. It remains
an NLP/extraction resource, not a qualified event-timing dataset in this program.

FNSPID's dataset card states CC BY-NC-4.0 and prohibits commercial use. Its authors' GitHub
README additionally includes a July 2025 rights-release note while retaining restrictive
commercial-use text elsewhere. No assumption resolving that conflict was made, and no bulk
news/price archive was downloaded or treated as an approved trading dataset.

Sources: https://huggingface.co/datasets/c3po-ai/edgar-corpus,
https://huggingface.co/datasets/Zihan1004/FNSPID,
https://github.com/Zdong104/FNSPID_Financial_News_Dataset

## Historical Market-Data Checks

The configured Alpha Vantage integration successfully retrieved:

| Request | Rows | Qualification Limit |
|---|---:|---|
| Active listings as of December 1, 2011 | 6,023 | 35 duplicate-symbol rows; no permanent-security/CIK mapping |
| Active listings as of August 3, 2023 | 10,603 | 57 duplicate-symbol rows; no permanent-security/CIK mapping |
| Delisted listings as of November 25, 2026 | 9,651 | Listing metadata, not terminal payouts or complete daily return paths |

These four capability/listing requests used the existing free-tier quota reservation mechanism,
retained no API key, purchased nothing and sent no account holdings or balances.

The fourth request, daily adjusted prices for a fixed delisted-company diagnostic (ATVI),
returned HTTP 200 with an Information payload indicating premium-only access. An HTTP success
was not treated as usable prices. No purchase, entitlement workaround or endpoint retry followed.

The historical listing snapshots contain no future IPO or delisting dates in their date fields.
This does not establish that company names, classifications or the whole universe are point-in-time
correct. Exact-symbol matching against the provider's current delisted-history intervals leaves
20 and 8 unmatched symbols for the two dates. Symbol changes and reuse mean these are identity
reconciliation queues, not proof of that many missing companies. No future delisting information
was used to choose a strategy's historical holdings.

Provider documentation: https://www.alphavantage.co/documentation/#listing-status

## Remaining Gates

1. Qualify full content-family coverage and historical release availability. The pilot does not
   certify the entire corpus or each original document against an independent source.
2. Reconcile historical issuer/security identities, duplicate symbols, listing intervals, share
   classes and then-known investability. An issuer CIK or ticker is not a permanent share identifier.
3. Obtain legitimately accessible, independently reviewed adjusted daily opens/closes and
   explicit terminal settlements, including failures. Current snapshots and last observed quotes
   are not substitutes. Existing free-tier adjusted-daily access did not provide the test data.
4. Only then execute event studies, self-financing portfolios, simultaneous execution/cost
   stresses, temporal transport, combinations and native top-strategy integration.

There is no new CAGR, drawdown, event-return, alpha or live-position recommendation to report.
This turn advanced acquisition and content extraction, not investment-performance validation.

## Evidence And Verification

- Raw/public sources and metadata: `data/academic_filing_pilot_20261125/`.
- Final content pilot: `reports/academic_filing_content_pilot_20261125/`.
- Source hashes and report artifacts were verified; each rejection retains accession/source row.
- The full local suite passed 230 tests; no skipped tests. Software verification only:
  `reports/verification/academic_filing_pilot_20261125.xml`.
- No existing Trade Bot, Swing Trader or Portfolio Lab investment policy was changed. The only
  Swing Trader state write was four reservations in its market-data quota ledger.

```sh
.venv/bin/python -m fundamental_event_trader.academic_filing_audit \
  --sources data/academic_filing_pilot_20261125 \
  --output reports/academic_filing_content_pilot_new_run
```

The output must not already exist. Replays and source/report audits do not add research trials.
