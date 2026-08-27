# R2 Screening Protocol V1

**Status:** ACTIVE  
**Scope:** R2 mechanism discovery, R3 candidate freeze, R4 validation  
**Supplements:** `docs/EDGE_RESEARCH_PROTOCOL.md` and `docs/RESEARCH_ROADMAP.md`

This protocol exists to reduce both false positives and false negatives while Signalbot repeatedly explores the same long-history discovery dataset.

The discovery dataset is a laboratory. Repeated exploration is allowed there, but repeated exploration is not independent confirmation.

## 1. Evidence pools are fixed

For `CORE_BTC_BINANCE_V0` snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`:

- **DISCOVERY LAB:** 2020-02-01T00:00:00Z through 2025-01-01T00:00:00Z
- **BATCH VALIDATION:** 2025-01-01T00:00:00Z through 2026-01-01T00:00:00Z
- **FINAL OOS:** 2026-01-01T00:00:00Z through 2026-08-26T00:00:00Z

The discovery lab is permanently considered contaminated-for-discovery: it may be reused to generate and develop hypotheses, but no later analysis on that same window may be described as independent confirmation.

**Red-team fix (BLOCKER):** these boundaries are pinned to snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`. If
`CORE_BTC_BINANCE_V0` is superseded by a new accepted snapshot while Batch
01 is still in progress, the evidence pools above must be explicitly
re-validated and re-frozen against the new snapshot's own observed date
range before any further hypothesis in the batch proceeds. A silent
carry-forward of these exact timestamps onto a different snapshot is not
authorized.

**Red-team fix (BLOCKER — boundary/horizon embargo):** any candidate or
outcome computation whose required resolution horizon would read
price/volume data at or after a later pool's start boundary is embargoed
from the earlier pool and MUST be excluded from that pool's
development/validation population for that horizon. Per-event horizon
truncation is not allowed: it would mix different outcome definitions near
the boundary and silently change the estimand. A decision boundary is
eligible for horizon H only when the entire frozen outcome path resolves
strictly before the pool's `end_exclusive` boundary. This applies at both
the DISCOVERY LAB / BATCH VALIDATION boundary and the BATCH VALIDATION /
FINAL OOS boundary. This mirrors the `+4h` purge already applied at the
E1-RUN-001 development/holdout boundary (`docs/RESEARCH_LEDGER.md`);
without an explicit embargo here, a discovery-phase outcome computed for a
candidate near 2024-12-31 could silently read 2025-01-01+ price bars,
contradicting Section 1's claim that BATCH VALIDATION remains untouched by
discovery-phase analysis.

## 2. R2 Batch 01 is frozen before H03

R2 Batch 01 contains exactly five primary mechanism families:

1. H01 — Compression → Expansion
2. H02 — Failed Breakout → Mean Reversion
3. H03 — Extreme Impulse → Continuation vs Exhaustion
4. H04 — Trend Pullback → Continuation
5. H05 — Taker Imbalance → Subsequent Return Distribution

H01 and H02 are already consumed discovery experiments.

No 2025 validation outcomes may be opened until H01-H05 are all closed with one of:

- `REJECTED_SPECIFIC_CLAIM`
- `INCONCLUSIVE`
- `CANDIDATE_FOR_FREEZE`

A null result is acceptable. Batch size must not be expanded because early hypotheses fail.

## 3. Validation is opened as a batch, not sequentially

After H01-H05 finish:

- freeze every surviving candidate rule;
- freeze all candidate parameters, direction/sign, metrics, controls and verdict criteria;
- record the full global search ledger;
- only then open 2025 validation for the frozen survivor set.

Do not:

- open 2025 after the first attractive candidate;
- retune one candidate after seeing another candidate's 2025 result;
- repeatedly reuse 2025 as a fresh holdout.

All frozen survivors are evaluated in the same validation batch.

