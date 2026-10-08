-- OUT-8, step 2: de-identify the audit rows written before #418. Run it on a SCRATCH copy first
-- (docs/BETA_AUDIT_DEIDENTIFY_V1.md, block A); on production only after the owner's go (block B).
-- Usage: psql -X -v ON_ERROR_STOP=1 [-v coarsen=off] [-v other_actions=off] -f deploy/signalbot-beta-audit-deidentify.sql
--
-- Always, for the deletion rows (user_delete_me, retention_purge, admin_remove):
--   * detail keeps only cohort {joined_kyiv_date, known_contact, joined_after_test_open = false}; every pre-#418
--     deletion predates any /admin_test_open, so false is the true value;
--   * target_fingerprint becomes NULL.
-- Owner switches, defaulting to the most protective until the owner answers (OUT-8):
--   coarsen       (default on)  recorded_at of the deletion rows is cut to 00:00 of its Kyiv date;
--   other_actions (default on)  admin_known / admin_reply / admin_add rows whose target fingerprint belongs to
--                               nobody still in beta_users, beta_allowlist or beta_waitlist (a deleted person) lose
--                               that fingerprint; the owner's own fingerprint is never touched.
-- Salting the fingerprint itself is a separate code change, not this script.
-- The table is append-only (trigger trg_beta_audit_append_only). The trigger is disabled only inside this
-- transaction: ALTER TABLE holds an ACCESS EXCLUSIVE lock to the end, so no other session can touch the table
-- while it is off, and any error rolls everything back, the DISABLE included. It needs the table owner.
\set ON_ERROR_STOP 1
\if :{?coarsen}
\else
\set coarsen on
\endif
\if :{?other_actions}
\else
\set other_actions on
\endif
\echo 'switches: coarsen=' :coarsen ' other_actions=' :other_actions

BEGIN;
LOCK TABLE beta_admin_audit IN ACCESS EXCLUSIVE MODE;

CREATE TEMP VIEW deid_live_fp AS
    SELECT 'u_' || left(encode(sha256(convert_to('signalbot-beta-v0:' || id::text, 'UTF8')), 'hex'), 12) AS fp
    FROM (SELECT telegram_user_id AS id FROM beta_users
          UNION SELECT telegram_user_id FROM beta_allowlist
          UNION SELECT telegram_user_id FROM beta_waitlist) ids;

SELECT 'before' AS stage, action, count(*) AS rows,
       count(*) FILTER (WHERE target_fingerprint IS NOT NULL) AS with_target_fingerprint,
       count(*) FILTER (WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
                          AND detail - 'cohort' <> '{}'::jsonb) AS with_extra_detail_keys,
       count(*) FILTER (WHERE recorded_at <> date_trunc('day', recorded_at AT TIME ZONE 'Europe/Kyiv')
                                             AT TIME ZONE 'Europe/Kyiv') AS with_exact_time
FROM beta_admin_audit
WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove', 'admin_known', 'admin_reply', 'admin_add')
GROUP BY action ORDER BY action;

ALTER TABLE beta_admin_audit DISABLE TRIGGER trg_beta_audit_append_only;

UPDATE beta_admin_audit
SET target_fingerprint = NULL,
    detail = jsonb_build_object('cohort',
        CASE WHEN detail ? 'cohort' AND detail->>'cohort' <> 'null'
             THEN jsonb_build_object('joined_kyiv_date', detail->'cohort'->'joined_kyiv_date',
                                     'known_contact', detail->'cohort'->'known_contact',
                                     'joined_after_test_open', COALESCE(detail->'cohort'->'joined_after_test_open',
                                                                        'false'::jsonb))
             ELSE 'null'::jsonb END)
WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
  AND (target_fingerprint IS NOT NULL
       OR detail - 'cohort' <> '{}'::jsonb
       OR (detail ? 'cohort' AND detail->>'cohort' <> 'null' AND NOT (detail->'cohort') ? 'joined_after_test_open'));

\if :coarsen
UPDATE beta_admin_audit
SET recorded_at = date_trunc('day', recorded_at AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv'
WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
  AND recorded_at <> date_trunc('day', recorded_at AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv';
\endif

\if :other_actions
UPDATE beta_admin_audit a
SET target_fingerprint = NULL
WHERE a.action IN ('admin_known', 'admin_reply', 'admin_add')
  AND a.target_fingerprint IS NOT NULL
  AND a.target_fingerprint <> a.actor_fingerprint                   -- the owner's own fingerprint stays
  AND NOT EXISTS (SELECT 1 FROM deid_live_fp l WHERE l.fp = a.target_fingerprint);
\endif

ALTER TABLE beta_admin_audit ENABLE TRIGGER trg_beta_audit_append_only;

SELECT 'after' AS stage, action, count(*) AS rows,
       count(*) FILTER (WHERE target_fingerprint IS NOT NULL) AS with_target_fingerprint,
       count(*) FILTER (WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
                          AND detail - 'cohort' <> '{}'::jsonb) AS with_extra_detail_keys,
       count(*) FILTER (WHERE recorded_at <> date_trunc('day', recorded_at AT TIME ZONE 'Europe/Kyiv')
                                             AT TIME ZONE 'Europe/Kyiv') AS with_exact_time
FROM beta_admin_audit
WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove', 'admin_known', 'admin_reply', 'admin_add')
GROUP BY action ORDER BY action;

-- the trigger is back on before COMMIT (tgenabled 'O' = enabled)
SELECT tgname, tgenabled FROM pg_trigger WHERE tgname = 'trg_beta_audit_append_only';
COMMIT;
