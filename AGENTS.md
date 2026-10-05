# Signalbot — Repository Instructions

This file tells coding/review agents what is authoritative **now**. Keep it concise and defer large research contracts/history to `docs/`.

## Project posture

**Mode since 2026-10-03:** `PRODUCT_FIRST / DECISION_SUPPORT / NO_DIRECT_TRADE_CALLS`. The canonical product decision is `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md`: the owner lifted the predictive freeze for the product (forecasts of range, touch probabilities, levels, historical statistics with direction, an event calendar, timely market alerts) and opened Binance 2025/2026 for product statistics. Still forbidden in every user text: direct trade calls (buy/sell, long/short now, entries, targets), hype, unobservable attributions. Every historical number carries N and a comparable "обычно"; every forecast carries its tracked accuracy. Where it differs, it wins over the V1 decision below.

**Directional hypotheses for the bot (2026-10-04, `docs/research/DIRECTIONAL_HYPOTHESES_DECISION_V1.md`).** For program `DH1` only, the owner lets research target directional outcomes so the bot can state probabilities with a status.
- **Endpoints:** level hold 4h after a first touch; barrier first-passage ±X within 4h.
- **Bar:** 3 pp against "обычно" plus a positive Brier skill score.
- **Display:** «Проверено» needs a replicated result; «Гипотеза» is a discovery-only `PROMISING_PROTOTYPE`, labelled not confirmed.
- **Data:** discovery on Binance 2020–2024; confirmation on 2017–2019 (BitMEX trades plus Binance spot) and live tracking. No 2025/2026 objects, no paid data.
- **Rules:** contract V1 applies in full (`INCREMENTAL` claims); no direct trade calls; no deploy without a separate owner go.
- **DH3 (2026-10-04, `docs/research/DH3_RESULT.md`):** five cards of three (direction and range); two `PROMISING_PROTOTYPE` cells: P3 crowd positioning (−5.9 pp) and V3 retests (+3.9 pp, not repeated on 2017–2019). They appear as «Гипотеза» lines in `/research` only. DH3 is CLOSED (owner, 2026-10-04); P3 live tracking is not started.
- **Status (2026-10-04):** DH1 and DH2 (six coins pooled, `docs/research/DH2_POOLED_DESIGN.md`) each executed once. No cell moved a directional probability by 3 pp; nothing replicated; no probability line in the bot (`docs/research/DH1_RESULT.md`, `docs/research/DH2_RESULT.md`).

**Mode 2026-10-02 → 2026-10-03 (superseded where V2 differs):** `PRODUCT_FIRST / RESEARCH_SERVES_PRODUCT / PREDICTIVE_CLAIMS_FROZEN`. The canonical product decision is `docs/PRODUCT_FIRST_DECISION_V1.md`: the product hypothesis, the build-to-test MUST scope, the architectural constraint (one detector, one episodization, one context projection, one shared view builder, one outbox, one notifier), the DO-NOT-BUILD-YET list, the data/launch orientation and the 30-day user test. Research infrastructure is kept, but it no longer sets the pace of product work; no new research programs or one-shot confirmation units are started. Two evidence standards are kept apart: **product evidence** (honest descriptive/heuristic interpretation with uncertainty and provenance) and **research claim** (the existing research contract). "Do not lie" does not mean "do not interpret".

The research posture below is kept as the record of what is sealed and frozen. It is no longer the research-first routing of product work.

Signalbot was in `RESEARCH_FIRST / PRODUCT_BUILD_FROZEN` mode until 2026-10-02.

The synthetic Microscope V3 calibration is closed immutable historical evidence. `V3_METHODOLOGY_CLAIMABLE = NO`, `V3_RERUN_AUTHORIZED = NO`, and `DEFAULT_V4 = NO`. Do not repair/rerun V3 or treat its synthetic PASS cells as a robust market-edge claim.

The MARKET program is through MARKET-06:

- MARKET-01: `NO_EVIDENCE`;
- MARKET-02: `NO_EVIDENCE`;
- MARKET-03: `EXTERNAL_REPRODUCTION / REPRODUCED_DIRECTION` under its own historical contract, not a validated internal edge;
- MARKET-04 / 04H: `BLOCKED_OBSERVABLE / NOT_TESTED`, not rejected;
- MARKET-05: `MARKET_05_NO_EVIDENCE`;
- MARKET-06: `MARKET_06_NO_EVIDENCE`, canonical one-shot consumed and sealed; no rerun or reverse-effect rescue;
- internal historical candidates promoted: `0`;
- protected 2025/2026 OOS: not globally unopened; see the surface notes below (research: the divergence surface; product statistics: PRODUCT_DECISION_V2 §4).

The exact/near-exact M05/M06 cell (external/cross-market observable -> additive incremental term beside BTC own-state controls -> 24h direction-aligned adverse-path prediction -> holdout MAE improvement) is `REPEATED_NULL / LOW_PRIORITY_FOR_NOW`. The broader short-horizon BTC conditional scalar-prediction family is `LOW_PRIORITY / SATURATED_FOR_NOW` as a search-priority conclusion, not a claim that every member is false.

