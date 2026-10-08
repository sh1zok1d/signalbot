# Beta invite-candidate checklist — from the current state to the first invites

**Status: OPERATIONAL CHECKLIST (owner-run).** It records which steps were validated off-production (with the evidence) and which only the owner can run on the VPS, with the exact command and the pass condition. It adds no product scope. Authorities:

- `docs/PRODUCT_FIRST_DECISION_V1.md` (scope, §7 test);
- `docs/BETA_MEASUREMENT_CONTRACT_V1.md` (measurement, draft until frozen);
- `docs/PRIVATE_BETA_V0_DEPLOY.md` (runbook).

A step is DONE only when its pass condition holds on production for the exact candidate commit.

## 1. Startup-recovery race (PR #319)

**Status.** #319 is merged into main (owner-authorised, 2026-10-03). It was reconciled with the current main and passed its targeted tests: startup recovery, deploy/systemd and beta runtime.

**On the VPS** (after the owner authorises the deploy):

1. Restart Stage-1 and watch the journal:

   ```bash
   sudo systemctl restart signalbot
   journalctl -u signalbot -f | grep -m2 'startup recovery'
   ```

   You should see `started (run N)`, then `READY (complete): …`.

2. Read the newest readiness row:

   ```bash
   psql "$DSN" -c "SELECT id,status,started_at,finished_at,note FROM backfill_runs WHERE source='startup_recovery' ORDER BY id DESC LIMIT 1"
   ```

   It must read `complete`, or `partial` with the failing venue named.

3. Reboot the VPS. Within 10 minutes `journalctl -u signalbot-beta-detector` shows at most one `detector blocked … WAITING_FOR_STAGE1_START|RECOVERING`, then `detector resumed … READY`.
4. Run the smoke SQL. Its section `I. Startup recovery` must show PASS for both rows, with no "raw recovered, tape stale".
5. `python main.py --beta-health --beta-json` shows no `STAGE1_RECOVERY_NOT_READY` and no `STARTUP_RECOVERY_REPAIR_INCOMPLETE`.

## 2. Production smoke on the candidate commit

- Record the commit: `git -C /opt/signalbot rev-parse HEAD`. That hash is **INVITE_CANDIDATE_1**.
- From then on, only fixes for what breaks the test land.

| Check | How | Pass |
|---|---|---|
| Units | `systemctl list-timers 'signalbot-beta-*'` and `deploy/check_beta_units.sh` | detector, outcomes, notify, d7, history timers are active; bot is running |
| Health | `python main.py --beta-health --beta-json` | `status: OK`; no alert keys |
| Smoke SQL | `psql "$DSN" -v deploy_ts='…' -f deploy/signalbot-beta-smoke.sql` | no FAIL |
| History build | `journalctl -u signalbot-beta-history --since yesterday` | the last run is OK; `/levels` shows `после первого касания (N случаев)` |

**Telegram, with a second (non-owner) test account:**

- **Join and onboarding (J1, E5).** `/start <invite>` → language → privacy (v7) → Join → the welcome ends with «Как вы торгуете?»; an answer (or «Пропустить») brings, once, the live `/btc`, an example message marked as an example and the `/check` offer. Pass: first value within 60 seconds of Join.
- **Commands.** `/btc` (tabs, Levels, Risk, «🔬 Исследования»), `/catchup`, `/catchup 3`, `/levels`, `/risk`, `/risk 0.5`, `/check 65000`, `/check 64000 61000`, `/events`, `/accuracy`, `/research`, `/alert <price ±2%>`, `/alert`, `/alert del 1`, `/push`, `/push off`, `/push on`, `/brief off`, `/brief on`, `/brief 07:30`, `/tz +3`, `/tz kyiv`, `/type`, `/guide`, `/idea` then a plain message, a plain message on its own, `/interview` and a slot, `/history`, `/help`, `/terms`.
- **Buttons under messages.** «🔕 Не присылать такие» and «↩️ Вернуть» under a push; «Полезно / Шум» under an alert, the briefing and the weekly report, and the reason question after «Шум»; «🎯 Проверить» and «🔔 Следить».
- **Wrong arguments.** `/catchup 99`, `/risk abc`, `/alert abc`, `/alert <price ×2>`, `/alert del 1` on an empty list, `/check abc`, `/tz Mars/Base`, `/brief 25:00`, `/foo`.
- **Leaving.** `/stop` (and its one question), then `/btc`, then `/start`, then `/delete_me`.

Pass condition: every reply is human-readable. No reply shows an id (`EV-…`), a version, a digest, an English status code or a stack trace.

**Already covered off-production** by `tests/beta/test_beta_invite_journey_pg.py` (synthetic data, real code):

- the same journey, with wrong arguments;
- stale data;
- a blocked bot and a network failure;
- `/stop` and `/delete_me`;
- an internal-identifier scan of every participant-visible text.

## 3. Owner-only shadow soak (several days, no external user)

Keep a log: one line per observation, with date, time and the screenshot file name.

**What to see at least once:**

- an ordinary hour;
- an unusual-hour push (a real `TRIGGERED` episode);
- a market alert (level, event or move);
- a personal `/alert` firing;
- two morning briefings;
- `/levels` with live history;
- a VPS restart;
- a nightly history build.

**What would fail the soak:**

- a repeated alert;
- more pushes than the daily cap;
- silence where `/catchup` lists an unusual hour that was eligible for a push;
- contradictory text between push, `/btc` and `/catchup`;
- stale data shown as fresh;
- a briefing with `н/д` everywhere while `/btc` is fresh;
- anything broken after a restart or a gap.

