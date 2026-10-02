# SEED-0001 — regular bullish divergence with order-book support: twin preregistration

**Status:** `FROZEN_BEFORE_COUNTS_AND_OUTCOMES`
**Date:** 2026-10-02
**Card:** `SEED0001_REGULAR_DIVERGENCE_BOOK_SUPPORT_V1` (`HYPOTHESIS_ID = SEED0001-RD-V1`)
**Contract:** `HYPOTHESIS_EVALUATION_CONTRACT_V1`
**Machine twin:** `SEED0001_REGULAR_DIVERGENCE_PREREG.json`. It is authoritative for every constant, and its SHA256 is bound in `SCIENTIFIC_TEST_LEDGER.json`.
**Seed record:** `SEED_ABSORPTION_DIVERGENCE_V0.md`

```
TEST_FAMILY_ID (retrospective)   = TF-SEED0001-RD-RETRO1
TEST_FAMILY_ID (prospective)     = TF-SEED0001-RD-PROSP1
SEARCH_FAMILY_ID                 = SF-OWNER-SEEDS
PRIMARY_CELLS                    = 2 (P1 = A vs B, P2 = A vs C)
MARKET_OUTCOMES_COMPUTED         = false
PROTECTED_2025_2026_OPENED       = false
OUTCOME_EVALUATOR_IMPLEMENTED    = false
NEXT_UNIT                        = SEED0001_OUTCOME_BLIND_FEASIBILITY_COUNT_PASS
```

This file freezes the retrospective card and the prospective confirmation design together, before any count or outcome. The owner's decisions of 2026-10-02 are the design inputs (§11). The next unit counts episodes only; it never computes an outcome. Opening outcomes needs a separate owner authorization.

## 1. Evidence labels

| Surface | Label | Meaning |
|---|---|---|
| BTCUSDT perp, decisions 2023-01-01 .. 2024-12-28 | `RETROSPECTIVE_EVIDENCE` | Never a holdout, never a final confirmation. The rule reached the project as a working scheme from this period, and 2024 is owner-exposed. |
| Binance UM `bookDepth` within 5% | `RETROSPECTIVE_PROXY_TO_OWNER_OBSERVABLE` | The owner watched a Hyblock spot bid/ask 0–5% indicator. This is the perp book, close but not identical. |
| BTCUSDT perp, decisions from 2026-10-05 | `PROSPECTIVE_CONFIRMATION` | Episodes after the freeze, same frozen code (§9). |
| ETHUSDT perp, same periods | robustness only | Never pooled; cannot change the verdict (§8). |

A long-history flow surrogate for the book is Track B, a separate card. It is never this card's confirmation.

## 2. Claim

On BTCUSDT perpetual 1h bars, at a confirmed swing low that makes a lower low after a pronounced decline, **arm A** (book bid support within 5% AND regular bullish divergence in at least 2 of 3 families) reaches +1R before −1R within 48h more often than:
- **arm B**, support without divergence (P1);
- **arm C**, divergence without support (P2).

Both comparisons are made after the frozen adjustment set (§5).

- **Claim type:** `INCREMENTAL`.
- **Target class:** `UNCONDITIONAL`. The swing-low population is part of the event definition, not a regime.
- **Not the claim:**
  - taker imbalance predicts future return (that is H05);
  - divergence alone predicts a bounce;
  - book support alone predicts a bounce;
  - mean reversion after a decline. A beating D is ordinary mean reversion and is never evidence for this card.

## 3. Event (point-in-time)

All times are UTC.

| Step | Frozen definition |
|---|---|
| Bars | 1h bars `[h, h+1h)` from 1m klines. A bar needs all 60 minutes, otherwise it is incomplete and splits the series. Indicators restart in each complete segment, and an episode needs its pivot at least 720 bars into its segment. |
| Swing low at bar i | `low_i` is below each of the 3 previous lows and not above any of the 3 next lows. |
| Decision time T | The close of bar i+3, when the swing low is confirmed. Every episode field uses bars and book hours up to i+3 only. |
| Pronounced decline | `max(high, bars i−48..i) − low_i ≥ 3.0 × ATR14(i)` (Wilder ATR). |
| Comparison pivot j | The most recent swing low with `i−48 ≤ j ≤ i−5`. The episode needs `low_i < low_j` (lower low); otherwise it is outside the population. |

