# News Performance Findings

## Conclusion

There is a modest research candidate, not a demonstrated profitable article-reading event bot.
Raw news sentiment/uncertainty rules were generally weak. A source-maturity follow-up found
better results from a seven-day average of historically released newspaper uncertainty. It
modestly improves the recent risk/return trade-off and transfers reasonably across several
markets, but does not establish statistically durable alpha or predict bubble breaks in advance.
Nothing was promoted into a live allocation, and no portfolio account data was used.

## Tests Actually Run

| Study | Policy variants | Candidate/scenario runs | Evidence scope |
|---|---:|---:|---|
| Sentiment/uncertainty/confirmation/repair/sector screen | 68 | 408 | Current historical vintages; exploratory only |
| Historical released uncertainty vintages | 40 | 200 | 151 monthly ALFRED releases; 149 fresh, two explicit no-update months |
| Source-maturity follow-up | 24 | 120 | Fixed 7/14-day maturity and seven-day average, within released histories |
| Unchanged selected-rule transport | Same rule, seven additional ETFs | 28 | No new threshold fitting or per-market winner selection |

These are 132 correlated policy variants and 728 candidate/scenario evaluations, plus 28
cross-market evaluations. Provenance/reporting reruns are not counted as new hypotheses.
Additional benchmark replays are not candidate tests. This is not hundreds of independent
confirmations.

Rules and selection were frozen before each study's return evaluation. The third study was a
follow-up to the release-revision audit, not a fresh unseen holdout. Chronological validation,
63-session boundary purges, execution delays, transaction costs, source reconstruction and
independent selected-path replays are recorded in the artifacts.

## Recent Diagnostic Results

April 4, 2022 through November 24, 2026; net of 10 bps per traded side, with next-session-close
execution. Selection uses development data only, not the table below.

| Asset | Approach | CAGR | Maximum drawdown |
|---|---|---:|---:|
| SPY | Buy-and-hold | 11.95% | -21.28% |
| SPY | Weekly 200-day price rule, 50% floor | 10.46% | -15.23% |
| SPY | Selected raw released-vintage rule | 8.87% | -14.10% |
| SPY | Selected seven-day-average news rule | 12.79% | -17.80% |
| QQQ | Buy-and-hold | 13.71% | -29.20% |
| QQQ | Weekly 200-day price rule, 50% floor | 13.34% | -19.15% |
| QQQ | Selected raw released-vintage rule | 10.96% | -29.20% |
| QQQ | Selected seven-day-average news rule | 14.66% | -24.02% |

The smoothed rule increases recent CAGR by approximately 0.84 percentage points for SPY and
0.95 points for QQQ versus buy-and-hold, while reducing maximum drawdown by 3.48 and 5.19
percentage points. Price-only timing still offers stronger drawdown control, so the news rule
does not dominate that comparator on both return and risk.

## What The Candidate Does

At each tested monthly decision, use the uncertainty history in that month's actual ALFRED
vintage. Calculate a trailing seven-calendar-day average, transform by log(1 + index), and compare
the latest level with its preceding 252 observed values. If the standardized reading reaches
1.5, reduce the chosen equity ETF from 100% to 50% and allocate the remainder to SHY. Otherwise
hold the equity ETF. The threshold is shared across both assets, not individually optimized.

Decision availability is delayed two calendar days beyond the vintage date and orders fill at
a subsequent close. Stale source releases issue no new target. This tests a low-frequency
defensive budget, not intraday event trading, stock selection or a recommendation to trade now.

## Robustness And Boundaries

- Five-session execution delay: recent SPY CAGR 12.60%, max DD -16.68%; QQQ CAGR 14.71%, max
  DD -21.65%. At 25 bps cost: SPY 12.60%/-17.93%; QQQ 14.48%/-24.13%. The modest recent
  buy-and-hold advantage survives these separate stresses; a simultaneous cost-plus-delay
  stress was not part of this released-vintage protocol.
