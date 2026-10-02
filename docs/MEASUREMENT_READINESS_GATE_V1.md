# Measurement readiness gate V1

**Status:** `MEASUREMENT_GATE / DAY0_NOT_DECLARED`
**Date:** 2026-10-02
**Decision source:** `docs/PRODUCT_FIRST_DECISION_V1.md` at `d7f931d070d65815c4f1c39284af20a6d5b21f90` (not on `main`).

This gate is the evidence layer for a future 30-day PRODUCT_FIRST test. It does not change detector thresholds, UX thresholds, U1–U5 thresholds, or decision rules. It does not start the test, invite users, or build the morning-briefing product.

`config/measurement_contract_v1.json` freezes only what that decision already fixes. Every other scoring choice is `REQUIRES_FREEZE_BEFORE_DAY0`. The evaluator returns `MEASUREMENT_FAILURE` when a choice is still open and the stored rows do not make every implemented reading agree. Product `INCONCLUSIVE` is only the cell the decision table names.

## What is persisted

- `beta_measurement_enrollment` — random 64-hex pseudonym, `joined_at`, invite code and label, initial `known_contact`, `owner_excluded`. Append-only. The pseudonym is `secrets.token_hex(32)`. It is not a Telegram id and not `fingerprint()`.
- `beta_measurement_classification` — append-only known/unknown history. The initial flag is not updated.
- `beta_user_activity.enrollment_pk` plus actions `cmd_catchup`, `cmd_brief` (`detail=on|off`), `cmd_push` (`detail=on|off`), `btn_fake_door`. `/delete_me` sets `user_pk` to null and keeps the enrollment link. Rows with no enrollment are still deleted.
- `beta_users.brief_enabled` and `beta_users.push_enabled`. `/push off` suppresses that user's episodic send with `USER_PUSH_OFF`.
- `beta_brief_deliveries` — one append-only row per enrollment per Kyiv morning: `SENT`, `FAILED`, or `WITHHELD`. No `episode_pk` and no `decision_id`.
- `beta_commercial_evidence` — append-only `OFFER`, `PAYMENT`, `REFUND` with amount and currency. Not a payment integration.
- `beta_interview_verbatim` — append-only question id, timestamp, verbatim, `spontaneous`.
- `beta_feedback_revisions` — append-only Useful/Noise history. The live `beta_feedback` row still follows the user and is removed with them.

`/catchup` is not a bot command. The view does not exist, so the command would record a pull of a screen the user cannot see. `cmd_catchup` is a legal activity action for when that view is built. `brief_delivered` is not an activity action; the brief ledger is the delivery fact.

The morning sender is not in this gate. Until something calls `record_brief_attempt`, briefing days have no rows and the evaluator does not invent them.

## Privacy

`/delete_me` and the 30-day stop purge delete the Telegram id, the allowlist row, the waitlist row, feedback texts, and the live vote row. They do not delete the enrollment or the rows that point at it. After that, the Telegram id is not recoverable from the measurement tables: the pseudonym was not derived from it.

The privacy notice is version 4 and says this. Feedback texts stay on the 120-day delete. Interview verbatim can contain whatever the person said; the row is keyed only by the random pseudonym.

## Evaluator

`beta/measurement_eval.py` is read-only. It does not call `/admin_stats` or the usage report. It ignores rows after the cutoff. Activity-write failures that cannot be shown to fall after the cutoff blank U1a, U1b, U2 and U5. Missing offers, missing interviews when the fake door is short of 5, an unfrozen parameter that changes a cell, and an unclassified Telegram failure are `MEASUREMENT_FAILURE`, not a product PASS, FAIL, or INCONCLUSIVE.

`snapshot.prices` stays empty (`SERIES_NOT_FROZEN`) until the RV series is chosen. The evaluator can compute `MEAN_SQUARED_LOG_RETURN_VS_P25_PRIOR_90` when a freeze names that formula and daily closes are present. Short history is `MEASUREMENT_FAILURE`, not the decision's volatility INCONCLUSIVE cell. The decision's "bottom quartile of the prior 90 days" does not name the series or the formula, and the V2 tape does not contain 90 days at the maturity described in the decision.

## Still `REQUIRES_FREEZE_BEFORE_DAY0`

Withdrawal dates; U1a aggregation and its conflict precedence; the U1a "ask where it is" question id; which commands are U1b pulls; the week inside days 18–30; click-to-push attribution; the U2 push-floor scope; the RV series and formula; how `/brief off` and `/push off` are counted; the blocked-bot substring list; the delivery-failure-day denominator, statuses, and which metrics lose the day; the refund-window anchor; the U3 denominator when someone joins after day 25; the U4 window start and the ≤6h work attestation; the U5 verbal question id; the human code for "the same missing thing"; operational confirmation that the owner account is flagged `owner_excluded`.

Cells the decision table does not name (exactly 3 positive U2 users with fewer than 3 disables, U3 with at least 3 payments but under 25%, U1a with a pass-shaped reaction count and exactly 2 `/brief off`) stay `MEASUREMENT_FAILURE`. This gate does not fill them in.

Kyiv day boundary, 08:00 brief time, the 3-hour withdrawal window, the 10-minute push window, the reaction actions, days 8–30 and 18–30, offer days 21–25, the numeric thresholds, and "more than 30%" are frozen from the decision.
