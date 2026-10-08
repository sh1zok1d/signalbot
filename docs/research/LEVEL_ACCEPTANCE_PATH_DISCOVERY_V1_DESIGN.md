# LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1 — design note

**MODE = DISCOVERY.** Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is frozen before any path state is joined to a late BREAK or REJECT label. A null is a complete result. The unit does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, scoring, the findings registry, or deployment.

## Question

`LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1` found a strong historical association between `END_POSITION_X` at T+15m and later BREAK among events still unresolved at that time: about +20.3 pp per +1 SD, with one sign across years and sides. The frozen candidate conjunction of that unit was not met. The pseudo-price point was larger. `END_POSITION_X` is close to a direct measure of progress toward the future break barrier.

This unit asks a different question.

At a comparable price location at D = T+15m, does the 15-minute path around the structural level carry additional information about the later BREAK versus REJECT resolution?

Two events can finish the 15 minutes in a similar place. One may have stayed beyond the structural zone. The other may have closed beyond it and come back, or may have arrived there only on the last bar. The question is whether that history adds anything once the endpoint is held fixed.

## What is already established and is not re-tested

The endpoint slope is already on the record. This unit does not rescore it, does not threshold it, and does not turn it into an acceptance, reclaim, failed-break, or confirmed-breakout flag. `END_POSITION_X` enters only as a mandatory nuisance.

## Novelty audit

Read before implementation: H02 failed-breakout, B2-02 breakout, V2 `CONFIRMED_BREAKOUT`, the V2 breakout-lifecycle false-break rules, the Atlas row `PRICE_STRUCTURE.breakout`, and #361.

| Object | What it tested | Why this unit is a different object |
|---|---|---|
| H02 | A 5m bar that opens and closes inside a 60/120/240m range and wicks through it, then a signed return. Verdict `H02_KILL`. | Population is a rolling-range wick. Outcome is a signed return. There is no structural first-touch cohort and no control for the observed endpoint. |
| B2-02 | A closed breakout cell on CORE BTC. | That cell stays closed. This unit does not reopen it. |
| V2 `CONFIRMED_BREAKOUT` | First 5m close beyond a 48-bucket 1h high or low, plus a directional-context gate. Stage-5 qualification, retired as a current formulation. | Different level, different clock, and a qualification flag this unit does not emit. |
| V2 breakout-lifecycle false-break rules | Stage-5/6 lifecycle labels on a breakout family. | This unit assigns a descriptive path state inside a fixed endpoint side. It does not emit `FALSE_BREAK`. |
| `PRICE_STRUCTURE.breakout` | Generic breakout continuation. | Atlas row for this unit is `PRICE_STRUCTURE.levels`. Reopen key `NEW_MECHANISM`. |
| #361 `END_POSITION_X` | The continuous close location at D, in barrier units, as a predictor of later BREAK. | This unit conditions on that location and asks whether path history adds a difference inside one endpoint side. |

The new object is path memory within the first 15 minutes after an independently replicated structural first touch, conditional on the observed endpoint at D.

The formulation is a within-endpoint contrast with `END_POSITION_X` held as a nuisance. It is an incremental path question on `PRICE_STRUCTURE.levels`. `BLOCKED_REOPENING_FAILED_BREAKOUT_CELL` does not apply. The taxonomy is not being edited to avoid that stop.

## Data

