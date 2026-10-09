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

**Between 3a and 3b:** OUT-8 block B (`docs/BETA_AUDIT_DEIDENTIFY_V1.md`, merged with #422 as `db381de9`; the blocks fetch the scripts pinned to that commit) only after the owner's go: it needs the 3a schema and must run before 3b.

**Step 3b, planned:** main `3b094688` (3a + #422 scripts + #423 keyed HMAC pseudonyms) + the Day-0 config commit (`level_race.journal_enabled = true`, `display_enabled = true`, `push_trigger = structural`), deployed at 00:00 UTC. Order: `BETA_FINGERPRINT_KEY` into `/opt/signalbot/.env` (a copy kept off the server, never in dumps) → checkout → install units → beta restart → collector restart; the bot refuses to start without the key. The 7-day observation starts at 3b. Its own RC record follows.

**Pre-3b items:**
1. OKX volume scale (`ctVal`) checked against an independent reference.
2. The old rows (pre-D1 Bybit sides, the empty OKX history) checked on the screens through D2's read-time correction.
3. Block B run (or explicitly skipped) by the owner.

### Step 3b — keyed pseudonyms and the Day-0 flags, commit `b833f7c6cbef843dfde35f83d6ea3ffd592b67e2`

| Field | Value |
|---|---|
| Step / date | 3b, cut 2026-10-08 23:29Z (main after #428). Deployed only after 3a is deployed and verified, block B done or skipped, and the pre-3b checks C1/C2 closed; deploy at **00:00 UTC**. |
| Exact commit | `b833f7c6cbef843dfde35f83d6ea3ffd592b67e2` |
| Contents since 3a (`fe8ac969`) | #422 (OUT-8 de-identification scripts and doc, prepare-only), #423 (keyed HMAC-SHA-256 pseudonyms; deletion de-identifies keyed and legacy audit rows), #427 (block A/B pinned to `db381de9`), #428 (Day-0 flags). |
| Migrations (beta / Stage-1) and restart order | No new schema. **Before anything:** `BETA_FINGERPRINT_KEY` (`openssl rand -hex 32`) into `/opt/signalbot/.env`, a copy in the owner's password manager, never in dumps or chats. Then checkout the SHA → `install_beta_units.sh` → restart `signalbot-beta-bot` → `sudo systemctl restart signalbot.service`. The bot, the notifier and every `--beta-*` command refuse to start without a valid key (CONFIG_ERROR, exit 2). Checks: `--beta-health` OK; `/admin_health` test state `NOT_OPEN`; a level touch, if one happens, reads «вошла в зону …» with the T0 race line; `/levels` shows the T15 line. |
| Flags and values | `level_race.journal_enabled = true`, `display_enabled = true`, `push_trigger = structural`; `model_states_enabled = false`. Unchanged: `access.tiers_enforced = false`, `access.u3_offer` empty, `briefing.withdrawal.day0_kyiv` null. |
| Release-candidate suite on this SHA | Actions run 37859774589 (ci.yml, suite=rc, on this exact SHA): **success**, 2026-10-08 23:30–23:38Z. |
| Known limitations | Old audit fingerprints (unkeyed) no longer match new ones; `/admin_reply` works only with fingerprints printed after 3b. The SQL audit guard checks the legacy form only; the keyed form is checked in Python before de-identification. The legacy level-touch trigger is the fallback (contract §12.1). |
| Rollback | Checkout `fe8ac969` (3a), reinstall units, restart beta then collector; the key may stay in `.env` (3a ignores it). The flags go off with the rollback; the claim journal keeps its rows. Rolling back after the start is a dated event. |
| Kind of change for the 7-day count | **Starts the count**: the deploy that turns on every Day-0 flag (`ORCHESTRATION_V1` §4a). Any later collector, schema, push-gating, metric-definition or journal change, or a flag turned on, restarts it. The #403 `L3_LEVEL_TOUCH_24H` cohort boundary is dated by this deploy (contract §12.3). |
| ОПГ-2: forecast layer | ОПГ-2's 3a sign-off covers 3b: only `journal_enabled`, `display_enabled` and `push_trigger = structural` turn on; `model_states_enabled` stays false; the HIST table V1 file must be in the deployed tree (a digest mismatch loads OFF); the #419 model freeze is not needed. ОПГ-2 confirmed 3b (2026-10-09 00:44Z): flags verified in `config/beta_v0.yaml`; `LR.mode` stays HIST and the HIST table digest is verified (test in #428); #422/#423/#427 touch no level_race code; the layer ships HIST only (L2, 2020–2024, prices only), with no model and no 2025/26 race outcomes. Nothing blocks 3b. |

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
