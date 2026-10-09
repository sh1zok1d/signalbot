# OKX liquidation events arriving late — impact note

**Status:** `DECIDED: (d)`. Facts are from 2026-10-09. The architect decided the same day, the owner confirmed it, and track A built it for 3b. Sections 1–4 are the facts the decision was taken on. Section 5 is the decision and what was built; section 6 is the step after the beta. The pre-3b checks are in `docs/BETA_PRE3B_DATA_CHECKS.md`, and run 1 is recorded in `docs/BETA_RELEASE_LOG_V1.md`.

**What was observed (run 1, production).**
- 6 OKX liquidation events with event times from 14:04:48Z were processed by the collector after its 14:59:21Z restart, 57–71 min after their event time. All carry `mapping_version = 2`.
- All 6 events predate the restart. So this does not yet establish a steady-state delay on a running socket. It may be a backlog delivered after (re)subscription. The owner's per-venue measurement decides.
- **What the database cannot tell.** `liquidations` stores the event time only (`ts`, `storage/schema.sql`). There is no ingest or recorded-at column. `id` gives the arrival order, not the arrival time. The delay can't be measured from the database; it comes from the collector journal.

## 1. When a tape bucket is materialized, and whether it is rebuilt
- **Materialized once, about 25 s after the bucket closes.**
  - The detector timer fires every 5 min at :25 s (`deploy/signalbot-beta-detector.timer`, `OnCalendar=*-*-* *:00/5:25 UTC`).
  - It decides the latest bucket whose close + `bucket_close_grace_s` (20 s, `config/beta_v0.yaml`) has passed (`select_latest_closed_bucket`, `beta/state_tape.py`).
  - It catches up at most 12 buckets after its watermark (`plan_buckets`, `beta/detector.py`; `max_catchup_buckets_per_run: 12`).
- **The liquidation input is read once.** Stage 2 reads that bucket's raw rows by **event time** at materialization (`LIQUIDATIONS_SQL`, `storage/stage2_readers.py`: `ts >= start AND ts < end`). The per-venue sums are stored by value in `beta_state_tape.metrics` as `x:okx:{long,short}_liquidation_notional`.
- **Rebuilt only on two paths.** Each one appends a `CORRECTION_CHECK` revision, never an UPDATE (`_correction_check`, `beta/detector.py`):
  1. an operator run of `--beta-once --beta-bucket-ts <bucket>` for a bucket at or below the watermark (`run_detector_once`, `runtime/beta_cli.py`);
  2. `repair_after_startup_recovery`, after a Stage-1 startup recovery. It selects buckets **by 1m kline counts only** (`stale_buckets`, `beta/recovery.py`), so a late liquidation row never triggers it.
- **When a revision is appended.**
  - It happens only if the bucket's feature digest changed.
  - The episodes decided from the old snapshot are flagged (`flag_correction`), not re-decided.
  - Readers take the newest revision per bucket (`fetch_tape_history`, `DISTINCT ON (bucket_ts) … ORDER BY bucket_ts, tape_id DESC`, `storage/beta_v0_store.py`).

## 2. Does a row arriving 60 min late enter its bucket?
**No.** By the time it arrives, its bucket was materialized about 55 min earlier, and neither rebuild path runs for it. The row stays in `liquidations` but never reaches `x:okx:*_liquidation_notional` for its bucket. It reaches no later bucket either, because buckets are keyed by event time.
- **The 1h/4h/24h liquidation lines** (`build_horizons` → `_liq_side`, `beta/horizons.py`) sum those tape values. They miss late OKX events for **every** window, not only the last hour.
- **OKX's percentiles** are built from the same tape values (`compute_percentiles` over `fetch_tape_history`). They describe "OKX liquidations that arrived within about 25 s", consistently in history and now.
- **The OKX liveness rule** (`feed_alive`, `beta/liq_mapping.py`) is unaffected: it reads heartbeats, not liquidation rows.

