# DIRECTIONAL_STATE_SEARCH_V2 — design (one bounded discovery cycle; frozen before any outcome)

**Date:** 2026-10-09. **Author:** chief architect. **Owner instruction:** 2026-10-09 ("Открываем следующий research program `DIRECTIONAL_STATE_SEARCH_V2`… execute ONE bounded discovery cycle").
**Owner priority:** `FIND_DIRECTIONAL_EDGE`.
**Mode:** `DISCOVERY` (`DISCOVERY_FIRST_RESEARCH_DECISION_V1`).
**Exposure class:** `ADAPTIVE_HISTORICAL_DISCOVERY`. **Claim ceiling:** `DISCOVERY_ONLY` for every number, whatever its interval.
**Rules:** `RESEARCH_RULES_DECISION_V1.md`, `EVIDENCE_AND_CLAIMS_DECISION_V1.md`. `PRODUCT_INTEGRATION_CANDIDATE = NO`. No product work, no user probability, no PnL filter.
**Code:** `scripts/research/directional_state_search_v2/`; tests `tests/research/test_directional_state_search_v2.py` (synthetic only).
**Ledger:** `DIRECTIONAL_STATE_SEARCH_V2_LEDGER.json`. Its pre-outcome section is frozen with this note; the run appends a post-outcome section and deletes nothing.

## 1. Question

Besides `RANGE_POSITION_4H`, does any independently observable state of BTC carry information about the sign of the next hour, beyond the baseline and simple price-state controls?

- **Canonical predictor and baseline:** `RANGE_POSITION_4H` has the status `CROSS_VENUE_AND_MULTI_EPOCH_REPLICATED_DIRECTIONAL_STATE / HISTORICAL_ONLY`. It enters only as the baseline here: `B0 = {RP4H, RET_4H, RV_4H}` (formulas of the RP4H units, parent code imported).
- **Target:** `R_1H = log(close[i+12] / close[i])` on 5m bars and its sign. No other horizon is read.
- **Level A (standalone):** raw Spearman(STATE, R_1H).
- **Level B (incremental, the main question):** partial Spearman(STATE, R_1H | B0 + at most the listed family nuisance).

## 2. Surface and sample

- **Data:** `CORE_BTC_BINANCE_V0`, Binance USD-M BTCUSDT perpetual 1m klines 2020-01-01 … 2024-12-31.
  - The 60 pinned monthly objects come through the R03 pinned fetcher, SHA256-verified; zip-list digest `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`.
  - Gapless: 2,630,880 rows.
  - Aggregated to 526,176 5m bars (high = max, low = min, close = last, quote and taker-buy quote summed). Aggregation only; nothing is filled.
- **Not read:** Binance 2025/2026, OI, funding, spot, BitMEX, Bybit, books.
- **Anchors:** the RP4H 15-minute phase (`((open − 2020-01-01)/5m) mod 3 = 2`, T at :00/:15/:30/:45 UTC).
  - The bar index must satisfy i ≥ 288 (24h of history) and i + 12 within the surface, with B0 and R_1H finite.
  - That gives 175,292 anchors over 262 ISO weeks (outcome-blind preflight).
- **Session objects:** one row per NYSE trading day 2020-01-02 … 2024-12-31, 1,258 days.
  - Trading days are weekdays minus the `FULL_DAY_CLOSURE` rows of `NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0/EVENTS.json` (SHA256 `69ee28a5…0be2`, pinned in code). Early-close days are kept: they close at 13:00, after every clock used here.
  - Clocks: America/New_York (IANA tzdata 2026c, system zoneinfo; US DST rules for 2020–24 unchanged).
  - P[t] is the close of the 5m bar whose close is t. Every clock falls on the 15-minute grid.
- **Parity gate (engineering only):** before any new state is scored, the run reproduces the recorded discovery cell close_pos_4h → R_1H (Cursor `PRE_IMPULSE_STATE_ATLAS_V1`: anchors i ≥ 96, N 175,356, ρ −0.057773446228651215) within 1e-9. Otherwise it refuses. This re-reads an already-recorded cell and adds no exposure.

## 3. Collision and feasibility audit (outcome-blind) and the frozen inventory

Three read-only audits were run against the red team (`MARKET_PHENOMENA_CATALOG_V1_RED_TEAM.md` §5, §13), the closed units and the Cursor pre-impulse atlas registry.

