# Pre-3b data checks C1, C2 — prepared, not run

**Status:** `RUN_1_DONE / V2_PREPARED` (v1 2026-10-09, run once on production by the owner; v2 2026-10-09 changes C1b's matching and C2's OKX premise after run 1, see «Run 1 results»). The owner runs both blocks on the VPS **after step 3a is deployed** and before 3b. Both are read-only on production. Each prints `PASS` / `FAIL` lines; the owner sends the output to the architect.

- **C1** checks the scale of OKX liquidation sizes (`ctVal`, D1).
- **C2** checks how the beta reads the rows written before D1: the D2 read-time correction.

**D1 deploy instant:** `2026-10-08 14:59Z` (collector restart with the fixed mapping). Rows after it carry `mapping_version = 2`. Rows before it carry `NULL`: Bybit sides swapped, no OKX rows (`storage/schema.sql`, `beta/liq_mapping.py`).

## How the blocks run (as in `docs/BETA_AUDIT_DEIDENTIFY_V1.md`)
- **Pasting.** The owner pastes the whole block, nothing else.
  - Each block runs in its own shell: `bash -c "$(cat <<'C1' … C1` + newline + `)"`. The quoted delimiter means nothing is expanded at paste time.
  - `set -euo pipefail` lives in that child shell, so an error ends the block, not the SSH session.
  - The block's stdin is `/dev/null`, so nothing inside reads the terminal or swallows lines pasted after it.
- **Settings.** Everything comes from `/opt/signalbot/.env`, read in a subshell. The defaults are those of `deploy/backup.sh` and `docker-compose.yml`: container `btcbot_timescaledb`, `POSTGRES_DB` / `POSTGRES_USER` = `btcbot`. Nothing secret is printed.
- **Production is read-only.**
  - Every `psql` runs through `docker exec -e PGOPTIONS='-c default_transaction_read_only=on'`.
  - C2's Python part connects with the same setting (`server_settings`).
  - Neither block writes a table, a temporary table or a file outside its own `mktemp -d` directory, which is removed on exit.
- **Symbol.** `BTCUSDT`, the canonical symbol stored in every row (`config/config.yaml`).

## Run 1 results (production, owner, 2026-10-09)
The full record is in `docs/BETA_RELEASE_LOG_V1.md` (step 3a, pre-3b checks). In short:
- **C1.**
  - `C1a_*` and `C1b_ctval` (0.01) passed.
  - `C1b_match` failed under v1's ±1 s rule: 82 matched, 51 equal.
  - Re-run on the exact ms plus price: 51 keys, 50 equal. The one difference is a count, not a scale. At 04:01:48.625Z, px 82455.2, REST holds two orders (0.09 and 2.94 contracts) and the database one row, `qty` 0.0294 = 2.94 × 0.01.
  - **C1 is closed.** v2's rule below (stored ⊆ REST, multiset) passes on that data.
- **C2.**
  - `C2_rows_swapped`, `C2_tape_swapped`, `C2_okx_not_measured` and `C2_mark_side` passed.
  - `C2_okx_no_rows` and `C2_window_old_only` failed. 6 OKX rows fall in the window; the first event is at 14:04:48Z.
  - All 6 carry `mapping_version = 2` and were processed after the 14:59:21Z restart, 57–71 min after their event time.
  - v2 drops that premise (see C2). The impact of late OKX events on the tape is in `docs/BETA_OKX_LATE_ARRIVAL_IMPACT.md`.

## C1 — OKX liquidation sizes (ctVal)
**What it shows.**
- **(a)** For each venue, over the rows after `2026-10-08 14:59Z`: N, then p10 / median / p90 of `qty` (BTC) and of `notional` (USD).
- **(a)** The extreme values of `notional / (price × qty)`, which must be 1 within rounding.
- **(b)** An independent reference:
  - OKX's own REST list of recent filled BTC-USDT-SWAP liquidations;
  - `ctVal`, fetched in the same block from the instruments endpoint.
