# MARKET_PHENOMENA_CATALOG_V1 — directional market states: ideas and collision audit

**Date:** 2026-10-09.
**Role:** market phenomena scout / research director (chief architect).
**Owner priority:** `FIND_DIRECTIONAL_MARKET_STATES`.

**Status: ideation and collision audit only.**
- No market outcome was opened, no data was downloaded and no candidate was tested.
- Nothing here is evidence, a preregistration or a product proposal.
- Every number quoted from earlier units comes from that unit's own record.

**Companion.** Cursor runs `PRE_IMPULSE_STATE_ATLAS_V1`, a broad quantitative scan. This catalog is the conceptual layer: what market behaviour suggests testing. §10 says how the two are compared.

## 0. Correction of the previous conclusion

The architect's message after `P3_CONFIRMATION_V1` said «направленного преимущества нет». That was too broad.

What `P3_CONFIRMATION_V1` established:
> one specific historical crowd-positioning effect (DH3-P3: Binance global long/short account ratio, 30-day z, top vs bottom quintile → up first within 4h) did not repeat on 2025-01..2026-08 (−1.66 pp, CI −5.45..+2.19) and had no trading value after costs.

It is **not** evidence about other directional market states.

The correct project-level statement is: **no validated directional edge has been found yet.** The state families below are largely untested. A failed candidate means only that the candidate failed.

## 1. What was reviewed

- **Atlas:** 218 units (207 on main and 11 on Cursor branches: opening range ×2, formation width ×6, funding ×3).
- **Generator memory:** 79 signatures (`MECHANISM_MEMORY_V0.json`, governance regions).
- **Research history audit:** V1 and its erratum.
- **Record level:** about 180 unit and cell entries were audited across five collision registers:
  - H01–H05, B2-01..06, MARKET-01..06/04H, rangecast;
  - D1–D13, DH1/DH2/DH3 (all cells including the X-cells closed before data), R03, G01, C012, the S4 pool, SEED-0001/0002, Generator V0 cards;
  - Level Engine #352–#368 and LEVEL_RACE_FORECAST_V1, the hold and retest cells, the divergence / selling-exhaustion line, D2/RULE_1, formation width and opening range (Cursor branches);
  - the funding line (MARKET-03, FUNDING_STATE_HISTORICAL_STRUCTURE_V1, the two FUNDING_TAIL_RISK units);
  - the data inventory (`ATLAS_SURFACES_V1.yaml`, `docs/research_data/`, the loaders, live tables).

**What the map says, in one paragraph.**
- Most deaths were real.
- But almost every killed cell was one of:
  - an **unsigned** outcome (range, RV, activity);
  - a **single event** (one breach, one pullback, one impulse);
  - a **level of an input** (imbalance, OI change, crowd ratio).
- Untested so far:
  - the direction of release from flats, and position or migration inside a range;
  - decay across successive swings or touches;
  - up-vs-down speed asymmetry as a state;
  - price response to flow as a state (the flow_conditional_response row has never held a unit);
  - direction at session transitions;
  - temporal venue leadership;
  - sequences of three or more states.

  The per-unit "does not kill" lists in §3 and §6 say exactly where each of these sits.

## 2. Common frame (applies to every phenomenon)

**Form.** `STATE_A → TRANSITION → DIRECTIONAL_MOVE`. Every observable is computed from data available at the decision time T (bar close). Nothing is filled across granularities: 5m sources are never turned into 1m information.

**Outcome families** (a unit picks one family before any outcome):
- **O1 `UP_FIRST(h)`:** +X before −X within h, with X the DH1 barrier (0.5·1.2816·σ5m·√48, half the 80 % 4h corridor half-width).
  - Neither, or both in one bar, scores 0.5.
  - The three-way split is also reported.
  - h ∈ {4h, 8h}.
- **O2 `EXIT_SIDE(8h)`:** the side through which price first leaves the state's own envelope by a buffer, or NEITHER.
- **O3 `BREAK_FIRST`** at an emergent barrier: a ±X race from the latest touch, as in the level race.
- **O4:** signed return at h in X units. This is the economics line, never the primary.

**Baseline stack (BASE).** Every phenomenon must be **incremental over BASE**:
1. **B0:** driftless first-passage geometry from the current position relative to the outcome boundaries.
   - Near the top of a box, the top is more often hit first with no information at all.
   - This is the main false-effect generator for every "tilt" or "pressure" state.
2. Current width/σ and the σ tercile. This is the contemporaneous-state lesson: on the Cursor branch, the opening-range +9.48 pp went to about 0 at equal width.
3. Signed return over the prior 4h and 24h (trend).
4. Hour block and weekend.
5. A matched ordinary-state comparison: same position bucket, σ and hour, without the phenomenon.

**Economics, as information and never a gate.** With symmetric ±X payoffs and round-trip cost c, the break-even hit rate is 0.5 + c/(2X).

| Cost | X ≈ 0.82 % (2020–24 mean) | X ≈ 0.57 % (2025–26) |
|---|---|---|
| Taker, c = 0.12 % | ≈ 57 % | ≈ 60 % |
| Maker, c = 0.04 % | ≈ 52 % | ≈ 54 % |

- Longer natural horizons (8h, 24h) raise X and lower that hurdle.
- DH3-P3's −5.9 pp was untradeable even on its own discovery surface.

**Surfaces.**
- **Discovery:** `CORE_BTC_BINANCE_V0`, 1m, 2020–24 (OHLCV, trade count, taker buy). It is exposed for every row and serves discovery only.
- **ERA (time-disjoint replication):**
  - BitMEX XBTUSD 5m 2016-05..2019 (volume, trades; taker buy from 2017-08 via the DH1 trades build);
  - Binance spot BTCUSDT 5m 2017-08..2019 (taker buy; 1m acquirable).
  - Both are unread for every row except levels.
  - Features meant to replicate there are defined at 5m.
- **PROSP:** the live `klines_1m` on Binance/Bybit/OKX after a unit's freeze.
- **VENUE:** Bybit/OKX over the same period. Robustness only, never confirmation.
- **Binance 2025–26:** product-open and partly consumed. Robustness only.
- **Untouchable:** the E1-RUN-001 holdout `[2026-08-16, 2026-08-25 17:20)`.

**Governance.**
- Atlas §5 forbids: PARAMETER_NEIGHBOR, FUNCTIONAL_RELABEL, OBSERVABLE_SUBSTITUTION, SUBGROUP_MINING, REVERSE_EFFECT_RESCUE, COMPOSITION_OF_CONSUMED, CONFIRMATION_ON_EXPOSED.
- Allowed reopen keys: NEW_MECHANISM, NEW_SURFACE, BLOCKER_RESOLVED, PROSPECTIVE_DATA, OWNER_DECISION.
- Each unit follows `DISCOVERY_FIRST_RESEARCH_DECISION_V1`:
  - a design note before any outcome;
  - a bounded declared search;
  - the whole search reported;
  - a selected relation is DISCOVERY_ONLY.
- Flags used below:
  - **[G]** needs an atlas novelty ruling;
  - **[B]** is blocked by a recorded owner closure (needs OWNER_DECISION);
  - **[C]** carries composition risk.

## 3. Catalog — 41 distinct phenomena

Shorthand:
- **CORE1m:** Binance perp 1m, 2020–24.
- **OI5:** Binance metrics, 5m, from 2020-09.
- **ERA, PROSP, BASE:** see §2.

