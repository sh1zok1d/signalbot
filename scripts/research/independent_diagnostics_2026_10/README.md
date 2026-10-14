# Independent diagnostics (2026-10-14)

Supporting computations for `docs/PULSY_INDEPENDENT_FORECAST_INVESTIGATION_2026-10-14.md`.
They are diagnostics for the investigation, not research units under the evaluation
contract: no preregistration, no claim decision, no product change. Nothing here is
imported by the bot.

## Data

All inputs are public Binance Vision archives, downloaded at run time and never
committed (`artifacts/` is gitignored):

- USD-M `BTCUSDT` 5m klines, monthly objects 2020-01 .. 2026-07;
- USD-M `BTCUSDT` funding rate, monthly objects 2020-01 .. 2026-07;
- USD-M `BTCUSDT` daily `metrics` objects (open interest, long/short account ratios,
  taker long/short ratio) 2021-12-01 .. 2026-07-31.

The E1-RUN-001 holdout `[2026-08-16, 2026-08-25T17:20Z)` was never requested: no object
of August 2026 or later is downloaded. The last forward window used ends on
2026-08-01 (24h horizon from the last July anchor).

Exposure note: the 2025-01 .. 2026-07 Binance BTC surface was read for walk-forward
direction and volatility scores and for a time-disjoint check of DH3-P3 (crowd
positioning). The ledger entry in `docs/RESEARCH_LEDGER.md` records this.

## Run

```bash
export DIAG_DATA_DIR=artifacts/independent_diagnostics_2026_10
mkdir -p "$DIAG_DATA_DIR" && cd "$DIAG_DATA_DIR"
bash /path/to/download_klines_funding.sh      # writes klines5m/ and funding/
bash /path/to/download_metrics.sh             # writes metrics/
cd -
pip install scipy scikit-learn                # pandas/numpy are already required
python scripts/research/independent_diagnostics_2026_10/build.py      # btc5m.pkl
python scripts/research/independent_diagnostics_2026_10/features.py   # feat5m.pkl
python scripts/research/independent_diagnostics_2026_10/run_direction.py
python scripts/research/independent_diagnostics_2026_10/run_ablation.py
python scripts/research/independent_diagnostics_2026_10/run_misc.py
python scripts/research/independent_diagnostics_2026_10/run_econ.py
python scripts/research/independent_diagnostics_2026_10/run_p3.py
```

The scripts resolve the data directory from `DIAG_DATA_DIR`; the download scripts
write into the current directory.

## What each script does

| Script | Question |
|---|---|
| `run_direction.py` | Walk-forward by year (train < Y, test = Y, 2022..2026H1): AUC, log-loss skill and after-cost value of the sign of the next 1h / 4h / 24h return from 29 price, range, taker, volume, funding and clock features (logistic regression and gradient boosting); out-of-sample R² of the next-window realised volatility and range against the train mean and against persistence |
| `run_ablation.py` | Which feature groups carry the directional information (only / drop) and whether the skill concentrates in states |
| `run_misc.py` | Minimum detectable effect table, autocorrelation of non-overlapping returns by year, logistic coefficients, univariate AUCs |
| `run_econ.py` | After-cost value of the 4h direction model by confidence and by volatility / move-size tercile (tercile edges from training years) |
| `run_p3.py` | Time-disjoint check of the DH3-P3 object (top-quintile long/short account ratio → up-first within 4h) on 2025-01 .. 2026-07 |

Outputs of the 2026-10-14 run are in `results/`.
