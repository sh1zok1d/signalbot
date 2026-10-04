# DH1 — candidates, red team and dedupe

**Program:** `DIRECTIONAL_HYPOTHESES_DH1` (`docs/research/DIRECTIONAL_HYPOTHESES_DECISION_V1.md`)
**Written:** 2026-10-04, before any DH1 data byte was read and before any outcome
**Design source of truth:** `scripts/research/dh1/constants.py`

## 1. Where the candidates come from

- **The owner's example.** The bot shows, for a key level, how often price stayed beyond it 4h after its first touch. The question is which observable state shifts that rate.
- **The owner's second form.** "In the next 4h the probability of a move up is …%". This is tied to a concrete event (a sharp 15-minute move, which the bot already alerts on) and made a clean binary by two barriers.
- **The atlas frontier.** The top open cells are spot↔perp (spot confirmation, spot volume share) and objective levels. Spot data is free from 2017, so a time-disjoint earlier era exists for it.

## 2. Inventory

| ID | Candidate | Stage | Reason |
|---|---|---|---|
| DH1-L1 | Spot-confirmed approach to a level → 4h hold | **SURVIVES** | new mechanism variable from a new surface (spot); see §3 |
| DH1-L2 | Confluent level (another level kind within 0.15 %) → 4h hold | **SURVIVES** | the product's own zones; no prior unit; see §3 |
| DH1-L3 | Stale level (not traded in the prior 24h) → 4h hold | **SURVIVES** | neighbour of GV0R01-C017 but a different design (§3) |
| DH1-B1 | Spot-confirmed sharp move → which 4h barrier first | **SURVIVES** | top atlas cell `SPOT_PERP.spot_confirmation`; see §3 |
| DH1-B2 | High spot share in a sharp move → which 4h barrier first | **SURVIVES** | atlas cell `SPOT_PERP.volume_share`; see §3 |
| X1 | Approach speed into a level (impulse vs drift) → hold | CLOSED_AT_RED_TEAM | composition of consumed path families: H02 failed breakout, B2-02 boundary interaction path, H03 / B2-03 impulse morphology. Conditioning their null on a level type would be `COMPOSITION_OF_CONSUMED` |
| X2 | OI change on the approach to a level → hold | CLOSED_AT_RED_TEAM | OI-continuation neighbourhood: MARKET-01 and MARKET-02 `NO_EVIDENCE`, family B exhausted. No earlier-era OI exists for confirmation |
| X3 | OI change during a sharp move → barrier | CLOSED_AT_RED_TEAM | same as X2 |
| X4 | Time of day / session of the touch or move → direction | CLOSED_AT_RED_TEAM | family J sessions exhausted (D12, R03); time of day is in the nuisance baseline, not a mechanism |
| X5 | Spot vs perp lead inside the move (1m lead) → barrier | CLOSED_AT_RED_TEAM | D9 conditional venue-resolution attribution `NO_STRUCTURE`, whose reopen note forbids converting it into a neighbour |
| X6 | Sharp move ending into a key level → barrier | CLOSED_AT_RED_TEAM | H03 extreme impulse rejected; conditioning it on a level is subgroup mining of a consumed claim |
| X7 | Perp premium / basis during the move → barrier | CLOSED_AT_RED_TEAM | basis × SPOT `NO_STRUCTURE` (GV0V03L40-C002/C034); MARKET-04H adjudicated the premium observable blocked |
| X8 | Order-book recovery after the move (OKX L2) → barrier | DEFERRED (FUTURE_CANDIDATE) | free and pristine from 2023-03, but heavy; no time-disjoint history (live only). Needs its own data-feasibility pass |
| X9 | Options DVOL − realized → direction | CLOSED_AT_RED_TEAM | not a directional mechanism. DVOL belongs in the product as a descriptive number, not in a card |
| X10 | Taker imbalance on the perp alone → barrier | CLOSED_AT_RED_TEAM | H05 closed; B2-05 governance forbids formula-changed taker children. Perp imbalance is a nuisance variable in L1, B1 and B2 |

**Counts:** 15 generated, 5 survive, 9 closed at red team, 1 deferred.

## 3. Survivors

### Common rules

**Decision time.** T is the close of the event bar. Every feature uses bars that closed at or before T. The outcome uses the 48 bars after it.

**Claim type.** Every survivor is an `INCREMENTAL` directional claim, because the bot would state a direction.

**Nuisance baseline.** The contract's standard set, plus card-specific terms:
- the 4h block of the UTC hour;
- the tercile of the 24h realized volatility before the event;
- the tercile of the prior 4h return aligned with the event direction (the lagged target);
- card L adds the level-type group: day, week, month, round, POC;
- card B adds the move-size tercile;
- the three spot cells add the tercile of the perp taker imbalance over the same window. This is the contract's "prior net taker flow" term, so a spot cell must add information beyond perp flow.

Terciles are computed within each surface by a frozen rule.

