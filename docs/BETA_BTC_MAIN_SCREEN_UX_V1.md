# Beta V0.2 — `/btc` main screen UX V1

Presentation only. The detector, `BETA_EVENT_RULES_V1`, push switches, and the persisted `/btc` view model are unchanged. This document specifies what the main Telegram screen says. `docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md` remains the authority for the view model, anchors, and the rolling 1h.

**Next pass:** `BETA_BTC_MULTI_HORIZON_UX_V1.md` specifies the next `/btc` UX pass: tabs, `ru`/`en`, Kyiv time, 1h/24h and the D7 context. It is not implemented yet. This document stays authoritative for what runs until that pass updates it.

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
- Reading line from the **anchor bucket** (why it was noticed), not from the latest 5m print. One visual grammar:
  - An arrow is **direction only**: exactly one `↑` or `↓` from the sign of Price, OI or taker flow. Arrows are never repeated and never encode a percentile tier, so there is no hidden intensity scale to learn, and immature history looks the same as mature history.
  - Volume is a word, never an arrow: the frozen context level (`Volume elevated`, `Volume high`, `Volume extreme`). `normal` and immature levels are omitted.
  - Unusualness is not repeated on the main screen. For the conjunction events the anchor is in the detector's own tail by definition, so an intensity mark would be almost constant. The exact values and `pct of 30d` ranks are in Details.
- One sentence for a price+OI event, from the signs only. It names the observed open-interest field and nothing more (OI is not a count of individual positions):
  - price up, OI down: `Open interest fell during the rise`
  - price down, OI down: `Open interest fell during the drop`
  - both up: `Open interest rose during the rise`
  - price down, OI up: `Open interest rose during the drop`
  - If that same anchor bucket has at least 2 eligible top-tail liquidation votes on the matching side, the sentence names the elevated liquidations. It does not say they caused the move, and there is no short-covering or long-unwind wording.
- Rolling 1h volume and range as level words. If both labels are immature: `1h activity: history building`. If the window is missing: `1h activity: incomplete`.
- `Still active`, `Event has ended`, or the data-gap sentence. Never under `DATA STALE` / `DATA DEGRADED` (see below).
- `Data through HH:MM UTC` when the view has it.
- The existing disclaimer, once.

Other open episodes are one extra line: `Also open: seller-initiated flow`.

**Fail-closed event block (`DATA STALE` / `DATA DEGRADED`).** Current observability is insufficient, so the screen may not present any episode as current. After the fail-closed sentence it shows only the last known detector fact and its time, then `Current event state unavailable`:

- open episode: `Last known (HH:MM): <plain name>`, where HH:MM is the end of the episode's last qualifying bucket;
- retained ended episode: `Last known (HH:MM): <plain name>, ended`, where HH:MM is the episode's end.

No reading line, no OI sentence, no `Still active` / `Event has ended`, no `Also open`, no 1h line. The historical measurements stay behind the Details button.

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

- Descriptive and joint, not causal. `Open interest fell during the rise` is allowed. `Positions shrank`, `Shorts were liquidated`, `short covering`, `healthy trend`, `continuation`, and `reversal` are not.
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
| Arrows | Anchor `view` metrics: `value` sign only |
| Volume word | Anchor `volume_notional_usd` `rank` + `tier` via `level_label` (the frozen `context.label_*` cuts) |
| Last known (stale / degraded) | `active_episode.last_bucket` + 5m, or `last_event.terminal_at` |
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
Price ↓ · OI ↓ · Volume high
Open interest fell during the drop
1h activity: incomplete
Still active
Data through 12:10 UTC
```

Each arrow is the sign only. `Volume high` is the frozen level word; a normal volume is omitted. `incomplete` means the 12-bucket window is not on the view yet. A present window whose ranks are still immature says `1h activity: history building`.

### 3. Recently ended

```
BTC · calmed
22m ago: unusual rise
Price ↑ · OI ↓
Open interest fell during the rise
1h activity: history building
Event has ended
Data through 12:10 UTC
```

### 4. Data stale or degraded

No episode:

```
BTC · data incomplete
Current observability is insufficient; the absence of events cannot be claimed right now.
Data through 12:05 UTC
```

With an episode that was open at the last good bucket (identical for `DATA STALE` and `DATA DEGRADED`):

```
BTC · data incomplete
Current observability is insufficient; the absence of events cannot be claimed right now.
Last known (12:10): unusual drop
Current event state unavailable
Data through 12:10 UTC
```

With a retained ended episode:

```
BTC · data incomplete
Current observability is insufficient; the absence of events cannot be claimed right now.
Last known (12:15): unusual drop, ended
Current event state unavailable
Data through 12:15 UTC
```

The episode is never presented as current: no arrows, OI sentence, `Still active` or `Also open`. The 1h line is omitted while the tape is stale or degraded.

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