- **(b) Matching (v2, after run 1).** A key is OKX's own event time, to the exact millisecond, plus the price (`bkPx`). The collector stores both as received.
  - At each key that appears in both the REST list and the database, the stored sizes must be a sub-multiset of the REST sizes × ctVal: every stored row equals a **distinct** REST order of the same size.
  - REST may hold more orders at a key than the database. The WS channel is a subset of liquidations.
  - For up to 10 keys the block shows the stored sizes beside the REST sizes.
  - **Why v1's rule was replaced.** v1 matched ±1 s and the nearest row. That paired REST-only orders with a neighbouring WS row at the same price: 82 matched, 51 equal on production.

**PASS lines.**

| Line | PASS when |
|---|---|
| `C1a_notional_identity` | every venue's `notional / (price × qty)` is within 1e-9 of 1 |
| `C1a_okx_rows` | at least one OKX row exists after D1 |
| `C1a_okx_scale` | OKX's median notional lies between 0.1× and 10× the median of Binance's and Bybit's medians. A wrong ctVal (1 or 0.0001 instead of 0.01) gives a 100× gap. |
| `C1b_ctval` | `ctVal` from the instruments endpoint is `0.01` |
| `C1b_match` | at least 5 keys (exact ms + price) are shared, and at every one the stored sizes are covered by distinct REST orders of the same size (rounded to 1e-8 BTC) |
| `INFO C1b_unkeyed` | (not judged) stored OKX rows inside the REST list's time span that have no REST order at the same ms and price |

- **Not enough matches.** If fewer than 5 keys are shared, `C1b_match` prints `INCONCLUSIVE`, not PASS. Run C1 again later.
  - OKX's WebSocket channel pushes a subset of liquidations, not all of them. Its docs say it "doesn't represent the total number of liquidations".
  - The REST list holds only the latest 100 orders.

