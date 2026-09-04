# B2-04 Moderate Pullback Structure — Frozen Preregistration

**Status:** FROZEN_BEFORE_IMPLEMENTATION  
**Hypothesis ID:** `B2-04_MODERATE_PULLBACK_STRUCTURE`  
**Primary family:** F1 — directional persistence / continuation  
**This document:** outcome-blind design unit. No B2-04 runner, no CORE parquet access, no durable reservation, no outcome claim.

Machine-readable twin: [`B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json`](B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json).

---

## 0. Authority and freeze

This preregistration instantiates the immutable inventory entry:

- ID = `B2-04_MODERATE_PULLBACK_STRUCTURE`
- PRIMARY_FAMILY = F1
- BATCH01_SOURCE = H04 isolated moderate-depth/local residual
- PROVENANCE = explicit `POSTHOC_UNTESTED` child
- ADMISSION = `ADMIT_TO_V2_INVENTORY`

`docs/research/V2_FORMULATION_INVENTORY.md` is **not** modified by this unit.

This unit does **not**:

- implement `scripts/research/b2_04_*.py`;
- run B2-04;
- open CORE parquet;
- create a durable evidence reservation;
- claim outcome access;
- inspect 2025 validation or 2026 OOS.

`outcome_access_authorized = false`.

---

## 1. Frozen H04 provenance (public evidence only)

`H04_VERDICT = H04_REJECTED_SPECIFIC_CLAIM`.

H04 tested the **broad** claim that a material counter-trend pullback, after established trend, is a continuation setup. That specific claim failed on development. Public summary:

- primary continuation MAE vs same-sign no-pullback control was **not** directionally correct at any of the 45 L×band×H cells;
- the moderate band `[0.25,0.40)` showed a **local residual** that was **not** the confirmatory claim.

That residual is **hypothesis-generation material only**. It is **not** positive evidence for B2-04. B2-04 is an explicit `POSTHOC_UNTESTED` child: a new confirmatory formulation, not a rescue of H04.

Public H04 event counts used below are taken from `docs/research/H04_DEV_SUMMARY.md` / `H04_DEV_RESULTS.json`. This unit does **not** open underlying market parquet.

---

## 2. Exact mechanism

**Inventory claim (verbatim):**

> Within an established directional state and a preregistered moderate pullback domain, one predeclared structural property of the pullback/recovery process adds stable continuation information beyond trend state + pullback depth alone.

The new information is **structure**, not:

- another depth threshold;
- a better L;
- another trend indicator;
- another volatility filter;
- whichever H04 cell was strongest;
- another generic momentum indicator.

B2-04 is **not** B2-03. B2-03 tested generic same-displacement **impulse path morphology** (`DISTRIBUTEDNESS`, `PATH_EFFICIENCY`, `DIRECTIONAL_BAR_SHARE`, `COUNTERMOVE_SHALLOWNESS`) and closed `B2_03_CLOSED_NO_PROMOTION`. Those features are **forbidden** as B2-04 candidates. B2-03 outcomes are **not** used to tune B2-04.

Novelty:

| | B2-03 | B2-04 |
|---|---|---|
| Object | shape of an impulse generating a displacement | degree of recovery from the deepest adverse excursion |
| Conditioning | same signed log-return magnitude | already-qualified moderate counter-trend pullback in an established trend |
| Property family | path morphology menu (one selected) | `INTRA_PULLBACK_RECOVERY` only |

---

## 3. Exactly one structural property: `INTRA_PULLBACK_RECOVERY`

Intended mechanism:

> Among pullbacks with the same established-trend context and similar final moderate depth, a pullback that has already recovered more strongly from its deepest counter-trend excursion by decision time T may contain different continuation information from a pullback that remains near its deepest excursion.

This is a **pullback/recovery interaction**. It is not an open-ended path-morphology menu.

Directional prior (frozen before outcomes):

**higher `RECOVERY_FRACTION` → stronger subsequent trend-direction continuation.**

If data later show the reverse, that is **failure of this formulation**. Exhaustion / sign-flip rescue is forbidden. UP and DOWN consistency are part of the primary contract.

---

## 4. Descriptor audit (H04 compatibility)

H04 frozen definitions (close-only, 15m grid, `P = 60`):

