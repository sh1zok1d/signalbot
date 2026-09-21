# MARKET-04 candidate selection freeze

- **Status:** `SELECTED_OUTCOME_BLIND_NOT_PREREGISTERED_NOT_AUTHORIZED`
- **Unit ID:** `MARKET_04_CANDIDATE_SELECTION`
- **Research ID:** `MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK`
- **Short name:** `MARKET-04`
- **Date:** 2026-09-19
- **Machine-readable twin:** [`MARKET_04_CANDIDATE_SELECTION.json`](MARKET_04_CANDIDATE_SELECTION.json)

This unit freezes a MARKET-04 **candidate identity** before any outcome
inspection. It is not a preregistration, not an ARM, not an implementation,
and not an execution authorization.

Bound evidence registry:

```text
REGISTRY_HEAD = ec7960d5cad47682fec1fa5d33b1a03997a8b62b
REGISTRY_TREE = 293e6d338b0cde1e9859435036f6bef4c427520f
REGISTRY_MD = docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.md
REGISTRY_JSON = docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.json
REGISTRY_MD_SHA256 = f30b44a2d333600e3e6417f517e65c5dc1bde81fb03a6d1870cfcf19576c83c2
REGISTRY_JSON_SHA256 = 0892f66db94cc679cb938980127985ab9a81efece62b2adb755c1b7e8a048c72
```

```text
market_04_selected = true
candidate_identity_frozen = true
candidate = MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK
role = RISK_STATE_FILTER
direction_predictor = false
primary_outcome_family = FUTURE_ADVERSE_PATH_RISK
market_03_lineage = ADAPTIVE_HYPOTHESIS_GENERATION_FROM_EXTERNAL_REPRODUCTION
independent_replication_of_market_03 = false
market_01_02_rescue = false
funding_publication_latency_proven = false
funding_legal_historical_availability_resolved = false
full_preregistration_frozen = false
implementation_frozen = false
armed = false
execution_authorized = false
scientific_outcomes_inspected = false
protected_oos_touched = false
```

This unit does **not**: run MARKET-04; inspect MARKET-04 outcomes; inspect
protected 2025/2026 OOS; ARM an experiment; implement an evaluator; choose
thresholds or horizons by looking at returns; reuse MARKET-03 threshold 55
as scientific authority; treat MARKET-03 as independent confirmation;
weaken funding publication-time requirements; or infer legal availability
from `fundingTime` without authority.

---

## 1. Selected candidate

```text
RESEARCH_ID = MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK
SHORT_NAME = MARKET-04
MECHANISM_FAMILY = F5_POSITIONING_OI_FUNDING
CANDIDATE_ROLE = RISK_STATE_FILTER
NOT_ROLE = DIRECTION_PREDICTOR
STATUS = SELECTED_OUTCOME_BLIND_NOT_PREREGISTERED_NOT_AUTHORIZED
```

MARKET-04 is a **risk-state filter** candidate. It is not a direction
predictor.

---

## 2. Scientific question

Does historically available funding state add stable incremental information about future adverse price-path risk beyond a simple price / trend / volatility state?

Intended interpretation: funding may be useful for identifying dangerous
market states, even when it does not reliably predict the sign of
subsequent return.

This is specifically **not**:

- "high funding means price will fall";
- "low funding means price will rise";
- a MARKET-01 / MARKET-02 rescue;
- a rerun of EmaCrossFunding;
- validation of threshold 55;
- a claim that funding causes drawdowns.

---

## 3. Primary mechanism

Crowded / elevated funding may identify market states in which long exposure experiences worse subsequent adverse path / downside risk than would be expected from contemporaneous price and volatility state alone.

The feature must earn incremental value on identical support:

```text
CANDIDATE = CORE_PRICE_STATE + FUNDING_STATE
BASELINE  = CORE_PRICE_STATE
same_support_mandatory = true
```

Funding complexity earns value only if it improves risk-state information
beyond the simpler baseline.

---

## 4. Outcome family

```text
PRIMARY_OUTCOME_FAMILY = FUTURE_ADVERSE_PATH_RISK
pnl_is_primary_outcome = false
final_horizon_return_is_primary = false
```

The exact later preregistered primary statistic should be based on future
downside / maximum adverse excursion from decision time `T`.

Allowable implementation forms for a later design unit (not chosen here):

- future maximum adverse excursion;
- future minimum cumulative return from `T`;
- a predeclared lower-tail adverse-path statistic.

Do **not** choose among these by inspecting scientific outcomes. The exact
metric, units, horizon(s), block uncertainty method, and materiality gate
must be frozen in a later outcome-blind preregistration unit before
execution.

Final-horizon return may later be a **secondary diagnostic only**. PnL must
**not** become the MARKET-04 primary outcome. This unit creates no numeric
success thresholds.

---

## 5. Lineage

```text
EXTERNAL MARKET-03 -> MARKET-04 hypothesis generation
kind = ADAPTIVE_HYPOTHESIS_GENERATION_FROM_EXTERNAL_REPRODUCTION
independent_replication_of_market_03 = false
```

