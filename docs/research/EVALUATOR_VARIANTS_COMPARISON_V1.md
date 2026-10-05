# Evaluator variants — comparative note on DH3-P1, G01-A1 and R03-B1 (V1)

**Status:** `NOTE FOR AN OWNER DECISION (2026-10-05) / NOTHING RUN / CHANGES NOTHING`
**Source of truth:** git, `main` at `c2b1316`. Chat summaries are not used. Every number is either copied from the cited record or labelled as planning arithmetic on recorded numbers.
**Governing rules:**
- `EVIDENCE_AND_CLAIMS_DECISION_V1.md`: §3 method chosen by design, §4 ladder, §5 journal, §7 exclusions and infrastructure stop rule;
- `COMPILER_V3_VARIANCE_LINE_CLOSURE_V1.md`: the line is closed, and its lesson applies;
- `RESEARCH_HISTORY_AUDIT_V1.md`: candidate order.

**What this note does not do.**
- **Nothing computed, read or started.** No outcome was computed, no surface opened and no data read. No unit is started and no design note is written for any unit.
- **Nothing changed.** No verdict, record, finding text, registry entry, atlas source or product code is touched.
- **No posterior evaluator exists.** The repository contains no `POSTERIOR_EVALUATOR_V1` object; a full-text search finds neither the name nor the phrase. None is created here.

## 0. Question and short answer

**Question.** What would each of three evaluation variants give for three concrete units? Is variant 1 enough, or does `EVIDENCE_AND_CLAIMS_DECISION_V1` need an amendment?

**Short answer.**
- **The data surface sets the ceiling, not the estimator.** For each unit, the reachable claim level comes from the data surface and its exposure. No variant lifts any of the three above what variant 1 already allows:
  - DH3-P1 stays L2 until live calibration;
  - G01-A1 and R03-B1 reach L1 at most from a first retrospective computation.
- **Variant 2 is already available inside variant 1, unit by unit.** §3 lists "Bayesian or partial pooling" as a method a design note may choose.
  - It helps in two narrow places: sibling pooling for R03-B1, and a new-era predictive band in P1's live evaluation rule.
  - For G01-A1 it reduces to variant 1, because its participation endpoint has no commensurable reference set.
- **Variant 3 conflicts with the decision record and adds nothing here.**
  - It contradicts §7 in four named items, and it is new research infrastructure (§7 stop rule).
  - It would estimate its prior and weights from at most 57 heterogeneous outcomes. That is the regime the compiler closure found uncertifiable.
  - Its "confidence" number would be an L3-like statement without live calibration (§4).
  - For these three units it adds no information.
- **Recommendation: variant 1 is enough, and no amendment is needed.** Appendix A has an optional one-paragraph clarification. It would only draw the line between a prior from named, commensurable units (allowed by §3) and a universe prior (excluded by §7), before a first design note relies on that line. Whether to adopt it, like everything else here, is the owner's decision.

## 1. The three variants as compared

| | Variant 1 — L0–L4, method per unit | Variant 2 — posterior only for suitable classes | Variant 3 — general posterior evaluator |
|---|---|---|---|
| Source | `EVIDENCE_AND_CLAIMS_DECISION_V1.md` (in force) | not written as a standing rule; per unit it is §3 "Bayesian or partial pooling" | chats only; GO cancelled; nothing built |
| Estimator | chosen per unit in a design note, before the outcome | as variant 1; for a unit of a suitable class the note picks a posterior | one evaluator for every unit |
| Prior | none required | per unit, from a listed reference set (siblings: same endpoint, unit, scale, design), with a sensitivity row | one universe prior over all units |
| Eras | the "stability" field: sign and size by era | per unit, partial pooling across eras where the note declares it | an era hierarchy in every evaluation |
| Strength | numbers only (estimate, interval, N); no verbal scale until the journal calibrates one (§4) | as variant 1 | confidence = statistics × regime × mechanism |
| Against current rules | in force | allowed per unit (§3) | conflicts with §7 four times: Bayesian program, universe prior, regime classifier, mechanism score; and the §7 stop rule (new infrastructure) |

