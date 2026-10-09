# OKX liquidation events arriving late — impact note

**Status:** `FACTS_FOR_DECISION` (2026-10-09, track A for ОПГ-1). The architect decides. This note contains no code change. The delay numbers are being measured by the owner. The pre-3b checks are in `docs/BETA_PRE3B_DATA_CHECKS.md`, and run 1 is recorded in `docs/BETA_RELEASE_LOG_V1.md`.

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