- Full May 2014-November 2026: SPY news rule 12.94% CAGR/-22.97% max DD versus buy-and-hold
  13.13%/-33.72%. QQQ news rule 17.23%/-32.59% versus 18.06%/-35.12%. It does not improve
  full-period CAGR. Do not present the recent-period result as a universal growth improvement.
- Unchanged transport improves recent CAGR in six of seven additional ETFs. RSP: 9.31% versus
  8.51%; IWM: 8.04% versus 6.91%; XLV: 10.88% versus 8.22%. XLE underperforms: 13.29% versus
  13.94%, with the same -26.04% max DD. At higher costs, five of seven beat buy-and-hold;
  at two-/five-session delay, six/seven do. These markets share common shocks and are not
  independent replications. The extended period remains mixed.
- The joint 64-variant released-vintage family screen has descriptive p-value 0.754. Paired
  block intervals for the selected models' excess return include zero. This is weak statistical
  support, not proof of a repeatable return edge.
- All 151 sampled vintages differ from current history somewhere in their matched window,
  including their newest observation. Historical versions matter; applying today's revised
  series to an old date can materially change the signal.
- The rule is not a leading crash alarm. Its first partial reduction occurred September 3,
  2015 (94 days after the selected stress-window start), December 4, 2018 (75 days after),
  March 3, 2020 (13 days after), and February 3, 2022 (31 days after). It made no reduction
  below 75% in the defined June-November 2026 window. Those dates are retrospective
  diagnostics. The lead-time CSV's legacy term "hard defense" refers to a below-75% threshold;
  the selected strategy's action is only a 50% risk budget, not a 20-40% hard-defense tier.

## What Is Not Validated

This does not backtest the new RSS article reader, extracted company guidance, financing or
demand events, SEC-driven stock selection, or additions to Trade Bot's roughly 22%-CAGR native
strategies. No such integration or profitability is claimed. The qualified company-event
research table can still correctly show zero tested policies while these separate ETF-proxy
screens have real historical results. Dot-com-era protection is not tested: reused prices begin
in 2005. There is no new untouched prospective lockbox or independent exchange-price audit.

## Next Performance Work

Stop tuning this small index family on these historical returns. Preserve the smoothed rule as
a frozen research comparator, not a live override. The next event-trader study needs archived
company-specific announcements and financial reporting with usable availability times and
security identities: guidance/capex cuts, funding stress, order cancellations, and comparable
positive events. Test post-publication drift against immediate price reaction and matched
non-events, including failed/delisted firms and 1/2/5-session human execution delays. Only then
test incremental benefit inside the actual native strategy families against unchanged controls.

The stronger lesson is source maturity plus explicit availability, not a new sentiment threshold.
General newspaper fear may help size risk, but it has not established the rapid, forward-looking
company-event advantage the user is asking for.

## Evidence

- Native protocol: [news_performance_protocol_20261125.md](news_performance_protocol_20261125.md).
- Native screens: `reports/news_proxy_screen_20261125`, `reports/news_vintage_screen_20261125`,
  `reports/news_maturity_screen_20261125`.
- Source/target audits: `reports/news_vintage_source_audit_20261125.json` and
  `reports/news_maturity_source_audit_20261125.json`; raw bytes, code and identities preserved.
- Portfolio Lab: `reports/news_proxy_performance_release_20261125`,
  `reports/news_vintage_performance_20261125`, `reports/news_maturity_performance_20261125`.
- Independent replay audits: `reports/news_proxy_validation_release_20261125`,
  `reports/news_vintage_validation_20261125`, `reports/news_maturity_validation_20261125`.
- Combined comparison/transport/statistics: Portfolio Lab
  `reports/news_performance_assessment_20261125`.
- Local regression suites: 203 native and 175 Portfolio Lab tests passed; no skipped tests.
  These are software checks, not additional investment-performance trials or remote CI.
