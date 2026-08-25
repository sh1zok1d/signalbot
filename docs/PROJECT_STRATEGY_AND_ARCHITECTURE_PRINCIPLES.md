# Signalbot Project Strategy and Architecture Principles

> Project-wide strategic and architectural guardrails for building the current roadmap without coupling Signalbot's long-term viability to one forecasting hypothesis.

## 0. Authority and scope

This document is **not** a replacement for the forecasting roadmap or frozen V2 contracts.

For V2 semantics and deterministic behavior, the existing authorities continue to govern:

1. `docs/V2_PRODUCT_CONTRACT.md` — what V2 product behavior means.
2. `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` — deterministic formulas, thresholds, correctness and promotion semantics.
3. `docs/FORECASTING_ROADMAP.md` — forecasting product direction and stage sequence.
4. `docs/PROJECT_EXECUTION_PLAN.md` — tactical execution ordering and gates.

This document instead freezes **project-level strategy and architecture posture** that should guide implementation where the V2 contracts do not dictate a narrower choice.

It does **not** authorize scope expansion, new signal families, new data sources, new engines, or changes to frozen V2-v0 hypotheses.

---

## 1. Working project thesis

Signalbot is not defined by the success of one forecasting model.

The current working thesis is:

> **Signalbot explores how to transform large volumes of market information into a small amount of traceable, contextual, decision-relevant information. Forecasting is one possible analytical capability, not a condition for the project's existence.**

This is a **working thesis**, not validated product-market fit and not a claim of competitive advantage.

The current product/research domain remains crypto market decision support, with V2 as the active primary implementation program.

---

## 2. V2 is an engine, not the identity of Signalbot

Forecasting V2 is the first major analytical engine being implemented and empirically tested. It must remain possible, in principle, for Signalbot to survive one of the following outcomes:

- V2 demonstrates a strong edge;
- V2 demonstrates only conditional/regime-specific edge;
- V2 is descriptively useful but lacks predictive edge;
- V2-v0 fails its empirical hypothesis and is killed/rethought.

A `KILL/RETHINK` decision for V2-v0 is therefore a valid research outcome, not automatically a project-termination event.

This does **not** weaken the current V2 roadmap. V2 should still be implemented and falsified rigorously enough that the result is informative.

---

## 3. Intellectual honesty is a product and engineering invariant

Signalbot must prefer an honest absence of a conclusion over a cosmetically strong conclusion.

Project defaults:

- `UNKNOWN` is preferable to invented certainty.
- `NO EDGE` is preferable to a weak signal presented as meaningful.
- `INSUFFICIENT DATA` is preferable to silent extrapolation.
- A failed hypothesis is preferable to post-hoc rule changes designed to rescue attractive metrics.
- Passing engineering tests is not evidence of predictive validity.
- A new market hypothesis is a new experiment, not retroactive justification for the previous one.

The project should be optimized for discovering what is true about its hypotheses, not for preserving a preferred narrative.

---

## 4. Evidence over narrative

Serious analytical conclusions should be traceable to their basis.

Future-facing result contracts should, where naturally appropriate, preserve enough structure to distinguish concepts such as:

- claim / conclusion;
- supporting evidence;
- counter-evidence;
- uncertainty;
- statistical support;
- data quality / availability;
- market context or regime;
- limitations;
- provenance / version identity.

This section does **not** mandate a universal `EvidenceEngine` class or a specific schema today. It freezes the direction: presentation text should not become the source of truth for analytical reasoning.

A future UI, Telegram message, API, or LLM explanation should consume structured analytical results rather than force core mathematics to conform to presentation needs.

---

## 5. Shared foundation versus engine-specific logic

The repository should preserve natural architectural boundaries between reusable foundations and model/engine-specific logic.

A component belongs inside `analytics/forecasting_v2` when it is genuinely specific to V2. Components that are naturally reusable across analytical engines should not become coupled to V2 merely because V2 is their first consumer.

Potentially reusable categories include, where supported by actual current requirements:

- canonical market-data contracts;
- temporal alignment and no-lookahead primitives;
- data-quality validation;
- reusable feature/statistical primitives;
- historical populations and outcome primitives;
- provenance/version identity;
- structured analytical result contracts.

V2-specific categories include:

- V2-v0 hypotheses and setup-family semantics;
- V2-specific thresholds and formulas;
- V2 confidence semantics;
- V2 episode lifecycle and arbitration rules;
- V2 promotion/evaluation contracts.

These examples are architectural guidance, not authorization for broad refactoring.

---

## 6. The second-engine and removal tests

When an ownership boundary is ambiguous, use two design questions:

1. **Second-engine test:** if a second analytical engine were added tomorrow, would it need to import private/internal V2 implementation details to reuse this capability?
2. **Removal test:** if Forecasting V2 were removed tomorrow, would this capability disappear even though it is conceptually useful outside V2?

A "yes" is a signal to review the boundary, not an automatic instruction to refactor.

The current task must still justify the abstraction. Future-proofing must not become speculative architecture work.

---

## 7. Future flexibility without speculative overengineering

Signalbot should be easy to deepen or extend later, but it must not build imaginary future products today.

Default rule:

> **Architecture should help today's code today and avoid blocking tomorrow's code; it should not implement tomorrow's unknown product in advance.**

Therefore:

- do not create universal plugin/factory abstractions without a real current boundary;
- do not add new engines merely to prove modularity;
- do not move stable V2-specific logic into generic packages solely because it might be reused someday;
- do prefer narrow typed/versioned contracts where multiple current layers already interact;
- do preserve deterministic replay, provenance and fail-closed behavior at shared boundaries.

---

## 8. Competitive posture

Signalbot does **not** aim to replace or directly out-feature major charting, exchange, market-data, derivatives-data, or general-purpose AI platforms.

Examples of explicit non-goals include building a broader TradingView, a larger CoinGlass, or an exchange-scale AI assistant by feature count.

The long-term product strategy is instead to identify a **narrow, high-value decision-support problem that existing platforms leave underserved**, and to become complementary to the existing tool ecosystem where that is advantageous.

The project's specific moat is currently **unknown and unvalidated**.

Competitive advantage must be demonstrated rather than declared.

---

## 9. Product hypotheses are not roadmap commitments

Ideas such as information compression, historical contextualization, anomaly detection, market-state interpretation, trade-thesis red-teaming, or conditional forecasting may be recorded for later evaluation.

They do not enter V2-v0 or the active development roadmap merely because they sound promising.

See `docs/PRODUCT_HYPOTHESES.md` for the current parking lot.

---

## 10. Post-roadmap strategy review trigger

Deep product/business-model work is intentionally deferred while the primary implementation/evidence roadmap is unfinished.

The project should hold a dedicated **Post-Roadmap Strategy & Product Review** when all of the following are materially true:

- the primary V2 implementation path has reached an end-to-end evaluable state;
- the project has honest empirical evidence about V2 rather than only implementation completeness;
- the reusable capabilities that actually exist can be audited from the repository and runtime;
- the team can compare real Signalbot outputs against relevant existing tools rather than hypothetical competitors.

That review should examine:

- V2 evidence and the GO / SIMPLIFY / KILL outcome;
- reusable capability inventory;
- competitor benchmark and underserved workflow analysis;
- candidate product wedge(s);
- user-value validation;
- monetization/business-model hypotheses;
- the next product roadmap.

Until that trigger, new product ideas should normally be recorded rather than implemented.
