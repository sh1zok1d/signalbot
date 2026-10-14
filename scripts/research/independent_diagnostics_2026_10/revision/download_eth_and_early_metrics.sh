#!/bin/bash
cd "$(dirname "$0")"
for y in 2020 2021 2022 2023 2024 2025 2026; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  if [ "$y" = "2026" ] && [ "$m" -gt 7 ]; then continue; fi
  f=ETHUSDT-5m-$y-$m.zip; [ -s eth5m/$f ] || curl -s -f -o eth5m/$f https://data.binance.vision/data/futures/um/monthly/klines/ETHUSDT/5m/$f || echo "miss $f"
done; done
d=2020-09-01; while [ "$d" != "2021-12-01" ]; do f=BTCUSDT-metrics-$d.zip; [ -s metrics_early/$f ] || curl -s -f -o metrics_early/$f https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/$f || echo "miss $f"; d=$(date -I -d "$d + 1 day"); done
echo DONE; ls eth5m | wc -l; ls metrics_early | wc -l
