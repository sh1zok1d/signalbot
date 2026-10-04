# Directional hypotheses for the bot — owner decision V1 (program DH1)

**Status:** `OWNER_DECISION_RECORDED (2026-10-04) / PROGRAM_DH1_OPEN`
**Date:** 2026-10-04
**Program:** `DIRECTIONAL_HYPOTHESES_DH1`, search family `SF-DH1`
**Branch:** `claude/signalbot-scalper-feedback-yenp8q`, from `main` at `b1c97b2`
**Builds on:**
- `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md`, which lifted the predictive product freeze on 2026-10-03 and kept the ban on direct trade calls;
- `docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1.md`, which still governs every card;
- `docs/research/SIGNALBOT_RESEARCH_ATLAS_V1.md`, the research map.

## 1. What the owner decided (verbatim, 2026-10-04)

> «мне нужно как и полезное для описания и будущих предположений об развитиях рынка. чтобы бот мог делать эти предположения ссылаясь на гипотезы. так и то, что поможет определять вероятность дальнейшего направления движений. не предсказывать с максимальной точностью (хотя если такое есть, то я не против) а скорее .. Пример: сейчас у нас есть уровни, да? И указано вот "после первого касания цена выше уровня в ...% случаев". как этот процент можно увеличить? ну по уверенности и тд. Мне нужно гипотезы которые смогут дать боту возможность писать "в следующие 4ч вероятность движения выше ...% (гипотеза)". … Да, это решение владельца.»

Typos in the quote are corrected; the wording is otherwise unchanged.

**Answers to the clarifying questions (same day).** The owner chose the recommended option in each case:

| Question | Answer |
|---|---|
| What counts as "a move up in 4h" | **level hold** (price beyond the level 4h after its first touch: the product's existing metric) **and** **barrier first-passage** (+X is reached before −X within 4h, X tied to the current volatility) |
| How the bot shows a hypothesis that is not yet confirmed | with the status **«Гипотеза»**: the number, "обычно", N and an interval, labelled "found on 2020–2024, not confirmed". A confirmed result is labelled «Проверено». A rejected result is never shown as a probability, only in `/research` |
| Confirmation data | the earlier era **2017–2019** (free archives: Binance spot from 2017, BitMEX trades) **and live tracking** of every probability the bot shows |
| Practical bar | **3 percentage points** against "обычно" (the product's existing materiality floor) **plus calibration**: the Brier score with the state must beat the score without it |

## 2. Decision fields

```
PROGRAM                            = DIRECTIONAL_HYPOTHESES_DH1 (search family SF-DH1)
RESEARCH_TARGET                    = directional probabilities that the bot can state with a status
DIRECTIONAL_RESEARCH_OUTCOMES      = allowed for this program (owner, 2026-10-04)
CLAIM_TYPE                         = INCREMENTAL (contract V1 §2: any directional claim)
ENDPOINTS                          = LEVEL_HOLD_4H; BARRIER_FIRST_PASSAGE_4H
PRACTICAL_BAR                      = |nuisance-adjusted shift| >= 3 pp AND Brier skill > 0
DISPLAY_TIERS                      = «Проверено» (SUPPORTED_*), «Гипотеза» (PROMISING_PROTOTYPE); others: /research only
DISCOVERY_SURFACE                  = Binance USD-M BTCUSDT (CORE_BTC_BINANCE_V0) + Binance spot BTCUSDT, 2020-01..2024-12
CONFIRMATION_SURFACES              = earlier era 2017-09..2019-12 (BitMEX XBTUSD trades + Binance spot BTCUSDT); live tracking
DATA_COST                          = free public archives only; no paid API
OBJECTS_2025_2026_USED             = none (product-exposed for levels and range; never a confirmation surface here)
DIRECT_TRADE_CALLS                 = forbidden (unchanged)
E1_RUN_001 / B2_06 / V3            = untouched
NEW_RESEARCH_PROGRAMS_AUTHORIZED   = overridden for this program only
DEPLOY                             = needs a separate owner go
```

## 3. What this decision changes

- **Research may target direction.** Until now research served the product with non-directional context claims, and directional cells were saturated or null. For this program a directional outcome may be the research target, because the bot is now allowed to state directional probabilities (`PRODUCT_DECISION_V2` §2). The claim type is `INCREMENTAL`, so the contract's nuisance baseline applies in full: time of day, prior realized volatility, the lagged target, and prior net taker flow for flow claims.
- **A second display tier.** Contract V1 §9 promotes only `SUPPORTED_*` results. The owner adds a labelled tier for a discovery result that passed every gate (`PROMISING_PROTOTYPE`) but is not yet replicated. It is shown as «Гипотеза» with its base, N and interval, and the line that it is not confirmed. It moves to «Проверено» only after the frozen replication passes. A failed replication removes the number.
- **The practical bar is a probability shift.** 3 percentage points of the event probability against the matched "обычно", plus a positive Brier skill score. This is the owner's product bar. It is not a claim that 3 pp beats trading costs, and the bot never presents it as an edge.

## 4. What stays

- **No direct trade calls:** no long/short now, buy/sell, entries, targets or take-profits (`PRODUCT_DECISION_V2` §3).
- **Honesty rule:** every number has N and "обычно" beside it; every forecast carries its own tracked accuracy.
- **The contract:**
  - twin preregistration before any outcome;
  - at most 3 primary cells per card, Holm within the card;
  - dependence-aware inference;
  - the epoch-heterogeneity gate;
  - time-disjoint replication with the same frozen rule;
  - no rescue.
- **Data rules:**
  - no lookahead;
  - no 2025/2026 object;
  - nothing from E1-RUN-001 or B2-06.
- **Sealed verdicts stay sealed:** MARKET-01..06, H01–H05, B2-01..05, the D series, R03, G01 and the divergence line. A hypothesis that sits near one of them is closed at red team rather than tested as its rescue (see `DH1_CANDIDATES.md`).
- **No deploy** without a separate owner go.

## 5. What the bot may say, and when

| Result | Bot text |
|---|---|
| `SUPPORTED_UNCONDITIONAL` / `SUPPORTED_CONDITIONAL` (discovery and replication pass) | «Проверено:» the probability with "обычно", N and interval, the data it was measured on |
| `PROMISING_PROTOTYPE` (discovery passes, replication pending or live-only) | «Гипотеза:» the same fields plus "найдено на 2020–2024, не подтверждено" |
| Anything else | no probability; the unit is listed in `/research` with its verdict |

Live tracking scores every probability the bot shows against what happened; the bot's own accuracy line comes from it.

## 6. Records

- Candidates, red team and dedupe: `docs/research/DH1_CANDIDATES.md`.
- Data inventories: `docs/research_data/DH1_*`.
- Feasibility and preregistration: `docs/research/DH1_FEASIBILITY.{md,json}` and `docs/research/DH1_PREREG.json`, written before any outcome.
- Results: `docs/research/DH1_RESULT.{md,json}`.
- Code and tests: `scripts/research/dh1/`, `tests/research/test_dh1.py`.
