# Signalbot Documentation Index

**Status:** ACTIVE / CANONICAL INDEX

This index exists to stop historical implementation documents from being mistaken for the current project plan **without erasing the history that explains how Signalbot evolved**.

The repository intentionally has two visible layers:

1. **current truth** — what the project is doing now;
2. **historical trail** — what it previously believed/built, what evidence changed that belief, and why the direction changed.

For the narrative evolution, read `PROJECT_HISTORY.md`. For complete original documents from earlier phases, use `history/README.md`.

---

## 1. Current sources of truth

Read these first:

| Document | Status | Purpose |
|---|---|---|
| `PROJECT_STATUS.md` | **ACTIVE / CANONICAL** | Current project posture, freeze, empirical state and restart gate. Active research phase: `MARKET` / `INFORMATION_SET_EXPANSION`. MARKET-05 closed `NO_EVIDENCE`. V3 Microscope calibration closed. |
| `RESEARCH_ROADMAP.md` | **ACTIVE / CANONICAL** | Active execution order. Same-information-set hypothesis generation paused; next phase `INFORMATION_SET_EXPANSION`; MARKET-04 blocked/not tested; V3 closed; no V4; B2-06 remains blocked. |
| `EDGE_RESEARCH_PROTOCOL.md` | **ACTIVE / CANONICAL** | Discovery/validation rules and anti-overfit discipline |
| `HISTORICAL_DATA_STRATEGY.md` | **ACTIVE / CANONICAL** | Multi-year CORE vs shorter RICH evidence strategy |
| `DATA_CAPABILITY_MATRIX.md` | **ACTIVE / RESEARCH DATA DESIGN** | Verified source/venue/date/granularity map and acquisition order for the 2020/2021–2026 research program |
| `CORE_BTC_BINANCE_V0_PROBE_RUNBOOK.md` | **ACTIVE / RESEARCH INFRASTRUCTURE** | How to run the small deterministic `CORE_BTC_BINANCE_V0` source-capability probe; why `SOURCE_PROBE_PASSED` != `DATASET_ACCEPTED` |
| `CORE_BTC_BINANCE_V0_MATERIALIZATION_RUNBOOK.md` | **ACTIVE / RESEARCH INFRASTRUCTURE** | How the CORE BTC Binance materializer pipeline is staged; CLI finalize is not dataset acceptance |
| `manifests/CORE_BTC_BINANCE_V0.yaml` | **ACCEPTED_FOR_DISCOVERY** | Canonical CORE BTC Binance V0 dataset manifest |
| `research_data/CORE_BTC_BINANCE_V0/` | **FROZEN_EVIDENCE** | Accepted snapshot `717d37a4` identity, source inventory, and quality report |
| `research/H01_COMPRESSION_EXPANSION_PREREG.md` | **FROZEN_EVIDENCE** | H01 preregistration (before development outcomes) |
| `research/H01_DEV_SUMMARY.md` | **FROZEN_EVIDENCE** | H01 development-only result; verdict `H01_KILL` |
| `research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.md` | **FROZEN_EVIDENCE** | H02 preregistration (before development outcomes) |
| `research/H02_DEV_SUMMARY.md` | **FROZEN_EVIDENCE** | H02 development-only result; verdict `H02_KILL` |
| `research/EVIDENCE_REGISTRY_H_B_M01_M05.md` | **CURRENT PROGRAM EVIDENCE REGISTRY** | 16 scientific units: H01–H05, B2-01–B2-06, MARKET-01–05. MARKET-04H nested under MARKET-04. MARKET-06 not created. |
| `research/EVIDENCE_REGISTRY_H_B_M01_M05.json` | **CURRENT PROGRAM EVIDENCE REGISTRY twin** | Machine-readable semantic twin; prior H/B/M01–M03 unit objects copied verbatim |
| `research/EVIDENCE_REGISTRY_H_B_M01_M03.md` | **FROZEN HISTORICAL SNAPSHOT / SUPERSEDED AS CURRENT AUTHORITY** | Immutable 14-unit synthesis of H01–H05, B2-01–B2-06, MARKET-01–03. Bytes unchanged. Current authority is `EVIDENCE_REGISTRY_H_B_M01_M05`. |
| `research/EVIDENCE_REGISTRY_H_B_M01_M03.json` | **FROZEN HISTORICAL SNAPSHOT twin** | Machine-readable twin of the 14-unit historical snapshot; SHA256 `0892f66d…` |
| `research/MARKET_05_PROGRAM_INTERPRETATION.md` | **PROGRAM CLOSEOUT / NOT A NEW EXPERIMENT** | Binds MARKET-05 RESULT `828c6916…` / `MARKET_05_NO_EVIDENCE`; pauses same-information-set generation; next phase `INFORMATION_SET_EXPANSION` |
| `research/MARKET_05_PROGRAM_INTERPRETATION.json` | **PROGRAM CLOSEOUT twin** | Machine-readable twin; `market_06_created=false`; `scientific_outcomes_inspected_during_update=false` |
| `research/FORWARD_MARKET_OBSERVABILITY_V1.md` | **DESIGN / IMPLEMENTED_FROZEN** | Forward funding/premium/leverage collection design; `legal_available_at=local_received_at_utc`; not a hypothesis test |
| `research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_CONTRACT.json` | **IMPLEMENTED_FROZEN contract** | Machine-readable collector contract; `authoritative_collection_started=false`; `computes_scientific_outcomes=false` |
| `research/FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION.md` | **IMPLEMENTATION / NOT AUTHORITATIVE COLLECTION** | Binance USD-M BTCUSDT acquisition package; CLI `smoke` / refused `collect` |
| `research/FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.md` | **IMPLEMENTATION_FROZEN / CURRENT COLLECTOR FREEZE AUTHORITY** | Freeze of collector SHA256 map + schema identities; not collection start; not M04-FWD |
| `research/FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.json` | **IMPLEMENTATION_FROZEN twin** | `collector_head`/`tree` `UNSET_UNTIL_THIS_COMMIT`; `authoritative_collection_start_utc=null` |
| `research/FORWARD_MARKET_OBSERVABILITY_V1_CONFIG.json` | **COLLECTOR CONFIG IDENTITY** | BTCUSDT USD-M sources; OI separately timestamped; not scientific evidence |
| `research/FORWARD_MARKET_OBSERVABILITY_V1_SCHEMAS.json` | **COLLECTOR SCHEMA IDENTITY** | Raw envelope / chunk / manifest schema ids; legal_available_at rule |
| `scripts/research/forward_market_observability_v1/` | **IMPLEMENTATION_FROZEN collector** | Hypothesis-neutral acquisition; raw append-only evidence; no scientific outcomes |
| `research/MARKET_04_CANDIDATE_SELECTION.md` | **CANDIDATE IDENTITY FROZEN / NOT PREREGISTERED / NOT AUTHORIZED** | Outcome-blind MARKET-04 identity `MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK`; role `RISK_STATE_FILTER`; funding availability later audited as still unresolved; no ARM/RESULT |
| `research/MARKET_04_CANDIDATE_SELECTION.json` | **CANDIDATE IDENTITY FROZEN twin** | Machine-readable twin; `execution_authorized=false`; `independent_replication_of_market_03=false` |
| `research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.md` | **TEMPORAL AUTHORITY / UNRESOLVED** | Outcome-blind first-party audit of Binance settled-funding publication; `FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED`; `legal_available_at` unset; does not ARM/execute MARKET-04 or B2-06 |
| `research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.json` | **TEMPORAL AUTHORITY twin** | Machine-readable twin; `historical_availability_proven=false`; `B2_06_FUNDING_BLOCKER_IMPLICATION=UNCHANGED` |
| `research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.md` | **CHILD DESIGN / BLOCKED** | Outcome-blind MARKET-04H Premium Index funding-pressure-proxy adjudication; `MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED`; archive-day timezone unresolved; no ARM/RESULT |
| `research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.json` | **CHILD DESIGN twin** | Machine-readable twin; `safe_usable_at_proven=false`; `settled_funding_claimed=false`; `execution_authorized=false` |
| `research/MARKET_05_CROSS_ASSET_CANDIDATE.md` | **CANDIDATE IDENTITY FROZEN / NOT PREREGISTERED / NOT AUTHORIZED** | Outcome-blind MARKET-05 identity `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`; BTC target / ETH context; continuous `ETH_CONFIRMATION_STATE`; no ARM/RESULT/prereg |
| `research/MARKET_05_CROSS_ASSET_CANDIDATE.json` | **CANDIDATE IDENTITY FROZEN twin** | Machine-readable twin; `execution_authorized=false`; `simple_direction_predictor=false`; `market_04_rescue=false` |
| `research/MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.md` | **OUTCOME_BLIND_FEASIBILITY / FEASIBLE** | BTC/ETH same-exchange temporal feasibility; `MARKET_05_CANDIDATE_FROZEN_DATA_FEASIBLE`; CORE BTC retained; CORE ETH inventory-bound only |
| `research/MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.json` | **OUTCOME_BLIND_FEASIBILITY twin** | Machine-readable twin; `common_decision_timestamps_feasible=true`; `protected_oos_touched=false` |
| `research/MARKET_05_CROSS_ASSET_PREREG.md` | **FROZEN_OUTCOME_BLIND preregistration** | Exact MARKET-05 formulation; daily 00:00 UTC; 24h/24h; continuous ETH confirmation; not ARM/execution |
| `research/MARKET_05_CROSS_ASSET_PREREG.json` | **FROZEN_OUTCOME_BLIND prereg twin** | Machine-readable twin; `FULL_PREREGISTRATION_FROZEN=true`; `MARKET_05_TEST_CALIBRATED=NO`; `execution_authorized=false` |
| `research/MARKET_05_IMPLEMENTATION_FREEZE.md` | **IMPLEMENTATION_FROZEN / HISTORICAL** | Original MARKET-05 evaluator freeze at `0016e4fc…`; superseded as current authority by the final pre-ARM freeze |
| `research/MARKET_05_IMPLEMENTATION_FREEZE.json` | **IMPLEMENTATION_FROZEN twin / HISTORICAL** | Machine-readable twin of the original freeze; `is_current_authority=false` |
| `research/MARKET_05_IMPLEMENTATION_REFREEZE.md` | **IMPLEMENTATION_REFROZEN / HISTORICAL** | Lifecycle-gate repair freeze at `46a7f6e0…`; superseded as current authority by the final pre-ARM freeze |
| `research/MARKET_05_IMPLEMENTATION_REFREEZE.json` | **IMPLEMENTATION_REFROZEN twin / HISTORICAL** | Machine-readable twin; `is_current_authority=false`; `superseded_by` final pre-ARM freeze |
| `research/MARKET_05_ARM_CONTRACT.md` | **DOCUMENTARY MIRROR / NOT RUNTIME AUTHORITY** | Prior ARM-contract text; not an ARM; hash maps describe `46a7f6e0…` and are not runtime-enforced |
| `research/MARKET_05_ARM_CONTRACT.json` | **DOCUMENTARY MIRROR twin** | `authority_role=DOCUMENTARY_MIRROR_OF_PRIOR_FREEZE`; `executable_authority=false` |
| `research/MARKET_05_ARM_SEMANTIC_CONTRACT.json` | **EXECUTABLE SEMANTIC CONTRACT** | Non-self-referential ARM semantic payload; SHA256 bound into `RUN_IDENTITY` |
| `research/MARKET_05_FINAL_PRE_ARM_FREEZE.md` | **HISTORICAL PRE-ARM EXECUTABLE FREEZE** | Claim-before-outcomes one-shot freeze; superseded as current lifecycle by ARM/RESULT; still valid historical freeze authority |
| `research/MARKET_05_FINAL_PRE_ARM_FREEZE.json` | **HISTORICAL PRE-ARM EXECUTABLE FREEZE twin** | `MARKET_05_FINAL_PRE_ARM_IMPLEMENTATION_FROZEN`; ARM/RESULT now exist |
| `research/MARKET_05_ARM.md` | **EXECUTED / CONSUMED** | One-shot canonical ARM; consumed by RESULT HEAD `828c6916…` |
| `research/MARKET_05_ARM.json` | **EXECUTED / CONSUMED twin** | ARM SHA256 `a7688057…`; `RUN_IDENTITY` `6957613d…` |
| `research/MARKET_05_RESERVATION.json` | **CONSUMED** | Canonical execution reservation; SHA256 `ad0cc648…` |
| `research/MARKET_05_RESULT.json` | **CANONICAL RESULT** | Sealed MARKET-05 RESULT; SHA256 `80a29335…`; `classification=MARKET_05_NO_EVIDENCE` |
| `research/MARKET_05_RESULT.md` | **CANONICAL RESULT** | Mechanical restatement of the sealed RESULT; not a stronger claim |
| `research/MARKET_05_EXECUTION_CLAIM.json` | **CONSUMED EXECUTION CLAIM** | One-shot O_EXCL claim; RESULT binds pre-status-stamp SHA `95094a5a…` |
| `research_data/CORE_ETH_BINANCE_V0/MARKET_05_EXECUTION_BINDING.json` | **ETH EXECUTION-DATA BINDING** | 2020-01..2024-12 parquet SHA256s bound to accepted ZIP SHA256s; `ETH_EXECUTION_DATA_ID` |
| `manifests/CORE_ETH_BINANCE_V0.yaml` | **ACCEPTED_FOR_DISCOVERY** | ETH companion to `CORE_BTC_BINANCE_V0`; snapshot `4b9c113f…`; does not redefine CORE BTC; not ARM/execution |
| `research_data/CORE_ETH_BINANCE_V0/` | **ACCEPTED COMPANION IDENTITY** | Vision ETHUSDT 1m inventory + accepted snapshot identity; no scientific MARKET-05 outcomes |
| `research/BATCH02_STATUS_LEDGER.md` | **ACTIVE RECORD** | Post-outcome Batch02 formulation/family status, including B2-05 durable-evidence recovery closeout `B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED` at archive `e31e5666fe845116197b6f2531289bf17d848027`; B2-06 remains `BLOCKED_MISSING_OBSERVABLE` after an outcome-blind OI/funding snapshot bind that does not authorize execution; does not mutate the frozen inventory |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_DATA_FEASIBILITY.md` | **OUTCOME_BLIND_FEASIBILITY** | MARKET-01 price/OI inventory only; `MARKET_01_PREREG_FEASIBLE = YES`; no outcomes, no B2-06 execution |
| `research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.md` | **OUTCOME_BLIND_SOURCE_FEASIBILITY / HISTORICAL UNIT** | MARKET-03 external EmaCross/EmaCrossFunding capture; unit verdict `DATA_ACQUISITION_REQUIRED`; superseded for current execution by later MARKET-03 units; not a prereg/ARM/RESULT |
| `research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.json` | **OUTCOME_BLIND_SOURCE_FEASIBILITY twin / HISTORICAL UNIT** | Machine-readable twin; pinned commit `b68a5518…`; no Signalbot strategy outcomes |
| `research/MARKET_03_DATA_ACQUISITION.md` | **DATA_ACQUISITION_COMPLETE_NOT_PREREGISTERED / HISTORICAL UNIT** | Binance SPOT BTCUSDT 1h snapshot + funding provenance; unit verdict `READY_FOR_MARKET_03_PREREG_DESIGN`; superseded for current execution by the prereg-design unit; not a prereg/ARM/RESULT |
| `research/MARKET_03_DATA_ACQUISITION.json` | **DATA_ACQUISITION twin / HISTORICAL UNIT** | Machine-readable twin; snapshot `2ce1f504…`; SHA256 `f1dfd27c…`; all strategy/prereg/ARM flags false |
| `research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.md` | **PREREG_DESIGN_COMPLETE / HISTORICAL UNIT** | MARKET-03 scientific identity/classification before execution; unit verdict `READY_FOR_MARKET_03_PREREG`; superseded for current execution by the frozen prereg |
| `research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.json` | **PREREG DESIGN twin / HISTORICAL UNIT** | Machine-readable twin; SHA256 `91e36249…`; directional primary classification; truncated authorized interval |
| `research/MARKET_03_PUBLIC_STRATEGY_PREREG.md` | **FROZEN_OUTCOME_BLIND payload** | Frozen MARKET-03 preregistration bytes; SHA256 `044bb2a6…`; internal status `PREREGISTERED_OUTCOME_BLIND` left unchanged; freeze authority is the freeze document |
| `research/MARKET_03_PUBLIC_STRATEGY_PREREG.json` | **FROZEN_OUTCOME_BLIND payload** | Frozen machine-readable twin; SHA256 `3f35f9a1…` |
| `research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.md` | **FROZEN_OUTCOME_BLIND / CURRENT FREEZE AUTHORITY** | Docs-only freeze of materialization `06d6ec01…` / tree `50bc810e…`; not an ARM; not execution |
| `research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.json` | **FROZEN_OUTCOME_BLIND / CURRENT FREEZE AUTHORITY** | Machine-readable twin; `freeze_commit_head`/`tree` intentionally `UNSET_UNTIL_THIS_COMMIT` |
| `research/MARKET_03_FUNDING_SNAPSHOT.md` | **FUNDING_SNAPSHOT_READY / CURRENT FUNDING AUTHORITY** | Dedicated REST funding snapshot wrap; snapshot `d47b7b78…`; not ARM/execution |
| `research/MARKET_03_FUNDING_SNAPSHOT.json` | **FUNDING_SNAPSHOT_READY twin** | Machine-readable twin; SHA256 `870dd397…`; source `e7885cd5…`; all strategy/ARM flags false |
| `research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.md` | **HISTORICAL IMPLEMENTATION UNIT** | Implementation-unit identity after F1/F2/F3/F5 repair; live freeze authority is the implementation-freeze document |
| `research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.json` | **HISTORICAL IMPLEMENTATION UNIT twin** | Machine-readable twin; repaired scientific file SHA256s; `EXACT_DIFFERENTIAL_TESTS=PARTIAL` |
| `research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_REPAIR.md` | **REPAIR_COMPLETE_NOT_FROZEN / HISTORICAL UNIT** | Outcome-blind F1/F2/F3/F5 repair record vs review HEAD `cada1bef…`; not ARM/execution |
| `research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_REPAIR.json` | **REPAIR_COMPLETE_NOT_FROZEN twin / HISTORICAL UNIT** | Machine-readable twin of the implementation repair |
| `research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.md` | **IMPLEMENTATION_FROZEN / CURRENT IMPLEMENTATION FREEZE AUTHORITY** | Docs-only freeze of reviewed HEAD `03411aaa…` / tree `87a1da25…`; not ARM; not execution |
| `research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.json` | **IMPLEMENTATION_FROZEN twin / CURRENT IMPLEMENTATION FREEZE AUTHORITY** | Machine-readable twin; `freeze_commit_head`/`tree` intentionally `UNSET_UNTIL_THIS_COMMIT` |
| `research/MARKET_03_PUBLIC_STRATEGY_ARM.md` | **EXECUTED / CONSUMED** | One-shot canonical ARM; consumed `1`; unused SHA256 `7c801cdc…` bound into RESULT |
| `research/MARKET_03_PUBLIC_STRATEGY_ARM.json` | **EXECUTED / CONSUMED twin** | Consumed ARM twin; unused identity `7c801cdc…`; run identity `f68b6de7…` |
| `research/MARKET_03_PUBLIC_STRATEGY_RESERVATION.json` | **CONSUMED** | Canonical execution reservation consumed `1`; no rerun pre-authorized |
| `research/MARKET_03_PUBLIC_STRATEGY_RESULT.md` | **CANONICAL RESULT** | Mechanical restatement; `PRIMARY_CLASSIFICATION = REPRODUCED_DIRECTION` |
| `research/MARKET_03_PUBLIC_STRATEGY_RESULT.json` | **CANONICAL RESULT** | Sealed MARKET-03 RESULT; SHA256 `32b9157f…`; unused ARM `7c801cdc…` |
| `research/MARKET_03_PUBLIC_STRATEGY_CONSUMPTION_LOCK.json` | **CONSUMED** | Pre-evaluate consumption boundary lock; not a scientific RESULT |
| `scripts/research/market_03_public_strategy_lib.py` | **IMPLEMENTATION_FROZEN** | Frozen scientific core at SHA256 `46ec2449…`; bound snapshots refused by frozen guards |
| `scripts/research/market_03_public_strategy_authority.py` | **IMPLEMENTATION_FROZEN** | Frozen identity + fail-closed guard at SHA256 `97f000c6…`; code identity remains unarmed |
| `scripts/research/market_03_public_strategy_execute.py` | **IMPLEMENTATION_FROZEN / FAIL_CLOSED** | Frozen bound-execution stub; still refuses while frozen flags stay unarmed |
| `scripts/research/market_03_public_strategy_arm_authority.py` | **ARM LIFECYCLE AUTHORITY** | RUN_IDENTITY / ARM / reservation authentication outside frozen scientific bytes |
| `scripts/research/market_03_public_strategy_canonical_execution.py` | **EXECUTED / ONE-SHOT** | Canonical execution runner; reservation consumed; not a second scientific implementation |
| `research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/` | **PINNED_EXTERNAL_SOURCE** | Immutable hashes + text snapshots of `wiktorj137/btc-strategy-lab` at `b68a5518…` |
| `research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/` | **RESEARCH INFRASTRUCTURE SNAPSHOT** | SPOT 1h identity `2ce1f504…`; not MARKET-03 scientifically bound; raw bytes gitignored |
| `manifests/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0.yaml` | **SNAPSHOT_MATERIALIZED_RESEARCH_INFRASTRUCTURE** | Planning/identity manifest; `research_authorized: false`; `market_03_scientifically_bound: false` |
| `research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0/` | **DEDICATED FUNDING SNAPSHOT** | REST funding identity `d47b7b78…`; source SHA256 `e7885cd5…`; not B2-06; raw bytes gitignored |
| `manifests/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0.yaml` | **SNAPSHOT_MATERIALIZED_PRE_ARM** | Funding identity manifest; `research_authorized: false`; `market_03_arm_bound: false` |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md` | **FROZEN_OUTCOME_BLIND payload** | Frozen MARKET-01 preregistration bytes; SHA256 `d82b60e1…`; internal materialization-unit status string left unchanged; freeze authority is the freeze document |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json` | **FROZEN_OUTCOME_BLIND payload** | Frozen machine-readable twin; SHA256 `6885abaf…` |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md` | **FROZEN_OUTCOME_BLIND / CURRENT FREEZE AUTHORITY** | Docs-only freeze of materialization `9c1a661c…` / tree `1928969e…`; SHA256 `e0e0da9e…`; not an ARM; not execution |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json` | **FROZEN_OUTCOME_BLIND / CURRENT FREEZE AUTHORITY** | Machine-readable twin; SHA256 `90286387…`; `freeze_commit_head`/`tree` intentionally `UNSET_UNTIL_THIS_COMMIT` |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION.md` | **HISTORICAL IMPLEMENTATION UNIT** | Implementation-unit identity; live freeze/ARM authority is the implementation-freeze and ARM documents |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION_FREEZE.md` | **IMPLEMENTATION_FROZEN** | Accepted implementation HEAD `1019c57` / tree `2a7a5ce`; not execution |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION_FREEZE.json` | **IMPLEMENTATION_FROZEN** | Machine-readable twin; SHA256 `a057260f…`; freeze_commit_head/tree `UNSET_UNTIL_THIS_COMMIT` |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_ARM.md` | **EXECUTED / CONSUMED** | One-shot canonical ARM; consumed `1`; unused SHA256 `5b639453…` bound into RESULT |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_ARM.json` | **EXECUTED / CONSUMED** | Consumed ARM twin; unused identity `5b639453…`; run identity `f430399f…` |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESERVATION.json` | **CONSUMED** | Canonical execution reservation consumed `1`; no rerun pre-authorized |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json` | **CANONICAL RESULT** | Sealed MARKET-01 RESULT; SHA256 `5310946b…`; `FINAL_CLASSIFICATION = NO_EVIDENCE` |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.md` | **CANONICAL RESULT** | Mechanical restatement of the sealed RESULT; not a stronger claim |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_CONSUMPTION_LOCK.json` | **CONSUMED** | Pre-evaluate consumption boundary lock; not a scientific RESULT |
| `scripts/research/market_01_oi_expansion_weak_continuation_lib.py` | **EXECUTED / FROZEN** | MARKET-01 scientific pipeline; bound snapshots refuse rerun |
| `scripts/research/market_01_oi_expansion_weak_continuation_authority.py` | **EXECUTED / CONSUMED** | Prereg/freeze/ARM authentication; canonical reservation consumed |
| `scripts/research/market_01_oi_expansion_weak_continuation_canonical_execution.py` | **EXECUTED / ONE-SHOT** | Canonical execution runner; not a second scientific implementation |
| `research/MARKET_01_EPISODE_CONSTRUCTION_PERF.md` | **RESEARCH INFRASTRUCTURE / NOT SCIENTIFIC EVIDENCE** | Post-close `construct_episodes` runtime diagnosis and semantics-preserving fast path; does not rerun MARKET-01 or change RESULT/prereg |
| `scripts/research/market_01_episode_construction_fast.py` | **RESEARCH INFRASTRUCTURE** | Frozen-rule episode construction with precomputed rolling arrays; not a second MARKET-01 execution |
| `scripts/research/market_01_episode_construction_perf_bench.py` | **RESEARCH INFRASTRUCTURE** | SYNTHETIC_SNAPSHOT only; profiles/benches construction; refuses bound snapshots via the frozen guard |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_DESIGN.md` | **PREREG_DESIGN_RESOLVED / HISTORICAL_BLOCKER_RECORD** | Preserved blocked-design unit; live scientific authority is the frozen prereg |
| `research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md` | **ACTIVE / RESEARCH DATA CONTRACT** | Outcome-blind B2-06 OI+funding identity + Git-bound snapshot `5a9d036b…`; unit verdict `SNAPSHOT_MATERIALIZED_FUNDING_PUBLICATION_UNPROVEN_RESEARCH_UNAUTHORIZED`; not a B2-06 RESULT |
| `research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.json` | **ACTIVE / RESEARCH DATA CONTRACT** | Machine-readable twin of the B2-06 data-expansion freeze |
| `research/B2_06_FUNDING_PUBLICATION_AUTHORITY.md` | **ACTIVE / RESEARCH AUTHORITY** | First-party investigation of settled `last_funding_rate` public availability; verdict `FUNDING_PUBLICATION_LATENCY_UNPROVEN`; does not invent latency |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md` | **FROZEN_BEFORE_IMPLEMENTATION / V1 ATTEMPT INCOMPLETE** | Outcome-blind synthetic methodology-calibration prereg; not market evidence; does not authorize B2-06. Canonical V1 production attempt at ARM `9ab32fc` is permanently `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM` |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json` | **FROZEN_BEFORE_IMPLEMENTATION / V1 ATTEMPT INCOMPLETE** | Machine-readable twin of the synthetic calibration prereg |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.md` | **FROZEN_BEFORE_IMPLEMENTATION** | V2 methodology-only candidate identifiability policy; not rewritten in place; not an ARM; does not salvage V1 |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.json` | **FROZEN_BEFORE_IMPLEMENTATION** | Machine-readable twin of the V2 rank-degeneracy policy prereg |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.md` | **FROZEN_BEFORE_IMPLEMENTATION** | Docs-only prospective amendment closing MAJOR-1 and MINOR-1..4; not rewritten by the fixture implementation |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.json` | **FROZEN_BEFORE_IMPLEMENTATION** | Machine-readable twin of amendment 001 |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION.md` | **FIXTURE_IMPLEMENTATION_UNARMED** | Fixture-only V2 rank-policy implementation identity; not a RESULT; not an ARM |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.md` | **FROZEN_BEFORE_V2_PRODUCTION / HISTORICAL** | Historical freeze of reviewed 33/33 implementation HEAD `614295d` / tree `e754b12`; remains valid historical evidence of that implementation; not the current executable runtime freeze; not an ARM |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.json` | **FROZEN_BEFORE_V2_PRODUCTION / HISTORICAL** | Machine-readable historical 33/33 implementation freeze at `e50fcee`; SHA256 `89ca1ba0…`; still valid; not sufficient for the post-wiring production runtime |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_POST_WIRING_RUNTIME_FREEZE.md` | **FROZEN_BEFORE_V2_PRODUCTION / HISTORICAL** | Historical freeze of reviewed post-wiring runtime HEAD `c1d6acc` / tree `67f19c99`; remains valid historical evidence of that implementation; superseded as current executable runtime freeze by `baf9f23`'s authority-self-reference repair; not an ARM |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_POST_WIRING_RUNTIME_FREEZE.json` | **FROZEN_BEFORE_V2_PRODUCTION / HISTORICAL** | Machine-readable historical post-wiring runtime freeze at `75f12bd`; SHA256 `f3563cbe…`; still valid; not sufficient for the current (authority-self-reference-repaired) production runtime |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.md` | **FROZEN_BEFORE_V2_PRODUCTION / CURRENT EXECUTABLE RUNTIME** | Control-calibration freeze of reviewed implementation `8917c776` / tree `15664b6a`; plan `b0ed1553…`; historical freeze `2523b389` / ARM `18ebb4c` remain valid for plan `7fa12fd3…`; not an ARM |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json` | **FROZEN_BEFORE_V2_PRODUCTION / CURRENT EXECUTABLE RUNTIME** | Machine-readable control-calibration execution freeze; binds `8917c776` / `15664b6a`, confirmatory rank-policy `1700ada1…`, plan `b0ed1553…`, world count 3200; does not arm |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.md` | **ARMED_FOR_ONE_CANONICAL_V2_CONTROL_CALIBRATION / RESERVED** | Control-calibration ARM immediate child of freeze `bd5b5d3`; authorizes one 3200-world run against implementation `8917c776` / plan `b0ed1553…`. Historical ARM `18ebb4c` remains valid for plan `7fa12fd3…` |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json` | **ARMED_FOR_ONE_CANONICAL_V2_CONTROL_CALIBRATION / RESERVED** | Live ARM of freeze `bd5b5d3`; canonical plan `b0ed1553…`, world count 3200, rank-policy `1700ada1…` |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESERVATION.json` | **CONTROL-CALIBRATION RESERVATION / CONSUMED WINDOW** | Durable reservation `068874d8` of ARM `710cad6`; RUN_IDENTITY `90d38af4…`; one canonical attempt |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_WORLD_RECORDS.json` | **CONTROL-CALIBRATION WORLD_RECORDS / HEAD; HISTORICAL BLOB IMMUTABLE** | HEAD SHA256 `e8667f93…` / inner `f0d18ca1…` for RUN_IDENTITY `90d38af4…`. Historical SHA256 `d372eb00…` remains immutable at its minting commit |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.md` | **CONTROL-CALIBRATION VISIBILITY RECORD** | Distinguishes HEAD control-calibration visibility `ed1c17f0…` from historical `9be8dceb…`; frozen V1 `GROUND_TRUTH_VISIBLE` formula unchanged |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json` | **CONTROL-CALIBRATION VISIBILITY / HEAD; HISTORICAL BLOB IMMUTABLE** | HEAD SHA256 `ed1c17f0…` bound to WORLD_RECORDS `e8667f93…`. Historical SHA256 `9be8dceb…` remains immutable at ARM `710cad6` |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESULT.json` | **CONTROL-CALIBRATION RESULT / HEAD; HISTORICAL BLOB IMMUTABLE** | HEAD SHA256 `ffce3daa…`; FINAL `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`. Historical SHA256 `761cc9af…` remains immutable at its minting commit |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_CONFIRMATORY_POWER_REPAIR.md` | **IMPLEMENTATION_COMPLETE_AWAITING_INDEPENDENT_POWER_REPAIR_REVIEW** | Targeted V2 evaluator repair restoring frozen V1 bootstrap/placebo and `MODEL_DETECTED` power identity; does not remint or reinterpret canonical V2 RESULT |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_CONTROL_PLAN_IDENTITY_REBIND.md` | **IMPLEMENTATION_COMPLETE_AWAITING_IDENTITY_REBIND_REVIEW** | Rebinds `FROZEN_CANONICAL_V2_PLAN_SHA256` to live `canonical_v2_plan` `b0ed1553…` of the reviewed confirmatory-power repair; 3200-world job set unchanged; does not freeze, arm, or remint |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md` | **PREREG_AMENDED / FROZEN_BEFORE_V3_IMPLEMENTATION** | Materializes the accepted V3 confirmatory design/spec (Clark-West-adjusted claim-conditional estimand, full-time-axis joint stationary bootstrap, Politis-White/Patton-Politis-White automatic block length, B=999, one-sided Wilson n=400/cell, fresh `world_index 10000..10399`), amended by Amendment 001 (§16): new `V3_CONFIRMATORY` RNG-namespace primitive + `SE_hat` `ddof=1`; frozen by `V3_PREREG_FREEZE` at `543687fe`; original pre-amendment text remains valid historical evidence at freeze `4136f53d`; not an ARM; no fresh outcomes |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json` | **PREREG_AMENDED / FROZEN_BEFORE_V3_IMPLEMENTATION** | Machine-readable twin; binds every scientific constant/algorithm required by implementation, including Amendment 001; SHA256 `ab03c68a…` (md) / `194fed69…` (json) frozen by `V3_PREREG_FREEZE` |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.md` | **FROZEN_BEFORE_V3_IMPLEMENTATION** | Freeze authority binding the amended V3 prereg content at `543687fe` / tree `50750efc…` (plus new primitive `harness_synthetic_edge_calibration_v3_rng.py`) as sole scientific authority for V3 implementation; supersedes prior freeze `4136f53d` (preserved, not rewritten); does not modify the prereg bytes; not an ARM |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.json` | **FROZEN_BEFORE_V3_IMPLEMENTATION** | Machine-readable twin of the current V3 prereg freeze; `freeze_commit_head`/`tree` intentionally `UNSET_UNTIL_THIS_COMMIT` (no self-hash); `supersedes.previous_freeze_head = 4136f530…` |
| `research/harness_synthetic_edge_calibration_v3_rng.py` | **FROZEN (Amendment 001 primitive)** | `v3_namespace_seed()`: legal `"V3_CONFIRMATORY"` namespace-seed derivation without modifying the frozen V1 `NAMESPACES` allowlist or its TCB hash; reuses `_uint64_from_digest` verbatim; proven equivalent/deterministic/distinct by its test file |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE.md` | **FROZEN_BEFORE_V3_ARM / HISTORICAL PARENT** | Docs freeze of accepted V3 implementation `70673673` / tree `e94e18cb`; freeze HEAD `76f21007` / tree `dd59466b` is the live ARM parent; not itself an ARM |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE.json` | **FROZEN_BEFORE_V3_ARM / HISTORICAL PARENT** | Machine-readable twin; SHA256 `16fe6550…`; pre-ARM binding parent of the live one-shot ARM |
| `scripts/research/harness_synthetic_edge_calibration_v3_authority.py` | **PRE_ARM_BINDING + ONE_SHOT_ARM_AUTH + RESERVATION_GATE** | Authenticates freeze bytes and the one-shot ARM; derives scientific run identity `ce664429…`; refuses caller kwargs/path/env substitution; reservation/execution delegated to the V3 production module |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_ARM.md` | **ARMED_FOR_ONE_CANONICAL_V3_PRODUCTION_EXECUTION / CONSUMED** | One-shot ARM immediate child of freeze `76f21007`; consumed by exactly one reservation; does not authorize a second run |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_ARM.json` | **ARMED_FOR_ONE_CANONICAL_V3_PRODUCTION_EXECUTION / CONSUMED** | Machine-readable one-shot ARM bytes remain `33354b48…`; lifecycle consumption is by reservation presence, not ARM rewrite |
| `scripts/research/harness_synthetic_edge_calibration_v3_production.py` | **CANONICAL_EXECUTION_PLUMBING / EXECUTED** | One-shot reservation, durable checkpoint resume, WORLD_RECORDS/RESULT mint; frozen science unchanged |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_RESERVATION.json` | **RESERVED / CONSUMED** | Exactly one canonical reservation; identity `0bb58c95…`; SHA256 `8a062f1a…` |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_WORLD_RECORDS.json` | **CANONICAL WORLD_RECORDS / IMMUTABLE / V3_CALIBRATION_CLOSED** | 1600 terminal worlds; file SHA256 `5d09631d…`; inner records SHA256 `57f8361b…`; closed historical evidence, not a live calibration program |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_RESULT.json` | **CANONICAL RESULT / IMMUTABLE / V3_CALIBRATION_CLOSED** | Mechanically derived; SHA256 `f72eedcd…`; EASY PASS, MODERATE PASS, NULL INDETERMINATE, TRAP FAIL; `methodology_claimable = false`; not a V4/B2-06 authorization; V3 `DETECTED`/`PASS` is not by itself a robust market-edge claim |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_IMPLEMENTATION_REVIEW.md` | **IMPLEMENTATION_FROZEN_BEFORE_PRODUCTION_EXECUTION** | Frozen fixture implementation identity; not a RESULT |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json` | **AUTHORIZED_FOR_ONE_PRODUCTION_EXECUTION / UNUSED** | Tracked one-shot production authorization; bytes frozen at reviewed HEAD `7b308f6`; `production_calibration_executed = false`; `production_monte_carlo_arm_authorized = false` |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.md` | **AUTHORIZATION_FROZEN_BEFORE_PRODUCTION_EXECUTION / UNUSED** | Human companion to the frozen unused one-shot authorization |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_AUTHORIZATION_REVIEW.md` | **AUTHORIZATION_FROZEN_BEFORE_PRODUCTION_EXECUTION** | Reviewed authorization freeze; OPUS `GO_FOR_AUTHORIZATION_FREEZE`; Monte Carlo remains unarmed |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY.md` | **PRODUCTION_DURABILITY_IMPLEMENTATION_FROZEN_UNARMED** | Production durability/aggregation/result-persistence contract; implementation frozen unarmed; Monte Carlo remains unarmed |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY.json` | **PRODUCTION_DURABILITY_IMPLEMENTATION_FROZEN_UNARMED** | Machine-readable twin of the frozen unarmed production durability contract |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY_IMPLEMENTATION_FREEZE.md` | **PRODUCTION_DURABILITY_IMPLEMENTATION_FROZEN_UNARMED** | Docs-only freeze of reviewed implementation HEAD `d5277c4` / tree `7ab4178`; OPUS `GO_FOR_IMPLEMENTATION_FREEZE`; Monte Carlo remains unarmed |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY_IMPLEMENTATION_FREEZE.json` | **PRODUCTION_DURABILITY_IMPLEMENTATION_FROZEN_UNARMED** | Machine-readable freeze identity; does not claim the freeze commit was the reviewed code HEAD |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_DRIVER.md` | **PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED** | Canonical 3200-world driver; unused driver ARM `0abc5fe` authorized the driver freeze parent; live performance ARM binds the performance freeze instead; calibration not executed |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_DRIVER.json` | **PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED** | Machine-readable twin of the production execution-driver contract |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DRIVER_FREEZE.md` | **PRODUCTION_DRIVER_IMPLEMENTATION_FROZEN_UNARMED** | Docs-only freeze of reviewed implementation HEAD `3fadc39` / tree `5fb7772`; OPUS `GO_FOR_DRIVER_FREEZE`; freeze itself does not arm |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DRIVER_FREEZE.json` | **PRODUCTION_DRIVER_IMPLEMENTATION_FROZEN_UNARMED** | Canonical machine-readable driver freeze; unused ARM `0abc5fe` binds this parent; live performance ARM does not |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.md` | **PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED** | Docs-only ARM immediate child of final runtime freeze `1499bc5`; authorizes one synthetic 3200-world run against reviewed implementation `f47c539`; does not execute |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json` | **PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED** | Live ARM of freeze `1499bc5`; ARMs `0abc5fe` and `120ac45` do not authorize this runtime |
| `research/HARNESS_PERFORMANCE_V1.md` | **PERFORMANCE_EXECUTION_FROZEN / PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED** | Performance-only descendant of the synthetic production path; final runtime freeze of reviewed `f47c539`; freeze parent of the live ARM; does not consume ARM `0abc5fe` or `120ac45`; does not execute the 3200-world grid |
| `research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json` | **PERFORMANCE_EXECUTION_FROZEN_UNARMED** | Canonical machine-readable final runtime freeze of reviewed implementation HEAD `f47c539` / tree `84b23e4`; OPUS `GO_FOR_FINAL_RUNTIME_FREEZE`; freeze itself does not arm; ARMs `0abc5fe` and `120ac45` do not authorize this implementation |
| `manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml` | **SNAPSHOT_MATERIALIZED_NOT_RESEARCH_AUTHORIZED** | Planning/identity manifest for the B2-06 first-party OI/funding dataset; `research_authorized: false`; snapshot `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33` |
| `research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/` | **MATERIALIZED EVIDENCE / NOT RESEARCH AUTHORIZED** | Snapshot identity, object ledger, and quality report for `5a9d036b…`; SHA256 values anchored in the YAML manifest; raw ZIP and normalized JSONL remain gitignored and are not currently locally recoverable |
| `research/B2_01_VOLATILITY_TRANSITION_RESULT.md` | **FROZEN_EVIDENCE** | B2-01 development-only result; verdict `B2_01_CLOSED_NO_PROMOTION` |
| `research/B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md` | **FROZEN_EVIDENCE** | B2-02 development-only result; verdict `B2_02_CLOSED_NO_PROMOTION` |
| `research/B2_03_IMPULSE_MORPHOLOGY_PREREG.md` | **FROZEN_EVIDENCE** | B2-03 preregistration (before development outcomes) |
| `research/B2_03_IMPULSE_MORPHOLOGY_RESULT.md` | **FROZEN_EVIDENCE** | B2-03 development-only result; verdict `B2_03_CLOSED_NO_PROMOTION` |
| `research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md` | **FROZEN_EVIDENCE** | B2-04 preregistration (before implementation or development outcomes) |
| `PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md` | **ACTIVE / CANONICAL** | Evidence-first architecture philosophy and current non-goals |
| `ACTIVE_RESEARCH_RISKS.md` | **ACTIVE RECORD** | Risks that can invalidate the current research-first program |
| `RESEARCH_LEDGER.md` | **ACTIVE RECORD** | Experiment/hypothesis history and consumed windows |
| `CODEBASE_STATUS.md` | **ACTIVE / CANONICAL MAP** | Which code surfaces are active, frozen, deferred or operational |
| `.github/workflows/ci.yml` | **ACTIVE / FAST PR GATE** | Required CI for `pull_request` → `main`; `python scripts/ci/pr_gate.py`. Does not run the full ~8k suite. |
| `.github/workflows/full-regression.yml` | **ACTIVE / FULL REGRESSION** | Complete `python -m pytest -q` on `workflow_dispatch` and push to `main`. Not required for ordinary PR iteration. |
| `scripts/ci/pr_gate.py` | **ACTIVE / FAST PR GATE** | compileall + explicit current-invariant paths + tests mapped from the PR diff. Does not rerun MARKET-01. |
| `PROJECT_HISTORY.md` | **ACTIVE HISTORY** | Narrative evolution of Signalbot's ideas, architecture and philosophy |
| `history/README.md` | **ACTIVE HISTORY INDEX** | Direct links to immutable full historical roadmaps/contracts/specifications |
| `DATA_DURABILITY_RUNBOOK.md` | **OPERATIONS** | Data durability/recovery reference |
| `research/BATCH02_DURABLE_EVIDENCE_RETENTION_V1.md` | **IMPLEMENTED_PENDING_INDEPENDENT_REVIEW** | Outcome-blind B2-03+ durable evidence reservation/archival contract, including exact-byte raw-chunk archival and fresh-process post-outcome recovery from a tracked recovery authority; historical artifact-byte origin is operator-adjudicated, not cryptographically proven by a later recovery commit; no market outcomes |
| `research/batch02_recovery_authority/B2-05/669ae93c6a5c1d102a46fd129f04292f1beff978.json` | **OPERATOR_ADJUDICATED RECOVERY AUTHORITY** | Tracked B2-05 recovery authority used for the one-shot production archive; explicitly not a cryptographic witness of historical execution persistence |

