> **Current routing note — 2026-09-23:** use `docs/CURRENT_RESEARCH_STATE.md` first for present lifecycle/next-unit status. Frozen experiment artifacts remain authoritative for their own semantics. Some older catalog descriptions below are historical and may retain the status they had when written. Original D2 BitMEX one-shot remains `INVALID`. Corrected execution classified `D2_BITMEX_REPLICATION_SUPPORTED`. Program class `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`. Excess path-risk decomposition one-shot is consumed: `D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`. Sprint 02 D7 is `PROMISING_PROTOTYPE` (consumed one-shot; confirmation candidate but not selected now). D8 is `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` and not a negative scientific result. Sprint 03 D9/D10 are `NO_USEFUL_STRUCTURE`; D11 is `PROMISING_PROTOTYPE` (unsigned scheduled-FOMC 6h RV; not D8 rescue). Sprint 04 D12 is `PROMISING_PROTOTYPE` (US-clock quote-volume anchoring; EU diagnostic does not classify). D13 is `NO_USEFUL_STRUCTURE` (observed reversal; practical gate failed). `INTERNAL_DISCOVERY_CARDS_EXECUTED = 10`. `INTERNAL_PROMISING_PROTOTYPES = 4`. `AUTOMATIC_SPRINT05 = false`. `POST_SPRINT04_AUTOMATION_MATURITY_DECISION` decided `HYPOTHESIS_GENERATOR_V0_INFRA_READY` (no Sprint 05; Generator V0 design frozen, not built, shadow-only). `NEXT_UNIT = GENERATOR_V0_MULTI_PROVIDER_ROUTING_READY_FOR_INDEPENDENT_REVIEW` (outcome-blind multi-provider routing; independent review before any provider smoke test or live run).

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