```
TREND_RET_L(T) = ln(close(T-P) / close(T-P-L))
d              = sign(TREND_RET_L(T)) ∈ {+1, −1}
SIGNED_PB_RET(T) = d * ln(close(T) / close(T-P))
PULLBACK_DEPTH(T) = −SIGNED_PB_RET(T) / abs(TREND_RET_L(T))
```

A qualifying H04 event requires `SIGNED_PB_RET(T) < 0` and therefore `PULLBACK_DEPTH(T) > 0`.

### 4.1 Path points

Using only fully available 15m closes in `[T−60m, T]`, the four pullback-step closes are:

`{close(T−45m), close(T−30m), close(T−15m), close(T)}`.

`close(T−60m)` is the **path origin**, not a path step (adverse at origin is identically 0).

### 4.2 Event-level trend context (mechanical clarification)

`d` and `TREND_RET_L` are **frozen at the event** using H04’s definitions at `T`. They are **not** recomputed at interior path times. This is required so that the final adverse step equals H04 `PULLBACK_DEPTH`.

### 4.3 Adverse displacement and recovery

For each path close `close_j`:

```
ADVERSE_j = −d * ln(close_j / close(T−60m)) / abs(TREND_RET_L)
```

At `j = T`:

```
ADVERSE_T = −d * ln(close(T) / close(T−60m)) / abs(TREND_RET_L)
          = PULLBACK_DEPTH(T)
```

so `FINAL_DEPTH := ADVERSE_T` is **exactly** H04 `PULLBACK_DEPTH`. Sign convention is correct for UP (`d=+1`) and DOWN (`d=−1`) events.

```
MAX_ADVERSE = max_j ADVERSE_j
RECOVERY_FRACTION = (MAX_ADVERSE − FINAL_DEPTH) / MAX_ADVERSE
```

On B2-04 qualifying events, `FINAL_DEPTH ∈ [0.25, 0.40)`, so `MAX_ADVERSE ≥ FINAL_DEPTH > 0`. Therefore `RECOVERY_FRACTION` is finite and in `[0, 1]`.

Interpretation:

- `0` = price ends at its deepest counter-trend excursion among the four path points;
- higher = a deeper counter-trend excursion occurred earlier in the 60m window and price recovered part of it by `T`.

### 4.4 Audit checklist

| Check | Result |
|---|---|
| Final adverse = H04 `PULLBACK_DEPTH` | yes, by algebra |
| Sign convention UP/DOWN | yes |
| `MAX_ADVERSE ≥ FINAL_DEPTH` | by construction of max |
| Finite and bounded on valid events | yes, `[0,1]` |
| High/low/close ambiguity | none: close-only |
| Future information | none: path ⊆ `[T−60m, T]` |
| Silent change to H04 eligibility | none: recovery scores events; it does not decide existence |

**No `B2_04_PREREG_DESCRIPTOR_CONTRACT_REPAIR_REQUIRED`.** The only mechanical clarification is event-level (not step-level) `d` and `TREND_RET_L`.

Malformed / nonfinite descriptors (`MAX_ADVERSE ≤ 0`, nonfinite path, missing closes) fail closed: the event is jointly `UNAVAILABLE_FOR_DECISION` for baseline and candidate. Recovery may **not** drop events because the recovery state later proves inconvenient.

---

## 5. Event support (H04 semantics, moderate domain only)

Reuse H04 event semantics. Do not invent a new detector.

A B2-04 qualifying event requires **all** of:

1. 15-minute decision grid (`T` aligned to `tf_ms=900000`);
2. exact 1m close at `T` and at every required lookback/horizon close;
3. `TREND_RET_L ≠ 0` and `d = sign(TREND_RET_L)`;
4. `TREND_PCTL_L(T) ≥ 0.80` (H04 30-calendar-day midrank of `ABS_TREND_L`, current excluded, `ref_t + 0 ≤ T`);
5. `SIGNED_PB_RET(T) < 0`;
6. `FINAL_DEPTH = PULLBACK_DEPTH(T) ∈ [0.25, 0.40)` — **moderate domain only**;
7. `MAX_ADVERSE > 0` and finite `RECOVERY_FRACTION ∈ [0, 1]`;
8. causal target `Y_H` available (exact 1m close at `T+H`; scale estimator defined below).

**No shallow `[0.10,0.25)` or deep `[0.40,1.00)` primary cells.** Those belong to the rejected H04 broad-depth hypothesis.

