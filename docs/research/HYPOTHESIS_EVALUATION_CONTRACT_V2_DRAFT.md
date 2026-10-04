# Hypothesis evaluation contract V2 — draft

**Status:** `DRAFT / NOT_ADOPTED / DESIGN_ONLY` (2026-10-04)
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

`STRUCTURE` is always declared (it is the empirical layer). `EDGE` and `PRODUCT_EVIDENCE` are declared only when the unit intends that claim; a unit that did not declare a track cannot acquire it after outcomes.

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

This is the combination `EMPIRICAL = STRUCTURE_DETECTED` with `CLAIM = BELOW_BAR` on a declared track. It is assigned only when **all** of these hold, on the frozen estimator and interval of the preregistration:

1. the interval excludes zero in the declared direction (detection);
2. the interval's bound on the practical side (the upper bound for a positive bar, the lower bound for a negative one) lies **below** the frozen bar (the bar is resolved against, not merely missed by the point estimate);
3. the planned precision was reached (the unit's information requirement is met).

If condition 2 fails because the interval straddles the bar, the result is `CLAIM = BAR_NOT_RESOLVED` with `EMPIRICAL = STRUCTURE_DETECTED`: "we know there is structure; we do not yet know whether it is large enough". That is a different statement from "the effect is small", and the ledger keeps them apart. Nothing in §3 is a lower gate: it changes labels, never promotion.

## 4. Claim-specific bars (frozen before outcomes)

The universal SD bar is retired. Each declared track freezes a **bar function** in the preregistration; the function and its inputs are part of the twin and are never edited after outcomes. Moving researcher freedom from the hypothesis to the utility function is the risk V2 must not create, so a bar is admissible only if every input is either a constant fixed in the preregistration or a quantity computed from data **before** the decision boundary.

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

The V1 planning stress (SD × 2.0, power 0.8) remains the **conservative fallback**. A design may instead freeze a variance estimate from exposed data with a declared estimator, data window and a cap (the estimate may never be smaller than the exposed-data sample variance of the unit statistic, and never smaller than 60 % of the fallback). Which of the two applies is chosen outcome-blind and recorded in the feasibility report.

### 5.4 Epochs

Unchanged from V1 §4.4 in method. The outcome becomes a flag on `EMPIRICAL` (`EPOCH_HOMOGENEITY = PASS / MAGNITUDE_VARIES / FAIL / NOT_ASSESSABLE`) rather than a separate class; `FAIL` still blocks any `CLAIM = MEETS_BAR`.

## 6. Rare-event track: `ACCUMULATING`

For mechanisms whose independent units arrive slowly (scheduled settlements, holidays, macro releases, regime episodes):
- the preregistration freezes the **information unit** (§5.1), the **accumulation target** (a count of units, not a date), the eras and venues that may contribute under §5.2, and the single analysis at the target;
- until the target is reached the unit's status is `EMPIRICAL = ACCUMULATING`; only counts of units are monitored; no estimate, no interim look;
- a unit may accumulate across historical eras and the prospective stream under one frozen rule; era is a declared cluster, and the epoch flag of §5.4 applies at analysis;
- the target may be raised before analysis by amendment; it is never lowered; reaching a calendar deadline below the target yields `INDETERMINATE`, not an analysis;
- `INFORMATIONALLY_WEAK` at feasibility is no longer a terminal state for a rare-event design that declares this track; it becomes the entry into `ACCUMULATING` with the required count stated.

`ACCUMULATING` is a live, unfinished experiment with a known finish line. It does not reopen any V1 result; a V1-closed rare-event hypothesis that wants this track is a new test family on data it has not seen, as V1 §8 already requires.

## 7. The 2025 disclosure tranche

- **One** preregistered, irreversible disclosure of the Binance 2025 surface (2025-01-01 .. 2025-12-31) for an **enumerated** set of hypotheses and families, with the multiplicity treatment frozen across the whole tranche before any 2025 value is read. The enumeration, the per-hypothesis frozen rules and the tranche-level Holm (or a pre-declared alternative) are one preregistration with one permit.
- A hypothesis not in the enumeration does not get 2025 later from this tranche; a further tranche would be a new owner decision, and V2 does not pre-authorize one.
- **2026 stays sealed.** E1-RUN-001 stays sealed. The six-symbol divergence surface already opened (2025-01-01 .. 2026-08-15) keeps its recorded status (`exposed for the divergence/support family; not spent for unrelated families; decided per family`) and is **not** silently folded into the tranche: a family that wants to use that surface says so in the tranche enumeration and carries the exposure label.
- The tranche is the natural first replication surface for `STRUCTURE_DETECTED` results whose mechanism post-dates BitMEX; it replaces, for them, a prospective wait to 2027+. Prospective replication remains available and remains the only surface for anything that reads 2026.

## 8. `PRODUCT_EVIDENCE` track

### 8.1 What it is

Permission for the product to use a **descriptive** fact: a baseline differs by weekday type; a profile shifts with the US clock; an hour is usually quieter after a given state. The forms of evidence are **calibration** (does a reference distribution match the nominal rates), **stability** (does the fact hold across epochs) and **transportability** (does it hold across venues or eras). Non-inferiority designs fit calibration questions; stability and transportability are descriptive with uncertainty. The method is declared per unit; "non-inferiority" is not imposed on questions that are not comparisons.

### 8.2 What it is not

It is not a reduced rung of `EDGE` promotion. A `PRODUCT_EVIDENCE` result never supports: a direction, a probability of direction, a bias or lean label, a target, a trade, or any sentence that implies the state predicts movement. The allowed vocabulary is the descriptive vocabulary of `BETA_COPY_CONTRACT_V1` ("обычно", "по сравнению с обычным", named comparator), and the unit's preregistration lists the exact sentences it may enable.

### 8.3 Allowed uses

`CALIBRATION_ALLOWED`: reference distributions, baselines, maturity rules, suppression and flag-rate calibration. `WORDING_ALLOWED`: a named descriptive sentence with its comparator and uncertainty. Each use is granted per unit by an owner decision recorded in the ledger (`PRODUCT_USE`), after the unit's own gates pass; the evaluator never grants it.

### 8.4 Replication

`REPLICATION = NOT_REQUIRED` for `PRODUCT_USE = CALIBRATION_ALLOWED` when the unit's design contains its own prospective guard (a counts-only, blinded prospective stage with a frozen stop and degradation guardrails, as in the weekday/weekend calibration design). `WORDING_ALLOWED` additionally requires stability across at least three epochs or a transportability check, as declared.

### 8.5 Reference design and first candidates

- **Reference design:** `WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1` (revision 5). It shows every element of the track: a product question, a calibration bar in product units, an availability guardrail, a blinded prospective stage with a count-defined stop, and no directional claim.
- **First candidates for an owner `PRODUCT_USE` decision under V2:** R03-C1 (weekend hours; `EMPIRICAL = STRUCTURE_DETECTED` is a V2 annotation, see §10) and D12 (US-clock profile shift, `PROMISING_PROTOTYPE` under its sprint rules). Neither becomes an edge claim; neither is granted anything by this draft.

## 9. Unchanged rules, restated

Twin preregistration (V1 §1) with the §5.1 fields added; claim type and variable roles (V1 §2) with the track declaration added; the nuisance baseline (V1 §3) unchanged, including the wording rule for context claims; integrity, statistical and epoch gates (V1 §4) unchanged in method; search surface and Holm within the test family (V1 §6) unchanged, with tranche-level multiplicity added for §7; no rescue (V1 §8) unchanged; product promotion of an `EDGE` claim (V1 §9) unchanged.

## 10. Migration

- **No V1 result is rescored.** Numbers, verdicts and ledger rows stand.
- **Annotation only.** A V1 result may receive the V2 `EMPIRICAL` field as an annotation computed from its **frozen** estimate and interval, with no new computation on market data, and recorded as a separate ledger field (`V2_EMPIRICAL_ANNOTATION`) beside the untouched V1 classification. Proposed annotations: R03-C1 → `STRUCTURE_DETECTED` with `CLAIM(PRODUCT_EVIDENCE) = NOT_DECLARED` (R03 declared no product track); C025-R1, R03-A2/A3/C3, B1/B3/B4 → `INDETERMINATE (feasibility)`; the six executed R03 cells other than C1 → `NO_STRUCTURE_DETECTED`. Annotations need an owner decision and are listed, not applied, here.
- **Ledger schema V2** adds the four fields of §2, the track declaration, and the §5.1 design fields; existing rows keep V1 fields verbatim.
- **Compiler V3** implements §5; V0–V2 compilers and their goldens stay reproducible and untouched.

## 11. Adoption (not yet)

| Field | Value |
|---|---|
| Adopted | — |
| By | — |
| Applies from | the commit that records adoption; cards registered after it; not retroactive |
| Prerequisites | owner review of this draft; ledger schema V2 and compiler V3 as separate implementation units; a red-team pass on §4 (bar functions as a new degree of freedom) and §7 (tranche enumeration) |

## 12. Open points for the owner

1. §3 precision condition: interval bound below the bar (as drafted) versus a stricter "bar outside a 90 % interval"; the drafted form uses the preregistered 95 % interval.
2. §5.3 floor of 60 % of the fallback variance: keep, raise, or drop the cap.
3. §7 tranche: who enumerates, and whether R03-C1 and D12 are inside the first tranche or only on the product track.
4. §8.4: whether `WORDING_ALLOWED` should always require a prospective stage, not only stability.
5. §10 annotations: approve the listed annotations as a batch or decide per unit.
