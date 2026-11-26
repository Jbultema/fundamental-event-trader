# News Performance Validation

## What Is Being Tested

The RSS/article reader is an observation system, not yet an investment strategy. Successful
collection and dashboard tests are not investment-performance evidence. These experiments ask
the narrower initial question: do public newspaper-derived signals improve ETF timing and
defensive allocation relative to buy-and-hold and price-only rules?

The experiments do not qualify individual-company filings, earnings, guidance, financing
events, takeover announcements or the new article reader. They do not admit an event specialist
into live Portfolio Lab allocations. Existing SEC/security-universe qualification remains intact.

## Frozen Screens

### Current Historical Vintages

- 68 fixed policies: sentiment level, changes and shocks; uncertainty changes and shocks;
  price/news confirmation and repair; combined evidence; four sector-rotation variants.
- Separate SPY/QQQ risk budgets; hard versus partial defense; investable SHY defense.
- Six predeclared scenarios: 14/28-calendar-day assumed publication delays, 1/2/5-session
  execution delays, and 10/25 basis-point costs per side of traded notional.
- Source history: SF Fed Daily News Sentiment chart CSV and authors' US daily policy uncertainty.
  The SF Fed publishes weekly; its public index dates from April 2020. Earlier history is backcast.
- Fixed development 2006-2014, validation 2015-2021, diagnostic holdout 2022 onward; 63-session
  purge at validation/test starts. No selection uses validation/test returns.
- Today's historical values are not demonstrated point-in-time. These results remain exploratory.

### Historical Released Vintages

- 40 fixed policies using official monthly ALFRED vintages of `USEPUINDXD`, April 2014 onward.
  A complete 151-vintage census is required; failed requests cannot silently disappear.
- Vintage date plus two calendar days defines the earliest decision; orders fill a later close.
  The archived column must identify the requested vintage and cannot contain future observations.
- Rules cover uncertainty level, standardized shocks, improving uncertainty, contrarian use,
  price confirmation/repair, and staged budgets. Thresholds are fixed before evaluating returns.
- Development May 2014-2018, validation 2019-2021, diagnostic holdout 2022 onward, with the same
  purge. There are also monthly-clock price controls and a latest-vintage matched-clock check.
- Primary inputs, features and targets are reconstructed from raw historical release bytes by
  a separate audit. This validates the release-based research, not an article-level strategy.
- A bounded transport-failure recovery may reuse verified response hashes. Denied-access
  responses cannot be retried automatically, and a sealed study cannot be overwritten.
- Before this study's returns were computed, the source census identified stale observations
  in the February 2022 and March 2025 vintages (last observations February 18 and March 21).
  A recorded amendment preserves both releases but issues no new target in those months.
  All 151 releases remain in the census; 149 are fresh. The original registry and acquisition
  attempts are retained. No rule threshold, selection criterion or partition was changed.
  New freezes now declare that no-update stale-source behavior before acquisition.

## Accounting And Reporting

### Source-Maturity Follow-Up

The release audit found material revisions to the newest observations. A third fixed study
therefore tests seven-/fourteen-calendar-day matured observations and a trailing seven-day
average, always calculated within the historical release. Four existing rules, two risk assets
and a fixed 50% defensive floor give 24 policy variants. It uses the same development selection,
validation/test periods, costs, execution delays and current-vintage comparison. This is a
source-quality follow-up, not an independent discovery or a newly untouched holdout. Its 64
released-vintage variants are also assessed jointly across the second and third studies.

The final transport check takes the unchanged development-selected maturity rule into RSP,
IWM, EFA, EEM, XLV, XLP and XLE. There is no per-asset threshold fitting or winner reselection.
Those are correlated cross-market diagnostics, not seven independent replications.

Native Event Trader owns data preparation and policy targets; Portfolio Lab owns common-clock
performance evaluation through its existing self-financing engine. Integration is through files,
not cross-repository strategy imports. Close-known targets fill at a subsequent close, and only
subsequent price moves produce P&L. Fees are funded from capital. Uninvested cash earns zero;
SHY uses its observed adjusted price history. Holdings drift between changed targets.

Prices start in 2005 and extend through November 24, 2026. ETF selections avoid using individual
surviving technology winners, but are not a complete historical security census. No dot-com-era
performance is claimed. Reused provider prices have not been independently reconciled to an
exchange/dividend corporate-action database.

Outputs include all policies, CAGR/max drawdown/turnover, costs/delays, yearly outcomes, named
stress windows, risk-off false alarms and lead-time diagnostics, paired block intervals and a
joint family-wise excess-return screen. Stress labels are outcomes, never strategy inputs.
Concatenated disjoint stress/normal sessions are not presented as achievable continuous CAGR.
Rule families, risk budgets and sensitivity scenarios are correlated, not independent discoveries.

The 2022+ diagnostic excludes its first 63 sessions, so its effective start is April 4, 2022.
It is retrospective chronological evidence, not a previously untouched lockbox. The family-wise
statistical screen remains descriptive under revision, nonstationarity and research-selection
risks. A positive return spread alone is not durable alpha.

For selected rules, a second runner verifies artifact hashes, independently recomputes every
scenario return path, and compares with the same SPY market-structure clock, risk asset, floor
and decision cadence. For price-containing rules that is a news-removal ablation; for pure-news
rules it is a matched comparator, not an algebraic ablation. There is no holdout reselection.

## Reproduce

```sh
.venv/bin/fundamental-event-trader news-screen-freeze --bundle ../portfolio-lab/data/bundles/RUN/trade-bot --output reports/NEW_SCREEN
.venv/bin/fundamental-event-trader news-screen-build --registry reports/NEW_SCREEN/registry.json
.venv/bin/fundamental-event-trader news-vintage-freeze --bundle ../portfolio-lab/data/bundles/RUN/trade-bot --output reports/NEW_VINTAGE_SCREEN
.venv/bin/fundamental-event-trader news-vintage-build --registry reports/NEW_VINTAGE_SCREEN/registry.json
.venv/bin/fundamental-event-trader news-vintage-audit --screen reports/NEW_VINTAGE_SCREEN --latest-screen reports/NEW_SCREEN --output reports/NEW_VINTAGE_AUDIT.json
.venv/bin/fundamental-event-trader news-maturity-freeze --parent reports/NEW_VINTAGE_SCREEN --output reports/NEW_MATURITY_SCREEN
.venv/bin/fundamental-event-trader news-maturity-build --registry reports/NEW_MATURITY_SCREEN/registry.json
```

From Portfolio Lab, using its isolated environment:

```sh
.venv/bin/python -m portfolio_lab.news_evaluation --screen ../fundamental-event-trader/reports/NEW_SCREEN --output reports/NEW_PERFORMANCE
.venv/bin/python -m portfolio_lab.news_validation --screen ../fundamental-event-trader/reports/NEW_SCREEN --report reports/NEW_PERFORMANCE --output reports/NEW_VALIDATION
```

Use the same evaluator and validator for the released-vintage screen. Do not count reruns for
provenance or reporting fixes as additional independent hypotheses. Dataset/report paths are
explicit and immutable after sealing. No configuration command promotes these screens.

## Primary Sources

- [SF Fed index and methodology](https://www.frbsf.org/research-and-insights/data-and-indicators/daily-news-sentiment-index/).
- [SF Fed publication history and weekly update schedule](https://www.frbsf.org/news-and-media/news-articles/research-spotlight/keeping-an-eye-on-daily-news-sentiment/).
- [ALFRED historical release series](https://alfred.stlouisfed.org/series?seid=USEPUINDXD).
- [Authors' daily uncertainty data](https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv).
