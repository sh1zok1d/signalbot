# DH3 — outcome-blind feasibility (five cards of three)

**Program:** `DIRECTIONAL_AND_RANGE_DH3` · written before any outcome · machine record `DH3_FEASIBILITY.json`

Rule frozen before counting: a cell runs if its discovery MDE at 80 % power (Holm first-step alpha 0.05/3) is at most twice its bar (range: 2 x log 1.15; direction: 6 pp), the smaller arm has at least 300 events and at least three years have both arms of 30 or more.

| Cell | Endpoint | N | state / comparator | MDE80 | bar | power at bar | status | reasons |
|---|---|---|---|---|---|---|---|---|
| DH3-P1 | RANGE_4H | 12397 | 3581 / 8816 | 0.0300 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-P2 | RANGE_4H | 37147 | 3715 / 33432 | 0.0464 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-P3 | UP_FIRST_4H | 14218 | 7109 / 7109 | 0.0367 | 0.0300 | 0.60 | `EXECUTABLE` | — |
| DH3-L1 | RANGE_4H | 101112 | 20226 / 80886 | 0.0211 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-L2 | UP_FIRST_4H | 41076 | 20538 / 20538 | 0.0194 | 0.0300 | 1.00 | `EXECUTABLE` | — |
| DH3-L3 | RANGE_4H | 4101 | 1369 / 2732 | 0.0807 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-O1 | RANGE_4H | 65464 | 21822 / 43642 | 0.0256 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-O2 | RANGE_4H | 65464 | 6548 / 58916 | 0.0338 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-O3 | UP_FIRST_4H | 65464 | 26045 / 39419 | 0.0151 | 0.0300 | 1.00 | `EXECUTABLE` | — |
| DH3-V1 | LEVEL_HOLD_4H | 120223 | 40407 / 79816 | 0.0112 | 0.0300 | 1.00 | `EXECUTABLE` | — |
| DH3-V2 | RANGE_4H | 52004 | 16912 / 35092 | 0.0239 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-V3 | LEVEL_HOLD_4H | 13622 | 4531 / 9091 | 0.0375 | 0.0300 | 0.58 | `EXECUTABLE` | — |
| DH3-S1 | RANGE_4H | 4299 | 967 / 3332 | 0.0627 | 0.1398 | 1.00 | `EXECUTABLE` | — |
| DH3-S2 | CONT_FIRST_4H | 4299 | 967 / 3332 | 0.0671 | 0.0300 | 0.17 | `INFORMATIONALLY_WEAK` | discovery MDE 0.0671 > 2.0 x bar 0.0300 |
| DH3-S3 | RANGE_4H | 4299 | 1432 / 2867 | 0.0592 | 0.1398 | 1.00 | `EXECUTABLE` | — |
