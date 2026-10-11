# RP4H_TREND_EXHAUSTION_INTERACTION_V1 — exact parity and information-adequacy protocol (frozen before any simulation summary)

**Date:** 2026-10-11. **Author:** chief architect, on the owner's decision of 2026-10-11 (Track B).
**Candidate status:** `DISCOVERY_CANDIDATE_FROM_SIGN_REVERSED_PRIMARY_HYPOTHESIS`. The hypothesis was formed **after** the RP4H_TREND_REGIME_MODULATION_V1 outcome. CORE 2020–24 is discovery and exposed. Unit 1 stays `TREND_REGIME_MODULATION_NOT_DETECTED` and is not reinterpreted.
**This stage:** no market interaction outcome is read. No replication runs before an owner decision.
**Constants:** `scripts/research/rp4h_trend_exhaustion_v1/constants.py` (this commit).

## 1. Question

Does the negative directional information of RANGE_POSITION_4H strengthen after a strong preceding trend move, on an independent historical surface?

This is a predictive interaction hypothesis. **No causal mechanism is claimed.**

## 2. Exact Unit-1 parity

Recovered literally from `scripts/research/rp4h_trend_regime_v1/` (design SHA `c1343df4…`, commit `175c95e2`).

| quantity | definition |
|---|---|
| RP4H, RET_4H, RV_4H, width, R_1H | RP4H parent code (`rp4h_bitmex_temporal_v1.parent.features`) on the surface's own 5m grid: RP4H = (close_i − min low_{i−47..i})/(max high − min low); RET_4H = log(close_i/close_{i−48}); RV_4H = √Σ_{48 bars} r²; R_1H = log(close_{i+12}/close_i) |
| TS_24H | \|log(close_i/close_{i−288})\| / √(Σ_{k=i−287..i} log(close_k/close_{k−1})²), computed as `spa_family(close)`: \|RET_24H\|/RV_24H |
| TS completeness | Defined only when the 289 closes i−288..i are all present. **On CORE this is vacuous:** 0 missing closes in 526,176 bars, and TS is identical for all 175,292 Unit-1 anchors (verified, outcome-free). |
| anchors | the RP4H 15-minute phase; RP4H, RET_4H, RV_4H, width and R_1H finite (target inside the surface); RET_1H and RET_15M inside the window; TS finite |
| **PRIMARY** | **interaction_b0**, the Unit-1 function imported unchanged: partial Spearman(R_1H, P \| RP4H, TS, RET_4H, RV_4H), with P = (rank RP4H − mean)·(rank TS − mean) on average ranks; then midranks of R_1H and of P, OLS residualization with an intercept on the ranks of the four controls, and the Pearson of the residuals |
| discovery value | −0.01187 [−0.02021, −0.00403], CORE 2020–24, N 175,292, 262 ISO weeks, bootstrap seed 20261122 |

**Why interaction_b0 is primary.** It is the only continuous interaction Unit 1 computed. Unit 1 had no local-path-controlled interaction: its local-path quantities were tercile partials and delta_b1. A local-path interaction therefore has no discovery value to replicate.

**Secondary, predeclared now, no route:** the same interaction with RET_1H and RET_15M added to the controls. Its CORE value does not exist.

**Separation of effects (diagnostics):**
- **A. main RP4H:** partial Spearman(R_1H, RP4H | RET_4H, RV_4H);
- **B. trend main:** partial Spearman(R_1H, TS | RP4H, RET_4H, RV_4H);
- **C. interaction:** the primary. Only C carries the route.

**Descriptive strata only:**
- T1/T2/T3 with **Unit 1's frozen CORE edges** 0.3603253093 / 0.8528621531, with stratum shares reported;
- years, halves, the comparison with CORE without pooling.

## 3. Candidate surfaces

| surface | definition |
|---|---|
| **BitMEX XBTUSD 2016–19** | D2 canonical 5m, SHA `8e027433…`; Unit A loader and sample |
| **Binance USD-M BTCUSDT 2025–26** | RP4H Unit B canonical 64 objects; E1 window and E1-development slice never requested; Unit B loader, census asserted |

**R_1H is dropped on load** in this stage (`surfaces.py` pops it before anything else runs).

**Exposure audit:** a read-only search of the current branch and every remote branch for EXACT or EQUIVALENT reads of the interaction on either surface, reported with the gate.

## 4. Synthetic data-generating process (real features and support, synthetic outcomes)

- **Model:** R_i = Σ_{k=i+1}^{i+12} s_k·e_k + σ_i·(β_main·g_main,i + β_int·g_int,i), with e_k ~ N(0,1) on every bar of the surface's grid.
- **Overlap:** anchors 15 minutes apart share 9 of 12 innovations, like real overlapping 1h targets.
- **Primary DGP (heteroskedastic):** s_k = the RMS of the surface's real log returns over bars k−60..k−13.
  - Every anchor whose target contains bar k lies at or after k−12, so s_k is past-only for all of them.
  - Fallback: the surface median when fewer than 24 returns are finite; floor at 10 % of the median.
