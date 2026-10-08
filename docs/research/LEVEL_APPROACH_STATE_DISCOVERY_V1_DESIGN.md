# LEVEL_APPROACH_STATE_DISCOVERY_V1 — design note

**Status.** Design, committed before any approach-conditioned break, reject or neither rate is read. The preflight section is outcome-blind. It is an amount of information, not a gate.

**Mode.** `DISCOVERY`. This unit maps a bounded approach-state space. It does not pre-assert a sign. A relation selected because it looked best is `DISCOVERY_ONLY` on this selection surface and needs a separate `MODE = CONFIRMATION` unit. This note does not authorize that successor.

**Unit.** `LEVEL_APPROACH_STATE_DISCOVERY_V1`, family `LEVEL_BEHAVIOR_V1`.

**Dependencies.** `#352` `LEVEL_TOUCH_DEGRADATION_V1` `dfc9e0f04358de15606382472badeb5aee787039` → `#353` `LEVEL_REJECTION_MEMORY_V1` `c3d39bffda861b535605a98205d7578c0c84c782` → `#354` methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26` → this unit. Source main: `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`. This branch starts at the #353 head and contains only the #354 methodology commits on top of it. It does not edit either parent result and it does not merge to main.

**Tracks.** `STRUCTURE` + `PRODUCT_EVIDENCE`. Not `EDGE`.

**Claim ceiling.** A family-level statement that reports the whole search, with no winner selected, may be L2 under `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` when the analysis N is at least 30. A cell named because it passed the successor rule is `DISCOVERY_ONLY`, not L3 and not L4. No current probability. No direct trade call. `PRODUCT_INTEGRATION_CANDIDATE` stays `NO`.

**Code.** `scripts/research/level_approach_state_discovery_v1/`. Constants in `constants.py` are the freeze. The parent packages are imported and not retuned. `evaluate.py` is not run before this note is committed.

## 1. Question

Which point-in-time characteristics of how price approaches an already-known structural BTC level, if any, carry stable incremental historical information about the subsequent independent touch ending as `BREAK_FIRST`, `REJECT_FIRST` or `NEITHER`?

The question is not which invented trader story works. No sign is assumed for speed, path shape, compression, volume or dwell. The market decides where, inside this frozen space, a relation exists.

## 2. What is reused unchanged

From `LEVEL_TOUCH_DEGRADATION_V1`: PDH/PDL, PWH/PWL, PMH/PML; zone half-width 0.0015; birth merge; independent-touch and refractory rules (clearance entirely outside the zone and at least `1.0 ×` primary X beyond the near edge); touch numbering; support/resistance orientation; barrier `X = 0.5 × 1.2816 × σ × √48`; `σ` the DH1 rolling sigma shifted one bar; 4h window of 48 bars; same-bar `AMBIGUOUS` drop; `NEITHER` kept; `CORE_BTC_BINANCE_V0` 2020–2024; the deterministic half-rotation pseudo-level inside `(family, struct_side)`.

Those definitions are not retuned because a new result would prefer a different zone, refractory or horizon.

Parent volatility tercile edges, not refit: `0.0012364306616934476` and `0.001790567553180052`.

## 3. Data

`CORE_BTC_BINANCE_V0`, Binance USD-M BTCUSDT 5m, 2020–2024, loaded by the parent `load_discovery_bars`. OHLC. Quote volume is the Binance kline quote field on the same complete 5m bins, available at bar close. The preflight audit below decides whether it stays.

Forbidden and not read: open interest, funding, taker-buy quote, liquidations, order book, live tape, 2025/2026, any new venue, and the E1 holdout `[2026-08-16, 2026-08-25 17:20)`. A later flow unit, if the owner authorizes one, must ask whether those fields add information above this price-only approach state. It is not part of this run.

## 4. Object and decision boundary

Each event is one independent touch of one structural episode: approach, then the touch, then the 4h outcome.

`T` is the open of the first bar `j` of the current independent touch. Every approach feature uses bars with index strictly less than `j`. The touch bar's OHLC and quote, the path after zone entry, the future max/min, future volume, and the next touch are not inputs.

Parent `feature_eligible` is a data-availability flag (known side, usable X, a complete 4h window, event window from 2020-02-01). It is the same availability rule as #352. It is not the outcome. Features themselves stop at `j−1`.

## 5. Approach semantics, frozen before outcomes

One geometric episode. Not a fixed clock window.

The outer distance is `D = band_mult ×` primary X. Primary `band_mult = 1.0`, the same multiple the parent already uses for the refractory. The sensitivity uses `band_mult = 2.0` and only moves where the episode starts. The inner dwell band stays `0.5 ×` primary X, not `0.5 × D`.

On side `+1` (approach from below) a close is in-band when `zlo × (1 − D) ≤ close < zlo`. On side `−1` when `zhi < close ≤ zhi × (1 + D)`. A close is far when it is strictly outside that band on the approach side.

The episode is the contiguous run of in-band closes ending at `j−1`. It is feature-eligible only when:

- the run has at least 4 bars (`MIN_APPROACH_BARS`);
- the bar immediately before the run has index at least `i0` (the entry is observed while the level is active) and that bar is far;
- every close from the entry bar through `j−1` is finite and positive.

No observed entry, a non-finite close in that suffix, or `j−1` not in band: the touch is not feature-eligible. There is no second approach definition.

The 4-bar floor also gives each acceleration half at least two close-to-close steps. It was chosen so the acceleration split is defined, not because a shorter episode looked worse.

## 6. Feature family

All formulas use closes, highs, lows and, for F7, quote from indices `< j`. `gap` on side `+1` is `log(zlo / close)`; on side `−1` it is `log(close / zhi)`. `toward` is the negative first difference of the gap: positive when the gap to the zone shrinks. `path` is the sum of absolute close-to-close log returns from the entry bar through `j−1`. `net` is the gap closed over that same path. `n_steps` is the number of those steps.

No sign is a hypothesis.

| id | name | formula |
| --- | --- | --- |
| F1 | velocity | `net / (n_steps × σ)` |
| F2 | efficiency | `net / path` |
| F3 | pullback | share of path with negative `toward`. Algebraic complement of F2: `(1 − efficiency) / 2` when the path is the absolute log-return sum. |
| F4 | persistence | share of steps with `toward > 0` |
| F5 | acceleration | second-half velocity minus first-half velocity. The split is `n_steps // 2`. |
| F6 | range state | `log(median bar-range over the last 6 bars before j / median bar-range over the last 288 bars ending at j−1)`. Bar-range is `(high − low) / close`. The recent window sits inside the 288. The base needs at least 90% finite bars. |
| F7 | relative volume | `log(mean quote over the last 6 bars / mean quote over the last 288)`, same windows. Both means must be positive. |
| F8 | dwell | consecutive bars ending at `j−1`, inside the in-band run, whose close is in the inner band `0.5 ×` primary X. |

