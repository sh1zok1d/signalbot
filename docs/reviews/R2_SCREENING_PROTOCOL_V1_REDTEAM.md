# R2 Screening Protocol V1 — Independent Methodological Red-Team

**Reviewed:** PR #74 "docs(research): freeze R2 screening protocol v1"
**Repo:** `sh1zok1d/signalbot`
**Reviewed branch/SHA:** `research/r2-screening-protocol-v1` @ `fd0b8355bc402e099c0a4a1fdbed1267a1d21239`
**Base:** `research/core-btc-binance-v0-discovery-acceptance`
**Reviewer role:** adversarial research-methodology audit only. No hypothesis started, no 2025/2026 outcomes inspected, no H03 run, no forecasting/product code touched.

This report is the persisted, GitHub-hosted record of the audit. A fix branch/PR exists (see **Fixes** below) applying only the narrow textual corrections this report identifies.

---

## Method

Read completely before forming any judgment: `docs/R2_SCREENING_PROTOCOL_V1.md` (the document under review), `docs/EDGE_RESEARCH_PROTOCOL.md`, `docs/RESEARCH_ROADMAP.md`, `docs/RESEARCH_LEDGER.md`, `docs/manifests/CORE_BTC_BINANCE_V0.yaml`. Verified the snapshot hash cited in the protocol (`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`) matches the manifest's `snapshot_id` byte-for-byte (it does). Checked whether H01/H02 already have ledger entries in `docs/RESEARCH_LEDGER.md` at this commit (they do not — see Minor-1 below). Cross-checked the document's boundary handling against the E1-RUN-001 precedent already in the ledger (`development +4h purge prevents development future reads from entering holdout`), which is directly relevant to Blocker-1.

---

## Findings

### BLOCKER

**B1 — No embargo/purge at pool boundaries (Section 1: "Evidence pools are fixed").**
- **Failure mode:** the document declares three fixed pools (DISCOVERY LAB / BATCH VALIDATION / FINAL OOS) but never states what happens when a candidate's outcome-resolution horizon extends past its own pool's `end_exclusive` boundary. A candidate generated near 2024-12-31 with, say, a 5-day or 4-week outcome horizon would need to read price bars into 2025 — i.e. into BATCH VALIDATION — to compute its own discovery-phase outcome.
- **Risk:** false positive / contamination risk. It directly undermines the document's own foundational claim that "the discovery lab is permanently considered contaminated-for-discovery" while BATCH VALIDATION stays untouched — for boundary-adjacent candidates that claim would be false as written.
- **Concrete example:** H04 (Trend Pullback → Continuation) or H03 (Extreme Impulse → Continuation vs Exhaustion) plausibly use multi-day horizons. A candidate detected 2024-12-28 with a 5-day horizon resolves 2025-01-02, inside BATCH VALIDATION — its development-phase feature/outcome computation would silently touch validation-window prices.
- **Evidence this is fixable and known-to-the-project:** `docs/RESEARCH_LEDGER.md`'s E1-RUN-001 section already implements exactly this discipline elsewhere ("development +4h purge prevents development future reads from entering holdout"). The R2 protocol simply didn't carry it forward.
- **Remediation applied:** added an explicit embargo rule to Section 1 — any candidate/outcome whose horizon would read data from a later pool is either excluded from the earlier pool or has its horizon truncated to stay strictly inside it. Applies at both pool boundaries.

### MAJOR

**M1 — Batch-internal hypothesis-design adaptation isn't required to be logged (Sections 2 & 5).**
H01/H02 already produced specific post-hoc observations (low-vol persistence; small generic short-horizon bounce). H03–H05 are not yet run. Nothing requires disclosing whether H03–H05's mechanism definitions, thresholds, or feature construction were shaped by knowledge of H01/H02's failure modes. A rejected mechanism could be quietly reintroduced under a new hypothesis label without being flagged as non-independent. *Example:* H03's impulse-volatility threshold set just above the band that would have captured H01's compression definition, with no declared link. **Fix applied:** Section 5 now requires a design-adaptation ledger note whenever a later hypothesis's definition was influenced by an earlier one's outcome.

**M2 — Cross-candidate verdict-criteria leakage inside one validation batch not addressed (Section 3/16).**
The document forbids *retuning a candidate's parameters* after seeing another candidate's 2025 result, but says nothing about reinterpreting or loosening *verdict criteria* (MPIE, control definitions) based on a sibling candidate's 2025 read. *Example:* candidate A misses MPIE in 2025 in a way attributable to an unusual 2025 regime; that regime narrative is then used to retroactively excuse candidate B's shortfall. **Fix applied:** froze verdict criteria/MPIE/control definitions explicitly against sibling-candidate reinterpretation in Section 3.

**M3 — Control/baseline "shopping" is not a tracked ledger category (Sections 5 & 13).**
Section 13 requires controls but leaves the exact formulation to researcher discretion ("appropriate to the mechanism"). Section 5's ledger tracks parameter variants but not control/baseline variants tried. Trying several negative controls and keeping only the flattering one is symmetric to threshold-shopping and just as capable of manufacturing a false positive. **Fix applied:** added "control/baseline formulations attempted per family" to the Section 5 ledger list.

