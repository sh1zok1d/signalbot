# Signalbot — Codebase Status Map

**Status:** ACTIVE / CANONICAL MAP  
**Purpose:** distinguish code that is active research infrastructure from frozen engines, historical product surfaces and operational-only components.

This file does **not** change runtime behavior. It prevents repository archaeology from being mistaken for active development scope.

For project history, see `PROJECT_HISTORY.md`. For current execution, see `PROJECT_STATUS.md` and `RESEARCH_ROADMAP.md`.

---

## Status vocabulary

- `ACTIVE_RESEARCH_INFRA` — may be extended when required by the current research program;
- `ACTIVE_RESEARCH_TOOLING` — research scripts/tools may evolve under the research protocol;
- `FROZEN_BASELINE` — retained for reproducibility/comparison; do not tune in place;
- `FROZEN_RESEARCH_ENGINE` — implemented model/engine retained for frozen experiments and future comparison; no product development;
- `FROZEN_EXPERIMENT_TOOLING` — code tied to an already-frozen run; semantics may not change after the freeze except documented correctness repair;
- `OPERATIONS` — runtime/deployment support, not evidence or roadmap authority;
- `DEFERRED_PRODUCT_SURFACE` — existing user-facing/product code retained but not active scope;
- `HISTORICAL_COMPATIBILITY` — legacy support retained because removing it would damage archaeology/reproducibility or current compatibility.

---

## Top-level map

| Path | Status | Current role |
|---|---|---|
| `data_ingestion/` | `ACTIVE_RESEARCH_INFRA` | Live/raw market-data acquisition. Change only when needed for trustworthy research data or operational correctness. |
| `backfill/` | `ACTIVE_RESEARCH_INFRA` | Historical acquisition. Expected to become important for multi-year CORE expansion. |
| `storage/` | `ACTIVE_RESEARCH_INFRA` | TimescaleDB persistence, data-quality, historical/replay support and provenance. |
| `common/` | `ACTIVE_RESEARCH_INFRA` | Shared config/versioning/logging primitives. |
| `scripts/research/` | mixed; see below | Primary research/audit tooling. New research tools belong here unless a repeated stable abstraction justifies promotion. |
| `analytics/forecasting/` | `FROZEN_BASELINE` | V1 forecasting logic. Retain for autopsy/baseline comparison; do not rescue/tune V1 in place. |
| `analytics/forecasting_v2/` | `FROZEN_RESEARCH_ENGINE` | V2-v0 implementation and correctness foundation. Retain for E1/reproducibility; Stage 6+ product progression is frozen. |
| `notifications/` | `DEFERRED_PRODUCT_SURFACE` | Existing notification infrastructure. Not current product-expansion scope. |
| `deploy/` | `OPERATIONS` | Deployment examples/runtime support. Presence is not authorization to deploy V2. |
| `config/` | mixed | Existing runtime/model configs. Frozen model semantics must not be changed merely because research-first mode changed. |
| `tests/` | active support | Correctness/regression coverage. Tests protecting research validity remain active; old engine tests remain useful historical regression evidence. |
| `main.py` | `OPERATIONS / ACTIVE_INFRA_ENTRYPOINT` | Existing runtime entrypoint. Do not reinterpret as current product roadmap. |

---

## `analytics/forecasting/` — V1

**Status:** `FROZEN_BASELINE`

V1 remains because it provides:

- a real historical implementation baseline;
- a known failure/autopsy case;
- comparable simple-system behavior for future research;
- evidence about churn, latency and confidence misuse.

Allowed changes:

- correctness/security fixes required to keep historical/replay behavior usable;
- explicit compatibility fixes that do not change the frozen model thesis.

Not allowed by default:

- threshold tuning;
- new features;
- confidence redesign intended to rescue results;
- production promotion.

A materially changed V1 idea is a **new hypothesis/version**, not “V1 fixed”.

---

## `analytics/forecasting_v2/` — V2-v0

**Status:** `FROZEN_RESEARCH_ENGINE`

This package contains substantial engineering value — temporal alignment, deterministic identities, provenance, model semantics and Stage-3/4/5 logic — but the package is no longer the active product roadmap.

Current uses:

