# SIGNALBOT Evidence Registry — H + B + MARKET-01..05

**Status:** `FROZEN_PROGRAM_EVIDENCE_THROUGH_MARKET_05`
**Registry ID:** `EVIDENCE_REGISTRY_H_B_M01_M05`
**Machine-readable twin:** [`EVIDENCE_REGISTRY_H_B_M01_M05.json`](EVIDENCE_REGISTRY_H_B_M01_M05.json)
**Current program authority:** this registry.
**Immutable historical snapshot:** [`EVIDENCE_REGISTRY_H_B_M01_M03.md`](EVIDENCE_REGISTRY_H_B_M01_M03.md) remains byte-identical. Prior unit objects are copied verbatim.

This is a documentation / evidence-synthesis artifact. It does **not** rerun MARKET-05, inspect protected OOS, create MARKET-06, invent a MARKET-05 rescue child, or change MARKET-05 interpretation.

```text
registry_authorizes_next_experiment = false
MARKET_06_CREATED = FALSE
NEW_SCIENTIFIC_HYPOTHESIS_ID_CREATED = FALSE
SCIENTIFIC_OUTCOMES_INSPECTED_DURING_UPDATE = FALSE
PROTECTED_OOS_TOUCHED = false
PRE_UPDATE_HEAD = 828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b
PRE_UPDATE_TREE = 338e72d23ff7f5547191221527b762a47e4e48bc
REGISTRY_CREATION_HEAD = UNSET_UNTIL_THIS_COMMIT
REGISTRY_CREATION_TREE = UNSET_UNTIL_THIS_COMMIT
```

## 1. Scope

Exactly sixteen scientific units. MARKET-04H is nested under MARKET-04 provenance and is **not** a seventeenth unit. MARKET-06 is not created.

```text
REGISTRY_UNIT_COUNT = 16
H_UNIT_COUNT = 5
B_UNIT_COUNT = 6
MARKET_UNIT_COUNT = 5
market_04_included = true
market_05_included = true
market_04h_top_level_unit = false
market_06_included = false
UNIT_IDS = H01 H02 H03 H04 H05 B2-01 B2-02 B2-03 B2-04 B2-05 B2-06 MARKET-01 MARKET-02 MARKET-03 MARKET-04 MARKET-05
```

## 2. Program-level facts

```text
internal_historical_candidates_promoted = 0
internal_validated_candidates = 0
validated_oos_candidates = 0
protected_oos_edge_confirmations = 0
h_generation_promoted = 0
h_generation_total = 5
b2_clean_promoted = 0
market_01_classification = NO_EVIDENCE
market_02_classification = NO_EVIDENCE
market_03_classification = REPRODUCED_DIRECTION
market_03_status = EXTERNAL_REPRODUCTION / REPRODUCED_DIRECTION
market_04_classification = BLOCKED_OBSERVABLE
market_04_status = BLOCKED_OBSERVABLE / NOT_TESTED
market_04_selected = true
market_04_tested = false
market_04_rejected = false
market_05_classification = NO_EVIDENCE
market_05_status = NO_EVIDENCE
signalbot_protected_oos_touched = false
independent_replication_count_is_not_equal_to_experiment_count = true
EXPERIMENT_COUNT_EQUALS_INDEPENDENT_EVIDENCE_COUNT = NO
M01_M02_INDEPENDENT_REPLICATIONS = NO
SAME_INFORMATION_SET_HYPOTHESIS_GENERATION_PAUSED = true
NEXT_PROGRAM_PHASE = INFORMATION_SET_EXPANSION
NEXT_INFORMATION_FAMILY = POINT_IN_TIME_FUNDING_PREMIUM_OBSERVABILITY
NEXT_UNIT = FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION
```

B2 units remain enumerated individually. MARKET-04 is **not** rejected. MARKET-04H is **not** scientific negative evidence.

| ID | Registry / project state |
|---|---|
| `B2-01` | `CLOSED_NO_PROMOTION` |
| `B2-02` | `CLOSED_NO_PROMOTION` |
| `B2-03` | `CLOSED_NO_PROMOTION` |
| `B2-04` | `CLOSED_NO_PROMOTION` |
| `B2-05` | `INTEGRITY_LIMITED / DEVELOPMENT_CONSUMED / ORDINARY_RESULT_UNAVAILABLE` |
| `B2-06` | `NO_EVIDENCE_UNIT / BLOCKED_MISSING_OBSERVABLE / scientific_outcome=None` |
| `MARKET-01` | `CANONICAL_HISTORICAL_TEST / NO_EVIDENCE` |
| `MARKET-02` | `CANONICAL_HISTORICAL_TEST / NO_EVIDENCE` |
| `MARKET-03` | `EXTERNAL_REPRODUCTION / REPRODUCED_DIRECTION` |
| `MARKET-04` | `SELECTED / NOT_TESTED / BLOCKED_HISTORICAL_OBSERVABLE` |
| `MARKET-05` | `CANONICAL_HISTORICAL_TEST / MARKET_05_NO_EVIDENCE` |

## 3. Lineage / dependence graph

```text
H01 -> B2-01 kind=AUTHORIZED_STRUCTURAL_CHILD
H02 -> B2-02 kind=AUTHORIZED_STRUCTURAL_CHILD
H03 -> B2-03 kind=AUTHORIZED_STRUCTURAL_CHILD
H04 -> B2-04 kind=AUTHORIZED_POSTHOC_CHILD
H05 -> B2-05 kind=AUTHORIZED_STRUCTURAL_CHILD
MARKET-01 -> MARKET-02 kind=ADAPTIVE_RESEARCH_LINEAGE independent_confirmatory_replications=false
EXTERNAL_EMA_CROSS_FUNDING_AUTHOR -> MARKET-03 kind=EXTERNAL_SOURCE_LINEAGE
MARKET-03 -> MARKET-04 kind=ADAPTIVE_HYPOTHESIS_GENERATION_FROM_EXTERNAL_REPRODUCTION independent_confirmatory_replications=false
(none) -> MARKET-05 kind=NEW_MECHANISM_SELECTED_FROM_PROGRAM_LEVEL_INFORMATION_GAP
MARKET-04H nested under MARKET-04 provenance; not a top-level unit
```

