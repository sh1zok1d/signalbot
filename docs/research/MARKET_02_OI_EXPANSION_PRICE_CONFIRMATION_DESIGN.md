# MARKET-02 OI_EXPANSION_PRICE_CONFIRMATION — outcome-aware sequential design

- **Status:** `SEQUENTIAL_FOLLOWUP_DESIGN / NOT_PREREG_FREEZE`
- **Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`
- **Branch:** `research/market-02`
- **Date:** 2026-09-18
- **Evaluator implemented:** **NO**
- **Execution authorized:** **NO**
- **Protected 2025/2026 OOS touched:** **NO**
- **B2-06 execution authorized:** **NO**
- **DEFAULT_V4:** **NO**

This is a design record only. It does not freeze, implement, ARM, enumerate
MARKET-02 episodes, or compute MARKET-02 outcomes.

## 0. Sequential-research disclosure

MARKET-02 is being formulated **after** the sealed MARKET-01 RESULT was
observed. MARKET-01 closed as `NO_EVIDENCE` under its own frozen design.
Therefore MARKET-02 must not be represented as an independent confirmation
of a hypothesis chosen before any related outcome was known.

The new question is allowed as a **new sequential research hypothesis**.
Its scientific identity, estimand and RESULT must remain separate from
MARKET-01. A positive MARKET-02 result on the same 2020-09 through 2024-12
market history would be new evidence for this new relationship, but not an
independent replication and not a rescue/reclassification of MARKET-01.

Forbidden:
- changing MARKET-01 thresholds, RESULT, or classification;
- rerunning MARKET-01;
- selecting MARKET-02 thresholds/horizons by inspecting additional future
  returns or subgroup outcomes;
- calling a MARKET-02 positive result independent confirmation;
- opening protected 2025/2026 partitions;
- using funding or unblocking B2-06.

## 1. Research question

After a strong directional BTC perpetual price impulse, does subsequent open
interest expansion have different information about the next price path
depending on whether price **confirms** the original move during the state
window or fails to continue in that direction?

Conceptual claim:

> Conditional on a qualifying directional impulse and OI expansion, price
> confirmation during the post-impulse state window is associated with
> stronger subsequent continuation in the original impulse direction than
> non-confirmation.

This is deliberately not phrased as absorption, crowding, liquidation,
causality, alpha, or a trading strategy.

## 2. Data authorities proposed for the later prereg

Reuse the already-bound first-party authorities; no new dataset search:

- Price: `CORE_BTC_BINANCE_V0`, snapshot
  `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.
- OI-only: Binance Vision BTCUSDT metrics snapshot
  `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`.
- Common legal period: `[2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)`.
- Decision grain: UTC-epoch 5-minute boundaries.
- OI remains native 5m and legal only under its frozen
  `available_at = create_time + 5m` rule with <=5m staleness.
- Funding remains forbidden.
- Protected 2025/2026 remains unopened.

No data feasibility rerun is needed merely to establish that these same price
and OI observables exist. MARKET-01 already established their PIT feasibility.
Any later implementation must still authenticate the exact snapshots.

## 3. Proposed temporal identity

Prefer reuse of the already-reasoned MARKET-01 temporal geometry unless the
prereg review finds a scientific reason to reject it:

```text
impulse window     = 30m
state window       = 30m
decision time T    = impulse_end + 30m
outcome horizon    = 60m after T
full episode span  = 120m
```

This is reuse for comparability and reduced researcher degrees of freedom,
not because MARKET-01's result selected these windows.

No outcome information after `T` may enter impulse qualification, OI
expansion, confirmation state, historical normalization, overlap resolution,
support selection, or stratification.

## 4. Proposed state variables

### 4.1 Qualifying impulse

Reuse MARKET-01's prospective definition:

```text
impulse_return = ln(close(t) / close(t-30m))
D              = sign(impulse_return)
abs_impulse    = abs(impulse_return)
QUALIFYING_IMPULSE iff trailing-30-calendar-day midrank P_impulse >= 0.90
```

Reference observations must be legally available before the current
`impulse_start`. Exact zero, missing, or non-finite input fails closed.

### 4.2 OI expansion

Reuse MARKET-01's prospective OI state:

```text
delta_oi = ln(legal_OI(T) / legal_OI(t))
OI_EXPANSION iff trailing-30-calendar-day midrank P_oi > 0.75
```

Only positive finite legal OI values. Missing/stale input fails closed.

### 4.3 Price confirmation

Use the same dimensionless continuation statistic that existed before
MARKET-01 outcome inspection:

