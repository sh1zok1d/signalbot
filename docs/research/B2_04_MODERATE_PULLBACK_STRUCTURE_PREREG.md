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

H04's broad preregistered pullback-continuation mechanism did not satisfy
its full promotion contract. Local effects, including a moderate-depth
residual, existed but did not form the required robust depth neighborhood
and remain `POSTHOC_UNTESTED`.

Canonical public evidence is mixed: some local cells satisfied effect or
control thresholds. That is **not** a claim that the primary effect was
directionally wrong in all 45 L×band×H cells, and it is **not** a
promoted moderate-depth mechanism.

The moderate residual is **hypothesis-generation material only**. It is **not** positive evidence for B2-04. B2-04 is an explicit `POSTHOC_UNTESTED` child: a new confirmatory formulation, not a rescue of H04.

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

Malformed / nonfinite descriptors (`MAX_ADVERSE ≤ 0`, nonfinite path, missing closes) do **not** delete the constructed event and do **not** change the refractory winner. The H-specific score record is jointly `UNAVAILABLE_FOR_DECISION` for baseline and candidate.

---

## 5. Event lifecycle (construction ≠ scoring)

Reuse H04 event semantics. Do not invent a new detector.

The pipeline is frozen in order. Later stages may mark a score record
unavailable. They may **not** rewrite earlier stages.

### STAGE A — CONSTRUCT EVENT

H04-compatible construction only:

1. 15-minute decision grid (`T` aligned to `tf_ms=900000`);
2. exact 1m closes required for `TREND_RET_L` and `PULLBACK_DEPTH`;
3. `TREND_RET_L ≠ 0` and `d = sign(TREND_RET_L)`;
4. `TREND_PCTL_L(T) ≥ 0.80` (H04 30-calendar-day midrank of `ABS_TREND_L`, current excluded);
5. `SIGNED_PB_RET(T) < 0`;
6. `FINAL_DEPTH = PULLBACK_DEPTH(T) ∈ [0.25, 0.40)`.

Forbidden at construction: `RECOVERY_FRACTION`, `RECOVERY_STATE`, `Y_H`, `H`, candidate prediction availability.

**No shallow `[0.10,0.25)` or deep `[0.40,1.00)` primary cells.** Those belong to the rejected H04 broad-depth hypothesis.

### STAGE B — REFRACTORY

60 minutes within each `L` on the **constructed moderate stream**. First-in-time wins. No cross-L suppression. No T-only global dedup.

Recovery availability, target availability, and `H` **must not** affect the refractory winner.

### STAGE C — IMMUTABLE EVENT POPULATION

Canonical base identity is fixed. Features and targets derived later cannot add, drop, or re-rank constructed events.

### STAGE D — DERIVE CAUSAL FEATURES AT T

Compute `RECOVERY_FRACTION`, the continuous `FINAL_DEPTH` control, and other model inputs from information available at `T`. A malformed recovery does not evict the event from Stage C.

### STAGE E — CREATE H-SPECIFIC SCORE RECORD

Attach `H`. Require `T+H < 2025-01-01T00:00:00Z`, causal scale, and finite `Y_H`. Failure here makes the score record unavailable. It does not change Stage C.

### STAGE F — SAME-SUPPORT FORECAST COMPARISON

Baseline and candidate use the exact same score records. No candidate fallback. No candidate-only depth transform.

Candidate and baseline therefore share constructed support. `RECOVERY_FRACTION` may score an event. It may **not** decide whether the event exists.

---

## 6. Canonical identities

Construction and refractory use a pre-H base identity:

```text
CANONICAL_BASE_EVENT_ID = snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms
```

Horizon evaluation uses:

```text
CANONICAL_SCORE_RECORD_ID = CANONICAL_BASE_EVENT_ID|H_minutes
```

which expands to:

```text
CANONICAL_EVENT_ID = snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms|H_minutes
```

where `pullback_start_ms = T_ms - 60*60000`, `T_ms` is decision time `T` as integer UTC epoch milliseconds, and `direction` is exactly `UP` or `DOWN`.

