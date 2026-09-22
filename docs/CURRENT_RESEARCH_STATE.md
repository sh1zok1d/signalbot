# Signalbot — Current Research State

**Status date:** 2026-09-22  
**Status:** `ACTIVE / CANONICAL ROUTING INDEX`  
**Main integration baseline before this status commit:** `35511b3e9665db2b80ee52480d401b795bbfe38a`

This file is the compact answer to “what controls the project now?”. Frozen preregistrations/results remain authoritative for reproducing their own experiments; this file controls current routing only.

## Program state

| Unit | Current state | Canonical reference |
|---|---|---|
| MARKET-01 | `NO_EVIDENCE`, consumed, no rerun | `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json` |
| MARKET-02 | `NO_EVIDENCE`, consumed, no rerun | result lineage head `70f9489bd4fed905255b6791adcd23dc1e7d5dfa` |
| MARKET-03 | `REPRODUCED_DIRECTION` historical external reproduction; not internal validated alpha | RESULT `9c360a19a8e35ba0e7638fd125a0e6ae32f15846` |
| MARKET-04 / 04H | `BLOCKED_OBSERVABLE / NOT_TESTED`; not rejected | adjudication `e8d77b3b5c016582304db55c6ff2dacff92f0210` |
| MARKET-05 | `MARKET_05_NO_EVIDENCE`, consumed, no rerun | RESULT `828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b` |
| Forward observability | collector implementation frozen; authoritative collection not started by repo cleanup | `4158403b942c3ac0e2af3fb602f074f0064690fd` |
| MARKET-06 | `MARKET_06_NO_EVIDENCE`, one canonical shot consumed, no rerun | RESULT `80c7d19f622cc7b5576154de59dbb9cdf85d4dcf` |

MARKET-06 sealed identity:

- run identity: `f3aa51372594d710a8f705d761d857f8385d0b848fb0ed59a36b27a16ce25c22`;
- RESULT payload SHA256: `67f6f14c9221d3d0be2c130938f6ff8588aadc6eabc52126dd00a5fbbedd2a53`;
- classification: `MARKET_06_NO_EVIDENCE`;
- pooled relative MAE improvement: `-0.03756596483364705`, CI95 `[-0.0644801374915513, -0.014898013948610516]`;
- 2023: `-0.02814838672162434`; 2024: `-0.045320425619876925`;
- G1=true; G2-G6=false;
- protected 2025/2026 unopened.

Program-level correction is sealed in `docs/research/MARKET_PROGRAM_UPDATE_POST_M06.*`: MARKET-01 is **not** in the exact M05/M06 cell. The exact cell is repeated-null / low-priority-for-now; the broader short-horizon BTC conditional scalar-prediction family is low-priority / saturated-for-now as a search-priority judgement.

## Exact next unit

