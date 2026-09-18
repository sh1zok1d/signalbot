# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3 — Confirmatory Preregistration

**Status:** `PREREG_AMENDED_AWAITING_IMPLEMENTATION_AND_FREEZE`
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3`
**Unit type:** methodology calibration, not a market hypothesis
**Base main head at design start:** `3339812a7ea30c7e325d83276f6ce4b5399afe50`
**Parent design unit head:** `2759e09449e2ec4c041ea9ec433191c2bbbff9a1`
**Amendment history:** Amendment 001 — pre-outcome correctness/spec-completeness amendment, §16. Original accepted content frozen at `4136f530378e91d545e2644a650f0a7a07a731c3` (that freeze remains valid historical evidence of the pre-amendment text and is not rewritten).
**Execution status:** `v3_prereg_frozen = false` (pending new freeze of this amended text), `v3_run_authorized = false`, `v3_armed = false`

Machine-readable twin: [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json).

This document materializes, without leaving any scientific choice to implementation, the V3 methodology accepted across `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_POSTRUN_FORENSIC_REVIEW.md`, `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_CONFIRMATORY_DESIGN.md`, `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_CONFIRMATORY_SPEC.md`, two rounds of independent adversarial methodology review (the second round corrected the dependence-aware resampling scheme from a gap-closed support-only extract to full-time-axis joint resampling), and Amendment 001 (§16), a pre-outcome correctness/spec-completeness amendment closing two implementation blockers discovered after the original freeze but before any implementation, ARM, reservation, or V3 outcome. It is **not** a freeze, ARM, execution authorization, or permission to inspect fresh V3 outcomes.

---

## 0. What V2 established, and what V3 is bounded to fix

V2's canonical, immutable RESULT (`761cc9af…`, built on WORLD_RECORDS `e8667f93…`) measured: EASY `365/400=0.9125` (Wilson lower `0.8807` → `INDETERMINATE` vs 0.90), MODERATE `108/400=0.27` (lower `0.2288` → `FAIL` vs 0.70), NULL `2/400=0.005` (upper `0.0180` → `PASS` vs 0.05), TRAP `PASS`. All MODERATE and EASY misses were bootstrap-only misses after the primary sign and placebo separation already passed. V3 is a **bounded repair** of that one measured deficiency — an over-conservative, pooled, AND-of-gates confirmatory decision — not a general redesign. `DEFAULT_V4 = NO`. V2 is `DEVELOPMENT-CONSUMED`: it may motivate V3's design but may never be V3 acceptance evidence (§9).

---

## 1. Purpose and boundaries

> Given one prospectively frozen conditional claim, can the validator detect its predeclared incremental predictive effect with adequate power while respecting a fixed false-positive budget and preserved nonstationary-trap protection?

```text
v3_prereg_frozen = false
v3_run_authorized = false
v3_armed = false
default_v4 = false
b2_06_scientific_execution_authorized = false
real_market_data_access_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
modify_v1_v2_frozen_artifacts = false
modify_v2_inventory = false
rerun_v2_canonical_worlds = false
market_promotion_possible = false
```

Not this unit: a general discovery framework, multi-candidate multiplicity correction, a V4 or further synthetic iteration, B2-06 authorization, real market data access, or a rescue of the completed V2 canonical RESULT.

---

## 2. Explicit estimand change from V2

V2's estimand was the pooled mean AE improvement over **all** scored rows (S=0 and S=1 mixed), decided by `primary_positive AND bootstrap_positive AND placebo_separation`. V3's estimand is the claim-aligned conditional mean of a Clark-West-adjusted squared-loss differential, restricted to `S_t=1`, decided by **one** studentized dependence-aware test. This is a genuine semantic change — conditioning removes the S=0-row dilution that suppressed V2's pooled point estimates — and must remain explicit in every V3 result artifact, not silently presented as "a more powerful V2."

---

## 3. Reused frozen primitives (unchanged)

V3 calls the following from `scripts/research/harness_synthetic_edge_calibration_v1_lib.py` (SHA256 `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`, size 37636 — the pinned V1 TCB, **not modified** by this unit) exactly as committed:

`simulate_dgp`, `world_identity`, `world_seed`, `namespace_seed`, `pcg64_generator`, `candidate_features`, `expanding_era_predictions`, `era_slices`, `scored_mask`, `era_blocks`, `ae_metrics`, `IncompleteWorld`, plus constants `ROOT_SEED`, `SCORED_ERAS`, `ERA_NAMES`, `RHO`.

**Explicitly not reused:** `compose_gates` (V1/V2's `MODEL_DETECTED`/`STRICT_PASS` composition — V3 has one `DETECTED` rule instead), `prediction_bootstrap`/`placebo_q95`/`resample_era_rows` (V1/V2's fixed-block bootstrap and permutation placebo — superseded by §6), `evaluate_production_candidate` (V1's per-candidate orchestrator — V3 has its own, built only from the primitives above).

---

## 4. Candidate/baseline construction — overlay forbidden

V3 reuses `expanding_era_predictions(y, x1, x2, feature, n_rows)` **unchanged**: `BASE` fits `(1, X1, X2)`; `CAND` fits `(1, X1, X2, feature)`; both OLS on the same expanding per-era training window, refit once per scored era. `CAND` strictly nests `BASE`.

**An overlay-with-exact-baseline-fallback-outside-support construction is FORBIDDEN for this calibration.** It is a materially different nesting relationship; the Clark-West identity in §5 is derived for and verified against the `expanding_era_predictions` nested-OLS construction only, and does not transfer without independent re-derivation and re-review.

Candidate for the frozen V3 claim: **F03** (oracle candidate, `feature = S_t`), matching the V1/V2 oracle-arm convention. V3 core validates one frozen claim, not the blind discovery library.

---

## 5. Loss, Clark-West adjustment, estimand

```text
L(y, yhat) = (y - yhat)^2
e_B,t = Y_t - BASE_PRED_t
e_C,t = Y_t - CAND_PRED_t
d_t   = e_B,t^2 - e_C,t^2                                    [diagnostic only]
d*_t  = e_B,t^2 - (e_C,t^2 - (yhat_B,t - yhat_C,t)^2)          [Clark-West-adjusted, primary]
```

Reference: Clark, T.E. & West, K.D. (2007), *Journal of Econometrics* 138(1):291-311. Applicability is conditioned on §4's nesting requirement holding at implementation review time; if it does not, execution stays blocked and this prereg is revised before freeze without using fresh outcomes.

```text
w_t = S_t in {0,1}                       (frozen DGP trigger; never learned from outcomes)
theta = E[d*_t | S_t = 1]
theta_hat = sum_t(S_t * d*_t) / sum_t(S_t)     (pooled over E2..E5)
H0: theta <= 0    H1: theta > 0    alpha = 0.05, one-sided
```

`theta_hat` is a ratio (M-)estimator of a conditional mean — this classification matters for §7's block-length-selector derivation.

---

## 6. Support validity

`support_count >= 50` (finite scored `S_t=1` rows, pooled over E2..E5) is the hard floor. `effective_N` is **mandatory diagnostic and range validity only** (`finite`, in `[1, support_count]`) — **not** an additional power veto. Verified against the actual frozen DGP: with `RHO=0.90` Markov persistence, mean `S=1` run length is ~8–12 rows and only ~25–80 independent runs occur per 4000-row scored world even when `support_count` is in the hundreds. An `effective_N` hard gate would spuriously invalidate correctly-functioning MODERATE worlds; this is not tuned to any V2 outcome.

---

## 7. Dependence-aware calibration — full-time-axis joint stationary bootstrap

**Resampled object:** the full chronological paired sequence `(d*_t, S_t)` for every scored row of a given era — **not** the gap-closed `{d*_t : S_t=1}` extract. Bootstrapping the gap-closed extract makes temporally distant support runs appear adjacent inside a resampled block; per-era resampling of that extract does not fix it, since multiple distinct `S=1` runs commonly occur within one era.

**Algorithm, per world:**

```text
1. compute theta_hat once from the full observed pooled series (§5)
2. select one expected block length b_hat once per world (below)
3. per replicate b = 1..999, independently for each scored era e:
     draw stationary-bootstrap blocks over the full chronological row
     index 1..n_e of era e; each block is a contiguous run of original
     adjacent rows carrying its joint (d*_t, S_t) pair for every row,
     never split; block starts drawn uniformly on 1..n_e; block lengths
     i.i.d. Geometric(p = 1/b_hat); if a block would run past n_e, wrap
     circularly WITHIN that era only (never into another era or E1)
