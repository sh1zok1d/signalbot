# Beta data reliability — fix plan V1 (DRAFT)

Status: **DRAFT, not scheduled.** Written 2026-10-06 from a code verification of an external review of one bot summary (the 24h tab / `/catchup` / briefing lines). The owner reviews it on 2026-10-08; nothing here is authorised to build until then. It changes no decision and no frozen record.

Scope of the verification: code on `origin/main` 1a2e425, compared with production `c980fae`. The collector, Stage-2 and tape code involved is identical on both; the only difference is `beta/derivatives.py` (the «обычно» comparators), which exists from `d0652d1` on. A summary that showed «обычно ±2,2%» therefore came from `d0652d1` or later. No VPS data was read: the items marked **confirm on VPS** rest on code, documents and small live probes.

## 1. Findings, by severity

### R1. OKX liquidations are not measured; the bot prints a measured «OKX $0» — HIGH
- **Collector.** `data_ingestion/okx_client.py:36,89-93` subscribes `liquidation-orders` on `wss://ws.okx.com:8443/ws/v5/business`. A live probe on 2026-10-06 got `60018 … channel:liquidation-orders … doesn't exist` there, while `/ws/v5/public` accepts the same subscribe (current OKX docs list the channel under `/public`). The error frame is dropped (`okx_client.py:113-114`). Earlier evidence: 0 OKX rows in the 2026-07-16 soak (`docs/STAGE1_ACCEPTANCE.md:136-141`); "no OKX liquidation rows" in `docs/E1_DATA_INVENTORY_2026-08-25.md:15`.
- **Formula.** Even when rows arrive, `okx_client.py:121-127` stores `notional = bkPx × sz` with `sz` in contracts (ctVal 0.01 BTC): about 100× too large. `beta/levels.py:41-43` already knows this and keeps OKX out of the level clusters. ctVal is applied to OKX bar volume/taker only (`analytics/feature_engine/units.py`), never to liquidations.
- **Flag clash.** The collector writes `is_snapshot_feed=True`; OKX's capability is `aggregated` (`common/capabilities.py:68`), so a real OKX row raises in `input_adapter.py:483-490` and drops the whole OKX feature vector for that bucket (price, OI, volume, liquidations).
- **What users see.** Stage-2 turns "venue available, no rows" into a measured 0.0 (`exchange_features.py:351-357`), so the «Событие» / «1ч» / «24ч» tabs print `Ликвидации лонгов: … · OKX $0` without the asterisk Binance gets. The storage schema itself says absence of rows means absence of data, not zero (`storage/schema.sql:94-98`).
- **Votes.** OKX sits in the denominator of «k из 3 бирж» (`formatter.py:199-204, 224-228, 734-740`) but with an all-zero history its rank is 0.5 forever, so it can never vote: liquidation stress in effect needs Binance and Bybit together. `readiness.py` reports OKX liquidations READY.
- **History.** False OKX 0.0 values are persisted append-only in `beta_state_tape` (metrics and 30-day percentiles), `beta_context_snapshots` and `beta_btc_views` (payload and rendered HTML). Liquidations are live-only, so there is nothing to backfill.

### R2. Bybit liquidation sides are probably swapped — HIGH, confirm on VPS
- `data_ingestion/bybit_client.py:70-78` maps `S == "Buy"` to `short`. Bybit's v5 `allLiquidation` docs say a Buy update means a **long** was liquidated. A live probe of 17 events matched the docs 17/17 (bankruptcy price below mark for Buy, above for Sell). Small sample.
- Affects the Bybit long/short cells, the per-side liquidation votes and «вынос» labels, and the LIQ_LONG / LIQ_SHORT level clusters (built from Binance + Bybit).

