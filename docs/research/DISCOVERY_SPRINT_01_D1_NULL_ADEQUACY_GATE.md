# Discovery Sprint 01 — D1 Null Adequacy Gate Adjudication

**Unit:** `DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE`
**Kind:** `PRE_EXECUTION_ADJUDICATION`
**Date:** `2026-09-21`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.json`

This is **not** D1 scientific execution. The adequacy gate was **not**
run. D1 target statistics were **not** computed. D2–D5 results are
unchanged. Protected 2025/2026 was not opened. MARKET-07 was not created.

## Verdict

| Field | Value |
|---|---|
| `D1_NULL_MODEL_OBSERVABLE_MISMATCH` | `true` |
| `D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED` | `true` |
| `D1_NULL_ADEQUACY_GATE_EXECUTED` | `false` |
| `D1_NULL_ADEQUACY_GATE_RESULT` | `null` |
| `D1_TARGET_OUTCOME_COMPUTED` | `false` |
| `D1_STATUS` | `DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH` |
| `NEXT_UNIT` | `D2_CONFIRMATION_FEASIBILITY_AND_DESIGN` |
| `INTERNAL_DISCOVERY_CARDS_EXECUTED` | `4` |
| `INTERNAL_PROMISING_PROTOTYPES` | `1` |
| `D2_STATUS` | `PROMISING_PROTOTYPE` |
| `MARKET_07_CREATED` | `false` |
| `PROTECTED_2025_OPENED` | `false` |
| `PROTECTED_2026_OPENED` | `false` |

Primary classification is **C** (`DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`).
The independent second check is also true (D), but does not replace the
fatal first finding.

## Check A — same-observable mapping

Frozen D1 state variable:

```
daily RV input = ev.rv_btc_24h(t)
RV_BTC_24H    = sqrt(sum_{i=1..288} r_i^2)   # 288 x 5m intra-day log returns
RV_20(t)      = sqrt(sum_{i=0..19} [ev.rv_btc_24h(t-i)]^2)
```

`ev.rv_btc_24h` is the MARKET-06 evaluator function
(`RV_RETURN_COUNT = 288`).

Frozen D1 null (`EXACT_SIMPLE_BASELINE_NULL.surrogate_generation`):

> For each replicate, circular block-bootstrap the standardized residuals with fixed block length = 20 decision points (matched to the RV_20 window, so the null does not trivially chop up the very window being tested), reinject through the fitted GARCH(1,1) conditional-variance recursion (same omega/alpha/beta, reinitialized at the empirical unconditional variance) to produce a full-length surrogate 24h-return path.

Corrected RV_20 (F6):

> RV_20_definition above ('sum of the 20-trailing-day realized-volatility values') is SUPERSEDED. Corrected: RV_20(t) := sqrt( sum_{i=0}^{19} [ev.rv_btc_24h(t-i)]^2 ) -- variance-level (L2) aggregation of the 20 trailing daily RV values, not a direct (L1) sum of already-square-rooted values. This changes the rolling_baseline (median of RV_20 values) and HIGH_VOL_STATE/LOW_VOL_STATE thresholding accordingly; no other part of EXACT_STATE_DEFINITION changes.

| Object | Frozen identity |
|---|---|
| `REAL_STATE_OBSERVABLE` | intraday realized volatility (ev.rv_btc_24h from 288 x 5m log returns; RV_20 L2-aggregates 20 of those daily RV values) |
| `NULL_GENERATED_OBSERVABLE` | synthetic DAILY 24h-return path from GARCH(1,1)+Student-t filtered circular block-bootstrap |
| `FROZEN_SAME_OBSERVABLE_MAPPING` | `false` |

No exact already-frozen mapping

`synthetic DAILY return path -> synthetic ev.rv_btc_24h -> synthetic RV_20`

exists in the authority documents. The following substitutes are **not**
used, and are not authorized as mappings: `abs(daily_return)`, GARCH
sigma, squared daily return, synthetic conditional variance. Forbidden
substitute phrases that appear in authority text (as **rejected**
options, not as maps): `intraday bridge`, `brownian bridge`.

F3 already recorded that D1's null generates exactly one scalar
surrogate 24h return per decision point and cannot produce a 288×5m
path. An arbitrary intraday bridge was explicitly rejected:

> An arbitrary intraday bridge (e.g. a Brownian bridge or linear interpolation forced between D1's daily-scale surrogate endpoints) is explicitly NOT used, per instruction.

F5's adequacy gate still requires surrogate `RV_20`, which is defined
only via `ev.rv_btc_24h`. That is a requirement, not a mapping.

Therefore:

```
D1_NULL_MODEL_OBSERVABLE_MISMATCH = true
```

The gate is not executed. No synthetic intraday bridge is created. No
5m GARCH is refit after sibling-card outcomes. The null is not replaced.

## Check B — adequacy-gate executability

Even if a same-observable mapping existed, the frozen gate is not
mathematically executable without new researcher degrees of freedom.
Underspecified quantities:

- `LEVERAGE_PROXY_OR_CLAUSE: Leverage/asymmetry proxy (correlation of return(t) with |return(t+1)| or next-period volatility)`
- `RV_20_SHORT_LAG_ACF_LAG_SET_UNENUMERATED: RV_20 distribution (mean, variance, and SHORT-lag autocorrelation only, using the corrected RV_20 definition from F6)`
- `RV_20_LAGWISE_PASS_FAIL_UNSPECIFIED: real value within surrogate [5th,95th] band for mean/variance/short-lag ACF only -- long-run RV_20 persistence is explicitly out of scope for this gate, since that is adjacent to the state-detection target itself`
- `SKEW_KURTOSIS_JOINT_VS_INDIVIDUAL_UNSPECIFIED: real-data value must fall within the surrogate replicate distribution's [5th,95th] percentile band`
- `ABS_OR_SQUARED_RETURN_ACF_OR_CLAUSE: Absolute-return (or squared-return) ACF at SHORT lags 1-10 (within GARCH(1,1)'s expected memory)`
- `NAN_DEGENERATE_TREATMENT_UNSPECIFIED: frozen gate never states NaN/degenerate handling`
- `GARCH_ESTIMATION_UNSPECIFIED: Student-t MLE is named, but library, optimizer, parameter constraints, and MLE initialization are not frozen`

```
D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED = true
```

No researcher-defined substitute is executed.

## Why defer rather than repair

D2-D5 scientific outcomes are already known. Sprint 01 specs were intended to be frozen before any card outcome. A new D1 null or new gate definitions would be a post-sibling-outcome redesign and must be a future D1-v2 card, not an in-sprint repair.

A future D1-v2 may be designed as a **new** discovery card/unit,
explicitly acknowledging that Sprint 01 sibling outcomes were already
observed.

## Program state

Deferred D1 is **not** counted as executed. D2 remains
`PROMISING_PROTOTYPE`. No confirmatory claim is created.

## Not done

- no synthetic intraday bridge
- no 5m GARCH refit
- no null replacement
- no D1 scientific target
- no HIGH_VOL_STATE / LOW_VOL_STATE sequence
- no MEAN_STATE_RUN_LENGTH
- no 2025/2026 access