```
PREVIOUS_ROUTING            = DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION
PREVIOUS_ROUTING_SUPERSEDED = true
R_A_CURRENT_STATUS          = DISCOVERY_SPRINT_01_D1
MARKET_07_CREATED           = false
NEXT_UNIT                   = DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
NEXT_ACTION                 = BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
HETEROGENEOUS_FAMILY_ROTATION_V1 = FROZEN_HISTORICAL_SPRINT_02_POLICY
HETEROGENEOUS_FAMILY_ROTATION_V2 = FROZEN
DISCOVERY_SPRINT_02 = D7_EXECUTED_D8_DEFERRED
DISCOVERY_SPRINT_02_INTERNAL_CARDS = 2
DISCOVERY_SPRINT_03 = DEFINED
DISCOVERY_SPRINT_03_INTERNAL_CARDS = 3
SPRINT03_SELECTION_INCOMPLETE = false
D7_STATUS                   = PROMISING_PROTOTYPE
D8_STATUS                   = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
D9_STATUS                   = DEFINED_NOT_EXECUTED
D10_STATUS                  = DEFINED_NOT_EXECUTED
D11_STATUS                  = DEFINED_NOT_EXECUTED
D9_CHOSEN_ESTIMAND          = RELATIVE_RESOLUTION_ATTRIBUTION
D9_ALGEBRAIC_IDENTIFICATION_FIXED = true
MANDATE_V1_ON_MAIN          = true
D7_IMPLEMENTATION_STATUS    = EXECUTED_ONE_SHOT
D8_IMPLEMENTATION_STATUS    = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
D7_EXECUTION_AUTHORIZED     = true
D7_ONE_SHOT_RUNNER_BYTES_BOUND = true
PROVENANCE_MODEL            = AUTHORITY_PARENT_PLUS_FILE_HASHES
D7_EXECUTED                 = true
D7_CONFIRMATION_CANDIDATE   = true
D7_CONFIRMATION_SELECTED_NOW = false
D8_EXECUTION_AUTHORIZED     = false
D8_EXECUTED                 = false
D9_EXECUTED                 = false
D9_SCIENTIFIC_OUTCOME_COMPUTED = false
D10_EXECUTED                = false
D11_EXECUTED                = false
DATA_IDENTITY_MODE          = TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION
D7_SELECTOR_N               = 4545
D7_SELECTOR_DIGEST_FROZEN   = true
SCIENTIFIC_OUTCOMES_COMPUTED = true
THIS_UNIT_SCIENTIFIC_OUTCOMES_COMPUTED = false
RESEARCH_DATA_DURABILITY_V1_REQUIRED = true
D2_DECOMPOSITION_DESIGN_STATUS = FROZEN
D2_DECOMPOSITION_IMPLEMENTATION_REVIEW = PASS
D2_DECOMPOSITION_SCIENTIFIC_KERNEL_READY = true
D2_DECOMPOSITION_CANONICAL_ORCHESTRATION_READY = true
D2_DECOMPOSITION_PERMIT_VERIFIER_READY = true
D2_DECOMPOSITION_EXACT_SELECTOR_IDENTITY_IMPLEMENTED = true
D2_DECOMPOSITION_IMPLEMENTATION_REVIEW_CANONICAL_SELECTOR_DIGEST_FROZEN = false
D2_DECOMPOSITION_SELECTOR_IDENTITY_AUTHORITY = FROZEN
D2_DECOMPOSITION_CANONICAL_SELECTOR_DIGEST_FROZEN = true
D2_DECOMPOSITION_SELECTOR_IDENTITY_AUTHORITY_CREATED = true
D2_DECOMPOSITION_EXECUTION_READY   = false
D2_DECOMPOSITION_EXECUTION_AUTHORIZED = true
D2_DECOMPOSITION_EXECUTION_PERMIT_CREATED = true
D2_DECOMPOSITION_ONE_SHOT = true
D2_DECOMPOSITION_RERUN_AUTHORIZED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = true
RESULT_CREATED = true
D2_DECOMPOSITION_CLASSIFICATION_ASSIGNED = D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT
D2_DECOMPOSITION_ONE_SHOT_CONSUMED = true
D2_PROGRAM_CLASS            = INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE
BINANCE_2025_2026_DECISION  = KEEP_SEALED
PRODUCT_BUILD_FROZEN        = true
HYPOTHESIS_GENERATION_POLICY = HETEROGENEOUS_FAMILY_ROTATION_V2
PROTECTED_2025_OPENED       = false
PROTECTED_2026_OPENED       = false
INTERNAL_DISCOVERY_CARDS_EXECUTED = 5
INTERNAL_PROMISING_PROTOTYPES     = 2
INTERNAL_DISCOVERY_WARNING        = null
INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED = false
FULL_DISCOVERY_CARDS_COMPLETED    = 5
PARTIAL_COMPONENT_OUTCOMES_OBSERVED = 1
PARTIAL_COMPONENT_OUTCOMES        = D2/RULE_2/DISLOCATION_ABSTENTION
D2_RULE_2_DISCOVERY_OUTCOME_OBSERVED = true
D2_RULE_2_GATE_PASS               = false
D2_RULE_2_REPLAY_EXACT_MATCH      = true
POST_OUTCOME_DESIGN_CHANGES       = false
D1_STATUS                         = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH
D2_DISCOVERY_STATUS               = PROMISING_PROTOTYPE
CONFIRMATION_FEASIBILITY          = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION
2025_OPEN_AUTHORIZED              = false
2026_OPEN_AUTHORIZED              = false
ARM_CREATED                       = false
D2_OUTCOME_COMPUTED_ON_BITMEX     = true
D2_BITMEX_CLASSIFICATION          = D2_BITMEX_REPLICATION_SUPPORTED
D2_BITMEX_ADJUDICATION_CLASS      = REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH
D2_BITMEX_CONSTRUCTED_ELIGIBLE_N  = 1067
D2_BITMEX_FROZEN_ELIGIBLE_N       = 1069
CORRECTED_EXPECTED_N              = 1067
ORIGINAL_RUN_CLASSIFICATION       = D2_BITMEX_REPLICATION_INVALID
ORIGINAL_RERUN_AUTHORIZED         = false
CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE = true
D2_REPLICATION_STATUS             = SUPPORTED_ON_INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_SURFACE
RERUN_AUTHORIZED                  = false
PROTECTED_2025_PRICE_VALUES_INSPECTED = false
PROTECTED_2026_PRICE_VALUES_INSPECTED = false
```