4. concatenate drawn blocks until length >= n_e, truncate to exactly n_e
5. concatenate the 4 resampled eras in order, without crossing
   era/refit boundaries, into (d*_t^(b), S_t^(b))
6. theta*_b = sum_t(S_t^(b) * d*_t^(b)) / sum_t(S_t^(b))
```

`B = 999` — reuses the project's existing `PRODUCTION_PLACEBO_REPLICATES` constant rather than a newly invented number; odd count avoids quantile ties; gives p-value resolution (~0.001) far finer than α=0.05.

**Zero-support replicate:** if `sum_t(S_t^(b)) = 0` for any replicate (ratio denominator undefined), the **whole world is `INVALID`** — no redraw, no rescue, matching the existing `prediction_bootstrap` convention.

### Block-length selector

**Reference:** Politis, D.N. & White, H. (2004), "Automatic Block-Length Selection for the Dependent Bootstrap," *Econometric Reviews* 23(1):53-70 (DOI `10.1081/ETC-120028836`), with the correction in Patton, A., Politis, D.N. & White, H. (2009), "Correction to 'Automatic Block-Length Selection for the Dependent Bootstrap' by D. Politis and H. White," *Econometric Reviews* 28(4):372-375 (DOI `10.1080/07474930802459016`).

**Input series — derived, not assumed:** `theta_hat` is a ratio estimator; its standard delta-method/Woodruff linearization has influence term proportional to

```text
z_t = S_t * (d*_t - theta_hat)
```

computed over the **full chronological t-axis of each scored era** (`z_t=0` at every `S_t=0` row — zeros are retained, since their temporal position carries the run-length/gap structure; the constant `1/E[S]` scale factor is dropped because autocovariance-based block selection is scale-invariant). This is exactly the object whose dependence structure governs the sampling variability of `theta_hat`.

- The four per-era `z_t` series are **pooled (concatenated)** into one series `x` of length `nobs` (sum of the 4 eras' row counts, ≈4000 for the canonical N=5000 DGP) solely for a stable spectral-density estimate.
- **Exactly one selector call per world**, on the single observed (non-resampled) pooled series `x`; the resulting `b_hat` is reused identically across all 4 eras' resampling and all 999 replicates.
- **RNG:** the selector itself consumes none (deterministic function of `x`); only the stationary bootstrap's block-continuation draws consume RNG (§9).

#### Selector authority: literal port, exact source identified

**Choice A** (literal port of a specific, identified, reproducible reference implementation), per the review's stated preference. The reference is the open-source Python package **`arch`** (PyPI: `arch`, author Kevin Sheppard), **version `8.0.0`**, function `arch.bootstrap.optimal_block_length` / its private stationary-bootstrap-branch helper in `arch/bootstrap/base.py`. This function's own docstring cites exactly the same two papers (2004 + 2009 correction, same DOIs) bound above, confirming it implements the target algorithm rather than a different one.

```text
package               = arch
package_version       = 8.0.0
source_file            = arch/bootstrap/base.py
source_file_sha256      = 104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21
source_file_size        = 60275 bytes
public_entry_point      = arch.bootstrap.optimal_block_length
implementing_function   = _single_optimal_block  (stationary-bootstrap branch only: b_sb/d_sb/c=2; the circular-bootstrap branch b_cb/d_cb/c=4/3 is not used — V3 uses the stationary bootstrap only, §7)
optimal_block_length_source_sha256   = b70543178ffb368cb22490f508de9bf35152eb9882ca4b66f26d338c5f1f4f12
_single_optimal_block_source_sha256  = 355cfaf81a09a42f32dd643d2cd5fd39a78d16faec1e4cc06a79a83d729b7421
```

**Exact algorithm, reproduced verbatim (0-based indexing; `x` = pooled `z_t` series, `nobs = len(x)`):**

```text
eps = x - mean(x)                                         # demean, as in the reference; no extra pre-demeaning by V3

