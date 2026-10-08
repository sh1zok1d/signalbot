# LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1

Mode: `CONFIRMATION`. Accrual: `PROSPECTIVE_ONLY`. Surface class, after this freeze and only for the exact prospective claim: `PRISTINE_CONFIRMATION`.

This note is the pre-outcome design. It does not contain a prospective effect, a confidence interval, or a route from future bars. No prospective sample exists yet. The official evaluator must refuse until the frozen stop is met, the cohort is closed, and the pair map is frozen.

Parent replication HEAD: `f4b8d6e8e15862aeb79ae9eea4d28f98123e1f46`. Source main: `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.

## Question

After the exact structural first-touch volatility-transition relation was frozen and reproduced on another era and venue, does that same relation appear on Binance USD-M BTCUSDT perpetual structural first touches whose episodes become active only after this design is committed?

One estimand. No new feature.

## Carried-forward claim

Discovery `#368`, design `54338b7faab9598152e2fa1270d2fb51a4beed18`. `DELTA_TRANSITION = +0.106803` log, about `+11.272%`, 95% about `+6.88%..+15.80%`, N=1231, Binance 2020–2024.

BitMEX replication, design `6d97157be44f02ad09344a00df58b715e5c8aa13`. `DELTA_TRANSITION = +0.096545` log, about `+10.136%`, 95% about `+2.20%..+18.31%`, N=554. Route `REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION`. Evidence `REPLICATED_ON_TIME_DISJOINT_EXPOSED_SURFACE`. That surface was neighbor-exposed. This prospective claim is a different surface.

Primary estimand, unchanged:

`DELTA_TRANSITION = mean(TRANSITION_REAL − TRANSITION_PSEUDO)`

`TRANSITION = log(RV_POST60 / RV_PRE60)`

`RV = sqrt(mean(r^2))`, `r_k = log(close_k / close_{k-1})`, no demean, no annualization, no epsilon.

`T` is the open of touch bar `j`. Bar `j` is in neither window. Pre returns are `j-12..j-1`. Post returns are `j+1..j+12`. The first post return is `log(close_{j+1} / close_j)`.

Practical bar: `log(1.10)`. The preselected sign is positive. A negative result is reported in full. This is not a two-sided search for any effect.

Multiplicative reading: `exp(DELTA_TRANSITION) − 1`.

## What is not changed

Level family, first-touch semantics, zone, pseudo rotation, pre window, post window, touch-bar exclusion, RV formula, transformation, practical bar, sign, and comparator stay as frozen. A future miss does not authorize a change.

Not in the estimator: volume, open interest, funding, taker, Bybit, OKX, spot, book, liquidations, RMUT, first-hit time, resolved-by-60, barrier labels, endpoint, or a cross-venue term. `INDEPENDENCE_FROM_RESOLUTION_CLOCK = UNRESOLVED`. No joint model. `#363` is not started.

## Start rule

`PROSPECTIVE_START_UTC` is the first UTC midnight strictly after the commit timestamp of this design file.

The resolver reads git committer time only. It does not read a market bar. The resolved instant is written into `LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_SURFACE_V1.json` and checked: start `>` design commit time. The manifest is immutable once written.

No start earlier than that midnight is legal. Product rows from 2020–2024, from 2025, or from 2026 before the start are not the prospective sample. `PRE_START_DATA_ROLE = WARMUP_ONLY`.

## Eligible episodes

A structural episode is eligible only when `episode_active_start >= PROSPECTIVE_START_UTC`.

Warm-up bars may build the previous day, week, or month level and the 24h sigma. They may not open an eligible episode. An episode that is already active at the start is dropped whole. It is not truncated.

The first eligible day episode is the first daily active period that opens at or after the start. The same rule applies to the week and the month. Constructor: `#352` `level_instances` and `build_episodes`, kinds `PDH PDL PWH PWL PMH PML` only, zone half-width `0.0015`, touch number 1 only. No POC, round number, session level, or manual level.