Discovery Sprint 01 first attempt (`37921089ce289cd9bcbcebb123724a3e033dcdc3`)
is preserved as blocked: D2/D3/D4 rolling/D5 were
`BLOCKED_MISSING_LOCAL_DATA`; D2 RULE_2 was a partial component outcome
(`GATE_PASS=false`), not a completed card.

After restoring frozen CORE BTC/ETH 2020-2024 only, the same
implementation `26d8f7066533bcae7138d5a1952783f2a16f3c39` was retried.
Preflight BTC/ETH/M06 all present. D2 RULE_2 replayed exactly. Retry
classifications: D2 `PROMISING_PROTOTYPE` (RULE_1 gate pass; RULE_2
still fails), D3/D4/D5 `NO_USEFUL_STRUCTURE`. Adaptive discovery only;
not confirmatory. Protected 2025/2026 unopened. MARKET-07 not created.
No post-outcome design changes.

D1 was then adjudicated for `D1_NULL_ADEQUACY_GATE` and **deferred**:
the frozen daily GARCH null cannot generate the 288×5m `ev.rv_btc_24h`
observable used by `RV_20`, and no already-frozen mapping exists. The
gate was not executed. Independently, gate statistics remain
underspecified. `D1_STATUS = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`.
Deferred D1 is not counted as executed. D6 remains `DEFERRED`.
D4 `LEAD_LAG_1DAY` remains `DEFERRED_FROM_SPRINT_01`.

Result records: `docs/research/discovery_results/`.
Adjudication record: `docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.{json,md}`.

D2 RULE_1 (`RV_ABSTENTION`) was then taken through
`D2_CONFIRMATION_FEASIBILITY_AND_DESIGN` without opening 2025/2026
prices or creating MARKET-07/ARM. Calendar 2025 is the proposed first
independent confirmation surface; 2026 remains a second reserved
surface. Metadata-only 2025 monthly source/canonical hashes are bound.
A 2020-2024 power calculation at the predeclared 20% true effect
returned year-cycled `ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011`
(joint pass probability `0.006` is diagnostic only; practical-gate
power `~0.499` at the exact 20% boundary is expected and is not
underpower evidence). Primary prospective criterion is statistical
power `>= 0.80`. `CONFIRMATION_FEASIBILITY = UNDERPOWERED_SINGLE_YEAR_2025`.
IID two-year power `0.903` is superseded. Authoritative
year-matched whole-year-block plus contiguous partial-block power
gives `POWER_N728 = 0.64 < 0.80` and `POWER_N1092 = 1.0`.
`MIN_REQUIRED_FRESH_DECISION_ROWS = 1092`.
`POTENTIAL_FUTURE_SURFACE = MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE`.
`AUTHORIZED_TO_OPEN = false`. `2025_OPEN_AUTHORIZED = false`.
Do not consume 2025+2026. Full calendar 2026 is not currently available.
Record: `docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.{json,md}`.

