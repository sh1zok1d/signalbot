# RESEARCH_HISTORY_AUDIT_V1 — forensic audit of every research unit, H01 to the weekday/weekend unit

**Status:** COMPLETE, 2026-10-05. Audit record. It changes no verdict, result, sealed record, product or beta behaviour, and authorizes no execution.
**Question:** Which old hypotheses really showed no useful structure, and which were buried mainly by the old framework's conservatism?
**Governing rules:** `EVIDENCE_AND_CLAIMS_DECISION_V1.md`. Contract V1 keeps its force for units registered under it, and sealed verdicts stay as recorded.

**Machine records:**
- `RESEARCH_HISTORY_AUDIT_V1.json` — census, completeness proof, counts, lists, every unit row;
- `RESEARCH_HISTORY_AUDIT_V1_TABLE.md` — the per-unit table, all 188 units in chronological order;
- `audit/RESEARCH_HISTORY_AUDIT_V1_ASSESSMENTS.yaml` — the hand-written judgments;
- `scripts/research/history_audit.py` — the builder and coverage proof (`--check` writes nothing);
- `tests/research/test_history_audit.py`.

## 0. Honesty rules applied

- **Verdicts are historical facts.** Every row quotes the official verdict, its framework and the recorded closing reason unchanged. The audit adds a separate category, a conservatism judgment and a claim level beside it.
- **Numbers are copied, not reconstructed.** Every estimate is copied from the cited result record. Where no outcome was computed, the row says so and states no effect. Where an artefact is lost or unprovable, the row says that too (§2.3).
- **No computation on market data.** No outcome was computed, no surface opened, no rerun executed. §6 holds design outlines only; each needs its own owner go.
- **Significance is not enough.** A small p-value alone never earns "killed by conservatism". `YES` requires that the data show an effect, or that information was present, and that a framework rule — not the data — decided the closure.

## 1. What a "unit" is here

A **census unit** is a research object with its own question and identity:
- a tested hypothesis, a card or a seed;
- a frozen experiment;
- a feasibility-closed card;
- a product-evidence track the atlas carries.

**Census = 188 units:**
- all 187 units of the Research Atlas V1, which already transfers every earlier source;
- `WEEKDAY_WEEKEND_BASELINE_UNIT_V2` (2026-10-05), the last completed research unit on `main`. It postdates the atlas transfer.

**Listed separately, not counted as census units:**
- **6 child executions** under a parent (`child_executions` in the JSON): the D2 BitMEX replication (first run INVALID, corrected run SUPPORTED), the D2 excess path-risk decomposition, the D7 confirmatory run, the DH3-V3 replication, the GV0R01-C013 confirmation feasibility and the MARKET-04H adjudication.
- **6 methodology or certification units** that are not market hypotheses: the V1 autopsy, Harness V1, Harness V2, the inference-profile program that served D7, the compiler V3 variance floor and the compiler V3 estimator calibration. V3 Microscope is an atlas row.

**Not units (each reason recorded in `not_units`):**
- **H-001..H-016:** the initial inventory, folded into the V1 autopsy and E1.
- **16 linked generator attempts:** duplicates or neighbours of an earlier signature.
- **GV0V03L40 slots C011–C020:** never produced. C011 failed intake; C012–C020 were never emitted.
- **The evidence-format shadow report:** a re-presentation, not a new computation.
- **Tooling:** the compilers, the campaigns and the atlas itself.
- **"B01":** no unit carries this id. The early series are BATCH01 (H01–H05) and BATCH02 (B2-01..06), both fully in the census.

## 2. Completeness proof

### 2.1 Mechanical checks

`python -m scripts.research.history_audit --check` reconciles the census with every independent id source. It fails on any unplaced id; it passes today with zero problems.