**Refractory:** 60 minutes within each `L`, applied on the **moderate-only** qualifying stream (same rule H04 used inside each L×band). First-in-time wins. No cross-L suppression. No T-only global dedup.

Candidate and baseline use **exactly the same** qualifying events. `RECOVERY_FRACTION` classifies/scores; it does **not** decide whether the event exists.

---

## 6. Canonical event identity

One exact serialization (no generic T-only identity):

```
CANONICAL_EVENT_ID = snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms|H_minutes
```

where `pullback_start_ms = T_ms - 60*60000`, `T_ms` is decision time `T` as integer UTC epoch milliseconds, and `direction` is exactly `UP` or `DOWN`.

Baseline and candidate carry **identical** event IDs on the same support. Deduplication is by this identity, never by `T` alone.

---

## 7. Anti-cherry-pick surface

H04 used `L = {240,480,960}`, `P = 60`, depth bands including moderate `[0.25,0.40)`, and `H = {15,30,60,120,240}`.

B2-04 **may** focus on the already-declared moderate domain because that provenance is frozen in the V2 inventory.

B2-04 **must not** drop `L=240` because H04’s historically attractive cells were `L=480/960`. The primary search surface retains:

- `L = {240, 480, 960}`
- `H = {15, 30, 60, 120, 240}`
- moderate depth fixed `[0.25, 0.40)`

**15 primary cells.** No new depth search dimension. No selection of H04’s best horizon.

---

## 8. Target (Batch02 / H04 continuation primitive)

```
RAW_FUTURE_RET_H(T) = ln(close(T+H) / close(T))
Y_H(T) = d * RAW_FUTURE_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)
```

- `d` is the H04 event trend direction at `T`.
- `PAST_MEDIAN_ABS_RET_H` is the median of `|ln(close(t+H)/close(t))|` on the 15m grid over the prior 30 calendar days with `ref_t + H ≤ T` (current excluded). Exact 1m closes. If the reference set is empty or the median is non-positive/nonfinite, the event is jointly unavailable.
- Horizon alignment: `T` and `T+H` on the 15m grid; last legal scored `T` satisfies `T+H < 2025-01-01T00:00:00Z`.
- No future outcomes and no whole-sample statistics enter the scale.

Positive `Y_H` is continuation in the established trend direction.

---

## 9. Recovery representation (exactly one)

Primary candidate uses **one** representation:

`RECOVERY_STATE ∈ {LOW, HIGH}` = causal midrank percentile of `RECOVERY_FRACTION` versus prior same-`L` moderate events, **directions pooled**, current excluded.

- reference window: 365 calendar days;
- inclusion: `ref_T < current_T` and `ref_T` in the same `L` moderate qualifying stream;
- threshold: midrank percentile `>= 0.5` → `HIGH`, else `LOW`;
- if the reference set is empty: fail closed (`UNAVAILABLE_FOR_DECISION`) jointly.

No full-sample quantiles. No tertiles (sparsity). No alternative transforms in the primary candidate.

---

## 10. Baseline: trend state + within-band depth

The baseline must represent **established trend state + pullback depth**, not merely `MODERATE = TRUE`. A boolean moderate flag would let `RECOVERY_FRACTION` proxy for meaningful within-band depth differences.

`DEPTH_HALF ∈ {LOWER, UPPER}` = causal midrank percentile of `FINAL_DEPTH` versus the same 365-day same-`L` moderate prior stream, directions pooled, current excluded, cut at 0.5.

Baseline features: `{L, DIRECTION, DEPTH_HALF}` (4 strata per L).  
Candidate features: `{L, DIRECTION, DEPTH_HALF, RECOVERY_STATE}` (8 strata per L).

Only information difference: candidate adds `RECOVERY_STATE`.

---

## 11. Prediction family

One fixed family for baseline and candidate: **stratum-conditional training median** of `Y_H`.

- same events, same `Y_H`, same MAE loss, same horizons, same fit schedule;
- prediction = median `Y_H` of causal training records in the matching stratum;
- empty/insufficient stratum → `UNAVAILABLE_FOR_DECISION` (no candidate→baseline fallback that would change same-support comparison).

No hyperparameter search. No unrelated model-class comparison.

---

## 12. Causal training and support feasibility (outcome-blind)

