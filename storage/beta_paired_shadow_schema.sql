-- Paired shadow store for Rangecast V1 and Rangecast V2.
--
-- Additive and standalone. Not included in storage/beta_v0_schema.sql and not applied
-- by apply_beta_schema. Creating these tables needs a separate owner permission
-- (scripts/beta/apply_paired_shadow_schema.py). Nothing here alters the user
-- claim journal, roles, or user text.
--
-- The export view omits barrier levels. Those levels stay on the host so the shared
-- outcome can be scored again; they are not part of an anonymized export.

CREATE OR REPLACE FUNCTION beta_shadow_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'paired shadow table % is append-only (% rejected)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TABLE IF NOT EXISTS beta_shadow_anchors (
    anchor_pk         BIGSERIAL PRIMARY KEY,
    anchor_key        TEXT NOT NULL UNIQUE,
    symbol            TEXT NOT NULL CHECK (symbol = 'BTCUSDT'),
    family            TEXT NOT NULL CHECK (family IN ('touch', 'neither')),
    horizon           TEXT NOT NULL CHECK (horizon IN ('1h', '4h', '24h')),
    issue_slot        TIMESTAMPTZ NOT NULL,
    as_of             TIMESTAMPTZ NOT NULL,
    horizon_end       TIMESTAMPTZ NOT NULL CHECK (horizon_end > as_of),
    side              SMALLINT CHECK (side IS NULL OR side IN (-1, 1)),
    distance_pct      DOUBLE PRECISION,
    distance_up_pct   DOUBLE PRECISION,
    distance_down_pct DOUBLE PRECISION,
    level_up          DOUBLE PRECISION,
    level_down        DOUBLE PRECISION,
    eval_rule_id      TEXT NOT NULL CHECK (eval_rule_id IN ('TOUCH_V1', 'NEITHER_V1')),
    eval_rule_digest  TEXT NOT NULL CHECK (eval_rule_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_beta_shadow_anchor_shape CHECK (
        (family = 'touch' AND side IS NOT NULL AND distance_pct > 0
            AND distance_up_pct IS NULL AND distance_down_pct IS NULL
            AND eval_rule_id = 'TOUCH_V1'
            AND ((side = 1 AND level_up IS NOT NULL AND level_down IS NULL)
              OR (side = -1 AND level_down IS NOT NULL AND level_up IS NULL)))
        OR
        (family = 'neither' AND side IS NULL AND distance_pct IS NULL
            AND distance_up_pct > 0 AND distance_down_pct > 0
            AND level_up IS NOT NULL AND level_down IS NOT NULL
            AND eval_rule_id = 'NEITHER_V1')
    )
);
DROP TRIGGER IF EXISTS trg_beta_shadow_anchors_append_only ON beta_shadow_anchors;
CREATE TRIGGER trg_beta_shadow_anchors_append_only
    BEFORE UPDATE OR DELETE ON beta_shadow_anchors
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_reject_mutation();

