# MARKET-05 cross-asset confirmation candidate freeze

- **Status:** `SELECTED_OUTCOME_BLIND_NOT_PREREGISTERED_NOT_AUTHORIZED`
- **Unit ID:** `MARKET_05_CROSS_ASSET_CANDIDATE`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Short name:** `MARKET-05`
- **Date:** 2026-09-19
- **Machine-readable twin:** [`MARKET_05_CROSS_ASSET_CANDIDATE.json`](MARKET_05_CROSS_ASSET_CANDIDATE.json)
- **Companion feasibility:** [`MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.md`](MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.md)

This unit freezes a MARKET-05 **candidate identity** and records the
outcome-blind BTC/ETH temporal-feasibility companion. It is not a
preregistration, not an ARM, not an implementation, and not an execution
authorization.

```text
market_05_selected = true
research_id = MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK
mechanism_family = F7_CROSS_ASSET_MARKET_CONTEXT
target_market = BTCUSDT
context_market = ETHUSDT
primary_role = MARKET_BREADTH_CONFIRMATION_STATE
simple_direction_predictor = false
NOT_ROLE = SIMPLE_DIRECTION_PREDICTOR
lineage_kind = NEW_MECHANISM_SELECTED_FROM_PROGRAM_LEVEL_INFORMATION_GAP
parent_scientific_unit = null
market_01_02_rescue = false
market_03_replication = false
market_04_rescue = false
context_feature_family = ETH_CONFIRMATION_STATE
continuous_feature_required = true
threshold_search_allowed = false
same_support_required = true
primary_outcome_family = FUTURE_BTC_DIRECTION_ALIGNED_ADVERSE_PATH_RISK
scientific_outcomes_inspected = false
protected_oos_touched = false
full_preregistration_frozen = false
implementation_frozen = false
armed = false
execution_authorized = false
STATUS = SELECTED_OUTCOME_BLIND_NOT_PREREGISTERED_NOT_AUTHORIZED
```

This unit does **not**: run MARKET-05; inspect future BTC returns; inspect future MAE; compute ETH-confirmation correlations with future outcomes;
calculate regression coefficients; compare confirmation buckets; test
lookbacks or horizons against outcomes; inspect yearly or regime
scientific performance; optimize normalization; create RESULT or ARM
artifacts; create a preregistration; or open protected 2025/2026 OOS for
parameter or year-retention decisions.

---

## 1. Selected candidate

```text
RESEARCH_ID = MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK
SHORT_NAME = MARKET-05
MECHANISM_FAMILY = F7_CROSS_ASSET_MARKET_CONTEXT
PRIMARY_ROLE = MARKET_BREADTH_CONFIRMATION_STATE
TARGET_MARKET = BTCUSDT
CONTEXT_MARKET = ETHUSDT
NOT_ROLE = SIMPLE_DIRECTION_PREDICTOR
STATUS = SELECTED_OUTCOME_BLIND_NOT_PREREGISTERED_NOT_AUTHORIZED
```

MARKET-05 is a **market-breadth confirmation-state** candidate. ETH is
contextual information about broader crypto participation around a BTC
move. ETH is **not** an independent asset replication.

This is **one BTC experiment**. Do not later count BTC and ETH as two
independent asset replications.

---

## 2. Scientific question

When BTC has a directional displacement, does contemporaneous ETH confirmation add stable incremental information about BTC's subsequent adverse-path risk beyond BTC's own price / path / volatility state?

The intended mechanism is: BTC movement confirmed by ETH may represent
broader crypto-market participation and therefore differ in subsequent
path reliability from BTC movement that is weakly confirmed or
contradicted by ETH.

This is specifically **not**:

- "ETH predicts BTC direction";
- "BTC and ETH are correlated";
- "buy BTC when ETH rises";
- a generic pair-trading hypothesis;
- a claim that cross-asset confirmation causes BTC continuation;
- a simple direction predictor.

---

## 3. Distinct information layer

Earlier Signalbot research already tested:

- volatility dynamics;
- boundary / breakout behavior;
- impulse morphology;
- trend pullback continuation;
- taker imbalance;
- OI directional formulations;
- funding/crowding historical formulations, currently blocked by
  observable availability.

MARKET-05 introduces a different information source:
`CROSS_ASSET_MARKET_CONTEXT`. ETH is a feature describing broader crypto
participation around a BTC move.

MARKET-05 is **not** an independent replication of earlier H/B/MARKET
units. Earlier H/B exact formulations are not renamed into MARKET-05.

Program-level observation that single-market features have repeatedly
failed to produce strong stable incremental evidence may motivate this
selection. That motivation is **not** positive evidence for MARKET-05.

---

## 4. Lineage

```text
LINEAGE_KIND = NEW_MECHANISM_SELECTED_FROM_PROGRAM_LEVEL_INFORMATION_GAP
PARENT_SCIENTIFIC_UNIT = NONE
parent_scientific_unit = null
POSTHOC_CHILD_OF_H01_H05 = false
MARKET_01_02_RESCUE = false
market_01_02_rescue = false
MARKET_03_REPLICATION = false
market_03_replication = false
MARKET_04_RESCUE = false
market_04_rescue = false
```

MARKET-04 remains `SELECTED`, `NOT_TESTED`, `NOT_REJECTED`,
`BLOCKED_OBSERVABLE`. MARKET-04H remains
`MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED`. Neither is a scientific failure
and neither is rewritten by this unit.

---

## 5. Target / feature distinction