| Source | Size | Result |
|---|---|---|
| Atlas units | 187 | every unit assessed: 143 explicitly; 44 idea-stage generator cards by their recorded blocker class |
| Generator memory chain `MECHANISM_MEMORY_V0.json` | 79 signatures | 79 / 79 in the census |
| Memory deltas (attempt records) | 65 attempts | 49 carry a census signature; the other 16 are linked attempts listed in `not_units` |
| `SCIENTIFIC_TEST_LEDGER.json` | 14 test families, 26 hypothesis ids | 26 / 26 resolved (alias `SEED0001-RD-V1` → `SEED-0001`) |
| `config/beta_research_findings.yaml` | 40 finding ids | 40 / 40 resolved through atlas aliases (`DIVERGENCE`, `DIVERGENCE-RSI`, `TWAP`, `C012`, `R03-C2-C4`) |
| `docs/RESEARCH_LEDGER.md` `##` headings | 258 headings | every unit-like id placed (28 distinct ids found) |
| `docs/research/` file names | 666 files | every unit-like id placed (31 distinct ids found) |

**What the file-name and heading scan covers.** It recognises the families H, B2, D, MARKET, GV0R01, GV0V03L40, DH and SEED. Other families — R03, G01, DH cells, the divergence line and the product tracks — have no id in their file names and come from the atlas, which was itself built fail-closed against the memory chain and the findings registry.

### 2.2 Chronology

`date` is the first git-add date of the unit's first non-generic record in this repository. That is when the evidence entered the repository, not necessarily when the work started.

| Range | Units |
|---|---|
| 2026-08 | 8 |
| 2026-09 | 65 |
| 2026-10 | 115 |

The first is E1-RUN-001 (2026-08-25), then H01 (2026-08-26). The last is WEEKDAY_WEEKEND_BASELINE_UNIT_V2 (2026-10-05).

### 2.3 Holes, conflicts, lost artefacts, ambiguous lineage

Each item is recorded and none is repaired here.

| Item | What is wrong | Effect on this audit |
|---|---|---|
| B2-02 | `RESULT_ARTIFACT_DURABLE_COPY = UNAVAILABLE` (post-run evidence-retention gap) | numbers rest on RESULT.md and the recorded digest; the classification is unaffected (clear negative) |
| B2-05 | development outcomes read; durable evidence archived under operator adjudication; historical bytes not cryptographically proven; no scientific RESULT | **not recoverable**; no result is reconstructed |
| D2 BitMEX replication | first one-shot `INVALID` on integrity, then a corrected one-shot `SUPPORTED` | the integrity process worked; the audit uses the corrected record |
| E1-RUN-001 | holdout outcome surface opened by the owner-run P4 follow-up (`INVALIDATED_FOR_P4_OVERLAP`) | a clean confirmatory reading is no longer available |
| R03-C3 | CARDS / PREREG say "no replication surface"; PLANNING / compiler used a prospective one | closure stands on the discovery MDE alone |
| G01-A3 | the ledger table shows replication "—"; FEASIBILITY.md lists 33 BitMEX months (MDE 1.010) | no effect; discovery MDE alone fails |
| R03-B2 | `PRODUCT_FREQUENCY_GATE = false` in RESULT.json, not mentioned in RESULT.md | no effect; primary gates failed |
| PRODUCT-V2-LEVELS / -ANALOGUES | no committed result numbers found | rows state no numbers |
| Memory vs atlas state | D7, GV0R01-C004/C012/C013/C020, GV0V03L40-C033 | already reconciled in the atlas `memory_reconciliation`; audit follows the atlas |
| H05 bot text | «не давал устойчивого продолжения или разворота» is broader than the record, which has a small, consistent SELL-side reversal (45/45 cells) | methodology finding §7.6; text not edited here (product text is out of scope) |
| H-002..H-016 | inventory hypotheses folded into E1 without separate verdicts | not units; nothing to classify |
| WEEKDAY_WEEKEND_BASELINE_UNIT_V2 | completed 2026-10-05 but not added to `atlas/ATLAS_UNITS_V1.yaml` (AGENTS.md asks for it in the same change) | carried here as a post-atlas unit; adding it to the atlas is an atlas-source change with its own hash-chained event, left to a separate change |

## 3. Taxonomy and counts

