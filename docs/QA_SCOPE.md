# QA_SCOPE.md — what this platform provides, and what is yours to build

This iteration delivers a **platform and guardrails**, not a finished test suite.
The QA engineer (with AI help) owns the substantial testing work below.

## Already provided (do not rebuild)
- Reproducible local setup: `scripts/qa-bootstrap.sh`, `.venv`,
  `requirements-dev.txt`.
- Isolated test TimescaleDB/Redis: `docker-compose.test.yml` (project
  `signalbot-qa`, ports 5433/6380), `.env.test.example`, and the
  `SIGNALBOT_ENV_FILE` config seam.
- Single command surface: `Makefile` (`qa-*`), `pytest.ini` with markers.
- Infra smoke test: `scripts/qa-smoke.py`.
- CI for the fast suite: `.github/workflows/tests.yml`.
- Safe teardown of test-only resources: `scripts/qa-reset.sh`.

## Your engineering scope (design and build these)
Currently thin/untested areas — this is where your work goes:
- **Test factories / fixtures** for bars, OI, funding, liquidation payloads.
- **Exchange payload corpus** (realistic + adversarial samples per venue).
- **Fake clock / sleep / backoff** helpers (deterministic time control).
- **Fake HTTP / WebSocket transports** for offline client tests.
- **`data_ingestion/bar_builder.py`** adversarial tests (`LiveBarBuilder`:
  out-of-order, duplicate, gap, boundary, late bars).
- **Exchange parser contract tests** (Binance, Bybit, OKX, Bitget).
- **`backfill/backfill.py`** pagination / retry / cursor / resume tests.
- **`data_ingestion/manager.py`** failure-isolation tests.
- **Real DB writer integration tests** (against the test TimescaleDB).
- **`storage/redis_client.py`** and **`storage/validate.py`** tests.
- **Mutation / property-based testing** — only after separately choosing tools
  (none are installed in this iteration; that choice is yours to justify).
- **Bug reproduction + minimal fixes**, each with a regression test.
- **Testability seams**: propose minimal dependency-injection points where code
  is hard to test.

## Rules for that work
- **Reproduce → test → fix.** A failing test comes before a fix.
- You may add production code in a **separate PR** only when it is a **minimal
  dependency-injection seam needed for testability** and **production behaviour
  does not change**. Any behaviour change needs a regression test **and** an
  owner decision.
- Never weaken assertions to make a test pass.
- Do not modify the Stage 2 frozen contract (Revision 0.2.3), `storage/*.sql`,
  migrations, exchange endpoints, backfill pagination logic, deploy/systemd, the
  production `docker-compose.yml`, server config, Telegram, or signal logic.
- Do not run real backfill or live clients in the unit suite.

## Recommended two-AI process
1. AI **A** analyses a component and proposes a test plan.
2. The **human** picks scenarios and the expected behaviour.
3. AI **A** implements in a branch.
4. AI **B** reviews the diff and the tests independently.
5. The **human** decides (merge is a human action).
6. Two AIs must **not** edit the same working copy simultaneously.

## Known limitations
- Docker must be running for `qa-infra-smoke` / integration work; in a WSL2 dev
  session where the Docker daemon is unavailable, DB-backed steps cannot run
  (unit tests and `compileall` still work).
- No linter/type-checker/property tools are installed yet — intentionally left as
  a separate decision.
