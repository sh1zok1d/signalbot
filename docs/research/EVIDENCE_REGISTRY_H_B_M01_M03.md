# SIGNALBOT Evidence Registry — H + B + MARKET-01..03

**Status:** `FROZEN_OUTCOME_BLIND_PROGRAM_SYNTHESIS`
**Registry ID:** `EVIDENCE_REGISTRY_H_B_M01_M03`
**Machine-readable twin:** [`EVIDENCE_REGISTRY_H_B_M01_M03.json`](EVIDENCE_REGISTRY_H_B_M01_M03.json)
**Purpose:** Freeze the state of H + B + MARKET-01..03 evidence BEFORE any MARKET-04 selection.

This is a documentation / evidence-synthesis artifact. It does not design MARKET-04,
select the next hypothesis, create a preregistration, run an experiment, or inspect
protected 2025/2026 Signalbot OOS.

Registry evidence classes are metadata only and do **not** replace existing
canonical project verdict strings.

```text
registry_authorizes_next_experiment = false
MARKET_04_SELECTED = FALSE
NEW_HYPOTHESIS_CREATED = FALSE
NEW_OUTCOME_ACCESSED = FALSE
PRE_REGISTRY_HEAD = 9c360a19a8e35ba0e7638fd125a0e6ae32f15846
PRE_REGISTRY_TREE = 16e8d125fc453202a4b5ce9c5c11f2cb5ff7b966
REGISTRY_CREATION_HEAD = UNSET_UNTIL_THIS_COMMIT
REGISTRY_CREATION_TREE = UNSET_UNTIL_THIS_COMMIT
```

## 1. Scope

Exactly fourteen research units. MARKET-04 is not included.

```text
REGISTRY_UNIT_COUNT = 14
H_UNIT_COUNT = 5
B_UNIT_COUNT = 6
MARKET_UNIT_COUNT = 3
market_04_included = false
UNIT_IDS = H01 H02 H03 H04 H05 B2-01 B2-02 B2-03 B2-04 B2-05 B2-06 MARKET-01 MARKET-02 MARKET-03
```

## 2. Program-level facts

```text
internal_validated_candidates = 0
protected_oos_edge_confirmations = 0
h_generation_promoted = 0
h_generation_total = 5
b2_clean_promoted = 0
market_01_classification = NO_EVIDENCE
market_02_classification = NO_EVIDENCE
market_03_classification = REPRODUCED_DIRECTION
signalbot_protected_oos_touched = false
independent_replication_count_is_not_equal_to_experiment_count = true
EXPERIMENT_COUNT_EQUALS_INDEPENDENT_EVIDENCE_COUNT = NO
M01_M02_INDEPENDENT_REPLICATIONS = NO
```

B2 units are enumerated individually. B2-05 and B2-06 have different evidence
states; they are not forced into one misleading denominator.

| ID | Registry / project state |
|---|---|
| `B2-01` | `CLOSED_NO_PROMOTION` |
| `B2-02` | `CLOSED_NO_PROMOTION` |
| `B2-03` | `CLOSED_NO_PROMOTION` |
| `B2-04` | `CLOSED_NO_PROMOTION` |
| `B2-05` | `INTEGRITY_LIMITED / DEVELOPMENT_CONSUMED / ORDINARY_RESULT_UNAVAILABLE` |
| `B2-06` | `NO_EVIDENCE_UNIT / BLOCKED_MISSING_OBSERVABLE / scientific_outcome=None` |

## 3. Lineage / dependence graph

```text
H01 -> B2-01 kind=AUTHORIZED_STRUCTURAL_CHILD
H02 -> B2-02 kind=AUTHORIZED_STRUCTURAL_CHILD
H03 -> B2-03 kind=AUTHORIZED_STRUCTURAL_CHILD
H04 -> B2-04 kind=AUTHORIZED_POSTHOC_CHILD
H05 -> B2-05 kind=AUTHORIZED_STRUCTURAL_CHILD
MARKET-01 -> MARKET-02 kind=ADAPTIVE_RESEARCH_LINEAGE independent_confirmatory_replications=false
EXTERNAL_EMA_CROSS_FUNDING_AUTHOR -> MARKET-03 kind=EXTERNAL_SOURCE_LINEAGE
```