```bash
bash -c "$(cat <<'C1'
# ---- C1: OKX liquidation sizes (ctVal). Read-only on production; writes only its own /tmp directory.
set -euo pipefail
exec </dev/null   # nothing inside reads the terminal or what is pasted after the block
eval "$( (set -a; . /opt/signalbot/.env; set +a
          printf 'C=%q\nDB=%q\nU=%q\n' "${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}" \
                 "${POSTGRES_DB:-btcbot}" "${POSTGRES_USER:-btcbot}") )"
PROD() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' "$C" psql -X -U "$U" -v ON_ERROR_STOP=1 -d "$DB" "$@"; }
WORK=$(mktemp -d /tmp/pre3b_c1.XXXXXXXX)
trap 'rm -rf "$WORK"' EXIT
echo "container=$C db=$DB user=$U"
# (a) per venue, rows after the D1 deploy
PROD -P pager=off <<'SQL'
\echo '--- C1a: per venue after 2026-10-08 14:59Z (qty in BTC, notional in USD)'
SELECT exchange, count(*) AS n,
       round(percentile_cont(0.1) WITHIN GROUP (ORDER BY qty)::numeric, 4)      AS qty_p10,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY qty)::numeric, 4)      AS qty_p50,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY qty)::numeric, 4)      AS qty_p90,
       round(percentile_cont(0.1) WITHIN GROUP (ORDER BY notional)::numeric, 0) AS usd_p10,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY notional)::numeric, 0) AS usd_p50,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY notional)::numeric, 0) AS usd_p90,
       min(notional / NULLIF(price * qty, 0)) AS ratio_min,
       max(notional / NULLIF(price * qty, 0)) AS ratio_max,
       count(*) FILTER (WHERE mapping_version IS NULL) AS n_unmapped
FROM liquidations
WHERE symbol = 'BTCUSDT' AND ts >= '2026-10-08 14:59:00+00'
GROUP BY exchange ORDER BY exchange;
WITH v AS (
  SELECT exchange, count(*) AS n, percentile_cont(0.5) WITHIN GROUP (ORDER BY notional) AS p50,
         max(abs(notional / NULLIF(price * qty, 0) - 1)) AS dev
  FROM liquidations WHERE symbol = 'BTCUSDT' AND ts >= '2026-10-08 14:59:00+00' GROUP BY exchange),
ref AS (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY p50) AS p50 FROM v WHERE exchange IN ('binance', 'bybit')),
okx AS (SELECT n, p50 FROM v WHERE exchange = 'okx')
SELECT CASE WHEN (SELECT bool_and(dev IS NOT NULL AND dev < 1e-9) FROM v) THEN 'PASS' ELSE 'FAIL' END
       || ' C1a_notional_identity: max |notional/(price*qty) - 1| = ' || coalesce((SELECT max(dev)::text FROM v), 'no rows') AS result
UNION ALL
SELECT CASE WHEN coalesce((SELECT n FROM okx), 0) > 0 THEN 'PASS' ELSE 'FAIL' END
       || ' C1a_okx_rows: ' || coalesce((SELECT n FROM okx), 0) || ' OKX rows after D1'
UNION ALL
SELECT CASE WHEN (SELECT p50 FROM okx) / NULLIF((SELECT p50 FROM ref), 0) BETWEEN 0.1 AND 10 THEN 'PASS' ELSE 'FAIL' END
       || ' C1a_okx_scale: OKX median notional / median of Binance and Bybit medians = '
       || coalesce(round(((SELECT p50 FROM okx) / NULLIF((SELECT p50 FROM ref), 0))::numeric, 3)::text, 'n/a') AS result;
SQL
# (b) the independent reference: OKX's REST list of filled liquidations and ctVal, fetched now
curl -fsS --max-time 20 'https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT&state=filled&limit=100' > "$WORK/liq.json"
curl -fsS --max-time 20 'https://www.okx.com/api/v5/public/instruments?instType=SWAP&instId=BTC-USDT-SWAP' > "$WORK/inst.json"
python3 - "$WORK" <<'PY' > "$WORK/ref.sql"
import json, sys
from decimal import Decimal
work = sys.argv[1]
inst = json.load(open(f"{work}/inst.json"))
liq = json.load(open(f"{work}/liq.json"))
assert inst.get("code") == "0" and inst["data"], "instruments: unexpected answer"
assert liq.get("code") == "0", "liquidation-orders: unexpected answer"
ct = Decimal(inst["data"][0]["ctVal"])
rows = [(int(d["ts"]), Decimal(d["bkPx"]), Decimal(d["sz"]))
        for g in liq["data"] if g.get("instId") == "BTC-USDT-SWAP" for d in g.get("details", [])]
vals = ",".join(f"({ts},{px},{sz})" for ts, px, sz in rows) or "(0,0,0)"
# keyed on OKX's own event time (exact ms, as the collector stores it) and the price; sizes compared as multisets
cte = f"""WITH ref(ts_ms, bkpx, sz) AS (VALUES {vals}),
r AS (SELECT ts_ms, round(bkpx, 8) AS px, round(sz * :ctval, 8) AS q, count(*) AS n_rest FROM ref GROUP BY 1, 2, 3),
span AS (SELECT to_timestamp(min(ts_ms) / 1000.0) - interval '1 second' AS t0,
                to_timestamp(max(ts_ms) / 1000.0) + interval '1 second' AS t1 FROM ref),
s AS (SELECT round(extract(epoch FROM l.ts) * 1000)::bigint AS ts_ms, round(l.price::numeric, 8) AS px,
             round(l.qty::numeric, 8) AS q, count(*) AS n_db
      FROM liquidations l, span
      WHERE l.exchange = 'okx' AND l.symbol = 'BTCUSDT' AND l.ts BETWEEN span.t0 AND span.t1 GROUP BY 1, 2, 3),
sk AS (SELECT s.* FROM s WHERE EXISTS (SELECT 1 FROM r WHERE r.ts_ms = s.ts_ms AND r.px = s.px)),
cmp AS (SELECT sk.ts_ms, sk.px, sk.q, sk.n_db, coalesce(r.n_rest, 0) AS n_rest
        FROM sk LEFT JOIN r USING (ts_ms, px, q))"""
print(f"\\set ctval {ct}")
print(f"\\echo '--- C1b: ctVal from /api/v5/public/instruments = {ct}; {len(rows)} REST orders fetched'")
print(f"""\\echo '--- stored OKX rows on a REST key (exact ms + price): stored qty against the REST sizes x ctVal at that key'
{cte}
SELECT to_timestamp(k.ts_ms / 1000.0) AS event_ts, k.px AS price,
       (SELECT string_agg(q || CASE WHEN n_db > 1 THEN ' x' || n_db ELSE '' END, ', ' ORDER BY q) FROM cmp c
        WHERE c.ts_ms = k.ts_ms AND c.px = k.px) AS stored_qty,
       (SELECT string_agg(q || CASE WHEN n_rest > 1 THEN ' x' || n_rest ELSE '' END, ', ' ORDER BY q) FROM r
        WHERE r.ts_ms = k.ts_ms AND r.px = k.px) AS rest_sz_x_ctval,
       bool_and(k.n_db <= k.n_rest) AS covered
FROM cmp k GROUP BY k.ts_ms, k.px ORDER BY k.ts_ms DESC LIMIT 10;
{cte}
SELECT CASE WHEN :ctval = 0.01 THEN 'PASS' ELSE 'FAIL' END || ' C1b_ctval: ctVal = ' || :ctval AS result
UNION ALL
SELECT CASE WHEN count(DISTINCT (ts_ms, px)) < 5 THEN 'INCONCLUSIVE'
            WHEN bool_and(n_db <= n_rest) THEN 'PASS' ELSE 'FAIL' END
       || ' C1b_match: ' || count(DISTINCT (ts_ms, px)) || ' keys (exact ms + price), '
       || coalesce(sum(n_db), 0) || ' stored rows, ' || coalesce(sum(least(n_db, n_rest)), 0)
       || ' matched to a distinct REST order of the same size'
FROM cmp
UNION ALL
SELECT 'INFO C1b_unkeyed: ' || coalesce(sum(n_db), 0)
       || ' stored OKX rows inside the REST time span with no REST order at the same ms and price'
FROM s WHERE NOT EXISTS (SELECT 1 FROM r WHERE r.ts_ms = s.ts_ms AND r.px = s.px);
""")
PY
PROD -P pager=off < "$WORK/ref.sql"
C1
)"
```

