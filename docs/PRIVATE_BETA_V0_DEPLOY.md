# Private Beta V0.2 — deploy, soak and privacy runbook

Authority: `docs/PRIVATE_BETA_V0_RESTART_DECISION.md`. The systemd artifacts are **prepared but not activated**. Activation is a separate, owner-authorized step.

## Units (`deploy/`)

| Unit | Schedule | Command |
|---|---|---|
| `signalbot-beta-detector.service` + `.timer` | every 5m at :25 s | `main.py --beta-once --beta-json` |
| `signalbot-beta-outcomes.service` + `.timer` | every 5m at :50 s (offset 2m) | `main.py --beta-outcomes-once --beta-json` |
| `signalbot-beta-notify.service` + `.timer` | every minute at :40 s | `main.py --beta-notify-once --beta-json` |
| `signalbot-beta-bot.service` | long-running (Restart=on-failure) | `python -m runtime.beta_bot` |
| `signalbot-beta-d7.service` + `.timer` | every hour at HH:01 UTC | `main.py --beta-d7-once --beta-json` |
| `signalbot-beta-history.service` + `.timer` | daily 02:20 UTC | `main.py --beta-history-sync` then `--beta-history-build` (decision support V2, below) |
| `signalbot-beta-feeds.service` + `.timer` | every 5 min at :40 s | `main.py --beta-feeds-once` (research evidence: public OI / long-short ratio, DVOL, depth, spot; `docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md`) |
| `signalbot-beta-stress.service` + `.timer` | every hour at HH:02 UTC | `main.py --beta-stress-once` (research evidence: public aggTrades of stress hours only) |

- `deploy/install_beta_units.sh` copies the units and runs `daemon-reload`. It **never enables or starts** anything.
- The research-evidence feed and stress units are activated only with a separate owner go: `sudo systemctl enable --now signalbot-beta-feeds.timer signalbot-beta-stress.timer`. Until then the evidence engine still runs on the history it has and lists the findings it cannot check, with the reason. Kill switches: `decision.research_evidence.{enabled, feeds_enabled, stress_hours_enabled}`.
- `deploy/check_beta_units.sh` is read-only.
- The detector and outcomes units wait for PostgreSQL first (`ExecStartPre=deploy/wait_for_infra.py --postgres-only --timeout 60`, the same readiness gate `signalbot.service` uses, minus Redis).
- The bounded history bootstrap is run manually with `python -m runtime.beta_bootstrap_runner [--max-iterations N]` (default 40, cap 100; 30 days need 31 batches of `bootstrap.max_buckets_per_run` = 288). Each iteration runs the unchanged `main.py --beta-bootstrap --beta-json` and prints progress. The runner stops on the first error, and fails if the bootstrap is still incomplete at the bound. After completion it runs one extra bootstrap as an idempotency check, which may only write buckets that closed in the meantime. Exit codes: `0` verified, `2` bootstrap error, `3` iteration limit, `4` verification failed.

## D7 hour state

The D7 feed is display-only. It does not enter the rules digest, does not open an episode, and does not change a push.

The line is shown only when both switches are on, the same shape as push:

- **Hard allow:** committed `regime_d7.enabled: true` in `config/beta_v0.yaml`. Turning this false in a future config hides the line even if the owner state is on. Activation does not edit this file on the VPS.
- **Owner state:** `/admin_d7_on` and `/admin_d7_off`. Both are audited in `beta_admin_audit`. The durable key is `beta_runtime_state.state_key = 'admin_d7_enabled'`. A missing row is off. `/admin_d7_on` cannot exceed the hard allow.

- **Timer:** `signalbot-beta-d7.timer` runs `main.py --beta-d7-once` at HH:01 UTC. Each run fetches closed Binance USD-M BTCUSDT 1m bars (`closeTime < now`) from the last stored bar, and at least the last 120 bars, paging at 1500. It then inserts hour states that do not exist yet. A missed run catches up on the next start.
- **Backfill:** `python main.py --beta-d7-backfill --days 90 --beta-json`. Paged at 1500 bars with a short pause between pages. Resumable and idempotent. 90 days covers the 1440-hour warm-up with room for gaps.
- **Health:** while `regime_d7.enabled` is true, `--beta-health` raises `D7_HOUR_STATE_STALE` when there is no hour state or the newest state's `available_at` (the end of that clock hour) is older than 70 minutes. With the hard allow false the alert is absent. The alert follows the hard allow, so it can fire before `/admin_d7_on`. It does not show the line.

**Enable, without editing files on the VPS:**

1. Deploy the commit that already has `regime_d7.enabled: true`. Schema init widens `beta_runtime_state` so `admin_d7_enabled` is allowed. No owner row is inserted.
2. Install and start `signalbot-beta-d7.timer`.
3. Run `python main.py --beta-d7-backfill --days 90 --beta-json`.
4. Run the sanity SQL below. Leave the line off until every check is sane.
5. From the owner account, send `/admin_d7_on`. The next `/btc` can show the line when the display rules also hold (complete last hour, state true, warm-up, computed on time, view not stale or degraded).
6. `/admin_d7_off` hides the line again. No restart and no config edit.

