# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 — support census

Row and week counts only. No probability was fit. No Brier score, log loss, AUROC, or coefficient was computed.

Training admission after amendment A1: `T + 12 * 300000 <= block_start`.

Zero-return rule: `ZERO_RETURN_EXCLUDED`.

| segment | feature rows | exact zeros dropped | labeled | 15m test rows | 15m test weeks | hourly test rows |
|---|---:|---:|---:|---:|---:|---:|
| BITMEX_2016_2019 | 127303 | 1320 | 125983 | 113210 | 171 | 28323 |
| BINANCE_2020_2024 | 175372 | 63 | 175309 | 162084 | 242 | 40523 |
| BINANCE_2025_2026 | 61016 | 17 | 60999 | 60999 | 92 | 15252 |

Train-row change versus the pre-A1 rule `T < block_start`. Week identity is the ISO week of each test block.

| segment | cadence | test weeks | test rows changed | first n_train before | first n_train after | max train-row delta |
|---|---|---:|---|---:|---:|---:|
| BITMEX_2016_2019 | primary_15m | 171 -> 171 | no | 12773 | 12770 | 3 |
| BITMEX_2016_2019 | secondary_hourly | 171 -> 171 | no | 3187 | 3187 | 0 |
| BINANCE_2020_2024 | primary_15m | 242 -> 242 | no | 13225 | 13222 | 3 |
| BINANCE_2020_2024 | secondary_hourly | 242 -> 242 | no | 3307 | 3307 | 0 |
| BINANCE_2025_2026 | primary_15m | 92 -> 92 | no | 175120 | 175117 | 3 |
| BINANCE_2025_2026 | secondary_hourly | 92 -> 92 | no | 43782 | 43782 | 0 |

