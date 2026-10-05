# Evidence and claims — decision V1 (research after the compiler line)

**Status:** `OWNER_DECISION_RECORDED (2026-10-05) / APPLIES TO NEW UNITS / NOT RETROACTIVE`
**Replaces as the successor plan:** `HYPOTHESIS_EVALUATION_CONTRACT_V2_DRAFT.md`, which is not adopted and is kept as history.
**Closes:** the compiler V3 variance line (`COMPILER_V3_VARIANCE_LINE_CLOSURE_V1.md`).
**Unchanged authorities:** the protected-data rules, E1-RUN-001, the V3 Microscope closure, `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` (no direct trade calls; N and "обычно" beside every historical number), and every sealed verdict.

## 0. The decision in one paragraph

Research answers market and product questions again. It does not certify its own designs in advance.
- **Each unit fixes four things before outcomes:** what it estimates, how, against what, and what would change our mind.
- **It then reports** an estimate, its uncertainty and how much information stands behind it.
- **What may be said follows from a separate decision:** a ladder of allowed claims, L0–L4.

The stricter the claim, the more evidence it needs. A result that cannot carry the strongest claim does not vanish; it carries the claim its evidence supports.

## 1. Keep / drop

| Keep | Drop |
|---|---|
| Design before outcome: a short design note, committed before the outcome is read | Multi-stage pre-certification of a design as a gate (feasibility compiler PASS, variance floors, estimator calibration, bar-function compilation) |
| No rescue: no new threshold, horizon, side, baseline or claim type after the outcome inside the same unit | One universal effect bar (0.5 SD) deciding what was "found" |
| Exposure and search ledger: every surface read and every variant tried is recorded; the number of variants is reported | Binary verdict words as the result (`CONFIRMED` / `FAILED` / `NO_INCREMENTAL_STRUCTURE`) |
| Sealed holdouts and protected data: E1, sealed 2026 research surfaces, recorded exposures | Tranche, bar-function and closed-registry machinery of the V2 draft (§4, §5, §7, §8.3a) |
| Full preregistration (twin, permit, one-shot) where it is really needed: L3 / L4 claims, any sealed or reserved surface, any prospective confirmation | A mandatory estimator or inference method for every unit |

The GV0R02 feasibility compiler V0–V2 stay available as a calculator. Their MDE and unit counts are reported as amount-of-information fields and never block a unit.

## 2. Three layers, kept apart

1. **Evidence.** What the data show: estimate, uncertainty, amount of information, stability, falsification check. No verdict words.
2. **Interpretation.** What it plausibly means: the mechanism, regime or era compatibility, the limitations and the alternative explanations. It is written as text and is not a score.
3. **Claim decision.** Which ladder level (§4) the evidence permits, with the exact wording template. It is decided per claim, not per unit.

**Tracks**, declared in the design note, say which decision a unit is meant to inform:
- `STRUCTURE` — is something there, and how big;
- `PRODUCT_EVIDENCE` — may the product use it for a baseline, calibration or context sentence;
- `EDGE` — is it actionable.

A unit may declare several tracks. A track added after the outcome is a new unit.

## 3. Before outcomes, and the result record

**Design note** (one page, committed before the outcome is read):
- the question / estimand;
- the primary method, chosen by design: frequentist, exact / randomization, Bayesian or partial pooling, or something else. There is no universal estimator;
- the comparison or baseline;
- what would change our mind;
- the family of variants actually tried or planned, with their count;
- the data surface and its exposure status.

**Result record.** Every unit reports these fields. A field that does not apply says why.

| Field | Content |
|---|---|
| estimate | effect or frequency in the unit of the question (pp, SD, ratio) |
| uncertainty | the interval or posterior interval of the declared method, with its level |
| information | N, effective N or clusters, events per era; the planning MDE if computed |
| stability | sign and size by era or year where meaningful |
| falsification | placebo, shuffled time, negative control or comparator where meaningful |
| limitations | venue, era, exposure, nuisance, missingness |
| search exposure | number of variants / cells in the family, and how multiplicity was handled |
| method before outcome | pointer to the committed design note (commit) |
| evidence summary | one sentence, no verdict word |
| claim decision | the ladder level per claim (§4), with template id |

## 4. Ladder of allowed claims

The ladder ranks **what may be said**. It does not rank how true a hypothesis is.