### A. Flat / accumulation / range migration (range internals)

#### MP-A1 · INTERNAL_RANGE_MIGRATION
- **See:** 4–12h sideways; high and low barely change, but the trading "body" drifts toward one edge. Later hours trade mostly in the upper half and the lower third stops being visited.
- **Why it might lead:** one side keeps accepting better prices inside the box while the other defends only the edge. When the edge goes, less opposing inventory is left.
- **Observables at T:**
  - envelope H/L over W;
  - per sub-window k, the time-weighted median position p_k = (median − L)/(H − L), and the slope of p_k;
  - occupancy skew (minutes in the upper third minus the lower third) in the last slice;
  - time since the last lower-third visit.
- **State:** flat (width/σ-implied width below typical and no new extreme for m minutes) and |migration slope| high.
- **Question:** O2 exit side within 8h beyond B0(current position), width and trend; O1 4h secondary.
- **Data:** CORE1m.
- **Nearest:** H01 (RV compression → expansion, unsigned, killed); formation width / opening range (clock-hour range, unsigned, closed); DH3-P1 (quiet + OI → range); #356 S5.
- **Novelty:** the direction of release and position inside the range are explicit "not killed" items of H01, and range migration has no unit.
- **Failure:**
  - the current position near an edge (B0);
  - the slope is just the last-hours return;
  - width mismatch.
- **Replication:** ERA (features at 5m), PROSP.

#### MP-A2 · CLOSE_LOCATION_SKEW
- **See:** inside the flat most bars close in their upper part; long lower wicks, short upper wicks ("dips are bought inside the bar").
- **Why:** intrabar rejection of lower prices means passive demand below.
- **Observables:**
  - mean close location (C − L)/(H − L) over the flat's bars;
  - lower-wick share Σ lower / Σ (lower + upper);
  - both against the trailing 30 days.
- **State:** flat and CLV skew in the top or bottom quintile.
- **Question:** O2 (8h). **Data:** CORE1m / 5m.
- **Nearest:** C013 (cross-sectional CLV rank → next-day wick asymmetry, sign unstable); D3 (unconditional path shape); path_shape × CANDLES NO_STRUCTURE.
- **Novelty:** a BTC time-series state inside flats predicting the exit side. C013 was cross-sectional and D3 unconditional.
- **Failure:** CLV is autocorrelated with drift; 1m noise. **Replication:** ERA, PROSP.

#### MP-A3 · MIDLINE_CROSSING_DECAY
- **See:** early in the box price crosses the middle often; later it stops crossing and stays on one side.
- **Why:** one side has stopped contesting the middle, and the box effectively narrows to one half.
- **Observables:** midline crossings per hour by slice; time since the last crossing; side of residence.
- **State:** flat, crossings decayed, residence side.
- **Question:** O2. **Data:** CORE1m.
- **Nearest:** H01; A1.
- **Novelty:** crossing-frequency dynamics, not location.
- **Failure:** decay is falling volatility (control the σ change); residence side ≈ position (B0).
- **Replication:** ERA, PROSP.

#### MP-A4 · ONE_SIDED_RETURN_SPEED
- **See:** a dip to the box's lower part returns to the middle fast; a visit to the upper part lingers.
- **Why:** urgency asymmetry — one side reacts fast to discounts, the other does not react to premiums.
- **Observables:** for excursions into the lower and upper thirds, the time to return to the midline (censored if no return); the log ratio of medians.
- **State:** flat and an extreme speed ratio.
- **Question:** O2. **Data:** CORE1m.
- **Nearest:** #353 (one prior rejection's speed at structural levels, killed); #355 (approach velocity, killed).
- **Novelty:** both sides' return speeds compared inside an emergent box; not a level property.
- **Failure:** censoring; few excursions per box. **Replication:** ERA, PROSP.

#### MP-A5 · ENVELOPE_ASYMMETRY
- **See:** highs stop at the same price while lows keep rising (or the mirror). The box narrows from one side.
- **Why:** one side transacts at progressively better prices while the other holds a fixed price.
- **Observables:**
  - swing highs and lows from one frozen zigzag (k·σ);
  - slope of the swing-low series vs the swing-high series over the last N swings (σ units);
  - swing count.
- **State:** one envelope slope large, the other ≈ 0.
- **Question:** break of the static edge before the latest swing on the contracting side within 8h; O2.
- **Data:** CORE1m.
- **Nearest:** #352 (touch count, killed); DH3-V3 (retest → hold); H02.
- **Novelty:** the joint shape of both envelopes on emergent (non-PDH/PDL) boxes.
- **Failure:** zigzag parameter (freeze one); rising lows put price nearer the top (B0).
- **Replication:** ERA, PROSP.

#### MP-A6 · LOCATION_CONDITIONAL_AGGRESSION [G]
- **See:** at the box bottom aggressive buying appears; at the top there is no aggressive selling.
- **Why:** one side initiates at its preferred prices and stays passive at the other edge.
- **Observables:** taker-buy share by in-range position bucket (kline or aggTrades); bottom minus top.
- **State:** flat and an extreme aggression asymmetry.
- **Question:** O2. **Data:** CORE1m taker; aggTrades side (unused outside stress hours).
- **Nearest:** H05 (imbalance level → return, killed); B2-05 (absorption, consumed); #361 R3; DH1-X10.
- **Novelty:** the location × flow interaction, not the level of imbalance.
- **Governance:** the taker-family rule ("formula changes are not fresh") needs an ORTHOGONAL_MECHANISM ruling; the aggTrades side offers a NEW_SURFACE route.
- **Failure:** taker share is mechanically higher on up bars. **Replication:** BitMEX taker 2017–19, PROSP.

