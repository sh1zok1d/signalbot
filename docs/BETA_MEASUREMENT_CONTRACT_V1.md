# Beta measurement contract V1 — operational definitions for the 30-day user test

**Status: DRAFT — NOT FROZEN.** The owner freezes it by filling §0 with a commit hash and a date. Until then nothing here is binding, and Day 0 cannot be declared.

**Authority:** `docs/PRODUCT_FIRST_DECISION_V1.md` §7–§8 holds the unknowns U1a–U5, their PASS / FAIL / INCONCLUSIVE thresholds and the decision rules. This file changes none of them. It adds only what §7 leaves open:

- who is counted;
- what each word in a threshold means;
- which recorded row answers it.

Where this file and §7 disagree, §7 wins and this file is corrected before the freeze.

## 0. Freeze record (owner)

| Field | Value |
|---|---|
| Frozen at commit | `<hash>` (empty = not frozen) |
| Frozen on (UTC) | `<date>` |
| Open decisions resolved (§9) | `<list>` |
| Day 0 | the `joined_at` of the first enrolled unknown-to-founder participant (§1.3), recorded here when it happens |

After the freeze, a definition changes only by an amendment that is dated, explains its reason and is committed **before** the affected number is read. No threshold, window or classification changes after the first number of the test is known (§7 "Hard limits").

## 1. Population

### 1.1 Participant
A row in `beta_users` with a non-null `joined_at`, meaning the person accepted the privacy notice and pressed Join. The owner (`BETA_OWNER_TELEGRAM_USER_ID`) is never a participant for any metric.

### 1.2 Known versus unknown to the founder
- **Field.** `beta_users.known_contact`, set by the owner with `/admin_known <telegram_user_id> on|off`.
- **Default and deadline.** A participant is unknown unless the owner marks them known within 24 hours of their `joined_at`.
- **Changes after the deadline.** Any change is recorded in `beta_admin_audit` (`admin_known`). A change made after the deadline does not move the participant into or out of a metric already read.
- **What "known" means.** Anyone the founder had a conversation with before the invite: friends, colleagues, chat contacts, people who were invited personally.
- **Where known users count.** They are reported separately and never count toward PASS (§7).

### 1.3 Enrolled (the denominator)
- **Who.** An unknown participant whose `joined_at` falls in the acquisition window: Day 0 through the end of day 12 (U4: 12 days).
- **Joining later.** An unknown participant who joins after day 12 is reported but not enrolled.
- **Fixed size.** The denominator is the enrolled count. It never shrinks: someone who stops, blocks the bot or deletes their data stays in it. U3's "≥ 25 % of all enrolled unknown users" uses this count.

### 1.4 Days
- **Calendar days are Kyiv days.** The product speaks Kyiv time, and the brief is 08:00 Kyiv.
- **Test days are counted from Day 0.** Day *n* is the Kyiv day `n` days after Day 0's Kyiv day, so Day 0 is day 0. Day 30 is when the decision rules are read.
- **One extension only.** It is 14 days with no product change (§7 rule 6).

## 2. Activity vocabulary (from `beta_user_activity`)

| Group | Actions |
|---|---|
| **Pull** (self-chosen look at the market) | `cmd_btc`, `cmd_catchup`, `cmd_levels`, `cmd_risk`, `cmd_events`, `cmd_accuracy`, `cmd_research`, `cmd_history`, `cmd_alert` |
| **Button** (inside a message) | `tab_event`, `tab_1h`, `tab_24h`, `btn_levels`, `btn_risk`, `btn_useful`, `btn_noise` |
| **Settings** (not usage) | `cmd_push`, `cmd_brief`, `cmd_lang`, `cmd_start`, `cmd_stop`, `cmd_help`, `cmd_terms`, `cmd_feedback`, `lang_set` |
| **Deliveries** | `push_delivered` (unusual hour), `alert_delivered` (market and personal alerts), `brief_delivered` |

- **Message.** A message is any delivery in the last row of the table.
- **Detail field.** `cmd_push` / `cmd_brief` carry `detail` = `on`, `off`, `<kind>:on|off` or `status`.
- **Not recorded.** Wrong-argument replies for `/catchup`, unknown commands and plain text are not recorded and count as nothing.

## 3. Definitions

| Term | Definition |
|---|---|
| **Prompted pull** | A pull or button within 10 minutes after any message delivered to the same participant. |
| **Self-initiated pull** | A pull outside every such 10-minute window (U1b). |
| **Active day** | A Kyiv day with at least one self-initiated pull. |
| **Return** | Active on at least one Kyiv day in each of two different test weeks. Descriptive only; it decides nothing in §7. |
| **Reaction after a push** (U2) | A `tab_*` or `btn_*` (Useful/Noise included) within 10 minutes after a `push_delivered`, per push. |
| **Useful share** (U2) | `btn_useful / (btn_useful + btn_noise)` per participant, counted only when the participant has ≥ 5 votes. |
| **Push disabled** (U2) | `cmd_push` with detail `off` or `hours:off`. A later `on` / `hours:on` counts as re-enabled; the state at day 30 is used. |
| **Blocked** (U2) | A delivery `FAILED` with `error_summary` starting `Forbidden:` (Telegram: the user blocked the bot). |
| **Stopped** | `cmd_stop` and not resumed by day 30. |
| **Deleted** | `/delete_me`. The participant's rows are gone; only the aggregate `beta_admin_audit` row `user_delete_me` remains. It counts as disabled for U2 and as not paying for U3, and stays in the denominator. |
| **Brief disabled** (U1a) | `cmd_brief` detail `off`, counted in weeks 3–4. |
| **Briefing reaction** (U1a) | On a withdrawal day: a `cmd_catchup` within 3 hours after 08:00 Kyiv, or a `/feedback` asking where the brief is (owner-classified, text kept ≤ 120 days). |
| **Payment** (U3) | A real transfer, recorded by the owner in a payment ledger outside the repository (it holds personal data): fingerprint, amount, date, refund date. A refund within 30 days cancels the payment. The price is offered to every enrolled participant (churned included) on days 21–25. |
| **Unprompted multi-asset demand** (U5) | A fake-door click recorded as activity on ≥ 2 distinct Kyiv days, or naming it unprompted in the final interview. |