## Pseudo

The half-rotation pseudo is a function of the closed cohort, not a price fixed in real time.

During accrual the permanent pseudo map is not written. At cohort close the exact `#352` `control_episodes` procedure runs inside `(family, structural side)`, ordered by `(start, anchor price, id)`, with the same collision rule. No new seed, no distance rematch, no replacement control.

The pair map is frozen before any transition is computed. It records identities, timestamps, family, side, and path presence. It does not record `RV_POST`, a transition, or a pair delta. Its digest is part of the freeze. The evaluator then runs once, or not at all.

## Path

A pair is path-complete when both arms have finite positive closes for the 12 pre returns, the touch close, and the 12 post returns. Missing bars stay missing. No interpolation, no forward fill, no nearest bar, no synthetic close. A nonpositive or nonfinite close makes the arm unusable. No epsilon.

## Data

Reference instrument: Binance USD-M BTCUSDT perpetual.

Forward bars come from the existing Signalbot collection when it preserves timestamp, OHLC, completeness, and exchange identity. The aggregation is `scripts.research.dh1.data.aggregate_1m_to_5m`: a UTC 5m bin enters only when all five 1m bars are present. RV then drops volume and taker fields and keeps the close.

`CORE_BTC_BINANCE_V0` is the discovery surface. It is not a prospective source. `beta_hist_bars_5m` and live `klines_1m` may supply bars, but a row is eligible only after the start rule and the episode-start rule. Generation time after the freeze is what makes a row prospective, including a row that landed in an existing production table.

If a post-start gap must be recovered, the official Binance USD-M kline archive or API may fill only open times `>= PROSPECTIVE_START_UTC`. Each interval is appended to `LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_RECOVERY_V1.jsonl` with source and range. Outcomes do not choose which gap is filled. Recovery before the start is rejected.

No new database table. The cohort is reconstructed from the frozen start, the immutable bars, the recovery log, and the code version in the manifest. Server restarts do not move the cohort.

## Claim journal

`BETA_CLAIM_JOURNAL_V1` is not reused. That journal records product L1–L3 wording claims, templates, and display links. This unit is one research estimand whose pseudo exists only after the cohort closes. Putting it in `beta_claims` would change that journal. Accrual state lives in the research manifest, the recovery log, and the later pair map.

## Stop

The stop does not look at a p-value, a point estimate, or an interval.

Both floors are required:

- `MIN_MATCHED_PATH_COMPLETE_PAIRS = 600`
- `MIN_COMPLETED_ISO_WEEKS = 104`

Completed weeks are full 7-day blocks from `PROSPECTIVE_START_UTC`. The outcome-blind check runs only at 104, 130, and 156 completed weeks. The first checkpoint that meets both floors is the cohort end. Later bars do not enter.

An episode whose active period ends after the checkpoint is excluded from that checkpoint. The rule is geometric.

If 156 completed weeks still have fewer than 600 matched path-complete pairs, the cohort closes as `PROSPECTIVE_CONFIRMATION_INFORMATION_LIMITED`. The transition is not read. N is not lowered. Another year is not added. An owner decision would be required for any later unit.

## Accrual status

`python -m scripts.research.level_volatility_transition_prospective_confirmation_v1.status` returns protocol state, start, completed weeks, structural counts when a forward panel is bound, the next checkpoint, and `exact_outcome_read = false`.

It does not return mean post-RV, a transition, a pair delta, a preliminary interval, a p-value, or an expansion-rate difference. Until a forward panel is bound, pair counts stay null rather than being filled from any historical sample.

## Peek

If the exact prospective `#368` statistic is intentionally computed before the frozen stop, `PROSPECTIVE_PEEK_CONTAMINATED = true` and the unit is no longer `PRISTINE_CONFIRMATION`. It may later be described only as an exposed or reanalysis class.

