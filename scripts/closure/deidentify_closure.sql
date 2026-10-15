-- deidentify_closure.sql — the ONE reproducible de-identification procedure of the Pulsy closure
-- (docs/closure/PAID_RESOURCES_AND_PII_V1.md §3.3, SHUTDOWN_CHECKLIST_V1 S6). Run on the LIVE database, with the
-- application stopped, AFTER the final full encrypted dump (S4) and BEFORE the de-identified export (S7):
--
--   psql -X -v ON_ERROR_STOP=1 [-v owner_fps=fp1,fp2] [-v owner_id=<telegram id>] [-v apply=1] -f deidentify_closure.sql
--
-- Without `-v apply=1` everything runs and is ROLLED BACK (dry run: the counts are printed). `owner_fps` are the
-- owner's keyed and legacy audit fingerprints (compute them with the project's Python: beta.admin.fingerprint and
-- beta.pseudonym.legacy_pseudonym; SQL cannot compute the keyed one); their rows take the role 'owner', every other
-- person fingerprint takes 'participant'. `owner_id` excludes the owner from the cohort counter (as delete_participant does).
--
-- What it does, in one transaction, in this order:
--   1. prints the test-opening time and the participant counts (aggregate only);
--   2. adds the #420 cohort counter for unknown participants who joined at/after the test opening (the same rule as
--      storage/beta_v0_store.py delete_participant), grouped by Kyiv join date;
--   3. deletes every participant: beta_users (feedback, votes, reasons, activity, price alerts, owner forwards and
--      free-text messages cascade; deliveries and market alerts keep a NULL user_pk), beta_allowlist, beta_waitlist;
--   4. redacts the remaining free text / identifiers outside the cascade: beta_invites.label, delivery error
--      summaries (kept non-NULL for the FAILED constraint), the legacy notifier's recipient fingerprints (if that
--      table exists), the rejected-start HMACs (the daily counts stay);
--   5. de-identifies EVERY audit row whose actor or target is a person fingerprint (u_ + 12 hex), through the
--      schema's own beta_audit_deidentify() (the append-only guard admits exactly this, and only while no listed
--      fingerprint belongs to anyone still present, which after step 3 is nobody): target NULL, detail {}, the Kyiv
--      date, actor -> role. Keyed and legacy fingerprints alike, because every string is listed, not recomputed;
--   6. verifies: participant tables empty, no person fingerprint left in the audit, result tables untouched
--      (their row counts are compared with the counts taken at the start of the transaction).
-- It never touches: beta_claims*, beta_forecasts, beta_hist_*, beta_episodes*, beta_state_tape, beta_context_snapshots,
-- beta_market_alerts rows (only the FK nulls itself), beta_shadow_*, forecast_*, beta_deleted_cohort_counts (except +n),
-- beta_rejected_start_counts.  VACUUM FULL of the touched tables is a separate step after COMMIT (see the checklist).
\set ON_ERROR_STOP 1
\if :{?owner_fps}
\else
\set owner_fps ''
\endif
\if :{?owner_id}
\else
\set owner_id 0
\endif
\if :{?apply}
\else
\set apply 0
\endif
\echo 'apply=' :apply '  (0 = dry run, rolled back)'

BEGIN;
LOCK TABLE beta_users, beta_allowlist, beta_waitlist, beta_admin_audit, beta_deleted_cohort_counts IN ACCESS EXCLUSIVE MODE;

-- 1. before: aggregate counts only
CREATE TEMP TABLE closure_before ON COMMIT DROP AS
SELECT t.name, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', t.name), false, true, '')))[1]::text::bigint AS n
FROM (SELECT tablename AS name FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'beta\_%' ESCAPE '\'
      UNION SELECT unnest(ARRAY['forecast_predictions','forecast_outcomes','telegram_notification_deliveries'])) t
WHERE to_regclass('public.' || t.name) IS NOT NULL;
SELECT 'test_open_at' AS k, (SELECT detail->>'test_open_at' FROM beta_admin_audit
        WHERE action = 'admin_test_open' AND authorized AND result = 'OK' AND detail ? 'test_open_at'
        ORDER BY audit_id DESC LIMIT 1) AS v;