For every evaluation event at `T`:

```
training_T + H ≤ current_T
```

Training history: **365 calendar days** (not B2-03’s 90d).

Minimum training support (frozen from public H04 counts, **not** from returns):

| Role | Minimum |
|---|---|
| Baseline stratum | 20 |
| Candidate stratum | 10 |

If either side is insufficient, **both** sides are `UNAVAILABLE_FOR_DECISION` for that event (joint fail-closed).

### Why not copy B2-03’s 90d / 80 / 40 / large cross-product

Public H04 **post-refractory moderate** development counts (`H04_DEV_SUMMARY.md`):

| L | N_moderate | events / day (N / 1796d) |
|---|---|---|
| 240 | 2511 | ≈ 1.40 |
| 480 | 1691 | ≈ 0.94 |
| 960 | 892 | ≈ 0.50 |

Expected 365-day training occupancy (outcome-blind arithmetic):

| L | ~events / 365d | ~per baseline stratum (÷4) | ~per candidate stratum (÷8) |
|---|---|---|---|
| 240 | 510 | 128 | 64 |
| 480 | 344 | 86 | 43 |
| 960 | 181 | 45 | 23 |

90-day occupancy would be ~3× smaller. A baseline-min-80 / candidate-min-40 rule, especially with more than two recovery states or direction-split recovery ranks, is **not viable** at `L=960`.

Binary depth half × binary recovery, 365d history, mins 20/10, keep all three L values. This is a **sample-size / simplicity / numerical-stability** choice. It is **not** a return-based choice. `L=960` remains the tightest cell; insufficient-stratum events fail closed rather than being patched.

---

## 13. Loss and comparisons

Primary loss: MAE of `Y_H`.

Per event, both models must produce finite predictions; otherwise the event is excluded from **both** (same-support).

```
AE_IMPROVEMENT = |Y − BASE_PRED| − |Y − CAND_PRED|
RELATIVE_MAE_IMPROVEMENT = 1 − MAE_CAND / MAE_BASE
```

when `MAE_BASE > 0` and finite. Nonfinite / non-positive baseline MAE → cell fails `material_relative_mae` rather than promoting.

---

## 14. Placebo (exactly one scheme)

Question: could an apparent improvement from recovery structure arise merely from assigning recovery information within comparable baseline context?

- permute **historical training** `RECOVERY_STATE` only, **inside the evaluation event’s baseline stratum**;
- evaluation-event recovery stays fixed;
- `Y` stays fixed;
- baseline context stays fixed;
- canonical event-id sort before RNG;
- `N_PLACEBO = 100`;
- `PLACEBO_BASE_SEED = 20260906`;
- seed derivation: `20260906|{replicate}|{L}|{H}|{T_ms}|{baseline_stratum_id}` → SHA-256 hex, first 16 hex digits as integer (same `_seed_int` convention as B2-02/B2-03);
- same model and evaluation procedure as primary.

---

## 15. Bootstrap

UTC-week block bootstrap (`week_id = UTC year * 100 + UTC ISO week`).

- `N_BOOT = 2000`;
- `BOOTSTRAP_BASE_SEED = 20260907`;
- 95% interval = bootstrap percentiles 2.5 and 97.5 of pooled mean `AE_IMPROVEMENT`;
- seed derivation: `20260907|{replicate}|{L}|{H}` → SHA-256, first 16 hex digits;
- resample whole weeks with replacement; concatenate events in canonical-id order within each drawn week;
- empty resample → that replicate is nonfinite and does not count toward a passing lower bound.

H04 moderate event frequency does **not** require a different block. Default UTC-week is retained.

---

## 16. Promotion contract (exactly eight gates)

No hidden ninth gate. A cell is `CELL_PROMOTED` iff all eight are true. Family promotion requires **at least one** `CELL_PROMOTED`.