Shared dataset, shared time period, shared market regimes, sequential idea generation, and post-result child design prevent naive iid counting of experiments. Parent and child are not independent evidence. Experiment count is not independent-replication count.

Do **not** count parent and child as independent evidence.
Do **not** count experiment number as independent evidence.
M01/M02 are dependent/sequential.
M03 is external historical reproduction.
M05 is a distinct information-family test but remains historical development evidence.

## 4. Critical MARKET-03 OOS distinction

```text
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
signalbot_protected_oos_touched = false
EXTERNAL_HYPOTHESIS_SELECTION_OOS_STATUS = NOT_GUARANTEED_UNTOUCHED
EXTERNAL_M03_SELECTION_OOS_UNTOUCHED_GUARANTEED = NO
```

The external MARKET-03 author published/selected the strategy using an open-ended historical process extending beyond Signalbot's frozen reproduction interval. Signalbot's untouched 2025/2026 data must not automatically be described as pristine independent OOS relative to the EXTERNAL AUTHOR'S strategy-selection process. Those protected Signalbot outcomes were not inspected in this unit.

## 5. Anti-rescue / program-transition contract

Closed exact formulations cannot become MARKET-06 merely through:
- threshold change;
- horizon change;
- nearby indicator substitution;
- sign reversal;
- subgroup/year rescue;
- regime explanation discovered after result;
- renaming the same mechanism;
- another simple transform of the same price/OI/cross-asset information set.

MARKET-05 negative relative MAE does **not** authorize a reverse hypothesis.

```text
registry_authorizes_that_experiment = false
posthoc_residuals_are_confirmatory = false
market_05_negative_relative_mae_does_not_authorize_reverse_hypothesis = true
third_historical_proxy_salvage_authorized = false
```

## 6. Unit records

### H01

**Research ID:** `H01_COMPRESSION_EXPANSION`

```text
id = H01
mechanism_family = F3_VOLATILITY_DYNAMICS
evidence_class = DISCOVERY
canonical_status = H01_KILL
scientific_outcome = REJECTED
protected_oos_touched = false
lineage_parents = (none)
lineage_children = B2-01
parent_child_independence = False
```

**Original claim:** Unusually low recent realized volatility predicts a subsequent increase in realized volatility (compression -> expansion).

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 45
cells_normalized_future_rv_range = [0.61, 0.8]
unconditional_baseline_A_range = [1.18, 1.25]
expansion_probability_range = [0.023, 0.072]
baseline_expansion_probability_approx = 0.255
all_45_cells_below_matched_random = True
all_week_block_bootstrap_cis_negative = True
all_five_years_negative_every_cell = True
year_blocks_negative = 225
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Original compression -> expansion claim was killed on the full 45-cell surface.
- Every cell mean normalized future RV was below baseline and matched-random.
- Stronger compression was more negative, the reverse of expansion.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Reverse volatility persistence (quiet remains quieter) is POSTHOC_UNTESTED. It is hypothesis-generation material, not positive H01 confirmation.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not reframe reverse persistence as H01 confirmation.
- Do not treat opposite-sign cells as a promoted persistence edge.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** H01 and B2-01 share CORE_BTC_BINANCE_V0, 2020-2024 development years, and sequential idea generation. They are not independent replications. B2-01 is the authorized structural child of the H01 residual, not a second confirmatory test of H01.

**Authoritative source paths:**
- docs/research/BATCH01_SYNTHESIS.md
- docs/research/H01_COMPRESSION_EXPANSION_PREREG.md
- docs/research/H01_COMPRESSION_EXPANSION_PREREG.json
- docs/research/H01_DEV_SUMMARY.md
- docs/research/H01_DEV_RESULTS.json


### H02

**Research ID:** `H02_FAILED_BREAKOUT_MEAN_REVERSION`

```text
id = H02
mechanism_family = F2_REVERSION_FAILURE
evidence_class = DISCOVERY
canonical_status = H02_KILL
scientific_outcome = REJECTED
protected_oos_touched = false
lineage_parents = (none)
lineage_children = B2-02
parent_child_independence = False
```

**Original claim:** Closing back inside a local range after a breakout establishes a failed-breakout-specific mean-reversion mechanism.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 45
successful_breakout_stronger_in_cells = 44/45
short_horizon_s0_mean_norm_rev_ret_approx = [0.03, 0.06]
short_horizon_raw_reversion_bps_approx = [0.7, 1.4]
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Failed-breakout-specific mean-reversion claim failed.
- Successful-breakout control was stronger in 44/45 cells.
- Stronger overshoot was not better; robustness inverted.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Generic short-horizon boundary-timing observations (15-30m s=0 bump vs matched-random) are exploratory only and do not rescue the failed-close definition.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not treat generic short-horizon boundary timing as H02 confirmation.
- Do not redefine H02 as lower-only or successful-breakout continuation.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** H02 and B2-02 share CORE snapshot, overlapping development years, and sequential residual-to-child design. Not independent replications.

**Authoritative source paths:**
- docs/research/BATCH01_SYNTHESIS.md
- docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.md
- docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.json
- docs/research/H02_DEV_SUMMARY.md
- docs/research/H02_DEV_RESULTS.json


### H03

**Research ID:** `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION`

```text
id = H03
mechanism_family = F1_DIRECTIONAL_PERSISTENCE_PRICE_PATH
evidence_class = DISCOVERY
canonical_status = H03_REJECTED_SPECIFIC_CLAIM
scientific_outcome = REJECTED
protected_oos_touched = false
lineage_parents = (none)
lineage_children = B2-03
parent_child_independence = False
```

**Original claim:** Extreme short-horizon impulse magnitude predicts a stable two-sided continuation or exhaustion surface.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 45
p_cont_ret_gt_0_range = [0.429, 0.481]
mean_norm_cont_ret_positive_cells = 14
mean_norm_cont_ret_negative_cells = 31
mpie_continuation_cells = 3
mpie_exhaustion_cells = 11
both_sides_same_sign_cells = 11
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Impulse magnitude continuation/exhaustion surface was mixed and sign-unstable.
- No isolated cell may be promoted.
- q/W/H neighborhood, year stability, and UP/DOWN symmetry all failed.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Isolated continuation MPIE cells (W=15 q=0.98 H=15/30; W=60 q=0.95 H=15) are POSTHOC_UNTESTED.
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  DOWN-only longer-horizon exhaustion and 2023-year concentration are POSTHOC_UNTESTED.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not promote any isolated cell.
- Do not select continuation or exhaustion after seeing the surface.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** H03 and B2-03 share CORE snapshot and sequential generation. B2-03 tests path morphology, not a retest of H03 extremeness, but is not an independent replication of H03.