- reproduce/finish `E1-RUN-001`;
- compare future simpler candidates against frozen V2 behavior where valid;
- reuse only genuinely generic primitives when a current research task proves the need.

Do not continue automatically into:

- Stage-6 episode lifecycle;
- Stage-7 feasibility/product logic;
- Stage-8+ product evaluation/promotion;
- new V2 families/thresholds;
- production enablement.

If later evidence validates a mechanism similar to V2, architecture is redesigned around the validated mechanism; old V2 code may be reused selectively rather than resumed wholesale.

---

## `scripts/research/`

**Status:** `ACTIVE_RESEARCH_TOOLING` with frozen sub-surfaces.

### E1-specific scripts

Any script explicitly tied to `E1-RUN-001` candidate generation, holdout inventory, preflight or final holdout evaluation is `FROZEN_EXPERIMENT_TOOLING` once its corresponding protocol/freeze document says so.

Examples include the E1 holdout inventory/preflight/final evaluator path.

Rules:

- do not change semantics after freeze because a result is inconvenient;
- correctness fixes require explicit dated documentation;
- one-shot holdout protections must remain intact;
- new research questions should normally receive a new script/run/version rather than mutating E1 history.

### Future research scripts

New CORE-history acquisition audits, hypothesis scans and development studies may be added here as `ACTIVE_RESEARCH_TOOLING` under `EDGE_RESEARCH_PROTOCOL.md`.

Prefer transparent scripts + manifests before building a generalized research framework.

---

## `storage/`, `data_ingestion/`, `backfill/`

**Status:** `ACTIVE_RESEARCH_INFRA`

These are the main reusable foundation under the research-first pivot.

Changes are justified when they improve:

- historical coverage;
- source fidelity;
- no-lookahead/as-of correctness;
- native provider granularity;
- missingness transparency;
- provenance/reproducibility;
- deterministic materialization;
- operational durability required to preserve research data.

Changes are **not** justified merely to add richer feeds before a research hypothesis needs them.

---

## Product and notification surfaces

Existing Telegram/notification/product-oriented code is retained as project history and potentially reusable infrastructure, but its expansion is deferred.

Do not delete it merely because product development is frozen. It documents an actual stage of the project and may remain useful after future validation.

Do not add UX/product features until the restart gate in `PROJECT_STATUS.md` is satisfied, except narrow operational/research observability needed to protect evidence.

---

## Config semantics

The repository contains configuration from several project eras.

Rules:

1. do not delete a config key merely because current research does not use it if frozen/historical code still depends on it;
2. do not assume presence means active policy;
3. when a key is truly unused/dead, remove it only with code-reference proof and tests where relevant;
4. V1/V2 model parameters stay frozen for experiments that depend on them;
5. new research parameters belong to a versioned research manifest/config, not silently into production V2 config.

---

## Tests

Tests are not “old junk” merely because they target a frozen engine.

Historical correctness tests preserve:

- exact old semantics;
- no-lookahead guarantees;
- provenance identities;
- regression knowledge acquired during earlier phases.

Delete tests only when the underlying code/contract is intentionally removed and its historical/reproducibility value has been consciously archived.

Passing tests prove engineering behavior, not market edge.

---

## What can eventually be removed

Physical code deletion should be conservative until research settles the future architecture.

Good deletion candidates are:

- proven unreachable duplicate implementation;
- abandoned scaffold never used by runtime/research and with no historical explanatory value;
- generated/cache/output files accidentally committed;
- compatibility branch whose consumers have been removed and whose history is already safely preserved;
- product code that a later validated architecture explicitly replaces and no frozen experiment needs.

Do not delete code solely because its market hypothesis failed. A failed implementation can remain a valuable frozen baseline and project-history artifact.

---

## Restart rule

When one or more edges become `VALIDATED_CANDIDATE` under `EDGE_RESEARCH_PROTOCOL.md`, perform a fresh architecture inventory:

1. identify which existing infrastructure directly supports the validated mechanism;
2. identify frozen V1/V2 code worth reusing;
3. identify obsolete baggage that can then be archived/removed safely;
4. design new lifecycle/risk/product layers from validated behavior rather than old roadmap inertia.

Until then, repository cleanup means **clarifying ownership/status and deleting true duplication**, not aggressively shrinking code for aesthetics.
