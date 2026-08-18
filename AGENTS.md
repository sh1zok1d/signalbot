# AGENTS.md — working rules for AI agents on Signalbot

Signalbot is a multi-exchange crypto **ingestion + storage** system (Stage 1)
plus a **Stage 2 analytics foundation** (per-exchange + consensus features). This
file is the short, binding rulebook for any AI agent doing QA/test work here.

## Environment
- QA is **local only**: an isolated `.venv` and the `signalbot-qa` Docker project
  (test TimescaleDB on 5433, test Redis on 6380). Production infra, the server,
  SSH, and real secrets are **not available and must not be assumed**.
- First-time setup: `./scripts/qa-bootstrap.sh`. Everyday loop: `make qa-fast`.

## Core commands
- `make qa-fast` — fast unit suite (no Docker/network).
- `make qa-infra-smoke` — bring up the test stack + `scripts/qa-smoke.py`.
- `make qa-check` — `compileall` + `pytest` (identical base to CI).
- `make qa-status` / `make qa-logs` / `make qa-down` / `make qa-reset`.

## How to work
1. **Reproduce, then test, then fix** — write a failing test before changing code.
2. Prefer the smallest change. A behaviour change requires a regression test
   **and** a human decision.
3. When a contract is ambiguous, **the project owner decides** — do not guess and
   encode a guess as truth.

## Hard limits (do not cross)
- Do **not** weaken or delete existing assertions to make tests pass.
- Do **not** merge, push to shared branches without being asked, or deploy.
- Do **not** modify the **Stage 2 frozen contract** (Consensus Contract Revision
  0.2.3, `docs/STAGE2_SPEC.md` §11) or its formulas.
- Do **not** change `storage/schema.sql`, `storage/stage2_schema.sql`, migrations,
  or schema objects without a separate, explicitly-approved task.
- Do **not** run a real backfill or live exchange/WebSocket clients from the unit
  suite. `scripts/test_shutdown.py` is a **manual/networked** test, never in CI.
- Do **not** touch production `docker-compose.yml`, deploy/systemd scripts, server
  config, or Telegram.

## Two-AI etiquette
Two agents must **not** edit the same working copy at the same time. One agent
proposes/implements in a branch; a second reviews the diff and tests; the human
decides. See `docs/QA_SCOPE.md` for the full workflow and what is yours to build.