**Red-team fix (MAJOR — cross-candidate verdict leakage):** verdict
criteria, MPIE thresholds and control definitions are frozen before 2025
is opened and may not be reinterpreted, reweighted or relaxed based on any
candidate's 2025 outcome, including a sibling candidate's result opened in
the same batch. A shared macro/regime observation surfaced by one
candidate's 2025 result may be recorded as context but must not soften
another candidate's already-frozen promotion criteria. "Do not retune
parameters" is not sufficient on its own -- reinterpreting the bar itself
is the same failure mode by another route.

## 4. Final OOS is rarer evidence

2026 remains untouched until the 2025 batch is complete.

Only candidates that survive their frozen 2025 validation may enter the 2026 final-OOS batch.

Before 2026 is opened:

- freeze the finalist set;
- freeze every rule and verdict criterion;
- record which hypotheses/variants were searched in discovery and validation.

A failed 2026 finalist is not repaired using 2026.

## 5. Global adaptivity and search ledger

Research accounting is global, not only per experiment.

The ledger must track at minimum:

- primary hypothesis families attempted;
- material parameter variants per family;
- primary outcome cells;
- secondary outcome families;
- post-hoc child ideas generated;
- candidates promoted;
- validation attempts;
- OOS attempts;
- control/baseline formulations attempted per family, not only the one reported;
- hypothesis-design-adaptation notes (see below).

A later winner must never be described as though it were the only hypothesis tested.

Do not use a simplistic Bonferroni threshold as the sole decision rule. The purpose is transparent selection accounting and selection-aware interpretation.

**Red-team fix (MAJOR — control shopping):** trying several candidate
negative-control or baseline formulations and reporting only the one that
makes a mechanism look cleanest is the same failure mode as
threshold-shopping. Every control/baseline formulation actually attempted
for a family, not only the one used in the final writeup, must appear in
the ledger.