`D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY` then tested whether the
same frozen RULE_1 / RV_ABSTENTION mechanism can be replicated on pre-2020
BitMEX XBTUSD without waiting for future Binance data and without opening
2025/2026. Refined year-matched power on exposed 2020-2024 only gives
`MIN_REQUIRED_FRESH_DECISION_ROWS = 815` (point-estimate power `0.801`).
Official BitMEX 5m buckets yield `BITMEX_PRE2020_ELIGIBLE_N = 1069` legal
decision rows whose 24h outcomes finish before 2020-01-01. Contract
compatibility is `SCIENTIFICALLY_COMPARABLE_CROSS_VENUE` (price-path MAE,
not inverse PnL). No D2 outcome was computed on BitMEX.
`CONFIRMATION_FEASIBILITY = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION`.
A later BitMEX result, if executed, is
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`, not exact Binance
confirmation. Protected 2025/2026 remain sealed.
Record: `docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.{json,md}`.

`D2_BITMEX_REPLICATION_PREREG_FREEZE` then froze the outcome-blind
replication contract without executing it. Evidence class
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`. Rule, target,
clock, year-matched comparator, 10000-replicate seed `20260921125`,
statistical `MU_RULE > CONTROL_P95`, and practical
`DELTA >= 0.20 * UNCONDITIONAL_MEAN` are bound. Mechanical census
reproduced `N=1069`, first `2017-01-24T00:05:00Z`, last
`2019-12-30T00:05:00Z`. Classification unassigned. No BitMEX D2 outcome.
Protected 2025/2026 unopened. MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_PREREG.{json,md}`.

`D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW` then
replaced the firewalled stub evaluator with a reviewed execution
implementation without computing BitMEX outcomes. Timestamp census still
reproduces `N=1069`. Execution remains unauthorized: no permit exists.
`IMPLEMENTATION_REVIEW = PASS`. `EXECUTION_READY = true`.
`EXECUTION_AUTHORIZED = false`.
Record: `docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.{json,md}`.

`D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION` then created the immutable
permit and executed once. Timestamp census still matches frozen
`N=1069` / `2017-01-24T00:05:00Z` / `2019-12-30T00:05:00Z` /
years `341/364/364`. Constructed eligible rows after frozen
`construct_discovery_row` were `N=1067` (years `341/363/363`). The
sample-identity gate therefore classified
`D2_BITMEX_REPLICATION_INVALID`. Primary MU_RULE / control metrics were
not computed. This is not `NOT_SUPPORTED` and not a rescue. No rerun.
Protected 2025/2026 unopened. MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_RESULT.{json,md}`.

`D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION` then identified the two
dropped timestamp-complete decisions as predeclared `BTC_RET_24H_EQ_0`
ineligibility. Class
`REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH`. Original INVALID
run preserved. No D2 effect computed. Corrected eligible N=1067; first/last
T unchanged. Original rerun unauthorized. A new integrity-repair lineage
is scientifically permissible; no permit yet.
Record: `docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.{json,md}`.

`D2_BITMEX_REPLICATION_CORRECTED_ONE_SHOT_EXECUTION` then created the
integrity-repair permit and executed once under NEW_RUN_IDENTITY
`8e3e9ecfadc18f71dae800cd16d0b0b36845c17710a108a0258c833af0420b43`.
Corrected identity passed: constructed `N=1317`, warmup `250`, eligible
`N=1067` (years `341/363/363`), first `2017-01-24T00:05:00Z`, last
`2019-12-30T00:05:00Z`. The two `BTC_RET_24H_EQ_0` rows remain excluded.
Original INVALID run preserved; primary metrics were computed only after
the amended identity gate. Classification
`D2_BITMEX_REPLICATION_SUPPORTED`. Evidence label
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED`. This is
not `EXACT_BINANCE_CONFIRMATION`, `PROVEN_ALPHA`, or
`VALIDATED_TRADING_EDGE`. No rerun. Protected 2025/2026 unopened.
MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.{json,md}`.

`PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED` then classified D2
as `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`. Discovery claim and
independent pre-2020 BitMEX replication claim are supported. Market-mechanism,
trading-edge, and product claims are not. Protected 2025/2026 remain sealed.
Hypothesis generation now rotates across families A–I; D2 neighbors are
forbidden. Product build remains frozen. MARKET-07 not created.
Record: `docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.{json,md}`.
That unit's next step was
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`
then froze an outcome-blind post-replication mechanism-decomposition
contract without executing it. Selector remains frozen D2 / RULE_1 /
`RV_ABSTENTION`. Primary target is `ADVERSE_SHARE = MAE_SIDE /
(MAE_SIDE + MAE_OPPOSITE)` on the same 24h path, versus year×SIDE-matched
rate-matched random abstention (`N=10000`, seed `20260922131`). A
pre-outcome correction replaced year-only matching with
`YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION` so candidate LONG/SHORT
composition cannot confound `ADVERSE_SHARE`. Evidence
class is `POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY`, not
independent confirmation. BitMEX 2017-2019 is not reused for this new
target. Protected 2025/2026 unopened. MARKET-07 not created. No real
decomposition outcome.
Record: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.{json,md}`.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`
then implemented that frozen design and reviewed it adversarially
**without executing the decomposition**. The design was not redesigned:
selector, SIDE, target, comparator, strata, seed, gates, thresholds and
classification order are imported from the frozen design module, not
reimplemented. The one new mechanical part is future-path reconstruction —
`DiscoveryRow` stores `future_closes` only, so the evaluator re-walks the
exact 288 5m `PerpBar` path and calls frozen `arithmetic_mae` twice on
that one shared sequence, cross-checking recomputed `MAE_SIDE`
bit-for-bit against the frozen `DiscoveryRow.severity`. Target
ineligibility (`TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE`, no
epsilon) never rebuilds the selector and is reported per year. Twenty
red-team failure classes (F1-F20) returned `NOT_CONFIRMED`; PASS is
justified by implemented/tested machinery, not by a hardcoded table.
Integrity repair closed dormant canonical orchestration, tracked-permit
authority verification, exact ordered selector-identity machinery, and
the inherited D2 NumPy linear P95 method. `IMPLEMENTATION_REVIEW = PASS`,
`SCIENTIFIC_KERNEL_READY = true`, `CANONICAL_ORCHESTRATION_READY = true`,
`PERMIT_VERIFIER_READY = true`, `EXACT_SELECTOR_IDENTITY_IMPLEMENTED = true`,
`CANONICAL_SELECTOR_DIGEST_FROZEN = false`, `EXECUTION_READY = false`,
`EXECUTION_AUTHORIZED = false`. The canonical route now requires a tracked
selector-identity authority (permit-bound SHA256) and compares the
reconstructed ordered digest to that frozen digest before any
ADVERSE_SHARE / PATH_SCALE evaluation. The authority artifact was **not**
created in the implementation-review unit.
Record: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REVIEW.{json,md}`.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE`
then reconstructed the frozen RULE_1 / RV_ABSTENTION identity from legal
CORE BTC 2020-2024 and wrote the tracked authority
`docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_SELECTOR_IDENTITY.json`.
Constructed N=1791 / years 334,364,364,364,365; abstain N=163 / years
10,48,32,23,50. No ADVERSE_SHARE, PATH_SCALE, permit, or RESULT was
computed. Distinguish:

```
IMPLEMENTATION_REVIEW_AT_TIME: CANONICAL_SELECTOR_DIGEST_FROZEN = false
CURRENT STATE: SELECTOR_IDENTITY_AUTHORITY = FROZEN
CURRENT STATE: CANONICAL_SELECTOR_DIGEST_FROZEN = true
```

The evaluator module constant remains `false` (review-unit truth). Current
lifecycle truth is the verified authority.

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION` commit 1 then
wrote the tracked execution permit
`docs/research/D2_EXCESS_PATH_RISK_EXECUTION_PERMIT.json` (exactly
`EV.tracked_permit_expected_authority`) and the outcome-blind one-shot
runner `scripts/research/d2_excess_path_risk_one_shot.py`. Evaluator-module
`EXECUTION_AUTHORIZED` remains `false` (review-era). Tracked-permit
`EXECUTION_AUTHORIZED = true`.

The exact permit commit `29f83a102bd8ece2b078f65ef69a578a52812c7c` was then
executed once. Canonical RESULT:
`docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.{json,md}`.
Evaluator classification (not reinterpreted):
`D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`.
`STATISTICAL_GATE = false`, `PRACTICAL_GATE = false`,
`TEMPORAL_GATE = true`, `PATH_SCALE_MATERIALLY_ELEVATED = true`.
No rerun. 2025/2026 remain sealed. BitMEX 2017-2019 was not reused for
this target. MARKET-07 was not created. D2 program class remains
`INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE` from the independent
pre-2020 BitMEX surface; this decomposition does not promote a robust
excess-alignment claim and does not authorize 2025/2026 open.

```
SELECTOR_IDENTITY_AUTHORITY = FROZEN
EXECUTION_PERMIT_CREATED = true
EXECUTION_AUTHORIZED = true
ONE_SHOT = true
RERUN_AUTHORIZED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = true
RESULT_CREATED = true
CLASSIFICATION = D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT
RESULT_PAYLOAD_SHA256 =
  53ce2e20064671f5ae26c9174e77e52986fba8619263b3015143dce4aa874b81
NEXT_ACTION = CONTINUE_ORTHOGONAL_FAMILY_ROTATION
NEXT_UNIT = HETEROGENEOUS_FAMILY_ROTATION_V1
```

