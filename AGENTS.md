# Signalbot — Repository Instructions

This file tells coding/review agents what is authoritative **now**. Keep it concise and defer large research contracts to `docs/`.

## Project posture

Signalbot is currently in `RESEARCH_FIRST / PRODUCT_DEVELOPMENT_FROZEN` mode.

The active objective is to discover and independently validate one or two robust conditional market mechanisms — or reject the investigated hypotheses without post-hoc rescue. There is no current claim of durable trading edge.

V1 is frozen. V2 code is retained as research material, but V2 is **not** the active product-development roadmap.

## Read these sources first

For any new task, use this authority order:

1. `docs/PROJECT_STATUS.md` — current posture and freeze;
2. `docs/RESEARCH_ROADMAP.md` — active execution order;
3. `docs/EDGE_RESEARCH_PROTOCOL.md` — research/validation rules;
4. `docs/HISTORICAL_DATA_STRATEGY.md` — data evidence strategy;
5. `docs/RESEARCH_LEDGER.md` — consumed windows/hypothesis history;
6. `docs/PROJECT_RISK_AND_DEBT_REGISTER.md` — current open risks;
7. `docs/DOCUMENTATION_INDEX.md` — current vs historical docs.

For `E1-RUN-001`, also read its frozen preregistration and `docs/e1/` artifacts. Those historical research records remain authoritative for reproducing that experiment even when current project direction has changed.

Old `FORECASTING_ROADMAP`, Stage1/Stage2/V2 product/correctness documents are not current roadmap authority. See `docs/DOCUMENTATION_INDEX.md`.

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

Allowed work is research-supporting work: historical expansion, reproducible datasets, hypothesis tooling, baselines/controls, empirical evaluation, correctness fixes that protect evidence, and completion of already-frozen experiments.

## Research governance

Research must try to falsify hypotheses rather than protect the existing implementation.

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

## Scope discipline

- Make the smallest change that satisfies the active research task.
- Do not opportunistically resume product development.
- Do not merge/deploy unless explicitly authorized.
- Never commit `.env`, tokens, credentials, chat IDs, private keys or other secrets.
- Preserve failed/null research artifacts; remove stale planning text instead of rewriting historical evidence.
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
- report what validation actually ran;
- update `docs/DOCUMENTATION_INDEX.md` when documentation authority changes;
- update `docs/RESEARCH_LEDGER.md` when a research window/result/hypothesis is consumed.