**Divergence families.** Each compares values at the pivot bars i and j, with strict inequalities and no minimum difference.
- **RSI:** Wilder RSI14 and RSI21 are both higher at i than at j.
- **MACD:** the MACD line, EMA12 − EMA26 of close, is higher at i. EMA alpha is 2/(n+1), seeded with the first close. The signal line is unused.
- **CVD:** the net taker delta `Σ(2·taker_buy − volume)` over bars j+1..i is above zero.

Divergence = at least 2 of the 3 families.

**Book support.**
- **Hourly imbalance.** The mean, over snapshots in `[h, h+1h)`, of `(bid5 − ask5)/(bid5 + ask5)`. `bid5` and `ask5` are the cumulative notional at percentage −5 and +5. An hour needs at least 60 valid snapshots.
- **Support.** Some hour among i+1, i+2, i+3 has an imbalance that is:
  - above zero (a green bar); and
  - at or above the 0.80 quantile (numpy linear) of hours i−719..i, with at least 480 of them present.

**Arms:**

| Arm | Support | Divergence |
|---|---|---|
| A | yes | yes |
| B | yes | no |
| C | no | yes |
| D | no | no |

**Exclusions.** These are applied first match first, and each one is counted:
- kline window incomplete;
- not a pronounced decline;
- no comparison pivot;
- not a lower low;
- risk width `close_{i+3} − low_i` below 0.25 ATR14(i);
- a support hour missing;
- book baseline immature.

**Decision window:** `2023-01-01T00:00Z ≤ T ≤ 2024-12-28T00:00Z`. This keeps `T + 96h` inside 2024, so every primary and sensitivity window ends before the protected surface.

**Point-in-time test.** For every episode, data truncated at T reproduce the identical record. A shock to every bar after T changes nothing. Both are tested in `tests/research/test_seed0001_regular_divergence.py`.

## 4. Endpoints (frozen now, not computed by the feasibility pass)

**Bracket:**
- **Entry:** E is the close of bar i+3.
- **Stop:** S is `low_i`. The stop event is the first 1m bar after T with `low < S`.
- **Risk:** `R = E − S`.
- **Target:** the first 1m bar with `high ≥ E + k·R`.

**Rules:**
- **Same minute:** stop and target in the same minute count as the stop.
- **Timeout:** reaching neither within the cap counts as failure.
- **Missing minute:** a missing minute in the window makes that endpoint unavailable. This is decided from timestamps only and is reported.

**Endpoints:**

| Endpoint | Role |
|---|---|
| `Y1_48H`: +1R before −1R within 48h | **primary** |
| `Y2_48H`: +2R before −1R within 48h | secondary |
| `Y1_96H`, `Y2_96H` | sensitivity |

The secondary and sensitivity endpoints never change the primary conclusion.

## 5. Adjustment set (frozen; nothing may be added after outcomes)

| Role | Variable | Computed at T |
|---|---|---|
| prior realized volatility | `log RV24` | SD of the 24 hourly log returns ending at bar i+3 |
| time of day | `sin`, `cos` of the UTC hour of T | — |
| decline magnitude (lagged target) | `DECLINE_ATR` | `(max high i−48..i − low_i) / ATR14(i)` |
| pre-decision net buy/sell flow | `NETFLOW24` | `Σ(2·taker_buy − volume) / Σ volume`, 24 bars ending at i+3 |
| bracket width (added at design) | `RISK_ATR` | `(close_{i+3} − low_i) / ATR14(i)` |

`RISK_ATR` is a card-specific addition: a 48h timeout counts as failure, so the bracket width relative to volatility moves the hit rate mechanically. The owner may strike it before outcomes are opened.

## 6. Primary test family and gates

**Model.** A linear probability model on all eligible BTC episodes:
- **Specification:** `Y1_48H ~ 1 + A + B + C (D reference) + the §5 covariates`.
- **Variance:** CR1 cluster-robust, with clusters = UTC weeks starting Monday 00:00 and a t reference on G − 1 degrees of freedom.

**Statistical gate.** P1 = β_A − β_B and P2 = β_A − β_C, with two-sided p-values, Holm at family alpha 0.05. The gate passes only if:
- the smaller p ≤ 0.025 and the larger p ≤ 0.05; and
- both estimates are positive.

These are not support for the claim:
- A beating D;
- one passing contrast;
- a high raw A rate.

**Practical gate (costs).** The round-trip cost is 0.10%: 0.04% taker fee and 0.01% slippage, per side. Both rules must hold:
- both adjusted risk differences are at least `MIN_MEANINGFUL_EFFECT = 0.10`;
- the adjusted A rate is at least the mean, over A episodes, of the 1R:1R break-even rate `0.5 + (0.0010 / RISK_FRACTION) / 2`, with timeouts counted as full losses.