**Authoritative source paths:**
- docs/research/BATCH01_SYNTHESIS.md
- docs/research/H03_EXTREME_IMPULSE_PREREG.md
- docs/research/H03_EXTREME_IMPULSE_PREREG.json
- docs/research/H03_DEV_SUMMARY.md
- docs/research/H03_DEV_RESULTS.json


### H04

**Research ID:** `H04_TREND_PULLBACK_CONTINUATION`

```text
id = H04
mechanism_family = F1_DIRECTIONAL_PERSISTENCE_PRICE_PATH
evidence_class = DISCOVERY
canonical_status = H04_REJECTED_SPECIFIC_CLAIM
scientific_outcome = REJECTED
protected_oos_touched = false
lineage_parents = (none)
lineage_children = B2-04
parent_child_independence = False
```

**Original claim:** Established-trend plus material counter-trend pullback produces robust continuation across a depth neighborhood.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 45
mpie_cells = 16
all_three_gates_cells = 10
two_adjacent_exclusive_depth_bands = False
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Broad pullback-continuation claim failed.
- Adjacent deep short-H cells were often opposite-signed.
- One isolated moderate band cannot promote H04.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Moderate/local L=480 and L=960 moderate-band continuation was post-hoc. B2-04 was the one authorized structural child.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not promote moderate-only as H04 confirmation.
- Do not create a second H04-derived child inside current V2.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** B2-04 is the explicit POSTHOC_UNTESTED H04 child. Parent and child are not independent confirmatory evidence.

**Authoritative source paths:**
- docs/research/BATCH01_SYNTHESIS.md
- docs/research/H04_TREND_PULLBACK_PREREG.md
- docs/research/H04_TREND_PULLBACK_PREREG.json
- docs/research/H04_DEV_SUMMARY.md
- docs/research/H04_DEV_RESULTS.json
- docs/research/V2_FORMULATION_INVENTORY.md


### H05

**Research ID:** `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN`

```text
id = H05
mechanism_family = F4_FLOW_PARTICIPATION
evidence_class = DISCOVERY
canonical_status = H05_REJECTED_SPECIFIC_CLAIM
scientific_outcome = REJECTED
protected_oos_touched = false
lineage_parents = (none)
lineage_children = B2-05
parent_child_independence = False
```

**Original claim:** Extreme taker imbalance adds stable incremental information about subsequent return as continuation or reversal.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 45
mpie_continuation = 0/45
mpie_reversal = 0/45
structural_continuation = 0/45
structural_reversal = 0/45
full_conjunction_both_orientations = 0/45
dev_results_sha256 = 37794ba525212681d0687cf4d35f9c5bf775ff63171c9efdb1b25a3acd947011
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Imbalance-alone incremental claim failed.
- MPIE and structural gates were 0/45 on both orientations.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  BUY/SELL raw asymmetry (SELL means negative in all 45 cells; BUY positive in 37/45) does not constitute promoted evidence.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not treat BUY/SELL raw asymmetry as promoted evidence.
- Do not choose continuation or reversal after the fact.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** B2-05 is the authorized F4 child of H05's imbalance-alone failure. They are not independent replications. B2-05 ordinary RESULT evidence is separately integrity-limited.

**Authoritative source paths:**
- docs/research/BATCH01_SYNTHESIS.md
- docs/research/H05_TAKER_IMBALANCE_PREREG.md
- docs/research/H05_TAKER_IMBALANCE_PREREG.json
- docs/research/H05_DEV_SUMMARY.md
- docs/research/H05_DEV_RESULTS.json


### B2-01

**Research ID:** `B2-01_VOLATILITY_TRANSITION`

```text
id = B2-01
mechanism_family = F3_VOLATILITY_DYNAMICS
evidence_class = CONTROLLED_DEVELOPMENT
canonical_status = CLOSED_NO_PROMOTION
scientific_outcome = B2_01_CLOSED_NO_PROMOTION
protected_oos_touched = false
lineage_parents = H01
lineage_children = (none)
parent_child_independence = False
near_pass_candidate = false
```