## 4. Real-event UX review (owner, on the first real alert)

Walk push → `/btc` → «После похожих» / tabs → Levels → Risk. After each screen, write one sentence: "what do I now know about the market?" Any line you had to think about to understand goes on the list for the owner's copy decision. It is not changed silently.

**Push action.** Every push now starts with «📊 BTC сейчас», which opens the current `/btc` (owner decision 2026-10-03; `BETA_COPY_CONTRACT_V1` §7). Walk the journey from that button.

## 5. Measurement freeze

`BETA_MEASUREMENT_CONTRACT_V1.md` is FREEZE_READY: the owner decisions of 2026-10-03 are recorded in its §9, and Amendment 1 (2026-10-06, §10) adds the pre-beta scope (`PRE_BETA_SCOPE_DECISION_V1.md` §6.7). The owner reviews the amendment and freezes the contract on the final build commit by filling §0 with that hash; nothing in §0 is filled before that.

When the first enrolled unknown participant joins:

1. Record Day 0 in §0.
2. Set `briefing.withdrawal.day0_kyiv` in `config/beta_v0.yaml` once and deploy. This is the only post-freeze value; it activates U1a.
3. Mark every known contact with `/admin_known` within 24 h.
4. Keep the U3 ledger outside git (contract §7).

## 6. Telemetry end-to-end

Verified off-production (see the contract §5). On production, with the test account:

```sql
SELECT a.action, a.detail, a.at
FROM beta_user_activity a
JOIN beta_users u USING (user_pk)
WHERE u.telegram_user_id = <test id>
ORDER BY a.activity_pk;
```

Every action of the §2 smoke must be present in order, with `cmd_push` / `cmd_brief` details, and with the classes of the contract's Amendments 1 and 2: `cmd_check`, `btn_check`, `btn_watch`, `cmd_tz`, `cmd_type`, `type_set`, `set_mute` / `set_unmute` (detail = the type; a setting, never a reaction), `btn_useful` / `btn_noise` (detail = the message type, none for the unusual-hour push), `reason_set`, `cmd_guide`, `cmd_idea`, `idea_sent`, `plain_text`, `cmd_interview`, `interview_booked`, `onboard_btc` (never `cmd_btc`).

## 7. Onboarding and privacy

**Off-production status.** Before Join, the privacy screen states:

- what is stored;
- the 120-day retention;
- `/stop`, `/delete_me` and automatic deletion 30 days after `/stop`;
- that this is not investment advice.

Right after Join, the welcome states what the bot is and what it never does.

`/history` and the readiness details no longer show internal ids, raw states, codes or versions (this PR).

**Before Join.** The privacy screen now opens with what the bot is and that it gives no trading recommendations (owner decision 2026-10-03). `/btc` no longer repeats the disclaimer, which lives in `/start` and `/terms` only.

## 8. Freeze → READY_FOR_INVITES

All of the following must hold:

- INVITE_CANDIDATE_1 deployed;
- §1–§2 pass on production;
- the soak (§3) is accepted by the owner;
- the measurement contract is frozen (§5);
- telemetry is verified on production (§6).

After this point, no feature lands unless it fixes something that breaks the test.

## 9. Invite ladder

| Stage | Who | Hold | Go on when |
|---|---|---|---|
| 1 | owner | soak | §8 |
| 2 | 2–3 people | 24–48 h | no confused-user report left unanswered; health clean |
| 3 | 5 | ~3 days | as above |
| 4 | up to 10 unknown | Day 0 = first unknown join | acquisition window 12 days (§7 U4) |

Mark every known contact with `/admin_known <id> on` within 24 hours of their join (contract §1.2).

## 10. Pre-beta scope additions (2026-10-06, `PRE_BETA_SCOPE_DECISION_V1.md`)

**Owner actions before Day 0 (not code; decision §9):**
- restore CI (GitHub billing);
- check `BETA_RESEARCH_EVIDENCE_ENABLED` in the production `.env` and record it;
- run `--beta-context-dry-run` on the production tape and record the gate coverage;
- fix the U3 price and the manual payment method in a commit: `access.u3_offer.price` / `.method` (`/admin_offer` refuses until then);
- a second acquisition channel for U4;
- approve the 5-question interview script;
- review the interpretation labels (`PROVISIONAL_PENDING_DRY_RUN`);
- 2–3 traders who have not seen the product for the onboarding check;
- update or close PR #307.

**Configuration on the candidate (pass = as written):**

| Key | Value | Why |
|---|---|---|
| `decision.research_evidence.main_surfaces_enabled` | `false` | research only in its tab (decision §6.1) |
| `access.tiers_enforced` | `false` | everything open during the beta (§6.5) |
| `access.u3_offer` | price and method set | U3 on days 21–25 |
| `briefing.withdrawal.day0_kyiv` | `null` until Day 0 | U1a inactive before Day 0 |
| `PRIVACY_NOTICE_VERSION` | 7 | the participants see the current notice once |

**Calendar.** Day 0 is not earlier than the C1 rank maturity (about the end of October) plus an owner soak that sees a real unusual-hour push (backlog §1).

**Soak additions (§3).** At least once: an approach message before a personal level's touch; a push to a participant with another time zone, and one withheld in their night (QUIET_HOURS); a briefing at a participant's own time; the weekly report with its «Полезно / Шум» and «🔕»; a reply with `/admin_reply` to a paused participant.
