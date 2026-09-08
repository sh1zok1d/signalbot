# Signalbot Batch02 Status Ledger

**Ledger type:** post-outcome status record  
**Frozen inventory source:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Inventory mutability:** IMMUTABLE after first real Batch02 outcome  
**Current Batch02 outcome count:** 4 completed result documents; B2-05 development consumed and durable-evidence recovery archived
**2025 validation:** UNTOUCHED  
**2026 OOS:** UNTOUCHED

## 1. Purpose

This ledger records deterministic status transitions after real Batch02 outcome
reads without editing the frozen `V2_FORMULATION_INVENTORY`.

It is not an admission surface. It cannot add a new formulation, threshold,
state, filter, cluster, child, or mechanism to current V2.

The authoritative formulation set remains the already-frozen six-entry inventory.

## 2. Formulation ledger

| Formulation | Primary family | Status | Evidence state |
|---|---|---|---|
| `B2-01_VOLATILITY_TRANSITION` | F3 | `CLOSED_NO_PROMOTION` | completed development verdict; see `B2_01_VOLATILITY_TRANSITION_RESULT.md` |
| `B2-02_BOUNDARY_INTERACTION_PATH` | F1 | `CLOSED_NO_PROMOTION` | completed one-shot development verdict; see `B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md` |
| `B2-03_IMPULSE_MORPHOLOGY` | F1 | `CLOSED_NO_PROMOTION` | completed one-shot development verdict; see `B2_03_IMPULSE_MORPHOLOGY_RESULT.md` |
| `B2-04_MODERATE_PULLBACK_STRUCTURE` | F1 | `CLOSED_NO_PROMOTION` | completed one-shot development verdict; explicit H04 post-hoc child; see `B2_04_MODERATE_PULLBACK_STRUCTURE_RESULT.md` |
| `B2-05_FLOW_ABSORPTION` | F4 | `DEVELOPMENT_CONSUMED` | durable evidence `ARCHIVED` (`B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED`); historical bytes not cryptographically proven; no RESULT.md in this closeout |
| `B2-06_LEVERAGE_CROWDING` | F5 | `BLOCKED_MISSING_OBSERVABLE` | OI + funding data-expansion **identity** frozen; unit verdict `DATA_CONTRACT_FROZEN_AWAITING_MATERIALIZATION_AND_FUNDING_AVAILABILITY_AUTHORITY`; funding publication latency unproven; snapshot not materialized; no B2-06 RESULT |

## 3. Family ledger

| Family | Status | Reason |
|---|---|---|
| F1 Directional persistence | `CLOSED_NO_PROMOTION` | B2-02, B2-03, and the sole B2-04 H04-derived child all closed without promotion |
| F2 Reversion/failure | `RETIRED` | no novelty-qualified F2 formulation exists in frozen inventory |
| F3 Volatility dynamics | `CLOSED_NO_PROMOTION` | sole frozen F3 formulation B2-01 closed without promotion |
| F4 Participation/order-flow | `DEVELOPMENT_CONSUMED` | B2-05 one-shot consumed; durable recovery archived; scientific RESULT.md is not this closeout |
| F5 State-mechanism interaction | `BLOCKED_MISSING_OBSERVABLE` | B2-06 identity frozen outcome-blind; snapshot not materialized; no outcome access |
| F6 State routing | `RETIRED` | no current-V2 routing formulation admitted |

## 4. Canonical state after B2-05 durable-evidence recovery