`HETEROGENEOUS_FAMILY_ROTATION_V1` was then frozen and applied as
`DISCOVERY_SPRINT_02_HETEROGENEOUS_CARD_DEFINITION`: exactly two internal
cards, D7 `KLINE_FLOW_IMPACT_STATE` (family E, kline proxy only) and D8
`ENDOGENOUS_SHOCK_RECOVERY` (family G). Neither card is executed.
F remains `DEFERRED_BLOCKER_UNRESOLVED`; H `DEFERRED_DATA_LIMITATION`;
I `DEFERRED_SOURCE_NOT_PINNED`. Record:
`docs/research/HETEROGENEOUS_FAMILY_ROTATION_V1.{json,md}` and
`docs/research/DISCOVERY_SPRINT_02.{json,md}`.
D8 primary control is `RETURN_SHOCK_MATCHED_NON_HIGH_ACTIVITY_CONTROL`
(same P99 return-shock gate; fails only P90 volume). Recovery clock is
frozen at `EVENT_DECISION_T = H+1h` with a strict
`EVENT_DECISION_T + 6h < 2025-01-01T00:00:00Z` bound. D7 unchanged.

Sprint 02 feasibility/implementation then ran selector/support census
only on legal CORE BTC 2020-2024. D7 is `OUTCOME_BLIND_READY`. D8 is
`DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` (event support passed; 1:1
return-shock controls did not). No scientific outcomes. An outcome-blind
integrity pass then formalized
`DATA_IDENTITY_MODE = TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION`
(runtime snapshot manifest is not required), froze D7 selector identity
`N=4545` / digest `8794fece…`, and recorded D8 as final non-executable
for this card (`NOT D8_NO_USEFUL_STRUCTURE`; recovery unevaluated).
Record: `docs/research/DISCOVERY_SPRINT_02_FEASIBILITY.{json,md}` and
`docs/research/DISCOVERY_SPRINT_02_IMPLEMENTATION_REVIEW.{json,md}`.
`NEXT_UNIT = DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION` (D7-only).
The D7 one-shot scientific execution route was then executed once from
execution root `0f22d46ab0ee41be78cb45de39842c8a5684b54e`. Canonical
RESULT `docs/research/DISCOVERY_SPRINT_02_D7_RESULT.{json,md}` classified
`D7_PROMISING_PROTOTYPE` (`STATISTICAL_GATE`, `PRACTICAL_GATE`, and
`TEMPORAL_GATE` all true; yearly delta positive in 2020–2024). Evidence
label remains `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`. Not
independent confirmation, proven alpha, a validated trading edge, or an
order-book liquidity claim. No rerun. D8 remains
`DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` and is not a negative scientific
result. Protected 2025/2026 unopened. MARKET-07 not created.

`POST_D7_PROGRAM_UPDATE_AND_DISCOVERY_SPRINT_03_SELECTION` then recorded
those counters (`INTERNAL_DISCOVERY_CARDS_EXECUTED = 5`,
`INTERNAL_PROMISING_PROTOTYPES = 2`) and froze
`HETEROGENEOUS_FAMILY_ROTATION_V2`. A pre-outcome amendment (this
status) keeps D7/D8 routing, rebases onto `origin/main` `35511b3`
(`SIGNALBOT_MANDATE_V1` canonical), and expands Sprint 03 to **three**
orthogonal internal cards after `MECHANISM_MEMORY_V0`:

- D9 `VENUE_DISLOCATION_RESOLUTION_STRUCTURE` (family H; `DATA_READY`;
  estimand A `RELATIVE_RESOLUTION_ATTRIBUTION`; old `-s*(rp+rs)`
  imbalance rejected);
- D10 `BTC_ETH_RESIDUAL_SHOCK_PERSISTENCE` (family D; `DATA_READY`);
- D11 `SCHEDULED_MACRO_EVENT_VOL_RESPONSE` (family G;
  `ACQUIRABLE_FREE_HISTORICAL`).

`SPRINT03_SELECTION_INCOMPLETE = false`. Family E remains in cooldown.
D7 remains a confirmation candidate but is **not** selected for
confirmation now. `RESEARCH_DATA_DURABILITY_V1` is required (CORE BTC
bytes live in gitignored `artifacts/` without a verified object-storage
restore path) and is **not** implemented in this unit.
`NEXT_UNIT = DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION`.