**"Suitable class", as used below.** All three conditions are needed:
- **(a) A reference set exists.** It is a list of named units with the same endpoint, unit of analysis, scale and design, fixed before the outcome.
- **(b) The prior can matter.** The unit's own uncertainty is not negligible against the spread of that set.
- **(c) The decision needs what a posterior gives directly.** That is a chance that a shift exceeds a materiality value, or a predictive band for a new era.

## 2. Why these three units

Together they cover the three situations in the audit's candidate list.

| Unit | Situation | Outcome computed? | Where new evidence could come from |
|---|---|---|---|
| DH3-P1 | measured; below a materiality bar; surface consumed | yes, 2020–2024 | prospective only: there are no pre-2020 OI metrics (card P replication is "live only", `DH3_DESIGN.md` §5) |
| G01-A1 | monthly clock; closed at feasibility; a product-baseline question | no | a first retrospective estimate on exposed 2020–2024 (L1 at most); BitMEX 2017–2019 with its label; future months |
| R03-B1 | panel state; closed by a stacked screen; executed sibling null | no | a first retrospective estimate on 2020–2024 (L1 at most); the declared prospective panel from 2027-01-01 |

## 3. Facts per unit (copied from the records)

### 3.1 DH3-P1 `LEVERAGE_LOADING` → next-4h range

- **Records:** `DH3_RESULT.md` §1; `DH3_RESULT_DISCOVERY.json` `CELLS/DH3-P1`; `DH3_DESIGN.md` §2–§3.
- **State.** Among hours whose prior 4h range is in the bottom tercile: 4h OI change in the top tercile vs not.
  - Surface: Binance USD-M BTCUSDT, discovery 2020-10..2024-12.
  - Nuisance: the 4h block of the UTC hour, the 24h RV tercile and the lagged 4h range tercile.
- **Estimate.** +13.4 % (adjusted log shift 0.1255; 95 % CI +9.9 … +17.1 %), Holm p 0.0015, MSE skill +0.0077. N 12397 (3581 state / 8816 comparator), 210 week clusters.
- **By year.** Log β with its SE, then ≈ exp(β) − 1:

  | Year | β (SE) | ≈ % | Note |
  |---|---|---|---|
  | 2020 | 0.260 (0.075) | +30 | from 2020-10 only; 221 state hours |
  | 2021 | 0.030 (0.054) | +3 | |
  | 2022 | 0.122 (0.037) | +13 | |
  | 2023 | 0.153 (0.029) | +17 | |
  | 2024 | 0.080 (0.025) | +8 | |

  Heterogeneity p 0.048 and no opposite-sign year (`PASS_MAGNITUDE_VARIES_BY_EPOCH`).
- **Bar and class.** The bar is log 1.15 (+15 %), the product's range materiality. The class is `NO_INCREMENTAL_STRUCTURE` because the CI is not wholly above the bar.
- **Audit row.** `BLOCKED_PRACTICAL_BAR`, conservatism `YES`, maximum claim L2, needs `PROSPECTIVE`.
- **In the bot.** `config/beta_research_findings.yaml` `DH3-P1` has status `WEAK` and a `live:` block, matched on its frozen state. The integration is merged at `423b9b8` and not deployed (`DOCUMENTATION_INDEX.md`).
- **Not a model-integration candidate.** `RESEARCH_EVIDENCE_INTEGRATION_V1.md` excludes it as below the 15 % bar.
- **Not in the claim journal.** It is not among the first classes in `BETA_CLAIM_JOURNAL_DESIGN_V1.md` §6.

### 3.2 G01-A1 `TOM_PARTICIPATION`