```text
BATCH01 = CLOSED
V2_RESEARCH_HARNESS_V1 = ACCEPTED
V2_RESEARCH_PROGRAM = CHARTER_ACCEPTED
V2_FORMULATION_INVENTORY = FROZEN_6_IMMUTABLE

REAL_BATCH02_OUTCOMES = OPENED_B2_01_AND_B2_02_AND_B2_03_AND_B2_04_AND_B2_05

B2_01 = CLOSED_NO_PROMOTION
B2_02 = CLOSED_NO_PROMOTION
B2_03 = CLOSED_NO_PROMOTION
B2_04 = CLOSED_NO_PROMOTION
B2_04_POSTHOC_PROVENANCE = H04_EXPLICIT_CHILD
B2_04_H04_CHILD_PATH = CLOSED
B2_05 = DEVELOPMENT_CONSUMED
B2_05_RECOVERY = B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED
B2_05_EVIDENCE = ARCHIVED
B2_06 = BLOCKED_MISSING_OBSERVABLE
B2_06_DATA_EXPANSION = DATA_EXPANSION_FEASIBLE_TO_FREEZE
B2_06_DATA_EXPANSION_UNIT_VERDICT = DATA_CONTRACT_FROZEN_AWAITING_MATERIALIZATION_AND_FUNDING_AVAILABILITY_AUTHORITY
B2_06_FUNDING_PUBLICATION = FUNDING_PUBLICATION_LATENCY_UNPROVEN
B2_06_DATASET = B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0
B2_06_DATASET_STATUS = CONTRACT_FROZEN_NOT_MATERIALIZED
B2_06_OUTCOME_ACCESS = NO

F1 = CLOSED_NO_PROMOTION
F2 = RETIRED
F3 = CLOSED_NO_PROMOTION
F4 = DEVELOPMENT_CONSUMED
F5 = BLOCKED_MISSING_OBSERVABLE
F6 = RETIRED

NEXT_FROZEN_FORMULATION = B2_06_LEVERAGE_CROWDING
NEXT_FROZEN_FORMULATION_STATUS = BLOCKED_MISSING_OBSERVABLE

2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```

## 5. B2-01 terminal record

```text
FORMULATION = B2-01_VOLATILITY_TRANSITION
VERDICT = B2_01_CLOSED_NO_PROMOTION
FORMULATION_STATUS = CLOSED_NO_PROMOTION
FAMILY = F3
FAMILY_STATUS = CLOSED_NO_PROMOTION
RESULT_ARTIFACT_SHA256 = 3fa3ad61752d4d7d56d1dbfa172af95bec7712aebe5d2e2edfccb725971d4d2a
IMPLEMENTATION_SHA = 1a0709526d6fd4bf4799bf218dba53d2d33e5bb8
PREREG_SHA256 = 7fe105549d756a74fd9360449e7b464bf53f51560705ba1010d127ac943838fb
RERUN_AUTHORIZED = NO
REFORMULATION_CURRENT_V2 = NO
```

## 6. B2-02 terminal record

```text
FORMULATION = B2-02_BOUNDARY_INTERACTION_PATH
VERDICT = B2_02_CLOSED_NO_PROMOTION
FORMULATION_STATUS = CLOSED_NO_PROMOTION
FAMILY = F1
FAMILY_STATUS_AT_CLOSEOUT = ACTIVE
RESULT_ARTIFACT_SHA256 = b5bc240bc30cff92e26b1cf5a7fca4e546c70c80b7f60d113f73f580b439e971
RESULT_ARTIFACT_DURABLE_COPY = UNAVAILABLE
RESULT_ARTIFACT_RETENTION_STATUS = POST_RUN_EVIDENCE_RETENTION_GAP
EXECUTION_SHA = a976a3fa3143f7290851ab8b2ddc5a9d811c891a
REVIEWED_IMPLEMENTATION_SHA = 37051de39f49b5b331a0ddbc3b37f8316811f9ef
EXECUTION_TREE = f220590be0a6323df29b8e35b47399d42c3ea137
PREREG_MERGE_SHA = cbf447276c1dc47c9a755038cfd6013199207eef
DATASET_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
RERUN_AUTHORIZED = NO
REFORMULATION_CURRENT_V2 = NO
```

## 7. Anti-rescue rule

Completed B2-01 through B2-04 outcomes do not authorize post-outcome rescue
inside current V2.

For B2-01 this includes another transition threshold, W/D/H grid, sign,
volatility normalization, target, loss, support minimum, nearby substitute, or
best-looking failed-cell child.

