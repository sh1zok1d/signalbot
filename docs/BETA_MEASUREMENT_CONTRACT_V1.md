# Beta measurement contract V1 — operational definitions for the 30-day user test

**Status: FREEZE_READY, amended 2026-10-06 (Amendment 1, §10) and 2026-10-08 (Amendment 2, §11) — owner decisions recorded 2026-10-03 and 2026-10-08; Day 0 NOT declared.** `PRE_BETA_SCOPE_DECISION_V1.md` §6.7: not frozen now; amended for the pre-beta scope. The owner reviews the amendment and freezes the contract himself on the final build commit; §0 is left to him. The owner made every open decision (§9). The contract becomes binding at the commit the owner records in §0. After that, nothing here changes except by a dated amendment committed **before** the affected number is read.

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
- **Kyiv days.** Cohort days and the active days of U1b are Kyiv days, for every participant.
- **The participant's own days.** Each participant's briefing comes at their own briefing time on their own clock (`brief_time`, default 08:00; `tz`, default Kyiv). The U1a withdrawal days are matched against the participant's **local briefing date**, not Kyiv's (owner decision 2026-10-08; §6.1).
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
| **Settings** (not usage) | `cmd_push`, `cmd_brief`, `cmd_lang`, `cmd_tz`, `cmd_type`, `type_set`, `set_mute`, `set_unmute`, `cmd_start`, `cmd_stop`, `cmd_help`, `cmd_terms`, `cmd_guide`, `lang_set` |
| **Feedback** (not usage) | `cmd_feedback`, `plain_text` (a plain message passed to the team), `cmd_idea`, `idea_sent`, `reason_set`, `cmd_interview`, `interview_booked` |
| **Deliveries** | `push_delivered` (unusual hour), `alert_delivered` with `detail` = `level` / `event` / `move` (market alert), `price` (personal `/alert`) or `approach` (the approach of a personal level), `brief_delivered`, `weekly_delivered` |
| **Onboarding** (not a pull) | `onboard_btc`: the automatic `/btc` after the trader-type answer (backlog J1); never `cmd_btc` |
| **Test instruments** | `brief_withheld` (U1a, `detail` = the withheld briefing's date on the participant's clock), `btn_other_assets` (U5) |

- **`cmd_push` / `cmd_brief` details.** They carry `detail` = `on`, `off`, `<kind>:on|off` or `status`; `cmd_brief` also `time` (a new briefing time, not a disable).
- **`set_mute` / `set_unmute` details.** The one-tap «🔕 Не присылать такие» / «↩️ Вернуть» under a message. The detail is the type: `hours`, `levels`, `events`, `moves`, `weekly`. They set the same preference as `/push <type> off|on`. They are settings, never button reactions; rows recorded before #379 as `btn_mute` / `btn_unmute` are renamed by the schema.
- **`btn_useful` / `btn_noise` details.** None for the unusual-hour push; the message type (`level`, `event`, `move`, `price`, `approach`, `brief`, `weekly`) for every other one. A repeated tap of the same vote records nothing. A changed vote records a second row, so votes are never counted from these activity rows (§3, useful share).
- **Feedback actions (backlog H1–H4, J4).** `cmd_idea`, `idea_sent`, `reason_set`, `cmd_interview`, `interview_booked` and `plain_text` are feedback, never a reaction: not a `tab_*` / `btn_*`, so neither the U2 reaction queries nor the owner's usage breakdown count them.
  - `reason_set` carries `detail` = `<topic>:<reason>`. With topic `noise` it follows a «Шум» vote; that vote (`btn_noise`, a row of the vote tables) is the signal, and the reason is not a second one. With topic `stop` it comes from a participant who has just paused, so it is not a sign of use.
  - `plain_text` is also recorded for a paused participant: since #405 their plain reply (for example to the U3 offer) reaches the team. It is not a return to the bot, and only `/start` makes them active again.
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
| **Reaction** (per class) | A `tab_*` or `btn_*` within 10 minutes after a delivery of that class to the same participant. A one-tap mute (`set_mute` / `set_unmute`) is a setting, never a reaction: it is a negative signal (below). |
| **Combined response** | Derived only: the union of the per-class reactions. Never a threshold input on its own. |
| **Prompted pull** | A pull within 10 minutes after any BRIEF, EVENT_MOVE_LEVEL_PUSH, WEEKLY or personal-alert delivery. This is the derived union window used only to exclude prompted pulls in U1b. |
| **Self-initiated pull** (U1b) | A pull outside every prompted window. |
| **Active day** | A Kyiv day with ≥ 1 self-initiated pull (Kyiv for every participant, whatever their time zone). |
| **Useful share** (U2) | USEFUL / (USEFUL + NOISE) per participant over their current votes on **pushes**, counted with ≥ 5 votes: the unusual-hour push (`beta_feedback`) and the market alerts with `beta_message_votes.kind` ∈ {`level`, `event`, `move`}. One vote per participant and message: the table row is the participant's last vote on that message (a second tap replaces it). Votes on the briefing, the weekly report and personal alerts (`brief`, `weekly`, `price`, `approach`) are reported separately and are not U2. |
| **Push** (U2 "< 15 pushes per user") | A SENT EVENT_MOVE_LEVEL_PUSH delivery to the participant: `push_delivered` or `alert_delivered` with `detail` ∈ {`level`, `event`, `move`}. BRIEF, WEEKLY, personal alerts and rows SUPPRESSED (quiet hours, push off, a muted type) are not pushes. |
| **Push disabled** (U2) | At day 30: `cmd_push` detail `off`, or a push type still switched off — `cmd_push` detail `hours:off` / `levels:off` / `events:off` / `moves:off`, or `set_mute` with that type and no later `set_unmute` or `cmd_push <type>:on` (the one-tap mute is the same setting; decision §6.6 makes a per-type mute a negative behavioural signal, never a reaction). A `/push off` keeps the category settings (they work again after `/push on`). |
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
               AND (r.action LIKE 'tab\_%' OR r.action LIKE 'btn\_%')   -- set_mute / set_unmute never match
               AND r.at >= p.at AND r.at <= p.at + interval '10 minutes') AS reacted
