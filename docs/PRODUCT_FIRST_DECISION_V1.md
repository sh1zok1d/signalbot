# Product-first decision V1 — canonical product decision record

**Status:** `OWNER_DECISION_RECORDED / CANONICAL_PRODUCT_DECISION / BUILD_TO_TEST_NOT_STARTED`
**Date:** 2026-10-02
**Operating mode from this decision:** `PRODUCT_FIRST / RESEARCH_SERVES_PRODUCT / PREDICTIVE_CLAIMS_FROZEN`
**Authority:** owner decision 2026-10-02, recorded after an independent external assessment of the project, a 30-day validation design, its red-team, a build-to-test scoping pass and a code-level reuse audit of `beta/`. This file is the single canonical record of the product decision. Where an older product or beta document disagrees with it on scope, sequence or evidence standard, this file wins. It changes no frozen research contract, no sealed verdict and no protected-data rule.

**What this file is not.** It is not an implementation. Nothing in it changed runtime code, schemas, config or tests. It is not a new governance framework: it records decisions so the next implementation task starts from them instead of redesigning the product.

```
PRODUCT_FIRST                       = true
RESEARCH_PACE_SETS_PRODUCT_PACE     = false
NEW_RESEARCH_PROGRAMS_AUTHORIZED    = false
NEW_ONE_SHOT_CONFIRMATIONS          = false
EDGE_CLAIM                          = none (unchanged)
BUILD_TO_TEST_SCOPE                 = §3 (MUST only)
DO_NOT_BUILD_YET                    = §5
USER_TEST                           = §7, after MUST scope is done and data are mature (§6)
```

## 1. Strategic decision

1. **Signalbot is product-first for the next stage.** The question the project answers next is whether a real, unknown-to-the-founder intraday trader finds the product useful. It is not whether a trading edge exists.
2. **Research infrastructure is kept.** It is not deleted and it is not declared useless. It stops setting the pace of product work.
3. **Research serves the product.** Research may continue only where cost is small and feasibility is confirmed in advance. No new large research programs, no new one-shot confirmation units, no widening of the research surface in the hope of finding an edge. Every sealed verdict, every frozen contract and the protected 2025/2026 data stay exactly as they are.
4. **Two evidence standards, kept separate in documentation and in wording:**
   - **Product evidence.** An honest descriptive or heuristic interpretation of observed data, with its uncertainty and provenance shown. It may be tuned for frequency and readability on non-outcome statistics. It never claims a mechanism, an edge or a future direction.
   - **Research claim.** Anything framed as a tested market statement. It goes through the existing research contract (`research/HYPOTHESIS_EVALUATION_CONTRACT_V1.md`, `EDGE_RESEARCH_PROTOCOL.md`) unchanged.
5. **"Do not lie" does not mean "do not interpret".** The product may say "похоже на …" with the observations that support it and a factual fallback when they conflict. It may not say what comes next.

## 2. The product hypothesis under test

> Signalbot saves an intraday BTC-perpetual trader time by compressing, in Russian, the answer to "what happened while I was away, who dominates now, and how unusual is it", delivered in the morning and at the rare genuinely unusual moments of the market.

The first user version does **not** test a trading-edge hypothesis and does **not** promise a direction of future price. The target user is unchanged from `BETA_BTC_MULTI_HORIZON_UX_V1.md`: a Russian-speaking BTC perpetual intraday trader holding about 30 minutes to several hours.

## 3. Build-to-test scope (MUST HAVE, before any external user)

Only the surface below is built before invitations. Reuse classification comes from the code audit of `beta/` on 2026-10-02 (HEAD `db80614`).

