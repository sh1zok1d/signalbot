# LEVEL_RACE_FORECAST_V1 — design note

**MODE = DISCOVERY** (model development on the discovery surface), followed by **one held-out read** of the frozen predictor.
**Program:** `FORECAST_LAYER_DECISION_V1` (the one bounded research exception of PRE_BETA_SCOPE §2.3). Family `LEVEL_BEHAVIOR_V1`. Tracks `PRODUCT_EVIDENCE` (may the product show these probabilities) and `STRUCTURE` (does the structural level move the race off geometry).
**Status:** `DESIGN_COMMITTED / NO_OUTCOME_READ`. Written by ОПГ-2 track F1 on 2026-10-08. No 2020–2024 outcome and no 2025/2026 object was read for it.
**Machine-readable freeze:** `docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.json`. Where the two differ, the JSON wins for numbers and this note wins for meaning.
**Contract:** `docs/FORECAST_LAYER_DECISION_V1.md` §2–§7. Evidence rules: `EVIDENCE_AND_CLAIMS_DECISION_V1`, `DISCOVERY_FIRST_RESEARCH_DECISION_V1`, `EXPOSURE_WEIGHTING_DECISION_V1`.

Numbers marked **[F3]** are planning values. Their final form is agreed with track F3 through the ОПГ-2 mini-head and committed in an amendment of this note **before** the held-out read and before any display. Everything else is frozen by this commit.

## 1. Question and estimand

At a structural first touch, what are the probabilities of the three race outcomes inside the original 4h window, given what is known at the landmark?

