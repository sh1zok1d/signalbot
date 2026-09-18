# MARKET-02 OI_EXPANSION_PRICE_CONFIRMATION — Preregistration

- **Status:** `PREREGISTERED_OUTCOME_BLIND_UNFROZEN`
- **Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`
- **Parent design:** `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_DESIGN.md`
- **Machine-readable twin:** `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json`
- **Authority:** this MD is the complete scientific authority; the JSON is a machine-readable twin/index and MUST agree on every duplicated field. Any disagreement is fail-closed and blocks freeze/execution; JSON never overrides this MD.
- **Date:** 2026-09-18
- **Outcome inspection for MARKET-02 design/prereg:** **NO**
- **Prereg freeze:** **NO — separate next unit required**
- **Evaluator / ARM / execution:** **NO / NO / NO**

This is the complete outcome-blind MARKET-02 preregistration. It does not
freeze, implement, ARM, execute, enumerate MARKET-02 episodes, or inspect
MARKET-02 subgroup outcomes.

## 0. Sequential-research disclosure

MARKET-02 was formulated after the sealed MARKET-01 RESULT was observed.
MARKET-01 remains permanently closed as `NO_EVIDENCE`. MARKET-02 is a new
sequential hypothesis on overlapping historical market data, not an
independent replication and not a rescue or reclassification of MARKET-01.

No MARKET-01 threshold, horizon, RESULT, or classification may be changed.
No additional subgroup outcome was inspected to select this prereg.

## 1. Claim

Conditional on a qualifying directional BTC perpetual price impulse and OI
expansion during the following 30-minute state window, price confirmation of
the original impulse during that state window is associated with stronger
subsequent 60-minute continuation in the original impulse direction than
weak/non-confirming price action.

Relationship study only. Not causality, alpha, PnL, or a trading strategy.

## 2. Data authority

Price:
```text
dataset_id  = CORE_BTC_BINANCE_V0
snapshot_id = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
venue       = Binance
instrument  = BTCUSDT
market      = USD-M perpetual
native      = 1m
available_at(close bar) = open_time + 60s
```

Open interest only:
```text
snapshot_id = 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
field       = sum_open_interest
native      = 5m
available_at = create_time + 5m
max staleness = 5m
```

At clock U, legal OI is the latest row with `available_at <= U` and
`U - available_at <= 5m`. No fill, interpolation, zero substitution, or
staleness extension.

```text
common_start_inclusive = 2020-09-01T00:00:00Z
common_end_exclusive   = 2025-01-01T00:00:00Z
decision_grain         = UTC epoch 5m boundaries
```

Funding is forbidden. B2-06 remains `BLOCKED_MISSING_OBSERVABLE`.
Protected 2025 validation and 2026 OOS are forbidden.

## 3. Temporal identity

For 5m boundary t:
```text
impulse_start = t - 30m
impulse_end   = t
state_start   = t
state_end=T   = t + 30m
outcome_end   = T + 60m = t + 90m
full span     = 120m
```

All eligibility, state, normalization, overlap, strata and support decisions
must be determined without information from `[T, T+60m]`.

## 4. Qualifying impulse

```text
impulse_return = ln(close(t) / close(t-30m))
D              = sign(impulse_return)
abs_impulse    = abs(impulse_return)
```

Exact zero is ineligible. Historical reference is the previous 30 calendar
days of legally available 30m absolute impulse returns ending strictly before
the current `impulse_start`. Midrank percentile:
```text
P = (#{ref < x} + 0.5 * #{ref == x}) / N_ref
QUALIFYING_IMPULSE iff P_impulse >= 0.90 and N_ref >= 1
```
Missing/non-finite input fails closed.

## 5. OI expansion

```text
OI_start = legal_OI(t)
OI_end   = legal_OI(T)
delta_oi = ln(OI_end / OI_start)
```

Both OI values must be finite and strictly positive. Historical comparable
30m OI changes use the prior 30 calendar days ending before state_start with
the same legal-OI rule.

```text
OI_EXPANSION iff P_oi > 0.75 and N_ref >= 1
```

Non-OI-expansion episodes are outside the primary MARKET-02 population.

## 6. Price confirmation

```text
state_return        = ln(close(T) / close(t))
signed_continuation = D * state_return
continuation_ratio  = signed_continuation / abs_impulse

PRICE_CONFIRMATION      iff continuation_ratio > 0.25
WEAK_OR_NONCONFIRMATION iff continuation_ratio <= 0.25
```

The 0.25 boundary is the exact complement of the threshold frozen before
MARKET-01 execution. No new confirmation threshold may be searched.

Primary population:
```text
QUALIFYING_IMPULSE AND OI_EXPANSION
```
Within it:
```text
candidate_indicator = 1 for PRICE_CONFIRMATION
candidate_indicator = 0 for WEAK_OR_NONCONFIRMATION
```

## 7. Primary outcome

```text
outcome_return      = ln(close(T+60m) / close(T))
continuation_return = D * outcome_return
```

Single horizon only. No alternate horizon or reversal-sign outcome may be
used for the primary claim.

## 8. Overlap and missingness

Use MARKET-01's exact earliest-first 120m overlap discipline. Once a
qualifying impulse occupies a slot, later qualifying impulses whose
`impulse_start` falls before that full episode ends are skipped regardless
of later group/outcome identity. An occupying episode that later fails an
input remains occupying.

All missing/non-finite required data fail closed. No redraw, interpolation,
threshold repair, or fallback data source.

## 9. Pre-state stratification

Use exactly two outcome-blind dimensions evaluated at impulse endpoint t:

1. `abs_impulse(t)`
2. `PRE_VOL_60(t)`, the existing B2-03/B2-02 60 one-minute-return
   `sqrt(sum(r_i^2))` statistic ending at t.

For each dimension, boundaries are historical 30-calendar-day midrank
tertiles using only observations legally available before current
`impulse_start`:
```text
LOW  iff P < 1/3
MID  iff 1/3 <= P < 2/3
HIGH iff P >= 2/3
stratum_id = IMPULSE_MAG_STATE|TRAILING_VOL_STATE
```

No OI/confirmation/outcome/funding matching. No stratum merging.

## 10. Support and identifiability

Usable stratum:
```text
candidate_count >= 5
baseline_count  >= 5
```

Primary test is eligible only if usable-stratum sample satisfies:
```text
TOTAL_ELIGIBLE_EPISODES >= 100
CANDIDATE_EPISODES      >= 30
BASELINE_EPISODES       >= 30
USABLE_STRATA           >= 3
```

and the primary design is finite and full rank. Otherwise:
```text
NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT
```

No support-driven threshold repair, stratum merging, unstratified fallback,
ridge, pseudoinverse, or selective removal.

## 11. Primary estimand / test family

MARKET-02 reuses the stratified two-group conditional-contrast family because
it exactly represents this estimand; no new family is created.

Among usable-stratum primary episodes:
```text
continuation_return_i =
  alpha_{stratum(i)} + beta_confirmation * candidate_indicator_i + e_i
```

Exact design matrix: one dummy per usable `stratum_id` sorted
lexicographically, no separate intercept, candidate indicator last.

Solve `X'X beta = X'y` with `numpy.linalg.solve` under `numpy==2.1.3`.
Before solve, require `numpy.linalg.matrix_rank(X'X) == ncols`. The same exact
rank test and numpy version apply to every bootstrap and LOEO refit. Rank
deficiency, `LinAlgError`, or non-finite coefficient =>
`NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT`.

Primary parameter is the last coefficient:
```text
H0: beta_confirmation <= 0
H1: beta_confirmation > 0
```

## 12. Confirmatory stationary bootstrap

One primary confirmatory test. Chronological sequence ordered by decision
time T ascending; resample tuples jointly:
```text
(continuation_return, candidate_indicator, stratum_id)
```

Politis-Romano stationary bootstrap with circular wrap within this sequence.

Block selector: the repository-pinned `arch==8.0.0`
`optimal_block_length` stationary-bootstrap branch (`c=2`, `b_sb`),
using the scale-invariant OLS influence series for the confirmation
coefficient after within-stratum demeaning:
```text
x_tilde = M * candidate_indicator
y_tilde = M * continuation_return
z_i = x_tilde_i * (y_tilde_i - x_tilde_i * beta_hat)
```

`b_hat = optimal_stationary_block_length(z)`; non-finite or <=0 fails
identifiability. Then:
```text
p_geom = 1 / round(clamp(b_hat, 1, n))
B = 999
```

Each replicate refits the exact primary model. Any replicate rank failure or
non-finite coefficient invalidates the entire primary test; no redraw/drop.

```text
SE_hat      = sample std(beta*_b), ddof=1
T_obs       = beta_hat / SE_hat
T*_b        = (beta*_b - beta_hat) / SE_hat
p_one_sided = (1 + #{b: T*_b >= T_obs}) / 1000
```

Non-finite/non-positive SE fails identifiability.

```text
DETECTED iff beta_hat > 0 AND p_one_sided <= 0.05
```

RNG identity:
```text
seed_material =
MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999

seed_material_sha256 =
19b71ee831e69f273338ef94e65ff4cc339eb6d8054c365fd160c7769955558f

MARKET_02_BOOTSTRAP_SEED =
int(first 16 hex, 16) = 1852983754304692007
```

Use existing V1 `pcg64_generator(namespace_seed(MARKET_02_BOOTSTRAP_SEED,
"BOOTSTRAP", "PRIMARY_BETA_CONFIRMATION"))`. No reroll.

## 13. Prospective robustness downgrade

Run only after valid primary `DETECTED`; it can downgrade but never rescue.

Era by decision time T:
```text
ERA_1 [2020-09-01, 2021-01-01)
ERA_2 [2021-01-01, 2022-01-01)
ERA_3 [2022-01-01, 2023-01-01)
ERA_4 [2023-01-01, 2024-01-01)
ERA_5 [2024-01-01, 2025-01-01)
```

Leave one era out from the primary sample. Keep the primary usable-stratum
columns fixed; do not recompute tertiles or usable strata. Each remainder
must retain TOTAL>=100, CANDIDATE>=30, BASELINE>=30 and >=5/5 in every
primary usable stratum, remain full rank/finite, and have
`beta_confirmation_LOEO > 0`.

`ROBUSTNESS_SIGN_STABLE=true` only if all five pass.

Candidate-era concentration:
```text
candidate_share_k = candidate count in ERA_k / all primary candidates
ROBUSTNESS_CONCENTRATION_OK iff max(candidate_share_k) <= 0.50
```

No LOEO p-value shopping.

## 14. Final classification

```text
support/identifiability fail
  -> NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT

valid primary but DETECTED = false
  -> NO_EVIDENCE

DETECTED = true and both robustness conditions true
  -> EVIDENCE_WITH_PROSPECTIVE_ROBUSTNESS

DETECTED = true but either robustness condition false
  -> EVIDENCE_FRAGILE_NONSTATIONARITY
```

No classification means validated alpha, causality, production readiness, or
independent replication.

## 15. Calibration / governance

```text
MARKET_02_TEST_CALIBRATED = NO
V3_REUSED_AS_MARKET_02_TEST = NO
DEFAULT_V4 = NO
B2_06_EXECUTION_AUTHORIZED = NO
PROTECTED_OOS_AUTHORIZED = NO
MARKET_01_RERUN_AUTHORIZED = NO
```

V3's frozen nonstationary-trap failure motivates the prospective robustness
downgrade only. It does not calibrate MARKET-02 and does not authorize V4.

## 16. Reuse and lifecycle

After a separate prereg freeze, implementation may reuse semantics-matching
price/OI guards, rolling primitives, `construct_episodes_fast` or equivalent
precompute, PRE_VOL, OLS, bootstrap, and lifecycle infrastructure. Frozen
MARKET-01 scientific/evidence bytes must remain untouched.

Current state:
```text
MARKET_02_PREREG_MATERIALIZED = YES
MARKET_02_PREREG_FROZEN       = NO
MARKET_02_IMPLEMENTED         = NO
MARKET_02_ARMED               = NO
MARKET_02_EXECUTED            = NO
```

Any materially different rule after freeze requires a new research identity.
Next authorized unit after materialization review: **separate prereg freeze**.
