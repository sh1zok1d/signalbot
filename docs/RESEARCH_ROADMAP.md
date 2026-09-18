# Signalbot Research-First Roadmap

**Status:** ACTIVE  
**Supersedes for current execution:** `docs/FORECASTING_ROADMAP.md` and the old V2 implementation sequence in `docs/PROJECT_EXECUTION_PLAN.md`.

The project does not resume product architecture work merely because an implementation stage is technically available. Research evidence is now the gating dependency.

**Active next phase (2026-09-17):** `MARKET`. The synthetic Microscope
calibration is closed (`V3_CALIBRATION_CLOSED = YES`). The Microscope
remains available as scientific instrumentation and is no longer the
active research program. Do not repair, rerun, or reinterpret V3. Do not
create V4 (`DEFAULT_V4 = NO`). `V3_METHODOLOGY_CLAIMABLE = NO`.
`V3_RERUN_AUTHORIZED = NO`.

MARKET-01 is **closed** under its frozen design. Mechanical
classification: **`NO_EVIDENCE`**. Canonical RESULT:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json`
(SHA256 `5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e`).
`CANONICAL_EXECUTIONS_CONSUMED = 1`. Do not rerun MARKET-01. Do not
change its thresholds or windows. Post-close `construct_episodes`
throughput work is infrastructure only and does not reopen the closed
RESULT. Do not design a large new MARKET
framework. A later market hypothesis requires a new research ID.
Do not create new infrastructure merely because MARKET is beginning. Operating
priority is approximately 70–80% actual market research and 20–30%
infrastructure only when concrete research blockers require it. Primary
progress metric: MARKET hypotheses honestly closed per week. Initial
observational milestone: 25–50 real market hypotheses through the stable
research process — not a promise that 25–50 studies establish alpha.


### Near-term research-thesis checkpoint (2026-09-18)

The next MARKET cycle tests whether Signalbot reduces the cost of reliable
market research; it is not required to discover positive alpha to have value.

Capability ladder:
1. research execution — claim -> explicit contract -> reproducible test -> result;
2. research audit — attack leakage, assumptions, confounders, and conclusion scope;
3. diagnosis — distinguish identified failure modes from unresolved explanations;
4. research guidance — propose a justified next hypothesis when evidence supports one;
5. autonomous discovery — use research memory to generate and test candidates.

Levels 4–5 are not prerequisites for Levels 1–2 to be useful.

Target human-in-the-loop workflow:
idea -> Signalbot drafts the Research Contract -> human confirms semantic intent ->
automatic execution -> adversarial validation -> sealed RESULT.
Do not optimize for zero human decisions. Optimize away repeated programming and
avoidable repair work while preserving explicit semantic approval.

For MARKET-02 onward, record lightweight operational evidence where practical:
active human time, wall-clock time, new scientific code required, material review
blockers, semantic corrections, reruns, and whether the result changed the next
research decision. Compare later studies with the ordinary analyst/notebook
workflow without building a benchmark framework solely for this measurement.

Research-memory provenance must retain which prior results/observations motivated
a new hypothesis, which historical data influenced its design, attempted variants,
and which evidence remains untouched for independent confirmation. A new research
ID alone does not imply independence.

After roughly 3–5 MARKET studies, evaluate whether supported experiments become
cheaper/faster/more reliable and whether the process transfers beyond hypotheses
authored inside Signalbot. Include at least one external-user claim when feasible:
Signalbot drafts the contract, the external user confirms meaning, then the normal
research lifecycle runs.

Commercial discovery may begin in parallel with MARKET research. Initial demand
test should focus on research audit/validation problems rather than promising
trading performance. Monitoring/decision support remains a possible later wedge,
not the default pivot.

Checkpoint question:
Can Signalbot test a market claim materially cheaper/faster/more reliably than
the ordinary workflow, with conclusions that change a research decision, and can
that capability transfer to an external user's claim?


### External-claim validation policy (2026-09-18)

Public, pre-existing crypto strategies and market hypotheses are the preferred
initial source for external transferability tests. Do not require private alpha,
positions, sizing, execution logic, or proprietary code from traders.

Maintain an `EXTERNAL_CLAIMS` candidate pool independently of the active MARKET
execution. Candidate selection should prefer claims that:
- were publicly timestamped before Signalbot selected them;
- have a clear economic assertion that can be separated from the author's full strategy;
- are testable with defensible available-at data;
- do not require copying a published backtest or treating its reported performance as evidence;
- are materially distinct from claims already tested by Signalbot.

For the first external experiment, freeze the public source, publication date,
original claim, and Signalbot's interpretation before outcome inspection. The
research target is the underlying claim, not reproduction of the author's PnL.

The intended transferability test is:
external public idea -> explicit Research Contract -> semantic confirmation where
available -> reproducible test -> adversarial checks -> sealed result.

Author participation is optional. After sealing, the author may be contacted to
assess whether Signalbot represented the intended claim correctly and whether the
audit would change a research decision. Lack of an author response does not erase
the transferability evidence, but semantic confirmation must not be falsely claimed.

Do not interrupt or modify frozen MARKET-02 for this work. Candidate discovery may
run in parallel. After MARKET-02, choose the next experiment by information gain;
`EXTERNAL-01` is not automatically required to precede an internally generated
MARKET-03.

B2-06 remains `BLOCKED_MISSING_OBSERVABLE`. `MARKET-01` is not required
to be B2-06 and does not silently unblock it.

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

### Batch02 status (2026-09-07)

`V2_RESEARCH_HARNESS_V1` is accepted and the six-entry Batch02 inventory is
frozen/immutable. Real development outcomes opened so far:

- B2-01 `VOLATILITY_TRANSITION` = `CLOSED_NO_PROMOTION`
- B2-02 `BOUNDARY_INTERACTION_PATH` = `CLOSED_NO_PROMOTION`
- B2-03 `IMPULSE_MORPHOLOGY` = `CLOSED_NO_PROMOTION`
- B2-04 `MODERATE_PULLBACK_STRUCTURE` = `CLOSED_NO_PROMOTION`
- B2-05 `FLOW_ABSORPTION` development consumed; durable-evidence recovery
  `B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED` at
  `e31e5666fe845116197b6f2531289bf17d848027`

2025 validation and 2026 OOS remain untouched. Do not rerun B2-01 through
B2-05. Do not rescue any closed formulation inside current V2. Historical
B2-05 artifact bytes remain `OPERATOR_ADJUDICATED`, not proven.

Family F1 is `CLOSED_NO_PROMOTION`. B2-06 `LEVERAGE_CROWDING` remains
`BLOCKED_MISSING_OBSERVABLE` and is **not** the next active research
unit. MARKET-01 is closed (`NO_EVIDENCE`); it does not unblock B2-06.
The outcome-blind
OI/funding snapshot is Git-bound as
`SNAPSHOT_MATERIALIZED_NOT_RESEARCH_AUTHORIZED` /
`SNAPSHOT_MATERIALIZED_FUNDING_PUBLICATION_UNPROVEN_RESEARCH_UNAUTHORIZED`
(`docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md`, snapshot
`5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`).
Materialized bytes are not B2-06 execution and do not authorize 2025/2026.
See `docs/research/BATCH02_STATUS_LEDGER.md`.

### Mandatory pre-B2-06 methodology calibration

This gate still applies **only** to B2-06. It does not block `MARKET-01`.
V3 closeout / MARKET becoming the active phase does not silently unblock
B2-06.

Before any B2-06 scientific outcome is opened, a separate methodology
calibration must complete with a claimable RESULT. V1
(`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`) attempted that grid and is
permanently `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`. The active
methodology successor for identifiability is
`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`
(`FROZEN_BEFORE_V2_PRODUCTION`; reviewed fixture module frozen at HEAD
`a310837`; production driver + canonical plan + ARM-authorization runtime
implemented on top and awaiting independent review; not armed).

The original V1 purpose remains: measure whether the current Signalbot-style
research process can detect small, noisy, sparse, clustered conditional
incremental information without materially increasing false positives. V2
adds a frozen identifiability policy so a rank-deficient candidate does not
void the world. It is not a market hypothesis, not B2-07, and synthetic
results are never market evidence.

V1 design/implementation/ARM remain historical frozen records. The
canonical V1 production attempt ran at ARM HEAD
`9ab32fc14c50df0c6f1c7ddfe2a8990d2d49c339`. Structural completion was
3200/3200. RESULT was not minted. Mechanical status:
`INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`. No V1 subset is claimable.
Do not mint a V1 RESULT and do not resume V1 as V2.

V2 rank-degeneracy policy prereg:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.md`
and `.json`, plus Amendment_001. Status of the methodology contract:
`FROZEN_BEFORE_IMPLEMENTATION`. Fixture implementation identity:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION.md`.
`implementation_exists = true` (fixture only),
`v2_production_arm_authorized = false`,
`synthetic_execution_authorized = false`.
This does not authorize B2-06, 2025, or 2026.

Frozen sequence:

1. design/preregistration only;
2. independent adversarial review and closure of all Blockers/Majors;
3. implementation using toy synthetic fixtures only;
4. independent implementation review before production synthetic outcomes;
5. one frozen Monte Carlo calibration execution;
6. immutable calibration result;
7. methodology decision;
8. only then may B2-06 scientific execution be considered, and only if its
   separate funding-publication/data/legal gates are also solved.

The repaired calibration separates four diagnostic layers:

- `GROUND_TRUTH_VISIBLE` — injected structure is statistically visible under frozen block-aware uncertainty;
- `MODEL_DETECTED` — the model/evaluation procedure detects incremental prediction;
- `STRICT_PASS_EX_MATERIALITY` — strict confirmatory gates pass except the 2% pooled-MAE materiality requirement;
- `STRICT_PASS` — the unchanged full strict gate passes.

It also measures:

- ORACLE confirmatory sensitivity when the correct candidate is supplied without truth metadata;
- bounded BLIND-LIBRARY discovery over ten distinct preregistered candidates;
- TRUE / PROXY / FALSE / NO_DISCOVERY outcomes;
- full-pipeline NULL false-positive rate;
- rejection of an initially stable edge that later vanishes (`NONSTATIONARY_TRAP`);
- clustered-support effective-N diagnostics;
- gate-level attrition and support-conditional utility;
- SMALL-edge sample-size sensitivity;
- explicit `VISIBILITY_FLOOR` versus `MODEL_FLOOR` attribution;
- identifiability coverage versus conditional detection (V2 policy);
- materiality-only suppression by comparing full strict pass with strict pass excluding materiality.

Canonical frozen V1 prereg (historical; attempt incomplete):
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md` and `.json`.
Canonical V2 identifiability policy prereg (active methodology successor;
not an ARM):
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.md`
and `.json`.
The reviewed fixture-only rank-policy module is frozen at HEAD `a310837`
(`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json`).
A pre-outcome production lifecycle (canonical plan, historical
commit-parameterized ARM authorization behind an unforgeable session,
durable reservation that gates execution before any scientific computation,
checkpointing, mechanical aggregation wired from the frozen fixture's own
aggregation pipeline, RESULT mint, historical result re-verification) plus
the independently reviewed 33/33 inherited-ladder implementation are now
frozen at reviewed HEAD `614295d` / tree `e754b12`
(`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.json`).
Governing methodology is Amendment_003 + Amendment_004. Amendment_002 is
rejected historical authority and cannot govern executable science. The
visibility statistic gap remains unresolved and fail-closed. This
implementation freeze is not an ARM and does not authorize execution; no V2
ARM artifact exists anywhere in the repository. Next required step for V2:
`INDEPENDENT_V2_33_33_IMPLEMENTATION_FREEZE_REVIEW`. Do not create a V2 ARM,
do not run the 3200-world production grid, and do not mint RESULT until that
independent freeze review closes and a later explicit ARM unit is authorized.
The original prereg at `ada237e` and Amendment_001 at `d8f0a99` are not
rewritten in place.

V3 confirmatory calibration is **closed**. Canonical RESULT authority is
commit `99b409cae279513eaf489194e7fa206082c60aef`, WORLD_RECORDS SHA256
`5d09631db5180f562076b2191fe002aa21318a3925d3cd1c4014d83e4b41eb4f`,
RESULT SHA256
`f72eedcdcb511e2c7f22369cbdef164688317dfc99f9ab3e533df14cb2a27866`.
Mechanical cell verdicts: EASY `PASS` (400/400), MODERATE `PASS`
(313/400), NULL `INDETERMINATE` (21/400), NONSTATIONARY_TRAP `FAIL`
(188/400). `methodology_claimable = false`. `incomplete_execution = false`.

Narrow interpretation: V3 repaired the measured V2 confirmatory
sensitivity problem (`EASY`/`MODERATE` `PASS`) but did **not** establish
a generally claimable methodology. Known limitation:
`NONSTATIONARY_TRAP_PROTECTION = INADEQUATE_ON_FROZEN_TRAP_DGP`. Do not
translate 188/400 into a general real-market false-positive rate; it
applies only to the frozen synthetic trap DGP. V3 `DETECTED`/`PASS` must
not by itself be treated as sufficient evidence of a robust market edge.
This limitation is not authorization for immediate V4.

Next required V3 step: none authorized. MARKET-01 is closed
(`FINAL_CLASSIFICATION = NO_EVIDENCE`). A later market hypothesis
requires a new research ID. Do not rerun MARKET-01.
Do not rerun V3, do not create V4, and do not execute B2-06.

This methodology closeout does not weaken or bypass the current B2-06 state:
`FUNDING_PUBLICATION_LATENCY_UNPROVEN`, `research_authorized = false`,
`outcome_access_authorized = false`, and `b2_06_evaluator_enabled = false`.

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

During the MARKET phase, the primary progress metric is **MARKET
hypotheses honestly closed per week**. Infrastructure work is progress
only when it unblocks a concrete research blocker.

Report separately:

1. **data/evidence readiness**;
2. **hypothesis status**;
3. **validation status**;
4. **engineering support readiness**.

Only the first three can justify restarting product development.