CREATE TABLE IF NOT EXISTS beta_shadow_issues (
    issue_pk      BIGSERIAL PRIMARY KEY,
    anchor_pk     BIGINT NOT NULL REFERENCES beta_shadow_anchors (anchor_pk),
    procedure_id  TEXT NOT NULL CHECK (procedure_id ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    spec_id       TEXT NOT NULL CHECK (spec_id ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    spec_digest   TEXT NOT NULL CHECK (spec_digest ~ '^[0-9a-f]{64}$'),
    snapshot_id   TEXT NOT NULL CHECK (length(snapshot_id) BETWEEN 1 AND 128),
    probability   DOUBLE PRECISION NOT NULL CHECK (probability >= 0 AND probability <= 1),
    issued_at     TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_beta_shadow_issue UNIQUE (anchor_pk, procedure_id, spec_id)
);
CREATE TABLE IF NOT EXISTS beta_shadow_spec_identity (
    procedure_id  TEXT NOT NULL CHECK (procedure_id ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    spec_id       TEXT NOT NULL CHECK (spec_id ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    spec_digest   TEXT NOT NULL CHECK (spec_digest ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (procedure_id, spec_id)
);
DROP TRIGGER IF EXISTS trg_beta_shadow_spec_identity_append_only ON beta_shadow_spec_identity;
CREATE TRIGGER trg_beta_shadow_spec_identity_append_only
    BEFORE UPDATE OR DELETE ON beta_shadow_spec_identity
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_reject_mutation();

CREATE OR REPLACE FUNCTION beta_shadow_issue_identity_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    existing TEXT;
BEGIN
    INSERT INTO beta_shadow_spec_identity (procedure_id, spec_id, spec_digest)
    VALUES (NEW.procedure_id, NEW.spec_id, NEW.spec_digest)
    ON CONFLICT (procedure_id, spec_id) DO NOTHING;
    SELECT spec_digest INTO existing
    FROM beta_shadow_spec_identity
    WHERE procedure_id = NEW.procedure_id AND spec_id = NEW.spec_id;
    IF existing IS DISTINCT FROM NEW.spec_digest THEN
        RAISE EXCEPTION 'spec_id % already has another spec_digest; use a new spec_id', NEW.spec_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_beta_shadow_issue_identity ON beta_shadow_issues;
CREATE TRIGGER trg_beta_shadow_issue_identity
    BEFORE INSERT ON beta_shadow_issues
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_issue_identity_guard();
DROP TRIGGER IF EXISTS trg_beta_shadow_issues_append_only ON beta_shadow_issues;
CREATE TRIGGER trg_beta_shadow_issues_append_only
    BEFORE UPDATE OR DELETE ON beta_shadow_issues
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_reject_mutation();

CREATE TABLE IF NOT EXISTS beta_shadow_outcomes (
    outcome_pk            BIGSERIAL PRIMARY KEY,
    anchor_pk             BIGINT NOT NULL REFERENCES beta_shadow_anchors (anchor_pk),
    revision              INTEGER NOT NULL CHECK (revision >= 1),
    supersedes_outcome_pk BIGINT REFERENCES beta_shadow_outcomes (outcome_pk),
    status                TEXT NOT NULL CHECK (status IN ('COMPLETE', 'INCOMPLETE_DATA', 'NO_DATA')),
    outcome               SMALLINT CHECK (outcome IS NULL OR outcome IN (0, 1)),
    coverage              DOUBLE PRECISION,
    eval_rule_digest      TEXT NOT NULL CHECK (eval_rule_digest ~ '^[0-9a-f]{64}$'),
    computed_at           TIMESTAMPTZ NOT NULL,
    correction_note       TEXT,
    CONSTRAINT ck_beta_shadow_outcome_revision_link CHECK ((revision = 1) = (supersedes_outcome_pk IS NULL)),
    CONSTRAINT ck_beta_shadow_outcome_note CHECK (revision = 1 OR correction_note IS NOT NULL),
    CONSTRAINT uq_beta_shadow_outcome_revision UNIQUE (anchor_pk, revision)
);
DROP TRIGGER IF EXISTS trg_beta_shadow_outcomes_append_only ON beta_shadow_outcomes;
CREATE TRIGGER trg_beta_shadow_outcomes_append_only
    BEFORE UPDATE OR DELETE ON beta_shadow_outcomes
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_reject_mutation();

CREATE OR REPLACE FUNCTION beta_shadow_outcome_rule_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.eval_rule_digest IS DISTINCT FROM
       (SELECT eval_rule_digest FROM beta_shadow_anchors WHERE anchor_pk = NEW.anchor_pk) THEN
        RAISE EXCEPTION 'shadow anchor % outcome under another evaluation rule rejected', NEW.anchor_pk
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_beta_shadow_outcome_rule ON beta_shadow_outcomes;
CREATE TRIGGER trg_beta_shadow_outcome_rule
    BEFORE INSERT ON beta_shadow_outcomes
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_outcome_rule_guard();

CREATE TABLE IF NOT EXISTS beta_shadow_hour_status (
    status_pk    BIGSERIAL PRIMARY KEY,
    issue_slot   TIMESTAMPTZ NOT NULL,
    horizon      TEXT NOT NULL CHECK (horizon IN ('1h', '4h', '24h')),
    status       TEXT NOT NULL CHECK (status IN (
        'OK', 'STALE_DATA', 'INSUFFICIENT_HISTORY', 'INCOMPLETE_WINDOW', 'EVENT_ZONE',
        'NO_MODEL', 'MODEL_INVALID', 'NOT_COMPUTABLE', 'INVALID_TARGET', 'PENDING'
    )),
    reason       TEXT,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_beta_shadow_hour_status UNIQUE (issue_slot, horizon)
);
CREATE OR REPLACE FUNCTION beta_shadow_hour_status_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    existing_status TEXT;
    existing_reason TEXT;
BEGIN
    SELECT status, reason INTO existing_status, existing_reason
    FROM beta_shadow_hour_status
    WHERE issue_slot = NEW.issue_slot AND horizon = NEW.horizon;
    IF FOUND AND (existing_status IS DISTINCT FROM NEW.status
                  OR existing_reason IS DISTINCT FROM NEW.reason) THEN
        RAISE EXCEPTION 'hour % % already has status %', NEW.issue_slot, NEW.horizon, existing_status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_beta_shadow_hour_status_guard ON beta_shadow_hour_status;
CREATE TRIGGER trg_beta_shadow_hour_status_guard
    BEFORE INSERT ON beta_shadow_hour_status
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_hour_status_guard();
DROP TRIGGER IF EXISTS trg_beta_shadow_hour_status_append_only ON beta_shadow_hour_status;
CREATE TRIGGER trg_beta_shadow_hour_status_append_only
    BEFORE UPDATE OR DELETE ON beta_shadow_hour_status
    FOR EACH ROW EXECUTE FUNCTION beta_shadow_reject_mutation();

CREATE OR REPLACE VIEW beta_shadow_export_v1 AS
SELECT a.anchor_key,
       a.symbol,
       a.family,
       a.horizon,
       a.issue_slot,
       a.as_of,
       a.horizon_end,
       a.side,
       a.distance_pct,
       a.distance_up_pct,
       a.distance_down_pct,
       a.eval_rule_id,
       a.eval_rule_digest,
       i.procedure_id,
       i.spec_id,
       i.spec_digest,
       i.snapshot_id,
       i.probability,
       o.status,
       o.outcome,
       o.coverage,
       o.revision AS outcome_revision
FROM beta_shadow_issues i
JOIN beta_shadow_anchors a ON a.anchor_pk = i.anchor_pk
LEFT JOIN LATERAL (
    SELECT status, outcome, coverage, revision
    FROM beta_shadow_outcomes x
    WHERE x.anchor_pk = a.anchor_pk
    ORDER BY x.revision DESC
    LIMIT 1
) o ON TRUE;
