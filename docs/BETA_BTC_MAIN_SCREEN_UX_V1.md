# Beta V0.2 — `/btc` main screen UX V1

Presentation only. The detector, `BETA_EVENT_RULES_V1`, the rules digest, push switches, readiness semantics, and the state-tape schema are unchanged.

**What this document describes:** the screen this repository renders after PR 1 of `BETA_BTC_MULTI_HORIZON_UX_V1.md` (language, Kyiv time, the `1h` line, the Event tab, and the 1h tab without an OI line).

**Not in this screen yet** (later steps of that document): OI over 1h/24h, the `24h` line and tab, "Changes vs previous 24h", and the D7 high-impact lines.

`docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md` remains the authority for anchors, episodization, and the rolling-1h percentile context. The new `horizons` block is a separate presentation projection (`BETA_HORIZON_1H_TOD_V0`). It is not detection.

## Product value

A five-second BTC chart already shows the price path. This screen does not replace that.

What it adds, and only when the tape supports it:

- the whole-dollar reference price and whether the frozen detector currently has an unusual state open, or one that ended inside the 2h memory window;
- the joint reading of that state's price and open interest;
- a 1h price change and volume/range ratios against the same UTC time of day. An immature baseline prints `n/a`. An incomplete window prints `1h: incomplete`.

On a calm screen that additive content is thin: the price, "nothing unusual is open", and the 1h line. That is an honest limitation. The PRICE_OI pilot classification is `BALANCE_FAILED`: the UI must not say that OI contraction predicts volatility, continuation, or reversal.

## 1. Language and time

- Per-user `ru` / `en`, default `ru`, stored on `beta_users.lang`. `/start` asks once (`[Русский] [English]`). `/lang` asks again. Every reply uses that language, from `beta/i18n.py`.
- Each `beta_btc_views` row stores the `lang` it was rendered in. The payload stays language-neutral.
- Displayed clocks are `Europe/Kyiv`, labelled `(Киев)` / `Kyiv`. Storage, windows, and baselines stay UTC.
- Russian titles: спокойно, необычно сейчас, затихло, событие завершено, накопление истории, данные неполные.
- Numbers: `ru` `112 450`, `−0,84%`, `$84 млн`; `en` `112,450`, `−0.84%`, `$84M`.

## 2. Information hierarchy

1. Title: `BTC <price> · <state>`. The price is `now.reference_price` in whole USD, omitted when null.
2. What was noticed, if anything.
3. Direction arrows and the frozen volume level word, from the anchor bucket.
4. One factual OI sentence. No mechanism the bucket does not support.
5. The `1h` line (price %, volume ×, range ×). No OI term in this pass.
6. Status and data-through on one line.
7. Disclaimer, once.

At most 8 lines plus that disclaimer.

## 3. User-visible states

Derived in the formatter from the existing view. Internal headlines stay in the stored payload.

| Presentation title | When |
|---|---|
| `BTC · data incomplete` | Headline is `DATA STALE`, `DATA DEGRADED`, or `DETECTOR NOT READY`. The price is included when `now.reference_price` is present (`DATA DEGRADED`) and omitted when `now` is null (`DATA STALE`). |
| `BTC · history building` | Headline is `HISTORY BUILDING`. |
| `BTC · unusual now` | An episode is open (`WATCH` or `EVENT ACTIVE`). |
| `BTC · calmed` | No open episode, and the retained last episode ended because the condition was no longer met. |
| `BTC · event ended` | No open episode, and the retained last episode ended for another reason. The body names that reason. |
| `BTC · calm` | No open episode and nothing retained. |

`EARLY`, `ARMED`, and `TRIGGERED` are not printed. A data-problem title wins over "calm".

## 4. What stays on Main

- The presentation title, with the price when it exists.
- For an open or retained episode: the short plain name, how long ago it ended, and whether it is still active or has ended. Reading line from the **anchor bucket**: one arrow for direction, volume as the frozen level word (`normal` omitted), then the factual OI sentence. No short-covering or long-unwind narrative.
- The `1h` line on every non-fail-closed screen, including calm. Incomplete window: `1ч: неполные данные` / `1h: incomplete`. Immature baseline: `н/д` / `n/a` in place of the ratio. A field that cannot be computed is dropped, never shown as 0.
- Status and data-through share one line: `Still active · data 15:10 Kyiv` / `Ещё активно · данные 15:10 (Киев)`.
- The disclaimer, once. Russian text: `Экспериментальная закрытая бета. Только описание состояния рынка — не инвестиционный совет и не указание к сделке.`

Other open episodes are one extra line: `Also open: seller-initiated flow`.