**Red-team fix (MAJOR — batch-internal design adaptation):** when a Batch
01 hypothesis's mechanism definition, threshold family, or feature
construction was influenced by an unexpected observation from an earlier
hypothesis in the same batch (including H01/H02's post-hoc observations),
that influence must be explicitly declared in the ledger as a
design-adaptation note before that hypothesis's development results are
opened. Silence on this point is not equivalent to independence -- a later
hypothesis quietly shaped around an earlier one's failure mode is adaptive
reuse of the discovery lab even though no single parameter was "retuned."

**Red-team fix (MINOR — ledger timing):** each hypothesis's ledger entry
(search surface, verdict, and post-hoc observations) must be recorded
contemporaneously, before the next hypothesis in the batch is opened for
development -- not reconstructed retroactively at batch completion.

**Red-team fix (MAJOR — batch restarting):** any future R2 batch beyond
Batch 01 remains subject to this same global ledger and is interpreted
jointly with the cumulative search surface of all prior batches. Starting
a new batch does not reset or exempt prior batches' adaptivity accounting,
and must not be used to functionally re-enlarge a batch that failed in
full under a new name.

## 6. Specific-claim rejection is narrower than phenomenon rejection

A failed preregistered claim means exactly that claim failed.

Examples:

- symmetric H03 fails because only DOWN impulses work:
  - symmetric H03 = `REJECTED_SPECIFIC_CLAIM`
  - downside-only idea = `POSTHOC_UNTESTED`

- H01 compression→expansion fails while low-vol persistence appears:
  - H01 expansion = `REJECTED_SPECIFIC_CLAIM`
  - persistence idea = `POSTHOC_UNTESTED`

Do not rescue the parent experiment by redefining it after outcomes.

Post-hoc child ideas may be logged for future work, but are not automatically promoted into Batch 01 validation.

## 7. Post-hoc child ideas are not Batch 01 candidates

Any hypothesis materially created from an unexpected H01-H05 development result is labeled:

`POSTHOC_UNTESTED`

It does not enter the R2 Batch 01 validation set.

This prevents repeated branching on the same discovery sample from silently inflating the effective search surface.

Post-hoc ideas may seed a later research batch or future-data experiment.

## 8. Candidate promotion requires practical magnitude, not significance alone

Large sample size can make tiny effects statistically stable.

Therefore every future directional/non-directional experiment from H03 onward must preregister a **minimum practically interesting effect (MPIE)** before real outcomes are opened.

Rules:

- MPIE must be expressed in the experiment's primary normalized metric;
- raw bps / raw-vol magnitude must also be reported unless the metric has no well-defined raw-magnitude form; a claim that raw magnitude is "not meaningful" must be stated explicitly in the writeup, not silently omitted;
- bootstrap CI excluding zero is not sufficient by itself;
- promotion requires the effect neighborhood to meet or materially exceed MPIE;
- if no defensible MPIE can be stated before outcomes, that experiment cannot be promoted to R3 on statistical significance alone.

**Red-team fix (MAJOR — MPIE anchoring):** MPIE must be justified against
a reference independent of the candidate's own development-sample
estimated effect. For mechanism-discovery experiments, prefer a
distributional anchor available without candidate outcomes -- for example
a fixed fraction of the unconditional/local median absolute move or
volatility scale used by the primary normalized metric, or a comparable
magnitude drawn from prior independently published evidence. Realistic
execution cost may be used as an additional anchor only when the claim
being made is explicitly about tradability; R2 mechanism discovery must
not be converted into a hidden PnL gate. An MPIE whose only stated
justification is "this is what the candidate happens to show in
development" is not acceptable, and any resulting promotion must be
treated as `INCONCLUSIVE` regardless of the observed effect. Without this,
a trivially small preregistered MPIE could make promotion easy to game,
while an arbitrarily large one could kill real effects for no principled
reason -- the requirement to preregister MPIE only closes the "significance
alone" loophole if the number itself cannot be chosen freely by whoever
is about to see the outcome.

Economic/trading profitability is still a later question. MPIE is a research relevance floor, not a PnL requirement.

## 9. Parameter neighborhoods, not magic cells

A candidate is promoted based on a predeclared neighborhood, not the best cell.

The neighborhood must show:

- coherent sign;
- non-fragile neighboring thresholds/lookbacks;
- at least two adjacent horizons when horizons are part of the claim;
- no dependence on one isolated optimum.

One magic cell may generate a `POSTHOC_UNTESTED` idea but cannot promote the parent family.

**Red-team fix (MINOR — magic-cell promotion disclosure):** if a magic-cell
`POSTHOC_UNTESTED` idea is later promoted to its own dedicated future
hypothesis, that hypothesis's preregistration must disclose the size of
the parent family's parameter scan (already required in the Section 5
ledger) from which it emerged, so a future reader is not misled into
treating it as an unsearched, freshly prespecified cell.

## 10. Chronological stability is descriptive and gating

Development must report 2020, 2021, 2022, 2023 and 2024 separately.

For a proposed candidate neighborhood:

- the required sign should normally hold in at least 4 of 5 years;
- one year may be weaker/null;
- repeated sign reversals block promotion.

This is a robustness gate, not five independent significance tests.

**Maintainer correction (MAJOR — regime-scoped claims without calendar
rescue):** the 4-of-5 rule applies to an unconditional mechanism claim.
Named calendar-year or event exclusions (for example "ignore 2020" or
"ignore 2022") are not an authorized escape hatch, even when declared
before computing the experiment's per-year outcome table, because the
historical path and those event labels are already known during discovery
and can themselves become a source of adaptive selection. If a mechanism
is genuinely intended to be regime-scoped, that scope must be part of the
hypothesis preregistration before real outcomes are opened and must be
implemented as a deterministic state rule using only information available
at decision time T (for example a trailing-volatility or trend state), not
as retrospective calendar/event deletion. The complete gated rule,
coverage and yearly distribution must then be evaluated as the claim.
A regime explanation invented after seeing which years disagree remains
`POSTHOC_UNTESTED` and cannot rescue the parent claim.

## 11. Claim scope controls side requirements

Do not require symmetry unless the claim is symmetric.

If a preregistered symmetric claim requires UP and DOWN effects, both sides must support that claim.

If only one side survives:

- reject the symmetric claim;
- record the asymmetric observation as `POSTHOC_UNTESTED`.