**Original claim:** A predeclared volatility-transition state adds stable information about future realized-volatility behavior beyond the current volatility level alone.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 16
primary_positive = True
bootstrap_positive = True
material_relative_mae = False
placebo_separation = False
transition_ordering = False
horizon_robustness = False
parameter_robustness = False
year_stability = False
max_relative_mae_improvement_approx = 0.00617
materiality_threshold = 0.02
result_artifact_sha256 = 3fa3ad61752d4d7d56d1dbfa172af95bec7712aebe5d2e2edfccb725971d4d2a
```

**Positive evidence:**
- Some positive primary and bootstrap behavior existed (W=60 cells; primary_positive=true; bootstrap_positive=true at formulation level).

**Negative evidence:**
- Materiality, placebo, ordering, robustness, and stability contract failed.
- All 16 cells failed the 2% relative-MAE materiality threshold.
- No cell passed the five-gate conjunction.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Observed weak/local W=60 positive error improvements are not promoted evidence and cannot seed a current-V2 rescue.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not call B2-01 a near-pass candidate.
- Do not relax materiality because primary/bootstrap were positive.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** Authorized H01 child on the same CORE development window. Not an independent replication of H01.

**Authoritative source paths:**
- docs/research/V2_FORMULATION_INVENTORY.md
- docs/research/BATCH02_STATUS_LEDGER.md
- docs/research/B2_01_VOLATILITY_TRANSITION_PREREG.md
- docs/research/B2_01_VOLATILITY_TRANSITION_PREREG.json
- docs/research/B2_01_VOLATILITY_TRANSITION_RESULT.md


### B2-02

**Research ID:** `B2-02_BOUNDARY_INTERACTION_PATH`

```text
id = B2-02
mechanism_family = F1_DIRECTIONAL_PERSISTENCE_PRICE_PATH
evidence_class = CONTROLLED_DEVELOPMENT
canonical_status = CLOSED_NO_PROMOTION
scientific_outcome = B2_02_CLOSED_NO_PROMOTION
protected_oos_touched = false
lineage_parents = H02
lineage_children = (none)
parent_child_independence = False
```

**Original claim:** Conditional on the same pre-breach market state and comparable boundary displacement, the decision-time-observable path of interaction with the breached boundary adds incremental information about directional persistence.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 12
qualifying_breaches = 107061
all_cells_negative_mean_ae = True
all_cells_negative_path_separation = True
result_artifact_sha256 = b5bc240bc30cff92e26b1cf5a7fca4e546c70c80b7f60d113f73f580b439e971
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Candidate path enrichment did not add stable information beyond baseline.
- All 12 cells had negative mean incremental AE and negative path separation.

**Post-hoc residuals (not confirmatory):**
- (none; none confirmatory)

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** Authorized H02 child on the same CORE development window. Not an independent replication of H02.

**Authoritative source paths:**
- docs/research/V2_FORMULATION_INVENTORY.md
- docs/research/BATCH02_STATUS_LEDGER.md
- docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.md
- docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.json
- docs/research/B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md


### B2-03

**Research ID:** `B2-03_IMPULSE_MORPHOLOGY`

```text
id = B2-03
mechanism_family = F1_DIRECTIONAL_PERSISTENCE_PRICE_PATH
evidence_class = CONTROLLED_DEVELOPMENT
canonical_status = CLOSED_NO_PROMOTION
scientific_outcome = B2_03_CLOSED_NO_PROMOTION
protected_oos_touched = false
lineage_parents = H03
lineage_children = (none)
parent_child_independence = False
```

**Original claim:** Conditional on comparable signed displacement, volatility state, and decision horizon, predeclared impulse-path morphology adds stable incremental information about subsequent directional persistence.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 15
constructed_events = 131469
all_cells_negative_pooled_mean_ae = True
positive_years_every_cell = 0
isolated_morphology_ordering_passes = 4
result_artifact_sha256 = a3586344ac9c094eb38670a16b7566b8c1628300b6a1f6605fd69c369894b0c0
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Morphology enrichment did not add stable incremental information.
- All 15 cells had negative pooled mean AE and entirely negative bootstrap CIs.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Four isolated morphology_ordering passes do not authorize rescue.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not promote isolated morphology_ordering cells.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** Authorized H03 child on the same CORE development window. Not an independent replication of H03.

**Authoritative source paths:**
- docs/research/V2_FORMULATION_INVENTORY.md
- docs/research/BATCH02_STATUS_LEDGER.md
- docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.md
- docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.json
- docs/research/B2_03_IMPULSE_MORPHOLOGY_RESULT.md


### B2-04

**Research ID:** `B2-04_MODERATE_PULLBACK_STRUCTURE`

```text
id = B2-04
mechanism_family = F1_DIRECTIONAL_PERSISTENCE_PRICE_PATH
evidence_class = CONTROLLED_DEVELOPMENT
canonical_status = CLOSED_NO_PROMOTION
scientific_outcome = B2_04_CLOSED_NO_PROMOTION
protected_oos_touched = false
lineage_parents = H04
lineage_children = (none)
parent_child_independence = False
h04_child_path = CLOSED
```

**Original claim:** Within an established directional state and a preregistered moderate pullback domain, RECOVERY_FRACTION adds stable continuation information beyond trend state + pullback depth.

Headline quantities (authoritative where present; not invented):

```text
primary_cells = 15
post_refractory_events = 5100
cells_negative_mean_ae = 15/15
max_positive_years = 2/5
result_artifact_sha256 = 2e7c84cda547e8de25c7ab7f2f95beac26655b632d2ba202e4490e51c54fd4e3
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Closes the authorized H04 child path in current V2.
- Adding RECOVERY_FRACTION failed to improve the same-support depth-controlled forecast in 15/15 cells.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Negative sign is not authorization for a reverse-sign strategy.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not admit a second H04-derived child in current V2.
- Do not interpret negative AE as a reverse-sign edge.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** Explicit H04 post-hoc child. Not independent of H04 discovery.

**Authoritative source paths:**
- docs/research/V2_FORMULATION_INVENTORY.md
- docs/research/BATCH02_STATUS_LEDGER.md
- docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md
- docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json
- docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_RESULT.md


### B2-05

**Research ID:** `B2-05_FLOW_ABSORPTION`

```text
id = B2-05
mechanism_family = F4_FLOW_PARTICIPATION
evidence_class = INTEGRITY_LIMITED
canonical_status = DEVELOPMENT_CONSUMED
scientific_outcome = ORDINARY_RESULT_UNAVAILABLE
protected_oos_touched = false
lineage_parents = H05
lineage_children = (none)
parent_child_independence = False
inferred_closed_no_promotion = false
inferred_promoted_candidate = false
ordinary_result_md_present = false
recovery_status = B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED
```

**Original claim:** Conditional on comparable taker-flow imbalance and price/volatility state, a predeclared measure of contemporaneous price impact/absorption adds stable information about subsequent directional behavior.

Headline quantities (authoritative where present; not invented):

```text
ordinary_result_transcribed = False
archive_sha = e31e5666fe845116197b6f2531289bf17d848027
claimed_artifact_sha256 = 530342759e70a135915ef82382b4b97bd939620ce02925524b745ccf6cc9a57c
artifact_size_bytes = 280017092
evidence_ref = refs/heads/research-evidence/batch02/B2-05/669ae93c6a5c1d102a46fd129f04292f1beff978
note = Claimed archive digest is recorded by recovery authority. This registry does not open the archive or reconstruct scientific outcomes.
```

**Positive evidence:**
- (none)

**Negative evidence:**
- (none)

**Post-hoc residuals (not confirmatory):**
- (none; none confirmatory)

**Allowed future use:** Ordinary scientific RESULT.md is unavailable. Do not reconstruct or rerun B2-05 to fill the gap. Recovery archive is operator-adjudicated and is not ordinary confirmatory evidence. This registry does not authorize a B2-05 rerun or a MARKET-04 child of B2-05.

**Forbidden reinterpretations:**
- Do not infer B2_05_CLOSED_NO_PROMOTION from recovery closeout.
- Do not infer B2_05_PROMOTED_CANDIDATE from recovery closeout.
- Do not treat operator adjudication as historical byte-proof.
- Do not rerun or reconstruct B2-05 outcomes to fill this gap.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** Authorized H05 child. Development execution consumed; durable evidence recovery archived; operator-adjudicated historical binding. Canonical ordinary RESULT evidence is unavailable/limited. Parent/child still not independent.