| # | MUST | Reuse class | What exactly |
|---|---|---|---|
| 1 | **Shared market/view builder** over the existing beta infrastructure | EXTEND | Extract the view assembly that `runtime/beta_bot.py::BetaBotHandler._btc` does today (`collect_status` → context state → `build_horizons` → regime → persist) into one function in `beta/` with a window parameter. `/btc`, `/catchup` and the briefing render this one object. None of them has business logic of its own. Views stay in `beta_btc_views`, with a `kind` column (`btc` / `catchup` / `brief`). |
| 2 | **`/catchup`** | NEW, thin | Default window 8h; `/catchup <hours>` from 1 to 24. The pull version of the same market summary the briefing sends. Activity action `cmd_catchup`. |
| 3 | **Morning briefing** | EXTEND | Once a day, 08:00 Kyiv for every user (per-user time is not in MUST). Same view and render path as `/catchup`. Delivered by a "due briefs" step inside the existing `run_notify_once` cycle through the existing outbox (`kind` column, nullable `episode_pk`). `/brief off` (`beta_users.brief_enabled`). No second notifier. |
| 4 | **1h and 4h product context** | EXTEND | 4h = the 1h machinery (`rolling_1h_values`, `context_1h`) parameterised by bucket count (48) under new labels `BETA_HORIZON_TOD_V2` and `BETA_CONTEXT_1H_V2`. The same 30-day baselines as 1h; 90-day baselines are not built. **24h stays a context-only horizon** (high/low, position in range, "changes vs previous 24h", average funding). It gets no interpretation label. |
| 5 | **Interpretation layer for 1h and 4h** | NEW, pure function | Vocabulary (RU): `похоже на выход шортов`, `похоже на рост с новыми лонгами`, `похоже на снижение с новыми шортами`, `похоже на выход лонгов`, `вынос лонгов` / `вынос шортов` (only with a confirming existing `LIQUIDATION_STRESS_*` episode overlapping the window), `сжатие`, `обычное состояние`. Rules in §3.1. |
| 6 | **Context projection extended** to 4h and to taker-delta and OI-change ranks | EXTEND | Add taker delta (sum of 5m, already on the tape) and the 1h/4h OI change (Stage-1 as-of, one 31-day range read plus the existing `pick_oi_asof`) to the ranked context metrics, under the new context version label. This is the product/context layer. The rules digest (`_RULE_DIGEST_FIELDS`) is not touched. |
| 7 | **Push on an unusual hour** | CONFLICT resolved → gate | No new detector, no new episodization. The only mechanism stays `rules → detector → episodes → push_policy → push decisions → outbox`. A product-level gate in `push_policy` lets a `TRIGGERED` episode push only when the rolling 1h around it is unusual: at least two of the three existing ranked 1h metrics (range, price move, volume) at or above `context.label_high`, and at least 2 of 3 venues agreeing on the sign of the 1h move. New suppression reasons `HOUR_NOT_UNUSUAL`, `QUIET_HOURS`, `GLOBAL_COOLDOWN`. The 1h ranks must be available before the decision (previous bucket's context snapshot, or `context_1h_asof` computed before the decision in `process_live_bucket`). **Before implementing the gate, run a diagnostic on the recorded tape:** what share of unusual 1h windows (by the rule above) contains at least one `TRIGGERED` episode. That diagnostic is a coverage check for the gate, not a research unit and never a reason to build a second detector engine. |
| 8 | **Push policy** | EXTEND, config digest only | `max_new_pushes_per_utc_day: 2`; quiet hours 23:00–07:00 Kyiv, fixed; one global cooldown across event types; `/push off` (`beta_users.push_enabled`, does not touch the briefing). The user-facing push renders the 1h state, not the 5m detector name. The 5m detector keeps running internally; it is never delivered to the user as a product event of its own. |
| 9 | **Clean user surface** | EXTEND | Remove from user text: hashes, rule versions, detector names, internal ids, repeated disclaimers. The disclaimer stays in `/start` and `/terms`. |
| 10 | **Minimal telemetry for the test** | REUSE + EXTEND | Reuse `beta_user_activity` (it carries `user_pk`; `beta_details_opens` deliberately does not and is not needed). Add actions `cmd_catchup`, `brief_delivered`, `cmd_brief`, `cmd_push`. Needed and derivable without new entities: briefing delivery; `/catchup`; push delivery (`push_delivered` exists); reaction after a push (`tab_*` / `btn_*` within 10 minutes of `push_delivered`); push or brief disabled; failed delivery and blocked bot (already in the outbox `error_summary`); known versus unknown-to-founder user (`beta_users.known_contact`, owner-set). |

Also fixed by this scope:
- the `/btc` screen itself is not redesigned; the Market State block is not added to it in build-to-test;
- `BETA_EVENT_RULES_V1`, the rules digest, tape schema V2, `STRICT_QUALIFICATION_V1`, `BETA_OUTCOME_V1`, the D7 gate and line are untouched;
- labels and 4h values live in the context projection and the view payload; they are never written to the tape;
- `beta/i18n.py::_FORBIDDEN_RU` is **not** changed. The vocabulary is chosen to pass it: "выход шортов" instead of the forbidden "закрытие шортов", "OI" instead of the forbidden "плечо".

Rough build order, each step separately testable offline: 4h window and labels with a dry run over the recorded tape → `/catchup` template and command → scheduled briefing and `/brief off` → surface clean-up and telemetry → gate coverage diagnostic → gate, policy, `/push off`.

### 3.1 Interpretation rules (frozen with this decision)

Inputs per horizon (1h, 4h): price move, range, volume, taker delta, OI change (all ranked over 30 days with the existing percentile core), per-venue liquidation sums, funding, venue agreement. Cut points reuse the existing `context.label_elevated` (0.80), `label_high` (0.95) and `tail_display_max` (0.20): "up" = price rank ≥ 0.80, "down" ≤ 0.20, "flat" in between; the same bands for OI and taker delta.

| Label | Required observations | On conflict → factual fallback |
|---|---|---|
| похоже на выход шортов | price up, OI down, taker delta positive | taker negative → «рост при снижении OI» |
| похоже на рост с новыми лонгами | price up, OI up, taker delta positive | taker negative → «рост с ростом OI» |
| похоже на снижение с новыми шортами | price down, OI up, taker delta negative | taker positive → «снижение с ростом OI» |
| похоже на выход лонгов | price down, OI down, taker delta negative | taker positive → «снижение при снижении OI» |
| вынос лонгов / вынос шортов | the matching row above plus an existing `LIQUIDATION_STRESS_LONG` / `_SHORT` episode overlapping the window | no episode → the row without «вынос» |
| сжатие | range rank in the bottom tail, OI not in the bottom tail | OI unavailable → «сжатие, OI н/д» |
| обычное состояние | none of the above | — |

Global rules:
- interpretations rest on price **and** OI **and** taker flow, never on price×OI alone;
- price agreement below 2 of 3 venues → «биржи расходятся», no label;
- OI from fewer than 2 venues or taker delta missing → factual pair only;
- immature ranks → «мало истории»;
- every inferred label is prefixed «похоже на»;
- labels describe what happened; they never say what follows;
- label rules may be tuned only for frequency and readability on non-outcome statistics, with each change written down. They are never tuned against forward outcomes, and never because they explain the past nicely.

## 4. Architectural constraint

```
5m tape V2
  → existing detector / rules V1
  → existing episodes
  → push_policy + product-level 1h gate
  → existing push decisions / outbox

in parallel:
tape
  → context projection 1h / 4h (one projection, new version label)
  → interpretation (pure function)
  → shared market/view builder
  → /btc · /catchup · morning briefing
```

One detector. One episodization. One context projection. One shared view builder. One outbox. One notifier.

Not allowed: "briefing episodes", a separate notification engine, a parallel product detector, a second significance rule with its own lifecycle.

## 5. DO NOT BUILD YET (until user evidence from §7)

- historical analogue cards / «что было после похожих» (`BETA_HISTORICAL_ANALOGUE_GATE_V1.md` stays frozen and inactive);
- new analogue, bootstrap or Holm gates for product UI;
- a claim ledger as a product feature;
- Generator V0 for the product;
- the synthetic user (`BETA_SYNTHETIC_USER_V0.md`);
- new research units of the D7 / C013 kind;
- a multi-asset scanner;
- personal decision history;
- read-only exchange keys;
- an LLM in production;
- a web UI;
- payment infrastructure beyond a manual link;
- order book, liquidation maps;
- per-type mute, complex personalisation;
- a new historical backfill only to launch a few days earlier;
- a separate 24h interpretation label;
- a second detector or event engine.

These ideas are not rejected. They are forbidden until there is user evidence.

## 6. Data and launch orientation

Fact: tape schema V2 rows, which carry the per-venue OHLC that every 1h/24h baseline and every ranked 1h context value reads, are written since **2026-10-01** (PR #248). V1 rows since 2026-09-25 count only for the 5m detector percentiles.

Expected maturity, without any new backfill:
- 1h and 24h time-of-day baselines (`_MATURE_DAYS = 20`): about **2026-10-21**;
- full 30-day window for context ranks: about **2026-10-31**;
- OI as-of, funding and the 5m detector percentiles: already sufficient.

No new backfill is built to win a few days. Re-running the existing bootstrap under schema V2 would need its watermark reset and would gain about six days; it is not done. Until maturity the existing honest «мало истории» / `n/a` states are shown. The external launch date is set by actual data maturity and by the MUST scope being done, not by a calendar promise. Until then the bot lives only with the owner, and owner use serves bug-finding only, never value assessment and never content redesign.

## 7. Product validation after build-to-test

After the MVP is ready, a separate 30-day user test runs. Sample: real traders unknown to the founder. The owner's own usage is excluded from every metric. The founder's acquaintances are counted separately and never toward PASS.

- **Days 1–7: calibration.** Allowed: clarity, timing, translation and bug fixes driven by interviews. Not allowed: adding or removing information types, changing the push rule or the labels' meaning. Every change is written down.
- **Day 8: frozen** product, value proposition and decision criteria. Measurement covers days 8–30; retention windows use days 18–30. First-week novelty is never read as retention.
- The 30 days start at the first unknown-to-founder user, not at a calendar date.
- A day with delivery failure for more than 30% of users is excluded for everyone.

Five unknowns, with their thresholds fixed before the first invitation (to be recorded with a commit hash before launch):

| Code | Unknown | Method | PASS | FAIL | INCONCLUSIVE |
|---|---|---|---|---|---|
| U4 | Reachability of the segment (precondition) | 2 acquisition channels, 12 days, at most 6 hours of work | ≥ 8 unknown users joined | < 8 after 12 days → "Stop: distribution", recorded separately from product value | — |
| U1a | Value of the scheduled briefing | Withdrawal test: 3 random weekdays in weeks 3–4 without the briefing, same days for everyone | ≥ 4 unknown users pull `/catchup` within 3h or ask where it is, on ≥ 2 of 3 days; `/brief off` ≤ 1 | ≤ 2 react, or `/brief off` ≥ 3 | 3 react |
| U1b | Pull demand | Self-initiated commands outside 10 minutes after any push, days 18–30 | ≥ 4 unknown users on ≥ 3 distinct days per week | ≤ 2 | 3 |
| U2 | Quality of rare pushes | Per user, not per vote: Useful share with ≥ 5 votes, tab click after a push, disable/block | ≥ 4 unknown users with Useful ≥ 60% or a click after ≥ 40% of pushes; disabled or blocked ≤ 2 | ≥ 3 disabled/blocked, or ≤ 2 users with a positive share | < 15 pushes per user, or the month's realised volatility in the bottom quartile of the prior 90 days |
| U3 | Willingness to pay | Real transfer only; the price is offered to **everyone** enrolled, churned included, on days 21–25; refunds within 30 days cancel | ≥ 3 unknown users paid **and** ≥ 25% of all enrolled unknown users | ≤ 1 | 2 |
| U5 | BTC-only vs multi-asset demand | Fake door in `/help` plus the last interview question, unprompted | ≥ 5 unknown users named it unprompted or clicked on 2 distinct days | — (direction input, not a verdict) | — |

Interviews: 15 minutes per user per week, one fixed 5-question script, answers stored verbatim; the owner sends no messages to users outside scheduled interviews; interviews happen after the week's metrics are closed; churned users are asked why.

Decision rules, fixed now, read on day 30 by unknown users only, evidence precedence money > behaviour > words:
1. **Continue:** U3 PASS and at least one of U1a, U1b, U2 PASS.
2. **Reposition:** U3 not PASS, but at least two of U1a, U1b, U2 PASS. The passing unknown names the direction (briefing-only; alerts-only; scanner if U5 PASS). It authorises no new feature.
3. **Pivot:** U4 PASS, U1a/U1b/U2 all FAIL or INCONCLUSIVE, U3 not PASS, and ≥ 5 unknown users independently name the same missing thing. Build that, with a new 30-day test under the same rules.
4. **Stop, no value:** U4 PASS, U1a/U1b/U2/U3 all FAIL, no shared request in interviews. The pipeline stays as an asset.
5. **Stop, distribution:** U4 FAIL. Recorded apart from rule 4.
6. **INCONCLUSIVE:** none of 1–5 fired. Exactly one extension of 14 days without product changes; after it, the nearest of rules 4 or 5 applies. No third round.

Hard limits: interviews cannot turn a FAIL into a PASS; they only choose the direction inside Reposition and Pivot. No threshold is changed after the first number is known. At N ≈ 10 these thresholds are a decision policy against self-deception, not statistical proof about the market.

## 8. Anti-self-deception rules

- the owner is not a user; owner opens, votes and impressions are excluded in code;
- push-driven opens are not pull retention;
- "I would pay" is not payment;
- no complaints is not satisfaction;
- criticism is never re-labelled "wrong segment" after the fact; the segment is fixed before launch;
- no new feature after a bad result without evidence (the fake door, the interviews);
- a bad product result is never answered by going back into research;
- criteria are never changed after a result;
- user words are stored verbatim, never only paraphrased, and coded against the fixed script by someone without project context;
- no product conclusions from the first week's novelty;
- interpretation rules are never tuned against future outcomes, nor by how well they explain the past.

## 9. Superseded by this decision

| Superseded | Where it came from | Replaced by |
|---|---|---|
| Separate "briefing episodes" (`BETA_BRIEFING_EPISODES_V1`) with open/close/merge and their own table | `BETA_V0_3_MARKET_BRIEFING.md` §1.4, §1.6, §5 | §3.7 gate over existing episodes |
| A new "1h detector" / significance rule as a push source independent of the detector | same | same |
| An interpretation label for 24h | V0.3 Market State block, 24h row | §3.4: 24h is context only |
| A mandatory historical backfill before the test | build-to-test draft of 2026-10-02 | §6: no backfill; launch follows maturity |
| A separate notifier for the briefing | same draft | §3.3: one notifier, one outbox |
| Reading a U4 FAIL as proof of no product value | 30-day plan draft | §7 rule 5: "Stop: distribution", recorded apart |
| A full 30-day product freeze with no UX or bug fixes | same | §7: days 1–7 calibration, frozen from day 8 |
| 90-day baselines for 4h/24h, "since your last view" window, per-user brief time, Market State block on `/btc`, 5m row in that block, absorption/unloading labels, Deribit calendar as MUST | `BETA_V0_3_MARKET_BRIEFING.md` §1 | not in build-to-test; may return after user evidence |
| "The beta ships as it is, no new beta features" | `research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md` §1.1 | §3 (already partly superseded by V0.3) |
| "Product/business exploration is frozen until a mechanism earns independent validation" | `PRODUCT_HYPOTHESES.md`, `PROJECT_STATUS.md` (research-first wording) | §1: product-first; validation gates research claims, not product evidence |

Unchanged by this decision: every sealed research verdict, `V3`, `E1-RUN-001`, `D2`, `D7`, `C013`, the scientific test ledger, Generator V0 memory, the protected 2025/2026 data, `BETA_EVENT_RULES_V1` and the beta boundary flags of `PRIVATE_BETA_V0_RESTART_DECISION.md`.

## 10. Open questions (not decided here)

- Exact coverage threshold for the gate diagnostic (§3.7) below which the gate rule itself is revisited before launch. Proposed: if fewer than 80% of unusual 1h windows on the recorded tape contain a `TRIGGERED` episode, the gate inputs are reviewed; still no second detector.
- Whether the 1h context used by the gate comes from the previous bucket's persisted snapshot or from an as-of computation inside the decision transaction. Implementation choice, to be recorded in the PR.
- The second acquisition channel for U4 beyond Russian-speaking perp chats.
- The exact day of the first external invitation, set by §6 maturity and MUST completion.
- Whether `/btc` keeps its current layout unchanged for the whole test or is reduced to a short form of the same view. Default: unchanged.
