# Signalbot

Signalbot is a crypto-market research and decision-support project focused on discovering **traceable, empirically validated market structure** before building product complexity around it.

> **Current mode: `RESEARCH_FIRST / DESCRIPTIVE_PRIVATE_BETA_V0_AUTHORIZED / PREDICTIVE_PRODUCT_FROZEN`.**
> Research comes first. A narrow, descriptive-only private beta is authorized. Predictive product and forecasting architecture stay frozen until an edge is independently validated.

**Signalbot has no validated trading edge.** Nothing in this repository establishes direction prediction, profitability or a durable market edge.

For "where are we now?", start with [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md).

## Current objective

The active objective is not “finish V2”. It is:

> **Discover and independently validate one or two robust conditional market mechanisms — or reject them without post-hoc rescue.**

Engineering exists to support that research. The owner-approved mandate is [`docs/SIGNALBOT_MANDATE_V1.md`](docs/SIGNALBOT_MANDATE_V1.md).

## High-level pipeline

1. **Ingestion.** Multi-exchange market data: Binance, Bybit and OKX perpetuals, with klines, open interest, taker flow and liquidations.
2. **Storage.** TimescaleDB with no-downgrade raw data, as-of semantics and provenance.
3. **Features.** Stage 2 feature materialization under a versioned `calculation_version`.
4. **Research.** Reproducible historical datasets, preregistered one-shot tests, the Generator V0 hypothesis generator and the outcome-blind feasibility compiler.
5. **Descriptive beta.** The 5m state tape feeds the `BETA_EVENT_RULES_V1` detector episodes. Their descriptive forward outcomes are shown in the Telegram `/btc` view.

## Private beta scope

The descriptive private beta V0.2 is authorized by [`docs/PRIVATE_BETA_V0_RESTART_DECISION.md`](docs/PRIVATE_BETA_V0_RESTART_DECISION.md). It covers BTCUSDT perpetuals on Binance, Bybit and OKX, runs on Telegram and is capped at 20 users.
- **What it does:** describes market states only. It makes no predictions, gives no trade instructions and claims no edge.
- **Where its code lives:** only in `beta/`, `runtime/beta_*`, `storage/beta_v0_*`, `config/beta_v0.yaml` and `deploy/signalbot-beta-*`.
- **Research boundary:** beta events are not hypotheses, and beta outcomes are not confirmation.

## Validation status

- **Validated trading edges:** none. Internal historical candidates promoted: `0`.
- **Where the research program stands:** MARKET-01 through MARKET-06 and Discovery Sprints 01–04 have closed. Several "promising prototype" results are discovery-tier only. D2 is a replicated mechanism *candidate*, not an edge.
- **Beta PRICE_OI_CONTRACTION history:** the historical follow-up figures are **descriptive only**. Their matched-baseline design has known defects and is not valid evidence. See [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md).
- **Protected data:** Binance 2025/2026 remain sealed.

## Where the project stands

### Data/platform foundation

The repository already contains substantial reusable infrastructure:

- multi-exchange market-data ingestion;
- TimescaleDB/Redis storage;
- historical backfill and validation tooling;
- closed-bucket/no-lookahead alignment primitives;
- version/provenance identity;
- Stage 2 feature materialization;
- replay/research tooling;
- frozen V1/V2 analytical code.

These assets are retained. The development freeze does **not** mean rebuilding from scratch.

### V1

V1 is a frozen research baseline. Its autopsy showed a high-churn reactive 5m momentum/continuation classifier with weak evidence of future predictive ordering and material notification lateness.

V1 is not an active product-development target.

### V2 / E1-RUN-001

V2 Stage-5 contains three frozen detector families:

- `TREND_PULLBACK`
- `COMPRESSION_BREAKOUT`
- `CONFIRMED_BREAKOUT`

`E1-RUN-001` is the current frozen detector-separation experiment. Development evidence has been consumed; the chronological holdout remains unopened as of the last verified state. The holdout populations reproduced exactly (`TP=105`, `CB=17`, `FB=19`), and the one-shot final evaluator is frozen.

Do not infer a final E1 verdict until that evaluator is actually run.

## Why the project changed direction

Signalbot did not begin as a “research-only” repository. It progressed through a data-platform phase, V1 shadow forecasting, a much more formal V2 multi-timeframe architecture, and then an empirical red-team phase.

The direction changed because engineering correctness and architectural sophistication were advancing faster than evidence of persistent predictive edge. E1 development results also weakened several V2 assumptions, while the richest historical overlap proved too short to support durable claims across market regimes.

The old work is **not erased**. Failed hypotheses, superseded plans and frozen contracts are preserved because they explain what the project learned.

Read [`docs/PROJECT_HISTORY.md`](docs/PROJECT_HISTORY.md) for the narrative evolution: original idea → Stage 1 → V1 → V2 → E1 → research-first pivot.

For the full historical source material, use [`docs/history/README.md`](docs/history/README.md), which links directly to immutable versions of the original roadmaps/contracts/specifications.