**Fail-closed (`DATA STALE` / `DATA DEGRADED`).** After the fail-closed sentence the screen shows only the last known detector fact, then `Current event state unavailable`, then the data-through line. No reading line, no OI sentence, no `Still active` / `Event has ended`, no `Also open`, no `1h` line.

English fail-closed sentence, unchanged: `Current observability is insufficient; the absence of events cannot be claimed right now.`

Russian: `Текущих данных недостаточно: отсутствие событий сейчас подтвердить нельзя.`

## 5. Buttons and tabs

- `[Событие]` / `[Event]` only when an episode is open or retained. Callback `o:<view_pk>:event`.
- `[1ч]` / `[1h]` outside fail-closed. Callback `o:<view_pk>:1h`. There is no 24h button in this pass.
- `[Готовность]` / `[Readiness]` keeps `r:latest`, shown only when some family is not `READY`.
- The first press sends one Details message. A tab press on that message (`e:<view_pk>:<tab>`) edits it in place. Both callbacks are at most 64 bytes.
- A tab renders only the persisted payload of that `/btc` row, in the `lang` stored on the row. It does not read live state.
- Each open writes `beta_details_opens (view_pk, tab, lang, opened_at)`. No user id.

### Event tab

Anchor bucket only. The duplicated "Now" 5m block is gone. Per-venue OI percents come from the anchor snapshot's `venue_raw.oi_change_pct`, persisted on the anchor view. Volume uses the frozen level word, including `normal`. Liquidations are per venue (§7 of the multi-horizon document): Binance amounts are prefixed `≥` with the one-line footnote; a missing per-venue value prints `н/д` / `n/a`, never `$0`. Last line: `ref EV-… · view <id8>`. No percentile ranks, no `EARLY` / `ARMED` / `TRIGGERED`, no version strings in the body. Those stay in the payload.

### 1h tab

Price, range, and volume with the 1h time-of-day baseline (`usual for this hour` / `от обычного для этого часа`). Taker flow is the sum of the 5m deltas. Long and short liquidations are separate per-venue lines, under the same §7 rules. Funding is the tape median at the view bucket, shown as a percent. No OI line and no D7 lines in this pass.

## 6. 1h baseline

Median of rolling-1h values whose window end lies within ±30 minutes of the same UTC time of day, on each of the prior 30 UTC days. Mature at 20 contributing days, per metric. Display: one decimal and `×`; values below 1 are shown; 10 or more prints `10×+`. The price on the main line is the signed percent move, not a ratio.

The block is stored under `horizons` with version `BETA_HORIZON_1H_TOD_V0` and its own digest. `BETA_CONTEXT_1H_V0` is unchanged. The baseline is never used for detection.

## 7. Wording

`assert_descriptive` checks every rendered string. Russian text is checked against the English list and the Russian list. Neither list is relaxed. Banned in both languages: pushing, dumping, whales, short covering, long unwind, healthy, continuation, reversal, and the Russian equivalents in the multi-horizon document §9.

## 8. Examples

Plain text. The title is bold in Telegram. The disclaimer follows each message and is omitted below. Times are Kyiv (EET in this March example, UTC+2).

### Calm

```
BTC 83,500 · calm
No unusual state now
1h: −0.8% · vol 2.1× · range 2.3×
No notable event in the last 2h · data 14:05 Kyiv
```

### Unusual now

```
BTC 83,500 · unusual now
Price ↓ · OI ↓
Open interest fell during the drop
1h: −0.8% · vol 2.1× · range 2.3×
Still active · data 14:10 Kyiv
```

### Data stale, last known episode (price omitted because `now` is null)

```
BTC · data incomplete
Current observability is insufficient; the absence of events cannot be claimed right now.
Last known (14:10): unusual drop
Current event state unavailable
data 14:10 Kyiv
```

### Event tab

```
EVENT · unusual drop
Still active · since 14:05 Kyiv
Why it was noticed (14:05–14:10):
  Price −0.50% · range 0.62% · volume $310M (high)
  OI −0.42%: binance −0.61% · bybit −0.35% · okx −0.12%
  Taker flow: sellers, net $41M
  Long liquidations: binance ≥$2.1M · bybit $3.4M · okx $600K
  Short liquidations: binance ≥$0 · bybit $0 · okx $0
≥ — lower bound: Binance does not report every liquidation.
ref EV-… · view 1a2b3c4d
```

### 1h tab

```
LAST HOUR · 14:10–15:10 Kyiv
Price −0.84% · range 1.12% (2.3× usual for this hour)
Volume $1.9B (2.1× usual for this hour)
Taker flow: sellers, net $84M
Long liquidations: binance ≥$8M · bybit $10M · okx $3M
Short liquidations: binance ≥$1M · bybit $2M · okx $400K
Funding now 0.006% (venue median)
≥ — lower bound: Binance does not report every liquidation.
ref EV-… · view 1a2b3c4d
```