SELECT 'before' AS stage, name, n FROM closure_before
WHERE name IN ('beta_users','beta_allowlist','beta_waitlist','beta_feedback','beta_feedback_messages','beta_message_votes',
               'beta_reasons','beta_user_activity','beta_price_alerts','beta_owner_forwards','beta_notification_deliveries',
               'beta_admin_audit','beta_rejected_start_hashes','beta_invites') ORDER BY name;

-- 2. cohort counter (delete_participant rule): unknown, joined at/after the opening, not the owner
INSERT INTO beta_deleted_cohort_counts AS c (joined_kyiv_date, n)
SELECT (u.joined_at AT TIME ZONE 'Europe/Kyiv')::date, count(*)
FROM beta_users u,
     LATERAL (SELECT (detail->>'test_open_at')::timestamptz AS opened FROM beta_admin_audit
              WHERE action = 'admin_test_open' AND authorized AND result = 'OK' AND detail ? 'test_open_at'
              ORDER BY audit_id DESC LIMIT 1) o
WHERE NOT u.known_contact AND u.joined_at >= o.opened AND u.telegram_user_id <> :owner_id
GROUP BY 1
ON CONFLICT (joined_kyiv_date) DO UPDATE SET n = c.n + EXCLUDED.n;

-- 2b. old deletion rows whose detail still carries a cohort record (OUT-8 rule; a no-op once OUT-8 ran)
INSERT INTO beta_deleted_cohort_counts AS c (joined_kyiv_date, n)
SELECT (a.detail->'cohort'->>'joined_kyiv_date')::date, count(*)
FROM beta_admin_audit a
WHERE a.action IN ('user_delete_me', 'retention_purge', 'admin_remove') AND jsonb_typeof(a.detail->'cohort') = 'object'
  AND COALESCE((a.detail->'cohort'->>'joined_after_test_open')::boolean, false)
  AND NOT COALESCE((a.detail->'cohort'->>'known_contact')::boolean, true)
GROUP BY 1
ON CONFLICT (joined_kyiv_date) DO UPDATE SET n = c.n + EXCLUDED.n;

-- 3. participants
DELETE FROM beta_users;
DELETE FROM beta_allowlist;
DELETE FROM beta_waitlist;

-- 4. residual text / identifiers outside the cascade
UPDATE beta_invites SET label = 'redacted' WHERE label <> 'redacted';
UPDATE beta_notification_deliveries SET error_summary = 'redacted' WHERE error_summary IS NOT NULL AND error_summary <> 'redacted';
DELETE FROM beta_rejected_start_hashes;
DO $$
BEGIN
    IF to_regclass('public.telegram_notification_deliveries') IS NOT NULL THEN
        EXECUTE 'UPDATE telegram_notification_deliveries SET recipient_fingerprint = NULL WHERE recipient_fingerprint IS NOT NULL';
    END IF;
    IF to_regclass('public.telegram_notifier_state') IS NOT NULL THEN
        EXECUTE 'UPDATE telegram_notifier_state SET recipient_fingerprint = NULL WHERE recipient_fingerprint IS NOT NULL';
    END IF;
EXCEPTION WHEN undefined_column THEN
    RAISE NOTICE 'legacy notifier tables have no recipient_fingerprint column; skipped';
END $$;

-- 5. audit: every person fingerprint, owner's first (role owner), then the rest (role participant)
-- (psql does not interpolate :vars inside dollar-quoted bodies, hence set_config)
SELECT set_config('closure.owner_fps', :'owner_fps', true);
DO $$
DECLARE
    owner_list TEXT[] := string_to_array(NULLIF(current_setting('closure.owner_fps', true), ''), ',');
    others TEXT[];
    n_owner INTEGER := 0;
    n_part INTEGER := 0;