**Sanity SQL** (read-only). `valid_hours` counts completed hours with a return. `share_true` is the share of decided hours whose stored state is true. That is the p90 threshold on hours already labeled. It is not a count of whether the next hour was also high impact.

```sql
SELECT count(*) FILTER (WHERE complete AND ret IS NOT NULL) AS valid_hours,
       count(*) FILTER (WHERE state IS NOT NULL) AS decided_hours,
       count(*) FILTER (WHERE state) AS state_true,
       count(*) FILTER (WHERE state)::float
           / NULLIF(count(*) FILTER (WHERE state IS NOT NULL), 0) AS share_true
FROM beta_d7_hour_states;
```

Expect `valid_hours >= 1440` and `share_true` near 0.10.

```sql
SELECT hour_start, available_at, now() - available_at AS age
FROM beta_d7_hour_states
ORDER BY hour_start DESC
LIMIT 1;
```

Expect `age` under 70 minutes.

Stage-1 `klines_1m.ts` is the Binance 1m open time, the same instant as `beta_d7_klines_1m.open_time`. The current open minute is excluded.

```sql
WITH bounds AS (
    SELECT now() - interval '24 hours' AS start_ts,
           date_bin('minute', now(), TIMESTAMPTZ '2000-01-01 00:00:00+00') AS open_minute
),
d7 AS (
    SELECT d.open_time, d.close
    FROM beta_d7_klines_1m d
    CROSS JOIN bounds b
    WHERE d.open_time >= b.start_ts AND d.open_time < b.open_minute
),
stage1 AS (
    SELECT k.ts, k.close
    FROM klines_1m k
    CROSS JOIN bounds b
    WHERE k.exchange = 'binance' AND k.symbol = 'BTCUSDT'
      AND k.ts >= b.start_ts AND k.ts < b.open_minute
)
SELECT (SELECT count(*) FROM d7) AS d7_bars,
       (SELECT count(*) FROM stage1) AS stage1_bars,
       (SELECT count(*) FROM d7 JOIN stage1 s ON s.ts = d7.open_time) AS compared,
       (SELECT count(*) FROM d7 JOIN stage1 s ON s.ts = d7.open_time
         WHERE d7.close IS DISTINCT FROM s.close) AS close_mismatches,
       (SELECT count(*) FROM d7 LEFT JOIN stage1 s ON s.ts = d7.open_time
         WHERE s.ts IS NULL) AS d7_only,
       (SELECT count(*) FROM stage1 s LEFT JOIN d7 ON d7.open_time = s.ts
         WHERE d7.open_time IS NULL) AS stage1_only;
```

Expect `close_mismatches = 0`, `d7_only = 0`, and `stage1_only = 0`.

## Temporal context (`/btc`)

`--beta-once` also advances the context projection (`beta_context_snapshots`) inside each bucket's transaction, and `/btc` records what it showed (`beta_btc_views`). See `docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md`. There is no new unit and no new command.

## Warm-up and detector readiness

A fresh deployment has a **warm-up period**. Readiness follows the accumulated **valid history** recorded on the state tape, not the calendar. A family becomes ready when every percentile it needs has a valid sample exactly one maturity span (30 days, the Stage-2 confidence-tier setting) before the latest bucket, and its venue and eligibility gates pass. Gaps delay readiness; a fixed date is never promised.

**What is available when:**
- **Right after the bootstrap:** the kline-derived context, meaning NOW (price, range, volume) and the rolling 1h context.
- **Not yet:**
  - **Price/OI families** (price+OI contraction, build-up/compression) need live OI history. The historical 5m OI sources cannot reproduce the within-bucket OI change, so the bootstrap adds no OI history.
  - **Taker flow** needs live multi-venue taker history.
  - **Liquidations** need live liquidation feeds plus live eligibility (healthy live bars, no outage) on at least two venues.

**How `/btc` shows it:**
- **Readiness on the main view:** `Detector ready` when every family is ready. Otherwise one line per family that is not ready (families in the identical condition share a line), then `Ready: <families>`. Each family is one of:
  - `ready`;
  - `history building · <input> <span> / 30d`, where the span is the earliest valid sample to the latest bucket, floored to 0.1 day;
  - `data unavailable · <reason>`;
  - `degraded · <reason>`;
  - `disabled`.
- The per-rule readiness details (tier, sample count, span, venue eligibility, read-model version) are owner diagnostics: participants get no Readiness button, and `r:latest` from an older message answers "not available" to anyone but the owner (`BETA_COPY_CONTRACT_V1` §5 rule 5: no internal states, codes or versions on the user surface).
- **Headline precedence:** DATA STALE, then DATA DEGRADED, then WATCH / EVENT ACTIVE, then HISTORY BUILDING (or DETECTOR NOT READY), then NO ACTIVE EVENTS. NO ACTIVE EVENTS is shown only when the Price/OI families are actually evaluable.
- **Absence of an event is not a negative detector decision** until the relevant family is `ready`. A valid event from a ready family is always shown, even while other families are still building.
- **No pushes:** readiness changes never send notifications.