b_max = ceil(min(3*sqrt(nobs), nobs/3))                    # (9) cap applied to the raw selector output, INSIDE the
                                                             #     reference algorithm; distinct from and prior to
                                                             #     the already-frozen per-era clamp below
kn    = max(5, int(log10(nobs)))                           # int() truncates toward zero (floor, nobs>1)
m_max = ceil(sqrt(nobs)) + kn
cv    = 2 * sqrt(log10(nobs) / nobs)                        # (4) significance threshold, constant = 2

acv[i]       = (eps[i:] @ eps[:nobs-i]) / nobs              # (1) autocovariance gamma_hat(i); BIASED estimator,
                                                             #     divided by nobs (not nobs-i), for i = 0..m_max
abs_acorr[i] = |eps[i:] @ eps[:nobs-i]| / sqrt(v1_i * v2_i)  # significance-test statistic only (NOT used in g/g_hat(0));
   where v1_i = eps[i+1:] @ eps[i+1:], v2_i = eps[:-(i+1)] @ eps[:-(i+1)]

opt_m = None
for i in 0..m_max:
    if i >= kn and all(abs_acorr[i-kn : i] < cv) and opt_m is None:
        opt_m = i - kn                                      # (2)/(3) first run of kn consecutive insignificant lags
m = 2 * max(opt_m, 1)  if opt_m is not None  else  m_max
m = min(m, m_max)