## C2 — rows written before D1, read through D2
**The window.** The 24 h ending at the last 5-minute boundary before the last pre-D1 Bybit row (`mapping_version IS NULL`), and never after `2026-10-08 14:59Z`.
- Every bucket in it holds only old Bybit rows: none is a restart bucket (`MIXED`).
- It ends before the first OKX heartbeat.
- **v2 (after run 1).** The window can no longer be "before the first OKX row". On production, 6 OKX events from before the 14:59:21Z restart arrived 57–71 min late, after it. Every one carries `mapping_version = 2`.
  - The window cannot be based on arrival time instead. `liquidations` stores the event time (`ts`) only; there is no ingest or recorded-at column (`storage/schema.sql`). The `id` order gives the order of arrival, but no time.
  - So the «no OKX row» premise is dropped, and the test keeps what the beta must guarantee: **OKX reads None in every tape bucket of the window**.
  - That holds for two reasons:
    - The fixed collector's OKX rows move OKX's cutover (`first_new`, the earliest event `ts`) before the restart. The pre-restart buckets after it are then `NEW`, not `UNPROVEN`.
    - Those buckets have no heartbeat, so liveness reads them `NO_FEED`, which is None.
  - The late rows themselves are checked to be fixed-collector rows (`C2_okx_rows_new_only`).

The block prints the window, the cutover, the first OKX heartbeat and the deployed commit.

**What it shows.**
- **(i) Raw, as stored.**
  - Bybit long/short counts and notional, which carry the swapped sides.
  - The share of rows whose stored side agrees with the mark price. Each liquidation's bankruptcy price is compared with Bybit's mark price nearest in time (within 60 s). A liquidated long fills below mark, a liquidated short above it.
  - The same share for the post-D1 Bybit rows, as a control.
- **(ii) What the beta reads, through the beta's own readers in the deployed code** (`/opt/signalbot/.venv`, read-only connection):
  - `fetch_liquidations` gives the raw rows read honestly;
  - `fetch_tape_history` gives the tape's 5-minute liquidation keys corrected by `correct_metrics` and `apply_liveness`;
  - the same tape read with the correction switched off gives raw tape values to compare against;
  - OKX tape keys for every bucket in the window.

