# Signalbot Research-First Roadmap

**Status:** ACTIVE  
**Supersedes for current execution:** `docs/FORECASTING_ROADMAP.md` and the old V2 implementation sequence in `docs/PROJECT_EXECUTION_PLAN.md`.

The project does not resume product architecture work merely because an implementation stage is technically available. Research evidence is now the gating dependency.

## R0 — Freeze and finish the already-frozen experiment

### Goal
Preserve the current state without contaminating `E1-RUN-001`.

### Work
- keep V1 frozen;
- keep V2 production disabled;
- do not change frozen TP/CB/FB rules inside `E1-RUN-001`;
- finish the one-shot final holdout evaluation when runtime/data access is available;
- record the final E1 family verdicts and global Level-0 decision in the research ledger.

### Exit
`E1-RUN-001` has a final immutable result, or is explicitly closed as technically incomplete with the reason recorded.

---

## R1 — Historical Expansion

### Goal
Stop allowing the shortest rich-data overlap to define the evidence horizon for every hypothesis.

### Build two evidence tiers

**CORE — long history**
- OHLCV / price structure;
- volume;
- taker-side flow when source semantics are reliable;
- funding where reliable;
- OI only for periods/providers with defensible timestamp semantics.

**RICH — shorter overlap**
- full cross-exchange OI;
- liquidations;
- venue agreement/divergence;
- richer derivatives context;
- live-equivalent feeds where available.

### Target
For BTC CORE, prefer a multi-year span containing materially different bull/bear/chop/high-vol/low-vol regimes. A practical target is 2021–present where source availability supports it. Add ETH and SOL later for cross-asset validation, not to inflate iid sample counts.

### Deliverables
- versioned dataset manifests;
- per-source capability/evidence-tier matrix;
- missingness/gap reports;
- provider-granularity notes;
- reproducible materialization commands;
- no-lookahead/as-of tests.

### Exit
At least one multi-year CORE dataset is reproducibly materialized and suitable for hypothesis discovery without silently mixing incompatible feed semantics.

---

## R2 — Mechanism-first hypothesis discovery

### Goal
Find plausible market mechanisms, not indicator combinations.

Initial hypothesis classes may include:
- compression -> volatility expansion;
- failed breakout / liquidity sweep -> mean reversion;
- trend pullback -> continuation;
- extreme impulse -> continuation versus exhaustion;
- price/OI divergence;
- crowded positioning -> reversal risk.

These are research directions, not implementation scope.

Prefer questions such as:
- `P(volatility expansion over next H)`;
- `P(return to range after failed break)`;
- `E[directional return | setup strength]`;
- `P(continuation | regime, setup)`;

over forcing every detector to output a continuous LONG/SHORT opinion.

### Required discipline
- define causal/mechanical rationale;
- define simple baseline;
- define negative control;
- define outcome before searching thresholds;
- log every tested configuration family in `RESEARCH_LEDGER.md` or a machine-readable successor.

### Exit
A small set of candidate mechanisms shows enough development evidence to justify formal validation. It is acceptable for none to qualify.

---

## R3 — Development-only optimization

### Goal
Turn a promising mechanism into a frozen candidate without contaminating validation data.

Allowed on development data:
- threshold search;
- lookback comparison;
- gate addition/removal;
- score construction;
- regime conditioning;
- simple feature ablations.

Not acceptable:
- selecting a magic parameter solely because it maximizes one PnL curve;
- repeatedly viewing OOS and retuning;
- silently expanding the search surface after weak results.

Prefer:
- monotonic strength/outcome relationships;
- broad stable parameter plateaus;
- consistent behavior across chronological development blocks;
- simple rules over fragile combinations.

### Exit
Candidate rule, parameters, metrics and validation plan are frozen before confirmatory data are opened.

---

## R4 — Independent validation / OOS

### Goal
Determine whether the candidate mechanism generalizes.

Use, as appropriate:
- chronological validation blocks;
- walk-forward evaluation;
- untouched final OOS;
- regime breakdowns declared before confirmatory inspection;
- clustering/effective-N reporting;
- matched random/simple controls;
- direction inversion/time shift where meaningful;
- delay and cost stress.

A consumed validation/OOS window cannot be reused as untouched evidence for a revised candidate.

### Exit statuses
- `VALIDATED_CANDIDATE`
- `SIMPLIFY_AND_REVALIDATE`
- `REJECTED`
- `INCONCLUSIVE_SAMPLE`

---

## R5 — Rich-feature incremental-value tests

### Goal
Only after a simpler CORE mechanism survives validation, ask whether richer data improve it.

Examples:
- CORE + OI versus CORE;
- CORE + taker versus CORE;
- CORE + funding versus CORE;
- CORE + liquidation context versus CORE;
- single-venue versus cross-venue context.

The shorter RICH overlap is used to answer **incremental-value** questions, not to prove the existence of the underlying market mechanism from scratch.

### Rule
A rich feature earns production complexity only if it adds stable information after matching the same candidate population, delays, costs and data-quality rules.

---

## R6 — Forward shadow

### Goal
Verify replay/live equivalence and operational survivability after a candidate has already earned historical credibility.

Measure:
- live feature availability;
- decision latency;
- candidate frequency;
- replay/live divergence;
- missing-data rates;
- economic sensitivity under realistic delay/cost assumptions.

Forward shadow is new evidence; it is not a deployment ceremony.

---

## R7 — Architecture and product restart

Only now design the product architecture around observed edge behavior.

Potential components may include:
- regime routing;
- one or more validated edge detectors;
- conflict resolution;
- risk/feasibility layer;
- lifecycle semantics derived from the actual setup behavior;
- explanations and decision-support UX.

Do not resurrect old Stage 6–10 scope automatically. Re-evaluate what is actually needed.

---

## Global non-goals during R0–R6

- no architecture progress as a proxy for research progress;
- no ML to rescue an unproven mechanism;
- no new data source merely because it is available;
- no synthetic/bootstrapped data presented as additional market regimes;
- no multiplying 5m rows and calling them independent evidence;
- no requirement that an edge must exist;
- no claim that one favorable month is durable alpha.

## Definition of progress

Report separately:

1. **data/evidence readiness**;
2. **hypothesis status**;
3. **validation status**;
4. **engineering support readiness**.

Only the first three can justify restarting product development.