| # | Family | Verdict | Objects |
|---|---|---|---|
| 1 | SIGNED_PATH_ASYMMETRY | NEW. S1's observable; no semivariance, up-fraction or 24h feature in any record or in the atlas | F1a SPA_24H, F1b UPFRAC_24H |
| 2 | PATH_OCCUPANCY_RESIDUAL | NEW (adjacent). A1's state. Parts were scanned in the atlas (close_pos_4h, frac_near_*, midpoint_slope_4h), but not this function | F2a OCC_MEAN_4H (+ variant OCC_THIRDS_4H) |
| 3 | REJECTION_DECAY | NEW. Not #352/#353/DH3-V3: a non-structural barrier, an amplitude sequence, and fixed anchors with R_1H. One part is a window neighbour of the atlas `last_rejection_*_4h` / `touch_count_*_4h` (disclosed) | F3a REJ_DECAY_24H |
| 4 | COUNTERMOVE_DECAY | NEW (adjacent to C1, which is SURVIVE). Two-sided fixed segments; no swing-low sequence, pivot mining or exhaustion framing | F4a CMD_UP_24H |
| 5 | FAILED_PROGRESS | **BLOCKED: inside the owner-closed divergence / selling-exhaustion line.** It is catalog §6 "lower lows with shrinking follow-through (price-only momentum divergence)", E2's price leg, and NEW_LOW_DEPTH_ATR was computed. Needs an owner override | none (abandoned before outcome; formula kept in the ledger) |
| 6 | US_OPEN_DRIVE / SESSION_HANDOFF | NEW. Not D12 (activity), not R03-C2/C3/C4 (unsigned range), not the opening-range / WIDTH object (no range object), and not DH1-X4 (no touch or move event). Signed states only | F6a US_OPEN_DRIVE (primary of the family), F6b SESSION_HANDOFF |
| 7 | EFFORT_TO_RESULT | NEW in change form, under the owner's E1 ruling. The level forms and the displacement residual are rejected (below) | F7a FLOW_RESPONSE_CHANGE_4H, F7b SIDE_ASYM_CHANGE_4H |
| 8 | OI_RESPONSE | **BLOCKED.** The efficiency-change form is catalog E4 and the built-but-refused form is E3 (owner-closed DH3 line), or MARKET-01 if signed by price. An OI read also needs its own owner OI-only permit. Not BLOCKED_DATA: B2-06 OI from 2020-09 exists | none |

**Abandoned before any outcome (kept visible in the ledger):**
- **FAILED_PROGRESS:** progress per attempt over 24 1h segments.
- **OI_PRICE_EFFICIENCY_CHANGE** and **OI built–price refused.**
- **E1-c:** RET_4H − β₃₀d·NF_4H reduces to the imbalance level (H05 neighbour) and is E5 under the exhaustion line.
- **SIDE_RESPONSE_ASYM_24H in level form:** not a change, so the E1 ruling does not admit it.
- **SESSION_HANDOFF at 08:00 Europe/London:** it sits on the 08:00 UTC funding settlement in winter, needs UK calendars, and D12's EU diagnostic was weak.
- **A Tokyo/00:00 UTC handoff:** this is the anchor of the closed opening-range line.

**Budget (owner §4):** 6 active families of at most 8; at most 2 formulations per family (limit 3); **9 primary objects** (limit 24). One declared variant and one declared sensitivity are not new hypotheses.

## 4. Exact formulas (bar i is the anchor bar; T is its close; every state uses bars ≤ i only)

Notation: c, h, l are close/high/low; r_k = log(c_k / c_{k−1}); q_k is the quote volume; b_k is the taker-buy quote; f_k = 2b_k − q_k (signed aggressive notional). B0 is as in §1.

- **F1a SPA_24H** = (RS+ − RS−)/(RS+ + RS−), with RS± = Σ r_k² over r_k ≷ 0, k = i−287 … i.
  - Extra controls: RET_24H = log(c_i/c_{i−288}) and RV_24H = √(RS+ + RS−).
