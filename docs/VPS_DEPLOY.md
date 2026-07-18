# VPS Deployment — BTC Signal Bot (stage 1, 3-exchange MVP)

Deploy from tag **`stage1-three-exchanges`**. Architecture: infra
(TimescaleDB + Redis) runs in Docker (managed by an admin); the bot runs on the
**host** under systemd as an unprivileged `signalbot` user. Postgres and Redis
are bound to **127.0.0.1 only** — never exposed publicly.

Stage 1 = ingestion + backfill + storage only. No `signal_engine` /
`percentile_engine` yet.

---

## 1. Python version

- **Tested on:** Python 3.14.4 (dev box, Ubuntu 26.04).
- **Recommended for a VPS:** **Python 3.12 on Ubuntu 24.04 LTS.** All pinned
  dependencies (`aiohttp`, `websockets`, `asyncpg`, `numpy`, `pandas`) ship
  manylinux **cp312** binary wheels — verified — so `pip install` needs no build
  toolchain. cp310 (Ubuntu 22.04) wheels also exist. Stage-1 code uses only
  Python ≥ 3.10 syntax.
- Do NOT rely on the system Python for the venv beyond creating it; the venv
  pins everything from `requirements.txt`.

## 2. Prerequisites (as admin / sudo)

```bash
# Docker engine + compose plugin
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 python3.12 python3.12-venv git
sudo systemctl enable --now docker

# Dedicated unprivileged service user (NOT added to the docker group)
sudo useradd --system --home-dir /opt/signalbot --shell /usr/sbin/nologin signalbot
```

No `postgresql-client` / `redis-tools` are required on the host: the service's
readiness gate (`deploy/wait_for_infra.py`) does a real `SELECT 1` / Redis
`PING` using the venv's own `asyncpg`/`redis` libraries. For ad-hoc admin DB
checks you can always use the container tools, e.g.
`sudo docker exec btcbot_timescaledb pg_isready -U btcbot`.

## 3. Get the code (at the release tag)

```bash
sudo mkdir -p /opt/signalbot
sudo chown signalbot:signalbot /opt/signalbot
sudo -u signalbot git clone <REPO_URL> /opt/signalbot
cd /opt/signalbot
sudo -u signalbot git fetch --tags
sudo -u signalbot git checkout stage1-three-exchanges
```

## 4. Configure secrets (.env)

```bash
# Create/edit .env as root (the signalbot user only needs to READ it).
sudo cp /opt/signalbot/.env.example /opt/signalbot/.env
PW="$(openssl rand -hex 24)"
sudo sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${PW}/" /opt/signalbot/.env
# Ownership: root owns it, signalbot reads via group, others cannot.
sudo chown root:signalbot /opt/signalbot/.env
sudo chmod 640 /opt/signalbot/.env
```

**Single source of truth:** the DB connection is assembled from discrete
components — `POSTGRES_HOST/PORT/USER/PASSWORD/DB`. docker compose and the bot
both read the same `POSTGRES_*` variables, so the password lives **once**
(`POSTGRES_PASSWORD`). The bot URL-encodes the password when building its DSN,
so special characters are safe. (An explicit `POSTGRES_DSN` override exists for
advanced use; if you set it, percent-encode the password yourself.)

`.env` is gitignored; ownership `root:signalbot`, mode `640`.

> **Important — when POSTGRES_PASSWORD takes effect.** `POSTGRES_PASSWORD` is
> applied by the Postgres image **only on first creation of an empty data
> volume** (first `docker compose up` with a fresh `timescale_data`). Changing
> the value in `.env` for an **existing** database does NOT change the Postgres
> role's password — the app would then fail to authenticate. To rotate the
> password on a live DB:
> 1. Change it inside Postgres first:
>    `sudo docker exec -it btcbot_timescaledb psql -U btcbot -d postgres -c "ALTER ROLE btcbot WITH PASSWORD 'NEW_STRONG_PW';"`
> 2. Update `POSTGRES_PASSWORD` in `.env` to the same value.
> 3. Restart the bot: `sudo systemctl restart signalbot` (compose does not need
>    to recreate the container; the running Postgres already has the new password).
> Take a backup (§10) before rotating.

## 5. Bring up infra (admin) + verify healthchecks

```bash
cd /opt/signalbot
# Validate the compose file WITHOUT printing it — plain `docker compose config`
# interpolates .env and would echo POSTGRES_PASSWORD to the terminal/logs.
sudo docker compose config --quiet && echo "compose OK"
sudo docker compose up -d
# Wait until both are healthy:
sudo docker compose ps          # STATUS should show "healthy"
sudo docker inspect --format '{{.Name}} {{.State.Health.Status}}' \
  btcbot_timescaledb btcbot_redis
```

Ports are bound to `127.0.0.1` only. To confirm bindings without revealing
secrets, check the listeners instead of dumping the config:
`sudo ss -tlnp | grep -E '5432|6379'` (must show `127.0.0.1`, never `0.0.0.0`).
Never run a plain `docker compose config` on a box where the output could be
logged — it prints the interpolated password.

## 6. Python venv + dependencies

