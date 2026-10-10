# MULTISCALE_ADAPTIVE_OCCUPANCY_V2 — design and synthetic adequacy report

**Date:** 2026-10-10. **Author:** chief architect, on the owner's decision of 2026-10-10.
**Status:** `DESIGN_STILL_INFORMATIONALLY_INSUFFICIENT`. **No market outcome was read.** V2 is not frozen for market evaluation, and no preflight was built.
**Records:**
- protocol `MULTISCALE_ADAPTIVE_OCCUPANCY_V2_SYNTHETIC_ADEQUACY_PROTOCOL.md`, frozen at commit `6e1bc6a4` before the Monte Carlo summary;
- full results `MULTISCALE_ADAPTIVE_OCCUPANCY_V2_SYNTHETIC_ADEQUACY.json`;
- code `scripts/research/multiscale_occupancy_v2/`;
- tests `tests/research/test_multiscale_occupancy_v2.py`.

## 1. Question and object

**Question:** can a low-variance, past-only multiscale occupancy model extract incremental next-hour directional forecast information when the useful occupancy timescale changes through time?

**Object:** one ridge logistic model with all seven OCC_L at once. It adapts its **weights** by retraining at each 28-day block. No lookback is picked.

**What stays as it was:**
- The fixed OCC_4H keeps its status `HISTORICALLY_REPLICATED_BUT_NOT_MODERNLY_STABLE`.
- The V1 hard selector stays unexecuted (`DESIGN_INFORMATIONALLY_INSUFFICIENT / OUTCOME_NOT_READ`).

## 2. Model, inputs, baseline

**OCC inputs:** OCC_1H, 2H, 3H, 4H, 6H, 8H, 12H.
- Exact V1 definition: box over n = 12L bars including T; mean of the n−1 previous normalized closes; the current close excluded; undefined for a flat box or a hole.
- No new scale, EMA, VWAP, thirds, threshold or nonlinearity.

**Baseline B1, unchanged:** RP4H, RET_4H, RV_4H, RET_1H, RET_15M, as [RP4H−0.5, RET_4H/RV, RET_1H/RV, RET_15M/RV, log RV]. Expanding window, ridge 1.0.

**Comparators:**
- CLIMATOLOGY, BASELINE_B1 and STATIC_OCC_4H (expanding);
- the V1 hard selector, diagnostic only;
- the V2 architecture's EXPANDING twin, a diagnostic of the value of adaptation.

**V2 structures tested:**
- **JOINT:** one ridge logistic on [B1, all seven OCC] over the memory window. B1 slopes keep ridge 1.0; the OCC slopes get λ_occ.
- **OFFSET:** the expanding B1 fit is a fixed offset, plus a no-intercept ridge overlay on the seven OCC over the memory window.

**Mechanics:**
- Standardization (weighted mean and sd) is fitted on training rows only; clip ±5.
- Newton-IRLS in a real run.

## 3. Regularization and memory candidates (synthetic only)

**λ_occ ∈ {1, 1e3, 1e4}** (none / moderate / strong).
- The data curvature of a standardized slope is about 0.25·n, i.e. 9k–60k here. So the example grid {0.1, 1, 10} would all mean "no shrinkage".

**Memories:**
- TRAIL_52 and TRAIL_104: up to M weeks;
- EWMA with half-life 26 weeks: effective sample ≈ 75 weeks, mean age ≈ 37 weeks;
- EXPANDING as a non-selectable reference.

**Grid:** 18 selectable candidates plus 6 references. No nested memory selector.

## 4. Outer-block semantics

V1's schedule, unchanged:
- 28-day blocks from Mondays 00:00 UTC;
- models trained on venue rows whose label is realized by the block start and frozen for the block;
- the two venues (BitMEX; Binance 2020–26) never mixed;
- 111 outer blocks and 294,493 outer rows on 440 ISO weeks.

## 5. Synthetic data-generating mechanisms

**Model:** R = N + β_L·g_L (L active) + drift; Y = 1{R > 0}.
- **Noise N:** the next 12 per-bar N(0,1) innovations on the row's own series grid, /√12. It overlaps exactly like real 1h targets.
- **g_L:** OCC_L residualized on the B1 design within each series, at unit variance.

**Worlds:**
- **NULL:** no information.
- **NULL_DRIFT:** no information plus a per-13-week level shift of sd 0.025 (≈ 1 pp of P(UP)); a base-rate nuisance.
- **CONSTANT_OCC_4H.**
- **SWITCHING_OCC_2H_8H:** 2H and 8H alternating every 52 weeks.
- **OCC_OFF_ON:** OCC_4H off and on in alternate 52-week periods.