All six Discovery Sprint 01 cards (D1-D6) were converted to frozen
`EXECUTABLE_DISCOVERY_SPEC` records (none deferred) by
`DISCOVERY_SPRINT_01_SPEC_COMPILATION`, recorded in
`docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`. That unit
is an outcome-blind spec freeze, not a confirmatory lifecycle: no ARM, no
claim/reservation, no one-shot execution authority. At compilation time
no discovery outcome had been computed. The first partial batch is
preserved as blocked; the CORE-restore retry completed D2-D5 as recorded
in the next-unit box above.

**Superseded by `DISCOVERY_SPRINT_01_RED_TEAM_REVIEW`** (reviewed commit
`7bb92b0bd6238693164b6592c0711fa4c15fc9fe`,
`docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.{json,md}`), which
checked whether each frozen spec was actually mechanically executable, not
merely well-worded. Seven suspected defects (F1-F7) were reviewed
outcome-blind: F1, F2, F3, F4, F6 were confirmed and fixed (per-rule legal
intervals + bound cross-venue dataset authority for D2/D5's
dislocation-based rule; an explicit base exposure schedule for D2/D5; a
corrected native-5m-granularity null for D3, replacing a mechanically
broken daily-granularity reuse; a corrected split null for D4's lead-lag
vs. rolling-correlation functionals; a corrected variance-level RV_20
formula for D1). F5 found D1's null defensibility had been asserted, not
verified -- a `D1_NULL_ADEQUACY_GATE` (non-target summary statistics only)
is now defined but not yet executed. F7 found D6's external benchmark has
at most one testable historical episode given `CORE_BTC_BINANCE_V0`'s
2020 start versus the source's 2013/2017/2021 claims, judged
diagnostically insufficient.

**Superseded again by `DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4`**
(reviewed commit `355a1657aac288fe75b272df1845fd9b5cfcac3f`,
`docs/research/DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4.{json,md}`),
D3 and D4 only; D1, D2, D5, D6 unchanged from the red-team review above.
D3's excursion functionals were direction-aligned via `BTC_SIDE(t)`,
contradicting its own `UNCONDITIONAL_DESIGN` label and risking
smuggled-in directional-predictability structure; redefined as genuinely
unsigned (`MAX_UPSIDE_EXCURSION_24h`, `MAX_DOWNSIDE_EXCURSION_24h`,
`TIME_TO_MAX_EXCURSION`, `PATH_ASYMMETRY`). D3's null was also found to
ignore UTC time-of-day -- since every MARKET-06 decision point shares the
same fixed UTC decision time, bar-offset structurally equals
time-of-day, making `TIME_TO_MAX_EXCURSION` a near-certain seasonality
confound -- corrected to a time-of-day-stratified block bootstrap. D4's
`INDEPENDENT_BLOCK_BOOTSTRAP` lead-lag null was found to also destroy
ordinary same-time common-factor dependence, not just the tested cross-lag;
`LEAD_LAG_1DAY` is now `DEFERRED_FROM_SPRINT_01` (no complex replacement
null invented), `ROLLING_CORRELATION_90D` retained unchanged.