BEGIN
    IF owner_list IS NOT NULL THEN
        n_owner := beta_audit_deidentify(owner_list, 'owner');
    END IF;
    SELECT array_agg(DISTINCT fp) INTO others FROM (
        SELECT actor_fingerprint AS fp FROM beta_admin_audit WHERE actor_fingerprint ~ '^u_[0-9a-f]{12}$'
        UNION SELECT target_fingerprint FROM beta_admin_audit WHERE target_fingerprint ~ '^u_[0-9a-f]{12}$') f
    WHERE owner_list IS NULL OR NOT (fp = ANY (owner_list));
    IF others IS NOT NULL THEN
        n_part := beta_audit_deidentify(others, 'participant');
    END IF;
    RAISE NOTICE 'audit rows de-identified: owner % participant %', n_owner, n_part;
END $$;

-- 6. verification (any failure raises and rolls back)
DO $$
DECLARE
    bad TEXT;
    n BIGINT;
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['beta_users','beta_allowlist','beta_waitlist','beta_feedback','beta_feedback_messages',
                             'beta_message_votes','beta_reasons','beta_user_activity','beta_price_alerts',
                             'beta_owner_forwards','beta_rejected_start_hashes'] LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('SELECT count(*) FROM public.%I', t) INTO n;
            IF n <> 0 THEN RAISE EXCEPTION 'participant table % still has % rows', t, n; END IF;
        END IF;
    END LOOP;
    SELECT count(*) INTO n FROM beta_admin_audit
    WHERE actor_fingerprint ~ '^u_[0-9a-f]{12}$' OR target_fingerprint ~ '^u_[0-9a-f]{12}$' OR detail <> '{}'::jsonb;
    IF n <> 0 THEN RAISE EXCEPTION 'audit still holds % identifiable rows', n; END IF;
    SELECT count(*) INTO n FROM beta_notification_deliveries WHERE user_pk IS NOT NULL;
    IF n <> 0 THEN RAISE EXCEPTION 'deliveries still linked to users: %', n; END IF;
    -- result tables: counts unchanged
    FOR t IN SELECT name FROM closure_before WHERE name IN ('beta_claims','beta_claim_outcomes','beta_claim_displays',
             'beta_forecasts','beta_hist_stats','beta_hist_bars_5m','beta_hist_oi_5m','beta_episodes','beta_episode_outcomes',
             'beta_push_decisions','beta_state_tape','beta_context_snapshots','beta_market_alerts','beta_weekly_reports',
             'beta_notification_deliveries','beta_shadow_anchors','beta_shadow_issues','beta_shadow_outcomes',
             'forecast_predictions','forecast_outcomes','beta_rejected_start_counts','beta_invites') LOOP
        EXECUTE format('SELECT count(*) FROM public.%I', t) INTO n;
        IF n <> (SELECT cb.n FROM closure_before cb WHERE cb.name = t) THEN
            RAISE EXCEPTION 'result table % changed row count (% -> %)', t, (SELECT cb.n FROM closure_before cb WHERE cb.name = t), n;
        END IF;
    END LOOP;
END $$;
SELECT 'after' AS stage, name, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', name), false, true, '')))[1]::text::bigint AS n
FROM closure_before WHERE name IN ('beta_users','beta_allowlist','beta_waitlist','beta_feedback_messages','beta_user_activity',
                                   'beta_admin_audit','beta_deleted_cohort_counts','beta_claims','beta_forecasts') ORDER BY name;
SELECT 'counter' AS stage, joined_kyiv_date, n FROM beta_deleted_cohort_counts ORDER BY 2;
SELECT tgname, tgenabled FROM pg_trigger WHERE tgname = 'trg_beta_audit_append_only';

\if :apply
COMMIT;
\echo 'COMMITTED. Next: VACUUM (FULL) beta_users, beta_allowlist, beta_waitlist, beta_feedback, beta_feedback_messages, beta_message_votes, beta_reasons, beta_user_activity, beta_price_alerts, beta_owner_forwards, beta_notification_deliveries, beta_admin_audit, beta_invites, beta_rejected_start_hashes; then CHECKPOINT.'
\else
ROLLBACK;
\echo 'DRY RUN: rolled back; re-run with -v apply=1'
\endif
