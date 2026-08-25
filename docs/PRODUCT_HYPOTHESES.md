# Signalbot Product Hypotheses

> Parking lot for product ideas that are worth remembering but are **not yet requirements**.
>
> Nothing in this document authorizes implementation, roadmap expansion, marketing claims, or product-market-fit claims. Promotion from this file requires explicit strategy/research review.

## Status vocabulary

- `UNVALIDATED` — plausible idea, no sufficient user/evidence proof.
- `RESEARCHING` — explicit validation work has been authorized.
- `SUPPORTED` — evidence justifies product/roadmap consideration.
- `REJECTED` — evidence does not support pursuing the idea under its tested formulation.

Default status is `UNVALIDATED`.

---

## H1 — Information compression

**Status:** `UNVALIDATED`

**Hypothesis:** users may value a system that compresses a large amount of market information into a small amount of decision-relevant context without hiding important uncertainty or contradictory evidence.

**Potential value:** less time spent switching between charts/data sources and less cognitive load.

**Must eventually prove:** that Signalbot reduces time-to-understand or improves decision quality versus realistic alternatives such as a general LLM plus existing market tools.

**Do not assume:** summarization alone is a moat.

---

## H2 — Evidence and auditability

**Status:** `UNVALIDATED`

**Hypothesis:** some users may value conclusions that can be traced from claim → evidence/counter-evidence → historical/statistical support → versioned source data.

**Potential value:** distinguish statistically grounded analysis from opaque AI confidence scores or indicator narration.

**Must eventually prove:** that target users care enough about auditability for it to change trust, usage, retention, or willingness to pay.

**Do not assume:** more methodological detail automatically creates a better user experience.

---

## H3 — Historical contextualization / analogues

**Status:** `UNVALIDATED`

**Hypothesis:** showing what happened after genuinely comparable historical market states may be more useful than generic indicator interpretation.

**Potential value:** contextual distributions, base rates, MFE/MAE/path behavior, and conditional outcomes rather than unsupported directional storytelling.

**Must eventually prove:** that similarity definitions are statistically defensible, non-leaky, stable enough to be useful, and decision-relevant to users.

**Do not assume:** nearest historical examples imply causal or predictive similarity.

---

## H4 — Material market-change detection

**Status:** `UNVALIDATED`

**Hypothesis:** users may prefer one high-quality notification when the market state materially changes over many independent threshold/indicator alerts.

**Potential value:** lower alert fatigue and lower probability of missing a genuinely important change.

**Must eventually prove:** a robust definition of "material change" and meaningful precision/recall versus simpler alerting systems.

**Do not assume:** fewer alerts are better if important events are missed.

---

## H5 — Trade-thesis red team

**Status:** `UNVALIDATED`

**Hypothesis:** a trader may value a system that checks a proposed trade thesis, quantifies/validates its arguments, identifies missing or contradictory evidence, and refuses vague unsupported reasoning.

**Potential value:** decision-quality improvement rather than direct signal generation.

**Must eventually prove:** that this changes real decision quality and is not merely an engaging conversational feature.

**Do not assume:** disagreement with the user is useful unless the underlying evidence is better than the user's existing process.

---

## H6 — Conditional forecasting / explicit no-edge state

**Status:** `UNVALIDATED` at product level; Forecasting V2 is the active research implementation.

**Hypothesis:** forecasting may be valuable only in a subset of market regimes/events, with an explicit `NO EDGE`/insufficient-evidence output the rest of the time.

**Potential value:** preserve small or conditional predictive asymmetries without forcing the system to hold a directional opinion on every decision boundary.

**Must eventually prove:** stable OOS/forward economic/statistical value after baselines, costs, delay, concentration, and multiple-testing concerns.

**Do not assume:** V2 implementation correctness demonstrates this hypothesis.

---

## H7 — Complementary intelligence layer

**Status:** `UNVALIDATED`

**Hypothesis:** Signalbot may be more viable as a complementary intelligence/decision-support layer that consumes or contextualizes data from strong existing tools than as a replacement for major market-data, charting, exchange, or general-AI platforms.

**Potential value:** occupy a narrow workflow gap while benefiting from the strengths of established platforms.

**Must eventually prove:** at least one specific task where adding Signalbot to the user's existing stack creates measurable incremental value.

**Do not assume:** integration/aggregation by itself creates defensibility.

---

## Promotion rule

Ideas in this file remain outside the current implementation backlog unless explicitly promoted.

Promotion requires, at minimum:

1. a clearly defined user/problem statement;
2. a benchmark or baseline representing realistic alternatives;
3. a falsifiable success criterion;
4. explicit scope and evidence plan;
5. a decision to add the work to a future roadmap.

The preferred strategy is to identify **one narrow problem Signalbot can solve measurably well**, then deepen from evidence. Breadth is not a substitute for a wedge.

---

## Current freeze

Until the current V2 roadmap reaches its legitimate empirical/validation stopping point, this document is a memory and prioritization mechanism only.

New ideas may be added here so they are not lost. They must not be smuggled into Forecasting V2 as rescue complexity or into unrelated PRs as speculative infrastructure.