FROM beta_user_activity p
WHERE p.action = 'push_delivered' OR (p.action = 'alert_delivered' AND p.detail IN ('level','event','move'));

-- useful share inputs (U2): the last vote per participant and message, on pushes only
SELECT user_pk, vote, count(*) AS n FROM (
    SELECT user_pk, vote FROM beta_feedback                                    -- the unusual-hour push
    UNION ALL SELECT user_pk, vote FROM beta_message_votes WHERE kind IN ('level', 'event', 'move')) v
GROUP BY 1, 2;

-- votes on the other message types (reported, not U2)
SELECT kind, user_pk, vote, count(*) AS n FROM beta_message_votes
WHERE kind IN ('brief', 'weekly', 'price', 'approach') GROUP BY 1, 2, 3;

-- push types switched off by a one-tap mute (U2, with cmd_push <type>:off from the same log)
SELECT user_pk, detail AS push_type, max(at) AS last_at FROM beta_user_activity
WHERE action IN ('set_mute', 'set_unmute') GROUP BY 1, 2;

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
- the withdrawal days are `count` distinct Mon–Fri calendar dates drawn with `seed` from cohort days 14–27 (weeks 3–4);
- they are the same dates for every participant, and each participant's briefing is withheld when **their local briefing date** is one of them (owner decision 2026-10-08; `brief_withheld.detail` is that local date);
- `beta.delivery.brief_withdrawal_dates` computes them.

**Day 0.** The only value set after this freeze is `day0_kyiv`, filled in once when Day 0 happens (config change plus deploy). While it is `null`, no brief is ever withheld. Seed, count and range never change after Day 0, and no adjustment follows results.

**On a withdrawal day:**
- every participant who would have received the brief gets an outbox row `SUPPRESSED` / `BRIEF_WITHDRAWAL` and a `brief_withheld` activity row;
- nothing is sent.

**Reaction (U1a):** a `cmd_catchup` within 3 hours after the participant's own briefing slot on a withdrawal day — their `brief_time` (default 08:00) on their clock (`tz`, default Kyiv), which is the withheld row's `decision_ts` — or a `/feedback`, an idea or a plain message asking where the brief is (owner-classified). The withdrawal days are calendar dates; each participant's briefing row carries the date on their own clock.

**The weekly report never lands on a withdrawal day.** It comes on Sunday at 19:00 on each participant's own clock (#379), outside every Mon–Fri date.

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

## 11. Amendment 2 (2026-10-08, before any number of the test)

Written before any number of the test exists, from the owner's decisions of 2026-10-08 (through the ОПГ-1 mini-head and the chief architect, `ORCHESTRATION_V1.md`) and the reviews of #373 and #375. The contract is still not frozen: the owner freezes it on the final build commit by filling §0, which this amendment does not touch. Changed above, and why:

