# LEVEL_LIQUIDITY_STATE_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. The observable is a local book state around the touch, not resting orders at the structural price. This note does not change the product.

## Provenance

Design SHA `f7430ca27c664e3669d7adb633561ba381a598e3`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
State term `LOCAL_BOOK_STATE_AROUND_LEVEL_TOUCH`. Exposure `DISCOVERY_ONLY`.

Dependencies, not rewritten:

- touch: `dfc9e0f04358de15606382472badeb5aee787039`
- memory: `c3d39bffda861b535605a98205d7578c0c84c782`
- method: `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`
- approach: `aa85e5b43c405ee225336ff385e3a3383fa59d09`
- structure: `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`
- confirmation: `c1cd4e0102e700f7860d21a9af0d243c3bc367be`
- positioning_flow: `e6e5f307cfa098db607544a556bae01a2310eb6a`
- joint_state: `bcc0a9e8a5c2af221b23b72768d7b7ba1d6a4aa2`

## Data

CORE `CORE_BTC_BINANCE_V0` zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`.
Book `DH3_BINANCE_UM_BOOKDEPTH_V0` object-list SHA256 `c53fc179d922f83b572703d52e80f847fb54531961ac776929f2e3e95feeddce`. BTC days verified 728, missing ['2023-02-08', '2023-02-09', '2024-04-18']. Snapshots 2068585. Bands [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5].
Event window 2023-01-01T02:00:00+00:00 inclusive to 2025-01-01T00:00:00+00:00 exclusive.

## Cohort

Retained features: TOTAL_LOCAL_DEPTH, ORIENTED_DEPTH_IMBALANCE, AHEAD_DEPTH_CHANGE_60M, BEHIND_DEPTH_CHANGE_60M, TOTAL_DEPTH_CHANGE_60M.
Dropped before outcomes: [].
Search exposure: `{'raw_features': 5, 'retained_features': 5, 'windows': 2, 'outcomes': 2, 'primary_cells': 10, 'shape_cells': 10, 'pseudo_cells': 10, 'specificity_cells': 10, 'stability_cells': 90, 'loeo_cells': 40, 'lofo_cells': 30, 'interactions': 0, 'clusters': 0, 'extra_window_sensitivities': 0, 'dh3_quintiles': 0}`.
Seed 20261016, bootstrap draws 2000, FDR q=0.1, practical scale 0.03.

## Decomposition

Crude BREAK / REJECT / NEITHER frequencies on geometry-legitimate first touches. Ambiguous labels are excluded from the rates.

BREAK 290 (0.3694), REJECT 425 (0.5414), NEITHER 70 (0.0892), RESOLVE 0.9108, ambiguous 5.

## RESOLVE_4H

- TOTAL_LOCAL_DEPTH → RESOLVE_4H: -2.61 pp (95% -4.93 pp .. -0.50 pp), p=0.0215, q=0.2032, N=762, clusters=106, bootstrap_valid=2000
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H: -0.06 pp (95% -2.44 pp .. +2.25 pp), p=0.9566, q=0.9566, N=762, clusters=106, bootstrap_valid=2000
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H: -1.01 pp (95% -2.86 pp .. +0.77 pp), p=0.2666, q=0.5368, N=762, clusters=106, bootstrap_valid=2000
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H: +0.06 pp (95% -1.47 pp .. +1.63 pp), p=0.9387, q=0.9566, N=762, clusters=106, bootstrap_valid=2000
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H: -0.85 pp (95% -2.69 pp .. +1.02 pp), p=0.3589, q=0.5981, N=762, clusters=106, bootstrap_valid=2000

## BREAK_GIVEN_RESOLVED

- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED: +4.03 pp (95% -0.30 pp .. +8.05 pp), p=0.0610, q=0.2032, N=695, clusters=106, bootstrap_valid=2000
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED: +3.93 pp (95% -0.42 pp .. +7.83 pp), p=0.0575, q=0.2032, N=695, clusters=106, bootstrap_valid=2000
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: -2.05 pp (95% -5.87 pp .. +1.44 pp), p=0.2684, q=0.5368, N=695, clusters=106, bootstrap_valid=2000
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: -0.46 pp (95% -4.56 pp .. +3.60 pp), p=0.8232, q=0.9566, N=695, clusters=106, bootstrap_valid=2000
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: -1.40 pp (95% -4.90 pp .. +2.09 pp), p=0.4316, q=0.6166, N=695, clusters=106, bootstrap_valid=2000

## Specificity (beta_real - beta_pseudo)

- TOTAL_LOCAL_DEPTH → RESOLVE_4H: delta +1.15 pp (95% -2.82 pp .. +4.93 pp), beta_real -0.15 pp, beta_pseudo -1.30 pp, N=732, clusters=101
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED: delta +5.63 pp (95% -1.27 pp .. +12.35 pp), beta_real +5.53 pp, beta_pseudo -0.10 pp, N=582, clusters=100
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H: delta -3.09 pp (95% -7.09 pp .. +1.00 pp), beta_real +2.13 pp, beta_pseudo +5.22 pp, N=732, clusters=101
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED: delta -2.08 pp (95% -9.42 pp .. +4.59 pp), beta_real +3.43 pp, beta_pseudo +5.51 pp, N=582, clusters=100
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H: delta -1.42 pp (95% -5.04 pp .. +2.25 pp), beta_real +1.04 pp, beta_pseudo +2.46 pp, N=732, clusters=101
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: delta -0.60 pp (95% -6.89 pp .. +5.76 pp), beta_real -1.69 pp, beta_pseudo -1.09 pp, N=582, clusters=100
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H: delta +0.54 pp (95% -3.13 pp .. +3.78 pp), beta_real +0.65 pp, beta_pseudo +0.11 pp, N=732, clusters=101
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: delta +0.45 pp (95% -6.72 pp .. +8.16 pp), beta_real -1.16 pp, beta_pseudo -1.61 pp, N=582, clusters=100
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H: delta -0.98 pp (95% -4.50 pp .. +2.37 pp), beta_real +1.23 pp, beta_pseudo +2.21 pp, N=732, clusters=101
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: delta +0.15 pp (95% -6.24 pp .. +6.87 pp), beta_real -1.80 pp, beta_pseudo -1.94 pp, N=582, clusters=100

## Pseudo cohort

- TOTAL_LOCAL_DEPTH → RESOLVE_4H: -0.52 pp (95% -4.06 pp .. +2.75 pp), N=366, clusters=101
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED: -1.98 pp (95% -8.64 pp .. +4.84 pp), N=291, clusters=100
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H: +5.09 pp (95% +1.64 pp .. +8.65 pp), N=366, clusters=101
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED: +5.00 pp (95% -0.45 pp .. +10.22 pp), N=291, clusters=100
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H: +3.04 pp (95% -0.53 pp .. +6.56 pp), N=366, clusters=101
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: -1.15 pp (95% -7.93 pp .. +4.49 pp), N=291, clusters=100
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H: +1.11 pp (95% -1.62 pp .. +4.17 pp), N=366, clusters=101
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: -1.04 pp (95% -6.56 pp .. +4.19 pp), N=291, clusters=100
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H: +3.25 pp (95% -0.04 pp .. +6.61 pp), N=366, clusters=101
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: -1.60 pp (95% -7.96 pp .. +4.18 pp), N=291, clusters=100

## Decisions

- TOTAL_LOCAL_DEPTH → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'family']
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'interval', 'family']
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loeo', 'family', 'side']
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'interval', 'epochs', 'family']
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'family']
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'family']
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loeo', 'family', 'side']
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loeo', 'family', 'side']
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'family']
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'family']

## Shape

- TOTAL_LOCAL_DEPTH → RESOLVE_4H: monotonic; low n=252 rate=0.9405, mid n=255 rate=0.9020, high n=255 rate=0.8941
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED: monotonic; low n=237 rate=0.3713, mid n=230 rate=0.4043, high n=228 rate=0.4386
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H: u_shape; low n=254 rate=0.9213, mid n=254 rate=0.8858, high n=254 rate=0.9291
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED: u_shape; low n=234 rate=0.3889, mid n=225 rate=0.3778, high n=236 rate=0.4449
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H: u_shape; low n=253 rate=0.9012, mid n=254 rate=0.9291, high n=255 rate=0.9059
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: monotonic; low n=228 rate=0.4254, mid n=236 rate=0.4025, high n=231 rate=0.3853
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H: monotonic; low n=253 rate=0.9328, mid n=254 rate=0.9055, high n=255 rate=0.8980
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: monotonic; low n=236 rate=0.4110, mid n=230 rate=0.4087, high n=229 rate=0.3930
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H: monotonic; low n=253 rate=0.9249, mid n=253 rate=0.9130, high n=256 rate=0.8984
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED: monotonic; low n=234 rate=0.4487, mid n=231 rate=0.4026, high n=230 rate=0.3609

## Stability

### epoch

- TOTAL_LOCAL_DEPTH → RESOLVE_4H [2023H1]: -1.76 pp, N=180
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [2023H2]: -6.41 pp, N=189
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [2024H1]: -1.87 pp, N=194
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [2024H2]: -2.16 pp, N=199
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [2023H1]: +0.37 pp, N=167
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [2023H2]: +10.37 pp, N=170
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [2024H1]: +2.29 pp, N=182
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [2024H2]: +3.61 pp, N=176
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [2023H1]: -1.37 pp, N=180
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [2023H2]: +1.09 pp, N=189
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [2024H1]: +0.73 pp, N=194
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [2024H2]: -2.19 pp, N=199
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [2023H1]: +5.15 pp, N=167
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [2023H2]: +6.92 pp, N=170
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [2024H1]: -5.00 pp, N=182
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [2024H2]: +4.22 pp, N=176
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [2023H1]: -2.15 pp, N=180
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [2023H2]: -4.68 pp, N=189
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [2024H1]: -0.69 pp, N=194
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [2024H2]: -0.05 pp, N=199
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2023H1]: +3.68 pp, N=167
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2023H2]: -4.42 pp, N=170
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2024H1]: -6.18 pp, N=182
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2024H2]: -4.72 pp, N=176
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [2023H1]: +0.98 pp, N=180
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [2023H2]: -1.78 pp, N=189
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [2024H1]: -0.02 pp, N=194
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [2024H2]: +0.17 pp, N=199
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2023H1]: -8.95 pp, N=167
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2023H2]: -0.26 pp, N=170
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2024H1]: +3.72 pp, N=182
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2024H2]: +1.75 pp, N=176
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [2023H1]: -1.37 pp, N=180
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [2023H2]: -4.15 pp, N=189
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [2024H1]: -0.64 pp, N=194
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [2024H2]: -0.40 pp, N=199
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2023H1]: -2.99 pp, N=167
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2023H2]: -2.08 pp, N=170
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2024H1]: -4.18 pp, N=182
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [2024H2]: -1.12 pp, N=176

### family

- TOTAL_LOCAL_DEPTH → RESOLVE_4H [DAY]: -2.76 pp, N=649
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [WEEK]: -1.56 pp, N=98
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [MONTH]: -0.00 pp, N=15
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [DAY]: +3.15 pp, N=584
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [WEEK]: +7.10 pp, N=96
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [MONTH]: -4.15 pp, N=15
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [DAY]: +0.37 pp, N=649
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [WEEK]: -2.98 pp, N=98
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [MONTH]: +0.00 pp, N=15
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [DAY]: +2.80 pp, N=584
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [WEEK]: +6.17 pp, N=96
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [MONTH]: +6.80 pp, N=15
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [DAY]: -0.57 pp, N=649
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [WEEK]: -4.63 pp, N=98
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [MONTH]: +0.00 pp, N=15
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [DAY]: -3.12 pp, N=584
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [WEEK]: -4.00 pp, N=96
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [MONTH]: +6.35 pp, N=15
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [DAY]: -0.13 pp, N=649
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [WEEK]: +0.40 pp, N=98
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [MONTH]: -0.00 pp, N=15
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [DAY]: +0.50 pp, N=584
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [WEEK]: -5.40 pp, N=96
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [MONTH]: -13.73 pp, N=15
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [DAY]: -0.48 pp, N=649
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [WEEK]: -3.95 pp, N=98
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [MONTH]: -0.00 pp, N=15
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [DAY]: -1.72 pp, N=584
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [WEEK]: -4.87 pp, N=96
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [MONTH]: -4.45 pp, N=15

### side

- TOTAL_LOCAL_DEPTH → RESOLVE_4H [resistance]: -2.80 pp, N=415
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [support]: -1.68 pp, N=347
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [resistance]: +0.35 pp, N=376
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [support]: +7.48 pp, N=319
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [resistance]: -2.56 pp, N=415
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [support]: +2.09 pp, N=347
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [resistance]: +1.14 pp, N=376
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [support]: +5.65 pp, N=319
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [resistance]: -2.47 pp, N=415
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [support]: -0.21 pp, N=347
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [resistance]: -2.27 pp, N=376
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [support]: -3.58 pp, N=319
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [resistance]: +1.43 pp, N=415
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [support]: -1.10 pp, N=347
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [resistance]: +2.02 pp, N=376
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [support]: -2.68 pp, N=319
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [resistance]: -1.21 pp, N=415
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [support]: -0.81 pp, N=347
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [resistance]: -0.22 pp, N=376
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [support]: -3.74 pp, N=319

## Leave-one-epoch-out

- TOTAL_LOCAL_DEPTH → RESOLVE_4H [omit_2023H1]: -2.81 pp, N=582
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [omit_2023H2]: -1.66 pp, N=573
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [omit_2024H1]: -3.05 pp, N=568
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [omit_2024H2]: -3.20 pp, N=563
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [omit_2023H1]: +4.35 pp, N=528
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [omit_2023H2]: +2.82 pp, N=525
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [omit_2024H1]: +4.87 pp, N=513
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [omit_2024H2]: +4.07 pp, N=519
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [omit_2023H1]: +0.12 pp, N=582
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [omit_2023H2]: -0.71 pp, N=573
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [omit_2024H1]: -0.47 pp, N=568
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [omit_2024H2]: +0.65 pp, N=563
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [omit_2023H1]: +2.69 pp, N=528
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [omit_2023H2]: +3.04 pp, N=525
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [omit_2024H1]: +6.25 pp, N=513
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [omit_2024H2]: +3.22 pp, N=519
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2023H1]: -0.99 pp, N=582
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2023H2]: -0.52 pp, N=573
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2024H1]: -1.54 pp, N=568
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2024H2]: -1.40 pp, N=563
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2023H1]: -4.08 pp, N=528
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2023H2]: -1.93 pp, N=525
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2024H1]: -1.33 pp, N=513
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2024H2]: -1.43 pp, N=519
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2023H1]: -0.24 pp, N=582
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2023H2]: +0.63 pp, N=573
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2024H1]: +0.10 pp, N=568
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2024H2]: -0.35 pp, N=563
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2023H1]: +1.62 pp, N=528
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2023H2]: -0.03 pp, N=525
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2024H1]: -2.08 pp, N=513
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2024H2]: -1.70 pp, N=519
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2023H1]: -0.97 pp, N=582
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2023H2]: -0.28 pp, N=573
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2024H1]: -1.29 pp, N=568
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [omit_2024H2]: -1.25 pp, N=563
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2023H1]: -1.80 pp, N=528
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2023H2]: -1.21 pp, N=525
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2024H1]: -1.38 pp, N=513
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2024H2]: -2.00 pp, N=519

## Leave-one-family-out

- TOTAL_LOCAL_DEPTH → RESOLVE_4H [omit_DAY]: n/a, N=113, dropped share 0.8517
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [omit_WEEK]: -2.69 pp, N=664, dropped share 0.1286
- TOTAL_LOCAL_DEPTH → RESOLVE_4H [omit_MONTH]: -2.67 pp, N=747, dropped share 0.0197
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=111, dropped share 0.8403
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [omit_WEEK]: +3.49 pp, N=599, dropped share 0.1381
- TOTAL_LOCAL_DEPTH → BREAK_GIVEN_RESOLVED [omit_MONTH]: +3.75 pp, N=680, dropped share 0.0216
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [omit_DAY]: n/a, N=113, dropped share 0.8517
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [omit_WEEK]: +0.35 pp, N=664, dropped share 0.1286
- ORIENTED_DEPTH_IMBALANCE → RESOLVE_4H [omit_MONTH]: -0.07 pp, N=747, dropped share 0.0197
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=111, dropped share 0.8403
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [omit_WEEK]: +3.84 pp, N=599, dropped share 0.1381
- ORIENTED_DEPTH_IMBALANCE → BREAK_GIVEN_RESOLVED [omit_MONTH]: +3.05 pp, N=680, dropped share 0.0216
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [omit_DAY]: n/a, N=113, dropped share 0.8517
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [omit_WEEK]: -0.41 pp, N=664, dropped share 0.1286
- AHEAD_DEPTH_CHANGE_60M → RESOLVE_4H [omit_MONTH]: -1.19 pp, N=747, dropped share 0.0197
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=111, dropped share 0.8403
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_WEEK]: -1.71 pp, N=599, dropped share 0.1381
- AHEAD_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_MONTH]: -3.24 pp, N=680, dropped share 0.0216
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [omit_DAY]: n/a, N=113, dropped share 0.8517
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [omit_WEEK]: -0.03 pp, N=664, dropped share 0.1286
- BEHIND_DEPTH_CHANGE_60M → RESOLVE_4H [omit_MONTH]: -0.00 pp, N=747, dropped share 0.0197
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=111, dropped share 0.8403
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_WEEK]: +0.03 pp, N=599, dropped share 0.1381
- BEHIND_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_MONTH]: -0.07 pp, N=680, dropped share 0.0216
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [omit_DAY]: n/a, N=113, dropped share 0.8517
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [omit_WEEK]: -0.32 pp, N=664, dropped share 0.1286
- TOTAL_DEPTH_CHANGE_60M → RESOLVE_4H [omit_MONTH]: -1.00 pp, N=747, dropped share 0.0197
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=111, dropped share 0.8403
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_WEEK]: -0.89 pp, N=599, dropped share 0.1381
- TOTAL_DEPTH_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_MONTH]: -2.10 pp, N=680, dropped share 0.0216

## Routing

Routing `NO_INCREMENTAL_LEVEL_LIQUIDITY_STRUCTURE`.
LEVEL_LIQUIDITY_INTERACTION_CANDIDATE count: 0.
GENERIC_LIQUIDITY_STATE_CANDIDATE count: 0.
SUCCESSOR_CANDIDATE = `NONE`.
PRODUCT_INTEGRATION_CANDIDATE = False.
Claim ceiling L2. A historical association is not a current probability.
Positive imbalance means more visible depth ahead of the approach than behind it. It does not mean the level is strong. A thin book is not read as a break.
No trade call and no product change.

Exploratory successor ideas, not estimated:

- EXPLORATORY_SUCCESSOR_IDEA: ORIENTED_DEPTH_IMBALANCE vs RESOLVE_4H is u_shape across frozen tertiles. No threshold, band change, or combined state was fit.
- EXPLORATORY_SUCCESSOR_IDEA: ORIENTED_DEPTH_IMBALANCE vs BREAK_GIVEN_RESOLVED is u_shape across frozen tertiles. No threshold, band change, or combined state was fit.
- EXPLORATORY_SUCCESSOR_IDEA: AHEAD_DEPTH_CHANGE_60M vs RESOLVE_4H is u_shape across frozen tertiles. No threshold, band change, or combined state was fit.

## Reporting note

Leave-one-family-out omitting DAY did not return a coefficient (complement N=113 under the full nuisance design). The frozen rule treats a missing coefficient on a complement with N≥30 as a family failure, so every primary cell lists `family`. That clause is not what decides the route. Every cell already fails Benjamini–Hochberg q=0.10. The two cells whose absolute point is at least 3 pp (total local depth → BREAK +4.03 pp; oriented imbalance → BREAK +3.93 pp) have intervals that include 0. Total local depth → RESOLVE is −2.61 pp, its interval excludes 0, and it is below the 3 pp scale. No coefficient was recomputed and the evaluator was not rerun.

The pseudo-only oriented-imbalance → RESOLVE slope is +5.09 pp (95% +1.64..+8.65). It is not a generic candidate. The real-cohort slope is −0.06 pp and the conjunction failed.