**Superseded once more by `DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX`**
(reviewed commit `475072d22f4c4631836ca7d38ccdc5da6ce59222`,
`docs/research/DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX.{json,md}`),
D3, D4's practical-threshold semantics, and D5 only; D1 and D6 unchanged.
D3's real functionals used 5m HIGH/LOW while its surrogate only ever
produced a close-to-close path -- a real/null observable mismatch, fixed
(without inventing synthetic high/low) by redefining D3 as CLOSE-PATH
morphology: `MAX_UPSIDE_CLOSE_24H`, `MAX_DOWNSIDE_CLOSE_24H`,
`TIME_TO_MAX_ABS_CLOSE_EXCURSION` (exactly 3 functionals; `PATH_ASYMMETRY`
removed, since the original card allowed at most 2-3 and it is derivative
of the other two anyway). D4's `ROLLING_CORRELATION_90D` practical gate
made mathematically exact: `PRACTICAL_EXCESS_RANGE =
OBSERVED_CORRELATION_RANGE - NULL_RANGE_MEDIAN >= 0.15`. D5's
"beats best component" check corrected to compare against
`COMPONENT_A_DELTA_FOR_D5` / `COMPONENT_B_DELTA_FOR_D5` (both evaluated
on D5's exact common interval `2022-02-01 -> 2025-01-01`), not D2
RULE_1's unrestricted full-2020-2024 result.

**Current per-card status:** `D1 = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`
(adequacy gate not executed); `D2 = PROMISING_PROTOTYPE` (adaptive
discovery; RULE_1 only; corrected independent pre-2020 BitMEX replication
classified `D2_BITMEX_REPLICATION_SUPPORTED`; program class
`INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`; original INVALID run
preserved; not exact Binance confirmation and not a validated trading
edge);
`D3 = NO_USEFUL_STRUCTURE`; `D4
ROLLING_CORRELATION_90D = NO_USEFUL_STRUCTURE` (`LEAD_LAG_1DAY` still
deferred); `D5 = NO_USEFUL_STRUCTURE`; `D6 = DEFERRED`;
`D7 = PROMISING_PROTOTYPE` (adaptive discovery; family E cooldown; not
selected for confirmation now); `D8 = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`
(not a negative scientific result; not counted as executed);
`D9 = DEFINED_NOT_EXECUTED` (family H venue-structure; not MARKET-06
rescue). First blocked Sprint 01 attempt preserved. D2–D5 and D7
scientific bytes unchanged.

The orthogonal-region selection is recorded in
`docs/research/MARKET_NEXT_HYPOTHESIS_SELECTION.{json,md}` (commit
`a711086c36eb7129fc3f0660732049de93dd1629`) and remains a valid historical
record: R-A was chosen because it materially changes the FUNCTION axis
(scalar outcome prediction -> state detection), does not rescue
MARKET-05/06, and is feasible with existing point-in-time price data. That
selection is **preserved, not retracted**.

A later, separate program-level decision recorded in
`docs/research/HYPOTHESIS_DISCOVERY_PIPELINE_V2.{json,md}` and
`docs/research/DISCOVERY_SPRINT_01.{json,md}` **supersedes only the
routing** that followed from a711086 (i.e. turning R-A directly into the
next confirmatory research unit). Signalbot has strong
falsification/validation machinery but `INTERNAL_PROMISING_PROTOTYPES = 0`
across MARKET-01/02/05/06; MARKET-03 is external reproduction, not internal
discovery. R-A is therefore reclassified as `DISCOVERY_SPRINT_01 / D1 =
STRUCTURAL_STATE_DETECTION`: it is explored first as one of six cheap,
outcome-inspecting, non-evidentiary discovery cards (D1-D6), not
immediately preregistered as a confirmatory hypothesis. R-A's null-model
risk (surrogate/null must preserve lower-order structure, chosen
outcome-blind) carries over unchanged into card D1.

a711086's statement that R-B and R-F "need a fresh evaluation surface that
does not exist" is now scoped to **confirmatory** use only.
`DISCOVERY_FEASIBILITY != CONFIRMATORY_FEASIBILITY`: both may be explored
under adaptive discovery on historically exposed 2020-2024 data (cards D2
and D5 respectively), but any resulting pattern remains exploratory and
requires an independent future confirmation surface, and D5 (R-F) carries
an explicitly recorded HIGH rescue/multiple-testing risk. R-C is still the
most orthogonal region but has no panel data and no listing/delisting
reconstruction (see the `CROSS_SECTIONAL_PANEL_FEASIBILITY` sidecar in
`DISCOVERY_SPRINT_01`). R-D and R-E remain forward-collection only.

Do not create MARKET-07. `DISCOVERY_SPRINT_01_CARD_EXECUTION` must stop and
require a program-level decision if, after 6-10 materially orthogonal
internal discovery cards, `INTERNAL_PROMISING_PROTOTYPES == 0`.

### Historical surface exposure

2020-2024 is a **historically exposed/adapted program research surface**:
H01/H02 and further H/BATCH work adapted on 2020-02-01 -> 2025-01-01 with
outcome inspection allowed, and MARKET-01/02/05/06 consumed confirmatory
windows inside it. A chronological split inside 2020-2024 must be called
"chronological held-out evaluation on historically exposed research data",
never out-of-sample or independent confirmation. The earlier claim that
2020-2021 was unconsumed is retracted.

## Hard boundaries

- no MARKET-05 or MARKET-06 rescue, sign flip, venue swap, threshold tweak, horizon tweak, or rerun;
- no opening protected 2025/2026 merely to search for a survivor;
- no V4;
- B2-06 remains blocked;
- product build remains frozen until evidence justifies a concrete restart.

For detailed history use `docs/RESEARCH_LEDGER.md`; for immutable experiment semantics use each experiment's frozen artifacts.
