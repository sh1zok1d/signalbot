# Beta V0.3 — market briefing (P1 contract)

**Status:** `OWNER_DECISION_RECORDED / CONTRACT / NOT_IMPLEMENTED`
**Date:** 2026-10-02
**Authority:** owner decision 2026-10-02. It is a `CHANGE PRODUCT` outcome under the frozen exit criteria of `PRIVATE_BETA_V0_RESTART_DECISION.md`; the amendment is recorded there.
**Companion gate:** `BETA_HISTORICAL_ANALOGUE_GATE_V1.md` governs "what happened after similar ones". That surface is not part of this contract and ships only through its gate.

```
PRODUCT_SURFACE            = MARKET_BRIEFING (was: event-push attention engine)
PICTURE_TIMEFRAMES         = 1h / 4h / 1d (5m is raw material and timing only)
DETECTOR_RULES_CHANGED     = false (BETA_EVENT_RULES_V1 untouched)
TAPE_SCHEMA_CHANGED        = false
PREDICTIVE_WORDING         = forbidden (analogue summaries: only under their gate)
LLM_IN_LIVE_PATH           = false
EXTERNAL_USERS             = not before the owner-only week of §7
```

## 0. Why the surface changes

**Owner use, two days.**
- **The event feed is noise.** On 5m–15m, events are only "aggressive buying" or "aggressive selling" and answer no decision question. The 1h summary repeats the 24h one.
- **The push cap runs out early.** The 3-push daily cap is used up by about 11:00. Later events are silently dropped, so the trader cannot tell what to do.

**The frozen criteria agree.**
- **Cap.** The soak target for cap-activation days is about zero. The cap binds every day.
- **Exit rule.** The restart decision names `CHANGE PRODUCT` when users report the events as unactionable or confusing.

**The arithmetic agrees.**
- `TAKER_FLOW_EXTREME` fires on the top or bottom 5% of 5m buckets, which is about 29 buckets a day by construction.
- Its rarity is a frequency set by configuration, not significance.

**The research agrees.**
- MARKET-01…06 and H05 found no direction information in short-horizon BTC conditional states.
- The `PRICE_OI` pilot is `BALANCE_FAILED`.

**The owner's job to be done.**
- At 08:00–09:00 Kyiv, and after any absence: what happened since I last looked, who dominates, and how the market is positioned for today.
- The picture is built on 1h and 4h bars. 5m bars are too noisy for it.
- Today the owner answers this with Coinglass and the chart. The value is the compression: what happened → why (positioning) → how unusual (versus normal, across venues) → is it continuing → the wider context.

**Target user** (unchanged from `BETA_BTC_MULTI_HORIZON_UX_V1.md`): a Russian-speaking BTC perpetual intraday trader holding about 30 minutes to several hours.

## 1. What P1 ships

### 1.1 `/catchup` and "since your last view"

**Window.**
- `/catchup` covers the time since the user's last `/btc` or `/catchup`. That time comes from `beta_user_activity` (`cmd_btc`, plus a new `cmd_catchup`).
- Bounds are 1h minimum and 24h maximum, defaulting to 8h with no prior view.
- `/catchup <hours>` overrides the window. The window is printed in Kyiv time.

**Content, in this order:**
1. **Price path.** Open → close, change, and range compared with the normal range for the same window length and the same time of day.
2. **Up to 3 episodes.** Hour-level episodes marked significant by §1.4, chronological, in Kyiv time. Each has its state label (§1.3) and its numbers: price %, OI %, buy share of taker volume, and liquidations by side if present. The episode with no significant hour says so: "тихо: ни один час не выбивался из обычного".
3. **Now.** The last 1h and 4h state labels, funding and who pays it, and crowd versus large-trader positioning where the feed exists.
4. **Day context.** Position of the price in the 24h range, the 24h OI change, and calendar facts.
   - The only calendar item computed in P1 is the Deribit options expiry, Fridays at 08:00 UTC, monthly on the last Friday of the month.
   - Macro calendar needs a source decision and is not in P1.
5. **Uncertainty lines** (§1.5).

**Morning brief.**
- One scheduled `/catchup` per user, at a time the user chooses, default 08:00 Kyiv.
- Opt-out with `/brief off`.
- It is a separate delivery class from event pushes and does not count toward the event cap.