- **Records:** `AUTOGEN_G01_CANDIDATES.md`, `AUTOGEN_G01_FEASIBILITY.{md,json}`, `AUTOGEN_G01_DECISION.md`.
- **Question.**
  - **State:** turn-of-month UTC days: the last day of the previous month and days 1–3, minus the last-Friday expiry day and the fixed holiday windows.
  - **Comparator:** days 8–21 of the same month.
  - **Outcome:** z(log daily trade count), standardized per year and weekday class.
  - **Unit:** the calendar month. Expected sign: positive.
- **Information.**
  - Discovery: 59 months, 203 state / 826 comparator days.
  - Compiler: n_eff 163, MDE stress 0.439.
  - Unit screen: SE_stress 0.174 and MDE 0.486 at alpha 0.05 (`HOLM_M = 0`; see §7.1).
  - Replication: 36 BitMEX months, MDE 0.632.
- **Official result.** `INFORMATIONALLY_WEAK` (`REPLICATION_MDE_TOO_LARGE`); never frozen or executed.
- **Audit row.** `BLOCKED_FEASIBILITY_MDE`, conservatism `YES`, maximum claim L0, needs `OWNER_DECISION`. It is the first candidate, together with A2 (audit §6.A).
- **Product relevance (card).** Activity ranks and baselines: a turn-of-month shift would mis-calibrate a 30-day activity baseline.

### 3.3 R03-B1 `RETURN_DISPERSION_HIGH`

- **Records:** `OWNER_CARDS_R03_CARDS.md`, `OWNER_CARDS_R03_FEASIBILITY.{md,json}`, `OWNER_CARDS_R03_RESULT.md`.
- **Question.**
  - **State:** the day-d cross-sectional SD of daily log returns on the top-100 USDT spot panel is at or above its trailing-180-day P80.
  - **Outcome:** BTC standardized log range of the next UTC day, against the other eligible days of the same month.
  - **Unit:** the month. Expected: wider.
- **Information.**
  - Discovery: 49 months with both arms, 353 state / 1142 comparator days.
  - Compiler: n_eff 269.6, MDE stress 0.341.
  - Unit screen: SE_stress 0.163, MDE 0.544 at alpha 0.0125 (m = 4).
- **Official result.** `INFORMATIONALLY_WEAK_AT_UNIT_LEVEL`; never executed.
- **Audit row.** Conservatism `PARTLY`, maximum claim L0, low priority (§6.C).
- **Siblings.**
  - **R03-B2** shares the panel, design, endpoint and unit. Result: +0.037 SD (SE 0.057), p 0.53; nuisance-adjusted −0.173, worded "reflects the general volatility regime".
  - **B3** was not executed.
  - **B4** should stay closed: its metric is a fee-promotion / FDUSD artefact.
- **Declared replication.** A prospective Binance spot panel from 2027-01-01: at least 365 days, ≥ 60 state and ≥ 240 comparator days. Not started.

## 4. What each variant would give

### 4.1 DH3-P1

| | Variant 1 | Variant 2 | Variant 3 |
|---|---|---|---|
| Computation | none: the estimate exists | optional re-summary of the recorded yearly betas; on a consumed surface it changes wording only | re-evaluation through the universe prior, era hierarchy and score; wording only |
| What may be said | L2 now, in the §4 quantitative format (illustration below) | the same level | the same level at most; an L3 "confidence" would still need the journal (§4, §5) |
| Effect on the number | — | the centre barely moves (see below); what it adds is a predictive band for a new year | prior-dependent shrinkage from a pool of incommensurable units |
| New evidence | prospective only: a P1 claim class in the journal | the same | the same |
| Product decision | the 15 % bar becomes a materiality decision on the claim, not an evidence verdict; whether the corridor uses P1 stays an owner `MODEL_INTEGRATION_CANDIDATE` question | the new-era band is the honest yardstick for the journal's evaluation rule, i.e. which live result counts as "held" | the regime factor double-counts; the mechanism factor is opinion |
| Needs | a wording change (product go) and a P1 class in `BETA_CLAIM_JOURNAL_V1_IMPL` (owner go) | the same, plus one line in that class's design note | a §7 reversal and new infrastructure |