If a historical document conflicts with the active canonical set about **what the project should do next**, the current documents win.

---

## 2. Project history — preserved intentionally

`PROJECT_HISTORY.md` is the human-readable map of the project's evolution:

- original market-information/decision-support idea;
- Stage 1 data foundation;
- V1 shadow forecasting;
- V1 empirical autopsy;
- V2 multi-timeframe architecture thesis;
- shift from correctness to falsification;
- E1 detector-separation experiment;
- discovery that one month of rich overlap is inadequate for durable-edge claims;
- 2026-08-26 research-first pivot;
- V3 Microscope calibration closeout and MARKET-phase transition (2026-09-17).

`history/README.md` complements that narrative with direct links to the full immutable source documents exactly as they existed before the pivot and records retired branch/PR history needed for safe branch cleanup.

The point of retaining history is not nostalgia. It prevents the project from repeatedly rediscovering rejected ideas and makes the reasoning behind architectural changes auditable.

Failed/null hypotheses remain part of the history.

---

## 3. Frozen experiment records — do not rewrite to match current philosophy

These are evidence/provenance artifacts for `E1-RUN-001` and must remain historically faithful:

- `E1_DETECTOR_SEPARATION_PREREG.md`
- `E1_DATA_INVENTORY_2026-08-25.md`
- `E1_VPS_RUNBOOK.md`
- `e1/E1_RUN_001_ABLATION_OUTCOME_REPORTING_FREEZE.md`
- `e1/E1_RUN_001_ABLATION_PROTOCOL_FREEZE.md`
- `e1/E1_RUN_001_CONTROL_PROTOCOL_FREEZE.md`
- `e1/E1_RUN_001_COVERAGE_PREFLIGHT_CLARIFICATION.md`
- `e1/E1_RUN_001_DEVELOPMENT_ABLATIONS.md`
- `e1/E1_RUN_001_DEVELOPMENT_CONTROLS.md`
- `e1/E1_RUN_001_DEVELOPMENT_OUTCOMES.md`
- `e1/E1_RUN_001_FINAL_HOLDOUT_EVALUATOR_FREEZE.md`
- `e1/E1_RUN_001_HOLDOUT_COVERAGE_READINESS_CLARIFICATION.md`
- `e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`

