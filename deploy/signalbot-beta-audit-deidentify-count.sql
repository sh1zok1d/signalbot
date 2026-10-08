-- OUT-8 v4, step 1 (READ-ONLY): what the redaction would change. Usage, as block A of
-- docs/BETA_AUDIT_DEIDENTIFY_V1.md runs it: psql -X -v owner_fp=<the owner's unkeyed fingerprint>
--   [-v keyed_since=<timestamptz>] < deploy/signalbot-beta-audit-deidentify-count.sql
\if :{?keyed_since}
\else
\set keyed_since 'infinity'
\endif
BEGIN TRANSACTION READ ONLY;

WITH live AS (
    SELECT DISTINCT 'u_' || left(encode(sha256(convert_to('signalbot-beta-v0:' || id::text, 'UTF8')), 'hex'), 12) AS fp
    FROM (SELECT telegram_user_id AS id FROM beta_users
          UNION SELECT telegram_user_id FROM beta_allowlist
          UNION SELECT telegram_user_id FROM beta_waitlist) ids),
kinds AS (
    SELECT a.*,
           CASE WHEN a.action IN ('user_delete_me', 'retention_purge', 'admin_remove') THEN 'deletion'
                WHEN a.target_fingerprint IS NULL THEN 'no_target'
                WHEN a.recorded_at >= :'keyed_since'::timestamptz THEN 'keyed_unmatched'
                WHEN a.target_fingerprint = a.actor_fingerprint
                     AND (a.actor_fingerprint = :'owner_fp'
                          OR EXISTS (SELECT 1 FROM live l WHERE l.fp = a.actor_fingerprint)) THEN 'actor_own'
                WHEN EXISTS (SELECT 1 FROM live l WHERE l.fp = a.target_fingerprint) THEN 'live'
                ELSE 'deleted_person' END AS kind,
           (a.action NOT IN ('user_delete_me', 'retention_purge', 'admin_remove')
            AND a.recorded_at < :'keyed_since'::timestamptz
            AND a.actor_fingerprint ~ '^u_[0-9a-f]{12}$' AND a.actor_fingerprint <> :'owner_fp'
            AND NOT EXISTS (SELECT 1 FROM live l WHERE l.fp = a.actor_fingerprint)) AS actor_deleted
    FROM beta_admin_audit a)
SELECT kind, actor_deleted, action, count(*) AS rows,
       count(*) FILTER (WHERE target_fingerprint IS NOT NULL) AS with_target,
       count(*) FILTER (WHERE target_fingerprint = :'owner_fp') AS target_is_owner,
       count(*) FILTER (WHERE actor_fingerprint = :'owner_fp') AS actor_is_owner,
       count(*) FILTER (WHERE detail <> '{}'::jsonb) AS with_detail,
       min(recorded_at) AS first_at, max(recorded_at) AS last_at
FROM kinds
WHERE kind IN ('deletion', 'deleted_person', 'keyed_unmatched', 'live', 'actor_own') OR actor_deleted
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

-- old deletion rows that would move into the #420 counter (unknown, joined after the test opening)
SELECT count(*) AS deletion_rows_for_counter
FROM beta_admin_audit
WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove') AND jsonb_typeof(detail->'cohort') = 'object'
  AND COALESCE((detail->'cohort'->>'joined_after_test_open')::boolean, false)
  AND NOT COALESCE((detail->'cohort'->>'known_contact')::boolean, true);

ROLLBACK;