## 6. Effect magnitude and the observed OCC scale

- **Scale:** ρ = partial Spearman of the active scale with R given the B1 ranks, within its active periods. This is the OCC replication's PRIMARY metric.
- **Observed order ρ_obs = 0.011** (OCC_4H on BitMEX 2016–19).
- **Ladder:** ×0.5, ×1, ×1.5, ×2, ×3, i.e. 0.0055 / 0.011 / 0.0165 / 0.022 / 0.033.
- **Mapping:** β_L = ρ/κ_L. A paired calibration (16 draws, β = 0.03 with and without signal on the same noise) gives:

| scale | κ (partial Spearman per unit β) | SE | β at ×1 | β at ×2 |
|---|---|---|---|---|
| OCC_4H | 0.8485 | 0.0004 | 0.0130 | 0.0259 |
| OCC_2H | 0.9193 | 0.0008 | 0.0120 | 0.0239 |
| OCC_8H | 0.8733 | 0.0007 | 0.0126 | 0.0252 |

V1's preflight β = 0.03 on the raw standardized OCC corresponded to ρ ≈ 0.019 (4H), 0.022 (2H) and 0.023 (8H), about 2× the observed order.

## 7. Monte Carlo

- **Stage 1 (architecture selection):** seed 202610101. 50 replications per signal level and 100 per NULL world: 950 in total.
- **Stage 2 (adequacy):** fresh seed 202610102. 100 per signal level and 200 per NULL world: 1,900 in total.
- **Seeds:** each replication has its own SeedSequence(stage, scenario, level, replication).
- **Route per replication, as a real run would use it:**
  - SUPPORT = ΔBrier(V2 − B1) < 0 with its 95 % ISO-week bootstrap interval < 0 (B 2000, seed `20261124`), ΔLogLoss < 0, and calibration slope ≥ 0;
  - BEAT = ΔBrier < 0.
- **Owner option (not the route):** SUPPORT_CW, the Clark–West-adjusted Brier for nested models.

**Computation:** a vectorized one-step-Newton surrogate of the ridge logistic.
- It reproduces the exact V1 preflight (full IRLS) to ≤ 1e-6 in ΔBrier and in the interval ends, with identical V1 selection shares.
- On the selected V2 over all 111 outer blocks, exact IRLS against the surrogate:

  | replication | exact ΔBrier [95 %] | surrogate ΔBrier [95 %] |
  |---|---|---|
  | 0 | −2.2084e-5 [−6.339e-5, +1.589e-5] | −2.2089e-5 [−6.336e-5, +1.584e-5] |
  | 1 | −6.287e-6 [−4.737e-5, +3.677e-5] | −6.316e-6 [−4.744e-5, +3.664e-5] |

## 8. Stage 1: architecture selection (frozen rule)

Every candidate is eligible: NULL and NULL_DRIFT false support is 0 and P(BEAT) ≤ 0.08. The score (mean P(SUPPORT) in SWITCHING at ×1 and ×2) is small everywhere:

| candidate | score | CONSTANT ×2 | SWITCHING ×2 | SWITCHING ×3 |
|---|---|---|---|---|
| OFFSET / EWMA_26 / 1e4 | 0.070 | 0.40 | 0.14 | 0.74 |
| **JOINT / TRAIL_104 / 1e4** | 0.040 | 0.54 | 0.08 | 0.64 |
| OFFSET / TRAIL_104 / 1e4 | 0.030 | 0.40 | 0.06 | 0.50 |
| OFFSET / TRAIL_52 / 1e4 | 0.010 | 0.18 | 0.02 | 0.14 |
| every λ 1 or 1e3 candidate | ≤ 0.000 | ≤ 0.14 | 0.00 | ≤ 0.24 |
| *reference JOINT / EXPANDING / 1e4* | *(not selectable)* | *0.86* | *0.42* | *0.98* |
| *STATIC_OCC_4H* | — | *0.88* | *0.08* | *0.24* |

- **Tie band:** within 0.05 of the best are OFFSET/EWMA_26 and JOINT/TRAIL_104 and OFFSET/TRAIL_104, all at 1e4.
- **Secondary score** (CONSTANT and OFF_ON at ×1 and ×2): 0.135, 0.130, 0.115.
- **Selected: `V2 | JOINT | TRAIL_104 | λ_occ 1e4`.**
- **Ridge:** the strongest ridge is best in every family. 1e4 is the edge of the predeclared grid (disclosed in the protocol §9).

## 9. Stage 2: adequacy of the selected architecture (fresh seeds)

