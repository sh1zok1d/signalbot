# AUTOGEN_G01 — outcome-blind feasibility

**Status:** `FEASIBILITY_COMPLETE / OUTCOMES_NOT_OPENED / NO_SURVIVOR`
**Date:** 2026-10-03
**Compiler:** `GV0R02_SCHEMA_V2 / GV0R02_POLICY_V2` via `to_compiler_proposal_v1` and the R03 extended registry (both imported unchanged), plus the program's unit-level screens (paired months at the card's Holm first-step alpha; two-era weeks for card B)
**Machine records:** `AUTOGEN_G01_FEASIBILITY.json`, `AUTOGEN_G01_PLANNING.json`

| ID | Units (discovery) | State / comparator windows | n_eff (compiler) | MDE stress (compiler) | MDE stress (units) | Replication units | Replication MDE (units) | Blockers | Status |
|---|---|---|---|---|---|---|---|---|---|
| G01-A1 `TOM_PARTICIPATION` | 59 months | 203 / 826 | 163.0 | 0.439 | 0.4862 | 36 of 36 months (BitMEX) | 0.632 | REPLICATION_MDE_TOO_LARGE | `INFORMATIONALLY_WEAK` |
| G01-A2 `TOM_RANGE` | 59 months | 203 / 826 | 163.0 | 0.439 | 0.4862 | 36 of 36 months (BitMEX) | 0.632 | REPLICATION_MDE_TOO_LARGE | `INFORMATIONALLY_WEAK` |
| G01-A3 `MONTH_END_MARK_HOUR` | 55 months | 55 / 770 | 51.3 | 0.782 | 0.7820 | 33 of 33 months (BitMEX) | 1.010 | MDE_TOO_LARGE, REPLICATION_MDE_TOO_LARGE | `INFORMATIONALLY_WEAK` |
| G01-B1 `ETF_FIXING_HOUR_PARTICIPATION` | 261 (210 pre / 51 post weeks) | 240 / 1004 | 193.7 | 0.403 | 0.5005 | prospective from 2027-01-01 (min 52 weeks) | compiler only | REPLICATION_MDE_TOO_LARGE | `INFORMATIONALLY_WEAK` |

Effect bar 0.5 comparator-SD for every hypothesis (not lowered). A hypothesis is executable only if the compiler returns `FEASIBLE_FOR_PREREGISTRATION` and the unit-level MDE is at or below the bar. **No hypothesis is executable; nothing is frozen or executed.**

## Reading

- **G01-A1 / A2 (turn of month).** The discovery surface alone would carry the bar (unit MDE 0.486 at the Holm first-step alpha). The declared time-disjoint replication surface, 36 BitMEX months, cannot (MDE about 0.63), and the compiler requires it to. A monthly calendar clock has too few independent units per era.
- **G01-A3 (month-end mark hour).** One state hour per month: discovery MDE 0.78, as expected (the R03-A2/A3 precedent).
- **G01-B1 (ETF fixing window).** One post-launch year: the unit-level MDE is 0.5005, above the bar by 5e-4. The prospective replication declared at 52 weeks is also underpowered. A natural experiment with a single launch has no historical replication surface.

## Definitional correction before freeze

First compile (same day, before freeze): G01-B1 returned `DEFINITION_INCOMPLETE / STOPPING_RULE_INVALID` because the prospective rule declared `MIN_N = 252` above `MAX_EPISODES = 104`. The 252 double-counted the frozen pre-launch arm (52 prospective + 200 pre weeks) against the stated intent of at least 52 prospective weeks. It was corrected to `MIN_N = 52` before any freeze. This is a definitional fix; it changes neither the bar, nor the discovery screen, nor the unit-level screen, and every other number below is from the recompile.

## What is not done

- No price, volume or trade count was read. Only calendars and BitMEX 5m bar open times (for replication availability) were used.
- No closed hypothesis is repaired: the replication surface, minimum N, pre-period, block length and bar stay as declared. A later variant is a new search object with its own test family.
- No 2025/2026 object, no B2-06, no product change, no API spend.
