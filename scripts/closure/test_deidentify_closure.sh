#!/usr/bin/env bash
# test_deidentify_closure.sh — prove scripts/closure/deidentify_closure.sql on an isolated throwaway database:
#   1. beta schema + synthetic fixture (no production data);
#   2. content hashes of every result table before;
#   3. dry run: nothing changes;
#   4. apply: participant tables empty, no person fingerprint or free text left, cohort counter as expected,
#      the owner's audit rows carry the role 'owner', result tables byte-identical (hash), append-only trigger still on;
#   5. VACUUM FULL of the touched tables runs; a plain dump contains none of the fixture's identifying strings.
# Usage: ./scripts/closure/test_deidentify_closure.sh [workdir]   (needs PostgreSQL 16 server binaries; root creates user pgtest)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
. "$HERE/testlib_pg.sh"
WORK="${1:-$(mktemp -d "${TMPDIR:-/tmp}/closure_deid_test.XXXXXX")}"; PORT="${PGTEST_PORT:-54391}"
DB=closure_deid_test
log() { printf '[test-deidentify] %s\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
mkdir -p "$WORK"; chmod 700 "$WORK"
trap 'pg_test_stop "$PORT"' EXIT
pg_test_start "$PORT"
P=(psql -X -q -v ON_ERROR_STOP=1 -d "$DB")
psql -X -q -d postgres -c "CREATE DATABASE $DB" >/dev/null
"${P[@]}" -f "$REPO/storage/beta_v0_schema.sql" >/dev/null
"${P[@]}" -f "$HERE/test_fixture_closure.sql" >/dev/null
log "schema + fixture loaded"

RESULT_TABLES="beta_claims beta_claim_outcomes beta_forecasts beta_hist_stats beta_episodes beta_push_decisions beta_market_alerts beta_rejected_start_counts"
# beta_market_alerts.target_user_pk is an FK ON DELETE SET NULL: it is nulled by design, every other column must stay
hash_tables() { for t in $RESULT_TABLES; do
  if [ "$t" = beta_market_alerts ]; then expr="(alert_pk, kind, alert_key, decision_ts, utc_day, decision, suppression_reason, payload, recorded_at)::text"; else expr="t::text"; fi
  printf '%s %s\n' "$t" "$("${P[@]}" -At -c "SELECT coalesce(md5(string_agg($expr, '|' ORDER BY $expr)), 'empty') FROM $t t")"; done; }
count() { "${P[@]}" -At -c "SELECT count(*) FROM $1"; }
before_hash="$(hash_tables)"
[ "$(count beta_users)" = 5 ] || fail "fixture: expected 5 users"
log "result-table hashes taken; users=5 allowlist=$(count beta_allowlist) waitlist=$(count beta_waitlist) audit=$(count beta_admin_audit)"

log "dry run"
"${P[@]}" -v owner_fps=u_0123456789ab -v owner_id=1001 -f "$HERE/deidentify_closure.sql" > "$WORK/dry.log" 2>&1 || { cat "$WORK/dry.log"; fail "dry run errored"; }
grep -q "DRY RUN: rolled back" "$WORK/dry.log" || fail "dry run did not roll back"
[ "$(count beta_users)" = 5 ] || fail "dry run changed beta_users"
[ "$(hash_tables)" = "$before_hash" ] || fail "dry run changed result tables"

log "apply"
"${P[@]}" -v owner_fps=u_0123456789ab -v owner_id=1001 -v apply=1 -f "$HERE/deidentify_closure.sql" > "$WORK/apply.log" 2>&1 || { cat "$WORK/apply.log"; fail "apply errored"; }
grep -q "COMMITTED" "$WORK/apply.log" || fail "apply did not commit"
for t in beta_users beta_allowlist beta_waitlist beta_feedback_messages beta_user_activity beta_message_votes beta_reasons beta_price_alerts beta_owner_forwards beta_rejected_start_hashes; do
  [ "$(count $t)" = 0 ] || fail "$t not empty after apply"
done
[ "$(hash_tables)" = "$before_hash" ] || { diff <(echo "$before_hash") <(hash_tables) || true; fail "result tables changed"; }
[ "$("${P[@]}" -At -c "SELECT count(*) FROM beta_admin_audit WHERE actor_fingerprint ~ '^u_' OR target_fingerprint ~ '^u_' OR detail <> '{}'")" = 0 ] || fail "audit still identifiable"
[ "$("${P[@]}" -At -c "SELECT count(*) FROM beta_admin_audit WHERE actor_fingerprint = 'owner'")" = 4 ] || fail "owner rows did not take the role 'owner'"
[ "$("${P[@]}" -At -c "SELECT count(*) FROM beta_admin_audit WHERE actor_fingerprint = 'participant'")" = 1 ] || fail "participant deletion row did not take the role"
[ "$("${P[@]}" -At -c "SELECT count(*) FROM beta_admin_audit WHERE recorded_at <> date_trunc('day', recorded_at AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv'")" = 0 ] || fail "audit timestamps not reduced to the Kyiv date"
counter="$("${P[@]}" -At -F, -c "SELECT joined_kyiv_date, n FROM beta_deleted_cohort_counts ORDER BY 1" | tr '\n' ';')"
[ "$counter" = "2026-10-02,1;2026-10-03,1;2026-10-04,1;" ] || fail "cohort counter unexpected: $counter"
[ "$("${P[@]}" -At -c "SELECT count(*) FROM beta_notification_deliveries WHERE user_pk IS NOT NULL OR error_summary NOT IN ('redacted')")" = 0 ] || fail "deliveries not de-identified"
[ "$("${P[@]}" -At -c "SELECT count(*) FROM beta_notification_deliveries")" = 3 ] || fail "delivery rows lost"
[ "$("${P[@]}" -At -c "SELECT label FROM beta_invites")" = "redacted" ] || fail "invite label not redacted"
[ "$("${P[@]}" -At -c "SELECT count(*) FROM beta_market_alerts WHERE target_user_pk IS NULL")" = 1 ] || fail "market alert FK not nulled"
[ "$("${P[@]}" -At -c "SELECT tgenabled FROM pg_trigger WHERE tgname = 'trg_beta_audit_append_only'")" = "O" ] || fail "audit append-only trigger not enabled"
"${P[@]}" -c "UPDATE beta_admin_audit SET result = 'X'" >/dev/null 2>&1 && fail "audit accepted an update after closure" || true
log "post-apply checks ok; cohort counter $counter"

log "vacuum full + dump scan"
"${P[@]}" -c "VACUUM (FULL, ANALYZE) beta_users, beta_allowlist, beta_waitlist, beta_feedback, beta_feedback_messages, beta_message_votes, beta_reasons, beta_user_activity, beta_price_alerts, beta_owner_forwards, beta_notification_deliveries, beta_admin_audit, beta_invites, beta_rejected_start_hashes" >/dev/null
"${P[@]}" -c "CHECKPOINT" >/dev/null
pg_dump -d "$DB" --no-owner --no-privileges > "$WORK/after.sql"
for s in "Rex" "friend from the chat" "blocked by the user" "u_aaaaaaaaaaaa" "u_bbbbbbbbbbbb" "u_cccccccccccc" "u_0123456789ab" "2026-10-02 12:05:17" "test_open_at"; do
  grep -q -- "$s" "$WORK/after.sql" && fail "identifying string still in the dump: $s"
done
# telegram ids of the fixture must not appear as values of the participant tables (they are absent entirely)
for id in 1001 1002 1003 1004 1005 1006 1007; do
  grep -E "^(COPY public\.(beta_users|beta_allowlist|beta_waitlist))" -A5 "$WORK/after.sql" | grep -qw "$id" && fail "telegram id $id still in a participant table" || true
done
# the physical heap no longer holds the deleted rows (VACUUM FULL rewrote the tables): scan the data files for a fixture string
heapgrep=$( (grep -rl --binary-files=text "friend from the chat" "$PGTEST_DATA/base" 2>/dev/null || true) | wc -l)
[ "$heapgrep" = 0 ] || log "WARNING: a fixture string is still present in $heapgrep data file(s) under base/ (expected 0 after VACUUM FULL; WAL may still hold it)"
walgrep=$( (grep -rl --binary-files=text "friend from the chat" "$PGTEST_DATA/pg_wal" 2>/dev/null || true) | wc -l)
log "residual copies: heap files $heapgrep, WAL segments $walgrep (WAL is why the physical volume copy and the VPS snapshot count as personal-data copies)"
grep -E "^ *(before|after|counter)" "$WORK/apply.log" | head -40 || true
log "PASS"
