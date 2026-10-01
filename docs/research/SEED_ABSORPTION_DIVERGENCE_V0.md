# Seed — absorption plus regular divergence after a decline (V0)

**Status:** `SEED_RECORDED / NOT_A_CARD / NO_OUTCOME_OPENED`
**Backlog entry:** `SEED-0001` in `HYPOTHESIS_SEED_BACKLOG.md`
**Recorded:** 2026-10-01 (UTC timestamp = the commit that adds this file)
**Origin:** the owner's own discretionary trading rule, used before this research program. It is recorded as stated, without improvements. It is not derived from any Signalbot result.

```
MARKET_DATA_OPENED_FOR_THIS_SEED = false
DEFINITIONS_FROZEN               = false
TIED_TO_TWAP_OUTCOME             = false
CARD_REGISTERED                  = false
```

## 0. Known provenance (facts from the owner only)

This is what the owner's practice establishes, without reconstruction. Everything else in this file is interpretation and stays unfrozen.

**Market and timeframes:**
- BTC and ETH perpetuals;
- 1h, 4h and 1D.

**Indicators:**
- RSI 14 and 21; the divergence was usually present on both;
- MACD with the default preset; the exact parameters are confirmed at design freeze;
- CVD;
- rule: at least 2 of 3 families;
- order-book "green bars" as the sign of strong bid support.

**Usage:**
- both ordinary and hidden divergences;
- used from about 2024.

**Trade management:**
- stop beyond the previous swing high or low, depending on the construction;
- partial close near the next level, the rest trailed;
- manual exit when the divergence breaks down.

> **NOT FROZEN:** the exact definition of the bid/ask indicator and its source. "Hyblock bid/ask 0–5% spot" is reconstructed from one screenshot and from memory. It is confirmed by the owner, or replaced, before any design freeze.

> **Evidence levels:** 2023–2024 = retrospective evidence. Future frozen data = prospective confirmation.

## 1. The rule as the owner used it

**Sequence:**
1. A pronounced decline.
2. Then an observable buyback (absorption) begins. Real buying has to start; a divergence drawn by an indicator alone does not count.
3. At least 2 of 3 indicator families show bullish divergence against price:
   - **RSI:** periods 14 and 21;
   - **MACD:** default preset; exact parameters are confirmed at design freeze;
   - **CVD:** cumulative taker delta.

**Timeframe.** The owner's prior is that a higher timeframe means a larger structural break and a larger or longer subsequent move. This is a separate axis to test, not a claim.

## 2. Mechanism framing

**Proposed mechanism:**
- aggressive selling stops pushing price lower efficiently;
- buy response appears;
- momentum and flow indicators diverge from the price low;
- that marks a change in the supply/demand balance.

**The claim is a combination, not "divergence = entry".** The joint state should be followed by a more favourable price distribution than either part alone.

**Comparators**, all frozen before outcomes:

| Arm | State |
|---|---|
| A | buyback + ≥2/3 divergence |
| B | buyback without ≥2/3 divergence |
| C | ≥2/3 divergence without buyback |
| D | a comparable decline with neither |

The finding requires A to beat both B and C. A beating D alone is ordinary mean reversion after a drop.

**V1 framing (planned):**
- `INCREMENTAL`, directional, with a cost-based practical bar;
- nuisance variables: prior realized volatility, time of day, and the decline itself as the lagged target.

## 3. Proximity to closed work

These closed cards are close. This seed is not a rescue of any of them: its provenance is prior owner practice, and its object is the conjunction.
- `H02_FAILED_BREAKOUT_MEAN_REVERSION` (killed).
- `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION` (rejected): exhaustion after an impulse.
- `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN` (rejected): CVD is cumulative taker imbalance.

**Consequences:**
- the card must state its distance from these three;
- Binance 2020–2024 discovery is labeled historically exposed for nearby questions;
- confirmation must be time-disjoint (BitMEX 2016–2019 trades, Binance spot 2017–2019, or a prospective surface under V1 §7).

## 4. Measurement problems to settle before any outcome