```text
state_return        = ln(close(T) / close(t))
signed_continuation = D * state_return
continuation_ratio  = signed_continuation / abs_impulse
```

Proposed binary identity:

```text
PRICE_CONFIRMS     iff continuation_ratio > 0.25
PRICE_NONCONFIRMS  iff continuation_ratio <= 0.25
```

The 0.25 cut is the exact complement of MARKET-01's already-frozen
`WEAK_CONTINUATION <= 0.25`; it is not a newly searched threshold.

MARKET-02 should **not** create LOW/MID/HIGH confirmation bins or search for
another cut after inspecting outcomes.

## 5. Proposed comparison and estimand

The cleanest MARKET-02 comparison is **within OI-expansion episodes**:

```text
eligible population:
  QUALIFYING_IMPULSE AND OI_EXPANSION

candidate_indicator = 1 for PRICE_CONFIRMS
candidate_indicator = 0 for PRICE_NONCONFIRMS
```

Primary outcome should be directional continuation, not MARKET-01's reversal
sign convention:

```text
outcome_return       = ln(close(T+60m) / close(T))
continuation_return  = D * outcome_return
```

Proposed primary parameter:

```text
beta_confirmation =
  conditional difference in continuation_return for
  PRICE_CONFIRMS versus PRICE_NONCONFIRMS
```

Proposed directional hypothesis:

```text
H0: beta_confirmation <= 0
H1: beta_confirmation > 0
```

This is a different estimand from MARKET-01. MARKET-01 asked whether the joint
OI-expansion/weak-continuation state had stronger later **reversal** than a
broad baseline. MARKET-02 asks, **conditional on OI expansion**, whether
confirmation versus non-confirmation separates later **continuation**.

## 6. Test-family routing decision still required

Do not automatically copy MARKET-01's exact regression/bootstrap just because
the data construction is reusable.

Before prereg freeze, route the proposed estimand against existing research
families:

1. If the existing stratified two-group contrast exactly represents the
   conditional confirmation contrast without changing its semantics, reuse
   that family and document the reuse.
2. If not, define one new narrow family for this estimand.
3. Do not create a generic MARKET framework in this unit.
4. Any reused/new MARKET-02 test remains **uncalibrated unless its exact test
   family has its own applicable calibration evidence**. V3 must not be
   claimed as calibration.

## 7. Reusable implementation surface

Later implementation should reuse, without modifying frozen MARKET-01
scientific bytes:

- `scripts/research/market_01_episode_construction_fast.py` or an equivalent
  semantics-preserving precompute for rolling price/OI/PRE_VOL quantities;
- PIT price/OI authority primitives;
- fail-closed missingness and overlap discipline;
- existing stationary-bootstrap primitives only if selected by the frozen
  MARKET-02 test-family identity.

The MARKET-01 performance record explicitly recommends the fast constructor
(or equivalent precompute) for later hypotheses. Do not wire MARKET-02 back
through the old O(T x W) construction path.

## 8. What must be resolved before prereg materialization

Outcome-blind author/review decisions still required:

1. Whether pre-state stratification is scientifically required for the
   confirmation contrast; if yes, bind exact dimensions and support floors.
2. Exact primary test-family identity.
3. Exact support/identifiability floors.
4. Exact bootstrap/resampling identity if the selected family requires one.
5. Prospective regime/nonstationarity downgrade checks, given the known V3
   frozen-trap limitation.
6. Exact final classification mapping.
7. Explicit statement that same-history MARKET-02 is sequential evidence,
   not independent replication.

These must be resolved without inspecting MARKET-02 subgroup outcomes.

## 9. Lifecycle

```text
MARKET_01                     = CLOSED / NO_EVIDENCE / NO RERUN
MARKET_02_DESIGN              = RESOLVED / SUPERSEDED_BY_PREREG
MARKET_02_PREREG              = MATERIALIZED / UNFROZEN
MARKET_02_PREREG_FREEZE       = NO
MARKET_02_IMPLEMENTED         = NO
MARKET_02_ARMED               = NO
MARKET_02_EXECUTED            = NO
PROTECTED_OOS_TOUCHED         = NO
B2_06_EXECUTION_AUTHORIZED    = NO
DEFAULT_V4                    = NO
```

The seven prereg decisions in section 8 were resolved outcome-blind and the
complete MARKET-02 prereg has now been materialized. This design record is
superseded by `MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md` for
scientific authority. Next step: independent prereg re-review, then a
separate freeze if and only if it is `FREEZE_READY`. Implementation must not
precede freeze.