**Why the centre barely moves under variant 2.**
- P1's own SE is about 0.016 log, read off its recorded CI.
- That is far below the spread among the nine DH3 range cells: P1, P2, L1, L3, O1, O2, V2, S1 and S3, from −5.9 % to +13.4 %.
- So any shrinkage toward that family is small.

**Why variant 3's factors fail here.**
- **Regime factor:** P1 is already a quiet-regime state, and its nuisance already holds the RV tercile and the lagged range.
- **Mechanism factor:** "leverage released" is untested as such, and the neighbouring deleveraging cell P2 was null.

**Illustration of the variant 1 line.** This is not product text; a wording change needs its own go.
> «В истории похожих часов (BTC, Binance, 2020–2024): следующие 4ч были шире на 13 % (95 % интервал +10..+17 %), чем в тихие часы без роста OI, с поправкой на волатильность; N = 3581 против 8816; по годам 2021–2024 от +3 до +17 %»

### 4.2 G01-A1

| | Variant 1 | Variant 2 | Variant 3 |
|---|---|---|---|
| Computation | a first retrospective estimate on CORE 2020–2024 under a design note (owner go): month-clustered interval, per-year values, no pass bar | as variant 1 with a prior, but no commensurable set exists for this endpoint (see below) | the result is prior-dominated (see below) |
| What may be said | L1 at most, e.g. «в 2020–2024 в дни смены месяца сделок было на X SD больше, чем в середине месяца (интервал …; 59 месяцев)» | the same | the same |
| New evidence | the first computation is new information for this contrast (never computed); confirmation needs later months, or BitMEX 2017–2019 with its label | the same | nothing beyond variant 1 |
| Product decision | the direct product question is the calibration of the activity flags and baselines on those days; `WEEKDAY_WEEKEND_BASELINE_UNIT_V2` is the template (nominal-rate gaps, a fixed decision rule) | a chance that the shift exceeds materiality would be the natural output; with only a vague prior it is about the variant 1 interval | the regime factor has no meaning for a calendar baseline; the mechanism ("fiat-rail cash flows") is untested opinion |
| Needs | owner go and a design note | the same, plus a declared prior that this endpoint does not have | a §7 reversal and new infrastructure |

**Why variant 2 reduces to variant 1 here.**
- **Calendar cells measure range.** Every executed calendar cell (R03-A1, A4, C1, C2, C4) has a range endpoint.
- **The participation evidence does not fit.** G01-B1 was never run. D12 measures participation timing, but with a different statistic on N = 10 transitions.
- **So the prior has two options.** It is either vague, which gives variant 1, or borrowed across endpoints, which is the universe-prior zone of §7.
- **G01-A2 differs.** It has a range endpoint, so a reference set from the R03 calendar range cells would exist for it.

**Why variant 3 is prior-dominated here.** No outcome exists yet, and the unit's own uncertainty is about 0.07–0.17 SD. The answer would largely restate a prior built mostly from directional, MAE and range units unrelated to calendars.

**Information (planning arithmetic on recorded numbers; no outcome read).**
- **Stress SE:** 0.174 SD.
- **Realized vs stress SE in the six executed R03 cells:**
  - 0.41–0.55 where each day gives one window (A1, A4, B2, C2, C4);
  - 1.55 for C1, which has 24 correlated hours per day.
- **Expected half-width.** If G01-A1 behaves like the first group, its 95 % half-width is about 0.14–0.19 SD.
- **Consequence for the audit's §6.A rule.** That rule reads "an interval inside ±0.15 SD means no product change". It is then reachable only for an estimate near zero at the low end of that range. A design note should also say what follows when the interval is neither inside ±0.15 SD nor clearly away from zero.

### 4.3 R03-B1

