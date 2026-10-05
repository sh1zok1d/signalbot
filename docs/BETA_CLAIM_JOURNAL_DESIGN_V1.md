# Beta prospective claim journal — design V1

**Status:** `IMPLEMENTED_IN_CODE (BETA_CLAIMS_V1; not deployed)` — the owner go is `PRE_BETA_SCOPE_DECISION_V1.md` §1 and §6.2 (full journal, first in order, with a DH3-P1 class). §7 records what was built and where it differs from §3–§6.
**Date:** 2026-10-05
**Authority:** `research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` §5. It adds no product scope. The implementation unit in §6 needs a separate owner go (given: see the status line).

## 1. Purpose

The journal records every L1 / L2 / L3 claim the bot was **entitled** to make, at the moment it was entitled to make it, with the exact numbers, versions and evaluation rule. Later outcomes are linked to each record. Two questions are then answered on live data, by claim class:

- did the historical tendency hold forward against its baseline?
- for L3, is the stated probability calibrated?

The journal is what makes L3 possible, and it is where L2 claims get their prospective record.

## 2. What already exists (reused, not rebuilt)

| Existing | What it gives | Gap for the journal |
|---|---|---|
| `beta_context_snapshots` | append-only context state per 5m bucket, with context, rules and episodization digests and `recorded_at` | none: the claim links to it |
| `beta_hist_stats` | versioned historical statistics (`version`, `data_through`, `payload_digest`) behind analogues, level reactions, corridors and touch chances | none: the claim links to `stats_pk` and copies the numbers it used |
| `beta_btc_views` | append-only record of what a `/btc`, `/catchup` or briefing view showed, with payload and rendered digests | only covers shown views, at user-chosen times (selection) |
| `beta_market_alerts` | every alert decision, `PUSH` and `SUPPRESSED`, with payload | event-driven only; no evaluation rule |
| `beta_episode_outcomes` | append-only, revisioned outcomes 15m–24h per detector episode | keyed by episode, not by claim |
| `beta_forecasts` + `record_forecasts` / `score_forecasts` | hourly corridor forecasts issued **regardless of users**, scored later | the closest precedent. Its outcome is written by `UPDATE` (not append-only), it has no claim level or evaluation-rule version, and it covers corridors only |
| `build_decision()` (`beta/decision.py`) | the single live decision block every surface renders from | the natural single source of claims |

Conclusion: no new telemetry system is needed. Two append-only tables, a link table and one writer and one scorer modelled on `record_forecasts` / `score_forecasts` are enough.

## 3. The minimal claim record

### `beta_claims` (append-only, mutation-rejecting trigger like `beta_context_snapshots`)

| Column | Content |
|---|---|
| `claim_pk` | id |
| `claim_class` | closed list per template, e.g. `L2_STATE_ANALOG_4H_UP`, `L2_LEVEL_FIRST_TOUCH_HOLD_4H`, `L3_LEVEL_TOUCH_4H`, `L1_WEEKEND_CALM` |
| `level` | `L1` / `L2` / `L3` (L0 is not journaled: the snapshot is the record) |
| `issued_at`, `as_of_bucket` | write time; the 5m bucket the claim is computed from |
| `context_pk` | the `beta_context_snapshots` row of `as_of_bucket` (null only if the claim does not use context) |
| `stats_pk`, `stats_digest` | the `beta_hist_stats` row and payload digest the numbers came from |
| `subject` | JSONB: what the claim is about: state label and horizon, level price and kind, target and side |
| `numbers` | JSONB, **exactly as the template would print them**: `observed`, `baseline`, `diff_pp`, `n`, `interval` (if available), `stability` (if available), `probability` (L3 only) |
| `rule_version` | state definition or model version (`BETA_CONTEXT_1H_V2`, `rangecast` version, `levels` version) |
| `template_id`, `template_digest` | wording template id and digest of its RU / EN text |
| `eval_rule_id`, `eval_rule` | JSONB evaluation rule, **frozen at write**, plus its digest (`eval_rule_digest`): outcome definition, price source, horizon end, settle delay, NO_DATA rule, cohort metric |
| `horizon_end` | when the outcome is due |
| `eligible_reason` | why the claim was eligible: N ≥ the template's minimum, data fresh, not inside an event zone |
| `claim_digest` | sha256 over every field above |
| `recorded_at` | default `now()` |

Unique key: `(claim_class, subject_key, issue_slot)`. The writer is idempotent within an hour, as forecasts are today.