**P(SUPPORT) / P(BEAT) / mean ΔBrier vs B1** (negative is better):

| world | ×0.5 | ×1 | ×1.5 | ×2 | ×3 |
|---|---|---|---|---|---|
| CONSTANT_OCC_4H | 0.00 / 0.04 / +2.6e-5 | 0.00 / 0.24 / +1.2e-5 | 0.05 / 0.77 / −1.5e-5 | **0.55** / 1.00 / −5.4e-5 | 1.00 / 1.00 / −1.5e-4 |
| SWITCHING_OCC_2H_8H | 0.00 / 0.04 / +3.0e-5 | 0.00 / 0.12 / +2.2e-5 | 0.01 / 0.27 / +9.0e-6 | **0.06** / 0.72 / −1.4e-5 | 0.68 / 1.00 / −7.0e-5 |
| OCC_OFF_ON | 0.00 / 0.04 / +3.0e-5 | 0.00 / 0.03 / +2.7e-5 | 0.00 / 0.13 / +2.0e-5 | 0.00 / 0.19 / **+1.2e-5** | 0.05 / 0.70 / −1.3e-5 |

**Nulls:**

| world | P(SUPPORT) | P(BEAT) | P(WORSE) | mean ΔBrier |
|---|---|---|---|---|
| NULL | 0.000 | 0.000 | 0.48 | +3.1e-5 |
| NULL_DRIFT | 0.000 | 0.035 | 0.48 | +3.3e-5 |

**ΔBrier distribution (V2 − B1; 5 % / 50 % / 95 %):**

| world | distribution |
|---|---|
| NULL | +1.1e-5 / +3.2e-5 / +5.2e-5 |
| CONSTANT ×1 | −2.2e-5 / +1.3e-5 / +3.9e-5 |
| CONSTANT ×2 | −9.0e-5 / −5.1e-5 / −1.8e-5 |
| SWITCHING ×1 | −1.1e-5 / +2.3e-5 / +4.8e-5 |
| SWITCHING ×2 | −5.0e-5 / −9.3e-6 / +1.7e-5 |
| SWITCHING ×3 | −1.1e-4 / −6.6e-5 / −3.1e-5 |
| OFF_ON ×2 | −1.8e-5 / +1.1e-5 / +3.8e-5 |

**Against STATIC_OCC_4H:**
- V2 is worse everywhere except SWITCHING, where it beats STATIC in 62 % of draws at ×2 and 100 % at ×3.
- The mean V2 − STATIC is +4.7e-5 in CONSTANT ×2.

**Against the old V1 selector:**
- V1 has P(SUPPORT) = 0 in every world below CONSTANT ×3 (0.31).
- V1 is WORSE than B1 in 99 % of NULL draws; its mean ΔBrier is +1.2e-4 in NULL and +8.0e-5 in SWITCHING ×2.
- V2 is far less costly (+3.1e-5 in NULL), but its SWITCHING gain over V1 is small:

  | | V2 − V1 | criterion |
  |---|---|---|
  | P(SUPPORT) at ×2 | +0.06 | ≥ 0.20 |
  | P(BEAT) at ×1 | +0.12 | ≥ 0.20 |

**The value of adaptation (V2 − its EXPANDING twin, mean ΔBrier):**
- **+1.9e-5 in NULL and +1.9e-5 to +2.4e-5 in every signal world, including SWITCHING (+1.9e-5 at ×1 and ×2, +2.4e-5 at ×3).**
- The 104-week window costs about 2e-5 of Brier and recovers none of it, even when the useful scale switches every 52 weeks.
- The twin's P(SUPPORT) in SWITCHING is 0.37 at ×2 and 0.99 at ×3, against V2's 0.06 and 0.68.

**Coefficient paths (diagnostic; SWITCHING ×2, 5 draws, standardized OCC slopes by the active regime):**
- active OCC_2H: β_2H 0.0133, β_8H 0.0063;
- active OCC_8H: β_2H 0.0132, β_8H 0.0065.
- **The weights do not move between regimes.** A 104-week window averages two 52-week regimes. Windows short enough to track them are too noisy (§8: TRAIL_52 and EWMA_26 have the lowest power).

## 10. Frozen adequacy criterion (protocol §7) and verdict

