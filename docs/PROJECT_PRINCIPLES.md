# Signalbot Project Principles

> Strategic and architectural guardrails for the Signalbot project.
>
> This document does **not** redefine V2 numeric semantics, acceptance rules, or the current forecasting roadmap. Where a V2 contract is more specific, the V2 contract wins for V2 behavior. The purpose here is to keep the project intellectually honest and architecturally capable of surviving, deepening, or pivoting after the current forecasting hypothesis is tested.

## 1. Current project thesis

Signalbot is **not identical to Forecasting V2**.

Forecasting V2 is the first serious analytical engine built on the Signalbot platform and the current primary roadmap remains focused on completing and falsifying/validating it. Its success is valuable, but its failure must not mechanically imply that the surrounding data, research, evidence, replay, and decision-support platform is worthless.

Working product thesis, explicitly **unvalidated**:

> Signalbot may create value by turning a large amount of market information into a smaller set of contextual, auditable, decision-relevant conclusions. Forecasting is one possible tool inside that system, not a promise that the system must always predict the future.

This thesis is a direction for future product discovery, not current product-market-fit evidence.

---

## 2. Evidence over narrative

The project must prefer an unattractive truthful result over an attractive unsupported result.

Canonical ordering:

```text
UNKNOWN > invented confidence
NO EDGE > weak fabricated signal
INSUFFICIENT DATA > silent extrapolation
FAILED HYPOTHESIS > post-hoc rescue story
```

Consequences:

- a failed experiment is a valid project outcome;
- a hypothesis that works only in a narrow regime must be reported as conditional, not generalized;
- a result that disappears after costs, delay, OOS, or proper controls is not rescued by presentation;
- adding a new hypothesis is a **new experiment**, not permission to redefine a failed old experiment until it looks good;
- implementation/correctness success must never be reported as evidence that the market hypothesis is true.

---

## 3. Forecasting is an engine, not the project identity

Architecturally, Forecasting V2 should remain replaceable, removable, or coexistent with future analytical engines.

A component belongs inside `forecasting_v2` when its semantics are genuinely V2-specific. Naturally reusable capabilities should not depend on V2 internals merely because V2 is the first consumer.

Examples of capabilities that may become shared when the boundary is natural and useful **today**:

- canonical market-data contracts;
- temporal alignment and fail-closed data-quality validation;
- reusable feature/statistical primitives;
- historical populations/outcome primitives;
- provenance and reproducibility metadata;
- structured evidence/result contracts.

Examples that remain V2-specific unless a later proven need says otherwise:

- V2 setup-family semantics;
- V2 thresholds and weights;
- V2 lifecycle/decision rules;
- V2 confidence semantics;
- V2-specific promotion criteria.

Do not move code merely because it *might* be useful someday. Reuse must be earned by a real boundary, not imagined future products.

---

## 4. Second-engine boundary test

Use these questions during architecture and PR review:

1. **If a second analytical engine were added tomorrow, would it need to import private/internal Forecasting V2 logic to consume basic market context, statistics, or evidence?**
   - If yes, re-check whether the boundary is too V2-centric.

2. **If Forecasting V2 were removed tomorrow, would generic data, alignment, replay, outcome, provenance, or evidence capability disappear with it even though those capabilities are not forecasting-specific?**
   - If yes, re-check ownership of that capability.

These are review heuristics, not automatic refactor mandates.

---

## 5. Structured conclusions and traceability

Signalbot should trend toward conclusions that are machine-readable and auditable before they are rendered as prose, notifications, API payloads, or UI.

Conceptually, a serious conclusion may eventually contain fields such as:

```text
Conclusion
├── claim
├── evidence[]
├── counter_evidence[]
├── uncertainty
├── statistical_support
├── data_quality
├── context / regime
├── limitations[]
└── provenance
```

This is **not a frozen schema** and does not authorize a new `EvidenceEngine` implementation now. It defines a design direction: user-facing language should be downstream of structured facts/evidence, not the source of truth itself.

A conclusion should be traceable, where technically applicable, from:

```text
rendered statement
    ↓
structured conclusion
    ↓
evidence / counter-evidence
    ↓
method / population / feature
    ↓
versioned source data
```

---

## 6. Future flexibility without speculative overengineering

Future-proofing means preserving clean boundaries in code that already needs to exist. It does **not** mean building a universal framework for hypothetical domains.

Rule of thumb:

> Architecture should help today's implementation today and avoid trapping tomorrow's implementation tomorrow.

Therefore the current roadmap does **not** gain speculative implementations for:

- market-state engines;
- anomaly engines;
- historical-analogue products;
- trade-thesis red-team assistants;
- news/on-chain/macro aggregation;
- equities/FX/multi-domain intelligence;
- universal plugin/engine factories;
- broad UI/API product surfaces.

Such ideas belong in `docs/PRODUCT_HYPOTHESES.md` until explicitly promoted after evidence and strategy review.

---

## 7. Competitive posture

Signalbot does **not** aim to replace or directly out-feature major charting, market-data, exchange, or general-purpose AI platforms.

Explicit non-goals include trying to become a better-by-breadth version of TradingView, CoinGlass, a major exchange, or a general LLM assistant.

The strategic search is instead for a narrow, high-value decision-support problem that existing tools leave underserved and that Signalbot can solve measurably well.

Large platforms may be:

- data sources;
- complementary tools;
- execution/visualization layers;
- benchmark competitors for a specific task.

Benchmarking them is used to discover where **not** to compete and where a real gap may exist. A future moat must be demonstrated experimentally; it must not be declared from architecture or marketing language.

---

## 8. Information compression is a hypothesis, not a moat

A promising but unvalidated product hypothesis is that users may value a system that:

- identifies what materially changed;
- rejects low-value noise;
- preserves the context required for a sound decision;
- explains the important evidence quickly and clearly.

This is not yet a proven competitive advantage. Current market products already perform forms of summarization and AI-assisted analysis, so Signalbot must eventually demonstrate a specific measurable advantage rather than rely on the phrase "saves time".

When evaluating future features, prefer features that do at least one of:

1. reduce the time required to reach an informed decision;
2. improve the quality/auditability of the decision;
3. reduce the probability of missing a material change.

If a feature does none of these, it needs a strong separate justification.

---

## 9. Current focus and strategy-review trigger

The current primary roadmap remains the priority. Product/business exploration must not interrupt correctness and empirical validation work merely because new ideas are attractive.

A formal **Post-Roadmap Strategy & Product Review** becomes active when the current V2 path reaches a legitimate stopping point:

- if the empirical gate produces `KILL/RETHINK`, the failed V2 hypothesis is preserved as evidence and the strategy review begins from the surviving platform capabilities;
- if V2 earns `GO`/`SIMPLIFY`, complete the agreed validation/promotion path before broad product expansion unless new evidence makes earlier review necessary.

The review should assess actual capabilities and evidence, benchmark existing alternatives, identify a narrow product wedge, and only then authorize a new product roadmap.

Until then: record ideas, do not silently implement them.