### `beta_claim_outcomes` (append-only, revisioned like `beta_episode_outcomes`)

`claim_pk`, `eval_rule_digest` (must equal the claim's), `revision`, `supersedes_outcome_id`, `status` (`COMPLETE` / `INCOMPLETE_DATA` / `NO_DATA`), `realized` JSONB (for example `close_change_pct`, `went_up`, `touched`, `high`, `low`), `computed_at`, `outcome_digest`. A correction is a new revision with a note, never an `UPDATE`.

### `beta_claim_displays` (append-only link, no user id)

`claim_pk`, `surface` (`btc` / `catchup` / `brief` / `alert` / `levels` / `risk`), `view_pk` or `alert_pk`, `shown_at`. This is how "shown" and "not shown" stay separable without making display the sampling rule.

## 4. Required properties and how they are met

- **Append-only.** Mutation-rejecting triggers on all three tables, as on the existing append-only beta tables.
- **Versioned.** `rule_version`, `template_digest`, `stats_digest` and `eval_rule_digest` are on every row. A change of any of them starts a new cohort, never a mix.
- **Every eligible state is logged, not only shown ones.** The writer runs on a **fixed grid independent of users**:
  - every hour for state-conditioned and level claims, inside `--beta-notify-once` like `record_forecasts`;
  - at every alert **evaluation** (`PUSH` or `SUPPRESSED`) for event-driven claims.

  Whether anyone saw the claim is recorded separately in `beta_claim_displays`.
- **Evaluation rule fixed at write.** The scorer reads the rule from the claim row and refuses an outcome whose `eval_rule_digest` differs. No outcome field exists at write time.
- **Same rule for the whole group.** Scoring is per cohort (`claim_class`, `rule_version`, `template_digest`, `eval_rule_digest`):
  - **L2:** live frequency in the state cohort minus the live frequency in its baseline cohort, compared with the claimed historical difference; log or Brier score of "historical frequency" against "baseline frequency" as the forecast;
  - **L3:** reliability by probability bin and Brier skill against the baseline rate;
  - **L1:** whether the stated gap persists in live data.

  Day-clustered intervals throughout. No per-claim "right / wrong" is ever shown to users.

## 5. What to expect, honestly

Hourly claims with 4h–24h horizons overlap heavily.
- **24h claims:** a month gives about 30 effective outcomes per class.
- **4h claims:** about 180 effective outcomes per class in a month (6 non-overlapping per day).
- **Rare states:** a handful.

So:
- **Month 1:** the pipeline works and eligibility rates are sane.
- **3–6 months:** the first L2 / L3 calibration for frequent classes.
- **Rare classes:** years. The journal starts that clock honestly; it does not remove the N problem.

L3 wording for a class is permitted only after the class reaches the count its design note fixes (`EVIDENCE_AND_CLAIMS_DECISION_V1.md` §5).

## 6. Implementation unit (for later; not done here)

**`BETA_CLAIM_JOURNAL_V1_IMPL`.** Needs an owner go under `PRODUCT_DECISION_V2`. The earlier instruction not to start new telemetry stands until then.

- **Schema:** the three tables plus triggers in `storage/beta_v0_schema.sql`.
- **Store methods:** insert, idempotency check, matured claims, insert outcome revision, cohort fetch.
- **Writer:** `beta/claims.py::record_claims(conn, block, now)`, called beside `record_forecasts`, with one extractor per template.
- **Scorer:** `score_claims`, beside `score_forecasts`, on the same 1m bars.
- **Report CLI:** `--beta-claims-report` (read-only, per-cohort tables).
- **Tests:**
  - the append-only triggers;
  - claims written with zero users and with the bot paused;
  - the rendered text equals the template filled with `numbers` (no drift between what is logged and what is shown);
  - no outcome is read at write time;
  - a rule-digest mismatch is refused;
  - an event-zone horizon produces no claim.
- **First classes:**
  - `L2_STATE_ANALOG_{1H,4H,24H}`;
  - `L2_LEVEL_FIRST_TOUCH_HOLD_4H`;
  - `L3_LEVEL_TOUCH_{4H,24H}` (today's «дойти» numbers, to start their live calibration);
  - `L1_WEEKEND_CALM` only if that line becomes live.
- **Not in scope:** corridors stay in `beta_forecasts` unchanged. Migrating them into the journal is a separate decision.

## 7. Implementation record (2026-10-05, `BETA_CLAIMS_V1`)

**Code.**
- Schema: `beta_claims`, `beta_claim_outcomes`, `beta_claim_displays` in `storage/beta_v0_schema.sql`. All three are append-only. A `BEFORE INSERT` guard refuses an outcome whose `eval_rule_digest` differs from its claim's.
- Writer, scorer, display links and the pure report: `beta/claims.py`.
- Store methods: `storage/beta_v0_store.py`.
- Hooks inside `beta/market_alerts.py::run_market_alerts`, behind `decision.claim_journal` in `config/beta_v0.yaml`:
  - the hourly writer and the scorer run beside `record_forecasts` / `score_forecasts`;
  - the level-touch writer runs after each evaluated candidate.
- Display links: the bot (`/catchup`, `/levels`, the `/risk` table) and the briefing (`beta/delivery.py`).
- Report: `--beta-claims-report [--claims-days N]`. It is read-only and prints per-cohort JSON.
- Tests: `tests/beta/test_beta_claims.py` (pure) and `tests/beta/test_beta_claims_pg.py` (PostgreSQL).

**Classes as built.**

| Class | When | Subject key | Rule |
|---|---|---|---|
| `L3_LEVEL_TOUCH_{4H,24H}` | hourly, every level zone of the decision block | `side:edge` | `TOUCH_V1` |
| `L3_DISTANCE_TOUCH_{1H,4H,24H}` | hourly, distances 0.25 / 0.5 / 1 / 2 / 3 / 5 % on each side | `side:distance` | `TOUCH_V1` |
| `L2_STATE_ANALOG_{1H_1H,1H_4H,4H_4H,4H_24H}` | hourly, the live 1h / 4h label of the full hour | `window:label` | `ANALOG_V1` |
| `L2_LEVEL_FIRST_TOUCH_HOLD_{1H,4H}` | every level-touch evaluation (`PUSH` or `SUPPRESSED`), history N ≥ 30 | the alert key | `LEVEL_HOLD_V1` |
| `L2_DH3_P1_RANGE_4H` | hourly, quiet hours only, arm `STATE` / `COMPARATOR` | `P1` | `DH3_P1_RANGE_4H_V1` |

**Differences from §3–§6.**
- **The `L3_DISTANCE_TOUCH_*` grid is added.** The `/risk` table and every arbitrary level of `/check` are read off the same distance curve. A user-independent grid is the unbiased sample for their calibration; user-chosen levels would make the display the sampling rule.
- **Analogue classes are named by window and outcome horizon.** Only `1H_1H` and `4H_4H` are printed today. Every label with a history card is written, so the live baseline cohort is "every hour", as in history:
  - rows under the display minimum, or for a horizon no line prints, carry `eligible_reason = BASELINE_COHORT_ONLY_N_BELOW_MIN`;
  - only `SHOWN_N_AT_LEAST_MIN` rows are a stated claim.
- **The level-hold class covers 1h as well as 4h.** The texts print the 1h hold rate.
- **`L2_DH3_P1_RANGE_4H` is added (owner decision).**
  - Its numbers are frozen from `research/DH3_RESULT_DISCOVERY.json` `CELLS.DH3-P1`, and a test keeps them equal to the record.
  - The cohort is the record's cohort: quiet hours by the frozen cuts of `config/beta_research_cuts.json`.
  - The live metric is the raw shift, read against the record's raw shift. The claim itself is the adjusted shift (+13.4 %). It is not shown as «Проверено» (status `WEAK`).
- **`L1_WEEKEND_CALM` is not built.** That line is not live.
- **Corridors stay in `beta_forecasts`** (§6).
- **What gets a display link.** `/btc` prints no journaled number. The `/alert` reply and `/risk <stop>` print an off-grid distance, so they are not linked. Every other number on a surface listed in §3 is linked when the hour's claim already exists.
- **`issue_slot`.**
  - Hourly classes: the UTC hour.
  - Level-touch claims: the touch time.
  - `as_of` is the close of the last 1m bar for touch chances, and the full hour for analogue and DH3-P1 claims.
  - For a level touch it is the touch bar's open + 5 min (the history uses the touching 5m bar's close).

**What it does not do.**
- It changes no text, corridor, touch chance, threshold or push decision.
- It reads no outcome at write time.
- Users see nothing from it until the `/check` design note (`PRE_BETA_SCOPE_DECISION_V1.md` §5) fixes the calibration bins, the tolerance and the effective-N threshold at which a live accuracy line appears.
