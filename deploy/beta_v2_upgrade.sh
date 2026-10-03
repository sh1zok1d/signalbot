#!/usr/bin/env bash
set -euo pipefail

# Decision support V2 upgrade (docs/PRIVATE_BETA_V0_DEPLOY.md, "Decision support V2").
# Run as root from the deployed checkout AFTER the code is updated:
#
#     cd /opt/signalbot && sudo deploy/beta_v2_upgrade.sh [--skip-rewind]
#
# Steps, each stopping the script on failure:
#   1. install the beta units (copy + daemon-reload; enables nothing by itself)
#   2. history sync from data.binance.vision, repeated until nothing is left to fetch
#   3. first statistics build (prints the held-out corridor coverage)
#   4. V2 tape rewind + the existing bounded bootstrap runner (unless --skip-rewind)
#   5. restart the long-running bot, enable the nightly history timer
#   6. read-only health report
# Never prints .env. Safe to re-run: every step is idempotent.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/.venv/bin/python"
SKIP_REWIND=0
[[ "${1:-}" == "--skip-rewind" ]] && SKIP_REWIND=1

as_sb() { sudo -u signalbot --set-home -- "$@"; }
step() { echo; echo "==== $* ===="; }

test -x "${PY}" || { echo "missing ${PY}"; exit 1; }
cd "${ROOT}"

step "1/6 install beta units"
"${ROOT}/deploy/install_beta_units.sh"

step "2/6 history sync (Binance Vision; resumable)"
for i in $(seq 1 6); do
  out="$(as_sb "${PY}" main.py --beta-history-sync --beta-json --log-level WARNING | tail -n 1)"
  echo "${out}" | "${PY}" -c 'import json,sys; r=json.loads(sys.stdin.read()); print({k: r.get(k) for k in ("status","planned","ok","missing","fallback_daily","bars_written","oi_written","bars_from","bars_through","oi_from","oi_through")}); print("errors:", len(r.get("errors") or []))'
  status="$(echo "${out}" | "${PY}" -c 'import json,sys; print(json.loads(sys.stdin.read()).get("status"))')"
  if [[ "${status}" == "OK" ]]; then break; fi
  if [[ "${status}" != "PARTIAL" ]]; then echo "history sync status ${status}; stopping"; exit 2; fi
  echo "partial run ${i}; retrying in 30s"; sleep 30
done

step "3/6 statistics build"
as_sb "${PY}" main.py --beta-history-build --beta-json --log-level WARNING | tail -n 1 | \
  "${PY}" -c 'import json,sys; r=json.loads(sys.stdin.read()); print({k: r.get(k) for k in ("status","stats_pk","data_from","data_through","bars","missing_bars","corridor_coverage_holdout","timings")}); sys.exit(0 if r.get("status")=="OK" else 3)'

if [[ "${SKIP_REWIND}" -eq 0 ]]; then
  step "4/6 V2 tape rewind + bootstrap runner (refills 30 days; the detector catches up)"
  as_sb "${PY}" main.py --beta-bootstrap-rewind --beta-json --log-level WARNING | tail -n 1
  as_sb "${PY}" -m runtime.beta_bootstrap_runner
else
  step "4/6 rewind skipped"
fi

step "5/6 restart the bot, enable the nightly history timer"
systemctl restart signalbot-beta-bot.service
systemctl enable --now signalbot-beta-history.timer
systemctl list-timers 'signalbot-beta-*' --no-pager || true

step "6/6 health (read-only)"
as_sb "${PY}" main.py --beta-health --beta-json --log-level WARNING | tail -n 1 | \
  "${PY}" -c 'import json,sys; r=json.loads(sys.stdin.read()); h=r.get("health") or {}; print("status:", r.get("status"), "alerts:", [a.get("key") for a in h.get("alerts") or []])'

echo
echo "Done. In Telegram: /levels, /risk 0.5, /events, /accuracy, /alert <price>, /btc, /catchup."
