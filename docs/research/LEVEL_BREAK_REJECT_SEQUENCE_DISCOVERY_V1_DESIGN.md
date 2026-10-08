# LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1 — design note

**MODE = DISCOVERY.** Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is frozen before any post-first opposite-barrier sequence is read. A null is a complete result. The unit does not create `ACCEPTED_BREAK`, `FALSE_BREAK`, `CONFIRMED_REJECT`, or a whipsaw alert. It does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, scoring, the findings registry, or deployment. It does not start a volume-at-level study, an acceptance threshold, a close-based false-break rule, a cross-venue composition, or a prospective confirmation.

## Exposure

`FIRST_EVENT_TYPE_ALREADY_EXPOSED = true`.

`POST_FIRST_OPPOSITE_BARRIER_SEQUENCE_NOT_YET_READ = true`.

CORE 2020–2024 already carries the parent first-event labels BREAK, REJECT, NEITHER, and AMBIGUOUS, and it already carries the #365 resolution clock. This unit is `DISCOVERY_ONLY`. It is not a confirmation and it cannot become one on this surface.

The preflight may recount those parent labels with the parent `classify` function, and it may use those counts to apply the denominator gate. Before this note is committed, nothing in the evaluator reads whether the opposite barrier was hit after the first one-sided barrier. The preflight file does not contain a sequence class.

## Question

#352 names a first touch BREAK when the BREAK barrier is the first one-sided barrier inside 4h, and REJECT when the REJECT barrier is first. Two BREAK labels can hide different later paths. One never reaches the REJECT barrier inside the same 4h event. The other reaches it later.

The question is whether, after the first resolution of a structural first touch, the move stays one-sided, or price also reaches the opposite frozen barrier inside the original 4h event.

This is a question about sequence semantics. It is not a predictor question. Primary tests are not conditioned on `END_POSITION_X`, a cross-venue move, open interest, taker flow, or spot.

## Novelty audit

Read before any opposite-barrier sequence: H02 failed breakout, B2-02 boundary interaction, V2 `CONFIRMED_BREAKOUT`, the V2 lifecycle false-break rule, DH level-hold, #362 acceptance path, #365 time-to-resolution, and the Atlas rows `PRICE_STRUCTURE.breakout`, `PRICE_STRUCTURE.levels`, and `PRICE_STRUCTURE.path_shape`.

| Object | What it tested | Why this unit is a different object |
|---|---|---|
| H02 | Generic recent-range boundary breach, then a close back inside, then a later normalized return. Search: 3 lookbacks × 3 overshoot thresholds × 5 horizons = 45 cells. Development verdict `H02_KILL`. | This unit does not use a rolling range, a close back inside, a normalized return, an overshoot threshold, or a horizon search. |
| B2-02 | A closed breakout cell on `PRICE_STRUCTURE.breakout`. | That cell stays closed. This unit does not reopen it. |
| V2 `CONFIRMED_BREAKOUT` | First 5m close beyond a 48-bucket 1h high or low, plus a directional-context gate. Retired as a current formulation. | Different level, different clock, and a qualification flag this unit does not emit. |
| V2 false-break lifecycle | A live setup qualifies, and a later close that crosses or reclaims a setup boundary can invalidate `EARLY_SIGNAL`. | This unit does not use the V2 detector, V2 confirmation, close-based invalidation, candidate age, or the V2 protection buffer. |
| DH level-hold | Whether a level holds for 4h after a first touch. | A hold endpoint is not a sequence of the two frozen barriers. |
| #362 | Whether 15m path history predicts later BREAK after `END_POSITION_X`. Result `NO_INCREMENTAL_PATH_MEMORY_BEYOND_ENDPOINT`. | This unit does not fit another path predictor and does not rescue that null. BREAK and REJECT are the objects being decomposed. |
| #365 | Time until the first barrier interaction. | This unit starts after that first interaction and asks whether the opposite barrier is reached later. The two results are not combined in one test. |
| `PRICE_STRUCTURE.breakout` | Generic breakout continuation, including H02. | The row for this unit is `PRICE_STRUCTURE.levels`. |
| `PRICE_STRUCTURE.path_shape` | Path shape. | The row stays `PRICE_STRUCTURE.levels`. The column is `CANDLES`. |