Price OHLC only, from `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. Complete 5m bins. The loader is the parent #352 discovery panel: 2020-01-01 inclusive through 2025-01-01 exclusive.

Volume, taker flow, open interest, funding, the order book, liquidations, spot, and any second venue are not read. The aim is to isolate price acceptance and reentry geometry.

No 2025 object. No 2026 object. No E1 holdout.

## Event window

Inclusive start `2020-02-01T00:00:00Z`, the parent #352 first-touch boundary after the January warm-up. Exclusive end `2025-01-01T00:00:00Z`.

The 2020 epoch is February through December and is labelled `2020`. This is the exposed discovery surface. It is not a confirmation.

## Event semantics

The geometry is the parent #352 geometry, imported and not rewritten: PDH, PDL, PWH, PWL, PMH, PML, level birth, lifetime, merge, zone, first touch, orientation, X, and the original 4h barrier. `touch_number = 1` only.

BREAK, REJECT, NEITHER, and AMBIGUOUS keep the parent barrier rule. The late window uses that rule on a later slice of the same horizon. The horizon is not extended.

## Clocks

T is the open of touch bar `j = [T, T+5m)`.

D = T+15m. The closed reaction bars are `j`, `j+1`, and `j+2`. Future information starts at `j+3`. The original horizon still ends at `j+48`. `LATE_STOP` is exclusive and equals `j+49`, the same parent end as #352 and #361.

## Early resolution

The #361 rule is reused. Barrier passage is evaluated on `j+1` and `j+2` only. The touch bar is not a resolution. An early BREAK, an early REJECT, or an early same-bar ambiguity is counted and then left out of every predictive contrast. The primary population is `UNRESOLVED_AT_D`.

## Break-side close indicator

For each reaction close, `B_k = 1` when the close is strictly beyond the break-side edge of the structural zone.

- Resistance, approached from below (`side = +1`): `B = 1` if and only if `close > zone_high`.
- Support, approached from above (`side = -1`): `B = 1` if and only if `close < zone_low`.

Equality with the edge is `B = 0`. A non-finite close makes the path unavailable and the event is not placed in an arm.

`B0` is the close of bar `j`. `B1` is the close of `j+1`. `B2` is the close of `j+2`. These bits locate the close relative to the structural zone. They are not the barrier `X`.

## Frozen four-state path taxonomy

Each unresolved event with three finite bits receives exactly one state.

| State | Rule | Sequences |
|---|---|---|
| `NEVER_OUTSIDE` | `B0 = B1 = B2 = 0` | `000` |
| `REENTERED` | `B2 = 0` and (`B0 = 1` or `B1 = 1`) | `010`, `100`, `110` |
| `LATE_OR_RECROSS_OUTSIDE` | `B2 = 1` and `B1 = 0` | `001`, `101` |
| `PERSISTENT_OUTSIDE` | `B2 = 1` and `B1 = 1` | `011`, `111` |

`REENTERED` is a descriptive name. It is not a `FALSE_BREAK` label. `PERSISTENT_OUTSIDE` is a descriptive name. It is not an acceptance label.

The eight binary sequences partition into these four states. The partition is exhaustive and mutually exclusive. After outcomes, the taxonomy stays frozen: no 2-of-3 rule, no 3-of-3 rule, no wick rule, no 10m, 20m, or 30m window, no zone-plus-percent band, and no close-beyond-a-fraction-of-X rule.

## Why the contrasts are within one endpoint side

`B2 = 0` contains `NEVER_OUTSIDE` and `REENTERED`. Both finish the 15 minutes inside the break-side edge. The contrast asks whether a prior close beyond the zone, followed by a return, carries information.

`B2 = 1` contains `LATE_OR_RECROSS_OUTSIDE` and `PERSISTENT_OUTSIDE`. Both finish the 15 minutes beyond the edge. The contrast asks whether two consecutive closes beyond the edge carry information beyond a last-bar arrival.

States are not compared across `B2`.

## Endpoint baseline

`END_POSITION_X` is the #361 R1 formula at the close of bar `j+2`, imported from that unit.

- From below: `(close_D - zone_high) / (zone_high × X)`.
- From above: `(zone_low - close_D) / (zone_low × X)`.

It is a mandatory nuisance in both primary models. A path contrast that exists only when this term is omitted is endpoint proximity. This unit does not fit that omitted model.

## Outcomes

One primary outcome: `LATE_BREAK_GIVEN_RESOLVED`.

Population: unresolved at D, then resolved after D and before the original T+4h, with no ambiguity. `1 = BREAK`. `0 = REJECT`.

`LATE_RESOLVE_BY_4H` is reported only as a descriptive rate by state and by sequence. It is not a candidate cell and it is not in the FDR set.

## Two primary estimands

**C1 `REENTRY_MEMORY`.** Population `B2 = 0`. Estimand: adjusted difference `P(LATE_BREAK | REENTERED) − P(LATE_BREAK | NEVER_OUTSIDE)`. The indicator is 1 for `REENTERED` and 0 for `NEVER_OUTSIDE`.

**C2 `PERSISTENCE_MEMORY`.** Population `B2 = 1`. Estimand: adjusted difference `P(LATE_BREAK | PERSISTENT_OUTSIDE) − P(LATE_BREAK | LATE_OR_RECROSS_OUTSIDE)`. The indicator is 1 for `PERSISTENT_OUTSIDE` and 0 for `LATE_OR_RECROSS_OUTSIDE`.

The reported coefficient is that indicator, in probability points. It is not a per-SD slope.

## Nuisance

Both models include:

- `END_POSITION_X` (standard score, ddof 0);
- family, with DAY as the reference and WEEK and MONTH as dummies;
- support versus resistance;
- year, with the earliest present year in `2020, 2021, 2022, 2023, 2024` as the reference;
- parent #352 pre-touch realized-volatility tercile, cuts `0.0012364306616934476` and `0.001790567553180052`, not refit;
- UTC 6-hour block of T;
- pre-touch approach displacement: `side × log(close of the bar that ends at T / open of the bar that opens at T−60m)`. Touch bar excluded. Price only.

No post-touch volume, taker, or open interest. No outcome-driven nuisance. No other path state as a covariate.

Scales for `END_POSITION_X` and displacement are frozen on the unresolved, nuisance-complete rows of that contrast, before late ambiguous and NEITHER rows are dropped, and are applied unchanged to the pseudo cohort.

## Positivity rule, frozen before the audit

For each contrast, report the arm means, standard deviations (ddof 0), quantiles `p05, p10, p25, p50, p75, p90, p95`, the standardized mean difference

`(mean_treated − mean_reference) / sqrt((sd_treated² + sd_reference²) / 2)`,

and the overlap interval equal to the intersection of the two arms' `[p10, p90]`.

A contrast passes the overlap rule only when all of the following hold:

1. the intersection of the two `[p10, p90]` intervals has positive length;
2. at least 50 percent of each arm lies inside the other arm's `[p05, p95]`.

The standardized difference is reported. It is not itself a gate. Quantiles use the linear numpy definition.

If the overlap rule fails, that contrast is `COMPARISON_INFORMATION_LIMITED_NO_OVERLAP`. No regression of Y is fit. No propensity model is added after the audit.

## Arm minimum, frozen before the audit

Each arm of a contrast needs `N >= 100` unresolved nuisance-complete events before that contrast may enter the outcome model.

Below that minimum the contrast is descriptive at the outcome-blind level only: arm counts and endpoint distributions. It is not a candidate, and Y is not regressed. The minimum is not lowered after the result.

Candidate eligibility adds a second count, applied after outcomes and not used to refit: each resolved arm (BREAK + REJECT) also needs `N >= 100`. A smaller resolved arm keeps the coefficient as a description and makes the candidate impossible.

A contrast whose frozen endpoint scale or displacement scale is non-positive is not estimated. The adjustment would not be identified.

## Information gate

A contrast that fails the arm minimum, the overlap rule, or the scale check is `INFORMATION_LIMITED` for that contrast. The other contrast may be estimated when it passes on its own.

If neither contrast passes, the unit stops before any late label is read. Routing is `INFORMATION_LIMITED` / `LEVEL_ACCEPTANCE_PATH_INFORMATION_LIMITED`. The taxonomy is not redefined.

## Estimator

Transparent linear probability model.

- C1: `Y ~ REENTERED + END_POSITION_X + frozen nuisance`
- C2: `Y ~ PERSISTENT_OUTSIDE + END_POSITION_X + frozen nuisance`

No classifier. No regularization. A design with more columns than rows, a constant non-intercept column that cannot be dropped, or a condition number above `1e8` returns no coefficient. Constant nuisance columns are dropped. The state indicator, and in the stacked model the real indicator and the interaction, are not dropped for being the object of the fit; a constant state indicator fails closed.

## Bootstrap

ISO week of the real touch for the primary fit. `B = 2000`. Seed `20261018`. Stream: `20261018 + 100 × contrast_index + kind`, with `REENTRY_MEMORY` index 0, `PERSISTENCE_MEMORY` index 1, kind 0 primary, kind 1 pseudo, kind 2 stacked. The index is the frozen contrast index even when the other contrast is skipped.

Whole weeks are resampled. The interval is the 95 percent percentile interval. A draw is valid when the reported coefficient is finite. The interval is reported only when at least 90 percent of draws are valid. That line is not lowered. A withheld interval is a missing interval, not a zero.

Pseudo-only fits cluster on the pseudo touch week. Stacked fits cluster on the real touch week, with both members of a pair in that week.

## Multiplicity

At most two primary hypotheses. Benjamini–Hochberg `q = 0.10` across the contrasts that were actually estimated. A contrast that stopped at the information gate has no p-value and is not in the set. One estimated contrast uses `q = p`.

## Practical scale

`3 pp` absolute adjusted difference. Unchanged after outcomes.

## Candidate rule

A contrast is a `PATH_MEMORY_CANDIDATE` only when every clause below holds.

1. Each resolved arm has `N >= 100`.
2. The overlap rule already passed, which is required for the model to exist.
3. The absolute adjusted difference is at least 3 pp.
4. The 95 percent interval excludes 0.
5. Benjamini–Hochberg `q <= 0.10`.
6. At least four of five eligible years share the primary sign. A year is eligible when its resolved `N >= 30` and both of its arms have `N >= 15`. A missing coefficient is not a match. One eligible year may differ in sign when five years are eligible. Fewer than four eligible years fails the clause.
7. Every leave-one-year-out complement with `N >= 30` keeps the sign. A missing coefficient on such a complement fails the clause.
8. Family. DAY and WEEK are the estimable strata. A stratum is estimable when `N >= 30`, both arms have `N >= 15`, and the coefficient exists. The clause fails only when both are estimable and the signs are opposite. MONTH is descriptive. A rank failure from omitting the dominant family is not a gate. Leave-one-family-out is not computed.
9. Side. When both resistance and support are estimable under the same N and arm rule and the signs are opposite, the clause fails. There is no side-specific winner. A side that is not estimable is information-limited and is not a contradiction.
10. Point-in-time construction: reaction closes stop at `j+2`. Late labels start at `j+3`.

This family clause is specific to this unit. It is frozen before outcomes. It does not rewrite #361.

## Stability

Epochs, because the price panel starts in February 2020: `2020`, `2021`, `2022`, `2023`, `2024`. The 2020 label covers the exact event interval inside 2020, which begins on 1 February.

Leave-one-year-out uses the same taxonomy and the same model. Thresholds are not refit. It is required only for contrasts that entered the outcome model.

Family report: DAY, WEEK, MONTH. MONTH is diagnostic. No family is a separate candidate.

Side report: resistance and support. No side is a separate candidate.

## Descriptive sequence table

After outcomes, and only after outcomes, report all eight `B0 B1 B2` sequences on the unresolved cohort: `000, 001, 010, 011, 100, 101, 110, 111`. For each: N, late BREAK share, late REJECT share, late NEITHER share. Early-resolved events are already excluded. This table is descriptive. It is not an eight-cell test.

## Pseudo specificity

After the real analysis, the parent #352 deterministic half-rotation pseudo first touches receive the same D, the same unresolved-at-D rule, the same bits, the same four states, the same two contrasts, and the same `END_POSITION_X` nuisance. The pseudo sample does not choose the taxonomy. The real contrast's frozen scales are reused.

Specificity is interpreted only when the real conjunction passes.

- `LEVEL_ACCEPTANCE_PATH_CANDIDATE`: the real conjunction passes, `|delta| >= 3 pp`, the 95 percent interval for delta excludes 0, `|beta_real| > |beta_pseudo|`, and the real slope, the stacked real slope, and delta share a sign.
- `GENERIC_PRICE_PATH_MEMORY_CANDIDATE`: the real conjunction passes, the material test does not, the pseudo slope has the same sign as the real slope, and `|beta_pseudo| >= 0.5 × |beta_real|`.

If the stacked interval is withheld under the 90 percent rule, the material test fails. Point estimates may still meet the generic rule. A large pseudo result does not rescue a real null.

A plausible and valid null is that the current price location carries the association and the path, once that location is held fixed, adds little. Structural specificity is not forced.

## Wording

Even if `REENTERED` differs, the text says that events with a prior close beyond the zone and a close back inside at D had an adjusted late-BREAK frequency different by the reported amount from events that never closed beyond the zone, after controlling for `END_POSITION_X`.

Even if `PERSISTENT_OUTSIDE` differs, the text says that events with two consecutive closes beyond the structural zone had an adjusted late-BREAK frequency different by the reported amount from events whose final close was beyond the zone and whose previous close was not, after controlling for `END_POSITION_X`.

The phrases `FALSE BREAK CONFIRMED` and `ACCEPTANCE CONFIRMED` are not used.

## Outcome-blind preflight

Allowed before the design commit is paired with outcomes: event counts, early-resolved counts, unresolved counts, sequence counts, four-state counts, arm sizes, endpoint distributions, the overlap audit, year, family and side counts, pseudo state counts, and a rough MDE.

The rough MDE is context. It assumes a Bernoulli variance of 0.25, the parent planning design effect 1.25, and a two-sample difference of proportions. It is not a gate.

Forbidden in the preflight: late BREAK rates by state, late REJECT rates, and any state-outcome association.

## One official run

The evaluator refuses a second run once a result file exists. After outcomes, D, the state definitions, the endpoint nuisance, the arm grouping, the overlap rule, the nuisance list, the FDR threshold, and the 3 pp scale stay as written here.

## Routes

- `LEVEL_PATH_MEMORY_STRUCTURE_PRESENT` — at least one real conjunction passes and the specificity class is `LEVEL_ACCEPTANCE_PATH_CANDIDATE`.
- `GENERIC_PRICE_PATH_MEMORY_ONLY` — a real conjunction passes and the class is `GENERIC_PRICE_PATH_MEMORY_CANDIDATE`, with no level-specific class.
- `NO_INCREMENTAL_PATH_MEMORY_BEYOND_ENDPOINT` — at least one contrast was estimated and none is a candidate or an unstable statistical hit. A contrast that stopped at the information gate is reported beside this route.
- `STRUCTURE_PRESENT_BUT_UNSTABLE` — a statistical hit on the magnitude, interval, and FDR clauses whose temporal, family, or side clause fails, or a real conjunction whose specificity is unresolved.
- `INFORMATION_LIMITED` — neither contrast reached the outcome model.
- `BLOCKED_REOPENING_FAILED_BREAKOUT_CELL` — novelty stop. Not taken.

`SUCCESSOR_CANDIDATE = NONE`. No cross-venue reaction, spot-versus-perp, time-to-resolution, false-break refinement, 30-minute window, or confirmation is started from this result.

## Claim ceiling

Maximum `L2 / DISCOVERY_ONLY`. The surface is already exposed. A historical frequency is not a current probability. No L3. No L4. No trade call. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
