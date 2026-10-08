-- OUT-8, step 2: de-identify the deletion audit rows written before #418. Run it on a SCRATCH copy first
-- (docs/BETA_AUDIT_DEIDENTIFY_V1.md); on production only after the owner's go.
-- Usage: psql "$DSN" -v ON_ERROR_STOP=1 -f deploy/signalbot-beta-audit-deidentify.sql
--
-- What it does, in one transaction:
--   * keeps only detail.cohort {joined_kyiv_date, known_contact, joined_after_test_open = false};
--     every pre-#418 deletion predates any /admin_test_open, so false is the true value;
--   * sets target_fingerprint to NULL;
--   * leaves audit_id, action, authorized, actor_fingerprint, result and recorded_at as they are.
-- The table is append-only (trigger trg_beta_audit_append_only). The trigger is disabled only inside this
-- transaction: ALTER TABLE takes an ACCESS EXCLUSIVE lock, so no other session can write the table while it
-- is off, and any error rolls the whole transaction back, the DISABLE included. It needs the table owner.
\set ON_ERROR_STOP 1
BEGIN;
LOCK TABLE beta_admin_audit IN ACCESS EXCLUSIVE MODE;

SELECT 'before' AS stage, action, count(*) AS rows,
       count(*) FILTER (WHERE target_fingerprint IS NOT NULL) AS with_target_fingerprint,
       count(*) FILTER (WHERE detail - 'cohort' <> '{}'::jsonb) AS with_extra_detail_keys
FROM beta_admin_audit WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
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

ALTER TABLE beta_admin_audit ENABLE TRIGGER trg_beta_audit_append_only;

SELECT 'after' AS stage, action, count(*) AS rows,
       count(*) FILTER (WHERE target_fingerprint IS NOT NULL) AS with_target_fingerprint,
       count(*) FILTER (WHERE detail - 'cohort' <> '{}'::jsonb) AS with_extra_detail_keys
FROM beta_admin_audit WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
GROUP BY action ORDER BY action;

-- the trigger is back on before COMMIT (tgenabled 'O' = enabled)
SELECT tgname, tgenabled FROM pg_trigger WHERE tgname = 'trg_beta_audit_append_only';
COMMIT;