## 3. What the readers and screens show today
- **`fetch_liquidations`** (raw rows, read at view time) is used by the levels block only, for **Binance and Bybit** (`LIQ_VENUES`, `beta/levels.py`; `beta/decision.py`). It never reads OKX, so late OKX rows don't touch it. For Binance and Bybit, a late row would appear in the 24h level window once it has arrived. Whether those venues are late too is the open per-venue measurement.
- **OKX amounts on screens** stay «н/д» until both OKX sides' percentiles are MATURE (30 days of history, `okx_liq_shown`; applied in `beta/market_view.py`). Once shown, an OKX sum is printed as a lower bound «≥» (`mark_okx_lower_bound`), because OKX's WS channel "doesn't represent the total number of liquidations".
- **OKX's vote in `LIQUIDATION_STRESS`** needs a MATURE percentile (`_pct`, `beta/rules.py`) and `min_eligible_venues: 2`. Until then OKX is ineligible.
- **Net effect today.** With the first OKX heartbeat at 2026-10-08 14:59Z, OKX liquidation values reach no user surface and no vote for about 30 days. After that, late events make the displayed «≥» bound looser and lower OKX's vote rate, but no displayed number states more than it measured.

## 4. Options

| | What changes | Code cost (estimate) | Effect on the 7-day count |
|---|---|---|---|
| **(a)** OKX buckets younger than a frozen max delay D read «не измерен» or partial | At read time only. It is a no-op for the tape: a tape bucket is never refilled, so after D it would show the same incomplete value. It helps only readers of raw rows, and none reads OKX rows. To matter for the tape it has to be combined with (b). | Small: one read-time rule plus tests, about 30–50 lines | A read-definition change for a metric that no user sees and no vote uses until OKX matures. Whether an invisible change resets the count is the architect's call under ORCHESTRATION §4a. |
| **(b)** Re-materialize | Run the existing `_correction_check` once for each bucket when it reaches age D (one extra bucket per detector run). The tape then holds "OKX within D" for buckets after the change. For a consistent history, the same must be run once over every post-D1 bucket (288 per day since D1). | Medium. About 40–80 lines plus tests: a second pass in `run_detector_once` and a one-off backfill command. Side effects to settle: it corrects **every** late input, not only OKX (any changed feature digest appends a revision and flags episodes), and percentiles of buckets decided before the correction keep the old history. | Changes stored values and percentile history: a metric definition change. Before 3b it costs nothing. After 3b it restarts the count. |
| **(c)** Leave it and disclose | Nothing in code. A line in `/terms`/methodology, along the lines of «часть ликвидаций OKX приходит с задержкой и в 5-минутные данные не попадает; суммы OKX — нижняя граница». The «≥» marking already exists. | Text only | No metric definition changes. Whether a wording change counts is under §4a. |

**Stated preference (facts first, not a recommendation; the architect decides):**
- If the owner's numbers show that late arrival is a reconnect/subscribe backlog and steady-state delays are seconds, prefer (c). OKX reaches no surface or vote for about 30 days anyway, and its shown sums are already lower bounds.
- If steady-state delays routinely exceed the 25 s materialization lag, or Binance/Bybit are late too, prefer (b), decided and backfilled before 3b, so the count is not restarted later.
- (a) alone does not fix the tape.

## 5. Decision (d) and what was built (2026-10-09)
**The owner's arrival-delay data.** Last 24 h, preliminary, measured from the collector journal (event time to processing):

| Venue | p50 | p99 | max |
|---|---|---|---|
| Binance | 1.1 s | 2.5 s | 3.3 s |
| Bybit | 0.4 s | 1.2 s | — |
| OKX | 2.9 s | 18 374 s | 18 432 s (5.1 h) |

On OKX, 34.5 % of events arrive more than 5 min late, 24.4 % more than 30 min late, and p90 is 8 636 s. This is a steady property of OKX's channel, not a reconnect backlog.
- **(b) is ruled out.** It would break as-of: a decided bucket would change hours later.
- **(a) is ruled out.** It would have to cover about 5 h.
- **(c) alone is not enough.** OKX is «н/д» and does not vote only until both sides' percentiles mature (about 30 days after D1). It would then enable itself automatically, around early November, in the middle of the beta.

