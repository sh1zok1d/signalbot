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
| D-007 | HIGH | IN_PROGRESS | Historical/as-of instrument metadata/tick size correctness | H2c as-of `exchange_instrument_history` model implemented (`storage/stage2_schema.sql`, `storage/v2_setup_readers.py::read_v2_instrument`, `storage/db.py::Database.upsert_exchange_instrument`/`fetch_v2_instrument`/`seed_current_instrument_history`/`bootstrap_instrument_metadata_revision`, `analytics/forecasting_v2/ports.py`) with pure-reader, schema, and real-PostgreSQL as-of/overlap/restart/concurrency tests — hardening/v2-h2c-asof-instrument-metadata, draft, not yet merged. Amended per tech-lead review 4990482334: explicit `observed_at` (provenance, nullable) vs `effective_from` (required decision-time activation boundary) split with a real Postgres CHECK, a conservative explicit LKG-history bootstrap (`seed_current_instrument_history`, never extrapolates backward), Stage 5 candidates now carry `decision_tick_size` by value. Amended AGAIN per tech-lead review 4991738511: the prior round's `accepted_code_version` label (storage-only, never connected to feature computation) was removed and replaced with a real end-to-end mechanism — `defaults.instrument_metadata_revision` (`config/stage2.yaml`) is part of `config_hash`/`calculation_version`; `Database.upsert_exchange_instrument`'s critical-acceptance path atomically bumps the ONE global `stage2_instrument_metadata_state.required_revision` row; `analytics/feature_engine/input_adapter.py::assemble_exchange_feature_request` fails closed the instant the resolved config's revision stops matching it, for every exchange/symbol, until an operator explicitly adopts the new revision (which is what actually forks `calculation_version`). Amended a THIRD time per tech-lead review 4992495660 (operational-integration gap): `execute_shadow_once`/`execute_shadow_recovery` (`runtime/shadow_cli.py`/`runtime/shadow_recovery.py`) now share one bootstrap helper that establishes/verifies `stage2_instrument_metadata_state` via `Database.bootstrap_instrument_metadata_revision` immediately after schema init and strictly before any instrument upsert or raw-bundle read (that method now fails closed, never silently overwrites, on a persisted/config revision mismatch); `--shadow-dry-run`/`--shadow-status` stay read-only and fail closed on a missing/mismatched revision instead of masking it; the status schema surface (`storage/shadow_cli_readers.py`) now treats the new table as a mandatory prerequisite (missing table or an empty singleton row both report `PARTIAL_SCHEMA`, never `EMPTY`/`READY`). Amended a FOURTH time per CodeRabbit's independent review (tech-lead-classified blocker): `Database.fetch_exchange_feature_raw_bundle`'s seven fixed reads now run inside one `REPEATABLE READ, readonly` transaction, closing a real cross-read snapshot race where a concurrent critical-metadata acceptance could commit between two of the reads and return an internally-incoherent bundle (OLD instrument paired with a NEW `required_metadata_revision`); proven for real against PostgreSQL with two concurrent connections. Also this round: `exchange_instrument_history`'s `tick_size`/`contract_multiplier` CHECK constraints tightened to also reject NaN/+Infinity (`v > 0 AND v < 'Infinity'::float8`, since a naive `> 0` does not), and a DDL-drift guard added proving the real-Postgres test suite's hand-copied DDL never silently diverges from this file. Closure per §I requires MERGED implementation + tests, not draft. | G0 |
| D-008 | HIGH | PLANNED | Stage-2 corrections can produce incoherent historical views | H2e publication-completeness/coherent-view/replay determinism | G0/G1 |
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