1. **Pivot lookahead.** A swing low is only confirmed some bars later. The decision time must be after confirmation, and the divergence must be computed from information available then.
2. **"Pronounced decline".** A frozen definition is needed, for example a drawdown of at least k× recent ATR or a tail percentile of the N-bar return.
3. **"Buyback" must be price-based.** Example: price reclaims a fixed share of the last down-swing, or closes above a local level. It must stay separate from the CVD divergence, otherwise one signal is counted twice.
4. **Divergence definition per family.**
   - Is RSI 14 OR 21, or both?
   - What swing distance, and what minimum indicator difference?
5. **Search surface.** Timeframes × families × periods × horizons is large, and V1 allows at most 3 primary cells per card.
   - The primary should be the timeframe and horizon the owner actually traded.
   - Other timeframes are separate cards, or a single pre-declared monotonic check across timeframes.
6. **Support.** Multi-condition states are rare on higher timeframes. Feasibility counts must come before any outcome.

## 5. Questions for the owner (provenance, before any data)

1. Which timeframe or timeframes did you actually trade this on?
2. What holding horizon or exit did you use (target, stop, time)?
3. How did you judge a "good buyback" in practice?
4. RSI 14 and 21: did both have to diverge, or either?
5. Did you use it on BTC only, or also on altcoins? On spot or perps?
6. Roughly when (which years) did you trade it?

The answers are appended here, with their date, before any definition is frozen.

### Owner answers — 2026-10-01 (before any data)

| # | Answer (owner's words, translated) |
|---|---|
| 1 | Timeframes traded: 1h, 4h, 1D. |
| 2 | Example with a hidden bearish divergence: stop beyond the previous high; target around the next resistance levels; close 50% there, trail the rest. Time exit: close manually when the divergence breaks, or get stopped out. |
| 3 | Buyback was judged on a monitoring site by its bars ("палки"). Small buybacks show nothing; large ones show green bars, meaning strong buying. No numeric thresholds: a utility did it. |
| 4 | Both RSI 14 and 21 had to diverge, and usually both did. |
| 5 | BTC and ETH only, futures. |
| 6 | Traded since 2024. The owner believes the structure existed earlier. |

**Implications for the card (not frozen):**
- **Timeframes.** The primary should be 1h or 4h. 1D will almost certainly lack support over 2020–2024; feasibility counts decide.
- **Estimand that mirrors the practice.** Use risk multiples. The stop is beyond the decline's swing low (bullish case). The outcome is whether price reaches +1R or +2R before the stop, within a frozen time cap. The divergence-break exit and the resistance-level targets are discretionary, so the time cap and fixed R targets stand in for them.
- **Buyback is flow-based in the owner's practice.** Green bars are large net taker-buy bars. The faithful definition is a net-taker-buy spike above a frozen trailing percentile after the low.
- **Risk of overlap.** That flow-based buyback overlaps with CVD divergence, with H05 (taker imbalance) and with the beta's Delta extremes. The card must keep the arms separable. A price-reclaim buyback can be a pre-declared secondary.
- **Hidden divergences.** The example is a hidden (continuation) divergence. This seed is about regular bullish divergence after a decline (reversal). Hidden divergences are a different mechanism and would be a separate seed (open question 7).
- **Exposure.** The owner traded this in 2024, so 2024 is owner-exposed. Discovery on Binance 2020–2024 carries that label. Confirmation must be time-disjoint: BTC on BitMEX 2016–2019 or Binance spot 2017–2019, or a prospective surface. ETH 2020–2024 on the same period is a robustness check only.
- **Instruments.** BTC and ETH perps, which matches `CORE_BTC_BINANCE_V0` and `CORE_ETH_BINANCE_V0`.

**Open questions:**
- 7: Was the rule traded on regular divergences, hidden ones, or both?
- 8: Which monitoring site or utility showed the bars, and what did a bar measure (spot or perp delta, which exchanges)?

### Owner answers to 7–8 — 2026-10-01 (before any data)

**7. Both.** The owner traded regular and hidden divergences. Hidden divergences are a continuation mechanism, not a reversal one, so they are a separate seed (`SEED_HIDDEN_DIVERGENCE_CONTINUATION_V0.md`) and are never mixed into this one, not even as a flag.

