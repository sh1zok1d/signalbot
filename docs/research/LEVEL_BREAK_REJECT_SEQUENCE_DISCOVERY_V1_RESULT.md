# LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. The question is whether, after a structural first touch reaches one frozen barrier, the opposite barrier is reached inside the same 4h event more or less often than after the matched pseudo-price touch. This note does not change the product. It does not name a false break, an accepted break, or a current probability.

## Provenance

Design SHA `fcfc3e438e4cbea4213e8284a4cb851234e030f0`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
Exposure `DISCOVERY_ONLY`. First-event labels were already exposed. Sequence outcomes read: True. Claim ceiling `L2`.

Dependencies, not rewritten:

- touch: `dfc9e0f04358de15606382472badeb5aee787039`
- acceptance path: `b005eaac895d3a4c644d16101d2e5eb7d2ff8d5f`
- resolution clock: `3ad8431ee62cc48c86eeaeface9b50884babfbbe`

The parent chain is #352 through #365. A second evaluator invocation returns `REFUSING_RERUN`.

## Novelty

The object is the sequence of the exact #352 BREAK and REJECT barriers after the first one-sided hit, inside the original 4h event. It is not H02: H02 tested a generic range breach, a close back inside, and a later normalized return across 45 cells, and that search failed. It is not the V2 false-break lifecycle and not V2 `CONFIRMED_BREAKOUT`. It is not the #362 path-memory predictor. It is not the #365 resolution clock: that unit stops at the first barrier, and this unit starts after it. The two results are not combined in one test.

Atlas row `PRICE_STRUCTURE.levels`, column `CANDLES`. Reopen key `NEW_MECHANISM`. `BLOCKED_REOPENING_FAILED_BREAKOUT_SEQUENCE` does not apply.

## Data and classes

