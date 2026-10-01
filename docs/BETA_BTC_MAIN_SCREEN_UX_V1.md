# Beta V0.2 — `/btc` main screen UX V1

Presentation only. The detector, `BETA_EVENT_RULES_V1`, the rules digest, push switches, readiness semantics, and the state-tape schema are unchanged.

**What this document describes:** the screen this repository renders after PR 2 of `BETA_BTC_MULTI_HORIZON_UX_V1.md` (language, Kyiv time, the `1h` and `24h` lines, OI over those horizons, "Changes vs previous 24h", the Event / 1h / 24h tabs, and `/terms`).

**Not in this screen yet:** the D7 high-impact lines (PR 3).

`docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md` remains the authority for anchors, episodization, and the rolling-1h percentile context. The `horizons` block is a separate presentation projection (`BETA_HORIZON_TOD_V1`). It is not detection.

## Product value

A five-second BTC chart already shows the price path. This screen does not replace that.

What it adds, and only when the tape supports it:

- the whole-dollar reference price and whether the frozen detector currently has an unusual state open, or one that ended inside the 2h memory window;
- the joint reading of that state's price and open interest;
- a 1h price change, volume/range ratios against the same UTC time of day, and the aggregate OI percent;
- a 24h price change, volume ratio against the 30-day same-time median, and the aggregate OI percent. An immature baseline prints `n/a`. An incomplete window prints `1h: incomplete` or `24h: incomplete`.

On a calm screen that additive content is thin: the price, "nothing unusual is open", and the 1h line. That is an honest limitation. The PRICE_OI pilot classification is `BALANCE_FAILED`: the UI must not say that OI contraction predicts volatility, continuation, or reversal.

## 1. Language and time

- Per-user `ru` / `en`, default `ru`, stored on `beta_users.lang`. `/start` asks once (`[Русский] [English]`). `/lang` asks again. Every reply uses that language, from `beta/i18n.py`.
- Each `beta_btc_views` row stores the `lang` it was rendered in. The payload stays language-neutral.
- Displayed clocks are `Europe/Kyiv`, labelled `(Киев)` / `Kyiv`. Storage, windows, and baselines stay UTC.
- Russian titles: спокойно, необычно сейчас, затихло, событие завершено, бот собирает историю, данные неполные. Technical terms stay English in the Russian UI: OI, Funding, Delta.
- Numbers: `ru` `112 450`, `−0,84%`, `$84 млн`; `en` `112,450`, `−0.84%`, `$84M`.

## 2. Information hierarchy

1. Title: `BTC <price> · <state>`. The price is `now.reference_price` in whole USD, omitted when null.
2. What was noticed, if anything.
3. Direction arrows and the frozen volume level word, from the anchor bucket.
4. One factual OI sentence. No mechanism the bucket does not support.
5. The `1h` line (price %, volume ×, range ×, OI %) and the `24h` line (price %, volume ×, OI %).
6. Status and data-through on one line.
7. Disclaimer, once.

At most 8 lines plus that disclaimer.

## 3. User-visible states

Derived in the formatter from the existing view. Internal headlines stay in the stored payload.

| Presentation title | When |
|---|---|
| `BTC · data incomplete` | Headline is `DATA STALE`, `DATA DEGRADED`, or `DETECTOR NOT READY`. The price is included when `now.reference_price` is present (`DATA DEGRADED`) and omitted when `now` is null (`DATA STALE`). |
| `BTC · history building` | Headline is `HISTORY BUILDING`. Russian title: `бот собирает историю`. |
| `BTC · unusual now` | An episode is open (`WATCH` or `EVENT ACTIVE`). |
| `BTC · calmed` | No open episode, and the retained last episode ended because the condition was no longer met. |
| `BTC · event ended` | No open episode, and the retained last episode ended for another reason. The body names that reason. |
| `BTC · calm` | No open episode and nothing retained. |

`EARLY`, `ARMED`, and `TRIGGERED` are not printed. A data-problem title wins over "calm".

## 4. What stays on Main

