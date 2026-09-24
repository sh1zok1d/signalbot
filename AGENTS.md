# Signalbot — Repository Instructions

This file tells coding/review agents what is authoritative **now**. Keep it concise and defer large research contracts/history to `docs/`.

## Project posture

Signalbot is currently in `RESEARCH_FIRST / PRODUCT_BUILD_FROZEN` mode.

The synthetic Microscope V3 calibration is closed immutable historical evidence. `V3_METHODOLOGY_CLAIMABLE = NO`, `V3_RERUN_AUTHORIZED = NO`, and `DEFAULT_V4 = NO`. Do not repair/rerun V3 or treat its synthetic PASS cells as a robust market-edge claim.

The MARKET program is through MARKET-06:

- MARKET-01: `NO_EVIDENCE`;
- MARKET-02: `NO_EVIDENCE`;
- MARKET-03: `EXTERNAL_REPRODUCTION / REPRODUCED_DIRECTION` under its own historical contract, not a validated internal edge;
- MARKET-04 / 04H: `BLOCKED_OBSERVABLE / NOT_TESTED`, not rejected;
- MARKET-05: `MARKET_05_NO_EVIDENCE`;
- MARKET-06: `MARKET_06_NO_EVIDENCE`, canonical one-shot consumed and sealed; no rerun or reverse-effect rescue;
- internal historical candidates promoted: `0`;
- protected 2025/2026 OOS: unopened.

The exact/near-exact M05/M06 cell (external/cross-market observable -> additive incremental term beside BTC own-state controls -> 24h direction-aligned adverse-path prediction -> holdout MAE improvement) is `REPEATED_NULL / LOW_PRIORITY_FOR_NOW`. The broader short-horizon BTC conditional scalar-prediction family is `LOW_PRIORITY / SATURATED_FOR_NOW` as a search-priority conclusion, not a claim that every member is false.

Do **not** create MARKET-07 merely to continue a queue. D2 / RULE_1 is an
`INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`, not a validated trading edge
and not a reason to restart product work. Protected Binance 2025/2026 remain
sealed. The next research unit is
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`
(implementation and outcome-blind review of the frozen decomposition
design). Do not generate nearby D2 threshold/horizon/RV variants.
New discovery cards, if defined, must rotate across heterogeneous families
rather than proliferate RV_ABSTENTION.

`FORWARD_MARKET_OBSERVABILITY_V1` collector implementation remains frozen; authoritative collection has not been started by this cleanup. B2-06 remains blocked on the missing/legally-timestamped observable problem.

There is still no claim of a durable trading edge.

## Read these sources first

For any new task, use this authority order:

0. `docs/SIGNALBOT_MANDATE_V1.md` — owner-approved strategic mandate; project success criteria, anti-sycophancy rule, scientific/product/commercial principles. It does not override frozen experiment-specific scientific authorities;
1. `docs/CURRENT_RESEARCH_STATE.md` — compact current routing and exact next unit;
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

## Generator V0 live-provider runtime protocol

Before any Generator V0 live-provider, smoke, calibration, paid-LLM, or first full campaign task, read and follow `docs/AGENT_RUNTIME_PROTOCOL.md`.

For the first full Generator V0 campaign, `docs/research/GENERATOR_V0_FIRST_30_CARD_ARCHITECTURE_FREEZE.md` is the active operational architecture authority. It does not override frozen scientific contracts or protected-data rules.

Generator V0 mechanism memory is an append-only event chain (`docs/research/generator_v0_memory/`, see `docs/research/GENERATOR_V0_MEMORY_FINALIZER.md`). After a completed campaign, ingest it only with `python -m scripts.research.generator_v0.finalize_memory` (dry-run, then apply, then verify). Never hand-edit `MECHANISM_MEMORY_V0.json`, `BLIND_MECHANISM_MAP_V0.json`, `GOVERNANCE_REGION_AUTHORITY_V0.json` or the context pins: they are derived caches of the chain. Finalization never edits `HYPOTHESIS_GENERATOR_V0_DESIGN.json`, and the blind generator projection must stay outcome-neutral.

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

Allowed work is research-supporting work: MARKET hypothesis formulation and honest closeout through the existing process; historical expansion; reproducible datasets; hypothesis tooling; baselines/controls; empirical evaluation; correctness fixes that protect evidence; and completion of already-frozen experiments. Infrastructure is in-scope only when a concrete research blocker requires it. Do not repair/rerun V3, create V4, execute B2-06, or treat V3 `DETECTED`/`PASS` as a robust market-edge claim.

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
