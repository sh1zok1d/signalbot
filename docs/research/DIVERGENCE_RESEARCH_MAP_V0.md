# Divergence research map V0

**Status:** `PROGRAM_MAP / NO_DATA_OPENED`
**Date:** 2026-10-02
**Owner direction:** turn SEED-0001 into a research program on divergences, map it before any new outcome test, then choose the next card by feasibility.
**Machine twin:** `DIVERGENCE_RESEARCH_MAP_V0.json`

```
MARKET_DATA_OPENED_FOR_THIS_MAP  = false
PROTECTED_2025_2026_OPENED       = false
PROTECTED_SPEND_DECIDED          = false (proposal in section 7; needs an explicit owner decision)
NEW_CARD_REGISTERED              = false
NEXT_UNIT                        = DIVERGENCE_PANEL_FEASIBILITY_V0 (outcome-blind)
```

## 1. What SEED-0001 does and does not give us

**Source.** `SEED0001_EXPLORATORY_OUTCOME_RESULT.md`, labelled exploratory / underpowered, on 2023–2024.

| Quantity | BTC | ETH |
|---|---|---|
| A − B: divergence added inside support, adjusted | +0.042 [−0.099, +0.184] | −0.089 [−0.278, +0.099] |
| A − C: support added to divergence, adjusted | +0.148 [−0.037, +0.332] | −0.138 [−0.378, +0.101] |
| raw rates A / B / C / D | 0.556 / 0.502 / 0.413 / 0.522 | 0.406 / 0.511 / 0.521 / 0.497 |
| raw interaction (A − B) − (C − D) | +0.16 | −0.13 |

The last row is arithmetic on published raw rates only. No inference was run on it, and none may be on 2023–2024.

**Reading.**
- **Divergence inside support.** The increment of divergence inside support (A − B) is close to zero on BTC and negative on ETH.
- **Divergence without support.** The visible BTC pattern is that divergence without support (C) underperforms, not that A outperforms: A is only +0.03 over D.
- **The two symbols disagree.** ETH reverses both contrasts.
- **What follows.** SEED-0001 is therefore not evidence for the hypothesis below; it is where the hypothesis came from. The hypothesis is motivated by mechanism, and it must be tested on data SEED-0001 never touched.

## 2. Program question and first hypothesis

**Program question.** Does regular divergence add information to a market context that already exists? The program does not ask whether divergence "works".