**Owner, 2026-10-09:** «пока можно убрать метрики OKX… потом можно будет добавить таймер получения данных». The scope is OKX **liquidations** only. OKX price, OI, volume and funding stay unchanged.

**Decision (d), minimal:** a config flag keeps OKX liquidations out of the beta, with no automatic enable.
- **The flag.** `config/beta_v0.yaml`: `liquidations.okx_enabled: false`. It is validated as a bool, and the section is required with exact keys (`beta/config.py`).
- **Display.** While the flag is off, `okx_liq_shown` is always false (`beta/liq_mapping.py`, used by `beta/market_view.py`), so OKX amounts stay «н/д» whatever their percentile maturity.
- **The rule.** `LIQUIDATION_STRESS` marks OKX ineligible with `OKX_LIQUIDATIONS_EXCLUDED` (`beta/rules.py`), so it never votes. Readiness shows it as unavailable, never as a venue on its way to readiness (`beta/readiness.py`).
- **What stays exactly as before.**
  - Screens, alerts, push inputs and the briefing (OKX was already «н/д» and not voting).
  - Binance and Bybit.
  - The collector, the schema and Stage-2 materialization. OKX values are still stored in the tape.
- **The rules digest.** The flag is deliberately outside the rules digest. With the flag off, the rule decides exactly as it did, so episode identity holds. Turning the flag on later is a rule change and needs its own rules version.
- **Texts.**
  - The liquidation-stress definitions end with «Ликвидации OKX не учитываются.» / «OKX liquidations are excluded.».
  - `/terms` adds «Ликвидации OKX не учитываются и показаны как «н/д»: OKX присылает данные о ликвидациях с задержкой до нескольких часов.» The EN version is «OKX liquidations are excluded and shown as n/a: OKX sends liquidation data up to several hours late.».

**With two voting venues, `min_eligible_venues: 2` still holds:**
- Binance and Bybit must both be eligible and both in their own top 5 %.
- If one of them is dead or immature for a bucket, the rule is `NOT_EVALUABLE` (`INSUFFICIENT_ELIGIBLE_VENUES`): no liquidation episode and no push for that bucket. OKX never fills in.
- This is what already held in practice: OKX was immature and never voted since D1.

## 6. After the beta: the «таймер получения данных» (not built)
**A receive time for every row: `received_at`.**
- **Schema change.** `ALTER TABLE liquidations ADD COLUMN received_at TIMESTAMPTZ`, nullable and without a default, so old rows stay NULL ("unknown") and are never mislabelled. The collector then writes its own receive time on each insert (`storage/db.py insert_liquidations`, one more field).
- **Cost on the hypertable.** A nullable column without a default is a catalog-only change in PostgreSQL and TimescaleDB: no chunk is rewritten. `storage/schema.sql` sets no compression or retention policy on `liquidations`, so no compressed-chunk restriction applies. It belongs in `storage/schema.sql`, applied by the collector at start like `mapping_version`. The beta never runs it, because it must not lock the collector's table (review of #378).
- **Use.** Stage 2 and the beta could read a bucket "as known at decision time" (`received_at <= evaluated_at`). A replay then gives the same answer, and OKX could return under a stated as-of instead of hours-late data silently missing.

**A lateness monitor.**
- Per venue over the last 24 h: p50, p99 and max of `received_at - ts`, and the share of rows later than the 25 s materialization lag. Shown in `--beta-health` / `/admin_health`.
- An alert when a measured venue's p99 exceeds the lag.
- **Cost:** one read-only query over a 24 h range of the `(exchange, symbol, ts)` indexes, plus one health line.

**Turning OKX back on** would need all of: these two pieces, a measured OKX lateness within the materialization lag (or an as-of read that tolerates it), `liquidations.okx_enabled: true`, and a new rules version.
