#!/usr/bin/env bash
# Downloads all OHLCV data used by the benchmark and the strategy.
set -euo pipefail
PY="${PY:-.venv/bin/freqtrade}"

"$PY" download-data -c config.json --timerange 20180101- \
  -t 5m 15m 1h 4h 12h 1d --data-format-ohlcv feather

.venv/bin/python research/fetch_onchain.py
