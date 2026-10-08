-- OUT-8 v4 (owner, 2026-10-08), step 2: de-identify every audit row about a participant who was deleted, and
-- reduce the old deletion rows to the minimal form of #420. Run it on a SCRATCH copy first (block A of
-- docs/BETA_AUDIT_DEIDENTIFY_V1.md); on production only after the owner's go (block B), after #420 is deployed
-- (beta_deleted_cohort_counts exists) and BEFORE the keyed fingerprints of #423 are switched on.
-- Usage: psql -X -v ON_ERROR_STOP=1 -v owner_fp=<the owner's unkeyed fingerprint> [-v keyed_since=<timestamptz>]
--   < deploy/signalbot-beta-audit-deidentify.sql
--
-- 1. Deletion rows (user_delete_me, retention_purge, admin_remove) -> the minimal form: actor kind
--    (participant / system / owner), result, the Kyiv date; target NULL; detail {}. A row whose old cohort record
--    says unknown AND joined after the test opening adds one to beta_deleted_cohort_counts for its join date
--    (rows written before any /admin_test_open never qualify).
-- 2. Rows about a deleted participant: every other audit row with a target fingerprint that belongs to nobody
--    still in beta_users, beta_allowlist or beta_waitlist (computed with the old, unkeyed formula the rows hold)
--    and is not the actor's own -> target NULL, detail {} (no nested ids, counts or attributes), the Kyiv date.
--    The fact that the action happened stays. The audit never stored reply bodies (admin_reply keeps none).
-- 3. The actor side: an actor fingerprint that is a person's (u_ + 12 hex), belongs to nobody still present and is
--    not the owner's -> 'participant', whatever the target. A row they only acted in keeps everything else; when
--    target = actor = a deleted person, both go. 'actor_own' is only a live person's or the owner's own row.
-- keyed_since: rows recorded at or after it carry #423's keyed fingerprints, which SQL cannot recompute; they are
-- left untouched and counted. Leave it unset when #423 is not deployed yet.
-- The table is append-only (trigger trg_beta_audit_append_only). The trigger is disabled only inside this
-- transaction: ALTER TABLE holds an ACCESS EXCLUSIVE lock to the end, so no other session can touch the table
-- while it is off, and any error rolls everything back, the DISABLE included. It needs the table owner.
\set ON_ERROR_STOP 1
\if :{?owner_fp}
\else
\echo 'owner_fp is required: -v owner_fp=<the owner unkeyed fingerprint>'
SELECT 1 / 0 AS owner_fp_is_required;
\endif
\if :{?keyed_since}
\else
\set keyed_since 'infinity'
\endif
\echo 'keyed_since=' :keyed_since

BEGIN;
LOCK TABLE beta_admin_audit IN ACCESS EXCLUSIVE MODE;
LOCK TABLE beta_deleted_cohort_counts IN ACCESS EXCLUSIVE MODE;

CREATE TEMP TABLE deid_live_fp ON COMMIT DROP AS
    SELECT DISTINCT 'u_' || left(encode(sha256(convert_to('signalbot-beta-v0:' || id::text, 'UTF8')), 'hex'), 12) AS fp
    FROM (SELECT telegram_user_id AS id FROM beta_users
          UNION SELECT telegram_user_id FROM beta_allowlist
          UNION SELECT telegram_user_id FROM beta_waitlist) ids;

CREATE TEMP TABLE deid_rows ON COMMIT DROP AS
    SELECT a.audit_id,
           CASE WHEN a.action IN ('user_delete_me', 'retention_purge', 'admin_remove') THEN 'deletion'
                WHEN a.target_fingerprint IS NULL THEN 'no_target'
                WHEN a.recorded_at >= :'keyed_since'::timestamptz THEN 'keyed_unmatched'
                WHEN a.target_fingerprint = a.actor_fingerprint
                     AND (a.actor_fingerprint = :'owner_fp'
                          OR EXISTS (SELECT 1 FROM deid_live_fp l WHERE l.fp = a.actor_fingerprint)) THEN 'actor_own'
                WHEN EXISTS (SELECT 1 FROM deid_live_fp l WHERE l.fp = a.target_fingerprint) THEN 'live'
                ELSE 'deleted_person' END AS kind,
           (a.action NOT IN ('user_delete_me', 'retention_purge', 'admin_remove')
            AND a.recorded_at < :'keyed_since'::timestamptz
            AND a.actor_fingerprint ~ '^u_[0-9a-f]{12}$' AND a.actor_fingerprint <> :'owner_fp'
            AND NOT EXISTS (SELECT 1 FROM deid_live_fp l WHERE l.fp = a.actor_fingerprint)) AS actor_deleted
    FROM beta_admin_audit a;