| `SIGNALBOT_MANDATE_V1.md` | **ACTIVE / CANONICAL STRATEGIC MANDATE** | Owner-approved project objective, anti-sycophancy rule, scientific/product/commercial mandate, agent operating principles, and amendment rules. Strategic authority; frozen experiment-specific scientific authorities still govern their own semantics. |
| `CURRENT_RESEARCH_STATE.md` | **ACTIVE / CANONICAL ROUTING INDEX** | Compact answer to current next-unit/status. D2 is `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`; D7 is `PROMISING_PROTOTYPE` (confirmation candidate, not selected now); D8 deferred; Sprint 03 D9/D10 `NO_USEFUL_STRUCTURE`, D11 `PROMISING_PROTOTYPE`; Sprint 04 D12 `PROMISING_PROTOTYPE`, D13 `NO_USEFUL_STRUCTURE`; 2025/2026 sealed; `NEXT_UNIT = GENERATOR_V0_MULTI_PROVIDER_ROUTING_READY_FOR_INDEPENDENT_REVIEW` |
| `research/MECHANISM_MEMORY_V0.md` | **MECHANISM MEMORY V0 (EXTENDED THROUGH D13)** | Compact H01–H05 / B2-01–B2-06 / MARKET-01–06 / D1–D13 map; D12 `PROMISING_PROTOTYPE`; D13 `NO_USEFUL_STRUCTURE`; not a new framework |
| `research/HETEROGENEOUS_FAMILY_ROTATION_V2.md` | **HYPOTHESIS GENERATION POLICY (FROZEN, CURRENT)** | Families A–I after D7; E cooldown; selected D/G/H as D10/D11/D9; true panel still absent; no MARKET-07 |
| `research/DISCOVERY_SPRINT_03.md` | **DISCOVERY SPRINT 03 (CARD DEFINITION / IMPLEMENTATION FREEZE)** | Frozen cards D9/D10/D11; scientific outcomes live in RESULT files; do not mutate this freeze |
| `research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.md` | **DISCOVERY SPRINT 03 IMPLEMENTATION FREEZE (OUTCOME-BLIND, CONSUMED)** | Structural feasibility + frozen evaluators/contracts; scientific outcomes are in RESULT files, not this freeze |
| `research/HETEROGENEOUS_FAMILY_ROTATION_V1.md` | **HYPOTHESIS GENERATION POLICY (FROZEN, HISTORICAL SPRINT 02)** | Families A–I; Sprint 02 selected E (D7) and G (D8); routing superseded by V2 |
| `research/DISCOVERY_SPRINT_02.md` | **DISCOVERY SPRINT 02 (CARD DEFINITION, HISTORICAL)** | Outcome-blind cards D7 `KLINE_FLOW_IMPACT_STATE` and D8 `ENDOGENOUS_SHOCK_RECOVERY`; definition freeze; D7 later executed |
| `research/DISCOVERY_SPRINT_02_FEASIBILITY.md` | **DISCOVERY SPRINT 02 FEASIBILITY (SELECTOR/SUPPORT ONLY)** | D7 `OUTCOME_BLIND_READY` with frozen selector digest; D8 `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`; exact-byte identity; no scientific outcomes |
| `research/DISCOVERY_SPRINT_02_IMPLEMENTATION_REVIEW.md` | **DISCOVERY SPRINT 02 IMPLEMENTATION REVIEW (OUTCOME-BLIND)** | `PASS` after exact-byte identity + frozen D7 selector + D8 non-executable; next unit is D7-only scientific execution freeze |
| `research/DISCOVERY_SPRINT_02_SCIENTIFIC_EXECUTION_FREEZE.md` | **DISCOVERY SPRINT 02 D7 EXECUTION FREEZE (HISTORICAL ROUTE)** | D7 one-shot route frozen before execution; later consumed by the canonical RESULT |
| `research/DISCOVERY_SPRINT_02_D7_EXECUTION_PERMIT.json` | **D7 ONE-SHOT EXECUTION PERMIT (TRACKED, CONSUMED)** | Outcome-blind permit; binds `ONE_SHOT_RUNNER_SHA256`; consumed by the canonical one-shot; `RERUN_AUTHORIZED = false` |
| `research/DISCOVERY_SPRINT_02_D7_RESULT.md` | **D7 CANONICAL ONE-SHOT RESULT (CONSUMED)** | `D7_PROMISING_PROTOTYPE`; adaptive discovery only; confirmation candidate but not selected now; no rerun |
| `research/DISCOVERY_SPRINT_02_D7_RESULT.json` | **D7 CANONICAL ONE-SHOT RESULT twin** | Payload SHA256 `7a7d38ef…`; gates all true; 2025/2026 unopened |
| `research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.md` | **D1 PRE-EXECUTION ADJUDICATION** | D1 deferred: null generates daily returns; state observable requires 288×5m RV. Gate not executed. |
| `research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.md` | **D2 CONFIRMATION DESIGN** | Outcome-blind 2025 confirmation design for RULE_1 / RV_ABSTENTION; underpowered single year; year-matched two-year surface still underpowered; 2025/2026 unopened |
| `research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.md` | **D2 ALTERNATIVE SURFACE FEASIBILITY** | Pre-2020 BitMEX XBTUSD is a feasible class-A independent replication surface; D2 outcomes not computed; 2025/2026 unopened |
| `research/D2_BITMEX_REPLICATION_PREREG.md` | **D2 BITMEX REPLICATION PREREG (FROZEN, OUTCOME-BLIND)** | Independent pre-2020 cross-venue temporal replication contract; N=1069; not executed; 2025/2026 unopened |
| `research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.md` | **D2 BITMEX IMPLEMENTATION REVIEW (OUTCOME-BLIND)** | Reviewed execution implementation; stub lineage preserved; no BitMEX result; execution unauthorized |
| `research/D2_BITMEX_REPLICATION_RESULT.md` | **D2 BITMEX REPLICATION RESULT (ONE-SHOT, INVALID)** | Canonical one-shot; constructed N=1067 vs frozen 1069; primary metrics not computed; not NOT_SUPPORTED; no rerun |
| `research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.md` | **D2 BITMEX INTEGRITY ADJUDICATION** | Two drops are predeclared BTC_RET_24H_EQ_0; Class A identity repair; original INVALID preserved; no D2 effect |
| `research/D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1.json` | **D2 BITMEX PREREG IDENTITY AMENDMENT** | Corrected expected N=1067; historical prereg bytes unchanged; execution unauthorized |
| `research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.md` | **D2 BITMEX CORRECTED RESULT (ONE-SHOT)** | Integrity-repair execution; identity 1317/250/1067; `D2_BITMEX_REPLICATION_SUPPORTED`; not exact Binance confirmation; original INVALID preserved |
| `research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.md` | **PROGRAM DECISION AFTER D2 SUPPORTED** | D2 classed independently replicated mechanism candidate; 2025/2026 sealed; generation policy A–I; product frozen; no MARKET-07 |
| `research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.md` | **D2 DECOMPOSITION DESIGN (FROZEN, OUTCOME-BLIND)** | Post-replication ADVERSE_SHARE vs year×SIDE-matched random abstention; selector unchanged; seed 20260922131; not independent confirmation; not executed |
| `research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REVIEW.md` | **D2 DECOMPOSITION IMPLEMENTATION REVIEW (OUTCOME-BLIND)** | Frozen design implemented and red-teamed; `PASS`; dormant canonical orchestration; tracked-permit verifier; selector-identity authority contract wired but artifact not created in that unit; `EXECUTION_READY = false`; no decomposition outcome, no permit, no RESULT |
| `research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_SELECTOR_IDENTITY.json` | **D2 SELECTOR IDENTITY AUTHORITY (FROZEN)** | Canonical ordered selector digest from legal CORE BTC 2020-2024; constructed N=1791 vs abstain N=163; no ADVERSE_SHARE/PATH_SCALE; `CANONICAL_SELECTOR_DIGEST_FROZEN = true` |
| `research/D2_EXCESS_PATH_RISK_EXECUTION_PERMIT.json` | **D2 EXCESS PATH-RISK EXECUTION PERMIT (TRACKED)** | Outcome-blind one-shot permit; `EXECUTION_AUTHORIZED = true`; `ONE_SHOT = true`; `RERUN_AUTHORIZED = false`; consumed |
| `research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.md` | **D2 EXCESS PATH-RISK RESULT (ONE-SHOT, CONSUMED)** | Canonical one-shot; `D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`; no rerun; 2025/2026 unopened |
| `research/DISCOVERY_SPRINT_03_RESULT.md` | **SPRINT 03 BATCH RESULT (CONSUMED)** | D9/D10 `NO_USEFUL_STRUCTURE`; D11 `PROMISING_PROTOTYPE`; counters 8/3; Sprint 04 not selected |
| `research/DISCOVERY_SPRINT_03_RESULT.json` | **SPRINT 03 BATCH RESULT twin** | Payload SHA256 `1e1d25e1…`; 2025/2026 unopened |
| `research/POST_SPRINT03_PROGRAM_DECISION.md` | **POST-SPRINT 03 PROGRAM DECISION (DECIDED)** | Unit `DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION`; D9/D10 consumed null, D11 consumed prototype; D7/D11 confirmation not selected now; second-moment concentration of prototypes; post-Sprint 04 automation maturity decision required; JSON twin `.json` |
| `research/HETEROGENEOUS_FAMILY_ROTATION_V3.md` | **HYPOTHESIS GENERATION POLICY V3 (FROZEN, ACTIVE)** | Whole-family vs tested-subfamily status for A–I plus new family J; selects H (true panel) and J; V2 preserved as history; JSON twin `.json` |
| `research/DISCOVERY_SPRINT_04.md` | **DISCOVERY SPRINT 04 (SELECTION FROZEN; EXECUTION CONSUMED)** | 12-candidate pool; D12 participation-clock DST natural experiment; D13 cross-sectional weekly relative return; D14 not selected; scientific outcomes live in RESULT files; JSON twin `.json` is authoritative |
| `research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.md` | **DISCOVERY SPRINT 04 IMPLEMENTATION FREEZE (OUTCOME-BLIND, CONSUMED)** | D12/D13 evaluators frozen; D12 10/10 US windows; D13 N=82, NO_POST_T_CLOSE_SELECTED_N=0; EXECUTION_AUTHORIZED=false in common.py; JSON twin `.json` |
| `research/DISCOVERY_SPRINT_04_EXECUTION_PERMIT.json` | **SPRINT 04 ONE-SHOT EXECUTION PERMIT (TRACKED, CONSUMED)** | Outcome-blind permit; binds EXECUTION_ROOT, freeze SHA, implementation hashes, D12/D13 identities; `ONE_SHOT=true`; `RERUN_AUTHORIZED=false` |
| `research/DISCOVERY_SPRINT_04_RESULT.md` | **SPRINT 04 BATCH RESULT (CONSUMED)** | D12 `PROMISING_PROTOTYPE`; D13 `NO_USEFUL_STRUCTURE`; counters 10/4; next unit automation-maturity decision |
| `research/DISCOVERY_SPRINT_04_RESULT.json` | **SPRINT 04 BATCH RESULT twin** | Payload SHA256 `a70d7c4b…`; 2025/2026 unopened |
| `research/POST_SPRINT04_AUTOMATION_MATURITY_DECISION.md` | **POST-SPRINT 04 AUTOMATION MATURITY DECISION (ACTIVE)** | `HYPOTHESIS_GENERATOR_V0_INFRA_READY`; option B rejected; 2 effective prototype classes; generator-first data demand; JSON twin `.json` |
| `research/HYPOTHESIS_GENERATOR_V0_DESIGN.md` | **HYPOTHESIS GENERATOR V0 DESIGN (FROZEN, NOT IMPLEMENTED)** | Blind generator context (`BLIND_MECHANISM_MAP_V0`), roles, frozen candidate schema, data-status taxonomy, two output streams, data-gap ledger, 40-candidate shadow batch, USD 30 cap; JSON twin `.json` is authoritative |
| `research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/` | **D13 PANEL IDENTITY / LEDGER** | Pinned listings, CHECKSUM ledger, fee pin, universe identity; raw zips gitignored |
| `research/discovery_results/D9_DISCOVERY_RESULT.md` | **D9 CANONICAL RESULT (CONSUMED)** | `NO_USEFUL_STRUCTURE`; unclipped SHARE; not price-discovery leadership; do not rescue |
| `research/discovery_results/D10_DISCOVERY_RESULT.md` | **D10 CANONICAL RESULT (CONSUMED)** | `NO_USEFUL_STRUCTURE`; residual persistence; does not validate MARKET-05 |
| `research/discovery_results/D11_DISCOVERY_RESULT.md` | **D11 CANONICAL RESULT (CONSUMED)** | `PROMISING_PROTOTYPE`; unsigned scheduled-FOMC 6h RV; N=39; not D8 rescue |
| `research/discovery_results/D12_DISCOVERY_RESULT.md` | **D12 CANONICAL RESULT (CONSUMED)** | `PROMISING_PROTOTYPE`; US-clock quote-volume anchoring; EU diagnostic does not classify |
| `research/discovery_results/D12_DISCOVERY_RESULT.json` | **D12 CANONICAL RESULT twin** | Payload SHA256 `73299c8d…`; MEAN_A `0.13355…`; MC_P `9.999e-05` |
| `research/discovery_results/D13_DISCOVERY_RESULT.md` | **D13 CANONICAL RESULT (CONSUMED)** | `NO_USEFUL_STRUCTURE`; observed reversal; practical gate failed vs friction 0.004 |
| `research/discovery_results/D13_DISCOVERY_RESULT.json` | **D13 CANONICAL RESULT twin** | Payload SHA256 `c18f7de5…`; N=82 WEEK_N=256; POOLED_IC_SIGN=-1 |
| `research/discovery_results/` | **ADAPTIVE DISCOVERY RESULTS** | D2-D5 plus Sprint 03 D9/D10/D11 and Sprint 04 D12/D13; not confirmatory |
| `RESEARCH_ROADMAP.md` | **ACTIVE / CANONICAL** | Active execution order. MARKET-01 closed `NO_EVIDENCE`; V3 closed; no V4; B2-06 remains blocked. |
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
| `research/BATCH02_STATUS_LEDGER.md` | **ACTIVE RECORD** | Post-outcome Batch02 formulation/family status, including B2-05 durable-evidence recovery closeout `B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED` at archive `e31e5666fe845116197b6f2531289bf17d848027`; B2-06 remains `BLOCKED_MISSING_OBSERVABLE` after an outcome-blind OI/funding snapshot bind that does not authorize execution; does not mutate the frozen inventory |
| `research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_DATA_FEASIBILITY.md` | **OUTCOME_BLIND_FEASIBILITY** | MARKET-01 price/OI inventory only; `MARKET_01_PREREG_FEASIBLE = YES`; no outcomes, no B2-06 execution |
| `research/MARKET_06_CROSS_VENUE_FEASIBILITY.md` | **OUTCOME_BLIND_FEASIBILITY / HISTORICAL BYBIT ROUTE** | Preserved Bybit-route probe; Binance Vision reachable; Bybit V5 CloudFront country 403; not rewritten by the OKX review |
| `research/MARKET_06_CROSS_VENUE_FEASIBILITY.json` | **OUTCOME_BLIND_FEASIBILITY twin / HISTORICAL** | `verdict=MARKET_06_HISTORICAL_FEASIBILITY_REQUIRES_DESIGN_REVIEW`; Bybit spot not reachable from this host |
| `research/MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.md` | **OUTCOME_BLIND_FEASIBILITY / CURRENT SOURCE-ROUTE REVIEW** | OKX BTC-USDT spot 5m replaces Bybit before prereg; Binance USD-M 5m trade-price perp unchanged; `MARKET_06_OKX_HISTORICAL_FEASIBILITY_CONFIRMED` |
| `research/MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.json` | **OUTCOME_BLIND_FEASIBILITY twin** | Timestamp census 315648/315648 aligned; `scientific_outcomes_inspected=false`; no prereg/ARM/RESULT |
| `research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/` | **IDENTITY_FROZEN + DURABLE RAW BYTES GIT-RETAINED** | Snapshot `e0403e40…` unchanged; `durable_raw/` holds exact Binance ZIPs and OKX HTTP bodies |
| `research/MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RETENTION.md` | **DURABLE RETENTION / NOT SCIENCE** | Outcome-blind Git retention of existing snapshot bytes; no redownload; no prereg |
| `research/MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RETENTION.json` | **DURABLE RETENTION twin** | `verdict=MARKET_06_DURABLE_RAW_EVIDENCE_RETAINED`; `new_snapshot_minted=false` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md` | **FROZEN_OUTCOME_BLIND payload (amended)** | Live MARKET-06 preregistration after amendment 002; SHA256 `70dd8d09…`; freeze authority is the freeze document |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json` | **FROZEN_OUTCOME_BLIND payload (amended)** | Frozen machine-readable twin; SHA256 `f60bf0bd…` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001.md` | **PRE_OUTCOME_AMENDMENT / HISTORICAL** | F1–F4 scientific-definition drift correction; outcomes not inspected |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001.json` | **PRE_OUTCOME_AMENDMENT twin / HISTORICAL** | Binds `OLD_PREREG_CONTENT_HEAD=b21bf46d…` and `OLD_FREEZE_HEAD=5f14411…` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002.md` | **PRE_OUTCOME_AMENDMENT** | Year-stratified predictive bootstrap correction; outcomes not inspected |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002.json` | **PRE_OUTCOME_AMENDMENT twin** | Binds `OLD_LIVE_PREREG_HEAD=b4459ab9…` and `OLD_LIVE_FREEZE_HEAD=371f71d…` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.md` | **HISTORICAL first payload** | Exact first prereg bytes; SHA256 `0489fc71…`; not live authority |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.json` | **HISTORICAL first payload twin** | Exact first JSON bytes; SHA256 `332d9114…` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V1.md` | **HISTORICAL amendment-001 payload** | Exact amendment-001 live bytes; SHA256 `55f6f352…`; not live authority |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V1.json` | **HISTORICAL amendment-001 payload twin** | Exact amendment-001 JSON bytes; SHA256 `191dfcf4…` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.md` | **FROZEN_OUTCOME_BLIND / CURRENT FREEZE AUTHORITY** | Docs-only freeze of amendment-002 materialization `6342d24e…` / tree `11658516…`; not an ARM; not execution |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.json` | **FROZEN_OUTCOME_BLIND / CURRENT FREEZE AUTHORITY** | Machine-readable twin; `freeze_commit_head`/`tree` intentionally `UNSET_UNTIL_THIS_COMMIT` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V0.md` | **HISTORICAL first freeze** | Exact first freeze bytes; SHA256 `3bf48957…`; not live authority |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V0.json` | **HISTORICAL first freeze twin** | Binds first payload `b21bf46d…`; superseded by later freezes |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V1.md` | **HISTORICAL amendment-001 freeze** | Exact amendment-001 freeze bytes; SHA256 `69f4de8f…`; not live authority |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V1.json` | **HISTORICAL amendment-001 freeze twin** | Binds amendment-001 payload `b4459ab9…`; superseded by amendment 002 freeze |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION.md` | **IMPLEMENTED_OUTCOME_BLIND / NOT EXECUTED** | MARKET-06 evaluator identity after amendment 002; canonical execution refused |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION.json` | **IMPLEMENTED_OUTCOME_BLIND twin** | Binds prereg freeze `e2d543ea…`; `real_canonical_execution_refused=true` |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.md` | **IMPLEMENTATION_FROZEN_OUTCOME_BLIND / CURRENT IMPLEMENTATION AUTHORITY** | Docs-only freeze of implementation `81c8e0a8…` / tree `7f4e0a85…`; not an ARM; not execution |
| `research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.json` | **IMPLEMENTATION_FROZEN_OUTCOME_BLIND twin** | Module SHA256 inventory; `freeze_commit_head`/`tree` intentionally `UNSET_UNTIL_THIS_COMMIT` |
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
- `scripts/audit/live_archive_replay_preflight/` — owner-executable read-only coverage exporter for a later live-archive replay preflight. It does not query production on import, does not export market magnitudes, and is not itself a coverage result.
- `docs/audit/live_archive_replay_preflight/phase_a_coverage_analysis.md` — Phase A classification of the owner-run live-archive coverage export. It does not reconstruct detector events or authorize replay.

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
- `PRIVATE_BETA_V0_DEPLOY.md`: beta V0.2 deploy, soak and privacy runbook. Its units are prepared, not activated.
- `BETA_BTC_TEMPORAL_CONTEXT_V0.md`: the `/btc` temporal-context amendment. The active episodization `STRICT_QUALIFICATION_V1` keeps the detector's own episode boundaries. The amendment adds LAST EVENT memory, factual anchor buckets, the rolling-1h context `BETA_CONTEXT_1H_V0` and replay. Live hysteresis is disabled; an unfrozen taker-only calibration tool remains dormant. Detector rules and push decisions are unchanged.
- `E1_VPS_RUNBOOK.md`

Before using an operational runbook, compare it with current code/config and runtime state. Some commands/names reflect earlier deployment stages.

---

## 7a. Descriptive private beta V0.2 (authorized 2026-09-25)

- `PRIVATE_BETA_V0_RESTART_DECISION.md` is the governance authority. It covers the scope, the frozen rule identity, the soak gate, and the rollout and exit criteria. It is descriptive only, and the predictive product stays frozen.
- `research/BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md` carries the label `PROSPECTIVE_PRE_REGISTERED_FORWARD_EVALUATION / OWNER_UNBLINDED`. It is never independent confirmation.

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

## Generator V0 implementation and shadow operation

- `research/GENERATOR_V0_OPERATOR.md` — active run/preflight/resume and human audit commands; protected-data exclusion is the unambiguous `NO_LOOKAHEAD_RULE` form only.
- `research/GENERATOR_V0_FIRST_SHADOW_V7.{json,md}` — operational closeout of live first-shadow-v7 (`STOPPED_PROTECTED_RANGE_VALIDATION`; not scientific).
- `research/generator_v0_first_shadow_v7/` — sealed v7 authority journal and generation:3 validation diagnostic.
- `research/GENERATOR_V0_IMPLEMENTATION_PLAN.md` — requirement-to-checkpoint mapping.
- `research/BLIND_MECHANISM_MAP_V0.json` — tracked outcome-neutral prior signatures.
- `research/GOVERNANCE_REGION_AUTHORITY_V0.json` — frozen per-signature authority, excluded from Generator/Selector.
- `research/GENERATOR_V0_CONTEXT_PINS.json` — exact-byte context source identities.
- `research/GENERATOR_V0_PROVIDER_VERIFICATION.md` — official API verification, mixed Responses/Chat Completions transport, Structured Outputs, and mixed-model prices.
- `research/GENERATOR_V0_MODEL_ROUTING.md` — role → stable model IDs and per-role reasoning_effort; GENERATOR is background Responses, critics remain Chat Completions.
- `research/GENERATOR_V0_ADVERSARIAL_REVIEW.md` — 25-class self-review, fixes and limits.
- `research/generator_v0_checkpoints/` — durable checkpoint chain and compact mock evidence.

- `research/GENERATOR_V0_PRE_LIVE_REPAIR.{json,md}` — offline pre-live repair record (contract V02, per-card quarantine, failure classes, lineage spend, advisory selector); outcome-blind design amendments.
- `research/GENERATOR_V0_LEGACY_V01_GRANDFATHER.json` — option-A compatibility manifest: the only historical call keys and card digests admitted under the frozen v0.1 validator.
- `research/GENERATOR_V0_SEALED_RUNS.json` — sealed journal hashes refused by the operator at any path.
- `research/generator_v0_repair/OFFLINE_GATE_REPORT.json` — offline gate evidence (corpus, noisy E2E, derive-after-partial-work, v7 derive proof, fresh and derived budget preflight).
- `research/GENERATOR_V0_LIMITED_REPAIR.{md,json}` — limited offline repair after the PR #215 verification (B1–B5, residuals, and the final narrow repair); `READY_FOR_FINAL_RE-VERIFICATION`.
- `research/GENERATOR_V0_MULTI_PROVIDER_ROUTING_AMENDMENT.{md,json}` — outcome-blind multi-provider routing amendment (Opus generator, Sol/Luna critics); routing registry `scripts/research/generator_v0/routing.py` is authoritative for routed runs.
- `research/GENERATOR_V0_ANTHROPIC_COMPACT_PROJECTION.{md,json}` — Anthropic GENERATOR compact wire projection (one shared card schema, array of cards) after the grammar-too-large 400; relaxed provider constraints and their intake enforcement; grammar before/after; live re-smoke blocked on a missing `ANTHROPIC_API_KEY`.
- `research/GENERATOR_V0_ANTHROPIC_OUTPUT_CAP_AMENDMENT.{md,json}` — live compact re-smoke result (HTTP 200, `max_tokens` at 32768, USD 0.713332) and the owner amendment raising only the routed Anthropic GENERATOR output cap to 100000; failure-path hash provenance fix; recalculated bounds and smoke budget.
- `research/GENERATOR_V0_BACKGROUND_NOVELTY_TRANSPORT_AMENDMENT.{md,json}` — routed NOVELTY_CRITIC moved from synchronous Chat Completions to background Responses (create once, poll by response_id) after two ambiguous HTTP 502s in the cost calibration; model, effort, prompt, schema and all other roles unchanged; offline timing diagnostic.
- `research/GENERATOR_V0_BACKGROUND_RED_TEAM_TRANSPORT_AMENDMENT.{md,json}` — routed RED_TEAM moved from synchronous Chat Completions to background Responses after the same ambiguous Sol HTTP 502 class in the critic calibration; model, effort, prompt, schema, token cap and all other roles unchanged; C001 red-team call reconciled UNKNOWN.
- `AGENT_RUNTIME_PROTOCOL.md` — active operational protocol for cloud-agent live-provider work: checkout verification, ephemeral-VM handling, verified HTTPS proxy binding, budgets, exactly-once semantics, provenance and artifact survival.
- `research/GENERATOR_V0_FIRST_30_CARD_ARCHITECTURE_FREEZE.{md,json}` — active/canonical operational freeze for the first full 30-card Generator V0 run; routes, calibration observations, run-size/budget boundary and no-more-precautionary-smokes rule.
- `research/GENERATOR_V0_FIRST_30_PRODUCTION_PATH_REPAIR.{md,json}` — offline enforcement of that freeze: one generator POST per round, zero selector LLM calls on the first 30-card path, and explicit `CLOUD_PROXY` OpenAI binding. Budget semantics and Memory Finalizer V1 are unchanged.
- `research/GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.{md,json}` — offline export of the five-card cost/pipeline calibration sample (C001-C005 cards, final critic verdicts, deterministic selector order, successful per-role costs); no scientific status, no market outcomes tested.
- `research/GENERATOR_V0_MEMORY_FINALIZER.{md,json}` — **active/canonical** memory authority. The `MARKET_TEST_RESULT` event has been implemented since 2026-09-25 (§8); it attaches executed test results to full memory only. The rest of this entry is unchanged: append-only memory event chain (`research/generator_v0_memory/`), full vs blind generator memory, deterministic dispositions and blocker mapping, atomic HEAD publish, idempotency, stable IDs, operator CLI. Mechanism memory, blind map, governance authority and context pins are derived caches of the chain.
- `research/generator_v0_repair/BUDGET_SCENARIOS.json` — budget/run-shape scenarios A–E (decision support only; none chosen).

- `research/GENERATOR_V0_FIRST_30_CARD_RUN_GV0R01.{md,json}` — **sealed** record of the first real 30-card campaign GV0R01 (`PENDING_HUMAN_REVIEW`, USD 5.091486, Stream A C013). The sealed journal is tracked at `research/generator_v0_gv0r01/run.sqlite`. It includes the memory finalization event `416b22fa…`. No market outcome was tested.

- `research/GV0R01_C013_MARKET_TEST_PREREG.{md,json}` — **frozen** one-shot preregistration of the first market test for GV0R01-C013 (JSON authoritative; `EXECUTION_AUTHORIZED = false`). Harness `scripts/research/gv0r01_c013_market_test{,_lib}.py`.
- `research/GV0R01_C013_MARKET_TEST_OUTCOME.{md,json}` — **immutable** outcome record of the one-shot C013 test (`PROMISING_PROTOTYPE`, discovery tier). The authoritative result is `research/GV0R01_C013_MARKET_TEST_RESULT.json` (SHA256 `036016c4…`). The pre-outcome permit is `research/GV0R01_C013_MARKET_TEST_EXECUTION_PERMIT.json` (commit `386bc10`).
- `research/GV0R01_C013_CONFIRMATION_FEASIBILITY_AND_DESIGN.{md,json}` — outcome-blind confirmation feasibility for C013: `WAIT_FOR_MORE_FRESH_DATA` (underpowered on every available fresh surface), with the design recorded for any future powered surface. The power record is `research/GV0R01_C013_CONFIRMATION_POWER.json` (script `scripts/research/gv0r01_c013_confirmation_power.py`). No prereg, no permit.
- `research/GV0R01_STREAM_B_FEASIBILITY_TRIAGE.{md,json}` — outcome-blind data-feasibility triage of the six GV0R01 Stream-B candidates and the post-C013 program decision. C013 is parked as `CONFIRMATION_DEFERRED_LOW_POWER`; next candidate is C012; GV0R02 is not next.
- `research/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0_ACQUISITION.{md,json}` — data-provenance record for `research_data/BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0/` (**DURABLY_PINNED**, digest `760ed2c5…`, raw bytes Git-retained). Point-in-time BLS CPI release schedule 2020–2024: 60 events, all safe at W6/W12/W24, 0 rescheduled, 0 unresolved; schedule metadata only. Resolves the CPI calendar observable for C012/C004; no design. Script `scripts/research/bls_cpi_schedule_archive_v0.py`.
- `research/GV0R01_C012_OUTCOME_BLIND_DESIGN.{md,json}` — outcome-blind preregistration candidate for GV0R01-C012. Primary is FOMC+CPI, 24h, two-sided. Gate `EXECUTION_JUSTIFIED`, `EXECUTION_AUTHORIZED = false`. Power in `research/GV0R01_C012_POWER.json`. Script `scripts/research/gv0r01_c012_design.py`. No market outcomes.
- `research/GV0R01_C012_PREFLIGHT.json` — calendar-only control assignment before any price access. `PREFLIGHT_STATUS = PASS`. Execution did not open CORE_BTC; see `research/GV0R01_C012_EXECUTION_BLOCK.json`.
- `research_data/C012_DISCOVERY_BTC_1M_V0/MANIFEST.json` — discovery-period identity for CORE_BTC 1m months 2020-01..2024-12 only. Raw bytes stay under gitignored `artifacts/`. No C012 outcome.
- `research/GV0R01_C012_DEPENDENCE_BLOCK.json` — one-shot C012 stopped before price access. Global permutation invariance is `NOT_ESTABLISHED` (177 overlap components, 154 swappable observations with differing external neighborhoods). `RUN_STATUS = BLOCKED_INFERENCE_DEPENDENCE_DEFECT`. Primary result not computed.
- `research/GV0R01_C012_INFERENCE_AMENDMENT.json` — outcome-blind replacement of the C012 permutation group by `G_C012_TOPO`. Structural invariance passes. Synthetic stress MDE is about 0.61 single-window SD, so the power gate is `INFERENCE_AMENDMENT_VALID_BUT_INFORMATIONALLY_WEAK`. No execution. No prices.
- `research/GV0R01_C012_CLOSE.json` — terminal C012 status `CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK`. No execution, no prices, no further C012 inference amendment. Next design candidate is C004.
- `research/GV0R01_C004_OUTCOME_BLIND_DESIGN.{md,json}` — outcome-blind C004 design. Primary is post-FOMC ETH residual share, not a C012 drift test. Gate `EXECUTION_INFORMATIONALLY_WEAK`. No prices. Script `scripts/research/gv0r01_c004_design.py`.
- `research/GV0R01_C004_CLOSE.json` — terminal C004 status `CLOSED_OUTCOME_BLIND_INFERENCE_SUPPORT_INSUFFICIENT`. Exact p floor is 1/16. No execution, no prices, no widened permutation. Next design candidate is C020.
- `research/GV0R01_C020_DESIGN_BLOCK.{md,json}` — C020 definition is unambiguous and the design stops at `BLOCKED_BY_MISSING_INPUT`. The NYSE, China State Council and US OPM holiday calendars were unpinned at that stop. No prices, no power.
- `research/GV0R01_C020_HOLIDAY_CALENDAR_PIN.json` — data-provenance pin of the three C020 calendars for 2020–2024. `STATUS = HOLIDAY_CALENDARS_PINNED`. NYSE digest `45201d10…`, OPM digest `e2402e00…`, China digest `4223719d…`. No prices. Script `scripts/research/c020_holiday_calendar_pin_v0.py`.
- `research/GV0R01_C020_OUTCOME_BLIND_DESIGN.{md,json}` — outcome-blind C020 design after the calendars were pinned. Gate `EXECUTION_INFORMATIONALLY_WEAK`. Lead arm is 47 NYSE full weekday closures. Execution bar `log(0.90)` was frozen before synthetic power. No prices, no C020 execution. Script `scripts/research/gv0r01_c020_design.py`.
- `research/GV0R01_C020_CLOSE.json` — C020 terminal classification. The pseudo-holiday procedure is a placebo reference distribution, not an exact randomization test. Status `CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK_REFERENCE_TEST`. Execution remains unauthorized.
- `research/GV0R02_FEASIBILITY_COMPILER_DESIGN.md` — design contract for a cheap outcome-blind feasibility screen before preregistration. Implemented by `scripts/research/gv0r02_feasibility_compiler.py`. The synthetic positive control is `GV0R02_POSITIVE_CONTROL_SYNTHETIC` in `tests/research/test_gv0r02_feasibility_compiler.py`. The schema file remains the frozen contract.
- `scripts/research/generator_v0/feasibility_contract.py` — `GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V0`. Future candidates carry an outcome-blind planning object that copies into a GV0R02 proposal. `GENERATOR_CONTRACT_V02` is unchanged.
- `research/GV0R02_FEASIBILITY_COMPILER_SCHEMA.json` — schema `GV0R02_SCHEMA_V0` and policy `GV0R02_POLICY_V0`.
- `research/GV0R02_FEASIBILITY_COMPILER_GOLDEN_CASES.json` — C012, C004, and C020 acceptance inputs. No market recomputation.
- `research/SCIENTIFIC_TEST_LEDGER.json` — **active** global machine-readable ledger of executed scientific tests and search families, registered before outcomes. Generated cards are not counted.

Implementation state: `GENERATOR_V0_FIRST_30_CARD_RUN_COMPLETE_MEMORY_FINALIZED` (previously `GENERATOR_V0_MEMORY_FINALIZER_V1_READY_FOR_FIRST_30_CARD_RUN`). Next unit: `GV0R02_FEASIBILITY_COMPILER_POSITIVE_CONTROL` (previously `GV0R02_OUTCOME_BLIND_FEASIBILITY_COMPILER_IMPLEMENTATION`; golden C012, C004, and C020 pass and the positive control was not run) (previously `GV0R02_OUTCOME_BLIND_FEASIBILITY_COMPILER_DESIGN`; the contract is frozen and the compiler is not built) (previously `STREAM_B_REMAINING_CANDIDATES_BLOCKED`; the candidate queue is not continued) (previously `NO_C020_EXECUTION_AUTHORIZED`; C020 is closed as a reference test and the power gate still fails) (previously `GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER_CONTINUATION`; the design is informationally weak and execution is not authorized) (previously `GV0R01_C020_HOLIDAY_CALENDAR_PINNING`; the three calendars are pinned) (previously `GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER`; that design stopped because the three holiday calendars are unpinned) (previously `GV0R01_C012_OUTCOME_BLIND_DESIGN_AND_POWER`; the design is frozen and execution is not authorized) (previously `GV0R01_C012_CPI_CALENDAR_ACQUISITION_AND_OUTCOME_BLIND_DESIGN`; the CPI calendar half is complete).
The archived partial paid runs `artifacts/generator_v0/first-shadow`,
`artifacts/generator_v0/first-shadow-v2`,
`artifacts/generator_v0/first-shadow-v3`,
`artifacts/generator_v0/first-shadow-v4`,
`artifacts/generator_v0/first-shadow-v5`,
`artifacts/generator_v0/first-shadow-v6`, and
`artifacts/generator_v0/first-shadow-v7` are sealed.
Offline `derive` may still read `first-shadow-v6` as an immutable source
through generation:2; it must not POST or mutate v6 or v7. Do not resume
v7. Do not extend LEGAL_RANGE or the C033 exclusion parser from observed
generation:3 wrappers. Owner-authorized absolute campaign total remains
USD 17.100000. Live run/resume cannot exceed that ceiling.
The original design's FROZEN_NOT_IMPLEMENTED label describes its historical
freeze, not the current implementation state.

- `research/GENERATOR_V0_CALIBRATION_MEMORY_INGESTION.{json,md}` — outcome-blind ingestion of all five calibration cards into durable mechanism memory; stable `GV0CAL-*` signatures and blocker-aware novelty governance.