Baseline and candidate carry **identical** score-record IDs on the same support. Refractory selection uses the base identity, never `H` and never `T` alone.

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
- Horizon alignment: `T` and `T+H` on the 15m grid. Last legal scored `T` is the latest 15m grid time satisfying `T+H < 2025-01-01T00:00:00Z` (`close(T+H)` at exactly `2025-01-01T00:00:00Z` is illegal):

| H (minutes) | last legal T |
|---|---|
| 15 | `2024-12-31T23:30:00Z` |
| 30 | `2024-12-31T23:15:00Z` |
| 60 | `2024-12-31T22:45:00Z` |
| 120 | `2024-12-31T21:45:00Z` |
| 240 | `2024-12-31T19:45:00Z` |
- No future outcomes and no whole-sample statistics enter the scale.

Positive `Y_H` is continuation in the established trend direction.

---

## 9. Recovery representation (exactly one candidate feature)

Primary candidate uses **one** representation: untransformed continuous
`RECOVERY_FRACTION ∈ [0, 1]`.

No percentile, no LOW/MID/HIGH state, no other transform enters the
candidate. Algebra:

```text
RECOVERY_FRACTION = 1 - FINAL_DEPTH / MAX_ADVERSE
```

Given `FINAL_DEPTH`, remaining recovery variation is variation in
`MAX_ADVERSE`. That is the structural increment the candidate is allowed
to use.

`RECOVERY_STATE ∈ {LOW, HIGH}` exists **only** for the `structure_ordering`
gate (causal 365-day same-`L` midrank of `RECOVERY_FRACTION`, directions
pooled, current excluded, `>= 0.5` → `HIGH`). It is not a candidate
feature and is not used to construct or suppress events.

---

## 10. Baseline: trend state + actual pullback depth

`RECOVERY_FRACTION` is algebraically dependent on `FINAL_DEPTH`. A two-bin
`DEPTH_HALF` control is **forbidden**: recovery could proxy leftover
within-half depth and still look like structure.

The frozen actual-depth control is **untransformed continuous
`FINAL_DEPTH`** inside one OLS family.

```text
BASELINE:   Y_H = a + b * FINAL_DEPTH
CANDIDATE:  Y_H = a + b * FINAL_DEPTH + c * RECOVERY_FRACTION
```

Fit separately within each `(L, DIRECTION)` causal training pool. Same
events, same `Y_H`, same estimator. The only information difference is
`RECOVERY_FRACTION`.

Boolean `MODERATE = TRUE` is also forbidden as the depth control.

---

## 11. Prediction family

One fixed family: **ordinary least squares** within `(L, DIRECTION)`.

- unweighted;
- no regularization;
- no column standardization;
- no pseudoinverse;
- prediction = `xβ` at the evaluation event;
- evaluation loss remains MAE;
- if `N < 30`, or `X'X` is singular, or any coefficient is nonfinite:
  both sides `UNAVAILABLE_FOR_DECISION`;
- no candidate→baseline fallback;
- no intercept-only fallback that drops `FINAL_DEPTH`.

No hyperparameter search. No unrelated model-class comparison.

---

## 12. Causal training and support feasibility (outcome-blind)

For every evaluation event at `T`:

```
training_T + H ≤ current_T
```

Training history: **365 calendar days**. Shared minimum: **30** observations
in the `(L, DIRECTION)` pool (3 OLS parameters; no pseudoinverse).

If the candidate cannot fit, the baseline is also `UNAVAILABLE_FOR_DECISION`
for that score record (joint fail-closed).

### Why not copy B2-03’s 90d / 80 / 40 / DEPTH_HALF strata

Public H04 **post-refractory moderate** development counts (`H04_DEV_SUMMARY.md`):

| L | N_moderate | events / day (N / 1796d) |
|---|---|---|
| 240 | 2511 | ≈ 1.40 |
| 480 | 1691 | ≈ 0.94 |
| 960 | 892 | ≈ 0.50 |

Expected 365-day training occupancy (outcome-blind arithmetic):

