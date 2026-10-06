# Beta measurement contract V1 — operational definitions for the 30-day user test

**Status: FREEZE_READY, amended 2026-10-06 (Amendment 1, §10) — owner decisions recorded 2026-10-03; Day 0 NOT declared.** `PRE_BETA_SCOPE_DECISION_V1.md` §6.7: not frozen now; amended for the pre-beta scope. The owner reviews the amendment and freezes the contract himself on the final build commit; §0 is left to him. The owner made every open decision (§9). The contract becomes binding at the commit the owner records in §0. After that, nothing here changes except by a dated amendment committed **before** the affected number is read.

**Authority:** `docs/PRODUCT_FIRST_DECISION_V1.md` §7–§8 holds the unknowns U1a–U5, their PASS / FAIL / INCONCLUSIVE thresholds and the decision rules. This file changes none of them. It adds only what §7 leaves open:

- who is counted;
- what each word in a threshold means;
- which recorded row answers it.

Where this file and §7 disagree, §7 wins.

## 0. Freeze record (owner)

| Field | Value |
|---|---|
| Owner decisions | 2026-10-03: enrollment window, known-classification deadline, reaction window, notification classes, `/delete_me` rule, U1a intervention, U5 fake door, U3 ledger (§9) |
| Frozen at commit | the merge commit of the PR that carries this text into `main` (fill in the hash) |
| Day 0 | **not declared.** It is recorded here, and as `briefing.withdrawal.day0_kyiv` in `config/beta_v0.yaml`, when it happens (§1.4, §6.1) |

No threshold, window or classification changes after the first number of the test is known (§7 "Hard limits"). `--beta-usage-report` (a 10-minute window after any delivery: push, alert, brief, weekly; known and unknown together) is an operational overview and is **never** read as U1–U5.

## 1. Population

### 1.1 Participant
A row in `beta_users` with a non-null `joined_at`, meaning the person accepted the privacy notice and pressed Join. The owner (`BETA_OWNER_TELEGRAM_USER_ID`) is never a participant for any metric.

### 1.2 Known versus unknown to the founder
- **Field.** `beta_users.known_contact`, set by the owner with `/admin_known <telegram_user_id> on|off`.
- **Deadline.** Classification happens **within 24 hours of enrollment** (`joined_at`). A participant not marked known by then is unknown.
- **Changes after the deadline.** A later change is recorded (`beta_admin_audit`, `admin_known`) but never moves a participant into or out of a metric.
- **What "known" means.** Anyone the founder had a conversation with before the invite, or invited personally.
- **Where known participants count.** They are reported separately and never count toward PASS (§7).

### 1.3 Enrolled (the denominator)
- **Who.** An unknown participant whose Kyiv join date is cohort day **0–12 inclusive** (U4: 12 days).
- **Joining later.** An unknown participant who joins after day 12 is reported but not enrolled.
- **Fixed size.** The denominator never shrinks. Stopping, blocking the bot, the 30-day retention purge and `/delete_me` all leave an enrolled participant in it (§1.5). U3's "≥ 25 % of all enrolled unknown users" uses this count.

### 1.4 Days
- **Kyiv days.** Calendar days are Kyiv days; the brief is at 08:00 Kyiv.
- **Day 0** is the Kyiv day of the first enrolled unknown participant's join. Cohort day *n* is Day 0 + *n* Kyiv days.
- **Reading and extension.** The decision rules are read on day 30. One extension of 14 days is allowed, with no product change (§7 rule 6).

### 1.5 `/delete_me` and retention purges
- **What is deleted.** The participant's personal telemetry is deleted as the privacy notice promises: the user row, activity and feedback text. Delivery rows keep only an anonymous `NULL` user.
- **What is kept.** The deletion's `beta_admin_audit` row (`user_delete_me`, `retention_purge`, `admin_remove`) keeps an irreversible cohort record in `detail.cohort`: `{joined_kyiv_date, known_contact}`. It has no Telegram id and no fingerprint for `/delete_me`.
- **Denominator.** It is computed from live rows **plus** these cohort records (§4).
- **Effect on the metrics.** A deleted enrolled participant counts as disabled for U2 and as not paying for U3, unless the payment ledger (§7) shows a payment made before the deletion.

