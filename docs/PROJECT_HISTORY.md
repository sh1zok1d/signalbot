# Signalbot — Project History and Evolution

**Purpose:** preserve how the project, hypotheses and engineering philosophy evolved without allowing historical plans to masquerade as current execution authority.

This document is intentionally narrative. It records *why* the project changed direction, not only what code exists today.

For current execution, read `docs/PROJECT_STATUS.md` and `docs/RESEARCH_ROADMAP.md` first.

---

## 1. Origin — market-information compression and decision support

Signalbot began from a practical problem: crypto market decisions require repeatedly checking price structure, exchange data, derivatives metrics and context across several tools. The original ambition was broader than a single trading formula: reduce a large market-information stream into a small amount of traceable, decision-relevant information.

Forecasting became the first concrete analytical engine because it provided a falsifiable target: can the system identify market states that change the distribution of future outcomes?

The project was never intended to win by reproducing every feature of TradingView, CoinGlass, exchange-native AI or a general-purpose LLM. The intended long-term value was a narrower decision-support capability whose usefulness would need to be demonstrated empirically.

---

## 2. Stage 1 — data foundation

The first implementation stage focused on ingestion and storage rather than prediction.

The project built:

- 1m market-data ingestion;
- REST backfill;
- TimescaleDB/Redis storage;
- multi-exchange normalization;
- connectivity/coverage handling;
- missing-data/fail-closed semantics;
- deterministic historical processing foundations.

The initial topology included Binance, Bybit, OKX and Bitget. The practical active topology later became Binance/Bybit/OKX, while Bitget code/data support was retained but disabled.

### Philosophy at this stage

The central belief was correct and remains active today:

> Data provenance, temporal correctness and honest missingness are prerequisites for any later analytical claim.

The mistake was not Stage 1 itself. The later mistake was allowing engineering maturity to progress faster than evidence that the forecasting hypotheses were useful.

Historical records from this period include `docs/STAGE1_ACCEPTANCE.md`, `docs/STAGE2_SPEC.md`, `docs/STAGE2_CLARIFICATIONS.md`, `docs/STAGE2_DATA_AUDIT.md` and `docs/STAGE2_IMPLEMENTATION_PLAN.md`.

---

## 3. V1 — single-bucket shadow forecasting

The first forecasting system, later called **V1**, operated primarily on one closed 5m market state. Price momentum, taker flow, OI, funding, liquidations and cross-exchange agreement were combined into a directional LONG/SHORT shadow output. The nominal 15m/1h/4h values were future outcome horizons, not independent multi-timeframe inputs.

V1 was useful as an engineering baseline because it proved that the system could:

- create deterministic analytical outputs;
- persist/version them;
- operate in shadow mode;
- handle real market-data availability;
- generate enough observations for an empirical autopsy.

### What the V1 autopsy showed

The later Telegram/export analysis changed the interpretation of V1 materially:

- the system generated signals almost continuously;
- adjacent-direction flipping was high;
- raw signal count overstated effective evidence because many rows represented the same underlying market episode;
- the signal aligned strongly with *past* 5m momentum but only weakly with future returns;
- confidence largely tracked score magnitude rather than demonstrated future-outcome quality;
- notification timing was roughly one extra 5m cycle late, consuming much of any very-short continuation.

The resulting interpretation was:

> V1 was mainly a reactive 5m momentum/continuation state classifier that had been treated as a longer-horizon forecasting product.

This did **not** prove that forecasting was impossible or that derivatives data were useless. It did prove that more components and a stronger-looking score were not evidence of predictive edge.

### Consequence

V1 was frozen as a research baseline rather than continuously tuned.

---

## 4. V2 — multi-timeframe architecture hypothesis

The next direction, **V2**, attempted to separate market roles by timeframe:

- 4h regime;
- 1h directional bias;
- 15m setup;
- 5m trigger.

Three initial setup families were defined:

- `TREND_PULLBACK` (TP);
- `COMPRESSION_BREAKOUT` (CB);
- `CONFIRMED_BREAKOUT` (FB).

A formal lifecycle was planned around states such as EARLY_SIGNAL, CONFIRMED, WEAKENING, INVALIDATED, REVERSAL_CANDIDATE, EXPIRED and COMPLETED.

This period produced substantial correctness infrastructure: deterministic alignment, versioning, provenance, replay semantics, persistence contracts, historical instrument metadata and publication/coherence controls.

### Philosophy at this stage

The project had moved toward a belief that a carefully specified multi-timeframe architecture could solve weaknesses observed in V1.

That belief was explicitly treated as a hypothesis rather than a fact, but implementation work still accumulated faster than decisive empirical evidence.

The legacy documents `docs/FORECASTING_ROADMAP.md`, `docs/V2_PRODUCT_CONTRACT.md`, `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` and related V2 audits/contracts preserve this design phase. They remain important for reproducing V2-v0 semantics, but they no longer define current project direction.

---

## 5. Empirical red-team shift — correctness is not edge

As V2 became more formal, the project adopted a stronger distinction between two questions:

1. **Is the system implemented correctly?**
2. **Does the market hypothesis contain incremental predictive information?**

This led to the evidence ladder and adversarial research posture reflected in `docs/V2_EMPIRICAL_RED_TEAM_PLAN.md`, `docs/RESEARCH_LEDGER.md` and later E1 preregistration.

Important principles established here remain permanent:

- no-lookahead is mandatory but does not imply alpha;
- simple baselines are mandatory;
- negative controls are mandatory;
- repeated 5m rows cannot be treated as iid evidence;
- OOS windows are consumed once inspected;
- failed hypotheses must remain visible;
- weak evidence must not trigger automatic feature/ML expansion.

