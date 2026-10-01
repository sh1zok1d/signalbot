-- Signalbot PRIVATE BETA V0.2 — additive schema (docs/PRIVATE_BETA_V0_RESTART_DECISION.md).
--
-- Separate from storage/schema.sql (Stage 1) and storage/stage2_schema.sql
-- (Stage 2 / frozen forecast tables); nothing here alters or drops any existing
-- table. Idempotent: CREATE ... IF NOT EXISTS, CREATE OR REPLACE FUNCTION and
-- DROP TRIGGER IF EXISTS + CREATE TRIGGER (a trigger drop never touches data).
-- Applied as ONE script inside ONE transaction by Database.init_beta_v0_schema().
--
-- PRIVACY: Telegram identifiers exist ONLY in beta_allowlist, beta_users (and,
-- indirectly via user_pk, beta_notification_deliveries / beta_feedback). The
-- tape / episode / transition / outcome / push-decision tables contain no
-- personal identifier. Backups of this database contain personal data.

-- ---------------------------------------------------------------------------
-- append-only guard
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION beta_v0_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'beta V0 table % is append-only (% rejected)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

-- ---------------------------------------------------------------------------
-- State tape: every evaluated / bootstrapped 5m bucket, by value, append-only.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS beta_state_tape (
    tape_id               BIGSERIAL PRIMARY KEY,
    symbol                TEXT NOT NULL CHECK (symbol = 'BTCUSDT'),
    market_type           TEXT NOT NULL CHECK (market_type = 'perp'),
    timeframe             TEXT NOT NULL CHECK (timeframe = '5m'),
    bucket_ts             TIMESTAMPTZ NOT NULL
        CHECK (date_part('second', bucket_ts) = 0
               AND (date_part('minute', bucket_ts)::int % 5) = 0),
    calculation_version   TEXT NOT NULL CHECK (calculation_version ~ '^[0-9a-f]{16}$'
                                               OR calculation_version = 'UNMATERIALIZED'),
    state_schema_version  INTEGER NOT NULL CHECK (state_schema_version > 0),
    rules_version         TEXT NOT NULL,
    rules_digest          TEXT NOT NULL CHECK (rules_digest ~ '^[0-9a-f]{64}$'),
    revision              INTEGER NOT NULL CHECK (revision >= 1),
    supersedes_tape_id    BIGINT REFERENCES beta_state_tape (tape_id),
    origin                TEXT NOT NULL CHECK (origin IN ('LIVE', 'BOOTSTRAP', 'CORRECTION_CHECK')),
    materialized          BOOLEAN NOT NULL,
    evaluation_fresh      BOOLEAN NOT NULL,
    code_version          TEXT NOT NULL,
    config_digest         TEXT NOT NULL CHECK (config_digest ~ '^[0-9a-f]{64}$'),
    raw_revision          BIGINT,
    evaluated_at          TIMESTAMPTZ NOT NULL,
    metrics               JSONB NOT NULL,
    snapshot              JSONB NOT NULL,
    feature_digest        TEXT NOT NULL CHECK (feature_digest ~ '^[0-9a-f]{64}$'),
    snapshot_digest       TEXT NOT NULL UNIQUE CHECK (snapshot_digest ~ '^[0-9a-f]{64}$'),
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- LIVE / BOOTSTRAP rows are revision 1; a later correction check APPENDS a
    -- CORRECTION_CHECK row (revision >= 2) that supersedes the previous row.
    CONSTRAINT ck_beta_tape_revision_link
        CHECK ((origin = 'CORRECTION_CHECK') = (supersedes_tape_id IS NOT NULL)),
    CONSTRAINT ck_beta_tape_revision_origin
        CHECK ((origin = 'CORRECTION_CHECK') = (revision >= 2)),
    CONSTRAINT uq_beta_tape_identity UNIQUE (symbol, market_type, timeframe, bucket_ts,
        calculation_version, state_schema_version, rules_digest, origin, revision)
);
CREATE INDEX IF NOT EXISTS ix_beta_tape_history
    ON beta_state_tape (symbol, market_type, timeframe, calculation_version,
                        state_schema_version, bucket_ts);
