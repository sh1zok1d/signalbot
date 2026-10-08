-- OUT-8, step 1 (READ-ONLY): the deletion audit rows written before #418 that still carry per-person data.
-- Usage: psql "$DSN" -v owner_fp='u_xxxxxxxxxxxx' -f deploy/signalbot-beta-audit-deidentify-count.sql
-- owner_fp: the owner's fingerprint (python -c "from beta.admin import fingerprint; print(fingerprint(<owner id>))").
BEGIN TRANSACTION READ ONLY;

SELECT action,
       count(*)                                                       AS rows_total,
       count(*) FILTER (WHERE target_fingerprint IS NOT NULL)         AS with_target_fingerprint,
       count(*) FILTER (WHERE target_fingerprint = :'owner_fp')       AS target_is_owner,
       count(*) FILTER (WHERE actor_fingerprint = :'owner_fp')        AS actor_is_owner,
       count(*) FILTER (WHERE detail - 'cohort' <> '{}'::jsonb)       AS with_extra_detail_keys,
       count(*) FILTER (WHERE detail->'cohort' IS NULL
                          OR detail->>'cohort' = 'null')               AS without_cohort,
       min(recorded_at)                                               AS first_at,
       max(recorded_at)                                               AS last_at
FROM beta_admin_audit
WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
GROUP BY action
ORDER BY action;

-- rows that the redaction would change (any per-person field beyond the cohort record)
SELECT count(*) AS rows_to_redact
FROM beta_admin_audit
WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove')
  AND (target_fingerprint IS NOT NULL
       OR detail - 'cohort' <> '{}'::jsonb
       OR (detail ? 'cohort' AND detail->>'cohort' <> 'null' AND NOT (detail->'cohort') ? 'joined_after_test_open'));

ROLLBACK;