`BLOCKED_REOPENING_FAILED_BREAKOUT_SEQUENCE` does not apply. The new object is an independently replicated structural first touch, the exact frozen #352 BREAK and REJECT barriers, and the sequence of those barrier first passages inside the original 4h event, compared with the matched pseudo-price touch. Reopen key: `NEW_MECHANISM`. The taxonomy is not edited.

## Data and events

Price OHLC only, `CORE_BTC_BINANCE_V0`, the existing #352 discovery snapshot, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. No volume, taker, open interest, spot, second venue, order book, or liquidation series.

Event window `[2020-02-01T00:00:00Z, 2025-01-01T00:00:00Z)`. Parent coverage is reused. No 2025, 2026, or E1 bar is requested.

Touch 1 only, of PDH, PDL, PWH, PWL, PMH, PML. Level birth, lifetime, merge, zone, approach side, X, the BREAK barrier, the REJECT barrier, the 4h horizon, and the same-bar ambiguity rule are the parent objects. No new barrier is defined.

The pseudo event is the #352 deterministic half-rotation: within `(family, structural side)`, shift `n // 2`, first non-colliding partner. Each source episode keeps its real event and its pseudo event. Both use the same horizon, the same barrier construction, the same first-event scan, and the same post-first scan. This is not a new random control.

## Clock and stage 1

T is the open of touch bar `j`. Bar `j` cannot resolve the event. The scan is `j+1` through `j+48`. Nothing after T+4h is read.

Stage 1 is the parent `classify` label, not a recomputation:

- `FIRST_BREAK`: the first one-sided barrier hit is BREAK.
- `FIRST_REJECT`: the first one-sided barrier hit is REJECT.
- `FIRST_AMBIGUOUS`: both barriers are hit on the same first resolving 5m bar. No order inside that bar is inferred from OHLC.
- `NEITHER`: no barrier by T+4h.

The sequence function raises if its first event disagrees with `classify`.

## Stage 2

This is the new outcome.

If `FIRST_BREAK` is on bar `k`, scan only `k+1 ... j+48` for a later REJECT-barrier hit. A hit is `BREAK_THEN_REJECT`. No hit is `BREAK_NO_LATER_REJECT`.

If `FIRST_REJECT` is on bar `k`, scan only `k+1 ... j+48` for a later BREAK-barrier hit. A hit is `REJECT_THEN_BREAK`. No hit is `REJECT_NO_LATER_BREAK`.

`FIRST_AMBIGUOUS` is excluded from both conditional primaries.

If the first one-sided hit was on an earlier bar and a later bar hits both barriers, the opposite barrier was reached. The class is `BREAK_THEN_REJECT` or `REJECT_THEN_BREAK`. No intra-bar order is required, because the first event is already on an earlier bar.

Every usable event receives exactly one of:

1. `BREAK_NO_LATER_REJECT`
2. `BREAK_THEN_REJECT`
3. `REJECT_NO_LATER_BREAK`
4. `REJECT_THEN_BREAK`
5. `FIRST_AMBIGUOUS`
6. `NEITHER`

There is no seventh class. The labels stay mechanical. `BREAK_THEN_REJECT` is not named a false break. `BREAK_NO_LATER_REJECT` is not named an accepted break.

A missing bar is not a hit and is not filled. A window with fewer than 90% finite bars is unusable. An unusable row inside a matched pair drops the pair and is a data artifact. Any such drop blocks a candidate and routes the unit to `INFORMATION_LIMITED`.

## Primary questions

P1 population: `FIRST_BREAK`. Outcome `LATER_REJECT_AFTER_BREAK` is 1 when the REJECT barrier is hit after that first BREAK and before the original T+4h, else 0.

`Δ_BREAK_REVERSAL = P(real later reject | real FIRST_BREAK) − P(pseudo later reject | pseudo FIRST_BREAK)`.

Positive: real BREAK-first events reach the opposite barrier more often. Negative: they stay one-sided more often. No sign is imposed.

P2 population: `FIRST_REJECT`. Outcome `LATER_BREAK_AFTER_REJECT` is defined the same way for the BREAK barrier.

`Δ_REJECT_REVERSAL = P(real later break | real FIRST_REJECT) − P(pseudo later break | pseudo FIRST_REJECT)`.

P1 asks how durable a BREAK-first event is. P2 asks how durable a REJECT-first event is. They are not forced to agree. One difference and one null is a valid result.

A source pair may be real `FIRST_BREAK` and pseudo `FIRST_REJECT`. That pair contributes to different conditional denominators. The pair is kept together only at resampling.

