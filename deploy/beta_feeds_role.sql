-- Least-privilege DB role for signalbot-beta-feeds / signalbot-beta-stress
-- (docs/RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md §A, PREREQ-3).
--
-- Run it as the core DB superuser, in the beta database:
--   * AFTER the core role has applied storage/beta_v0_schema.sql (the feed tables must exist);
--   * again after every restore: deploy/backup.sh dumps with --no-privileges, so grants are not
--     restored (the role itself is cluster-level and survives).
-- Idempotent: every run resets the role to exactly this grant set (anything else is revoked first)
-- and fails, rolling back, if the role could still create objects or reach any other table.
-- It never sets a password: deploy/install_beta_feeds_role.sh sets one from stdin.
-- No psql variables: the same file runs under psql (production) and asyncpg (tests).
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signalbot_beta_feeds') THEN
    CREATE ROLE signalbot_beta_feeds;
  END IF;
END $$;
ALTER ROLE signalbot_beta_feeds LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
  CONNECTION LIMIT 4;
ALTER ROLE signalbot_beta_feeds SET statement_timeout = '60s';
ALTER ROLE signalbot_beta_feeds SET idle_in_transaction_session_timeout = '60s';

-- never a member of another role (no SET ROLE, no inherited rights)
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT g.rolname FROM pg_auth_members m
           JOIN pg_roles g ON g.oid = m.roleid JOIN pg_roles u ON u.oid = m.member
           WHERE u.rolname = 'signalbot_beta_feeds' LOOP
    EXECUTE format('REVOKE %I FROM signalbot_beta_feeds', r.rolname);
  END LOOP;
END $$;

-- reset (table revokes also revoke column grants), then exactly the grants the two jobs use
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM signalbot_beta_feeds;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM signalbot_beta_feeds;
REVOKE ALL ON SCHEMA public FROM signalbot_beta_feeds;
DO $$
BEGIN
  EXECUTE format('REVOKE ALL ON DATABASE %I FROM signalbot_beta_feeds', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO signalbot_beta_feeds', current_database());
END $$;
GRANT USAGE ON SCHEMA public TO signalbot_beta_feeds;
GRANT SELECT, INSERT, UPDATE ON beta_feed_metrics_5m, beta_feed_dvol_1h, beta_feed_spot_5m, beta_feed_stress_hours
  TO signalbot_beta_feeds;
GRANT SELECT, INSERT ON beta_feed_depth TO signalbot_beta_feeds;
GRANT SELECT (ts, oi_base, ls_account_ratio) ON beta_hist_oi_5m TO signalbot_beta_feeds;
GRANT SELECT, INSERT, UPDATE ON beta_runtime_health TO signalbot_beta_feeds;

-- assertions: refuse (and roll back) rather than leave a wider role
DO $$
DECLARE
  t record;
  allowed CONSTANT text[] := ARRAY['beta_feed_metrics_5m', 'beta_feed_dvol_1h', 'beta_feed_spot_5m',
                                   'beta_feed_stress_hours', 'beta_feed_depth', 'beta_runtime_health'];
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'signalbot_beta_feeds'
             AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls)) THEN
    RAISE EXCEPTION 'signalbot_beta_feeds has a role attribute it must not have';
  END IF;
  IF has_schema_privilege('signalbot_beta_feeds', 'public', 'CREATE') THEN
    RAISE EXCEPTION 'signalbot_beta_feeds could CREATE in schema public (PUBLIC holds CREATE?): '
                    'REVOKE CREATE ON SCHEMA public FROM PUBLIC first';
  END IF;
  IF has_database_privilege('signalbot_beta_feeds', current_database(), 'CREATE') THEN
    RAISE EXCEPTION 'signalbot_beta_feeds could CREATE schemas in this database';
  END IF;
  FOR t IN SELECT c.oid, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f') LOOP
    IF has_table_privilege('signalbot_beta_feeds', t.oid, 'DELETE, TRUNCATE, REFERENCES, TRIGGER') THEN
      RAISE EXCEPTION 'signalbot_beta_feeds holds DELETE/TRUNCATE/REFERENCES/TRIGGER on %', t.relname;
    END IF;
    IF t.relname <> ALL (allowed) AND t.relname <> 'beta_hist_oi_5m'
       AND has_any_column_privilege('signalbot_beta_feeds', t.oid, 'SELECT, INSERT, UPDATE') THEN
      RAISE EXCEPTION 'signalbot_beta_feeds reaches table % (a grant to PUBLIC?)', t.relname;
    END IF;
  END LOOP;
  -- beta_hist_oi_5m: SELECT of exactly ts, oi_base, ls_account_ratio; never a write
  IF EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = 'beta_hist_oi_5m'::regclass AND a.attnum > 0
             AND NOT a.attisdropped
             AND (has_column_privilege('signalbot_beta_feeds', a.attrelid, a.attnum, 'INSERT, UPDATE')
                  OR (has_column_privilege('signalbot_beta_feeds', a.attrelid, a.attnum, 'SELECT')
                      <> (a.attname IN ('ts', 'oi_base', 'ls_account_ratio'))))) THEN
    RAISE EXCEPTION 'signalbot_beta_feeds column grants on beta_hist_oi_5m differ from (ts, oi_base, ls_account_ratio)';
  END IF;
END $$;

COMMIT;