## 2. Activity vocabulary (from `beta_user_activity`)

| Group | Actions |
|---|---|
| **Pull** (self-chosen look at the market) | `cmd_btc`, `cmd_catchup`, `cmd_levels`, `cmd_risk`, `cmd_events`, `cmd_accuracy`, `cmd_research`, `cmd_history`, `cmd_alert`, `cmd_check` |
| **Button** (inside a message) | `tab_event`, `tab_1h`, `tab_24h`, `tab_research`, `btn_levels`, `btn_risk`, `btn_btc_now` («📊 BTC сейчас» under a push), `btn_check` («🎯 Проверить» under a push or the briefing), `btn_watch` («🔔 Следить» under `/check`), `btn_useful`, `btn_noise` |
| **Settings** (not usage) | `cmd_push`, `cmd_brief`, `cmd_lang`, `cmd_tz`, `cmd_type`, `type_set`, `btn_mute`, `btn_unmute`, `cmd_start`, `cmd_stop`, `cmd_help`, `cmd_terms`, `cmd_guide`, `lang_set` |
| **Feedback** (not usage) | `cmd_feedback`, `plain_text` (a plain message passed to the team), `cmd_idea`, `idea_sent`, `reason_set`, `cmd_interview`, `interview_booked` |
| **Deliveries** | `push_delivered` (unusual hour), `alert_delivered` with `detail` = `level` / `event` / `move` (market alert), `price` (personal `/alert`) or `approach` (the approach of a personal level), `brief_delivered`, `weekly_delivered` |
| **Onboarding** (not a pull) | `onboard_btc`: the automatic `/btc` after the trader-type answer (backlog J1); never `cmd_btc` |
| **Test instruments** | `brief_withheld` (U1a, `detail` = the withheld briefing's date on the participant's clock), `btn_other_assets` (U5) |

- **`cmd_push` / `cmd_brief` details.** They carry `detail` = `on`, `off`, `<kind>:on|off` or `status`; `cmd_brief` also `time` (a new briefing time, not a disable).
- **`btn_mute` / `btn_unmute` details.** The type: `hours`, `levels`, `events`, `moves`, `weekly`. They set the same preference as `/push <type> off|on`.
- **`btn_useful` / `btn_noise` details.** None for the unusual-hour push; the message type (`level`, `event`, `move`, `price`, `approach`, `brief`, `weekly`) for every other one. A repeated tap of the same vote records nothing.
- **What is not recorded.** Wrong-argument replies to `/catchup` and unknown commands are not recorded and count as nothing. A plain message is recorded as `plain_text` (feedback, not usage).

## 3. Notification classes and reactions

The classes stay separate:

| Class | Rows |
|---|---|
| **BRIEF** | `brief_delivered` |
| **EVENT_MOVE_LEVEL_PUSH** | `push_delivered` (unusual hour) and `alert_delivered` with `detail` ∈ {`level`, `event`, `move`} |
| **WEEKLY** | `weekly_delivered`: its own class; it opens a prompted window (U1b) and is not a push for U2 |
| Personal alert (not a push) | `alert_delivered` with `detail` ∈ {`price`, `approach`}; the participant asked for it, so it is never a push or a reaction trigger |

**Reaction window: 10 minutes.**