h(x) = 1            if x <= 1/2                              # (3) flat-top lag window (Politis-Romano)
h(x) = 2*(1-x)       if 1/2 < x <= 1
                                                             # (note: loop only reaches k/m<=1, so the x>1 branch
                                                             #  h(x)=0 is never evaluated here)

G_hat     = sum_{k=1}^{m} 2 * h(k/m) * k * acv[k]             # (5)
g_hat(0)  = acv[0] + sum_{k=1}^{m} 2 * h(k/m) * acv[k]        # (6)  == "lr_acv" / long-run-variance estimate sigma_hat^2

D_hat_SB = 2 * g_hat(0)^2                                    # (7)  matches the Patton-Politis-White (2009) correction exactly
b_hat_SB = (2 * G_hat^2 / D_hat_SB)^(1/3) * nobs^(1/3)         # (8)
b_hat_SB = min(b_hat_SB, b_max)                               # (9)  reference algorithm's own internal cap
```

`G_hat` (the code's `g`) and `g_hat(0)` (the code's `lr_acv`, i.e. `sigma_hat^2`) are **distinct** quantities — both appear in the docstring; this document names them exactly as the task requires, with `g_hat(0)` bound to `D_hat_SB = 2*g_hat(0)^2` per item 7, matching `d_sb = 2 * lr_acv**2` in the reference source exactly.

**Degenerate-case behavior on top of the literal port (disclosed addition, not a silent deviation — the reference function itself does not guard these):**

| Condition | Disposition |
|---|---|
| `nobs` too small for `log10(nobs)`/`kn`/`m_max`/`b_max` to be finite and positive (e.g. `nobs<=1`) | world `INVALID` |
| `acv[0]` (sample variance of `x`) is `0` or non-finite | world `INVALID` |
| any of `acv[i]`, `abs_acorr[i]`, `G_hat`, `g_hat(0)`, `D_hat_SB`, `b_hat_SB` is non-finite (`NaN`/`Inf`) | world `INVALID` |
| `D_hat_SB <= 0` | world `INVALID` (mathematically `D_hat_SB=2*g_hat(0)^2>=0`; a non-positive value only arises from numerical degeneracy) |
| `b_hat_SB <= 0` after all of the above | world `INVALID` |

**Then, unchanged from the prior freeze, applied to the (now exactly-defined) `b_hat_SB`:**

- **Integer conversion/clamping into each era's resampling parameter:** `p = 1 / round(clamp(b_hat_SB, 1, n_e))` — a **second**, per-era clamp distinct from the selector's own internal `b_max` cap above (`b_max` uses the pooled `nobs`; this clamp uses the individual scored era's row count `n_e`, since each era is resampled separately in §7).
- **Deterministic fallback:** any `INVALID` disposition above (or non-finite/undefined/≤0 `b_hat_SB`) ⟹ world `INVALID`; no hand-picked rescue block.

**Intentional deviations from the literal reference (disclosed):**

1. Only the stationary-bootstrap branch (`c=2`, `b_sb`) is used; the circular-bootstrap branch (`c=4/3`, `b_cb`) is computed by the reference function but discarded, since V3 uses the stationary bootstrap only (§7).
2. The reference function's own docstring discloses a known, author-acknowledged discrepancy against Patton's original MATLAB reference program ("autocovariances/autocorrelations are all computed using the maximum sample length rather than a common sampling length") — this is inherited as-is from the pinned Python implementation and does not affect V3's reproducibility, since V3 pins this exact Python implementation, not the MATLAB one.
3. The degenerate-case table above adds an explicit fail-closed wrapper around the literal computation (required for V3's world-validity semantics); it does not alter any arithmetic step of the algorithm itself.

---

## 8. Studentized statistic and p-value

```text
SE_hat = sample standard deviation of theta*_b, b=1..999, with ddof=1
       = sqrt( sum_b( (theta*_b - mean_b(theta*_b))^2 ) / (999 - 1) )
       = numpy.std(theta_star, ddof=1)   [equivalent implementation]
