# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_A2 — support census

Amendment A2: only the 2025–2026 source changes (RP4H Unit B canonical surface; `[2026-08-02, 2026-08-26)` never requested).

Row and week counts only. No probability was fit. No Brier score, log loss, AUROC, or coefficient was computed.

Training admission after amendment A1: `T + 12 * 300000 <= block_start`.

Zero-return rule: `ZERO_RETURN_EXCLUDED`.

| segment | feature rows | exact zeros dropped | labeled | 15m test rows | 15m test weeks | hourly test rows |
|---|---:|---:|---:|---:|---:|---:|
| BITMEX_2016_2019 | 127303 | 1320 | 125983 | 113210 | 171 | 28323 |
| BINANCE_2020_2024 | 175372 | 63 | 175309 | 162084 | 242 | 40523 |
| BINANCE_2025_2026 | 59672 | 15 | 59657 | 59657 | 90 | 14916 |

Against Cursor's A1 census, whose 2025–2026 file includes `[2026-08-02, 2026-08-16)`. Counts only.

| segment | labeled A1 -> A2 | 15m test rows A1 -> A2 | 15m test weeks A1 -> A2 | 15m schedule identical | hourly schedule identical |
|---|---:|---:|---:|---|---|
| BITMEX_2016_2019 | 125983 -> 125983 | 113210 -> 113210 | 171 -> 171 | yes | yes |
| BINANCE_2020_2024 | 175309 -> 175309 | 162084 -> 162084 | 242 -> 242 | yes | yes |
| BINANCE_2025_2026 | 60999 -> 59657 | 60999 -> 59657 | 92 -> 90 | no | no |