| Term | Definition |
|---|---|
| **Reaction** (per class) | A `tab_*` or `btn_*` within 10 minutes after a delivery of that class to the same participant, except `btn_mute` / `btn_unmute` (a mute is a negative signal, below). |
| **Combined response** | Derived only: the union of the per-class reactions. Never a threshold input on its own. |
| **Prompted pull** | A pull within 10 minutes after any BRIEF, EVENT_MOVE_LEVEL_PUSH, WEEKLY or personal-alert delivery. This is the derived union window used only to exclude prompted pulls in U1b. |
| **Self-initiated pull** (U1b) | A pull outside every prompted window. |
| **Active day** | A Kyiv day with ≥ 1 self-initiated pull (Kyiv for every participant, whatever their time zone). |
| **Useful share** (U2) | USEFUL / (USEFUL + NOISE) per participant over their current votes on every message type (`beta_feedback` for the unusual-hour push, `beta_message_votes` for the others; one vote per message, a second tap replaces it), counted with ≥ 5 votes. |
| **Push** (U2 "< 15 pushes per user") | A SENT EVENT_MOVE_LEVEL_PUSH delivery to the participant: `push_delivered` or `alert_delivered` with `detail` ∈ {`level`, `event`, `move`}. BRIEF, WEEKLY, personal alerts and rows SUPPRESSED (quiet hours, push off, a muted type) are not pushes. |
| **Push disabled** (U2) | At day 30: `cmd_push` detail `off`, or a push type still switched off — `cmd_push` detail `hours:off` / `levels:off` / `events:off` / `moves:off`, or `btn_mute` with that type (the one-tap mute is the same setting; decision §6.6 makes a per-type mute a negative signal). A `/push off` keeps the category settings (they work again after `/push on`). |
| **Quiet hours** | On the participant's clock (their `tz`, Kyiv by default). A delivery in their night is SUPPRESSED / QUIET_HOURS and was never sent: it is neither a push nor a prompt. |
| **Blocked** (U2) | A delivery `FAILED` with `error_summary` starting `Forbidden:`. |
| **Brief disabled** (U1a) | `cmd_brief` detail `off` in weeks 3–4 (`time`, a new briefing time, is not a disable). |

## 4. Queries

The queries are read-only and use aggregates or internal keys only. Replace `:owner` with the owner's Telegram id and `:day0` with Day 0 as a Kyiv-midnight `timestamptz`.

```sql
-- enrolled unknown participants still present (denominator, part 1)
SELECT user_pk FROM beta_users
WHERE telegram_user_id <> :owner AND NOT known_contact
  AND joined_at >= :day0 AND joined_at < :day0 + interval '13 days';

-- self-initiated pulls and active days (Kyiv), outside the derived 10-minute prompted window
WITH msg AS (SELECT user_pk, at FROM beta_user_activity
             WHERE action IN ('push_delivered','alert_delivered','brief_delivered','weekly_delivered'))
SELECT a.user_pk, (a.at AT TIME ZONE 'Europe/Kyiv')::date AS kyiv_day, count(*) AS pulls
FROM beta_user_activity a
WHERE a.action IN ('cmd_btc','cmd_catchup','cmd_levels','cmd_risk','cmd_events','cmd_accuracy',
                   'cmd_research','cmd_history','cmd_alert','cmd_check')
  AND NOT EXISTS (SELECT 1 FROM msg m WHERE m.user_pk = a.user_pk
                  AND a.at >= m.at AND a.at <= m.at + interval '10 minutes')
GROUP BY 1, 2;

-- reaction per EVENT_MOVE_LEVEL_PUSH delivery (U2), BRIEF is read the same way with brief_delivered
SELECT p.user_pk, p.action, p.detail, p.at AS delivered_at,
       EXISTS (SELECT 1 FROM beta_user_activity r WHERE r.user_pk = p.user_pk
               AND (r.action LIKE 'tab\_%' OR r.action LIKE 'btn\_%')
               AND r.action NOT IN ('btn_mute', 'btn_unmute')
               AND r.at >= p.at AND r.at <= p.at + interval '10 minutes') AS reacted
FROM beta_user_activity p
WHERE p.action = 'push_delivered' OR (p.action = 'alert_delivered' AND p.detail IN ('level','event','move'));

-- useful share inputs (U2): the current vote per message, every type
SELECT user_pk, vote, count(*) AS n FROM (
    SELECT user_pk, vote FROM beta_feedback
    UNION ALL SELECT user_pk, vote FROM beta_message_votes) v
GROUP BY 1, 2;

-- push types switched off by a one-tap mute (U2, with cmd_push <type>:off from the same log)
SELECT user_pk, detail AS push_type, max(at) AS last_at FROM beta_user_activity
WHERE action IN ('btn_mute', 'btn_unmute') GROUP BY 1, 2;

-- blocked participants (U2)
SELECT DISTINCT user_pk FROM beta_notification_deliveries
WHERE state = 'FAILED' AND error_summary LIKE 'Forbidden:%';

-- deleted or purged participants' cohort records (denominator, part 2, no identity)
SELECT detail->'cohort'->>'joined_kyiv_date' AS joined_kyiv_date,
       (detail->'cohort'->>'known_contact')::boolean AS known_contact, count(*) AS n
FROM beta_admin_audit
WHERE action IN ('user_delete_me','retention_purge','admin_remove') AND detail ? 'cohort'
  AND detail->>'cohort' <> 'null' AND recorded_at >= :day0
GROUP BY 1, 2;
```

