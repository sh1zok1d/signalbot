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
