# First external cohort — operational plan V2

**Status:** `OPERATIONAL_PLAN / NOT_STARTED / NO_PRODUCT_CHANGE`
**Date:** 2026-10-08
**Replaces:** the unmerged draft of PR #307 (`FIRST_EXTERNAL_COHORT_OPS_PLAN_V1.md`, commit `43c082c` on `cursor/first-external-cohort-plan-caf8`, written 2026-10-02 against the V1 product). Its structure is kept; every rule is aligned with the current decisions; what was dropped is listed in §13.

**Authority, in this order; where this plan disagrees with any of them, they win:**
- `PRODUCT_FIRST_DECISION_V1.md` §7 — the 30-day user test, U1a–U5 and the six day-30 rules, unchanged;
- `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` — the product under test;
- `PRE_BETA_SCOPE_DECISION_V1.md` §9 — the path to Day 0 and the owner actions;
- `BETA_MEASUREMENT_CONTRACT_V1.md` with Amendments 1 and 2 and §12 — every metric definition (#411);
- `ORCHESTRATION_V1.md` §4a — the release candidate and the observation week;
- `BETA_INVITE_CANDIDATE_CHECKLIST.md` — the pass conditions on production.

**This file does not** change code, schema, config, a threshold, a metric definition, the product surface or a price. It does not authorize invitations: they wait for §1.

## 0. What is already decided

- **The test.** The 30-day user test of `PRODUCT_FIRST_DECISION_V1` §7, read at T(30) by unknown-to-founder participants only, evidence precedence money > behaviour > words.
- **The product under test** is the decision-support bot of `PRODUCT_DECISION_V2`: the corridor, levels with the chance to reach them, «что было после похожих», the event calendar, the morning briefing, the unusual-hour push and the market alerts. No direct trade calls, no hype; every historical number carries N and «обычно»; every forecast carries its tracked accuracy.
- **Who counts.** The owner is excluded from every metric. Known contacts (`beta_users.known_contact`) are reported separately and never count toward PASS (contract §1.2).
- **The join path** is the existing one: invite link `t.me/<bot>?start=<code>`, language, privacy notice v8, **Вступить**, the trader-type question, the onboarding (live `/btc`, an example message, the `/check` offer).
- **The cap** stays `access.max_active_users: 20`; the owner is exempt.

## 1. Preconditions before the first invitation

All of these hold before any invitation (the ladder's stage 2, §6). Missing any one means do not invite.

1. **Owner-only items done** (`PRE_BETA_SCOPE_DECISION_V1` §9; each recorded where it says):
   - the U3 price and the manual payment method fixed in a commit: `access.u3_offer.price` / `.method` (`/admin_offer` refuses until then); the payment link itself stays in the private ledger, never in git;
   - the second acquisition channel for U4 chosen and named in the private ledger (§5);
   - 2–3 traders who have not seen the product have run the onboarding check (they are known contacts and never enter the cohort);
   - CI restored, `BETA_RESEARCH_EVIDENCE_ENABLED` recorded, the gate-coverage dry-run recorded, the interpretation labels reviewed.
2. **The step-3 deploy** (`PRE_BETA_SCOPE_DECISION_V1` §9 step 3): ОПГ-1's release-candidate record (`ORCHESTRATION_V1` §4a: commit, migrations and restart order, flags, the RC suite result, known limits, rollback), ОПГ-2's forecast-layer sign-off, the architect's red-team, the owner's deploy. In that deploy:
   - `level_race.push_trigger` goes `legacy → structural`, switched **at 00:00 UTC** (contract §12.1). If it misses step 3, Day 0 runs `legacy`, and that is a recorded limitation: the test then says nothing about the structural trigger;
   - every other Day-0 flag is at its Day-0 value (the candidate configuration table in `BETA_INVITE_CANDIDATE_CHECKLIST` §10);
   - #403's cohort boundary for `L3_LEVEL_TOUCH_24H` is dated by this deploy (contract §12.3).
3. **The 7-day observation** (`ORCHESTRATION_V1` §4a) starts with that deploy and has run 7 days without a reset.
   - **Restarts it:** any change to the collectors or the schema, to push gating or limits (including `push_trigger`), to metric definitions or to the claim journal, and turning on a Day-0 flag after the start.
   - **Does not restart it:** text fixes, display-only flags whose code was in the starting deploy, bug fixes that do not change the observed behaviour. ОПГ-1 states which kind a fix is in its record; the architect confirms.
   - The owner soak of the checklist §3 runs inside this week; it includes a real unusual-hour push, an approach message, a push withheld in another participant's night, a briefing at a participant's own time, the weekly report, and `/admin_reply` to a paused participant whose plain reply reaches the owner.
4. **The checklist passes** (`BETA_INVITE_CANDIDATE_CHECKLIST` §8 READY_FOR_INVITES): candidate deployed, smoke and startup recovery pass on production, soak accepted, telemetry verified on production, the measurement contract frozen by the owner on the final build commit (§0 of the contract; the owner's only).
5. **Invite codes.** Created by the owner with `/admin_invite_new <max_uses> [days] <label>`, one per channel (§5), no other live cohort code; revoked with `/admin_invite_revoke` when ACTIVE participants reach the cap, when the acquisition window ends, or when a purity violation says stop. No personal codes.
6. **The test opening.** After the readiness announcement and the freeze, the owner runs `/admin_test_open` before the public posts (§2). Stages 2–3 of the ladder join before it and are never enrolled.

## 2. Cohort clock

Owner decisions of 2026-10-08 (contract §1.4, §13). Calendar days on the Europe/Kyiv clock: a day may be 23 or 25 hours at a clock change; never "168 hours".

- **The test opening.** After the readiness announcement and the contract freeze, the owner runs `/admin_test_open` once (a second call is refused unless forced). Joins before it never start the test and are never enrolled; they are reported separately.
- **Day 0** is the Kyiv date of the first unknown participant who joins at or after the opening (`/admin_health` shows it). **T(n)** = 00:00 Kyiv on Day 0's date + *n* calendar days; every period is half-open. `PRODUCT_FIRST` §7's day *n* = cohort day *n*−1.
- The owner records Day 0 in contract §0 and sets `briefing.withdrawal.day0_kyiv` once, with a deploy (checklist §5); `/admin_health` reports `OK` only when the config matches the audit. That config change is the only post-freeze value and activates U1a.

| Marker | Interval |
|---|---|
| The 30-day test | [T(0), T(30)) |
| Calibration | [T(0), T(7)): clarity, timing, translation and bug fixes from written bug reports, `/feedback`, ideas, plain messages and the owner's own use (which counts for improvements, never as user confirmation). Information types, the push rule and label meanings stay as built. Every change goes in the change log. |
| Enrollment (U4) | [T(0), T(12)); U4 is read at T(12) |
| Freeze | From T(7): product, value proposition and criteria frozen. Only the dated events of contract §12.2, announced in advance, may ship after that. |
| Measurement | [T(7), T(30)); U1b and retention [T(17), T(30)) |
| U1a | Automatic (contract §6.1): `seed 20261003`, 3 Mon–Fri dates in [T(14), T(28)), the same dates for everyone, each participant's briefing withheld when their **local briefing date** is one of them. Nobody toggles anything by hand. |
| Weekly report | Sunday 19:00 on each participant's clock; never on a withdrawal date |
| Metric seal | Weekly, after each Sunday (§8) |
| U3 offer | In [T(20), T(25)), `/admin_offer send` once (§10) |
| Reading | At T(30) (§12) |
| The one extension (rule 6) | [T(30), T(44)), no product change |
| Calendar windows | Every window is a calendar window on the Kyiv date (a window across the clock change may be 169 hours). A participant joining late on day 0 has a shorter actual participation; where a metric depends on exposure, per-participant exposure is reported separately. |

A Kyiv day with delivery failure for more than 30 % of enrolled participants is excluded for everyone. A withheld briefing (SUPPRESSED / `BRIEF_WITHDRAWAL`) is not a delivery failure.

## 3. Profile of a suitable participant

A recruitment filter applied by where the invitation goes and by its text, never after join:
- reads Russian or English (the bot is RU / EN);
- trades BTC perpetuals (Binance, Bybit or OKX are the bot's venues);
- holds from tens of minutes to days and looks at BTC during the day;
- does not need an order book or a signal service from this bot.

Someone who joins through a cohort code and turns out to be a poor fit stays in the denominator. A critic is never re-labelled "wrong segment".

## 4. Known and unknown-to-founder

- **Field and command.** `beta_users.known_contact`, set with `/admin_known <telegram_user_id> on|off` **within 24 hours of the join** (contract §1.2). A participant not marked known by then is unknown. Later changes are audited and never move anyone into or out of a metric.
- **Known** when any of these holds: the founder had a conversation with them before the invite, invited them personally, showed them the bot, a screenshot or a description of its behaviour (including the 2026-09-30 scalper conversation), or they joined through a code other than the two cohort codes. Uncertain is known.
- **Unknown** only when none holds and the join redeemed a cohort code.
- **Classify before reading** that participant's activity, votes or messages. Never reclassify after behaviour, a complaint or a payment.
- **Stages 2–3 of the ladder** (§6) are known contacts by construction.
- **Never** fill the cohort with acquaintances; never admit from the waitlist. A waitlist request gets one reply and no link:

```text
Доступ только по ссылке из публичного сообщения. Личные приглашения не отправляю.
```

**Forbidden post-hoc exclusions:** a complainer, someone who "trades wrong", a non-payer, someone who stopped. They stay in the counts defined at join.

## 5. Acquisition (U4)

U4 is fixed: 2 channels, 12 calendar days [T(0), T(12)), at most 6 hours of founder work, PASS ≥ 8 unknown joins, FAIL < 8 → "Stop: distribution", recorded apart from product value.

- **Channel 1 — `cohort1-chats`.** Two public Russian-language Telegram chats where BTC perpetuals are discussed, named in the private ledger before the first post. Not a signal-selling chat, not an order-book scalping room, not a chat where the founder is known as recruiting friends. One post per chat, the same code.
- **Channel 2 — `cohort1-public` (owner-chosen).** The owner names the venue in the ledger before the first post (`PRE_BETA_SCOPE_DECISION_V1` §9). Constraints kept from #307: public, not the founder's own contacts, no paid placement, no DM list, not a venue where the founder recruited for Signalbot before.
- **Work budget.** Start/stop blocks in the ledger, Kyiv time, to the minute. At 6 hours stop: no third venue, no extension, no repost by others. Joins that arrive later from the posts already made still count. A join that needed a private conversation is known.
- **At T(12)**, below 8 unknown joins: stop inviting, revoke both codes, record "Stop: distribution".

**Invitation text — final RU, owner 2026-10-08; re-checked against the build at the RC; EN after.** Verbatim, never edited here; the only placeholder is `<ссылка>`.

```text
Приглашаю в закрытую бесплатную бету Telegram-бота по BTC — на данных фьючерсов Binance, Bybit и OKX.

Бот помогает быстро посмотреть состояние рынка: оценочные ценовые коридоры на 1, 4 и 24 часа, ближайшие уровни и оценку шанса дойти до них, календарь событий; где данных достаточно — результаты проверки таких оценок (пока — на исторических данных, проверка на новых данных только начинается). Присылает короткие уведомления о заметных изменениях.

Исторические наблюдения и прогнозные оценки обозначены отдельно. Оценки могут ошибаться; бот не даёт команд покупать или продавать.

Ищу тех, кто следит за BTC в течение дня и готов попробовать бота в обычной работе. Отзывы и вопросы можно отправлять прямо в нём, без созвонов.

Бета бесплатна до конца теста. Ближе к завершению предложим участникам беты платное продолжение — по желанию.

Вход: <ссылка> Остановить сообщения — /stop, удалить данные — /delete_me.
```

**The only public follow-up**, once per thread, to "does it say where the price goes / give trades":

```text
Бот не даёт сделок и не говорит, покупать или продавать. Вход только по ссылке из сообщения выше.
```

## 6. Invite ladder

From `BETA_INVITE_CANDIDATE_CHECKLIST` §9, after §1 holds:

| Stage | Who | Hold | Go on when |
|---|---|---|---|
| 1 | owner | the 7-day observation and soak (§1.3) | checklist §8 |
| 2 | 2–3 known people (the onboarding check) | 24–48 h | no confused-user report left unanswered; health clean |
| 3 | up to 5 known people | about 3 days | as above |
| 4 | the public posts (§5), after `/admin_test_open` | Day 0 = the first unknown join after the opening | enrollment [T(0), T(12)) |

Stages 2–3 are known contacts and never count toward PASS. A fix found in stages 2–3 follows `ORCHESTRATION_V1` §4a: if it restarts the observation week, the posts wait for the new week.

## 7. Onboarding

The bot carries it; the founder sends nothing.
1. Open the link, pick the language, read the privacy notice v8, press **Вступить**.
2. Answer or skip the trader-type question.
3. The bot then sends, once: «Вот BTC прямо сейчас» with the live `/btc`, an example message marked «Это пример, не текущий рынок», and the `/check` offer with the nearest levels one tap away.
4. `/guide` («📖 Как читать бота») explains the messages and the numbers on demand.

No founder voice note, feature list, «зайдите в /btc» or request to vote. A private tour before or after join is a purity violation (§11). The automatic `/btc` is `onboard_btc`, never a pull (contract §2).

## 8. Verbatim storage and metric seal

The owner removed the interviews on 2026-10-08. What participants write on their own is the only text input.

**Metric seal.** Once a week, after each Sunday (Kyiv), export the week's activity the contract names (contract §4 queries) to a file outside git, timestamped in Kyiv time, never edited after.

**Verbatim rules.**
- `/feedback`, ideas, plain messages and the «почему» answers after «Шум» and at `/stop` are verbatim. The bot already stores the texts (`beta_feedback_messages`, `beta_reasons`); copy them unchanged into the ledger with their source.
- Silence and an empty reply are stored as `(молчание)` and `(пустой ответ)`, never turned into a meaning.
- No translation before storage. No Telegram ids, usernames or payment links in git; local ids (`C01`, …) only.

**U5 fake door.** «Другие монеты» under `/help` (contract §6.2): a tap answers that only BTC is available and records `btn_other_assets`. It is never pushed and never mentioned in the invitation, pushes or the welcome. U5 (contract §13.2, a draft frozen before Day 0) counts unique unknown participants with taps on ≥ 2 distinct Kyiv days or an unprompted mention of another coin in their own `/feedback`, ideas or plain messages; taps and text mentions are reported separately.

**Coding.** Participants' texts are coded with the contract's appendix (§13.3, frozen before Day 0) by a coder who gets only that instruction and de-identified texts, never the desired result or any metric status. Every conclusion keeps its supporting fragment; disputed cases are reported separately. Five **different** unknown participants with the same request are grounds to consider a pivot, never to build automatically. Silence is not «no need».

**Churn.** The bot asks at `/stop`; with no answer the reason is «неизвестно». Nobody writes first.

## 9. Participants who left

- **At `/stop`** the bot asks one question itself (H3): «Не нужен / Слишком много сообщений / Непонятно, что он показывает / Другое», answerable while paused (`reason_set`, topic `stop`). That is the churn question; the founder sends no second one.
- **A paused participant's plain message** reaches the owner (J4). The owner may answer it factually with `/admin_reply`, once, with no return offer and no request to open the bot.
- **`/delete_me`** ends contact. Never look them up elsewhere. An enrolled participant stays in the denominator through the cohort record (contract §1.5).
- **A blocked bot** is `(unreachable)`; no other channel is tried.
- `/brief off`, `/push off` or per-type mutes alone are not a departure; U1a and U2 already count them.
- Paused participants get only the team's replies to their own messages, as privacy notice v8 and the pause reply say; they never get the U3 offer (§10).

## 10. The payment offer (U3)

- **What counts.** A real transfer only; a promise or a "would pay" is not a payment. A refund within 30 days cancels it (contract §7).
- **Price and method** are the ones in the pre-invitation commit (`access.u3_offer`); the link is in the private ledger.
- **Sending.** `/admin_offer` shows a preview; `/admin_offer send` sends the offer once to each ACTIVE participant, inactive ones included, in [T(20), T(25)); never after `/stop`, `/delete_me` or a bot block (a `Forbidden:` failure with no later SENT delivery). The owner's reply counts the skipped stopped, blocked and deleted participants (#416). A second `send` is refused (#405); `send again` is reserved for a failed send and is logged as such.
- **The owner's output** is the fingerprints and the time, copied into the U3 ledger (`participant_fingerprint`, `known_contact`, `offered_at`, `paid_at`, `amount`, `currency`, `refunded_at`), kept outside git.
- **Late joiners.** A participant who joins at or after T(12) is not enrolled (contract §1.3): whatever they receive or pay is reported and never enters U3.
- **No reminder.** A transfer at or after T(25) does not count. Questions about payment come back through `/feedback` or a reply and are answered factually.
- **What is paid for** (owner, 2026-10-08): one month of the same bot (BTC, all current functions), starting at the **actual** end of the free test: T(30) without an extension, T(44) with one. The offer text says in advance that an extension is possible and moves the start (#416). No continuation means a full refund on the offered terms. The amount, currency and method come later; until then `/admin_offer` refuses.
- **U3 PASS** (owner, 2026-10-08): P ≥ 3 AND P / E ≥ 25 %, where E is **every enrolled unknown participant, including those not offered** (stopped, blocked, deleted), and P the unknown participants who paid in the window and were not refunded within 30 days.
- **The funnel** is reported beside it: enrolled → offer allowed → delivered → paid → refunded.

## 11. Founder silence and purity violations

**Allowed founder messages,** only in the form fixed above:
1. the public posts and the single public follow-up (§5);
2. the one waitlist sentence (§4);
3. the U3 offer (`/admin_offer`), the single separate exception (`PRODUCT_FIRST_DECISION_V1` §7, owner amendment 2026-10-08);
4. `/admin_reply` to a participant's own message (`/feedback`, an idea, a plain message), also while they are paused: a factual answer to what was asked, stickers included, stored verbatim. Never writing first, never a reminder, never persuading them to return;
5. on a withdrawal morning, only if asked where the briefing is: «Сегодня утренней сводки не было.»;
6. the ready outage notices (`/admin_outage start|end`) and factual answers about privacy or `/delete_me`.

**User-level violations** (the participant stays in the denominator if unknown, leaves every PASS numerator; the class label is not changed): any founder message outside the list, including «посмотри бота», «зайди в /btc», «сегодня интересный рынок», «как тебе бот»; telling anyone a briefing was withheld or pointing them to `/catchup` on a withdrawal day; a private tour or a screenshot; contacting a `/delete_me` participant.

**Cohort-level violations** (a note in front of the day-30 reading; thresholds are never recomputed to clean it):
- changing a known/unknown label after the 24-hour deadline to move someone into or out of a metric;
- removing a critic, a non-payer or a poor fit from the denominator;
- a third channel, a personal code, recruiting through others, extending the window, acquisition past 6 hours;
- changing any U1a–U5 threshold, the U3 price, or `briefing.withdrawal` (seed, count, range) after Day 0;
- offering payment only to active participants, or a payment reminder;
- naming another market, a scanner or a direction in the invitation or a reply;
- from T(7): adding or removing an information type, changing the push rule or a label's meaning, or switching `level_race.push_trigger`, unless it is an owner-decided dated event of contract §12.2 announced in advance;
- tuning labels or push gates on future prices;
- counting the owner, a push-driven open as a pull, or a promise as a payment;
- a paraphrase stored instead of the verbatim;
- inviting before §1 holds.

## 12. Day-30 reading

At T(30), compute U1a, U1b, U2, U3, U4 and U5 on unknown participants only, with the contract's definitions and the thresholds of `PRODUCT_FIRST` §7; apply the six rules in order. Report beside the reading, never as an input to it:
- the known column;
- the cohort-level violations;
- the dated events of contract §12.2 with the metrics split before and after each;
- the claim cohorts of contract §12.3 (accuracy lines per `template_digest` cohort);
- the `push_trigger` limitation if Day 0 ran `legacy`.

If none of rules 1–5 fires, the single extension [T(30), T(44)) of rule 6 runs with no product change. Feedback and ideas never turn a FAIL into a PASS. There is no third round.

**Private ledger, minimum columns** (one file outside git, no Telegram ids): `local_id`, `class` (`unknown` / `known` / `owner`), `invite_label`, `joined_at` (Kyiv), `class_reason` (one sentence, at join), `acquisition_log` (blocks and summed hours), `venues` (written before the first post), `u3` (price, method, link; the §10 ledger), `change_log` (date, what, why, and whether it restarts the observation week; empty from T(7) except dated events), `verbatim`, `violations`.

## 13. What was dropped from #307, and why

| #307 rule | Status | Why |
|---|---|---|
| Authority pinned to `PRODUCT_FIRST_DECISION_V1` blob `2e51492…` on a side branch | Replaced | The current authority list above; `PRODUCT_DECISION_V2` and the pre-beta scope came later. |
| The product is a Russian briefing plus a rare push; intraday 30 min – hours only | Replaced | `PRODUCT_DECISION_V2`: decision support (corridor, levels and chances, history, events, alerts); RU / EN; the trader-type question covers horizons. |
| Precondition «push cap of 2 per UTC day»; the `welcome_push` «не больше 3 в день» check | Dropped | Per-recipient budgets on the participant's own day (2 unusual-hour, 4 market alerts) and the fuses (#379); the welcome no longer states a cap. |
| A pre-invitation commit with this plan's SHA and the U3 amount | Replaced | The U3 price and method live in `access.u3_offer` (#405); the contract freeze (§0) is the owner's record of the build. |
| Cohort day 1 = first unknown join; acquisition days A1–A12 | Replaced | Contract §1.3–§1.4 (owner, 2026-10-08): T(n), Day 0 after `/admin_test_open`, enrollment [T(0), T(12)). |
| U1a dates drawn by a hash of day 1 from cohort days 15–28; the operator switches the briefing off by hand | Dropped | Contract §6.1: `briefing.withdrawal` (`seed 20261003`, days 14–27), automatic, by each participant's local briefing date; only `day0_kyiv` is set. |
| U1a window 08:00–11:00 Kyiv | Replaced | 3 hours from each participant's own briefing slot on their clock (Amendment 1). |
| The known/unknown classification lives only in the ledger; «this plan does not add the column» | Replaced | `beta_users.known_contact` and `/admin_known` within 24 h (contract §1.2). |
| The U5 control labelled «Другие рынки» | Replaced | Built as «Другие монеты» with its reply (contract §6.2). |
| The founder's churn message the morning after `/stop` | Dropped | The bot asks the `/stop` question itself (H3); a second founder message would be an extra prompt. |
| `/admin_reply` limited to outages and privacy | Widened | J4 and the privacy notice promise that the team answers a participant's own message; the answer is factual and stored (§11 item 5). |
| Weekly interviews: the 5-question script, the «своими словами» follow-up, the external coder and the question-5 groups | Dropped | The owner removed the interviews on 2026-10-08 (#416). |
| Invitation text describing the V1 briefing | Replaced | A draft for the decision-support product, for the owner's approval (§5). |
| Channel 2 fixed as one news-channel comment thread or forum | Replaced | The owner chooses the second channel (`PRE_BETA_SCOPE_DECISION_V1` §9); the constraints are kept. |
| No release candidate, observation week, push-trigger switch or claim cohorts | Added | `ORCHESTRATION_V1` §4a and contract Amendment 2 / §12 (§1.2–§1.3, §11, §12). |