`tests/beta/test_beta_invite_journey_pg.py` executes every query above against the real schema on each test run.

## 5. What the code records (verified on PostgreSQL)

`tests/beta/test_beta_invite_journey_pg.py` runs an invited participant through the real detector, notifier and bot. Together with `tests/beta/test_beta_catchup_brief_pg.py` and `tests/beta/test_beta_measurement.py`, the tests assert:

- **Activity rows.** Every pull, button and setting change (with its detail), and every delivery with its class, leaves an activity row.
- **Reactions.** A reaction within 10 minutes is derivable.
- **Delivery failures.** Blocked and network failures are distinguishable and never resent.
- **U1a.** The brief is withheld on a withdrawal day, with outbox state `SUPPRESSED` / `BRIEF_WITHDRAWAL` and a `brief_withheld` activity row.
- **U5.** The fake door records one `btn_other_assets` row per tap.
- **`/delete_me`.** It removes personal telemetry and keeps the cohort record.

## 6. Test instruments

### 6.1 U1a — withdrawal of the morning briefing (implemented, inactive until Day 0)

**The rule** is frozen in `config/beta_v0.yaml` → `briefing.withdrawal`:
- `seed: 20261003`, `count: 3`, `first_cohort_day: 14`, `last_cohort_day: 27`;
- the withdrawal days are `count` distinct Mon–Fri Kyiv dates drawn with `seed` from cohort days 14–27 (weeks 3–4);
- they are the same days for every participant;
- `beta.delivery.brief_withdrawal_dates` computes them.

**Day 0.** The only value set after this freeze is `day0_kyiv`, filled in once when Day 0 happens (config change plus deploy). While it is `null`, no brief is ever withheld. Seed, count and range never change after Day 0, and no adjustment follows results.

**On a withdrawal day:**
- every participant who would have received the brief gets an outbox row `SUPPRESSED` / `BRIEF_WITHDRAWAL` and a `brief_withheld` activity row;
- nothing is sent.

**Reaction (U1a):** a `cmd_catchup` within 3 hours after the participant's own briefing slot on a withdrawal day — their `brief_time` (default 08:00) on their clock (`tz`, default Kyiv), which is the withheld row's `decision_ts` — or a `/feedback`, an idea or a plain message asking where the brief is (owner-classified). The withdrawal days are calendar dates; each participant's briefing row carries the date on their own clock.

### 6.2 U5 — multi-asset fake door (implemented)
- **Where.** A «Другие монеты» button exists only under `/help`. It is never pushed and never repeated elsewhere.
- **Reply.** A tap answers «Пока доступен только BTC. Интерес к другим монетам записан.» and records one `btn_other_assets` row.
- **What sits behind it.** Nothing multi-asset.
- **Count.** U5 counts unknown participants with taps on ≥ 2 distinct Kyiv days, or who name it unprompted in the final interview.

## 7. U3 — payment ledger (outside git)

The payment ledger is a file or sheet kept by the owner **outside the repository** (it is personal data). It never enters git, the beta database or a report export.

