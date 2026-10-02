# First external cohort — operational plan V1

**Status:** `OPERATIONAL_PLAN / NOT_STARTED / NO_PRODUCT_CHANGE`
**Date:** 2026-10-02
**Authority:** `docs/PRODUCT_FIRST_DECISION_V1.md` at commit `d7f931d070d65815c4f1c39284af20a6d5b21f90`, blob `2e51492f15b75919221fa8dd73dfb3d483294bf9` (branch `origin/ccr-f8122eff-axgnoe` at the time of this plan). If that blob changes, revise this plan before any invitation. Where this plan and that decision disagree, the decision wins.
**This file does not:** change code, schema, config, the product surface, a price, a roadmap, or the U1a–U5 thresholds. It fixes the operating procedure so the first cohort can be run from §7 of the decision without a further product decision.

The cohort is not authorized to start by this file. Invitations wait until the preconditions in §1 are true.

## 0. What is already decided

The test is the 30-day user test in `PRODUCT_FIRST_DECISION_V1.md` §7. This plan only makes it executable.

- The product under test is the one in §2 and §3 of the decision: a Russian briefing that compresses "what happened while I was away, who dominates now, and how unusual is it", once in the morning, plus a rare push when an hour is unusual. No direction, no trade instruction, no edge claim.
- The target user is unchanged from `BETA_BTC_MULTI_HORIZON_UX_V1.md`: a Russian-speaking BTC perpetual intraday trader who holds from about 30 minutes to several hours.
- PASS is computed on **unknown-to-founder** users only. The owner's usage is excluded from every metric. Acquaintances are counted separately and never toward PASS.
- Evidence precedence at day 30 is money, then behaviour, then words. Interviews cannot turn a FAIL into a PASS.
- The active-user cap stays `access.max_active_users: 20`. The config states the owner is exempt. This plan does not raise the cap.
- Join path stays the existing one: invite link `t.me/<bot>?start=<code>`, language choice, privacy notice, **Вступить**.

## 1. Preconditions before the first public post

All of the following are true before either channel is posted. Missing any one of them means do not post.

1. The build-to-test MUST scope in the decision §3 is done, including `/catchup`, the 08:00 Kyiv morning briefing, `/brief off`, `/push off`, the 1h gate, the push cap of 2 per UTC day, and the cleaned user surface.
2. Data maturity follows the decision §6. The external date is set by actual maturity of the V2 tape baselines and 30-day ranks, and by MUST completion. Owner use before that date is bug-finding only.
3. The owner has already seen real pushes on the live bot (existing rule in `PRIVATE_BETA_V0_DEPLOY.md`). The first external post is not the owner's first look at push.
4. A pre-invitation commit exists on `main` and records, in the repo: this plan's commit SHA, the decision blob SHA above, and the single U3 amount and currency. The manual payment link is **not** committed. It is written only in the private ledger (§8). Invitations do not start while the amount line is absent. This plan does not choose the amount.
5. Two invite codes exist, created by the owner with the existing command, and no other live cohort code exists:
   - `/admin_invite_new 20 40 cohort1-chats`
   - `/admin_invite_new 20 40 cohort1-public`
   The `40` is the code lifetime in days (covers the 12-day acquisition window plus the 30-day test). `max_uses` 20 matches the cap. Labels are the channel ids. Codes are revoked with `/admin_invite_revoke` when ACTIVE users reach 20, when the acquisition window ends, or when a purity violation says to stop inviting. Do not create a personal code.
6. The two venues in §4 are named in the private ledger before the first post.
7. The external coder in §8 is named in the private ledger. The coder has no role in Signalbot and is not shown metrics, thresholds, or known/unknown labels.
8. The live `/start` welcome does not state a push cap other than 2 per day, and it does not promise a direction or a trade. The string currently in `beta/i18n.py` (`welcome_push`: "не больше 3 в день") is a pre-MUST string. Invitations wait until the running bot no longer says that.
9. `/help` contains the U5 control from §8, label `Другие рынки`, and pressing it only records the click.

## 2. Cohort clock

The clock is **Europe/Kyiv**, because the briefing time and the quiet hours in the decision are Kyiv times.