Shared dataset, shared time period, shared market regimes, sequential idea generation, and post-result child design prevent naive iid counting of experiments. Parent and child are not independent evidence. Experiment count is not independent-replication count.

Do **not** count parent and child as independent evidence.

## 4. Critical MARKET-03 OOS distinction

```text
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
signalbot_protected_oos_touched = false
EXTERNAL_HYPOTHESIS_SELECTION_OOS_STATUS = NOT_GUARANTEED_UNTOUCHED
EXTERNAL_M03_SELECTION_OOS_UNTOUCHED_GUARANTEED = NO
```

The external MARKET-03 author published/selected the strategy using an open-ended historical process extending beyond Signalbot's frozen reproduction interval. Signalbot's untouched 2025/2026 data must not automatically be described as pristine independent OOS relative to the EXTERNAL AUTHOR'S strategy-selection process. Those protected Signalbot outcomes were not inspected in this unit.

## 5. Anti-rescue / future-use contract

Closed exact formulations cannot become MARKET-04 merely through:
- threshold change;
- horizon change;
- nearby indicator substitution;
- sign reversal;
- subgroup/year rescue;
- regime explanation discovered after result;
- renaming the same mechanism;

Post-hoc residuals may be used only as hypothesis-generation material for a
new identity and a separately frozen future experiment.