### 1.2 Market State block

**Placement.** At the top of `/btc` and inside `/catchup`:

```
Состояние рынка
5m   похоже на закрытие шортов
1h   рост на новых лонгах
4h   сжатие: диапазон узкий, OI растёт
1d   цена у верхней границы дневного диапазона
Плечо: растёт · Поток: покупатели активнее обычного · Волатильность: выше обычной · Биржи: 3/3 согласны
```

**Rules for the block.**
- **Data.** Rows are computed from closed bars aggregated as-of from the 5m tape (1h, 4h, 1d), with the same-length time-of-day baselines of §2.
- **Narrow fallback.** A row whose inputs are not mature prints `мало истории` instead of a label.
- **Not a forecast.** No row ever says what comes next.

### 1.3 State vocabulary `BETA_MARKET_STATE_LABELS_V1`

**How labels are computed.** Labels are deterministic functions of one horizon's closed-bar aggregates:
- price change;
- OI change;
- taker buy share;
- range;
- liquidations by side;
- venue agreement.

Every condition compares a value with its own same-horizon baseline percentile, never with a raw constant. The cut points are frozen in `config/beta_v0.yaml` under this version label, outside the detector rules digest.

**Allowed tuning.** Only frequency and readability tuning on non-outcome statistics, such as how often each label fires. Every change is documented. Labels are never tuned against forward price outcomes.

| Label (ru) | Condition (sketch; exact cuts frozen at implementation) |
|---|---|
| похоже на закрытие шортов | price up, OI down beyond its normal band |
| рост на новых лонгах | price up, OI up |
| снижение на новых шортах | price down, OI up |
| похоже на закрытие лонгов | price down, OI down |
| вынос лонгов / вынос шортов | the closing case above, with liquidations of that side in the top tail |
| набор позиций без движения цены | price flat versus its own band, OI up |
| разгрузка рынка | OI down broadly with no dominant price direction |
| сжатие | range in the low tail and OI not falling |
| агрессивные покупки (продажи) без движения цены — их поглощали | taker share in the tail, price flat |
| обычное состояние | none of the above |

**Wording.**
- Inferred labels read "похоже на …", because the price/OI reading is a heuristic.
- Labels describe what happened. They never say what follows: the `PRICE_OI` pilot is `BALANCE_FAILED`.
- Detector names (`PRICE_OI_CONTRACTION_UP` and so on) move to Details.

### 1.4 Significance, decomposed

**Details panel.** For an episode or hour, Details lists:
- the percentile of each dimension against its baseline: price move, OI change, volume, taker imbalance, liquidations;
- per dimension, how many venues agree ("подтверждают 3/3 биржи").

There is **no composite score**.

**Significance rule** (frozen with §1.3), used for `/catchup` episode selection and for push: at least two dimensions in their top 5% at the 1h horizon, and at least 2 of 3 venues agreeing on the price-and-flow direction.

### 1.5 Saying "I don't know"

Fixed lines, printed whenever they apply:
- a venue missing or stale: "OKX OI нет 18 мин — оценка по 2/3 биржам";
- a degraded family;
- an immature baseline: "мало истории для сравнения";
- a cross-venue disagreement: "биржи расходятся".

### 1.6 Push policy V0.3

| Delivery | Rule |
|---|---|
| Morning brief | §1.1, opt-out, one per user per day |
| Event push | only TRIGGERED detector episodes that pass §1.4. One message per episode, plus at most one update when its 1h state label changes. EARLY and ARMED never push. |
| `TAKER_FLOW_EXTREME` (5m) | never pushes. It stays visible in `/btc` Details. |
| Daily event cap | stays as a safety fuse. With §1.4 it should rarely bind. The frozen target "cap-activation days ≈ 0" is checked in §7. |

The cooldown, TTL and push hard switches of the restart decision are unchanged.

## 2. Data and baselines

