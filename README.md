# Fundamental Event Trader

Independent personal research into information that price-only momentum systems do not directly
observe. Long-only ordinary securities and cash, human execution only, no broker connection.

## Distinct mandate

This project owns original SEC filing vintages, fundamental changes and content-verified events.
It does not own general price momentum, sector rotation or total-portfolio risk budgets.
Portfolio Lab owns cross-specialist evaluation. Existing Swing Trader SEC metadata is consumed
through a hash-verified sidecar import, not a duplicate candidate-collection workflow.

## Current capability and limits

- Official SEC submissions/Company Facts access probe with immutable raw bytes and hashes.
- Acceptance-time filtering; unknown publication times are omitted, never inferred from period ends.
- As-of fact vintages and explicit first-reported versus latest-known amendment policies.
- Same-duration annual accounting features; missing or mismatched periods remain unavailable.
- Non-derivative Form 4 purchase/sale parser and distinct-owner purchase clusters.
- Strict historical identity, survivor/delisting, price and source-evidence gates.
- Matched next-open event studies at several horizons/costs; these are NOT portfolio CAGR backtests.
- A 48-hypothesis registry across seven families and three combinations, explicitly not 48 tested strategies.

13D/13G stake-change and 8-K directional hypotheses remain disabled until their underlying content
is parsed and verified. Filing counts alone cannot establish either. A successful one-company SEC
capture is not a survivor-free stock dataset and cannot unlock allocation. No real-data alpha or
portfolio performance is claimed until those gates pass.

The current Company Facts normalizer admits only accessions with verified acceptance timestamps
in the captured recent-submission payload. Older archived submissions must be acquired and bound
before their facts can enter historical research. Nothing silently uses current restatements.

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
