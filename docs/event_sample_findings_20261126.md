# Event Research: Free-Sample Pilot

November 26, 2026. **Exploratory, survivor-biased, not admitted for trading.**

## What Changed

We separated a small event-return pilot from broad historical portfolio qualification.
The new `event_sample_pilot.py` path can study a limited, explicitly biased vendor sample
without inventing exact acceptance timestamps or satisfying an arbitrary ten-year /
100-security prerequisite. It cannot export targets, portfolio CAGR, promotion or
allocation authority. The existing broad research runner and its stricter gates are
unchanged. Software acceptance is not investment acceptance.

The previous goal-wide blocked report remains the record of that inspection, but is no
longer a reason to prevent all preliminary work. The full ten-family investment objective
is still incomplete; this is progress on two accounting-related formulations, not completion
or economic rejection of all ten families.

## Frozen Pilot

Before downloading this sample, we fixed ten current-Dow companies across several sectors,
two feature rules, 21/63/126-session outcomes, 1/2/5-session entry delays and 10/25/50 bps
per side. The roster was not chosen by inspecting returns. It nevertheless has substantial
survivor and hand-selection bias and cannot represent the historical stock universe.

- Cash conversion: year-over-year improvement in `(operating cash flow - net income) /
  assets`, using trailing-year as-reported financials and only an earlier public observation
  with a report period 300-430 days earlier.
- Net common capital returns: negative common-stock financing cash flow while profitable.
  This is a **net financing proxy**, not a gross buyback or authorization announcement.

The public sample supplied 200 financial observations and 1,254 daily price sessions for
each of ten securities, November 29, 2021-November 25, 2026. Original filing bytes and
precise historical acceptance/vendor ingestion times were not independently verified.
Date-only releases receive an explicit assumed processing delay; no exact acceptance
timestamp is fabricated. Forty cash-conversion observations lack a prior-year comparison
and are explicitly left-censored, not filled with future values. Cash-conversion signals
therefore begin in 2023 rather than covering the whole price panel.

The original control selects a different entry in the same stock and calendar year with
the closest trailing 63-session return, known before that entry. Disclosure entry dates are
excluded; ties use the earliest entry and controls are not reused within a scenario. This
is a retrospective event-return comparison, not a causal estimate or executable portfolio.
Control outcome windows can include subsequent disclosures and differ in regime exposure.

## Initial Results

Primary 63-session horizon, 25 bps entry and exit costs. Values below are **mean excess
returns in percentage points**, not annual returns, CAGR or avoided drawdown.

| Rule | 1-Session Delay | 2-Session Delay | 5-Session Delay | Observations Per Delay |
|---|---:|---:|---:|---:|
| Cash-conversion improvement | -0.71 | +0.71 | +1.81 | 72 |
| Net common repurchases while profitable | -0.69 | +0.38 | +0.54 | 161 / 161 / 162 |

There are 54 correlated family/horizon/delay/cost scenarios, **not 54 independent ideas**.
The output has 6,186 measured event-scenario rows. Another 191 event/delay/horizon rows
are right-censored and 69 lack the required earlier momentum window; those censoring
records are saved once before cost expansion. Repeated events overlap and are not
independent investment trials. No significance or untouched holdout claim is made.

## Adversarial Follow-Up

The apparent delay improvement prompted a control-method audit, frozen **after inspecting
the initial results**. It is explicitly a post-result diagnostic, not a fresh holdout or a
new strategy-selection round. We decomposed lag changes, checked same-year all-entry and
nearby-period alternatives, and exported year/issuer and leave-one-issuer-out breakdowns.
We did not tune feature thresholds or promote the most favorable delay.

On the same 72 cash-conversion events, changing lag 1 to lag 5 improved mean event returns
by 0.70 points, but the rematched control returns fell by 1.82 points. The apparent excess
improvement was 2.52 points. Much of the attractive comparison therefore came from moving
the benchmark, not an equivalent improvement in event returns. Repurchases showed the
same concern: +0.57 points in event returns and -0.64 points in control returns on the
161 paired events.

Against the average of **all eligible same-year non-disclosure entry periods** instead:

| Rule | 1-Session Delay | 2-Session Delay | 5-Session Delay |
|---|---:|---:|---:|
| Cash-conversion improvement | -0.72 | -0.68 | -0.01 |
| Net common repurchases while profitable | -0.65 | -0.64 | -0.11 |

A nearby momentum-matched alternative remains positive for the longer delays, so this is
not proof of no effect. It is evidence that the claimed edge depends materially on what
counts as a comparable non-event period. Year results change sign; leave-one-issuer-out
diagnostics do not repair the broad baseline weakness. These controls answer somewhat
different questions and are not a statistically identified causal experiment.

## Decision

**No robust improvement demonstrated in this pilot. No strategy admitted or integrated.**
Do not optimize a delayed-entry rule around the best-looking matched result. Obtain the
broader historical universe, independently review timestamps and failure paths, and improve
the comparison design before pursuing threshold searches. These findings do not invalidate
all cash-conversion or capital-return hypotheses, and say nothing conclusive about the
other eight event families.

The outstanding work includes validated guidance/financing/insider/event extractors,
original historical news permissions and dates, full identities and price/settlement paths,
and the frozen executable portfolio tests against unchanged existing strategies.

## Reproduction And Evidence

Run from the Fundamental Event Trader checkout after acquiring the frozen local sample:

```sh
./.venv/bin/python -m fundamental_event_trader.event_sample_pilot \
  --sources data/event_sample_20261126 \
  --output reports/event_sample_pilot_20261126_rerun
```

The output directory must not already exist. No network calls, key reads or allocation
changes occur in the analysis command.

- Sources/protocol/receipts: `data/event_sample_20261126/`.
- Initial measured returns and immutable source bindings: `reports/event_sample_pilot_20261126/`.
- Control audit and its post-result protocol: `reports/event_sample_sensitivity_20261126/`.
- Native code: `src/fundamental_event_trader/event_sample_pilot.py`.
- Boundary, integrity, timing, adjustment and return-math tests: `tests/test_event_sample_pilot.py`.
- Provider decision, prices, limitations and license requirements:
  [historical data decision](event_data_decision_20261126.md).

Raw vendor data and local reports are git-ignored. No commit, push, purchase, broker
connection or change to Trade Bot/Swing Trader/Rotation Trader/Portfolio Lab allocations
was made by this pass.