Categories (definitions in the assessments file):
- **Tested:** `REAL_NULL`, `STRONG_NEGATIVE`, `INSUFFICIENT_INFORMATION`, `BLOCKED_PRACTICAL_BAR`, `INFERENCE_LIMITATION`, `POSITIVE_ALIVE`.
- **Closed before an outcome:** `BLOCKED_FEASIBILITY_MDE`, `DATA_PROVENANCE_PIT`, `FLAWED_ESTIMAND_DESIGN`, `GOVERNANCE_BLOCKED`.
- **Never measured:** `NOT_TESTED_METHOD_BLOCK`, `NOT_TESTED_ANTI_RESCUE`, `NOT_TESTED_NOT_SELECTED`.
- **Other:** `EXPOSED_POTENTIALLY_USEFUL`, `PRODUCT_EVIDENCE`, `CERTIFICATION_MACHINERY`.

A unit that does not fit one category carries a second (`cat2`; 15 units).

| Category | Units | Of which an outcome was computed |
|---|---|---|
| NOT_TESTED_METHOD_BLOCK | 36 | 0 |
| REAL_NULL | 28 | 28 |
| BLOCKED_FEASIBILITY_MDE | 23 | 0 |
| NOT_TESTED_ANTI_RESCUE | 22 | 0 |
| DATA_PROVENANCE_PIT | 21 | 0 |
| NOT_TESTED_NOT_SELECTED | 15 | 0 |
| POSITIVE_ALIVE | 9 | 9 |
| BLOCKED_PRACTICAL_BAR | 7 | 7 |
| STRONG_NEGATIVE | 6 | 6 |
| FLAWED_ESTIMAND_DESIGN | 6 | 0 |
| PRODUCT_EVIDENCE | 6 | 2 |
| INSUFFICIENT_INFORMATION | 4 | 4 |
| EXPOSED_POTENTIALLY_USEFUL | 2 | 2 |
| INFERENCE_LIMITATION | 1 | 1 |
| GOVERNANCE_BLOCKED | 1 | 0 |
| CERTIFICATION_MACHINERY | 1 | 0 |
| **Total** | **188** | **59** (57 research + 2 product) |

**Conservatism judgment:**
- **YES 7.** A framework rule decided it, and the data showed an effect or the information was there.
- **PARTLY 11.** A rule was one of the deciding reasons; the data were also weak.
- **NO 118.** The data, or a correctness / provenance fact, decided it.
- **NA 52.** No evidential decision was taken: never tested, not selected, owner routing, product track.

**Maximum claim justified today:**
- **L2: 40.** 13 with positive or descriptive content, 27 informative nulls or negatives.
- **L1: 20.**
- **L0: 128.** Nothing measured, or nothing usable.
- **L3 / L4: none.** L3 needs live calibration, and none is logged yet.

## 4. Answers

**1. How many units in total?** 188 census units. Separately listed:
- 6 child executions;
- 6 methodology / certification units;
- excluded as non-units: 16 linked generator attempts, 10 never-produced ladder slots and the H-001..H-016 inventory.

**2. How many are genuine null or negative?** **34**: 28 `REAL_NULL` and 6 `STRONG_NEGATIVE`. That is 34 of the 57 research units with a computed outcome (60 %).
- 17 further untested ideas were closed as neighbours, relabels or rescues of closed units (`NOT_TESTED_ANTI_RESCUE`, conservatism `NO`); they are not counted as evidence.
- The 6 strong negatives are H01, H02, B2-02, B2-03, B2-04 and MARKET-06. Each claimed effect was reversed, or the feature made forecasts worse with an interval excluding zero.

**3. How many died mainly from lack of information?** **27**: 23 `BLOCKED_FEASIBILITY_MDE` and 4 `INSUFFICIENT_INFORMATION`.
- **20 are honest information limits** (`cons = NO`). Their clocks are monthly, event-driven, holiday-based or rare-state, with MDE 0.6–1.1 SD or 7–26 pp. Examples: R03-A2/A3/C3, G01-A3, GV0R01-C004/C012/C020, SEED-0001, SELLING-EXHAUSTION, E1.
- **7 were closed partly or wholly by a stacked rule** rather than by the information on the discovery surface: G01-A1 and G01-A2 (`YES`); R03-B1, R03-B3, R03-B4, G01-B1 and DH3-S2 (`PARTLY`).
- 21 more were blocked by data, provenance or PIT, which is availability, not information.