**Epoch gate (V1 §4).**
- **Epochs:** 2023H1, 2023H2, 2024H1 and 2024H2. No half-year needs to be individually significant; the epochs exist to detect concentration.
- **Tests, run on each contrast:**
  - **Heterogeneity:** a heterogeneity test against a block permutation of whole weeks across epochs (seed 20261003, 2000 draws, alpha_het 0.05).
  - **Opposite sign:** an opposite-sign test at one-sided p < 0.05.
- **Low power:** if the feasibility pass finds the gate `NOT_ASSESSABLE`, the gate cannot fail the card. Records then say heterogeneity could not be reliably assessed at this N, never "stable".
- **Diagnostics only:** the largest epoch share and leave-one-epoch-out estimates.

**Secondary and sensitivity (descriptive):**
- S1: `Y2_48H`;
- S2: `Y1_96H`;
- S3: `Y2_96H`;
- S4: `Y1_48H` with 48h overlap-chain clusters instead of weeks;
- raw arm rates, and A vs D.

## 7. H05 and closed-card distance

**H05.** The CVD family is close to the rejected `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN`. This card does not test whether taker imbalance predicts future return, and H05 stays closed. Why this card is different:
- **The object** is the order-book support × regular divergence state. CVD is one of three divergence families and is never sufficient on its own.
- **The comparison** stays within one swing-low lower-low population, between arms that differ in support or in divergence.
- **Incremental value** is required:
  - over support alone (P1);
  - over divergence alone (P2);
  - over pre-decision net flow (`NETFLOW24` is in the adjustment set).

**Other closed cards:**
- **H02 (killed):** mean reversion, which is the A-vs-D story this card refuses as evidence.
- **H03 (rejected):** exhaustion after an impulse. It is close to the decline filter, which is an eligibility condition shared by all arms.

This card rescues none of them; its provenance is prior owner practice.

## 8. ETH robustness

ETHUSDT perps run under exactly the same frozen definitions, constants and code:
- no tuning on BTC followed by a change for ETH;
- no change after seeing ETH;
- ETH is reported separately and never pooled;
- ETH cannot rescue BTC or change the verdict.

Labels: `ETH_SAME_DIRECTION`, `ETH_NOT_SAME_DIRECTION` or `ETH_INSUFFICIENT`.

## 9. Prospective confirmation (frozen now)

| Field | Value |
|---|---|
| Cohort | BTC episodes with decision time T ≥ `2026-10-05T00:00Z`, frozen detector and constants |
| Stop | First of: the decision time of the **30th Arm-A episode**, or the deadline **`2028-10-05T00:00Z`** |
| Minimum | 20 Arm-A episodes. Below it at the deadline the result is `INCONCLUSIVE`. Extending is a new preregistration on later data. |
| Monitoring | Counts only (eligibility funnel and arm counts). No outcome, effect estimate or test statistic before the stop. |
| Analysis | One analysis, after every cohort window plus 96h has closed. Same model, covariates and clusters. One-sided tests in the discovery direction, Holm over P1/P2 at 0.05, plus the practical gate. |
| Opening | A separate, explicit owner decision (an execution permit). No 2026 outcome may influence any retrospective definition. |

**Protected segment.**
- **Which decisions:** those before 2027-01-01, which fall inside protected 2026.
- **Allowed now:** their archive objects may be acquired and pinned, by checksum and timestamp metadata only, with no value parsed.
- **Needs an owner decision:** running the detector on them, even counts-only, needs an explicit owner decision under the protected-data rules.

**Product exposure.**
- **Beta.** The beta V0.3 briefing does not compute or show this state or any statistic of it. If a product surface starts to, that is recorded before the stop, with its first date.
- **Owner.** The owner sees live charts and may trade the rule. The rule and code are frozen, so that cannot change the cohort. The label stays `OWNER_UNBLINDED_TO_LIVE_CHARTS`.

## 10. Outcome-blind feasibility rule (next unit)

**Allowed:** the next unit computes, for BTC and separately for ETH:
- the funnel;
- A/B/C/D counts and distinct decision dates;
- counts by half-year;
- weekly-cluster and 48h overlap-chain structure;
- covariate support (per-arm summaries and A-vs-B and A-vs-C SMDs);
- the Holm thresholds;
- conjunction power and MDE for P1+P2, under the frozen profile;
- epoch-heterogeneity assessability;
- prospective planning power at 30 and 20 A episodes.

