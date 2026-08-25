# Signalbot Product Hypotheses — Parking Lot

> A deliberately non-executable list of future product hypotheses. Recording an idea here prevents it from being lost; it does **not** authorize implementation, scope expansion, or changes to frozen V2-v0 behavior.

## Status vocabulary

- `UNVALIDATED` — plausible idea with no sufficient user/product evidence.
- `PRELIMINARY` — some evidence exists, but not enough for roadmap commitment.
- `VALIDATED_FOR_EXPERIMENT` — enough evidence to justify a bounded product experiment.
- `REJECTED` — evidence does not support pursuing the hypothesis in its current form.

Unless a later strategy review explicitly changes status, every hypothesis below is `UNVALIDATED`.

---

## H1 — Information compression

**Status:** `UNVALIDATED`

**Hypothesis:** Users may value a system that reduces a large stream of market information to a small amount of decision-relevant context without materially omitting important information.

Potential value:

- less time spent checking multiple tools;
- lower cognitive load;
- better prioritization of what actually changed.

Open question:

> Can Signalbot do this materially better than an existing workflow built from general-purpose LLMs plus market-data/charting tools?

**Implementation authorization:** none.

---

## H2 — Evidence / auditability

**Status:** `UNVALIDATED`

**Hypothesis:** Some users may value analytical conclusions whose evidence, counter-evidence, historical population, methodology, limitations, and provenance can be inspected instead of accepting an opaque AI score.

Open question:

> Is this a real buying criterion for a sufficiently valuable user segment, or primarily an engineering/research virtue?

**Implementation authorization:** none beyond architectural traceability already required for correctness/research.

---

## H3 — Historical contextualization / analogue analysis

**Status:** `UNVALIDATED`

**Hypothesis:** Users may value seeing what happened after genuinely comparable historical market states rather than receiving only indicator interpretation or a directional prediction.

Potential outputs could eventually include distributions of future return, MFE/MAE, path behavior, sample size, and comparability limitations.

Open question:

> Can similarity/population definitions be made statistically defensible and useful enough to improve decisions rather than create false pattern confidence?

**Implementation authorization:** none.

---

## H4 — Material market-change detection

**Status:** `UNVALIDATED`

**Hypothesis:** Users may value being notified when the **overall decision-relevant market state materially changes**, instead of receiving one alert per metric/indicator event.

Open question:

> Can material change be defined in a stable, testable way that suppresses noise without hiding important events?

**Implementation authorization:** none.

---

## H5 — Trade-thesis red team

**Status:** `UNVALIDATED`

**Hypothesis:** Users may value a system that challenges a proposed trade thesis, verifies claimed evidence, identifies missing/counter evidence, and distinguishes quantified observations from vague reasoning.

Open question:

> Does this improve real decision quality enough to create repeated usage and willingness to pay?

**Implementation authorization:** none.

---

## H6 — Conditional forecasting

**Status:** `UNVALIDATED`

**Hypothesis:** Forecasting may be valuable only in a minority of sufficiently specific market states rather than as a continuously available directional opinion.

A useful system may legitimately return `NO EDGE` or equivalent most of the time and expose a forecast only when empirical evidence supports one.

Open question:

> Does V2 or later research demonstrate stable, economically meaningful conditional edge after proper controls, costs, delays, OOS testing, and uncertainty treatment?

**Implementation authorization:** current V2 research only; this hypothesis does not authorize tuning or expanding frozen V2-v0.

---

## Deferred product/business questions

The following are intentionally deferred to the Post-Roadmap Strategy & Product Review rather than answered by brainstorming alone:

- Which user segment has the strongest unmet problem?
- Which single workflow should become the initial product wedge?
- What does Signalbot do materially better than ChatGPT + TradingView + CoinGlass + exchange-native AI tools?
- Which capabilities are complementary to large platforms rather than directly competitive?
- What should be free, paid, API/B2B, or not built at all?
- What evidence would demonstrate willingness to pay?

## Default execution rule

Until the Post-Roadmap Strategy & Product Review:

> **Record promising product ideas here; do not silently convert them into active roadmap scope.**
