# Beta V0.2 — `/btc` main screen UX V1

Presentation only. The detector, `BETA_EVENT_RULES_V1`, push switches, and the persisted `/btc` view model are unchanged. This document specifies what the main Telegram screen says. `docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md` remains the authority for the view model, anchors, and the rolling 1h.

## Product value

A five-second BTC chart already shows the price path. This screen does not replace that.

What it adds, and only when the tape supports it:

- whether the frozen detector currently has an unusual state open, or one that ended inside the 2h memory window;
- the joint reading of that state's price and open interest (a chart does not show open interest);
- a 30-day activity label for the rolling 1h (`normal` / `elevated` / `high` / `extreme`), using the frozen context thresholds.

On a calm screen that additive content is thin: "nothing unusual is open" plus the 1h label. That is an honest limitation. This sprint is compression and comprehension, not a claim of unique alpha. The PRICE_OI pilot classification is `BALANCE_FAILED`: the UI must not say that OI contraction predicts volatility, continuation, or reversal.

## 1. Information hierarchy

1. Title: the presentation state, in the first line.
2. What was noticed, if anything: when it ended, or that it is still active.
3. What changed together: direction arrows for the event's anchor bucket.
4. One factual sentence connecting those arrows. No mechanism the bucket does not support.
5. Rolling 1h activity label.
6. Data-through time.
7. Disclaimer, once.

Details is the evidence surface. Readiness is a secondary button, shown only when some family is not ready.

## 2. User-visible states

Derived in the formatter from the existing view. Internal headlines (`NO ACTIVE EVENTS`, `WATCH`, `EVENT ACTIVE`, `HISTORY BUILDING`, …) stay in the stored payload.

| Presentation title | When |
|---|---|
| `BTC · data incomplete` | Headline is `DATA STALE`, `DATA DEGRADED`, or `DETECTOR NOT READY`. |
| `BTC · history building` | Headline is `HISTORY BUILDING` (Price/OI is not evaluable yet). |
| `BTC · unusual now` | An episode is open (`WATCH` or `EVENT ACTIVE`), including when episode details are temporarily unavailable. |
| `BTC · calmed` | No open episode, and the retained last episode ended because the condition was no longer met. |
| `BTC · event ended` | No open episode, and the retained last episode ended for another reason (duration cap, data gap, not evaluable, version change). The body names that reason. The current tape is not called incomplete just because an older episode stopped that way. |
| `BTC · calm` | No open episode and nothing retained. |

`EARLY`, `ARMED`, and `TRIGGERED` are not printed on the main screen. They stay in Details.

A data-problem title wins over "calm". The screen does not say both "no active events" and "an event ended recently".

## 3. What stays on Main

- The presentation title.
- For an open or retained episode: a short plain name (`unusual rise`, `unusual drop`, `position build-up`, `buyer-initiated flow`, `seller-initiated flow`, `long-side liquidations`, `short-side liquidations`), how long ago it ended, and whether it is still active or has ended.
- Arrow line from the **anchor bucket** (why it was noticed), not from the latest 5m print:
  - Price and OI: `↑` / `↓` from the sign. A second arrow when the mature rank is in the frozen `high` tail (rank ≥ 0.95 or ≤ 0.05). A third when it is in the `extreme` tail (≥ 0.99 or ≤ 0.01). Immature history gets a single arrow and no unusualness claim.
  - Volume is added only when its frozen level is `elevated`, `high`, or `extreme` (`↑`, `↑↑`, `↑↑↑`). `normal` is omitted.
- One sentence for a price+OI event, from the signs only:
  - price up, OI down: `Positions shrank during the rise`
  - price down, OI down: `Positions shrank during the drop`
  - both up: `Price and open positions both rose`
  - price down, OI up: `Open positions grew while price fell`
  - If that same anchor bucket has at least 2 eligible top-tail liquidation votes on the matching side, the sentence names the elevated liquidations. It does not say they caused the move.
- Rolling 1h volume and range as level words. If both labels are immature: `1h activity: history building`. If the window is missing: `1h activity: incomplete`.
- `Still active`, `Event has ended`, or the data-gap sentence.
- `Data through HH:MM UTC` when the view has it.
- The existing disclaimer, once.

Other open episodes are one extra line: `Also open: seller-initiated flow`.

## 4. What moves to Details

Details keeps, and this sprint does not delete:

- event id, plain description, detector state, reached level, qualifying window, end reason;
- anchor kind and the anchor's exact values and `pct of 30d` ranks;
- the latest bucket's exact values, ranks, and per-venue **direction**;
- taker delta and per-venue liquidation notionals and votes;
- rolling 1h values and ranks;
- episodization and context versions.

Added to Details, from fields already on the view: reference price, venue coverage, and an explicit note that per-venue OI is direction-only.