| | Variant 1 | Variant 2 | Variant 3 |
|---|---|---|---|
| Computation | a first estimate under a design note (owner go), raw and nuisance-adjusted (prior 24h RV, lagged target); which is primary is fixed before the outcome | the most natural case for pooling (see below) | universe prior plus a "regime" factor; here the regime is the confounder itself (see below) |
| What may be said | L1 at most | L1 at most | L1 at most |
| Information | B1's stress SE is 0.163; its sibling B2 realized SE 0.057 against stress 0.137 (ratio 0.41), so B1 would be about ±0.13 SD if alike | the same data; the posterior moves toward B2's ≈ 0 by an amount the spread prior sets | no more data |
| Product value | low: the 24h corridor already conditions on realized volatility; at most an L1 context line «в дни высокой дисперсии альтов…» | the same | the same |
| Needs | owner go and a design note | the same, plus a declared sibling prior and a sensitivity row | a §7 reversal and new infrastructure |

**Why variant 2 fits R03-B1 best of the three.**
- B1, B2 (already known: +0.037) and, if computed, B3 share the panel, the design, the endpoint, the unit and the comparator.
- A sibling posterior would replace Holm with shrinkage toward the family.
- With two or three cells, the spread between cells is not identified. Its prior decides the result, so a sensitivity row is mandatory.

**Why variant 3's regime factor fails here.**
- Dispersion rises with market-wide volatility. B2's adjustment moved its estimate from +0.04 to −0.17.
- The per-unit nuisance model already handles this without a classifier.

## 5. Across the three units

1. **Surfaces set the ceiling, not estimators.**
   - **P1:** its surface is consumed and there is no pre-2020 OI. Its wording can change now; its evidence can only come prospectively.
   - **G01-A1 and R03-B1:** their first computations would run on an exposed surface, so they reach L1 at most.
   - A posterior on a consumed surface is a re-summary. Audit §4.5–§4.6 already says so: confirmation of anything found on 2020–2024 needs prospective or pre-2020 data, and units that already support L1/L2 need wording and live tracking, not recomputation.
2. **Where a posterior helps, variant 1 already allows it.** There are three narrow uses:
   - sibling pooling (R03-B1);
   - a new-era predictive band in a live evaluation rule (P1);
   - a chance that a shift exceeds materiality (G01-A2, not A1).

   Each is a per-unit method choice under §3. None needs a standing rule.
3. **What variant 3 would cost, and why it fails here.**
   - **Rules.** It reverses §7 in four items and triggers the §7 stop rule (new infrastructure).
   - **The prior.**
     - It would be estimated from at most 57 outcomes on incommensurable scales: pp, % range, SD, MAE and IC.
     - Those units were selected by red team and a feasibility gate that new units no longer pass through, so the prior would be mis-specified for future units.
     - Calibrating it is the ≤ 100-effective-unit problem the compiler closure records.
   - **Eras.** There are five calendar eras. The between-era variance is weakly identified, so its prior decides the result.
   - **Confidence.**
     - "Statistics × regime × mechanism" multiplies a statistic by two author-assigned factors. The product is neither a probability nor calibrated.
     - Shown to users, it is the uncalibrated strength scale that §4 forbids. Kept internal, it is a mechanism score, which §7 excludes.
   - **Gain for these units: none.** None of the three gets a higher claim level, a different product decision or new information from it.
4. **What actually moves these units forward.** All of it is under variant 1, and each step needs its own owner go:
   - **P1:** a wording fix and a P1 claim class in the journal;
   - **G01-A1:** a design note, in the calibration framing of the weekday/weekend unit;
   - **R03-B1:** nothing soon (low product value).

## 6. Conclusion for the owner

**Variant 1 is enough for DH3-P1, G01-A1 and R03-B1. No amendment to `EVIDENCE_AND_CLAIMS_DECISION_V1` is needed.**