**PASS lines.**

| Line | PASS when |
|---|---|
| `C2_window_old_only` | the window has Bybit rows, all with `mapping_version IS NULL`, and its end is at or before the first OKX heartbeat (v2: the first OKX row is no longer a bound, see below) |
| `C2_rows_swapped` | the beta's corrected long count and notional equal the raw short ones, and vice versa |
| `C2_tape_swapped` | in every tape bucket of the window, corrected `x:bybit:long…` equals raw `x:bybit:short…` and vice versa (none read as None). Also printed: the bucket states, all `OLD`. |
| `C2_okx_not_measured` | no tape bucket in the window reads a number for OKX: every one is None («не измерен»), including those where the tape stored 0 |
| `C2_okx_rows_new_only` | (v2, replaces `C2_okx_no_rows`) every OKX row in the window carries `mapping_version = 2`: no row was ever stored by the old collector. The number of such rows is printed. They are events from before the restart that arrived after it. |
| `C2_mark_side` | at least 20 pre-D1 Bybit rows are matched to a mark; the corrected side agrees with the mark for ≥ 90% of them (raw ≤ 10%); post-D1 Bybit rows agree for ≥ 90%. Fewer than 20 matched gives `INCONCLUSIVE`. |

```bash
bash -c "$(cat <<'C2'
# ---- C2: pre-D1 rows through D2's read-time correction. Read-only on production; writes nothing.
set -euo pipefail
exec </dev/null   # nothing inside reads the terminal or what is pasted after the block
cd /opt/signalbot
eval "$( (set -a; . /opt/signalbot/.env; set +a
          printf 'C=%q\nDB=%q\nU=%q\n' "${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}" \
                 "${POSTGRES_DB:-btcbot}" "${POSTGRES_USER:-btcbot}") )"
PROD() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' "$C" psql -X -U "$U" -v ON_ERROR_STOP=1 -d "$DB" "$@"; }
[ -f beta/liq_mapping.py ] || { echo "beta/liq_mapping.py is missing: step 3a (D2) is not deployed in /opt/signalbot"; exit 1; }
echo "container=$C db=$DB user=$U deployed=$(git -C /opt/signalbot rev-parse --short HEAD)"
# the window: 24 h ending at the 5m boundary before the last pre-D1 Bybit row, never after the D1 deploy
read -r W0 W1 <<<"$(PROD -At -F ' ' -c "
  WITH e AS (SELECT to_timestamp(floor(extract(epoch FROM max(ts)) / 300) * 300) AS w1
             FROM liquidations WHERE exchange = 'bybit' AND symbol = 'BTCUSDT' AND mapping_version IS NULL
               AND ts < '2026-10-08 14:59:00+00')
  SELECT to_char((w1 - interval '24 hours') AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'),
         to_char(w1 AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') FROM e")"
[ -n "${W1:-}" ] || { echo "FAIL C2_window_old_only: no pre-D1 Bybit row found"; exit 1; }
echo "window [$W0, $W1)"
# (i) raw, as stored
PROD -P pager=off -v w0="$W0" -v w1="$W1" <<'SQL'
\echo '--- C2(i): raw stored Bybit rows in the window (sides as stored, i.e. swapped before D1)'
SELECT side, count(*) AS n, round(sum(notional)::numeric, 2) AS notional, count(*) FILTER (WHERE mapping_version IS NOT NULL) AS n_mapped
FROM liquidations WHERE exchange = 'bybit' AND symbol = 'BTCUSDT' AND ts >= :'w0' AND ts < :'w1'
GROUP BY side ORDER BY side;
\echo '--- cutover and the OKX feed'
SELECT (SELECT min(ts) FROM liquidations WHERE exchange = 'bybit' AND symbol = 'BTCUSDT' AND mapping_version IS NOT NULL) AS bybit_first_new,
       (SELECT max(ts) FROM liquidations WHERE exchange = 'bybit' AND symbol = 'BTCUSDT' AND mapping_version IS NULL)     AS bybit_last_old,
       (SELECT min(ts) FROM liquidations WHERE exchange = 'okx' AND symbol = 'BTCUSDT')                                   AS okx_first_row,
       (SELECT min(ts) FROM liquidation_feed_heartbeats WHERE exchange = 'okx' AND symbol = 'BTCUSDT')                    AS okx_first_heartbeat;
WITH r AS (
  SELECT l.ts, l.side, l.price, l.mapping_version,
         (SELECT m.mark_price FROM mark_price m
          WHERE m.exchange = 'bybit' AND m.symbol = 'BTCUSDT' AND m.ts BETWEEN l.ts - interval '60 seconds' AND l.ts + interval '60 seconds'
          ORDER BY abs(extract(epoch FROM m.ts - l.ts)) LIMIT 1) AS mark
  FROM liquidations l
  WHERE l.exchange = 'bybit' AND l.symbol = 'BTCUSDT'
    AND ((l.ts >= :'w0' AND l.ts < :'w1') OR (l.ts >= '2026-10-08 14:59:00+00' AND l.mapping_version IS NOT NULL))),
s AS (
  SELECT mapping_version IS NULL AS pre_d1,
         CASE WHEN (side = 'long' AND price < mark) OR (side = 'short' AND price > mark) THEN 1.0 ELSE 0.0 END AS agree
  FROM r WHERE mark IS NOT NULL AND price <> mark)
SELECT count(*) FILTER (WHERE pre_d1) AS n_pre, coalesce(avg(agree) FILTER (WHERE pre_d1), -1) AS a_pre,
       count(*) FILTER (WHERE NOT pre_d1) AS n_post, coalesce(avg(agree) FILTER (WHERE NOT pre_d1), -1) AS a_post
FROM s \gset
\echo '--- mark-price side check (bankruptcy price vs the nearest Bybit mark within 60 s; -1 = no rows)'
SELECT 'pre-D1 window' AS bybit_rows, :n_pre AS n, round(:a_pre, 3) AS stored_side_agrees, round(1 - :a_pre, 3) AS corrected_side_agrees
UNION ALL
SELECT 'post-D1 (control)', :n_post, round(:a_post, 3), NULL;
SELECT CASE WHEN :n_pre < 20 THEN 'INCONCLUSIVE'
            WHEN 1 - :a_pre >= 0.9 AND :a_pre <= 0.1 AND :a_post >= 0.9 THEN 'PASS' ELSE 'FAIL' END
       || ' C2_mark_side: pre-D1 corrected side agrees ' || round(1 - :a_pre, 3) || ' (N=' || :n_pre
       || '), post-D1 stored side agrees ' || round(:a_post, 3) || ' (N=' || :n_post || ')' AS result;
SQL
# (ii) what the beta reads: its own readers, deployed code, read-only connection
( set -a; . /opt/signalbot/.env; set +a
  /opt/signalbot/.venv/bin/python - "$W0" "$W1" <<'PY'
import asyncio, sys
from datetime import datetime
import asyncpg
import beta.liq_mapping as lm
from beta.config import BetaConfig
from runtime.beta_cli import load_postgres_dsn
from storage.beta_v0_store import BetaConn

W0, W1 = (datetime.fromisoformat(a.replace("Z", "+00:00")) for a in sys.argv[1:3])
KEYS = {(ex, s): f"x:{ex}:{s}_liquidation_notional" for ex in ("bybit", "okx") for s in ("long", "short")}


def line(ok, name, text):
    print(("PASS" if ok else "FAIL") + f" {name}: {text}")


async def tape(c, cfg, calcs, corrected):
    saved = lm.correct_metrics, lm.apply_liveness
    if not corrected:                                   # the same reader with D2 switched off: raw tape values
        lm.correct_metrics = lambda m, *a: dict(m)
        lm.apply_liveness = lambda m, *a: dict(m)
    try:
        out = {}
        for calc in calcs:
            for b, m in await c.fetch_tape_history(symbol=cfg.symbol, market_type=cfg.market_type,
                                                   timeframe=cfg.timeframe, calculation_version=calc,
                                                   state_schema_versions=(cfg.state_schema_version,),
                                                   start=W0, end=W1):
                out[(calc, b)] = m
        return out
    finally:
        lm.correct_metrics, lm.apply_liveness = saved


async def main():
    raw = await asyncpg.connect(load_postgres_dsn(), server_settings={"default_transaction_read_only": "on"})
    try:
        c, cfg = BetaConn(raw), BetaConfig.load()
        rows = await c.fetch_liquidations(symbol=cfg.symbol, exchanges=["bybit", "okx"], start=W0, end=W1)
        stored = await raw.fetch("""SELECT side, count(*) AS n, sum(notional) AS usd FROM liquidations
                                    WHERE exchange='bybit' AND symbol=$1 AND ts >= $2 AND ts < $3 GROUP BY side""",
                                 cfg.symbol, W0, W1)
        st = {r["side"]: (r["n"], float(r["usd"])) for r in stored}
        rd = {s: (sum(1 for r in rows if r["exchange"] == "bybit" and r["side"] == s),
                  sum(float(r["notional"]) for r in rows if r["exchange"] == "bybit" and r["side"] == s))
              for s in ("long", "short")}
        print("--- C2(ii): the beta's raw-row reader (fetch_liquidations), Bybit in the window")
        for s in ("long", "short"):
            print(f"  {s:5}  stored n={st.get(s, (0, 0.0))[0]} usd={st.get(s, (0, 0.0))[1]:.2f}"
                  f"   beta reads n={rd[s][0]} usd={rd[s][1]:.2f}")
        swapped = all(rd[s][0] == st.get(o, (0, 0.0))[0] and abs(rd[s][1] - st.get(o, (0, 0.0))[1]) < 1e-6
                      for s, o in (("long", "short"), ("short", "long")))
        line(swapped and sum(v[0] for v in st.values()) > 0, "C2_rows_swapped",
             "corrected long = stored short and corrected short = stored long")
        okx_old = await raw.fetchval("""SELECT count(*) FROM liquidations WHERE exchange='okx' AND symbol=$1
                                        AND ts >= $2 AND ts < $3 AND mapping_version IS NULL""", cfg.symbol, W0, W1)
        okx_rows = [r for r in rows if r["exchange"] == "okx"]
        line(okx_old == 0, "C2_okx_rows_new_only",
             f"{okx_old} old-mapping OKX rows; {len(okx_rows)} OKX rows read in the window, all written by the fixed "
             f"collector (events before the restart that arrived after it)")

        cut = await c.fetch_liquidation_cutover(symbol=cfg.symbol)
        calcs = [r["calculation_version"] for r in await raw.fetch(
            """SELECT DISTINCT calculation_version FROM beta_state_tape WHERE symbol=$1 AND bucket_ts >= $2
               AND bucket_ts < $3 AND materialized ORDER BY 1""", cfg.symbol, W0, W1)]
        before, after = await tape(c, cfg, calcs, False), await tape(c, cfg, calcs, True)
        states = {}
        for (_, b) in after:
            for ex in ("bybit", "okx"):
                states.setdefault(ex, {}).setdefault(lm.bucket_state(cut, ex, b), 0)
                states[ex][lm.bucket_state(cut, ex, b)] += 1
        print(f"--- C2(ii): the tape reader (fetch_tape_history), {len(after)} buckets, calculation versions {calcs}")
        print(f"  bucket states: {states}")
        sums = {k: [0.0, 0.0, 0] for k in KEYS}           # raw sum, corrected sum, corrected None count
        bybit_ok, okx_numbers, okx_stored_zero = True, 0, 0
        for key, m_after in after.items():
            m_before = before[key]
            for (ex, s), k in KEYS.items():
                v0, v1 = m_before.get(k), m_after.get(k)
                sums[(ex, s)][0] += v0 or 0.0
                if v1 is None:
                    sums[(ex, s)][2] += 1
                else:
                    sums[(ex, s)][1] += v1
            o = {"long": "short", "short": "long"}
            for s in ("long", "short"):
                a, b = m_after.get(KEYS[("bybit", s)]), m_before.get(KEYS[("bybit", o[s])])
                if a is None or b is None or abs(a - b) > 1e-6:
                    bybit_ok = False
            for s in ("long", "short"):
                if m_after.get(KEYS[("okx", s)]) is not None:
                    okx_numbers += 1
                if m_before.get(KEYS[("okx", s)]) == 0:
                    okx_stored_zero += 1
        for (ex, s), (v0, v1, nn) in sums.items():
            print(f"  {ex:5} {s:5}  raw tape usd={v0:.2f}   beta reads usd={v1:.2f}  (None in {nn} buckets)")
        line(bybit_ok and len(after) > 0, "C2_tape_swapped",
             f"in all {len(after)} buckets corrected Bybit long = raw short and short = raw long")
        line(okx_numbers == 0 and len(after) > 0, "C2_okx_not_measured",
             f"OKX reads None in every bucket ({okx_numbers} numbers read; the tape stored 0 in {okx_stored_zero} "
             f"bucket-sides)")
        okx_first_row = await raw.fetchval("SELECT min(ts) FROM liquidations WHERE exchange='okx' AND symbol=$1", cfg.symbol)
        okx_first_beat = await raw.fetchval(
            "SELECT min(ts) FROM liquidation_feed_heartbeats WHERE exchange='okx' AND symbol=$1", cfg.symbol)
        mapped = await raw.fetchval("""SELECT count(*) FROM liquidations WHERE exchange='bybit' AND symbol=$1
                                       AND ts >= $2 AND ts < $3 AND mapping_version IS NOT NULL""", cfg.symbol, W0, W1)
        line(mapped == 0 and sum(v[0] for v in st.values()) > 0
             and (okx_first_beat is None or W1 <= okx_first_beat),
             "C2_window_old_only", f"{mapped} mapped Bybit rows in the window; OKX first row {okx_first_row}, "
             f"first heartbeat {okx_first_beat}")
    finally:
        await raw.close()

asyncio.run(main())
PY
)
C2
)"
```

