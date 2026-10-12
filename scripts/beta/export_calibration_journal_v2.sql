-- Read-only JSONL export for calibration monitor V2.
-- One object per line. Whitelist of journal fields. Latest outcome revision only.
-- Coverage, the evaluation rule and outcome_revision are included.
-- tests/beta/test_calibration_journal_export.py checks these columns against
-- storage/beta_v0_schema.sql. Run under default_transaction_read_only.
-- A single SELECT, so psql -q -t -A prints JSONL and no command tag.
SELECT jsonb_strip_nulls(jsonb_build_object(
    'claim_class', c.claim_class,
    'as_of', to_char(c.as_of AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'horizon_end', to_char(c.horizon_end AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'probability', (c.numbers->>'probability')::double precision,
    'stats_digest', c.stats_digest,
    'stats_pk', c.stats_pk::text,
    'eval_rule_digest', c.eval_rule_digest,
    'eval_rule_id', c.eval_rule_id,
    'rule_version', c.rule_version,
    'status', o.status,
    'outcome_revision', o.revision,
    'realized', jsonb_strip_nulls(jsonb_build_object(
        'touched', o.realized->'touched',
        'neither', o.realized->'neither',
        'coverage', o.realized->'coverage'
    ))
))
FROM beta_claims c
LEFT JOIN LATERAL (
    SELECT x.status, x.revision, x.realized
    FROM beta_claim_outcomes x
    WHERE x.claim_pk = c.claim_pk
    ORDER BY x.revision DESC
    LIMIT 1
) o ON TRUE
WHERE c.claim_class LIKE 'L3\_%' ESCAPE '\'
ORDER BY c.as_of, c.claim_class;
