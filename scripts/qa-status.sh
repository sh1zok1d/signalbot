#!/usr/bin/env bash
# Read-only QA environment status. Prints NO secret values (only host/port/db
# names and service state). Never mutates anything.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/qa-lib.sh
source "${SCRIPT_DIR}/qa-lib.sh"
cd "${REPO_ROOT}"

qa_step "Git"
qa_info "branch : $(git branch --show-current 2>/dev/null || echo '?')"
qa_info "head   : $(git log -1 --oneline 2>/dev/null || echo '?')"

qa_step "Python / venv"
if qa_have_venv; then
  qa_info "venv   : ${QA_VENV}"
  qa_info "python : $("${QA_PY}" --version 2>&1) (${QA_PY})"
  qa_info "pytest : $("${QA_PY}" -m pytest --version 2>&1 | head -1)"
else
  qa_warn "venv missing — run ./scripts/qa-bootstrap.sh"
fi
qa_info "system : $(python3 --version 2>&1)"

qa_step "Test environment file"
if [[ -f "${QA_ENV_FILE}" ]]; then
  qa_info "env    : ${QA_ENV_FILE} (present)"
else
  qa_warn "${QA_ENV_FILE} missing — run ./scripts/qa-bootstrap.sh"
fi
# Show only non-secret coordinates from the env file (never the password).
if [[ -f "${QA_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a; source "${QA_ENV_FILE}" >/dev/null 2>&1 || true; set +a
  qa_info "pg     : ${POSTGRES_HOST:-?}:${POSTGRES_PORT:-?}/${POSTGRES_DB:-?} (user ${POSTGRES_USER:-?})"
  # REDIS_URL may embed a password; print host/port/db only.
  qa_info "redis  : $(printf '%s' "${REDIS_URL:-}" | sed -E 's#(redis://)([^@]*@)?#\1#')"
  qa_info "telegram: $([[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] && echo 'unset (correct for QA)' || echo 'SET — unexpected for QA')"
fi

qa_step "Docker"
if command -v docker >/dev/null 2>&1; then
  qa_info "docker : $(docker --version 2>&1 | head -1)"
  if docker compose version >/dev/null 2>&1; then
    qa_info "compose: $(docker compose version 2>&1 | head -1)"
  else
    qa_warn "docker compose plugin not found"
  fi
  if docker info >/dev/null 2>&1; then
    qa_info "daemon : reachable"
    qa_step "Test services (project ${QA_PROJECT})"
    qa_compose ps 2>/dev/null || qa_warn "test stack not up — run 'make qa-infra-smoke' or bootstrap"
  else
    qa_warn "docker daemon not reachable — start Docker Desktop"
  fi
else
  qa_warn "docker not installed"
fi
