# MULTISCALE_ADAPTIVE_OCCUPANCY_V2 — synthetic adequacy protocol (frozen before the Monte Carlo summary)

**Date:** 2026-10-10. **Author:** chief architect, on the owner's decision of 2026-10-10.
**Stage:** design and outcome-free synthetic adequacy only. **No market outcome is read.** V2 is not frozen for market evaluation.
**Constants:** `scripts/research/multiscale_occupancy_v2/constants.py` (this commit).

## 1. Object

**Question:** can a low-variance, past-only multiscale occupancy model extract incremental next-hour directional forecast information when the useful occupancy timescale changes through time?

The model adapts its **weights** across the seven frozen OCC timescales by retraining. It does not pick one winning lookback.

**Inputs:**
- **OCC:** OCC_1H, 2H, 3H, 4H, 6H, 8H, 12H. Same rows, anchors and exact OCC_L definition as V1, feature digest `7afa8e8d…`.
- **B1:** RP4H, RET_4H, RV_4H, RET_1H, RET_15M, in V1's representation.

**Systems compared:** CLIMATOLOGY, BASELINE_B1, STATIC_OCC_4H (all expanding, as in V1), V2, and the V1 hard selector (comparison only).

## 2. V2 candidate architectures (engineering grid; synthetic outcomes only)

**Structures:**
- **JOINT:** one ridge logistic on [B1, OCC_1H…OCC_12H] fitted on the memory window. Ridge 1.0 on the B1 slopes (the frozen B1 value) and λ_occ on the seven OCC slopes.
- **OFFSET:** the expanding B1 fit at the block start is a fixed offset. A ridge logistic overlay on the seven OCC features (λ_occ, no intercept) is fitted on the memory window.
  - The B1 part is then exactly the baseline, and V2 − B1 is purely the occupancy contribution.
  - The memory window cannot re-estimate B1.

