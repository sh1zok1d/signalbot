# DH2 — pooled directional hypotheses on six coins: owner decision and design

**Status:** `OWNER_DECISION_RECORDED (2026-10-04) / DESIGN_FROZEN_BEFORE_DATA`
**Program:** `DIRECTIONAL_HYPOTHESES_DH2`, search family `SF-DH2`
**Builds on:**
- `DIRECTIONAL_HYPOTHESES_DECISION_V1.md`: endpoints, bar, statuses and contract;
- `DH1_RESULT.md`: DH1 showed that the binding constraint is the number of events.

**Design source of truth:** `scripts/research/dh2/constants.py`

## 1. Owner decision (2026-10-04)

After DH1, the owner chose «Пул монет 2020–2024»: the same level and sharp-move rules on BTC, ETH, BNB, XRP, DOGE and SOL (Binance USD-M), to get enough independent events for a 3–6 pp directional effect. Every DH1 rule carries over: endpoints, the 3 pp + Brier bar, the «Гипотеза»/«Проверено» statuses, free data only, no 2025/2026 objects and no deploy without a go.

**Atlas override, recorded explicitly.**
- **The rule.** The atlas routes `INFORMATIONALLY_WEAK` cells with "do not run now; no proxy or pooling to manufacture N".
- **The override.** The owner's choice overrides this for DH2 only.
- **The cost.** The claim changes population: it is about six major coins, not about BTC alone, and applying it to BTC assumes the effect is the same across coins.
- **The safeguards, frozen before any data:**
  1. **Symbol fixed effects.** Every coin has its own base rate.
  2. **A symbol-heterogeneity gate.** It mirrors the epoch gate: a Q-test over coins, with a permutation of week×coin blocks across coins. A cell fails as `HETEROGENEOUS_UNEXPLAINED` when heterogeneity is significant and at least one coin is significantly opposite. When the gate's power is below 0.5, it is `NOT_ASSESSABLE` and does not fail the cell.
  3. **BTC on its own.** BTC's own estimate is always reported beside the pooled one. Product wording says "на шести крупных монетах", never "на BTC".

## 2. Cells (at most 3 per card; DH1 L2 is not repeated)

| Cell | Card | State vs comparator | Endpoint |
|---|---|---|---|
| DH2-L1 | DH2-L | spot taker net flow over the hour into the first touch points in the approach direction, vs not | level hold 4h |
| DH2-L3 | DH2-L | level price not traded during the 24h before the touch (stale), vs traded | level hold 4h |
| DH2-B2 | DH2-B | spot share of spot+perp quote volume during the sharp move is above its prior-24h share, vs not | barrier first-passage 4h (X = half of the 4h corridor half-width) |

**Not carried over:**
- **DH1-L2 (confluence)** was tested and is practically null.
- **DH1-B1** is degenerate as a sign state. A relative version would be a new candidate, which the owner did not select.

**Level population.** PDH, PDL, PWH, PWL, PMH, PML and the previous day's POC, under the product's first-touch rules (`beta/levels.py`). Round numbers are excluded: the product's 1000-USD step has no meaning for ETH, XRP, DOGE or SOL, and any per-coin step rule would be invented here.

**Nuisance terms:**
- the 4h block of the UTC hour;
- terciles within each coin of: 24h realized volatility, prior 4h aligned return, and (for L1 and B2) perp taker imbalance; B2 also takes the move-size tercile;
- the level-type group (day / week / month / POC);
- coin fixed effects.

**Estimand, inference and bar: as DH1.**
- **Estimand:** the state coefficient of a linear probability model.
- **Clusters:** ISO weeks pooled across coins and cut at year boundaries, so cross-coin co-movement inside a week sits in one cluster.
- **Testing:** 2000 bootstrap draws; Holm within each card.
- **Bar:** |shift| ≥ 3 pp and Brier skill > 0.
- **Feasibility rule:** discovery MDE ≤ 6 pp, smaller arm ≥ 300, at least 3 years with both arms ≥ 30.

## 3. Surfaces

| Surface | Coins and instruments | Period |
|---|---|---|
| Discovery | Binance USD-M perps and spot, six coins: BTC from `CORE_BTC_BINANCE_V0`; the others from Binance Vision 5m klines | from each coin's first full listing month plus one month of warm-up, to 2024-12-31 |
| Replication, DH2-L3 | Binance spot 5m klines BTC, ETH, BNB, XRP (price only; spot instead of perp is a declared instrument difference) | 2017-09 (or listing + 1 month) .. 2019-12 |
| Replication, DH2-L1 and DH2-B2 | BTC only: BitMEX XBTUSD trades + Binance spot (the DH1 surface); no free pre-2020 alt perp flow is pinned | 2017-09..2019-12 |
| Prospective | live tracking on all six coins after the freeze (Binance Vision daily klines) | stopping rule as DH1 |

**Exposure:**
- Alt 2020–2024 has not been used for any level hypothesis. Its only prior use is the divergence panel 2022-11..2024-12, for divergence/exhaustion/microstructure rows.
- BTC 2020–2024 is product- and DH1-exposed for levels. It is a discovery surface here, which the contract allows.

## 4. Red team

- **Pooling as rescue.** DH1-L1, L3 and B2 were never run, so no outcome is being rescued. Pooling changes the population, as stated in §1.
- **Crypto co-movement.** Coins move together, so their events are not independent. Pooled weekly clusters absorb same-week co-movement, and the effective N is reported.
- **Coin composition.** DOGE and SOL are far more volatile than BTC. Within-coin terciles and coin fixed effects absorb the level differences. The symbol gate catches a sign that flips between coins.
- **Venue artefacts.** BNB is the venue's own token. This is recorded and not modelled; the symbol gate would flag it.