- **Event:** the #352 constructor, unchanged (`scripts/research/level_touch_degradation_v1/events.py`): `level_instances` → `build_episodes(zone_half = 0.0015)` → `scan_all`; `touch_number == 1`, `feature_eligible == True`. Kinds PDH PDL PWH PWL PMH PML. No second detector.
- **Barriers:** #352 `X = 0.5 × 1.2816 × σ × √48`, σ = `sigma_before_touch` (sample SD of the 288 5m log returns ending at bar j−1). Upper price `P_UP = zone_high × (1 + X)`, lower price `P_DN = zone_low × (1 − X)`. Both approach sides use the same two prices; only the label differs (approach from below: BREAK = upper; from above: BREAK = lower).
- **Outcome:** #352 `classify` on the original window, bars `j+1 … j+48` (high/low). Three outcomes `BREAK` / `REJECT` / `NEITHER`. `AMBIGUOUS` (both barriers on one bar) is excluded from fitting and scoring and counted (§9).
- **Landmarks:** one forecast per event per landmark; each landmark is its own claim class.
  - **T0:** issued at the close of bar `j` (the touch bar). Position = `close[j]`. Time left τ = 48 bars. Population: every eligible first touch.
  - **T15:** issued at the close of bar `j+2`. Position = `close[j+2]`. τ = 45 bars. Population: events with no barrier hit on `j+1`, `j+2` (the #361 `UNRESOLVED_AT_D` rule); early-resolved and early-ambiguous events are counted and get no T15 forecast.
- **Estimand of the development stage:** out-of-fold log-loss of each menu model against B0 and B1, per landmark, plus the calibration quantities of §6.

## 2. Model menu (6 entries, frozen)

All models output three probabilities. `logit` is natural. Every model probability, raw or published, and B0 itself is floored at `ε = 0.001` per outcome and renormalised before scoring and before display.

| Id | Role | Parameters |
|---|---|---|
| `B0` | «обычно»; reference for skill | 0 |
| `B1` | climatology comparator | 6 cells per landmark (§2.2) |
| `M1` | champion candidate, primary | 10 |
| `M1A` | M1 variant: full family, no σ | 10 |
| `M1B` | M1 variant: pure level offset on geometry | 4 |
| `C1` | first live challenger (§8); not champion-eligible | M1-family + 1 |

No other model, feature, transformation or interaction is fitted in this unit. No boosting, no neural network, no isotonic calibration.

### 2.1 B0 — driftless first-passage geometry

Log price `u` is a driftless Brownian motion with variance σ² per 5m bar (σ as above, the same σ at both landmarks). With `L = ln P_DN`, `U = ln P_UP`, `w = U − L`, start `z = ln(position) − L` and `s = σ² τ / w²`:

```
P_up(z)   = z/w + Σ_{n≥1} [2(−1)^n / (nπ)] · sin(nπ z/w) · exp(−n² π² s / 2)
P_dn(z)   = P_up(w − z)
P_neither = Σ_{n odd} [4 / (nπ)] · sin(nπ z/w) · exp(−n² π² s / 2)   ( = 1 − P_up − P_dn )
```

- Closed-form sine series (method of the two absorbing barriers). Terms are summed until `exp(−n²π²s/2) < 1e-15` (cap 20 000 terms). No simulation is used in production; tests check the series against a fixed-seed simulation (seed `20261008`) and against the method-of-images sum for small `s`.
- **Out-of-corridor start.** If `z ≤ 0` (position at or below `P_DN`) or `z ≥ w`, B0 puts `1 − 2ε` on that side. This can happen only at T0 (a T15 event by definition did not reach a barrier on `j+1`, `j+2`). The count is reported.
- **Discretisation.** The outcome is read on 5m highs and lows of the trade-price path, which are the true extremes inside each bar. Monitoring is therefore effectively continuous and the continuous-path formula is the model of record; no discrete-monitoring (Broadie–Glasserman) shift is applied. Remaining mismatches are **not corrected inside B0** and are listed so the reader knows where they go: σ is a 5m close-to-close estimate (fat tails, intrabar jumps, volatility clustering); trade-print extremes include bid/ask bounce; a same-bar double hit is `AMBIGUOUS` while the continuous path has an order; up to 10 % of window bars may be missing (`MIN_PRESENT = 0.9`), which shortens monitoring; drift in log price is set to 0 (the martingale drift −σ²/2 per bar is about 10⁻⁴ of the barrier span over 4h). Systematic effects of all of these land in the M1 intercepts and in the calibrator, by design.
- The time origin is the landmark close; bars before it are not in the window. τ counts whole 5m bars to the close of `j+48`.

### 2.2 B1 — climatology

Per landmark, the three-outcome frequency in each of the 6 cells family (DAY, WEEK, MONTH) × structural side (`STRUCT_SIDE`: +1 for PxH, −1 for PxL), from the training folds only, with add-one (Dirichlet 1,1,1) smoothing. B1 ignores position and σ; at T15 it is expected to be far behind B0 and is kept as the base-rate comparator §5 asks for. **Question Q1 (§12):** six cells with three outcomes are 12 free frequencies per landmark; if "≤ 6 parameters" is meant literally, the fallback is family only (3 cells, 6 free frequencies).

### 2.3 M1 family — two heads, offset by B0, ridge

Factorisation (exact; not a conditioning on the future): `P(BREAK) = p_R · p_B`, `P(REJECT) = p_R · (1 − p_B)`, `P(NEITHER) = 1 − p_R`.

- Head R (resolve by 4h): `logit p_R = logit(B0_up + B0_dn) + x'β_R`, fitted on all scored rows.
- Head B (BREAK given resolved): `logit p_B = logit(B0_break / (B0_up + B0_dn)) + x'β_B`, fitted on resolved rows. The product of the two maximum-likelihood fits is the maximum-likelihood fit of the three-outcome model.
- One pooled fit over both landmarks (row = event × landmark); the landmark enters as a dummy. Rows of one event are correlated; inference is week-clustered (§6).
- Offsets are clipped to `[1e-4, 1 − 1e-4]` before the logit.

| Term | Coding | M1 | M1A | M1B |
|---|---|---|---|---|
| intercept | 1 | R, B | R, B | R, B |
| `T15` | 1 at T15, 0 at T0 | R, B | R, B | R, B |
| `FAM_WM` | 1 if WEEK or MONTH, 0 if DAY | R, B | — | — |
| `WEEK`, `MONTH` | dummies, DAY reference | — | R, B | — |
| `SIDE` | `STRUCT_SIDE` (+1 / −1) | R, B | R, B | — |
| `SIGMA_T` | σ tercile −1 / 0 / +1; edges from training-fold T0 events | R, B | — | — |
| **count** | | **10** | **10** | **4** |

- **Ridge:** minimise `−loglik + (λ/2)·‖β‖²` over the non-intercept coefficients of each head (intercepts unpenalised). λ grid `{0.5, 2, 8, 32}` (absolute, on the summed negative log-likelihood). λ is chosen per variant by the pooled out-of-fold log-loss of §3; ties (< 0.0005 nats) go to the larger λ. The frozen model is refit on all of 2020–2024 at the chosen λ.
- Binary and ordinal codes are used as given (no standardisation). σ tercile edges are fold-local (training rows only) and, for the frozen model, the 2020–2024 T0 terciles.
- **Not in any model** (FORECAST_LAYER §3): touch ordinal, rejection speed, approach geometry, static level properties, OI, taker, joint OI/taker/price state, ±1 % book, path memory, spot, the sequence taxonomy, zone notional, the #365 clock, the #368 RV transition, `END_POSITION_X` as a separate feature (position enters only through B0), the pseudo map. The #361 and #363 coefficients are not reused.

## 3. Development: cross-validation

- **Surface:** `CORE_BTC_BINANCE_V0`, Binance USD-M BTCUSDT 1m → complete 5m bins by the frozen DH1 loader (`scripts/research/dh1/data.py`, `level_touch_degradation_v1/data.py`), events 2020-02-01 → 2024-12-31 with the 4h window inside 2024. C1 additionally reads `LEVEL_CROSS_VENUE_PERP_5M_V0` (the #363 Bybit and OKX canonical files) from 2020-04-01T00:05Z.
- **Folds (rolling origin by calendar year of the touch):** train 2020 → test 2021; train 2020–21 → test 2022; train 2020–22 → test 2023; train 2020–23 → test 2024. All fitted quantities (B1 cells, σ tercile edges, coefficients, λ choice, the C1 moments) come from the training years of the fold. Pooled out-of-fold predictions for 2021–2024 are the development evidence.
- **Clusters:** product week (`touch_week`, Monday 00:00 UTC). Uncertainty: week-cluster bootstrap over the pooled out-of-fold rows, 2000 draws, seed `20261008`, percentile 95 % interval; both landmark rows of an event share its week.
- **Stability:** per test year and per family, the same metrics, reported in full whatever their sign.

## 4. Champion rule and freeze

1. For each of M1, M1A, M1B: pooled (both landmarks) out-of-fold mean log-loss at its chosen λ.
2. **Champion** = the variant with the lowest pooled out-of-fold log-loss **if** its point estimate is below B0's; a difference under 0.002 nats goes to the variant with fewer parameters (M1B, then M1, then M1A). If no variant is below B0, **champion = B0** and no level model is frozen.
3. The champion and C1 are refit on all 2020–2024 at their λ and frozen in one commit; that SHA is `MODEL_VERSION`. The frozen module is the predictor the product imports (proposed `beta/level_race.py`, an ОПГ-2 file under ORCHESTRATION_V1 §4; to be agreed with F2).
4. Development results are internal L2 evidence (`DISCOVERY_ONLY` for the selected variant). They are not shown to users and are not the gate.

## 5. Held-out check (one read)

- **Surface:** Binance USD-M BTCUSDT 5m klines from data.binance.vision through the product object planner `beta.history_data.plan_objects` (the product-history source, `BINANCE_UM_KLINES_5M_PRODUCT`; same source as live, which is the parity that matters for display). Warm-up bars from 2024-12 come from the same source.
- **Events:** touch open ≥ 2025-01-01T00:00Z and 4h window closed before the **freeze date** (UTC midnight of the freeze commit's date, exclusive).
- **E1-RUN-001 exclusion, object level first:** no archive object overlapping `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` is requested (the planner replaces the August 2026 monthly file by daily files outside it; the 2026-08-16 … 2026-08-25 daily objects are not requested). The resulting bar gap is `[2026-08-16, 2026-08-26)`. **Event level:** every event whose span from the first bar of its σ window (touch − 289 bars) to bar `j+48` intersects that gap is dropped; levels whose source or active period is incomplete because of the gap are dropped by the unchanged constructor (`incomplete_source` / `incomplete_active`, which removes the August 2026 monthly levels and the levels of the affected weeks and days). Every count is reported.
- **Read once,** after the freeze commit and only on the mini-head's explicit go. No refit, no λ change, no menu change after it. Expected size (FORECAST_LAYER §4): about 600–700 T0 and 400–450 T15 events.
- **Parity preflight (outcome-blind, before the read):** on 2024 (development period) the constructor run on product 5m klines and on CORE 1m→5m bars must give the same first-touch events; the agreement share and every difference are reported. It is a data check; nothing is tuned on it.
- **Exposure class:** `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`-like (EXPOSURE_WEIGHTING_DECISION_V1 class B). The predictor is frozen on 2020–2024 before any 2025/2026 outcome is read for it; the Level Engine chain never read 2025/2026; but the product's first-touch hold statistics already read a neighbouring outcome on this surface. Disclosed with every held-out number; never called pristine.
- **Raw and published.** Raw = frozen predictor output. Published = the raw output passed through the calibrator **prequentially**: the calibrator used for an event issued in week t is fitted only on held-out events resolved before week t starts (weekly batches; first batch at the identity prior of §7). This is the same rule the live calibrator follows, so the published held-out metrics are honest out-of-sample.

## 6. Metrics (both stages, both landmarks, raw and published separately)

In this order (FORECAST_LAYER §5):
1. **Log-loss skill** `1 − LL_model / LL_ref` against B0 and against B1, with the paired mean difference `LL_ref − LL_model` (nats per event) and its week-clustered 95 % interval.
2. **Calibration** per head (R: resolve vs neither; B: BREAK vs REJECT among resolved) and per outcome one-vs-rest: calibration-in-the-large `CITL = mean(y − p)` in pp, logistic recalibration intercept and slope (`logit P(y) = a + b·logit p`), each with week-clustered 95 % intervals; 5-bin reliability table (bins 0–0.2, …, 0.8–1.0), stacked over the three outcomes and per outcome.
3. **Brier** (three-outcome sum of squares) with the Murphy decomposition (reliability, resolution, uncertainty) on the same 5 bins.
4. **Sharpness:** share of forecasts with `p_B` outside 40–60 %; SD of each outcome probability.
5. **AUC** per head, diagnostic only.
ECE is reported descriptively and never used in a rule. Every number carries N, clusters and the AMBIGUOUS / out-of-corridor counts.

## 7. Gates and display states

**Calibrator.** Per head (R and B), two-parameter Bayesian logistic recalibration `logit p' = a + b·logit p`, Gaussian prior, MAP plug-in, weekly batches, versioned. Identity prior for the held-out prequential pass: `a ~ N(0, 0.5²)`, `b ~ N(1, 0.25²)` [F3]. Live prior: the held-out posterior with its covariance inflated to an equivalent of 150 events [F3] (FORECAST_LAYER §5: 100–200). Published probabilities are rebuilt from the two calibrated heads. No isotonic or other non-parametric calibrator below 300 events.

**Level effect rule.** The level offset is claimed (published model = calibrated champion) only if the champion is not B0 **and** on the held-out read the raw champion's paired log-loss gain over raw B0 has a week-clustered 95 % interval above 0 for that landmark. Otherwise the calibrated **B0** is what is published for that landmark and no level effect is claimed (FORECAST_LAYER §6).

**Held-out tolerance → `L3_HISTORY_BACKED`** (per landmark class, all of) [F3]:
- G0: at least 200 scored held-out events.
- G1: published log-loss not worse than raw B0: upper end of the 95 % interval of `LL_published − LL_B0` ≤ +0.01 nats.
- G2: per outcome, |CITL| ≤ 5 pp and its 95 % interval inside ±10 pp.
- G3: per head, the 95 % interval of the recalibration slope overlaps [0.8, 1.25].
A class that fails stays `HIST` (or `FALLBACK` if a fallback model is available); Day 0 is not delayed (FORECAST_LAYER §6).

**Live floor → `L3_LIVE`:** at least **150** resolved live forecasts in the class [F3] and the live published probabilities meeting G2 and G3 on the live record.

**Drift → `FALLBACK` / `OFF`** (monitors frozen before display) [F3]:
- D0 → `OFF` at once: a data fault, stale bars at issue (last closed bar older than 10 minutes), or a parity break of the live detector against the research constructor.
- D1: per outcome, a mixture betting e-process on `y − p` of the published probabilities, `E_t = mean over λ ∈ {−0.5, −0.25, +0.25, +0.5} of Π (1 + λ (y_i − p_i))`, started at entry into the state; `E_t > 10` → `FALLBACK`.
- D2: over the last 100 resolved events, the CITL point estimate of some outcome outside ±10 pp **and** its 95 % interval excluding 0 → `FALLBACK`.
- D3: over the last 100 resolved events, `LL_published − LL_B0` with a 95 % interval above 0 → `FALLBACK`.
- Input drift (σ level, position distribution, event rate) is reported weekly and changes no state.
- **Return:** at least 50 new resolved events since the fallback, with the champion's shadow published probabilities on them inside D2's band, D1 restarted at the fallback ≤ 10, and D3 not triggered.

**`FALLBACK` model:** the generic race engine's B0 with its own calibration line (FORECAST_LAYER §5–§6), when that engine exists (another track; dependency Q4); until then raw B0 with its held-out tracked accuracy. The level offset is not claimed in this state.

## 8. Challenger C1

- `C1` = the frozen champion's M1-family specification (M1 if the champion is B0) plus `OTHER_VENUE_MEDIAN_MOVE` exactly as #363 defines it (median of the Bybit BTCUSDT-linear and OKX BTC-USDT-SWAP oriented 15m log returns from the close of the last bar before T to the close of bar j+2; all three venues required; no fill), z-scored with training-fold moments, entering head B on T15 rows only (0 at T0: the move is not defined before D). One extra parameter, same λ as its base.
- Frozen with the champion; logs in shadow from registration on live three-venue klines; promotion only by FORECAST_LAYER §7 (≥ 150 paired events, week-clustered interval of the log-loss gain excluding 0, calibration not worse). Its development numbers are descriptive. It replaces portfolio P3-2; #363's `LEVEL_SPECIFICITY = NOT_ESTABLISHED` is unchanged.

## 9. Wording templates (ids frozen; prices only)

`{P_UP}` is the upper barrier price, `{P_DN}` the lower, always in that order (never ordered by BREAK/REJECT). The three outcomes are always shown together. Percentages are integers summing to 100 (largest remainder). Every line carries `данные на {HH:MM} UTC`; the disclaimer lives once in `/terms`. Never «пробой», «отбой», BREAK, REJECT, buy/sell, long/short, entry or target.

| Id | State | Text |
|---|---|---|
| `LR_HIST_V1` | `HIST` | «В истории похожих касаний (N = {n}): раньше дошла до {P_UP} — {h_up} % (обычно {b_up} %), до {P_DN} — {h_dn} % (обычно {b_dn} %), ни до одной за 4ч — {h_ne} % (обычно {b_ne} %).» |
| `LR_HIST_LOW_N_V1` | `HIST`, n < 30 | «В истории похожих касаний мало данных (N = {n}).» |
| `LR_L3H_V1` | `L3_HISTORY_BACKED` | «≈ {p_up} % раньше {P_UP}, чем {P_DN} · ≈ {p_dn} % раньше {P_DN}, чем {P_UP} · ни одной за 4ч ≈ {p_ne} % · обычно {b_up} / {b_dn} / {b_ne} % · на истории: говорили {r_p} % → было {r_y} %, N = {r_n} · live: копится (N = {m})» |
| `LR_L3L_V1` | `L3_LIVE` | as `LR_L3H_V1`, the last segment «live: говорили {l_p} % → было {l_y} %, N = {l_n}» |
| `LR_FB_V1` | `FALLBACK` | «≈ {q_up} % раньше {P_UP}, чем {P_DN} · ≈ {q_dn} % раньше {P_DN}, чем {P_UP} · ни одной за 4ч ≈ {q_ne} % · общая модель цены, без учёта уровня · точность: говорили {f_p} % → было {f_y} %, N = {f_n}» |
| `LR_OFF_V1` | `OFF` | «нет данных» |

- **HIST cohort (L2, past tense):** events of the same landmark in the history the state may read (2020–2024 before the held-out read; 2020–2024 plus held-out after it), in the same B0 bin (5 equal-width bins of `B0_up`). `h_*` = observed frequencies, `b_*` = mean B0 over the same cohort, `n` = cohort size. The bin set is fixed here and shown whatever it says.
- **«говорили X → было Y»:** the stacked 5-bin reliability table of the class (held-out for «на истории», the journal for «live»); the line shows the bin of the largest displayed probability: mean forecast, observed frequency, number of forecasts in that bin.
- `b_*` in L3 lines = B0 at this event (the «обычно» of FORECAST_LAYER §2).

## 10. Records, exposure, ledger

- **Journal:** classes `L3_LEVEL_RACE_T0_4H` and `L3_LEVEL_RACE_T15_4H` in `beta/claims.py` (shared file, F2's change), with the fields of FORECAST_LAYER §5 and evaluation rule id `LEVEL_RACE_4H_V1` (the #352 `classify` on `j+1 … j+48`, AMBIGUOUS excluded and counted).
- **Exposure ledger and atlas** (AGENTS.md): when development closes, one unit `LEVEL-RACE-FORECAST-V1` is added to `ATLAS_UNITS_V1.yaml` (row `PRICE_STRUCTURE.levels`, cols `CANDLES` and `CROSS_VENUE` for C1) with `CORE_BTC_BINANCE_V0` 2020-02..2024-12 and `LEVEL_CROSS_VENUE_PERP_5M_V0` 2020-04..2024-12 entries `CONSUMED` (further exposure of the level row, model development, not a confirmation), rebuilt with `python -m scripts.research.atlas.build_atlas` and a hash-chained `--append-event`; `docs/RESEARCH_LEDGER.md` gets the row. The held-out read adds a `BINANCE_UM_KLINES_5M_PRODUCT` 2025-01-01..freeze-date entry (E1 gap excluded, class B disclosed) the same way.
- **Search exposure:** 6 menu entries; 3 M1 variants × 4 λ = 12 development fits, plus B1, B0 (no fit) and C1 (1 fit); 2 landmarks; 3 outcomes (2 heads); 4 folds. All are reported.
- **Prior knowledge disclosure:** the menu was chosen knowing the recorded #357, #361, #363, #365 aggregates on these same surfaces (FORECAST_LAYER §2). That is why development is `DISCOVERY` and the gate is the held-out read.

## 11. What would change our mind; limitations

- **No level effect:** no M1 variant beats B0 out of fold, or the held-out gain interval includes 0 → the level offset is not claimed; calibrated B0 is published. This is a complete result.
- **Geometry is a poor «обычно»:** large out-of-fold CITL of raw B0 (e.g. NEITHER off by > 10 pp) is reported as such; B0 is not re-specified after the outcome (that would be a new version).
- **Unstable offset:** M1 intercepts that change sign across test years are reported; the champion rule is not changed.
- **Held-out fails G1–G3:** the class ships in `HIST` / `FALLBACK` at Day 0.
- **Limitations:** one venue for the event (Binance perp); about 7.5 events a week, so the T15 class carries roughly 450 held-out events; σ from the trailing 24h only; the B0 discretisation caveats of §2.1; held-out surface exposed (class B); two landmark rows per event are dependent (clustered, not modelled); the development folds' early training sets are small (2020 only for the first fold).

## 12. Open questions for the mini-head

- **Q1** B1 parameter count (§2.2): family × structural side (12 free frequencies per landmark) as written, or family only (6)?
- **Q2** `SIDE` = structural side (PxH / PxL) as in FORECAST_LAYER §3, not the approach side. Confirm.
- **Q3** The [F3] numbers in §7 (prior, G0–G3, live floor, D0–D3, return rule), to be settled with F3 before the held-out read.
- **Q4** `FALLBACK` depends on the generic race engine (another track); until then raw B0 with its held-out accuracy.
- **Q5** Held-out bars from product 5m klines (live parity) rather than 1m → 5m (development parity), with the 2024 parity preflight of §5.
- **Q6** Predictor module path `beta/level_race.py` (ОПГ-2 file), to agree with F2.