**Memories:**
- **Eligible for selection** (the owner's A, B, C):
  - TRAIL_52 and TRAIL_104: up to M weeks before the block start; shorter only while the venue's history is shorter;
  - EWMA_26: exponential weights 2^(−age/26 weeks) on every earlier venue row.
- **EXPANDING:** reported as a reference only, **never selectable**, because it does not adapt.

**Ridge on OCC:** λ_occ ∈ {1, 1e3, 1e4}, i.e. none / moderate / strong.
- **Why not {0.1, 1, 10}:** the data curvature of a standardized slope is about 0.25·n, i.e. 9k–60k at these window sizes. Values of 0.1 to 10 are all "no shrinkage".
- **1e3** shrinks mainly the contrasts between neighbouring scales (small eigenvalues).
- **1e4** also shrinks the common occupancy level, by about a fifth.

**Shared mechanics:**
- Standardization (weighted mean and sd) is fitted on training rows only; clip ±5.
- Walk-forward: V1's schedule (28-day blocks from Mondays; 111 outer blocks; 294,493 outer rows; venues never mixed). Models are trained on rows realized by the block start and frozen for the block.

**Total:** 18 selectable candidates plus 6 references.

## 3. Synthetic worlds

Latent next-hour return: R = N + β_L·g_L (L active) + drift.
- **Noise N:** the next 12 per-bar N(0,1) innovations on the row's own series grid, /√12. Overlap is as in real 1h targets.
- **g_L:** OCC_L residualized on the B1 design within each series, at unit variance.
- **Outcome:** Y = 1{R > 0}.

**Worlds (52-week periods from the first row):**
- **NULL:** no OCC information.
- **NULL_DRIFT:** no OCC information plus a per-13-week level shift N(0, 0.025²), about 1 pp of P(UP). This is a nuisance test for false support from base-rate tracking.
- **CONSTANT_OCC_4H:** OCC_4H in every period.
- **SWITCHING_OCC_2H_8H:** OCC_2H in even periods, OCC_8H in odd ones. This is the crucial scenario.
- **OCC_OFF_ON:** OCC_4H off in even periods and on in odd ones.

**Effect scale:**
- The target is ρ = partial Spearman of the *active* scale with R given B1 (rp, ret4, rv4, ret1h, ret15 ranks, the OCC replication's PRIMARY metric), within its active periods.
- **Observed order ρ_obs = 0.011**, OCC_4H's PRIMARY on BitMEX 2016–19.
- **Ladder:** ×0.5, ×1, ×1.5, ×2, ×3, i.e. 0.0055, 0.011, 0.0165, 0.022, 0.033.
- **Mapping:** β_L = ρ/κ_L, with κ_4H 0.8485, κ_2H 0.9193, κ_8H 0.8733. This is a paired calibration over 16 draws of β = 0.03 against the same noise (SE ≤ 0.0008). It agrees with corr(rank residual of OCC_L | B1, g_L) = 0.869 / 0.906 / 0.928 times the normal rank factor.

## 4. Route per replication (as the real run would use)

**SUPPORT:**
- ΔBrier(V2 − B1) < 0, with its 95 % ISO-week block-bootstrap interval < 0 (B 2000, the frozen seed `20261124`);
- ΔLogLoss < 0;
- calibration slope ≥ 0.

**BEAT:** ΔBrier point < 0.

**Owner option, reported but not the route — `SUPPORT_CW`:** the Clark–West-adjusted Brier statistic for nested models, 2(p_V2 − p_B1)(y − p_B1), has its weekly-bootstrap mean > 0 and interval > 0. It adds back the noise term that the plain loss difference charges a larger nested model.

## 5. Monte Carlo

- **Seeds:** every replication has its own seed, SeedSequence(stage seed, scenario id, level id, replication).
- **Stage 1 (selection):** seed 202610101. 50 replications per signal level; 100 per NULL world.
- **Stage 2 (adequacy):** fresh seed 202610102. 100 replications per signal level; 200 per NULL world. Systems: the selected V2, its EXPANDING twin, B1, STATIC_OCC_4H, CLIM and the V1 selector.

## 6. Stage-1 selection rule (frozen)

1. **Eligible:** a TRAIL_52, TRAIL_104 or EWMA_26 candidate whose NULL and NULL_DRIFT false-support rates are ≤ 0.05 and whose P(BEAT) is ≤ 0.50 in both.
2. **Score:** mean P(SUPPORT) in SWITCHING at ×1 and ×2.
3. **Tie band:** among candidates within 0.05 of the best score, the highest mean P(SUPPORT) over CONSTANT and OFF_ON at ×1 and ×2 wins.
4. **Exact ties:** larger λ, then OFFSET, then TRAIL_104, TRAIL_52, EWMA_26.
5. **No eligible candidate:** `DESIGN_STILL_INFORMATIONALLY_INSUFFICIENT`.

## 7. Stage-2 adequacy criterion (frozen)

`READY_FOR_PREFLIGHT` requires all five:

| | criterion |
|---|---|
| **C1** | NULL and NULL_DRIFT: P(SUPPORT) ≤ 0.05 |
| **C2** | NULL and NULL_DRIFT: P(BEAT) ≤ 0.50 (no systematic apparent improvement) |
| **C3** | SWITCHING: P(SUPPORT_V2) − P(SUPPORT_V1) ≥ 0.20 at ×2, and P(BEAT_V2) − P(BEAT_V1) ≥ 0.20 at ×1 |
| **C4** | P(SUPPORT) ≥ 0.80 at ×2 in SWITCHING and in CONSTANT_OCC_4H (a real null then rules out effects of 2× the observed order) |
| **C5** | OCC_OFF_ON at ×2: mean ΔBrier(V2 − B1) < 0 (dead periods do not erase the gain) |

Otherwise the verdict is `DESIGN_STILL_INFORMATIONALLY_INSUFFICIENT`, naming the failing criteria.

**Also reported:**
- P(SUPPORT), P(BEAT), P(WORSE), the ΔBrier distribution and V2 − STATIC_OCC4 at every level;
- MDE80, by linear interpolation over the ladder;
- the same C1–C5 with `SUPPORT_CW` as the owner option;
- coefficient paths of the selected architecture in SWITCHING;
- an exact-IRLS check of the selected architecture.

## 8. Computation and its validation

**Surrogate:** all fits are the one-step Newton solution of the weighted ridge logistic from the intercept-only start, computed from segment sums, vectorized over replications. At |η| ≪ 1 this is the IRLS solution to ~1e-4 relative.

**Validated before this protocol:**
- **V1 reproduction:** the surrogate reproduces the exact V1 preflight (three worlds, full IRLS with clip):
  - ΔBrier to ≤ 1e-6, e.g. NULL +1.534e-4 against exact +1.538e-4;
  - intervals to ~1e-6;
  - identical V1 selection shares.
- **Single fits:** surrogate vs exact IRLS on sample blocks: mean |Δp| 1–3e-5, against a prediction sd of 4e-3–1.4e-2.

**To come:** stage 2 adds an exact-IRLS check of the selected architecture.

## 9. Disclosure

`constants.py` (grid, worlds, ladder, seeds, selection rule and C1–C5) was written before any V2 synthetic summary. Then one exploratory timing batch was printed, before this commit:
- 50 replications of SWITCHING ×2;
- exploratory seed (1, …), not a stage seed;
- all 24 candidates and V1.

**Nothing was changed after it.** It showed:
- P(SUPPORT) ≤ 0.18 for every selectable candidate and 0.28 for the best expanding reference;
- the strongest ridge (1e4) best in each family;
- V1 0.00.

The grid edge at λ = 1e4 is therefore known. Extending the grid would be an owner-authorized synthetic amendment, not a silent change.