This was the philosophical transition from **build a forecasting architecture and then evaluate it** toward **make every layer earn its complexity empirically**.

---

## 6. E1-RUN-001 — detector separation before more architecture

Before continuing into the planned Stage-6 lifecycle, the project paused implementation and asked a cheaper question:

> Do the frozen Stage-5 detectors alter future outcome distributions at all relative to simple/matched controls?

This became `E1-RUN-001`.

The experiment froze candidate generation before outcome inspection, used a chronological development/holdout split and added controls/ablations before the holdout was opened.

### Development evidence

Development evidence materially weakened the original V2 story:

- **TP:** the 4h/1h context stack selected a worse longer-horizon subset than several simpler populations. Full MTF complexity had not earned its place.
- **CB:** compression retained some structural selection value relative to an ordinary range breakout, but taker/context contributed little demonstrated incremental value and directional edge remained uncertain.
- **FB:** frozen breakout-continuation direction was adverse across development horizons; removing context did not rescue it. It became a strong kill candidate.

This was the first strong empirical reason to stop treating further V2 architecture as the default next step.

### Holdout discipline

The untouched holdout population reproduced exactly (`TP=105`, `CB=17`, `FB=19`). A one-shot final evaluator, ablation rules, matched controls, inversion, time shift, delay/cost stress and uncertainty reporting were frozen before opening outcomes.

At the time of the research-first pivot, the holdout had not yet been opened. This is important: the later strategic change was motivated by development evidence and sample-horizon limitations, not by changing rules after seeing final OOS results.

The full experiment record lives in `docs/E1_DETECTOR_SEPARATION_PREREG.md` and `docs/e1/`.

---

## 7. Why one month of rich history became a project-level blocker

The E1 work exposed a deeper limitation: the richest fully overlapping historical dataset covered only roughly one month.

A month can be useful to:

- expose obvious failure;
- debug causal/lookahead assumptions;
- compare candidate structures;
- generate new hypotheses.

It is not enough to establish durable edge across materially different bull, bear, high-volatility, low-volatility and choppy regimes.

The July–August 2026 period itself illustrated the problem: much of the window was unusually quiet before a large volatility/trend transition around 19 August. Any conclusion based on one localized regime mixture would be fragile.

This led to a key data-design insight:

> The shortest rich-feature overlap should not determine the evidence horizon for the underlying market mechanism.

The project therefore separates future research into:

- **CORE history:** multi-year price/volume/flow/funding/OI data where semantics are defensible;
- **RICH overlap:** shorter liquidation/cross-exchange/richer-derivatives data used to test incremental value after a simpler mechanism has earned credibility.

---

## 8. 2026-08-26 research-first pivot

The project formally froze further product/forecasting architecture development.

The new order is:

`DATA -> HYPOTHESIS -> FALSIFICATION -> DEVELOPMENT -> FREEZE -> OOS -> EDGE -> ARCHITECTURE -> PRODUCT`

instead of:

`ARCHITECTURE -> MORE FEATURES -> MORE ARCHITECTURE -> EVENTUAL EDGE TEST`.

### What changed

The immediate objective is no longer “finish V2 Stage 6–10.”

It is:

> discover and independently validate one or two market mechanisms with stable conditional expectation — or honestly conclude that the investigated hypothesis classes have not demonstrated one.

The project is explicitly allowed to return `NO EDGE`, `REJECTED` or `INSUFFICIENT DATA`.

Thresholds and parameters may be optimized on declared development data. They become invalid as confirmatory evidence only when the same validation/OOS data are repeatedly used to tune them.

Regime-specific strategies are allowed, but regime dependence must itself become a frozen prospectively validated rule rather than a post-hoc excuse.

### What did not change

The earlier work is not considered wasted.

The reusable foundation remains valuable:

- ingestion/storage;
- temporal alignment;
- no-lookahead controls;
- versioning/provenance;
- replay/research tooling;
- deterministic candidate generation;
- data-quality handling;
- empirical governance practices.

V1 and V2 remain historical research engines and baselines. They are not deleted and their failed/weak hypotheses are not erased.

---

## 9. Current philosophy

Signalbot now follows five project-level rules:

1. **Evidence before architecture.** No production component is justified because it is elegant or was already planned.
2. **Mechanism before complexity.** Start from the simplest plausible market mechanism and make every feature/gate earn incremental value.
3. **History before confidence.** A favorable month is not durable alpha; multiple regimes and chronological validation matter more than raw row count.
4. **Failure is retained.** Rejected hypotheses remain documented because they define what the project has already learned.
5. **Architecture follows validated behavior.** Lifecycle, regime routing, risk logic, explanations and UX are redesigned later around whatever edge actually survives.

---

## 10. How to read the repository historically

Use `docs/DOCUMENTATION_INDEX.md` to distinguish current and historical documents.

Suggested historical path:

1. `docs/STAGE1_ACCEPTANCE.md` — data-platform origin;
2. `docs/STAGE2_SPEC.md` / `docs/STAGE2_CLARIFICATIONS.md` — early feature/percentile formalization;
3. V1 code and forecasting history in git;
4. `docs/FORECASTING_ROADMAP.md` — original V2 build-out thesis;
5. `docs/V2_PRODUCT_CONTRACT.md` and `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` — formal V2-v0 semantics;
6. `docs/V2_EMPIRICAL_RED_TEAM_PLAN.md` — shift toward falsification;
7. `docs/E1_DETECTOR_SEPARATION_PREREG.md` + `docs/e1/` — first detector-level empirical gate;
8. `docs/PROJECT_STATUS.md` + `docs/RESEARCH_ROADMAP.md` — current research-first direction.

The value of this history is not that every past idea was correct. It shows how each layer of evidence changed what the project believed and therefore what it chose to build next.