## Inference

The effect unit is a percentage-point difference. For each primary report the real rate, the pseudo rate, the delta, the 95% interval, p, q, both denominators, and the week-cluster count.

Practical scale: 5 percentage points. A 1–3 pp difference is not enough to justify a new lifecycle state. The bar is not lowered after the result.

Multiplicity: Benjamini–Hochberg across exactly P1 and P2, `q = 0.10`. No secondary metric enters the FDR. If only one primary is estimated, `m = 1` and `q = p`.

Bootstrap: week-block, paired by the real-touch week id. `B = 2000`. Seed `20261022`. Percentile 95% interval. The interval is withheld if fewer than 90% of draws return a delta. No redraw. p is the Wald p from the bootstrap standard error, using `math.erfc`. On each draw the real P1 denominator is rebuilt from resampled real `FIRST_BREAK` rows and the pseudo P1 denominator from resampled pseudo `FIRST_BREAK` rows. P2 is separate. The two arms of one pair do not have to share a first-event type.

## Candidate rule

A primary is a sequence candidate only if all of the following hold:

1. absolute delta at least 5 pp;
2. the 95% interval excludes 0;
3. BH q at most 0.10;
4. the year rule passes;
5. every estimable leave-one-year-out delta keeps the full-sample sign;
6. DAY and WEEK are not materially contradictory;
7. resistance and support are not materially contradictory;
8. no unusable path in the paired sample.

q failure is not an unstable structure. It is no incremental sequence difference.

Class names, research labels only:

- P1 and delta < 0: `BREAK_FIRST_ONE_SIDED_CANDIDATE`
- P1 and delta > 0: `BREAK_FIRST_REVERSAL_CANDIDATE`
- P2 and delta < 0: `REJECT_FIRST_ONE_SIDED_CANDIDATE`
- P2 and delta > 0: `REJECT_FIRST_REVERSAL_CANDIDATE`

These names are not translated into accepted breakout, false breakout, or strong rejection.

A contrast with absolute delta at least 5 pp, an interval that excludes 0, and q at most 0.10, but a failed stability rule, is `STRUCTURE_PRESENT_BUT_UNSTABLE` for the unit if no primary is a full candidate.

## Stability

Eligible slice: at least 30 events in the real conditional denominator and at least 30 in the pseudo conditional denominator.

The slice key is the real touch. Year is the real touch's calendar year. Family is the episode family. Side is the real approach side (`side > 0` resistance, `side < 0` support). The paired pseudo row stays in that slice even when its own timestamp or its own approach side differs. Year, family, side, and leave-one-year-out figures are point deltas. They are not each given a bootstrap interval, and leave-one-year-out is not required to be significant on its own.

Year rule, frozen before the sequence read:

- five eligible years: at least 4 of 5 share the pooled sign;
- four eligible years: at least 3 of 4 share the pooled sign, and every opposite slice is strictly under 5 pp;
- three eligible years: all three share the pooled sign;
- fewer than three eligible years: the year rule fails.

Leave-one-year-out is required for a primary that passes the effect scale, the interval, and q. It passes only when at least three omits are estimable and every estimable omit keeps the pooled sign.

Family: DAY and WEEK. The contradiction that fails the candidate is both estimable, opposite in sign, and both at least 5 pp in absolute value. A smaller opposite point is reported and does not fail. MONTH is diagnostic when its denominator is under 30. There is no family-specific winner.

Side: the same material-opposite rule. There is no side-specific candidate. "Materially contradictory" in the candidate rule, and "opposite signs with adequate information" for side, are this rule: adequate means both denominators at least 30, and material means both absolute deltas at least 5 pp.

## Information gate

Before the sequence read, each primary needs about 300 real and 300 pseudo events in its own conditional denominator. The gate is the parent first-event count: real and pseudo BREAK for P1, real and pseudo REJECT for P2. The threshold is not lowered and the two directions are not pooled.

If one primary fails the gate, that primary is `INFORMATION_LIMITED_BEFORE_SEQUENCE_READ` and its opposite barrier is not scanned. The other primary may be read. If both fail, the evaluator writes `INFORMATION_LIMITED` and does not call the sequence function.

After a read, a contrast is information-limited when either denominator is under 300, the interval is withheld, or the interval is wider than 20 pp. Exception: absolute delta at least 5 pp and an interval that excludes 0 is a candidate or an unstable structure, not an information failure.

