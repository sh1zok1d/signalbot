# Research Evidence Integration — production deploy plan V1

**Status:** PLAN ONLY (2026-10-04). Nothing here has been run on production. Owner go is required for every step that changes production.

| Item | Value |
| --- | --- |
| Code | `main` at `423b9b8` (merge of PR #326; head `02919af`) |
| Units `signalbot-beta-feeds` / `signalbot-beta-stress` | not enabled |
| P3 prospective confirmation | not started |
| CI | GitHub Actions did not run on `02919af` or `423b9b8` (billing block). The only validation is local; see §0. |

Authority:
- `docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md` (design);
- `docs/PRIVATE_BETA_V0_DEPLOY.md` (beta runbook);
- `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md` (product rules).

## 0. What was verified, and how

The checks ran on a local PostgreSQL 16 (no TimescaleDB). Scratch scripts were used and are not committed.

| Check | Result |
| --- | --- |
| Pre-merge schema (`38f97bd`) with 8 352 `beta_hist_oi_5m` rows, then the new schema applied twice | Both applies succeed. All rows kept. `ls_account_ratio` is NULL on every existing row. |
| Least-privilege role (§A.2), schema init | `init_beta_v0_schema` **fails** (`permission denied for schema public`) |
| Least-privilege role (§A.2), feed jobs | `run_feeds_job` OK: no errors, both definition checks `OK`, depth `COVERED`. `run_stress_job` OK. |
| Same role, denied operations | Every one is denied: <br>• reads of `beta_users`, `beta_allowlist`, `beta_invites`, `beta_notification_deliveries`, `klines_1m`, all columns of `beta_hist_oi_5m`; <br>• writes to `beta_push_decisions`, `beta_market_alerts`, `beta_hist_oi_5m`; <br>• DELETE and TRUNCATE on feed tables, UPDATE on `beta_feed_depth`; <br>• CREATE TABLE. |
| Grants after the core role re-applies the schema | Kept |
| Pre-merge schema re-applied after one research-tab row exists | **Fails** (`CheckViolation ck_beta_details_opens_tab`). See §F. |
| Decision block, evidence ON vs OFF, same `now` (synthetic data) | Identical except the `evidence` key |
| Focused tests on `02919af` | `test_research_evidence.py` + `test_research_evidence_pg.py` + `test_research_evidence_parity.py`: 40 passed |
| `fapi.binance.com` from the dev sandbox | HTTP 451 (geo-restricted). Reachability and ±1 % depth coverage must be measured **from the production host** (§E.1, §E.4). |

## A. Database / credential isolation

CodeRabbit proposed a separate DB role and environment for the two feed units. **Recommendation: adopt it.**

The feed units fetch from the internet. Today they would load `/opt/signalbot/.env`, which holds:
- the core DB superuser password;
- both Telegram tokens;
- the owner's Telegram id.

They need none of these.

### A.1 What the feed jobs actually touch (from the code, confirmed by the run in §0)

| Object | Feeds job | Stress job | Privilege |
| --- | --- | --- | --- |
| `beta_feed_metrics_5m` | read last ts, upsert (`ON CONFLICT … COALESCE(existing)`) | — | SELECT, INSERT, UPDATE |
| `beta_feed_dvol_1h` | read last hour, upsert | — | SELECT, INSERT, UPDATE |
| `beta_feed_spot_5m` | read last bar, upsert | — | SELECT, INSERT, UPDATE |
| `beta_feed_depth` | `INSERT … ON CONFLICT DO NOTHING RETURNING 1` | — | SELECT, INSERT (the run showed SELECT is required) |
| `beta_feed_stress_hours` | — | read known hours, upsert only while `INCOMPLETE` | SELECT, INSERT, UPDATE |
| `beta_hist_oi_5m` | definition check reads `ts, oi_base, ls_account_ratio` | — | column SELECT only |
| `beta_runtime_health` | upsert `research_feeds`, `research_feeds_definition` | upsert `research_stress_hours` | SELECT, INSERT, UPDATE |
| advisory locks `7311000008` / `7311000009` | `pg_try_advisory_lock` | same | none needed |

Three things the role never needs:
- **No DELETE, TRUNCATE or DDL.** Neither job issues them.
- **No sequence grants.** None of these tables has a serial column.
- **No access to user, Telegram, delivery, push-decision, Stage-1 or forecast tables.**

The remaining over-grant is `beta_runtime_health`: the role can write any component's row. That table holds only operational health, so the impact is low. Narrowing it to `component LIKE 'research_%'` would take row-level security on a shared table; that is not proposed for V1.

### A.2 Role SQL (exact; run once by the DB superuser)

The role is created without a password inside the script. The password is set from stdin so it never appears in a process list. The script never grants anything on other tables, and default privileges are unchanged, so tables added later are not granted.

```sql
-- deploy step A, as the core DB superuser ($POSTGRES_USER) in database $POSTGRES_DB
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signalbot_beta_feeds') THEN
    CREATE ROLE signalbot_beta_feeds LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION
      CONNECTION LIMIT 4;
  END IF;
END $$;
ALTER ROLE signalbot_beta_feeds SET statement_timeout = '60s';
ALTER ROLE signalbot_beta_feeds SET idle_in_transaction_session_timeout = '60s';
GRANT CONNECT ON DATABASE :"dbname" TO signalbot_beta_feeds;
GRANT USAGE ON SCHEMA public TO signalbot_beta_feeds;
GRANT SELECT, INSERT, UPDATE ON beta_feed_metrics_5m, beta_feed_dvol_1h, beta_feed_spot_5m,
                                 beta_feed_stress_hours TO signalbot_beta_feeds;
GRANT SELECT, INSERT ON beta_feed_depth TO signalbot_beta_feeds;
GRANT SELECT (ts, oi_base, ls_account_ratio) ON beta_hist_oi_5m TO signalbot_beta_feeds;
GRANT SELECT, INSERT, UPDATE ON beta_runtime_health TO signalbot_beta_feeds;
-- must return f (PostgreSQL 15+ default; do not change PUBLIC's rights here)
SELECT has_schema_privilege('signalbot_beta_feeds', 'public', 'CREATE') AS can_create;
```

Commands on the host:

```bash
cd /opt/signalbot
# the feed tables must exist first (step D.2); then:
DB=$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2-); SU=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2-)
docker exec -i btcbot_timescaledb psql -U "$SU" -d "$DB" -v ON_ERROR_STOP=1 -v dbname="$DB" < /path/to/beta_feeds_role.sql
FEEDS_PW="$(openssl rand -hex 24)"
printf "ALTER ROLE signalbot_beta_feeds PASSWORD '%s';\n" "$FEEDS_PW" \
  | docker exec -i btcbot_timescaledb psql -U "$SU" -d "$DB" -v ON_ERROR_STOP=1 -q
```

Before running it, confirm that `log_statement` is `none` or `ddl`-free, so the ALTER ROLE line is not logged:

```bash
docker exec btcbot_timescaledb psql -U "$SU" -d "$DB" -tAc 'SHOW log_statement'
```

Grants are lost after a restore. `deploy/backup.sh` dumps with `--no-owner --no-privileges`, so after any `deploy/restore.sh` re-run the GRANT block above. The role itself is cluster-level and survives.

### A.3 Feed environment file

Create `/opt/signalbot/.env.beta-feeds` with owner `root:signalbot` and mode `0640`. It holds **only**:

```
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=<same as .env>
POSTGRES_USER=signalbot_beta_feeds
POSTGRES_PASSWORD=<FEEDS_PW from A.2>
# required by common.config.load_secrets(); beta commands never connect to Redis — placeholder, no password
REDIS_URL=redis://127.0.0.1:6379/15
BETA_ENABLED=<same value as .env>
```

It must **not** contain:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`;
- `BETA_TELEGRAM_BOT_TOKEN`, `BETA_OWNER_TELEGRAM_USER_ID`;
- `BETA_PUSH_ENABLED`;
- the core `POSTGRES_PASSWORD` or `POSTGRES_DSN`.

### A.4 Unit wiring

This is either a repo change (PREREQ-3) or a systemd drop-in with the same content. The drop-in, applied with `sudo systemctl edit signalbot-beta-feeds.service` (and the same for `signalbot-beta-stress.service`), is:

```ini
[Service]
EnvironmentFile=
EnvironmentFile=/opt/signalbot/.env.beta-feeds
ExecStartPre=
ExecStartPre=/usr/bin/test -x /opt/signalbot/.venv/bin/python
ExecStartPre=/usr/bin/test -r /opt/signalbot/.env.beta-feeds
ExecStartPre=/usr/bin/test -f /opt/signalbot/main.py
ExecStartPre=/opt/signalbot/.venv/bin/python /opt/signalbot/deploy/wait_for_infra.py --postgres-only --timeout 60
```

`wait_for_infra.py --postgres-only` then connects as the feed role (`SELECT 1`), which is enough.

**Blocker (PREREQ-1):** `main.py --beta-feeds-once` / `--beta-stress-once` call `db.init_beta_v0_schema()` (`runtime/beta_cli.py`, feeds/stress branch). Under this role that call fails, as §0 shows. The feed branch must replace it with a read-only readiness check before the role can be used; §G gives the patch. The core role keeps applying the schema.

## B. Schema

Everything lives in `storage/beta_v0_schema.sql`. It is applied by `storage/beta_v0_store.apply_beta_schema` as **one script in one transaction**, under `pg_advisory_xact_lock(hashtext('beta_v0_schema_init'))`. That function is called through `Database.init_beta_v0_schema()` by:
- the beta bot at start-up (`runtime/beta_bot.py`);
- every writing `--beta-*` CLI command.

Today that includes the feed commands; PREREQ-1 removes them.

| Change | Kind |
| --- | --- |
| `beta_hist_oi_5m.ls_account_ratio DOUBLE PRECISION` (nullable, no default) | `ALTER TABLE … ADD COLUMN IF NOT EXISTS` |
| `beta_feed_metrics_5m` (PK `ts`; 5-minute grid CHECK; `ls_account_ratio > 0`; `source = 'binance_futures_data'`) | `CREATE TABLE IF NOT EXISTS` |
| `beta_feed_dvol_1h` (PK `hour_start`; hour grid; OHLC > 0; `source = 'deribit_dvol'`) | `CREATE TABLE IF NOT EXISTS` |
| `beta_feed_depth` (PK `ts`; CHECK `ck_beta_feed_depth_cover`: a side is NULL exactly when its reach < 1 %) | `CREATE TABLE IF NOT EXISTS` |
| `beta_feed_spot_5m` (PK `open_time`; 5-minute grid; `source = 'binance_spot'`) | `CREATE TABLE IF NOT EXISTS` |
| `beta_feed_stress_hours` (PK `hour_start`; status ∈ NOT_STRESS/OK/INSUFFICIENT_TRADES/INCOMPLETE; `ck_beta_feed_stress_ok`) | `CREATE TABLE IF NOT EXISTS` |
| `ck_beta_details_opens_tab` widened by `'research'` | DROP + ADD CONSTRAINT (existing pattern) |
| `beta_user_activity_action_check` widened by `'tab_research'` | DROP + ADD CONSTRAINT (existing pattern) |

- **Indexes:** only the five primary keys (unique btree). No secondary index. No trigger. No sequence.
- **Idempotent:** yes. §0 upgrades from the `38f97bd` schema and then re-applies twice.
- **Downtime:** none.
  - `ADD COLUMN` without a default is a catalog-only change.
  - New tables lock nothing else.
  - The two constraint re-validations take a brief ACCESS EXCLUSIVE lock on `beta_details_opens` and `beta_user_activity` (small tables). They already run on every beta CLI invocation today.
  - Stage-1 (`signalbot.service`) tables are not touched.
- **Fail-closed:** a failed apply rolls back as a whole, and the command that ran it exits with an error.
  - Feed tables that do not exist mean every feed-backed finding is `unavailable` (no data).
  - A failed evidence build sets `evidence.error_type`. `build_decision` and `surface_lines` catch it, so the bot keeps answering without research lines.
- **Rollback:** see §F. The schema stays; a code rollback to before `423b9b8` is **not** safe once the research tab has been opened.

## C. Services

| | `signalbot-beta-feeds` | `signalbot-beta-stress` |
| --- | --- | --- |
| Service | `Type=oneshot`, `main.py --beta-feeds-once --beta-json`, `TimeoutStartSec=240`, user `signalbot`, hardening profile of `signalbot-telegram.service` | `Type=oneshot`, `main.py --beta-stress-once --beta-json`, `TimeoutStartSec=1800`, same user and profile |
| Timer | `OnCalendar=*-*-* *:00/5:40 UTC`, `Persistent=true` | `OnCalendar=*-*-* *:02:00 UTC`, `Persistent=true` |
| Cadence | every 5 min, 40 s after the bar boundary | hourly at HH:02 |
| Env | `/opt/signalbot/.env.beta-feeds` (§A.3) | same file |
| DB role | `signalbot_beta_feeds` (§A.2) | same role |
| Endpoints (public, no key, `User-Agent: signalbot-beta-feeds/1`) | `fapi.binance.com/futures/data/openInterestHist`, `…/futures/data/globalLongShortAccountRatio` (5m), `fapi.binance.com/fapi/v1/depth?limit=1000`, `data-api.binance.vision/api/v3/klines` (5m), `www.deribit.com/api/v2/public/get_volatility_index_data` (3600) | `fapi.binance.com/fapi/v1/klines` (1h), `fapi.binance.com/fapi/v1/aggTrades`, `data-api.binance.vision/api/v3/aggTrades` |
| Timeouts | aiohttp total 30 s per request | aiohttp total 60 s per request |
| Retry | none within a run; the next run continues from the last stored row (metrics from the last label, at most 30 days back; spot at most 3 days; DVOL at most 72 h) | none within a run; the last 6 completed hours are checked every run, and an `INCOMPLETE` hour is retried |
| Rate limit / pacing | 0.2 s between metrics pages. HTTP 418/429 raises `RateLimited` and that feed stops for the run; the other feeds continue. Steady state about 5 requests per run; the first run makes about 36 metrics pages. | perp aggTrades 1.0 s between pages (weight 20), spot 0.25 s; at most 1 500 pages per venue-hour, beyond that the hour is `INCOMPLETE`. Any fetch error marks the hour `INCOMPLETE` and the run ends `PARTIAL`. |
| Failure isolation | one feed's exception never stops the others; advisory lock `7311000008` (a second run returns `BUSY`) | advisory lock `7311000009`; health is recorded on a partial or failed run (`02919af`) |
| Health signal | `beta_runtime_health.research_feeds` (errors per feed) and `research_feeds_definition` (detail per field: `OK`/`PENDING`/`FAILED`, overlap, agree share) | `beta_runtime_health.research_stress_hours` |
| Unit dependencies | ordering only (`After=network-online.target docker.service`); it never starts, stops or requires any other unit | same |

**Known edge (stress).** In an extreme hour that needs close to 1 500 perp pages plus spot pages, the run can approach `TimeoutStartSec=1800`. If systemd kills the run:
- the hour gets no row in that run and is retried on the following runs while it stays within the 6-hour lookback;
- health then shows a stale `last_run_at`;
- the evidence for that hour stays unavailable (fail-closed).

No unit change is proposed for V1; watch for it in the soak.

No unit touches `signalbot.service`, `signalbot-telegram`, `signalbot-shadow`, the detector, outcomes, notify or bot units.

## D. Initialization order (production)

The prerequisites (§G) are merged first. In this order, nothing shows research evidence to a user until step 7.

1. **Update the code.**
   - Check out `main` with the prerequisites at `/opt/signalbot`.
   - `sudo deploy/install_beta_units.sh` copies the units and runs daemon-reload. It enables nothing.
   - No new Python dependency (`requirements*.txt` unchanged since `38f97bd`).
   - Before restarting anything, run on the host venv: `python -m pytest -q tests/beta/test_research_evidence.py tests/research/test_research_evidence_parity.py`. These need no DB.
   - Keep `decision.research_evidence.enabled: false` (display off; PREREQ-2).
2. **Schema.** Apply it as the core role.
   - If `signalbot-beta-bot.service` is active: `sudo systemctl restart signalbot-beta-bot.service`. The bot applies the schema at start-up.
   - Otherwise: `sudo systemctl start signalbot-beta-history.service`. Its first command applies the schema before it syncs.

   Verify:

   ```sql
   SELECT to_regclass('beta_feed_metrics_5m'), to_regclass('beta_feed_dvol_1h'),
          to_regclass('beta_feed_depth'), to_regclass('beta_feed_spot_5m'),
          to_regclass('beta_feed_stress_hours'),
          (SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'beta_hist_oi_5m' AND column_name = 'ls_account_ratio') AS ls_col;
   ```

   All five must be non-null and `ls_col = 1`. Then create the role and env file (§A.2–A.4).
3. **Historical / definition parity sync.** This is needed for DH3-P3 only. Vision rows synced before this release have `ls_account_ratio = NULL`, because the object ledger never re-fetches an `OK` object. Without this step P3 needs about 26 days to mature: `crowd_z` needs at least 600 of the previous 720 hourly values.
   - The step re-queues the **last 35 daily `metrics` objects** (the same Vision objects as before, checksum-verified; no new source).
   - The selector stops at 2026-08-26, so the E1 holdout `[2026-08-16, 2026-08-25 17:20)` cannot be reached. Objects inside it are never planned in any case.

   Dry run (as the core role):

   ```sql
   SELECT count(*), min(object_key), max(object_key) FROM beta_hist_objects
   WHERE kind = 'metrics_daily' AND status = 'OK'
     AND to_date(substring(object_key FROM 'metrics-(\d{4}-\d{2}-\d{2})\.zip$'), 'YYYY-MM-DD')
         BETWEEN GREATEST(current_date - 35, DATE '2026-08-26') AND current_date - 1;
   ```

   It should return 35 rows (35 objects, oldest to newest). Apply:

   ```sql
   BEGIN;
   DELETE FROM beta_hist_objects
   WHERE kind = 'metrics_daily' AND status = 'OK'
     AND to_date(substring(object_key FROM 'metrics-(\d{4}-\d{2}-\d{2})\.zip$'), 'YYYY-MM-DD')
         BETWEEN GREATEST(current_date - 35, DATE '2026-08-26') AND current_date - 1;
   COMMIT;
   ```

   Then re-sync:

   ```bash
   sudo systemctl start signalbot-beta-history.service
   journalctl -u signalbot-beta-history -n 30
   ```

   The sync re-fetches those objects and upserts `ls_account_ratio`. The OI values are the same object bytes, re-verified. Then the build runs.

   Verify:

   ```sql
   SELECT count(*) FROM beta_hist_oi_5m WHERE ls_account_ratio IS NOT NULL AND ts >= now() - interval '35 days';
   ```

   Expect about 288 per day.
4. **Enable the feeds** (owner go). Collection only; display is still off.

   ```bash
   sudo systemctl start signalbot-beta-feeds.service    # first run backfills: metrics ≤30 d, spot 3 d, DVOL 72 h
   sudo systemctl start signalbot-beta-stress.service
   sudo systemctl enable --now signalbot-beta-feeds.timer signalbot-beta-stress.timer
   ```

5. **Wait for mature data.** Times are counted from the first feeds run (T0).

   | Finding(s) | Needs | Ready |
   | --- | --- | --- |
   | DH3-P1, DH3-P2, MARKET-01/02 (OI) | Vision OI history plus REST tail, `oi_base` definition `OK` | first run (30-day REST backfill overlaps Vision) |
   | DH3-P3 (crowd) | `ls_account_ratio` definition `OK` and at least 600 of 720 hourly values | first run after step 3 (otherwise about 26 days) |
   | DH3-O1/O2/O3 (DVOL) | 72 h backfill, 24 h window | first run |
   | DH2-L1, DH2-B2 (spot) | 3-day spot backfill, 1-day baseline | first run |
   | DH3-L2 (book skew) | a **covered** snapshot at most 10 min old at the bar close | first covered snapshot |
   | DH3-L1 (thin book) | at least 120 covered hourly values in the previous 168 h | ≥ 5 days of **covered** snapshots |
   | DH3-L3 (book recovery) | covered snapshots at a sharp move and 6 bars later | first sharp move after T0 |
   | DH3-S1, DH3-S3 (stress) | a stress hour with status `OK` (6 h lookback, no older backfill) | first stress hour after T0 |
   | D2, D7, H02–H05, R03, D12, DH1/DH2 levels, DH3-V*, H01 | bars, Stage-1 1m and the calendar (no feed) | at once |

6. **Check health** with §E.1–E.4. All of the following must hold:
   - `research_feeds` successful in the last 10 min;
   - `research_feeds_definition` shows `oi_base.status = OK` **and** `ls_account_ratio.status = OK`;
   - `research_stress_hours` successful in the last 75 min;
   - fresh-row ages are within the limits in §E.2;
   - E1 count is 0;
   - depth coverage is known.

   Collect for at least 24 h. Recommended: 5 days, so L1 can mature.
7. **Only then is the evidence live.**
   - Set `decision.research_evidence.enabled: true` (a reviewed one-line config change, or the env switch from PREREQ-2).
   - `sudo systemctl restart signalbot-beta-bot.service`. The notify and detector one-shots read the config on their next run.
   - Run the surface smoke (§E.5–E.9).

**Rules that hold at every step** (code; covered by the tests named in §E):
- **P3 and the REST tail.** P3 uses the REST tail only while `research_feeds_definition.ls_account_ratio.status = OK`. Otherwise P3 is `unavailable: DEFINITION_PENDING/FAILED`. Vision-only values are about a day old, so they are `STALE` and never current. Tests: `test_the_rest_tail_is_used_only_after_its_definition_check_passes`, `test_a_stale_or_unchecked_source_is_not_current_evidence`.
- **L1/L2/L3 and depth coverage.** These use only snapshots whose **both** sides reach ±1 % (enforced by the DB CHECK) and that are at most 10 min old at the bar close. A partial sum is never stored. Otherwise the findings are `unavailable: STALE_OR_NOT_COVERED`. Tests: `test_depth_band_is_exact_or_absent_never_partial`, `test_book_states_match_l1_l2_and_a_snapshot_older_than_ten_minutes_is_not_used`.
- **Stale or missing sources.** A stale or missing source makes the finding unavailable with a reason. There is no fallback, no proxy and no forward fill. Freshness limits: OI, ratio, DVOL and depth 75 min; spot 15 min; stress 3 h; 15-minute flow 30 min. Test: `test_a_missing_observable_is_unavailable_never_fabricated`.

## E. Production smoke

Run everything as the core role, read-only, with `psql` in the container or via `systemd-run`.

1. **Reachability**, from the production host:
   ```bash
   for u in https://fapi.binance.com/fapi/v1/ping https://data-api.binance.vision/api/v3/ping \
            "https://www.deribit.com/api/v2/public/get_time"; do curl -sS -o /dev/null -w "%{http_code} $u\n" "$u"; done
   ```
   All must return `200`. A `451` or `403` means the host is geo-restricted, so the feeds cannot run there.
2. **Feed health and fresh rows**:
   ```sql
   SELECT component, last_run_at, last_success_at, last_error_type, detail
   FROM beta_runtime_health WHERE component IN ('research_feeds', 'research_feeds_definition', 'research_stress_hours');

   SELECT 'oi' AS feed, now() - (max(ts) + interval '5 min') AS age FROM beta_feed_metrics_5m WHERE oi_base IS NOT NULL
   UNION ALL SELECT 'ls_ratio', now() - (max(ts) + interval '5 min') FROM beta_feed_metrics_5m WHERE ls_account_ratio IS NOT NULL
   UNION ALL SELECT 'dvol', now() - (max(hour_start) + interval '1 hour') FROM beta_feed_dvol_1h
   UNION ALL SELECT 'depth_covered', now() - max(ts) FROM beta_feed_depth WHERE bid1_usd IS NOT NULL AND ask1_usd IS NOT NULL
   UNION ALL SELECT 'spot', now() - (max(open_time) + interval '5 min') FROM beta_feed_spot_5m
   UNION ALL SELECT 'stress', now() - (max(hour_start) + interval '1 hour') FROM beta_feed_stress_hours;
   ```
   Pass: OI, ratio, DVOL and depth under 75 min; spot under 15 min; stress under 3 h. Both definition fields `OK`.
3. **E1 protected window.** Every count must be 0. The bounds are on row labels, the same rule the feeds apply before storing a row.
   ```sql
   SELECT 'metrics' t, count(*) FROM beta_feed_metrics_5m WHERE ts >= '2026-08-16T00:00Z' AND ts < '2026-08-25T17:20Z'
   UNION ALL SELECT 'dvol', count(*) FROM beta_feed_dvol_1h WHERE hour_start >= '2026-08-16T00:00Z' AND hour_start < '2026-08-25T17:20Z'
   UNION ALL SELECT 'depth', count(*) FROM beta_feed_depth WHERE ts >= '2026-08-16T00:00Z' AND ts < '2026-08-25T17:20Z'
   UNION ALL SELECT 'spot', count(*) FROM beta_feed_spot_5m WHERE open_time >= '2026-08-16T00:00Z' AND open_time < '2026-08-25T17:20Z'
   UNION ALL SELECT 'stress', count(*) FROM beta_feed_stress_hours WHERE hour_start >= '2026-08-16T00:00Z' AND hour_start < '2026-08-25T17:20Z'
   UNION ALL SELECT 'hist_oi', count(*) FROM beta_hist_oi_5m WHERE ts >= '2026-08-16T00:00Z' AND ts < '2026-08-25T17:20Z'
   UNION ALL SELECT 'ledger', count(*) FROM beta_hist_objects
     WHERE object_key ~ '2026-08-(1[6-9]|2[0-5])\.zip$' OR object_key ~ '-2026-08\.zip$';
   ```
4. **Depth coverage**, over 24 h, which decides whether L1/L2/L3 can ever be live:
   ```sql
   SELECT count(*) AS snapshots,
          round(100.0 * count(*) FILTER (WHERE bid1_usd IS NOT NULL AND ask1_usd IS NOT NULL) / nullif(count(*), 0), 1) AS covered_pct,
          percentile_disc(0.5) WITHIN GROUP (ORDER BY least(bid_reach_pct, ask_reach_pct)) AS median_min_reach_pct
   FROM beta_feed_depth WHERE ts > now() - interval '24 hours';
   ```
   L1 needs about 72 % or more of hour closes covered (120 of 168). If coverage is lower, L1/L2/L3 stay `unavailable: STALE_OR_NOT_COVERED`. That is correct fail-closed behaviour, not a bug. Report it to the owner; do not substitute a proxy.
5. **Evidence ON/OFF identity** (read-only).

   Run command:
   ```bash
   sudo systemd-run --quiet --wait --pipe --uid=signalbot --gid=signalbot -p WorkingDirectory=/opt/signalbot \
     -p EnvironmentFile=/opt/signalbot/.env /opt/signalbot/.venv/bin/python - < evidence_onoff_check.py
   ```

   `evidence_onoff_check.py`:
   ```python
   import asyncio, json
   from datetime import datetime, timezone
   from beta.config import BetaConfig
   from beta.decision import build_decision, reset_cache
   from runtime.beta_cli import load_postgres_dsn
   from storage.db import Database

   async def main():
       cfg = BetaConfig.load(); dec = cfg.section("decision")
       on = cfg.with_overrides(decision={**dec, "research_evidence": {**dec["research_evidence"], "enabled": True}})
       off = cfg.with_overrides(decision={**dec, "research_evidence": {**dec["research_evidence"], "enabled": False}})
       db = Database(load_postgres_dsn()); await db.connect(); now = datetime.now(timezone.utc)
       try:
           async with db.beta_store().connect() as conn:
               reset_cache(); a = await build_decision(conn, on, now=now)
               reset_cache(); b = await build_decision(conn, off, now=now)
       finally:
           await db.close()
       diff = sorted(k for k in set(a) | set(b) if k != "evidence" and a.get(k) != b.get(k))
       ev = a.get("evidence") or {}
       print(json.dumps({"identical": not diff, "differs": diff, "evidence_error": ev.get("error_type"),
                         "matches": [m["finding_id"] for m in ev.get("matches", [])],
                         "unavailable": {u["finding_id"]: u["reason"] for u in ev.get("unavailable", [])}},
                        ensure_ascii=False, default=str))
   asyncio.run(main())
   ```
   Pass: `identical: true` and `evidence_error: null`. The check covers the corridor, levels, touch probabilities, price, events and analogues, i.e. the whole block except `evidence`. On synthetic data it returns `identical: true`.
6. **Push decision identity.**
   - `python -m pytest -q tests/beta/test_research_evidence.py -k "push_decision or decision_block_numbers"` on the host venv.
   - Then compare `main.py --beta-status --beta-json` → `push_decisions` for the 7 days before and after step 7. Alert evidence is attached after the decision (`beta/market_alerts.py`: "text context only"), so the counts per decision reason must not shift because of it.
   - `SELECT count(*) FILTER (WHERE payload ? 'evidence') FROM beta_market_alerts WHERE recorded_at > <step 7>` shows the evidence is recorded.
7. **`/btc`** (owner account):
   - At most 2 lines starting with 🔬, each ending with `(ID)`.
   - The wording matches the status:
     - DISCOVERY: «Гипотеза (найдено на истории, не подтверждено)»;
     - WEAK: «…ниже нашего порога значимости»;
     - NOT_CONFIRMED: «Историческая проверка эффекта не нашла»;
     - SIDE_FINDING: «Побочный результат проверки».
   - Only CONFIRMED (D2, D7) may say «Проверено».
   - No line from a finding listed as unavailable.
   - No trade call.
8. **`/risk` and `/levels`.**
   - `/risk` shows only range topics (D7, D2, P1, O1/O2, L1/L3, S1/S3, R03-C1, P2), each at most once.
   - `/levels` shows at most one «🔬 Если цена дойдёт сюда: …» line per zone.
   - The corridor and touch-probability numbers equal those in the step-5 script's output.
9. **Details.**
   - «🔬 Исследования» opens «Исследования к рынку сейчас».
   - Every match carries its comparator, N, replication and limits.
   - A vetoed match is marked «Не используется».
   - «Не проверить сейчас» lists the unavailable findings with their reasons.
   - Then check:
     ```sql
     SELECT count(*) FROM beta_details_opens WHERE tab = 'research';
     SELECT count(*) FROM beta_user_activity WHERE action = 'tab_research';
     ```
     Both counts must be ≥ 1.
10. **Stale-source suppression** (during the soak only).
    - `sudo systemctl stop signalbot-beta-feeds.timer` for 80 min.
    - Then run the step-5 script. DH3-P1/P2/P3, O*, L* and the MARKET-01/02 tail must appear under `unavailable` with `STALE` (or a `DEFINITION_*` reason), and `/btc` must show no line for them.
    - `sudo systemctl start signalbot-beta-feeds.timer`. The next run catches up.

## F. Rollback

The bot keeps running without research evidence at every level below. No level stops or restarts `signalbot.service` (Stage-1), the telegram or shadow units, or the detector, outcomes or notify units.

| Level | Action | Effect |
| --- | --- | --- |
| F1: feeds off | `sudo systemctl disable --now signalbot-beta-feeds.timer signalbot-beta-stress.timer` | No more fetches. After 15 min (spot), 75 min (OI, ratio, DVOL, depth) and 3 h (stress), the feed findings become `unavailable: STALE`. History findings stay. The bot is unaffected. |
| F2: evidence display off | `decision.research_evidence.enabled: false` (or the PREREQ-2 env switch `BETA_RESEARCH_EVIDENCE_ENABLED=0`), then `sudo systemctl restart signalbot-beta-bot.service` | No research lines, no research tab content, no alert evidence. Corridors, levels, probabilities and push decisions are unchanged (§E.5–E.6). |
| F3: feed broken while running | nothing to do | Per-feed exceptions are isolated, health records them, and the evidence for that source goes `unavailable`. `build_decision` and `surface_lines` catch evidence errors. |
| F4: role revoke | `REVOKE ALL ON beta_feed_metrics_5m, beta_feed_dvol_1h, beta_feed_depth, beta_feed_spot_5m, beta_feed_stress_hours, beta_runtime_health FROM signalbot_beta_feeds; REVOKE SELECT (ts, oi_base, ls_account_ratio) ON beta_hist_oi_5m FROM signalbot_beta_feeds; ALTER ROLE signalbot_beta_feeds NOLOGIN;` | The feed jobs fail. The bot reads the tables as the core role and is unaffected. |
| F5: data cleanup (optional) | as the core role: `TRUNCATE beta_feed_metrics_5m, beta_feed_dvol_1h, beta_feed_depth, beta_feed_spot_5m, beta_feed_stress_hours;` | Only the evidence engine reads these tables. |

**Do not roll back the code to before `423b9b8`.** Once anyone has opened the research tab, the old schema file cannot be applied, as §0 showed. It re-adds `ck_beta_details_opens_tab` and `beta_user_activity_action_check` without `research` / `tab_research`. The bot start-up and every beta CLI command would then fail at schema init. `beta_details_opens` is append-only, so the rows cannot simply be deleted.

Use F1/F2 instead. If a code revert is ever needed, it must keep the widened CHECK lists.

## G. Blockers / prerequisites (code; not done — needs owner go)

- **PREREQ-1: the feed commands must not run DDL.** It blocks the DB role isolation in §A.
  - In `runtime/beta_cli.py`, in the `--beta-feeds-once` / `--beta-stress-once` branch, replace `await db.init_beta_v0_schema()` with a read-only check. The check returns `{"status": "SCHEMA_NOT_READY"}` unless the five `beta_feed_*` tables and `beta_hist_oi_5m.ls_account_ratio` exist (`to_regclass` / `information_schema`).
  - Add a PG test that runs both jobs under a role created with the §A.2 grants.
- **PREREQ-2: separate collection from display.** It blocks the order in §D (collect before display).
  - Today the feed commands return `DISABLED` unless `research_evidence.enabled` **and** their own flag are true. With display off, nothing can be collected.
  - Proposal: gate the feed commands only by `feeds_enabled` / `stress_hours_enabled`.
  - Add a restrict-only env switch `BETA_RESEARCH_EVIDENCE_ENABLED`, read where `enabled` is read: `beta/decision.research_evidence_block` is the only reader. Alert evidence and the `/levels` zone lines come from that block, so they turn off with it. This mirrors the existing `BETA_DETECTION_ENABLED` pattern: the env can only restrict.
  - Ship with `enabled: false`; step 7 flips it.
  - Without PREREQ-2, display starts at the code update. History findings show at once and feed findings stay `unavailable` until mature. That is still fail-closed, but it is not the requested order.
- **PREREQ-3: units read `/opt/signalbot/.env.beta-feeds`** (repo change to the two `.service` files, or the §A.4 drop-ins). Also add the role SQL as `deploy/beta_feeds_role.sql`.
- **Production facts still to confirm on the host** (§E.1, §E.4):
  - Binance and Deribit reachability (the sandbox gets HTTP 451);
  - the share of depth snapshots covering ±1 %;
  - `log_statement` (§A.2).
- **CI:** GitHub Actions has not run since the billing block. Restore it, or run the tests on the host (§D.1), before the restart.
