# Research rules review V1 — what to keep, change or drop (PROPOSAL)

**Date:** 2026-10-09.
**Author:** chief architect, on the owner's request: «пересмотреть правила по ресерчу — что тупо, что нет».
**Status:** `PROPOSAL`. Nothing here is in force until the owner adopts it. Until then, the current rules (AGENTS.md, the atlas §5, the decisions cited below) apply unchanged.

## 1. The owner's question

> Why can't we reuse data that was already used, if we honestly don't rewrite hypotheses after the fact and don't tune anything after opening it?

**Short answer.**
- **For discovery: we can, and the current rules are too strict.**
- **For confirmation: we can too, as long as that data was never used to pick or test *this* hypothesis.** Data does not wear out. A specific question wears out on a specific dataset.
- **The current rules count exposure by dataset and atlas row.** That blocks clean confirmations of unrelated hypotheses. Exposure should be counted by relation.

## 2. Why honesty alone does not make confirmation valid on the same data

Two reasons. Neither is about dishonesty.

1. **Selection arithmetic.**
   - Test 40 honest, untuned ideas on 2020–24 at a 5 % level: about 2 will look real by chance.
   - Re-checking those 2 on the same 2020–24 "confirms" them, because it is the same data.
   - So the data used to *select* a hypothesis cannot be the data that *confirms* it.
   - This is why P3 went from −5.9 pp in discovery to −1.7 pp on new data: shrinkage after selection is normal.
2. **Knowledge leakage.**
   - After seeing results on a dataset, new ideas are shaped by them, with no explicit tuning. For example, the knowledge that crowd positioning "worked" on 2020–24 shapes the next positioning idea.
   - Such a hypothesis is not independent of that data for that question.

Neither reason applies to a **different** question on the same data. The answer to "does signed path asymmetry predict 4h direction?" was never seen on BitMEX 2016–19 just because D7 read BitMEX volume for a different relation.

## 3. Proposed core rule: exposure per relation, not per dataset

- **Relation R** = (state family, outcome family, horizon class). Example: (signed path asymmetry, up-first barrier race, 1–8h).
- **A surface is EXPOSED for R** if any test was read on it whose result depends materially on R. That means the same or a strongly correlated state, or a state the hypothesis was derived from, with the same outcome family. Otherwise the surface is **CLEAN for R**, even if it was used for other relations.
- **Discovery** may use any surface. Every test is logged before its result (design note commit). The discovery threshold rises with the number of tests already run on that surface (§4, rule 12).
- **Confirmation** of R must use a surface CLEAN for R: time-disjoint, another market or era, or prospective. One shot, no rescue.
- **The ledger records relations read per surface**, not "row consumed". Existing row entries are kept as history and reinterpreted through this rule.

This is what makes "honest" verifiable rather than a matter of trust: the hypothesis and its search are committed before the data is opened.

## 4. The rules, one by one

