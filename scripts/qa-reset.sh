#!/usr/bin/env bash
# DESTROY the local test stack — ONLY the test containers and test volumes.
# Guarded so it can never act on the production stack: it refuses unless every
# test-resource invariant matches (project name, compose file, test DB name,
# test ports). Production docker-compose.yml, its containers and volumes are
# never referenced here.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/qa-lib.sh
source "${SCRIPT_DIR}/qa-lib.sh"
cd "${REPO_ROOT}"

qa_step "qa-reset safety checks"

# 1. Compose file is the test file.
[[ "${QA_COMPOSE_FILE}" == "docker-compose.test.yml" ]] \
  || qa_die "compose file is not docker-compose.test.yml (got '${QA_COMPOSE_FILE}')"
[[ -f "${REPO_ROOT}/${QA_COMPOSE_FILE}" ]] || qa_die "missing ${QA_COMPOSE_FILE}"
qa_ok "compose file: ${QA_COMPOSE_FILE}"

# 2. Compose project is the QA project.
[[ "${QA_PROJECT}" == "signalbot-qa" ]] \
  || qa_die "compose project is not signalbot-qa (got '${QA_PROJECT}')"
qa_ok "compose project: ${QA_PROJECT}"

# 3–5. Test-resource coordinates must match the expected test values, read from
#      the actual test env file (never assume production values).
[[ -f "${QA_ENV_FILE}" ]] || qa_die "missing ${QA_ENV_FILE} — nothing to reset safely"
# shellcheck disable=SC1090
set -a; source "${QA_ENV_FILE}" >/dev/null 2>&1 || true; set +a

[[ "${POSTGRES_DB:-}" == "${QA_PG_DB}" ]] \
  || qa_die "POSTGRES_DB='${POSTGRES_DB:-}' != expected test DB '${QA_PG_DB}' — refusing"
qa_ok "test DB name: ${POSTGRES_DB}"

[[ "${POSTGRES_PORT:-}" == "${QA_PG_PORT}" ]] \
  || qa_die "POSTGRES_PORT='${POSTGRES_PORT:-}' != expected test port '${QA_PG_PORT}' — refusing"
qa_ok "test Postgres port: ${POSTGRES_PORT}"

case "${REDIS_URL:-}" in
  *":${QA_REDIS_PORT}/"*) qa_ok "test Redis port: ${QA_REDIS_PORT}" ;;
  *) qa_die "REDIS_URL does not use the test port ${QA_REDIS_PORT} — refusing" ;;
esac

# All guards passed → tear down ONLY the signalbot-qa project (containers + its
# named volumes). This cannot reach the default-project production resources.
qa_step "Removing test containers and volumes (project ${QA_PROJECT})"
qa_compose down -v --remove-orphans
qa_ok "test stack destroyed. Re-create it with ./scripts/qa-bootstrap.sh or 'make qa-infra-smoke'"
