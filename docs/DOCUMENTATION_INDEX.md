# Signalbot Documentation Index

**Status:** ACTIVE

This index exists to stop historical implementation documents from being mistaken for the current project plan.

## 1. Current sources of truth

Read these first:

| Document | Purpose |
|---|---|
| `PROJECT_STATUS.md` | Current project posture, freeze, empirical state and restart gate |
| `RESEARCH_ROADMAP.md` | Active execution order |
| `EDGE_RESEARCH_PROTOCOL.md` | Discovery/validation rules and anti-overfit discipline |
| `HISTORICAL_DATA_STRATEGY.md` | Multi-year CORE vs shorter RICH evidence strategy |
| `RESEARCH_LEDGER.md` | Experiment/hypothesis history and consumed windows |
| `PROJECT_RISK_AND_DEBT_REGISTER.md` | Current open risks and debt |
| `DATA_DURABILITY_RUNBOOK.md` | Operational data durability/recovery reference |

If a historical document conflicts with the first four about **what the project should do next**, the current documents win.

## 2. Active frozen research record

These are not editable roadmaps. They are evidence/provenance artifacts for `E1-RUN-001` and must remain historically faithful:

- `E1_DETECTOR_SEPARATION_PREREG.md`
- `E1_DATA_INVENTORY_2026-08-25.md`
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

## 3. Historical implementation contracts / audits

The following describe earlier Stage1/Stage2/V2 implementation states or audits. They remain useful for code archaeology/reproducibility but are **not active product-development authorization**:

- `STAGE1_ACCEPTANCE.md`
- `STAGE2_SPEC.md`
- `STAGE2_CLARIFICATIONS.md`
- `STAGE2_DATA_AUDIT.md`
- `STAGE2_IMPLEMENTATION_PLAN.md`
- `V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md`
- `V2_PERCENTILE_MATURITY_AUDIT.md`

Where an old contract is replaced by a short superseded stub, the full historical version remains in git history and at the frozen implementation commit used by the relevant experiment.

## 4. Superseded roadmap/product documents

These paths are intentionally retained only as compatibility pointers so old links do not silently lead readers into an obsolete plan:

- `FORECASTING_ROADMAP.md`
- `PROJECT_EXECUTION_PLAN.md`
- `V2_PRODUCT_CONTRACT.md`
- `V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
- `V2_EMPIRICAL_RED_TEAM_PLAN.md`
- `PRODUCT_SPEC_V0.md`

They must not contain a second active roadmap.

## 5. Deferred product hypotheses

`PRODUCT_HYPOTHESES.md` is a parking lot only. Product/business work is frozen while the project is in research-first mode.

## 6. Operational/deployment references

These documents may still be useful operationally, but following them is not authorization to deploy or restart product development:

- `VPS_DEPLOY.md`
- `SHADOW_TIMER_DEPLOY.md`
- `TELEGRAM_NOTIFIER_DEPLOY.md`
- `E1_VPS_RUNBOOK.md`

Before using an operational runbook, compare it with current code/config and runtime state. Some commands/names reflect earlier deployment stages.

## 7. Repository instruction file

`../AGENTS.md` should point only to current sources of truth plus the frozen research artifacts relevant to the task. It must not restore old V2 roadmap authority.

## 8. Hygiene rules

When adding documentation:

1. state whether it is `ACTIVE`, `FROZEN_EVIDENCE`, `HISTORICAL`, `DEFERRED`, or `SUPERSEDED`;
2. do not create another roadmap if an existing current document can be updated;
3. do not duplicate large formulas/contracts across files;
4. preserve failed experiments and preregistrations, but keep them outside current execution authority;
5. remove obsolete instructions rather than leaving contradictory paragraphs in current docs;
6. prefer short links to immutable historical commits over carrying hundreds of kilobytes of dead planning text in the active tree;
7. update this index when authority changes.
