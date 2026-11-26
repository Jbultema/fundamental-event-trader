# Fundamental Event Trader

News investment-performance results and limits: [November 25 findings](docs/news_performance_findings_20261125.md).
The public-news reader remains an observation lane; ETF news-proxy screens are not validated
article-level stock strategies or permission to allocate.

Independent personal research into information that price-only momentum systems do not directly
observe. Long-only ordinary securities and cash, human execution only, no broker connection.

## Distinct mandate

This project owns original SEC filing vintages, fundamental changes, content-verified events and
public financial-news observations. It does not own general price momentum, sector rotation or
total-portfolio risk budgets. Current news is separate from historical strategy admission.
Portfolio Lab owns cross-specialist evaluation. Existing Swing Trader SEC metadata is consumed
through a hash-verified sidecar import, not a duplicate candidate-collection workflow.

## Current capability and limits

- Official SEC submissions/Company Facts access probe with immutable raw bytes and hashes.
- Public financial-publisher feeds and accessible article-body reading, with robots/paywall
  boundaries, first-seen/version timestamps, source archives and explicit partial coverage.
- Acceptance-time filtering; unknown publication times are omitted, never inferred from period ends.
- As-of fact vintages and explicit first-reported versus latest-known amendment policies.
- Same-duration annual accounting features; missing or mismatched periods remain unavailable.
- Non-derivative Form 4 purchase/sale parser and distinct-owner purchase clusters.
- Strict historical identity, survivor/delisting, price and source-evidence gates.
- Matched next-open event studies, kept separate from portfolio CAGR calculations.
- Content-specific fixed-specification policies; missing content is unavailable, not a bullish filing-count proxy.
- A self-financing portfolio engine with next-open fills, drifting holdings, funded transaction costs,
  overnight gaps and explicit zero/nonzero terminal cash for delisted holdings.
- Development selection, purged chronological validation/lockbox diagnostics, annual expanding
  walk-forward selection, lag/cost stress tests, regime diagnostics and paired block intervals.
- Frozen-policy daily captures and a common Portfolio Lab export with explicit terminal cash.
- A pre-execution, hash-chained prospective journal; missing sessions break the streak and
  historical backfills cannot count as forward evidence. Recorded decisions are marked only
  against subsequently completed prices, with short-run annualization withheld.
- A 48-hypothesis registry across seven families and three combinations, explicitly not 48 tested strategies.

13D/13G stake-change and 8-K directional hypotheses remain disabled until their underlying content
is parsed and verified. Filing counts alone cannot establish either. A successful one-company SEC
capture is not a survivor-free stock dataset and cannot unlock allocation. No real-data alpha or
portfolio performance is claimed until those gates pass.

The normalizer admits only accessions with verified acceptance timestamps in hash-bound recent
or older submission payloads. The offline bulk importer binds declared archived submission files;
unknown acceptances remain omitted. A current Company Facts download is not by itself proof of
preserved original filing vintages.

## Run

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/fundamental-event-trader capture --cik 320193 --output data/captures/RUN
.venv/bin/fundamental-event-trader normalize --capture data/captures/RUN --output data/normalized/RUN
.venv/bin/fundamental-event-trader registry --output reports/registry.json
.venv/bin/fundamental-event-trader qualify --output reports/qualification.json
.venv/bin/python -m pytest -q
```

Collect current public financial news, independently of the SEC historical-data gate:

```sh
.venv/bin/fundamental-event-trader news-refresh --max-articles 16
.venv/bin/fundamental-event-trader daily --refresh-news --output reports/daily/NEW_NEWS_CAPTURE
```

The daily command can exit 2 because historical strategies remain blocked while still producing
a valid, useful news observation. Portfolio Lab's **News & events** workspace and downloaded daily
readout show that lane separately. News refresh is due hourly; missing feeds do not become market
signals. [News sourcing and validation](docs/news_sources_20261125.md) describes the boundaries.

`capture` and `qualify` exit 2 on blocked gates while preserving diagnostic evidence. Official
access controls are never worked around with mirrors or repeated identity changes. Missing
historical prices, identity and delisted coverage are not replaced with today's successful names.

```sh
.venv/bin/fundamental-event-trader import-swing-sidecar --manifest PATH --output data/imported/RUN
.venv/bin/fundamental-event-trader qualify --dataset data/qualified/DATASET
.venv/bin/fundamental-event-trader research --dataset data/qualified/DATASET --output reports/RUN
```

See [qualification and research protocol](docs/protocol.md). The official
[SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
and [developer fair-access guidance](https://www.sec.gov/about/developer-resources) govern acquisition.

## Portfolio Research And Integration

```sh
export SEC_USER_AGENT='Your research application your-contact@example.com'
.venv/bin/fundamental-event-trader capture --cik 320193 --output data/captures/NEW_CAPTURE
.venv/bin/fundamental-event-trader import-sec-bulk --submissions PATH/submissions.zip --companyfacts PATH/companyfacts.zip --cik 320193 --captured-at ACTUAL_UTC_CAPTURE_TIMESTAMP --output data/captures/NEW_IMPORT
.venv/bin/fundamental-event-trader portfolio-research --dataset data/qualified/DATASET --output reports/NEW_RESEARCH
.venv/bin/fundamental-event-trader audit-research --report reports/NEW_RESEARCH
.venv/bin/fundamental-event-trader configure --dataset data/qualified/DATASET --report reports/NEW_RESEARCH
.venv/bin/fundamental-event-trader daily --output reports/daily/NEW_CAPTURE
.venv/bin/python -m fundamental_event_trader.portfolio_export --output reports/NEW_BUNDLE
```

Use an actual declared research contact; do not impersonate a browser or rotate identities around
access restrictions. Bulk import accepts legitimately obtained official archives offline; it does
not download around a blocked endpoint.

`portfolio-research` requires additionally bound `close_prices.parquet`, `cash_returns.parquet`
and `terminal_events.parquet`, content-derived feature availability, raw source hashes and a real-source
review artifact for every qualification criterion. Synthetic fixtures cannot configure a running
specialist or produce a real-data research export. See [the operational contract](docs/operations.md).

Portfolio Lab captures a hash-bound daily status and exposes a dedicated **Event research** view.
With a configured, qualified dataset and audited native report, its research export joins the
common-engine comparison as a fourth research specialist. Native next-open and common next-close
performance remain separate. Neither integration authorizes automatic trading or promotion.

The [November 25 readiness continuation](docs/readiness_continuation_20261125.md) records the
latest access checks, correctness fixes, local verification and unresolved real-data gates.