| Option | What it means | Recommendation |
|---|---|---|
| **O1 — no change** | variant 1 as written; a posterior or partial pooling only as a per-unit method choice in a design note (§3) | **recommended** |
| **O2 — clarification only** | add the Appendix A paragraph to §3 / §7: what a permitted informative prior is, plus a prior-sensitivity row in the result record; no model change | optional; worth it only before the first design note that borrows a prior from other units (e.g. R03-B1 with B2, or G01-A2 with the R03 calendar range cells) |
| **O3 — general posterior evaluator** | reverse §7 (Bayesian program, universe prior, regime classifier, mechanism score); build new infrastructure; face its own calibration problem | not recommended; it adds nothing for these three units |

**What would change this conclusion.** A unit whose decision genuinely depends on borrowing strength across many commensurable units would change it: for example, a large family of same-endpoint cells with little information per cell. Then O2 becomes necessary, but still not O3.

## 7. Observations found while writing (recorded; nothing repaired)

1. **G01-A1/A2: the unit MDE was computed at alpha 0.05, not at a Holm step.**
   - **What the record says.** `AUTOGEN_G01_FEASIBILITY.json` has `OWN_UNIT_SCREEN.ALPHA = 0.05` and `HOLM_M = 0`.
   - **Why.** `scripts/research/autogen_g01/support.py` sets m to the number of the card's hypotheses that passed the compiler, and none did.
   - **What it would have been.** Had A1 and A2 passed, m = 2, and the same SE gives MDE ≈ 0.535 (> 0.5); with m = 3, ≈ 0.562.
   - **What it affects.** "The discovery surface alone would carry the bar" (`AUTOGEN_G01_FEASIBILITY.md`; audit §5.1, §6.A) holds only at the unadjusted alpha.
   - **Practical effect: none.** Under the new model feasibility numbers are information fields.
   - **But the audit leans on it.** Its `YES` for G01-A1/A2 rests partly on that sentence. The case looks closer to R03-B1's stacked screen (`PARTLY`). Changing the audit's assessment is a separate change: the assessments YAML plus `python -m scripts.research.history_audit --check`.
2. **The planning stress SE is not a reliable guide in either direction.**
   - In the six executed R03 cells, realized SE was 0.41–0.55 of the stress SE for one-window-per-day cells, and 1.55 for C1.
   - A design note should label stress numbers as stress.
3. **The "significance" wording defect is wider than §6 of the decision lists.**
   - `config/beta_research_findings.yaml` says «ниже порога значимости 15%» for DH3-P1, O2, L3 and S1, whose Holm p is 0.0015–0.016. The 15 % is the materiality bar.
   - §6 of the decision and `EVIDENCE_FORMAT_SHADOW_REPORT_V1.md` flag only R03-C1.
   - This is a product follow-up and is not changed here.
4. **P1's only evidence path is not yet planned.**
   - The journal design's first classes include no research-state range class.
   - Without one, P1 accumulates no prospective record, even when its live line is matched.

## 8. Validation

- **Docs only.** No code, config, registry, atlas source, sealed record or product file changed.
- **Numbers checked.** Every number was checked against its cited file at `c2b1316`.
- **Arithmetic.** §4.2, §4.3 and §7.1–7.2 use only recorded planning numbers (`SE_STRESS`, `MDE_STRESS`, alpha) and the recorded SEs of executed cells. No outcome was read or computed.
- **`git diff --check`** is clean.

## Appendix A — optional clarification text (O2; not applied)

> **§3 addition — informative priors.** A design note may choose a Bayesian or partial-pooling method with an informative prior only if:
> 1. the prior comes from a list of named units with the same endpoint, unit of analysis, scale and design, fixed in the note before the outcome;
> 2. the result record adds a `prior sensitivity` row: the estimate under the declared prior and under a vague prior;
> 3. the posterior never replaces live calibration: L3 still needs its journal count (§5);
> 4. a posterior computed on a consumed surface changes wording only, never the evidence status.
>
> A prior pooled over the project's units at large, or across incommensurable endpoints, remains excluded (§7).
