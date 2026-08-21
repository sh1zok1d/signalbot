# Signalbot Project Risk & Debt Register

> Canonical inventory of known project risks, research-validity threats, correctness concerns, operational/documentation debt, and required follow-up. The purpose is to prevent non-urgent findings from disappearing merely because they do not block the current PR.

## Status vocabulary

- `OPEN` — known and not yet resolved.
- `IN_PROGRESS` — active work exists.
- `PLANNED` — accepted, scheduled after an explicit dependency/gate.
- `VERIFY` — implementation may already be correct; requires a focused audit/proof.
- `CLOSED` — resolved with evidence and a pointer to the resolving PR/report.
- `DEFERRED` — consciously postponed with a reason and re-entry condition.

Severity:

- `CRITICAL` — can invalidate the central research conclusion or promotion decision.
- `HIGH` — can materially bias results, correctness, or operational trust.
- `MEDIUM` — meaningful engineering/product debt that should be closed before maturity.
- `LOW` — quality/presentation improvement; still tracked.

---

## A. Research validity / predictive-evidence risks

| ID | Severity | Status | Risk / debt | Required closure evidence | Gate |
|---|---|---|---|---|---|
| R-001 | CRITICAL | OPEN | Correctness may be mistaken for evidence of trading edge | Reports explicitly separate correctness level from detector/episode/OOS/live evidence | all empirical claims |
| R-002 | CRITICAL | OPEN | V1 -> V2 causal diagnosis is unproven | Formal V1 diagnostic: direction, lateness, MFE/MAE, clustering, simple/random baselines | before interpreting V2 superiority |
| R-003 | CRITICAL | OPEN | Human/researcher overfit after repeated backtest inspection | Research ledger + untouched chronological OOS rules + version reset after consumed holdout | confirmatory evaluation |
| R-004 | HIGH | OPEN | Setup-selection bias for the three chosen families | Pre-registered evaluation + controls; future setup changes recorded as new hypotheses/versions | G4 empirical gate |
| R-005 | HIGH | OPEN | Parameter magic-point/brittleness | Predeclared local sensitivity neighborhoods, no optimizer-style search | G4 |
| R-006 | HIGH | OPEN | Small raw/effective sample size | Episode-level counts, calendar span, cluster/effective-evidence notes, uncertainty method | G4/G5 |
| R-007 | HIGH | OPEN | Regime dependency / non-stationarity | Chronological blocks + predeclared regime/concentration analysis | G4/G5 |
| R-008 | HIGH | OPEN | MTF roles may duplicate one latent market impulse | Full V2 vs lower-TF/price-structure ablation and setup overlap analysis | G4 |
| R-009 | HIGH | OPEN | Feature complexity may not add incremental value | Ablation for OI/funding/liquidations/taker/HTF/consensus | G4 |
| R-010 | HIGH | OPEN | Cross-exchange consensus may be robustness rather than independent information | Single/reduced/median/full venue contribution study; confidence interpretation review | G4 |
| R-011 | MEDIUM | DEFERRED | Venue divergence/lead-lag may be more informative than agreement | Record as future hypothesis only; do not add until current V2 survives G4 | post-G4 research |
| R-012 | HIGH | OPEN | Setup families may identify the same latent events | Event overlap/outcome-correlation matrix and effective sample adjustment | G4 |
| R-013 | HIGH | OPEN | Model confidence may not order outcome quality | Confidence-bin curves for feasibility/MFE/MAE/utility; remain non-probabilistic | G4/G5 |
| R-014 | HIGH | OPEN | Multiple comparisons/subgroup cherry-picking | Predeclared subgroup set + exploratory labels + research ledger | G4 |
| R-015 | HIGH | OPEN | 30-day replay may be misread as proof of edge | Documentation/report labels 30d as engineering/event-study polygon, not durable edge evidence | G2/G4 |
| R-016 | HIGH | OPEN | Simple baseline may match/beat V2 | Pre-registered V1/simple TA/time-matched/null baselines under same delay/cost semantics | G4 |
| R-017 | HIGH | OPEN | Negative controls may reveal regime exposure rather than signal information | Time-shift, direction-inversion, feature/venue permutation controls where valid | G2/G4 |
| R-018 | HIGH | OPEN | Delay/cost sensitivity may erase edge | Multi-point delay curve + conservative cost/slippage stress | G4/G5 |
| R-019 | HIGH | OPEN | Incomplete data may be dropped non-randomly and inflate performance | Full denominator tree including incomplete/non-comparable episodes; no silent survivor-only headline metric | G4/G5 |
| R-020 | HIGH | OPEN | Live shadow may diverge from replay | Explicit replay-vs-live comparison and contract-mandated independent shadow evidence | G5 |
| R-021 | MEDIUM | OPEN | Automatic/new feature expansion can become response to weak evidence | Expansion freeze until G4; new ideas ledger-only | until G4 |
| R-022 | HIGH | OPEN | Many future configurations can create backtest-overfitting probability | Track number of tested configs; freeze method for multiple-testing/PBO-style analysis if search surface grows | G4 |
| R-023 | MEDIUM | DEFERRED | Percentile `confidence_tier` is calendar-span-only (`STAGE2_SPEC.md` §12.6, deliberate); reaching `MIN_PCTL_TIER` proves `sample_size >= 2` and a wide-enough span, never statistical density. Once a real Stage 2 percentile orchestrator exists, V2 evidence (`normalized_evidence`/`compression_score`) and activation readiness could accept an extremely sparse (e.g. 2-sample) distribution as fully usable, materially misleading the empirical program (issue #51/MATH-001) | Either (a) a percentile-computation orchestrator ships with an explicit, mathematically/structurally justified minimum-density invariant reviewed and frozen at that time, or (b) an explicit, documented product/research decision to accept span-only maturity permanently | before any percentile orchestrator ships / before treating V2 evidence as empirically meaningful |

---

## B. Historical data / feed-semantics risks

| ID | Severity | Status | Risk / debt | Required closure evidence | Gate |
|---|---|---|---|---|---|
| D-001 | CRITICAL | OPEN | Historical feature availability is not automatically live-equivalent | Define evidence tiers (`LIVE_EQUIVALENT`, partial, non-comparable, not-evaluable) and surface them in reports | G1/G4 |
| D-002 | HIGH | OPEN | Liquidation feeds differ in completeness/aggregation semantics across venues | Per-venue/per-period semantic inventory; no absolute cross-venue equivalence assumption without proof | G1/G4 |
| D-003 | HIGH | VERIFY | 5m OI -> 1m ffill may create pseudo-minute timing/slope information | Focused feature-engine audit/tests proving no inference from unavailable temporal granularity; redesign if violated | G1 |
| D-004 | HIGH | OPEN | Historical OI/taker/liquidation coverage differs by venue | Capability/evidence matrix included with each research window | G1/G4 |
| D-005 | HIGH | OPEN | Provider/API semantics can change over calendar time | Historically versioned feed-semantics/capability record or equivalent research manifest | G4/reproducibility |
| D-006 | HIGH | OPEN | Data outages/gaps may correlate with volatility | Missingness-by-regime/outage analysis and denominator transparency | G4/G5 |
| D-007 | HIGH | CLOSED | Historical/as-of instrument metadata/tick size correctness | H2c as-of `exchange_instrument_history` model implemented and MERGED: PR #59 (`hardening/v2-h2c-asof-instrument-metadata`), merge commit `1eef3dc7d19ccb7dd9c9410f8c3b7da2b84f3572`. `storage/stage2_schema.sql`, `storage/v2_setup_readers.py::read_v2_instrument`, `storage/db.py::Database.upsert_exchange_instrument`/`fetch_v2_instrument`/`seed_current_instrument_history`/`bootstrap_instrument_metadata_revision`, `analytics/forecasting_v2/ports.py`, with pure-reader, schema, and real-PostgreSQL as-of/overlap/restart/concurrency tests, five tech-lead/CodeRabbit review rounds resolved. Closure per §I requires MERGED implementation + tests, not draft — satisfied. | G0 |
| D-008 | HIGH | IN_PROGRESS | Stage-2 corrections can produce incoherent historical views | H2e publication-completeness/coherent-view/replay determinism — implemented on `hardening/v2-h2e-correction-publication-coherent-replay`, NOT YET MERGED (per §I closure requires MERGED implementation + tests, not draft): `storage/stage2_publication_state.py` (durable DIRTY/CLEAN state machine, `stage2_publication_state` table, scope `(symbol, market_type)`), `Database.insert_klines`/`insert_open_interest`/`insert_funding` now detect a genuine raw correction (`xmax <> 0` on their `ON CONFLICT DO UPDATE`) and mark DIRTY in the SAME transaction/COMMIT as the raw write, `Database.publish_stage2_correction` (one atomic transaction publishing every derived family and flipping CLEAN — reuses `Stage2WriterSpec`/`serialize_batch` unchanged), `Database.open_v2_coherent_read_session`/`storage/v2_coherent_read_session.py::V2CoherentReadSession` (one pinned connection/`REPEATABLE READ, readonly` transaction satisfying both `V2AlignedInputReader` and `V2SetupHistoryReader`, publication-state checked as the FIRST read, fail-closed on DIRTY/unbootstrapped). Proven with six real-PostgreSQL concurrency vectors (old-snapshot-survives-correction, raw-new/derived-old-gap-fails-closed, partial-publication-rollback, successful-publication, DIRTY-survives-restart/reconnect, same-snapshot/no-TOCTOU) plus a two-independent-session deterministic replay harness exercising `load_v2_aligned_inputs`/`build_v2_context_snapshot`/`load_compression_breakout_inputs`. Explicitly NOT built this round (documented, not silently deferred): the `stage2_recompute_queue`-driven reconciliation WORKER (confirmed schema-only/unexecuted anywhere in this repo before this PR) and real percentile-invalidation orchestration — a scope that becomes DIRTY today stays DIRTY until a future worker or manual operator calls `publish_stage2_correction`. | G0/G1 |
| D-009 | HIGH | OPEN | Research reports may depend on mutable/revised database state | Data snapshot/revision identity in validation artifacts; rerun reproducibility proof | G4 |
| D-010 | MEDIUM | OPEN | Cross-venue metrics can compare unlike measurement instruments | Feature-specific comparability rules and report flags | G4 |

---

## C. Core correctness / persistence / lifecycle risks

| ID | Severity | Status | Risk / debt | Required closure evidence | Gate |
|---|---|---|---|---|---|
| C-001 | HIGH | CLOSED | Version switch can mix old/new model semantics mid-episode | H2b durable DRAIN-BEFORE-ACTIVATE state machine implemented (`analytics/forecasting_v2/version_switch.py` + `version_switch_orchestrator.py`, `storage/v2_version_switch_readers.py`, `v2_version_switch_state` table) with pure-transition, orchestration-boundary, schema, and real-PostgreSQL row-locking/atomicity/restart tests — MERGED via PR #58, merge commit `19f3b1d5075df642a3f1e8decb0f53ea0b3d8b48`. | G0 |
| C-002 | HIGH | PLANNED | Event persistence/idempotency may duplicate or partially persist same-T decisions | H3 deterministic IDs, uniqueness, atomic batch tests, restart identity | G0 |
| C-003 | HIGH | PLANNED | Full episode transition semantics not implemented | Stage 6 completion and contract-vector tests | G3 |
| C-004 | HIGH | PLANNED | Entry feasibility not implemented | Stage 7 completion | G3 |
| C-005 | HIGH | PLANNED | Full V2 outcome/evaluation populations not implemented | Stage 8 completion | G3 |
| C-006 | MEDIUM | OPEN | Large formal system can create bugs in its own validation/readiness layers | Continue adversarial contract-vector/property tests; periodic API simplification review | ongoing |

---

## D. Documentation / configuration debt

| ID | Severity | Status | Risk / debt | Required closure evidence | Gate |
|---|---|---|---|---|---|
| DOC-001 | MEDIUM | OPEN | README materially understates/misstates current V2 implementation state | README rewritten to current architecture/status and source-of-truth links | G6 |
| DOC-002 | MEDIUM | OPEN | Documentation topology is difficult for new readers | Link explicit authority hierarchy from README/roadmap; index current vs historical docs | G6 |
| DOC-003 | MEDIUM | OPEN | Roadmap contains historical/stale “V2 not implemented” wording despite Stage 3–5 code | Reconcile status section without erasing historical context | G6 |
| CFG-001 | MEDIUM | OPEN | `coverage_2of4_blocks_new_triggered` names old 4-exchange topology and may be unused | Prove consumer or remove/rename/migrate with tests | G6 |
| CFG-002 | MEDIUM | OPEN | `coverage_1of4_pauses_signal_engine` same legacy-topology ambiguity | Prove consumer or remove/rename/migrate with tests | G6 |
| CFG-003 | MEDIUM | OPEN | Legacy calibration `30 total / 10 per setup` can be misread as V2 evidence threshold | Prove V2 isolation; rename/document/remove legacy keys as appropriate | G6 |
| CFG-004 | MEDIUM | OPEN | Unused config can create illusion of active protection | Add config-consumption audit/dead-config test strategy | G6 |
| DOC-004 | LOW | OPEN | Public repo has weak metadata/presentation | Decide description/topics/license; update only after explicit project-positioning decision | G6 |

---

## E. CI / security / reproducibility debt

| ID | Severity | Status | Risk / debt | Required closure evidence | Gate |
|---|---|---|---|---|---|
| CI-001 | MEDIUM | OPEN | GitHub Actions permissions are not explicitly minimized in workflow | Add explicit least-privilege `permissions:` | G6 |
| CI-002 | MEDIUM | OPEN | Actions referenced by movable major tags | Pin third-party/GitHub Actions to immutable commit SHAs with update process | G6 |
| CI-003 | MEDIUM | OPEN | No visible dependency vulnerability/review gate | Add dependency review/vulnerability policy/workflow | G6 |
| CI-004 | MEDIUM | OPEN | No visible static typing/lint gate | Choose typing/lint scope, baseline existing debt, add non-noisy CI gates | G6 |
| CI-005 | MEDIUM | OPEN | No explicit SAST/secret-scanning workflow evidence in repo | Verify GitHub settings and/or add appropriate scanning | G6 |
| CI-006 | LOW | OPEN | No explicit coverage threshold/policy | Measure coverage by risk area; decide whether threshold adds value without gaming | G6 |
| CI-007 | MEDIUM | OPEN | High-value invariants rely mainly on example tests | Add property-based tests selectively for alignment/identity/state invariants where valuable | ongoing/G6 |
| ENV-001 | HIGH | OPEN | Direct pins do not lock transitive dependency graph | Adopt reproducible lock/hash strategy appropriate for deployment/research | G4/G6 |
| ENV-002 | HIGH | OPEN | Research identity may omit execution environment | Include Python/dependency/container/environment identity in validation manifests | G4 |
| ENV-003 | MEDIUM | OPEN | Dependency/API updates can change behavior without research comparability review | Define upgrade procedure including replay/regression impact assessment | G6 |

---

## F. Maintainability / complexity debt

| ID | Severity | Status | Risk / debt | Required closure evidence | Gate |
|---|---|---|---|---|---|
| M-001 | MEDIUM | OPEN | Detector modules/contracts are becoming very large | Architecture review; split only where semantic boundaries are clear and tests protect behavior | G6/ongoing |
| M-002 | MEDIUM | OPEN | Defensive layers may duplicate validation logic | Identify duplicated invariants and centralize only when it reduces bug surface | G6 |
| M-003 | MEDIUM | OPEN | Test-suite size/runtime/maintenance cost will continue growing | Track runtime, integration boundaries, flaky/duplicate tests, parallelization/caching options | G6 |
| M-004 | LOW | OPEN | Correctness contract is difficult to navigate | Add stable index/traceability/navigation aids without weakening normative text | G6 |
| M-005 | MEDIUM | OPEN | Engineering complexity can continue despite low empirical knowledge | Enforce expansion freeze and progress reporting split by correctness vs evidence | until G4 |

---

## G. Product / operational evidence debt

| ID | Severity | Status | Risk / debt | Required closure evidence | Gate |
|---|---|---|---|---|---|
| P-001 | HIGH | OPEN | Real human notification/action delay is unknown | Measure live delivery/action latency distribution during shadow/pilot; use sensitivity before then | G4/G5 |
| P-002 | HIGH | OPEN | Attention load/usefulness may differ from statistical edge | Report episodes/week, updates/episode, late fraction, spam burden | G5 |
| P-003 | HIGH | OPEN | User-facing wording can overstate confidence/edge | Preserve non-calibrated confidence language; no “proven win probability” without future contract | G5 |
| P-004 | MEDIUM | OPEN | V1 retirement could happen without comparable evidence | Keep separate explicit V1_RETIRABLE decision per correctness contract | after G5 |
| P-005 | HIGH | OPEN | Automatic execution would change risk/evaluation problem entirely | Remains out of initial scope; requires separate product/risk contract | deferred |

---

## H. Required near-term closure order

### Before Stage 6

- H2b/H2c/H2e/H3 and convergence gate.

### Parallel now

- R-002 formal V1 diagnosis;
- R-003 research ledger discipline;
- D-001 live-equivalent evidence design;
- D-002 feed-semantics inventory;
- D-003 OI/provider-granularity audit;
- R-016/R-017 baseline + negative-control preregistration.

### Immediately after H2e

- Stage-5 detector event study (`E1_DETECTOR_SEPARATION`).

### Before empirical GO decision

- full Stage 6/7/8;
- all G4 research-validity items in `V2_EMPIRICAL_RED_TEAM_PLAN.md`;
- environment/data identities sufficient for reproducible reports.

### Before product maturity / public-facing confidence in repo

- documentation/config cleanup;
- CI/supply-chain/reproducibility hardening;
- maintainability review;
- live-shadow product metrics.

---

## I. Closure rule

A risk is not `CLOSED` because “we discussed it” or “a test probably covers it”. Closure requires one of:

- merged implementation + tests;
- version-pinned empirical report;
- explicit audit proving no defect/consumer gap;
- documented product decision that removes the risky behavior from scope.

Every closure should add a PR/commit/report reference to this register.