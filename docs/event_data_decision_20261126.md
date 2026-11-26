# Historical Event Data: Procurement Decision

Checked November 26, 2026. Personal research only. No subscription purchased, account
created, private API key accessed, or trading allocation changed in this work.

## Decision

Evaluate Sharadar's direct personal-use Full History Bundle first. It is a candidate,
not a qualified dataset. Its current published price is **USD 69/month or USD 499/year**.
The Prices-only Full History plan is **USD 39/month or USD 299/year** if we only need
prices, reference data, corporate actions and historical S&P 500 membership.
The cheaper USD 29/month Bundle has only five years of history and is not the right
product for the full research objective. [Official plans](https://sharadar.com/subscribe).

The bundle is the more useful candidate for this project because it also supplies
as-reported financials, insider transactions and material corporate events. It does
not remove the need to validate event semantics, historical identity joins, failed-firm
paths, original publication dates and financial-news rights. API access is not evidence
of investment value. [API documentation](https://sharadar.com/docs/intro).

## Alternatives

| Candidate | Published Cost/Availability | Relevant Coverage | Practical Limitation |
|---|---|---|---|
| Sharadar direct, Full History Bundle | USD 69/month or 499/year | Stock/fund prices, company financials, reference/actions and investor/event tables | Vendor assertions still need independent checks; personal-use licensing and data-retention restrictions |
| Sharadar direct, Full History Prices | USD 39/month or 299/year | Prices, actions/reference and historical S&P 500 membership | No financial/insider/event table entitlement |
| Norgate US Platinum | USD 346.50/6 months or 630/year | Active and selected delisted securities, historical index membership, history back to 1990 | Updater requires Windows; no independently verified original filing/news event archive |
| Varve | New purchases paused at inspection | SEC-derived first-report/restatement versions, identity history, filing events and corporate actions; free sample available | Not currently purchasable; no qualified daily price/terminal-return panel established |

Norgate's updater is Windows-only, though its FAQ permits exporting data for personal
analysis on other systems during an active subscription. It is a credible alternative
if we can support a Windows acquisition machine. Not every security type is covered
in its delisted database. [Plans](https://norgatedata.com/stockmarketpackages.php),
[platform FAQ](https://norgatedata.com/ndu-faq.php),
[coverage](https://norgatedata.com/data-content-tables.php).

Varve is a potential supplementary identity/fundamentals source, not a current remedy
for the price gap. Its public pricing page says new purchases are paused; its free
sample is not a broad historical event census.
[Data documentation](https://varvedata.com/data), [availability](https://varvedata.com/pricing).

## What Was Actually Tested

Sharadar's documented public test key returned both requested tables for every member
of a fixed ten-company roster: AAPL, MSFT, AMGN, CAT, KO, WMT, DIS, PG, UNH and JPM.
Twenty CSV downloads were retained with hashes and acquisition receipts. No credential
or account information was sent. This was the publisher's free current-Dow sample,
not a delisted-security or historical-membership evaluation.

The sample supplied 200 trailing-year as-reported financial observations and 1,254
daily price sessions per company from November 29, 2021 through November 25, 2026.
The pilot required every actual NYSE session for every frozen roster member, without
forward-filling or silently removing failed requests.

Fully adjusted opens were derived as `open * closeadj / close`. Filing-date observations
were not converted into fictitious SEC acceptance timestamps. The separate pilot waits
until the end of the filing date plus one full calendar day of assumed vendor processing,
then applies fixed next-open session delays. This remains a conservative modeling
assumption, not verified historical vendor availability.
[Sample API](https://sharadar.com/docs/getting-started),
[adjustment and as-reported definitions](https://sharadar.com/docs/faqs).

## Admission Checklist Before Broad Research

1. Confirm a personal research license and an explicitly approved spending limit. Do not
   infer purchase authorization from approval to investigate.
2. Acquire full-history reference, actions, stocks and funds under the correct entitlement.
   Add financials and investor/event tables if the Bundle is selected. Keep raw vendor
   data in ignored local storage, never a public GitHub repository or external narration pack.
3. Audit stable security IDs against dated ticker/CIK histories. Current ticker labels are
   not historical identities, and one company can have multiple securities or CIKs.
4. Reconcile a deliberately adverse set of bankruptcies, cash and stock acquisitions,
   exchange-to-OTC transitions, reused symbols, spin-offs, splits and prolonged suspensions.
   Establish final cash/share consideration, timing, non-tradeable intervals and unresolved
   contingent claims. Never use the last quoted price as a universal liquidation value.
5. Independently check adjusted OHLC paths, cash distributions, price gaps and tradeability.
   Do not let later-known terminal outcomes choose the historical event universe.
6. Review first-report versions and publication dates against original disclosures.
   Implement and return-blind validate each directional extractor before performance review.
7. Make any broad-gate transition from `official_public_free_sources` to licensed research
   inputs explicit, evidence-bound and regression-tested. This pilot did **not** change
   that legacy criterion or silently permit paid inputs through it.
8. Run the frozen chronological portfolio protocol with cash, SPY/matched controls,
   costs, delays, failure settlements and the actual unchanged top-strategy controls.
   Keep the already-inspected history distinct from genuinely prospective evidence.

Sharadar documents acquisition cash/share consideration but excludes contingent value
rights. Its estimated coverage is a vendor claim, not proof that all terminal paths are
complete. [Corporate actions](https://sharadar.com/docs/actions),
[consideration limitations](https://sharadar.com/docs/faqs).

## Licensing And Reproducibility

The personal terms restrict redistribution and require deletion of raw/copyable service
data within 30 days after termination. Non-reconstructive research outputs may be kept.
A one-month purchase must therefore not be presented as an indefinite right to retain
the historical archive. Keep raw data out of git and maintain a license/retention register
before subscribing. Provider evaluation notes remain private local research.
[Personal terms](https://sharadar.com/terms).

## Research Status

The earlier blanket "blocked" framing needs qualification: small exploratory studies
and extractor development can proceed. Broad survivorship-aware investment validation
still needs the data and implementation above. A vendor subscription alone will not
complete the ten-family research goal, and the sample results do not authorize trading.

See [sample findings](event_sample_findings_20261126.md) for the actual return pilot and
the control-method sensitivity that prevented a false performance claim.
