# Beta invite-candidate checklist — from the current state to the first invites

**Status: OPERATIONAL CHECKLIST (owner-run).** It records which steps were validated off-production (with the evidence) and which only the owner can run on the VPS, with the exact command and the pass condition. It adds no product scope. Authorities:

- `docs/PRODUCT_FIRST_DECISION_V1.md` (scope, §7 test);
- `docs/BETA_MEASUREMENT_CONTRACT_V1.md` (measurement, draft until frozen);
- `docs/PRIVATE_BETA_V0_DEPLOY.md` (runbook).

A step is DONE only when its pass condition holds on production for the exact candidate commit.

## 1. Startup-recovery race (PR #319)

**Off-production status.** On a local PostgreSQL 16, #319 merges into the current main without conflicts. The full beta, user-sim, deploy and Stage-1 main suites pass on the merge: 1118 passed, 1 environmental skip.

**On the VPS** (after the owner merges #319 and deploys):

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

- **Join.** `/start <invite>` → language → privacy → Join.
- **Commands.** `/btc` (tabs, Levels, Risk), `/catchup`, `/catchup 3`, `/levels`, `/risk`, `/risk 0.5`, `/events`, `/accuracy`, `/research`, `/alert <price ±2%>`, `/alert`, `/alert del 1`, `/push`, `/push off`, `/push on`, `/brief off`, `/brief on`, `/history`, `/help`, `/terms`.
- **Wrong arguments.** `/catchup 99`, `/risk abc`, `/alert abc`, `/alert <price ×2>`, `/alert del 1` on an empty list, `/foo`.
- **Leaving.** `/stop`, then `/btc`, then `/start`, then `/delete_me`.

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

**Known journey gap.** The unusual-hour push has only Useful / Noise buttons, so `/btc` must be typed. `BETA_COPY_CONTRACT_V1` §5 rule 8 says a push has no buttons, and the votes are U2's input. Adding Levels / Risk buttons to the push is an owner copy decision.

## 5. Measurement freeze

The owner resolves the open decisions in `BETA_MEASUREMENT_CONTRACT_V1.md` §9 and fills §0. Day 0 is not declared before that.

## 6. Telemetry end-to-end

Verified off-production (see the contract §5). On production, with the test account:

```sql
SELECT a.action, a.detail, a.at
FROM beta_user_activity a
JOIN beta_users u USING (user_pk)
WHERE u.telegram_user_id = <test id>
ORDER BY a.activity_pk;
```

Every action of the §2 smoke must be present in order, with `cmd_push` / `cmd_brief` details.

## 7. Onboarding and privacy

**Off-production status.** Before Join, the privacy screen states:

- what is stored;
- the 120-day retention;
- `/stop`, `/delete_me` and automatic deletion 30 days after `/stop`;
- that this is not investment advice.

Right after Join, the welcome states what the bot is and what it never does.

`/history` and the readiness details no longer show internal ids, raw states, codes or versions (this PR).

**Owner decision.** The pre-Join screen does not yet say in one line what the bot is; it says so right after Join.

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