## Tested here, and what was not
- **What ran.** Both blocks, as extracted from this file, ran against a local `postgres:16` container named `btcbot_timescaledb`. It had `storage/schema.sql` (without the TimescaleDB calls) and `storage/beta_v0_schema.sql`, and these representative rows:
  - pre-D1 Bybit rows with swapped sides and Bybit marks every 15 s;
  - post-D1 Bybit, Binance and OKX rows, with OKX `qty = sz × 0.01`;
  - OKX heartbeats from the restart, with a 20-minute gap;
  - tape buckets where OKX was stored as 0 before D1.
- **Results on those rows.**
  - All PASS lines passed.
  - With OKX rows scaled ×100 (as if ctVal were 1), `C1a_okx_scale` (ratio 130) and `C1b_match` (0 of 8 equal) gave FAIL.
  - With the post-D1 Bybit sides swapped back, `C2_mark_side` gave FAIL (control 0.017).
  - Under `PGOPTIONS` and under the Python connection's `server_settings`, a `CREATE TABLE` / `CREATE TEMP TABLE` is refused (read-only transaction).
- **v2 re-run (same container, same rows, plus the cases of run 1).**
  - Six OKX rows with `mapping_version = 2` were added at event times 14:04–14:51Z, inside the C2 window.
    - All C2 lines passed. `C2_okx_rows_new_only` printed 6 rows.
    - The OKX bucket states were 277 `UNPROVEN` and 11 `NEW`, and all 288 read None (the `NEW` ones through liveness).
  - The canned REST answer gained a second order at one key: same ms and price, 0.09 contracts. The database holds one row there. `C1b_match` passed, 8 keys.
  - A stored row duplicated at a key where REST holds one order gave FAIL: 9 stored, 8 matched.
  - One stored size ×100 gave FAIL: 7 of 8.
- **Not tested here: the two `curl` calls to okx.com.** C1(b)'s parsing and matching ran on a canned answer of the documented shape, served by a stub `curl`.
- **Not tested here: the TimescaleDB image itself.** The SQL uses only plain PostgreSQL.
