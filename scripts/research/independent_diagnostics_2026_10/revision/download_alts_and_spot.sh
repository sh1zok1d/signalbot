#!/bin/bash
cd "$(dirname "$0")"
for s in SOLUSDT BNBUSDT XRPUSDT DOGEUSDT; do mkdir -p ${s}_5m
 for y in 2020 2021 2022 2023 2024 2025 2026; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  if [ "$y" = "2026" ] && [ "$m" -gt 7 ]; then continue; fi
  f=$s-5m-$y-$m.zip; [ -s ${s}_5m/$f ] || curl -s -f -o ${s}_5m/$f https://data.binance.vision/data/futures/um/monthly/klines/$s/5m/$f || echo "miss $f"
 done; done; done
mkdir -p spot_btc_5m
for y in 2017 2018 2019; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  if [ "$y" = "2017" ] && [ "$m" -lt 8 ]; then continue; fi
  f=BTCUSDT-5m-$y-$m.zip; [ -s spot_btc_5m/$f ] || curl -s -f -o spot_btc_5m/$f https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/5m/$f || echo "miss $f"
done; done
echo DONE; for s in SOLUSDT BNBUSDT XRPUSDT DOGEUSDT; do ls ${s}_5m | wc -l; done; ls spot_btc_5m | wc -l
