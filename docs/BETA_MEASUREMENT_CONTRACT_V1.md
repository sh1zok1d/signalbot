# Beta measurement contract V1 — operational definitions for the 30-day user test

**Status: FREEZE_READY — owner decisions recorded 2026-10-03; Day 0 NOT declared.** The owner made every open decision (§9). The contract becomes binding at the merge commit that carries this text, which the owner records in §0. After that, nothing here changes except by a dated amendment committed **before** the affected number is read.

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

No threshold, window or classification changes after the first number of the test is known (§7 "Hard limits"). `--beta-usage-report` (30-minute window, known and unknown together) is an operational overview and is **never** read as U1–U5.

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
| **Pull** (self-chosen look at the market) | `cmd_btc`, `cmd_catchup`, `cmd_levels`, `cmd_risk`, `cmd_events`, `cmd_accuracy`, `cmd_research`, `cmd_history`, `cmd_alert` |
| **Button** (inside a message) | `tab_event`, `tab_1h`, `tab_24h`, `btn_levels`, `btn_risk`, `btn_btc_now` («📊 BTC сейчас» under a push), `btn_useful`, `btn_noise` |
| **Settings** (not usage) | `cmd_push`, `cmd_brief`, `cmd_lang`, `cmd_start`, `cmd_stop`, `cmd_help`, `cmd_terms`, `cmd_feedback`, `lang_set` |
| **Deliveries** | `push_delivered` (unusual hour), `alert_delivered` with `detail` = `level` / `event` / `move` (market alert) or `price` (personal `/alert`), `brief_delivered` |
| **Test instruments** | `brief_withheld` (U1a, `detail` = the withheld Kyiv date), `btn_other_assets` (U5) |

- **`cmd_push` / `cmd_brief` details.** They carry `detail` = `on`, `off`, `<kind>:on|off` or `status`.
- **What is not recorded.** Wrong-argument replies to `/catchup`, unknown commands and plain text are not recorded and count as nothing.

## 3. Notification classes and reactions

The classes stay separate:

| Class | Rows |
|---|---|
| **BRIEF** | `brief_delivered` |
| **EVENT_MOVE_LEVEL_PUSH** | `push_delivered` (unusual hour) and `alert_delivered` with `detail` ∈ {`level`, `event`, `move`} |
| Personal alert (not a push) | `alert_delivered` with `detail` = `price`; the participant asked for it, so it is never a push or a reaction trigger |

**Reaction window: 10 minutes.**

| Term | Definition |
|---|---|
| **Reaction** (per class) | A `tab_*` or `btn_*` within 10 minutes after a delivery of that class to the same participant. |
| **Combined response** | Derived only: the union of the per-class reactions. Never a threshold input on its own. |
| **Prompted pull** | A pull within 10 minutes after any BRIEF, EVENT_MOVE_LEVEL_PUSH or personal-alert delivery. This is the derived union window used only to exclude prompted pulls in U1b. |
| **Self-initiated pull** (U1b) | A pull outside every prompted window. |
| **Active day** | A Kyiv day with ≥ 1 self-initiated pull. |
| **Useful share** (U2) | `btn_useful / (btn_useful + btn_noise)` per participant, counted with ≥ 5 votes. |
| **Push disabled** (U2) | `cmd_push` detail `off` or `hours:off`. The state at day 30 is used. A `/push off` keeps the category settings (they work again after `/push on`). |
| **Blocked** (U2) | A delivery `FAILED` with `error_summary` starting `Forbidden:`. |
| **Brief disabled** (U1a) | `cmd_brief` detail `off` in weeks 3–4. |

## 4. Queries

The queries are read-only and use aggregates or internal keys only. Replace `:owner` with the owner's Telegram id and `:day0` with Day 0 as a Kyiv-midnight `timestamptz`.

```sql
-- enrolled unknown participants still present (denominator, part 1)
SELECT user_pk FROM beta_users
WHERE telegram_user_id <> :owner AND NOT known_contact
  AND joined_at >= :day0 AND joined_at < :day0 + interval '13 days';

-- self-initiated pulls and active days (Kyiv), outside the derived 10-minute prompted window
WITH msg AS (SELECT user_pk, at FROM beta_user_activity
             WHERE action IN ('push_delivered','alert_delivered','brief_delivered'))
SELECT a.user_pk, (a.at AT TIME ZONE 'Europe/Kyiv')::date AS kyiv_day, count(*) AS pulls
FROM beta_user_activity a
WHERE a.action IN ('cmd_btc','cmd_catchup','cmd_levels','cmd_risk','cmd_events','cmd_accuracy',
                   'cmd_research','cmd_history','cmd_alert')
  AND NOT EXISTS (SELECT 1 FROM msg m WHERE m.user_pk = a.user_pk
                  AND a.at >= m.at AND a.at <= m.at + interval '10 minutes')
GROUP BY 1, 2;

-- reaction per EVENT_MOVE_LEVEL_PUSH delivery (U2), BRIEF is read the same way with brief_delivered
SELECT p.user_pk, p.action, p.detail, p.at AS delivered_at,
       EXISTS (SELECT 1 FROM beta_user_activity r WHERE r.user_pk = p.user_pk
               AND (r.action LIKE 'tab\_%' OR r.action LIKE 'btn\_%')
               AND r.at >= p.at AND r.at <= p.at + interval '10 minutes') AS reacted
FROM beta_user_activity p
WHERE p.action = 'push_delivered' OR (p.action = 'alert_delivered' AND p.detail IN ('level','event','move'));

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

**Reaction (U1a):** a `cmd_catchup` within 3 hours after 08:00 Kyiv on a withdrawal day, or a `/feedback` asking where the brief is (owner-classified).

### 6.2 U5 — multi-asset fake door (implemented)
- **Where.** A «Другие монеты» button exists only under `/help`. It is never pushed and never repeated elsewhere.
- **Reply.** A tap answers «Пока доступен только BTC. Интерес к другим монетам записан.» and records one `btn_other_assets` row.
- **What sits behind it.** Nothing multi-asset.
- **Count.** U5 counts unknown participants with taps on ≥ 2 distinct Kyiv days, or who name it unprompted in the final interview.

## 7. U3 — payment ledger (outside git)

The payment ledger is a file or sheet kept by the owner **outside the repository** (it is personal data). It never enters git, the beta database or a report export.

| Field | Meaning |
|---|---|
| `participant_fingerprint` | the keyed pseudonym the owner tools print (HMAC with `BETA_FINGERPRINT_KEY`; never a Telegram id) |
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
- **Pseudonyms only.** Reports use keyed fingerprints: `"u_" + HMAC-SHA-256(key, telegram id)[:12]` with the `.env` secret `BETA_FINGERPRINT_KEY` (owner, 2026-10-08). They are pseudonyms, not anonymous data: whoever holds the key and a Telegram id can recompute one. Fingerprints printed before the key was introduced do not match the keyed ones.
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
9. **Usage report:** the 30-minute `--beta-usage-report` is not used for U1–U5.
