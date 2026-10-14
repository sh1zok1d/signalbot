#!/bin/bash
# daily metrics objects (OI, long/short ratios, taker ratio), 2021-12-01 .. 2026-07-31
d=2021-12-01
end=2026-07-31
while [ "$d" != "$(date -I -d "$end + 1 day")" ]; do
  f=BTCUSDT-metrics-$d.zip
  [ -s metrics/$f ] || curl -s -f -o metrics/$f https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/$f || echo "miss $f"
  d=$(date -I -d "$d + 1 day")
done
echo DONE; ls metrics | wc -l