```text
registry_authorizes_that_experiment = false
posthoc_residuals_are_confirmatory = false
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


## 7. Mechanism-family synthesis

Families are **not ranked**. No next family is selected. MARKET-04 is not recommended.

```text
families_ranked = false
next_family_selected = false
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
evidence_units = B2-06, MARKET-01, MARKET-02, MARKET-03
clean_positive_units = (none)
clean_negative_or_no_promotion_units = MARKET-01, MARKET-02
untested_or_integrity_limited_units = B2-06
external_reproduction_units = MARKET-03
```

- **Current interpretation:** B2-06 was never scientifically opened. MARKET-01 and MARKET-02 are canonical historical tests with NO_EVIDENCE and are adaptively dependent. MARKET-03 reproduced the public drawdown-direction claim at LEVEL_2; that is not a validated internal candidate and not protected-OOS confirmation.
- **What is closed:** Exact MARKET-01 and MARKET-02 confirmatory identities. MARKET-03 one-shot reservation is consumed; no rerun.
- **What remains hypothesis-generation material:** B2-06 leverage-crowding remains untested (not negative). MARKET-03 external reproduction is not authorization for a funding-alpha candidate. No family is ranked or selected here.

## 8. Source bindings

Each authoritative source is bound to a git blob SHA and SHA256 of exact bytes.
MARKET-02 RESULT/prereg bytes are bound from open PR #157 commit
`70f9489bd4fed905255b6791adcd23dc1e7d5dfa` and are **not**
on origin/main or this working tree. MARKET-03 RESULT bytes are on this tree /
open PR #162 and are **not** on origin/main. MARKET-01 RESULT is on origin/main.

Governance files (`PROJECT_STATUS`, `RESEARCH_LEDGER`, `EDGE_RESEARCH_PROTOCOL`,
`ACTIVE_RESEARCH_RISKS`) are bound at `PRE_REGISTRY_HEAD`. This unit may append
a pointer after that binding.

| Path | Location | Bound commit | git blob | SHA256 |
|---|---|---|---|---|
| `docs/research/BATCH01_SYNTHESIS.md` | `this_tree` | `9c360a19a8e3` | `d62807f30d62c645f7e816c124c92974f4124715` | `5b25807af794e5e407002eeddbe2d481b34828c7c5214c0c5047bb81a52bf62b` |
| `docs/research/H01_COMPRESSION_EXPANSION_PREREG.md` | `this_tree` | `9c360a19a8e3` | `d41bf2ea9634882b09bfbe3e82a21b08c440efbd` | `c41be1bdfd00a2c45699d50e6d75fc02afabfa9636e8dd40fb4c879277212fe5` |
| `docs/research/H01_COMPRESSION_EXPANSION_PREREG.json` | `this_tree` | `9c360a19a8e3` | `f505c8468a5ae3f4a1cde0c855ef855bdba93b68` | `26ba3bd8009342c38be7525df3f09d14aa28b36f31a5dcbed3db4de0c0184e53` |
| `docs/research/H01_DEV_SUMMARY.md` | `this_tree` | `9c360a19a8e3` | `c1e3e38e506b6f1deba3e9686c1cf07c86849d89` | `2f29eeba7c50e7775144ed0f9171f3dd1c2da3d2345d73756adb8faf29006b0f` |
| `docs/research/H01_DEV_RESULTS.json` | `this_tree` | `9c360a19a8e3` | `ac766ef8b3dd0b2628d531206437cf490ab9cc79` | `6b5e17e62d94c9b0510cf6e6a110bec460c0f97ef40db0d41f631111b135392d` |
| `docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.md` | `this_tree` | `9c360a19a8e3` | `5fcf7302ed080cdb3a7d0db1c7d4660cabb17d5f` | `7b5a9493d07c532799e79484dfab55f0186d71075d83998ae94a5a71dce9ae81` |
| `docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.json` | `this_tree` | `9c360a19a8e3` | `dd4c62cd0fddafb6abe88f72eed95e3425956e04` | `34d39d453fb3eba863437dfd36c913cb354b76f045f340b29bb0a25eb6398985` |
| `docs/research/H02_DEV_SUMMARY.md` | `this_tree` | `9c360a19a8e3` | `83a2dc13b30a7d2e2e600f507fd37d95ddcc123d` | `234a61870b39506343094780d80518c9a958d75040d9de2eed87d3e157791fcb` |
| `docs/research/H02_DEV_RESULTS.json` | `this_tree` | `9c360a19a8e3` | `17969e0791d79d0673594deb3b919a2efd3fe587` | `a53775a7edffc20933886326dce112df85f831def187b172e11158889a0168fc` |
| `docs/research/H03_EXTREME_IMPULSE_PREREG.md` | `this_tree` | `9c360a19a8e3` | `f02abbd4b97e877e16b40c310931d4817a64c6d8` | `5035116cfc4fb1ba16b67ad2d3fc104d14746069f5a5ff8e6b0e71ac29254ca8` |
| `docs/research/H03_EXTREME_IMPULSE_PREREG.json` | `this_tree` | `9c360a19a8e3` | `2eec2e41334a8e3c68bc62d8dae7e03ff7694f5d` | `121ab2fac863ed255906072180e9a0a4e7554660640f0dcea6163b78eb2ce719` |
| `docs/research/H03_DEV_SUMMARY.md` | `this_tree` | `9c360a19a8e3` | `6c5d496a9d75db602511d4a46f86a219442fbf8d` | `512dae6a88aab319f10b9c12de9470ca0d506105b97159d9c91d1631b08a67e2` |
| `docs/research/H03_DEV_RESULTS.json` | `this_tree` | `9c360a19a8e3` | `44a6050c521ec3ab65e198d86463163678c6e569` | `866f4f6ad9f061df2c116a58681854d7a778d5823e0e321c37f5fe455d017d86` |
| `docs/research/H04_TREND_PULLBACK_PREREG.md` | `this_tree` | `9c360a19a8e3` | `ede95eb4a51f5c8d061b485ca0145b26fa4d6334` | `29afa57dc93aaec8a42e24d9c7e9db80d12abb4c69842619f1d1e57f2329a4da` |
| `docs/research/H04_TREND_PULLBACK_PREREG.json` | `this_tree` | `9c360a19a8e3` | `ccc46e0c2459def3bc3c51e94507047e5880acf6` | `ed61a39a3b7c0adc8e472223bb0bfeef7d3c23e5ba07eeabdaba95fa184f09d3` |
| `docs/research/H04_DEV_SUMMARY.md` | `this_tree` | `9c360a19a8e3` | `99b642c2e1a0616c7d0b3a105eb0b557dfda8447` | `5996e15acf084e5e88b7ec2dca02da4f0f5fbafd73ee1390759d6a4e19654e3c` |
| `docs/research/H04_DEV_RESULTS.json` | `this_tree` | `9c360a19a8e3` | `1ebb8ee5689332d1a730fd0cee9d445157896d85` | `14d5cd3d64113c922e4128a45d00ce49ba324dc8fb066449ddb8e79dcecf862b` |
| `docs/research/H05_TAKER_IMBALANCE_PREREG.md` | `this_tree` | `9c360a19a8e3` | `31dd29f1a0dd91dee1c689340a4a3a8dc183f93f` | `fc155259e60c75c27fa512aa82741c2fc67c2c83fe706d929a908346375700ae` |
| `docs/research/H05_TAKER_IMBALANCE_PREREG.json` | `this_tree` | `9c360a19a8e3` | `a2fcc055cc89c9b26eb9e549780884b576179234` | `654a9571fbfb597eb8d4217504e6c39209827e9552c06d32f1c1fae7c7b972df` |
| `docs/research/H05_DEV_SUMMARY.md` | `this_tree` | `9c360a19a8e3` | `25794c8a48b9b79f3f584f416e4fd5335304d52c` | `c07ac64308128a0f9ef5702cf135f97160ff1c538d56ec606f95beff83e198a6` |
| `docs/research/H05_DEV_RESULTS.json` | `this_tree` | `9c360a19a8e3` | `b39525939292f4e7a2f236510788e3eb608895ae` | `37794ba525212681d0687cf4d35f9c5bf775ff63171c9efdb1b25a3acd947011` |
| `docs/research/V2_FORMULATION_INVENTORY.md` | `this_tree` | `9c360a19a8e3` | `d20a3ad4f6d3fb417ee9875933f097c174da3a30` | `a369c8de42871b6a1decd8680c06fb6b1f744cf012c7bf3c3752b03da12c5b20` |
| `docs/research/BATCH02_STATUS_LEDGER.md` | `this_tree` | `9c360a19a8e3` | `5bfe32dae5624ba0e574b93f1d7474f6e03c9385` | `6067ab255d6e3fc7216914369849f2bc1cf30f6fd50dd3c502314ff3ca7d8599` |
| `docs/research/B2_01_VOLATILITY_TRANSITION_PREREG.md` | `this_tree` | `9c360a19a8e3` | `6ecf005468bb7fa59cd109df6917a59ae219dfdc` | `8ac37cd9929113a87b3c9be799f2920f2d0e1afcda4177de089a8c705e41f57c` |
| `docs/research/B2_01_VOLATILITY_TRANSITION_PREREG.json` | `this_tree` | `9c360a19a8e3` | `342a7c3816136b91c22c193a929b9c9c52492f62` | `7fe105549d756a74fd9360449e7b464bf53f51560705ba1010d127ac943838fb` |
| `docs/research/B2_01_VOLATILITY_TRANSITION_RESULT.md` | `this_tree` | `9c360a19a8e3` | `25ec33d95f4e74c89a91867de873fc085f315908` | `500ee6819960d310d39c36716b793c888b7fdeaec605b44d0a12fc81c2133d9f` |
| `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.md` | `this_tree` | `9c360a19a8e3` | `abe8d6bcdf9a71a451f15ebb13d3e2131792b0a3` | `e74897f48b63dfc4433ad919ac7dce6c490f40f64a4110deb47b70868440de85` |
| `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.json` | `this_tree` | `9c360a19a8e3` | `6c3b53002a38db2fc0e7cda86b4490ada2233118` | `3dd11009cd738ab02ab3a3a0a552de9a25a6c4db765d6510f63937c922a6d7b1` |
| `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md` | `this_tree` | `9c360a19a8e3` | `48a0fcec4a44edff9bd8a70c6f4912232415665e` | `9ab013b8909ed8eaddd0ddd3611d493ba0f4db30d883562c38d1d62ef3653b63` |
| `docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.md` | `this_tree` | `9c360a19a8e3` | `e84910f51837e91c4462586b1bfaa0a22797014c` | `9c74464d574e3650fdd3fe7dfe3e9bf08273cfc8e33acd558d5676bb7c88f5d5` |
| `docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.json` | `this_tree` | `9c360a19a8e3` | `b01e89c2f9d2ab20cf7a7de96f9e3071d5da875a` | `1af2727eb99538224c432b4ad023e50b56bee724a229789c2a436faede36be7f` |
| `docs/research/B2_03_IMPULSE_MORPHOLOGY_RESULT.md` | `this_tree` | `9c360a19a8e3` | `f47493d8a5ed3a0c0b616037719f5980223e5f63` | `7516450ae6836de2f131800105d5f590007118ad2cd7eab5b37659dee01489ce` |
| `docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md` | `this_tree` | `9c360a19a8e3` | `e8ed92bbc0974d9de002db5f2754f78fe2e47a71` | `840e49557ea44d5939bf5d791aa5448ce57a4e2fcd830d93502e7bce2cc9d1c0` |
| `docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json` | `this_tree` | `9c360a19a8e3` | `4a5a8afd8dc219112446a8b91c3d66c063d4aa6e` | `6ec991d2e33578a735e4ecf5ff6029c11baed6b7b7f6aca7a4061d5c65f0df13` |
| `docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_RESULT.md` | `this_tree` | `9c360a19a8e3` | `f15eedb5be9281af6404a2a0dc1057332abba4a2` | `6dbaaa1116522194348ae0806a7cfdae7f825c37ac509cfc0a89e412897421a7` |
| `docs/research/B2_05_FLOW_ABSORPTION_PREREG.md` | `this_tree` | `9c360a19a8e3` | `edd35bcacaf12321f7832982cb522dd8f04588a2` | `4b2f6a2f66719e93d2281b0513b39b35197bf8ae55c023748ecf1bbd38a3f020` |
| `docs/research/B2_05_FLOW_ABSORPTION_PREREG.json` | `this_tree` | `9c360a19a8e3` | `198f496ea5ea4f8b8696a08d5230d1ac8c37d4c8` | `494b9c3a3f8fa51228c2e7e737d9d84e18e61dc0f0349749382ba93170243662` |
| `docs/research/BATCH02_DURABLE_EVIDENCE_RETENTION_V1.md` | `this_tree` | `9c360a19a8e3` | `89d23af8f1e0bc87102d8057b2fcc6e8d9450139` | `1b2746099190efcb42e5b99e57601aafaa1b1a4eaf793417f42b732f9b4f4f6f` |
| `docs/research/batch02_recovery_authority/B2-05/669ae93c6a5c1d102a46fd129f04292f1beff978.json` | `this_tree` | `9c360a19a8e3` | `38c39a52f5f218d9f5c36475d49fac2778d825e4` | `1172598beea64b33750201f4e9030d3ffd779336b6258dcfeb49bde407a126c8` |
| `docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md` | `this_tree` | `9c360a19a8e3` | `cb65e02399a08a07af7043ca900ae44eedf7570a` | `5a6dac5c27346b8ec63164fe1bc2eceeb0b84d1a4f3a098a84c568b3e361935c` |
| `docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.json` | `this_tree` | `9c360a19a8e3` | `6ff10256e42bc52c8a59ef8dd55a39cf03afb9fd` | `61672b64dd9e69f77cf515f0f03d916f5e89de592fec3bf4595ec3af9090b814` |
| `docs/research/B2_06_FUNDING_PUBLICATION_AUTHORITY.md` | `this_tree` | `9c360a19a8e3` | `b2a3967d7732a5f4bc84dd5dd6da16089c36bdd4` | `1917c74d2ddd0bd4b421d2220f3ac56bbdf37aaecf5b088d5eb8ce5c89f88ff0` |
| `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md` | `this_tree` | `9c360a19a8e3` | `7d40e10891ab821097da674fa0616a9486913004` | `d82b60e1a923e8eb897252abc4a9013b6535357004f2dc7dc08f56f072542866` |
| `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json` | `this_tree` | `9c360a19a8e3` | `215823d161982d62ab3683fca3ac78f830cfbad8` | `6885abaf178401a1307e9adc5c02c69dac4fb5f3034bfddebfafc2439dde2ce4` |
| `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.md` | `this_tree` | `9c360a19a8e3` | `67335d96c882116c1ee92a5ebe7488069974910c` | `f853bc523705bd8886d20c857fe6de8521788f6064a93be8f746006993bbc0d2` |
| `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json` | `this_tree` | `9c360a19a8e3` | `30cdab772d3edaf621ae3c6e2b8c55a376862365` | `5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e` |
| `docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md` | `this_tree` | `9c360a19a8e3` | `a11b995964b8520670f2dcffdfb0253a5fb357b6` | `044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57` |
| `docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json` | `this_tree` | `9c360a19a8e3` | `ddb5c8dac00aba6a4c4c67da3b02d5d70ca605a0` | `3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89` |
| `docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.md` | `this_tree` | `9c360a19a8e3` | `a0deaf0453b83a831da7b4b2c960e15cbfc4a7e1` | `0cc76a04a3833091f0903064dccab7fbec198c1b982487eb259b3ca8e250ebb3` |
| `docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.md` | `this_tree` | `9c360a19a8e3` | `a34e7dd664bdfe61efc32024b910057007262a6a` | `a338f09d0cf0cc87879c6547b8058740bcf085c6f1e59bab9148f6825eae79bc` |
| `docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.json` | `this_tree` | `9c360a19a8e3` | `f6d3b3fa711a41f9e007334b12d6db6926566ba8` | `32b9157f9e4ce285627030218c0b9e37bed1347e6d4a30e2bd8e8ca87d46976e` |
| `docs/EDGE_RESEARCH_PROTOCOL.md` | `pre_registry_head_governance` | `9c360a19a8e3` | `5a2590a72fbe93ef6afd3f1dff669afcc1007210` | `10c39bf1f685e09fef2b68fd866ddc2635a2d9e9e2caa10b6237a4e11218e3b8` |
| `docs/ACTIVE_RESEARCH_RISKS.md` | `pre_registry_head_governance` | `9c360a19a8e3` | `8a4ed9399e2d2df6250a5d5f5f6f7dd154ccb96f` | `819c5924e3eb0d05b5130b9b5753f8c8436d37b166ff0cb89327c68a86505ca6` |
| `docs/RESEARCH_LEDGER.md` | `pre_registry_head_governance` | `9c360a19a8e3` | `c3a19f6c8a8708f1d23f420e5aa701a856e54f80` | `5c9630c67ef6d35d2a6630deed42518b68fc57bd40f6cc419886764170d4563f` |
| `docs/PROJECT_STATUS.md` | `pre_registry_head_governance` | `9c360a19a8e3` | `a497e861a759f9f37e6ab6c3d7cb894c133159b2` | `222dba0e0fbd99b1450e9efdaf0c846c6e4c24265c1ad013a13b63a770ee1b02` |
| `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md` | `unmerged_pr_157` | `70f9489bd4fe` | `11d1b5867d3673412fb5f539131503bb2d9e3efd` | `4f19fd27435adddf4cc7e3c5568a8e316d8865b64468cdc30a9fd3918ffc3275` |
| `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json` | `unmerged_pr_157` | `70f9489bd4fe` | `f837e12387679960ac6b2c40e919052add5b0035` | `ffc11ffd0f9d76ca12542ce45f466a6a7f9c651f1a030168a1617af2caa545a7` |
| `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.md` | `unmerged_pr_157` | `70f9489bd4fe` | `78726dfc50d0db5c7e793ca19010261ed56a324a` | `a354a78124746bd0151dc1a30b5faa61b5167607afaa8db3e95f76037a639897` |
| `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.json` | `unmerged_pr_157` | `70f9489bd4fe` | `5ce635dd90528cc173bbe32a05322262ebc0c4b3` | `68e084b35201d227ecd9f48e99cc65a937b15fcb55a5849b1630c5d61850b478` |

```text
MARKET_04_SELECTED = NO
NEW_HYPOTHESIS_CREATED = NO
NEW_OUTCOME_ACCESSED = NO
```