- The presentation title, with the price when it exists.
- For an open or retained episode: the short plain name and whether it is still active or has ended. Reading line from the **anchor bucket**: one arrow for direction, volume as the frozen level word (`normal` omitted), then the factual OI sentence. No short-covering or long-unwind narrative.
- **One time reference** (amended 2026-10-01 after the owner's live review). An ended event is one line: the Kyiv window of the whole qualifying run, the plain name, when it ended and how long ago: `14:00–14:10: sharp drop · ended 14:15, 7m ago` / `14:00–14:10: резкое падение · завершилось в 14:15, 7 мин назад`. The run starts at the first qualifying bucket (the episode opens when the streak reaches its entry streak, so for build-up that is two buckets before it opens). The reading line names its 5m bucket: `5m 14:05–14:10: Price ↓ · OI ↓`. When the title already says `calmed`, the data line does not repeat `Event has ended`; it still names the technical endings (gap, not evaluable, version change, duration cap).
- The `1h` and `24h` lines on every non-fail-closed screen, including calm. Incomplete window: `1ч: неполные данные` / `1h: incomplete` and `24ч: неполные данные` / `24h: incomplete`. Immature baseline: `н/д` / `n/a` in place of the ratio. A 24h volume that is not 288/288 prints `(неполные)` / `(partial)` and no ratio. A field that cannot be computed is dropped, never shown as 0. OI on these lines is the median of venue percents from the Stage-1 as-of read, never a USD sum.
- Status and data-through share one line: `Still active · data 15:10 Kyiv` / `Ещё активно · данные 15:10 (Киев)`.
- The disclaimer, once. Russian text: `Экспериментальная закрытая бета. Только описание состояния рынка — не инвестиционный совет и не указание к сделке.`

Other open episodes are one extra line: `Also open: seller-initiated flow`.

**Fail-closed (`DATA STALE` / `DATA DEGRADED`).** After the fail-closed sentence the screen shows only the last known detector fact, then `Current event state unavailable`, then the data-through line. No reading line, no OI sentence, no `Still active` / `Event has ended`, no `Also open`, no `1h` line, no `24h` line.

English fail-closed sentence, unchanged: `Current observability is insufficient; the absence of events cannot be claimed right now.`

Russian: `Текущих данных недостаточно: отсутствие событий сейчас подтвердить нельзя.`

## 5. Buttons and tabs

- `[Событие]` / `[Event]` only when an episode is open or retained. Callback `o:<view_pk>:event`.
- `[1ч]` / `[1h]` and `[24ч]` / `[24h]` outside fail-closed. Callbacks `o:<view_pk>:1h` and `o:<view_pk>:24h`.
- `[Готовность]` / `[Readiness]` keeps `r:latest`, shown only when some family is not `READY`.
- The first press sends one Details message. A tab press on that message (`e:<view_pk>:<tab>`) edits it in place. Both callbacks are at most 64 bytes.
- A tab renders only the persisted payload of that `/btc` row, in the `lang` stored on the row. It does not read live state.
- Each open writes `beta_details_opens (view_pk, tab, lang, opened_at)`. No user id.

### Event tab

Anchor bucket only. The duplicated "Now" 5m block is gone. Per-venue OI percents come from the anchor snapshot's `venue_raw.oi_change_pct`, persisted on the anchor view. Volume uses the frozen level word, including `normal`. Liquidations are per venue (§7 of the multi-horizon document): positive Binance amounts are prefixed `≥` with the one-line footnote, and a Binance zero prints `$0*` with its own footnote; `Still active · since` and `Why it was noticed` both start at the first qualifying bucket and cover the whole run, and the metrics are headed by their 5m bucket; a missing per-venue value prints `н/д` / `n/a`, never `$0`. Venue names are `Binance · Bybit · OKX`. Last line: `Термины: /terms` / `Terms: /terms`. Episode and view ids stay in the payload and are not printed. No percentile ranks, no `EARLY` / `ARMED` / `TRIGGERED`, no version strings in the body.

### 1h tab

Price, range, and volume with the 1h time-of-day baseline (`usual for this hour` / `от обычного для этого часа`). OI is the as-of aggregate and the per-venue percents. Delta is the sum of the 5m deltas, printed `Delta: −$84M (sellers)` / `Delta: −$84 млн (продавцы)`. Long and short liquidations are separate per-venue lines, under the same §7 rules. Funding is the tape median at the view bucket, shown as a percent. No D7 lines in this pass. Last line: `Terms: /terms`.

### 24h tab

Price with the window high and low, range and volume against the 30-day same-time median, OI, Delta, per-venue liquidations, Funding now and the 24h average, then "Changes vs previous 24h" (at most 3 lines, or the none-line). A partial volume prints the dollar amount with `(partial)` / `(неполные)` and no ratio. An incomplete 24h window marks every venue liquidation with `≥`. Last line: `Terms: /terms`.

## 6. 1h baseline

Median of rolling-1h values whose window end lies within ±30 minutes of the same UTC time of day, on each of the prior 30 UTC days. Mature at 20 contributing days, per metric. Display: one decimal and `×`; values below 1 are shown; 10 or more prints `10×+`. The price on the main line is the signed percent move, not a ratio.

The 24h baseline is the median of one rolling-24h value per prior UTC day, ending at the same UTC time of day, mature at 20 days. Price and range need at least 282 of 288 buckets with the first and last present. The volume ratio needs 288 of 288.

The block is stored under `horizons` with version `BETA_HORIZON_TOD_V1` and its own digest. It covers 1h, 24h, and the OI as-of read. `BETA_CONTEXT_1H_V0` is unchanged. The baseline is never used for detection. "Changes vs previous 24h" thresholds live in `config/beta_v0.yaml` `horizon_changes` and do not enter the rules digest.

## 7. Wording

`assert_descriptive` checks every rendered string. Russian text is checked against the English list and the Russian list. Neither list is relaxed. Banned in both languages: pushing, dumping, whales, short covering, long unwind, healthy, continuation, reversal, and the Russian equivalents in the multi-horizon document §9.

## 8. Examples

Plain text. The title is bold in Telegram. The disclaimer follows each message and is omitted below. Times are Kyiv (EET in this March example, UTC+2).

### Calm

```
BTC 83,500 · calm
No unusual state now
1h: −0.8% · vol 2.1× · range 2.3× · OI −0.6%
24h: −1.9% · vol 1.3× · OI +2.1%
No notable event in the last 2h · data 14:05 Kyiv
```

### Unusual now

```
BTC 83,500 · unusual now
5m 14:05–14:10: Price ↓ · OI ↓
Open interest fell during the drop
1h: −0.8% · vol 2.1× · range 2.3× · OI −0.6%
24h: −1.9% · vol 1.3× · OI +2.1%
Still active · data 14:10 Kyiv
```

### Data stale, last known episode (price omitted because `now` is null)

```
BTC · data incomplete
Current observability is insufficient; the absence of events cannot be claimed right now.
Last known (14:10): sharp drop
Current event state unavailable
data 14:10 Kyiv
```

### Event tab

```
EVENT · sharp drop
Still active · since 14:00 Kyiv
Why it was noticed (14:00–14:10):
Readings for the 5m bucket 14:05–14:10:
  Price −0.50% · range 0.62% · volume $310M (high)
  OI −0.42%: Binance −0.61% · Bybit −0.35% · OKX −0.12%
  Delta: −$41M (sellers)
  Long liquidations: Binance ≥$2.1M · Bybit $3.4M · OKX $600K
  Short liquidations: Binance $0* · Bybit $0 · OKX $0
≥ — lower bound: Binance does not report every liquidation.
* — $0 from incomplete data: it does not mean there were no liquidations.
Terms: /terms
```

### 1h tab

```
LAST HOUR · 14:10–15:10 Kyiv
Price −0.84% · range 1.12% (2.3× usual for this hour)
Volume $1.9B (2.1× usual for this hour)
OI −0.6%: Binance −0.9% · Bybit −0.4% · OKX +0.1%
Delta: −$84M (sellers)
Long liquidations: Binance ≥$8M · Bybit $10M · OKX $3M
Short liquidations: Binance ≥$1M · Bybit $2M · OKX $400K
Funding now 0.006% (venue median)
≥ — lower bound: Binance does not report every liquidation.
Terms: /terms
```
