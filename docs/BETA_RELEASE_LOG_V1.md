# Beta release log V1 — release candidates and post-merge misses (ОПГ-1)

Owner: ОПГ-1 mini-head. Rules: `docs/ORCHESTRATION_V1.md` §4a (release candidate before every deploy step; reset rules of the 7-day observation) and the owner's rule of 2026-10-08 on a short log of defects found after merge.

## 1. Release candidates

One record per deploy step, written before the deploy block goes to the owner. ОПГ-2 adds a line on the forecast layer («не затронут» is enough).

Template:

| Field | Value |
|---|---|
| Step / date | |
| Exact commit | |
| Migrations (beta / Stage-1) and restart order | |
| Flags and values | |
| Release-candidate suite on this SHA (tests/beta, tests/deploy, tests/data_ingestion, storage, Stage-2 on PostgreSQL, guard tests incl. research/product boundary) | |
| Known limitations | |
| Rollback | |
| Kind of change for the 7-day count (resets / does not reset) | |
| ОПГ-2: forecast layer | |

### Step 1 — D1 + D2 (data reliability), commit `b004669`

Handed to the owner by the architect on 2026-10-08 before §4a; no retroactive record. Order: beta first (checkout, `install_beta_units.sh`, restart `signalbot-beta-bot`), then `sudo systemctl restart signalbot.service`; checks: OKX subscribe in the journal, after 2–4 h `mapping_version = 2` rows for okx and bybit and the mark-price side check. Includes #373 and #375 before their review fixes (acceptable only while every participant is on Kyiv time). Not part of the 7-day count.

**Deployed** by the owner on 2026-10-08 (report 2026-10-09 00:28 Kyiv):
- `b004669` on a clean tree, after a local backup `btcbot_20261008T145511Z.sql.gz` (159 MB);
- units installed, bot restarted, `--beta-health` OK with `alerts=[]`;
- collector restarted 2026-10-08 14:59:21Z; startup recovery READY; OKX acknowledged the liquidation-orders subscription on the public WS.

Side check at 21:28Z, rows after the restart only (all `mapping_version = 2`, no missing mark price):

| Venue | Rows | Long below mark | Short above mark |
|---|---|---|---|
| Binance (control) | 811 | 516/561 (92.0 %) | 208/250 (83.2 %) |
| Bybit | 2178 | 2028/2028 | 150/150 |
| OKX | 623 | 386/430 (89.8 %) | 175/193 (90.7 %) |

Bybit sides are now correct (inverted before D1), and OKX rows exist (none before D1). OKX's shares are in the range of the Binance control.

**Open checks, not covered by these queries:**
1. The OKX volume scale (`ctVal`): notional per row against an independent reference.
2. How the product treats the old rows (pre-D1 Bybit and the empty OKX history) through D2's read-time correction on the screens.

### Step 3a — everything since step 1 except the keyed fingerprints, commit `fe8ac969aa49b6ab60e7a501e60f9ddcdf5081ac`