**8. A screenshot of the owner's TradingView layout** (interpretation, not frozen; see §0), BTCUSDT spot Binance, 15m. Not stored in the repository. It shows Hyblock indicators:
- `<Hyblock> Bid… 0% 5% Spot Filter1 OR Filter2`: an **order-book bid/ask imbalance within 0–5% of price**, spot. It shows red bars (ask-heavy) during the decline, then green bars (bid-heavy) right after the low. The owner pointed at these green bars as the "buyback bars".
- `<Hyblock> Volume … 100k–1M Binance Spot`: CVD of large trades.
- `<Hyblock> Volume … 100–1k Binance Spot`: CVD of small trades.
- `<Hyblock> Whale vs Retail Delta`.

**Correction to the earlier implication.** The "buyback" the owner watched is **resting order-book liquidity (bids within 5%)**, not executed taker flow. So the faithful definition is order-book based. It also does not double-count with CVD divergence, which is good. Known weakness: resting bids can be placed and pulled (spoofing).

**Data availability, checked 2026-10-01 against `data.binance.vision`.**

| Observable | Source | Coverage |
|---|---|---|
| Order-book depth at ±1…±5% from price | futures/um daily `bookDepth` (`timestamp, percentage, depth, notional`, about every 30 s) | from 2023-01 only |
| Spot order-book depth | `spot/daily/bookDepth` | none: no spot `bookDepth` archive exists |
| Large-trade and small-trade CVD | `aggTrades` (spot and futures) | 2020–2024, and spot from 2017-08 |

**Consequence:**
- The faithful order-book version has only 2023–2024 history outside the protected window, and 2024 is owner-exposed.
- That leaves 2023 for discovery, and no time-disjoint historical surface for confirmation, only a prospective one. A prospective surface inside 2026 needs a protected-data decision.
- A flow-based proxy (large-trade CVD turning up, or net taker buying after the low) is testable on 2020–2024, with BitMEX and Binance spot 2016/2017–2019 for confirmation. But it is not the observable the owner used.
- The choice between the faithful version, the proxy, or the proxy first and the faithful version prospectively is an owner decision when the card is written.

**Owner note on 2024 — 2026-10-01.** "Use 2024 too. I saw it, but I don't remember it." This is recorded as provenance.
- **2023–2024 is retrospective evidence.** It is used fully. It is never called a confirmatory holdout, because the rule reached us as a working scheme from that period, and that selection carries information about it whatever is remembered.
- **Future frozen data is prospective confirmation.** The rule is recorded in advance and the definitions are frozen. New episodes arrive after the freeze, so the result could not have shaped the construction.
- **What 2023–2024 can show.** A retrospective result that reproduces, survives the comparators and has a practical size is a strong reason to continue. It is not the final proof for the product.

**Three information layers.** The owner's scheme combines three different layers, not three correlated indicators:
1. **Order-book intent and liquidity:** bid support within 0–5% appears after the decline.
2. **Executed flow:** CVD.
3. **Price and momentum response:** divergence in RSI and MACD.

**Programme (owner-endorsed shape, 2026-10-01):**

| Track | Content | Evidence label |
|---|---|---|
| A. Exact historical test | BTC and ETH perps 2023–2024: the bid/ask-depth construction plus the owner's divergence rules | `RETROSPECTIVE_EVIDENCE` |
| B. Long-history surrogate | A point-in-time flow replacement for book support, 2020–2024 or earlier | `SURROGATE`; never "reproduced the owner's strategy" |
| C. Prospective confirmation | After the freeze, collect new episodes automatically and change nothing until a pre-set N or date (V1 §7) | `PROSPECTIVE_CONFIRMATION` |

**Notes on the tracks:**
- **Track A** uses the perp book depth in the Binance archive. The Hyblock indicator the owner watched is spot. They are close but not identical observables.
- **Track C** inside the protected 2025/2026 window needs its own protected-data decision.
- **Regular and hidden divergences** stay separate in every track: different mechanisms, possibly opposite signs. Mixing them can average to nothing.

## 6. Routing

The hidden-divergence continuation seed is a separate seed: `SEED_HIDDEN_DIVERGENCE_CONTINUATION_V0.md`.

This seed does not change `NEXT_UNIT`. The TWAP feasibility unit runs first. After it, the owner decides when this seed becomes a card under `HYPOTHESIS_EVALUATION_CONTRACT_V1`, alongside the statement matrix.

The hidden-divergence continuation seed is a separate seed: `SEED_HIDDEN_DIVERGENCE_CONTINUATION_V0.md`.