F6 does not use the V2 percentile engine. That engine is a different stack. The baseline here is the trailing median ratio on this 5m panel.

`log(n_steps)` is a nuisance, not a feature. The geometric band makes speed partly a restatement of how long the price stayed inside the band, so duration is adjusted rather than treated as a second speed.

Not in V1: RSI, MACD, EMA, Fibonacci, Bollinger, candlestick patterns, liquidation clusters, open interest, delta, funding, book imbalance, and any weighted `APPROACH_STRENGTH` or 0–100 score. No pairwise interaction is estimated. A combination that looks interesting after the matrix is an `EXPLORATORY_SUCCESSOR_IDEA` with no number attached.

## 7. Redundancy rule, applied before outcomes

Look only at predictor distributions and Pearson correlations. If `|ρ| ≥ 0.90` between two candidates, or between a candidate and `log(n_steps)`, and they describe the same object, drop the later one. Greedy keep order: velocity, efficiency, persistence, acceleration, range state, relative volume, dwell.

F3 is dropped analytically before the correlation step, because it is exactly `(1 − efficiency) / 2`. The preflight records the realized ρ as a check, not as a reason discovered after Y.

A feature is not dropped after its slope is seen.

Volume audit, also before outcomes: if the share of price-eligible rows with an unusable quote exceeds 0.01, F7 leaves the family and is not required. If the missing rate is at most 0.01, the common sample is the rows with a usable quote, and redundancy runs on that sample.

## 8. Outcomes

The parent state family, horizon 48 bars only: `BREAK`, `REJECT`, `NEITHER`. `AMBIGUOUS` is dropped exactly as in #352. No 1h, 8h or 24h horizon. The sensitivity is the wider approach band, not a second horizon.

## 9. Nuisance, fixed before outcomes

Each retained feature is estimated above:

- touch ordinal 1 / 2 / 3+ (reference: 1);
- family WEEK and MONTH (reference: DAY);
- support (reference: resistance, approach from below);
- pre-touch volatility tercile mid and high, parent edges (reference: low);
- `log(n_steps)`, z-scored on the frozen scale;
- year 2021–2024 (reference: 2020).

Session and time of day are not nuisances. #352 did not use them, and no unit in this family has a frozen session dependence for these barrier outcomes. They are not added after the result.

## 10. Estimand

For each retained feature and each of the three outcomes, one linear probability model. Not a classifier.

The reported coefficient is the change in the historical frequency of that outcome per +1 SD of the feature, after the nuisance list. +1 SD is the full-sample standard deviation frozen in the preflight (`ddof = 0`). Scales are not refit on Y, inside the bootstrap, on a slice, or after ambiguous touches are dropped. Ambiguous touches stay inside the frozen moments. The sensitivity band uses its own frozen scales. The pseudo-level control uses the real primary scales, so "1 SD" stays the structural scale.