**H-DIV-1** (the owner's hypothesis, recorded before any new data): regular bullish divergence is close to useless on its own. Its value appears when it marks seller exhaustion inside an already confirmed support state.

**Estimand.** The interaction contrast `(A − B) − (C − D)` on the frozen bracket endpoint, where:
- A = support with divergence;
- B = support without divergence;
- C = divergence without support;
- D = neither.

The hypothesis predicts both of these:
- A − B > 0, meaning divergence helps inside support;
- C − D ≤ 0, meaning divergence alone adds nothing.

**Deeper framing.** The construction may not need the word "divergence" at all:

> price down + downside momentum weakening + selling pressure weakening + support persisting → a higher chance of a local reversal.

A classic MACD/RSI divergence may be only one visual symptom of that state. The program therefore stores mechanism features (section 3) beside the divergence flag.

**Power note (structural, before any count).** An interaction contrast spans four cells. For the same N it needs roughly four times the information of a single two-arm contrast. Section 6 sizes this.

## 3. Mechanism features (discovery features, never selection rules)

Every feature is computed point-in-time at the decision time T. Features describe events. They do not filter them until a later card freezes a rule.

| Feature | Sketch | Source | Coverage |
|---|---|---|---|
| price-leg depth | (max high over leg − low) / ATR | klines | UM 2020-01+, spot 2017-08+, BitMEX 2016–2019 |
| strength of the new low | (low_j − low_i) / ATR | klines | same |
| momentum change | ΔRSI14, ΔRSI21, ΔMACD line between pivots (ATR-normalized) | klines | same |
| pivot distance | i − j bars | klines | same |
| ATR-normalized move, RV | RV24, ATR14 | klines | same |
| OI change into the low | Δ open interest over the leg and over the last N hours | Binance UM `metrics`, 5m (native grain; never presented as 1m) | archive from 2020-09 |
| taker flow | net taker delta over the leg and before T; CVD slope | klines `taker_buy`; BitMEX trades | UM 2020-01+, BitMEX 2016–2019 |
| liquidation stress | not in the public archive (`liquidationSnapshot` returns 404 for 2021 and 2023) | — | **DATA_GAP**; only a proxy: price down × OI down × volume spike |
| bid support | (bid − ask)/(bid + ask) within 5%, persistence after the low | UM `bookDepth` | 2023-01+ for BTC, ETH, SOL, XRP, BNB, DOGE (checked); none before 2023 |
| higher-timeframe trend | 4h / 1D EMA slope, distance from a 1D high | klines | as klines |

## 4. When divergence fails (questions to test, not rules)

The edge, if any, might appear only when:
- price makes a new low and sellers are exhausted, meaning the selling flow into the low is weaker than on the previous leg;
- OI falls into the low, so positions close and no fresh shorts open;
- a liquidation flush has already happened (proxy only);
- the bid holds after the low.

The edge might disappear when the new low comes with rising OI or aggressive selling. Each of these is a separate pre-registered conditional question with its own `TEST_FAMILY_ID`. None is a rescue of SEED-0001.

## 5. Tracks and divergence types

| Track | Observable | Discovery surface | Confirmation surface | Label |
|---|---|---|---|---|
| A: book-faithful | UM `bookDepth` within 5% | 2023–2024. BTC/ETH outcomes are consumed; other symbols are exposed by correlation and are discovery-only. | a protected spend window (section 7), or the prospective stream | `RETROSPECTIVE_PROXY_TO_OWNER_OBSERVABLE` |
| B: long-history proxy | support replaced by a frozen flow/OI proxy | Binance UM 2020-01..2022-12, never used for divergence | BitMEX XBTUSD 2016–2019 (time-disjoint) | `SURROGATE`; never "the owner's strategy" |
| C: prospective | as Track A | — | decisions from 2026-10-05 (SEED-0001 prospective leg, frozen) | `PROSPECTIVE_CONFIRMATION` |

**Rules across tracks.**
- **No mixing.** Tracks are never pooled into one experiment.
- **What Track B is for.** It can show quickly, and with hundreds of episodes, whether the mechanism is worth digging into. It cannot confirm Track A.

**Divergence types.** Each type gets its own card. They are never mixed, not even as a flag.
1. **Regular bullish** comes first, because SEED-0001 already exists and the mechanism is clear.
2. **Hidden bullish** is already `SEED-0002` in the backlog (`SEED_HIDDEN_DIVERGENCE_CONTINUATION_V0.md`), a continuation mechanism.
3. **Regular bearish and hidden bearish** come later, as separate objects.

**Numbering.** `SEED-0002` is taken. The next regular-bullish card is a new object, `SEED-0003` or a new research id. It is not "SEED-0002".

## 6. Metrics battery (frozen per card before outcomes)

**One primary per card** (V1 allows at most 3 primary cells). The rest is secondary or descriptive, defined before opening:

| Metric | Role |
|---|---|
| P(+1R before −1R within the cap) | primary candidate (continuity with SEED-0001) |
| P(+2R before −1R) | secondary |
| forward R-return at the cap | secondary |
| MFE / MAE in R units | descriptive |
| time to MFE | descriptive; tests "better timing, not a better win rate" |
| adverse excursion before the reversal (MAE before the MFE peak) | descriptive |

Several metrics do not mean several primaries. A secondary that looks better never replaces the primary.

## 7. Data surfaces and the proposed protected spend

| Surface | Status now | Role in the program |
|---|---|---|
| BitMEX XBTUSD 2016–2019 | unopened for divergence; used by D2 | Track B replication |
| Binance UM 2020-01..2022-12 | discovery era, not used for divergence | Track B discovery |
| Binance UM 2023–2024, BTC and ETH 1h | **consumed** by SEED-0001 (exploratory) | feature discovery only; never confirmation |
| Binance UM 2023–2024, other symbols | outcomes unopened, but exposed by correlation | panel discovery and feasibility only |
| **2025-01-01 .. 2026-08-11** (last decision; T + 96h ≤ 2026-08-15) | **protected** | **proposed spend**: the confirmation surface for one frozen divergence card |
| 2026-08-16 .. 2026-08-25 17:20 | **E1-RUN-001 sealed holdout** (load-bearing frozen experiment) | untouchable; any window touching it is excluded |
| 2026-08-26 .. 2026-10-04 | protected | not proposed (short; next to the E1 window) |
| 2026-10-05 onward | SEED-0001 prospective stream | prospective only |

### The owner's argument and its assessment

**The argument.** A holdout has value only while it is kept for a concrete decision. Keeping 2025–2026 forever "for the grail", while rare signals cannot be studied without it, turns data into a museum piece.

**Assessment.** It is sound, provided the spend is tied to one frozen question.

**Conditions before any 2025–2026 byte is read:**
1. **Card frozen first.** A divergence card is frozen as a twin prereg: detector, arms, costs, endpoints, statistics and interpretation, together with its outcome-blind feasibility.
2. **Feasibility from outside the window.** The feasibility comes from 2023–2024 layouts and extrapolation, not from 2025–2026 bytes. A spend that is about 15% powered is not authorized; that would burn the holdout on another `INCONCLUSIVE`.
3. **The E1 window stays sealed.** `[2026-08-16, 2026-08-25 17:20)` is never read. That includes trailing baselines: decisions whose 30-day book baseline would reach into it are excluded.
4. **D2.** D2's 2025 reservation is released or explicitly shared by an owner decision. Today D2 records 2025 as its primary confirmation surface and 2026 as its second reserved surface. Its one-year confirmation power is 0.011, so the reservation is dormant. Exposure cannot tune D2's frozen rule, but a later D2 run on 2025 would carry the label "surface exposed to unrelated research".
5. **One primary on the pooled window.** The window is one pooled primary; 2025 and 2026 are reported only as temporal consistency.
6. **Policy documents updated in the same decision.** These follow the owner's decision:
   - `AGENTS.md` and `PROJECT_STATUS.md`, which say "Protected Binance 2025/2026 remain sealed";
   - the GV0R02 compiler's protected-window policy, which needs a new policy version, not an edit of V1.

### Feasibility of the spend for a SEED-0001-like card (outcome-blind estimate)

This uses the BTC 2023–2024 rate of about 18.8 A episodes a year. The spend window is about 1.6 years, so roughly 30 A episodes.

| Design | A episodes | Power at 10 pp | MDE (80%) | Source |
|---|---:|---:|---:|---|
| SEED-0001 replica, BTC only | ~30 | ~0.15 | ~0.30 | SEED-0001 prospective planning, 30-A prefix |
| BTC + 5 other symbols with bookDepth since 2023 | ~180 | ≤ 0.5 (optimistic; cross-symbol co-movement lowers it) | ~0.15–0.20 (optimistic) | stacked-layout extrapolation (SEED-0001 feasibility report) |
| the same panel, interaction contrast | ~180 A plus the other cells | lower still | larger | four-cell contrast |

**Conclusion.** Spending 2025–2026 on a BTC-only replica cannot answer the 10 pp question. A pre-declared multi-symbol panel can plausibly answer a 20 pp question, and perhaps 15 pp. Whether that is worth the holdout is the owner's choice, made before opening. The number comes from the next unit.

## 8. Order of work

1. **`DIVERGENCE_PANEL_FEASIBILITY_V0`** (outcome-blind; no 2025–2026 byte):
   - **Panel rule.** The panel is fixed before counting: BTC, ETH, SOL, XRP, BNB, DOGE. These are the UM perps with checked `bookDepth` from 2023-01-01. No symbol is added or dropped after counting.
   - **Counts.** The SEED-0001 detector, unchanged, on 2023–2024 for each symbol: A/B/C/D counts and distinct dates.
   - **Dependence.** Cross-symbol week clustering and same-day co-occurrence.
   - **Power.** For the main contrasts and for the interaction contrast at 10, 15 and 20 pp, extrapolated to the spend window.
   - **No outcome** is computed.
2. **Track B design** (in parallel, outcome-blind):
   - a frozen flow/OI support proxy on Binance UM 2020–2022, with replication on BitMEX 2016–2019;
   - counts and power.
3. **Owner decision** on the protected spend, under the conditions in section 7.
4. **Freeze the next card** (`SEED-0003` or a new id) as a twin prereg with its feasibility, then open the authorized surface once.

## 9. Not done in this unit

- No market data opened.
- No 2025–2026 metadata or bytes fetched.
- No card registered.
- No change to SEED-0001, its prospective leg, D2, E1 or the compiler.
