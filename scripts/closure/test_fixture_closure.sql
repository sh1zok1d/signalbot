-- Synthetic fixture for the closure tests (scripts/closure/test_deidentify_closure.sh, test_backup_restore.sh).
-- Every id, text and number here is invented; nothing comes from the production database.
-- Participants: 1001 = owner (known), 1002 = known contact, 1003 and 1004 = unknown participants who joined after the
-- test opening (one STOPPED), 1005 = joined before the opening; 1006 waitlisted only; 1007 allowlisted only.
BEGIN;
INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, target_fingerprint, result, detail, recorded_at) VALUES
  ('admin_test_open', true, 'u_0123456789ab', NULL, 'OK', '{"test_open_at": "2026-10-01T10:00:00+00:00"}', '2026-10-01 10:00:00+00');
INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at, stopped_at, lang, known_contact, tz, trader_type, brief_time, tier) VALUES
  (1001, 1001, 'ACTIVE', '2026-09-20 09:00+00', '2026-09-20 09:00+00', NULL, 'ru', true,  'Europe/Kyiv', 'swing', '08:00', 'free'),
  (1002, 1002, 'ACTIVE', '2026-10-02 09:00+00', '2026-10-02 09:00+00', NULL, 'ru', true,  'Europe/Kyiv', 'intraday', '08:00', 'free'),
  (1003, 1003, 'ACTIVE', '2026-10-02 12:00+00', '2026-10-02 12:00+00', NULL, 'en', false, 'UTC', 'scalp', '07:30', 'free'),
  (1004, 1004, 'STOPPED', '2026-10-03 22:30+00', '2026-10-03 22:30+00', '2026-10-09 10:00+00', 'ru', false, 'Europe/Kyiv', 'invest', '09:00', 'free'),
  (1005, 1005, 'ACTIVE', '2026-09-25 09:00+00', '2026-09-25 09:00+00', NULL, 'ru', false, 'Europe/Kyiv', 'swing', '08:00', 'free');
INSERT INTO beta_allowlist (telegram_user_id, added_at, invite_code) VALUES (1001, now(), NULL), (1002, now(), NULL), (1003, now(), NULL), (1004, now(), NULL), (1005, now(), NULL), (1007, now(), NULL);
INSERT INTO beta_waitlist (telegram_user_id, requested_at) VALUES (1006, now());
INSERT INTO beta_invites (code, label, max_uses) VALUES ('AbCdEfGhIjKl', 'friend from the chat', 3);
INSERT INTO beta_feedback_messages (user_pk, text, lang, created_at)
  SELECT user_pk, 'free text that could identify me: my dog is called Rex', lang, now() FROM beta_users WHERE telegram_user_id IN (1002, 1003);
INSERT INTO beta_user_activity (user_pk, action, detail, lang, at) SELECT user_pk, 'cmd_btc', 'tab=1h', lang, now() FROM beta_users;
INSERT INTO beta_message_votes (user_pk, kind, ref, vote) SELECT user_pk, 'level', 7, 'NOISE' FROM beta_users WHERE telegram_user_id = 1003;
INSERT INTO beta_reasons (user_pk, topic, subject, reason, at) SELECT user_pk, 'noise', 'level:7', 'too_often', now() FROM beta_users WHERE telegram_user_id = 1003;
INSERT INTO beta_price_alerts (user_pk, price, direction, created_at, created_price) SELECT user_pk, 70000, 'above', now(), 65000 FROM beta_users WHERE telegram_user_id = 1004;
INSERT INTO beta_owner_forwards (owner_message_id, user_pk, kind, created_at) SELECT 5001, user_pk, 'feedback', now() FROM beta_users WHERE telegram_user_id = 1003;
INSERT INTO beta_rejected_start_hashes (utc_day, user_hmac) VALUES ('2026-10-05', repeat('a', 64)), ('2026-10-06', repeat('b', 64));
INSERT INTO beta_rejected_start_counts (utc_day, attempt_count) VALUES ('2026-10-05', 1), ('2026-10-06', 1) ON CONFLICT DO NOTHING;
-- audit rows: legacy and keyed fingerprints of the people above (strings only; nothing is recomputed)
INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, target_fingerprint, result, detail, recorded_at) VALUES
  ('admin_add',    true, 'u_0123456789ab', 'u_aaaaaaaaaaaa', 'OK', '{"telegram_user_id": 1003, "note": "x"}', '2026-10-02 12:05:17+00'),
  ('admin_reply',  true, 'u_0123456789ab', 'u_bbbbbbbbbbbb', 'OK', '{"len": 40}', '2026-10-04 08:15:00+00'),
  ('user_delete_me', true, 'u_cccccccccccc', NULL, 'OK', '{"cohort": {"joined_kyiv_date": "2026-10-03", "joined_after_test_open": true, "known_contact": false}}', '2026-10-08 20:00:00+00'),
  ('admin_status', true, 'u_0123456789ab', NULL, 'OK', '{"active": 4}', '2026-10-09 09:00:00+00');