The three models are separate. Their coefficients are not constrained to sum to zero. That is a limitation of the estimator, recorded here, not a finding.

Columns, and `feature_z` stays in column 1:

intercept, feature_z, touch2, touch3, fam_week, fam_month, support, vol_mid, vol_high, log_steps_z, y2021, y2022, y2023, y2024.

Two predeclared ablations, not rescues: `no_touch` drops the touch dummies; `no_duration` drops `log_steps_z`. The successor rule reads the full model. A slope that appears only after a control is removed is not a candidate.

Uncertainty: 95% percentile interval, 2000 cluster resamples, seed `20261009`. A replicate whose design is not full rank, or whose non-intercept column has fewer than two distinct values, is dropped. If fewer than 90% of replicates survive, the interval is not computable. The Wald p used only inside the FDR screen is two-sided, from the bootstrap standard error (`ddof = 1`) via the complementary error function. A missing p enters Benjamini–Hochberg as 1 and stays in `m`.

Cluster, decided before the outcome: `episode_id` for every family. Week clustering would split repeated touches of one month-long zone. Episode clustering keeps them together.

## 11. Shape

Tertile edges are the 1/3 and 2/3 quantiles of the feature on the outcome-blind sample (`q33`, `q66` in the preflight `scales` object). `low` is at or below `q33`, `high` is above `q66`, `mid` is the rest. All three bands are reported. The high-minus-low contrast is an OLS coefficient on an indicator, with the same cluster bootstrap. It is descriptive.

Shape labels, applied after the rates exist, do not create a cut: `near_zero` when `|high − low| < 0.03` and the interval includes 0; else `monotonic` when the three rates are ordered and the ends differ; else `u_shape` when the middle rate lies outside the end rates; else `other`; `insufficient` when a band rate is missing. An unexpected shape is named as a successor note. It does not become a new threshold inside this unit.

## 12. Multiplicity

Benjamini–Hochberg FDR at `q = 0.10` on the primary matrix only: retained features × 3 outcome slopes. That is a discovery screen, not a validator. Raw coefficients and intervals are reported whether or not they pass. A feature is not hidden because of the correction. Stability, leave-one-year-out, tertiles, the two ablations, the sensitivity band and the control are not in the FDR family.

## 13. Successor rule

A feature-outcome cell is a `SUCCESSOR_CANDIDATE` only when every clause holds. The clauses are not a score.

1. The full-model coefficient passes FDR at `q = 0.10`.
2. `|b| ≥ 0.03` and the 95% interval excludes 0. The 0.03 figure is the parent level-reaction reading scale (`MATERIAL_DIFF` in `LEVEL_TOUCH_DEGRADATION_V1`), applied here per 1 SD. It is not the DH1 3pp-plus-Brier rule, not Holm, and not a gate. The universal 0.5 SD bar is not used.
3. At least 4 of the 5 within-year coefficients that have N ≥ 30 have the same non-zero sign.
4. All 5 leave-one-year-out coefficients are finite and have that same sign. Definitions and tertile edges are not refit. Leaving 2020 out drops the 2021 dummy so 2021 becomes the reference; leaving another year out drops only that year's dummy.
5. The cell is judged on the full model, which already includes touch ordinal. The `no_touch` ablation is reported beside it and is not itself a candidate.
6. The pseudo-level coefficient is finite, and either its absolute value is below half the structural `|b|`, or its interval includes 0. A missing control coefficient fails the clause. A missing control interval fails the clause when the half-magnitude test also fails.
7. The busiest family holds at most 70% of the analysis rows (after the ambiguous drop), and at least 2 families with N ≥ 30 have the same sign.

If none pass, `SUCCESSOR_CANDIDATE = NONE`. That is a complete result.

The preflight family share is already about 72.9% DAY (1,441 / 1,976) before the ambiguous drop. Clause 7 uses the analysis sample and the cap stays 0.70. The cap is not raised because the preflight share exceeds it.

## 14. Routing labels

Descriptive labels, not truth scores. Applied in this order:

- any successor candidate → `DISCOVERY_STRUCTURE_PRESENT`;
- else any primary cell with `|b| ≥ 0.03` and an interval that excludes 0 → `STRUCTURE_PRESENT_BUT_UNSTABLE`;
- else any `no_touch` cell with that same notable reading → `REDUNDANT_WITH_KNOWN_STATE`;
- else `NO_STABLE_APPROACH_STRUCTURE`.