T_obs  = theta_hat / SE_hat
T*_b   = (theta*_b - theta_hat) / SE_hat
p_one_sided = (1 + #{b : T*_b >= T_obs}) / (999 + 1)

DETECTED iff world_valid AND theta_hat > 0 AND p_one_sided <= 0.05
          AND all 3 per-world validity guards pass (§10)
```

`ddof=1` (Bessel's correction, the sample standard deviation) is bound explicitly by Amendment 001 (§16) to remove an implementation ambiguity the original text left open; it does not change `B=999`, `theta_hat`, `theta*_b` construction, `T_obs`, `T*_b`, the p-value formula, `alpha`, or any acceptance threshold.

Single-level recentered bootstrap-t — the standard pairing for a studentized statistic with a single-level bootstrap SE. `DETECTED` is the **single** primary decision; it is not V2's `primary_positive AND bootstrap_positive AND placebo_separation` reconstructed under a new name.

---

## 9. RNG authority and fresh world identities

Reused unchanged: `ROOT_SEED`, `world_identity()`, `world_seed()`, `namespace_seed()`, `pcg64_generator()` — the identity-string literal prefix is unmodified (pinned V1 TCB).

**Fresh world_index range:** `world_index in [10000, 10399]` (400 worlds) for each of `EASY`, `MODERATE`, `NULL`, `NONSTATIONARY_TRAP` at `N=5000`. V1/V2's canonical 3200-world grid exhausts `world_index 0..399` for every scenario at every frozen N (verified against `planned_production_jobs()`); `10000..10399` is disjoint with a large safety margin, requires no change to any frozen identity function, and makes V2-world reuse **mechanically impossible**, not merely policy-forbidden.

**New RNG namespace token — bound by Amendment 001 (§16):** `"V3_CONFIRMATORY"` is the sole stream for the stationary-bootstrap block-continuation draws, deliberately distinct from V1/V2's `"BOOTSTRAP"`/`"PLACEBO"` tokens. The frozen V1 `namespace_seed()` rejects any token outside its own `NAMESPACES = ("DGP","BOOTSTRAP","PLACEBO","VISIBILITY")` allowlist — extending that allowlist by editing `harness_synthetic_edge_calibration_v1_lib.py` was evaluated and rejected (it would either break the live `assert_v1_tcb_intact()` check unless `FROZEN_V1_TCB_SHA256["lib"]` in `harness_synthetic_edge_calibration_v2_production.py` is also updated, or, if that constant is updated, reintroduce for TCB identity the exact live-global commit-purity defect already found and repaired once for canonical plan identity — both out of scope for this narrow amendment). Instead:

```text
V3_NAMESPACE_SOURCE   = scripts/research/harness_synthetic_edge_calibration_v3_rng.py
V3_NAMESPACE_SHA256    = 8bd6aef151139bc1afd4d890d7ba293b1adec5cf66b405dde677eccb3b06d698
V3_NAMESPACE_SIZE      = 2325 bytes
V3_NAMESPACE_FUNCTION   = v3_namespace_seed(world_seed_int, *context)
V3_NAMESPACE_TOKEN      = V3_NAMESPACE = "V3_CONFIRMATORY"
```

`v3_namespace_seed(world_seed_int, *context)` computes exactly the value `namespace_seed(world_seed_int, "V3_CONFIRMATORY", *context)` would compute if its allowlist admitted the token: identical `"|".join(str(world_seed_int), "V3_CONFIRMATORY", *[str(c) for c in context])` payload, identical `_uint64_from_digest(sha256(...))` truncation, with `_uint64_from_digest` imported from the frozen V1 module and reused verbatim (not reimplemented). `harness_synthetic_edge_calibration_v1_lib.py` is not modified by this file or by this amendment; its SHA256 remains `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`, unchanged.

`pcg64_generator(v3_namespace_seed(world_seed, feature_id))` is the sole stream for the stationary-bootstrap block-continuation draws. `python_hash_forbidden = true`, `reroll_forbidden = true`.

---

## 10. Per-world validity guards vs. aggregate acceptance cells (corrected taxonomy)

**Exactly 3 per-world validity guards**, each a distinct validity/correctness failure:

1. **Chronology** — training window for a scored era must never include that era or a later one.
2. **Support validity** — `support_count < 50`, or `effective_N` non-finite/out-of-range, invalidates the world.
3. **Identifiability & resampling validity** — rank-deficient OLS fit; non-finite required fit/prediction/statistic; block-length selector non-finite/undefined; any bootstrap replicate with zero resampled support.

**`NONSTATIONARY_TRAP` is NOT a per-world guard.** It is a fourth **aggregate acceptance cell**, using the identical per-world `DETECTED` decision (§8), aggregated with a `0.20` one-sided Wilson-upper ceiling instead of a power target — see §11.

**Diagnostics (never a second significance gate for the same null):** placebo result if computed, raw unadjusted conditional differential, unconditional/pool-wide differential, era-level effects, economic/materiality statistic, near-oracle reference if implemented, resampling-distribution shape/quantiles, `effective_N` beyond its range check, and the selected block length itself.

---

## 11. Aggregate Monte Carlo acceptance

400 fresh worlds per cell (`EASY`, `MODERATE`, `NULL`, `NONSTATIONARY_TRAP`), fresh seeds only (§9). 95% **one-sided** Wilson bound, `z = 1.6448536269514722`:

```text
center=(phat+z^2/(2n))/(1+z^2/n); half=z/(1+z^2/n)*sqrt(phat*(1-phat)/n+z^2/(4n^2))
lower=center-half; upper=center+half
```

| Cell | Target | PASS | FAIL | INDETERMINATE (successes) |
|---|---|---|---|---|
| EASY | power ≥ 0.90 | x≥370 (lower=0.90037) | x≤350 (upper=0.89971) | 351–369 |
| MODERATE | power ≥ 0.70 | x≥296 (lower=0.70240) | x≤264 (upper=0.69777) | 265–295 |
| NULL | FPR ≤ 0.05 | x≤12 (upper=0.04749) | x≥28 (lower=0.05178) | 13–27 |
| NONSTATIONARY_TRAP | detect ≤ 0.20 | x≤66 (upper=0.19776) | x≥94 (lower=0.20198) | 67–93 |

Independently verified: `n=400` is not structurally unable to reach any target — wide PASS/FAIL bands exist well inside `[0,400]` for every cell.

**TRAP statistic:** exactly the `DETECTED` indicator of §8, evaluated on `NONSTATIONARY_TRAP` worlds — **not** V2 `STRICT_PASS`/`STRICT_PASS_EX_MATERIALITY`. `NONSTATIONARY_TRAP` has frozen `beta_by_era = {E1:0.3, E2:0.3, E3:0.3, E4:0.0, E5:0.0}`: true effect exists in early scored eras and vanishes by E4/E5, so pooling `d*_t` across all four scored eras is expected to produce a diluted-but-nonzero average — hence the `0.20` ceiling rather than NULL's `0.05`.

Failed/invalid worlds remain in the planned denominator; any scientific-execution invalidity preventing frozen-aggregate evaluation produces `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`. No automatic second batch to resolve INDETERMINATE.

---

## 12. Required WORLD_RECORD diagnostics

Per world, where applicable: scenario/identity/seed/run identity; `support_count`, support fraction, support runs/clusters, `effective_N`; raw conditional differential; `theta_hat`; unconditional/pool-wide differential; `SE_hat`; `T_obs`; selected `b_hat` and selector status; `p_one_sided` and margin to 0.05; resampling summaries sufficient to explain a miss; era-level effects; visibility diagnostic if computed; identifiability state/reason; chronology/leakage state; materiality/economic diagnostic (non-authoritative); which validity guard (if any) fired. No statistic needed to explain a miss may be computed and discarded, as V2 discarded `bootstrap_q025`/`placebo_q95`.

---

## 13. Anti-rescue

No threshold, support rule, loss, statistic, block-length rule, alpha, confidence rule, or acceptance mapping may change after fresh V3 outcomes are inspected. No selective rerun, replacement world, second reservation, or second attempt. No seed reroll. No denominator replacement. No lowering NULL's 0.05 or TRAP's 0.20 to manufacture a PASS. No switching resampling family/selector after seeing outcomes. No converting a diagnostic into a gate (or vice versa) after seeing outcomes. No synthetic-as-market-evidence. No automatic second batch for INDETERMINATE.

---

## 14. V2 evidence boundary

V2 is `DEVELOPMENT-CONSUMED`. Its canonical RESULT (`761cc9af…`) and WORLD_RECORDS (`e8667f93…`) are diagnosis/design motivation only, never V3 acceptance evidence. V2's `world_index 0..399` ranges are excluded from V3 by construction (§9) — not merely by policy.

---

## 15. Execution ceremony

`this prereg materialized` → `independent prereg/implementation review` → `exact implementation + disposable non-canonical unit tests proving this document's mechanics` → `freeze implementation commit/tree` → `independent freeze review` → `explicit one-run ARM authorization` → `exactly one fresh sealed acceptance execution using §9's world-index range` → `persist complete evidence` → `inspect outcomes once` → any new methodology choice after outcomes requires a new prereg/version.

`implementation_exists = false`. Planned module: `scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py`; planned tests: `tests/research/test_harness_synthetic_edge_calibration_v3_confirmatory.py`. `production_calibration_executed = false`.

---

## 16. Amendment 001 — pre-outcome correctness/spec-completeness amendment

**Classification:** `PRE_OUTCOME_CORRECTNESS_AND_SPEC_COMPLETENESS_AMENDMENT`. Not outcome-driven, not a power repair, not a threshold repair, not a methodology redesign. Discovered and resolved before any V3 implementation, ARM, reservation, canonical world, or outcome existed.

**Parent frozen commit:** `4136f530378e91d545e2644a650f0a7a07a731c3` (`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE`), which remains valid historical evidence of the original, pre-amendment text and is not rewritten.

**Blocker 1 — RNG namespace impossibility.** The original text required `pcg64_generator(namespace_seed(world_seed, "V3_CONFIRMATORY", feature_id))`, but the frozen V1 `namespace_seed()` raises `ValueError` for any token outside `NAMESPACES = ("DGP","BOOTSTRAP","PLACEBO","VISIBILITY")`. The spec was therefore literally unimplementable as written. Resolved in §9 by a new, dedicated, non-frozen-file-modifying primitive (`scripts/research/harness_synthetic_edge_calibration_v3_rng.py`, `v3_namespace_seed`) that reproduces `namespace_seed`'s own hash construction exactly for the `"V3_CONFIRMATORY"` token, without editing `harness_synthetic_edge_calibration_v1_lib.py` (its SHA256 `12230dcad7…` is unchanged) or `FROZEN_V1_TCB_SHA256` in `harness_synthetic_edge_calibration_v2_production.py` (unchanged). Proven equivalent to what the frozen `namespace_seed()` would itself produce for this token (a local, in-memory-only, immediately-reverted allowlist extension inside a test — never written to disk), proven deterministic, and proven distinct from `BOOTSTRAP`/`PLACEBO` for the same world/context, by `tests/research/test_harness_synthetic_edge_calibration_v3_rng.py` (7/7 passing). All four existing namespace outputs and PCG64 stream prefixes are proven unchanged by the same test file.

**Blocker 2 — SE_hat ddof ambiguity.** The original text specified `SE_hat = stdev_b(theta*_b)` without binding the delta-degrees-of-freedom convention. Resolved in §8: `ddof=1` (sample standard deviation, Bessel's correction), equivalently `numpy.std(theta_star, ddof=1)`. `B=999`, `theta_hat`, `theta*_b` construction, `T_obs`, `T*_b`, the p-value formula, `alpha`, and every acceptance threshold are unchanged.

**Scope discipline:** no other section of this document was touched by this amendment. Clark-West adjustment, the estimand, candidate construction, support semantics and floor, `effective_N` semantics, the full-time-axis joint stationary-bootstrap algorithm, the block-length selector and its implementation authority, `B=999`, zero-support-replicate behavior, `alpha`, the Wilson aggregate rules, world counts, the fresh world-index range, TRAP semantics, the required diagnostics list, and `DEFAULT_V4` are all byte-for-byte unchanged from the frozen `4136f53` text.

---

## 17. Explicit state

```text
v3_design_complete = true
v3_prereg_materialized = true
v3_prereg_review_required = false
v3_prereg_amended = true
v3_amendment_001_applied = true
v3_prereg_frozen = false
v3_run_authorized = false
v3_armed = false
default_v4 = false
b2_06_execution_authorized = false
```

This document is the amended, frozen-candidate specification, closed for a new freeze. No fresh V3 acceptance outcome exists or may be inspected before that new freeze and an ARM.