| Field | Meaning |
|---|---|
| `participant_fingerprint` | the salted fingerprint the owner tools print (never a Telegram id) |
| `known_contact` | the §1.2 classification |
| `offered_at` | when the price was offered (days 21–25, to every enrolled participant, churned included) |
| `paid_at` | when a real transfer arrived; empty if none |
| `amount`, `currency` | of that transfer |
| `refunded_at` | a refund within 30 days cancels the payment |

- **Never stored:** bank or card details, screenshots, the payer's real name, payment-reference text, unless operationally unavoidable.
- **What counts as payment.** A willingness statement, a promise or a "would pay" is **not** a payment. Only a row with `paid_at` and no `refunded_at` within 30 days counts.

## 8. Privacy

- **Disclosed rows only.** Every number above comes from rows the privacy notice discloses: commands and buttons with their time, the invite link, delivery status, votes and feedback text.
- **Nothing else is read.** No message content or Telegram profile data is read.
- **Fingerprints only.** Reports use salted fingerprints.
- **Cohort records** after deletion hold no identity.

## 9. Owner decisions (2026-10-03)

1. **Enrollment window:** cohort days 0–12 inclusive.
2. **Known-classification deadline:** within 24 h of enrollment.
3. **Reaction window:** 10 minutes.
4. **Notification classes:** BRIEF and EVENT_MOVE_LEVEL_PUSH stay separate; a combined response exists only as a derived metric.
5. **`/delete_me`:** the enrolled participant stays in the denominator through the cohort record only (§1.5).
6. **U1a:** implement before the freeze. Schedule frozen before Day 0, observable in telemetry, no post-Day-0 adjustment (§6.1).
7. **U5:** a minimal fake door before Day 0 (§6.2).
8. **U3:** a ledger outside git with the §7 fields; only a real transfer counts.
9. **Usage report:** `--beta-usage-report` (10 minutes after any delivery since backlog F5, #341) is not used for U1–U5.

## 10. Amendment 1 (2026-10-06, before any number of the test)

`PRE_BETA_SCOPE_DECISION_V1.md` §6.7 amends this contract for the pre-beta scope. Written before any number of the test exists. The owner reviews it and freezes the contract on the final build commit by filling §0, which this amendment does not touch. Changed above, and why:

| Item | Change | Built in |
|---|---|---|
| U1a | Reaction window from each participant's own briefing slot (time and zone), not 08:00 Kyiv | E3, C5 |
| Quiet hours | On the participant's clock; a delivery in their night is SUPPRESSED / QUIET_HOURS and counts as nothing | C5 |
| U2 votes | «Полезно / Шум» on every message type; the useful share reads the current vote per message from `beta_feedback` and `beta_message_votes`; a repeated tap records nothing | F6 |
| U2 disabled | A per-type mute (`/push <type> off` or «🔕» `btn_mute`) still on at day 30 counts as disabled; a mute is never a reaction | E2, decision §6.6 |
| U2 "< 15 pushes" | A push is a SENT EVENT_MOVE_LEVEL_PUSH delivery; BRIEF, WEEKLY and personal alerts are not | — |
| U1b | WEEKLY is a class of its own and opens a prompted window | B4 (track A) |
| Classes | Pull `cmd_check`; buttons `tab_research`, `btn_check`, `btn_watch`; settings `cmd_tz`, `cmd_type`, `type_set`, `btn_mute`, `btn_unmute`, `cmd_guide`; feedback `plain_text`, `cmd_idea`, `idea_sent`, `reason_set`, `cmd_interview`, `interview_booked`; onboarding `onboard_btc` (never a pull); deliveries `weekly_delivered` and `alert_delivered` / `approach` | D1, D5, E1–E5, H1–H4, J1, J2, J4 |

Unchanged: every threshold of `PRODUCT_FIRST_DECISION_V1.md` §7, the 10-minute window, the enrolled denominator, Kyiv days for U1b, the U3 ledger outside git, the U5 fake door.
