# Signalbot — Repository Instructions

This file tells coding/review agents what is authoritative **now**. Keep it concise and defer large research contracts/history to `docs/`.

## Project posture

Signalbot is currently in `RESEARCH_FIRST / PRODUCT_DEVELOPMENT_FROZEN` mode.

The synthetic Microscope calibration is closed (`V3_CALIBRATION_CLOSED = YES`). Canonical V3 is immutable historical evidence: confirmatory sensitivity was demonstrated on frozen synthetic `EASY`/`MODERATE`, but the methodology is not generally claimable (`NULL` `INDETERMINATE`, `NONSTATIONARY_TRAP` `FAIL`; `V3_METHODOLOGY_CLAIMABLE = NO`). Do not repair, rerun, or reinterpret V3 (`V3_RERUN_AUTHORIZED = NO`). Do not create V4 (`DEFAULT_V4 = NO`). V3 `DETECTED`/`PASS` is not by itself sufficient evidence of a robust market edge.

The active research phase is a **bounded MARKET + external-claim evaluation cycle**. MARKET-01 and MARKET-02 are closed `NO_EVIDENCE`; MARKET-03 is a limited historical reproduction under a materially different success contract; MARKET-05 is closed without promotion. Do not compare their labels as a public-vs-internal hypothesis success rate. The canonical routing table is `docs/CURRENT_RESEARCH_STATE.md`.

Do not design a large MARKET framework or create MARKET-07 merely to keep a queue moving. At most three active decision cards may exist. Progress is measured by useful prototypes, precise exclusions, changed research decisions, material errors caught, and total human effort—not hypotheses closed per week.

B2-06 remains blocked (`BLOCKED_MISSING_OBSERVABLE` / funding publication-latency unproven). `MARKET-01` is not B2-06 and does not unblock it.

The Microscope remains available as scientific instrumentation. It is not the active research program.

The current cycle has two separate objectives: (1) find useful decision-relevant prototypes and only then test novel incremental information where appropriate; (2) test whether Signalbot produces a more useful, reliable, or cheaper audit than a competent notebook workflow. There is no current claim of durable trading edge or comparative product value.

V1 is frozen. V2 code is retained as research material, but V2 is **not** the active product-development roadmap.

The repository intentionally preserves old plans, failed hypotheses and frozen contracts as project history. Historical presence is not current authorization.

## Read these sources first

For any new task, use this authority order:

1. `docs/CURRENT_RESEARCH_STATE.md` — branch-pinned current routing and bounded cycle;
2. `docs/PROJECT_STATUS.md` — current posture and freeze;
3. `docs/RESEARCH_ROADMAP.md` — active execution order;
4. `docs/EDGE_RESEARCH_PROTOCOL.md` — research/validation rules;
5. `docs/HISTORICAL_DATA_STRATEGY.md` — data evidence strategy;
6. `docs/ACTIVE_RESEARCH_RISKS.md` — current inference risks;
7. `docs/RESEARCH_LEDGER.md` — consumed windows/hypothesis history;
8. `docs/DOCUMENTATION_INDEX.md` — current vs frozen/historical docs;
9. `docs/PROJECT_HISTORY.md` — why the project evolved into the current posture.

For `E1-RUN-001`, also read its frozen preregistration and `docs/e1/` artifacts. Those research records remain authoritative for reproducing that experiment even when current project direction has changed.

Old `FORECASTING_ROADMAP`, Stage1/Stage2/V2 product/correctness documents are historical/frozen references, not current roadmap authority. See `docs/DOCUMENTATION_INDEX.md`.

## Hard development freeze

Unless a task explicitly changes the project posture, do not build:

- Stage 6+ lifecycle/product work;
- new production setup families;
- new production thresholds/scoring/confidence systems;
- ML/adaptive tuning;
- product Telegram/UI features unrelated to research;
- V2 production enable/deploy;
- speculative generic frameworks;
- new data/features merely to rescue weak results.

Allowed work is research-supporting work: the three slots in `CURRENT_RESEARCH_STATE.md`; historical expansion tied to a discriminating question; reproducible datasets; baselines/controls; empirical evaluation; correctness fixes that protect evidence; and completion of already-frozen experiments. Infrastructure is in-scope only when a concrete research blocker requires it. Do not repair/rerun V3, create V4, execute B2-06, or treat V3 `DETECTED`/`PASS` as a robust market-edge claim. Do not ARM MARKET-06 until the preregistered matrix-rank predicate exists in the frozen implementation and the affected surface is reviewed.

## Research governance

Research must try to falsify hypotheses rather than protect the existing implementation.