Price OHLC only. `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. No volume, taker, open interest, spot, other venue, book, or liquidation series.

Event window `[2020-02-01T00:00:00Z, 2025-01-01T00:00:00Z)`. No 2025/2026 object was requested.

Stage 1 is the parent `classify` label. Stage 2 scans only bars after that first one-sided hit, through `j+48`. A later bar that hits both barriers counts as the opposite hit. The first resolving bar that hits both is `FIRST_AMBIGUOUS` and is excluded from both conditional primaries. No order inside a 5m bar is inferred.

The pseudo event is the #352 half-rotation. Real and pseudo rows of one episode move together in the week bootstrap. They do not have to share a first-event type. Seed `20261022`. Draws 2000. Practical scale 5 percentage points. BH q = 0.10 across P1 and P2 only.

## Cohort

Structural episodes 4076. Real legitimate first touches 1919. Pseudo legitimate 1962. Incomplete 4h paths: 0 and 0. Matched pairs 1231. Unusable windows 0. Labeled pairs 1231. Weeks 254.

Parent first events, already exposed, and reproduced by this census:

Real: BREAK 579, REJECT 539, AMBIGUOUS 6, NEITHER 107.
Pseudo: BREAK 467, REJECT 549, AMBIGUOUS 8, NEITHER 207.

Both pre-sequence gates pass. Both directions were read.

## Six-class table

Shares are of the 1231 labeled pairs. The six counts sum to 1231 on each arm.

| Class | Real N | Real share | Pseudo N | Pseudo share |
|---|---:|---:|---:|---:|
| BREAK_NO_LATER_REJECT | 474 | 38.51% | 397 | 32.25% |
| BREAK_THEN_REJECT | 105 | 8.53% | 70 | 5.69% |
| REJECT_NO_LATER_BREAK | 430 | 34.93% | 445 | 36.15% |
| REJECT_THEN_BREAK | 109 | 8.85% | 104 | 8.45% |
| FIRST_AMBIGUOUS | 6 | 0.49% | 8 | 0.65% |
| NEITHER | 107 | 8.69% | 207 | 16.82% |

## P1 — later REJECT after FIRST_BREAK

Real reversal rate 18.13% (105/579). Pseudo 14.99% (70/467). Delta +3.15 pp. 95% interval −1.23 to +7.56 pp. p = 0.160. q = 0.320. Weeks 254. Bootstrap 2000/2000.

The interval includes 0. The point is under 5 pp. The contrast is not statistical. Class `NONE`.

Years, point deltas, real-touch year: +2.04 (109/92), +4.81 (160/123), +8.26 (126/102), +7.39 (86/68), −7.64 (98/82). Five years are eligible. Four share the pooled positive sign, so the frozen year rule passes. 2024 is opposite and larger than 5 pp. That fact is reported. The year rule was not rewritten, because the five-year rule is a 4/5 sign rule.

Leave-one-year-out: +3.42, +2.66, +1.72, +2.41, +5.46. All five keep the sign.

DAY +2.32 pp (498/405). WEEK +7.91 pp (72/52). MONTH +12.22 pp (9/10) is under 30 and is diagnostic. Resistance +3.13 pp (334/259). Support +3.44 pp (245/208). No material family or side contradiction.

## P2 — later BREAK after FIRST_REJECT

Real reversal rate 20.22% (109/539). Pseudo 18.94% (104/549). Delta +1.28 pp. 95% interval −3.27 to +5.95 pp. p = 0.578. q = 0.578. Weeks 254. Bootstrap 2000/2000.

The interval includes 0. The point is under 5 pp. The contrast is not statistical. Class `NONE`. q failure is not an unstable structure.

Years: +9.27 (118/98), +2.69 (140/156), −4.40 (97/114), −0.45 (85/88), −2.25 (99/93). Two of five eligible years share the pooled sign. The year rule fails. Leave-one-year-out: −0.73, +0.71, +2.65, +1.61, +2.04. Omitting 2020 flips the sign.

DAY +2.79 pp (466/472). WEEK −5.95 pp (61/68). The signs differ, and only WEEK clears 5 pp, so the frozen material-opposite rule does not fail. MONTH −16.67 pp (12/9) is under 30. Resistance −3.33 pp (275/292). Support +5.87 pp (264/257). The signs differ, and only support clears 5 pp, so the same rule does not fail. There is no side-specific candidate.

## Descriptive, not primary

Two-sided traversal, including the first ambiguous bar: real 17.87% (220/1231), pseudo 14.78% (182/1231), point delta +3.09 pp.

One-sided resolution: real 73.44% (904/1231), pseudo 68.40% (842/1231), point delta +5.04 pp. This share is of every labeled pair, including `NEITHER`. Real events are already known to reach a first barrier more often. The conditional one-sided rates given the first event are the complements of P1 and P2, so their deltas are −3.15 pp and −1.28 pp. The unconditional 5.04 pp figure does not create a candidate.

Reversal delay, minutes from the first barrier to the later opposite barrier. No threshold was tested.

| Sequence | Arm | N | p25 | median | p75 |
|---|---|---:|---:|---:|---:|
| BREAK_THEN_REJECT | real | 105 | 40 | 70 | 135 |
| BREAK_THEN_REJECT | pseudo | 70 | 31.25 | 60 | 118.75 |
| REJECT_THEN_BREAK | real | 109 | 40 | 90 | 145 |
| REJECT_THEN_BREAK | pseudo | 104 | 50 | 87.50 | 151.25 |

## Routing

`NO_INCREMENTAL_SEQUENTIAL_OUTCOME_STRUCTURE`.

P1 class `NONE`. P2 class `NONE`. Overall candidate none. `SUCCESSOR_CANDIDATE = NONE`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

The coarse words BREAK and REJECT are not shown, on this surface, to need a sequential subdivision against the matched pseudo touch. A 3 pp conditional gap is inside the frozen practical bar.

## Claim

L2, discovery only. Among historical structural first touches that reached the BREAK barrier first, the opposite REJECT barrier was later reached 3.15 pp more often than after matched pseudo-price touches, and the interval includes 0. Among first touches that reached the REJECT barrier first, the opposite BREAK barrier was later reached 1.28 pp more often, and that interval includes 0. Neither sentence is a current probability. Neither says that a break was confirmed or that a false-break probability is now X%.

## What was not done

No close-back-inside rule. No 15m, 30m, or 60m cutoff. No acceptance threshold. No volume, spot, or cross-venue feature. No product label. No successor.