For B2-02 this includes another breach threshold, L/H grid, path window,
context/path-state cutpoint, target scaling rule, training-history length,
support minimum, placebo mapping, bootstrap rule, sign reversal, or child based
on an attractive failed cell.

For B2-03 this includes another morphology component or weighting, W/H grid,
sign reversal of `MORPHOLOGY_SEPARATION`, exhaustion reinterpretation,
one-sided UP/DOWN rescue, or child based on an isolated `morphology_ordering`
pass.

For B2-04 this includes another moderate-depth threshold, trend indicator,
recovery descriptor, recovery-state transform, horizon/L grid, reverse-sign
interpretation, one-sided direction rescue, or any second H04-derived child.

Any such idea conceived after these outcomes remains future-program material
only and cannot enter current V2.

B2-05 durable-evidence recovery does not authorize a scientific rerun, does
not reopen CORE / 2025 / 2026, and does not convert operator adjudication
into historical byte-proof.

## 8. B2-03 terminal record

```text
FORMULATION = B2-03_IMPULSE_MORPHOLOGY
VERDICT = B2_03_CLOSED_NO_PROMOTION
FORMULATION_STATUS = CLOSED_NO_PROMOTION
FAMILY = F1
FAMILY_STATUS_AT_CLOSEOUT = ACTIVE
RESULT_ARTIFACT_SHA256 = a3586344ac9c094eb38670a16b7566b8c1628300b6a1f6605fd69c369894b0c0
ARTIFACT_SIZE_BYTES = 68487026
EVIDENCE_REF = refs/heads/research-evidence/batch02/B2-03/8a7490167e086a201ec7b3780878d2cf3252ecfd
RESERVED_SHA = 5dec8d075e5e35db3946fef4e0b530fd719cc7d3
CLAIMED_SHA = 7a7adf1e4236286d8c69bb67efd51271ffc5473e
ARCHIVED_SHA = 16854498afc34c69f62e46a387ef08e7896a5172
EXECUTION_SHA = 8a7490167e086a201ec7b3780878d2cf3252ecfd
EXECUTION_TREE = b83f4f5dfa82da6d9ab219829bbcccd214d2f11a
PREREG_MERGE_SHA = 61bc9cfde80c6a142ac147ebee6487a1ae710324
DATASET_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
SCIENTIFIC_DEVELOPMENT_EXECUTIONS = 1
PRE_CLAIM_OPERATIONAL_ABORT = YES
RERUN_AUTHORIZED = NO
REFORMULATION_CURRENT_V2 = NO
```

## 9. B2-04 terminal record

```text
FORMULATION = B2-04_MODERATE_PULLBACK_STRUCTURE
VERDICT = B2_04_CLOSED_NO_PROMOTION
FORMULATION_STATUS = CLOSED_NO_PROMOTION
FAMILY = F1
FAMILY_STATUS = CLOSED_NO_PROMOTION
H04_DERIVED_CHILD_PATH = CLOSED
RESULT_ARTIFACT_SHA256 = 2e7c84cda547e8de25c7ab7f2f95beac26655b632d2ba202e4490e51c54fd4e3
ARTIFACT_SIZE_BYTES = 3152434
EVIDENCE_REF = refs/heads/research-evidence/batch02/B2-04/9c2ed3ca7fab24dca832065cf4bed9a5c860a362
RESERVED_SHA = f5a63e0b6c169bf2868e5d40357906b85e9ddbcd
CLAIMED_SHA = 557f0df8be0ccfed712d30343b2e83be9cece4bd
ARCHIVED_SHA = a75838482a8472148d6686c4864189c99ca2f19e
EXECUTION_SHA = 9c2ed3ca7fab24dca832065cf4bed9a5c860a362
EXECUTION_TREE = cc4c3691e522b4f83681ce069d4dc40a7b15d0a6
PREREG_MERGE_SHA = bcc00d4a6180105991fd4828b7cfc7983c9c9ccf
DATASET_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
POST_REFRACTORY_EVENTS = 5100
SCIENTIFIC_DEVELOPMENT_EXECUTIONS = 1
RERUN_AUTHORIZED = NO
REFORMULATION_CURRENT_V2 = NO
```

