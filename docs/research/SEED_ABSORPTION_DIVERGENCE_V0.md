# Seed — absorption plus indicator divergence after a decline (V0)

**Status:** `SEED_RECORDED / NOT_A_CARD / NO_OUTCOME_OPENED`
**Recorded:** 2026-10-01 (UTC timestamp = the commit that adds this file)
**Origin:** the owner's own discretionary trading rule, used before this research program. It is recorded as stated, without improvements. It is not derived from any Signalbot result.

```
MARKET_DATA_OPENED_FOR_THIS_SEED = false
DEFINITIONS_FROZEN               = false
TIED_TO_TWAP_OUTCOME             = false
CARD_REGISTERED                  = false
```

## 1. The rule as the owner used it

**Sequence:**
1. A pronounced decline.
2. Then an observable buyback (absorption) begins. Real buying has to start; a divergence drawn by an indicator alone does not count.
3. At least 2 of 3 indicator families show bullish divergence against price:
   - **RSI:** periods 14 and 21;
   - **MACD:** standard 12/26/9;
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

## 6. Routing

This seed does not change `NEXT_UNIT`. The TWAP feasibility unit runs first. After it, the owner decides when this seed becomes a card under `HYPOTHESIS_EVALUATION_CONTRACT_V1`, alongside the statement matrix.