## Active work

Allowed work during research-first mode:

- finish already-frozen E1 without changing its rules;
- expand historical data coverage to multiple years/regimes;
- build reproducible CORE/RICH research datasets;
- formulate mechanism-first hypotheses;
- tune thresholds/parameters on development data only;
- compare simple baselines and negative controls;
- run chronological validation/OOS/walk-forward studies;
- measure regime dependence, clustering/effective N, missingness, delay and costs;
- test richer derivatives/cross-venue features only for incremental value after a simpler core mechanism earns evidence.

## Frozen work

Do not continue by default:

- Stage 6+ lifecycle/product implementation;
- new production signal families;
- ML/adaptive tuning;
- product Telegram/UI expansion beyond the authorized descriptive beta;
- production V2 enable/deploy;
- speculative architecture/framework work;
- feature accumulation to rescue weak backtests;
- monetization/business expansion before the research gate is satisfied.

## Research philosophy

A favorable backtest is not enough.

Signalbot explicitly accepts:

- `NO EDGE`;
- `INSUFFICIENT DATA`;
- `REJECTED` hypotheses;
- simplifying or killing previously built logic.

Threshold optimization is allowed during development research. Repeatedly viewing OOS and retuning against it is not.

A one-month rich-data overlap can falsify obvious hypotheses but cannot establish durability across regimes. The new data strategy therefore separates multi-year **CORE** mechanism evidence from shorter **RICH** incremental-feature evidence.

## Documentation map

### What is true now

The authority order is defined in [`AGENTS.md`](AGENTS.md). In short:

0. [`docs/SIGNALBOT_MANDATE_V1.md`](docs/SIGNALBOT_MANDATE_V1.md) — owner-approved strategic mandate;
1. [`docs/CURRENT_RESEARCH_STATE.md`](docs/CURRENT_RESEARCH_STATE.md) — canonical routing and exact next research unit;
2. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — current posture and development freeze;
3. [`docs/RESEARCH_ROADMAP.md`](docs/RESEARCH_ROADMAP.md) — active execution order;
4. [`docs/EDGE_RESEARCH_PROTOCOL.md`](docs/EDGE_RESEARCH_PROTOCOL.md) — discovery/validation rules;
5. [`docs/HISTORICAL_DATA_STRATEGY.md`](docs/HISTORICAL_DATA_STRATEGY.md) — multi-year evidence strategy;
6. [`docs/ACTIVE_RESEARCH_RISKS.md`](docs/ACTIVE_RESEARCH_RISKS.md) — risks that can invalidate current research;
7. [`docs/RESEARCH_LEDGER.md`](docs/RESEARCH_LEDGER.md) — experiments, hypotheses and consumed windows.

Also useful:
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) — a short human summary that points into the documents above;
- [`docs/PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md`](docs/PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md) — evidence-first design philosophy;
- [`docs/CODEBASE_STATUS.md`](docs/CODEBASE_STATUS.md) — active/frozen/deferred code surfaces.

### How the project got here

- [`docs/PROJECT_HISTORY.md`](docs/PROJECT_HISTORY.md) — narrative evolution of ideas/philosophy;
- [`docs/history/README.md`](docs/history/README.md) — browsable immutable archive of original historical documents;
- [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md) — classification of active, frozen, historical and superseded documents.

Historical Stage1/Stage2/V2 contracts remain useful for code archaeology and frozen experiment provenance, but they are **not the active project roadmap**.

## Repository structure

```text
analytics/          analytical engines and V1/V2 research code
backfill/           historical acquisition/backfill tooling
beta/               descriptive private beta V0.2 (state tape, detector, outcomes, delivery)
common/             shared config/versioning/logging primitives
config/             runtime/model configuration
data_ingestion/     live exchange ingestion
deploy/             operational deployment examples
docs/               current strategy + frozen/historical research records
notifications/      notification infrastructure
runtime/            CLI/runtime entry points (shadow, Telegram, beta_*)
scripts/research/   reproducible research/audit tools
storage/            TimescaleDB schema/read/write/replay support
tests/              correctness/regression tests
```

## Local engineering setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# local infrastructure when required
docker compose up -d

# baseline validation
python -m compileall -q .
python -m pytest -q
```

Operational/research commands are documented in the relevant runbooks. Do not treat an old deployment guide as authorization to enable V2 or resume product development.

## Core invariants

Regardless of research direction:

- no lookahead;
- exact timestamp/bucket identity;
- explicit missingness rather than fabricated zeros;
- deterministic replay/provenance;
- historical source granularity must not be upgraded by resampling;
- engineering correctness and predictive evidence are separate;
- a complicated model must earn its complexity against simple controls.

## Restart condition

Predictive product architecture resumes only after a candidate edge earns independent validation under [`docs/EDGE_RESEARCH_PROTOCOL.md`](docs/EDGE_RESEARCH_PROTOCOL.md).

At that point the old Stage 6–10 plan is **not automatically resumed**. Architecture should be redesigned around the behavior and requirements of what the data actually validated.