| # | Rule (source) | Verdict | Why | Replacement |
|---|---|---|---|---|
| 1 | Exposure by surface and atlas row; `CONFIRMATION_ON_EXPOSED` (atlas §5; `ATLAS_SURFACES_V1.yaml`) | **CHANGE** | Blocks clean confirmations of relations never examined there (e.g. BitMEX 2016–19 for path asymmetry) | Relation-level exposure (§3) |
| 2 | 2025/2026 is never a confirmation surface for anything overlapping product features (PRODUCT_DECISION_V2 §4; DIRECTIONAL_HYPOTHESES_DECISION_V1: "no 2025/2026 object") | **CHANGE** | The product computed range, volatility and level statistics there, not every relation. 19 months of fresh confirmation data are being thrown away. | 2025–26 is CLEAN for any relation the product or research never read there. E1 holdout aside, it counts as time-disjoint confirmation data. |
| 3 | Family-wide closures after one or a few nulls: the taker family (via H05/B2-05), "family J sessions exhausted" (DH1-X4), D7/D12 child bans, "no second H04 child", the closed divergence/exhaustion line | **CHANGE** | One null closes one formulation, not a mechanism family. The history audit (§291) found anti-rescue rules inherited from weak parents. The memory itself says "no row closes a family". | Closure covers the tested formulation and its parameter neighbours. The family gets a lower priority, not a ban. Owner-closed lines stay closed until the owner reopens them. |
| 4 | No new threshold, window or horizon on a closed cell (PARAMETER_NEIGHBOR) | **KEEP** | This is the most common p-hacking route, and its prior value is low | A variant is allowed only as a predeclared sensitivity inside a new design, never as a rescue |
| 5 | Causal identification required before an idea may be tested (generator red team; e.g. GV0R01-C002 blocked) | **DROP** for predictive research | The aim is prediction that holds out of sample. The audit counted 24 cards closed at idea stage with zero information. | Predictive tests need out-of-sample confirmation, not causal identification. Causal wording stays banned. |
| 6 | Feasibility screens and MDE gates that stop a cheap test from running (audit §277: stacked screens) | **CHANGE** | Partly fixed already (EVIDENCE_AND_CLAIMS: feasibility numbers are information) | Run cheap tests and report the interval. MDE is information, not a gate. |
| 7 | Fixed magnitude bar as a verdict switch (0.5 SD, 15 %, 3 pp) | **already changed** by EVIDENCE_AND_CLAIMS V1 | — | For direction, also report the cost-adjusted value: break-even 0.5 + c/(2X), as information. 3 pp was untradeable for P3. |
| 8 | Design note before any outcome; frozen search space; report every test | **KEEP** | This is the mechanism that makes honesty checkable | — |
| 9 | One-shot confirmation; no rescue inside a confirmatory run | **KEEP** | Without it every miss becomes "almost" | — |
| 10 | Discovery and confirmation kept apart; a selected relation is DISCOVERY_ONLY on its surface | **KEEP** | The core of rule §3 | — |
| 11 | Claim ladder: a historical frequency is not a current probability; L3 needs live calibration | **KEEP** | Prevents the commonest overclaim | — |
| 12 | Multiplicity: Holm only within a unit; no program-level count | **ADD** | Hundreds of cells were run on CORE 2020–24 (H01–H05 alone: 225). Per-unit Holm ignores that. | Ledger of tests per surface. A discovery on a heavily mined surface needs a stricter bar (e.g. \|t\| ≥ 3, Harvey–Liu–Zhu) or program-level FDR. |
| 13 | E1-RUN-001 holdout protected until E1 completes or closes | **OWNER DECISION** | Its pristine status is already `INVALIDATED_FOR_P4_OVERLAP`. Protecting it still costs product history and research data. | Finish E1 with its frozen evaluator, or close it as technically incomplete; then release the window |
| 14 | "No new research programs" (PRODUCT_FIRST §1) | **DROP** (superseded) | Contradicts `FIND_DIRECTIONAL_MARKET_STATES` | — |
| 15 | Heavy machinery (hash-chained atlas events, derived generator views, compilers) | **SIMPLIFY**, not urgent | Audit §294: a large share of effort went into machinery | Keep the atlas map and the ledger; no new machinery |
| 16 | Outcome-blind generator view | **KEEP** for confirmation candidates | Data-driven discovery (Cursor's pre-impulse atlas) is allowed under DISCOVERY_FIRST, so the blind view is not needed there | — |

## 5. What changes immediately if adopted

- **P3_CONFIRMATION_V1 on 2025–26 becomes a valid time-disjoint confirmation.** No one had read crowd → direction there. Its NOT_CONFIRMED stands, and the governance deviation is resolved.
- **BitMEX 2016–19 and Binance spot 2017–19 become CLEAN** for path asymmetry, occupancy, countermove decay and session direction (S1, A1, C1, T2, T3). Those relations were never read there.
- **Binance 2025–26 becomes a second confirmation surface** for those same relations. It stays exposed for range/volatility, levels, leverage crowding, and the unconditional 4h path distribution.
- **The flow-response idea (E1):**
  - its discovery surface is BitMEX trades 2017–19, because CORE is exposed for the absorption relation (B2-05);
  - it still needs an owner reopen of the taker/absorption family under rule 3.
- **Session ideas (T2, T3)** stop being banned by "family J exhausted". They remain separate units with their own design notes.

## 6. What does not change

These are non-negotiable:
- design before outcome;
- full test ledger;
- one-shot confirmation;
- no rescue;
- discovery ≠ confirmation;
- no trade calls in user texts;
- no historical frequency stated as a current probability;
- sealed records are never rewritten.

## 7. Owner decisions requested

1. Adopt relation-level exposure (§3, rules 1–2) in place of dataset/row exposure.
2. Narrow family closures to the tested formulation (rule 3). Say which owner-closed lines stay closed (divergence/exhaustion, taker family).
3. Drop causal identification as a gate for predictive tests (rule 5).
4. Add the program-level multiplicity rule (rule 12).
5. E1-RUN-001: finish with its frozen evaluator, or close as technically incomplete (rule 13).