Do **not** create MARKET-07 merely to continue a queue. D2 / RULE_1 is an
`INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`, not a validated trading edge
and not a reason to restart product work. 2025/2026 status: see the surface notes below. The D2 excess direction-aligned path-risk decomposition one-shot
is consumed (`D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`; no
rerun). The exact next research unit is recorded in
`docs/CURRENT_RESEARCH_STATE.md`. Do not generate nearby D2
threshold/horizon/RV variants.
New discovery cards, if defined, must rotate across heterogeneous families
rather than proliferate RV_ABSTENTION.

**2025/2026 surface note (2026-10-02, `docs/research/DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3.md`).**
- **Opened.** The six-symbol Binance USD-M surface (BTC, ETH, SOL, BNB, DOGE and XRP: 1m klines, bookDepth and OI metrics) from 2025-01-01 to the exclusive read horizon 2026-08-15 was opened for the divergence/support research program.
- **Status.** It is no longer pristine OOS for hypotheses generated from divergence, support or mechanism research. It stays usable as previously exposed data for estimation and feasibility.
- **E1-RUN-001** stays protected and unopened: the holdout `[2026-08-16, 2026-08-25 17:20)`, and nothing at or after 2026-08-15 is read.
- **Everything else is unopened.** Other 2025/2026 venues, symbols and observables remain so, and all of 2025/2026 is not declared spent for unrelated families; that is decided per family.

**Divergence / selling-exhaustion line (2026-10-03).** `COMPLETED` and closed as an active research route.
- Do not start another divergence or exhaustion unit, SEED or prospective stream.
- Do not evaluate the archived `RSI_GRADIENT_SUPPORT_CANDIDATE`.
- Routing follows `PRODUCT_FIRST_DECISION_V1`.

