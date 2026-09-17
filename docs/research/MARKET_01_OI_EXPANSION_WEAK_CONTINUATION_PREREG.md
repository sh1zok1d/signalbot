# MARKET-01 OI_EXPANSION_WEAK_CONTINUATION — Preregistration

- **Status:** `PREREGISTERED_OUTCOME_BLIND_UNFROZEN`
- **Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`
- **Machine-readable twin:** `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json`
- **Parent feasibility:** `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_DATA_FEASIBILITY.md` (commit `901f96eaa551e2591a6212a14ddd4488f5528e8e`)
- **Parent design/blocker record:** `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_DESIGN.md` (commit `5a629819676240e98b6b125aa4606e8759c1f0f2`)
- **Date:** 2026-09-17
- **Outcome inspection:** **NO**
- **Prereg freeze:** **NOT THIS UNIT** (`MARKET_01_FREEZE_REQUIRED = YES`)
- **ARM / execution:** **NO**
- **Evaluator implemented:** **NO**

This document is the complete outcome-blind MARKET-01 preregistration after
explicit research-author resolution of:

- `BLOCKER_BASELINE_MATCHING_SEMANTICS`
- `V3_CONFIRMATORY_ESTIMAND_NOT_MAPPABLE_TO_TWO_GROUP_REVERSAL_CONTRAST`
- `BLOCKER_ROBUSTNESS_SEMANTICS`
- the unbound support floor

It does **not** freeze, ARM, implement, or execute. A separate freeze is
required before implementation. No MARKET outcomes were inspected to write
this text. Thresholds and windows below are author-frozen, not searched.

Machine-readable twin: `MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json`.

---

## 0. What this is and is not

Market-relationship study. First real-market study of the MARKET phase.

Not a trading strategy. Forbidden in this prereg and any later RESULT:

entries, exits, stop-losses, take-profits, fees, Sharpe, position sizing,
PnL optimization, production enablement, automatic OOS promotion.

"Absorption", "crowding", and leverage accumulation are possible mechanism
interpretations only. They are not observed facts and are not encoded as
proven.

V3 is **not** the MARKET-01 confirmatory test. V3 remains closed historical
instrumentation (`V3_METHODOLOGY_CLAIMABLE = NO`). This prereg does not
modify V3 and does not create V4 (`DEFAULT_V4 = NO`).

The MARKET-01 confirmatory test is a **new** scientific identity. V3
synthetic calibration does **not** validate it. The V3
`NONSTATIONARY_TRAP = FAIL` result is why this prereg includes a
prospective temporal robustness **downgrade** layer. The MARKET-01 test
itself is **uncalibrated** (`MARKET_01_TEST_CALIBRATED = NO`). This
limitation must be restated in any later RESULT. No new synthetic
calibration phase is authorized by this document.

B2-06 remains `BLOCKED_MISSING_OBSERVABLE`. Using OI rows from snapshot
`5a9d036b…` does not unblock B2-06. Funding is unusable.

Protected 2025 validation and 2026 OOS remain untouched and forbidden.

---

## 1. Research identity

```text
MARKET-01_OI_EXPANSION_WEAK_CONTINUATION
```

Primary claim (relationship, not a strategy):

After a significant directional 30-minute price impulse, the state in
which open interest expands while price exhibits weak continuation in the
impulse direction is associated with stronger subsequent 60-minute
reversal than comparable impulse episodes without the full OI-expansion /
weak-continuation state.

---

## 2. Data authorities

### 2.1 Price

```text
dataset_id     = CORE_BTC_BINANCE_V0
snapshot_id    = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
venue          = Binance
instrument     = BTCUSDT
market_type    = USD_M_FUTURES / perpetual
native grain   = 1m klines
evidence_tier  = OFFICIAL_ARCHIVE / HISTORICAL_COMPARABLE
research_authorized (discovery) = true
confirmatory_authorized         = false
```

`open_time_ms` = bar start.

`available_at = bar_end_exclusive = open_time + 60s`.

`close(T)` is the close of the canonical 1m bar whose `bar_end_exclusive`
equals `T`. The still-forming bar is never used.

CORE frozen range includes `[2020-01-01, 2026-08-26)` with 0 missing
minutes. This study may use price only inside the common legal period
in §2.3.

### 2.2 Open interest

```text
source         = Binance Vision daily/metrics/BTCUSDT
field          = sum_open_interest
snapshot_id    = 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
native grain   = 5m
create_time    = bucket start
available_at   = create_time + 5 minutes
```

Legal OI at clock `U`:

the latest observation with `available_at <= U` **and**
`U - available_at <= 300000` ms.

If none exists: missing. Never fill, never interpolate, never substitute
zero, never upsample to 1m, never extend staleness.

Funding in the same snapshot is **out of scope** and not legally
consumable.

### 2.3 Common legal period and grain

```text
common_start_inclusive = 2020-09-01T00:00:00Z
common_end_exclusive   = 2025-01-01T00:00:00Z
decision_grain         = UTC-epoch 5-minute boundaries
```

An accepted episode's full span `[impulse_start, outcome_end]` must
satisfy:

```text
impulse_start >= 2020-09-01T00:00:00Z
outcome_end   <= 2025-01-01T00:00:00Z
```

2025/2026 price outside this common authority is unavailable to this
study.

---

## 3. Temporal structure

Let `t` be a UTC 5-minute boundary (impulse endpoint).

```text
impulse_start     = t - 30m
impulse_end       = t
state_start       = t
state_end = T     = t + 30m     (decision time)
outcome_end       = T + 60m = t + 90m
full_episode_span = 120m
```

```text
[t-30m ........ t]          IMPULSE
[t ........ t+30m]          STATE FORMATION
decision time               T = t+30m
[t+30m ........ t+90m]      OUTCOME
```

No information from the OUTCOME window may enter eligibility, impulse /
OI-expansion / weak-continuation classification, normalization, tertile
construction, matching/stratification, threshold selection, or support
selection.

---

## 4. Impulse

```text
impulse_return(t) = ln( close(t) / close(t-30m) )
D(t)              = sign(impulse_return(t))
abs_impulse(t)    = abs(impulse_return(t))
```

Exact-zero `impulse_return` is not a qualifying impulse (`D` undefined):
`EPISODE_NOT_ELIGIBLE`.

Historical reference for extremeness: all UTC 5-minute boundaries `τ`
whose 30-minute price window `[τ-30m, τ]` is fully legally available and
lies entirely before `impulse_start`:

```text
τ <= impulse_start
τ-30m >= 2020-09-01T00:00:00Z or whenever CORE bars exist
τ in [impulse_start - 30 calendar days, impulse_start)
```

30 calendar days = `30 * 86400000` ms UTC.

Midrank percentile, H01/H03/B2-03 formula:

```text
P_impulse = ( #{ref < abs_impulse} + 0.5 * #{ref == abs_impulse} ) / N_ref
```

`QUALIFYING_IMPULSE` iff `P_impulse >= 0.90` and `N_ref >= 1`.

Empty or non-finite reference, missing required closes, or non-finite
`impulse_return`: `EPISODE_NOT_ELIGIBLE`. No fallback threshold.

---

## 5. OI expansion

During STATE FORMATION, using only legal native OI:

```text
OI_start = legal OI at U = t
OI_end   = legal OI at U = T = t+30m
delta_oi = log(OI_end / OI_start)
```

Both OI values must be finite and **strictly positive**. Otherwise
`EPISODE_NOT_ELIGIBLE`.

Historical comparable 30-minute OI changes: for 5-minute boundaries `τ`
in `[state_start - 30 calendar days, state_start)` with both
`legal_OI(τ)` and `legal_OI(τ-30m)` defined, finite, and strictly
positive,

```text
delta_oi_ref(τ) = log( legal_OI(τ) / legal_OI(τ-30m) )
P_oi = ( #{ref < delta_oi} + 0.5 * #{ref == delta_oi} ) / N_ref
```

`OI_EXPANSION` iff `P_oi > 0.75` (strict) and `N_ref >= 1`.

Missing/stale/non-positive/non-finite required OI, or empty OI reference:
`EPISODE_NOT_ELIGIBLE`. Never redraw. Never fill.

---

## 6. Weak continuation

During the same STATE FORMATION window:

```text
state_return          = ln( close(T) / close(t) )
signed_continuation   = D * state_return
continuation_ratio    = signed_continuation / abs_impulse
WEAK_CONTINUATION iff continuation_ratio <= 0.25
```

Non-finite `state_return` or `abs_impulse == 0`: `EPISODE_NOT_ELIGIBLE`.

Negative `signed_continuation` satisfies weak continuation. It is **not**
observed absorption.

---

## 7. Candidate and baseline identity

Determined before the outcome window begins.

```text
CANDIDATE iff
  QUALIFYING_IMPULSE
  AND OI_EXPANSION
  AND WEAK_CONTINUATION

BASELINE iff
  QUALIFYING_IMPULSE
  AND episode is confirmatory-eligible (inputs, stratum, outcome path)
  AND NOT CANDIDATE
```

`candidate_indicator = 1` for CANDIDATE, `0` for BASELINE.

Do not match on OI expansion, weak continuation, future return, outcome,
funding, or post-impulse/state information other than candidate identity.

---

## 8. Primary outcome

```text
outcome_return  = ln( close(T+60m) / close(T) )
reversal_return = -D * outcome_return
```

Single frozen horizon. No alternative horizons. Not PnL.

Missing outcome bars cannot occur inside CORE's zero-gap common period
if §2.3 span holds; if any required close is non-finite:
`EPISODE_NOT_ELIGIBLE`.

---

## 9. Overlap policy

Walk candidate impulse endpoints `t` in chronological 5-minute order.

Once a qualifying impulse episode is **accepted**, no new qualifying
impulse episode may **begin** before that full episode ends:

```text
next_impulse_start >= current_impulse_start + 120m
                   = current outcome_end
```

On conflict, keep the earliest chronologically eligible qualifying
impulse. The same rule applies regardless of later candidate/baseline
class. Outcome does not influence overlap resolution.

An accepted qualifying impulse that later fails OI/state/stratum/outcome
checks remains `EPISODE_NOT_ELIGIBLE` for confirmatory use but still
occupies the 120-minute slot.

---

## 10. Missing data

Fail closed.

Never interpolate native OI. Never treat missing OI as zero change.
Never unauthorized forward-fill. Never staleness `> 5m`.

Any episode requiring unavailable OI for state calculation, historical
normalization, or legal decision-time observation:
`EPISODE_NOT_ELIGIBLE`.

Exclusion counts are later diagnostics and must not alter this prereg.

---

## 11. Trailing-volatility statistic

**Bound definition:** B2-03 / B2-02 `PRE_VOL_60`, the repository's unique
frozen **pre-state volatility tertile** statistic
(`b2_03_impulse_morphology_lib.pre_vol_60`; B2-02 `PRE_VOL` is the same
formula).

H01 `RV_L = sqrt(sum r^2)` over L ∈ {30, 60, 120} is the same *formula*
at L=60 but is H01's candidate **feature search surface**, not a
pre-state matching state. This prereg does not use H01's L∈{30,120}.

Evaluated at **impulse endpoint** `t` (pre-state: the window does **not**
include STATE FORMATION `[t, t+30m]`):

```text
PRE_VOL_60(t) = sqrt( sum_{i=1..60} r_i^2 )
r_i = ln(close_i / close_{i-1})
close_0 = close(t-60m)
close_1..close_60 cover [t-60m, t) exactly 60 complete 1m bars
available_at <= t for close_0 and all 60 bars
```

Fewer or more than 60 returns, any unavailable bar, or non-finite
result: `EPISODE_NOT_ELIGIBLE`. No alternate vol metric.

---

## 12. Pre-state stratification (author decision 1)

Two dimensions only, each mapped to `LOW` / `MID` / `HIGH`:

1. impulse magnitude = `abs_impulse(t)`
2. trailing volatility = `PRE_VOL_60(t)`

Maximum 3 × 3 = 9 strata.

Tertile **boundaries** for episode `t` use only historical observations
legally available **before** `impulse_start`, previous 30 calendar days,
current episode excluded. Outcome information must not enter.

Reference population (both dimensions): UTC 5-minute boundaries `τ` in
`[impulse_start - 30 calendar days, impulse_start)` with the relevant
statistic fully legally available (for vol: `PRE_VOL_60(τ)` with `τ`
as the window end; for magnitude: `abs(ln(close(τ)/close(τ-30m)))`).

Midrank `P` as in §4. Tertile cuts, B2-03:

```text
LOW  iff P <  1/3
MID  iff 1/3 <= P < 2/3
HIGH iff P >= 2/3
```

Empty/non-finite reference for either dimension: `EPISODE_NOT_ELIGIBLE`.
No nearest-neighbor, propensity, outcome-chosen bins, or stratum merging.

```text
stratum_id = IMPULSE_MAG_STATE | TRAILING_VOL_STATE
```

uppercase `LOW`/`MID`/`HIGH`, single `|`, no direction field, no
whitespace.

No matching on OI expansion or weak continuation.

---

## 13. Support and identifiability (author decision 3)

Confirmatory analysis uses only accepted episodes that are
confirmatory-eligible (valid candidate/baseline identity, valid stratum,
finite `reversal_return`, full span inside §2.3).

A **usable stratum** requires both:

```text
candidate_count_in_stratum >= 5
baseline_count_in_stratum  >= 5
```

Only usable strata enter the primary regression. Other strata are
reportable diagnostics only.

Primary confirmatory test is eligible only if **all** are true:

```text
TOTAL_ELIGIBLE_EPISODES >= 100   (usable-stratum episodes only)
CANDIDATE_EPISODES      >= 30    (usable-stratum candidates)
BASELINE_EPISODES       >= 30    (usable-stratum baselines)
USABLE_STRATA           >= 3
```

and the regression design in §14 is finite and full rank.

Otherwise:

```text
final classification = NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT
```

No threshold repair, no stratum merging, no fallback unstratified test,
no selective removal to obtain support, no ridge, no pseudoinverse.

---

## 14. Primary estimand (author decision 2)

Not V3. Not Clark-West. Not nested OLS on a regular bar grid.

Among confirmatory usable-stratum episodes, ordinary least squares:

```text
reversal_return_i = alpha_{stratum(i)} + beta_candidate * candidate_indicator_i + e_i
```

**Design matrix (exact):** one dummy column per usable `stratum_id`
sorted lexicographically, **no separate intercept**, plus
`candidate_indicator` as the last column.

```text
X = [ I_{s1}, I_{s2}, ..., I_{sK}, candidate_indicator ]
β = (X'X)^{-1} X'y
```

Solve `X'X β = X'y` with `numpy.linalg.solve` (`numpy==2.1.3`).
If `numpy.linalg.matrix_rank(X'X) < ncols`, `LinAlgError`, or any
coefficient is non-finite:
`NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT`.
Do not use `lstsq`, ridge, or pseudoinverse.

Primary parameter: `beta_candidate` (the last coefficient).

```text
H0: beta_candidate <= 0
H1: beta_candidate > 0
```

---

## 15. Confirmatory bootstrap identity

**One** primary confirmatory test.

Resample the chronological confirmatory episode sequence (order: decision
time `T` ascending, then `impulse_start` ascending; overlap policy makes
`T` unique). Each draw preserves the tuple jointly:

```text
(reversal_return, candidate_indicator, stratum_id)
```

**Algorithm:** Politis–Romano stationary bootstrap on that length-`n`
sequence, circular wrap **within** the sequence only.

**Expected block length** `b_hat`: Politis–White / Patton–Politis–White
**stationary-bootstrap branch only** (`c=2`, `b_sb`), locked dependency
`arch==8.0.0` function `arch.bootstrap.optimal_block_length` /
`_single_optimal_block`, source file SHA256
`104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21`
(already pinned in this repository). The circular-bootstrap branch is
not used.

This selector is an algorithm identity, **not** V3 `DETECTED` and **not**
the Clark-West estimand. Do not call `evaluate_v3_world` on MARKET data.

**Selector input series** (scale-invariant OLS influence for
`beta_candidate` after stratum demeaning / Frisch–Waugh):

Let `M` be the within-usable-stratum residual maker.
`x̃ = M * candidate_indicator`, `ỹ = M * reversal_return`,
`beta_hat` the observed OLS coefficient.

```text
z_i = x̃_i * (ỹ_i - x̃_i * beta_hat)
```

`b_hat = optimal_stationary_block_length(z)`. Selector consumes no RNG.
If `b_hat` is non-finite or `<= 0`:
`NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT`.

```text
p_geom = 1 / round( clamp(b_hat, 1, n) )
```

`n` = confirmatory episode count. `round` is half-to-even / Python 3
`round` of a real number to nearest integer, matching the V3 confirmatory
module's `round(clamped)` on this same selector output (algorithm reuse,
not estimand reuse).

**Replicates:** `B = 999`.

For replicate `b = 1..999`:

1. Draw stationary-bootstrap index path of length `n`: start uniform on
   `0..n-1`; block length i.i.d. Geometric(`p_geom`) on `{1,2,...}`;
   indices `(start+j) mod n`; concatenate until length `n`, truncate.
2. Refit §14 on the resampled tuples.
3. Record `beta*_b`. If that replicate is rank-deficient or non-finite:
   the **entire** primary confirmatory test is
   `NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT` (no redraw, no drop).

**Studentized one-sided p-value** (same arithmetic construction the
repository already froze for one-sided SB tests, applied to
`beta_candidate` not V3 `theta_hat`):

```text
SE_hat      = sample std of {beta*_b}, ddof=1
T_obs       = beta_hat / SE_hat
T*_b        = (beta*_b - beta_hat) / SE_hat
p_one_sided = (1 + #{ b : T*_b >= T_obs }) / (999 + 1)
```

If `SE_hat` is non-finite or `<= 0`:
`NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT`.

**DETECTED** iff support/identifiability pass **and**

```text
beta_hat > 0
AND p_one_sided <= 0.05
```

**RNG (not V3_CONFIRMATORY):**

```text
seed_material = MARKET-01_OI_EXPANSION_WEAK_CONTINUATION|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999
seed_material_sha256 = a960350293eacee83f5cfcb21e138f5f4dbbea1af4547d298e5a1da2ec571dbe
MARKET_01_BOOTSTRAP_SEED = int(sha256(seed_material)[:16 hex], 16)
                         = 12204813275361890024
```

Stream: existing V1 `pcg64_generator(namespace_seed(MARKET_01_BOOTSTRAP_SEED, "BOOTSTRAP", "PRIMARY_BETA_CANDIDATE"))`
(`scripts/research/harness_synthetic_edge_calibration_v1_lib.py`). Token
`BOOTSTRAP` is already in the V1 allowlist. Do not use
`V3_CONFIRMATORY`. `python_hash` forbidden. Reroll forbidden.

`alpha = 0.05`. No second primary test. No later test shopping.

---

## 16. Robustness (author decision 4)

Evaluated **only after** a valid primary DETECTED result. May only
**downgrade**. May never rescue `NO_EVIDENCE`, failed primary evidence,
insufficient support, or non-identifiability.

Episode era is assigned by **decision time `T`**:

```text
ERA_1  [2020-09-01T00:00:00Z, 2021-01-01T00:00:00Z)
ERA_2  [2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z)
ERA_3  [2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z)
ERA_4  [2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z)
ERA_5  [2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z)
```

**Leave-one-era-out:** for each `k=1..5`, start from the **primary
confirmatory sample** (usable-stratum episodes that entered §14). Drop
rows with `T` in `ERA_k`. Keep the **same** stratum dummy columns as the
primary design (lexicographic usable `stratum_id` set from the primary
sample). Do **not** recompute tertiles, re-select usable strata, merge
strata, or add previously excluded strata. Do **not** require bootstrap
`p <= 0.05` in LOEO refits. LOEO records only `beta_candidate_LOEO_k`.

On that remainder, `ROBUSTNESS_SIGN_STABLE = false` immediately if any
of:

- remaining `TOTAL < 100`, remaining `CANDIDATE < 30`, or remaining
  `BASELINE < 30`;
- any primary usable stratum has remaining `candidate_count < 5` or
  remaining `baseline_count < 5` (zeros included);
- the §14 solve is rank-deficient or any coefficient is non-finite.

Otherwise record `beta_candidate_LOEO_k`. `ROBUSTNESS_SIGN_STABLE` iff
`beta_candidate_LOEO_k > 0` (finite) for **all five** refits.

No support repair. No unstratified fallback. No per-LOEO p-value test.

**Concentration** (primary confirmatory candidates only):

```text
candidate_share_k = (# primary confirmatory candidates with T in ERA_k)
                    / (# primary confirmatory candidates)
ROBUSTNESS_CONCENTRATION_OK iff max_k candidate_share_k <= 0.50
```

Exactly 0.50 passes. Greater than 0.50 fails.

```text
ROBUSTNESS_PASS = ROBUSTNESS_SIGN_STABLE AND ROBUSTNESS_CONCENTRATION_OK
```

Do not use robustness to change the primary test.

---

## 17. Final classification

Mechanical mapping. No rhetoric promotion.

**CASE 1** — §13 support/identifiability fail (including bootstrap
selector/replicate/SE failure):

```text
NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT
```

**CASE 2** — primary test valid but `beta_hat <= 0` OR `p_one_sided > 0.05`:

```text
NO_EVIDENCE
```

**CASE 3** — primary DETECTED (`beta_hat > 0` AND `p <= 0.05`) but
`ROBUSTNESS_PASS = false`:

```text
DETECTED_BUT_NOT_ROBUST
```

**CASE 4** — primary DETECTED and `ROBUSTNESS_PASS = true`:

```text
ROBUST_CANDIDATE
```

`ROBUST_CANDIDATE` means only: the preregistered MARKET-01 relationship
produced positive primary evidence and survived the frozen temporal
robustness downgrade checks.

It does **not** mean validated alpha, a profitable strategy, production
readiness, causal proof, proven absorption, permission to trade, or
automatic promotion to protected OOS.

---

## 18. No-lookahead, no repair, no selective rerun

Decision `T` may use only information with `available_at <= T`.
Tertiles and input percentiles use only history before `impulse_start`
(impulse/vol) or before `state_start` (OI), as specified.

Forbidden after this prereg:

- changing 90th / 75th / 0.25;
- changing 30m / 30m / 60m;
- changing support floors or era bounds;
- opening 2025/2026;
- using funding or executing B2-06;
- modifying V3 or creating V4;
- inspecting outcomes to choose among tests;
- selective rerun or post-outcome threshold repair.

A materially different rule is a **new** hypothesis ID.

---

## 19. Implementation / freeze / ARM

This unit materializes the preregistration only.

```text
prereg_frozen                         = false
implementation_authorized             = false
arm_authorized                        = false
market_01_execution_authorized        = false
b2_06_execution_authorized            = false
protected_oos_authorized              = false
default_v4                            = false
v3_reused_as_market_01_test           = false
market_01_test_calibrated             = false
```

Next required step after this document: **separate prereg freeze**.
Then a later implementation unit. Not this unit.
