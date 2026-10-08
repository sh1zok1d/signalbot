# LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. The question is whether the 15-minute path adds a late-BREAK difference after the endpoint location is held fixed. This note does not change the product.

## Provenance

Design SHA `bae1060c390e049f652c57792b8c18fc1c41058e`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
Exposure `DISCOVERY_ONLY`. Outcomes read: True.

Dependencies, not rewritten:

- touch: `dfc9e0f04358de15606382472badeb5aee787039`
- memory: `c3d39bffda861b535605a98205d7578c0c84c782`
- method: `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`
- approach: `aa85e5b43c405ee225336ff385e3a3383fa59d09`
- structure: `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`
- confirmation: `c1cd4e0102e700f7860d21a9af0d243c3bc367be`
- positioning_flow: `e6e5f307cfa098db607544a556bae01a2310eb6a`
- joint_state: `bcc0a9e8a5c2af221b23b72768d7b7ba1d6a4aa2`
- liquidity: `181debc4aa626637f2cd560103447d2d4adc96b1`
- post_touch_reaction: `44726ded55c75fefecc6848ab8b76971ead83721`

## Data

CORE `CORE_BTC_BINANCE_V0` zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`.
Price OHLC only.
Event window 2020-02-01T00:00:00+00:00 inclusive to 2025-01-01T00:00:00+00:00 exclusive.
T is the open of the touch bar. D = T+15m. Path bits use closes of j, j+1 and j+2. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.

Seed 20261018, bootstrap draws 2000, FDR q=0.1, practical scale 0.03.
Eligible contrasts: REENTRY_MEMORY.
Search exposure: `{'states': 4, 'sequences_descriptive': 8, 'primary_contrasts_frozen': 2, 'primary_contrasts_estimated': 1, 'outcomes_primary': 1, 'outcomes_secondary_descriptive': 1, 'pseudo_contrasts': 1, 'specificity_contrasts': 1, 'stability_slices': 10, 'loyo_cells': 5, 'lofo_cells': 0, 'taxonomy_variants': 0, 'horizon_extensions': 0}`.

## Early census

Geometry-legitimate rows in the census base 1919. Early BREAK 296, early REJECT 278, early ambiguous 13, unresolved 1332, unavailable 0.

## Path counts on unresolved events

Sequences: `{'000': 983, '001': 69, '010': 39, '011': 81, '100': 52, '101': 11, '110': 24, '111': 73, 'UNAVAILABLE': 0}`.
States: `{'LATE_OR_RECROSS_OUTSIDE': 80, 'NEVER_OUTSIDE': 983, 'PERSISTENT_OUTSIDE': 154, 'REENTERED': 115, 'UNAVAILABLE': 0}`.
Pseudo unresolved sequences: `{'000': 700, '001': 81, '010': 30, '011': 51, '100': 27, '101': 12, '110': 5, '111': 36, 'UNAVAILABLE': 0}`.
Pseudo unresolved states: `{'LATE_OR_RECROSS_OUTSIDE': 93, 'NEVER_OUTSIDE': 700, 'PERSISTENT_OUTSIDE': 87, 'REENTERED': 62, 'UNAVAILABLE': 0}`.

## Endpoint overlap

PERSISTENCE_MEMORY: treated `PERSISTENT_OUTSIDE` N=154 mean=0.3493 sd=0.2276; reference `LATE_OR_RECROSS_OUTSIDE` N=80 mean=0.2254 sd=0.1872.
Standardized difference 0.5945. Overlap [0.0616, 0.5378] width 0.4762. Shares 0.8052 and 0.9250. Overlap pass True. Arm pass False. Reasons ['ARM_N_BELOW_MINIMUM'].
Eligible False. Rough 80% MDE +21.58 pp. Block reasons ['ARM_N_BELOW_MINIMUM'].
REENTRY_MEMORY: treated `REENTERED` N=115 mean=-0.3218 sd=0.2695; reference `NEVER_OUTSIDE` N=983 mean=-0.8188 sd=0.4823.
Standardized difference 1.2721. Overlap [-0.7082, -0.2524] width 0.4558. Shares 0.6261 and 0.5381. Overlap pass True. Arm pass True. Reasons [].
Eligible True. Rough 80% MDE +15.43 pp. Block reasons [].

## Primary contrasts

REENTRY_MEMORY: +6.74 pp (95% -4.22 pp .. +17.62 pp), p=0.2218, q=0.2218, N=952, treated=101, reference=851, clusters=253, bootstrap_valid=2000

## Decisions

REENTRY_MEMORY: class `NONE`, conjunction False, failed ['fdr', 'interval', 'epochs', 'loyo', 'family', 'side'], statistical hit False, delta -20.21 pp (95% -45.18 pp .. +6.12 pp), pseudo slope +9.52 pp (95% -9.68 pp .. +28.77 pp).

## Year, family, side, leave-one-year-out

### epoch

REENTRY_MEMORY 2020: -26.28 pp, N=164, treated=15, reference=149
REENTRY_MEMORY 2021: +8.81 pp, N=162, treated=24, reference=138
REENTRY_MEMORY 2022: +25.23 pp, N=214, treated=31, reference=183
REENTRY_MEMORY 2023: +5.28 pp, N=192, treated=13, reference=179
REENTRY_MEMORY 2024: -6.94 pp, N=220, treated=18, reference=202

### family

REENTRY_MEMORY DAY: +8.99 pp, N=842, treated=82, reference=760
REENTRY_MEMORY WEEK: -12.72 pp, N=100, treated=18, reference=82
REENTRY_MEMORY MONTH: n/a, N=10, treated=1, reference=9

### side

REENTRY_MEMORY resistance: -3.46 pp, N=524, treated=54, reference=470
REENTRY_MEMORY support: +18.59 pp, N=428, treated=47, reference=381

### leave-one-year-out

REENTRY_MEMORY omit_2020: +11.81 pp, N=788, treated=86, reference=702
REENTRY_MEMORY omit_2021: +5.21 pp, N=790, treated=77, reference=713
REENTRY_MEMORY omit_2022: -0.86 pp, N=738, treated=70, reference=668
REENTRY_MEMORY omit_2023: +6.42 pp, N=760, treated=88, reference=672
REENTRY_MEMORY omit_2024: +9.18 pp, N=732, treated=83, reference=649

## Descriptive sequences

000: N=983, BREAK 27.6%, REJECT 59.0%, NEITHER 13.3%, ambiguous 1
001: N=69, BREAK 65.2%, REJECT 18.8%, NEITHER 15.9%, ambiguous 0
010: N=39, BREAK 59.0%, REJECT 30.8%, NEITHER 10.3%, ambiguous 0
011: N=81, BREAK 69.1%, REJECT 18.5%, NEITHER 12.3%, ambiguous 0
100: N=52, BREAK 38.5%, REJECT 50.0%, NEITHER 11.5%, ambiguous 0
101: N=11, BREAK 36.4%, REJECT 36.4%, NEITHER 27.3%, ambiguous 0
110: N=24, BREAK 29.2%, REJECT 54.2%, NEITHER 16.7%, ambiguous 0
111: N=73, BREAK 57.5%, REJECT 23.3%, NEITHER 19.2%, ambiguous 0

## Descriptive states, including resolve rate

NEVER_OUTSIDE: N=983, BREAK 27.6%, REJECT 59.0%, NEITHER 13.3%, resolve among labeled 86.7%
REENTERED: N=115, BREAK 43.5%, REJECT 44.3%, NEITHER 12.2%, resolve among labeled 87.8%
LATE_OR_RECROSS_OUTSIDE: N=80, BREAK 61.3%, REJECT 21.2%, NEITHER 17.5%, resolve among labeled 82.5%
PERSISTENT_OUTSIDE: N=154, BREAK 63.6%, REJECT 20.8%, NEITHER 15.6%, resolve among labeled 84.4%

## Routing

`NO_INCREMENTAL_PATH_MEMORY_BEYOND_ENDPOINT`. Successor candidate `NONE`.
Claim ceiling L2, discovery only. The coefficient is a historical adjusted difference in this unresolved first-touch cohort. It is not a current probability.
No product change.

## Reporting note

`PERSISTENCE_MEMORY` was not estimated. `LATE_OR_RECROSS_OUTSIDE` has 80 unresolved events, below the frozen arm minimum of 100. The endpoint overlap for that contrast would have passed. The state-table frequencies for those two states are counts. They are not an adjusted coefficient.

The `REENTRY_MEMORY` point is +6.74 pp, which is above 3 pp. The 95 percent interval includes 0 and q is 0.2218, so the frozen conjunction fails. The interval was not narrowed and the arm minimum was not lowered.

DAY is +8.99 pp and WEEK is −12.72 pp. Both strata are estimable and the signs are opposite, so the family clause fails because the estimates disagree. It is not a rank failure from omitting DAY.

Specificity was not applied. The pseudo slope interval includes 0. A pseudo result does not rescue the real null. No taxonomy variant was fit.
