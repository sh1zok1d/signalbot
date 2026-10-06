# RESEARCH_HISTORY_AUDIT_V1 — erratum 1: G01-A1 / G01-A2 unit MDE was not at a Holm step

**Status:** `APPEND-ONLY ERRATUM (2026-10-05) / AUDIT FILES UNCHANGED / NO VERDICT CHANGED`
**Concerns:** `RESEARCH_HISTORY_AUDIT_V1.md`, merged in #330 (`c2b1316`).
- **Not edited:** the audit and its twins (`RESEARCH_HISTORY_AUDIT_V1.json`, `_TABLE.md`, `audit/RESEARCH_HISTORY_AUDIT_V1_ASSESSMENTS.yaml`) stay byte for byte as merged.
- **This record sits beside them.** Where it differs from them for G01-A1 and G01-A2, read this record.

**Found by:** `EVALUATOR_VARIANTS_COMPARISON_V1.md` §7.1.
**Method:** no outcome computed and no market data read. Only recorded planning numbers and the feasibility code were used.

## 1. What the audit says

The audit rests its `YES` (killed by conservatism) for G01-A1 and G01-A2 on one sentence: the discovery surface alone would have carried the 0.5 SD bar, and only the replication rule closed the cards. The sentence appears in four places:
- **Assessments YAML, G01-A1:** "The discovery surface alone carried the bar (unit MDE 0.486 < 0.5). The card was closed only because the declared replication surface (36 BitMEX months, MDE about 0.63) could not."
- **§5.1 `YES` table:** "no outcome; discovery unit MDE 0.486 < 0.5 bar | replication surface (36 BitMEX months) required to carry the same bar".
- **§6.A:** "closed by the rule that a 36-month replication surface must carry the same 0.5 SD bar, not by the discovery information (unit MDE 0.486)".
- **Source of the wording:** the sentence comes from `AUTOGEN_G01_FEASIBILITY.md` ("unit MDE 0.486 at the Holm first-step alpha").

## 2. What the record shows

| Item | Value | Source |
|---|---|---|
| `OWN_UNIT_SCREEN.ALPHA` (A1 and A2) | **0.05** | `AUTOGEN_G01_FEASIBILITY.json` `DETAIL/G01-A1`, `DETAIL/G01-A2` |
| `OWN_UNIT_SCREEN.HOLM_M` | **0** | same |
| `SE_STRESS`, `MDE_STRESS` | 0.1736, 0.4862 | same |
| How m is set | the number of the card's hypotheses that passed the compiler; the screen uses alpha = 0.05 / max(1, m) | `scripts/research/autogen_g01/support.py` (`holm_m = sum(... FEASIBILITY_STATUS == "FEASIBLE_FOR_PREREGISTRATION")`), `scripts/research/owner_cards_r03/support.py::unit_screen` |

**So 0.486 is the MDE at the unadjusted alpha.** Neither A1 nor A2 passed the compiler (`REPLICATION_MDE_TOO_LARGE`), so m was 0 and the formula used alpha 0.05.

**The counterfactual the sentence implies** is that the replication rule is removed and A1 and A2 both pass the compiler. The card's own rule then makes m = 2. A3 failed the discovery MDE in any case. With the same recorded SE and the same formula (80 % power):

| m | alpha | Unit MDE (stress) | Against the 0.5 bar |
|---|---|---|---|
| 1 | 0.05 | 0.486 | below |
| **2** | **0.025** | **≈ 0.535** | **above** |
| 3 | 0.0167 | ≈ 0.562 | above |

**Under the card's own multiplicity rule, the discovery surface alone would also have failed the unit-level screen.** It is a near miss of the same kind as R03-B1 (0.544 at m = 4, which the audit records as `PARTLY`).

Both numbers are stress-profile planning numbers. In the executed R03 cells with one window per day, realized SEs were 0.41–0.55 of the stress SE (`EVALUATOR_VARIANTS_COMPARISON_V1.md` §4.2). That conservatism applies to G01-A1/A2 and R03-B1 alike, so it does not separate them.

## 3. Corrected reading

**G01-A1 and G01-A2: conservatism `PARTLY`, not `YES`.**
- **Why `PARTLY`.** A stacked rule closed them: the compiler's replication requirement, and the unit-level screen at the card's Holm step. The information on the discovery surface was also just short of the bar, which is the audit's `PARTLY` definition. The `YES` definition needs "the information was there", and at the card's own alpha it was not.
- **Unchanged for both:** category `BLOCKED_FEASIBILITY_MDE`, maximum claim L0, needs `OWNER_DECISION`. No outcome was computed, and nothing is known about the effect.

**Counts that change:**

| Audit place | As merged | Corrected |
|---|---|---|
| Conservatism totals (§3, JSON `counts.cons`) | YES 7, PARTLY 11, NO 118, NA 52 | **YES 5**, **PARTLY 13**, NO 118, NA 52 |
| §4 answer 4: firm / upper bound | 7 (3.7 %) / 18 (9.6 %) | **5 (2.7 %)** / 18 (9.6 %), unchanged |
| §4 answer 4: among units with an outcome | 5 `YES`, 3 `PARTLY` | unchanged (G01-A1/A2 have no outcome) |
| §4 answer 3: stacked-rule closures | 7, of which G01-A1/A2 `YES` | 7, **all `PARTLY`** |
| JSON `cons_by_cat.BLOCKED_FEASIBILITY_MDE` | NO 16, YES 2, PARTLY 5 | NO 16, **YES 0, PARTLY 7** |
| §5.1 lists | G01-A1/A2 in the `YES (7)` table | G01-A1/A2 belong in the `PARTLY` table; the `YES` list is R03-C1, D3, DH3-P1, DH3-O2, DH3-L3 |
| §7.1 | "5 of the 7 `YES` cases" were magnitude bars | all 5 `YES` cases were magnitude bars |
| `CURRENT_RESEARCH_STATE.md` audit section | `KILLED_BY_OLD_CONSERVATISM = YES 7 … PARTLY 11` | read as YES 5 / PARTLY 13 (this erratum) |

**What does not change:**
- **The audit's main conclusion is strengthened, not weakened.** It reads "most deaths were real; the conservatism that mattered was the fixed magnitude bar used as a verdict switch and stacked feasibility screens". Every remaining `YES` is a magnitude-bar case.
- **§7.2 (stacked feasibility screens) still lists G01-A1/A2 correctly.**
- **The candidate order stands.** G01-A1/A2 stay first in §6.A, because their value is the product baseline question (a calibration fact for the activity flags, like weekday/weekend), not the conservatism label. The owner chose that unit as the next step on 2026-10-05; its design note is `docs/TURN_OF_MONTH_BASELINE_UNIT_V1.md`.
- **Nothing else changes.** No other unit row, verdict, G01 record or sealed record is affected.

## 4. Why the audit files are not edited

- **The audit is a merged record.** Its builder (`python -m scripts.research.history_audit --check`) and tests bind the YAML, JSON and table to each other.
- **The owner asked for a separate erratum.** If the corrected values are ever folded into a V2 audit, that is a new record built by the builder, and this erratum is its source.

## 5. Validation

- Recorded values were read from `AUTOGEN_G01_FEASIBILITY.json`. The MDE at m = 2 / 3 uses `unit_screen`'s formula, `(z(1 − alpha/2) + z(0.8)) × SE_STRESS`, on the recorded SE.
- `python -m scripts.research.history_audit --check` still passes on the unchanged audit files.
- `git diff --check` is clean.
