# Research Evidence Integration — production deploy plan V1

**Status:** PLAN ONLY (2026-10-04). Nothing here has been run on production. Owner go is required for every step that changes production.

| Item | Value |
| --- | --- |
| Code | `main` at `423b9b8` (merge of PR #326; head `02919af`) plus the prerequisites PR from branch `claude/research-evidence-deploy-plan` (PREREQ-1–3, §G) |
| PREREQ-1–3 | **RESOLVED** in that PR, proven by the tests named in §G. The PR is open and not merged. |
| Units `signalbot-beta-feeds` / `signalbot-beta-stress` | not enabled |
| P3 prospective confirmation | not started |
| CI | GitHub Actions has not run since `02919af` (billing block). The only validation is local; see §0. |

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

Prerequisites PR (PREREQ-1–3), on a local PostgreSQL 16 and committed as tests:

| Check | Result |
| --- | --- |
| The core role applies the schema; `deploy/beta_feeds_role.sql` applied twice; both jobs run as `signalbot_beta_feeds` | OK. Rows in all five feed tables. Health recorded. Readiness `OK`. `statement_timeout` is `1min`. |
| The feed role tries DDL, other tables, writes outside its grants, `SET ROLE`, or granting itself | All 23 attempts denied. `apply_beta_schema` under the role fails. The catalog is byte-identical before and after. |
| Readiness: no schema; a dropped check and column; a revoked grant; the wrong role | Each is refused (`SCHEMA_NOT_READY` / `WRONG_DB_ROLE`) before any fetch. Nothing is written. The CLI exits 3. |
| Feed commands with presentation off (config, or env `BETA_RESEARCH_EVIDENCE_ENABLED=0`) | Both collectors run, insert and record health. |
| Decision block with presentation on, off by env, and off by config | Byte-identical JSON except `evidence`. `evidence` is absent when off. |
| `run_market_alerts` with presentation on and off (two identical databases) | Same report, alert rows, decisions, suppression reasons and tracked forecasts. Only the payload `evidence` differs. |
| Bot with presentation off | No 🔬 line, no research button. A stored view's research tab is refused, and no open is recorded. |
| `deploy/install_beta_feeds_role.sh` against the local cluster (`docker` replaced by `psql`) | Idempotent over three runs. The env file is `root:root 0600` with exactly six keys. The password is never printed. Login as the role works. |
| `SIGNALBOT_DOTENV=0` | `common.config` does not load the shared `.env`. Default unchanged. |

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

### A.2 Role SQL and install script (in the repo)

- **`deploy/beta_feeds_role.sql`** is idempotent. It runs as the core DB superuser in the beta database, after the core role has applied the schema. On every run it:
  - creates the role if it is missing;
  - sets LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOINHERIT, NOREPLICATION, NOBYPASSRLS, `CONNECTION LIMIT 4`, `statement_timeout = 60s` and `idle_in_transaction_session_timeout = 60s`;
  - removes any role membership;
  - **revokes everything** on the schema's tables, sequences, schema and database;
  - grants exactly the §A.1 set.

  The script ends with assertions that roll the whole change back if the role could still:
  - create in `public` or in the database;
  - hold DELETE, TRUNCATE, REFERENCES or TRIGGER anywhere;
  - reach any other table (for example through a grant to PUBLIC);
  - read any `beta_hist_oi_5m` column other than `ts`, `oi_base` and `ls_account_ratio`.

  It holds no password.
- **`deploy/install_beta_feeds_role.sh [--set-password]`** runs on the host as root.
  - It reads `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_HOST` and `POSTGRES_PORT` from the core `.env` with `grep`. The file is never sourced or printed.
  - It refuses to run unless the seven tables exist.
  - It applies the SQL through `docker exec … psql`.
  - With `--set-password`, it generates `openssl rand -hex 24`, sets it through **stdin** (not visible in a process list), and writes `/opt/signalbot/.env.beta-feeds` (§A.3).
  - It never enables, starts or restarts a unit.

Before the first `--set-password`, confirm that statements are not logged:

```bash
docker exec btcbot_timescaledb psql -U "$SU" -d "$DB" -tAc 'SHOW log_statement'   # must be none
```

**After every restore,** run `sudo deploy/install_beta_feeds_role.sh` again, without `--set-password`. `deploy/backup.sh` dumps with `--no-owner --no-privileges`, so grants are not restored; the role itself is cluster-level and survives. Until this is done, the feed jobs refuse to run with `SCHEMA_NOT_READY` (`grant:…`) and exit 3. They never run with wider rights.

### A.3 Feed environment file

`/opt/signalbot/.env.beta-feeds` is written by the install script as `root:root 0600`. systemd reads it as root for the two feed units only, so neither the bot nor the feed processes can read it from disk. The template is `deploy/beta-feeds.env.example`; `.gitignore` (`.env.*`) keeps the real file out of git. It holds **only**:

```
POSTGRES_HOST=<from .env, default 127.0.0.1>
POSTGRES_PORT=<from .env, default 5432>
POSTGRES_DB=<same as .env>
POSTGRES_USER=signalbot_beta_feeds
POSTGRES_PASSWORD=<generated>
BETA_ENABLED=<same value as .env, when set there>
```

It never contains:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`;
- `BETA_TELEGRAM_BOT_TOKEN`, `BETA_OWNER_TELEGRAM_USER_ID`;
- `BETA_PUSH_ENABLED`;
- the core `POSTGRES_PASSWORD` or `POSTGRES_DSN`.

`REDIS_URL` (a placeholder that `load_secrets()` requires; beta commands never connect to Redis) and `BETA_FEEDS_EXPECTED_DB_ROLE` are set in the units, not in this file.

### A.4 Unit wiring (in the repo)

`deploy/signalbot-beta-feeds.service` and `deploy/signalbot-beta-stress.service`:

```ini
EnvironmentFile=/opt/signalbot/.env.beta-feeds          # no "-": a missing file fails the unit
Environment=SIGNALBOT_DOTENV=0                           # common/config.py does not load the shared .env
InaccessiblePaths=-/opt/signalbot/.env                   # the shared .env is not even visible in the unit
Environment=BETA_FEEDS_EXPECTED_DB_ROLE=signalbot_beta_feeds
Environment=REDIS_URL=redis://unused.invalid:6379/0
```

Why the dotenv switch is needed: `common/config.py` used to call `load_dotenv(ROOT_DIR / ".env")` on import. With only `EnvironmentFile=` changed, the feed process would still have loaded `/opt/signalbot/.env`, getting the Telegram tokens and the owner id. If that file sets `POSTGRES_DSN`, the process would also have connected **as the core role**, because `_build_postgres_dsn()` prefers `POSTGRES_DSN`. `SIGNALBOT_DOTENV=0` turns the load off for these units only; every other process behaves as before.

**No fallback to the core role.** If the connected role is not `signalbot_beta_feeds`, the job refuses with `WRONG_DB_ROLE` and exits 3. That covers a stray `POSTGRES_DSN` or a hand-edited env file. `wait_for_infra.py --postgres-only` connects as the feed role (`SELECT 1`), which is enough.

### A.5 Read-only schema readiness (PREREQ-1)

The feed commands no longer call `init_beta_v0_schema()`. Before any fetch or write, each job reads the catalog through `beta/research_feeds.feed_schema_readiness`. It checks, per job:
- the tables and columns it uses;
- the primary keys its `ON CONFLICT` needs;
- `ck_beta_feed_depth_cover` and `ck_beta_feed_stress_ok`;
- the table and column privileges of the connected role;
- the expected role.

If anything is missing, the job returns `SCHEMA_NOT_READY` or `WRONG_DB_ROLE` with the missing items, writes nothing, logs the reason, and the CLI exits 3, so the unit fails visibly. Creating and migrating the schema stays with the core role.

## B. Schema

Everything lives in `storage/beta_v0_schema.sql`. It is applied by `storage/beta_v0_store.apply_beta_schema` as **one script in one transaction**, under `pg_advisory_xact_lock(hashtext('beta_v0_schema_init'))`. That function is called through `Database.init_beta_v0_schema()` by:
- the beta bot at start-up (`runtime/beta_bot.py`);
- every writing `--beta-*` CLI command.

The feed commands are **not** among them (PREREQ-1). They only verify the schema (§A.5).

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
| Env | `/opt/signalbot/.env.beta-feeds` only. The shared `.env` is not loaded (`SIGNALBOT_DOTENV=0`) and not visible (`InaccessiblePaths`). §A.3–A.4. | same |
| DB role | `signalbot_beta_feeds` (§A.2), enforced by `BETA_FEEDS_EXPECTED_DB_ROLE` | same |
| Schema | verified read-only before each run (§A.5); a refusal means exit 3 and nothing written | same |
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
   - Before restarting anything, run on the host venv: `python -m pytest -q tests/beta/test_research_evidence.py tests/research/test_research_evidence_parity.py tests/deploy/test_beta_systemd.py`. These need no DB.
   - **Presentation off:** add `BETA_RESEARCH_EVIDENCE_ENABLED=0` to `/opt/signalbot/.env` (PREREQ-2).
     - The committed `decision.research_evidence.enabled: true` stays.
     - The env can only switch presentation off; the collectors never read it.
     - From the restart on, no surface shows live research evidence and no alert records it.
     - The registry `/research` list and its «Проверено: …» context line predate PR #326 and are not part of this switch.
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

   All five must be non-null and `ls_col = 1`. Then create the role and the env file:

   ```bash
   sudo deploy/install_beta_feeds_role.sh --set-password
   sudo stat -c '%U:%G %a %n' /opt/signalbot/.env.beta-feeds    # root:root 600
   ```
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
4. **Enable the feeds** (owner go). This is collection only; presentation is still off.

   A refused run (`SCHEMA_NOT_READY` / `WRONG_DB_ROLE`, exit 3) appears in `journalctl -u signalbot-beta-feeds` with the missing items.

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
   - Remove `BETA_RESEARCH_EVIDENCE_ENABLED=0` from `/opt/signalbot/.env`.
   - `sudo systemctl restart signalbot-beta-bot.service`. The notify and detector one-shots read the env on their next run.
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
2. **Feed role and health.** First, confirm that the units run as the feed role and with the feed env only:
   ```bash
   systemctl show signalbot-beta-feeds -p EnvironmentFiles -p InaccessiblePaths
   journalctl -u signalbot-beta-feeds -n 3 --no-pager      # last report "status": "OK" (not SCHEMA_NOT_READY / WRONG_DB_ROLE)
   ```
   ```sql
   SELECT usename, count(*) FROM pg_stat_activity WHERE usename = 'signalbot_beta_feeds' GROUP BY 1;  -- during a run
   ```
   Then health and fresh rows:
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
   import asyncio, json, os
   from datetime import datetime, timezone
   os.environ.pop("BETA_RESEARCH_EVIDENCE_ENABLED", None)   # this check compares the config on/off itself
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
   Pass: `identical: true`, `evidence_error: null`, and `matches` or `unavailable` not both empty, which proves evidence was built. The check covers the corridor, levels, touch probabilities, price, events and analogues, i.e. the whole block except `evidence`. On synthetic data it returns `identical: true`.
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
| F2: evidence display off | `BETA_RESEARCH_EVIDENCE_ENABLED=0` in `/opt/signalbot/.env` (or `decision.research_evidence.enabled: false`), then `sudo systemctl restart signalbot-beta-bot.service` | No research lines and no research button. The research tab of a view stored earlier is refused too. No alert evidence. Corridors, levels, probabilities, tracked forecasts and push decisions are unchanged (tested). The collectors keep running. |
| F3: feed broken while running | nothing to do | Per-feed exceptions are isolated, health records them, and the evidence for that source goes `unavailable`. `build_decision` and `surface_lines` catch evidence errors. |
| F4: role off | `ALTER ROLE signalbot_beta_feeds NOLOGIN;` (rerunning `deploy/install_beta_feeds_role.sh` restores the grants; `--set-password` restores the login) | The feed units fail at `wait_for_infra`. The bot reads the tables as the core role and is unaffected. |
| F5: data cleanup (optional) | as the core role: `TRUNCATE beta_feed_metrics_5m, beta_feed_dvol_1h, beta_feed_depth, beta_feed_spot_5m, beta_feed_stress_hours;` | Only the evidence engine reads these tables. |

**Do not roll back the code to before `423b9b8`.** Once anyone has opened the research tab, the old schema file cannot be applied, as §0 showed. It re-adds `ck_beta_details_opens_tab` and `beta_user_activity_action_check` without `research` / `tab_research`. The bot start-up and every beta CLI command would then fail at schema init. `beta_details_opens` is append-only, so the rows cannot simply be deleted.

Use F1/F2 instead. If a code revert is ever needed, it must keep the widened CHECK lists.

## G. Prerequisites and remaining blockers

PREREQ-1–3 are **RESOLVED** in the prerequisites PR (branch `claude/research-evidence-deploy-plan`). It is not merged and needs an owner merge.

| Prerequisite | Change | Proven by |
| --- | --- | --- |
| **PREREQ-1** feed jobs never run DDL | `runtime/beta_cli.py`: the feed branch no longer calls `init_beta_v0_schema()`. `beta/research_feeds.feed_schema_readiness` reads the catalog only (`storage/beta_v0_store.py`: `db_role`, `catalog_tables`, `table_privileges`, `column_privileges`). A refusal returns `SCHEMA_NOT_READY` / `WRONG_DB_ROLE` with nothing written, and the CLI exits 3. | `tests/beta/test_research_feeds_role_pg.py`: `…restricted_role_runs_both_jobs`, `…cannot_run_ddl_reach_other_tables_or_escalate`, `…missing_schema_column_check_grant_or_role_fails_closed_and_writes_nothing`, `…feed_commands_never_initialize_the_schema_and_exit_3_when_refused`; `tests/beta/test_research_evidence.py::test_collection_is_gated_only_by_its_own_flags_and_never_applies_the_schema` |
| **PREREQ-2** collection separate from presentation | The feed commands are gated only by `feeds_enabled` / `stress_hours_enabled` (and `BETA_ENABLED`). `beta/config.research_presentation_enabled` = `decision.research_evidence.enabled` AND `BETA_RESEARCH_EVIDENCE_ENABLED`; the env can only switch it off, and an unrecognised value counts as off. It is read by `beta/decision.research_evidence_block` (the only producer of evidence; alerts and `/levels` derive from it) and by the bot's research tab. One engine; matching unchanged. | `test_the_presentation_env_switch_can_only_turn_presentation_off`, `test_collection_is_gated_only_by_its_own_flags…`, `test_collection_runs_with_presentation_off_and_the_block_is_identical_without_evidence`, `test_presentation_never_changes_a_push_decision_or_a_tracked_forecast`, `test_presentation_off_hides_research_lines_the_button_and_a_stored_research_tab` |
| **PREREQ-3** isolated feed credentials | `deploy/beta_feeds_role.sql`, `deploy/install_beta_feeds_role.sh`, `deploy/beta-feeds.env.example`, both feed units (§A.4), the `common/config.py` dotenv switch, and `deploy/check_beta_units.sh` (env-file owner and mode only). | `tests/deploy/test_beta_systemd.py`: `test_feed_units_read_only_the_feed_env_file_and_never_the_core_env`, `test_no_core_unit_depends_on_the_research_feeds`, `test_feed_role_sql_grants_exactly_what_the_jobs_verify_and_holds_no_secret`, `test_feed_role_install_script_never_activates_and_never_exposes_the_password`, `test_the_shared_env_file_is_not_loaded_when_a_unit_says_so`; `test_research_feeds_role_pg.py::test_the_install_script_applies_the_grants_and_writes_a_private_env_file` |

Known limit: PUBLIC holds TEMPORARY on every database by default, so the feed role can create **session-local temporary** tables. These are not persistent schema and vanish at disconnect. Revoking TEMPORARY from PUBLIC would affect every role and is not part of this plan.

Remaining blockers before production:
- **The prerequisites PR is not merged** (owner).
- **Production facts still to confirm on the host** (§E.1, §E.4):
  - Binance and Deribit reachability (the sandbox gets HTTP 451);
  - the share of depth snapshots covering ±1 %;
  - `log_statement` (§A.2).
- **CI:** GitHub Actions has not run since the billing block. Restore it, or run the tests on the host (§D.1), before the restart.
- **Owner go** for every production step in §D.