| L | ~events / 365d | ~per direction (×0.5) | OLS params baseline/candidate |
|---|---|---|---|
| 240 | 510 | 255 | 2 / 3 |
| 480 | 344 | 172 | 2 / 3 |
| 960 | 181 | 90 | 2 / 3 |

90-day occupancy at `L=960` is about 45 events before the direction split.
That is too tight for a 3-parameter OLS plus MAE evaluation. 365d keeps
all three `L` values and supplies an actual-depth regressor without a
sparse categorical cross-product. This is a **sample-size / simplicity /
numerical-stability** choice. It is **not** a return-based choice.

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

- permute **historical training** `RECOVERY_FRACTION` only, inside the evaluation event’s `(L, DIRECTION)` training pool;
- evaluation-event recovery stays fixed;
- `Y` stays fixed;
- `FINAL_DEPTH` stays fixed;
- sort by `CANONICAL_SCORE_RECORD_ID` before RNG;
- `N_PLACEBO = 100`;
- `PLACEBO_BASE_SEED = 20260906`;
- seed derivation: `20260906|{replicate}|{L}|{H}|{T_ms}|{baseline_stratum_id}` with `baseline_stratum_id = L_minutes|direction` → SHA-256 hex, first 16 hex digits as integer (same `_seed_int` convention as B2-02/B2-03);
- same model and evaluation procedure as primary.

---

## 15. Bootstrap

UTC-week block bootstrap (`week_id = ISO_week_year * 100 + ISO_week`, UTC `datetime.isocalendar()`, not the Gregorian calendar year).

- `N_BOOT = 2000`;
- `BOOTSTRAP_BASE_SEED = 20260907`;
- 95% interval = bootstrap percentiles 2.5 and 97.5 of pooled mean `AE_IMPROVEMENT`;
- seed derivation: `20260907|{replicate}|{L}|{H}` → SHA-256, first 16 hex digits;
- resample whole weeks with replacement; concatenate events in canonical-id order within each drawn week;
- empty resample → that replicate is nonfinite and does not count toward a passing lower bound.

H04 moderate event frequency does **not** require a different block. Default UTC-week is retained.

---

## 16. Promotion contract (exactly eight gates)

No hidden ninth gate. The five per-cell gates are evaluated on each `L×H` cell. `horizon_robustness`, `parameter_robustness`, and `year_stability` are neighborhood gates. Family promotion requires all eight named gates true.

| Gate | Rule |
|---|---|
| `primary_positive` | mean `AE_IMPROVEMENT` `> 0` pooled, UP, and DOWN; all finite |
| `material_relative_mae` | pooled relative MAE improvement `≥ 0.02` (Batch02 standard; not optimized) |
| `bootstrap_positive` | pooled UTC-week bootstrap 95% lower bound `> 0` |
| `placebo_separation` | observed pooled mean AE improvement `>` frozen placebo q95 |
| `structure_ordering` | median `BASE_RESIDUAL = Y − BASE_PRED` for `HIGH` minus `LOW` is `> 0` pooled, UP, and DOWN (causal HIGH/LOW is gate-only; §9) |
| `horizon_robustness` | at least one adjacent-H pair among `{15,30}`, `{30,60}`, `{60,120}`, `{120,240}` within the same `L` has `primary_positive ∧ material_relative_mae ∧ bootstrap_positive ∧ placebo_separation ∧ structure_ordering` on **both** members |
| `parameter_robustness` | the **same** adjacent-H pair also satisfies that five-gate bundle at **another** `L` (cannot promote on historically attractive H04 L alone) |
| `year_stability` | **every cell in the promotion neighborhood** (the adjacent-H pair at both promoting `L` values) has pooled mean AE improvement `> 0` in at least **4 of 5** calendar years `{2020,2021,2022,2023,2024}` of that cell’s event `T`; no year exclusions after inspection |

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
- last legal `T` also requires `T+H < 2025-01-01T00:00:00Z` on the 15m grid (table in §8); `close(T+H)` at exactly `2025-01-01T00:00:00Z` is illegal
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
