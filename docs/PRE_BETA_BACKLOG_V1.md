# Pre-beta backlog V1 — code status of plan A–J and of both pre-beta audits

**Status:** `READ_ONLY_AUDIT_RECORD / NOT_AN_AUTHORITY` (2026-10-05)
**Code basis:** `main` at `c2b1316`. For product code this equals production `c980fae` (C1 deployed 2026-10-05, owner-reported smoke 27/0/0): `c980fae..c2b1316` touches research documents and research tooling only (`scripts/research/history_audit.py` and its test), nothing under `beta/`, `runtime/`, `storage/`, `config/` or `deploy/`.

> **Precedence.** Where this file and `docs/PRE_BETA_SCOPE_DECISION_V1.md` (PR #331) differ, the decision wins. In particular:
> - **Touch chance wording = «B»** as that decision defines it (§5): «шанс ≈ X%» beside the held-out accuracy of such estimates («на истории: говорили 20% → было 19%, N=…») and, once mature, the live accuracy from the claim journal. Below the tolerance the design note fixes, the wording falls back to «исторически в X% случаев». (The chat version of this backlog used its own option letters and recommended the past-tense wording; those letters are not used here.)
> - **Time zone and briefing time: full, before Day 0.** The U1a `/catchup` window is measured from each user's own briefing time; quiet hours run in the user's time zone.
> - **Two levels:** the touch chance of each level plus the chance that neither is touched (from joint historical excursions, never by multiplying the two chances). «Кто первый» is post-beta.
> - **No automatic «больше не присылать такие?» prompt** after 👎. The manual one-tap per-type mute stays and counts as a negative behavioural signal in U2.
> - **Claim journal: full** (`BETA_CLAIM_JOURNAL_V1_IMPL` of `BETA_CLAIM_JOURNAL_DESIGN_V1.md` §6), with a claim class for DH3-P1.
>
> The *Code status* and *Evidence* columns below describe the code at `c2b1316` and are not changed by the decision. The *Scope* column applies the decision.

This file changes no code, config, schema, research verdict or measurement rule. It records what exists, what is missing and roughly how long each gap takes.

## 0. How to read

- **Code status:** `DONE` / `PARTIAL` / `MISSING`. `CONFLICT` marks an item that contradicted a written rule before the decision; the *Scope* column says how the decision resolved it.
- **Days:** developer-days for one developer, tests included, owner time excluded, ±30 %.
- **Priority:**
  - **P0** — blocks invitations (honesty, trust or measurement integrity);
  - **P1** — core value of the plan;
  - **P2** — wanted, does not block.
- **Scope:** `IN` (decision §2.1), `IN, amended` (decision §3), `POST-BETA` (decision §2.2), `DONE`.

## 1. Summary

- **Effort inside the decision's scope:** about **64 developer-days** (P0 ≈ 27, P1 ≈ 29, P2 ≈ 8), about **74** with integration, red-team and copy review. ETH (8–12 days) and the other post-beta items are excluded.
- **Calendar constraint.** Under C1 the live ranks mature at about the end of October (decision §4; owner estimate). Until then the unusual-hour gate answers `IMMATURE` (`BETA_C1_DAY_TYPE_BASELINE_V1.md` §1). So:
  - no unusual-hour push fires;
  - the soak cannot observe one;
  - U2 collects no votes on that class.

  Day 0 therefore cannot be earlier than rank maturity plus an owner soak that sees a real unusual-hour push.
- **Rules of `PRODUCT_DECISION_V2` §3 or `EVIDENCE_AND_CLAIMS_DECISION_V1` already broken in production:**
  - no tracked-accuracy line on `/btc` or in the briefing;
  - touch chances shown without live calibration (L3);
  - every Russian WEAK line says «порог значимости» where the record says materiality (§4, X2);
  - research IDs on the main surfaces;
  - research evidence probably live on the main surfaces (§5, finding 4).

## 2. Plan A–J

### A. Trust

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| A1 Data time on every screen and push | PARTIAL | `/btc`, `/catchup` and the brief show the tape bucket time («данные HH:MM», `beta/formatter.py:525-532,580`). `/levels` shows the request time (`beta/decision_format.py:383`). `/risk`, `/alert`, `/accuracy` and `/events` show none | One «данные HH:MM (Binance)» line from `price_ts`. The stats build time (`built_at`) is shown nowhere. Level and price alerts print the touch time next to the price at notifier run time (`beta/market_alerts.py:130`, `beta/i18n_decision.py:190`) | 1.0 | P0 | IN |
| A2 Stale = «нет данных» | PARTIAL (mostly done) | Tape older than 420 s → `DATA STALE` (`beta/health.py:85`); `/btc` hides everything (`formatter.py:487-517`). Binance price older than 10 min → «данные Binance отстают» (`beta/decision.py:34,168`). Market alerts are not detected (`market_alerts.py:351`). The unusual-hour push is suppressed `DATA_DEGRADED` | Stats age is never checked: `latest_stats` serves any row (`decision.py:46`). `/catchup` and the brief show corridor and levels under «данных недостаточно» (`formatter.py:577` has no guard). The schema reason `DATA_STALE` is never written | 0.75 | P0 | IN |
| A3 Monitoring and a ready outage text | PARTIAL | 11 owner alert keys (`health.py:112-166`), sent as a DM from inside the notifier run and repeated every 30 min (`beta/delivery.py:143-159`). `/admin_broadcast` exists (`beta/admin.py:195`) | **No dead-man switch:** `NOTIFIER_NOT_RUNNING` is sent by the notifier itself. **Never alerted:** DB or VPS down; a Binance-only outage (two venues keep the heartbeat healthy); feeds, stress and history-sync failures; alert and brief exceptions. `DELIVERY_FAILURE_SPIKE` counts only `kind='push'` (`storage/beta_v0_store.py:770`). No outage i18n key. Broadcast reaches ACTIVE users only, unpaced, with no delivery count | 1.5 | P0 | IN |
| A4 Measured alert latency, written into the push | PARTIAL | Stored: `decision_ts`, delivery `created_at` / `sending_at` / `finished_at` (`storage/beta_v0_schema.sql:281-293`), `evaluation_lag_s` on the tape | Not computed, reported or shown. Floor about 40 s after the bucket close (the notifier runs each minute at :40). A level push can be up to about 20 min after the touch: 10 min `touch_max_age_min` plus a 10 min TTL | 0.75 | P1 (the metric is needed for the soak) | IN |
| A5 Send load test; one failure never blocks the queue | MISSING | No test | `RetryAfter` becomes a final `FAILED` with no retry (`runtime/beta_bot.py:63`). No per-chat pacing. The notifier is killed at 50 s (`deploy/signalbot-beta-notify.service:23`); rows left `DELIVERY_UNKNOWN` are never resent (`delivery.py:60`). Needs a 20-user run with a fake sender | 1.0 | P0 | IN |
| A6 Tested restore incl. the feed role | PARTIAL | Monthly `restore.sh --self-test` restores the newest local dump and checks only `klines_1m` (`deploy/restore.sh:54-59`). The dump uses `--no-owner --no-privileges` (`deploy/backup.sh:29`) | Not checked: `beta_*` tables, the off-site copy. `restore.sh` never re-applies `beta_feeds_role.sql`, and the DR section of `DATA_DURABILITY_RUNBOOK.md` has no beta step. Never drilled (runbook :333-339) | 1.0 (+0.5 owner on the VPS) | P0 | IN |

### B. Accuracy

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| B1 Corridors: target vs realized, width, 7/30/90 days, misses up/down with size, calm vs event / high-volatility days | PARTIAL | `beta_forecasts` stores lower, upper, coverage, realized high/low and outcome (`schema:720-737`). It is written hourly whether or not anyone uses the bot (`market_alerts.py:255-293`). `/accuracy` shows the hit share over 30 days and on the held-out year (`decision_format.py:498`) | The 80 % target is only header text. Missing: width, 7 and 90 days, up/down split (realized high/low unused), held-out N, regime split (the scale is not stored). **«(из N)» is inflated:** it counts overlapping hourly forecasts, about 720 a month at 24h against about 30 independent | 2.75 | P0 | IN (short windows hidden at small N) |
| B2 Own calibration («говорили X% → было Y%») | MISSING | Touch chances are not stored. The claim journal is `DESIGN_ONLY / NOT_IMPLEMENTED` (`BETA_CLAIM_JOURNAL_DESIGN_V1.md:3`) | The full journal (§6 of the design) plus a DH3-P1 class. Calibration of frequent classes takes 3–6 months (design §5), so it ships first (decision §6.2) | 5.5 | P0 | IN, full |
| B3 Touch backtest for arbitrary levels before display | PARTIAL | `touch_probability` interpolates any distance (`beta/rangecast.py:342`); `/alert` accepts up to 30 % (`runtime/beta_bot.py:477`). `touch_reliability` on the held-out year exists only at 50/20/10 % (`rangecast.py:175`) and nothing reads it | More calibration bins over distance. No number outside the checked range (<10 %). Reliability shown in `/accuracy` | 1.5 | P0 (a prerequisite of wording «B») | IN |
| B4 Weekly report | MISSING | No timer or command | Owner and user versions. It is a new push type, counted in the measurement contract (decision §6.4) | 1.75 | P1 | IN |
| B5 One «мало данных» threshold | PARTIAL | About 12 scattered constants: `beta/analogues.py:50` (30), the same value duplicated in `decision_format.py:18`, `beta/levels.py:61-62` (30/15), `beta/followup.py:58-59` (10/5), `rangecast.py:44`. None is a config key | Level history prints shares at any n ≥ 1 with the verdict «мало данных» (`decision.py:111`). Analogues are hidden below 30 | 0.75 | P0 | IN |

### C. Screens

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| C1 `/btc` | PARTIAL | `format_btc` (`formatter.py:483`) plus `btc_lines` (`decision_format.py:312`). Content: price; 1h and 24h lines (volume and range as × обычно); **4h corridor only**; 2 levels **without** a touch chance; research lines; data time. Maximum 12 lines | Price vs «обычно» (`typical_move_pct` is in the block; only `/risk` uses it). 1h and 24h corridors. **An accuracy line — V2 §3 is broken today.** Today's events (already in the block). Research IDs on the main screen: every `rs_line_*` / `rev_line_*` template ends in «({id})» (`i18n_decision.py:218-256`), and tests pin the suffix | 3.0 | P0 | IN |
| C2 Briefing about 8 lines | PARTIAL | `/catchup` render path, 08:00 Kyiv (`config/beta_v0.yaml:154`) | Typically 20 non-empty lines, up to 29 (8 without the decision block). The line-budget tests render without the decision block | 1.5 | P1 | IN |
| C3 One style for `/levels`, `/risk`, Details | PARTIAL | `/levels` reaches 36 lines (3+3 zones × 6). A level is written 4 ways and the corridor 4 ways; headers, time position and indents differ | One style and order | 1.5 | P1 | IN |
| C4 One vocabulary, RU and EN equal | PARTIAL | Key parity is complete: 565/565 | Term drift: venue/exchange, summary/briefing, three phrasings of «шанс дойти». «High impact» untranslated. Two research-line systems. The WEAK wording is X2 | 1.0 | P0 | IN |
| C5 User time zone in every time | MISSING | Every clock goes through `i18n.KYIV` (about 50 call sites). `beta_users` has no tz column. Quiet hours and the brief slot are global Kyiv. Level periods «вчера/неделя» are UTC days with no caveat on `/btc` and in the brief | Full time zone in rendering and in quiet hours | 2.5 | P1 | IN, amended (PRODUCT_FIRST §9; MC U1a) |

### D. `/check` (full version, decision §5)

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| D1 The command | MISSING | Not in the dispatch (`runtime/beta_bot.py:211-267`) or in help. Nearest: `/risk <price>` (1/4/24h), `/alert <price>` (24h), `/levels` | — | 1.0 | P1 | IN |
| D2 Touch chance 1h/4h/24h with «обычно», events in the window, next levels | PARTIAL | `/risk 61500` gives three horizons (`decision_format.py:429`), with no «обычно» and no accuracy | Wording «B» with the held-out accuracy line; events and next levels | 1.0 | P1 | IN («B») |
| D3 What followed touches of similar levels | MISSING (for an arbitrary price) | Exists only per objective level type (`levels.py:503-514`). The random-level control at the same distance exists in `levels.py` | Arbitrary-price statistic with N and «обычно» | 1.5 | P1 | IN |
| D4 Two levels | MISSING | — | Each level's chance plus «ни один» from joint up/down excursions. The range model keeps one-sided quantiles only, so a joint excursion table is needed | 2.0 | P1 | IN; «кто первый» POST-BETA |
| D5 + D7 «Следить за уровнем»; one tap from push and brief with the level filled in | MISSING | No callback carries a price (`_parse_tab`); buttons are `L:levels` / `L:risk` (`formatter.py:808`, `market_alerts.py:413-416`) | — | 1.5 | P1 | IN |
| D6 Any input format | PARTIAL | `parse_risk_arg` (`decision_format.py:418`) rejects «-2%», «105k», «105 000». `/alert` rejects «105k» and «105,5к», and reads «65,000» as 65.0 | Required: «64000», «64к», «64 000», «-3 %» | 0.5 | P1 | IN |

### E. Personal layer

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| E1 My levels (list, approach and touch alerts, delete) | MISSING | Only one-shot `/alert`, at most 5 (`schema:741`) | List, approach alert, deletion | 1.5 | P1 | IN |
| E2 One-tap per-type disable with undo | PARTIAL | Text only: `/push levels off` and so on (`runtime/beta_bot.py:375-402`) | Buttons under each push. MC §3 counts "push disabled" only as `off` / `hours:off` (amendment, X5) | 0.75 | P1 | IN, amended (PRODUCT_FIRST §5) |
| E3 Briefing time | MISSING | One global `time_kyiv: "08:00"`; `brief_slot` (`delivery.py:188`) | Per-user time; U1a measured from it | 1.5 | P1 | IN, amended (PRODUCT_FIRST §9; MC §6.1) |
| E4 Time zone | see C5 | | | | | |
| E5 Trader type as one onboarding question | MISSING | No column | Store only; bump `PRIVACY_NOTICE_VERSION` (`beta/access.py:18`); the owner report is split by it | 1.0 | P1 | IN |

### F. Push

F1 template parts by push type (code today):

| Push | Fact | Unusual? | Usually next | Levels | Delay | Buttons |
|---|---|---|---|---|---|---|
| Unusual hour (`format_push`, `formatter.py:1222`) | yes | yes (price tail) | analogue line when it fits in 8 lines | no | window times only | «BTC сейчас», 👍/👎 |
| Level (`format_alert`, `decision_format.py:534`) | yes | vs a random level | hold and move after touch | next level, corridor | touch time | «BTC сейчас», Levels, Risk |
| Event | yes | — | — (must stay absent: V2 event zones) | — | minutes ahead | same |
| Sharp move | yes | «раз в N дней» | research line only | nearby levels, 1h corridor | span end | same |
| Personal price | yes | — | — | 4h corridor | late note only | same |

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| F1 Template «факт → необычно ли → что обычно дальше → уровни → задержка → кнопки» | PARTIAL | Table above | Delay line everywhere; levels in the unusual-hour push; «дальше» for moves | 1.25 | P1 | IN |
| F2 Deduplication | DONE | `alert_key UNIQUE` (`schema:591`), at most 4 market alerts a day, 120 min move cooldown, `touch_max_age_min: 10`. Push: `episode_pk UNIQUE`, cap 2/day, cooldowns 20/60 min, quiet hours (`config/beta_v0.yaml:38-40,171-184`) | — | 0 | — | DONE |
| F3 «Больше не присылать» after 2 of 3 👎 | MISSING | Votes are only stored | — | — | — | POST-BETA (automatic prompt); the manual mute is E2 |
| F4 Owner review flag | MISSING | — | Observe-only during the test. Thresholds: ≥ 30 votes from ≥ 8 people, noise > 50 %, or mass disables | 0.75 | P2 | IN |
| F5 Implicit metrics per push | PARTIAL | Derivable from `beta_user_activity`; SQL in MC §4 | The owner report uses a 30-min window (`beta/usage.py:13`) and drops `detail` (`beta_v0_store.py:1098`). No "action within 10 min", no "time to disable" | 0.75 | P1 | IN |
| F6 «Полезно / Шум» on every alert type | PARTIAL | 👍/👎 only under the unusual-hour push (`delivery.py:117`). Storage is keyed by `episode_pk NOT NULL` | Votes on level, event, move, price alerts and the brief; storage not tied to episodes | 1.0 | P0 | IN (+MC amendment) |

### G. Context and extensions

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| G1 CPI/FOMC before/after sizes | CONFLICT | V2 event zones; `BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1.md` §9 | — | — | — | POST-BETA |
| G2 Derivatives in numbers with «обычно» (funding, OI change, long/short skew) | PARTIAL | OI and average funding are shown. Long/short exists only in the research feeds, which are not enabled on production per the deploy plan | «Обычно» for funding and OI; long/short needs the feeds deployed | 2.0 | P2 | IN |
| G3 ETH as a second asset | CONFLICT | V2 §3 multi-asset ban; it would contaminate U5 | — | 8–12 | — | POST-BETA |
| G4 Research evidence: off on the main surfaces, on in the «🔬 Исследования» tab | PARTIAL | One switch: `research_presentation_enabled` (config AND env, `beta/config.py:575-587`) controls main surfaces and tab together. The «Проверено» registry lines and `/research` are outside it (`formatter.py:597-606`) | Split switch (decision §6.1) | 0.5 | P0 | IN |

### H. Feedback

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| H1 «💡 Идея / чего не хватает» | MISSING | Only `/feedback <text>` (`runtime/beta_bot.py:299`); plain text gets «Неизвестная команда» (`:267`) | Button plus capture of the next message | 0.75 | P1 | IN |
| H2 One reason after 👎 | MISSING | 👎 shows only a toast (`:637`) | — | 0.75 | P1 | IN |
| H3 One question at `/stop` | MISSING | `/stop` replies «paused» (`:263-266`) | — | 1.0 | P1 | IN |
| H4 In-bot interview booking | MISSING | — | — | 0.5 | P1 | IN |
| H5 Fake doors with a price | CONFLICT | PRODUCT_FIRST §7 U3, §8; MC §7 | — | — | — | POST-BETA |
| H6 Owner report (organic vs post-push returns, repeat `/check`, noise by type, by trader type) | PARTIAL | `/admin_stats` → `format_usage_report` (`usage.py:256-314`) | Returns counted only for `/btc` with a 30-min window. Repeat `/check` needs D1. Noise by type needs F6. Split by trader type needs E5 | 1.25 | P1 | IN |

### I. Monetization readiness

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| I1 free / paid flags, everything open | MISSING | — | Dormant flags only | 0.5 | P2 | IN |
| I2 Tariff description | MISSING | — | A tariff page with prices is POST-BETA. Still needed: delivery of the U3 offer to churned users. Broadcast and `/admin_reply` reach ACTIVE users only (`beta_v0_store.py:1133`) | 0.5 | P1 | Offer delivery IN; price page POST-BETA |
| I3 No payment processing | DONE | `allowed_updates` excludes payments (`runtime/beta_bot.py:104`) | — | 0 | — | DONE |

### J. Onboarding

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| J1 `/start` → trader type → live `/btc` → sample push → `/check` | PARTIAL | Today: code → language → privacy → Join → welcome (`runtime/beta_bot.py:269-287,573-583`) | The missing steps. The automatic `/btc` must not be logged as `cmd_btc`, or it pollutes U1b | 1.75 | P1 | IN |
| J2 «Как читать бота» | PARTIAL | `DECISION_HELP` (`i18n_decision.py:372`); `/terms` is a glossary | Annotated push and brief | 0.5 | P1 | IN |
| J3 Terms, privacy, disclaimer in `/terms` | PARTIAL | Privacy v4 (`beta/i18n.py:297-335`) | It describes the V1 product. No operator or contact. **The disclaimer is not in `/terms`**, although `formatter.py:533` and the copy contract say it is. It appears in `/help`, `/start` (active users) and `/history` | 0.5 (+owner review) | P0 | IN |
| J4 Support contact, one-day answer | DONE (base) | `/feedback` is forwarded to the owner with a fingerprint; `/admin_reply` (`admin.py:269`) | Plain text is lost; STOPPED users cannot be answered | 0.5 | P2 | IN |

### K. Owner-only signature index `/hypotheses` (decision §7)

| # | Code status | Evidence | Gap | Days | P | Scope |
|---|---|---|---|---|---|---|
| K1 Signature, episodes, NEW flag, blind review, `/pin` | MISSING (not audited in depth; no related code found) | — | Signature tuple from existing states; append-only episodes; NEW flag rule; blind owner review written to the exposure ledger | 4.0 (rough) | P2 (parallel track) | IN |

## 3. Items of the two audits

| Audit item | Code check | Where |
|---|---|---|
| Fail-closed; owner alerts | Confirmed, with the gaps in A2 and A3 | A2, A3 |
| Push mechanics (5 types, caps, quiet hours); `/alert`, `/push`, `/brief`; invites and the 20-user cap | Confirmed | DONE |
| U1a–U5 contract with SQL | Confirmed; the SQL runs in `tests/beta/test_beta_invite_journey_pg.py` | DONE; amendments X5 |
| `/accuracy` shows only the hit share | Confirmed; also the inflated N | B1 |
| No accuracy line on `/btc` or in the brief | Confirmed. The brief header «в 4 из 5 похожих случаев» (`i18n_decision.py:52`) is the design coverage, not tracked accuracy | C1, C2 (P0) |
| Touch chances without live calibration (L3) | Confirmed | B2, B3, X8; wording «B» |
| L2 lines in words, not percentage points | Observed share, «обычно» and N are present. No difference in pp, no interval; verdict words «чаще выше обычного», «чаще/реже обычного» (`i18n_decision.py:76-86,108-116`) | X1 |
| R03-C1 text inaccurate | Confirmed, in the other direction. RU says «ниже порога значимости». The record (`docs/research/OWNER_CARDS_R03_RESULT.md`) has the effect statistically significant (Holm p 0.0001) and below the materiality bar (0.40 < 0.50 SD). It also says the effect reflects the general volatility regime (adjusted −0.104), which the text omits | X2 |
| Research IDs on the main surfaces | Confirmed for every research template | C1, G4 |
| `/levels` up to 36 lines, brief 27 | `/levels` 36; brief 20–29 | C2, C3 |
| `/check` = `/risk <price>` + `/levels` | Confirmed: there is no `/check` | D1 |
| «Полезно / Шум» only under the unusual-hour push | Confirmed | F6 |
| U2 will hardly collect votes | 10–25 votable pushes per user per 30 days (8–19 in days 8–30); zero while ranks are immature. The contract does not define "push" for the < 15 rule | F6, X5 |
| Gate coverage diagnostic not recorded | Confirmed. The tool exists (`--beta-context-dry-run`, `beta/dry_run.py:66-156`); the 80 % threshold is still "Proposed" (PRODUCT_FIRST §10) | §6 |
| `PROVISIONAL_PENDING_DRY_RUN` | The constant is read nowhere (`beta/interpretation.py:29`); the venue-divergence behaviour is active (`:160-164`); no owner review recorded | §6 |
| `touch_reliability` not shown | Confirmed | B3 |
| No interview script, no second U4 channel, no U3 price or payment method | Absent in `main`. The script and channel 2 exist only in draft PR #307. No price anywhere | X3, §6 |
| MC §0 hash empty, Day 0 not declared | Confirmed. Contract merged in `7fdcaf4` (#322); 37 product files changed since (#326, #327, #329). `tab_research` is missing from the §2 vocabulary but counts as a reaction through `LIKE 'tab\_%'` | X5 |
| PR #307 open | Draft, merge state `dirty`, 2026-10-02, written before V2. It conflicts with the merged contract: U1a is manual with a SHA seed there and automatic with seed `20261003` in code; U5 is «Другие рынки» with no reply there and «Другие монеты» with a reply in code | X3 |
| Stale status records | Confirmed. `PROJECT_STATUS.md`, `CURRENT_STATE.md`, the V2 header (`a16b876`), `PRIVATE_BETA_V0_DEPLOY.md` (V2 context labels, no C1 section), `BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1.md`, `RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md` (#327 already merged). The C1 doc and the index are updated by PR #331 | X4 |
| CI not working (billing) | GitHub runs on `c980fae` and `c2b1316` conclude `failure` within about 5 s. Separately, `scripts/ci/pr_gate.py` lists no `tests/beta` file, so a `beta/` change runs no beta test even when CI works | X6 |

### Extra items (not in A–J)

| # | Item | Days | P |
|---|---|---|---|
| X1 | L2 lines: observed vs baseline, the difference in pp and an interval; no verdict words. The bootstraps store p-values only | 2.0 | P0 |
| X2 | Materiality wording. Four RU templates say «порог значимости» (`i18n_decision.py:221,229,249,259`), as do 8 registry lines (`config/beta_research_findings.yaml:180,200,204,224,248,274,302,322`). The EN text is correct. Registry lines change only as a reviewed findings-registry change | 0.5 | P0 |
| X3 | PR #307: reconcile with the contract and with V2, then merge, or close it after moving the interview script, the channels and the invitation text | 0.5 | P0 |
| X4 | Refresh the stale status records not covered by #331 | 0.5 | P0 |
| X5 | Amend the measurement contract (decision §6.7). Items:<br>- U1a from each user's briefing time; quiet hours in the user's time zone<br>- votes on every alert type<br>- per-type mute as a negative U2 signal<br>- what counts as a push for the < 15 rule<br>- the weekly report in U1b<br>- `tab_research`<br>- classes for the new actions (`cmd_check`, watch, idea, the onboarding `/btc`)<br>Then freeze on the final build commit | 1.0 | P0 |
| X6 | Add `tests/beta` to `scripts/ci/pr_gate.py` (plus owner: billing) | 0.25 | P0 |
| X7 | In «обычно дальше / обратно» (`i18n_decision.py:112,197`) «обычно» is the cohort's own median, not a baseline | 0.25 | P0 |
| X8 | `/check` design note before implementation (decision §5). It fixes:<br>- the calibration bins and tolerance<br>- the effective-N threshold for the live line<br>- the rule for live vs held-out divergence | 0.5 | P0 |

## 4. Findings not in either audit

1. **No dead-man switch for the notifier.** The notifier sends its own `NOTIFIER_NOT_RUNNING` alert, so a dead notifier is silent.
2. **A Binance-only outage blacks out the decision features without an owner alert.** Corridor, levels and every market alert go dark, while the 2-of-3 venue heartbeat stays healthy.
3. **Send failures are final.** `RetryAfter` is final, the notifier is killed at 50 s, and `DELIVERY_UNKNOWN` rows are never resent.
4. **Research evidence is probably live on the main surfaces in production.** `c980fae` carries `research_evidence.enabled: true` (`config/beta_v0.yaml:189-193`), and no record says `BETA_RESEARCH_EVIDENCE_ENABLED=0` was set on the VPS. Feed-dependent lines need the feeds; registry-only lines do not.
5. **Telemetry edge cases.** The contract's "push disabled" ignores per-type mutes. Re-tapping 👍/👎 writes several activity rows for one stored vote.
6. **`rs_line_not_confirmed` reads «Проверено:».** This contradicts the rule written in `beta/research_render.py:4` («Проверено» only for CONFIRMED). The texts themselves say the belief did not hold.
7. **The product never checks the age of the history statistics.** The owner alert fires only after 50 h (`health.py:109`).

## 5. Owner decisions

**Decided by `PRE_BETA_SCOPE_DECISION_V1.md`:**

| Question raised by this backlog | Decision |
|---|---|
| Plan A–J as a recorded decision; PRODUCT_FIRST §3/§5/§9 conflicts | §2.1, §3 |
| Touch chance wording (L3) | «B», §5 |
| Claim journal go | Full, first in order, with DH3-P1 (§1, §6.2) |
| Votes on alerts; measurement-contract amendments | §6.3, §6.7 |
| ETH, CPI/FOMC sizes, priced fake doors, «кто первый», the automatic mute prompt | POST-BETA, §2.2 |
| Time zone and briefing time | Full, before Day 0; U1a per user (§1) |
| My levels; trader type; weekly report to users | IN, §2.1, §6.4 |
| Research evidence during the test | Main surfaces off, tab on (§6.1) |
| «Пороги оставляем пользователям» | Fixed during the test; interviews inform changes after day 30 (§8) |
| free / paid flags | IN, everything open (§6.5) |
| Scope versus date | «Раз сроки не жмут»: everything before Day 0 (§1) |

**Still open (owner actions, decision §9):**

1. The U3 price, the manual payment method, and the commit that fixes the price before Day 0.
2. The second U4 acquisition channel.
3. Approval of the 5-question interview script, and the coder without project context (PRODUCT_FIRST §8).
4. The gate coverage dry-run on the production tape, its record, and the threshold (80 % proposed).
5. The owner review of the interpretation labels (`PROVISIONAL_PENDING_DRY_RUN`).
6. `BETA_RESEARCH_EVIDENCE_ENABLED` on production, checked and recorded.
7. CI billing.
8. PR #307: update or close.
9. 2–3 traders who have not seen the product, for the onboarding check.

## 6. Operations before Day 0

1. **Now:**
   - production state recorded (X4; #331 covers the C1 doc and the index);
   - research env flag checked;
   - CI billing restored.
2. **On the production tape:** the gate coverage dry-run and the interpretation review, both recorded.
3. **Build in the decision's order:** claim journal → calibration bins → `/check` → the rest of A–J, with `/hypotheses` in parallel.
4. **Amend the measurement contract** (X5) and freeze it on the final build commit. §0 gets that commit, not `7fdcaf4`.
5. **Deploy the final commit.** Record `INVITE_CANDIDATE_1 = git -C /opt/signalbot rev-parse HEAD`. After this, only fixes for what breaks the test land.
6. **On the candidate, `BETA_INVITE_CANDIDATE_CHECKLIST.md`:**
   - §1: restart and reboot;
   - §2: units, health, smoke SQL, history build, and the second-account journey with wrong arguments and `/stop` → `/delete_me`;
   - §6: telemetry SQL for the test account, including every new action.
7. **Restore drill** into a scratch database on the VPS, including the feed role; recorded.
8. **Send load test:** 20 users with a fake sender off production, then owner and test account on production.
9. **Latency during the soak:** P50/P95 from `decision_ts` to `finished_at`, per class.
10. **Owner-only soak:**
    - at least 7 days, including two weekends (C1 separates weekday and weekend references);
    - it must include a real unusual-hour push, possible only after rank maturity;
    - failure criteria from checklist §3; a UX review on the first real alert (§4).
11. **Invite ladder:**
    - 2–3 known people for 24–48 h, then 5 for about 3 days; all of them are known and never count toward PASS;
    - then unknown users. Day 0 is the first unknown join;
    - set `day0_kyiv` once and deploy;
    - `/admin_known` within 24 h;
    - the U3 ledger stays outside git.

## 7. Validation behind this record

- **Tests on a local PostgreSQL 16 at `c2b1316`** (`tests/beta`, `tests/beta_user_sim`, `tests/product`): 936 passed, 1 skipped, 1 failed.
  - The failure is environmental: `deploy/install_beta_feeds_role.sh:43` verifies the role login on port 5432 inside the container, and the scratch database ran on another port.
  - The research suite was not run.
- **Surface line counts** come from rendering with the repository's own test fixtures.
- **PR #307 and the CI run results** were read from GitHub.
- **Code references** were spot-checked by hand.
