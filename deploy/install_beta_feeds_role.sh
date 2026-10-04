#!/usr/bin/env bash
set -euo pipefail

# Create or refresh the least-privilege DB role of the research feed units (signalbot_beta_feeds)
# from deploy/beta_feeds_role.sql (docs/RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md §A, PREREQ-3).
#
#   sudo deploy/install_beta_feeds_role.sh                 # grants only (also after every restore)
#   sudo deploy/install_beta_feeds_role.sh --set-password  # + new random password, writes the env file
#
# Idempotent. Run as root on the host, after the core role has applied the beta schema. It never
# enables, starts or restarts a unit, never prints a password or the core .env, and passes the
# password to psql on stdin only (not in a process list). The env file is root:root 0600: systemd
# reads it for the feed units; neither the bot nor the feed processes can read it from disk.

ROOT=${SIGNALBOT_ROOT:-/opt/signalbot}
CONTAINER=${CONTAINER:-btcbot_timescaledb}
ENV_CORE="${ROOT}/.env"
ENV_FEEDS="${ROOT}/.env.beta-feeds"
ROLE=signalbot_beta_feeds

# one value from the core .env without sourcing it (surrounding quotes removed)
core_value() {
  grep -E "^${1}=" "${ENV_CORE}" | tail -n 1 | cut -d= -f2- | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/" || true
}

[ -r "${ENV_CORE}" ] || { echo "cannot read ${ENV_CORE}" >&2; exit 2; }
SU=$(core_value POSTGRES_USER); SU=${SU:-btcbot}       # docker-compose.yml defaults
DB=$(core_value POSTGRES_DB); DB=${DB:-btcbot}
HOST=$(core_value POSTGRES_HOST); HOST=${HOST:-127.0.0.1}
PORT=$(core_value POSTGRES_PORT); PORT=${PORT:-5432}

psql_su() { docker exec -i "${CONTAINER}" psql -U "${SU}" -d "${DB}" -v ON_ERROR_STOP=1 -q "$@"; }

# the feed tables are created by the core role (bot start-up or any beta command); never here
n=$(psql_su -tA -c "SELECT count(*) FROM unnest(ARRAY['beta_feed_metrics_5m','beta_feed_dvol_1h','beta_feed_depth',
      'beta_feed_spot_5m','beta_feed_stress_hours','beta_runtime_health','beta_hist_oi_5m']) AS t
      WHERE to_regclass(t) IS NOT NULL")
if [ "${n}" != "7" ]; then
  echo "the beta feed schema is not applied yet (${n}/7 tables): apply it with the core role first" >&2
  exit 2
fi

psql_su < "${ROOT}/deploy/beta_feeds_role.sql"
echo "role ${ROLE}: grants applied"

if [ "${1:-}" = "--set-password" ]; then
  pw=$(openssl rand -hex 24)
  printf "ALTER ROLE %s PASSWORD '%s';\n" "${ROLE}" "${pw}" | psql_su
  umask 077
  tmp=$(mktemp "${ENV_FEEDS}.XXXXXX")
  {
    echo "# Research feed units only (deploy/beta-feeds.env.example). Written by deploy/install_beta_feeds_role.sh."
    echo "POSTGRES_HOST=${HOST}"
    echo "POSTGRES_PORT=${PORT}"
    echo "POSTGRES_DB=${DB}"
    echo "POSTGRES_USER=${ROLE}"
    echo "POSTGRES_PASSWORD=${pw}"
    be=$(core_value BETA_ENABLED)
    if [ -n "${be}" ]; then echo "BETA_ENABLED=${be}"; fi
  } > "${tmp}"
  chown root:root "${tmp}"
  chmod 0600 "${tmp}"
  mv -f "${tmp}" "${ENV_FEEDS}"
  unset pw
  echo "role ${ROLE}: new password set; ${ENV_FEEDS} written (root:root 0600)"
fi
echo "Nothing was enabled or started. Activation needs a separate owner go (docs/RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md §D)."