Atlas map, for the closeout after the one run: `NO_STABLE_APPROACH_STRUCTURE` or `REDUNDANT_WITH_KNOWN_STATE` → `NO_STRUCTURE`. The other two labels → `CLOSED_ON_SURFACE`. A discovery candidate is not a live product signal, and confirmation on this same 2020–2024 surface is not allowed by the atlas reopen rule.

Claim: `DISCOVERY_ONLY` when a candidate exists; otherwise L2 when the analysis N is at least 30; otherwise no claim line.

Ranking of the matrix, even when nobody passes: FDR-adjusted evidence, then absolute effect, then year-sign stability, then feature id. No combined quality score.

## 15. Search exposure

Counted before outcomes. With 7 retained features the formula is `7 × 3 × 21 = 441` material cells. The FDR family is the 21 primary slopes.

Per feature and per outcome, 21 cells:

- 6 with intervals: full model, `no_touch`, `no_duration`, tertile high−low, sensitivity band 2.0, pseudo-level control;
- 15 point estimates: 5 years, 3 families, 2 sides, 5 leave-one-year-out.

Tertile band rates are components of the tertile contrast, not extra cells. No cell is added after the result. Interactions estimated: 0.

## 16. Falsification and stability

Falsification uses the parent half-rotation pseudo-level touches, with the same approach rules and the real primary scales. If the control shows the same stable pattern, that limits a candidate reading: the pattern may be a property of a crossing path rather than of the structural price.

Stability, not new hypotheses: within each year 2020–2024, within DAY / WEEK / MONTH, and within support / resistance. Leave-one-year-out is the sign-and-magnitude check in the successor rule. A flip is reported. It is not hidden and it does not start a new cut.

## 17. Selection

The estimate is about structural touches that have an observed entry into the outer band, a run of at least four in-band bars ending at the bar before the touch, a usable pre-touch range baseline, and a complete 4h window. Touches that gap into the zone, or that never show a far bar while the level is active, are outside the estimate. Repeating that limit is part of the result.

## 18. Preflight

Source: `docs/research/LEVEL_APPROACH_STATE_DISCOVERY_V1_PREFLIGHT.json`, computed before this note was committed. No outcome was classified. No slope was fit. No technical change follows these counts. Sections 5–17 stay as written.

The grid is the parent's 526,176 five-minute bars. Parent feature-eligible touches: 4,213. Approach price-eligible rows: 1,976. Quote missing rate on those rows: 0. Volume status: `available`. Field: `quote`. Taker-buy quote was not used. After the volume filter the sample is unchanged: N = 1,976, episode clusters = 1,211, product weeks = 258.

Touch buckets: 1 = 684, 2 = 640, 3+ = 652. Family: DAY = 1,441, WEEK = 421, MONTH = 114. Side: resistance = 1,073, support = 903. Year: 2020 = 339, 2021 = 450, 2022 = 393, 2023 = 343, 2024 = 451. Busiest family share on this preflight sample: 1,441 / 1,976 ≈ 72.9% (DAY).

Control rows at the primary band, after the same volume filter: N = 1,828, clusters = 1,149. Sensitivity band 2.0: N = 2,107, clusters = 1,352. Its scales are the `sensitivity_scales` object. They are not refit.

Dropped: `pullback` only, ρ with efficiency = −1, reason algebraic. Retained: velocity, efficiency, persistence, acceleration, range_state, rel_volume, dwell.

Largest `|ρ|` below the 0.90 cut, all kept: velocity–log_steps −0.787; efficiency–log_steps −0.762; velocity–efficiency 0.766; efficiency–persistence 0.752; range_state–rel_volume 0.781; velocity–rel_volume 0.653. `log_steps` with raw `n_steps` is 0.928; `n_steps` is not a model feature.

Predictor moments (mean / sd / median), N = 1,976:

- velocity 0.470 / 0.295 / 0.402 (minimum 0.017; the band geometry makes net closure positive);
- efficiency 0.574 / 0.249 / 0.548;
- persistence 0.693 / 0.144 / 0.667;
- acceleration −0.287 / 0.608 / −0.173 (the entry step is often the largest gap closure, so the mean acceleration is negative; that is geometry);
- range_state 0.119 / 0.375 / 0.095;
- rel_volume −0.051 / 0.530 / −0.084;
- dwell 2.32 / 2.57 / 2 (maximum 27);
- log_steps 2.206 / 0.643 / 2.079 (minimum `log(4)`).

Frozen scales, including tertile edges, are the `scales` object in the preflight file. Material cells: 441. FDR family size: 21.

Month N = 114 is still estimated. The column set is not reduced because of that count.

## 19. Out of this unit

No product change. No `/btc`, `/levels`, `/check`, `/risk`, score, Telegram line, config, findings registry, or deploy edit.

Not started from this note: a confirmation unit, `LEVEL_APPROACH_FLOW_INCREMENTAL_V1`, any interaction, any new feature, any new horizon, any new threshold.