This prevents a genuine narrow effect from being erased conceptually while also preventing post-hoc rescue.

## 12. Dependence sensitivity for survivors

UTC-week block bootstrap remains the primary dependence-aware uncertainty method.

Any proposed R3 candidate must additionally run fixed sensitivity using:

- 1-week blocks;
- 2-week blocks;
- 4-week blocks.

These are robustness checks, not selectable alternatives.

The conclusion should not depend on choosing the block length that gives the narrowest favorable interval.

**Red-team fix (MAJOR — block-length adequacy diagnostic):** BTC regime
persistence (a single bull/bear leg) can plausibly exceed 4 weeks, in
which case even 1w/2w/4w block sensitivity could all understate true
dependence and inflate apparent confidence. Every R3 candidate must
additionally report a fixed, non-selectable autocorrelation-decay or
effective-sample-size diagnostic computed on the underlying return/outcome
series over the full development window. This diagnostic is descriptive
only -- it is not a new selectable block length and does not gate
promotion by itself -- but a diagnostic implying dependence materially
longer than 4 weeks must be disclosed alongside the block-sensitivity
results and flagged for qualitative caution in the freeze writeup, rather
than silently left unreported.

## 13. Control hierarchy

Every mechanism must face:

1. unconditional or matched-time baseline;
2. a simple structural baseline that removes the claimed incremental ingredient where possible;
3. at least one timing/feature negative control appropriate to the mechanism.

A complex mechanism that does not beat the simpler structural explanation is rejected in that form.

Secondary metrics cannot rescue a failed primary outcome.

## 14. Discovery verdicts

Use exactly these meanings:

### REJECTED_SPECIFIC_CLAIM

The preregistered mechanism, as scoped, did not earn more complexity.

This does not prove all neighboring phenomena are impossible.

### INCONCLUSIVE

Evidence is coherent enough not to reject cleanly, but insufficient for freeze work.

Do not open validation.

### CANDIDATE_FOR_FREEZE

Development evidence is strong enough to justify one controlled R3 freeze step.

This is not validated evidence.

### POSTHOC_UNTESTED

An observation generated after outcome inspection that may motivate future work but has no independent evidentiary status.

## 15. Candidate-for-freeze minimum requirements

A candidate should normally satisfy all of:

1. primary outcome has the preregistered sign;
2. effect neighborhood meets the preregistered MPIE;
3. candidate separates from matched/random baseline;
4. candidate separates from the simplest relevant structural control;
5. negative control materially weakens/destroys the effect;
6. neighboring parameter values are coherent;
7. at least two adjacent horizons support the claim when applicable;
8. proposed sign is stable in at least 4/5 development years;
9. no single month/regime dominates;
10. dependence-aware uncertainty is compatible with a real effect under 1w/2w/4w block sensitivity;
11. claim-scope requirements such as UP/DOWN symmetry are satisfied when explicitly preregistered.

A failure of one scope-specific requirement rejects that scope; it should not be rhetorically generalized beyond the tested claim.

## 16. No validation rescue

Once 2025 is opened for the batch:

- no candidate may be retuned using 2025 and still call 2025 independent validation;
- revised candidates return to discovery status;
- the consumed validation evidence remains consumed for that lineage.

The same rule applies more strongly to 2026 final OOS.

**Red-team fix (MINOR — operationalize "stronger" for 2026):** for 2026
final OOS specifically, "stronger" means: a candidate revised after 2026
is opened does not merely return to discovery status -- its original
lineage is permanently closed as a failed final-OOS attempt and may not
re-enter any future validation/OOS batch under the same claim. Only a
materially distinct future hypothesis, developed and frozen without
reference to the specific 2026 outcome, may be considered later.

## 17. R2 Batch 01 completion

Batch 01 completes only when H01-H05 are closed and the global ledger is frozen.

Then:

- zero survivors → do not open 2025 merely for curiosity;
- one or more survivors → freeze all survivors, then open 2025 once as a batch.

The project is allowed to discover zero usable mechanisms.
