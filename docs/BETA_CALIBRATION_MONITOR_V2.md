# Calibration monitor V2

**Status:** `SHADOW / NOT_THE_LIVE_WORDING_RULE` (2026-10-12).

`docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md` remains the rule for what users read. V1 (`beta.claims.touch_wording`, health component `touch_live_cal`) is unchanged. This monitor is a pure function of an immutable claim journal. Nothing here writes production, clears a sticky flag, or refits a model. `beta/health.py` and the notifier do not call it.

Code: `beta/calibration_monitor.py`. Tests: `tests/beta/test_calibration_monitor.py`, `tests/beta/test_calibration_journal_export.py`. Shared-path check: `scripts/beta/compare_calibration_monitor_v1.py`, result `docs/BETA_CALIBRATION_MONITOR_V2_COMPARISON.json`. Read-only export: `scripts/beta/export_calibration_journal_v2.sh` and `scripts/beta/export_calibration_journal_v2.sql`. Offline replay: `scripts/beta/replay_calibration_monitor_v2.py`.

`variants_tried_for_thresholds = 0`. The thresholds below were not moved after the shared-path check, and they were not fit to the October 2026 alerts.

## What it scores

One book is a forecast **procedure**, a **specification**, a **family** (`touch` or `neither`), and a **horizon** (`1h`, `4h`, `24h`). Each specification has six predeclared books.

- Procedure `TOUCH_CHANCE_PROCEDURE_V1` is the claim classes scored by `TOUCH_V1` / `NEITHER_V1`. It is not a coefficient vector.
- `snapshot_id` is `stats_digest`, or `stats_pk` when the digest is absent. Snapshot ids are stored and **do not reset** the evidence. A nightly refit can change coefficients and still leave the same procedure.
- The evaluation identity is `eval_rule_digest` when the journal has one, so two rule versions do not pool. A digest mismatch, or a rule id that does not match the family, is `TECHNICAL_FAULT`.
- A book is one procedure and one specification. Rows from the production journal carry procedure `TOUCH_CHANCE_PROCEDURE_V1` and spec `JOURNAL_UNSPECIFIED`. A row that names another procedure or spec is a separate book. Adding that book does not move `E_CONFIRM`. The 10% bound stays inside one specification's six books. Two specifications watched at once are two separate 10% families. A statement about any book across both families is not a 10% bound.
- Monitor version is `CALIBRATION_MONITOR_V2`. Recomputing it does not rewrite claims or outcomes.

The monitor imports no rangecast module.

## Filtration

A claim issued at `t` with horizon `H` is settled by prices on `(t, t+H]`. The next bet is valid only when every claim already inside the e-process has resolved before this claim is issued.

Candidate claims are those issued in the first hour of a horizon slot (production claims are issued one minute after the bar). Claims in one slot are averaged into one step. The chain then keeps a slot only when its issue time is at or after the previous kept slot's resolution. Hours inside a 4h or 24h window are counted as claims and then ignored by the decision statistic. Calendar floors still use distinct UTC issue days of the kept slots, so a burst of 1h anchors cannot confirm inside a week.

The previous daily average was not a valid time index: a 24h claim issued on day D resolves on day D+1, after the next day's claims have already been issued. Betting on that day order uses outcomes that were not yet known.

## Channels and the false-confirm bound

Each book runs four channels. A near-zero average residual is not treated as a pass.

| Channel | Statistic | What a zero LEVEL residual can still hide |
|---|---|---|
| `LEVEL` | mean of y − p | a uniform shift of the horizon |
| `TAIL_HIGH` | y − p on p ≥ 0.70 | the upper tail |
| `TAIL_LOW` | y − p on p < 0.30 | the lower tail |
| `SHAPE` | (y − p on p ≥ 0.5) minus (y − p on p < 0.5), halved on input | a slope error |

The book's decision statistic is the average of the four channel e-processes. A channel with no claims stays at 1. Dropping empty channels after seeing the data would be optional stopping, so the dilution stays. λ ∈ {−0.5, −0.25, +0.25, +0.5}.

Ville's inequality applies to that one non-negative supermartingale per book. Six books, dependent or not, are covered by a union bound:

| Bar | E-value | Union bound on any book ever crossing |
|---|---|---|
| Suspicion | 20 | 30% |
| Confirmation | 60 | 10% |