```text
TARGET = BTCUSDT
CONTEXT_FEATURE_MARKET = ETHUSDT
eth_is_independent_replication = false
one_btc_experiment = true
```

BTC is the prediction target. ETH is contextual information. The future
experiment asks whether ETH adds information about BTC.

---

## 6. Conceptual feature

```text
context_feature_family = ETH_CONFIRMATION_STATE
continuous_feature_required = true
threshold_search_allowed = false
```

Conceptually:

```text
BTC_DIRECTION = sign(recent BTC directional displacement)
ETH_CONFIRMATION = BTC_DIRECTION * normalized contemporaneous ETH displacement
```

Interpretation:

- positive: ETH moved in the same direction as BTC;
- near zero: weak ETH confirmation;
- negative: ETH contradicted BTC direction.

The exact normalization formula is **not** frozen here. The later
preregistration must choose one simple deterministic normalization
outcome-blind. This unit did not inspect outcomes to choose a
normalization.

The first MARKET-05 formulation must use a **continuous** confirmation
feature. Forbidden in the first formulation:

- ETH_CONFIRMATION > threshold;
- BTC move > optimized threshold;
- correlation > optimized threshold;
- percentile bucket selection;
- top/bottom decile selection;
- threshold search;
- window search using outcomes;
- choosing only large divergences because they look predictive.

No magic threshold is allowed to define the primary candidate.

---

## 7. Future baseline / candidate architecture

```text
BASELINE  = BTC-only information available at T
CANDIDATE = exact BASELINE + continuous ETH_CONFIRMATION_STATE
same_support_required = true
ml_forbidden_in_first_formulation = true
funding_oi_taker_contamination_forbidden = true
large_indicator_library_forbidden = true
```

Baseline may include only simple predeclared BTC categories such as:

- BTC directional displacement;
- BTC realized volatility;
- BTC simple path/range state.

Candidate complexity must earn incremental value. No ML in the MARKET-05
primary formulation. No large technical-indicator library. No order-flow
/ OI / funding variables.

---

## 8. Future primary outcome family

```text
PRIMARY_OUTCOME_FAMILY = FUTURE_BTC_DIRECTION_ALIGNED_ADVERSE_PATH_RISK
pnl_is_primary_outcome = false
final_horizon_return_is_primary = false
```

Conceptual form only (not computed in this unit):

```text
s_T = sign(BTC displacement before T)
aligned_future_return(u) = s_T * log(BTC_price(T+u) / BTC_price(T))
direction-aligned adverse excursion = maximum excursion against s_T after T
```

The exact horizon and exact primary statistic must be frozen later. PnL
is **not** the primary outcome. Final directional return may later be a
secondary diagnostic only. This unit creates no numeric success
thresholds and computes no future-outcome artifacts.

---

## 9. Same-support and missingness

```text
same_support_required = true
```

For every BTC decision timestamp `T`, later execution requires:

- BTC feature state available at `T`;
- ETH feature state available at `T`;
- future BTC outcome available for evaluation.

BASELINE and CANDIDATE must use exactly the same rows. No ETH missing
row may silently disappear only from the candidate.

Deterministic missingness rule for later scientific execution:

```text
if BTC missing or ETH missing at T: row ineligible for BOTH baseline and candidate
no silent candidate-only drop
no venue/instrument-class fallback
```

---

## 10. Anti-rescue fence

After MARKET-05 scientific execution begins, the same identity cannot be
rescued by changing:

- ETH to SOL;
- ETH to a basket;
- BTC target to another asset;
- confirmation sign;
- feature normalization;
- lookback window;
- horizon;
- primary outcome;
- baseline;
- subset;
- bull/bear years;
- regime;
- threshold;
- materiality requirement;
- uncertainty method.

A material change requires a **NEW** research identity.

---

## 11. Identifiability contract (later prereg)

MARKET-05 asks for incremental ETH information beyond BTC state. Later
preregistration must include an identifiability contract. The candidate
must not receive credit merely because `ETH_CONFIRMATION` is another
representation of BTC displacement.

This unit performed **no** outcome-blind identifiability diagnostic and
did not search a best feature definition.

```text
outcome_blind_identifiability_diagnostic_performed = false
```

---

## 12. Success / failure interpretation boundary

No numeric success gates are defined here.

A future **positive** MARKET-05 result would mean: ETH confirmation
added stable incremental historical information about BTC adverse-path
risk beyond the frozen BTC-only baseline.

It would **not** mean: validated alpha; profitable strategy; causality;
independent OOS confirmation; ETH predicts BTC direction; or that
cross-asset context generally works.

A future **negative** result would mean: the exact frozen
ETH-confirmation formulation did not establish stable incremental
information.

It would **not** prove all cross-asset information is useless.

---

## 13. Protected OOS and lifecycle

```text
scientific_outcomes_inspected = false
protected_oos_touched = false
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
PROTECTED_OOS_TOUCHED = false
full_preregistration_frozen = false
implementation_frozen = false
armed = false
execution_authorized = false
result_created = false
arm_created = false
evaluator_implemented = false
prereg_created = false
```

The scientific development window is **not** selected here. Common
BTC/ETH historical coverage is recorded only in the feasibility
companion. Later preregistration must freeze the actual scientific
development window before outcomes are computed. Protected 2025/2026
OOS remains untouched.

```text
NEXT_UNIT = OUTCOME_BLIND_MARKET_05_EXACT_PREREGISTRATION
```

This freeze does not create MARKET-05 RESULT files, ARM files, or a
preregistration.