| Field | Value |
|---|---|
| Step / date | 3a, cut 2026-10-08 22:48Z (main after #413). Followed by OUT-8 block B (owner's go only), then step 3b. |
| Exact commit | `fe8ac969aa49b6ab60e7a501e60f9ddcdf5081ac` |
| Contents since step 1 (`b004669`) | #379 (multi-zone push budget, quiet hours, U2 fixes); #383/#385/#387/#388/#389/#393/#408/#409 (ОПГ-2 level race: HIST journal and lines, the structural trigger behind a flag, calibrator design, model inputs); #386 (build SHA); #398 (OKX liquidation liveness); #402/#403 (alert corridor and next-level records); #404/#405/#416/#417 (feedback, onboarding, interviews removed, offer recipients, privacy v8, owner sticker replies); #410/#412/#413 (D3 honest labels: OI, change checks, partial volume, funding); #411/#414/#418/#420/#424 (measurement contract amendments, first-cohort plan V2, Day 0 via `/admin_test_open`, deletion counters with the de-identification exception, payment terms); docs and CI PRs. Not included: #422 (prepare-only scripts), #423 (keyed fingerprints, step 3b). |
| Migrations (beta / Stage-1) and restart order | Stage-1 `storage/schema.sql`: new `liquidation_feed_heartbeats`, created by the collector at start. Beta `storage/beta_v0_schema.sql`, applied idempotently at bot / notifier start: new columns (feedback kind, awaiting, tier, onboarded_at), `beta_reasons`, `beta_owner_forwards`, `beta_deleted_cohort_counts`, the `beta_audit_guard` trigger on `beta_admin_audit`, widened CHECKs. The beta reads the heartbeats behind a `to_regclass` guard, so beta-before-collector is safe (OKX reads «не измерен» until the collector restarts). Order: backup → checkout the SHA → `install_beta_units.sh` (writes `BUILD_SHA`) → restart `signalbot-beta-bot` → `sudo systemctl restart signalbot.service`. Checks: `--beta-health` OK, an OKX heartbeat row within a minute, `/admin_health` test state `NOT_OPEN`. |
| Flags and values | No flag change: `level_race.journal_enabled/display_enabled = false`, `push_trigger = legacy`, `access.tiers_enforced = false`, `access.u3_offer` empty. |
| Release-candidate suite on this SHA | Actions run 37855733150 (ci.yml, suite=rc, `scripts/ci/rc_suite.txt`, on this exact SHA): **success**, 2026-10-08 22:48–23:00Z. |
| Known limitations | Before 3b, the fingerprints are still the unkeyed legacy form. OKX volume scale (`ctVal`) not yet checked against a reference. |
| Rollback | Checkout `b004669`, reinstall units, restart beta then collector. The schema changes are additive; the old code ignores the new tables and columns. The audit guard stays (it only refuses mutations). |
| Kind of change for the 7-day count | Pre-start: schema, collector and journal changes, no Day-0 flag. The count has not started. |
| ОПГ-2: forecast layer | Signed off by ОПГ-2 (2026-10-08 22:49Z). 3a ships the level race HIST layer (#381 table V1 file plus digest #385, one detector #383, L2 journal and HIST display #387/#388, the structural trigger #393) and the inert calibration/state module and C1 inputs (#408, #409). Every `level_race` flag is off at 3a. For 3b: no new schema (the existing claim journal is used); the HIST table V1 file must be in the deployed tree (a digest mismatch loads OFF, never a wrong number); 3b turns on only `journal_enabled`, `display_enabled` and `push_trigger = structural`, while `model_states_enabled` stays false; the #419 model freeze is not needed for 3b. Model states arrive later as the predeclared dated upgrade (FORECAST_LAYER §6a). Standing disclosure, from the model states on: «a level-specific drift of about ±10 pp is detected in about a year, not weeks; inside the beta the accuracy line next to the number is the guard». |

**Deployed** by the owner on 2026-10-09 (report ~06:55Z, relayed by the architect):
- HEAD and `BUILD_SHA` `fe8ac969`, after a local backup `btcbot_20261009T064542Z.sql.gz` (161 MB; pg_dump warned about TimescaleDB circular foreign keys; restore not tested);
- bot restarted 06:47:08Z, collector 06:47:19Z;
- `--beta-health` OK with `alerts=[]`; `/admin_health` `alerts=[]`, test `NOT_OPEN`, Day 0 None; OKX heartbeat age 34.7 s;
- #368 status `ACCRUING` since 2026-10-09T00:00Z: 415/415 minutes, 0 missing, no gap from the restart.

Pre-3b checks (`docs/BETA_PRE3B_DATA_CHECKS.md`, #429), first run:

| Line | Result |
|---|---|
| `C1a_notional_identity`, `C1a_okx_scale`, `C1b_ctval` (= 0.01) | PASS |
| `C1b_match` | FAIL: 82 matched, 51 equal. Architect's diagnosis: an artifact of the ±1 s / same-price rule (the WS channel is a subset, so a REST-only order at the same `bkPx` within 1 s pairs with a WS row). The collector stores OKX's own `ts`, so the check moves to the exact ms plus price, compared as (count, sum) per key; reproduced locally as FAIL under the old rule and PASS under the exact rule. Not yet re-run on production. |
| `C2_rows_swapped`, `C2_tape_swapped` (288 buckets), `C2_okx_not_measured` (None in all 288), `C2_mark_side` (99.9 %, N=1586 pre-D1; 100 % post-D1) | PASS |
| `C2_okx_no_rows`, `C2_window_old_only` | FAIL: 6 OKX rows in the window; the first OKX row is at 2026-10-08 14:04:48.875Z, before the documented 14:59Z D1 restart. Unexplained; a read-only diagnosis is with the owner (first OKX rows, collector starts 13:00–15:30Z, reflog, C1b on the exact ms). |

Diagnosis and block B (owner, 07:23Z):
- **C1 closed.** Re-run on the exact ms plus price: 51 keys, 50 equal. The one difference is a count, not a scale: at 04:01:48.625Z, px 82455.2, REST holds two orders (0.09 and 2.94 contracts) and the database one row, qty 0.0294 = 2.94 × 0.01, which fits the documented WS subset. Every stored row equals a REST order at the same ms and price. The check's rule becomes stored ⊆ REST (multiset).
- **C2.** All 6 early OKX rows carry `mapping_version = 2`, and the journal shows each processed after the 14:59:21Z restart (event 14:04:48 → logged 15:01:26; event 14:20:36 → logged 15:31:34; delays of 57–71 min). OKX liquidation events can reach the collector up to about an hour late. The rest of C2 passed. Open: per-venue arrival delay (owner's read-only block) and its impact on tape materialization, which is to be decided before 3b because a later change to a metric definition restarts the 7-day count.
- **OUT-8 block B: COMPLETE.** Backup `btcbot_20261009T071954Z` uploaded off the server; SQL from `db381de9`; `UPDATE 0/2/0`, i.e. exactly 2 `admin_reply` rows de-identified; the trigger back to enabled (`O`); deletion counter unchanged.

**Between 3a and 3b:** OUT-8 block B (`docs/BETA_AUDIT_DEIDENTIFY_V1.md`, merged with #422 as `db381de9`; the blocks fetch the scripts pinned to that commit) only after the owner's go: it needs the 3a schema and must run before 3b.

**Step 3b:** see the record below (`bd35820b`, re-cut 2026-10-09).

**Pre-3b items:**
1. OKX volume scale (`ctVal`) checked against an independent reference: **closed** (scale confirmed on the exact-ms rule).
2. The old rows (pre-D1 Bybit sides, the empty OKX history) checked through D2's read-time correction: Bybit and OKX tape PASS; the early OKX rows are late arrivals. **Open:** the OKX late-arrival delay and its tape impact (decision before 3b).
3. Block B run (or explicitly skipped) by the owner: **closed** (run, 2026-10-09 07:23Z).

### Step 3b — keyed pseudonyms, the Day-0 flags and OKX liquidations excluded, commit `bd35820bd89310b7e5db57b1afe5356bd79184f3`

Re-cut on 2026-10-09 after the pre-3b checks; the earlier cut `b833f7c6` (RC run 37859774589, success, 2026-10-08 23:30–23:38Z) is superseded and was never deployed.

| Field | Value |
|---|---|
| Step / date | 3b, cut 2026-10-09 08:20Z (main after #434). 3a is deployed and verified, block B is done, C1 is closed and C2 is resolved by #434; deploy at **00:00 UTC**. |
| Exact commit | `bd35820bd89310b7e5db57b1afe5356bd79184f3` |
| Contents since 3a (`fe8ac969`) | #422 (OUT-8 de-identification scripts and doc, prepare-only), #423 (keyed HMAC-SHA-256 pseudonyms; deletion de-identifies keyed and legacy audit rows), #427 (block A/B pinned to `db381de9`), #428 (Day-0 flags), #419 (LEVEL_RACE_MODEL_V1 freeze and the model code, inert while `model_states_enabled = false`), #429/#433 (pre-3b checks and the OKX late-arrival note, docs only), #434 (`liquidations.okx_enabled: false`: OKX liquidations never shown and never vote, decision (d), owner-confirmed 2026-10-09). |
| Migrations (beta / Stage-1) and restart order | No new schema. **Before anything:** `BETA_FINGERPRINT_KEY` (`openssl rand -hex 32`) into `/opt/signalbot/.env`, a copy in the owner's password manager, never in dumps or chats. Then checkout the SHA → `install_beta_units.sh` → restart `signalbot-beta-bot` → `sudo systemctl restart signalbot.service`. The bot, the notifier and every `--beta-*` command refuse to start without a valid key (CONFIG_ERROR, exit 2). Checks: `--beta-health` OK; `/admin_health` test state `NOT_OPEN`; a level touch, if one happens, reads «вошла в зону …» with the T0 race line; `/levels` shows the T15 line. |
| Flags and values | `level_race.journal_enabled = true`, `display_enabled = true`, `push_trigger = structural`; `model_states_enabled = false`; `liquidations.okx_enabled = false`. Unchanged: `access.tiers_enforced = false`, `access.u3_offer` empty, `briefing.withdrawal.day0_kyiv` null. |
| Release-candidate suite on this SHA | ci.yml, suite=rc, on this exact SHA: dispatched 2026-10-09 ~08:21Z, **result pending**. |
| Known limitations | Old audit fingerprints (unkeyed) no longer match new ones; `/admin_reply` works only with fingerprints printed after 3b. The SQL audit guard checks the legacy form only; the keyed form is checked in Python before de-identification. The legacy level-touch trigger is the fallback (contract §12.1). OKX liquidations are excluded for the whole beta (events arrive up to ~5 h late, `docs/BETA_OKX_LATE_ARRIVAL_IMPACT.md`); `LIQUIDATION_STRESS` therefore needs both Binance and Bybit eligible (`min_eligible_venues: 2`): if either is dead or immature the rule is NOT_EVALUABLE for that bucket (no episode, no push). Enabling OKX later needs a new rules version. Collector, schema and Stage-2 still store OKX rows. After the beta: a `received_at` column plus a lateness monitor. |
| Rollback | Checkout `fe8ac969` (3a), reinstall units, restart beta then collector; the key may stay in `.env` (3a ignores it). The flags go off with the rollback; the claim journal keeps its rows. Rolling back after the start is a dated event. |
| Kind of change for the 7-day count | **Starts the count**: the deploy that turns on every Day-0 flag (`ORCHESTRATION_V1` §4a). Any later collector, schema, push-gating, metric-definition or journal change, or a flag turned on, restarts it. The #403 `L3_LEVEL_TOUCH_24H` cohort boundary is dated by this deploy (contract §12.3). |
| ОПГ-2: forecast layer | ОПГ-2's 3a sign-off covers 3b: only `journal_enabled`, `display_enabled` and `push_trigger = structural` turn on; `model_states_enabled` stays false; the HIST table V1 file must be in the deployed tree (a digest mismatch loads OFF); the #419 model freeze is not needed. ОПГ-2 confirmed 3b (2026-10-09 00:44Z): flags verified in `config/beta_v0.yaml`; `LR.mode` stays HIST and the HIST table digest is verified (test in #428); #422/#423/#427 touch no level_race code; the layer ships HIST only (L2, 2020–2024, prices only), with no model and no 2025/26 race outcomes. Nothing blocks 3b. **Re-cut `bd35820b`: ОПГ-2's line pending** (#419 inert; #434 against the level race layer). |

## 2. Misses — defects found after merge

| PR | What was missed | Found by | Check that should have caught it |
|---|---|---|---|
| #343 | 7 honesty defects (bare difference without interval, glossary interval rule, analog estimand key, rounding, /feedback after /stop, R03-C1 qualifier) | external review after merge | pre-merge honesty review of every user text change |
| #345 | owner weekly copy re-sent on an ambiguous send; feed readiness missed the new column | external review after merge | pre-merge review of delivery/monitoring changes |
| #346 / #348 | research per level vanished from the tab; stale statistics still fed the push analogue; price alerts broken under STATS_STALE; fallback chance without N; /btc silent when stale | external review after merge | pre-merge review of screens against PRE_BETA §6.1 and A2 |
| #373 | shared push budget across time zones; `/tz` regex range; weekly in recipients' quiet hours; mute counted as a U2 reaction; zone label used today's offset | external review after merge | pre-merge review of push/U2 changes with multi-zone scenarios |
| #374 (D1) | deploy-unsafe without D2 (OKX zeros history → false votes); PR description claimed screens unchanged until D2 | external review after merge | review of the beta's reading of new collector data before a collector PR merges |
| #375 | F4 flag only per subgroup; weekly copy without `as_setting`; mute as reaction in the owner breakdown; move-alert corridor worded as a forecast without accuracy; latency «обычно» gate passed on one broadcast | external review after merge (merged before the rule «risky PRs reviewed before merge») | pre-merge review of push PRs |
| #381 (ОПГ-2) | main red: `tests/beta/test_level_race.py` imports `scripts.research` (guard test `test_beta_modules_do_not_import_scripts_research`) | track A's run on main | the release-candidate suite incl. guard tests before merge |
