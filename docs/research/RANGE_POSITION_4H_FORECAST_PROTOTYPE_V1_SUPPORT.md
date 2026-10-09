# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 — support census

Row and week counts only. No probability was fit. No Brier score, log loss, AUROC, or coefficient was computed.

Zero-return rule: `ZERO_RETURN_EXCLUDED`.

| segment | feature rows | exact zeros dropped | labeled | 15m test rows | 15m test weeks | hourly test rows |
|---|---:|---:|---:|---:|---:|---:|
| BITMEX_2016_2019 | 127303 | 1320 | 125983 | 113210 | 171 | 28323 |
| BINANCE_2020_2024 | 175372 | 63 | 175309 | 162084 | 242 | 40523 |
| BINANCE_2025_2026 | 61016 | 17 | 60999 | 60999 | 92 | 15252 |