SELECT 'before' AS stage, d.kind, d.actor_deleted, a.action, count(*) AS rows,
       count(*) FILTER (WHERE a.target_fingerprint IS NOT NULL) AS with_target,
       count(*) FILTER (WHERE a.actor_fingerprint ~ '^u_[0-9a-f]{12}$') AS with_person_actor,
       count(*) FILTER (WHERE a.detail <> '{}'::jsonb) AS with_detail,
       count(*) FILTER (WHERE a.recorded_at <> date_trunc('day', a.recorded_at AT TIME ZONE 'Europe/Kyiv')
                                               AT TIME ZONE 'Europe/Kyiv') AS with_exact_time
FROM beta_admin_audit a JOIN deid_rows d USING (audit_id)
WHERE d.kind IN ('deletion', 'deleted_person', 'keyed_unmatched') OR d.actor_deleted
GROUP BY 2, 3, 4 ORDER BY 2, 3, 4;

-- the old deletion rows that qualify for the #420 counter (unknown, joined after the test opening)
INSERT INTO beta_deleted_cohort_counts AS c (joined_kyiv_date, n)
SELECT (a.detail->'cohort'->>'joined_kyiv_date')::date, count(*)
FROM beta_admin_audit a JOIN deid_rows d USING (audit_id)
WHERE d.kind = 'deletion' AND jsonb_typeof(a.detail->'cohort') = 'object'
  AND COALESCE((a.detail->'cohort'->>'joined_after_test_open')::boolean, false)
  AND NOT COALESCE((a.detail->'cohort'->>'known_contact')::boolean, true)
GROUP BY 1
ON CONFLICT (joined_kyiv_date) DO UPDATE SET n = c.n + EXCLUDED.n;

ALTER TABLE beta_admin_audit DISABLE TRIGGER trg_beta_audit_append_only;

UPDATE beta_admin_audit a
SET actor_fingerprint = CASE WHEN a.action = 'user_delete_me' THEN 'participant'
                             WHEN a.action = 'retention_purge' THEN 'system' ELSE 'owner' END,
    target_fingerprint = NULL,
    detail = '{}'::jsonb,
    recorded_at = date_trunc('day', a.recorded_at AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv'
FROM deid_rows d
WHERE d.audit_id = a.audit_id AND d.kind = 'deletion'
  AND (a.target_fingerprint IS NOT NULL OR a.detail <> '{}'::jsonb
       OR a.actor_fingerprint NOT IN ('participant', 'system', 'owner')
       OR a.recorded_at <> date_trunc('day', a.recorded_at AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv');

UPDATE beta_admin_audit a
SET target_fingerprint = NULL,
    detail = '{}'::jsonb,
    recorded_at = date_trunc('day', a.recorded_at AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv'
FROM deid_rows d
WHERE d.audit_id = a.audit_id AND d.kind = 'deleted_person';

-- the actor side: a deleted person's fingerprint as the actor becomes the role, whatever the target
UPDATE beta_admin_audit a
SET actor_fingerprint = 'participant'
FROM deid_rows d
WHERE d.audit_id = a.audit_id AND d.actor_deleted;

ALTER TABLE beta_admin_audit ENABLE TRIGGER trg_beta_audit_append_only;

SELECT 'after' AS stage, d.kind, d.actor_deleted, a.action, count(*) AS rows,
       count(*) FILTER (WHERE a.target_fingerprint IS NOT NULL) AS with_target,
       count(*) FILTER (WHERE a.actor_fingerprint ~ '^u_[0-9a-f]{12}$') AS with_person_actor,
       count(*) FILTER (WHERE a.detail <> '{}'::jsonb) AS with_detail,
       count(*) FILTER (WHERE a.recorded_at <> date_trunc('day', a.recorded_at AT TIME ZONE 'Europe/Kyiv')
                                               AT TIME ZONE 'Europe/Kyiv') AS with_exact_time
FROM beta_admin_audit a JOIN deid_rows d USING (audit_id)
WHERE d.kind IN ('deletion', 'deleted_person', 'keyed_unmatched') OR d.actor_deleted
GROUP BY 2, 3, 4 ORDER BY 2, 3, 4;
SELECT 'counter' AS stage, joined_kyiv_date, n FROM beta_deleted_cohort_counts ORDER BY 2;

-- the trigger is back on before COMMIT (tgenabled 'O' = enabled)
SELECT tgname, tgenabled FROM pg_trigger WHERE tgname = 'trg_beta_audit_append_only';
COMMIT;