Suspicion and confirmation are nested thresholds on the same process, so the 10% confirm bound is not added on top of the 30% suspect bound. Both also require the practical gate of 5 pp, the channel's own e-value at least 20, agreeing direction, and the day floor (10 days to suspect, 20 to confirm). There is no second bootstrap look.

## When the 10% bound applies

`E_CONFIRM = 60` is `6 / 0.10`. When the conditions below hold, Ville's inequality plus a union bound says that the probability of any of the six books ever reaching 60 is at most 10%, at any time. The books may share a price path. The union bound does not need them to be independent.

The bound applies to a scored step only when all of the following are true:

1. Each scored residual has conditional mean 0 at the claim's issue time, given the information the probability was allowed to use.
2. The stakes λ stay the four values fixed above. They are not chosen after seeing the journal.
3. A step is added only after every earlier step in that book has resolved, and whether a claim is an anchor depends only on its timestamps.
4. The six books and the four channels are the ones named above. A channel with no claims stays at 1. Dropping it after seeing the data would be optional stopping.
5. A row is left out for coverage or status in the same way for a hit and for a miss.

The 10% figure does not apply to the suspect bar. That union bound is 30%, on the same process, and is not added to the 10%. It does not apply to which channel is named. The 5 pp gate is not a second test: it can only make a false confirmation rarer than 10%. It does not apply to the wording users currently read. It does not apply when the chance of clearing the coverage rule depends on the price path. That case is in the next section.

## States

| State | Rule |
|---|---|
| `INSUFFICIENT_DATA` | Fewer than 10 UTC days on the anchor chain. A large gap does not override this. |
| `WITHIN_NOISE` | Enough days, and the book mixture has not reached 20 with a channel past the 5 pp gate. |
| `SUSPECTED_DEGRADATION` | At least 10 days, book e-value ≥ 20, and at least one channel past 5 pp with agreeing direction. No user-text change. |
| `CONFIRMED_DIVERGENCE` | At least 20 days, book e-value ≥ 60, and a channel past the same practical gate. |
| `RECOVERED` | After a confirmation, a later 20 UTC days have every present channel inside 5 pp and a fresh e-process on that window below 2. The confirmation episode stays, including the e-value at the crossing. |
| `TECHNICAL_FAULT` | Illegal probability, naive timestamp, missing rule, mixed rule digests, or a horizon window that is not the claimed horizon. |
| `INCOMPLETE_DATA` | At least 10 due rows and more than 20% of those due rows unfinished. No calibration verdict is issued on top of a hole. |

A channel is named on the episode only when its own evidence meets the gate. The 10% bound is on the book, not on which channel is named.

## Incomplete price windows

`TOUCH_V1` / `NEITHER_V1` mark a hit `COMPLETE` even when coverage is below 0.9, and mark a non-hit `NO_DATA` in that same partial window. Scoring the hit and dropping the miss pushes the touch rate up and the neither rate down.

The monitor treats coverage below 0.9 as unfinished for both outcomes. Coverage is the full-window fraction stored at the horizon, not a truncation at the first touch (`fetch_due_claims` waits until `horizon_end`). If coverage is absent, the monitor does not invent it and will score a `COMPLETE` row. Production outcomes store coverage. The export keeps `realized.coverage` when the outcome stored it.

If the chance of coverage ≥ 0.9 does not depend on the price path, the claims that remain are still a calibrated subset of the full-window procedure, and the 10% bound applies to that subset.

If that chance does depend on the path — minutes missing more often on a touch than on a quiet window, for example — the scored rows can have a residual whose mean is not 0 even when every issued probability was right for the full window. The 10% bound does not cover that subset. The 20% unfinished gate does not restore the bound. It only refuses a calibration verdict when the hole is large: at least 10 due rows and more than 20% of those due rows unfinished. A smaller price-dependent hole can still pass the gate and still bias the e-process.

A forecast whose horizon has not elapsed is `PENDING`. It is not a due row, so it is not in the unfinished fraction and it is not scored. A 24h issue before that horizon ends does not move the book to `INCOMPLETE_DATA`. `NO_DATA`, a missing outcome after the horizon, and coverage below 0.9 stay unfinished for a hit and for a miss. The journal replay passes the process clock: `horizon_end` still in the future is pending; once that time has passed, a missing outcome is a hole. Pending rows are outside the scored set the 10% bound talks about.

## Journal adapter

