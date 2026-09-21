# Signalbot Product Hypotheses — DEFERRED PARKING LOT

**Status:** `DEFERRED / NON-EXECUTABLE`.

Broad product implementation is frozen. A bounded comparison of the assisted-audit workflow against an ordinary notebook workflow is active research, not authorization to build a product UI or general platform.

Signal-product decisions remain gated by independent analytical validation. Assisted-audit continuation has a separate gate: an external claim owner must value the result and the workflow must save meaningful effort or catch additional material errors.

## H1 — Information compression

**Status:** `ACTIVE BOUNDED WORKFLOW TEST / UNVALIDATED PRODUCT`

Hypothesis: users may value reducing many market-data streams to a small amount of traceable decision-relevant context.

Open question: can Signalbot do this materially better than workflows built from charting/data tools plus general-purpose AI?

## H2 — Evidence / auditability

**Status:** `UNVALIDATED`

Hypothesis: some users may value inspectable evidence, counter-evidence, methodology, limitations and provenance rather than opaque AI scores.

Open question: across three comparable external cases, is this a real repeated user value and does it outperform a competent notebook workflow on effort or material-error detection?

## H3 — Historical contextualization / analogue analysis

**Status:** `UNVALIDATED`

Hypothesis: distributions from genuinely comparable historical states may be more useful than indicator interpretation alone.

Open question: can similarity/population definitions be made statistically defensible rather than pattern storytelling?

## H4 — Material market-change detection

**Status:** `UNVALIDATED`

Hypothesis: users may value alerts when the overall decision-relevant market state materially changes rather than one alert per metric.

## H5 — Trade-thesis red team

**Status:** `UNVALIDATED`

Hypothesis: a structured system that challenges a trade thesis and distinguishes quantified evidence from narrative may improve decisions.

## H6 — Conditional forecasting / NO-TRADE

**Status:** `ACTIVE_RESEARCH_THESIS`, not a validated product hypothesis.

Forecasting may be useful only in a minority of prospectively identifiable states. A correct system may output `NO EDGE / NO TRADE` most of the time.

Current research asks whether any such conditional edge exists and survives independent evidence.

## H7 — Regime-routed multiple edges

**Status:** `EXPLORATORY`

A future forecasting module may be better expressed as several simple mechanisms selected by a prospectively measurable regime rather than one universal directional strategy.

Example research shape only:

- trend/high-vol -> continuation candidate;
- range/failed move -> mean-reversion candidate;
- compression -> expansion candidate;
- unsupported regime -> no trade.

This is not authorization to build a regime router before the underlying mechanisms are validated.

## Deferred product/business questions

Do not answer these through brainstorming. Use owner-confirmed evidence where the bounded workflow test requires it:

- initial user segment;
- product wedge;
- moat versus TradingView/CoinGlass/exchange AI/general LLM workflows;
- free/paid/API/B2B model;
- monetization/pricing;
- UI/Telegram feature scope;
- broad asset coverage.

## Re-entry trigger

Signal-product hypotheses may be promoted only after analytical evidence. A bounded assisted-audit experiment may proceed under `CURRENT_RESEARCH_STATE.md`, but it does not authorize a general OS, autonomous discovery, UI build, pricing rollout, or signal-product expansion.
