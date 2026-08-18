# TESTING.md — local QA quickstart

A minimal, safe local test platform. Everything runs on your machine against an
**isolated** test TimescaleDB/Redis — never the production stack, the server, or
live exchange APIs.

## Requirements
Install these yourself first (the bootstrap never uses `sudo`/`apt`/`curl|bash`):
- Git, Python 3 (**3.12+**; dev is validated on 3.12 and 3.14), and Docker with
  the `docker compose` plugin (on Windows: Docker Desktop with **WSL2
  integration** enabled).

## First run
```bash
cd signalbot
./scripts/qa-bootstrap.sh      # venv + dev deps + test stack + smoke + fast tests
make qa-fast                   # the everyday loop
```
`qa-bootstrap.sh` is **idempotent** — re-running it is safe and never overwrites
an existing `.env.test`.

## Everyday commands
| Command | What it does |
|---|---|
| `make qa-fast` | Fast unit suite. No Docker, no network. |
| `make qa-full` | Full pytest suite (still no live internet). |
| `make qa-infra-smoke` | Bring up the test stack and run `scripts/qa-smoke.py`. |
| `make qa-check` | `compileall` + `pytest` — the **same base as CI**. |
| `make qa-status` | Env + service status (no secrets printed). |
| `make qa-last-failure` | Re-run only the tests that failed last time. |
| `make qa-logs` | Follow the test-stack logs. |
| `make qa-down` | Stop the test stack (keeps volumes). |
| `make qa-reset` | **Destroy** only the test containers + volumes (guarded). |

## The test environment
- `.env.test` (gitignored; created from `.env.test.example`) points the app at
  the test resources. QA commands export `SIGNALBOT_ENV_FILE=.env.test`; the seam
  in `common/config.py` loads it instead of the production `.env`. Default
  behaviour (production `.env`) is unchanged when the variable is unset.
- The test stack is `docker-compose.test.yml` under the **`signalbot-qa`** Docker
  project: TimescaleDB on `127.0.0.1:5433`, Redis on `127.0.0.1:6380`, with their
  own volumes. It is completely separate from production `docker-compose.yml`
  (5432 / 6379).
- `make qa-reset` refuses to run unless the project name, compose file, test DB
  name, and test ports all match — so it can never delete production data.

## The infra smoke test (`scripts/qa-smoke.py`)
Proves, through the project's own code: `Config` loads; the DSN targets the test
DB; TimescaleDB connects; `Database.init_schema()` runs twice (idempotent); Stage
1 schema exists; **Stage 2 schema is NOT auto-created**; Redis connects, PINGs,
and a heartbeat round-trips. It never contacts exchanges, runs `main.py`, runs
backfill, starts live clients, or uses Telegram.

## Markers (`pytest.ini`)
`unit`, `integration`, `regression`, `contract`, `slow`, `manual`. Async support
is present (`pytest-asyncio`, strict mode) but the current suite is synchronous.
`scripts/test_shutdown.py` is a **manual/networked** test (real backfill + live
APIs); it is not under `tests/` and never runs in `qa-fast`/CI.

## Two-AI workflow
One agent proposes and implements in a branch; a second agent reviews the diff
and tests; the human decides. Two agents must not edit the same working copy at
once. Full engineering scope and boundaries: `docs/QA_SCOPE.md`.
