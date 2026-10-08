# LEVEL_POSITIONING_FLOW_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. This note does not change the product.

## Provenance

Design SHA `2491bbe9277faa24f0e5e3a295bbe6a01672ddf9`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.

Dependencies, not rewritten:

- touch: `dfc9e0f04358de15606382472badeb5aee787039`
- memory: `c3d39bffda861b535605a98205d7578c0c84c782`
- method: `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`
- approach: `aa85e5b43c405ee225336ff385e3a3383fa59d09`
- structure: `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`
- confirmation: `c1cd4e0102e700f7860d21a9af0d243c3bc367be`

## Data

CORE `CORE_BTC_BINANCE_V0` zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`.
OI git snapshot `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33` oi.jsonl SHA256 `c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94` rows 455273. Runtime wrapper snapshot `dc7435fe4a5f7c8239edf076954a9072b3b9497a62f3e549c1614abf34a70e18`. Funding opened: False.
Event window 2020-09-01T01:05:00+00:00 inclusive to 2025-01-01T00:00:00+00:00 exclusive.

## Cohort

Retained features: OI_CHANGE_60M, OI_RECENT_ACCELERATION, ORIENTED_TAKER_IMBALANCE_60M, TAKER_RECENT_SHIFT.
Dropped before outcomes: [].
Search exposure: `{'raw_features': 4, 'retained_features': 4, 'windows': 2, 'outcomes': 2, 'primary_cells': 8, 'shape_cells': 8, 'pseudo_cells': 8, 'specificity_cells': 8, 'stability_cells': 80, 'loyo_cells': 40, 'lofo_cells': 24, 'interactions': 0, 'extra_window_sensitivities': 0}`.
Seed 20261013, bootstrap draws 2000, FDR q=0.1, practical scale 0.03.

## Decomposition

Crude BREAK / REJECT / NEITHER frequencies on geometry-legitimate first touches, including events whose positioning window is incomplete. Ambiguous labels are excluded from the rates.

BREAK 688 (0.4052), REJECT 843 (0.4965), NEITHER 167 (0.0984), RESOLVE 0.9016, ambiguous 10.

## RESOLVE_4H

- OI_CHANGE_60M → RESOLVE_4H: +0.41 pp (95% -0.88 pp .. +1.63 pp), p=0.5184, q=0.8294, N=1679, clusters=227
- OI_RECENT_ACCELERATION → RESOLVE_4H: -0.18 pp (95% -1.24 pp .. +0.85 pp), p=0.7424, q=0.8485, N=1679, clusters=227
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H: -0.62 pp (95% -2.21 pp .. +0.90 pp), p=0.4345, q=0.8294, N=1698, clusters=227
- TAKER_RECENT_SHIFT → RESOLVE_4H: +0.01 pp (95% -1.67 pp .. +1.78 pp), p=0.9899, q=0.9899, N=1698, clusters=227

## BREAK_GIVEN_RESOLVED

- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED: +1.77 pp (95% -0.74 pp .. +4.41 pp), p=0.1775, q=0.4734, N=1513, clusters=227
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED: +2.90 pp (95% +0.43 pp .. +5.50 pp), p=0.0271, q=0.2011, N=1513, clusters=227
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED: +2.68 pp (95% -0.20 pp .. +5.22 pp), p=0.0503, q=0.2011, N=1531, clusters=227
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED: -0.57 pp (95% -3.11 pp .. +1.94 pp), p=0.6598, q=0.8485, N=1531, clusters=227

## Specificity (beta_real - beta_pseudo)

- OI_CHANGE_60M → RESOLVE_4H: delta -0.61 pp (95% -2.43 pp .. +1.08 pp), beta_real -0.10 pp, beta_pseudo +0.51 pp, N=2118, clusters=224
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED: delta +2.90 pp (95% -1.20 pp .. +7.10 pp), beta_real +2.59 pp, beta_pseudo -0.31 pp, N=1622, clusters=222
- OI_RECENT_ACCELERATION → RESOLVE_4H: delta -0.72 pp (95% -2.61 pp .. +1.16 pp), beta_real -0.28 pp, beta_pseudo +0.44 pp, N=2118, clusters=224
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED: delta +4.21 pp (95% +0.28 pp .. +8.38 pp), beta_real +3.88 pp, beta_pseudo -0.33 pp, N=1622, clusters=222
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H: delta -4.35 pp (95% -7.04 pp .. -1.68 pp), beta_real -2.07 pp, beta_pseudo +2.28 pp, N=2148, clusters=224
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED: delta +5.32 pp (95% +0.41 pp .. +9.94 pp), beta_real +4.96 pp, beta_pseudo -0.37 pp, N=1652, clusters=222
- TAKER_RECENT_SHIFT → RESOLVE_4H: delta +0.43 pp (95% -2.18 pp .. +3.31 pp), beta_real +0.74 pp, beta_pseudo +0.31 pp, N=2148, clusters=224
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED: delta +3.72 pp (95% -0.65 pp .. +8.29 pp), beta_real +1.81 pp, beta_pseudo -1.91 pp, N=1652, clusters=222

## Pseudo cohort

- OI_CHANGE_60M → RESOLVE_4H: +0.66 pp (95% -1.10 pp .. +2.48 pp), N=1059, clusters=224
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED: -0.20 pp (95% -3.84 pp .. +3.23 pp), N=811, clusters=222
- OI_RECENT_ACCELERATION → RESOLVE_4H: +0.51 pp (95% -1.09 pp .. +2.02 pp), N=1059, clusters=224
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED: -0.26 pp (95% -3.42 pp .. +2.80 pp), N=811, clusters=222
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H: +2.22 pp (95% -0.43 pp .. +4.78 pp), N=1074, clusters=224
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED: -1.44 pp (95% -5.84 pp .. +3.03 pp), N=826, clusters=222
- TAKER_RECENT_SHIFT → RESOLVE_4H: +0.49 pp (95% -1.78 pp .. +2.64 pp), N=1074, clusters=224
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED: -1.60 pp (95% -5.06 pp .. +2.05 pp), N=826, clusters=222

## Decisions

- OI_CHANGE_60M → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs']
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs']
- OI_RECENT_ACCELERATION → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loyo']
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale']
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs']
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs']
- TAKER_RECENT_SHIFT → RESOLVE_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loyo']
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loyo']

## Shape

- OI_CHANGE_60M → RESOLVE_4H: monotonic; low n=559 rate=0.8837, mid n=560 rate=0.8946, high n=560 rate=0.9250
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED: monotonic; low n=494 rate=0.4231, mid n=501 rate=0.4491, high n=518 rate=0.4768
- OI_RECENT_ACCELERATION → RESOLVE_4H: u_shape; low n=555 rate=0.9207, mid n=562 rate=0.8808, high n=562 rate=0.9021
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED: monotonic; low n=511 rate=0.4188, mid n=495 rate=0.4323, high n=507 rate=0.4990
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H: u_shape; low n=566 rate=0.8958, mid n=568 rate=0.9049, high n=564 rate=0.9043
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED: u_shape; low n=507 rate=0.4517, mid n=514 rate=0.4319, high n=510 rate=0.4647
- TAKER_RECENT_SHIFT → RESOLVE_4H: u_shape; low n=568 rate=0.8979, mid n=565 rate=0.9133, high n=565 rate=0.8938
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED: u_shape; low n=510 rate=0.4608, mid n=516 rate=0.4419, high n=505 rate=0.4455

## Stability

### epoch

- OI_CHANGE_60M → RESOLVE_4H [2020Q4]: -0.12 pp, N=124
- OI_CHANGE_60M → RESOLVE_4H [2021]: +0.45 pp, N=383
- OI_CHANGE_60M → RESOLVE_4H [2022]: -0.69 pp, N=394
- OI_CHANGE_60M → RESOLVE_4H [2023]: +2.04 pp, N=389
- OI_CHANGE_60M → RESOLVE_4H [2024]: -0.48 pp, N=389
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [2020Q4]: -3.77 pp, N=116
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [2021]: +5.07 pp, N=343
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [2022]: +1.94 pp, N=345
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [2023]: +0.88 pp, N=356
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [2024]: +0.51 pp, N=353
- OI_RECENT_ACCELERATION → RESOLVE_4H [2020Q4]: +0.32 pp, N=124
- OI_RECENT_ACCELERATION → RESOLVE_4H [2021]: -0.80 pp, N=383
- OI_RECENT_ACCELERATION → RESOLVE_4H [2022]: -0.36 pp, N=394
- OI_RECENT_ACCELERATION → RESOLVE_4H [2023]: +0.64 pp, N=389
- OI_RECENT_ACCELERATION → RESOLVE_4H [2024]: -0.22 pp, N=389
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [2020Q4]: +0.34 pp, N=116
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [2021]: +2.66 pp, N=343
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [2022]: +4.48 pp, N=345
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [2023]: +4.97 pp, N=356
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [2024]: +2.85 pp, N=353
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [2020Q4]: -2.52 pp, N=124
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [2021]: +0.96 pp, N=394
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [2022]: -2.66 pp, N=395
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [2023]: +2.11 pp, N=390
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [2024]: -1.86 pp, N=395
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [2020Q4]: +9.63 pp, N=116
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [2021]: -3.09 pp, N=354
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [2022]: +1.73 pp, N=346
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [2023]: +1.46 pp, N=357
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [2024]: +2.96 pp, N=358
- TAKER_RECENT_SHIFT → RESOLVE_4H [2020Q4]: -0.72 pp, N=124
- TAKER_RECENT_SHIFT → RESOLVE_4H [2021]: +2.64 pp, N=394
- TAKER_RECENT_SHIFT → RESOLVE_4H [2022]: -2.21 pp, N=395
- TAKER_RECENT_SHIFT → RESOLVE_4H [2023]: -0.83 pp, N=390
- TAKER_RECENT_SHIFT → RESOLVE_4H [2024]: +1.33 pp, N=395
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [2020Q4]: +6.39 pp, N=116
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [2021]: -0.77 pp, N=354
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [2022]: +1.89 pp, N=346
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [2023]: -4.81 pp, N=357
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [2024]: -1.14 pp, N=358

### family

- OI_CHANGE_60M → RESOLVE_4H [DAY]: +0.37 pp, N=1438
- OI_CHANGE_60M → RESOLVE_4H [WEEK]: +0.39 pp, N=208
- OI_CHANGE_60M → RESOLVE_4H [MONTH]: +0.83 pp, N=33
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [DAY]: +0.77 pp, N=1280
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [WEEK]: +5.26 pp, N=201
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [MONTH]: +7.02 pp, N=32
- OI_RECENT_ACCELERATION → RESOLVE_4H [DAY]: -0.08 pp, N=1438
- OI_RECENT_ACCELERATION → RESOLVE_4H [WEEK]: -0.41 pp, N=208
- OI_RECENT_ACCELERATION → RESOLVE_4H [MONTH]: +0.48 pp, N=33
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [DAY]: +3.24 pp, N=1280
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [WEEK]: +1.56 pp, N=201
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [MONTH]: +8.27 pp, N=32
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [DAY]: -0.97 pp, N=1453
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [WEEK]: +0.54 pp, N=212
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [MONTH]: +11.52 pp, N=33
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [DAY]: +0.61 pp, N=1294
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [WEEK]: +12.92 pp, N=205
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [MONTH]: -5.34 pp, N=32
- TAKER_RECENT_SHIFT → RESOLVE_4H [DAY]: +0.11 pp, N=1453
- TAKER_RECENT_SHIFT → RESOLVE_4H [WEEK]: -0.35 pp, N=212
- TAKER_RECENT_SHIFT → RESOLVE_4H [MONTH]: -10.41 pp, N=33
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [DAY]: -0.44 pp, N=1294
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [WEEK]: -3.59 pp, N=205
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [MONTH]: -4.04 pp, N=32

### side

- OI_CHANGE_60M → RESOLVE_4H [resistance]: +0.50 pp, N=904
- OI_CHANGE_60M → RESOLVE_4H [support]: -0.05 pp, N=775
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [resistance]: +1.91 pp, N=796
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [support]: +1.45 pp, N=717
- OI_RECENT_ACCELERATION → RESOLVE_4H [resistance]: +0.14 pp, N=904
- OI_RECENT_ACCELERATION → RESOLVE_4H [support]: -0.53 pp, N=775
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [resistance]: +2.92 pp, N=796
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [support]: +2.88 pp, N=717
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [resistance]: -1.41 pp, N=912
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [support]: +0.90 pp, N=786
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [resistance]: +4.05 pp, N=804
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [support]: +0.79 pp, N=727
- TAKER_RECENT_SHIFT → RESOLVE_4H [resistance]: -0.00 pp, N=912
- TAKER_RECENT_SHIFT → RESOLVE_4H [support]: +0.07 pp, N=786
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [resistance]: -0.06 pp, N=804
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [support]: -1.09 pp, N=727

## Leave-one-year-out

- OI_CHANGE_60M → RESOLVE_4H [omit_2020Q4]: +0.41 pp, N=1555
- OI_CHANGE_60M → RESOLVE_4H [omit_2021]: +0.02 pp, N=1296
- OI_CHANGE_60M → RESOLVE_4H [omit_2022]: +0.83 pp, N=1285
- OI_CHANGE_60M → RESOLVE_4H [omit_2023]: +0.03 pp, N=1290
- OI_CHANGE_60M → RESOLVE_4H [omit_2024]: +0.62 pp, N=1290
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2020Q4]: +2.33 pp, N=1397
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2021]: +0.90 pp, N=1170
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2022]: +1.70 pp, N=1168
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2023]: +1.96 pp, N=1157
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_2024]: +1.91 pp, N=1160
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_2020Q4]: -0.31 pp, N=1555
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_2021]: +0.03 pp, N=1296
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_2022]: -0.06 pp, N=1285
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_2023]: -0.35 pp, N=1290
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_2024]: -0.17 pp, N=1290
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_2020Q4]: +3.43 pp, N=1397
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_2021]: +3.48 pp, N=1170
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_2022]: +2.66 pp, N=1168
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_2023]: +2.17 pp, N=1157
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_2024]: +2.95 pp, N=1160
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_2020Q4]: -0.36 pp, N=1574
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_2021]: -0.90 pp, N=1304
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_2022]: -0.18 pp, N=1303
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_2023]: -1.58 pp, N=1308
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_2024]: -0.12 pp, N=1303
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_2020Q4]: +1.83 pp, N=1415
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_2021]: +3.15 pp, N=1177
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_2022]: +2.84 pp, N=1185
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_2023]: +3.18 pp, N=1174
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_2024]: +2.18 pp, N=1173
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_2020Q4]: +0.11 pp, N=1574
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_2021]: -0.44 pp, N=1304
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_2022]: +0.55 pp, N=1303
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_2023]: +0.29 pp, N=1308
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_2024]: -0.46 pp, N=1303
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_2020Q4]: -1.43 pp, N=1415
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_2021]: -0.48 pp, N=1177
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_2022]: -1.24 pp, N=1185
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_2023]: +0.80 pp, N=1174
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_2024]: -0.29 pp, N=1173

## Leave-one-family-out

- OI_CHANGE_60M → RESOLVE_4H [omit_DAY]: n/a, N=241, dropped share 0.8565
- OI_CHANGE_60M → RESOLVE_4H [omit_WEEK]: +0.47 pp, N=1471, dropped share 0.1239
- OI_CHANGE_60M → RESOLVE_4H [omit_MONTH]: +0.33 pp, N=1646, dropped share 0.0197
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=233, dropped share 0.8460
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_WEEK]: +1.05 pp, N=1312, dropped share 0.1328
- OI_CHANGE_60M → BREAK_GIVEN_RESOLVED [omit_MONTH]: +1.57 pp, N=1481, dropped share 0.0212
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_DAY]: n/a, N=241, dropped share 0.8565
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_WEEK]: -0.05 pp, N=1471, dropped share 0.1239
- OI_RECENT_ACCELERATION → RESOLVE_4H [omit_MONTH]: -0.21 pp, N=1646, dropped share 0.0197
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=233, dropped share 0.8460
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_WEEK]: +3.68 pp, N=1312, dropped share 0.1328
- OI_RECENT_ACCELERATION → BREAK_GIVEN_RESOLVED [omit_MONTH]: +2.49 pp, N=1481, dropped share 0.0212
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_DAY]: n/a, N=245, dropped share 0.8557
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_WEEK]: -0.91 pp, N=1486, dropped share 0.1249
- ORIENTED_TAKER_IMBALANCE_60M → RESOLVE_4H [omit_MONTH]: -0.67 pp, N=1665, dropped share 0.0194
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=237, dropped share 0.8452
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_WEEK]: +0.57 pp, N=1326, dropped share 0.1339
- ORIENTED_TAKER_IMBALANCE_60M → BREAK_GIVEN_RESOLVED [omit_MONTH]: +2.74 pp, N=1499, dropped share 0.0209
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_DAY]: n/a, N=245, dropped share 0.8557
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_WEEK]: +0.11 pp, N=1486, dropped share 0.1249
- TAKER_RECENT_SHIFT → RESOLVE_4H [omit_MONTH]: +0.01 pp, N=1665, dropped share 0.0194
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=237, dropped share 0.8452
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_WEEK]: -0.23 pp, N=1326, dropped share 0.1339
- TAKER_RECENT_SHIFT → BREAK_GIVEN_RESOLVED [omit_MONTH]: -0.78 pp, N=1499, dropped share 0.0209

## Routing

Routing `NO_INCREMENTAL_POSITION_FLOW_STRUCTURE`.
SUCCESSOR_CANDIDATE = `NONE`.
PRODUCT_INTEGRATION_CANDIDATE = False.
Claim ceiling L2. A selected cell is a historical association in this cohort, not a current probability.
OI up is more outstanding open interest. Oriented flow is aggressive executed volume toward the level.
No long/short identity, no trade call, no product change.

Exploratory successor ideas, not estimated:

- EXPLORATORY_SUCCESSOR_IDEA: OI_RECENT_ACCELERATION vs RESOLVE_4H is U-shaped across frozen tertiles. No threshold, saturation model, or interaction was fit.
- EXPLORATORY_SUCCESSOR_IDEA: ORIENTED_TAKER_IMBALANCE_60M vs RESOLVE_4H is U-shaped across frozen tertiles. No threshold, saturation model, or interaction was fit.
- EXPLORATORY_SUCCESSOR_IDEA: ORIENTED_TAKER_IMBALANCE_60M vs BREAK_GIVEN_RESOLVED is U-shaped across frozen tertiles. No threshold, saturation model, or interaction was fit.
- EXPLORATORY_SUCCESSOR_IDEA: TAKER_RECENT_SHIFT vs RESOLVE_4H is U-shaped across frozen tertiles. No threshold, saturation model, or interaction was fit.
- EXPLORATORY_SUCCESSOR_IDEA: TAKER_RECENT_SHIFT vs BREAK_GIVEN_RESOLVED is U-shaped across frozen tertiles. No threshold, saturation model, or interaction was fit.

## Reporting note

`bootstrap_valid` on the unstacked primary and pseudo cells is 0. That field is the finite-draw count of the last target key. For an unstacked fit the last key is `delta`, which stays unused, so the returned count is 0. A coefficient interval is written only when that coefficient's own draws clear 90% of 2000. Every primary and pseudo `ci95` in this file is non-null, so those coefficients cleared that bar. The eight stacked specificity cells report `bootstrap_valid` = 2000 because `delta` is their last key and was filled. Coefficients, intervals, q-values and the routing were not recomputed.