| Marker | Rule |
|---|---|
| Acquisition day A1 | The Kyiv date of the first public post. |
| Acquisition window | A1 through A12 inclusive. U4 is read at the end of A12. |
| Cohort day 1 | The Kyiv date on which the first `unknown` user presses **Вступить**. If no unknown user has joined by the end of A12, cohort day 1 never starts and U4 is FAIL ("Stop: distribution"). |
| Cohort days 1–7 | Calibration only: clarity, timing, translation, bug fixes driven by the day-7 interview. Information types, the push rule, and the meaning of labels stay as built. Every change is one line in the ledger change log. |
| Cohort day 8 00:00 | Product, value proposition, and decision criteria are frozen. |
| Measurement | Cohort days 8–30. Retention and U1b use days 18–30. Week-1 behaviour is never read as retention. |
| Interview mornings | Cohort days 7, 14, 21, and 28, after 00:00, after that week's metric seal (§8). |
| U3 offer window | Cohort days 21–25. |
| Reading | After cohort day 30 has closed, unknown users only, rules in the decision §7. |

A Kyiv date on which delivery fails for more than 30% of enrolled users is excluded for everyone. Intentional suppression of the morning briefing on a withdrawal day is not a delivery failure.

### U1a dates, drawn once

On cohort day 1, as soon as day 1's date is known, compute the three withdrawal dates and write them into the private ledger. Do this before looking at any later market day. Do not redraw.

Eligible pool: the Kyiv weekdays (Monday–Friday) whose cohort day index is 15 through 28 inclusive.

```python
import datetime as dt
import hashlib
import random

def u1a_dates(day1: dt.date) -> list[dt.date]:
    pool = [day1 + dt.timedelta(days=offset) for offset in range(14, 28)]
    pool = [d for d in pool if d.weekday() < 5]
    seed = int.from_bytes(
        hashlib.sha256(f"COHORT_01_U1A|{day1.isoformat()}".encode()).digest()[:8],
        "big",
    )
    rng = random.Random(seed)
    rng.shuffle(pool)
    return sorted(pool[:3])
```

On those three dates the morning briefing is not sent to any beta user. The operator sets briefing delivery off before 08:00 Kyiv and restores it the next Kyiv midnight, and writes both actions in the change log. Users are not told that the briefing was withheld. If one of the three dates is later a delivery-failure exclusion, it stays on the list and is not replaced. U1a then has fewer than three measurable days. The PASS rule still requires a reaction on at least 2 of the 3 originally drawn dates, so a failed date cannot be swapped for a quieter one.

U1a reaction window for each drawn date: `/catchup` from 08:00 to 11:00 Kyiv, or an unprompted user message in that same window asking where the morning summary is. The operator's reply, if any, is only: `Сегодня утренней сводки не было.` The reply does not mention `/catchup`.

## 3. Profile of a suitable participant

The profile is a recruitment filter. It is applied by where the posts go and by the invitation text. It is not applied again after someone has joined.

A suitable participant, for choosing venues and writing the invitation:

- reads Russian;
- trades BTC perpetual (Binance, Bybit, or OKX are the bot's venues; the invitation does not require all three);
- holds positions on the order of 30 minutes to several hours, and looks at BTC during the day;
- does not need the order book from this bot.

People who match this description and arrive through a public cohort code are the intended unknown users. The decision forbids re-labelling a critic as "wrong segment" after the fact. Someone who joins and turns out to be a poor fit stays in the unknown denominator if they were classified `unknown` at join.

## 4. Who is excluded from the main cohort

The main cohort is the unknown-to-founder set that can count toward PASS. These people are excluded from it:

| Person | Treatment |
|---|---|
| The owner | Class `owner`. Excluded from every metric. No interview script is sent to the owner. |
| A founder's acquaintance (§5) | Class `known`. Counted in a separate column. Never in a PASS numerator or in the unknown denominator. |
| Anyone who joins through a code other than `cohort1-chats` or `cohort1-public` | Class `known`. Personal recruitment is not an unknown join. |
| Anyone the founder has already shown the bot, a screenshot, or a description of how it behaves, including the 2026-09-30 scalper interview | Class `known`, even if they later use a public link. |
| A person who becomes the subject of a purity violation after join (§11) | Stays in the unknown denominator if they were `unknown` at join. Removed from every PASS numerator. The class label is not rewritten. |

Do not invite acquaintances to "fill the cohort". Do not grant access from the waitlist. A waitlist request gets one reply and no link:

```text
Доступ в эту когорту только по ссылке из публичного сообщения. Личные приглашения не отправляю.
```

That single reply does not by itself change the class of a stranger who later joins through a public code. Any further message does (§5).

Post-hoc exclusions that are forbidden: dropping a complainer, dropping someone who does not trade "correctly", dropping a non-payer, dropping someone who stopped. They remain in the counts defined at join.

## 5. Known and unknown-to-founder

Classify at the moment the join is first seen, before opening that user's activity, votes, or messages. Write the class once. Do not change it after behaviour, an interview, a complaint, or a payment.

**`unknown`** only when every line is true:

1. The founder cannot name this person from before A1: no prior two-way conversation, no shared work, no family, no friendship, no earlier interview.
2. The join redeemed `cohort1-chats` or `cohort1-public`.
3. The founder did not ask anyone to pass them the link, and did not send them the link in a private message.
4. The founder has not previously shown them the bot, a screenshot, or a description of its behaviour.
5. The founder is sure. Uncertainty is `known`.

**`known`** when any line fails. Acquaintances are this class. They are the separate count in the decision. They never move a threshold.

**`owner`** is the owner account only.

A stranger who sends one access question and receives only the waitlist sentence in §4 can still be `unknown` if they later join through a public code and lines 1–5 hold. The next founder message after that sentence makes them `known` if it happens before join. After join, an extra founder message is a purity violation (§11): the class stays `unknown`, and the user leaves every numerator.

When `beta_users.known_contact` exists, set it once at classification to match this ledger (`known` → true, `unknown` → false, `owner` → true). Until that column exists, this ledger is the classification record. This plan does not add the column.

## 6. Acquisition (U4)

U4 is fixed by the decision: two channels, 12 days, at most 6 hours of founder work, PASS at 8 or more unknown joins, FAIL below 8 at the end of A12 ("Stop: distribution", recorded apart from product value).

### Channel 1 — `cohort1-chats`

Russian-speaking Telegram chats where people discuss BTC perpetual intraday trading. This is the channel the decision names.

- Exactly two chats, named in the ledger before A1.
- A chat qualifies when it is public, the language is Russian, and the visible topic is BTC perpetual positions held from tens of minutes to hours.
- A chat does not qualify when it sells signals, when it is an order-book scalping room, when the founder is already known there as someone recruiting friends, or when the founder has already posted about Signalbot there.
- One post per chat. The text is §6.3 with the `cohort1-chats` link. The same link in both chats: they are one channel.

### Channel 2 — `cohort1-public`

This closes the open question in the decision §10 ("the second acquisition channel beyond Russian-speaking perp chats") for this cohort only. It is a distribution choice, not a product change.

Exactly one venue, named in the ledger before A1:

- a public Russian-language crypto discussion that is not a perp-trading chat;
- either the open comment thread of one Russian crypto news Telegram channel, or one thread on a Russian crypto forum;
- the founder has not recruited for Signalbot there before;
- no paid placement, no Discord or Telegram DM list, no post to the founder's own contacts.

One post. The text is §6.3 with the `cohort1-public` link.

### Work budget

The 6 hours cover choosing the venues, writing their names, posting, and classifying joins. They do not cover weekly interviews.

Log each block in the ledger as start and stop, Kyiv time, to the minute. When the logged sum reaches 6 hours, stop. Do not open a third venue, do not extend A12, do not ask someone else to repost, and do not answer product questions in the thread beyond the single clarification in §6.4. Joins that arrive later from the posts already made still count. A join that required a private conversation is `known`.

At the end of A12, if unknown joins are below 8: stop inviting, revoke both codes, record "Stop: distribution". Do not infer that the product has no value.

### Invitation text

Post this text unchanged. The only substitution is the link. No founder signature, no "напишите мне", no price, no urgency, no request to open the bot on a particular day.

```text
Закрытая бета Telegram-бота по BTC perpetual (Binance, Bybit, OKX).

Утром приходит короткая сводка: что произошло, пока вас не было, кто сейчас доминирует и насколько это необычно относительно обычного. Реже — одно сообщение, если какой-то час сильно выбивается из обычного.

Бот только описывает состояние рынка. Он не даёт сделок и не называет направление.

Имеет смысл, если вы торгуете BTC внутри дня и обычно держите позицию от получаса до нескольких часов. Это не стакан и не скальперский бот.

Вход по ссылке, около двух минут: <INVITE_URL>
Остановить сообщения: /stop. Удалить данные: /delete_me.
```

### The only public follow-up

If someone asks in the same thread whether the bot says where price will go, or whether it gives trades, reply once with:

```text
Бот не даёт сделок и не называет направление. Вход только по ссылке из сообщения выше.
```

No other public reply. No screenshots. No "сегодня как раз интересный рынок".

## 7. Onboarding, under two minutes

The founder sends no onboarding message. The user does only what the bot already asks:

1. Open the invite link (about 10 seconds).
2. Press **Русский** (about 10 seconds). English is available; the cohort texts and interviews stay Russian. A user who picks English is still classified by §5 and still receives the Russian interview script.
3. Read the privacy notice and press **Вступить** (the notice is the long step; it fits in the remaining minute for a skim, and the bot does not add a second form).
4. Stop. The existing welcome is the whole tour.

The founder does not follow with a voice note, a feature list, a "зайдите в /btc", or a request to vote Useful. Questions about privacy are answered by the notice itself. A private product tour before or after join is a purity violation.

Commands the user may discover from the bot, which the founder does not teach in chat: `/btc`, `/catchup`, `/brief off`, `/push off`, Useful / Noise, `/feedback`, `/stop`, `/delete_me`. Teaching this list in a founder message is an extra prompt. It stays out of the invitation and out of the interviews.

## 8. Weekly interview, verbatim storage, metric seal

### When

Four sends, on cohort mornings 7, 14, 21, and 28, after 00:00 Kyiv. Each send goes to every user who pressed **Вступить** before that midnight and who has not used `/delete_me`. Users who join later in the day of an interview are not chased with an extra send.

Order on those mornings:

1. Seal the metric export (§8.3).
2. Send the script. Do not open that user's activity before sending.
3. On day 21 only, send the U3 offer (§10) at least four hours after the interview message, as a separate message.

The day-7 interview is the only interview that may produce a calibration change, and the change must be deployed before day 8 00:00. Interviews on days 14, 21, and 28 produce no product change.

### The script

One message, these five questions, this order, every week. No examples, no "other coins", no "scanner", no "alerts", no payment question, no "would you miss it".

```text
Короткий разговор раз в неделю. Пять вопросов, без правильных ответов. Можно ответить здесь текстом. Если неудобно — напишите «не сейчас», и я не напомню до следующей недели.

1. За последние 7 дней вы открывали бота? Если да — когда и что хотели узнать.
2. Что в нём оказалось полезным, если что-то было?
3. Что мешало пользоваться тем, что уже есть?
4. Было ли сообщение от бота, после которого вы зашли? Что вы сделали после него?
5. Чего вы ждали от такого бота и не нашли?
```

If the user writes "не сейчас", store that as the verbatim and do not write again until the next interview morning. If an answer is ambiguous, one follow-up is allowed, and only this sentence:

```text
Повторите, пожалуйста, своими словами — я не хочу додумывать.
```

Store the follow-up and the reply. No second follow-up. A voice call, if the user asks for one, uses the same five questions, lasts at most 15 minutes, and is typed as they speak.

Question 5 is the unprompted input for U5 and for the Pivot rule. Multi-asset demand counts only when the user's own words name a market other than BTC. "Сканер" or "больше данных" without another market is not U5. The founder does not suggest the missing thing.

### Metric seal

Before each interview morning send, export the activity the decision already names (commands, `push_delivered`, brief delivery, `/brief off`, `/push off`, failed delivery, blocks) for the days being closed. Save the file outside the git repository with the Kyiv timestamp in the filename. Do not edit the file after saving. The founder may read a user's rows only after that user's verbatim for that week is stored.

### Verbatim rules

Words are stored as said or typed. A summary may exist only as a later coder note in a separate column. The summary never replaces the verbatim, and the founder does not write the summary.

- Interview answers and `/feedback` texts are both verbatim. `/feedback` is already stored by the bot in `beta_feedback_messages`; copy that text unchanged into the ledger row with `source: bot_feedback`. Do not rewrite it.
- If the user numbered their answers, store one row per question number.
- If the user sent one block of text, store it as a single row with `question: unsplit`. Do not divide it into questions by inference. The coder may divide it. The founder may not.
- Silence, "не сейчас", and an empty reply are stored as `(молчание)`, `не сейчас`, or `(пустой ответ)`. They are not converted into a meaning.
- Do not translate before storage.
- Do not commit Telegram ids, usernames, payment links, or the filled ledger. The ledger lives outside the repository, in a private directory the founder keeps. Local ids (`C01`, `C02`, …) are the only identifiers that go to the coder.

Ledger row:

```text
local_id: C03
class: unknown
invite_label: cohort1-public
joined_at: 2026-11-02T14:06+03
week: 2
source: interview
question: 5
asked_at: 2026-11-16T09:05+03
verbatim: |
  <exact words>
```

Classification rows use the same header with `source: classification`, `question: -`, and `verbatim` set to the one-sentence reason, written at join.

### Coding

After each interview morning, send the coder only `local_id`, `week`, `question`, and `verbatim`. Do not send class, metrics, thresholds, or the founder's impression.

The coder groups question-5 answers that ask for the same missing thing. The group label is a short quote from the answers, not a feature name from the roadmap. Two answers share a group only when a reader without project context would say they asked for the same thing. The coder also marks `named_other_market` when the words themselves name a market other than BTC.

The founder does not merge or split those groups afterward. Pivot uses a group only when at least five `unknown` users are in it. An interview answer counts toward U5 only when the coder marked `named_other_market` and that user had not clicked the `/help` control below before the interview was sent.

### U5 control in `/help`

The decision's U5 method is a fake door in `/help` plus question 5. The door is a measurement control, not the multi-asset scanner. The scanner stays on the DO-NOT-BUILD list. This plan does not add a screen, a second asset, or a follow-up message.

Before the first public post, `/help` has one extra control, label exactly `Другие рынки`. Pressing it records one activity event for that user and that time, and the bot does not reply with another market, a promise, or a question. The control is absent from the invitation, the weekly script, pushes, and the welcome. A user counts on the click half of U5 when that event occurs on two distinct Kyiv dates. The label is frozen here so it is not rewritten after the first click.

## 9. Users who left

Contact is one message, and only for `/stop` or a blocked-bot failure that still accepts a Telegram message. Send it on the next Kyiv morning after the event, after midnight, not in the same hour they left.

`/delete_me` ends contact. Do not write. Do not look them up in another chat. Their join remains in the unknown denominator if they were `unknown`.

`/brief off` alone, or `/push off` alone, is not a departure. Those users stay on the weekly script. Both switches off is still not a departure; U1a and U2 already count the switches. The weekly script continues.

The message:

```text
Вы остановили бота. Можно один вопрос: почему вы это сделали? Ответьте как есть, можно одной фразой. Если не хотите отвечать — ничего не пишите, я не напишу снова.
```

Store the reply verbatim with `source: churn`. If they do not reply within 7 days, close the row as `no_reply`. The only reply the founder may then send is `Спасибо, записал.` No return offer, no feature explanation, no request to look at the bot.

A blocked bot that cannot be messaged is `source: churn`, `verbatim: (unreachable)`. Do not try another channel.

Churned users who have not used `/delete_me` still receive the U3 offer in the day 21–25 window. The offer is sent to everyone enrolled, as the decision requires, including people who stopped.

## 10. The payment offer (U3)

U3 is a real transfer. "I would pay" is not payment. This plan does not set the price. The amount and currency are the ones in the pre-invitation commit from §1. The manual link is the one in the private ledger.

Send this once, to every enrolled user who has not used `/delete_me`, known and unknown alike, including people who have `/stop`. Send it on cohort day 21, at least four hours after the interview. A user who joins on day 22, 23, 24, or 25 receives the same text once, on the morning after they join. A user who joins on day 26 or later is not offered payment. They remain in the unknown denominator if they are `unknown`, which keeps the 25% rule conservative.

```text
Это одно сообщение про оплату, без продолжения.

Signalbot можно оплатить на 30 дней: <AMOUNT> <CURRENCY>.
Ссылка: <MANUAL_LINK>
Оплата необязательна. Бот не отключится, если вы не заплатите.
Возврат в течение 30 дней отменяет оплату.
Если не хотите — ничего не делайте. Я не спрошу снова.
```

No reminder on days 22–25. A transfer that arrives on day 26 or later does not count. A refund within 30 days removes that user from the paid count. Known users' payments are recorded and ignored for the threshold. The denominator of the 25% rule is every `unknown` user who pressed **Вступить**, including those who later stopped or deleted themselves. The numerator is `unknown` users with a transfer inside the window that was not refunded within 30 days.

## 11. Founder silence, and what counts as a purity violation

### Allowed founder messages

Only these, and only in the form fixed above:

1. The two public posts and the single public clarification in §6.
2. The one waitlist sentence in §4.
3. The weekly script, plus at most one "своими словами" follow-up, plus `Спасибо, записал.` after a churn reply.
4. The one churn question.
5. The one U3 offer.
6. On a withdrawal morning, and only if the user asks where the summary is: `Сегодня утренней сводки не было.`
7. A factual answer to a bot outage or a privacy/deletion request: what broke or what `/delete_me` does. The answer does not suggest opening the bot, and the answer is stored verbatim.

`/admin_reply` is limited to item 7. A thank-you, a hint, or a product explanation through `/admin_reply` is a violation.

### Violations

Record the violation in the ledger the day it happens. Do not delete the underlying rows.

**User-level.** The user, if they were `unknown`, stays in the unknown denominator and is removed from every PASS numerator. The class label is not changed.

- Any founder message outside the allowed list, including "посмотри сегодня бота", "зайди в /btc", "посмотри утреннюю сводку", "сегодня интересный рынок", "как тебе бот", and a reaction to `/feedback` other than item 7.
- Telling a user that a briefing was withheld, or telling them to use `/catchup`, on a withdrawal day.
- A private product tour, a screenshot, or a description of behaviour beyond the invitation text.
- Contacting a `/delete_me` user.

**Cohort-level.** Attach the note to the day-30 reading. Do not recompute thresholds and do not drop the note to obtain a cleaner rule.

- Changing a known/unknown label after join.
- Removing a critic, a non-payer, or a poor fit from the unknown denominator.
- A third channel, a personal invite code, a request that someone else recruit, an extension of A12, or acquisition work past 6 hours that produces further persuasion.
- Changing any U1a–U5 threshold, the U3 amount, or the withdrawal dates after they are recorded.
- Redrawing the withdrawal dates after day 1.
- Offering payment only to active or enthusiastic users, or sending a payment reminder.
- Naming another market, a scanner, alerts, or a direction inside an interview, the invitation, or a reply. This touches U5 for the whole cohort because the prompt is shared.
- A product change on or after day 8 that adds or removes an information type, changes the push rule, or changes what a label means. A fix that only restores the already-frozen behaviour is logged and is not this violation.
- Tuning labels or the push gate on future prices, or on how well they explain the past.
- Counting the owner's activity, counting a push-driven open as pull, or counting a promise to pay as U3.
- The founder, or anyone who has seen the metrics or the PASS table, coding the interviews.
- Storing a paraphrase and discarding the verbatim.
- Starting posts before §1 is complete.

The day-30 rules remain the six rules in the decision §7. A cohort-level violation is reported in front of that reading so Continue / Reposition / Pivot is not taken from a contaminated run. This plan does not add a seventh verdict and does not authorize a replacement cohort.

## 12. Day-30 reading

After day 30 closes, compute U1a, U1b, U2, U3, U4, and U5 on `unknown` users only, with the thresholds already printed in the decision. Then apply the six rules in order. Interviews choose a direction only inside Reposition and Pivot. They do not flip a FAIL. If none of rules 1–5 fire, the single 14-day extension in rule 6 is available only with no product change. There is no third round.

The separate `known` column is reported beside the reading and is not an input to it.

## 13. Private ledger, minimum columns

One file outside git. No Telegram ids. No payment link in git; the link may sit in this private file.

| Column | Values |
|---|---|
| `local_id` | `C01`… |
| `class` | `unknown`, `known`, `owner` |
| `invite_label` | `cohort1-chats`, `cohort1-public`, or `other` |
| `joined_at` | Kyiv timestamp |
| `class_reason` | one sentence, written at join |
| `acquisition_log` | start/stop blocks, summed hours |
| `venues` | the two chat names and the one public venue, written before A1 |
| `u1a_dates` | three dates from §2, written on day 1 |
| `u3_amount` | copied from the pre-invitation commit; link stored here only |
| `change_log` | date, what changed, why; empty on and after day 8 except a restoration fix |
| `verbatim` | rows from §8 and §9 |
| `violations` | date, user-level or cohort-level, the act |
| `coder_groups` | quote-labels returned by the coder, unedited |

The day-30 note is appended to this file and copied, without personal data, into the repo only when the owner records the result. This plan does not pre-write that result.