| Item | Change | Source |
|---|---|---|
| U1a dates | The withdrawal days are calendar dates matched against each participant's **local briefing date**, not «дата Киева» (§1.4, §6.1). This is what `beta.delivery` already does (`brief_withheld.detail` = the local date). | Owner decision 2026-10-08 |
| Mute | The one-tap mute is recorded as `set_mute` / `set_unmute` (was `btn_mute` / `btn_unmute`). It is a setting and a **negative U2 signal** (push disabled while still on at day 30), never a reaction (§2, §3, §4). | Review of #373; `PRE_BETA_SCOPE_DECISION_V1` §6.6 |
| U2 votes | (Confirmed by the ОПГ-1 mini-head on 2026-10-08, following U2's definition in `PRODUCT_FIRST_DECISION_V1` §7.) The useful share counts votes on pushes only: the unusual-hour push and `level` / `event` / `move` alerts, from the vote tables, one row per participant and message (their last vote). Votes on the briefing, the weekly report and personal alerts are reported separately (§3, §4). Activity rows `btn_useful` / `btn_noise` are never the vote count. | Review of #375; `PRODUCT_FIRST_DECISION_V1` §7 (U2 is the quality of pushes) |
| Daily limits | Each participant has their own daily push budget on their own calendar date. A delivery over it is SUPPRESSED / DAILY_CAP and is not a push (§3 «Push»). | Review of #373 |
| Weekly report | Sunday 19:00 on each participant's clock, never on a Mon–Fri withdrawal date (§6.1). | Review of #379 (ОПГ-1) |
| Forecast layer | Registered surfaces, journal classes and the level-push trigger change (§12.1). | `FORECAST_LAYER_DECISION_V1` §6, §6a, §8 |
| Dated events | Changes during the test that split the metrics before and after their date (§12.2). | `FORECAST_LAYER_DECISION_V1` §6a; the architect for D2 |
| Push trigger | `level_race.push_trigger` `legacy → structural` only at 00:00 UTC in the step-3 deploy, before the 7-day start; after the start it restarts the week; the legacy fallback is a limitation (§12.1). | ОПГ-1, 2026-10-08; #393 |
| Claim cohorts | A `template_digest` change starts a new claim cohort (#403, `L3_LEVEL_TOUCH_24H`); journal = display (a chance is journaled as shown only where printed, mode B); #402's corridor record and #410's OI definition reset nothing (§12.3). | ОПГ-1, 2026-10-08 |
| Feedback actions | `cmd_idea`, `idea_sent`, `reason_set`, `cmd_interview`, `interview_booked`, `plain_text` are feedback, never reactions; `reason_set` with topic `stop` and `plain_text` may come from a paused participant (§2). | #404, #405 |

Unchanged: every threshold of `PRODUCT_FIRST_DECISION_V1.md` §7, the 10-minute window, the enrolled denominator, Kyiv cohort days and Kyiv active days for U1b, the U3 ledger outside git, the U5 fake door.

## 12. Forecast layer and dated events

### 12.1 Forecast layer (registered before the freeze)

`FORECAST_LAYER_DECISION_V1.md` decides the layer; this section only registers what it adds to the measured product.

**At Day 0, state `HIST`** (§6a of that file):
- **T0:** one line in the existing level-touch push, the race history one-liner. It replaces the `level_reaction_stats` line in that push (that line stays in `/levels` and Details), so the push does not grow.
- **T15:** `/levels` and `/check`.
- **Journal classes, active from Day 0:** `L2_LEVEL_RACE_HIST_T0_4H` and `L2_LEVEL_RACE_HIST_T15_4H`, evaluation rule `LEVEL_RACE_4H_V1`. Every eligible statement is logged, shown or not.
- **When the line is hidden.** The race line is not shown inside a CPI / FOMC event zone. It is shown only once its claim row exists in the journal (the architect's decision, 2026-10-08), so every shown line has its record.

**The level-push trigger.**
- **What changes.** Behind `level_race.push_trigger` (#393, `legacy` by default), the PDH / PDL / PWH / PWL / PMH / PML touch push moves from `legacy` (the exact price) to `structural`: the #352 event, entry into the ±0.15 % zone on a closed 5m bar. Its text says «вошла в зону PDH …», not «коснулась», and the T0 race line replaces the hold history.
- **When it is switched.** `legacy → structural` is switched only at **00:00 UTC**, in the step-3 deploy, **before** the 7-day observation starts. It is a push-gating change, so switching it after the start restarts the observation week (`ORCHESTRATION_V1.md` §4a). During the test it is not switched at all without an owner decision recorded as a dated event (below).
- **What stays.** It is the same push type. It stays in the class EVENT_MOVE_LEVEL_PUSH with `alert_delivered` detail `level`, under the same per-recipient limits, quiet hours and per-type mute. There is **no new push type**.
- **Fallback (a limitation).** If the switch misses step 3, Day 0 runs `legacy` without the T0 line, and `HIST` is shown only in `/levels` and `/check`. The test then measures the exact-price push, and its U2 numbers say nothing about the structural trigger.
- **Moving the trigger later.** Moving or switching on the new trigger during the test changes the push rule (`PRODUCT_FIRST_DECISION_V1` §7). The forecast-layer exception of §6a does not cover it, so it needs an owner decision recorded as a dated event (§12.2).
- **Before the test.** Turning on a Day-0 flag after the observation week has started restarts that week (`ORCHESTRATION_V1.md` §4a).

**Future model states, not active at Day 0:**
- the classes `L3_LEVEL_RACE_T0_4H`, `L3_LEVEL_RACE_T15_4H` and `L3_GENERIC_RACE_4H`;
- the states `L3_HISTORY_BACKED`, `L3_LIVE` and `FALLBACK`.

They enter the running test only as a dated event (§12.2).

### 12.2 Dated events

During the test, two kinds of change may ship:
- changes of the forecast layer (the exception of `FORECAST_LAYER_DECISION_V1` §6a);
- the data-reliability fixes the owner deploys.

For each one:
- it is announced in advance with its date and content;
- it is recorded below with that date before the date;
- every affected metric is reported **separately before and after the date**.

Nothing else in the product changes during the test (`PRODUCT_FIRST_DECISION_V1` §7).

| Event | Date (UTC) | Metrics split at the date |
|---|---|---|
| Forecast layer: model states (`L3_HISTORY_BACKED` / `L3_LIVE` / `FALLBACK`) replace `HIST` | *to be announced* | every metric of the test (U1a, U1b, U2, U3 inputs) and every forecast-layer accuracy line |
| Forecast layer: each later correction | *to be announced, one row each* | every metric of the test and the layer's accuracy lines |
| D2: the liquidation fix (OKX / Bybit mapping, `mapping_version`) reaches production | *filled in after the deploy* | every metric in which `LIQUIDATION_STRESS`, the «вынос лонгов / шортов» lines or the liquidation votes take part |

A row is never removed or back-dated, and a date is never moved after a number of the test that depends on it is known.

### 12.3 Claim cohorts and text changes

- **Cohort boundary.** A journal row carries the `template_digest` of its class: a sha256 over the RU / EN texts its numbers are printed with (`beta/claims.py`). Any change to one of those texts starts a **new claim cohort** of that class. Accuracy lines and the claim journal's reports count each cohort on its own; rows of the two cohorts are never pooled.
- **#403.** It changes the `pa_next` template, which is part of `L3_LEVEL_TOUCH_24H`. Its deploy is therefore a cohort boundary for that class: the first row with the new digest opens the new cohort. The date is the step-3 deploy, before Day 0, so the boundary falls before the test.
- **Journal = display.** A chance is journaled as shown only where its number is printed. Since #403 (`fa0ccb2`), `claims.shown_keys` journals a level alert's `L3_LEVEL_TOUCH_24H` only when the payload's `next.touch_24h_wording.mode` is `"B"`. A chance shown in the «исторически» fallback, or not printed at all, is never journaled as shown. The rule takes effect at the same #403 deploy date as the cohort boundary.
- **A text change that is not a cohort boundary.** #402's 4h-corridor record in the level and price alerts (`pa_corridor`, `pa_corridor_now`, `pa_track_live`, `pa_track_hold`) is in no claim class's template, so no digest changes. It is a text change: it does not restart the observation week (`ORCHESTRATION_V1.md` §4a) and resets no count.
- **A display-definition change that is not in the contract.** #410 (HORIZON V4: the OI headline needs ≥ 2 venues on every horizon) changes what a surface shows, not a definition or a query of this contract, and no metric of the test reads it. It resets no count. D3(c) (funding, a HORIZON bump) gets the same check when it ships; if it touches nothing here, one line saying so is added.
- **Every later template change** is checked the same way before it ships: does a key of a claim class change (cohort boundary, recorded here with its date) or not (text only)?

| Template change | Classes | Date (UTC) |
|---|---|---|
| #403 `pa_next` (merged as `a6b0129`) | `L3_LEVEL_TOUCH_24H` | the step-3 deploy (its UTC date recorded here when it runs) |