**4. How many were substantially affected by over-conservatism?**
- **Firm: 7 (`YES`). Upper bound: 18** with the 11 `PARTLY` cases. That is 3.7 % to 9.6 % of the census.
- **Among the 57 units with an outcome:** 5 `YES` (R03-C1, D3, DH3-P1, DH3-O2, DH3-L3) and 3 `PARTLY` (H04, H05, DH3-S1).
- **Partly recovered already:** R03-C1 received its second chance and is in the product as C1. DH3-P1, O2, L3 and S1 are already shown as «есть, но слабее порога» in `/research`.
- **Not counted:** 24 idea-stage generator cards blocked by a causal-identification / confounding standard. That standard is stricter than an L1/L2 descriptive question needs (flag `STANDARD_MISMATCH_POSSIBLE`), but with no estimate no effect can be said to have been lost.

**5. Best re-evaluation candidates and why.** See §6. In order:
- G01-A1/A2 turn-of-month (closed by the replication rule, not the discovery information; a product baseline question);
- D8 shock recovery (a design-support failure, not a null; product-relevant);
- R03-B1/B3 (near-miss stacked screen; low prior);
- H04 moderate-band continuation (pre-2020 surface only).

No rerun is needed for the units that already support L1/L2 — they need wording and live tracking, not recomputation.

**6. What cannot be honestly re-evaluated without new data?**
- **Confirmation of anything found on CORE 2020–2024**, because that surface is consumed. This covers DH3-P1/O2/L3/S1/P3/V3, D3, H04, H05, D11, D12 and GV0R01-C013. Paths: prospective data, or a pre-2020 surface with its exposure label. BitMEX 2017–2019 is recorded `NOT_PROVABLY_INDEPENDENT` for event questions.
- **Information-limited calendars and events** (R03-A2/A3/C3, G01-A3/B1, G01-X7/X10, DH3-X5, GV0R01-C004/C012/C020) need years of new events.
- **Data / PIT blocks** (B2-06, MARKET-04, D6, the generator data cards, S4-C04/06/07/09) need a provable source.
- **Not recoverable at all:** B2-05 (unprovable bytes) and E1-RUN-001 (no clean holdout remains).

**7. Which already support a useful L1/L2 claim?**
- **L2 with positive content:** D7 (confirmed), D2 (replicated; volatility-scale), D11 (FOMC 6h RV +76 %, N = 39, every year positive), DH3-P3, DH3-V3 (discovery; with its failed-replication caveat), DH3-P1 / O2 / L3 / S1 (range states, quantitative), R03-C1 (as the C1 baseline), H01's reverse side (volatility persistence), and the product range corridor (tracked).
- **L1:** D3 (24h excursions about 11–13 % smaller than a block surrogate), D12 (N = 10), TWAP (footprint exists), GV0R01-C013, SEED-0001 (inconclusive), MARKET-03 (external), H04 / H05 (post-hoc patterns), the weekday/weekend unit.
- **27 informative nulls at L2**, e.g. DH1-L2 «разница больше ±3 п.п. почти исключена», MARKET-01/02/05/06, R03-A1/A4/B2/C2/C4, DH2-L1/L3/B2. Most are already `NOT_CONFIRMED` lines.

**8. What does this say about the old pipeline?** §7 below. In short:
- most deaths were real;
- the conservatism that mattered was the **fixed magnitude bar used as a verdict switch** and **stacked feasibility screens**, not statistical caution as such;
- a large share of effort went into machinery and untested idea generation rather than into measurements.

## 5. The lists

### 5.1 POTENTIALLY_KILLED_BY_OLD_CONSERVATISM

**`YES` (7)** — a framework rule, not the data, decided the closure:

| Unit | Evidence | Rule that decided | Today |
|---|---|---|---|
| R03-C1 weekend hours | −0.396 SD (SE 0.036), Holm p 0.0001; −0.19 → −0.65 across 2020–2024, no opposite-sign year | 0.5 SD bar (0.40 < 0.50) | second chance done: WEEKDAY_WEEKEND_BASELINE_UNIT_V2 → product C1; as a mechanism mostly the volatility regime (nuisance-adjusted −0.10) |
| D3 path morphology | −13.3 % / −10.8 % / −4.5 % vs block surrogate; all three outside the 2.5–97.5 % band; temporally consistent | 15 % practical bar | L1 descriptive; low product value (the corridor already absorbs it) |
| DH3-P1 OI build-up in a quiet market → range | +13.4 % (CI +9.9..+17.1), Holm p 0.0015 | 15 % range bar; the CI overlaps the bar | L2 range line; live tracking for L3 |
| DH3-O2 DVOL jump → range | +9.6 % (CI +6.6..+12.5), Holm p 0.0015 | 15 % range bar | L2; MSE skill only +0.0001 |
| DH3-L3 book not recovered → range | +6.5 % (CI +1.9..+11.1), Holm p 0.012 | 15 % range bar | L2 |
| G01-A1 turn-of-month participation | no outcome; discovery unit MDE 0.486 < 0.5 bar | replication surface (36 BitMEX months) required to carry the same bar | candidate §6.A |
| G01-A2 turn-of-month range | no outcome; same unit sets as A1 | same | candidate §6.A |

**`PARTLY` (11)** — a rule was one of the deciding reasons; the data were also weak:

| Unit | Why partly |
|---|---|
| H04 trend pullback | Moderate-band continuation: MPIE 16/45, triple gate 10/45; L=960 moderate positive 5/5 years at H=15/30/240. Rejected by the two-adjacent-band neighbourhood plus the gate conjunction after a 45-cell search. Its child B2-04 measured a different estimand. |
| H05 taker imbalance | SELL-side reversal in 45/45 cells, but matched delta ≤ 0.052 vs the 0.10 MPIE bar and a nine-way conjunction; tiny and one-sided |
| DH3-S1 spot-led stress → range | −5.9 % (CI −10.1..−1.4), below the bar and opposite to the stated mechanism |
| R03-B1, R03-B3, R03-B4 | Passed the compiler (MDE 0.34–0.35); closed by the second paired-month screen at Holm alpha 0.0125 (MDE 0.54–0.60 vs 0.5). The sibling B2 was null; B4's metric is also artefact-prone. |
| G01-B1 ETF fixing hour | Unit MDE 0.5005 vs 0.5 (a cliff edge). The decisive weaknesses are real: a single launch and an unresolvable hour confound. |
| DH3-S2 | MDE 6.7 pp vs a 6 pp rule; its sibling S1 contradicts the mechanism |
| DH1-X10, DH3-X2 | The taker-family ban inherits from H05 (small one-sided effect) and B2-05 (no provable result) |
| DH3-X7 | Cites the R03-B "null neighbourhood", but only B2 of B1–B4 was executed |

### 5.2 TRUE_NEGATIVE / NULL (34)

- **REAL_NULL (28):**
  - B2-01, D4, D5, D9, D10, D13, H03, H-DIV-1;
  - DH1-L2, DH2-L1, DH2-L3, DH2-B2;
  - DH3-L1, DH3-L2, DH3-O1, DH3-O3, DH3-P2, DH3-V1, DH3-V2;
  - DIVERGENCE-FULL-HISTORY-V0;
  - MARKET-01, MARKET-02, MARKET-05;
  - R03-A1, R03-A4, R03-B2, R03-C2, R03-C4.
- **STRONG_NEGATIVE (6):** H01, H02, B2-02, B2-03, B2-04, MARKET-06.

**Notable details:**
- **B2-01 and DH3-V2** are real but negligible effects. Any sensible bar rejects them.
- **D13's two estimators disagree in sign:** IC −0.027 against a Q5−Q1 spread of +0.79 %. The code signs the spread by the pooled IC, so the gate failed correctly.
- **DH1-L2, DH2-L1 and DH2-L3 carry the official label INCONCLUSIVE**, yet their intervals exclude anything beyond about ±3–3.5 pp. Here the old vocabulary under-stated a null.