CREATE INDEX IF NOT EXISTS ix_beta_tape_live
    ON beta_state_tape (symbol, market_type, timeframe, bucket_ts DESC) WHERE origin = 'LIVE';
DROP TRIGGER IF EXISTS trg_beta_tape_append_only ON beta_state_tape;
CREATE TRIGGER trg_beta_tape_append_only BEFORE UPDATE OR DELETE ON beta_state_tape
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();

-- ---------------------------------------------------------------------------
-- Episodes: one row per detector episode; at most ONE open per (symbol,event_type).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS beta_episodes (
    episode_pk               BIGSERIAL PRIMARY KEY,
    public_id                TEXT NOT NULL UNIQUE CHECK (public_id ~ '^EV-[0-9A-F]{10}$'),
    symbol                   TEXT NOT NULL CHECK (symbol = 'BTCUSDT'),
    event_type               TEXT NOT NULL CHECK (event_type IN (
        'PRICE_OI_CONTRACTION_DOWN', 'PRICE_OI_CONTRACTION_UP', 'POSITION_BUILDUP_COMPRESSION',
        'TAKER_FLOW_EXTREME_BUY', 'TAKER_FLOW_EXTREME_SELL',
        'LIQUIDATION_STRESS_LONG', 'LIQUIDATION_STRESS_SHORT')),
    state                    TEXT NOT NULL CHECK (state IN ('EARLY', 'ARMED', 'TRIGGERED', 'ENDED', 'EXPIRED')),
    opened_bucket            TIMESTAMPTZ NOT NULL,
    opened_at                TIMESTAMPTZ NOT NULL,
    armed_at                 TIMESTAMPTZ,
    triggered_at             TIMESTAMPTZ,
    terminal_at              TIMESTAMPTZ,
    terminal_reason          TEXT CHECK (terminal_reason IS NULL OR terminal_reason IN (
        'CONDITION_FAILED', 'NOT_EVALUABLE', 'MAX_DURATION', 'DETECTOR_VERSION_CHANGED',
        'DETECTION_GAP')),
    rules_version            TEXT NOT NULL,
    rules_digest             TEXT NOT NULL CHECK (rules_digest ~ '^[0-9a-f]{64}$'),
    code_version             TEXT NOT NULL,
    calculation_version      TEXT NOT NULL,
    opening_tape_digest      TEXT NOT NULL CHECK (opening_tape_digest ~ '^[0-9a-f]{64}$'),
    trigger_tape_digest      TEXT CHECK (trigger_tape_digest IS NULL OR trigger_tape_digest ~ '^[0-9a-f]{64}$'),
    last_bucket              TIMESTAMPTZ NOT NULL,
    last_streak              INTEGER NOT NULL CHECK (last_streak >= 0),
    reference_price          DOUBLE PRECISION CHECK (reference_price IS NULL OR reference_price > 0),
    reference_exchanges      TEXT[] NOT NULL DEFAULT '{}',
    reference_dispersion_pct DOUBLE PRECISION,
    reference_bucket         TIMESTAMPTZ,
    correction_flag          BOOLEAN NOT NULL DEFAULT FALSE,
    correction_note          TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_beta_episode_terminal
        CHECK ((state IN ('ENDED', 'EXPIRED')) = (terminal_at IS NOT NULL AND terminal_reason IS NOT NULL)),
    CONSTRAINT ck_beta_episode_triggered
        CHECK (state <> 'TRIGGERED' OR (triggered_at IS NOT NULL AND trigger_tape_digest IS NOT NULL)),
    CONSTRAINT ck_beta_episode_ended_after_trigger
        CHECK (state <> 'ENDED' OR triggered_at IS NOT NULL),
    CONSTRAINT ck_beta_episode_expired_before_trigger
        CHECK (state <> 'EXPIRED' OR triggered_at IS NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_beta_episode_one_open
    ON beta_episodes (symbol, event_type) WHERE state IN ('EARLY', 'ARMED', 'TRIGGERED');
CREATE INDEX IF NOT EXISTS ix_beta_episode_type_terminal
    ON beta_episodes (symbol, event_type, terminal_at DESC);

CREATE TABLE IF NOT EXISTS beta_episode_transitions (
    transition_id    BIGSERIAL PRIMARY KEY,
    episode_pk       BIGINT NOT NULL REFERENCES beta_episodes (episode_pk),
    seq              INTEGER NOT NULL CHECK (seq >= 1),
    from_state       TEXT CHECK (from_state IS NULL OR from_state IN ('EARLY', 'ARMED', 'TRIGGERED')),
    to_state         TEXT NOT NULL CHECK (to_state IN ('EARLY', 'ARMED', 'TRIGGERED', 'ENDED', 'EXPIRED')),
    decision_bucket  TIMESTAMPTZ NOT NULL,
    decision_ts      TIMESTAMPTZ NOT NULL,
    snapshot_digest  TEXT NOT NULL CHECK (snapshot_digest ~ '^[0-9a-f]{64}$'),
    reason           TEXT NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_beta_transition_first CHECK ((seq = 1) = (from_state IS NULL)),
    CONSTRAINT uq_beta_transition_seq UNIQUE (episode_pk, seq),
    CONSTRAINT uq_beta_transition_state UNIQUE (episode_pk, to_state)
);
DROP TRIGGER IF EXISTS trg_beta_transitions_append_only ON beta_episode_transitions;
CREATE TRIGGER trg_beta_transitions_append_only BEFORE UPDATE OR DELETE ON beta_episode_transitions
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();

-- ---------------------------------------------------------------------------
-- Push policy decision: exactly one per TRIGGERED episode, suppression persisted.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS beta_push_decisions (
    decision_id             BIGSERIAL PRIMARY KEY,
    episode_pk              BIGINT NOT NULL UNIQUE REFERENCES beta_episodes (episode_pk),
    event_type              TEXT NOT NULL,
    decision_ts             TIMESTAMPTZ NOT NULL,
    utc_day                 DATE NOT NULL,
    would_push              BOOLEAN NOT NULL,
    decision                TEXT NOT NULL CHECK (decision IN ('PUSH', 'SUPPRESSED')),
    suppression_reason      TEXT CHECK (suppression_reason IS NULL OR suppression_reason IN (
        'DAILY_CAP', 'SAME_EVENT_COOLDOWN', 'PUSH_DISABLED', 'DELIVERY_TOO_OLD', 'DATA_DEGRADED')),
    push_enabled_effective  BOOLEAN NOT NULL,
    recorded_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_beta_push_reason CHECK ((decision = 'PUSH') = (suppression_reason IS NULL)),
    CONSTRAINT ck_beta_push_would CHECK (decision <> 'PUSH' OR would_push)
);
CREATE INDEX IF NOT EXISTS ix_beta_push_day ON beta_push_decisions (utc_day) WHERE would_push;
DROP TRIGGER IF EXISTS trg_beta_push_append_only ON beta_push_decisions;
CREATE TRIGGER trg_beta_push_append_only BEFORE UPDATE OR DELETE ON beta_push_decisions
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();

-- ---------------------------------------------------------------------------
-- Forward outcomes: factual, symmetric; append-only revisions (supersede link).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS beta_episode_outcomes (
    outcome_id            BIGSERIAL PRIMARY KEY,
    episode_pk            BIGINT NOT NULL REFERENCES beta_episodes (episode_pk),
    horizon               TEXT NOT NULL CHECK (horizon IN ('15m', '30m', '1h', '4h', '24h')),
    outcome_version       TEXT NOT NULL,
    revision              INTEGER NOT NULL CHECK (revision >= 1),
    supersedes_outcome_id BIGINT REFERENCES beta_episode_outcomes (outcome_id),
    status                TEXT NOT NULL CHECK (status IN ('COMPLETE', 'INCOMPLETE_DATA', 'REFERENCE_UNAVAILABLE')),
    anchor_ts             TIMESTAMPTZ NOT NULL,
    window_end            TIMESTAMPTZ NOT NULL,
    reference_price       DOUBLE PRECISION,
    max_up_pct            DOUBLE PRECISION,
    max_down_pct          DOUBLE PRECISION,
    close_return_pct      DOUBLE PRECISION,
    realized_range_pct    DOUBLE PRECISION,
    time_to_max_up_s      INTEGER,
    time_to_max_down_s    INTEGER,
    bars_expected         INTEGER NOT NULL,
    bars_complete         INTEGER NOT NULL,
    source_exchanges      TEXT[] NOT NULL DEFAULT '{}',
    source_raw_revision   BIGINT,
    outcome_digest        TEXT NOT NULL CHECK (outcome_digest ~ '^[0-9a-f]{64}$'),
    correction_note       TEXT,
    computed_at           TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_beta_outcome_revision_link CHECK ((revision = 1) = (supersedes_outcome_id IS NULL)),
    CONSTRAINT ck_beta_outcome_complete_values CHECK (status <> 'COMPLETE' OR (
        max_up_pct IS NOT NULL AND max_down_pct IS NOT NULL AND close_return_pct IS NOT NULL
        AND realized_range_pct IS NOT NULL AND bars_complete = bars_expected)),
    CONSTRAINT uq_beta_outcome_revision UNIQUE (episode_pk, horizon, outcome_version, revision)
);
DROP TRIGGER IF EXISTS trg_beta_outcomes_append_only ON beta_episode_outcomes;
CREATE TRIGGER trg_beta_outcomes_append_only BEFORE UPDATE OR DELETE ON beta_episode_outcomes
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();

-- ---------------------------------------------------------------------------
-- Runner watermarks / runtime health / durable operational state.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS beta_detector_watermark (
    runner_name  TEXT NOT NULL CHECK (runner_name IN ('detector', 'bootstrap')),
    symbol       TEXT NOT NULL,
    market_type  TEXT NOT NULL,
    timeframe    TEXT NOT NULL,
    bucket_ts    TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (runner_name, symbol, market_type, timeframe)
);

CREATE TABLE IF NOT EXISTS beta_runtime_health (
    component        TEXT PRIMARY KEY,
    last_run_at      TIMESTAMPTZ NOT NULL,
    last_success_at  TIMESTAMPTZ,
    last_error_type  TEXT,
    detail           JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS beta_runtime_state (
    state_key   TEXT PRIMARY KEY CHECK (state_key IN ('admin_push_enabled')),
    bool_value  BOOLEAN NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Participants (PERSONAL DATA).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS beta_allowlist (
    telegram_user_id  BIGINT PRIMARY KEY CHECK (telegram_user_id > 0),
    added_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS beta_users (
    user_pk              BIGSERIAL PRIMARY KEY,
    telegram_user_id     BIGINT NOT NULL UNIQUE CHECK (telegram_user_id > 0),
    chat_id              BIGINT NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('ACTIVE', 'STOPPED')),
    privacy_accepted_at  TIMESTAMPTZ NOT NULL,
    joined_at            TIMESTAMPTZ NOT NULL,
    stopped_at           TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    lang                 TEXT NOT NULL DEFAULT 'ru' CHECK (lang IN ('ru', 'en')),
    CONSTRAINT ck_beta_user_stopped CHECK ((status = 'STOPPED') = (stopped_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS beta_bot_update_state (
    bot_name        TEXT PRIMARY KEY,
    last_update_id  BIGINT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS beta_notification_deliveries (
    delivery_id          BIGSERIAL PRIMARY KEY,
    decision_id          BIGINT NOT NULL REFERENCES beta_push_decisions (decision_id),
    episode_pk           BIGINT NOT NULL REFERENCES beta_episodes (episode_pk),
    user_pk              BIGINT REFERENCES beta_users (user_pk) ON DELETE SET NULL,
    state                TEXT NOT NULL CHECK (state IN ('PENDING', 'SENDING', 'SENT', 'FAILED',
                                                        'DELIVERY_UNKNOWN', 'EXPIRED_UNDELIVERED', 'SUPPRESSED')),
    suppression_reason   TEXT CHECK (suppression_reason IS NULL OR suppression_reason IN (
        'PUSH_DISABLED', 'DELIVERY_TOO_OLD', 'USER_INACTIVE')),
    decision_ts          TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    sending_at           TIMESTAMPTZ,
    finished_at          TIMESTAMPTZ,
    telegram_message_id  BIGINT,
    error_summary        TEXT,
    CONSTRAINT ck_beta_delivery_suppressed CHECK (
        (state IN ('SUPPRESSED', 'EXPIRED_UNDELIVERED')) = (suppression_reason IS NOT NULL)),
    CONSTRAINT ck_beta_delivery_sent CHECK ((state = 'SENT') = (telegram_message_id IS NOT NULL)),
    CONSTRAINT ck_beta_delivery_attempted CHECK (
        state NOT IN ('SENDING', 'SENT', 'FAILED', 'DELIVERY_UNKNOWN') OR sending_at IS NOT NULL
        OR (state = 'FAILED' AND error_summary IS NOT NULL)),
    CONSTRAINT uq_beta_delivery_identity UNIQUE (decision_id, user_pk)
);
CREATE INDEX IF NOT EXISTS ix_beta_delivery_state ON beta_notification_deliveries (state);

CREATE TABLE IF NOT EXISTS beta_feedback (
    feedback_id  BIGSERIAL PRIMARY KEY,
    user_pk      BIGINT NOT NULL REFERENCES beta_users (user_pk) ON DELETE CASCADE,
    episode_pk   BIGINT NOT NULL REFERENCES beta_episodes (episode_pk),
    vote         TEXT NOT NULL CHECK (vote IN ('USEFUL', 'NOISE')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_beta_feedback_vote UNIQUE (user_pk, episode_pk)
);

-- Owner admin audit: pseudonymous fingerprints only, never raw Telegram ids.
CREATE TABLE IF NOT EXISTS beta_admin_audit (
    audit_id            BIGSERIAL PRIMARY KEY,
    action              TEXT NOT NULL CHECK (action IN (
        'admin_status', 'admin_users', 'admin_add', 'admin_remove', 'admin_pause_push',
        'admin_resume_push', 'admin_broadcast', 'admin_health', 'user_delete_me', 'retention_purge')),
    authorized          BOOLEAN NOT NULL,
    actor_fingerprint   TEXT NOT NULL,
    target_fingerprint  TEXT,
    result              TEXT NOT NULL,
    detail              JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_beta_audit_append_only ON beta_admin_audit;
CREATE TRIGGER trg_beta_audit_append_only BEFORE UPDATE OR DELETE ON beta_admin_audit
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();

-- ---------------------------------------------------------------------------
-- Temporal context (episodization V0): the deterministic projection of the tape.
-- One append-only state per closed 5m bucket per (episodization, context, rules)
-- version; `prev_state_digest` chains consecutive states.
CREATE TABLE IF NOT EXISTS beta_context_snapshots (
    context_pk             BIGSERIAL PRIMARY KEY,
    symbol                 TEXT NOT NULL CHECK (symbol = 'BTCUSDT'),
    bucket_ts              TIMESTAMPTZ NOT NULL
        CHECK (date_part('second', bucket_ts) = 0
               AND (date_part('minute', bucket_ts)::int % 5) = 0),
    episodization_version  TEXT NOT NULL,
    episodization_digest   TEXT NOT NULL CHECK (episodization_digest ~ '^[0-9a-f]{64}$'),
    context_version        TEXT NOT NULL,
    context_digest         TEXT NOT NULL CHECK (context_digest ~ '^[0-9a-f]{64}$'),
    rules_digest           TEXT NOT NULL CHECK (rules_digest ~ '^[0-9a-f]{64}$'),
    tape_id                BIGINT REFERENCES beta_state_tape (tape_id),
    tape_revision          INTEGER CHECK (tape_revision IS NULL OR tape_revision >= 1),
    prev_state_digest      TEXT CHECK (prev_state_digest IS NULL OR prev_state_digest ~ '^[0-9a-f]{64}$'),
    state                  JSONB NOT NULL,
    state_digest           TEXT NOT NULL CHECK (state_digest ~ '^[0-9a-f]{64}$'),
    recorded_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_beta_context_bucket
        UNIQUE (symbol, bucket_ts, episodization_digest, context_digest, rules_digest)
);
DROP TRIGGER IF EXISTS trg_beta_context_append_only ON beta_context_snapshots;
CREATE TRIGGER trg_beta_context_append_only BEFORE UPDATE OR DELETE ON beta_context_snapshots
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();

-- What a /btc request actually showed (no user id): the compact view model, its
-- digest and the rendered text, tied to the context state it was built from.
CREATE TABLE IF NOT EXISTS beta_btc_views (
    view_pk                BIGSERIAL PRIMARY KEY,
    requested_at           TIMESTAMPTZ NOT NULL,
    as_of_bucket           TIMESTAMPTZ,
    context_state_digest   TEXT CHECK (context_state_digest IS NULL OR context_state_digest ~ '^[0-9a-f]{64}$'),
    episodization_version  TEXT,
    episodization_digest   TEXT CHECK (episodization_digest IS NULL OR episodization_digest ~ '^[0-9a-f]{64}$'),
    payload                JSONB NOT NULL,
    payload_digest         TEXT NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
    rendered_sha256        TEXT NOT NULL CHECK (rendered_sha256 ~ '^[0-9a-f]{64}$'),
    rendered_html          TEXT NOT NULL,
    lang                   TEXT NOT NULL DEFAULT 'ru' CHECK (lang IN ('ru', 'en')),
    recorded_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_beta_btc_views_append_only ON beta_btc_views;
CREATE TRIGGER trg_beta_btc_views_append_only BEFORE UPDATE OR DELETE ON beta_btc_views
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();

-- Additive columns for databases created before the language / horizon pass.
-- CREATE TABLE IF NOT EXISTS does not add columns to an existing table.
ALTER TABLE beta_users ADD COLUMN IF NOT EXISTS lang TEXT NOT NULL DEFAULT 'ru' CHECK (lang IN ('ru', 'en'));
ALTER TABLE beta_btc_views ADD COLUMN IF NOT EXISTS lang TEXT NOT NULL DEFAULT 'ru' CHECK (lang IN ('ru', 'en'));

-- Which horizon tab was opened. No user id: same privacy posture as beta_btc_views.
CREATE TABLE IF NOT EXISTS beta_details_opens (
    open_pk    BIGSERIAL PRIMARY KEY,
    view_pk    BIGINT NOT NULL REFERENCES beta_btc_views (view_pk),
    tab        TEXT NOT NULL,
    lang       TEXT NOT NULL CHECK (lang IN ('ru', 'en')),
    opened_at  TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_beta_details_opens_tab CHECK (tab IN ('event', '1h', '24h'))
);
-- Widen tab to 24h. PR 1 created an unnamed column check (beta_details_opens_tab_check).
-- Drop both that name and this name, then re-add the named check. Idempotent.
ALTER TABLE beta_details_opens DROP CONSTRAINT IF EXISTS beta_details_opens_tab_check;
ALTER TABLE beta_details_opens DROP CONSTRAINT IF EXISTS ck_beta_details_opens_tab;
ALTER TABLE beta_details_opens ADD CONSTRAINT ck_beta_details_opens_tab
    CHECK (tab IN ('event', '1h', '24h'));
CREATE INDEX IF NOT EXISTS ix_beta_details_opens_view ON beta_details_opens (view_pk, opened_at);
DROP TRIGGER IF EXISTS trg_beta_details_opens_append_only ON beta_details_opens;
CREATE TRIGGER trg_beta_details_opens_append_only BEFORE UPDATE OR DELETE ON beta_details_opens
    FOR EACH ROW EXECUTE FUNCTION beta_v0_reject_mutation();