| Gate | Rule |
|---|---|
| `primary_positive` | mean `AE_IMPROVEMENT` `> 0` pooled, UP, and DOWN; all finite |
| `material_relative_mae` | pooled relative MAE improvement `≥ 0.02` (Batch02 standard; not optimized) |
| `bootstrap_positive` | pooled UTC-week bootstrap 95% lower bound `> 0` |
| `placebo_separation` | observed pooled mean AE improvement `>` frozen placebo q95 |
| `structure_ordering` | median `BASE_RESIDUAL = Y − BASE_PRED` for `HIGH` minus `LOW` is `> 0` pooled, UP, and DOWN (causal HIGH/LOW from §9) |
| `horizon_robustness` | at least one adjacent-H pair among `{15,30}`, `{30,60}`, `{60,120}`, `{120,240}` within the same `L` has `primary_positive ∧ material_relative_mae ∧ bootstrap_positive ∧ placebo_separation ∧ structure_ordering` on **both** members |
| `parameter_robustness` | the **same** adjacent-H pair also satisfies that five-gate bundle at **another** `L` (cannot promote on historically attractive H04 L alone) |
| `year_stability` | among calendar years `{2020,2021,2022,2023,2024}` of the event’s `T`, at least **4 of 5** have pooled mean AE improvement `> 0`; no year exclusions after inspection |

`NO_PROMOTION` → scientific verdict `B2_04_CLOSED_NO_PROMOTION`. That closes the H04 child path inside current V2. It does **not** mean bearish, bullish, or no-trade.

Integrity / operational failure is **neither** scientific verdict.

---

## 17. Anti-rescue (exactly one B2-04 attempt)

If `NO_PROMOTION`:

**Forbidden afterward:**

- another moderate threshold;
- narrow depth around an attractive result;
- shallow/deep rescue;
- another recovery formula;
- another L subset;
- another horizon subset;
- sign reversal;
- exhaustion reinterpretation;
- another structural property;
- new trend indicator;
- B2-04 child-of-child.

There is exactly **one** B2-04 attempt. Failure closes this H04 child path inside current V2.

---

## 18. Dataset and development boundary

- `DATASET_ID = CORE_BTC_BINANCE_V0`
- `SNAPSHOT_ID = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- scored development: `2020-02-01T00:00:00Z ≤ T < 2025-01-01T00:00:00Z`
- last legal `T` also requires `T+H < 2025-01-01T00:00:00Z`
- warmup/reference may use authorized January 2020 CORE history only as already permitted by CORE/H04 semantics
- **2025 validation = UNTOUCHED**
- **2026 OOS = UNTOUCHED**

---

## 19. Future durable-evidence ceremony (not executed in this unit)

The future implementation **must** use the already-accepted B2-03+ contract:

1. `verify_batch02_code`
2. `prepare_batch02_evidence_reservation`
3. `prepare_batch02_retained_run`
4. `load_authorized_parquet_table`
5. evaluate
6. `persist_batch02_retained_result`
7. `archive_batch02_result`

Protected production slot: **`B2-04`**.  
Evidence ref: `refs/heads/research-evidence/batch02/B2-04/<code_sha>`.

No historical retention API. No direct parquet reads in the production B2-04 runner. No result may be returned before durable archive and readback succeed.

This preregistration unit:

- `B2_04_RESERVATION_CREATED = NO`
- `B2_04_OUTCOME_ACCESS_CLAIMED = NO`
- `B2_04_RUN = NO`

This unit does **not** modify retention infrastructure.

### Credential operational lesson (B2-03 precedent; not a statistical change)

The B2-03 first invoke aborted **before claim** because isolated evidence git uses `GIT_CONFIG_GLOBAL=/dev/null`, so host `url.*.insteadOf` credential helpers were invisible (`PRE_CLAIM_OPERATIONAL_ABORT`). That incident is **operational only**. It must **not** change B2-04 statistics, gates, seeds, or promotion rules.

The **future execution-host preflight** (before one-shot authorization) must verify **authenticated isolated evidence transport** — specifically that `git ls-remote` to GitHub over HTTPS succeeds **inside the retention subprocess environment** (empty global git config), using ephemeral `GIT_ASKPASS` + `GITHUB_TOKEN` from the environment, **not** `insteadOf` rewriting and **not** tokens in files or remote URLs.

---

## 20. Implementation prohibition (this PR)

This PR must **not** create:

- `scripts/research/b2_04_*.py`
- a B2-04 result JSON
- a runner, evaluator, CORE loader invocation, reservation, or claim

---

## 21. Scientific verdicts (future run only)

Only:

- `B2_04_PROMOTED_CANDIDATE`
- `B2_04_CLOSED_NO_PROMOTION`

`NO_PROMOTION` is not a market recommendation.