-- result tables (no user identifiers) — must be byte-identical after de-identification
INSERT INTO beta_hist_stats (version, built_at, data_from, data_through, payload, payload_digest) VALUES
  ('TEST_V1', '2026-10-10 02:30+00', '2020-01-01', '2026-10-09', '{"range_4h": {"n": 1234, "q50": 1.1}}', repeat('0', 64));
INSERT INTO beta_forecasts (horizon, issued_at, horizon_end, anchor_price, lower, upper, coverage, model_version, stats_pk, outcome, realized_high, realized_low, evaluated_at)
  SELECT '4h', '2026-10-10 08:00+00', '2026-10-10 12:00+00', 65000, 64000, 66000, 0.8, 'RANGECAST_V1', stats_pk, 'INSIDE', 65500, 64500, '2026-10-10 12:05+00' FROM beta_hist_stats;
INSERT INTO beta_episodes (public_id, symbol, event_type, state, opened_bucket, opened_at, rules_version, rules_digest, code_version, calculation_version, opening_tape_digest, last_bucket, last_streak)
  VALUES ('EV-0000000001', 'BTCUSDT', 'TAKER_FLOW_EXTREME_BUY', 'EARLY', '2026-10-10 08:00+00', '2026-10-10 08:00+00', 'R1', repeat('1', 64), 'c1', 'v1', repeat('2', 64), '2026-10-10 08:00+00', 1);
INSERT INTO beta_push_decisions (episode_pk, event_type, decision_ts, utc_day, would_push, decision, push_enabled_effective)
  SELECT episode_pk, event_type, '2026-10-10 08:05+00', '2026-10-10', true, 'PUSH', true FROM beta_episodes;
INSERT INTO beta_notification_deliveries (decision_id, episode_pk, user_pk, state, decision_ts, sending_at, finished_at, telegram_message_id, error_summary)
  SELECT d.decision_id, d.episode_pk, u.user_pk, 'SENT', d.decision_ts, d.decision_ts, d.decision_ts, 900 + u.user_pk, NULL
  FROM beta_push_decisions d, beta_users u WHERE u.telegram_user_id IN (1002, 1003);
INSERT INTO beta_notification_deliveries (decision_id, episode_pk, user_pk, state, decision_ts, sending_at, error_summary)
  SELECT d.decision_id, d.episode_pk, u.user_pk, 'FAILED', d.decision_ts, NULL, 'Forbidden: bot was blocked by the user (chat 1004)'
  FROM beta_push_decisions d, beta_users u WHERE u.telegram_user_id = 1004;
INSERT INTO beta_market_alerts (kind, alert_key, decision_ts, utc_day, decision, target_user_pk, payload)
  SELECT 'level', 'PDH:2026-10-10', '2026-10-10 09:00+00', '2026-10-10', 'PUSH', user_pk, '{"level": 66000}' FROM beta_users WHERE telegram_user_id = 1003;
INSERT INTO beta_claims (claim_class, level, issued_at, issue_slot, as_of, stats_pk, subject, subject_key, numbers, rule_version, template_id, template_digest, eval_rule_id, eval_rule, eval_rule_digest, horizon_end, eligible_reason, claim_digest)
  SELECT 'L2_LEVEL_FIRST_TOUCH_HOLD_4H', 'L2', '2026-10-10 09:00+00', '2026-10-10 09:00+00', '2026-10-10 09:00+00', stats_pk,
         '{"level": "PDH"}', 'PDH', '{"p": 0.46, "n": 1200}', 'r1', 't1', repeat('3', 64), 'e1', '{"kind": "hold"}', repeat('4', 64), '2026-10-10 13:00+00', 'ok', repeat('5', 64)
  FROM beta_hist_stats;
INSERT INTO beta_claim_outcomes (claim_pk, eval_rule_digest, revision, status, realized, computed_at, outcome_digest)
  SELECT claim_pk, eval_rule_digest, 1, 'COMPLETE', '{"held": true}', '2026-10-10 13:05+00', repeat('6', 64) FROM beta_claims;
COMMIT;