**Authoritative source paths:**
- docs/research/V2_FORMULATION_INVENTORY.md
- docs/research/BATCH02_STATUS_LEDGER.md
- docs/research/B2_05_FLOW_ABSORPTION_PREREG.md
- docs/research/B2_05_FLOW_ABSORPTION_PREREG.json
- docs/research/BATCH02_DURABLE_EVIDENCE_RETENTION_V1.md
- docs/research/batch02_recovery_authority/B2-05/669ae93c6a5c1d102a46fd129f04292f1beff978.json

**Missing expected artifacts (not manufactured):**
- docs/research/B2_05_FLOW_ABSORPTION_RESULT.md does not exist on this tree or origin/main.


### B2-06

**Research ID:** `B2-06_LEVERAGE_CROWDING`

```text
id = B2-06
mechanism_family = F5_POSITIONING_OI_FUNDING
evidence_class = NO_EVIDENCE_UNIT
canonical_status = BLOCKED_MISSING_OBSERVABLE
scientific_outcome = None
protected_oos_touched = false
lineage_parents = (none)
lineage_children = (none)
parent_child_independence = True
scientific_outcome_opened = false
absence_of_execution_is_negative_evidence = false
```

**Original claim:** A predeclared BTC perpetual leverage-crowding state formed from open interest and funding changes the predictive value of a comparable price displacement beyond a price/volatility/flow-only baseline.

Headline quantities (authoritative where present; not invented):

```text
result_present = False
snapshot_id = 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
unit_verdict = SNAPSHOT_MATERIALIZED_FUNDING_PUBLICATION_UNPROVEN_RESEARCH_UNAUTHORIZED
funding_publication = FUNDING_PUBLICATION_LATENCY_UNPROVEN
```

**Positive evidence:**
- (none)

**Negative evidence:**
- (none)

**Post-hoc residuals (not confirmatory):**
- (none; none confirmatory)

**Allowed future use:** No scientific outcome was opened. Absence of execution is not negative evidence against leverage crowding. Snapshot/data-expansion identity remains available as infrastructure only. This registry does not authorize B2-06 execution or MARKET-04.

**Forbidden reinterpretations:**
- Do not treat non-execution as a failed crowding test.
- Do not treat the OI/funding snapshot as a B2-06 RESULT.
- Do not treat MARKET-01/02/03 as B2-06 execution.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** No scientific outcome. Later MARKET units that reuse OI or funding snapshots are not B2-06 results and do not close B2-06.

**Authoritative source paths:**
- docs/research/V2_FORMULATION_INVENTORY.md
- docs/research/BATCH02_STATUS_LEDGER.md
- docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md
- docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.json
- docs/research/B2_06_FUNDING_PUBLICATION_AUTHORITY.md

**Missing expected artifacts (not manufactured):**
- No B2-06 preregistered scientific RESULT exists. Expected absence.


### MARKET-01

**Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`

```text
id = MARKET-01
mechanism_family = F5_POSITIONING_OI_FUNDING
evidence_class = CANONICAL_HISTORICAL_TEST
canonical_status = RESULT
scientific_outcome = NO_EVIDENCE
protected_oos_touched = false
lineage_parents = (none)
lineage_children = MARKET-02
parent_child_independence = False
dependence_type = ADAPTIVE_RESEARCH_LINEAGE
on_origin_main = true
```

**Original claim:** After a significant directional 30-minute price impulse, the state in which open interest expands while price exhibits weak continuation in the impulse direction is associated with stronger subsequent 60-minute reversal than comparable impulse episodes without the full OI-expansion / weak-continuation state.

Headline quantities (authoritative where present; not invented):

```text
beta_candidate = -0.00016324445975347867
p_one_sided = 0.757
bootstrap_se = 0.00022218794009876234
total_eligible_episodes = 7701
candidate_episodes = 1720
baseline_episodes = 5981
usable_strata = 3
detected = False
market_01_test_calibrated = False
result_json_sha256 = 5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Frozen primary test was identifiable and did not satisfy beta_candidate > 0 and p_one_sided <= 0.05.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Opposite point-estimate sign is not evidence for a reverse effect.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not interpret opposite point-estimate sign as evidence for a reverse effect.
- Do not describe the test as V3-calibrated.
- Do not treat MARKET-01 and MARKET-02 as two independent confirmatory replications.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** MARKET-02 was designed after MARKET-01 outcome was known. Adaptive research lineage, not an independent confirmatory pair.

**Authoritative source paths:**
- docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md
- docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json
- docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.md
- docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json


### MARKET-02

**Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`

```text
id = MARKET-02
mechanism_family = F5_POSITIONING_OI_FUNDING
evidence_class = CANONICAL_HISTORICAL_TEST
canonical_status = RESULT
scientific_outcome = NO_EVIDENCE
protected_oos_touched = false
lineage_parents = MARKET-01
lineage_children = (none)
parent_child_independence = False
dependence_type = ADAPTIVE_RESEARCH_LINEAGE
on_origin_main = false
on_this_tree = false
open_research_pr = 157
```

**Original claim:** Conditional on a qualifying directional BTC perpetual price impulse and OI expansion during the following 30-minute state window, price confirmation of the original impulse during that state window is associated with stronger subsequent 60-minute continuation in the original impulse direction than weak/non-confirming price action.

Headline quantities (authoritative where present; not invented):

```text
beta_confirmation = -0.00018378788969437528
bootstrap_se = 0.0004006951864901606
p_one_sided = 0.647
total_eligible_episodes = 2487
candidate_episodes = 767
baseline_episodes = 1720
usable_strata = 3
detected = False
market_02_test_calibrated = False
result_json_sha256 = 68e084b35201d227ecd9f48e99cc65a937b15fcb55a5849b1630c5d61850b478
```

**Positive evidence:**
- (none)

**Negative evidence:**
- Frozen primary test was identifiable and did not satisfy beta_confirmation > 0 and p_one_sided <= 0.05.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Opposite point-estimate sign is not evidence for a reverse effect.

**Allowed future use:** Closed exact formulation may not become MARKET-04 or any new confirmatory identity merely by threshold/horizon/indicator/sign/subgroup/regime/rename rescue. Post-hoc residuals may be used only as hypothesis-generation material for a new identity and a separately frozen future experiment. This registry does not authorize that experiment.

**Forbidden reinterpretations:**
- Do not count MARKET-01 and MARKET-02 as two independent confirmatory replications.
- Do not describe MARKET-02 as a rescue or reclassification of MARKET-01.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** M02 design followed knowledge of M01. Shared dataset, overlapping period, and sequential idea generation prevent iid counting.

**Authoritative source paths:**
- docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md
- docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json
- docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.md
- docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.json


### MARKET-03

**Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`

