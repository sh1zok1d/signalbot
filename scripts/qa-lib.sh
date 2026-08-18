#!/usr/bin/env bash
# Shared helpers for the QA scripts. Sourced, never executed directly.
# Keeps the test Compose project / file / env-file in ONE place so every command
# is guaranteed to act on the isolated test stack and never on production.
set -Eeuo pipefail

# Repo root = parent of this scripts/ directory.
QA_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${QA_LIB_DIR}/.." && pwd)"

# The ONLY test-stack identifiers. Do not change without updating qa-reset guards.
QA_PROJECT="signalbot-qa"
QA_COMPOSE_FILE="docker-compose.test.yml"
QA_ENV_FILE=".env.test"
QA_ENV_EXAMPLE=".env.test.example"

# Expected test-resource facts (used by qa-reset safety checks).
QA_PG_PORT="5433"
QA_REDIS_PORT="6380"
QA_PG_DB="signalbot_test"

QA_VENV="${REPO_ROOT}/.venv"
QA_PY="${QA_VENV}/bin/python"

# --- tiny output helpers (no secrets ever printed) ---
qa_info()  { printf '  %s\n' "$*"; }
qa_step()  { printf '\n==> %s\n' "$*"; }
qa_ok()    { printf '  [ok] %s\n' "$*"; }
qa_warn()  { printf '  [!] %s\n' "$*" >&2; }
qa_err()   { printf '  [x] %s\n' "$*" >&2; }
qa_die()   { qa_err "$*"; exit 1; }

# Compose wrapper — ALWAYS scoped to the test project + file, and to the test
# env-file when it exists (so substitution never reads production ./.env).
qa_compose() {
  local env_args=()
  if [[ -f "${REPO_ROOT}/${QA_ENV_FILE}" ]]; then
    env_args=(--env-file "${REPO_ROOT}/${QA_ENV_FILE}")
  fi
  docker compose -p "${QA_PROJECT}" "${env_args[@]}" \
    -f "${REPO_ROOT}/${QA_COMPOSE_FILE}" "$@"
}

# True if a `python -m pytest` is available in the venv.
qa_have_venv() { [[ -x "${QA_PY}" ]]; }