### 5.3 Needs new data or prospective evidence (52)

`lists.NEEDS_NEW_DATA_OR_PROSPECTIVE` in the JSON. Grouped:
- **Prospective calibration of live findings:** D2, D7, D11, D12, DH3-P3, DH3-V3, GV0R01-C013, DH3-P1/O2/L3/S1, PRODUCT-V2-RANGE, the weekday/weekend unit.
- **Pre-2020 or prospective replication of post-hoc patterns:** H04, H05.
- **Event and calendar accumulation:** R03-A2/A3/C3, G01-A3/B1/X7/X10, DH3-S2/X5, GV0R01-C004/C012/C020, EVCORR-K1-CPI/FOMC.
- **Provable data sources:** B2-06, MARKET-04, D6, DH1-X7/X8, DH3-X1, S3-C6, S4-C04/06/07/09/12, and the 10 generator data cards.
- **Owner decision plus prospective data:** RSI-GRADIENT-SUPPORT.

**Not recoverable:** B2-05 and E1-RUN-001.

## 6. Best re-evaluation candidates — design outlines only, not executed

Each needs its own design note committed before any outcome and its own owner go. No method may be chosen after looking.

### A. Turn-of-month baseline (G01-A1 / A2) — highest value per cost

- **Why.** It was closed by the rule that a 36-month replication surface must carry the same 0.5 SD bar, not by the discovery information (unit MDE 0.486). It is the same kind of question as weekday/weekend, a baseline-calibration fact for the unusual-hour flags, which needs L1, not L4.
- **Estimand.** Shift in standardized log range / participation on turn-of-month days against the same UTC hour on other days. It would be reported as an estimate with a month-clustered interval and per-year values, with no pass bar.
- **Data.** CORE 2020–2024 (59 months). Exposure label: the surface is exposed, and this contrast was never computed. It is retrospective, L1 at most.
- **What would change our mind.** An interval inside ±0.15 SD means no product change. A clear shift that is stable by year means a baseline adjustment question, handled like C1.

### B. D8 shock recovery — a new object, not a rerun

- **Why.** Closed as `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`; recovery was never evaluated. It is product-relevant for `/risk`.
- **What a retry needs.** A new id and a design whose comparison has support by construction. The frozen D8 thresholds stay frozen; any new design is a new object, not a weakened D8.
- **Estimand.** Recovery-time distribution after large shocks against volatility-matched hours. Pre-2020 BitMEX could serve as an independent surface, with its exposure label.

### C. R03-B1 / B3 panel states — low priority

- **Why.** They passed the compiler and were closed by a stacked unit-level screen.
- **Option.** An estimate with an interval on the existing panel (L1 context).
- **Prior is low:** the sibling B2 is null. B4 stays closed because its metric is a fee-promotion artefact.

### D. H04 moderate-band continuation — only on a fresh surface

- **What.** The exact H04 moderate band (L=480/960) frozen as recorded, with no band or horizon search. It must run on Binance spot or BitMEX 2017–2019, or prospectively.
- **Prior is low.** It is directional, and directional effects here have repeatedly failed to repeat (DH3-V3).

### No rerun needed

- **D11, D7, D2 and DH3-P1/O2/L3/S1/P3/V3:** they need the L2 quantitative wording and the prospective claim journal (`docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md`), not a recomputation.
- **D11 specifically:** its user-facing event lines stay withheld until the K1 event-window semantics pass. That is product safety, not research conservatism.

## 7. Methodology problems found

1. **Fixed magnitude bars used as verdict switches.**
   - The bars were 0.5 SD, 15 % range, 2 % MAE, 20 % relative and MPIE 0.10. Each turned a measured effect into `NO_USEFUL_STRUCTURE` / `NO_INCREMENTAL_STRUCTURE`.
   - This was the single largest source of misleading verdict words: 5 of the 7 `YES` cases.
   - A bar is a product decision about materiality. It belongs in the claim decision, not in the evidence verdict.