#### MP-A7 · VALUE_AREA_MIGRATION
- **See:** the price where most volume trades inside the box (point of control) moves toward one edge.
- **Why:** in auction terms, volume concentrates where both sides accept price. Accepted value moving up precedes the edge giving way.
- **Observables:**
  - volume-at-price from 1m bars (each bar's volume spread over its H–L);
  - point-of-control and 70 % value-area position per slice;
  - POC drift.
- **State:** flat and POC migration.
- **Question:** O2. **Data:** CORE1m.
- **Nearest:** #367 (unsigned volume in a structural-level zone, null); D7 (impact, unsigned).
- **Novelty:** volume-weighted acceptance migration in emergent ranges. A1 is the time-weighted counterpart, and disagreement between the two is itself informative.
- **Failure:** volume ↔ volatility; the allocation is approximate (no ticks); collinear with A1.
- **Replication:** ERA (volume), PROSP.

### B. Barrier pressure (emergent barriers, not the consumed structural levels)

**Emergent barrier.** Two or more swing extremes within a zone w, formed by the market's own rejections. It is not PDH/PDL/PWH/PWL/PMH/PML.

#### MP-B1 · REJECTION_AMPLITUDE_DECAY
- **See:** a ceiling rejects price by 1.0 %, then 0.6 %, then 0.3 %. Each bounce away is smaller.
- **Why:** the defending side's capacity shrinks; the barrier stops repelling before it breaks.
- **Observables:** for each touch k, the max excursion away before the next touch (σ units), the ratio a_k/a_{k−1} and the touch count. Past touches only.
- **State:** three or more touches with decaying amplitude.
- **Question:** O3 BREAK_FIRST within 4h from the latest touch, against B0 and against the touch-number baseline.
  - #352: on structural levels later touches broke less (−6.6 pp at 3+).
- **Data:** CORE1m.
- **Nearest:** #352 (touch count); #353 (one prior rejection's speed and overshoot, killed); DH3-V3; H02.
- **Novelty:** the sequence of rejection sizes is an explicit "not killed" item of #352/#353, on a new object.
- **Failure:**
  - amplitude decay as falling σ;
  - proximity to the barrier (B0);
  - barrier survivorship (define it at T only).
- **Replication:**
  - the levels row is consumed on BitMEX 2017-09..2019 for structural first touches, so emergent barriers there are exposed-surface robustness;
  - BitMEX 2016-05..2017-08, spot 2017–19 and PROSP are cleaner.

#### MP-B2 · INTER_TOUCH_INTERVAL_COMPRESSION
- **See:** price returns to the ceiling sooner each time: 90, 40, 15 min.
- **Why:** the push-back away from the barrier gets shorter in time; the pressing side re-engages faster.
- **Observables:** intervals between touches; their log-ratio trend; time since the last touch.
- **State:** three or more touches with shrinking intervals.
- **Question:** O3 (4h). **Data:** CORE1m.
- **Nearest:** #352 (lists "shrinking time between touches" as not killed); #353; #365 (time after the touch).
- **Novelty:** the interval sequence before the touch.
- **Failure:** session-clock activity (control hour and RV); collinear with B1. **Replication:** as B1.

#### MP-B3 · PENETRATION_CREEP [G]
- **See:** each probe pokes slightly deeper past the ceiling before closing back ("стену съедают").
- **Why:** resting supply at the barrier is being consumed layer by layer.
- **Observables:** max overshoot per touch (σ units) with close-back; the overshoot trend over three or more probes.
- **State:** rising overshoots with closes back inside.
- **Question:** O3. **Data:** CORE1m.
- **Nearest:** #353 (overshoot of one prior rejection, a sensitivity, killed); H02; #362.
- **Novelty:** a trend across three or more probes. It needs a ruling that this is not a PARAMETER_NEIGHBOR of #353.
- **Failure:** zone-location error creates spurious overshoots. **Replication:** as B1.

### E. Effort versus result

#### MP-E1 · FLOW_IMPACT_ASYMMETRY (transfer function) [G]
- **See:** the same aggressive selling moves price down less than it used to, while buying moves it up as before («продавец давит, а цена стоит»).
- **Why:** passive one-sided liquidity (limit buyers absorbing sells) lowers one side's impact. The impact asymmetry shows hidden liquidity.
- **Observables:**
  - rolling 24h regressions of 1m/5m return on signed taker flow, split by sign (λ_buy, λ_sell);
  - log(λ_sell/λ_buy) against its own trailing 7–30 days.
- **State:** asymmetry in the top or bottom quintile.
- **Question:** O1 UP_FIRST 4h/8h. **Data:** CORE1m taker buy; aggTrades as robustness.
- **Nearest:**
  - H05 (flow level → return, killed);
  - B2-05 (|IMB|×FLOW_RET tertile → continuation, consumed with no result; IMB/move ratios forbidden);
  - D7 (unsigned impact state persists, CONFIRMED on BitMEX);
  - C025-R1 (burst impact, N = 1, blocked).
- **Novelty:** the market's transfer function and its sign asymmetry over a day — not an input level or a 15–60m window ratio. D7 shows the impact state is real and persistent, and lists "the direction after high or low impact" as not killed.
- **Governance:** an ORTHOGONAL_MECHANISM ruling against B2-05 is required.
- **Failure:** simultaneity (up bars carry buy flow); λ ↔ volatility and spread; estimation noise.
- **Replication:** BitMEX taker 2017-08..2019 (ERA), PROSP.

#### MP-E2 · SWING_EFFICIENCY_DECAY [G]
- **See:** each new push of a run needs more volume for less distance.
- **Why:** trend fuel is being spent. Sign not pre-asserted (continuation stall or reversal).
- **Observables:** for the last three same-direction swings, displacement/σ divided by relative volume (vs 30 days); its trend.
- **State:** efficiency decaying across three or more swings in a directional run.
- **Question:** O1, two-sided. **Data:** CORE1m.
- **Nearest:** D7 (hourly impact, unsigned); B2-03 (path efficiency of one move, killed); H03/H04.
- **Governance:** exhaustion framing touches the closed divergence / selling-exhaustion line. This is volume per displacement across swings, not an oscillator, but it needs a ruling.
- **Failure:** secular volume trends; session clock. **Replication:** ERA (BitMEX volume), PROSP.

#### MP-E3 · SIGNED_OI_BUILD_IN_FLAT
- **See:** in a quiet box, open interest climbs and the taker flow during the build leans one way.
- **Why:** new leveraged positions accumulate on one side inside the box. A later exit against them forces their unwind. Sign not pre-asserted.
- **Observables:** ΔOI over the flat (OI5); taker-buy share during OI-up intervals; the OI-weighted flow sign.
- **State:** flat, ΔOI in the top tercile, flow sign.
- **Question:** O2. **Data:** OI5 + CORE1m.
- **Nearest:**
  - DH3-P1 (quiet OI build → range, unsigned, WEAK +13.4 %);
  - MARKET-01 (OI up while price stalls after an impulse → 60m reversal, killed);
  - #358.
- **Novelty:** both "the direction out of quiet OI loading" (DH3-P1) and "OI building during flat periods" (MARKET-01) are listed as not killed.
- **Failure:** OI gaps (631 missing buckets); a 5m-only source.
- **Replication:** POSITIONING has no pre-2020 era, so PROSP plus Bybit OI (robustness).

#### MP-E4 · OI_PRICE_COUPLING_REGIME
- **See:** lately OI rises when price falls and falls when price rises (shorts opening into weakness, covering into strength), or the reverse.
- **Why:** it shows who drives the tape. A switch between long-driven and short-driven coupling may precede direction.
- **Observables:** rolling 24h slope/correlation of ΔOI on Δprice (5m or 1h); its change vs 7 days.
- **State:** extreme coupling sign or change.
- **Question:** O1 4h/8h. **Data:** OI5 + CORE1m.
- **Nearest:** MARKET-01/02 (OI after impulses); DH3-P1/P2; DH3-O3 (DVOL–price correlation, null).
- **Novelty:** a coupling (transfer) regime, not an OI level or change.
- **Failure:** forced exits mechanically couple OI and price. **Replication:** PROSP, Bybit OI.

#### MP-E5 · EFFORT_WITHOUT_PROGRESS [B]
- **See:** heavy aggressive selling for hours while price is flat.
- **Observables:** cumulative net taker flow over 1–4h vs displacement.
- **Nearest:** B2-05 (consumed; its low tertile is this state at 15–60m); H05; SEED-0001 (CVD divergence); selling-exhaustion feasibility (INFORMATIONALLY_WEAK). The divergence / exhaustion line is CLOSED (2026-10-03).
- **Status:**
  - the kline-taker version is a collision;
  - a multi-hour version would be a window neighbour.
  - Admissible only by OWNER_DECISION, or through E1 (the transfer function), which this catalog recommends.

### C. Countermove decay

#### MP-C1 · PULLBACK_MAGNITUDE_DECAY
- **See:** in an up-leg the dips are 0.8 %, 0.5 %, 0.2 %. Each pullback is shallower.
- **Why:** the counter side can push less each time, and dip demand arrives earlier.
- **Observables:** past-only zigzag swings (frozen k·σ) in the current leg; the last three adverse excursions (σ units), their ratios and monotonicity.
- **State:** three or more pullbacks, monotone decay.
- **Question:** O1 continuation first within 4h/8h, against matched legs of the same size and σ with non-decaying pullbacks, beyond BASE.
- **Data:** CORE1m.
- **Nearest:** H04 (one pullback's depth, killed); B2-04 (V-recovery inside one pullback, killed); B2-03 (countermove shallowness inside one move, killed).
- **Novelty:** decay across successive swings is listed explicitly as not killed in H04 and B2-04.
- **Failure:** decay as falling σ; zigzag lag; legs that continue have more swings (define the leg at T).
- **Replication:** ERA, PROSP.

#### MP-C2 · RECOVERY_SPEED_ACCELERATION
- **See:** after each dip, price regains the prior high faster: 42, 21, 8 min.
- **Why:** rising time-urgency of the dominant side.
- **Observables:** per pullback, the time from swing low back above the prior swing high; its sequence trend.
- **State:** accelerating recoveries over three or more pullbacks.
- **Question:** O1. **Data:** CORE1m.
- **Nearest:** B2-04 (recovery fraction within one pullback); #353.
- **Novelty:** the time dimension across swings.
- **Failure:** session-clock activity; censoring. **Replication:** ERA, PROSP.

#### MP-C3 · EQUILIBRIUM_RECAPTURE_DECAY
- **See:** dips below the rolling VWAP last less and less time.
- **Why:** prices below accepted value are rejected faster each time.
- **Observables:** rolling 24h VWAP (quote/volume); for each excursion below it, duration and depth; their trend.
- **State:** shrinking time below equilibrium.
- **Question:** O1. **Data:** CORE1m.
- **Nearest:** H04.
- **Novelty:** VWAP was only named as an untested level population (`DH1_RESULT.md`). No unit has used it as a dynamic anchor.
- **Failure:** in trends price stays above VWAP mechanically (control trend). **Replication:** ERA, PROSP.

### F. Failed attempts

#### MP-F1 · RECLAIMED_PROBE_SEQUENCE
- **See:** price breaks below the box low three times. Each time it is back inside within minutes, faster each time. The box high is never tested.
- **Why:** repeated failure to progress one way while the other side is not even contested.
- **Observables:** in W:
  - count of probes beyond one boundary that closed back inside within m minutes;
  - the time-to-reclaim and depth sequences;
  - time since the last touch of the opposite boundary.
- **State:** two or more reclaimed probes on one side and none on the other.
- **Question:** O2 exit side within 8h. Two-sided, with no sign pre-asserted.
- **Data:** CORE1m.
- **Nearest:** H02 (single failed breakout → reversion, killed; it forbids a "liquidity sweep" relabel and a LOWER-only child); B2-02; #362; #366.
- **Novelty:** the count and sequence of repeated attempts and the time-to-reclaim are listed as not killed in H02 and B2-02. Symmetric by design.
- **Failure:** overlaps A1/A5; must not be sold as a sweep. **Replication:** ERA, PROSP.

#### MP-F2 · ATTEMPT_LIFETIME_DECAY
- **See:** moves one way start and die sooner each time: legs of 40, 25, 10 min.
- **Why:** initiative on that side is fading.
- **Observables:** durations and extents of successive same-direction legs over 8–24h; the opposite legs' durations.
- **State:** shortening attempts one way.
- **Question:** O1, two-sided. **Data:** CORE1m.
- **Nearest:** B2-03 (shape of one move); H03.
- **Novelty:** the lifetime sequence across attempts.
- **Failure:** zigzag; volatility regime. **Replication:** ERA, PROSP.

### S. Market speed

#### MP-S1 · TRAVERSAL_TIME_ASYMMETRY
- **See:** going up 0.3 % takes 10 minutes, going down 0.3 % takes 30, with no net change («вверх быстро, вниз медленно»).
- **Why:** pressure can show as speed before it shows as displacement: the urgent side moves fast, the passive side drifts.
- **Observables:**
  - over the last 24h, from each bar, completed first-passage times to +x and −x (x = k·σ), and the log ratio of their medians;
  - the duration of equal-size up vs down zigzag legs.
- **State:** extreme speed ratio while the 24h return is small.
- **Question:** O1 4h/8h. **Data:** CORE1m.
- **Nearest:**
  - B2-03 (lists "up vs down speed asymmetry as a state" as not killed);
  - D3 (its asymmetry functional was dropped before execution);
  - V03L40-C023 (downside path share, blocked);
  - the H03/H05 one-sided asymmetries are quarantined (post-hoc, not usable).
- **Novelty:** never measured as a state.
- **Failure:** realized skewness and drift mechanics; jumps. **Replication:** ERA, PROSP.

#### MP-S2 · ASYMMETRIC_SHOCK_PERSISTENCE
- **See:** lately down-moves get bought back quickly, up-moves stay.
- **Why:** one side absorbs shocks against it.
- **Observables:** rolling 48h sign-split autocorrelation — the regression of the next k 5m returns on r_t, separately for r_t > 0 and r_t < 0 — and the coefficient gap.
- **State:** extreme gap.
- **Question:** O1. **Data:** CORE 5m.
- **Nearest:** V03L40-C027 (down vs up shock recovery, method-blocked); G01-X5 (dedupe); D8 (deferred, insufficient controls).
- **Novelty:** built from ordinary returns rather than rare shocks, so it avoids the support blocker. A state, not an event.
- **Failure:** bid-ask bounce (use 5m); volatility asymmetry. **Replication:** ERA, PROSP.

### T. Quiet → active and session transitions

#### MP-T1 · QUIET_BEFORE_ACTIVITY_TILT
- **See:** (owner) at 06:00 Kyiv the market stands still; at 07:00 a move starts. More generally: in the quiet window before a predictable activity ramp, the internal tilt (A1/A2) may announce the release side.
- **Why:** early participants position quietly; the ramp releases in the direction of that inventory.
- **Observables:**
  - for every predeclared transition, never a winner hour: Asia→Europe ramp, Europe→US ramp (both in local exchange time across DST), US close→Asia, weekend→Monday;
  - in the quiet window before each: A1/A2 tilt, RV and range;
  - ramp times from the D12 activity profile.
- **State:** a quiet pre-ramp window with tilt.
- **Question:** O1 4h from the ramp start; O2 for the pre-ramp box.
- **Identification:** DST shifts. If the effect moves with local session time (one hour in UTC), it is a human-session effect. If it stays at the UTC clock, it is a clock or algorithm effect.
- **Data:** CORE1m.
- **Nearest:**
  - D12 (activity anchored to the US clock; direction is forbidden as a D12 child);
  - R03-C2/C4 (unsigned range at Monday US open and Friday close);
  - formation width / opening range (clock-hour range object closed; "no winner hour");
  - DH1-X4; DH3-V1.
- **Novelty:** the clock is only the event definition and the predictor is the pre-ramp state. Direction at clocks is listed as not killed in R03.
- **Failure:** hour-of-day drift (keep it in the baseline); few DST transitions (about 10). **Replication:** ERA, PROSP.

#### MP-T2 · SESSION_HANDOFF
- **See:** Asia drifted up quietly; Europe opens and either extends or reverses it.
- **Why:** the participant population changes and inventory is handed over.
- **Observables:** the prior session's net return, efficiency (net/path) and close position in its range.
- **State:** extreme prior-session efficiency and sign.
- **Question:** O1 4h from the next ramp, for all handoffs predeclared. **Data:** CORE1m.
- **Nearest:** R03 (unsigned); H04; DH3-V1.
- **Novelty:** an inter-session sign relation conditioned on efficiency.
- **Failure:** generic 8h return autocorrelation (keep it in the baseline). **Replication:** ERA, PROSP.

#### MP-T3 · US_OPEN_DRIVE [G]
- **See:** in the first 30 minutes after the US equity open BTC moves decisively; the session follows or reverses.
- **Why:** US participants (ETF flows, CME) enter at the open, carrying overnight imbalance.
- **Observables:** the first-30m signed displacement in σ (DST-tracked), its efficiency, volume vs typical, and no retrace through the open.
- **State:** strong drive.
- **Question:** O1 from 30m after the open to +4h, against a predeclared placebo clock grid. **Data:** CORE1m.
- **Nearest:** OPENING_RANGE_OBJECT_V1 (UTC 00:00 range; "another hour" forbidden); R03-C2 (unsigned); D12; G01-B1 (ETF fix, IW).
- **Novelty:** event-anchored and signed; the closure lists "direction" and "event-anchored ranges" as not killed. Needs a ruling that this is not "another hour" of the opening-range object.
- **Failure:** hour drift; the 2024 ETF structural break (split the eras). **Replication:** ERA, PROSP.

#### MP-T4 · SETTLEMENT_BASIS_UNWIND [G]
- **See:** the perp trades rich to spot into the 8h settlement; after it the premium collapses and price drifts.
- **Why:** positioning to collect or avoid funding at the timestamp, and its unwind.
- **Observables:** perp − spot basis from klines (PIT-legal; not the funding print) in the hour before 00/08/16 UTC, and its change after.
- **State:** extreme pre-settlement basis.
- **Question:** O1 1h/4h after settlement. **Data:** CORE + Binance spot 5m (pinned) or 1m (acquirable).
- **Nearest:**
  - MARKET-04/04H (funding/premium, BLOCKED_OBSERVABLE);
  - DH3-X1 and DH1-X7 (closed);
  - FUNDING_STATE_HISTORICAL_STRUCTURE_V1 (path stress, ρ ≈ 0.03, CI includes 0);
  - funding_clock × CROSS_VENUE is method-blocked (the 08:00 UTC confound).
- **Novelty:** the kline basis avoids the funding-latency blocker (a BLOCKER_RESOLVED route), but it is still premium-family.
- **Failure:** 08:00 UTC is also the Europe ramp. **Replication:** PROSP.

### V. Cross-venue timing and population

#### MP-V1 · VENUE_LEADERSHIP_ORDER
- **See:** OKX starts moving up, Bybit confirms, Binance is still inside its range and then catches up — or the leader fails.
- **Why:** venues host different participants. Who moves first, and whether leadership persists, may say whether the move is informed.
- **Observables:**
  - per venue, the time of first exit from its own 1h range by δ;
  - the order and lead time, and the number of confirming venues;
  - leader-identity persistence over 24h;
  - Binance's position in its own range.
- **State:** two or more venues out on one side with Binance inside; a persistent leader.
- **Question:** continuation of the episode on the cross-venue mid (+X before −X within 1h/4h), not the closing of the lag, which is arbitrage.
- **Data (acquisition):** Binance aggTrades from 2020-01; Bybit trades from 2020-03-25; OKX trades from 2021-09.
- **Nearest:**
  - MARKET-06 (dislocation level → MAE, null); D9 (resolution share, null);
  - #363 (same-window moves after a structural touch; it lists "lead/lag in time" as not killed);
  - DH3-S1/S2 (spot vs perp lead score in stress hours → range); DH1-X5 (closed); R01-C002 (blocked).
- **Novelty:** temporal order and leader persistence. price_discovery × CROSS_VENUE is open.
- **Failure:** at 1m or coarser the lag may be fully arbitraged; venue clock skew (the Bybit MT4 label shift).
- **Replication:** venue pairs across years, PROSP (`klines_1m` on three venues).

#### MP-V2 · COINBASE_PREMIUM (US spot demand)
- **See:** Coinbase BTC-USD trades above Binance BTCUSDT after the USDT/USD conversion. US spot buyers are paying up.
- **Why:** a distinct participant population (US institutional, ETF-adjacent) may lead the offshore market.
- **Observables:** premium = ln(CB / (BN·USDTUSD)) per hour; its level z vs 30 days; its 4h change; persistence.
- **State:** extreme signed premium or change.
- **Question:** O1 4h/8h/24h.
- **Data (acquisition):** Coinbase 1m candles (from 2015), plus USDT-USD. Not in the inventory.
- **Nearest:** MARKET-06 (|z| of OKX spot vs Binance perp → MAE); D9; SPOT_PERP basis NO_STRUCTURE.
- **Novelty:** a new venue and population, and a signed premium predicting direction rather than an unsigned dislocation predicting risk.
- **Failure:** USDT basis noise; outages; the 2024 ETF regime change.
- **Replication:** 2016–19 (GDAX vs BitMEX/Bitfinex), PROSP.

#### MP-V3 · CROSS_VENUE_BARRIER_DISAGREEMENT
- **See:** the ceiling broke on Bybit/OKX (wicks printed above) but held on Binance, or the reverse.
- **Why:** thinner venues get swept first. Whether the main venue's wall holds shows where liquidity really sits.
- **Observables:** per-venue emergent barriers; per-venue breach state at T.
- **State:** a disagreement in breach state.
- **Question:** O3 on Binance.
- **Data:** Bybit/OKX 5m OHLC (pinned; coarse); 1m by acquisition.
- **Nearest:** #363 (lists "pre-touch venue divergence" as not killed); V1.
- **Novelty:** venue disagreement at emergent barriers before the resolution.
- **Failure:** venue price offsets; 5m coarseness. **Replication:** PROSP.

#### MP-V4 · BASIS_PRICE_DIVERGENCE [G]
- **See:** price rises while the perp premium over spot shrinks (a spot-led rally), or price rises with the premium expanding (leverage-led).
- **Why:** spot-led moves are funded by unlevered buyers; leverage-led moves can unwind.
- **Observables:** the change in perp − spot basis vs the price change over 4h (klines).
- **Question:** O1 4h/8h. **Data:** CORE + spot 5m.
- **Nearest:** #364 (spot excess, null); DH1-X7; DH3-S1; DH2-B2; MARKET-04H.
- **Novelty:** moderate; risk of OBSERVABLE_SUBSTITUTION of the spot-led cells. **Replication:** ERA (spot vs BitMEX), PROSP.

### I. Impulse ignition

#### MP-I1 · IGNITION_COMPOSITION [G]
- **See:** the first expansion leg out of a box comes with many small trades (a crowd chase) or with few large ones (block initiative).
- **Observables:** average trade size (quote/trades) and trade-count growth vs volume growth in the first 15–30 minutes of an exit.
- **Question:** O1 continuation. **Data:** CORE1m trade count.
- **Nearest:** participant_composition × PERP_FLOW NO_STRUCTURE (TWAP footprint); DH3-S3 (≥ $1M prints → range); DH3-X2 (closed); GV0CAL-C001 (untested); B2-03 (lists "volume profile of the impulse" as not killed).
- **Novelty:** moderate.
- **Failure:** average trade size trends with price level and the venue's lot rules. **Replication:** ERA (BitMEX trades), PROSP.

#### MP-I2 · SIGNED_SEMIVARIANCE_SHIFT
- **See:** volatility is starting to return on one side only: up bars get bigger while down bars stay small.
- **Why:** "good vs bad volatility" — the first side to gain variance is the side with initiative.
- **Observables:** realized upside vs downside semivariance (5m) over the last 2–6h vs the prior 24h; signed jump variation.
- **State:** an extreme signed semivariance shift at the end of a quiet period.
- **Question:** O1 4h. **Data:** CORE 5m.
- **Nearest:** H01 and B2-01 (unsigned RV); D3; S1.
- **Novelty:** signed variance as a release precursor.
- **Failure:** it equals the recent return sign unless trend is in the baseline. **Replication:** ERA, PROSP.

### R. Response regime change (transfer functions)

Other formulations live under E1 (flow → price, sign split), E4 (OI ↔ price coupling), S2 (shock persistence, sign split) and B1 (the response to the same barrier contact).

#### MP-R1 · VOLUME_ELASTICITY_ASYMMETRY
- **See:** up bars travel far on modest volume; down bars need heavy volume to move a little.
- **Why:** thin offers above and thick bids below, visible from candles alone.
- **Observables:** |ret|/relative volume per bar, split by bar sign; the ratio over 24h vs 30 days.
- **State:** extreme elasticity asymmetry.
- **Question:** O1 4h/8h. **Data:** CORE1m.
- **Nearest:** D7 (unsigned impact persistence, CONFIRMED; lists direction as not killed); E1.
- **Novelty:** signed impact from candles and total volume. It replicates on BitMEX 2016–19 without taker data.
- **Failure:** volatility clustering; jumps. **Replication:** ERA, PROSP.

#### MP-R2 · AUTOCORRELATION_REGIME_SWITCH
- **See:** the market switches from choppy (moves reverse) to trending (moves extend). The switch, plus the last leg's sign.
- **Observables:** rolling variance ratio VR(k) of 5m returns over 24h vs 7 days; its change; the sign of the last 4h.
- **State:** VR crossing 1 upward, with the leg sign.
- **Question:** O1 continuation. **Data:** CORE 5m.
- **Nearest:** H03/H04 (continuation, killed); D1 (state detection, deferred); GV0CAL-C001.
- **Novelty:** a persistence regime as the conditioning state; moderate.
- **Failure:** VR noise; overlaps trend. **Replication:** ERA, PROSP.

### Q. State sequences (2–4 interpretable states, one frozen definition each, never a mined grid)

#### MP-Q1 · MIGRATION_THEN_PRESSURE (the owner's example)
- **Sequence:** flat → centre migrates up (A1) → the upper edge is re-touched with decaying rejections (B1) or shrinking pullbacks (C1) → upside release.
- **Question:** O2 against B0, and against A1-only flats.
- **Composition:** both components are untested, so this is not COMPOSITION_OF_CONSUMED. **Data:** CORE1m.

#### MP-Q2 · COUNTERMOVE_DECAY_INTO_CEILING
- **Sequence:** up-leg with shrinking pullbacks (C1) → the leg's ceiling retested at shorter intervals (B2) → break.
- **Question:** O3 BREAK_FIRST. **Data:** CORE1m.

#### MP-Q3 · FAILED_PROBES_QUIET_RELEASE
- **Sequence:** reclaimed probes at one edge (F1) → RV falls (quiet) → release.
- **Question:** the release side (O2), two-sided. **Data:** CORE1m.

#### MP-Q4 · SPRING_TEST [C]
- **Sequence:** range → sweep below the low reclaimed → a higher-low retest holds → push into the upper half (Wyckoff spring).
- **Status:** its components touch H02 (single sweep, killed) and DH3-V3 (retest). Admissible only as one theory-specified definition with an atlas ruling.

#### MP-Q5 · IMPULSE_FLAG_CONTRACTION [C]
- **Sequence:** impulse → shallow pullback (< 38 %) with contracting volume → dwell near the impulse high → continuation.
- **Status:** B2-04 forbids "a second H04 child". Admissible only if the pullback-volume contraction is ruled a new mechanism (H04 lists "effort during the pullback" as not killed).

#### MP-Q6 · DISTRIBUTION_UPTHRUST [B]
- **Sequence:** trend leg → effort without progress at the top (E5) → first lower high → reversal.
- **Status:** the exhaustion line is CLOSED; needs OWNER_DECISION.

### X. Positioning composition

#### MP-X1 · TOP_TRADER_VS_CROWD [G]
- **See:** large accounts (Binance "top traders") are net short while the crowd's accounts are long, or the reverse.
- **Why:** disagreement between informed-leaning and crowd positioning, not crowd extremity.
- **Observables:** the top-trader long/short position ratio vs the global account ratio. These metrics columns are pinned and have never been used. Divergence z.
- **Question:** O1 4h/8h. **Data:** OI5 metrics.
- **Nearest:** DH3-P3 (global account-ratio extremity; NOT_CONFIRMED on 2025–26).
- **Novelty:** a different object (between-group disagreement), but there is OBSERVABLE_SUBSTITUTION risk against P3. Needs a ruling. It is not another test of P3.
- **Replication:** PROSP only (no pre-2020 era).

## 4. Top-15 research priority

This is a research-priority ranking, not evidence. Criteria: directional relevance (Dir), novelty (Nov), observability (Obs), data available now (Data), interpretability (Int), independent replication route (Rep), distance from known nulls (Dist). H/M/L.

| # | ID | Phenomenon | Dir | Nov | Obs | Data | Int | Rep | Dist | Why here |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | A1 | Internal range migration | H | H | H | H | H | H | H | untested row; the owner's own example; candles only; ERA unread |
| 2 | C1 | Pullback-magnitude decay | H | H | H | H | H | H | M | explicitly not killed in H04/B2-04; owner's example |
| 3 | S1 | Up/down traversal-time asymmetry | H | H | H | H | M | H | H | explicitly not killed in B2-03; never measured |
| 4 | T1 | Quiet-before-activity tilt (DST) | H | H | M | H | H | H | M | direction at clocks untested; DST is a natural experiment |
| 5 | E1 | Flow-impact asymmetry (transfer function) | H | H | H | H | M | H | M | flow_conditional_response row empty; D7 persistence; ruling needed vs B2-05 |
| 6 | B1 | Rejection-amplitude decay (emergent barrier) | H | H | H | H | H | L | M | not killed in #352/#353; the levels confirmation surfaces are consumed |
| 7 | A7 | Value-area migration | H | H | M | H | H | H | H | volume-weighted twin of A1; auction logic |
| 8 | A5 | Envelope asymmetry | H | M | H | H | H | H | M | classic accumulation geometry, never tested on emergent boxes |
| 9 | F1 | Reclaimed-probe sequence | H | M | H | H | H | H | L | repeated attempts not killed in H02/B2-02; must stay two-sided |
| 10 | Q1 | Migration → pressure | H | H | M | H | H | H | H | sequence of two untested states; fewer events |
| 11 | R1 | Volume-elasticity asymmetry | H | M | H | H | M | H | M | signed D7; replicates without taker data |
| 12 | S2 | Asymmetric shock persistence | H | M | H | H | M | H | M | resolves C027's support blocker |
| 13 | V2 | Coinbase premium | H | H | M | L | H | M | H | new venue and population; acquisition needed |
| 14 | E3 | Signed OI build in flat | H | H | H | M | M | L | M | not killed in DH3-P1 and MARKET-01; no pre-2020 OI |
| 15 | V1 | Venue leadership order | H | H | M | L | M | M | H | price discovery in time; tick acquisition; may be arbitraged at 1m |

Close behind (siblings folded into the units of §9): C2, B2, I2, A2, T3, A3, F2.

## 5. Special shortlist with synthetic examples

The examples are illustrative, not frozen thresholds.

1. **Flat / accumulation — MP-A1 INTERNAL_RANGE_MIGRATION.**
   - **Example:** over the last 8h the high is 64,420 and the low 63,610 (range 1.26 %, about 0.9× a typical 8h range).
     - Time-weighted median position by 2h slice: 0.31, 0.44, 0.58, 0.71.
     - In the last 2h, 62 % of minutes were in the upper third and 5 % in the lower third.
     - The last lower-third visit was 3h10m ago; price is now at 0.68 of the box.
   - **Question:** does an upward-migration state raise P(exit up within 8h) above B0 (≈ 0.68 at this position) and above matched flats at the same position without migration?

2. **Barrier pressure — MP-B1 REJECTION_AMPLITUDE_DECAY.**
   - **Example:** an emergent ceiling at 64,400 ± 0.15 % formed by swing highs at 09:10, 11:25, 13:05 and 13:50.
     - Rejections after the touches: 1.05 %, 0.62 %, 0.31 % (2.1σ, 1.2σ, 0.6σ).
     - Intervals between touches: 135, 100, 45 min.
     - Price is now 0.2 % below the ceiling.
   - **Question:** from the fourth touch, is BREAK_FIRST (±X race) more frequent than for fourth touches with non-decaying amplitudes, and above B0? #352's prior: on structural levels later touches break less often.

3. **Effort vs result — MP-E1 FLOW_IMPACT_ASYMMETRY.**
   - **Example:** over the last 24h, each $1M of net taker selling moved price −0.021 % and each $1M of net buying +0.034 %. The 30-day typical values are −0.035 % and +0.033 %.
     - Sell impact is at 60 % of normal while buy impact is unchanged.
     - The 24h return is −0.3 %.
   - **Question:** does a low-sell-impact, normal-buy-impact state raise 8h UP_FIRST vs matched days with symmetric impact and the same 24h return and σ?

4. **Countermove decay — MP-C1 PULLBACK_MAGNITUDE_DECAY.**
   - **Example:** an up-leg since 06:00 of +2.4 %.
     - Pullbacks of 0.80 %, 0.50 %, 0.20 % (1.6σ, 1.0σ, 0.4σ).
     - Recoveries to the prior high took 42, 21 and 8 min.
     - Price is in the top 25 % of the 4h range.
   - **Question:** does this state increase 4h UP_FIRST versus matched legs of the same size and σ whose pullbacks did not decay?

5. **Session transition — MP-T1 QUIET_BEFORE_ACTIVITY_TILT.**
   - **Example:** the Europe ramp (07:00 London local, tracked across DST).
     - The pre-ramp window 05:00–07:00 local had a range of 0.35 % (0.6× typical for that window).
     - A1 migration slope +0.3 box per hour; mean close location 0.68.
   - **Question:**
     - Is the first post-ramp 4h direction tilted toward the pre-ramp migration, beyond the hour-of-day drift and B0?
     - Does the effect move with local time across DST (a human session) or stay at UTC (a clock)?

6. **Cross-venue timing — MP-V1 VENUE_LEADERSHIP_ORDER.**
   - **Example:**
     - 11:42:10 — OKX leaves its 1h range upward by 0.15 %.
     - 11:42:40 — Bybit follows.
     - 11:43 — Binance is still 0.05 % below its own range high.
     - OKX led the day's last three episodes.
   - **Question:** given two or more venues out on one side with Binance inside, does the cross-venue mid reach +X before −X within 1h/4h more often than for single-venue exits or Binance-led exits?
   - The state-based alternative is V2 (Coinbase premium).

7. **State sequence — MP-Q1 MIGRATION_THEN_PRESSURE.**
   - **Example:** a 10h flat with upward migration (slices 0.35 → 0.70).
     - The last three touches of the box high were rejected 0.6 %, 0.4 %, 0.2 %.
     - The lower third has not been visited for 4h.
   - **Question:** is the 8h exit side up beyond B0 and beyond A1-only flats at the same position?

Also illustrated:
- **MP-S1:** over the last 24h the median time to +0.3 % was 11 min and to −0.3 % 34 min, with a net 24h of −0.1 %.
  - **Question:** does fast-up / slow-down raise 4h UP_FIRST beyond the 24h return and σ?

## 6. Ideas generated and rejected as collisions

| Idea | Collides with | Why rejected |
|---|---|---|
| Dwell growth near a barrier | #355 F8 dwell (killed) | FUNCTIONAL_RELABEL / PARAMETER_NEIGHBOR |
| Post-breach acceptance (closes beyond, shallow retest) | #362 (15m acceptance states) and B2-02 (30m acceptance path) | both killed; nearby recodes forbidden |
| Approach speed vs rejection speed | #355 velocity and #353 rejection speed | COMPOSITION_OF_CONSUMED |
| OI rises while price stalls after a move | MARKET-01 | exact cell killed; OI threshold/horizon rescue forbidden |
| Meta-order footprint / taker-sign persistence | G01-X4 (red team: known stylized fact), TWAP footprint, participant_composition NO_STRUCTURE | consumed |
| Large-lot (whale) aggression imbalance → direction | DH3-X2 / X3 | closed before data |
| Spot-vs-perp effort split, spot-led move continuation | DH2-B2 (null), DH3-S1/S2, #364, DH1-X5 | consumed or closed |
| Lower lows with shrinking follow-through (price-only momentum divergence) | divergence / selling-exhaustion line, CLOSED 2026-10-03 | owner closure; FUNCTIONAL_RELABEL of divergence |
| Expansion staircase / first-bar ignition morphology | B2-03 (any displacement W 15–60, morphology → continuation, killed) + H01 | FUNCTIONAL_RELABEL |
| CME weekend gap fill | DH3-X5 | INFORMATIONALLY_WEAK (MDE about 12 pp) |
| Realized spot–vol correlation regime → direction | DH3-O3 (DVOL–price correlation, null) | OBSERVABLE_SUBSTITUTION |
| Range breakout at another clock hour (daily close, Asia open) | OPENING_RANGE_OBJECT_V1 / formation-width closure | "another hour" forbidden |
| Thin book side attracts price | DH3-L2 (+0.21 pp, null), #360 | consumed |
| Up-leg vs down-leg acceleration (convexity) | B2-03 morphology | FUNCTIONAL_RELABEL |

## 7. Data gaps that limit the promising ideas

1. **Synchronized multi-venue data at 1m or finer.** Only 5m Bybit/OKX OHLC is pinned, with a Bybit hole 2023-12..2024-03.
   - V1 and V3 need the Bybit (from 2020-03-25) and OKX (from 2021-09) trade tapes plus Binance aggTrades.
2. **Coinbase and USDT/USD.** Not in the inventory (V2).
3. **1m data in the earlier era.** Only 5m is pinned for BitMEX/spot 2016–19.
   - Binance spot 1m 2017–19 is acquirable, and BitMEX tick trades (and an unlisted quote archive) are acquirable.
   - Until then, features meant to replicate must be defined at 5m.
4. **Positioning has no pre-2020 era.** OI, ratios and top-trader metrics start 2020-09, so E3/E4/X1 can be confirmed only prospectively.
5. **Funding publication latency is unproven.** Funding prints are research-blocked; T4 uses the kline basis instead.
6. **Premium, mark and index klines** are acquirable but not materialized.
7. **Historical liquidations:** none.
   - Live only since 2026-07-17 (Bybit side fix 2026-10-08; OKX excluded).
   - Liquidation-sweep ignition and cascade ideas are forward-only.
8. **A forward book-depth surface** depends on the beta research feeds, which are recorded as not enabled.
9. **Options skew** (25-delta risk reversal) is not pinned; only DVOL.
10. **On-chain, ETF and stablecoin flows:** nothing pinned.
11. **Confirmation surfaces are scarce.**
    - CORE 2020–24 is exposed for every row.
    - Binance 2025–26 is product-open.
    - Real confirmation must come from ERA or PROSP.

## 8. Testable now vs acquisition first

- **Testable now on existing data:**
  - **Discovery on CORE 2020–24:** A1–A5, A7, B1–B3, C1–C3, F1–F2, S1–S2, I1–I2, R1–R2, T1–T3, Q1–Q3.
  - **Replication (ERA, pinned 5m):** BitMEX 2016–19 and Binance spot 2017–19.
  - **Testable but governance first:** E1–E2 (kline taker and volume; ruling first), E3–E4 and X1 (OI5 and metrics; X1 ruling first), and T4 and V4 at 5m (spot 5m pinned; ruling first).
- **Acquisition first:**
  - V1 (three-venue tapes); V2 (Coinbase, USDT-USD); V3 at 1m;
  - 1m-era replication (spot 1m, BitMEX ticks);
  - any liquidation, options-skew or flows idea.

## 9. Recommended first five execution units

These are not executed. Each needs its own design note before any outcome, and the batch needs an owner go.

1. **U1 RANGE_INTERNALS_DIRECTION_V1** (A1, A2, A3, A5, A7).
   - **Object:** one frozen flat-episode definition on CORE.
   - **Features:** five, defined at 5m so they replicate.
   - **Outcome:** O2 three-way within 8h, with O1 4h secondary.
   - **Baseline:** BASE with B0 from the current position and matched ordinary flats.
   - **Surfaces:** discovery on CORE 2020–24; confirmation on ERA (BitMEX 2016–19, spot 2017–19); then PROSP.
   - **Why first:** the most direct test of "the market looks still but is already tilted". The row is untested and replication is clean.
2. **U2 COUNTERMOVE_DECAY_V1** (C1, C2, C3, plus F2 as the opposite-side view).
   - **Object:** one frozen zigzag and a past-only leg definition.
   - **Outcome:** O1 continuation within 4h/8h.
   - **Baseline:** BASE plus leg size and σ-matched legs.
   - **Surfaces:** as U1.
   - **Why:** explicitly not killed in H04 and B2-04; candles only.
3. **U3 SPEED_AND_SIGNED_RESPONSE_V1** (S1, S2, I2, R1).
   - **State:** speed, signed-variance and elasticity asymmetries over the trailing 24–48h.
   - **Outcome:** O1 4h/8h.
   - **Baseline:** BASE with a strong trend control.
   - **Surfaces:** discovery CORE; confirmation ERA (R1 needs only volume, available on BitMEX 2016–19); then PROSP.
   - **Why:** never measured as a state; listed as not killed in B2-03 and D7.
4. **U4 SESSION_RELEASE_V1** (T1, plus T2 and T3 if the T3 ruling allows).
   - **Grid:** all transitions predeclared; no winner hour.
   - **Identification:** DST (local-time vs UTC anchoring).
   - **Outcome:** O1 4h from the ramp.
   - **Baseline:** BASE plus hour-of-day drift and unconditional 8h autocorrelation.
   - **Surfaces:** discovery CORE; confirmation ERA; then PROSP.
   - **Why:** the owner's 06:00→07:00 observation, generalized and identified.
5. **U5 FLOW_TRANSFER_FUNCTION_V1** (E1, E2, E4).
   - **Prerequisite:** an atlas novelty ruling against B2-05/H05 (ORTHOGONAL_MECHANISM), and against the exhaustion closure for E2.
   - **Outcome:** O1 4h/8h.
   - **Surfaces:** discovery CORE kline taker plus OI5; confirmation BitMEX taker 2017-08..2019 for E1/E2 (E4 is prospective only).
   - **Why:** the effort-vs-result row has never held a unit, and D7 shows the impact state is real.

**Next after these:** U6 EMERGENT_BARRIER_PRESSURE_V1 (B1–B3 with Q1/Q2).
- Its discovery is feasible now.
- Its confirmation route is weaker because the levels row is consumed on BitMEX 2017-09..2019. The cleaner surfaces are BitMEX 2016-05..2017-08, spot 2017–19 and PROSP; settle that before running it.
- V2 and V1 follow their data acquisition.

## 10. Comparing with Cursor's PRE_IMPULSE_STATE_ATLAS_V1

When it returns, compare it on these points:

1. **Conditioning direction.** A profile of states seen *before* impulses is selection on the outcome. The comparison needs forward rates: P(up impulse | state), P(down impulse | state) and P(no impulse | state) against the base rates.
2. **Signed vs unsigned.** States that precede |moves| (quiet, compression, low RV) are volatility precursors, not direction. For each surfaced state, ask whether it separates up-impulses from down-impulses.
3. **The same baselines.** Every surfaced state should survive BASE: B0 from the current position, width/σ (the contemporaneous-state lesson), trend and hour. A range-position feature is the B0 baseline itself, not a phenomenon.
4. **Crosswalk.** Map each surfaced feature to catalog IDs:
   - position/tilt → A1/A2/A5/A7;
   - speed/semivariance → S1/I2;
   - flow/impact → E1/R1;
   - OI → E3/E4;
   - clock → T1–T3;
   - venue → V1/V3.
   A state with no catalog ID is a new phenomenon to add.
5. **Convergence rule.** Priority rises when a top signed state from the atlas falls in the same family and direction as a top-ranked catalog idea. Disagreement is recorded, not resolved by retuning.
6. **Independence and exposure.**
   - Agreement between theory and data scan is independence of generation, not of data.
   - If both use CORE 2020–24, nothing is confirmed. Whatever the atlas selects is DISCOVERY_ONLY and needs ERA or PROSP.
   - Its search size goes into the exposure ledger.

## 11. Confirmations

- No outcome test was run.
- No market data was downloaded or read for outcomes. This task read only repository documents, code and metadata.
- No product work was done, and the bot, the beta and its configuration were not changed.
- No atlas source was changed: this catalog is not a unit. Units are added to the atlas when designed and run.