| criterion | value | pass |
|---|---|---|
| C1 NULL / NULL_DRIFT false support ≤ 0.05 | 0.000 / 0.000 | ✅ |
| C2 NULL / NULL_DRIFT P(BEAT) ≤ 0.50 | 0.000 / 0.035 | ✅ |
| C3 SWITCHING: support gain over V1 at ×2 ≥ 0.20; beat gain at ×1 ≥ 0.20 | +0.06; +0.12 | ❌ |
| C4 P(SUPPORT) ≥ 0.80 at ×2 in SWITCHING and CONSTANT | 0.06; 0.55 | ❌ |
| C5 OCC_OFF_ON ×2 mean ΔBrier < 0 | +1.2e-5 | ❌ |

**Verdict: `DESIGN_STILL_INFORMATIONALLY_INSUFFICIENT`.**

**Owner option, the Clark–West route (same C1–C5): it also fails.**
- Pass:
  - C1: 0.015 / 0.045;
  - C4: CONSTANT 1.00, SWITCHING 0.81 at ×2.
- Fail:
  - C3: the beat gain at ×1 is +0.12; the support gain at ×2 is +0.81 and passes;
  - C5: +1.2e-5.
- CW multiplies the power of the nested test by roughly 2 in z. **It does not change what the adaptive model estimates.**

## 11. Power characterization (MDE80, multiples of ρ_obs = 0.011)

| world | V2 (ΔBrier route) | V2 (CW option) | STATIC_OCC_4H | V1 |
|---|---|---|---|---|
| CONSTANT_OCC_4H | 2.56× | 1.43× | 1.68× | > 3× |
| SWITCHING_OCC_2H_8H | > 3× (0.68 at 3×) | 1.98× | > 3× (0.28 at 3×) | > 3× |
| OCC_OFF_ON | > 3× (0.05 at 3×) | > 3× (0.77 at 3×) | > 3× (0.74 at 3×) | > 3× |

At the observed order (×1), no architecture on these surfaces has useful power:
- ΔBrier route: P(SUPPORT) ≤ 0.18 (the static single-scale model in its own correct world, and the expanding multiscale reference);
- CW option: ≤ 0.55 (the expanding twin in CONSTANT).

A real NULL/WORSE from V2 could not exclude:
- adaptive occupancy information of up to about 3× the historical OCC_4H increment;
- in OFF_ON-type worlds, more than that.

**Why (information, not only the estimator):**
- The out-of-sample Brier gain of a correctly specified increment is ≈ Var(Δp) ≈ 0.16·ρ²/κ². That is about 2.7e-5 at ×1.
- The bootstrap SE of a nested ΔBrier over these 440 weeks is ≈ 1.5–2e-5.
- Adaptation must also estimate the weights from the rows inside one regime: 52 weeks ≈ 35k overlapping rows, about 13k effective. There, the standard error of a scale's partial association (~0.009) is about the size of the effect at ×1.

## 12. Recommendation

**`DESIGN_STILL_INFORMATIONALLY_INSUFFICIENT`.** Do not build a preflight and do not read market outcomes for V2.

**What is established (synthetic, outcome-free):**
- Multiscale shrinkage removes most of V1's selection cost: NULL ΔBrier +3.1e-5 against V1's +1.2e-4, with zero false support.
- But trailing-memory adaptation still costs about 2e-5 of Brier and recovers nothing at 1–3× the observed magnitude.
- At the observed magnitude, no forecast-skill design on these surfaces can make a real null informative.

**Options for the owner (none started):**
1. **Record the adaptive-occupancy question as informationally weak on these surfaces,** atlas `INFORMATIONALLY_WEAK` with this MDE table, and return to the run order (S1 next). *(Recommended.)*
2. **A static multiscale question:**
   - the EXPANDING JOINT ridge 1e4 on all seven OCC: synthetic MDE80 ≈ 1.8× in CONSTANT and ≈ 2.7× in SWITCHING on the ΔBrier route; 1.3× and 1.6× with CW;
   - but it does not adapt, and the static OCC line was ended by owner rule. It needs an explicit reopen.
3. **A higher-signal question:**
   - e.g. an association-level test of whether the OCC scale profile differs between periods (no out-of-sample forecast cost);
   - it needs its own design and its own synthetic gate.

## 13. Confirmations

- **No real outer market metric was read.**
  - The study reads only the outcome-free feature rows: V1 loader, feature digest `7afa8e8d…`, R_1H and Y deleted on load.
  - Every outcome is synthetic.
- No V2 market evaluator, preflight or attempt journal exists.
- DIRECTION exposure counters are unchanged. The E1 holdout and the E1-development slice were never requested.
- No Track A work. No product work.
- **Disclosure** (protocol §9): one exploratory timing batch (SWITCHING ×2, 50 draws, non-stage seed) was seen after the criterion was written and before it was committed. Nothing was changed.
