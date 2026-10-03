# Owner cards R03 — outcome-blind feasibility

**Status:** `FEASIBILITY_COMPLETE / OUTCOMES_NOT_OPENED`
**Date:** 2026-10-03
**Compiler:** `GV0R02_SCHEMA_V2 / GV0R02_POLICY_V2` via `to_compiler_proposal_v1`; paired-unit screen at the card's Holm first-step alpha
**Machine record:** `OWNER_CARDS_R03_FEASIBILITY.json`; planning objects in `OWNER_CARDS_R03_PLANNING.json`

| ID | Units | Active / comparator windows | n_eff (compiler) | MDE stress (compiler) | MDE stress (units, alpha/m) | Replication units | Status |
|---|---|---|---|---|---|---|---|
| R03-A1 `WEEKLY_EXPIRY_HOUR` | 260 | 260 / 1040 | 208.0 | 0.389 | 0.428 | 156 | `FEASIBLE_FOR_PREREGISTRATION` |
| R03-A2 `LARGE_EXPIRY_INCREMENT` | 60 | 60 / 201 | 46.2 | 0.824 | 0.909 | 36 | `INFORMATIONALLY_WEAK` |
| R03-A3 `CME_EXPIRY_HOUR` | 60 | 60 / 201 | 46.2 | 0.824 | 0.909 | 24 | `INFORMATIONALLY_WEAK` |
| R03-A4 `PRE_EXPIRY_PINNING` | 260 | 260 / 1040 | 208.0 | 0.389 | 0.428 | 156 | `FEASIBLE_FOR_PREREGISTRATION` |
| R03-B1 `RETURN_DISPERSION_HIGH` | 49 | 353 / 1142 | 269.6 | 0.341 | 0.544 | 0 | `INFORMATIONALLY_WEAK_AT_UNIT_LEVEL` |
| R03-B2 `BREADTH_SYNCHRONY` | 53 | 357 / 1257 | 278.0 | 0.336 | 0.459 | 0 | `FEASIBLE_FOR_PREREGISTRATION` |
| R03-B3 `VOLUME_SHOCK_FRACTION` | 48 | 332 / 1129 | 256.6 | 0.350 | 0.588 | 0 | `INFORMATIONALLY_WEAK_AT_UNIT_LEVEL` |
| R03-B4 `BTC_SHARE_LOW` | 41 | 422 / 826 | 279.3 | 0.335 | 0.602 | 0 | `INFORMATIONALLY_WEAK_AT_UNIT_LEVEL` |
| R03-C1 `WEEKEND_HOURS` | 260 | 12480 / 18720 | 7488.0 | 0.065 | 0.075 | 156 | `FEASIBLE_FOR_PREREGISTRATION` |
| R03-C2 `MONDAY_US_OPEN` | 232 | 232 / 696 | 174.0 | 0.425 | 0.491 | 156 | `FEASIBLE_FOR_PREREGISTRATION` |
| R03-C3 `NYSE_CLOSURE_US_OPEN` | 46 | 46 / 184 | 36.8 | 0.924 | 1.067 | 0 | `INFORMATIONALLY_WEAK` |
| R03-C4 `FRIDAY_US_CLOSE` | 246 | 246 / 738 | 184.5 | 0.413 | 0.476 | 156 | `FEASIBLE_FOR_PREREGISTRATION` |

Effect bar 0.5 SD for every hypothesis. Executed set: R03-A1, R03-A4, R03-B2, R03-C1, R03-C2, R03-C4.
Closed at feasibility (never executed, no rescue): R03-A2 (`INFORMATIONALLY_WEAK`), R03-A3 (`INFORMATIONALLY_WEAK`), R03-B1 (`INFORMATIONALLY_WEAK_AT_UNIT_LEVEL`), R03-B3 (`INFORMATIONALLY_WEAK_AT_UNIT_LEVEL`), R03-B4 (`INFORMATIONALLY_WEAK_AT_UNIT_LEVEL`), R03-C3 (`INFORMATIONALLY_WEAK`).

Holm counts per card: R03-A = 2, R03-B = 1, R03-C = 3.

No BTC target was read. No 2025/2026 object was selected. Panel states for card B use panel closes and quote volumes up to the decision boundary only.
- R03-B1 panel state diagnostic: {"DEFINED_DAYS": 1647, "MONTHS_WITH_BOTH": 49, "STATE_DAYS": 353}
- R03-B2 panel state diagnostic: {"DEFINED_DAYS": 1647, "MONTHS_WITH_BOTH": 53, "STATE_DAYS": 357}
- R03-B3 panel state diagnostic: {"DEFINED_DAYS": 1647, "MONTHS_WITH_BOTH": 48, "STATE_DAYS": 332}
- R03-B4 panel state diagnostic: {"DEFINED_DAYS": 1647, "MONTHS_WITH_BOTH": 41, "STATE_DAYS": 482}
