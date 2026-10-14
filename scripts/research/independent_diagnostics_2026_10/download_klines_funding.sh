#!/bin/bash
# download monthly 5m klines and funding for BTCUSDT USD-M, 2020-01 .. 2026-07 (E1 holdout and later months never requested)
for y in 2020 2021 2022 2023 2024 2025 2026; do
  for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
    if [ "$y" = "2026" ] && [ "$m" -gt 7 ]; then continue; fi
    f=BTCUSDT-5m-$y-$m.zip
    [ -s klines5m/$f ] || curl -s -f -o klines5m/$f https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/$f || echo "miss $f"
    g=BTCUSDT-fundingRate-$y-$m.zip
    [ -s funding/$g ] || curl -s -f -o funding/$g https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/$g || echo "miss $g"
  done
done
echo DONE; ls klines5m | wc -l; ls funding | wc -l; du -sh klines5m funding