`observations_from_claim_rows` reads claim class, `as_of`, `horizon_end`, probability, `stats_digest` / `stats_pk`, `eval_rule_digest`, `eval_rule_id`, `rule_version`, outcome status, and `realized.touched` / `realized.neither` / `realized.coverage`. It does not copy `subject` or prices. Classes other than `L3_LEVEL_TOUCH_*`, `L3_DISTANCE_TOUCH_*` and `L3_NEITHER_*` are ignored. Level and distance touches share the touch book.

The census role cannot `SELECT` `beta_claims` or `beta_claim_outcomes`. The export does not grant it anything. `scripts/beta/export_calibration_journal_v2.sh` runs `scripts/beta/export_calibration_journal_v2.sql` through the existing Docker PostgreSQL as the table owner already configured for that container, with `default_transaction_read_only`. The SQL is one `SELECT`. It whitelists fields, keeps coverage, `eval_rule_id`, `eval_rule_digest` and the latest `outcome_revision`, and does not select subject or price keys. `scripts/beta/replay_calibration_monitor_v2.py` reads that JSONL. It does not open a database and does not read `BETA_DSN`. It refuses a file that still contains subject, price, high, low, close, or credential fields.

## Owner notices

`shadow_notifications` emits `STATE_CHANGED` when a book enters or leaves suspected, confirmed, recovered, fault, or incomplete. A book that stays confirmed does not emit again. A daily summary lists those books at most once per UTC day. Transitions that stay inside insufficient/noise are not paged. V1's 30-minute repeat and the sticky `touch_live_cal` flags are a different component and are not modified.

## User action

The function returns an action. It does not render Telegram text.

| State | Action |
|---|---|
| Insufficient, noise, suspected, recovered | `NO_V2_OVERRIDE`. V1 wording stays. |
| Confirmed | `WITHHOLD_MODEL_PROBABILITY`. The model number is not shown. A softer sentence around the same number is not a substitute. A historical baseline may be shown only as a separate figure the caller already has. The monitor does not blend the model toward the live rate. |
| Fault, incomplete | `WITHHOLD_FIGURE`. No model number and no baseline. |

## What was checked

Surface: one Gaussian path per seed. A claim at hour `t` with horizon `H` is settled by the sum of the next `H` increments. The null probability is the exact Gaussian tail or central probability of that sum, so 1h, 4h and 24h claims share the path and each is calibrated at issue time. This is a terminal barrier, not a path-maximum touch. It is not the Binance archive and not October 2026.

Null, 36 paths, 80 days, all six books:

- Any book ever confirmed: 1/36 (neither 4h, e-value at the crossing 61.6, just over 60). Point rate 2.8%. One-sided Clopper-Pearson 95% upper bound 12.5%. The Ville union bound is 10%. With one event in 36 paths the simulation is too small to pin the rate under 10% by itself; 1/36 sits inside that bound and was not used to move `E_CONFIRM`.
- The same 4h touch level residual, anchor hours only: 0/36 level-only confirmations, maximum book-equivalent e-value 24.9 (median 1.24).
- The same residual updated every hour, in issue order: 4/36 level-only confirmations, maximum book-equivalent e-value about 3.8×10^8 (median 24.2). That is the overlapping filtration the daily index was using.
- Kept 4h slots: 480 on every path, which is 80 days × 6 anchors.

V1 on the same generator, 8 paths, 48 windows of 7 days: V1 diverged on 27/48 (0.5625). V2 called every one of those windows `INSUFFICIENT_DATA`.

Power, 3 paths, predeclared shifts, 70 days (recovery run 90 days). Not the October residuals.

- Touch stated 10 pp below the true probability: touch 1h and 4h confirmed, with `LEVEL` and both tails named and `SHAPE` left in noise. Neither stayed in noise. Touch 24h confirmed on 0/3 paths and was suspected on 1/3.
- Tails shifted by 12 pp, and the shape stretch: `LEVEL` stayed in noise (4h level estimates about +0.01 to +0.04) while `TAIL_HIGH`, `TAIL_LOW` and `SHAPE` confirmed on 1h and 4h. Touch 24h was suspected on 1/3 paths and confirmed on none.
- Neither shifted by 10 pp, touch left calibrated: neither 1h and 4h confirmed; every touch book stayed in noise.
- 36 days of a 10 pp touch shift, then a null path: touch 1h and 4h ended `RECOVERED` on 3/3 paths. The episode remains.

Unit tests cover the anchor chain, a claim issued before the previous anchor resolves, partial-coverage hits, the journal adapter, and the once-per-day shadow notice (`tests/beta/test_calibration_monitor.py`). `tests/beta/test_calibration_journal_export.py` checks the export columns against `storage/beta_v0_schema.sql` and, on PostgreSQL, runs SQL → JSONL → adapter → `evaluate`, including a second outcome revision and a read-only session.