```text
id = MARKET-03
mechanism_family = F5_POSITIONING_OI_FUNDING
evidence_class = EXTERNAL_REPRODUCTION
canonical_status = RESULT
scientific_outcome = REPRODUCED_DIRECTION
protected_oos_touched = false
lineage_parents = (none)
lineage_children = (none)
parent_child_independence = None
dependence_type = EXTERNAL_SOURCE_LINEAGE
validated_oos = false
replication_level = LEVEL_2_FAITHFUL_REIMPLEMENTATION
exact_differential_tests = PARTIAL
strict_funding_publication_latency = UNPROVEN
validated_candidate = false
on_origin_main = false
on_this_tree = true
open_research_pr = 162
```

**Original claim:** Under a LEVEL_2 faithful reimplementation of the pinned public EmaCross vs EmaCrossFunding strategies, signed MDD_filtered > MDD_baseline on the truncated authorized historical interval.

Headline quantities (authoritative where present; not invented):

```text
mdd_baseline = -0.4935539254862912
mdd_filtered = -0.33775527768227054
absolute_improvement_pp = 15.579864780402064
relative_improvement = 0.3156669205913307
baseline_trades = 97
filtered_trades = 71
primary_rule = REPRODUCED_DIRECTION iff MDD_filtered > MDD_baseline (signed)
result_json_sha256 = 32b9157f9e4ce285627030218c0b9e37bed1347e6d4a30e2bd8e8ca87d46976e
result_md_sha256 = a338f09d0cf0cc87879c6547b8058740bcf085c6f1e59bab9148f6825eae79bc
```

**Positive evidence:**
- Primary signed rule held: MDD_filtered > MDD_baseline on the frozen truncated interval.

**Negative evidence:**
- (none)

**Post-hoc residuals (not confirmatory):**
- (none; none confirmatory)

**Allowed future use:** LEVEL_2 historical-reproduction statement only. Not a Signalbot VALIDATED_CANDIDATE, not current alpha, not causal funding proof, not protected-OOS confirmation. This registry does not authorize MARKET-04 or a second MARKET-03 run.

**Forbidden reinterpretations:**
- Do not treat REPRODUCED_DIRECTION as VALIDATED_OOS.
- Do not treat Signalbot protected 2025/2026 as pristine independent OOS relative to the external author's selection process.
- Do not claim causal funding effect or current alpha.
- Do not upgrade EXACT_DIFFERENTIAL_TESTS beyond PARTIAL.
- Do not claim STRICT_HISTORICAL_PUBLICATION_LATENCY is proven.
- threshold change
- horizon change
- nearby indicator substitution
- sign reversal
- subgroup/year rescue
- regime explanation discovered after result
- renaming the same mechanism

**Independence notes:** External-source lineage. Not a child of MARKET-01/02 and not an independent internal validation of those units. External author selected the strategy on an open-ended historical process extending beyond Signalbot's frozen reproduction interval.

**Authoritative source paths:**
- docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md
- docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json
- docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.md
- docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.md
- docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.json

### MARKET-04

**Research ID:** `MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK`

```text
id = MARKET-04
mechanism_family = F5_POSITIONING_OI_FUNDING
evidence_class = BLOCKED_OBSERVABLE
canonical_status = SELECTED_NOT_TESTED_BLOCKED_HISTORICAL_OBSERVABLE
scientific_outcome = None
protected_oos_touched = false
lineage_parents = MARKET-03
lineage_children = (none)
parent_child_independence = False
dependence_type = ADAPTIVE_HYPOTHESIS_GENERATION_FROM_EXTERNAL_REPRODUCTION
selected = true
tested = false
rejected = false
not_tested = true
not_rejected = true
blocked_historical_observable = true
absence_of_execution_is_negative_evidence = false
scientific_failure = false
execution_authorized = false
armed = false
full_preregistration_frozen = false
result_created = false
funding_legal_historical_availability = UNRESOLVED
```

**Original claim:** Does historically available funding state add stable incremental information about future adverse price-path risk beyond a simple price / trend / volatility state?

Headline quantities (authoritative where present; not invented):

```text
scientific_result_exists = false
parent_selection_head = 33ef39988f03bf634ff61c014671b35ba9b0f6ee
audit_outcome = FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED
audit_head = 6e58882a0b7b01036a03cd9c2ec5af7cf7b7e046
```

**Positive evidence:**
- (none; unit was not scientifically tested)

**Negative evidence:**
- (none; absence of execution is not negative evidence)

**Post-hoc residuals (not confirmatory):**
- (none)

**Blocked-observable history / MARKET-04H (not a top-level unit):**

```text
MARKET-04H independent_scientific_evidence_unit = false
MARKET-04H top_level_registry_unit = false
lineage_kind = OUTCOME_BLIND_OBSERVABLE_SUBSTITUTION_AFTER_TEMPORAL_FEASIBILITY_FAILURE
status = BLOCKED_OBSERVABLE
adjudication_outcome = MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED
scientific_negative_evidence = false
```

**Allowed future use:** Parent hypothesis remains scientifically alive. MARKET-04 is SELECTED / NOT TESTED / BLOCKED HISTORICAL OBSERVABLE. Do not mark it rejected. Do not attempt a third historical proxy salvage. Do not reinterpret current Binance historical archives as point-in-time safe. Future scientific use of funding/premium requires locally provable point-in-time availability under FORWARD_MARKET_OBSERVABILITY_V1. This registry does not freeze MARKET-06 or a new MARKET hypothesis.

