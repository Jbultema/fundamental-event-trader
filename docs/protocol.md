# Data Qualification And Research Protocol

## Historical dataset

A candidate dataset contains hash-bound `events.parquet`, `identity.parquet`, `prices.parquet`,
and evidence artifacts for every criterion in `qualification.CRITERIA`.

- Events: permanent security id, issuer CIK, timezone-aware official acceptance time, content-derived
  directional signal. Neither filing date nor reporting-period end is a publication timestamp.
- Identity: security id, CIK, known-at timestamp, valid-from/until intervals, delisted flag and
  explicit terminal-treatment verification. Current ticker mappings cannot rewrite past identity.
- Prices: actual regular-session adjusted opens, timezone-aware, with SPY and every held security.
  Missing terminal paths fail rather than receiving a free cash exit.
- Evidence: official free-source provenance, historical membership including dead securities,
  acceptance coverage, original fact vintages and independent price-quality review. Each criterion
  needs a bound evidence artifact, not merely a passed boolean.

At least ten years and one hundred historical identities, including delisted securities, are
required before broad event studies. This threshold is a minimum feasibility gate, not proof of
statistical adequacy. A human still needs to review the underlying membership census and evidence.

## Hypotheses

Registered candidates cover profitability change, cash conversion, repurchases/issuance,
distinct-owner insider clusters, post-filing drift, ownership change and 8-K events; combinations
join profitability/cash, repurchases/profitability and insider/filing evidence. No strategy is
created from a generic positive filing count. Content-dependent families remain unimplemented
until exact source semantics have been validated.

The current accounting extractor uses annual same-duration statements and same-period asset
denominators. It refuses to mix annual, quarterly and year-to-date cash-flow periods. Quarterly
de-cumulation is future work requiring same-vintage, matched-period verification.

## Evaluation

Every fill follows the exact public acceptance time at the next observed regular-session open.
Test several holding periods and 20/50/100 basis-point round trips. Unknown or unmatured outcomes
are omitted with coverage reporting, not labeled zero. Compare matching dates with costed SPY,
within-industry controls once point-in-time classifications exist, and no-event matched samples.

Event-study observations overlap and cluster by issuer and date. Their arithmetic averages are
not a tradable portfolio CAGR. Clustered uncertainty, economic portfolio construction and a
survivor-free universe must precede an alpha claim or Portfolio Lab admission. Once a qualified
portfolio strategy exists it must export the common specialist contract; no empty/fake expert is
exported now. There is no broker connector or automatic promotion path.

## Isolation

Only personal repository identities and public/free source contracts are used. No employer
code, credentials, datasets or runtime dependencies are imported.