**M4 — MPIE has no anchoring principle (Section 8).**
The document correctly bans "significance alone," but never states how MPIE itself must be derived. An MPIE justified only by "what this candidate shows in development" can be set trivially small (promotion becomes easy) or arbitrarily large (real effects get killed) with no guardrail either way — this is the exact false-positive/false-negative pair the audit was asked to check for. **Fix applied:** MPIE must now be justified against a reference *independent of the candidate's own development-sample effect* (execution-cost fraction, unconditional volatility fraction, or prior published magnitude); an MPIE justified only by the candidate's own numbers forces `INCONCLUSIVE`.

**M5 — Flat "4 of 5 years" default has no prespecified shock-exclusion path (Section 10).**
2020 (COVID crash/recovery) and 2022 (rate-hike/FTX collapse) are two widely-recognized outlier years inside the five-year development window. A real, regime-scoped mechanism could legitimately show 3-of-5 rather than 4-of-5 sign consistency purely because two of five years are historically atypical — a genuine false-negative risk the audit explicitly asked about. Simply loosening the threshold would reopen exactly the post-hoc-rescue door the rule exists to close. **Fix applied:** added a narrow, outcome-blind escape valve — a hypothesis may *prespecify*, before any per-year result is inspected, a fixed shock-period exclusion list, reported separately; it cannot be chosen or adjusted after seeing which years disagree.

**M6 — Fixed 1w/2w/4w blocks may understate true BTC regime persistence (Section 12).**
A single BTC bull/bear leg can run many months — plausibly longer than the 4-week upper sensitivity bound. If so, even passing all three block lengths could reflect underestimated dependence rather than a real effect (false-positive risk via overstated confidence). The audit explicitly asked for a *bounded diagnostic, not a new parameter search* — adding e.g. 8-week/16-week blocks would just expand the tunable surface. **Fix applied:** added a required, non-selectable autocorrelation-decay/effective-N diagnostic, reported alongside (not instead of) the fixed 1w/2w/4w results, flagged for caution — not itself a new gate.

**M7 — Serial batch-restarting is not bound to the same cumulative ledger (Sections 5 & 17).**
"Do not enlarge Batch 01 because all five fail" is well-designed, but nothing stops the same fishing behavior re-emerging as "Batch 02, Batch 03, …" each nominally respecting the no-enlargement rule while achieving the identical effect over time. **Fix applied:** any future batch is explicitly bound to the same global ledger and interpreted jointly with all prior batches' cumulative search surface.

### MINOR

**m1 — H01/H02 have no corresponding entry in `docs/RESEARCH_LEDGER.md` at this commit**, even though Section 2 treats them as "already consumed." The document doesn't specify *when* per-hypothesis ledger entries must be written (immediately on closure vs. batched at the end) — deferred logging risks hindsight-shaped reconstruction. **Fix applied:** ledger entries must be written contemporaneously, before the next hypothesis in the batch opens.

**m2 — "when meaningful, also report raw bps/raw-vol magnitude" (Section 8)** is a hedge a researcher could always invoke to skip raw-magnitude reporting. **Fix applied:** raw magnitude must be reported unless the metric genuinely has no raw-magnitude form, and that exemption must be stated explicitly, not silently assumed.

**m3 — Magic-cell promotion doesn't require disclosing the parent scan size (Section 9)**, even though that size is already required elsewhere in the Section 5 ledger. **Fix applied:** a promoted magic-cell idea's own future preregistration must cite the parent family's scan size.

**m4 — "The same rule applies more strongly to 2026" (Section 16) is asserted but never operationalized** — unclear what "stronger" concretely forbids beyond the 2025 rule. **Fix applied:** stated explicitly that a 2026-revised candidate's lineage is permanently closed, not merely returned to discovery status.

**m5 — Snapshot-revision reconciliation is unaddressed (Section 1).** If `CORE_BTC_BINANCE_V0` is superseded by a new snapshot mid-batch, the document doesn't say the pinned date boundaries must be re-frozen against it. **Fix applied:** added an explicit re-validation requirement, folded into the same Section 1 edit as B1.

### NO ISSUE (explicitly checked, found sound — listed so this isn't mistaken for an oversight)

