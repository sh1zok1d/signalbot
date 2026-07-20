#!/usr/bin/env bash
# One-shot, idempotent local QA setup for a second developer on WSL2 Ubuntu
# (also plain Linux). Creates a venv, installs dev deps, brings up the ISOLATED
# test TimescaleDB/Redis, runs the infra smoke test and the fast unit suite.
#
# It never uses sudo / apt / curl|bash, never touches the production stack, and
# never overwrites an existing .env.test. Safe to re-run.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/qa-lib.sh
source "${SCRIPT_DIR}/qa-lib.sh"
cd "${REPO_ROOT}"

fail_hint() {
  qa_err "bootstrap failed at: ${1}"
  [[ -n "${2:-}" ]] && qa_info "next step: ${2}"
  exit 1
}

# 1. Root already resolved by qa-lib.sh (REPO_ROOT).
qa_step "QA bootstrap in ${REPO_ROOT}"

# 2. OS check — allow Linux/WSL, warn (don't block) elsewhere.
case "$(uname -s)" in
  Linux*) grep -qiE "microsoft|wsl" /proc/version 2>/dev/null \
            && qa_info "environment: WSL2" || qa_info "environment: Linux" ;;
  *)      qa_warn "non-Linux host ($(uname -s)); this is meant for WSL2/Linux — continuing" ;;
esac

# 3. Required tools.
qa_step "Checking required tools"
need() { command -v "$1" >/dev/null 2>&1 || fail_hint "missing '$1'" "install $1 and re-run"; qa_ok "$1"; }
need git
need python3
python3 -m venv --help >/dev/null 2>&1 || fail_hint "python3 venv module missing" \
  "install the python3-venv package (e.g. 'sudo apt install python3-venv') and re-run"
qa_ok "python3 -m venv"
need docker
docker compose version >/dev/null 2>&1 || fail_hint "'docker compose' plugin missing" \
  "install Docker Desktop WSL integration or the docker-compose-plugin"
qa_ok "docker compose"

# 4. Docker daemon reachable.
qa_step "Checking Docker daemon"
docker info >/dev/null 2>&1 || fail_hint "Docker daemon not reachable" \
  "start Docker Desktop (with WSL integration enabled) and re-run"
qa_ok "docker info"

# 6. venv (create if absent).
qa_step "Python virtualenv (.venv)"
if [[ ! -x "${QA_PY}" ]]; then
  python3 -m venv "${QA_VENV}" || fail_hint "could not create .venv" "check disk space / python3-venv"
  qa_ok "created .venv ($("${QA_PY}" --version 2>&1))"
else
  qa_ok "reusing .venv ($("${QA_PY}" --version 2>&1))"
fi

# 7. Dev dependencies (idempotent — pip is a no-op when satisfied).
qa_step "Installing dev dependencies (requirements-dev.txt)"
"${QA_PY}" -m pip install --quiet --upgrade pip >/dev/null
"${QA_PY}" -m pip install --quiet -r requirements-dev.txt \
  || fail_hint "pip install failed" "re-run; if it persists, check your network/proxy"
qa_ok "dependencies installed"

# 8–9. .env.test — create from example ONLY if missing; never overwrite.
qa_step "Test environment file (${QA_ENV_FILE})"
if [[ -f "${QA_ENV_FILE}" ]]; then
  qa_ok "${QA_ENV_FILE} already exists — left untouched"
else
  [[ -f "${QA_ENV_EXAMPLE}" ]] || fail_hint "${QA_ENV_EXAMPLE} not found" "restore it from git"
  cp "${QA_ENV_EXAMPLE}" "${QA_ENV_FILE}"
  qa_ok "created ${QA_ENV_FILE} from ${QA_ENV_EXAMPLE}"
fi

# 10. Bring up the isolated test stack.
qa_step "Starting test stack (project ${QA_PROJECT})"
qa_compose up -d || fail_hint "docker compose up failed" "check 'make qa-logs' and 'docker info'"
qa_ok "compose up issued"

# 11. Wait for health checks.
qa_step "Waiting for test services to be healthy"
deadline=$(( $(date +%s) + 120 ))
while :; do
  all_healthy=1
  for svc in timescaledb-test redis-test; do
    cid="$(qa_compose ps -q "$svc" 2>/dev/null || true)"
    if [[ -z "$cid" ]]; then all_healthy=0; break; fi
    # Both test services declare a healthcheck, so require "healthy".
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$cid" 2>/dev/null || echo unknown)"
    if [[ "$state" != "healthy" ]]; then all_healthy=0; break; fi
  done
  [[ "$all_healthy" -eq 1 ]] && break
  [[ "$(date +%s)" -ge "$deadline" ]] && fail_hint "services did not become healthy in time" "inspect with 'make qa-logs'"
  sleep 2
done
qa_ok "test services healthy"

# 12. Infra smoke.
qa_step "Infrastructure smoke test"
SIGNALBOT_ENV_FILE="${QA_ENV_FILE}" "${QA_PY}" scripts/qa-smoke.py \
  || fail_hint "infra smoke failed" "check 'make qa-status' and 'make qa-logs'"

# 13. Fast unit suite (no Docker/network needed).
qa_step "Fast test suite"
"${QA_PY}" -m pytest -q || fail_hint "unit tests failed" "re-run 'make qa-fast' to see details"

# 14. Command cheatsheet.
qa_step "Bootstrap complete — common commands"
cat <<'EOF'
  make qa-fast          fast unit suite (no Docker/network)
  make qa-infra-smoke   bring up test stack + infra smoke
  make qa-full          full pytest suite
  make qa-check         compileall + pytest (same as CI)
  make qa-status        environment + service status (no secrets)
  make qa-logs          tail test-stack logs
  make qa-down          stop the test stack
  make qa-reset         DESTROY only the test containers + volumes
EOF
