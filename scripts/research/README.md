# Research Scripts

This directory contains **research/audit tooling**, not production runtime code.

## Status rules

Every new script should be treated as one of:

- `FROZEN_RUN_TOOL` — belongs to a specific preregistered/consumed experiment; preserve for reproducibility;
- `AUDIT_TOOL` — one-off or targeted correctness/data audit;
- `REUSABLE_RESEARCH_TOOL` — intentionally generalized after repeated real use;
- `DEPRECATED` — retained temporarily only because another artifact still references it.

Do not promote one-off research code into production packages merely to make the tree look cleaner.

## E1-RUN-001 tools

The `v2_e1_*` scripts are primarily `FROZEN_RUN_TOOL` / E1 provenance. They should not be casually refactored, consolidated or deleted while `E1-RUN-001` is incomplete.

Important current E1 tools include:

- candidate/data inventory and population audit;
- development outcomes/controls/ablation inventory/outcomes;
- holdout ablation inventory;
- timestamp-only holdout coverage preflight;
- one-shot final holdout evaluator.

Their exact semantics are governed by `docs/E1_DETECTOR_SEPARATION_PREREG.md` and `docs/e1/` freezes, not by the new general research roadmap.

After E1 is permanently closed, these scripts may be moved to a run-specific archive or replaced by reusable primitives **only if the immutable run remains reproducible from a commit/tag**.

## Earlier mathematical/audit tools

`math002b_*` belongs to earlier consensus-robustness research/audit work. Treat it as `AUDIT_TOOL` unless a current research run explicitly reuses it.

Do not delete it solely because it is old; first confirm that the corresponding audit/report is reproducible from immutable git history and no active run imports it.

## New research-first work

For R1+ work, prefer a small structure such as:

```text
scripts/research/
  datasets/        # reproducible historical materialization/manifests
  audits/          # source semantics, gaps, no-lookahead checks
  experiments/     # explicit run/version entrypoints
  lib/             # only primitives proven reusable by multiple experiments
```

Do not reorganize the existing E1 scripts during E1 itself. Introduce the structure incrementally when the first historical-expansion work begins.

## Hygiene rules

1. A script that opens outcome data must state which dataset/window it is allowed to read.
2. Confirmatory scripts must fail closed on identity/split/version mismatches.
3. Research scripts should write immutable/versioned artifacts rather than only stdout summaries.
4. Do not silently overwrite a final confirmatory artifact.
5. Separate timestamp/data-availability preflight from outcome inspection when feasible.
6. Record seeds for stochastic controls/bootstrap/matching.
7. Do not hardcode a new threshold discovered from OOS into an old frozen run.
8. Add the experiment/result to `docs/RESEARCH_LEDGER.md`.

## Cleanup policy

A research script is safe to delete from the active tree only when all are true:

- no current/frozen run depends on it;
- no code imports it;
- its historical purpose/result is recorded;
- an immutable commit/tag preserves reproducibility;
- deletion does not erase the only executable description of a consumed experiment.

This is intentionally stricter than normal application-code cleanup because failed and one-off experiments are part of the research record.