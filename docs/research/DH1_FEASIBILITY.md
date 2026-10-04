# DH1 — outcome-blind feasibility

**Program:** `DIRECTIONAL_HYPOTHESES_DH1` · **Written before any outcome** · machine record: `DH1_FEASIBILITY.json`

Events, states and nuisance terms were built from prices and flows known at each decision time. No outcome was computed (`MARKET_OUTCOMES_OPENED = false`). Planning SE assumes outcome variance 0.25 and a design effect of 1.25 for week clustering. Rule, frozen before counting: a cell runs if its discovery MDE at 80 % power (Holm first-step alpha) is at most 0.06 and the smaller arm has at least 300 events in at least three epochs with both arms of 30 or more.

## Surfaces

| Surface | 5m bars present | spot bars present | level events | sharp-move events |
|---|---|---|---|---|
| DISCOVERY | 526176 / 526176 | 525714 | 4622 | 1852 |
| REPLICATION | 254252 / 254304 | 248407 | 1481 | 897 |

## Cells

| Cell | Surface | N | state / comparator | MDE80 | power at 3 pp | power at 4.5 pp | epochs OK | het power |
|---|---|---|---|---|---|---|---|---|
| DH1-L1 | DISCOVERY | 4616 | 3985 / 631 | 0.0851 | 0.11 | 0.25 | 5 | 0.04 |
| DH1-L1 | REPLICATION | 1471 | 1192 / 279 | 0.1298 | 0.05 | 0.10 | 3 | 0.03 |
| DH1-L2 | DISCOVERY | 4622 | 2049 / 2573 | 0.0578 | 0.24 | 0.55 | 5 | 0.10 |
| DH1-L2 | REPLICATION | 1481 | 629 / 852 | 0.1065 | 0.07 | 0.15 | 3 | 0.08 |
| DH1-L3 | DISCOVERY | 4622 | 1506 / 3116 | 0.0741 | 0.14 | 0.33 | 5 | 0.09 |
| DH1-L3 | REPLICATION | 1481 | 419 / 1062 | 0.1457 | 0.04 | 0.08 | 3 | 0.07 |
| DH1-B1 | DISCOVERY | 1852 | 1807 / 45 | 0.2648 | 0.03 | 0.05 | 0 | 0.00 |
| DH1-B1 | REPLICATION | 896 | 849 / 47 | 0.2610 | 0.03 | 0.05 | 0 | 0.00 |
| DH1-B2 | DISCOVERY | 1846 | 289 / 1557 | 0.1140 | 0.08 | 0.15 | 5 | 0.04 |
| DH1-B2 | REPLICATION | 885 | 124 / 761 | 0.1730 | 0.05 | 0.08 | 2 | 0.00 |

## Decisions

| Cell | Status | Replication powered | Het (discovery / replication) | Reasons |
|---|---|---|---|---|
| DH1-L1 | `INFORMATIONALLY_WEAK` | no (live tracking decides) | NOT_ASSESSABLE / NOT_ASSESSABLE | discovery MDE 0.0851 > 0.06 |
| DH1-L2 | `EXECUTABLE` | no (live tracking decides) | NOT_ASSESSABLE / NOT_ASSESSABLE | — |
| DH1-L3 | `INFORMATIONALLY_WEAK` | no (live tracking decides) | NOT_ASSESSABLE / NOT_ASSESSABLE | discovery MDE 0.0741 > 0.06 |
| DH1-B1 | `INFORMATIONALLY_WEAK` | no (live tracking decides) | NOT_ASSESSABLE / NOT_ASSESSABLE | discovery MDE 0.2648 > 0.06; smaller arm 45 < 300; fewer than 3 discovery epochs with both arms >= 30 |
| DH1-B2 | `INFORMATIONALLY_WEAK` | no (live tracking decides) | NOT_ASSESSABLE / NOT_ASSESSABLE | discovery MDE 0.1140 > 0.06; smaller arm 289 < 300 |
