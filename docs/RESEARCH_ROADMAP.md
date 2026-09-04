# Signalbot Research-First Roadmap

**Status:** ACTIVE  
**Supersedes for current execution:** `docs/FORECASTING_ROADMAP.md` and the old V2 implementation sequence in `docs/PROJECT_EXECUTION_PLAN.md`.

The project does not resume product architecture work merely because an implementation stage is technically available. Research evidence is now the gating dependency.

## R0 — E1 frozen experiment closeout

**Status:** `CLOSED_AT_DEVELOPMENT / HOLDOUT_UNOPENED`

### Goal
Preserve the E1 evidence without spending clean holdout on formulations that
did not earn promotion.

### Decision
- keep V1 frozen;
- retain all E1 preregistration/evaluator artifacts as historical evidence;
- `TREND_PULLBACK`, `COMPRESSION_BREAKOUT`, and `CONFIRMED_BREAKOUT`
  are `RETIRED_CURRENT_FORMULATION`;
- do not run the frozen E1 holdout evaluator to rescue those formulations;
- keep the chronological holdout unopened.

### Exit
Satisfied on 2026-08-28 by explicit project closeout after E1 development and
R2 Batch01 synthesis.

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

### H01 status (2026-08-26)

`H01_COMPRESSION_EXPANSION` completed a development-only run on `CORE_BTC_BINANCE_V0` snapshot `717d37a4`. Verdict: **`H01_KILL`**. 2025 validation and 2026 OOS remain untouched. Do not start R3 for H01. See `docs/research/H01_DEV_SUMMARY.md` and `docs/RESEARCH_LEDGER.md`.

`H02_FAILED_BREAKOUT_MEAN_REVERSION` completed a development-only run on the same snapshot. Verdict: **`H02_KILL`**. 2025/2026 remain untouched. Do not start R3 for H02. See `docs/research/H02_DEV_SUMMARY.md`.

### Batch01 closeout (2026-08-28)

R2 Batch01 is **CLOSED: 0/5 primary families promoted**.

- H01 `REJECTED / H01_KILL`
- H02 `REJECTED / H02_KILL`
- H03 `H03_REJECTED_SPECIFIC_CLAIM`
- H04 `H04_REJECTED_SPECIFIC_CLAIM`
- H05 `H05_REJECTED_SPECIFIC_CLAIM`

2025 validation and 2026 OOS remain untouched. Do not continue mechanically
to H06 and do not reopen a rejected family through parameter rescue.

**Next execution step:** extract the common research-integrity mechanics into
`V2_RESEARCH_HARNESS_V1`; after independent audit, perform
`BATCH02_DESIGN`. See `docs/research/BATCH01_SYNTHESIS.md`.

### Batch02 status (2026-09-04)

`V2_RESEARCH_HARNESS_V1` is accepted and the six-entry Batch02 inventory is
frozen/immutable. Real development outcomes opened so far:

- B2-01 `VOLATILITY_TRANSITION` = `CLOSED_NO_PROMOTION`
- B2-02 `BOUNDARY_INTERACTION_PATH` = `CLOSED_NO_PROMOTION`
- B2-03 `IMPULSE_MORPHOLOGY` = `CLOSED_NO_PROMOTION`

2025 validation and 2026 OOS remain untouched. Do not rerun B2-01, B2-02, or
B2-03. Do not rescue any closed formulation inside current V2.

Family F1 remains `ACTIVE`. **Next frozen unit:**
`B2-04_MODERATE_PULLBACK_STRUCTURE`. Its outcome-blind preregistration is
frozen in `docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md`. It still
requires implementation, exact-SHA CI, reviews, merge, and a separate
development-outcome authorization. This roadmap note does not implement B2-04
or authorize B2-04 outcomes. See `docs/research/BATCH02_STATUS_LEDGER.md`.

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