**Forbidden reinterpretations:**
- Do not mark MARKET-04 rejected.
- Do not treat absence of execution as scientific negative evidence.
- Do not count MARKET-04H as an independent scientific evidence unit.
- Do not treat MARKET-04H as scientific negative evidence.
- Do not invent publication latency.
- Do not treat MARKET-03 fundingTime as legal_available_at for MARKET-04.
- Do not adopt Premium Index close_time or a guessed D+2 archive rule as legal_available_at.
- Do not treat current Vision bytes as the historically first-published file.

**Independence notes:** MARKET-04 is adaptive hypothesis generation from the MARKET-03 external reproduction. It is not an independent confirmatory replication of MARKET-03. MARKET-04H is nested blocked-observable provenance, not a 17th scientific unit.

**Authoritative source paths:**
- docs/research/MARKET_04_CANDIDATE_SELECTION.md
- docs/research/MARKET_04_CANDIDATE_SELECTION.json
- docs/research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.md
- docs/research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.json
- docs/research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.md
- docs/research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.json


### MARKET-05

**Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`

```text
id = MARKET-05
mechanism_family = F7_CROSS_ASSET_MARKET_CONTEXT
evidence_class = CANONICAL_HISTORICAL_TEST
canonical_status = RESULT
scientific_outcome = NO_EVIDENCE
classification = MARKET_05_NO_EVIDENCE
scientifically_spent = true
rerun_authorized = false
protected_oos_touched = false
lineage_parents = (none)
lineage_children = (none)
parent_child_independence = None
dependence_type = NEW_MECHANISM_SELECTED_FROM_PROGRAM_LEVEL_INFORMATION_GAP
market_04_rescue = false
```

**Original claim:** When BTC has a directional displacement, does contemporaneous ETH confirmation add stable incremental information about BTC's subsequent adverse-path risk beyond BTC's own price / path / volatility state?

Closed exact formulation:

```text
daily 00:00 UTC decisions
24h BTC state
continuous ETH confirmation
ETH_CONFIRMATION = BTC_SIDE * Z_ETH
24h BTC direction-aligned adverse-path risk
BTC-only baseline vs baseline + ETH_CONFIRMATION
```

Canonical RESULT identity:

```text
RESULT_HEAD = 828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b
RESULT_TREE = 338e72d23ff7f5547191221527b762a47e4e48bc
RUN_IDENTITY = 6957613de4b035d850fc97edb833565c5fd3d7b085aa158e0992b88142190635
result_json_sha256 = 80a29335dc697e784c1bb6d47c81dd1760f2f19bc49d36573b59372255a47f14
result_md_sha256 = f0849bdaf3cf1fb0e939696d2fdc230342045717f902fcb5ef12f28b889db6ed
```

Headline quantities (authoritative bound RESULT; not re-derived here):

```text
eligible_rows = 1825
BETA_ETH_CONFIRMATION = -0.0002567502511611957
BETA_ETH_CONFIRMATION_CI = [-0.0023464584123732146, 0.0015931596784811688]
POOLED_MAE_BASELINE = 0.01474832634118777
POOLED_MAE_CANDIDATE = 0.014768642312125536
RELATIVE_MAE_IMPROVEMENT = -0.0013775102657600513
RELATIVE_MAE_IMPROVEMENT_CI = [-0.00249762914797686, -0.000375839559399871]
YEAR_2022 = 0.000026398780684000478
YEAR_2023 = -0.004303506211586372
YEAR_2024 = -0.00045725937785223714
G1 = PASS
G2 = FAIL
G3 = FAIL
G4 = FAIL
G5 = FAIL
G6 = FAIL
```

**Positive evidence:**
- (none)

**Negative evidence:**
- The frozen exact formulation did not provide stable incremental predictive value on the canonical historical test. G1 PASS; G2-G6 FAIL. Classification MARKET_05_NO_EVIDENCE.

**Post-hoc residuals (not confirmatory):**
- status = POSTHOC_UNTESTED; confirmatory = FALSE
  Negative relative MAE does not authorize a reverse hypothesis.

**Allowed future use:** MARKET-05 is scientifically spent. No rerun. Closed exact formulation may not be rescued by threshold/horizon/indicator/sign/subgroup/regime/rename. Negative relative MAE does not authorize a reverse hypothesis. This is historical development evidence, not validated OOS.

**Forbidden reinterpretations:**
- Do not write that cross-asset context is useless.
- Do not write that ETH contains no predictive information.
- Do not write that divergence is validated.
- Do not write that reverse sign is validated.
- Do not write that ETH worsens BTC forecasting generally.
- Do not invent a rescue child of MARKET-05.
- Do not create MARKET-06 from another simple transform of the same information set.
- Do not change MARKET-05 interpretation.
- Do not inspect protected OOS.
- Do not rerun MARKET-05.

**Independence notes:** MARKET-05 is a distinct information-family test (F7 cross-asset confirmation) but remains historical development evidence. It is not an independent confirmatory replication of MARKET-01/02/03/04. Experiment count is not independent-evidence count.

**Authoritative source paths:**
- docs/research/MARKET_05_CROSS_ASSET_PREREG.md
- docs/research/MARKET_05_CROSS_ASSET_PREREG.json
- docs/research/MARKET_05_RESULT.md
- docs/research/MARKET_05_RESULT.json
- docs/research/MARKET_05_PROGRAM_INTERPRETATION.md
- docs/research/MARKET_05_PROGRAM_INTERPRETATION.json


## 7. Mechanism-family synthesis

Families are **not ranked**. No new MARKET hypothesis family is selected. MARKET-06 is not created. Same-information-set hypothesis generation is paused.

```text
families_ranked = false
next_family_selected = false
same_information_set_hypothesis_generation_paused = true
next_program_phase = INFORMATION_SET_EXPANSION
next_information_family = POINT_IN_TIME_FUNDING_PREMIUM_OBSERVABILITY
```

### F1_DIRECTIONAL_PERSISTENCE_PRICE_PATH

```text
evidence_units = H03, H04, B2-02, B2-03, B2-04
clean_positive_units = (none)
clean_negative_or_no_promotion_units = H03, H04, B2-02, B2-03, B2-04
untested_or_integrity_limited_units = (none)
```

- **Current interpretation:** Current-V2 F1 formulations closed without promotion. H03/H04 discovery claims failed; B2-02/03/04 added no stable incremental path/morphology/recovery information. H04 moderate residual was tested once as B2-04 and closed.
- **What is closed:** Exact H03/H04 discovery claims and current-V2 B2-02/03/04 formulations, including the sole H04 child path.
- **What remains hypothesis-generation material:** H03 isolated-cell / one-sided residuals and any future materially new path identity. Not confirmatory and not selected here.

### F2_REVERSION_FAILURE

```text
evidence_units = H02
clean_positive_units = (none)
clean_negative_or_no_promotion_units = H02
untested_or_integrity_limited_units = (none)
```

- **Current interpretation:** Failed-breakout-specific mean reversion is closed. No novelty-qualified F2 formulation was admitted to frozen V2 inventory (F2 = RETIRED).
- **What is closed:** Exact H02 failed-breakout-specific claim; current-V2 F2 inventory empty/retired.
- **What remains hypothesis-generation material:** Generic short-horizon boundary-timing observations are exploratory only. Not confirmatory and not selected here.

### F3_VOLATILITY_DYNAMICS

```text
evidence_units = H01, B2-01
clean_positive_units = (none)
clean_negative_or_no_promotion_units = H01, B2-01
untested_or_integrity_limited_units = (none)
```

- **Current interpretation:** Compression -> expansion was killed. The authorized transition child B2-01 closed without promotion despite some primary/bootstrap positives because the full contract failed. Not a near-pass.
- **What is closed:** Exact H01 expansion claim and current-V2 B2-01 transition formulation.
- **What remains hypothesis-generation material:** Reverse volatility persistence remains POSTHOC_UNTESTED. Not H01 confirmation and not selected here.

### F4_FLOW_PARTICIPATION

```text
evidence_units = H05, B2-05
clean_positive_units = (none)
clean_negative_or_no_promotion_units = H05
untested_or_integrity_limited_units = B2-05
```

- **Current interpretation:** Imbalance-alone incremental claim failed. B2-05 development was consumed but ordinary RESULT evidence is integrity-limited; no CLOSED_NO_PROMOTION or PROMOTED verdict is inferred.
- **What is closed:** Exact H05 imbalance-alone incremental claim.
- **What remains hypothesis-generation material:** H05 BUY/SELL raw asymmetry is POSTHOC_UNTESTED and not promoted. B2-05 remains integrity-limited, not a clean family close.

### F5_POSITIONING_OI_FUNDING

```text
evidence_units = B2-06, MARKET-01, MARKET-02, MARKET-03, MARKET-04
clean_positive_units = (none)
clean_negative_or_no_promotion_units = MARKET-01, MARKET-02
untested_or_integrity_limited_units = B2-06, MARKET-04
external_reproduction_units = MARKET-03
```

- **Current interpretation:** B2-06 was never scientifically opened. MARKET-01 and MARKET-02 are canonical historical tests with NO_EVIDENCE and are adaptively dependent. MARKET-03 reproduced the public drawdown-direction claim at LEVEL_2; that is not a validated internal candidate and not protected-OOS confirmation. MARKET-04 remains SELECTED / NOT TESTED / BLOCKED HISTORICAL OBSERVABLE. MARKET-04 is not rejected. MARKET-04H is nested blocked-observable provenance, not independent scientific negative evidence.
- **What is closed:** Exact MARKET-01 and MARKET-02 confirmatory identities. MARKET-03 one-shot reservation is consumed; no rerun. MARKET-04 parent hypothesis remains scientifically alive but historically untestable under current provenance.
- **What remains hypothesis-generation material:** B2-06 leverage-crowding remains untested (not negative). MARKET-04 remains blocked/not tested (not rejected). MARKET-03 external reproduction is not authorization for a funding-alpha candidate. Do not attempt a third historical proxy salvage. Next information work is point-in-time funding/premium observability, not a new MARKET hypothesis ID.

### F7_CROSS_ASSET_MARKET_CONTEXT

```text
evidence_units = MARKET-05
clean_positive_units = (none)
clean_negative_or_no_promotion_units = MARKET-05
untested_or_integrity_limited_units = (none)
```

- **Current interpretation:** MARKET-05 closed the exact preregistered ETH-confirmation incremental-MAE formulation as MARKET_05_NO_EVIDENCE. The candidate did not provide stable incremental predictive value. This does not prove ETH is generally non-predictive or that reverse sign is validated.
- **What is closed:** Exact MARKET-05 formulation: daily 00:00 UTC decisions, 24h BTC state, continuous ETH confirmation, 24h BTC direction-aligned adverse-path risk, BTC-only baseline vs baseline + ETH_CONFIRMATION.
- **What remains hypothesis-generation material:** MARKET-05 is scientifically spent. Nearby same-information-set transforms are paused. Negative relative MAE is not a reverse-hypothesis authorization.

## 8. Source bindings

Prior H/B/M01–M03 source bindings remain those frozen in
`EVIDENCE_REGISTRY_H_B_M01_M03` (SHA256
`f30b44a2d333600e3e6417f517e65c5dc1bde81fb03a6d1870cfcf19576c83c2` /
`0892f66db94cc679cb938980127985ab9a81efece62b2adb755c1b7e8a048c72`
at HEAD `ec7960d5cad47682fec1fa5d33b1a03997a8b62b`). This unit does not
rewrite those bytes.

Additional MARKET-04 / MARKET-05 / program-closeout bindings:

| Path | Role |
|---|---|
| `docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.md` | Immutable 14-unit historical snapshot |
| `docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.json` | Immutable 14-unit historical snapshot twin |
| `docs/research/MARKET_04_CANDIDATE_SELECTION.md` | MARKET-04 selected identity |
| `docs/research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.md` | Unresolved historical availability |
| `docs/research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.md` | Nested blocked observable |
| `docs/research/MARKET_05_RESULT.json` | Canonical MARKET-05 RESULT |
| `docs/research/MARKET_05_PROGRAM_INTERPRETATION.md` | Program-level MARKET-05 interpretation |
| `docs/research/FORWARD_MARKET_OBSERVABILITY_V1.md` | Design-only next information-collection unit |

```text
MARKET_06_CREATED = NO
NEW_HYPOTHESIS_CREATED = NO
NEW_OUTCOME_ACCESSED = NO
SCIENTIFIC_OUTCOMES_INSPECTED_DURING_UPDATE = NO
PROTECTED_OOS_TOUCHED = NO
```