**Soak planning:** until the Price/OI families are ready, the soak cannot observe core events. Start judging event behaviour from the first bucket in which the relevant family reports `ready`.

## Product-first V1: /catchup, morning briefing, unusual-hour push (build-to-test)

Authority: `docs/PRODUCT_FIRST_DECISION_V1.md` §3 and `docs/BETA_COPY_CONTRACT_V1.md`. One detector, one episodization, one context projection (`BETA_CONTEXT_1H_V2`), one shared view builder (`beta/market_view.py`), one outbox, one notifier. No new unit and no new timer.

**What changes at deployment (all additive, applied by the usual schema init: `main.py --beta-once` and the other `--beta-*` commands run `storage/beta_v0_schema.sql` idempotently):**
- `beta_push_decisions.gate JSONB` (the unusual-hour gate by value) and the suppression reasons `HOUR_NOT_UNUSUAL`, `QUIET_HOURS`, `GLOBAL_COOLDOWN` (the old unnamed check constraint is replaced by `ck_beta_push_suppression`);
- `beta_users.brief_enabled`, `beta_users.push_enabled` (both default true), `beta_users.known_contact` (default false);
- `beta_btc_views.kind` (`btc` / `catchup` / `brief`); `beta_notification_deliveries.kind` / `view_pk` / `brief_date`, with `decision_id` and `episode_pk` nullable for `kind = 'brief'`;
- `beta_user_activity.action` accepts `cmd_catchup`, `cmd_brief`, `cmd_push`, `brief_delivered`; `beta_admin_audit.action` accepts `admin_known`.
- Rules digest unchanged (`BETA_EVENT_RULES_V1`); tape schema V2 unchanged; `BETA_OUTCOME_V1` unchanged.

**Config (committed, `config/beta_v0.yaml`):** `max_new_pushes_per_utc_day: 2`; `push_policy.quiet_hours_kyiv: ["23:00", "07:00"]`; `push_policy.global_cooldown_min: 60`; `context.version: BETA_CONTEXT_1H_V2` with `rolling_buckets_4h: 48`; `briefing.enabled: false` (committed off; see below). None of these enters the rules digest.

**Behaviour after restart:**
- **Context V2 warm-up.** The projection adopts the open-episode memory of `BETA_CONTEXT_1H_V1` and recomputes the 1h/4h readings (now with taker-delta and OI-change ranks) from V2 tape rows. Ranks are `mature` only with 30 days of V2 rows (written since 2026-10-01); until then `/catchup` prints «мало истории» and the gate answers `IMMATURE`.
- **Pushes.** Every `TRIGGERED` episode is still decided and recorded, but it is delivered only when the rolling 1h around it passes the gate (two of three ranked metrics extreme and 2 of 3 venues agreeing). Expect `HOUR_NOT_UNUSUAL` on most decisions, and `IMMATURE` in `gate->>'status'` until the ranks mature. Quiet hours 23:00–07:00 Kyiv, at most 2 a day, one per hour. The push text is the 1h state, never a detector name or an id.
- **`/catchup`** works at once (facts; labels follow maturity). **`/push on|off`** and **`/brief on|off`** work at once.
- **Morning briefing** needs `briefing.enabled: true` (committed, a separate PR) **and** effective push (hard switch + admin state). It is built once a day after 08:00 Kyiv inside the notifier run and sent through the outbox as `kind = 'brief'`; a brief not sent within `briefing.max_delay_min` expires and is never sent late.

**Operator steps (in this order):**
1. Deploy, restart the bot (`signalbot-beta-bot`), let the timers pick up the new code. Schema init is part of every `--beta-*` command.
2. `python main.py --beta-health --beta-json` and `/admin_status`.
3. **Gate coverage diagnostic** (decision §3 row 7, read-only): `python main.py --beta-context-dry-run --dry-run-days 14 --dry-run-provisional --beta-json`. Read `dry_run.gate_coverage`: `unusual_hours`, `covered_by_triggered_episode`, `share`. Below about 0.8 the gate inputs are reviewed before invitations (decision §10); the second detector is never the answer. The same report shows label frequencies and rendered `/catchup` samples for the owner review of the interpretation (`INTERPRETATION_STATUS = PROVISIONAL_PENDING_DRY_RUN`).
4. Owner-only use until V2 ranks are mature (about 2026-10-31) and the owner has seen real unusual-hour pushes. Mark the owner's acquaintances with `/admin_known <telegram_user_id> on` as they join.
5. Enable the briefing with a one-line config PR (`briefing.enabled: true`) when the owner wants it; nothing else is needed.
6. Invitations only after the decision's §6 maturity and the pre-invitation commit that fixes the §7 thresholds.

**Rollback:** the schema changes are additive and keep V0.2 rows valid. Reverting the code leaves `gate`, `kind`, `brief_*` columns unused.

## Decision support V2: corridor, levels, history, events, market alerts

Authority: `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md` (owner decision 2026-10-03). Everything below is additive; the detector, the rules digest, tape schema V2 and `BETA_OUTCOME_V1` are unchanged.