## 4. Queries

The queries are read-only and run against the production database with the owner excluded. Replace `:owner` with the owner's Telegram id and `:day0` with the frozen Day 0. Each one returns aggregates or fingerprints only.

```sql
-- enrolled unknown participants (denominator)
SELECT user_pk FROM beta_users
WHERE telegram_user_id <> :owner AND NOT known_contact
  AND joined_at >= :day0 AND joined_at < :day0 + interval '13 days';

-- self-initiated pulls and active days (Kyiv), outside 10 minutes after any message
WITH msg AS (SELECT user_pk, at FROM beta_user_activity
             WHERE action IN ('push_delivered','alert_delivered','brief_delivered'))
SELECT a.user_pk, (a.at AT TIME ZONE 'Europe/Kyiv')::date AS kyiv_day, count(*) AS pulls
FROM beta_user_activity a
WHERE a.action IN ('cmd_btc','cmd_catchup','cmd_levels','cmd_risk','cmd_events','cmd_accuracy',
                   'cmd_research','cmd_history','cmd_alert')
  AND NOT EXISTS (SELECT 1 FROM msg m WHERE m.user_pk = a.user_pk
                  AND a.at >= m.at AND a.at <= m.at + interval '10 minutes')
GROUP BY 1, 2;

-- reaction after each unusual-hour push (U2)
SELECT p.user_pk, p.at AS pushed_at,
       EXISTS (SELECT 1 FROM beta_user_activity r WHERE r.user_pk = p.user_pk
               AND (r.action LIKE 'tab\_%' OR r.action LIKE 'btn\_%')
               AND r.at >= p.at AND r.at <= p.at + interval '10 minutes') AS reacted
FROM beta_user_activity p WHERE p.action = 'push_delivered';

-- blocked participants (U2)
SELECT DISTINCT user_pk FROM beta_notification_deliveries
WHERE state = 'FAILED' AND error_summary LIKE 'Forbidden:%';

-- deletions (aggregate only)
SELECT count(*) FROM beta_admin_audit WHERE action = 'user_delete_me' AND recorded_at >= :day0;
```

`--beta-usage-report` is an operational overview, not this contract. It counts every non-owner user, known contacts included, and uses a 30-minute prompt window. Its numbers are never read as U1–U5.

## 5. What the code already records (verified)

`tests/beta/test_beta_invite_journey_pg.py` runs the real detector, notifier and bot on PostgreSQL for an invited participant and asserts the following:

- **Pulls and buttons.** Every pull, button, setting change (with its `detail`) and delivery leaves its activity row.
- **Push reaction.** A reaction within 10 minutes of a push is derivable.
- **Blocked and network failures.** A blocked bot is a `FAILED` delivery with `Forbidden: …`. A network failure is `DELIVERY_UNKNOWN`. Neither is ever resent.
- **`/delete_me`.** It removes the participant's activity and leaves one `user_delete_me` audit row.
- **Retention.** Activity and feedback text are kept 120 days (`telemetry.retention_days`), which is longer than 30 + 14 days.

## 6. What is NOT instrumented yet (blocks part of §7)

| Unknown | Missing | Needed by |
|---|---|---|
| U1a | A switch that withholds the morning briefing on 3 chosen weekdays (same days for everyone) and records the withheld slot. Today the brief is only per-user `/brief off` or globally off. | Before week 3 (day 14) |
| U5 | The multi-asset fake door in `/help` and its activity action. | Day 0: it counts clicks on distinct days |
| U3 | The payment ledger: its format, where it lives and who writes it. | Day 21 |
| Known/unknown | The habit and the deadline of `/admin_known` (§1.2). `known_contact` exists, but no report reads it. | Day 0 |

## 7. Anti-self-deception checks before reading day 30

- The enrolled list (§1.3) is exported once, at the end of day 12, and kept as the denominator.
- Nobody re-reads a number "to see" before day 30 and then changes a definition.
- Interviews can only choose a direction inside Reposition or Pivot (§7).

## 8. Privacy

- Every number above comes from rows the privacy notice discloses: commands and buttons with their time, the invite link, delivery status, votes and feedback text.
- No message content or Telegram profile data is read.
- Reports use salted fingerprints, never Telegram ids.
- The payment ledger is personal data and stays outside the repository.

## 9. Open decisions for the owner before the freeze

1. **Is a brief a "push" for U1b?** Draft: yes, any delivered message opens the 10-minute prompted window.
2. **Acquisition window.** Draft: enrolled = unknown participants who join on days 0–12.
3. **Deleted participants.** Draft: they stay in the denominator, count as disabled for U2 and as not paying for U3.
4. **Implement the U1a withdrawal switch and the U5 fake door now** (before INVITE_CANDIDATE_1 is frozen), or accept that U1a / U5 are reported as NOT_MEASURED.
5. **Payment ledger** format and location.