- **Sources.** Beta state tape V2 (5m, Binance / Bybit / OKX), Stage-1 OI as-of reads (as the multi-horizon pass already does), funding, and the beta liquidation feeds. Bitget stays disabled.
- **Aggregation.** 1h, 4h and 1d aggregates are read-only projections over closed buckets. Nothing is written to the tape, so the rules digest and the open episodes are untouched.
- **Baselines.**
  - 1h: the same time of day over 30 days.
  - 4h and 1d: 90 days. The bootstrap lookback grows from 30 to 90 days for these projections only. The detector's 30d percentiles are unchanged.
  - Until mature: `n/a` and "мало истории".
- **No lookahead.** A value shown at time `T` uses only buckets closed before `T`. Offline tests enforce it.
- **Time and language.** Display in Europe/Kyiv, RU/EN as today. Liquidations stay per venue and are never summed (multi-horizon rule).

## 3. Boundaries

**Unchanged:**
- the detector, `BETA_EVENT_RULES_V1`, the rules digest, episodization `STRICT_QUALIFICATION_V1`, readiness, forward outcomes (`BETA_OUTCOME_V1`), tape schema V2;
- D7 gate and line;
- the code paths (`beta/`, `runtime/beta_*`, `storage/beta_v0_*`, `config/beta_v0.yaml`, `deploy/signalbot-beta-*`).

**Additive only:** storage for the brief schedule and the new activity actions.

**Not in P1:**
- historical analogues (their own gate);
- episode evolution with `COOLING` — P2, needs a new episodization version;
- a range forecast — needs its own gate;
- spot and Coinbase premium;
- macro calendar;
- other assets;
- an LLM in the live path.

**Wording.** Templates are deterministic. The rules of `BETA_BTC_MAIN_SCREEN_UX_V1.md` §5 apply, extended by §1.3. Never allowed:
- a trade recommendation;
- a direction call;
- a target;
- a probability of future direction.

## 4. Supersession

- **2026-10-01 freeze.** `research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md` §1.1 ("the beta ships as it is, no new beta features") is superseded for exactly the scope of this contract. The rest of that program is unchanged.
- **Direction proposal.** `PRODUCT_DIRECTION_AFTER_BETA_PROPOSAL.md` item 3 ("no direction") is superseded by `BETA_HISTORICAL_ANALOGUE_GATE_V1.md`, for analogue summaries only.

## 5. Implementation order (P1)

1. **Read-model projections:** 1h / 4h / 1d aggregates and baselines, the state labels, decomposed significance. Pure functions with offline tests.
2. **Commands:** `/catchup`, the Market State block on `/btc`, and the Details significance panel.
3. **Push:** the V0.3 push policy, the morning brief scheduler, and the removal of 5m taker pushes from push.
4. **Docs:** update `BETA_BTC_MAIN_SCREEN_UX_V1.md` to what is rendered.

Each step is its own PR. None changes detection.

## 6. Tests (offline, before deploy)

- **Aggregation:** as-of correctness and no lookahead; boundary buckets; missing venues.
- **Labels:** determinism, every label reachable, `обычное состояние` as the fallback.
- **Significance:** venue agreement with 3, 2 and 1 usable venues.
- **`/catchup`:** window bounds and episode selection on synthetic tapes.
- **Push:**
  - one push per episode plus at most one update;
  - no `TAKER_FLOW_EXTREME` push;
  - the brief is outside the event cap.
- **Forbidden wording** in both languages.

## 7. Acceptance (before any external user)

**One owner-only week on production data:**
- the morning brief arrives every day;
- cap-activation days ≈ 0;
- no stale or degraded output is shown as normal;
- no forbidden wording.

The owner's verdict decides whether invites open.

**Exit criteria.** The frozen beta success and exit criteria of the restart decision apply unchanged, counted from the first external user of V0.3.

## 8. Owner decisions recorded (2026-10-02)

| Decision | Value |
|---|---|
| Change the beta surface to a market briefing (`CHANGE PRODUCT`) | yes |
| Picture timeframes | 1h and 4h (plus 1d context); 5m only as raw material and timing |
| Morning time | 08:00–09:00 Kyiv; default brief 08:00 |
| Owner's current tools | Coinglass and the chart; futures |
| Direction medians | allowed only inside analogue summaries, under `BETA_HISTORICAL_ANALOGUE_GATE_V1.md` |
| Sequence | P1 this contract → P2 episode evolution (`COOLING`) → P3 analogue summaries through their gate |