B2-04 was the final current-V2 F1 formulation. With B2-02, B2-03, and B2-04
all closed without promotion, F1 directional persistence closes for current V2.

## 10. Next allowed research unit

B2-05 development is consumed. Its durable-evidence recovery incident is
closed as `B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED`. This ledger does
not transcribe a scientific RESULT.md and does not authorize a B2-05 rerun.

The next frozen inventory unit is:

`B2-06_LEVERAGE_CROWDING`

It remains `BLOCKED_MISSING_OBSERVABLE` for scientific execution. The
required OI/funding **data-expansion identity** is frozen outcome-blind as
`DATA_EXPANSION_FEASIBLE_TO_FREEZE` in
`docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md` with dataset
`B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` still
`CONTRACT_FROZEN_NOT_MATERIALIZED` and unit verdict
`DATA_CONTRACT_FROZEN_AWAITING_MATERIALIZATION_AND_FUNDING_AVAILABILITY_AUTHORITY`.
Funding `calc_time` is not a proven legal availability clock. Next allowed
work is materialization, Git-bound snapshot authorization, and a separately
frozen first-party funding publication rule — not B2-06 outcome access, not
2025, not 2026, and not crowding-threshold search.

## 11. Validation boundary

No 2025 validation or 2026 OOS outcome has been opened by Batch02 so far.

B2-01, B2-02, B2-03, and B2-04 are closed at development and have no promoted
candidate, therefore none has a validation path to open. B2-05 development is
consumed and its durable archive is operator-adjudicated; this closeout does
not open 2025 or 2026 and does not transcribe a scientific RESULT.md.

## 12. B2-05 durable-evidence recovery terminal record

This record closes the B2-05 post-outcome retention incident. It does not
relabel the recovered bytes as historically cryptographically proven, and it
does not claim the original failed process had already durably persisted
these exact bytes. Scientific RESULT.md transcription is not this closeout.

```text
FORMULATION = B2-05_FLOW_ABSORPTION
TERMINAL_STATUS = B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED
B2_05_RECOVERY_STATUS = ARCHIVED
EVIDENCE_REF = refs/heads/research-evidence/batch02/B2-05/669ae93c6a5c1d102a46fd129f04292f1beff978
ARCHIVED_SHA = e31e5666fe845116197b6f2531289bf17d848027
CLAIMED_SHA = e6590062b3dba06b716199552b74f9c68b14f4b2
RESERVED_SHA = 40cd095122b32d0f5fdb731fa429901d546777e3
ARCHIVE_PARENT = e6590062b3dba06b716199552b74f9c68b14f4b2
RESULT_ARTIFACT_SHA256 = 530342759e70a135915ef82382b4b97bd939620ce02925524b745ccf6cc9a57c
ARTIFACT_SIZE_BYTES = 280017092
CHUNK_COUNT = 5
ARCHIVE_REPRESENTATION = raw_chunks
RECOVERY_CODE_SHA = 3f1b42a667fe982bf399921d1c200b2b56885a28
RECOVERY_CODE_TREE = b97a31f9688c2d76176264e420de50511ea1ca6a
EXECUTION_SHA = 669ae93c6a5c1d102a46fd129f04292f1beff978
EXECUTION_TREE = 7a5c31aef771e4bbdeb686045ae154d33e7c8fd4
HISTORICAL_ARTIFACT_BINDING = OPERATOR_ADJUDICATED
HISTORICAL_EXECUTION_PERSISTENCE_PROVEN = false
RECOVERY_PROVES = artifact_equals_authority_committed_during_recovery
PRODUCTION_RECOVERY_INVOCATION_COUNT = 1
B2_05_RERUN = NO
CORE_REOPENED = NO
FORCE_PUSH = NO
AUTOMATIC_RETRY = NO
LOCAL_ARTIFACT_UNCHANGED_AFTER_RECOVERY = YES
EVIDENCE_REF_POINTS_AT_EXACT_ARCHIVE = YES
RERUN_AUTHORIZED = NO
```
