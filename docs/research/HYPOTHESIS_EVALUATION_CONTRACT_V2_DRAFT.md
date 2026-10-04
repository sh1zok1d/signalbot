# Hypothesis evaluation contract V2 — draft

**Status:** `DRAFT / NOT_ADOPTED / DESIGN_ONLY` (2026-10-04; owner decisions D1–D6 in §12a; red-team repairs R1–R7 applied per the owner decisions in §12b; variance-floor validation spec in `COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md`)
**Supersedes when adopted:** `HYPOTHESIS_EVALUATION_CONTRACT_V1.md` for cards registered after adoption. **Not retroactive:** every V1 preregistration, permit, result, verdict and ledger row keeps its force and its numbers. V1 stays the adopted contract until the owner records adoption of V2.
**Motivation record:** the owner review of 2026-10-04 (this draft's §0) and the internal evidence in §0.2.
**Authority unchanged:** `EDGE_RESEARCH_PROTOCOL.md`, the protected-data rules, `PRODUCT_FIRST_DECISION_V1.md`.

## 0. Why a V2

### 0.1 The problem V2 fixes

V1 makes three different questions pass one examination:

1. **Is there structure?** (an empirical question: a preregistered effect, separated from zero, with a known size);
2. **Is it a practically meaningful trading claim?** (an economic question: after costs, at the event's frequency and capacity);
3. **May the product use it safely?** (a calibration question: baselines, unusualness, suppression, wording; never direction).

Under V1 a unit answers all three with one class, and the class is driven by one fixed bar in SD units. That produces wrong labels and loses information.

### 0.2 Internal evidence (no external empirics needed)

- **R03-C1 (2026-10-03).** Preregistered, Holm p = 0.0001, estimate about −0.40 comparator-SD with a sign-flip SE of 0.036, growing every year. Classified `NO_INCREMENTAL_STRUCTURE` because the frozen bar was 0.5 SD. The contract was entitled to say "below our claim"; it was not entitled to record "no structure".
- **R03-A2, A3, C3; C025-R1.** Rare, calendar-defined events (about 46–60 in five years) cannot pass the feasibility screen at any effect size that the stress profile (SD × 2, power 0.8, Holm alpha) makes measurable; they are closed `INFORMATIONALLY_WEAK` for a reason that no mechanism could overcome. The calendar, not the hypothesis, decided.
- **SEED-0001, selling-exhaustion feasibility, C025-R1.** Every modern mechanism must replicate prospectively, because the only historical replication era (BitMEX 2016–2019) predates most of today's market structure and 2025/2026 are sealed; prospective starts fall in 2027 and stops in 2031. Sealed data that is never opened on a schedule has an expected information value near zero.
- **D7, D11, D12.** `PROMISING_PROTOTYPE` results that the product may not use in any form until a replication that, by the previous point, cannot arrive for years, although the product's own evidence standard permits honest descriptive interpretation.
- **Compiler.** `n_eff = a·b/(a+b)` is applied to every design, including paired and clustered ones where it does not measure the information actually available; R03 had to add an ad-hoc unit screen.

### 0.3 What V2 does not change (the epistemic core)

Twin preregistration before any outcome; outcome-blind feasibility; sealed data rules and the sealed 2026; no rescue (no re-scoring with new parameters, regimes, horizons, sides, baselines or claim types after outcomes); Holm within the test family; the forbidden wording set (direction, probability of direction, bias/lean labels, targets, trade recommendations); one-shot execution with permits and digests; the ledger. V2 adds tracks and statuses on top of this core; it lowers no gate inside it.

## 1. Tracks

Every unit declares, before any outcome, which tracks it will be judged on. A unit may declare several; each track has its own bar and its own status.

| Track | Question | Bar | Confirmation |
|---|---|---|---|
| `STRUCTURE` | is the preregistered effect separated from zero, with a known size | statistical only (§3) | time-disjoint replication raises the empirical status; not required to record detection |
| `EDGE` | is it a trading claim worth acting on | claim-specific economic bar (§4.1) | replication on a time-disjoint surface **and** holdout as in V1 §7; unchanged strictness |
| `PRODUCT_EVIDENCE` | may the product use it as calibration, stability or transportability evidence | claim-specific product bar (§4.2) | the product-evidence rules of §8; never a direction |

`STRUCTURE` is always declared (it is the empirical layer). `EDGE` and `PRODUCT_EVIDENCE` are declared only when the unit intends that claim, and only with **every** track-specific field filled in the twin: the claim, the bar function (§4) with its realized outcome-blind value, the decision rule, and for `PRODUCT_EVIDENCE` the §8.3 grant skeleton (`SCOPE`, `ALLOWED_WORDING_CLASS`, `PROSPECTIVE_GUARD`). **The set of declared tracks is closed before outcomes.**

**Two tracks on one unit (R3).** If both `EDGE` and `PRODUCT_EVIDENCE` are declared, the twin also freezes `TRACK_RELATIONSHIP`: the error-control relationship between the two decisions (one common family under one multiplicity rule; a hierarchy or gatekeeping order; or justified independent families) and which decision is read first. A result on one track is always recorded beside the result on the other.

**No late track.** A `PRODUCT_EVIDENCE` claim that was frozen before outcomes keeps its own decision even when the unit's `EDGE` decision is `BELOW_BAR`: no new unit is needed for the already-declared product claim. A product track that was **not** declared before outcomes can never be added to that unit; the product question then needs a new `PRODUCT_EVIDENCE` unit with its own prospective guard.

## 2. Status model: evidence and decisions are separate fields

A result carries **four fields**, each with a closed vocabulary. No field overwrites another.

**`EMPIRICAL`** (track `STRUCTURE`):
- `STRUCTURE_DETECTED` — the primary interval excludes zero in the declared direction at the Holm-adjusted level;
- `NO_STRUCTURE_DETECTED` — the interval includes zero and the unit had the planned precision;
- `INDETERMINATE` — the interval includes zero but the planned precision was not reached, or it excludes zero with a width that does not resolve the bar (§3);
- `ACCUMULATING` — a rare-event unit that is still collecting its pre-declared information units (§6);
- `INVALID_RUN` — integrity failure.

**`CLAIM`** (one entry per declared track other than `STRUCTURE`):
- `MEETS_BAR`, `BELOW_BAR`, `BAR_NOT_RESOLVED`, `NOT_DECLARED`.

**`REPLICATION`**: `REPLICATED`, `NOT_REPLICATED`, `PENDING`, `NOT_AVAILABLE`, `NOT_REQUIRED` (for `PRODUCT_EVIDENCE`, see §8).

**`PRODUCT_USE`**: `CALIBRATION_ALLOWED`, `WORDING_ALLOWED`, `NOT_ALLOWED`, `NOT_DECLARED`. Set only by an owner decision under §8; never computed by the evaluator.

The V1 classes map as follows and are retired for new cards: `PROMISING_PROTOTYPE` → `STRUCTURE_DETECTED` + `REPLICATION = PENDING`; `SUPPORTED_*` → `STRUCTURE_DETECTED` + `REPLICATED` + `CLAIM = MEETS_BAR` on the relevant track; `NO_INCREMENTAL_STRUCTURE` splits into `NO_STRUCTURE_DETECTED` and the new §3 class; `HETEROGENEOUS_UNEXPLAINED` becomes an epoch flag on `EMPIRICAL` (§5.4); `INCONCLUSIVE` → `INDETERMINATE` or `ACCUMULATING`.

## 3. `STRUCTURE_BELOW_PRACTICAL_BAR`

**Decision-compatible interval.** V2 does not use a generic confidence interval. Each decision uses the **`DECISION_COMPATIBLE_INTERVAL`**: the 95 % interval produced by the preregistered inference procedure of that decision, under that decision's preregistered multiplicity regime (for a Holm-adjusted test the interval is the one that is dual to the adjusted test; for a sign-flip or permutation test the test-inverted interval at the adjusted level; for a cluster-robust estimator the `t_{G−1}` interval at the adjusted level). Its construction is frozen in the twin; no other interval decides anything. The level stays 95 %; a stricter level is not introduced (owner, 2026-10-04).

`STRUCTURE_BELOW_PRACTICAL_BAR` is the combination `EMPIRICAL = STRUCTURE_DETECTED` with `CLAIM = BELOW_BAR` on a declared track. It is assigned only when **all** of these hold on the frozen estimator:

1. the null is excluded: the `DECISION_COMPATIBLE_INTERVAL` excludes zero in the declared direction;
2. the **claim-aligned bound** of the `DECISION_COMPATIBLE_INTERVAL` (the bound on the side of the frozen practical bar: upper for a positive bar, lower for a negative one) lies **below** the frozen bar;
3. the **preregistered precision target** is reached (the unit's information requirement as frozen in the twin).

If 1 holds but 2 fails because the interval straddles the bar, the result is `CLAIM = BAR_NOT_RESOLVED` with `EMPIRICAL = STRUCTURE_DETECTED`: "structure is known; whether it is large enough is not". If 3 fails, `EMPIRICAL = INDETERMINATE`. Nothing in §3 lowers a gate: it changes labels, never promotion.

## 4. Claim-specific bars (frozen before outcomes)

The universal SD bar is retired. Each declared track freezes a **`BAR_FUNCTION`** in the preregistration. Moving researcher freedom from the hypothesis to the utility function is the risk V2 must not create, so (R1, owner 2026-10-04):

- the function and every one of its inputs are part of the twin; an input is admissible only if it is a **constant frozen in the twin** or a quantity computed **only from data outside the evaluation surface** of the decision (a prior era, or outcome-blind feasibility counts from calendars and timestamps). "Before the decision boundary" is not enough: an input that lives on the evaluation surface, even pre-`T`, can move with the outcome and is forbidden;
- **one `TEST_FAMILY_ID` has exactly one bar function.** A different bar function for the same mechanism is a **new family**, registered with a cross-reference to the first in both ledger rows;
- the **realized bar value** is computed from the frozen inputs by the feasibility compiler, written into the feasibility artifact **before any outcome**, and **bound by digest in the execution permit**. A permit whose realized bar differs from the feasibility artifact is invalid.

### 4.1 `EDGE` bars

Expressed in the unit of the decision, not in SD: net effect after a frozen cost model × event frequency × a capacity or turnover constraint, on the declared horizon. The preregistration states the cost model, the frequency source (outcome-blind counts) and the capacity assumption. A frequent small effect and a rare large one are compared on the same economic scale. V1 §4 "above costs on both surfaces" remains the minimum.

### 4.2 `PRODUCT_EVIDENCE` bars

Expressed in product quantities: change in a calibration error, in the rate of unusual flags, in a conditional event rate, in a baseline's coverage. The bar states what change is worth a user-facing difference and is justified from the product surface it affects (as the weekday/weekend design does for the unusual-hour gate). It is never a direction or a probability.

### 4.3 `STRUCTURE`

No practical bar. Detection and precision only (§3 and §5).

## 5. Design-specific inference (compiler V3 requirement)

### 5.1 What a design must declare

The feasibility compiler (schema V3) requires, and the preregistration freezes:
- `INDEPENDENT_UNIT`: the unit the null acts on (event, date, epoch, cluster, pair);
- `ESTIMATOR`: the estimand and its weights;
- `DEPENDENCE_STRUCTURE`: what is correlated with what, and the cluster key;
- `VARIANCE_OR_RANDOMIZATION_METHOD`: cluster-robust, block, sign-flip, permutation within strata, with seeds and draws;
- `EFFECTIVE_INFORMATION_MEASURE`: how the design counts information for planning (number of independent units, cluster-adjusted effective N, or a frozen variance estimate).

The binary `a·b/(a+b)` remains the default **only** for genuine two-group unpaired designs. For paired, repeated-event, event-cluster, venue-panel and epoch-cluster designs the declared measure is used and the binary formula is reported beside it as a diagnostic only.

### 5.2 Venues are measurements, not units

A scheduled event observed on three venues is one event with three measurements unless the preregistration argues otherwise and the red team accepts it. Venue pooling reduces noise and tests transportability; it never multiplies N. The independent unit of a venue panel is the event-date, and the panel enters through the estimator, not through the count.

### 5.3 Stress profile

The V1 planning stress (SD × 2.0, power 0.8) remains the **conservative fallback**. A design may instead freeze a variance estimate from exposed data with a declared estimator, data window and a cap, chosen outcome-blind and recorded in the feasibility report.

**Scale of the floor (owner, 2026-10-04: keep 0.60, define it).** The floor is applied on the **variance** scale of the unit statistic used for planning:

`VAR_PLANNING = max( VAR_EXPOSED_ESTIMATE , 0.60 × VAR_FALLBACK )`, where `VAR_FALLBACK = (2.0 × SD_BASE)²` for the same unit statistic.

Equivalently the planning SD and SE may never fall below `√0.60 ≈ 0.775` of the fallback SD and SE. The estimate also may never be smaller than the exposed-data sample variance of the unit statistic. **Frozen before the count pass (R2, owner 2026-10-04).** The twin freezes, before any count or outcome: the variance **estimator**, the **estimator window**, the **variance source** (which exposed surface, under §6/§7 rules), and the **choice** between the fallback and the exposed estimate. None of these may change afterwards.

**The floor 0.60 is `PROVISIONAL`, not adopted.** Its adopted value is set by a separate adoption gate, **`COMPILER_V3_VARIANCE_FLOOR_VALIDATION`** (spec: `COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md`): a synthetic validation suite with known ground truth, a frozen candidate grid `0.60 / 0.75 / 1.00`, a frozen adverse variance-ratio grid, null and positive controls, and a **selection rule frozen before the suite runs**: choose the **smallest** candidate floor under which every design declared feasible at nominal power 0.80 keeps empirical power ≥ 0.75 on the adverse grid; if no candidate satisfies it, the variance model goes back to redesign, and no floor is chosen by hand. Known real outcomes (R03-C1, D12 or any executed unit) are **never** inputs to the selection; after the floor is adopted, historical exposed units may serve only as a non-decisive regression suite.

### 5.4 Epochs

Unchanged from V1 §4.4 in method. The outcome becomes a flag on `EMPIRICAL` (`EPOCH_HOMOGENEITY = PASS / MAGNITUDE_VARIES / FAIL / NOT_ASSESSABLE`) rather than a separate class; `FAIL` still blocks any `CLAIM = MEETS_BAR`.

## 6. Rare-event track: `ACCUMULATING`

For mechanisms whose independent units arrive slowly (scheduled settlements, holidays, macro releases, regime episodes):
- the preregistration freezes the **information unit** (§5.1), the **`TARGET_INFORMATION_COUNT`** (a count of units), the **`CALENDAR_CAP`** (a date), the eras and venues that may contribute under §5.2, and the single analysis at the target;
- **`TARGET_INFORMATION_COUNT` and `CALENDAR_CAP` are immutable once accumulation has started** (R5, owner 2026-10-04). There is no discretionary raise. The only admissible adaptation of the target is an **exact adaptation rule frozen before the first eligible event**, whose inputs are outcome-independent availability or count information (timestamps, calendar eligibility, bucket presence); manual extension after the start is forbidden;
- the monitored count is the count of **eligibility units** defined by calendar, timestamp and presence logic only; an outcome-defined event state (a flag, a qualified hour, a detector episode) is never the counted unit;
- until the target is reached the status is `EMPIRICAL = ACCUMULATING`; only that count is monitored; no estimate, no interim look;
- reaching `CALENDAR_CAP` below the target yields `EMPIRICAL = INDETERMINATE` and closes the unit; a continuation is a new unit on later data;
- a unit may accumulate across historical eras and the prospective stream under one frozen rule; era is a declared cluster and the epoch flag of §5.4 applies at analysis;
- `INFORMATIONALLY_WEAK` at feasibility is no longer terminal for a rare-event design that declares this track; it becomes the entry into `ACCUMULATING` with the required count stated;
- the ledger row of an `ACCUMULATING` unit shows its target, its current eligibility count and its cap.

`ACCUMULATING` is a live, unfinished experiment with a finish line fixed at its start. It reopens no V1 result; a V1-closed rare-event hypothesis that wants this track is a new test family on data it has not seen, as V1 §8 already requires.

## 7. The 2025 disclosure tranche

- **One** preregistered, irreversible disclosure of the Binance 2025 surface (2025-01-01 .. 2025-12-31) for an **enumerated** set of units and families, with the multiplicity treatment frozen across the whole tranche before any 2025 value is read.
- **Mandatory order (R7, owner 2026-10-04):** (1) commit the deterministic eligibility rule; (2) freeze and identify the ledger snapshot it applies to (commit and digest); (3) apply the rule **mechanically by script** to that snapshot; (4) emit the immutable `TRANCHE_MANIFEST` with the rule's inputs per unit, the selected units, the family mapping, the multiplicity / error-control policy and all digests. A rule committed after the snapshot, or applied by hand, is invalid. The red team checks **each eligibility clause** separately for post-hoc proxy selection: a clause with no justification other than the units it selects is struck.
- **`TRANCHE_MANIFEST` (frozen, separate artifact).** The manifest contains:
  - an **outcome-blind, deterministic eligibility rule** that selects units and families from the ledger using only fields that exist before outcomes (track declared, design class, data requirements, registration date, feasibility status computed without 2025) — **never** an observed effect, p-value, interval, classification or any 2020–2024 outcome quantity;
  - the full list of units and families the rule selects, with the rule's inputs shown per unit so the selection is reproducible;
  - the per-unit frozen rules (the twins) and the **error-control policy of the tranche** (R6): every decision unit whose positive result could change a promotion or replication decision inside the tranche is in the accounting; the units declare, before opening, their relationship as one common family, a hierarchy / gatekeeping order, or justified independent families. No single global Holm is imposed by default, and the relationship is never chosen after outcomes;
  - the digests of everything above and of the loaders.
  A tranche formed from results chosen for their observed promise is forbidden; the manifest's reproducibility is the check.
- **R03-C1 and D12 are not in the first tranche by default.** They go through `PRODUCT_EVIDENCE` (§8). They may enter a tranche only if the independent, pre-frozen eligibility rule selects them without using their observed effects or p-values.
- A unit not in the manifest does not get 2025 later from this tranche; a further tranche would be a new owner decision, and V2 does not pre-authorize one.
- **2026 stays sealed.** E1-RUN-001 stays sealed. The six-symbol divergence surface already opened (2025-01-01 .. 2026-08-15) keeps its recorded status and is not folded into the tranche silently: a family that wants to use it says so in the manifest and carries the exposure label.
- The tranche is the natural first replication surface for `STRUCTURE_DETECTED` results whose mechanism post-dates BitMEX. Prospective replication remains available and remains the only surface for anything that reads 2026.

### 7.1 Exposure ledger and reuse across tracks (R6)

- Every reuse of an evaluation or exposed surface by any unit, on any track, is a **separate exposure-ledger row** (unit, surface, purpose: test / bar input / variance source / replication, date, digest).
- A surface's `spent` status for a family is **derived mechanically** from those rows, never asserted in prose.
- All confirmatory decisions that share a disclosure or selection mechanism must define their error-control relationship **before** outcomes (common family; hierarchy / gatekeeping; or justified independent families). Choosing the relationship after outcomes is forbidden.
- A variance source (§5.3) may use only a surface that is already legally exposed for that family under the frozen rules, and that use is itself a row.

## 8. `PRODUCT_EVIDENCE` track

### 8.1 What it is

Permission for the product to use a **descriptive** fact: a baseline differs by weekday type; a profile shifts with the US clock; an hour is usually quieter after a given state. The forms of evidence are **calibration** (does a reference distribution match the nominal rates), **stability** (does the fact hold across epochs) and **transportability** (does it hold across venues or eras). Non-inferiority designs fit calibration questions; stability and transportability are descriptive with uncertainty. The method is declared per unit; "non-inferiority" is not imposed on questions that are not comparisons.

### 8.2 What it is not

It is not a reduced rung of `EDGE` promotion. A `PRODUCT_EVIDENCE` result never supports: a direction, a probability of direction, a bias or lean label, a target, a trade, or any sentence that implies the state predicts movement. The allowed vocabulary is the descriptive vocabulary of `BETA_COPY_CONTRACT_V1` ("обычно", "по сравнению с обычным", named comparator), and the unit's preregistration lists the exact sentences it may enable.

### 8.3 Allowed uses and the `PRODUCT_USE` record

`CALIBRATION_ALLOWED`: reference distributions, baselines, maturity rules, suppression and flag-rate calibration. `WORDING_ALLOWED`: a named descriptive sentence with its comparator and uncertainty. Each use is granted per unit by an owner decision recorded in the ledger, after the unit's own gates pass; the evaluator never grants it.

A `PRODUCT_USE` grant is a record with at least these fields (owner, 2026-10-04):

| Field | Content |
|---|---|
| `SCOPE` | a value from the **closed `PRODUCT_USE_SCOPE` registry** (§8.3a), never free text; each value names one bounded data-flow / use class; anything outside it is not granted |
| `ALLOWED_WORDING_CLASS` | a value from the **closed `ALLOWED_WORDING_CLASS` registry** (§8.3a): `NONE` for a calibration-only grant, or a descriptive class whose concrete copy lives in a separate versioned, hash-bound template artifact (never in this contract's prose); **no** directional, probability, bias or lean class exists in the registry |
| `EVIDENCE_VERSION` | the result digest and design revision the grant rests on; a new evidence version needs a new grant |
| `PROSPECTIVE_GUARD` | the blinded prospective stage (counts-only, frozen stop, degradation guardrails) that protects the grant, with its status |

**A calibration grant never enables language.** `CALIBRATION_ALLOWED` with `ALLOWED_WORDING_CLASS = NONE` changes numbers inside the product and no sentence; directional or probability wording is not grantable under any field value.

### 8.3a Closed registries (R4; residual DoF item 7 closed)

- **`PRODUCT_USE_SCOPE` registry** (initial values; extending the registry is a contract amendment): `GATE_RANK_REFERENCE_1H` (reference distribution of the unusual-hour gate's 1h ranks), `TOD_BASELINE_PRESENTATION` (time-of-day presentation baselines), `MATURITY_RULE` (maturity / usability rules of a reference), `SUPPRESSION_CALIBRATION` (push-policy suppression thresholds that are calibration, not rules), `DESCRIPTIVE_SENTENCE` (a named sentence class in `/catchup`, the briefing or the push text). Each value maps to one bounded data-flow; a grant names exactly one value. **A scope is never widened by editing a grant:** a wider use is a new auditable grant with its own `EVIDENCE_VERSION` and `PROSPECTIVE_GUARD`.
- **`ALLOWED_WORDING_CLASS` registry**: `NONE`, `COMPARATOR_DESCRIPTIVE` ("обычно … по сравнению с …", comparator named, uncertainty shown), `STATE_FREQUENCY_DESCRIPTIVE` (how often a state occurred, with N and window). The concrete copy for a class is a **versioned, hash-bound template artifact** under the copy contract; the grant records the template digest. The registry contains no class that states direction, probability, bias or lean, so none can be granted.
- **Implementation tests required before any grant is live:** (1) no code path from a calibration input to a directional renderer; (2) isolation: no enabled descriptive sentence is rendered in the same block as a directional line; (3) forbidden-wording tests over the i18n catalog and over the template artifacts, extending the existing predictive-wording pin of the beta.

### 8.4 Replication and prospective guards

- **`WORDING_ALLOWED` always requires at least one completed blinded prospective stage** for the unit (counts-only operation to a frozen stop, one analysis). No exception (owner, 2026-10-04). Stability across epochs or transportability is additional, as declared, never a substitute.
- **`CALIBRATION_ALLOWED` may exist before a replication or before the prospective stage completes**, but only inside a pre-written **internal product-use scope** (the `SCOPE` field, written before the grant) and only while a `PROSPECTIVE_GUARD` is active: the prospective stage is declared and running, its guardrails are frozen, and a guardrail breach at its stop revokes the grant automatically. A calibration grant without an active guard is not valid.

### 8.5 Reference design and first candidates

- **Reference design:** `WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1` (revision 5). It shows every element of the track: a product question, a calibration bar in product units, an availability guardrail, a blinded prospective stage with a count-defined stop, and no directional claim.
- **First candidates for an owner `PRODUCT_USE` decision under V2:** R03-C1 (weekend hours; `EMPIRICAL = STRUCTURE_DETECTED` is a V2 annotation, see §10) and D12 (US-clock profile shift, `PROMISING_PROTOTYPE` under its sprint rules). Neither becomes an edge claim; neither is granted anything by this draft.

## 9. Unchanged rules, restated

Twin preregistration (V1 §1) with the §5.1 fields added; claim type and variable roles (V1 §2) with the track declaration added; the nuisance baseline (V1 §3) unchanged, including the wording rule for context claims; integrity, statistical and epoch gates (V1 §4) unchanged in method; search surface and Holm within the test family (V1 §6) unchanged, with tranche-level multiplicity added for §7; no rescue (V1 §8) unchanged; product promotion of an `EDGE` claim (V1 §9) unchanged.

## 10. Migration

- **No V1 result is rescored.** Numbers, verdicts and ledger rows stand.
- **Annotation only, as one mechanical batch (owner, 2026-10-04).** V1 results receive the V2 `EMPIRICAL` field as an annotation computed by one deterministic script from the **frozen** estimates and intervals already in the result files, with no new computation on market data, written to a separate ledger field (`V2_EMPIRICAL_ANNOTATION`) beside the untouched V1 classification. The batch runs once over every eligible V1 unit under one rule; units are not annotated one by one. Expected outputs of that rule: R03-C1 → `STRUCTURE_DETECTED` with `CLAIM(PRODUCT_EVIDENCE) = NOT_DECLARED`; C025-R1, R03-A2/A3/C3, B1/B3/B4 → `INDETERMINATE (feasibility)`; the other five executed R03 cells → `NO_STRUCTURE_DETECTED`. Any later correction is a separate, auditable amendment record that names the batch digest; the original results are never recomputed.
- **Ledger schema V2** adds the four fields of §2, the track declaration, and the §5.1 design fields; existing rows keep V1 fields verbatim.
- **Compiler V3** implements §5; V0–V2 compilers and their goldens stay reproducible and untouched.

## 11. Adoption (not yet)

| Field | Value |
|---|---|
| Adopted | — |
| By | — |
| Applies from | the commit that records adoption; cards registered after it; not retroactive |
| Prerequisites | owner review of this draft; ledger schema V2 and compiler V3 as separate implementation units; a red-team pass on §4 (bar functions as a new degree of freedom) and §7 (tranche enumeration) |

## 12a. Owner decisions recorded (2026-10-04)

| # | Decision | Where |
|---|---|---|
| D1 | 95 % level kept; `DECISION_COMPATIBLE_INTERVAL` replaces the generic CI; `STRUCTURE_BELOW_PRACTICAL_BAR` needs null excluded, claim-aligned bound below the bar, precision target reached | §3 |
| D2 | 0.60 floor kept on the **variance** scale; red-team sensitivity 0.60 / 0.75 / 1.00 on synthetic and positive-control designs; adopted value frozen after that | §5.3, §13 R2 |
| D3 | frozen `TRANCHE_MANIFEST` with outcome-blind deterministic eligibility, full list, tranche-level multiplicity; R03-C1 and D12 not in the first tranche by default | §7 |
| D4 | `WORDING_ALLOWED` always needs a completed blinded prospective stage; `CALIBRATION_ALLOWED` before completion only inside a pre-written internal scope with an active prospective guard | §8.4 |
| D5 | V2 annotations of V1 units as one mechanical batch from frozen numbers; corrections as separate auditable amendments | §10 |
| D6 | `PRODUCT_USE` carries `SCOPE`, `ALLOWED_WORDING_CLASS`, `EVIDENCE_VERSION`, `PROSPECTIVE_GUARD`; a calibration grant never enables directional or probability language | §8.3 |

## 13. Red-team pass on the new degrees of freedom (§4 bar functions, §7 tranche; 2026-10-04)

Scope: only what V2 adds. The owner decided each finding on 2026-10-04 (§12b); the repairs are now applied in the sections named there. The findings are kept as the record of the attack surface.

**R1 — Post-outcome flexibility in the bar function and its inputs (§4).**
Attack: a unit freezes a bar *function* whose inputs include quantities computed "before the decision boundary" that are nonetheless correlated with the outcome (an event-frequency count that rises exactly when the effect is present; a cost model whose spread input is itself volatility). The frozen function then moves with the data. Second vector: the same mechanism is registered twice with two bar functions, and the one that passes is reported.
Repair: (a) every bar input must be either a constant in the twin or a quantity computed from data **outside the evaluation period** of the decision (prior era or outcome-blind feasibility counts), never from the decision's own surface; (b) a bar function is registered once per `TEST_FAMILY_ID`; a second registration of the same mechanism with another bar is a new family and both are listed in the ledger with a cross-reference; (c) the feasibility report prints the bar's realized value from the outcome-blind inputs before any outcome, and the permit binds that value.

**R2 — The 0.60 floor as a new degree of freedom (§5.3).**
Attack: the exposed-data variance estimate is chosen (window, estimator) so that the floor binds exactly where it makes the unit "feasible". Repair: the estimator and window are fixed in the twin and the choice between fallback and exposed estimate is made **before** the count pass; the red-team sensitivity at 0.60 / 0.75 / 1.00 on synthetic and positive-control designs is run outcome-blind and its report is bound in the adoption record; the adopted floor is then a constant of the contract, not a per-unit choice.

**R3 — Track switching and dual use to escape a negative decision (§1, §2).**
Attack: a unit that declares `EDGE` and fails `MEETS_BAR` is "re-read" as `PRODUCT_EVIDENCE` with a product bar it would pass; or a unit declares all three tracks so that at least one reads well. Repair: (a) tracks are declared before outcomes and the set is closed; (b) a product-track grant for a unit that also declared `EDGE` and got `BELOW_BAR` is possible only through a **new** `PRODUCT_EVIDENCE` unit with its own prospective guard, never by relabelling; (c) the ledger row shows every declared track and every track's result on one line, so a positive on one track is always read beside the negative on another; (d) declaring both `EDGE` and `PRODUCT_EVIDENCE` is allowed but each has its own multiplicity, and the product grant still needs §8.4.

**R4 — Leakage of `PRODUCT_EVIDENCE` into directional or probability wording (§8).**
Attack: a calibration grant ("weekend reference differs") is rendered by the product as "weekends are quieter, so expect…"; or `ALLOWED_WORDING_CLASS` is set to a descriptive class whose sentence template, combined with another product line, reads as a forecast. Repair: (a) `ALLOWED_WORDING_CLASS` enumerates exact sentences, and the copy contract's isolation test is extended to assert that no enabled sentence co-occurs with a directional line in the same rendered block; (b) a calibration grant has `ALLOWED_WORDING_CLASS = NONE` by construction and the renderer has no code path from a calibration input to text; (c) the §8.2 forbidden list is pinned by a test on the i18n catalog, as the current beta does for predictive wording.

**R5 — Optional stopping and indefinite extension through `ACCUMULATING` (§6).**
Attack: the accumulation target is raised whenever an interim count suggests the result would be null (raising is allowed "before analysis"), or a unit stays `ACCUMULATING` forever to avoid a negative. Second vector: counts-only monitoring leaks because the count of qualifying events is itself correlated with the effect. Repair: (a) a raise of the target is allowed **once**, must be filed before 50 % of the original target is reached, and must cite an outcome-blind reason (a variance re-estimate on exposed data, a design-effect finding from another unit); (b) a hard calendar cap is frozen in the twin; reaching it yields `INDETERMINATE` and closes the unit; (c) the monitored count is the count of **eligibility** units from timestamps and calendars, never of outcome-defined events; (d) an `ACCUMULATING` unit is listed in the ledger with its target, its current count and its cap, so an endless unit is visible.

**R6 — Data reuse across tracks, multiplicity and tranche accounting (§6, §7).**
Attack: the same 2020–2024 outcomes feed a `STRUCTURE` test, then a `PRODUCT_EVIDENCE` bar, then are used as the exposed-data variance estimate for a third unit, with Holm applied inside each but never across; the 2025 tranche then admits a family whose per-unit rules were refined on those reuses. Repair: (a) every reuse of a surface by a unit is a ledger row with the surface's exposure label; a surface's "spent-for-family" status is derived from those rows, not asserted; (b) tranche-level multiplicity counts every unit in the manifest, including units that enter only for replication; (c) a unit may use a surface as a variance source only if that surface is already exposed for its family, and that use is itself a row; (d) the eligibility rule of the manifest excludes any unit whose twin was amended after a 2020–2024 outcome was seen for the same mechanism.

**R7 — The eligibility rule itself (§7).**
Attack: the "outcome-blind deterministic" rule is written after looking at which units look promising, encoding promise through proxies (registration date, design class). Repair: the rule is written and committed **before** the ledger snapshot it will be applied to is fixed, and applied to that snapshot by a script whose inputs are listed; the red team checks whether any rule clause has no justification other than the units it selects.

### 13.1 Residual researcher degrees of freedom (after the R1–R7 repairs)

Closed by the repairs: bar inputs on the evaluation surface (R1); per-unit choice of variance estimator, window and source after the count pass (R2); late track addition and relabelling (R3); free-text wording and free-text scope (R4, item 7 of the previous list); discretionary target raise and manual extension (R5); asserted "spent" status and post-outcome error-control choice (R6); hand-applied or post-snapshot eligibility (R7).

Still open, and relying on preregistration discipline and review rather than mechanics:

1. **Form of the bar function** before outcomes (§4): intended; constrained to frozen constants and off-surface inputs, but still authored.
2. **Inference procedure and clustering key** (§5.1): the `DECISION_COMPATIBLE_INTERVAL` inherits whichever reasonable key was frozen.
3. **Variance floor** until `COMPILER_V3_VARIANCE_FLOOR_VALIDATION` adopts a value; the selection rule is frozen, the suite is authored.
4. **Which tracks to declare and the `TRACK_RELATIONSHIP`** (§1): closed before outcomes and with a frozen hierarchy, but the hierarchy itself is a design choice.
5. **The initial `TARGET_INFORMATION_COUNT`, `CALENDAR_CAP` and any frozen adaptation rule** (§6): immutable after start, authored before.
6. **Authorship of the tranche eligibility rule** (§7): committed before the snapshot and clause-checked, but written by a person.
7. **Family boundaries** behind the mechanical `spent` derivation (§7.1): rows are mechanical, the family definition of a new unit is human.
8. **Stricter-only amendments** before Stage P or before analysis: "stricter" is confirmed by a reviewer.
9. **The precision target per unit** (§3): frozen per unit, set by the designer.
10. **Registry extensions** (§8.3a): a contract amendment, but the registries can grow.

Items 1, 3, 4, 5, 6 and 10 are the price of the three tracks, the rare-event track and the tranche; the others existed under V1.

## 12b. Owner decisions on the red-team findings (2026-10-04)

| Finding | Decision | Applied in |
|---|---|---|
| R1 bar function | ACCEPT | §4 |
| R2 variance floor | PARTIAL ACCEPT: freeze estimator/window/source/choice before counts; floor stays provisional; separate adoption gate with a frozen selection rule and a synthetic suite; no known outcome used for selection | §5.3, validation spec |
| R3 track switching | ACCEPT WITH REPAIR: closed track set, mandatory `STRUCTURE`, full track fields, `TRACK_RELATIONSHIP`, no late track; a pre-declared product claim survives an `EDGE` `BELOW_BAR` | §1 |
| R4 wording leakage | ACCEPT: closed registries for wording class and scope, hash-bound templates, implementation tests; calibration never enables wording | §8.3, §8.3a |
| R5 accumulating | ACCEPT WITH STRICTER REPAIR: immutable target and cap, frozen adaptation rule only, no manual extension, eligibility-only counts | §6 |
| R6 reuse / multiplicity | ACCEPT WITH CLARIFICATION: exposure rows, mechanical `spent`, pre-declared error-control relationship instead of one global Holm, full tranche accounting, legal variance sources only | §7, §7.1 |
| R7 eligibility rule | ACCEPT: mandatory order rule → snapshot → script → manifest; clause-by-clause proxy check | §7 |

## 12. Open points for the owner

Decided: D1–D6 (§12a) and R1–R7 (§12b). Remaining before adoption:
1. Review of `COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md` (suite manifest and selection rule) and authorization to run it; the floor is adopted only through that gate.
2. Initial contents of the two closed registries (§8.3a) and the first template artifacts under the copy contract.
3. Ledger schema V2 and compiler V3 as implementation units (fields of §5.1, exposure rows of §7.1, `PRODUCT_USE` record of §8.3).
4. Whether residual items 4 and 7 of §13.1 get a mechanical constraint.