2. **Stacked feasibility screens before any estimate.**
   - The rule was compiler MDE, then unit-level MDE at the Holm first-step alpha, then a replication surface carrying the same bar.
   - This closed G01-A1/A2, R03-B1/B3/B4, G01-B1 (by 5e-4) and DH3-S2 without a single number.
3. **Gate conjunctions without conjunction power.**
   - Batch01 required primary ∧ MPIE ∧ structural ∧ +6h ∧ three bootstraps ∧ 4/5 years ∧ symmetry ∧ q/H adjacency. Batch02 used a five-gate conjunction plus robustness.
   - The power of the conjunction under a true modest effect was never computed.
   - Most Batch01/02 units failed cleanly anyway; H04 and H05 are the cases where it mattered.
4. **A verdict vocabulary that mixes "precisely zero" with "uninformative".**
   - `INCONCLUSIVE` was used for DH1-L2 and DH2-L1/L3 even though ±3 pp is excluded.
   - `NO_USEFUL_STRUCTURE` was used for D3, which had stable structure.
   - `INFORMATIONALLY_WEAK` sits beside `NO_STRUCTURE` without the interval that tells them apart.
5. **Causal-identification standards at idea stage.**
   - 24 generator cards were blocked for identification or confounding, the standard for a mechanism or edge claim, before any descriptive estimate.
   - This produced zero false positives and zero information.
6. **Anti-rescue rules inherited from weak parents.**
   - The taker-flow family is closed because of H05, which shows a small one-sided effect, and B2-05, which has no provable result.
   - The H05 bot line states a broader null than its record.
7. **Machinery cost.**
   - Harness V1 (non-claimable), Harness V2 (development-consumed), V3 Microscope (NULL indeterminate, trap fail) and the compiler V3 variance line (unpassable at realistic N, CLOSED) produced no market evidence.
   - Generator V0 produced 65 attempts and one market test.
8. **Provenance gaps:** B2-02 (durable copy unavailable) and B2-05 (unprovable bytes). The D2 replication integrity catch shows the process could also detect such problems.
9. **The binding constraint is information, not caution.** Many questions live on monthly, event or holiday clocks with 40–60 units in five years. No method rescues that, and it is reported as such.

**What the old pipeline did right:**
- Protected data were respected; the one breach (P4/E1) was recorded openly.
- Integrity failures were caught (the first D2 BitMEX run was declared INVALID).
- Nulls were reported as nulls. 34 of 57 tested units are genuine nulls or negatives, so the pipeline did not hide failure, and its rejections mostly stand.

## 8. Decision

**Useful now (no new computation):**
- D7, D2 and D11 at L2;
- DH3-P3 and DH3-V3 as «Гипотеза» at L2 with their caveats;
- DH3-P1/O2/L3/S1 as quantitative L2 range lines;
- R03-C1 via C1;
- H01's reverse side;
- the 27 informative nulls as L2 «не подтвердилось» lines with their intervals.

Any wording change is a product change and needs its own go. This audit edits no product text.

**Stays closed:**
- every `REAL_NULL` and `STRONG_NEGATIVE` (34);
- every honest information limit (20);
- every correctness-based block (lookahead, PIT, provenance);
- the divergence / selling-exhaustion line (owner routing);
- B2-05 and E1-RUN-001 (not recoverable);
- V3 and the compiler V3 line (closed machinery).

**Second chance:**
- Already given: R03-C1 → C1.
- Proposed: G01-A1/A2 turn-of-month baseline (§6.A, first) and a new D8-successor shock-recovery object (§6.B).
- Low priority: R03-B1/B3 (§6.C) and H04 on a fresh surface (§6.D).
- Each needs an owner go and a design note before any outcome.

**Not started here:** no new research program, no rerun, no protected surface, no claim beyond `EVIDENCE_AND_CLAIMS_DECISION_V1`.

## 9. Validation

- `python -m scripts.research.history_audit --check`: zero problems; every source id placed.
- `python -m pytest -q tests/research/test_history_audit.py` passes.
- `git diff --check` is clean.
- No product, beta, config, sealed-record or atlas-source file changed.