### R3. Funding has no freshness bound and no interval — MEDIUM
- **Freshness.** `storage/stage2_readers.py:46-53` takes the latest row before the bucket end with no lower bound (pinned by `tests/storage/test_stage2_feature_readers.py:171-172`). A venue whose funding poll stops keeps its last rate in the cross-venue median indefinitely, with no user-visible sign. Funding is not a core family, so the status never degrades. OI, by contrast, has a 2-minute bound.
- **Interval.** No venue's funding interval is stored (`base_client.py:47-53`, `schema.sql:68-76`); rates are medianed as directly comparable (`docs/STAGE2_SPEC.md:385-387`). Latent today: BTCUSDT settles every 8h on all three venues.
- **Coverage.** «среднее за 24 ч» is the mean over whatever 5m buckets exist; one bucket of 288 is enough (`horizons.py:216-225`). «Funding стал положительным/отрицательным» has no coverage rule and no size threshold; it fires on a rate that prints as «-0,000%» (`horizons.py:359-362, 407`).
- **Text.** The number is a per-8h rate; no text says «за 8 ч», and «среднее за 24 ч» is not the 24h cost.
- Backfilled settled rates and live predicted rates share one column with no source filter (`backfill.py:338,419,489`).

### R4. OI headline is a cross-venue median labelled like a total — MEDIUM
- `horizons.py:228-235`: the 24h OI headline is the median of per-venue % changes (base BTC for Binance/Bybit, contracts for OKX; same unit at both ends, `oi_asof.py:65-81`). It is not the total-OI change; the sign can differ.
- No minimum venue count on the 24h horizon: one venue makes the headline (the 1h/4h context requires 2).
- Labels: the 24h tab says «OI {med}: {venues}», the main screen «OI −0,3%», `/catchup` and the briefing «OI −0,3% за 24ч». Only funding says «(медиана бирж)». `/terms` describes OI as a total.
- `contract_value` is never written by the live collectors, so the as-of contract-value check never fires.

### R5. «обычно ±2,2%» compares the venue median with a Binance-only absolute comparator — MEDIUM
- `derivatives.py:31-48`: median of |Δ| of Binance OI between consecutive UTC midnights since 2020-09 (N days shown). The live number is a signed rolling-24h median across up to three venues. Only the horizon and the unit match; a cross-venue median damps single-venue moves.
- The 24h tab label is honest («медиана, Binance, N=… дн.»); the `/catchup` and briefing label «(обычно ±2,2%, N=…)» is not.

### R6. «Крупных изменений к предыдущим 24 ч нет» is broader than its four checks — MEDIUM
- `horizons.py:337-363` with `config/beta_v0.yaml:130-137` checks only: range ×1.5 / ×0.67, volume ×1.5 / ×0.67, |OI| ≥ 1 pp together with |price| ≥ 1 %, and a funding sign flip.
- It prints «нет» when inputs are missing, and stays silent on a single-venue OI move (e.g. OKX +4,4 %), funding moves within one sign, liquidations, taker delta and venue divergence.

### R7. Volume and taker delta can mix venue sets — LOW
- Each 5m bucket sums whichever 2–3 venues have all five 1m bars (`consensus.py:312-320`, `input_adapter.py:108-124`). `volume_partial` is set only for missing buckets, never for a bucket with 2 of 3 venues (`horizons.py:261-275, 311`). The 30-day median comparator follows the same rule, so «×… от медианы 30 дн.» can move because a venue dropped out. `/terms` says the volume is Binance + Bybit + OKX.
- OKX units are correct here (contracts × ctVal × close).

### R8. Completeness figures — INFO
- `buckets_present` / `buckets_expected` (288/288) is a payload field, never printed. It means "a tape row exists for every 5m bucket"; a bucket materialised by one venue counts. It says nothing about per-venue presence, complete 1m bars, complete trades (bars are built from websocket trades with no continuity check), OI, funding or liquidations.
- Binance liquidations are a lower bound by design (forceOrder pushes at most one per symbol per second) and are marked «≥» / «$0*».

## 2. Reliability statement (what each number may be used for today)