```bash
sudo -u signalbot python3.12 -m venv /opt/signalbot/.venv
sudo -u signalbot /opt/signalbot/.venv/bin/pip install --upgrade pip
sudo -u signalbot /opt/signalbot/.venv/bin/pip install -r /opt/signalbot/requirements.txt
```

## 7. First run: backfill then validate

```bash
cd /opt/signalbot
sudo -u signalbot .venv/bin/python main.py --backfill-only     # idempotent
sudo -u signalbot .venv/bin/python main.py --validate          # read-only report
```

Expected in `--validate`: active exchanges **binance, bybit, okx**; per-metric
coverage building toward **3/3** once live; Bitget listed under **DISABLED
EXCHANGES** (data retained, not ingested).

## 8. Install & start the service

```bash
sudo cp /opt/signalbot/deploy/signalbot.service /etc/systemd/system/signalbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now signalbot
systemctl status signalbot
```

The unit waits for infra (`deploy/wait_for_infra.py` — a real `SELECT 1` /
Redis `PING` via the venv, no docker access needed) before starting, runs as
`signalbot`, `Restart=always`, and is hardened (`ProtectSystem=strict` with no
writable paths — the bot writes nothing to disk; logs go to journald).

Only AFTER the new service is confirmed running may you remove the deprecated
`deploy/btc-signal-bot.service` (do not install it).

## 9. Validate / logs

```bash
# Read-only validation report (safe anytime)
sudo -u signalbot /opt/signalbot/.venv/bin/python /opt/signalbot/main.py --validate

# Bot logs (journald)
journalctl -u signalbot -f
journalctl -u signalbot --since "1 hour ago"

# Infra logs
sudo docker compose -f /opt/signalbot/docker-compose.yml logs -f timescaledb redis
```

## 10. Backup / restore PostgreSQL (admin)

Backups are an **admin** task (needs docker access); the `signalbot` user has
none by design.

```bash
# One-off backup -> /opt/signalbot/backups/btcbot_<ts>.sql.gz (private, gzip'd, keeps 7)
sudo /opt/signalbot/deploy/backup.sh

# Daily cron (root):  15 3 * * *  /opt/signalbot/deploy/backup.sh >> /var/log/signalbot-backup.log 2>&1

# Verify a dump is restorable (restores into a throwaway DB, checks, drops it)
sudo /opt/signalbot/deploy/restore.sh --self-test

# Restore a dump into a NEW inspection DB (never touches live)
sudo /opt/signalbot/deploy/restore.sh /opt/signalbot/backups/btcbot_<ts>.sql.gz

# Restore OVER the live DB (guarded: stop service first, type confirmation)
sudo systemctl stop signalbot
sudo /opt/signalbot/deploy/restore.sh --force-live /opt/signalbot/backups/btcbot_<ts>.sql.gz
sudo systemctl start signalbot
```

**Off-site copies:** local backups only protect against DB corruption, not loss
of the VPS. Periodically copy `backups/` off the box, e.g.:
```bash
rsync -avz /opt/signalbot/backups/ user@backup-host:/srv/signalbot-backups/
```

## 11. Update via Git

```bash
cd /opt/signalbot
sudo systemctl stop signalbot
sudo -u signalbot git fetch --tags
sudo -u signalbot git checkout <new_tag>
sudo -u signalbot .venv/bin/pip install -r requirements.txt   # if deps changed
sudo systemctl start signalbot
sudo -u signalbot .venv/bin/python main.py --validate
```

Schema changes are applied idempotently at startup (`init_schema`), so a normal
restart migrates safely. Take a backup (§10) before updating.

## 12. Free space & log rotation

**Disk:** TimescaleDB stores ~30 days of 1m data across 3 exchanges plus
continuous aggregates. Keep comfortable headroom (**≥ 5–10 GB free**
recommended, more if you extend retention).

```bash
df -h /var/lib/docker /opt          # host + docker storage
sudo docker system df               # image/volume usage
# DB size:
sudo docker exec btcbot_timescaledb psql -U btcbot -d btcbot \
  -c "SELECT pg_size_pretty(pg_database_size('btcbot'));"
```

Optional disk-space guard (root cron) — warn under 5 GB free:
```bash
*/30 * * * * [ "$(df --output=avail -BG /var/lib/docker | tail -1 | tr -dc 0-9)" -lt 5 ] \
  && logger -t signalbot-disk "LOW DISK: <5GB free on /var/lib/docker"
```

**Log rotation:**
- Container logs are capped in `docker-compose.yml` (`json-file`, `max-size=10m`,
  `max-file=3`).
- journald (the bot's logs): cap total usage, e.g. in
  `/etc/systemd/journald.conf` set `SystemMaxUse=500M`, then
  `sudo systemctl restart systemd-journald`. Reclaim now with
  `sudo journalctl --vacuum-size=500M`.
- Backup log (`/var/log/signalbot-backup.log`): add a logrotate rule if you cron
  the backup.

## 13. Security recap

- Postgres/Redis bound to `127.0.0.1` only (verify: `sudo ss -tlnp | grep -E '5432|6379'`
  shows `127.0.0.1`, never `0.0.0.0`).
- Bot runs as unprivileged `signalbot`, not root, not in the docker group.
- `.env` is `chmod 600`, gitignored, never committed.
- Consider a host firewall (ufw) allowing only SSH inbound.