## Safe switch

1. This tree does not call the monitor from `beta/health.py` or the notifier. Deploying the module alone does not change alerts or wording.
2. A later shadow recorder may write health component `touch_cal_monitor_v2` from the same journal. It must not update `touch_live_cal` and must not clear V1 flags. Shadow notices are state changes plus one daily summary, not the 1800-second V1 repeat.
3. User text changes only after a separate owner permission, and only through `user_action`.
4. V1 stays armed until that permission. The two monitors can disagree; V1 remains the one users feel. This change does not clear the October sticky alerts.

## Residual risks

- The 10% bound is the guarantee only under the conditions in "When the 10% bound applies". The 36-path simulation does not have the precision to show the joint rate is under 10%: the 95% upper bound on 1/36 is 12.5%. A different path dependence could still expose a filtration mistake the Gaussian terminal barrier does not.
- If missing minutes depend on the price path, the scored subset can be biased and the 10% bound does not apply. The 20% gate only refuses a large hole. It does not repair a smaller one.
- Twenty-four hour books have one anchor per day. A 10 pp shift was not confirmed in 70 days. That is low power, not a reason to lower the threshold.
- Empty channels stay at 1 and dilute the mixture. A failure that lives in one channel has to overcome that dilution. The tail and shape checks still confirmed on 1h and 4h.
- A `COMPLETE` row with no coverage field is scored. Production stores coverage. An export that drops the field would undo the censoring rule. The export SQL keeps the field.
- Recovery can close on a quiet 20-day slice while an older bias is only archived.
- October's 7 days stay `INSUFFICIENT_DATA` however large the gap. That is the information floor, not a verdict that those probabilities were right.
- The live journal has not been replayed. Shadow mode is the replay of an anonymized export, not a verdict already computed on production. The census role still cannot read the claim tables. The export below uses the existing container's table owner and does not change that grant.

## What the owner runs

Do not restart services, do not clear `touch_live_cal`, do not edit user text, do not grant the census role, and do not point health or the notifier at this module.

One command, on the VPS, as the user that already runs the bot. It fetches the verified export commit `1c82e638211f0c889891c830d8bde8ee4e88741e` and extracts those two files. A later move of the branch does not change which files run. It does not check out `/opt/signalbot`. The session inside the existing container is read-only. The query uses the table owner already configured there, because the census role cannot `SELECT` these tables.

```bash
bash -c "$(cat <<'BLOCK'
set -euo pipefail
exec </dev/null
cd /opt/signalbot
WORK=$(mktemp -d /tmp/calmon.XXXXXXXX)
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
EXPORT_SHA=1c82e638211f0c889891c830d8bde8ee4e88741e
git -C /opt/signalbot fetch -q origin "$EXPORT_SHA" \
  || git -C /opt/signalbot fetch -q origin cursor/calibration-monitor-v2-shadow-08d8
git -C /opt/signalbot cat-file -e "${EXPORT_SHA}^{commit}" \
  || { echo "export sha $EXPORT_SHA is not available"; exit 1; }
echo "scripts from ${EXPORT_SHA:0:12}"
git -C /opt/signalbot archive "$EXPORT_SHA" \
    scripts/beta/export_calibration_journal_v2.sql \
    scripts/beta/export_calibration_journal_v2.sh | tar -x -C "$WORK"
bash "$WORK/scripts/beta/export_calibration_journal_v2.sh" /tmp/calibration_monitor_v2.jsonl
BLOCK
)"
```

What to send back: the file `/tmp/calibration_monitor_v2.jsonl` (mode 0600) and the printed `rows=… sha256=… path=…` line from the same run, plus the `container`, `db`, `user` and commit lines. That file is the anonymized journal: claim class, timestamps, probability, stats digest, evaluation rule, outcome status, outcome revision, and `touched` / `neither` / `coverage`. It has no subject, no prices, and no user data. Do not send `/opt/signalbot/.env`, a database dump, or any other query.

The diagnosis is `python3 scripts/beta/replay_calibration_monitor_v2.py` on that file, off the VPS. Do not run the monitor inside health or the notifier to produce it.

If the script stops because a line contains a forbidden key, send that error line and do not send the file.

A later recorder, if one is added, writes only `touch_cal_monitor_v2` and pages through `shadow_notifications`.