Do not rewrite old preregistration text to match later knowledge. Add a new dated clarification/ledger entry instead.

---

## 4. Historical implementation contracts / audits

The following describe earlier Stage1/Stage2/V2 implementation states or audits. They remain useful for code archaeology/reproducibility but are **not active product-development authorization**:

- `STAGE1_ACCEPTANCE.md`
- `STAGE2_SPEC.md`
- `STAGE2_CLARIFICATIONS.md`
- `STAGE2_DATA_AUDIT.md`
- `STAGE2_IMPLEMENTATION_PLAN.md`
- `V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md`
- `V2_PERCENTILE_MATURITY_AUDIT.md`
- `history/V2_MATHEMATICAL_HYPOTHESIS_REGISTER.md` — exact historical governance content archived from the standalone `research/v2-mathematical-hypothesis-register` branch before branch cleanup.

The old `PROJECT_RISK_AND_DEBT_REGISTER.md` is also retained as a **historical V2-era debt register**. Its Stage-6/7/8 implementation items are not automatically current work. Use `ACTIVE_RESEARCH_RISKS.md` for the current program.

---

## 5. Superseded roadmap/product documents

These paths are intentionally retained as compatibility/history pointers so old links do not silently lead readers into an obsolete active plan:

- `FORECASTING_ROADMAP.md`
- `PROJECT_EXECUTION_PLAN.md`
- `V2_PRODUCT_CONTRACT.md`
- `V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
- `V2_EMPIRICAL_RED_TEAM_PLAN.md`
- `PRODUCT_SPEC_V0.md`

Their former full contents are preserved in git history at the pre-pivot repository state, indexed for normal browsing in `history/README.md`, and their role in project evolution is summarized in `PROJECT_HISTORY.md`.

They must not contain a second active roadmap.

---

## 6. Deferred product hypotheses

`PRODUCT_HYPOTHESES.md` is a parking lot / historical product-thinking record only. Product/business work is frozen while the project is in research-first mode.

Do not delete rejected/deferred ideas merely to make the repository look cleaner; label them honestly and keep them outside current execution authority.

---

## 7. Operational/deployment references

These documents may still be useful operationally, but following them is not authorization to deploy or restart product development:

- `VPS_DEPLOY.md`
- `SHADOW_TIMER_DEPLOY.md`
- `TELEGRAM_NOTIFIER_DEPLOY.md`
- `E1_VPS_RUNBOOK.md`

Before using an operational runbook, compare it with current code/config and runtime state. Some commands/names reflect earlier deployment stages.

---

## 8. Code status

Use `CODEBASE_STATUS.md` before assuming that an implemented module is active roadmap scope.

Key examples:

- `analytics/forecasting/` — `FROZEN_BASELINE` (V1);
- `analytics/forecasting_v2/` — `FROZEN_RESEARCH_ENGINE` (V2-v0);
- E1-specific holdout scripts — `FROZEN_EXPERIMENT_TOOLING` once frozen;
- `storage/`, `data_ingestion/`, `backfill/` — active research infrastructure where justified by evidence/data needs;
- notification/product surfaces — retained but deferred.

Code may remain because it is useful history or a frozen comparator. Presence does not imply active development.

---

## 9. Repository instruction file

`../AGENTS.md` points coding/review agents to current sources of truth plus frozen research artifacts relevant to the task. It must not restore old V2 roadmap authority.

---

## 10. Status vocabulary for future docs

Every new planning/research document should declare one status near the top:

- `ACTIVE / CANONICAL` — current decision authority;
- `ACTIVE RECORD` — mutable ledger/register, not roadmap authority;
- `ACTIVE HISTORY` — maintained narrative/history index;
- `FROZEN_EVIDENCE` — immutable preregistration/result artifact;
- `FROZEN_ENGINE_REFERENCE` — semantics of a specific historical engine/version;
- `HISTORICAL` — preserved project history, no current execution authority;
- `DEFERRED` — intentionally parked, not active scope;
- `SUPERSEDED` — old active authority replaced by a newer source;
- `OPERATIONS` — runtime/runbook reference, not research/product authority.

Do not create an unlabelled roadmap/contract that can later be mistaken for current truth.

---

## 11. Cleanup policy

The target is **one current truth + a readable historical trail**.

Delete a file only when it is:

- an exact/near duplicate with no independent historical value;
- generated/transient material accidentally committed;
- an obsolete instruction whose presence creates operational risk and whose historical role is already preserved;
- dead scaffold/placeholder with no evidence, provenance or explanatory value.

Do **not** delete merely because:

- a hypothesis failed;
- a roadmap was superseded;
- the project changed philosophy;
- an implementation was abandoned.

When historically meaningful content is shortened or removed from the active tree, preserve at least one of:

- a clear entry in `PROJECT_HISTORY.md`;
- a frozen experiment record;
- an immutable git commit/reference containing the full original document.

When adding documentation:

1. declare its status;
2. update an existing canonical document instead of creating a competing roadmap;
3. do not duplicate large formulas/contracts across current files;
4. preserve failed experiments/preregistrations exactly;
5. remove contradictory instructions from current docs;
6. keep historical links discoverable from `PROJECT_HISTORY.md` / `history/README.md` / this index;
7. update this index whenever authority changes.