| Number | Usable for | Not usable for |
|---|---|---|
| OI per venue | the venue's 24h change in BTC/contracts | — |
| OI headline | what a typical venue did | total-OI change; a one-venue headline is not flagged |
| «обычно» beside OI | rough size of a typical Binance daily OI move since 2020 | the "usual" for the headline number or the current regime |
| Funding now | cross-venue median per-8h rate while all three polls are live | freshness after any poll stops; 24h cost |
| Funding 24h mean, sign change | — | no coverage rule; sign change fires on ±0,000 % |
| Volume, delta | order of magnitude across 2–3 venues | the 30-day ratio when a venue drops out |
| Binance liquidations | lower bound | full amount |
| Bybit liquidations | amount (base BTC) | side, until R2 is confirmed |
| OKX liquidations | nothing | anything, including the «k из 3» denominator |
| «Крупных изменений нет» | "none of the four checks fired, where computable" | "nothing notable happened" |

## 3. Fix directions (to plan on 2026-10-08)

One line each; each needs its own design check before code. Collector changes are evidence-protecting correctness fixes; beta-side changes stay inside `beta/`, `storage/beta_v0_*` and `config/beta_v0.yaml`. The Stage-2 SQL is shared with frozen engines, so freshness bounds go on the beta side.

1. **R1** — subscribe on `/ws/v5/public`; multiply by ctVal; make the snapshot flag agree with the capability; log subscribe errors; until fixed, print OKX liquidations as «н/д» (not «$0») and drop OKX from the «k из n» denominator; exclude pre-fix OKX tape rows from the percentile history (a collector fix does not start a new calculation version: `common/versioning.py:173-182`).
2. **R2** — after the VPS check, map Buy → long, Sell → short; decide what to do with stored Bybit rows (swap in a derived view; the raw table keeps its bytes) and with the level clusters and percentiles built from them.
3. **R3** — beta-side age bound on each venue's funding row (drop the venue or «н/д»); coverage rule for the 24h mean and the sign-change line; a size threshold for the sign change; store the interval (Bybit `fundingIntervalHour`, OKX `nextFundingTime − fundingTime`, Binance `fundingInfo`) and refuse to mix intervals; «за 8 ч» in the text.
4. **R4** — label the headline «медиана бирж», require ≥ 2 venues on 24h as on 1h/4h; `/terms` wording.
5. **R5** — compare like with like (the Binance venue number against the Binance comparator, or a venue-median history) and say «Binance» on every surface.
6. **R6** — name the checks in the sentence or narrow it; never print «нет» when the comparison could not be computed.
7. **R7** — mark volume partial when any bucket has fewer than three venues; build the 30-day median from full-venue days.
8. **R8** — if coverage is ever shown, show it per venue.

## 4. Confirm on the VPS (read-only)

```bash
git -C /opt/signalbot rev-parse --short HEAD
journalctl -u signalbot --since "-1 day" | grep -c "okx.*liquidation"
```

```sql
-- R1: does any OKX liquidation row exist?
SELECT exchange, side, count(*), min(ts), max(ts) FROM liquidations GROUP BY 1,2 ORDER BY 1,2;

-- R2: a liquidated long has its bankruptcy price below mark, a short above (Binance as control)
SELECT l.exchange, l.side, count(*) AS n,
       count(*) FILTER (WHERE l.price < m.mark_price) AS below_mark,
       count(*) FILTER (WHERE l.price > m.mark_price) AS above_mark
FROM liquidations l
CROSS JOIN LATERAL (SELECT mark_price FROM mark_price mp
                    WHERE mp.exchange = l.exchange AND mp.symbol = l.symbol
                      AND mp.ts <= l.ts AND mp.ts > l.ts - interval '5 minutes'
                    ORDER BY mp.ts DESC LIMIT 1) m
WHERE l.exchange IN ('bybit', 'binance') AND l.ts > now() - interval '7 days'
GROUP BY 1,2 ORDER BY 1,2;
```

If Bybit `short` rows are mostly `below_mark`, R2 is confirmed.