**Must not compute:**
- future return;
- +1R/−1R or +2R/−1R;
- MFE/MAE;
- any post-decision price field.

**Power profile `SEED0001_BINARY_POWER_PROFILE_V1`.**
- **Synthetic outcomes** on the real arm × week layout:
  - the comparator rate is 0.50;
  - A is 0.50 + δ.
- **Two profiles:**
  - **BASE:** a weekly probit shock shared by all arms, latent ICC 0.10;
  - **STRESS:** an independent (week × arm) shock, latent ICC 0.25.
- **Settings:**
  - 2000 replicates, seed 20261002;
  - δ grid 0.025..0.40;
  - target power 0.80;
  - the planning effect equals `MIN_MEANINGFUL_EFFECT = 0.10`, reported at 50%, 75% and 100%.

**Verdict.** First match wins:
1. BTC A episodes < 40 or A distinct decision dates < 30 → `INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR`.
2. Max |SMD| of a frozen covariate, A vs B or A vs C, > 1.0 → `INCONCLUSIVE_SAMPLE / NUISANCE_SUPPORT_INSUFFICIENT`.
3. STRESS conjunction power at 0.10 < 0.80 → `INCONCLUSIVE_SAMPLE / INFORMATIONALLY_WEAK`.
4. Otherwise → `FEASIBLE_FOR_OUTCOME_OPENING_REQUEST`. Outcomes still need a separate owner authorization.

**Limits of the rule:**
- The 40/30 floor is a hard floor, not evidence of power.
- Definitions do not change after the counts, whatever they are.

**Compiler.** `GV0R02_SCHEMA_V1` has no model-based cluster-robust inference class. The pass therefore:
- runs the class-agnostic V1 checks (definitions, protected window);
- computes power for the frozen procedure directly.

The prospective surface starts inside protected 2026, so the compiler is expected to raise `PROTECTED_SURFACE_DECISION_REQUIRED`. That matches the owner's rule that the protected segment needs a separate decision.

## 11. Owner decisions recorded (2026-10-02)

1. **Confirmation is prospective.**
   - The 2023–2024 test is retrospective evidence only.
   - The prospective design is frozen here.
   - The stop is 30 Arm-A episodes or a fixed deadline, the deadline recorded before opening.
   - No faithful-observable replacement by a surrogate.
2. **Feasibility floor.**
   - The floor is 40 A episodes and 30 distinct days, and it is a hard floor only.
   - Power inadequate means `INCONCLUSIVE_SAMPLE / INFORMATIONALLY_WEAK`.
   - Definitions are not weakened to increase N.
3. **ETH** is robustness only, under identical definitions (§8).
4. **Primary family:** exactly P1 and P2 on +1R/−1R within 48h, with a predeclared multiplicity correction, and both are needed. +2R and 96h are secondary.
5. **Adjustment set:** prior RV, time of day, decline magnitude and pre-decision net flow, frozen before outcomes.
6. **H05 distance** is stated (§7), and H05 stays closed.
7. **Four descriptive half-year epochs.** Primary inference is the clustered analysis.
8. **Scope of this task:** documentation, the PIT detector and an outcome-blind count pass. Outcomes stay closed until a separate owner authorization.

**What was chosen at design, inside those decisions:**
- the 1h primary timeframe (4h and 1D are separate future cards);
- L = R = 3 pivots;
- the 3 ATR decline over 48 bars;
- the j window i−48..i−5;
- the MACD line, not the histogram;
- the P80 + positive support rule;
- the 0.25 ATR minimum risk;
- `RISK_ATR`;
- weekly clusters;
- the 0.10 practical bar;
- the power profile;
- the start date 2026-10-05 and the deadline 2028-10-05;
- the minimum of 20.

Each was fixed before any count. None may change after.

## 12. Code identity

| File | Role |
|---|---|
| `scripts/research/seed0001_regular_divergence_lib.py` | PIT detector, SHA256 in the JSON twin |
| `scripts/research/seed0001_feasibility_lib.py` | feasibility statistics and verdict, SHA256 in the JSON twin |
| `tests/research/test_seed0001_regular_divergence.py` | offline tests: indicators, pivots, funnel, truncation invariance, protected guard, prereg and ledger binding |

The outcome evaluator is not implemented. It is written and frozen before any outcome-opening request.

**Before this freeze**, only format probes touched market files:
- the BTCUSDT bookDepth file of 2023-01-01 was opened and its first rows were read to learn the columns;
- the 2022-12-31 file was confirmed absent;
- two `.CHECKSUM` files were fetched.

No kline value and no outcome was read.
