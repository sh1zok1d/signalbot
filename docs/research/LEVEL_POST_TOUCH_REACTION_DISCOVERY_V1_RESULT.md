# LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. Decision time is 15 minutes after the first touch. Events that already reached a barrier before that time are a census, not a prediction. This note does not change the product.

## Provenance

Design SHA `f3101015f33b19d38b38c226891422c5863cc723`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
Exposure `DISCOVERY_ONLY`.

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

## Data

CORE `CORE_BTC_BINANCE_V0` zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`.
OI `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` snapshot `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33` jsonl SHA256 `c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94`. Funding opened: False.
Event window 2020-09-01T00:05:00+00:00 inclusive to 2025-01-01T00:00:00+00:00 exclusive.
T is the open of the touch bar. D = T+15m. Reaction bars are j, j+1, j+2. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.

## Cohort

Retained features: END_POSITION_X, RELATIVE_ACTIVITY_15M, ORIENTED_TAKER_REACTION_15M, TAKER_CHANGE_VS_PRE, OI_REACTION_15M.
Dropped before outcomes: [].
Search exposure: `{'raw_features': 5, 'retained_features': 5, 'reaction_bars': 3, 'outcomes': 2, 'primary_cells': 10, 'shape_cells': 10, 'pseudo_cells': 10, 'specificity_cells': 10, 'stability_cells': 100, 'loyo_cells': 50, 'lofo_cells': 30, 'interactions': 0, 'acceptance_flags': 0, 'horizon_extensions': 0, 'extra_window_sensitivities': 0}`.
Seed 20261017, bootstrap draws 2000, FDR q=0.1, practical scale 0.03.

## Early census

Counts of geometry-legitimate first touches. No real-versus-pseudo test is reported.

N 1709. Early BREAK 260 (0.1521), early REJECT 238 (0.1393), early ambiguous 9 (0.0053), unresolved 1202 (0.7033), unavailable 0.

## Late decomposition

BREAK / REJECT / NEITHER after D, on events unresolved at D. Ambiguous labels are excluded from the rates.

BREAK 428 (0.3564), REJECT 606 (0.5046), NEITHER 167 (0.1391), RESOLVE 0.8609, ambiguous 1.

## LATE_RESOLVE_BY_4H

- END_POSITION_X → LATE_RESOLVE_BY_4H: -2.06 pp (95% -4.22 pp .. +0.05 pp), p=0.0588, q=0.2451, N=1201, clusters=227, bootstrap_valid=2000
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H: +1.01 pp (95% -1.80 pp .. +3.86 pp), p=0.4824, q=0.8039, N=1201, clusters=227, bootstrap_valid=2000
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H: -1.30 pp (95% -3.37 pp .. +1.24 pp), p=0.2792, q=0.6981, N=1201, clusters=227, bootstrap_valid=2000
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H: -0.24 pp (95% -2.26 pp .. +1.88 pp), p=0.8236, q=0.8471, N=1201, clusters=227, bootstrap_valid=2000
- OI_REACTION_15M → LATE_RESOLVE_BY_4H: +0.85 pp (95% -1.15 pp .. +2.76 pp), p=0.4041, q=0.8039, N=1198, clusters=227, bootstrap_valid=2000

## LATE_BREAK_GIVEN_RESOLVED

- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED: +20.31 pp (95% +17.20 pp .. +23.46 pp), p=0.0000, q=0.0000, N=1034, clusters=226, bootstrap_valid=2000
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED: +0.78 pp (95% -2.76 pp .. +4.41 pp), p=0.6793, q=0.8471, N=1034, clusters=226, bootstrap_valid=2000
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: +3.09 pp (95% -0.33 pp .. +6.41 pp), p=0.0735, q=0.2451, N=1034, clusters=226, bootstrap_valid=1998
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED: +0.95 pp (95% -2.30 pp .. +4.20 pp), p=0.5653, q=0.8076, N=1034, clusters=226, bootstrap_valid=2000
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: -0.28 pp (95% -3.13 pp .. +2.63 pp), p=0.8471, q=0.8471, N=1031, clusters=226, bootstrap_valid=2000

## Specificity (beta_real - beta_pseudo)

- END_POSITION_X → LATE_RESOLVE_BY_4H: delta -1.90 pp (95% n/a), beta_real -3.28 pp, beta_pseudo -1.38 pp, N=1206, clusters=207
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED: delta -8.11 pp (95% n/a), beta_real +22.66 pp, beta_pseudo +30.77 pp, N=826, clusters=190
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H: delta -1.07 pp (95% n/a), beta_real +1.30 pp, beta_pseudo +2.36 pp, N=1206, clusters=207
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED: delta +3.87 pp (95% n/a), beta_real +0.99 pp, beta_pseudo -2.88 pp, N=826, clusters=190
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H: delta +1.27 pp (95% n/a), beta_real -2.45 pp, beta_pseudo -3.72 pp, N=1206, clusters=207
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: delta +4.37 pp (95% n/a), beta_real +1.24 pp, beta_pseudo -3.13 pp, N=826, clusters=190
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H: delta +5.45 pp (95% n/a), beta_real +0.15 pp, beta_pseudo -5.30 pp, N=1206, clusters=207
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED: delta -0.14 pp (95% n/a), beta_real -1.34 pp, beta_pseudo -1.19 pp, N=826, clusters=190
- OI_REACTION_15M → LATE_RESOLVE_BY_4H: delta +1.80 pp (95% n/a), beta_real +1.00 pp, beta_pseudo -0.80 pp, N=1198, clusters=207
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: delta +0.04 pp (95% n/a), beta_real -1.50 pp, beta_pseudo -1.53 pp, N=820, clusters=189

## Pseudo cohort

- END_POSITION_X → LATE_RESOLVE_BY_4H: -2.11 pp (95% n/a), N=603, clusters=207
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED: +30.13 pp (95% n/a), N=413, clusters=190
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H: +3.27 pp (95% n/a), N=603, clusters=207
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED: -2.99 pp (95% n/a), N=413, clusters=190
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H: -3.86 pp (95% n/a), N=603, clusters=207
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: -4.66 pp (95% n/a), N=413, clusters=190
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H: -6.08 pp (95% n/a), N=603, clusters=207
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED: -2.13 pp (95% n/a), N=413, clusters=190
- OI_REACTION_15M → LATE_RESOLVE_BY_4H: -0.57 pp (95% n/a), N=599, clusters=207
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: -1.29 pp (95% n/a), N=410, clusters=189

## Decisions

- END_POSITION_X → LATE_RESOLVE_BY_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'family']
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['family']
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'family']
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'family', 'side']
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'family']
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'interval', 'epochs', 'family']
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'loyo', 'family', 'side']
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'loyo', 'family', 'side']
- OI_REACTION_15M → LATE_RESOLVE_BY_4H: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'epochs', 'family', 'side']
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: label NONE, conjunction False, failed ['fdr', 'scale', 'interval', 'loyo', 'family', 'side']

## Shape

- END_POSITION_X → LATE_RESOLVE_BY_4H: monotonic; low n=400 rate=0.9100, mid n=400 rate=0.8475, high n=401 rate=0.8254
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED: monotonic; low n=364 rate=0.2473, mid n=339 rate=0.3599, high n=331 rate=0.6526
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H: u_shape; low n=401 rate=0.8504, mid n=400 rate=0.8850, high n=400 rate=0.8475
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED: monotonic; low n=341 rate=0.3343, mid n=354 rate=0.4181, high n=339 rate=0.4897
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H: monotonic; low n=401 rate=0.8728, mid n=400 rate=0.8700, high n=400 rate=0.8400
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: monotonic; low n=350 rate=0.2800, mid n=348 rate=0.4397, high n=336 rate=0.5268
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H: monotonic; low n=401 rate=0.8803, mid n=400 rate=0.8525, high n=400 rate=0.8500
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED: monotonic; low n=353 rate=0.3229, mid n=341 rate=0.4135, high n=340 rate=0.5088
- OI_REACTION_15M → LATE_RESOLVE_BY_4H: monotonic; low n=400 rate=0.8525, mid n=398 rate=0.8568, high n=400 rate=0.8725
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED: u_shape; low n=341 rate=0.4575, mid n=341 rate=0.3431, high n=349 rate=0.4413

## Stability

### epoch

- END_POSITION_X → LATE_RESOLVE_BY_4H [2020Q4]: -1.82 pp, N=84
- END_POSITION_X → LATE_RESOLVE_BY_4H [2021]: +0.00 pp, N=270
- END_POSITION_X → LATE_RESOLVE_BY_4H [2022]: -7.61 pp, N=297
- END_POSITION_X → LATE_RESOLVE_BY_4H [2023]: -0.25 pp, N=245
- END_POSITION_X → LATE_RESOLVE_BY_4H [2024]: -2.60 pp, N=305
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [2020Q4]: +18.67 pp, N=76
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [2021]: +28.54 pp, N=230
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [2022]: +24.40 pp, N=248
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [2023]: +11.66 pp, N=212
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [2024]: +22.24 pp, N=268
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [2020Q4]: -7.82 pp, N=84
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [2021]: +2.50 pp, N=270
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [2022]: +0.98 pp, N=297
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [2023]: +3.68 pp, N=245
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [2024]: -0.08 pp, N=305
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [2020Q4]: +6.45 pp, N=76
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [2021]: +2.31 pp, N=230
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [2022]: +2.77 pp, N=248
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [2023]: +1.42 pp, N=212
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [2024]: -2.16 pp, N=268
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [2020Q4]: -6.18 pp, N=84
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [2021]: -0.90 pp, N=270
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [2022]: -0.70 pp, N=297
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [2023]: -1.48 pp, N=245
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [2024]: +0.05 pp, N=305
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2020Q4]: -0.71 pp, N=76
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2021]: -0.21 pp, N=230
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2022]: +3.52 pp, N=248
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2023]: +2.07 pp, N=212
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2024]: +2.27 pp, N=268
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [2020Q4]: -0.70 pp, N=84
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [2021]: +0.10 pp, N=270
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [2022]: +1.02 pp, N=297
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [2023]: -2.74 pp, N=245
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [2024]: +1.27 pp, N=305
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [2020Q4]: -11.17 pp, N=76
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [2021]: +1.74 pp, N=230
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [2022]: +1.39 pp, N=248
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [2023]: +0.59 pp, N=212
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [2024]: +1.97 pp, N=268
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [2020Q4]: +6.41 pp, N=84
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [2021]: +1.54 pp, N=269
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [2022]: -2.28 pp, N=296
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [2023]: -1.95 pp, N=245
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [2024]: +3.10 pp, N=304
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2020Q4]: -6.91 pp, N=76
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2021]: +1.85 pp, N=229
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2022]: -0.37 pp, N=247
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2023]: -0.85 pp, N=212
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [2024]: -1.90 pp, N=267

### family

- END_POSITION_X → LATE_RESOLVE_BY_4H [DAY]: -2.17 pp, N=1071
- END_POSITION_X → LATE_RESOLVE_BY_4H [WEEK]: -2.64 pp, N=120
- END_POSITION_X → LATE_RESOLVE_BY_4H [MONTH]: n/a, N=10
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [DAY]: +20.20 pp, N=912
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [WEEK]: +19.45 pp, N=113
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [MONTH]: n/a, N=9
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [DAY]: +1.22 pp, N=1071
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [WEEK]: -2.45 pp, N=120
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [MONTH]: n/a, N=10
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [DAY]: -0.35 pp, N=912
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [WEEK]: +5.46 pp, N=113
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [MONTH]: n/a, N=9
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [DAY]: -1.34 pp, N=1071
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [WEEK]: -1.22 pp, N=120
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [MONTH]: n/a, N=10
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [DAY]: +2.83 pp, N=912
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [WEEK]: +5.67 pp, N=113
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [MONTH]: n/a, N=9
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [DAY]: -0.07 pp, N=1071
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [WEEK]: -2.59 pp, N=120
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [MONTH]: n/a, N=10
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [DAY]: +1.76 pp, N=912
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [WEEK]: -10.43 pp, N=113
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [MONTH]: n/a, N=9
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [DAY]: +1.41 pp, N=1070
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [WEEK]: +0.38 pp, N=118
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [MONTH]: n/a, N=10
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [DAY]: +0.48 pp, N=911
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [WEEK]: -3.35 pp, N=111
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [MONTH]: n/a, N=9

### side

- END_POSITION_X → LATE_RESOLVE_BY_4H [resistance]: -1.35 pp, N=682
- END_POSITION_X → LATE_RESOLVE_BY_4H [support]: -3.22 pp, N=519
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [resistance]: +20.02 pp, N=574
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [support]: +21.06 pp, N=460
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [resistance]: +0.11 pp, N=682
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [support]: +2.33 pp, N=519
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [resistance]: -0.63 pp, N=574
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [support]: +2.95 pp, N=460
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [resistance]: -1.69 pp, N=682
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [support]: -1.04 pp, N=519
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [resistance]: +1.40 pp, N=574
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [support]: +5.45 pp, N=460
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [resistance]: +0.22 pp, N=682
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [support]: -1.16 pp, N=519
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [resistance]: -1.96 pp, N=574
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [support]: +4.94 pp, N=460
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [resistance]: +2.24 pp, N=680
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [support]: -1.84 pp, N=518
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [resistance]: -1.41 pp, N=572
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [support]: +1.63 pp, N=459

## Leave-one-year-out

- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_2020Q4]: -2.04 pp, N=1117
- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_2021]: -2.64 pp, N=931
- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_2022]: -0.43 pp, N=904
- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_2023]: -3.31 pp, N=956
- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_2024]: -2.11 pp, N=896
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_2020Q4]: +20.60 pp, N=958
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_2021]: +18.51 pp, N=804
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_2022]: +19.21 pp, N=786
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_2023]: +23.67 pp, N=822
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_2024]: +19.87 pp, N=766
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_2020Q4]: +1.60 pp, N=1117
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_2021]: +0.82 pp, N=931
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_2022]: +0.84 pp, N=904
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_2023]: +0.36 pp, N=956
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_2024]: +1.33 pp, N=896
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2020Q4]: +1.08 pp, N=958
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2021]: +0.76 pp, N=804
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2022]: +0.14 pp, N=786
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2023]: +0.28 pp, N=822
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2024]: +1.57 pp, N=766
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2020Q4]: -0.88 pp, N=1117
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2021]: -1.67 pp, N=931
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2022]: -1.41 pp, N=904
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2023]: -0.69 pp, N=956
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2024]: -1.80 pp, N=896
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2020Q4]: +3.39 pp, N=958
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2021]: +3.45 pp, N=804
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2022]: +2.83 pp, N=786
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2023]: +1.94 pp, N=822
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2024]: +3.33 pp, N=766
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_2020Q4]: -0.15 pp, N=1117
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_2021]: -0.44 pp, N=931
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_2022]: -0.57 pp, N=904
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_2023]: +0.96 pp, N=956
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_2024]: -0.96 pp, N=896
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_2020Q4]: +1.97 pp, N=958
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_2021]: +0.82 pp, N=804
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_2022]: +0.82 pp, N=786
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_2023]: -0.11 pp, N=822
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_2024]: +0.86 pp, N=766
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2020Q4]: +0.04 pp, N=1114
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2021]: +0.50 pp, N=929
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2022]: +1.39 pp, N=902
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2023]: +1.92 pp, N=953
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_2024]: +0.46 pp, N=894
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2020Q4]: +0.58 pp, N=955
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2021]: -1.55 pp, N=802
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2022]: -0.17 pp, N=784
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2023]: -0.75 pp, N=819
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_2024]: -0.02 pp, N=764

## Leave-one-family-out

- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_DAY]: n/a, N=130, dropped share 0.8918
- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_WEEK]: -2.17 pp, N=1081, dropped share 0.0999
- END_POSITION_X → LATE_RESOLVE_BY_4H [omit_MONTH]: -2.06 pp, N=1191, dropped share 0.0083
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=122, dropped share 0.8820
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_WEEK]: +20.21 pp, N=921, dropped share 0.1093
- END_POSITION_X → LATE_BREAK_GIVEN_RESOLVED [omit_MONTH]: +20.29 pp, N=1025, dropped share 0.0087
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_DAY]: n/a, N=130, dropped share 0.8918
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_WEEK]: +1.11 pp, N=1081, dropped share 0.0999
- RELATIVE_ACTIVITY_15M → LATE_RESOLVE_BY_4H [omit_MONTH]: +1.11 pp, N=1191, dropped share 0.0083
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=122, dropped share 0.8820
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_WEEK]: +0.03 pp, N=921, dropped share 0.1093
- RELATIVE_ACTIVITY_15M → LATE_BREAK_GIVEN_RESOLVED [omit_MONTH]: +0.44 pp, N=1025, dropped share 0.0087
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_DAY]: n/a, N=130, dropped share 0.8918
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_WEEK]: -1.34 pp, N=1081, dropped share 0.0999
- ORIENTED_TAKER_REACTION_15M → LATE_RESOLVE_BY_4H [omit_MONTH]: -1.29 pp, N=1191, dropped share 0.0083
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=122, dropped share 0.8820
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_WEEK]: +2.83 pp, N=921, dropped share 0.1093
- ORIENTED_TAKER_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_MONTH]: +3.09 pp, N=1025, dropped share 0.0087
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_DAY]: n/a, N=130, dropped share 0.8918
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_WEEK]: -0.11 pp, N=1081, dropped share 0.0999
- TAKER_CHANGE_VS_PRE → LATE_RESOLVE_BY_4H [omit_MONTH]: -0.20 pp, N=1191, dropped share 0.0083
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=122, dropped share 0.8820
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_WEEK]: +1.80 pp, N=921, dropped share 0.1093
- TAKER_CHANGE_VS_PRE → LATE_BREAK_GIVEN_RESOLVED [omit_MONTH]: +0.91 pp, N=1025, dropped share 0.0087
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_DAY]: n/a, N=128, dropped share 0.8932
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_WEEK]: +1.25 pp, N=1080, dropped share 0.0985
- OI_REACTION_15M → LATE_RESOLVE_BY_4H [omit_MONTH]: +0.98 pp, N=1188, dropped share 0.0083
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_DAY]: n/a, N=120, dropped share 0.8836
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_WEEK]: +0.31 pp, N=920, dropped share 0.1077
- OI_REACTION_15M → LATE_BREAK_GIVEN_RESOLVED [omit_MONTH]: -0.16 pp, N=1022, dropped share 0.0087

## Routing

Routing `STRUCTURE_PRESENT_BUT_UNSTABLE`.
LEVEL_POST_TOUCH_REACTION_CANDIDATE count: 0.
GENERIC_POST_TOUCH_STATE_CANDIDATE count: 0.
SUCCESSOR_CANDIDATE = `NONE`.
PRODUCT_INTEGRATION_CANDIDATE = False.
Claim ceiling L2. A historical association is not a current probability.
End position is the close at D in units of the barrier distance. It is not acceptance, a failed break, or a confirmed breakout.
No trade call and no product change.

Exploratory successor ideas, not estimated:

- EXPLORATORY_SUCCESSOR_IDEA: RELATIVE_ACTIVITY_15M vs LATE_RESOLVE_BY_4H is u_shape across frozen tertiles. No threshold, acceptance flag, or extra window was fit.
- EXPLORATORY_SUCCESSOR_IDEA: OI_REACTION_15M vs LATE_BREAK_GIVEN_RESOLVED is u_shape across frozen tertiles. No threshold, acceptance flag, or extra window was fit.

## Reporting note

Leave-one-family-out omitting DAY did not return a coefficient. The complement has N=130 for late resolve and N=122 for late break, under the full nuisance design. The frozen rule treats a missing coefficient on a complement with N≥30 as a family failure, so every primary cell lists `family`. That is the only failed clause on `END_POSITION_X` → `LATE_BREAK_GIVEN_RESOLVED` (+20.31 pp, 95% +17.20..+23.46, q=0.0000, N=1034). The DAY slice is +20.20 pp (N=912) and the WEEK slice is +19.45 pp (N=113). MONTH has N=9. Every year and every leave-one-year-out keeps the positive sign, and both sides are about +20 pp. The cell is a statistical hit and the conjunction does not pass, so the frozen route remains `STRUCTURE_PRESENT_BUT_UNSTABLE`. It is not a named candidate. No coefficient was recomputed and the evaluator was not rerun.

Pseudo and stacked intervals were not formed. Valid week-cluster draws on those fits were 1241–1747 of 2000, below the frozen 90 percent line. Point estimates are shown. The pseudo end-position → late BREAK point is +30.13 pp (N=413). It is not a generic candidate, because the real conjunction did not pass. The ten primary intervals are complete.