**Product statistics (2026-10-03, `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §4).** The owner opened Binance USD-M BTCUSDT 2025/2026 5m klines and OI metrics for the product's decision-support statistics, up to yesterday, **except the E1-RUN-001 final holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)`**: the history sync never requests an archive object that overlaps it (object level, before any fetch) and never stores a row inside it. For research this BTC surface is consumed for hypotheses over the product features (range/volatility, levels, price/OI/taker states, event days); sealed verdicts are not reopened.

**Research Atlas (2026-10-03, `docs/research/SIGNALBOT_RESEARCH_ATLAS_V1.md`).** Research is chosen from one permanent map (Mechanism × Data surface × State), not from numbered campaigns.
- Never reopen a closed cell for a new threshold, window or horizon; a new branch needs a new mechanism or a new data surface (§5 reopen keys and forbidden moves).
- Generators read only `docs/research/atlas/ATLAS_GENERATOR_VIEW_V1.json`; the full view is for the owner, selector and critics.
- When a unit closes, add it to `docs/research/atlas/ATLAS_UNITS_V1.yaml` (and the surfaces' exposure ledger) in the same change and rebuild with `python -m scripts.research.atlas.build_atlas`; never hand-edit the derived files.
- Every change of the atlas sources appends a hash-chained event (`--append-event`); never rewrite `ATLAS_EVENTS_V1.jsonl`.
- The atlas is the authority for current routing; generator memory stays provenance. Where they differ, the reconciliation layer says why.
- Reserved confirmation surfaces (`reservations:`; today only the E1-RUN-001 holdout) are invisible to generation and need an explicit permit to consume.
- Atlas state changes reach the bot only as a reviewed findings-registry change, never automatically.
- A batch still needs its own owner go.

`FORWARD_MARKET_OBSERVABILITY_V1` collector implementation remains frozen; authoritative collection has not been started by this cleanup. B2-06 remains blocked on the missing/legally-timestamped observable problem.

There is still no claim of a durable trading edge.

A narrow **descriptive private beta V0.2** is authorized (`docs/PRIVATE_BETA_V0_RESTART_DECISION.md`). Since 2026-10-02 its implementation scope is the build-to-test MUST list of `docs/PRODUCT_FIRST_DECISION_V1.md` §3; `docs/BETA_V0_3_MARKET_BRIEFING.md` is superseded where the two differ (briefing episodes, 24h label, 90-day baselines, separate notifier).
- **Where it lives:** beta work belongs only in `beta/`, `runtime/beta_*`, `storage/beta_v0_*`, `config/beta_v0.yaml` and `deploy/signalbot-beta-*`.
- **What it must never do:** never a direct trade call (PRODUCT_DECISION_V2 §3), never V1/V2 forecast-engine changes, never a research claim without the research contract. Forecasting vocabulary is allowed since 2026-10-03.
- **V0.3 (2026-10-02):** the surface is a market briefing (`docs/BETA_V0_3_MARKET_BRIEFING.md`).
  - **One narrow exception to the predictive freeze:** outcome-aware historical analogue summaries, only under `docs/BETA_HISTORICAL_ANALOGUE_GATE_V1.md`. That means a baseline beside every number, N and spread, a mandatory verdict, separate historical and live cohorts, and no 2025/2026 data.
  - **Superseded 2026-10-03 by PRODUCT_DECISION_V2:** directional history, range forecasts and touch probabilities are allowed in the product; trade recommendations, targets and direct long/short calls stay forbidden.
- **Research ↔ bot (PRODUCT_DECISION_V2 §2.4).** `config/beta_research_findings.yaml` lists closed research units in trader language (confirmed, discovery-only, below the bar, not confirmed, side findings, underpowered). The bot shows one «Проверено: …» line in the matching context and the full list in `/research`.
  - **When a research unit closes,** add or update its entry in the same change: a text that states only what its record states, its own numbers, its record path, and the bot contexts it applies to (`pending_merge: true` while the record is on an unmerged branch; remove the flag when it merges).
  - Never turn a null into a trade call, never extend a result beyond its tested scope (D11 is FOMC only; C012 says nothing either way), and never edit a sealed record to fit a bot text.
  - **Live evidence (2026-10-04, `docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md`).** A finding with a `live:` block is matched on its exact frozen state from fresh data and worded by status (DISCOVERY never «Проверено»; NOT_CONFIRMED vetoes the same mechanism; UNDERPOWERED never live). The bot shows at most 2 such lines on a main surface and the full set in the «🔬 Исследования» tab. It never changes corridors, touch probabilities, forecasts or push gating; a model use is a MODEL_INTEGRATION_CANDIDATE for the owner. When a closed unit is live-relevant, add its `live:` block, its state function (with a parity test against the research code) and its cut points (frozen from the research surface, never recomputed live).

## Read these sources first

For any new task, use this authority order:

0. `docs/SIGNALBOT_MANDATE_V1.md` — owner-approved strategic mandate; project success criteria, anti-sycophancy rule, scientific/product/commercial principles. It does not override frozen experiment-specific scientific authorities;
0a. `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md` — canonical product decision (2026-10-03): decision support (corridor, levels, history, events, market alerts), the rules that stay, protected 2025/2026 opened for product use. Read it first for any product/beta task;
0b. `docs/PRODUCT_FIRST_DECISION_V1.md` — product decision of 2026-10-02 (hypothesis, architecture constraint, DO-NOT-BUILD-YET, user-test design); superseded where V2 differs;
0c. `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` — research decision (2026-10-05): evidence vs claim decision, L0–L4 ladder, design note before outcome, claim journal; read it before any new research unit or any product line that states a historical or probabilistic number;
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

Product work is allowed inside `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §2 and the build-to-test scope of `docs/PRODUCT_FIRST_DECISION_V1.md` §3, and never inside the still-forbidden items listed in V2 §3 (LLM in production, web UI, payments, multi-asset scanner, order book / liquidation heatmaps, exchange keys, a second detector engine). Research work follows `PRODUCT_FIRST_DECISION_V1.md` §1: small, feasibility-confirmed, product-serving only.

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

**Since 2026-10-05, new research units follow `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`.**
- **Before the outcome:** a one-page design note with the estimand, the method chosen by design (no universal estimator), the comparison, what would change our mind, and the variants tried.
- **Result:** reported as evidence: estimate, uncertainty, information, stability, falsification, limitations and search exposure. No verdict words.
- **What may be said:** a separate claim decision on the L0–L4 ladder.
  - L2 directional historical lines are quantitative: observed vs baseline, the difference, N and uncertainty.
  - A historical frequency is never stated as a current probability. L3 needs live calibration through the claim journal.
  - No uncalibrated weak/moderate/strong wording reaches users.
- **The compiler V3 variance line is CLOSED** (`docs/research/COMPILER_V3_VARIANCE_LINE_CLOSURE_V1.md`). Do not start Run 2, a variance or estimator calibration, compiler V3 or a ledger schema V2 for it. Feasibility numbers are amount-of-information fields, not a gate.
- **Contract V2 draft:** not adopted and superseded as the plan.
- **Contract V1** below keeps its force for every unit registered under it.

Hypothesis cards registered before 2026-10-05 are evaluated under `docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1.md` (adopted 2026-10-01, not retroactive). It covers:
- twin preregistration;
- the `CONTEXT_DESCRIPTIVE` and `INCREMENTAL` claim types;
- the nuisance baseline;
- the calibrated epoch-heterogeneity gate;
- time-disjoint or prospective replication with a fixed stopping rule;
- promotion rules.

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

Owner decision 2026-10-03 (`docs/research/PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.md`, Amendment 1): the P4 owner-run descriptive follow-up read live `klines_1m` / `open_interest` over the whole holdout interval. `E1_EVALUATOR_TOUCHED = NO`, `E1_SEALED_ARTIFACTS_OPENED = NO`, `E1_OUTCOME_SURFACE_OPENED_BY_P4 = YES`, `E1_PRISTINE_HOLDOUT_STATUS = INVALIDATED_FOR_P4_OVERLAP`. The E1 records are not rewritten and the rules above still apply.

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