- **F1b UPFRAC_24H** = (#{r_k > 0} − #{r_k < 0}) / (#{r_k > 0} + #{r_k < 0}) over the same 288 returns. Same controls.
- **F2a OCC_MEAN_4H.** The box is the RP4H box: H = max h, L = min l over bars i−47 … i.
  - p_k = (c_k − L)/(H − L) for the 47 closes k = i−47 … i−1. The current close, i.e. RP4H itself, is excluded.
  - OCC_MEAN_4H = mean p_k. Controls: B0 only.
  - **Variant F2a-v OCC_THIRDS_4H** = share(p_k ≥ 2/3) − share(p_k ≤ 1/3).
- **F3a REJ_DECAY_24H.** Box at T over bars i−287 … i in log units: H, L, W = log H − log L; positions ph, pl, pc of highs, lows and closes.
  - **Upper wall:** contact when ph ≥ 0.90.
    - An episode starts at a contact bar that has no earlier contact, or that has a close with pc < 0.75 strictly after the previous contact bar.
    - The rejection completed before episode e (e ≥ 2) is the max of 1 − pl over the bars strictly between the previous contact bar and the start of e.
    - UD = log(last completed / previous completed); at least two completed rejections are needed.
  - **Lower wall:** mirror, with contact pl ≤ 0.10, gate pc > 0.25, depth ph; gives LD.
  - **RP_24H** = pc of bar i.
  - **State** = −UD if RP_24H ≥ 0.5, else +LD (NaN when the near wall has fewer than two completed rejections). Positive = shrinking rejections at a near upper wall, or growing rebounds at a near lower wall.
  - Extra control: RP_24H. Support: 25,439 anchors.
- **F4a CMD_UP_24H.** Bars i−287 … i in six chronological 4h segments of 48.
  - In segment s: DD_s = max over bars of [log running-max high − log low] and RU_s = max over bars of [log high − log running-min low], both running within s.
  - CMD_UP_24H = [mean log RU(5, 6) − mean log RU(1, 2)] − [mean log DD(5, 6) − mean log DD(1, 2)].
  - Extra control: RET_24H.
- **F6a US_OPEN_DRIVE.** T = 10:00 ET on trading days. State = log(P[10:00]/P[09:30]) / RV_24H ending at 09:30 ET. B0 at T. 1,258 rows.
- **F6b SESSION_HANDOFF.** T = 09:30 ET on trading days. State = log(P[09:30]/P[03:00]) / RV_24H ending at 03:00 ET. B0 at T. 1,258 rows.
- **F7a FLOW_RESPONSE_CHANGE_4H.** λ(window) = Σ r f / Σ f² (OLS slope through the origin). Recent = bars i−47 … i; prior = bars i−287 … i−48.
  - State = sign(Σ f recent) · log(λ_recent / λ_prior). NaN if either slope is ≤ 0 or the recent net flow is 0 (30 anchors).
  - Extra control: IMB_4H = Σ f / Σ q over the recent window (the flow itself).
  - **Sensitivity F7a-s:** also controls LOG_LAMBDA_4H = log λ_recent (the 1h λ level `flow_beta_1h` is exposed on CORE).
- **F7b SIDE_ASYM_CHANGE_4H** = log(λ_buy/λ_sell)_recent − log(λ_buy/λ_sell)_prior, with side slopes on bars f > 0 or f < 0. All four slopes must be > 0. Extra control: IMB_4H.

No sign is asserted before the outcome. Discovery reports both directions.

**Deviations from the red-team frozen formulas, stated before the outcome:**
- S1, A1 and T3 move from 4h races at hourly or daily anchors to R_1H at the RP4H anchors with B0, by owner instruction.
- A1 drops the chord term and the quiet filter. RP4H is excluded mechanically and controlled.
- E1 uses the owner's change form instead of the level against its 30-day reference.
- The red team's exact S1, A1 and T3 race cells stay unexecuted.

## 5. Method (fixed by design)

- **Estimands:** midranks, OLS residualization with intercept on the ranks of the controls, and the Pearson correlation of the residuals. The rank code is the RP4H parent code, imported.
- **Uncertainty:** an ISO-week block bootstrap of the fixed rank residuals.
  - The 262 global weeks are resampled with replacement, B = 2000, seed 20261120.
  - ρ* = Σ S_xy / √(Σ S_xx Σ S_yy) over the drawn weeks; percentile 2.5 / 97.5.
  - SE is the draw standard deviation; z = point/SE.
  - The same draw matrix is used for every cell, so differences are paired.
- **Per object:**
  - N, weeks, P(UP), mean and median R_1H (bp);
  - raw and incremental estimates with intervals;
  - per-year raw and incremental points (each year re-ranked);
  - years whose incremental sign matches the full-sample sign;
  - quintiles of the state and of its residual on the controls (P(UP), mean bp, median bp; description only).
- **Session objects:**
  - **Placebo clocks:** the same statistic (30-min, resp. 6.5h, return over RV_24H ending at the start) at every other main-grid anchor, with B0.
  - Report the clock − placebo difference with a paired interval.
  - Holm over F6a and F6b.
  - CPI and NFP days are kept; no event subset is read (a limitation).
- **Stage 2 (only after standalone incremental information):** run only for an object whose incremental interval excludes zero.
  - **Estimand:** partial Spearman of the product of centered ranks (state × RP4H) with R_1H, given the controls plus the state.
  - **Description:** the RP4H partial (given RET_4H, RV_4H) within state terciles.
  - No other interaction, combination or threshold.

## 6. Ranking, the search bar and the TOP-3 rule (frozen)

- **Search-exposure bar** (rules §4, EXPOSURE_COUNTERS §3): family-wise α 0.10 Bonferroni over m = 813 (CORE × DIRECTION before this cycle, a lower bound) plus every cell read in this cycle. Two-sided.
- **Eligible for a TOP-3 replication proposal:**
  - the incremental interval excludes zero;
  - the incremental sign holds in ≥ 4 of 5 years;
  - |z| ≥ the bar;
  - a question-fresh surface with the needed observables exists (pre-assigned below).
- **Order:** eligible objects by |incremental point| in 0.002-wide bins (floor); within a bin, by the pre-assigned grades; then by |point|.
- **TOP 3:** the first three eligible. Fewer if fewer qualify. Everything else stays `DISCOVERY_ONLY` and is reported in full.

**Pre-assigned before any outcome:**

| id | simplicity | novelty | distance from consumed | question-fresh replication surfaces |
|---|---|---|---|---|
| F1a | A | A | A | price surfaces* |
| F1b | A | B | A | price surfaces* |
| F2a | A | B | B | price surfaces* |
| F3a | C | B | B | price surfaces* |
| F4a | B | B | B | price surfaces* |
| F6a | A | A | A | session surfaces** |
| F6b | A | A | B | session surfaces** |
| F7a | B | A | B | flow surfaces*** |
| F7b | B | B | C | flow surfaces*** |

\* **Price surfaces:**
- BitMEX XBTUSD 5m 2016-05 … 2019-12 (D2 canonical);
- Binance spot BTCUSDT 5m 2017-08 … 2019-12;
- Binance USD-M 2025-01 … 2026-10 minus the E1 window. Each needs its own per-question exposure audit.

\*\* **Session surfaces:**
- Binance USD-M 2025–26 minus the E1 window. Needs a 2025–26 NYSE calendar pin including the 2025-01-09 closure.
- BitMEX 2016–19. Needs 2016–19 calendar pins.

\*\*\* **Flow surfaces:**
- Binance spot 5m klines with taker-buy quote 2017-08 … 2019-12;
- BitMEX trades 2017-08 … 2019-12 (taker side);
- Binance USD-M 2025–26 minus the E1 window.

## 7. Exposure before this cycle

- **CORE × DIRECTION:** ≈ 813\* cells.
- **Disclosed neighbours:**
  - the atlas scanned close_pos_4h (= RP4H), rv_4h, frac_near_*, midpoint_slope_4h, last_rejection_*_4h, touch_count_*_4h and flow_beta_1h/flow_corr_1h against R_1H … R_24H on these anchors;
  - the generic hourly 4h race stream read unconditional direction;
  - B2-03, B2-04, H04, H05 and B2-05 read their exact objects.
- **None of the nine states** was read against a direction outcome on any surface.
- **Governance note:** S1 and A1 were next in the owner's earlier run order as their own units. This program uses their observables first, under the R_1H estimand, by owner instruction. Their red-team race cells remain unexecuted and are not replaced.

## 8. What would change the reading

- **An interval that excludes zero after B0** (and after the family nuisance), with ≥ 4/5 stable years: discovery information beyond RANGE_POSITION. It still needs a question-fresh replication before any claim.
- **Raw only:** the state is a re-expression of position, recent return or volatility.
- **Session objects:** a clock effect needs the clock − placebo interval to exclude zero. Otherwise the state is a generic return state at that clock.
- **Nothing passes:** a valid result. The cycle stops with no neighbouring variant.

## 9. Execution

- `preflight`: outcome-blind support only. Done before this freeze: N, weeks, years, state quantiles, and correlations among states and with controls.
- `run --go`: the one cycle. It refuses on a design or pre-ledger hash mismatch, a parity failure or an existing result.
- **Outputs:**
  - `DIRECTIONAL_STATE_SEARCH_V2_RESULT.json` / `.md` (frozen evaluator output);
  - the ledger post-outcome section;
  - a separate interpretation section and the TOP-3 proposals by the frozen rule.
- **No successor runs in this program:** no replication, interaction beyond §5, horizon or variant.
