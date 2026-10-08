# Beta release log V1 — release candidates (ОПГ-1)

Owner: ОПГ-1 mini-head. Rules: `docs/ORCHESTRATION_V1.md` §4a (release candidate before every deploy step; reset rules of the 7-day observation).

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

## 2. Misses

The log of defects found after merge lives in `docs/ops/OPG1_ESCAPED_DEFECTS.md` (architect, 2026-10-08).
