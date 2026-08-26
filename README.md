# Signalbot

Signalbot is a crypto-market research and decision-support project focused on discovering **traceable, empirically validated market structure** before building product complexity around it.

> **Current mode (2026-08-26): `RESEARCH_FIRST / PRODUCT_DEVELOPMENT_FROZEN`.**  
> Further forecasting/product architecture work is frozen until at least one market edge is independently validated, or the investigated hypothesis classes are convincingly falsified.

There is currently **no claim that Signalbot has a durable trading edge**.

## Current objective

The active objective is not “finish V2”. It is:

> **Discover and independently validate one or two robust conditional market mechanisms — or reject them without post-hoc rescue.**

Engineering exists to support that research.

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
- product Telegram/UI expansion;
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

## Canonical documentation

Start here:

1. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — current status and development freeze;
2. [`docs/RESEARCH_ROADMAP.md`](docs/RESEARCH_ROADMAP.md) — active execution order;
3. [`docs/EDGE_RESEARCH_PROTOCOL.md`](docs/EDGE_RESEARCH_PROTOCOL.md) — discovery/validation rules;
4. [`docs/HISTORICAL_DATA_STRATEGY.md`](docs/HISTORICAL_DATA_STRATEGY.md) — multi-year evidence strategy;
5. [`docs/RESEARCH_LEDGER.md`](docs/RESEARCH_LEDGER.md) — experiment history/consumed windows;
6. [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md) — current vs historical documents.

Historical Stage1/Stage2/V2 contracts remain useful for code archaeology and frozen experiment provenance, but they are **not the active project roadmap**.

## Repository structure

```text
analytics/          analytical engines and V1/V2 research code
backfill/           historical acquisition/backfill tooling
common/             shared config/versioning/logging primitives
config/             runtime/model configuration
data_ingestion/     live exchange ingestion
deploy/             operational deployment examples
docs/               current strategy + frozen/historical research records
notifications/      notification infrastructure
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

Product architecture resumes only after a candidate edge earns independent validation under [`docs/EDGE_RESEARCH_PROTOCOL.md`](docs/EDGE_RESEARCH_PROTOCOL.md).

At that point the old Stage 6–10 plan is **not automatically resumed**. Architecture should be redesigned around the behavior and requirements of what the data actually validated.