Separate prototype utility from novel incremental-information claims. A study failure must be classified as `PRECISE_NEGATIVE`, `UNRESOLVED`, or `INVALID`; do not let a failed promotion gate silently become a claim that the whole mechanism is false.

Rules:

- engineering correctness != predictive validity;
- threshold/parameter search is allowed on development data;
- validation/OOS that influences a rule change becomes consumed;
- do not tune against the same OOS and still call it untouched;
- prefer stable parameter plateaus/monotonic score-outcome relationships over isolated optima;
- track material search surface / repeated variants;
- simple baselines and negative controls are mandatory for edge claims;
- report clustering/effective N, regime concentration and missingness;
- `NO EDGE`, `REJECTED`, `INCONCLUSIVE_SAMPLE` are valid outcomes;
- a failed hypothesis may be replaced by a new version/hypothesis, but never retroactively rescued inside the old confirmatory run.

## Historical data rules

Do not let the youngest/richest source constrain every research question.

Use long-history CORE datasets to test mechanisms and shorter RICH overlap datasets to test incremental feature value.

Preserve:

- no lookahead/as-of semantics;
- source/provider granularity;
- explicit evidence tiers;
- gap/missingness denominators;
- deterministic dataset/version provenance.

Never turn 5m source observations into genuine 1m information by forward-fill/resampling.

## E1-RUN-001 load-bearing rule

`E1-RUN-001` remains frozen until completed or explicitly closed as technically incomplete.

Do not change its:

- TP/CB/FB definitions;
- thresholds/directions;
- horizons;
- ablation/control definitions;
- delay/cost grid;
- holdout split;
- verdict criteria.

The final holdout may be opened only by its frozen one-shot evaluator after the timestamp-only coverage gate passes. Correctness fixes require explicit documentation and may not be motivated by observed holdout metrics.

## V3 Microscope load-bearing rule

Canonical V3 is closed immutable historical evidence. Do not change V3 scientific code, prereg, WORLD_RECORDS, or RESULT. Do not repair, rerun, or reinterpret V3. Do not create V4. `V3_CALIBRATION_CLOSED = YES`. `V3_METHODOLOGY_CLAIMABLE = NO`. `V3_RERUN_AUTHORIZED = NO`. `DEFAULT_V4 = NO`.

## History-preservation rule

Do not “clean” the repository by erasing meaningful failed/superseded work.

Preserve historically meaningful material when it documents:

- an earlier project thesis;
- a frozen model/contract;
- an experiment/preregistration/result;
- a failed/null hypothesis;
- a reason for a strategic pivot.

Cleanup should remove **ambiguity and duplication**, not evidence of how the project learned.

When an old active document is shortened into a superseded pointer, ensure its role is covered by `docs/PROJECT_HISTORY.md` and/or an immutable git reference.

## Scope discipline

- Make the smallest change that satisfies the active research task.
- Do not opportunistically resume product development.
- Do not merge/deploy unless explicitly authorized.
- Never commit `.env`, tokens, credentials, chat IDs, private keys or other secrets.
- Preserve failed/null research artifacts; remove stale planning authority instead of rewriting historical evidence.
- When current and historical docs disagree about present execution, current status/roadmap wins. When reproducing a historical experiment, its frozen contract wins.

## Core correctness invariants

- decision boundary `T` may only use information available as-of `T`;
- exact timeframe-aligned bucket identity matters;
- missing/immature data differs from malformed/corrupt data;
- do not silently fall back across windows/versions/symbols/market types;
- preserve deterministic replay/provenance;
- preserve raw-data no-downgrade behavior;
- presentation/LLM/Telegram wording is downstream of structured analytical truth.

## Tests and validation

CI uses Python 3.11 with `requirements-dev.txt`.

Default code validation when feasible:

```bash
python -m compileall -q .
python -m pytest -q
git diff --check
```

Use focused tests first. If a real PostgreSQL behavior is relevant, a skipped integration test is not proof of correctness.

For docs-only changes, inspect references and `git diff --check`; do not fabricate test/CI results that were not run.

## Before finishing

- inspect final diff for accidental product-scope expansion;
- confirm V2 remains disabled unless explicitly authorized;
- confirm frozen experiments were not semantically changed;
- confirm canonical V3 WORLD_RECORDS/RESULT bytes were not modified;
- report what validation actually ran;
- update `docs/DOCUMENTATION_INDEX.md` when documentation authority changes;
- update `docs/RESEARCH_LEDGER.md` when a research window/result/hypothesis is consumed;
- update `docs/PROJECT_HISTORY.md` when a major project-level philosophy/direction change occurs.