A calm screen has no episode, so its Details button opens the latest bucket and the rolling 1h (`n:latest`). Event screens keep Details on the episode (`c:<id>`).

Readiness text (per-family history span, degraded reasons, "Detector ready") is not on the main screen. The Readiness button remains when any group is not `READY`, and the `r:latest` handler is unchanged.

## 5. Wording rules

- Descriptive and joint, not causal. `Positions shrank during the rise` is allowed. `Shorts were liquidated`, `healthy trend`, `continuation`, and `reversal` are not.
- No trade instruction and no forecast. `assert_descriptive` still rejects buy/sell/likely/predict/signal and the existing forbidden list.
- No watch-next sentence. A conditional such as "if OI starts rising…" is easy to read as a forecast and costs a line. Omitted on purpose.
- Context labels are not renamed. A rank of 0.91 is `elevated`, not `extreme`.
- Percentile ranks and the words `ARMED` / `TRIGGERED` / `EARLY` are not on the main screen.
- Venue names are not on the main screen. A larger OI print is not "this venue is pushing the move".

## 6. Mobile constraint

Common states are about 6–8 short lines, title included, then one disclaimer line. Sections are separated by single newlines, not blank lines. The fail-closed sentence for stale or degraded data is kept verbatim and will wrap; shortening it would drop the claim that absence of events cannot be asserted. The disclaimer stays the existing one-line text. It already says the observation is not investment advice and not a trade instruction.

## 7. Data each line uses

| Line | Source already on the view |
|---|---|
| Title | `headline`, `active_episode`, `last_event.terminal_reason` |
| `22m ago` | `requested_at` minus `last_event.terminal_at` |
| Arrows | Anchor `view` metrics: `value` for sign, `rank` + `tier` for intensity, via `level_label` / the frozen `context.label_*` cuts |
| Joint sentence | Anchor price and OI signs; liquidation `voting` / `eligible` on that same anchor |
| 1h line | `context_1h` values and percentiles |
| `No notable event in the last 2h` | `context.last_event_retention_min` (120) and no `last_event` |
| History span | Price/OI readiness `progress.span_days` |
| Data through | `data_through` |

## 8. Deliberately not shown

- 15m and 4h summaries. The tape can aggregate OHLC, but the persisted view only has the latest 5m bucket and the rolling 1h. Adding horizons would be a new projection, not a wording change.
- Numeric per-venue OI. `venue_raw` is on the tape; the view stores only up/down/flat.
- Latest-5m raw percents on the main screen. They are the diagnostic panel this sprint removes. They remain in Details.
- Reference price, venue counts, and readiness breakdowns on the main screen.
- Any claim that OI contraction adds forward information. The pilot did not establish that.
- Order book, other coins, forecasts, and push. Push stays disabled.

## Examples

Plain text. The title is bold in Telegram. The disclaimer follows each message and is omitted below.

### 1. Calm

```
BTC · calm
No unusual state now
1h volume: normal · range: normal
No notable event in the last 2h
Data through 12:05 UTC
```

### 2. Active price/OI event

```
BTC · unusual now
Price ↓↓ · OI ↓↓
Positions shrank during the drop
1h activity: incomplete
Still active
Data through 12:10 UTC
```

`↓↓` means the anchor rank is in the high tail, not merely that the percent is large. `incomplete` means the 12-bucket window is not on the view yet. A present window whose ranks are still immature says `1h activity: history building`.

### 3. Recently ended

```
BTC · calmed
22m ago: unusual rise
Price ↑↑ · OI ↓↓
Positions shrank during the rise
1h activity: history building
Event has ended
Data through 12:10 UTC
```

### 4. Data degraded

```
BTC · data incomplete
Current observability is insufficient; the absence of events cannot be claimed right now.
Data through 12:05 UTC
```

An open episode is still listed under that sentence. The 1h line is omitted while the tape is stale or degraded.

### 5. History still building

```
BTC · history building
Price/OI history 8.4d / 30d
Unusual states are not evaluated yet
1h activity: incomplete
Data through 12:05 UTC
```

### Details (event)

```
EVENT
EV-… — price + OI contraction down
<frozen description>
Detector state ended · reached triggered
Ended …: condition no longer met

Trigger bucket 12:05–12:10 UTC

MARKET
  price move: −0.50% · 2.0 pct of 30d (mature)
  range width: …
  price by venue: up — · down binance,bybit,okx

OI BY VENUE
  OI change: …
  OI by venue: …
  Direction only. Per-venue OI percents are not in this view.

FLOW
  taker delta: …
  long-side / short-side liquidations by venue: …

DATA
  Now …
  Rolling 1h …
  Reference price …
  Venues …
  Episodization STRICT_QUALIFICATION_V1
```
