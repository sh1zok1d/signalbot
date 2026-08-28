# Signalbot Strategy and Architecture Principles

**Status:** ACTIVE  
**Current posture:** `RESEARCH_FIRST / PRODUCT_DEVELOPMENT_FROZEN`

## 1. Core thesis

Signalbot should not build a sophisticated forecasting product first and ask whether the market edge exists later.

Current strategy:

> **Evidence first. Architecture second. Product third.**

The project temporarily acts as a research platform whose job is to discover, falsify and independently validate market mechanisms.

## 2. Edge is a dependency, not a promised deliverable

The project is allowed to conclude:

- a tested hypothesis has no edge;
- a setup works only under a specific prospectively detectable regime;
- a simpler rule is better than a richer model;
- current data are insufficient;
- no investigated mechanism justifies product development yet.

Do not turn “find one or two edges” into a requirement to manufacture them through repeated search.

## 3. Complexity must earn its place

Every added layer should answer an incremental-value question.

Examples:

- does 4h context improve a simpler pullback rule?
- does OI improve a price-only candidate?
- does taker flow improve compression selection?
- do multiple venues improve a robust single/median venue baseline?

If the answer is not supported, remove/demote the complexity rather than defending sunk cost.

## 4. Research before architecture

Do not implement generic lifecycle/risk/orchestration layers for hypothetical future edges.

Once a candidate edge is independently validated, inspect its actual behavior:

- setup formation;
- trigger timing;
- invalidation;
- decay;
- regime dependence;
- conflict with other edges;
- delay/execution sensitivity.

Then design only the architecture required by those observed properties.

## 5. Preserve the reusable foundation

The freeze does not mean discarding good infrastructure.

Reusable assets include where correctly implemented:

- raw market-data ingestion/storage;
- historical materialization;
- no-lookahead alignment;
- data-quality/missingness handling;
- version/provenance identity;
- replay/outcome primitives;
- research tooling.

V1/V2-specific hypotheses and product semantics remain isolated research artifacts rather than definitions of the whole project.

## 6. No speculative generalization

Even in research-first mode, do not build a universal research framework merely because many experiments are imaginable.

Create reusable abstractions only when at least two real current workflows expose the same stable boundary.

Prefer simple scripts/manifests first; promote them into shared infrastructure after repetition proves the need.

## 7. Intellectual honesty is load-bearing

Project defaults:

- `UNKNOWN` > invented certainty;
- `NO EDGE` > cosmetic confidence;
- `INCONCLUSIVE_SAMPLE` > overclaiming a small N;
- a failed hypothesis > post-hoc rescue on the same holdout;
- a simple baseline > unsupported complexity;
- explicit missingness > fabricated zero;
- historical source limitations > pretend live-equivalence.

## 8. Regime dependence

A market mechanism may legitimately be regime-specific.

But “the market regime was bad” is only an exploratory explanation until:

1. the regime is defined using information available at `T`;
2. the gating rule is frozen;
3. the conditional effect reproduces on independent data.

A no-trade state is a valid product outcome if the evidence supports conditional rather than continuous forecasting.

## 9. Product positioning remains deferred

Signalbot does not aim to out-feature TradingView, CoinGlass, exchanges or general-purpose AI systems.

The eventual product should target a narrow decision-support problem that is justified by real evidence and user workflow value.

Do not decide the product wedge, moat or monetization model while the core analytical value remains unvalidated.

`docs/PRODUCT_HYPOTHESES.md` is a parking lot only.

## 10. Architecture restart test

Before restarting product development, at least one candidate edge must satisfy the validation standard in `docs/EDGE_RESEARCH_PROTOCOL.md`.

Then ask:

- what capabilities are genuinely needed by the validated mechanism?
- which existing V1/V2 components remain useful?
- which old components are unnecessary baggage?
- does a regime router actually improve generalization?
- what structured evidence must reach the user?

Do **not** resume the old Stage 6–10 roadmap automatically.

## 11. Second-engine / removal tests

These remain useful design checks after research earns architecture work:

**Second-engine test:** would another validated analytical engine need private V2 internals to reuse a capability?

**Removal test:** would removing V2 also delete a capability that is conceptually useful for research/other engines?

A positive answer means inspect ownership; it does not authorize speculative refactoring.

## 12. Current non-goals

Until the restart gate:

- autonomous trading;
- new production model families;
- ML/adaptive thresholds;
- speculative multi-engine platform work;
- UI/Telegram feature expansion;
- production V2 enablement;
- business-model expansion;
- expensive rich-data acquisition without a specific validated-core incremental hypothesis.

## 13. Canonical companions

- `PROJECT_STATUS.md`
- `RESEARCH_ROADMAP.md`
- `EDGE_RESEARCH_PROTOCOL.md`
- `HISTORICAL_DATA_STRATEGY.md`
- `RESEARCH_LEDGER.md`
- `DOCUMENTATION_INDEX.md`