- Section 1's "permanently contaminated-for-discovery, not merely disallowed" framing.
- Section 2's frozen five-hypothesis batch + explicit no-enlargement-on-failure rule.
- Section 3's freeze-everything-before-opening-2025-as-one-batch discipline.
- Section 4's 2026 nesting and no-repair-on-failure rule (apart from m4's wording gap).
- Section 5's explicit rejection of Bonferroni-as-sole-decision-rule.
- Sections 6/7's `REJECTED_SPECIFIC_CLAIM` vs. phenomenon-impossibility distinction, and the non-promotion of post-hoc children into Batch 01 — this is exactly the mechanism the audit's Q6 asked for, already present.
- Section 8's explicit "not a PnL requirement" and ban on promoting via significance alone (apart from M4's anchoring gap).
- Section 9's `POSTHOC_UNTESTED` treatment of a single magic cell — exactly the "honest scoping without post-hoc rescue" the audit's Q8 asked for.
- Section 11's symmetric-claim-rejects/asymmetric-observation-preserved split — the strongest section in the document; directly matches the audit's own H03 example.
- Section 13's three-tier control hierarchy (reasonable given the dataset's own single-venue scope — no Bybit/OKX cross-venue control is possible with the currently accepted dataset, which is a data-capability limit, not a protocol defect).
- Section 14's four verdict labels — each is precisely worded to avoid overstating evidence.
- Section 16's core no-validation-rescue rule for the ordinary case (apart from m4's wording gap).
- MPIE being scoped to "H03 onward," exempting the already-rejected H01/H02 — sound, since MPIE guards against false *promotion*, and H01/H02 were not promoted.
- The DISCOVERY LAB starting 2020-02-01 rather than the dataset's 2020-01-01 start — a sensible feature/indicator burn-in buffer, not a flaw.

---

## False-positive risks

Concentrated in: M3 (control shopping), M4 (unanchored MPIE), M6 (dependence blocks too short for true BTC regime persistence), M1 (design adaptation smuggling a rejected mechanism back in under a new label), and B1 (boundary bleed silently inflating apparent "clean, untouched" validation evidence).

## False-negative risks

Concentrated in: M5 (flat 4-of-5 years unfairly killing a real regime-scoped mechanism in a sample containing two outlier years), and — as explicitly checked and found already well-handled — the magic-cell/parameter-neighborhood question (Section 9's `POSTHOC_UNTESTED` path already avoids discarding a genuine narrow effect).

## Holdout reuse assessment

- **2020–2024 (discovery lab):** correctly declared permanently contaminated-for-discovery-only; repeated reuse for generation/development is allowed and honestly labeled as never independent confirmation. Sound, subject to B1's boundary-embargo fix.
- **2025 (batch validation):** correctly gated as one-shot-per-frozen-batch, not sequential; sound, subject to M2 (cross-candidate criteria leakage) and B1 (boundary bleed) fixes.
- **2026 (final OOS):** correctly nested behind 2025 survival; sound, subject to m4 (operationalizing "stronger") and B1 fixes.

## Global search accounting assessment

Directionally correct and above the naive per-hypothesis-cell standard (explicitly rejects Bonferroni-as-sole-rule, tracks families/variants/post-hoc children/promotions/validation/OOS attempts). Two blind spots closed by this red-team: control/baseline-formulation search (M3) and cross-hypothesis design-adaptation influence (M1), plus binding future batches to the same cumulative ledger (M7).

## MPIE assessment

The mechanism (preregister before outcomes, ban significance-alone promotion, require normalized + raw magnitude) is sound in structure. The missing piece was calibration: nothing prevented MPIE itself from being chosen freely by whoever is about to see the outcome. Fixed by requiring an independent anchor (M4).

## Dependence assessment

UTC-week block bootstrap plus fixed 1w/2w/4w sensitivity is a reasonable, non-gameable default, but BTC's actual regime persistence can plausibly exceed 4 weeks. Fixed with a bounded, non-selectable diagnostic (M6) rather than an expanded parameter search, per the task's own instruction.

## Post-hoc hypothesis policy assessment

This is the strongest part of the document. `POSTHOC_UNTESTED` correctly separates falsifying a specific preregistered claim from claiming a neighboring phenomenon is impossible (Sections 6, 7, 9, 11), and correctly refuses to let a post-hoc idea piggyback into the same batch's validation. No changes were needed here beyond the narrow disclosure/logging additions in M1 and m3.

## Fixes

Applied (13 total: 1 BLOCKER, 7 MAJOR, 5 MINOR) as narrow textual amendments to `docs/R2_SCREENING_PROTOCOL_V1.md` only — no research outcomes added, no hypothesis started, no code touched.

- fix branch: `research/r2-screening-protocol-v1-redteam`
- fix SHA: `835b297d5e2bb974a6318f99240a1e6be154ab8f` (created from exact base `fd0b8355bc402e099c0a4a1fdbed1267a1d21239`)
- fix PR: opened as **draft** against `research/r2-screening-protocol-v1`, not merged

## Validation contamination

- 2025 inspected: **NO**
- 2026 inspected: **NO**

## Final verdict

**C — PROTOCOL HAS MATERIAL METHODOLOGICAL FLAWS — H03 BLOCKED**, as written at `fd0b8355bc402e099c0a4a1fdbed1267a1d21239` (one BLOCKER: no boundary/horizon embargo between the three evidence pools, directly undermining Section 1's core "fixed evidence pools" claim; plus seven MAJOR gaps in adaptivity/control-shopping/MPIE-anchoring/chronological-robustness/dependence-adequacy/batch-accounting).

The narrow fixes above are proposed on branch `research/r2-screening-protocol-v1-redteam` / draft PR against `research/r2-screening-protocol-v1` for maintainer review and merge. This report does not itself authorize H03 — that requires the maintainer to accept (or otherwise resolve) the fixes.
