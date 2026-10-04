# DH3 — five cards of three hypotheses (direction and range): owner decision, candidates, red team, design

**Status:** `OWNER_DECISION_RECORDED (2026-10-04) / DESIGN_FROZEN_BEFORE_DATA`
**Program:** `DIRECTIONAL_AND_RANGE_DH3`, search family `SF-DH3`
**Design source of truth:** `scripts/research/dh3/constants.py`
**Builds on:**
- `DIRECTIONAL_HYPOTHESES_DECISION_V1.md`: statuses, contract and data rules;
- `DH1_RESULT.md` and `DH2_RESULT.md`: directional states on levels and moves were null at the 3 pp scale.

## 1. Owner decision (2026-10-04)

The owner gave these instructions: «закрывай этот ресерч, мержи. Открывай новый. Придумай 3 карты по 5 гипотез. Точно так же по схеме доведи до экзекьюта. Мне финальные результаты только.»

**Answers to the clarifying questions:**

| Question | Answer |
|---|---|
| Card size | **5 cards of 3.** Contract V1 §6 allows at most 3 primary cells per card. |
| What the hypotheses predict | **Direction and range:** 6 directional cells and 9 range cells. The project's earlier successes were all range or activity effects. |
| OI / funding history 2020–2024 | **Allowed** (BTC, the product's own surface) |
| Heavy free data | **Allowed**, streamed, with only aggregates committed |

**What did not change:**
- no 2025/2026 objects;
- no E1, B2-06 or V3;
- no direct trade calls;
- no deploy without a go;
- the contract applies in full.

**What the owner's OI/funding answer covers.** Only Binance OI metrics are used. Funding and the premium index stay out:
- MARKET-04H adjudicated the premium-index archive `BLOCKED` (publication time and revision status unproven);
- B2-06 is blocked on funding publication latency.

## 2. Endpoints and bars

| Endpoint | Definition (decision time T = close of the decision bar; outcome bars T+1..T+48) | Bar |
|---|---|---|
| `RANGE_4H` | log((max high − min low) / close at T) | \|shift\| ≥ log 1.15 (the product's range materiality) and out-of-sample MSE skill > 0 |
| `UP_FIRST_4H` | 1 if close·(1+X) is reached before close·(1−X), 0 if the reverse, 0.5 if neither or the same bar; X = half of the 4h corridor half-width (DH1) | \|shift\| ≥ 3 pp and Brier skill > 0 |
| `CONT_FIRST_4H` | as UP_FIRST in the direction d of the triggering move | 3 pp and Brier skill > 0 |
| `LEVEL_HOLD_4H` | the product's metric (close 4h after the touch beyond the level) | 3 pp and Brier skill > 0 |

**Claim type.** Every cell is `INCREMENTAL`, so range claims must beat the volatility nuisance. The nuisance always includes:
- the 4h block of the UTC hour;
- the 24h realized-volatility tercile;
- the lagged target tercile: the prior 4h log range for range cells, and the prior 4h return in the endpoint's direction for directional cells.

Card-specific terms are listed with each cell.

**Inference and gates.**
- **Estimand:** the state coefficient of a linear model.
- **Inference:** ISO-week cluster bootstrap (2000 draws), pooled across coins; Holm within each card.
- **Gates:**
  - **Epoch heterogeneity** (years);
  - **Coin heterogeneity** for pooled cards;
  - **Feasibility rule:** discovery MDE at most twice the bar, smaller arm ≥ 300, at least 3 years with both arms ≥ 30.

**Classes.** As DH1. For range cells, `NO_INCREMENTAL_STRUCTURE` requires the whole 95 % CI inside ±log 1.15.

## 3. Cards and cells (15 primary cells)

### Card DH3-P — positioning (Binance USD-M BTCUSDT OI metrics 5m, 2020-09..2024-12; decision every hour)

| Cell | State vs comparator | Endpoint | Extra nuisance | Mechanism |
|---|---|---|---|---|
| P1 `LEVERAGE_LOADING` | among hours whose prior 4h range is in the bottom tercile: 4h OI change in the top tercile vs not | RANGE_4H | — | leverage built in a quiet market is released in a larger move |
| P2 `DELEVERAGING` | 1h OI change in the bottom decile vs other hours | RANGE_4H | \|1h return\| tercile | a forced flush clears leverage, so volatility decays faster than the regime implies |
| P3 `CROWD_LONG` | global long/short account ratio, z-scored against its trailing 30 days: top quintile (crowd long) vs bottom quintile (crowd short) | UP_FIRST_4H | prior 24h return tercile | the crowd is on the wrong side (contrarian) |

**Point-in-time rule.** The metrics snapshot labelled with bar j's open time is used at bar j's close (the product's rule).

### Card DH3-L — liquidity (Binance USD-M bookDepth ±1 %, six coins, 2023-01..2024-12)

| Cell | State vs comparator | Endpoint | Extra nuisance | Mechanism |
|---|---|---|---|---|
| L1 `THIN_BOOK` | notional within ±1 % at T vs its trailing 7-day median of hourly values: bottom quintile vs rest | RANGE_4H | coin | thin books amplify moves |
| L2 `BID_HEAVY_BOOK` | log(bid notional −1 % / ask notional +1 %): top quintile vs bottom quintile | UP_FIRST_4H | coin | price drifts toward the thinner side, or is held by the heavier one (two-sided test) |
| L3 `BOOK_NOT_RECOVERED` | 30 min after a sharp move (DH1 rule): ±1 % notional relative to just before the move, bottom tercile vs rest | RANGE_4H from T' = move end + 30 min | move-size tercile, coin | liquidity that has not come back keeps volatility up |

**Point-in-time rule.** The last snapshot at or before T is used.

**Exposure.** bookDepth 2023–2024 is exposed for MICROSTRUCTURE rows: SEED-0001 used the ±5 % imbalance on BTC/ETH, and the divergence panel used all six coins. It is discovery-only here; confirmation is live only. L2 is a ±1 %, unconditional, all-hours state, not SEED-0001's ±5 % support state inside divergence episodes.

### Card DH3-O — options (Deribit DVOL hourly, BTC and ETH, 2021-04..2024-12)

| Cell | State vs comparator | Endpoint | Extra nuisance | Mechanism |
|---|---|---|---|---|
| O1 `IMPLIED_ABOVE_REALIZED` | log(DVOL-implied 4h σ / realized 4h σ from the prior 24h): top tercile vs rest | RANGE_4H | coin | options price risk the recent tape has not shown yet |
| O2 `DVOL_JUMP` | 1h log change of DVOL: top decile vs rest | RANGE_4H | \|1h return\| tercile, coin | option buyers bid for protection before moves |
| O3 `UP_VOL_REGIME` | correlation of hourly ΔlogDVOL and Δlog price over the prior 24h: > 0 vs ≤ 0 | UP_FIRST_4H | prior 24h return tercile, coin | when volatility rises with price, rallies are demand-led (calls bid) and continue |

**Point-in-time rule.** The hourly candle whose start is T − 1h (closed by T) is used.

### Card DH3-V — levels extended (six coins pooled, Binance 2020–2024; replication spot BTC/ETH/BNB/XRP 2017–2019)

| Cell | State vs comparator | Endpoint | Extra nuisance | Mechanism |
|---|---|---|---|---|
| V1 `SESSION_EXTREME` | first touch of the last completed Asia/EU/US session high or low within 24h after the session, vs 2 random control levels per event at distances drawn from the real distance distribution (the product's control method) | LEVEL_HOLD_4H | coin, session | session extremes collect stops, so a touch runs through them |
| V2 `KEY_LEVEL_RANGE` | first touch of PDH/PDL/PWH/PWL/PMH/PML/POC vs first touch of 2 random control levels per real level (product method) | RANGE_4H | coin, level-type group | stops at watched levels widen the next hours |
| V3 `RETEST` | second touch of PDH/PDL on the same UTC day after a retreat of at least X, vs first touches of PDH/PDL | LEVEL_HOLD_4H | coin, level type | a retested level has less liquidity left and breaks more often |

### Card DH3-S — spot↔perp at one second (Binance aggTrades BTCUSDT USD-M and spot, 2020–2024)

**Stress hour.** An hour whose perp log range is in the top decile of the surface. Decision T is the hour's end.

**Lead score.** Built from 1-second last-trade log returns within the hour, k = 1..3 s:

Σ [corr(perp_t, spot_t+k) − corr(spot_t, perp_t+k)]

| Cell | State vs comparator | Endpoint | Extra nuisance | Mechanism |
|---|---|---|---|---|
| S1 `SPOT_LED_STRESS` | spot-led (score < 0) vs perp-led stress hours | RANGE_4H | — | spot-led stress is real repositioning and keeps volatility up; perp-led stress is a leverage flush that fades |
| S2 `SPOT_LED_STRESS_DIR` | the same states | CONT_FIRST_4H (d = sign of the hour's return) | \|hour return\| tercile | spot-led stress continues |
| S3 `LARGE_PERP_PRINTS` | number of perp aggTrades ≥ 1 M USD in the stress hour: top tercile vs rest | RANGE_4H | — | large aggressive orders mark informed or forced flow that is not finished |

**Replication.** None in history: tick lead/lag needs both venues. Live tracking only.

## 4. Candidates closed at red team (no data read)

| ID | Candidate | Why closed |
|---|---|---|
| X1 | Premium index / funding extreme → direction | MARKET-04H: premium archive `BLOCKED` (PIT unproven); B2-06: funding publication latency |
| X2 | Large-print buy/sell imbalance → direction | H05 closed; B2-05 governance forbids formula-changed taker children |
| X3 | Spot whales vs perp whales → direction | the spot-confirmation family was null in DH1/DH2 |
| X4 | OI change on a level approach → hold | DH1-X2 closure (OI-continuation neighbourhood) |
| X5 | CME gap fill (Friday close level touched after the weekend) | about 260 weekends on 2020–2024, so MDE ≈ 12 pp; recorded as `INFORMATIONALLY_WEAK` before data |
| X6 | Binance–Bybit price gap → range | MARKET-06 venue-dislocation observable (REPEATED_NULL family); not a new mechanism |
| X7 | Alt-coin stress spillover → BTC range | R03-B breadth states `NO_INCREMENTAL_STRUCTURE` neighbourhood |
| X8 | DVOL level → direction | no directional mechanism; level is a regime, already in the RV nuisance |
| X9 | ±5 % book imbalance at support → direction | SEED-0001 / divergence line closed (functional relabel) |

**Counts:** 24 generated; 9 closed at red team; 15 to feasibility.

## 5. Surfaces and exposure

| Card | Discovery | Replication |
|---|---|---|
| P | BTC 2020-10..2024-12 (OI metrics from 2020-09). Product-exposed for price/OI states; the long/short ratio is unused | live only |
| L | six coins 2023-01..2024-12 (exposed) | live only |
| O | BTC, ETH 2021-04..2024-12 (DVOL unused) | live only |
| V | six coins 2020–2024. Levels: BTC exposed, alts used by DH2 (PD/PW/PM levels only); session levels and retests unused | spot BTC/ETH/BNB/XRP 2017–2019 |
| S | BTC 2020–2024 aggTrades. UM unused; spot consumed only for participant composition (TWAP), and DH3-S uses its price path for a lead score | live only |

## 6. PRE_FREEZE_DEFINITIONAL_CORRECTION (2026-10-04, outcome-blind)

**The error.** The first feasibility pass closed all three card-L cells for a single reason: "fewer than 3 years with both arms ≥ 30". BookDepth starts on 2023-01-01, so card L spans two calendar years, and calendar-year epochs could never satisfy that rule.

**The correction.** Contract V1 §4 allows epochs other than calendar years when they are declared. Card L now declares half-year epochs (2023H1, 2023H2, 2024H1, 2024H2) for:
- the epoch gate;
- the feasibility rule;
- the week-cluster cut.

**Why this is not a rescue.**
- It was made before freeze and before any outcome. Only event counts had been seen.
- It changes no state, threshold, endpoint, bar or comparator.
- Every other card keeps calendar years.

The whole feasibility pass was re-run with the corrected code; `DH3_FEASIBILITY.json` is the re-run.
