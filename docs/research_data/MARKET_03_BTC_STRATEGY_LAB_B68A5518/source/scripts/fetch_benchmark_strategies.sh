#!/usr/bin/env bash
# Clones the public strategy collections used in the benchmark.
# They are NOT redistributed here - each has its own license and author.
set -euo pipefail

DEST="user_data/strategies_benchmark"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST"

git clone -q --depth 1 https://github.com/freqtrade/freqtrade-strategies.git "$TMP/official"
git clone -q --depth 1 https://github.com/paulcpk/freqtrade-strategies-that-work.git "$TMP/paulcpk"

cp "$TMP"/official/user_data/strategies/*.py            "$DEST/" 2>/dev/null || true
cp "$TMP"/official/user_data/strategies/berlinguyinca/*.py "$DEST/" 2>/dev/null || true
cp "$TMP"/paulcpk/*.py                                   "$DEST/" 2>/dev/null || true

# 1m strategies need 1m data we do not download; futures/lookahead_bias are excluded
# from the benchmark on purpose (see README).
grep -lE "^\s*timeframe\s*=\s*.1m." "$DEST"/*.py 2>/dev/null | xargs -r rm

echo "Fetched $(ls "$DEST"/*.py | wc -l) strategies into $DEST"