**Estimand.** The coefficient of the state in a linear probability model with the nuisance dummies. Each event has equal weight. It is the nuisance-adjusted shift of the probability, in percentage points.

**Inference.**
- ISO-week cluster bootstrap, 2000 draws, two-sided.
- Holm within each card at 0.05.

**Gates.**
- **Practical:** |shift| ≥ 3 pp, and the Brier skill score of the model with the state must be positive against the nuisance-only model. On discovery the score is cross-fitted leave-one-year-out. On replication the frozen discovery models are used.
- **Epoch heterogeneity:** as in contract V1 §4.

**Events.**
- **Level event (card L):**
  - the first touch of a key level in its period, using the product's types and rules (`beta/levels.py`, bound by digest): PDH, PDL, PWH, PWL, PMH, PML, round numbers, and the previous day's POC;
  - several levels touched by the same bar on the same side form one event, keeping the most important type;
  - **hold** = the close 4h after the touch bar is beyond the level, on the approach side. This is the product's metric.
- **Sharp-move event (card B):**
  - |log(close[i] / close[i−3])| ≥ 2 × the 1h scale, where the scale comes from the 24h of 5m returns that closed before the move began;
  - at most one event per hour; the direction d is the sign of the move;
  - **barrier outcome:**
    - X is half of the 4h corridor half-width, X = 0.5 × 1.2816 × σ5m × √48;
    - 1 if close × (1 + d·X) is reached before close × (1 − d·X) within 4h, 0 if the reverse;
    - 0.5 if neither is reached, or both in the same bar.

**Why X is half the half-width.** The bot shows the corridor as "±h". The owner chose "X = половина текущего коридора", read here as h/2. With X = h, about half of the events reach neither edge within 4h, and the probability would mix direction with volatility. With h/2 almost every event resolves, so the number is a clean measure of direction. The choice was made before any data was read.

### DH1-L1 — spot-confirmed approach
- **State:** spot taker net flow over the hour into the touch (touch bar included) points in the approach direction. **Comparator:** zero or against it.
- **Mechanism:** a push carried by unlevered spot flow is less likely to be unwound.
- **Red team:**
  - **Not H05:** the mechanism variable is spot participation; perp imbalance is a nuisance.
  - **Not D9:** that unit attributed closing extremes to a venue; here the measure is net flow in the approach direction.
  - **Confounding:** spot flow co-moves with price, so the lagged-return and perp-flow terms are mandatory.
  - **Data:** the free Binance spot archive since 2017 gives the earlier era.

### DH1-L2 — confluent level
- **State:** another objective level of a different kind lies within the product's zone tolerance (0.15 %) at the touch. It is computed with `beta.levels.compute_levels` on the bars up to the touch, excluding liquidation clusters, which have no history.
- **Mechanism:** levels watched by more participants concentrate resting orders and stops.
- **Red team:**
  - No prior unit tests it.
  - Its weakness is a mechanical link with level type: weekly and monthly highs often coincide with daily highs. The level-type nuisance absorbs the group-level part.

### DH1-L3 — stale level
- **State:** the level price was not traded during the 24h before the touch bar.
- **Mechanism:** orders and stops accumulate at a level the market has not visited.
- **Red team:** a neighbour of GV0R01-C017 (round numbers vs placebo grids, `BLOCKED_METHOD` on causal identification). This card differs in three ways:
  - it covers all objective level types;
  - it compares real levels with real levels (stale vs fresh);
  - it makes no causal claim: it is a conditional probability beyond the nuisance baseline.

### DH1-B1 — spot-confirmed sharp move
- **State:** spot taker net flow over the three bars of the move points in the move direction. **Comparator:** zero or against it.
- **Mechanism:** spot-carried moves are unlevered demand; perp-only moves are more often leverage that unwinds.
- **Red team:**
  - H03 rejected the unconditional "extreme impulse → continuation" claim. This card makes no unconditional claim. It asks whether a new observable from a new surface (spot) separates moves.
  - It is not the M05/M06 cell (24h direction-aligned adverse-path MAE regression). The horizon, estimand and event conditioning all differ.

### DH1-B2 — high spot share in a sharp move
- **State:** the spot share of spot+perp quote volume during the move is above its share over the 24h before the move.
- **Mechanism:** high spot participation means the move is less leverage-driven.
- **Red team:**
  - It overlaps B1 in spirit (spot participation vs spot direction). Both sit in one card, so Holm treats them as one family.
  - The share is venue-specific. In the earlier era the perp is BitMEX, so the share means something different there, and replication may fail for that reason alone. This is recorded in advance.

## 4. Confirmation and display

| Status | Bot display |
|---|---|
| `PROMISING_PROTOTYPE` (discovery passes) | «Гипотеза» |
| `SUPPORTED_UNCONDITIONAL` (replication on 2017–2019 passes the same frozen rule) | «Проверено» |
| Failed replication | no number |

**Live tracking:**
- runs after the freeze, on Binance daily archives;
- stopping rule: at least 300 events, at most 1000, end 2027-12-31;
- counts only until the stop.