Ordinary product observations of the same market are not that peek. The forbidden read is this estimand.

## Epochs

Epochs are successive 26-week blocks from the start: `E1` through `E6`. An epoch is eligible at 80 or more matched usable pairs.

- 3 eligible epochs: all 3 positive.
- 4 eligible epochs: at least 3 of 4 positive, and every nonpositive epoch has absolute effect below `log(1.10)`.
- 5 eligible epochs: at least 4 of 5 positive.
- 6 eligible epochs: at least 5 of 6 positive.
- Fewer than 3 eligible epochs: `TEMPORAL_STABILITY_INFORMATION_LIMITED`.

Leave-one-epoch-out runs only when the pooled point is at least the bar and the interval excludes 0. Every estimable leave-one-epoch-out mean (retained N at least 80) must stay positive. No separate significance test.

Family (`DAY`, `WEEK`, `MONTH`) and side (resistance, support) use the `#368` material-contradiction rule: opposite signs fail the candidate only when both absolute effects are at least `log(1.10)`. A smaller positive magnitude does not. There is no family winner and no side winner. `MONTH` is not required when it is small.

## Inference

Paired ISO-week block bootstrap. The atomic unit is the frozen real/pseudo pair. `B = 2000`. Seed `20261026`, chosen before any prospective outcome. 95% percentile interval. A two-sided Wald p from the bootstrap standard error may be reported beside it. One primary claim. No FDR.

## Routes

Frozen now:

- `PROSPECTIVE_CONFIRMATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION` only when the point is positive, the point is at least `log(1.10)`, the interval excludes 0, epoch stability passes, every estimable leave-one-epoch-out mean stays positive, day/week and resistance/support show no material contradiction, the N and week floors were met, there was no exact-claim peek, and provenance did not fail.
- `PROSPECTIVE_POSITIVE_BELOW_PRACTICAL_BAR` when the point is positive, the interval excludes 0, and the point is below `log(1.10)`. Not a pass. The bar is not lowered.
- `PROSPECTIVE_CONFIRMATION_INCONCLUSIVE` when the floors were met, the interval includes 0, and the sign is not a predeclared contradiction. The record states whether the interval still contains the historical 10% scale.
- `PROSPECTIVE_CONFIRMATION_CONTRADICTS_HISTORY` when the point is less than or equal to 0 and the interval excludes 0.
- `PROSPECTIVE_CONFIRMATION_INFORMATION_LIMITED` only from the frozen information or provenance conditions, including the 156-week shortfall and fewer than 3 eligible epochs.
- `PROSPECTIVE_CONFIRMATION_UNSTABLE` when the point and the interval would otherwise support the claim but a frozen stability clause fails. This name is fixed now so a later result cannot invent it.

A pass sets `PRODUCT_INTEGRATION_CANDIDATE = YES` in the research record only. That means an owner may separately authorize a volatility-transition field. It does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, scoring, the findings registry, or deploy. No badge, alert, probability, or confidence score.

Claim ceiling on a pass remains L2. Prospective confirmation is not L3. L3 would be a probability claim with its own calibration. The evidence label on a pass is `PROSPECTIVELY_CONFIRMED_LEVEL_VOLATILITY_TRANSITION`. That is process provenance, not user-facing confidence wording.

The chain, if a pass later occurs, is discovery, then the time-disjoint BitMEX replication, then this prospective confirmation. This design does not declare that pass.

## Evaluator

Until the manifest, the closed cohort, the stop, and a digest-matched pair map all exist, and no peek flag is present:

`REFUSING_PREMATURE_PROSPECTIVE_EVALUATION`

After one legal execution, a second call is `REFUSING_RERUN`.

`close_cohort` is a separate command. Reaching the stop does not evaluate by itself. Today that command refuses because the floors are not met.

## Claim ceiling and product

L0–L4 are unchanged. No L5. No product change in this setup task.
