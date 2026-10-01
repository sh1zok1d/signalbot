# Hypothesis seed backlog

**Status:** `ACTIVE_BACKLOG / NOT_AN_EXECUTION_QUEUE`
**Created:** 2026-10-01

> **The backlog is not an execution queue.** A seed may sit here for months. It enters the research pipeline only after a novelty check, a feasibility check (`GV0R02` V1) and a separate design freeze under `HYPOTHESIS_EVALUATION_CONTRACT_V1`. Nothing here is run one after another because it exists.

The backlog stores ideas as **mechanism seeds**. The question is never "does indicator X work?". It is "what market mechanism should this reflect, and which observable states would it create?".

## Sources

| Source | What it is | Rule |
|---|---|---|
| `TRADER_HEURISTIC` | Real schemes traders used, such as the owner's | Record exactly as practised; no improvements at capture |
| `INDICATOR_DERIVED` | A known indicator or pattern | Ask which mechanism it is supposed to reflect, then seed that mechanism |
| `MICROSTRUCTURE` | TWAP, absorption, OI/price disagreement, liquidation stress, order-book imbalance, and similar | Name the observable and its data availability |
| `FAILED_DESCENDANT` | A descendant of a closed hypothesis | Only with a genuinely new mechanism, measurement or regime. Never a rescue of a closed null. State the closed card and what is new. |
| `EXTERNAL_STRATEGY` | Public ideas: papers, GitHub, bots, TradingView scripts | Convert to a mechanism seed first; never test the script as is |

## Tags

**`PROVENANCE`:**
- `USER_USED_BEFORE_RESEARCH`: an independent origin before any Signalbot test. Prefer these.
- `RESEARCH_DERIVED`: created inside the program. State from what.
- `EXTERNAL`: from a public source. Give the reference.

**`MECHANISM_FAMILY`:**
- `EXECUTION`, `LIQUIDITY`, `POSITIONING`, `MOMENTUM_EXHAUSTION`, `VOLATILITY`;
- `EVENT_RESPONSE`, `ORDER_BOOK`, `CROSS_MARKET`, `CALENDAR_CLOCK`, `PATH_MORPHOLOGY`.

The family tag keeps the backlog honest. Twenty-five "indicator → return" variants are one family, not twenty-five ideas.

**`STATUS`:**
- `SEED_ONLY`: recorded, no design yet.
- `READY_FOR_DESIGN`: passed novelty and feasibility; waiting for an owner decision to design.
- `DEFERRED`: blocked by data or priority. Give the reason.
- `REJECTED`: duplicate, rescue, or unmeasurable. Give the reason.

A seed that becomes a card points to its card, preregistration and result. It is never deleted.

## Seed card template

```
SEED_ID:
ORIGIN:                 (source category + reference)
PROVENANCE:
MECHANISM_FAMILY:
DATE_CAPTURED:

RAW_IDEA:
MECHANISM:
OBSERVABLE_STATE:
WHY_IT_MIGHT_MATTER:

KNOWN_RELATED_TESTS:
WHAT_IS_ACTUALLY_NEW:

DATA_NEEDED:
POSSIBLE_COMPARATOR:

STATUS:
DETAIL:                 (link to a longer seed file, if any)
```

## Seeds

### SEED-0001 — regular divergence after a decline with order-book support

```
SEED_ID:              SEED-0001
ORIGIN:               TRADER_HEURISTIC (owner's discretionary practice)
PROVENANCE:           USER_USED_BEFORE_RESEARCH (since about 2024)
MECHANISM_FAMILY:     ORDER_BOOK + MOMENTUM_EXHAUSTION
DATE_CAPTURED:        2026-10-01

RAW_IDEA:             After a pronounced decline, strong bid support appears in the
                      book ("green bars"), and at least 2 of 3 families show regular
                      bullish divergence (RSI 14 and 21, MACD default preset, CVD).
MECHANISM:            Selling stops pushing price efficiently; resting demand appears;
                      momentum and flow diverge from the price low. The supply/demand
                      balance changes (reversal).
OBSERVABLE_STATE:     book bid dominance within a few % of price + divergence at a
                      point-in-time confirmed swing low
WHY_IT_MIGHT_MATTER:  It combines three information layers: book intent, executed flow
                      and price/momentum response.

KNOWN_RELATED_TESTS:  H02 (killed), H03 and H05 (rejected): close, not rescued
WHAT_IS_ACTUALLY_NEW: the conjunction with an order-book support layer; its provenance

DATA_NEEDED:          Binance UM bookDepth (+-1..5 %, from 2023-01); aggTrades for CVD;
                      klines. The bid/ask indicator definition and source are NOT FROZEN.
POSSIBLE_COMPARATOR:  A both / B book support only / C divergence only / D decline only

STATUS:               SEED_ONLY
DETAIL:               SEED_ABSORPTION_DIVERGENCE_V0.md
```

Evidence levels: 2023–2024 = retrospective evidence. Future frozen data = prospective confirmation.

### SEED-0002 — hidden divergence continuation

```
SEED_ID:              SEED-0002
ORIGIN:               TRADER_HEURISTIC (owner's discretionary practice)
PROVENANCE:           USER_USED_BEFORE_RESEARCH (since about 2024)
MECHANISM_FAMILY:     MOMENTUM_EXHAUSTION (continuation)
DATE_CAPTURED:        2026-10-01

RAW_IDEA:             A hidden divergence in the trend direction, with the same
                      families and the at-least-2-of-3 rule. Example (bearish): price
                      makes a lower high while the indicator makes a higher high.
MECHANISM:            A pullback inside a trend fails to restore momentum, and the
                      trend resumes (continuation, not reversal).
OBSERVABLE_STATE:     a trend + a pullback swing with hidden divergence, confirmed
                      point-in-time
WHY_IT_MIGHT_MATTER:  Its sign may be opposite to SEED-0001. Mixing the two could
                      average to nothing.

KNOWN_RELATED_TESTS:  H04 TREND_PULLBACK_CONTINUATION (rejected): close, not rescued
WHAT_IS_ACTUALLY_NEW: the divergence-confirmed pullback; its provenance

DATA_NEEDED:          klines; aggTrades for CVD
POSSIBLE_COMPARATOR:  pullbacks in a trend without hidden divergence; matched trend states

STATUS:               SEED_ONLY
DETAIL:               SEED_HIDDEN_DIVERGENCE_CONTINUATION_V0.md
```

Evidence levels: 2023–2024 = retrospective evidence. Future frozen data = prospective confirmation.