**What is new**
| Piece | Where | Runs |
|---|---|---|
| Binance Vision history (5m klines from 2020-01, OI metrics from 2020-09), checksum-verified, resumable | `main.py --beta-history-sync` → `beta_hist_bars_5m`, `beta_hist_oi_5m`, ledger `beta_hist_objects` | new `signalbot-beta-history.timer`, daily 02:20 UTC |
| Nightly statistics (range model + held-out-year check, level reactions vs random levels, state analogues, event-day sizes) | `main.py --beta-history-build` → one `beta_hist_stats` row per build | same unit, right after the sync |
| Decision block in `/btc`, `/catchup`, the briefing | `beta/decision.py` (Binance history + Stage-1 Binance 1m tail + Stage-1 liquidations, read-only) | on every view |
| Commands `/levels`, `/risk`, `/alert`, `/events`, `/accuracy`, `/research`, `/push <kind> on|off`; buttons «Уровни», «Риск» | `runtime/beta_bot.py` | bot service |
| Research findings in the bot: one «Проверено: …» line in the matching context, the full list in `/research` | `beta/research_link.py`, `config/beta_research_findings.yaml` (no DB) | bot service, notifier |
| Market alerts (first touch of yesterday's / last week's / last month's high or low, CPI / FOMC 30 min ahead, sharp 15-minute move, personal `/alert`) and corridor tracking (`beta_forecasts`) | `beta/market_alerts.py` inside `--beta-notify-once`, outbox `kind = 'alert'` | the existing notifier timer (every minute) |
| Event calendar | `config/beta_calendar.yaml` (generated by `python -m scripts.beta.build_calendar` from the BLS / Federal Reserve pages already in the repo; CPI through 2026-12, FOMC through 2027-12) | read on every view |
| V2 tape rewind (removes «мало истории» where Stage-1 raw data exist) | `main.py --beta-bootstrap-rewind`, then the existing `runtime.beta_bootstrap_runner` | once, by hand |

New tables: `beta_hist_bars_5m`, `beta_hist_oi_5m`, `beta_hist_objects`, `beta_hist_stats`, `beta_forecasts`, `beta_market_alerts`, `beta_price_alerts`. New columns: `beta_users.push_levels / push_events / push_moves / push_hours` (default true), `beta_notification_deliveries.alert_pk`. New activity actions: `cmd_levels`, `cmd_risk`, `cmd_alert`, `cmd_events`, `cmd_accuracy`, `alert_delivered`, `btn_levels`, `btn_risk`. Privacy notice version 4 (personal `/alert` levels; `/delete_me` deletes them). New owner alert `HISTORY_STATS_STALE` (no successful build for 50h once builds have started).

**Config (committed):** a `decision:` section (`max_price_alerts: 5`, `forecast_tracking: true`, `market_alerts: {enabled: true, max_per_utc_day: 4, move_cooldown_min: 120, event_lead_min: 30, touch_max_age_min: 10}`); `briefing.enabled: true`. Market alerts also need effective push (`BETA_PUSH_ENABLED` and no `/admin_pause_push`) and respect quiet hours (23:00–07:00 Kyiv) except personal `/alert`.

**Protected window:** the E1-RUN-001 final holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` is never requested: every archive object whose period overlaps it is rejected before any request (the August 2026 monthly klines; the daily klines and metrics of 2026-08-16 … 2026-08-25, the 25th whole). August is read from its other daily objects, and the grid keeps 2026-08-16 00:00 → 2026-08-26 00:00 as a gap. The sync report lists them as `protected_rejected_keys` (21 objects).

**Network:** the history sync reads `https://data.binance.vision` only (about 4,500 objects on the first run, a few per night afterwards). Nothing else new leaves the VPS.

**One-shot helper:** after updating the code, `cd /opt/signalbot && sudo deploy/beta_v2_upgrade.sh` runs steps 2–8 below in order (each idempotent, stops on the first failure; `--skip-rewind` skips step 5). The manual steps are the same:

**VPS steps (in this order; run as the `signalbot` user from `/opt/signalbot` with the venv python)**
1. Update the code: `git fetch origin && git checkout <this branch or the merge commit>`; no new Python dependency.
2. Install the units (copies and `daemon-reload`, enables nothing): `sudo deploy/install_beta_units.sh`.
3. First history load (resumable; repeat until `planned` is 0 or only recent `MISSING` objects remain):
   `.venv/bin/python main.py --beta-history-sync --beta-json`
   Expect about 10–20 minutes; `bars_through` should end yesterday, `oi_from` should be 2020-09-01. `status: PARTIAL` with errors means some objects failed and will be retried on the next run; an archive whose content does not parse is recorded `BAD` (nothing of it is stored) and retried like a missing one. A failed sync never stops the nightly build over the history already stored.
4. First build: `.venv/bin/python main.py --beta-history-build --beta-json`. Read `corridor_coverage_holdout` (each about 0.80; 0.76–0.84 is fine) and `timings`.
5. Remove «мало истории» (optional but recommended): `.venv/bin/python main.py --beta-bootstrap-rewind --beta-json`, then `.venv/bin/python -m runtime.beta_bootstrap_runner` until it exits `0`. It refills current-schema tape rows for the last 30 days from Stage-1 raw data and skips every row that exists; the detector keeps running.
6. Restart the bot to load the new code: `sudo systemctl restart signalbot-beta-bot.service`. The notifier, detector and outcome timers pick up the new code on their next run.
7. Enable the nightly history timer: `sudo systemctl enable --now signalbot-beta-history.timer`.
8. Check: `.venv/bin/python main.py --beta-health --beta-json` (no `HISTORY_STATS_STALE`); in Telegram: `/levels`, `/risk 0.5`, `/events`, `/accuracy`, `/alert <price>`, `/research` (two messages), `/btc` (two new lines and the «Уровни» / «Риск» buttons), `/catchup`.
9. Read-only SQL after an hour:
   ```sql
   SELECT count(*), min(open_time), max(open_time) FROM beta_hist_bars_5m;
   SELECT stats_pk, built_at, data_through, payload->'timings' FROM beta_hist_stats ORDER BY stats_pk DESC LIMIT 1;
   SELECT horizon, outcome, count(*) FROM beta_forecasts GROUP BY 1, 2 ORDER BY 1, 2;
   SELECT kind, decision, suppression_reason, count(*) FROM beta_market_alerts GROUP BY 1, 2, 3;
   ```

**Expected behaviour**
- Around a CPI or FOMC release, for horizon H while now ∈ [release − H, release + 60 min), the corridor, touch chances and `/risk` figures for H are withheld. In their place one line names the release and its Kyiv time: «…: числовую оценку не показываем — CPI США, Вт 12.05 15:30 (Киев). Вокруг публикации обычная калибровка коридора не применяется.» The event reminder carries no corridor and no multiplier, and no forecast is tracked inside a zone. `/events` and the briefing's «Сегодня» list each event with its name and exact time only; when CPI or FOMC is listed, one line says «…: вокруг публикации обычная калибровка коридора не применяется.»
- Without a statistics row the views print «Коридор и уровни сейчас не показываем: история ещё не загружена»; with a Binance 1m tail older than 10 minutes, «данные Binance отстают». Nothing forward-looking is shown in either case.
- At most 4 level/move alerts per UTC day, one sharp-move alert per 2h, one alert per level per period (unique `alert_key`); a day high that is also the week high is one alert («максимум недели = максимум вчера»). A level touch older than 10 minutes (the notifier was down) is not pushed. A personal `/alert` touched while messages were off is still delivered and says when it happened.
- The sharp-move check runs once per closed 5m bar (the 15-minute statistic the threshold was calibrated on), so it can arrive up to 5 minutes after the move.
- The sharp-move statistic ignores the CPI/FOMC term (`SHARP_MOVE_EVENT_CONDITIONING = DISABLED_PENDING_VALIDATION`). The threshold is used only with the statistic it was built on (`payload->'range_model'->'move'->>'statistic' = 'MOVE15_OVER_1H_SCALE_EVENT_NEUTRAL_V1'`). A statistics row built by older code sends no sharp-move push until the next build; step 4 or the nightly timer builds one. Inside a release's 1h zone the alert has no «раз в N дней» line and no «Проверено» line.
- Pausing pushes (`/admin_pause_push` or the kill switch) also stops market alerts already queued; they are recorded `SUPPRESSED / PUSH_DISABLED`.
- A command that fails inside the bot is logged and skipped; it is never replayed.
- The corridor of the current hour is recorded once in its first 10 minutes and scored when its horizon ends (`/accuracy`).

**Rollback:** `sudo systemctl disable --now signalbot-beta-history.timer`, check out the previous commit and restart the bot. The tables are additive; the old code ignores them. Turning off only the pushes: `decision.market_alerts.enabled: false` (config), or per user `/push levels off` etc.

## POST-DEPLOY V2 SMOKE CHECK

Run this after the detector is active. The SQL file is read-only (`BEGIN TRANSACTION READ ONLY`). It does not read outcomes and does not compute forward returns, PnL, MAE, MFE, or hit rate. Any `FAIL` row is an operational stop.

1. `systemctl status signalbot signalbot-beta-bot`
2. `systemctl list-timers 'signalbot-beta-*'`
3. `python main.py --beta-health --beta-json`
4. Wait for 2–3 closed 5m buckets.
5. Run:

```bash
psql "$DSN" \
  -v deploy_ts='<UTC deployment timestamp>' \
  -f deploy/signalbot-beta-smoke.sql

# If regime_d7.enabled is true, also pass a timestamp from which D7 hour-state
# coverage is expected to be continuous:
psql "$DSN" \
  -v deploy_ts='<UTC deployment timestamp>' \
  -v d7_enabled=true \
  -v d7_deploy_ts='<UTC D7 coverage start>' \
  -f deploy/signalbot-beta-smoke.sql
```

`deploy_ts` is UTC, for example `2026-09-25 18:00:00+00`. The script scores 5m buckets that start at or after that time and have already closed.

6. Manual Telegram `/btc` check.

On a fresh deployment, `HISTORY BUILDING` is normal. `DETECTOR NOT READY` is also valid when live quorum or a required input is missing. `NO ACTIVE EVENTS` is not valid while the mandatory Price/OI scope is immature. Participants see no Readiness button (owner diagnostics only). Temporal-context Details exists only when an ACTIVE EVENT or a retained LAST EVENT exists. No temporal Details button immediately after a quiet fresh deployment is normal.

### Live OI sampling is the Day-0 gate

The current Stage-2 OI-change definition requires at least two OI observations inside a closed 5m bucket. With the unchanged ~15s Stage-1 poll, a healthy venue produces about 20 live observations per bucket. The hard correctness requirement is `>=2` usable observations on Binance, Bybit, and OKX.

If closed buckets repeatedly contain fewer than 2 live observations, do not wait for the 30-day warm-up. Treat that as an operational blocker immediately. Historical backfill cannot supply this within-bucket OI change.

A measured liquidation zero on an eligible venue is not a failure. `NULL` on an ineligible venue is UNKNOWN, not zero.

### First ~24 hours

Re-run the same script with the original `deploy_ts`. Read:

- expected vs written V2 buckets, missing buckets, revisions
- materialized rate and `evaluation_fresh` rate
- per venue: live OHLC coverage, OI observations per bucket (min / median / max), percent of buckets with `>=2` OI samples, taker coverage, liquidation-source rows, heartbeat healthy rate
- per readiness group, from recorded `/btc` payloads: `READY`, `HISTORY_BUILDING`, `DATA_UNAVAILABLE`, `DEGRADED`

Do not query `beta_episode_outcomes`. Do not compute forward returns, PnL, MAE, MFE, or hit rate.

## Startup recovery (reboot / power cycle)

**Incident 2026-10-02.** After a power cycle the persistent detector timer fired at 22:57:00, one second before Stage-1 was ready and 11 s before its startup gap-fill had restored the outage's raw 1m bars (22:35–22:54). The detector caught up 22:35, 22:40, 22:45 and 22:50 without raw bars. Their LIVE rows kept NULL kline OHLC: the 4h window was incomplete, and 8h had 92 of 96 valid buckets against a minimum of 94.

**Readiness barrier.** Every live Stage-1 start records one row in `backfill_runs` (`exchange='*'`, `source='startup_recovery'`, `common/startup_recovery.py`):

- **Lifecycle.** The row is `running` from before the startup backfill/gap-fill until the gap-fill is done. It then becomes `complete`, or `partial` if a venue's gap-fill failed.
- **Clean stop or error.** A clean stop or an error marks it `cancelled` / `failed`.
- **Killed process.** A killed process leaves it `running`, and the next start sweeps it to `cancelled`.

The detector reads the newest row on every run (`beta/recovery.py`) and does **not** decide any bucket while it is not ready:

| Gate state | Meaning | Detector |
|---|---|---|
| `NO_SIGNAL` | no row at all (Stage-1 predates the signal) | runs as before |
| `WAITING_FOR_STAGE1_START` | the newest row started before this host booted (`/proc/stat` `btime`): this boot's Stage-1 has not begun its recovery | waits |
| `RECOVERING` | `running` | waits |
| `NOT_READY` | `cancelled` / `failed`: waiting for Stage-1 to restart | waits |
| `READY` | `complete` / `partial` | runs, then repairs (below) |
| `OVERDUE` | waited `max_catchup_buckets_per_run` × 5m = 60 min | runs, owner alert |

The 60 minutes count from the start of the detector's continuous block. A Stage-1 crash loop writes a new row on every start, but it does not restart that count.

- **Waiting is not skipping.** The watermark stays where it is, and the next run catches up normally with the restored raw.
- **Why the wait is bounded at 60 minutes.** Beyond that, catch-up would drop buckets as `DETECTION_GAP` anyway.
- **Why there is no fixed delay.** A sleep only guesses how long the gap-fill takes.
- **Why `After=signalbot.service` is not the fix.** `After=` orders the unit only behind Stage-1's *start* (`Type=simple`), not behind the end of its gap-fill.

**Automatic bounded repair.** On the first `READY` run after a recovery, the detector re-checks the decided buckets in the window [recovery start − 12 buckets, recovery finish]. It picks only those whose stored per-venue bar count is below the raw count now in PostgreSQL, and re-checks them through the existing `CORRECTION_CHECK` path:

- **What gets written.** The detector appends a new tape revision (`supersedes_tape_id` = the LIVE row). It never updates the LIVE row. Product history and `/catchup` read the newest revision.
- **What does not change.** No episode, transition, push decision or notification is created. Affected episodes are only annotated (`correction_flag`).
- **Restored bars keep their source.** Restored bars stay `source=backfill`: they fill OHLC but never count as a live heartbeat, so the venue's `live_bars` stays 0 and its liquidation vote stays not evaluable.
- **Cap per run.** At most 12 buckets are re-checked per run; the rest are deferred to the next run.
- **Done marker.** Each bucket is its own transaction. The done marker (`beta_runtime_health` component `startup_recovery_repair`, keyed by the recovery run id) is written only when nothing failed. A crash or failure is therefore retried on the next run, and repeated runs append nothing.

**Observability.** The `--beta-once --beta-json` report and the detector's health detail carry `startup_recovery` (gate state, run id, wait time) and `recovery_repair` (`degraded`, `appended`, `unchanged`, `failed`, `deferred`). The journal has one line per blocked/resumed transition and one summary line per repair. Stage-1 logs `Stage-1 startup recovery started` / `READY`.

**Smoke.** Section `I. Startup recovery` reports two things:

- **The newest readiness row.** `complete` → PASS. `partial`, missing, or `running` for less than 60 minutes → WARN. Anything else → FAIL.
- **"Raw recovered, tape stale".** Decided buckets since `deploy_ts − 24h` whose raw bars now exceed the stored bars. FAIL when a venue has no stored bar at all.

**Existing 2026-10-02 buckets (operator step, not automatic).** Those buckets predate any readiness row, so the automatic repair window does not reach them. If the owner wants them repaired, run the existing explicit correction path once per bucket, after reviewing the smoke output:

```bash
python main.py --beta-once --beta-json --beta-bucket-ts '2026-10-02T22:35:00+00:00'   # then 22:40, 22:45, 22:50
```

Each run appends one `CORRECTION_CHECK` revision, or reports `UNCHANGED`. Nothing is sent.

## Environment (`/opt/signalbot/.env`, never committed, never printed)

| Variable | Meaning |
|---|---|
| `BETA_TELEGRAM_BOT_TOKEN` | Beta bot token. It is separate from the legacy notifier token. |
| `BETA_OWNER_TELEGRAM_USER_ID` | The single owner/admin Telegram user id. |
| `BETA_ENABLED` | Runtime enable. An explicit `1`/`true` enables and `0`/`false` disables, overriding the committed `beta.enabled: false`. If unset or empty, the config decides. |
| `BETA_DETECTION_ENABLED` | Kill switch for the tape and detector (restrict-only). |
| `BETA_PUSH_ENABLED` | Must be set explicitly to `1`/`true` **and** `beta.push_enabled: true` must be committed. If unset, push is forbidden. |
| `BETA_OUTCOME_TRACKING_ENABLED` | Kill switch for the outcome tracker (restrict-only). |
| `BETA_TELEGRAM_ENABLED` | `0` selects the no-Telegram shadow-soak mode (below). Default: Telegram is part of the deployment. |
| `BETA_CODE_VERSION` | Optional explicit beta code version. The default is resolved from the path-scoped git history. |

- **Switch precedence:**
  - `BETA_ENABLED`: explicit env value, else committed config.
  - Detection and outcome tracking: config AND env; the env can only restrict.
  - Push: committed `push_enabled` AND explicit env true. The env alone can never enable push.
- **Required even for beta-only runs:** the database variables and `REDIS_URL`. The shared secrets loader validates `REDIS_URL` for every `main.py` command, although the beta never connects to Redis.
- **Admin push state:** `/admin_pause_push` and `/admin_resume_push` change a durable admin push state. Effective push = hard push switch AND admin state, so an admin command can never exceed the hard switch.
- **Admin D7 state:** `/admin_d7_on` and `/admin_d7_off` change a durable owner state that defaults off. The D7 line is shown only when that state is on and `regime_d7.enabled` is true. See the D7 section for the sanity SQL.
- **Push OFF scope:** turning push off does not stop the tape, the detector or outcome tracking.

## Soak (7 days, push disabled)

1. Set `BETA_ENABLED=1` in `.env`. The committed config stays `beta.enabled: false`. During the soak `push_enabled` was `false`; since 2026-10-01 it is `true` (see Live push), so keep `BETA_PUSH_ENABLED` unset for a soak.
2. Run `python -m runtime.beta_bootstrap_runner` until it exits `0`.
3. Enable the detector and outcomes timers. Then either:
   - **With Telegram:** also enable the notify timer and the bot, with only the owner allowlisted; or
   - **No-Telegram shadow soak:** set `BETA_TELEGRAM_ENABLED=0`, leave `BETA_TELEGRAM_BOT_TOKEN` empty, and do not enable the notify timer or the bot.
4. Check `--beta-status` (soak metrics) and `--beta-health` (alerts) daily.

### No-Telegram shadow-soak mode

`BETA_TELEGRAM_ENABLED=0` is accepted only while push is off and no beta bot token is set; otherwise every beta command fails with a configuration error. In this mode:
- `--beta-health` does not report `BOT_RECEIVER_DOWN` or `NOTIFIER_NOT_RUNNING`, because Telegram is deliberately absent.
- `--beta-notify-once` returns `TELEGRAM_DISABLED` without doing anything.
- `runtime.beta_bot` exits without starting.

All other health alerts (ingestion, detector, materialization, outcomes, delivery) are unchanged. With Telegram enabled (the default), the bot and notifier liveness checks apply exactly as before.

The gate criteria are listed in the restart decision.

## Live push (owner decision 2026-10-01)

The committed config now has `beta.push_enabled: true`. This is the hard allow only. Push is effective only when all three hold:
- `beta.push_enabled: true` (committed);
- `BETA_PUSH_ENABLED=true` in `/opt/signalbot/.env` (unset, empty or `0` forbids push);
- the durable admin state is not paused (`/admin_resume_push`; a missing row counts as resumed).

**Recipients:** every `ACTIVE` beta user. While only the owner has joined, this is the owner-only live push of the rollout. Do not hand out invite codes until the owner has seen real pushes.

**Limits:** at most `max_new_pushes_per_utc_day` = 2 new pushes per UTC day (3 in V0.2), `same_event_cooldown_min` = 20, `push_policy.global_cooldown_min` = 60 across event types, quiet hours 23:00–07:00 Kyiv, nothing older than `delivery_ttl_s` = 600 s, and only hours that pass the unusual-hour gate (see the Product-first V1 section). D7 and readiness changes never push.

**Enable:**
1. From the owner account, send `/admin_pause_push` before touching `.env`. A missing admin row counts as resumed, so without this step push starts at the first restart.
2. Add `BETA_PUSH_ENABLED=true` to `/opt/signalbot/.env`. The detector and notify timers read `.env` on every run, so the env change applies within a minute; the bot needs a restart.
3. Deploy and restart as usual (pull, schema init, restart the bot, timers keep running).
4. Check `/admin_health`: switches show `'BETA_PUSH_ENABLED': True`. Check `/admin_status`: `push effective False` (paused).
5. Send `/admin_resume_push`. The reply must say effective push is on.

**Stop:** `/admin_pause_push` stops new deliveries at once, without a restart. Pending deliveries are suppressed with `PUSH_DISABLED`. For a hard stop, set `BETA_PUSH_ENABLED=0` and restart the bot and the notify timer.

## Owner health alerts

`--beta-notify-once` evaluates `--beta-health`. When a bot token and owner id are configured, it sends one owner alert per alert key, rate-limited by `health.owner_alert_repeat_s`. The alert keys are:
- `INGESTION_STALE`
- `DETECTOR_NOT_ADVANCING`
- `MATERIALIZATION_FAILURE`
- `OUTCOME_TRACKER_NOT_ADVANCING`
- `BOT_RECEIVER_DOWN`
- `NOTIFIER_NOT_RUNNING`
- `DELIVERY_FAILURE_SPIKE`
- `D7_HOUR_STATE_STALE` (only while `regime_d7.enabled` is true, and only when the newest hour state's `available_at` is older than 70 minutes; independent of `/admin_d7_on`)
- `STAGE1_RECOVERY_NOT_READY` (the detector has waited for Stage-1's startup recovery for at least `health.detector_stall_s`, or proceeded without it as `OVERDUE`; see "Startup recovery" below)
- `STARTUP_RECOVERY_REPAIR_INCOMPLETE` (the post-recovery repair failed on a bucket or deferred buckets to the next run)

A DB outage makes every beta command exit with status 2 and report `DB_UNAVAILABLE`. systemd records that as a failed unit.

## Privacy (personal data)

- **Where personal data lives:** Telegram user and chat ids exist in `beta_allowlist` and `beta_users`. `beta_waitlist` stores a Telegram id and `requested_at` only after the person presses the request-access button. `beta_notification_deliveries`, `beta_feedback`, `beta_feedback_messages`, and `beta_user_activity` reference a person through `user_pk` only.
- **`beta_user_activity`:** one row per command, button, or delivered push (`action`, optional `detail`, `lang`, `at`). No Telegram id, no chat id, no message text. Kept for `telemetry.retention_days` (120), then purged. `/delete_me` deletes the user row and the activity rows cascade.
- **`beta_feedback_messages`:** free text from `/feedback` (`text`, `lang`, `created_at`) keyed by `user_pk`. This is not the Useful/Noise table `beta_feedback`. At most `feedback.max_chars` (1000) characters and `feedback.max_per_utc_day` (5) stored messages per user per UTC day. Rows older than `telemetry.retention_days` (120) are purged by the notifier retention job. `/delete_me` deletes them through `ON DELETE CASCADE`. A copy is forwarded to the owner's private chat as a fingerprint, language, Kyiv time, and the text. The forward does not contain the Telegram id. The audit row for `/admin_reply` stores the fingerprint only, not the reply text.
- **`beta_invites`:** invite codes and labels. Not user ids. `beta_allowlist.invite_code` and `beta_users.invite_code` remember which code admitted the person. Codes are revoked, not deleted.
- **Rejected `/start`:** when `BETA_TELEMETRY_SALT` is set, a row is `(utc_day, HMAC-SHA256(salt, telegram id))`. When the salt is unset, the day stores a count only. The raw id is never stored. Purged after `telemetry.rejected_start_retention_days` (30).
- **What never holds ids:** the tape, episode, transition, outcome, push-decision, `beta_btc_views`, `beta_details_opens`, and audit tables hold no Telegram identifiers. Audit rows store pseudonymous fingerprints only. The owner waitlist view is the exception that shows ids to the owner.
- **Database backups contain personal data.** Treat backup files and offsite copies accordingly (`deploy/backup.sh`).
- **`/stop`** pauses messages.
- **`/delete_me`** deletes the user row, the allowlist entry, and the waitlist row. Feedback and activity rows cascade. Delivery rows keep only an anonymous `NULL` user.
- **Retention:** stopped users are purged automatically after `privacy.stopped_user_retention_days` (30).
- **Logs:** never contain a raw Telegram id, chat id or token.