| Level | What it says | Needs | Example wording | Never at this level |
|---|---|---|---|---|
| **L0** observation | the current observed state | correct data and code | «рост при стабильном OI» | any statement about the future |
| **L1** historical context | in past data X differed from a baseline (no future outcome) | §3 record; interval excludes the trivial; stability shown | «Выходные часы в 2020–2024 были спокойнее того же часа в будни, примерно на 0,4 SD; разрыв рос каждый год» | a direction or chance of a future move |
| **L2** directional historical evidence | how often an outcome followed similar states, against a baseline | §3 record; a fixed, pre-declared set of states and horizons; a comparable baseline (same horizon, same volatility conditioning); the quantitative format below | «В истории похожих состояний: через 4ч ниже в 61 % против 49 % обычно (+12 п.п., N = 86; 95 % интервал +2..+22 п.п.)» | «вероятность падения сейчас 61 %», «скорее всего упадёт», a bare verbal tendency |
| **L3** current calibrated probability | a probability for now | live / prospective calibration of this exact claim class (§5) on enough logged cases; tracked accuracy shown | «Шанс дойти до 64 000 за 4ч: 34 % (такие оценки сбывались в 33 % из 410 случаев)» | a probability without its live record |
| **L4** actionable edge | the effect is worth acting on | after-cost effect, time-disjoint or prospective replication, stability, execution assumptions, full preregistration | none today | direct trade calls (forbidden at every level) |

**The L2 quantitative format.** Every directional historical line shows:
- the observed frequency or effect;
- the baseline;
- the difference;
- N;
- uncertainty or stability, when available.

A bare verbal tendency is never the whole line: «чаще выше обычного», «чаще снижался». The set of states and horizons shown is fixed in advance and shown whether or not it differs, so the surface does not select winners.

**Historical frequency is not a current probability.** L2 speaks in the past tense about a cohort: «в истории похожих … было». Turning it into a present-tense chance is an L3 claim, and L3 needs its own live calibration.

**No verbal confidence scale.** Words like weak / moderate / strong are not shown to users as a truth scale until the claim journal (§5) has calibrated them. Numbers carry the uncertainty.

The existing research status words describe which process a result has passed, not how strong it is:
- «Проверено» — a replicated result;
- «Гипотеза … не подтверждено» — found once, not replicated;
- «ниже нашего порога значимости» — below the bar.

They stay for now as provenance labels. §7 lists the wording fixes.

## 5. Claim-specific requirements and prospective logging

| Claim | Minimum information | Preregistration | Live logging |
|---|---|---|---|
| L0 | data freshness and completeness checks | no | snapshot (already recorded) |
| L1 | stated per design note; interval width shown | design note | yes, as eligible statements |
| L2 | stated per state family; below it the line says «мало данных (N)» | design note; fixed state set | yes: every eligible state, shown or not |
| L3 | a live calibration count fixed in the design note | full | yes, mandatory; the claim is shown as L3 only after its count is reached |
| L4 | after-cost, replication | full, one-shot | yes |

**Prospective claim journal.** From the first L1 / L2 / L3 line onward, every state in which such a claim was **eligible** is recorded at the moment it arises, not just the ones shown. Each record carries:
- its level, exact numbers and baseline;
- the rule, model and template versions;
- the **evaluation rule fixed at write time**.

Claims of one class are scored together by the same rule against their baseline, not one by one. The design is `docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md`. It reuses the existing context snapshots, episode outcomes, views and forecast tables.

**Rare events.** A unit with few events keeps and shows its estimate and direction, and states that its information is insufficient. It names the next event dates and accumulates prospectively under its design note. There is no fixed status vocabulary for this beyond the result record.

## 6. Mapping to today's product (2026-10-05)

| Surface | Level | Gap (follow-up, not done here) |
|---|---|---|
| 1h / 4h labels, live state | L0 | none |
| Research lines (`config/beta_research_findings.yaml`), "обычно" comparisons | L1 | R03-C1 text says «ниже порога значимости»; its record says significant (Holm p = 0.0001) and below the **materiality** bar |
| «после похожих (N): через 4ч выше в X (обычно Y) — чаще выше обычного» | L2 | add the difference in п.п. and the uncertainty; replace the verdict word with numbers |
| Level reactions beside a random level | L2 | same |
| Corridor «в 4 из 5 похожих случаев» | L2 wording over a forecast already tracked in `beta_forecasts` | none for the wording |
| Touch chances «дойти: за 4ч 34 %», `/risk` | L3 wording | live calibration not yet logged per claim; until it is, either show the tracked accuracy beside the number or phrase it as a historical frequency. Owner choice; not changed here |
| «Проверено» / «Гипотеза» lines | L1 / L2 by content | status words are provenance, not confidence; keep |

## 7. Not changed by this decision

- **Code and verdicts:** no product code, wording, schema or config; no research verdict, ledger row, atlas unit or findings entry. The wording gaps of §6 are a separate product task.
- **Frozen experiments:** E1-RUN-001, V3, D2, D7 and the sealed records are untouched.
- **Contract V1** stays the contract of every unit registered under it; its records keep their force.
- **What this is not:** a new framework, a Bayesian program, a universe prior, a regime classifier or a mechanism score.
- **Infrastructure stop rule:** if applying this decision to a unit appears to need new research infrastructure, the unit stops and the owner is asked.