MARKET-03, in the bound registry, is an `EXTERNAL_REPRODUCTION` whose
canonical scientific outcome is `REPRODUCED_DIRECTION`. That statement is
hypothesis-generation metadata only. It is not independent confirmation
of a Signalbot funding-risk mechanism.

MARKET-04 is motivated by asking whether a broader funding-risk-state
mechanism exists independently of that specific EMA strategy.

Therefore:

- MARKET-04 positive ≠ independent replication of MARKET-03
- MARKET-04 negative ≠ MARKET-03 reproduction was invalid

The two answer different questions.

---

## 6. Required novelty versus MARKET-03

MARKET-04 must **not** use the external strategy as its core population.

Forbidden as the defining MARKET-04 design:

- EMA600 entry population;
- author threshold 55 as inherited authority;
- author's exact 180d percentile merely copied because it worked;
- EmaCross vs EmaCrossFunding;
- drawdown of the author's backtest as the primary experiment;
- parameter search around the author's published rule.

```text
ema600_is_defining_population = false
threshold_55_inherited = false
```

MARKET-04 must test funding as a market-state feature outside the specific
external strategy implementation.

---

## 7. Required novelty versus MARKET-01 / MARKET-02

MARKET-01 and MARKET-02 tested directional-return hypotheses using OI /
price-confirmation logic. They are lineage context only. They are **not**
positive support for MARKET-04.

```text
M01/M02: feature -> direction / continuation return
M04:     funding state -> adverse-path risk
market_01_02_rescue = false
market_01_02_are_positive_support = false
```

Do not reinterpret negative directional tests as positive evidence for
MARKET-04.

---

## 8. Baseline principle

```text
BASELINE  = simple information available at T describing current price state, trend/displacement, and realized volatility
CANDIDATE = the exact same baseline + funding-state information
same_support_mandatory = true
```

The later prereg must define the simplest defensible baseline. Do not add
a large indicator set merely to improve fit. Do not use ML in the first
MARKET-04 formulation.

---

## 9. Funding availability blocker

Existing project authority states `FUNDING_PUBLICATION_LATENCY_UNPROVEN`.

For MARKET-03, using `fundingTime` was accepted only as a LEVEL_2
reproduction assumption. That assumption is **not** sufficient authority
for a new Signalbot scientific hypothesis.

```text
FUNDING_LEGAL_HISTORICAL_AVAILABILITY = UNRESOLVED
funding_publication_latency_proven = false
funding_legal_historical_availability_resolved = false
MARKET_04_EXECUTION_AUTHORIZED = NO
execution_authorized = false
```

The next unit must perform an outcome-blind availability / feasibility
audit and establish a defensible historical availability rule from source
authority.

Forbidden:

- inventing +1 second;
- inventing +1 minute;
- inventing +5 minutes;
- assuming `calc_time` == publication time;
- assuming `fundingTime` == publication time merely because MARKET-03 did;
- choosing a latency because it gives more rows.

If historical availability cannot be established honestly, MARKET-04 must
become `BLOCKED_OBSERVABLE` rather than weakening the no-lookahead
contract.

---

## 10. Data / time boundary

No scientific outcome data may be opened in this freeze.

```text
scientific_outcomes_inspected = false
protected_oos_touched = false
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
```

Candidate selection may reference metadata / existing frozen evidence
only. This unit does not inspect future returns, future MAE, correlations,
threshold performance, regime performance, or funding buckets versus
outcomes. No MARKET-04 outcome numbers appear because none were produced.

---

## 11. Anti-rescue contract

MARKET-04 cannot later be rescued after outcome inspection by:

- changing funding threshold;
- changing percentile window;
- switching high funding to low funding;
- changing horizon;
- changing primary metric;
- choosing only bullish/bearish years;
- choosing one regime post-hoc;
- adding OI after failure;
- replacing funding with another derivatives feature;
- switching from adverse-path risk to final return;
- changing baseline after outcome inspection.

Any materially changed mechanism after execution must receive a new
research identity.

---

## 12. Success / failure interpretation boundary

No numeric success thresholds are created in this unit.

A future **positive** MARKET-04 would mean only: funding state showed
stable incremental information about adverse-path risk beyond the frozen
baseline under the preregistered historical test.

It would **not** mean: validated alpha; profitable strategy; causal
effect; independent confirmation of MARKET-03; or OOS confirmation.

A future **negative** MARKET-04 would mean: the frozen formulation did
not establish stable incremental adverse-risk information.

It would **not** mean "funding is useless".

---

## 13. Lifecycle and next unit

```text
full_preregistration_frozen = false
implementation_frozen = false
armed = false
execution_authorized = false
result_created = false
arm_created = false
evaluator_implemented = false
NEXT_UNIT = OUTCOME_BLIND_FUNDING_AVAILABILITY_AND_MARKET04_DESIGN_FEASIBILITY
```

This freeze does not create MARKET-04 RESULT files, ARM files, or a full
preregistration.
