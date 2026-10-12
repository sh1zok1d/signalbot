#!/usr/bin/env bash
# Read-only JSONL export of L3 calibration claims for monitor V2.
# Prints the row count and sha256 only. Does not print the database password,
# a DSN, or the JSONL. Does not change roles or grants.
# On the VPS, leave CALIBRATION_EXPORT_DSN unset so the existing container is used.
# That variable is only for a local read-only check.
set -euo pipefail
umask 077
exec </dev/null

OUT="${1:-/tmp/calibration_monitor_v2.jsonl}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SQL="$HERE/export_calibration_journal_v2.sql"
if [ ! -f "$SQL" ]; then
  echo "missing export SQL next to this script" >&2
  exit 1
fi

TMP="$(mktemp "${TMPDIR:-/tmp}/calibration_monitor_v2.XXXXXXXX.jsonl")"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

if [ -n "${CALIBRATION_EXPORT_DSN:-}" ]; then
  PGOPTIONS='-c default_transaction_read_only=on' \
    psql "$CALIBRATION_EXPORT_DSN" -X -q -t -A -v ON_ERROR_STOP=1 -f "$SQL" >"$TMP"
else
  ENV_FILE="${SIGNALBOT_ENV:-/opt/signalbot/.env}"
  if [ ! -f "$ENV_FILE" ]; then
    echo "missing env file; the VPS path reads /opt/signalbot/.env" >&2
    exit 1
  fi
  eval "$( (set -a; . "$ENV_FILE"; set +a
            printf 'C=%q\nDB=%q\nU=%q\n' \
              "${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}" \
              "${POSTGRES_DB:-btcbot}" \
              "${POSTGRES_USER:-btcbot}") )"
  printf 'container=%s db=%s user=%s\n' "$C" "$DB" "$U"
  docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' "$C" \
    psql -X -q -t -A -v ON_ERROR_STOP=1 -U "$U" -d "$DB" -f - <"$SQL" >"$TMP"
fi

ROWS="$(python3 - "$TMP" <<'PY'
import json
import sys

FORBIDDEN = {
    "subject",
    "subject_key",
    "price",
    "high",
    "low",
    "close",
    "chat_id",
    "user_id",
    "token",
    "password",
    "dsn",
    "secret",
    "api_key",
    "authorization",
}

def walk(node, found):
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in FORBIDDEN:
                found.add(str(key))
            walk(value, found)
    elif isinstance(node, list):
        for value in node:
            walk(value, found)

path = sys.argv[1]
count = 0
with open(path, encoding="utf-8") as handle:
    for line_number, line in enumerate(handle, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        if not isinstance(row, dict):
            raise SystemExit(f"line {line_number} is not an object")
        found = set()
        walk(row, found)
        if found:
            names = ", ".join(sorted(found))
            raise SystemExit(f"line {line_number} contains forbidden keys: {names}")
        count += 1
print(count)
PY
)"

SHA="$(sha256sum "$TMP" | awk '{print $1}')"
install -m 0600 "$TMP" "$OUT"
trap - EXIT
rm -f "$TMP"
printf 'rows=%s sha256=%s path=%s\n' "$ROWS" "$SHA" "$OUT"
