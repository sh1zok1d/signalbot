# DH2 — outcome-blind feasibility (six coins pooled)

**Program:** `DIRECTIONAL_HYPOTHESES_DH2` · **written before any outcome** · machine record `DH2_FEASIBILITY.json`

States and nuisance terms were built from prices and flows known at each decision time; no outcome was computed. Rule as DH1: a cell runs if its discovery MDE at 80 % power (Holm first-step alpha) is at most 0.06, the smaller arm has at least 300 events and at least three years have both arms of 30 or more.

## Events by coin

| Surface / card | BTC | ETH | BNB | XRP | DOGE | SOL |
|---|---|---|---|---|---|---|
| DISCOVERY DH2-L | 2859 | 2875 | 2838 | 2797 | 2506 | 2498 |
| DISCOVERY DH2-B | 1852 | 1812 | 1515 | 1644 | 1594 | 1238 |
| REPLICATION DH2-L1 | 1317 | 0 | 0 | 0 | 0 | 0 |
| REPLICATION DH2-L3 | 1265 | 1297 | 1126 | 845 | 0 | 0 |
| REPLICATION DH2-B2 | 897 | 0 | 0 | 0 | 0 | 0 |

## Cells

| Cell | Surface | N | state / comparator | MDE80 | power at 3 pp | BTC-only MDE | epoch het power | coin het power |
|---|---|---|---|---|---|---|---|---|
| DH2-L1 | DISCOVERY | 16362 | 13645 / 2717 | 0.0386 | 0.56 | 0.1059 | 0.15 | 0.14 |
| DH2-L1 | REPLICATION | 1309 | 1065 / 244 | 0.1323 | 0.06 | — | 0.03 | 0.00 |
| DH2-L3 | DISCOVERY | 16373 | 4777 / 11596 | 0.0416 | 0.49 | 0.0971 | 0.13 | 0.11 |
| DH2-L3 | REPLICATION | 4524 | 1309 / 3215 | 0.0797 | 0.14 | 0.1529 | 0.11 | 0.08 |
| DH2-B2 | DISCOVERY | 9630 | 3143 / 6487 | 0.0357 | 0.65 | 0.1036 | 0.14 | 0.18 |
| DH2-B2 | REPLICATION | 885 | 124 / 761 | 0.1572 | 0.08 | — | 0.00 | 0.00 |

## Decisions

| Cell | Status | Replication powered | Reasons |
|---|---|---|---|
| DH2-L1 | `EXECUTABLE` | no (live tracking decides) | — |
| DH2-L3 | `EXECUTABLE` | no (live tracking decides) | — |
| DH2-B2 | `EXECUTABLE` | no (live tracking decides) | — |