- **Sensitivity DGP (homoskedastic):** s_k = 1.
- **Signal scale:** σ_i = √Σ_{k=i+1}^{i+12} s_k², so the planted associations are scale-free.
- **g_main:** the standardized rank residual of RP4H on the RET_4H and RV_4H ranks. β_main is set for a planted main partial of **−0.030** at every level, including the null.
- **g_int:** the standardized rank residual of P on the four control ranks. **No planted TS main effect.**
- **Interaction ladder:** ρ_int = level × (−0.01187), level ∈ {0, 0.5, 1, 1.5, 2, 3}. The 3× level only locates the MDE.
- **Calibration of β:** β_int = ρ_int/κ_int, per surface and per DGP. κ comes from a paired calibration over 16 draws: the estimator with and without β = 0.03 on the same noise and the same planted main effect.

## 5. Monte Carlo

- **Replications:**
  - 400 per surface and level on the primary DGP;
  - 200 per surface at levels 0 and 1 on the sensitivity DGP.
- **Seeds:** SeedSequence(202610111 or 202610112, surface, level, replication).
- **Estimator per replication:** the exact primary point (vectorized; equal to the imported Unit-1 function to 1e-12, tested).
- **Interval per replication:** a fast fixed-residual ISO-week block bootstrap of the same estimator (B 2000, the run's seed 20261125, re-centred per draw).
- **Validation:** the canonical re-rank bootstrap of a real run against the fast one, 2 replications per surface at 1×.
  - If the canonical/fast interval-width ratio exceeds 1.10, the gate is recomputed with the fast intervals widened by that ratio.
- **Reported per surface and level:**
  - P(SUPPORTED), P(UNCERTAIN), P(NOT_REPLICATED), P(SIGN_OPPOSES), P(correct sign);
  - the mean and sd of the point estimate;
  - the CI-width distribution;
  - MDE80 by linear interpolation;
  - a planted main-effect check.
- **Pooled BitMEX + Binance 2025–26:** inverse-variance combination of the two estimates per replication. **Informational only; never selectable by the rule.**

## 6. Frozen adequacy criterion, per surface

A surface is adequately powered only if all four hold:
1. Primary DGP, null: P(SUPPORTED) ≤ 0.05 **and** P(SIGN_OPPOSES) ≤ 0.05.
2. Sensitivity DGP, null: the same.
3. Primary DGP: P(SUPPORTED | 1× discovery magnitude) ≥ 0.80.
4. Sensitivity DGP: P(SUPPORTED | 1×) ≥ 0.80.

The bar is not lowered after the simulations.

## 7. Frozen surface rule (owner, 2026-10-11)

**Eligibility:** a surface is eligible only if it is adequately powered (§6) **and** question-fresh for the interaction (no EXACT or EQUIVALENT prior read in the exposure audit).

1. If Binance 2025–26 is eligible → Binance 2025–26, the direct test of modern stability.
2. Else, if BitMEX 2016–19 is eligible → BitMEX, stating explicitly that modern stability remains unresolved.
3. Else → **`TREND_EXHAUSTION_REPLICATION_INFORMATIONALLY_INSUFFICIENT`**, no market outcome, STOP.

**Not used for the choice:**
- any real interaction outcome;
- the pooled configuration;
- the secondary or diagnostic quantities.

## 8. Routes of a later real run (frozen; PRIMARY interaction_b0 only)

1. **`IMPLEMENTATION_INVALID`:** a provenance, support or leakage failure, or fewer than 1,900 valid draws.
2. **`TREND_EXHAUSTION_INTERACTION_SIGN_OPPOSES`:** the whole 95 % interval > 0.
3. **`TREND_EXHAUSTION_INTERACTION_REPLICATION_SUPPORTED`:** point < 0 and the whole 95 % interval < 0.
4. **`TREND_EXHAUSTION_INTERACTION_DIRECTION_COMPATIBLE_UNCERTAIN`:** point < 0 and the interval includes 0.
5. **`TREND_EXHAUSTION_INTERACTION_NOT_REPLICATED`:** otherwise (point ≥ 0 with the interval including 0).

**Interval:** the dependence-aware ISO-week block bootstrap of a real run (Unit-1 machinery, every rank recomputed per draw), B 2000, seed 20261125.

There is no magnitude threshold. **No rescue on failure.**

## 9. No tuning

This unit replicates one exact discovery interaction. There is no scan over any of:
- trend windows or definitions;
- tercile edges;
- RP lookbacks;
- target horizons;
- sessions;
- volatility filters.

No product, forecast-engine use, PnL, current probability or entry/exit rule.