## Secondary descriptions

None of these can create a candidate, and none enters the FDR.

`TWO_SIDED_TRAVERSAL`: the event reaches both barriers in sequence, or the first resolving bar is ambiguous. Report the real frequency, the pseudo frequency, and the point delta, with the denominator equal to all labeled matched pairs. Reported only when both primaries were read.

`ONE_SIDED_RESOLUTION`: `BREAK_NO_LATER_REJECT` or `REJECT_NO_LATER_BREAK`. Same denominator. Descriptive only.

The six-class table reports N and share for real and for pseudo separately.

`REVERSAL_DELAY` for `BREAK_THEN_REJECT` is `5 × (opposite bar index − first BREAK bar index)` minutes. The same difference is used for `REJECT_THEN_BREAK`. Report the median, the 25th percentile, and the 75th percentile. No delay threshold is tested. No "fast false break" class is created.

Forbidden after the result: a 15m, 30m, or 60m false-break cutoff, an acceptance cutoff, two closes, three closes, a close back inside the zone, a wick outside then a close inside, consecutive closes outside, and any scan past T+4h.

## Routing and ceiling

Allowed routes:

- `LEVEL_SEQUENTIAL_OUTCOME_STRUCTURE_PRESENT` — at least one primary is a full candidate;
- `NO_INCREMENTAL_SEQUENTIAL_OUTCOME_STRUCTURE` — neither contrast differs materially and stably, including a precise null beside an information-limited arm;
- `STRUCTURE_PRESENT_BUT_UNSTABLE` — effect scale, interval, and q pass, and stability fails;
- `INFORMATION_LIMITED` — denominators or the interval are inadequate, or an unusable path artifact is present, or both pre-sequence gates fail;
- `BLOCKED_REOPENING_FAILED_BREAKOUT_SEQUENCE` — the novelty audit fails. Definitions are not altered to get past that stop.

Maximum claim: `L2 / DISCOVERY_ONLY`. An allowed sentence states a historical rate difference against the matched pseudo touch. It does not say that a break is confirmed, that a false-break probability is now X%, or that an acceptance probability is X%. No L3. No L4. No trade instruction.

`PRODUCT_INTEGRATION_CANDIDATE = NO` even if a candidate passes. Product wording needs a separate owner decision.

One official evaluator run. A second invocation returns `REFUSING_RERUN`. The sequence taxonomy, the horizon, the barriers, the first-event treatment, the 5 pp scale, the FDR, and the candidate rule are not changed after the result. No successor is started.

## Outcome-blind census

Filled from `LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1_PREFLIGHT.json` in this same commit, before any post-first opposite-barrier scan. `outcomes_sequence_read` is false. `post_first_opposite_barrier_sequence_not_yet_read` is true. The counts below are parent first-event labels. They are not sequence classes.

Event window `[2020-02-01T00:00:00Z, 2025-01-01T00:00:00Z)`. Structural episodes 4076. Real legitimate first touches 1919. Outside the window 33. No touch 2124. Incomplete 4h paths 0. Unknown side 0. Unusable X 0.

Pseudo legitimate first touches 1962. No control 0. Pseudo no-touch 2086. Pseudo outside the window 28. Pseudo incomplete 4h paths 0. Unknown side 0. Unusable X 0.

Matched pairs, both legitimate with a complete 4h path: 1231. Weeks 254. Years, by the real touch: 242 / 334 / 258 / 181 / 216. No year outside 2020–2024. Family: DAY 1071, WEEK 138, MONTH 22. MONTH is below the pair-count slice minimum of 30 and stays descriptive until a conditional denominator is checked. Side, by the real approach: resistance 690, support 541.

Parent first-event counts on those 1231 pairs. These labels were already exposed. They are not sequence classes, and the opposite barrier after the first hit has not been read.

Real: BREAK 579, REJECT 539, AMBIGUOUS 6, NEITHER 107, unusable 0.
Pseudo: BREAK 467, REJECT 549, AMBIGUOUS 8, NEITHER 207, unusable 0.

P1 denominator: real BREAK 579, pseudo BREAK 467. Both are at least 300. Gate pass.
P2 denominator: real REJECT 539, pseudo REJECT 549. Both are at least 300. Gate pass.

Both primaries are eligible for the one sequence read after this commit.
