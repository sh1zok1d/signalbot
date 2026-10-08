# FROZEN_HOUR_EQUAL_WIDTH_V1 — one historical outcome read

- Unit: `FROZEN_HOUR_EQUAL_WIDTH_V1`
- Read at: `2026-10-08T22:02:27Z`
- Evaluator commit: `c51e7da046c785861877de9b5aa0ebea5a9a86a5`
- Code digest: `846c784c9bb09f6c236cc3ef31407301235cf03984e97fed9236e14477037303`
- Design commit: `5c3f6e6bdc4df8ef3ce7266b318253c42dada4a3`
- Design SHA256: `abb3283046277201278f2e952196e870e324009d86e39324d4fdca530b4cfef7`
- Support census HEAD: `3b02de8380064aa2ce3fe384e86899e08d2b3778`
- Surface: `DH1_BINANCE_SPOT_BTCUSDT_5M_V0` `2017-09-01` to `2020-01-01` exclusive, months `2017-09`..`2019-12`
- Route: `NO_WIDTH_HELD_RESOLUTION_DIFFERENCE`
- Seeds: UTC_00 `20261031`, UTC_12 `20261102`, B = 2000

On this surface, after holding linear width equal, the frozen 3 pp and interval rule did not detect a resolution difference. That is compatible with the 2020–2024 perpetual contrast having depended on width and volatility-regime coupling. It does not prove that account, because this read also changes the era and the instrument. It does not say that width completely explains +9.48 pp. UTC_12 does not clear and is not adopted.

UTC_12 does not clear and is not adopted.

## UTC_00

- N: 817
- ISO weeks: 123
- real resolution rate: 0.925337
- pseudo resolution rate: 0.922889
- paired delta: 0.002448
- 95% interval: [-0.018029932228915663, 0.02237284271737255]
- interpretable: true
- clears: false
- immediate real rate: 0.265606
- immediate pseudo rate: 0.241126
- neither-immediate N: 488 (DESCRIPTIVE_NOT_A_CANDIDATE)
- neither-immediate paired mean: 0.000000

## UTC_12

- N: 833
- ISO weeks: 123
- real resolution rate: 0.955582
- pseudo resolution rate: 0.948379
- paired delta: 0.007203
- 95% interval: [-0.006009796179302046, 0.021377672209026127]
- interpretable: true
- clears: false
- immediate real rate: 0.266507
- immediate pseudo rate: 0.273709
- neither-immediate N: 483 (DESCRIPTIVE_NOT_A_CANDIDATE)
- neither-immediate paired mean: 0.008282

No year slice, extension-first split, occupancy, excursion, or volatility endpoint is in this file.
No product change and no successor was started.
