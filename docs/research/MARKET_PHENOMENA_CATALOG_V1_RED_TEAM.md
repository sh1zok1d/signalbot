# MARKET_PHENOMENA_CATALOG_V1 — independent red team

**Date:** 2026-10-09.
**Subject:** `MARKET_PHENOMENA_CATALOG_V1.md` (41 phenomena), treated as written by an untrusted author.
**Machine-readable records:** `MARKET_PHENOMENA_CATALOG_V1_RED_TEAM.json` (all 41 audit records with every field).

**Method.**
- Three independent read-only auditors checked the primary sources against the catalog's claims: prereg, design and result docs, feature code, manifests, the atlas, mechanism memory, and Cursor branches via `git show`.
  - The first covered range, barrier and attempt ideas.
  - The second covered flow, speed, countermove and positioning.
  - The third covered clock, venue and the exposure ledger.
- The architect then audited each idea against those sources. Where the catalog and a canonical source disagree, the source wins.
- **No market outcome was computed and no market data was read for this audit** (§10).

**Standard.** A surviving idea must be implementable by another researcher without asking what "flat", "pressure", "rejection", "leader", "countermove" or "accumulation" means, and without future information.

## 1. Headline

| Verdict | N | IDs |
|---|---|---|
| SURVIVE | 1 | S1 (re-specified as SIGNED_PATH_ASYMMETRY_24H) |
| REPAIR_NEEDED | 5 | A1, B1, C1, T2, T3 |
| DEFER_DATA | 2 | V1, V2 |
| REJECT_DUPLICATE | 25 | A2, A4, A5, A6, A7, B2, B3, E1, E2, E3, E4, E5, C2, C3, F1, I1, I2, R1, T4, V3, V4, X1, Q4, Q5, Q6 |
| REJECT_UNCLEAR | 6 | S2, R2, T1, Q1, Q2, Q3 |
| REJECT_LOOKAHEAD | 1 | F2 |
| REJECT_NOT_DIRECTIONAL | 1 | A3 |

**Novelty classes:** GENUINELY_NEW 4 (A3, S1, I2, V2), ADJACENT_BUT_DISTINCT 14, COSMETIC_RESCUE 16, UNCLEAR_NOVELTY 5, ALREADY_TESTED 2.

**What went wrong in the catalog, systematically:**
1. **The novelty argument rested on lists that do not exist.**
   - The catalog repeatedly says an idea is "explicitly listed as not killed" by H01, H02, H04, B2-02, B2-03, B2-04, #352, #353, D7, DH3-P1, MARKET-01, R03, #363 or the opening-range closure.
   - No canonical record contains such lists. They were the collision auditors' inferences, presented as record text.
   - The records often say the opposite. For example:
     - D7 lists direction under "Not established" and authorizes no children;
     - B2-04: "No second H04-derived child";
     - B2-03 forbids "another morphology component";
     - DH3-P1 forbids "rescuing it with a neighbouring state or endpoint".
2. **The replication claim was too generous.** "Both ERA surfaces are unread for every row except levels" is false (§8).
3. **Governance texts were missed:**
   - B2-05's verbatim forbidden formula list;
   - D7's child ban;
   - D12's "equity-open child" ban;
   - the opening-range "US, Europe, or Asia session anchor" ban;
   - DH1-X4 ("family J sessions exhausted");
   - the M04 basis family;
   - the BLOCKED_METHOD `venue_disagreement` cell.
4. **Chart concepts carried hidden lookahead.** Swing pivots, rolling boxes, flat-end selection and ramp times derived from data were not dated at their confirmation time (§2.1).
5. **Most "tilt" and "decay" states reduce in large part to current position, signed return, trend or σ** unless the baseline names those explicitly (§2.2).

## 2. Cross-cutting findings

### 2.1 Lookahead and leakage (U)

| Concept | Problem | Repair rule |
|---|---|---|
| Swing high/low, pivot, pullback, leg (A5, B1–B3, C1–C3, E2, F2, Q) | No zigzag exists in the repo. A k·σ zigzag pivot is known only after a k·σ reversal. The only repo swing (SEED-0001 3/3 fractal) is known at bar i+3. The last leg is always unconfirmed at T. | Timestamp each pivot at its confirmation bar. Use only pivots confirmed by T. Exclude the open leg. |
| Rolling box / range (A1–A7, F1, B3) | H02's `prior_range` uses [i−n, i). A probe below the box resets R_low, so the box moves while pressure is measured. "Flat" thresholds taken from sample quantiles are not point-in-time. | Freeze the box at T. Use trailing (causal 30d midrank) thresholds. |
| Flat selected at its end (A1, Q1) | One decision per flat taken at the last bar before the exit leaks the exit. | Evaluate at every qualifying anchor with spacing; keep NEITHER; cluster by week. |
| Touch defined as a swing extreme (B1) | Confirming the touch needs a reversal, which conditions the sample toward REJECT. | Decide at zone entry. Censor the latest amplitude. |
| Emergent barrier (B1–B3) | A deeper probe re-centres a pivot-defined barrier (circular in B3). | Freeze the barrier at formation. |
| Activity ramps (T1) | "Ramp times from the D12 profile" would be an in-sample event definition. D12 publishes no profile and bans "selected UTC hours". | Fixed exchange clocks only (IANA tz). |
| Excursion speed (A4, S1 passage times, C2) | Open excursions at T: dropping them is survivorship. Slow passages started near T cannot complete (censoring bias). | Censor, or re-specify without passage times (S1 → semivariance share). |
| Flow vs same-bar return (E1) | λ > 0 by construction (simultaneity). | Not lookahead, but the baseline must hold 24h net flow and 24h return. |
| OI alignment (E3, E4) | create_time is the bucket start. A one-bar shift changes contemporaneous corr(ΔOI, Δp). | Freeze the as-of rule (snapshot labelled with bar j's open, used at j's close). |

### 2.2 Baseline confounds (V)

| Idea | It could be nothing more than | Minimum nuisance baseline |
|---|---|---|
| A1 | signed return over the box window plus current position | B0 (driftless two-edge first passage from p_T); R_W; R_1h; width/σ; σ tercile; hour |
| A2, A4 | bar-return signs, S1 | S1, R_W, B0 |
| A3 | falling σ relative to width plus position | σ change, B0, A1 |
| A5 | trend plus a barrier | R4, R24, B0, the B1 object |
| B1 | waiting time between touches (#353's reason to exclude it), σ decay, touch ordinal, proximity | touch ordinal, inter-touch time, σ_now/σ_first, oriented R4/R24, hour, pseudo-barrier half-rotation |
| C1 | trend strength, latest pullback depth (H04), σ decay | leg size in σ, latest depth, R4, R24, σ tercile and change, hour |
| S1 | signed momentum (R24, R4) and RV | R24 and R4 continuous, σ tercile, hour, weekend |
| E1 | 24h net flow and 24h return; volatility | net flow, return, their interaction, RV |
| T2, T3 | hour-of-day drift; generic 30m→4h or 8h→8h momentum at any clock | the same statistic on every placebo clock offset; R24; σ; weekday |

### 2.3 Hidden degrees of freedom (W)

| Candidate | Tunable choices (count) |
|---|---|
| A1 | box window W, flat threshold, occupancy statistic, slice count, chord definition, exit buffer, horizon, anchor spacing (8) |
| B1 | pivot rule, zone width w, sub-X refractory, minimum touches, decay statistic, barrier freeze rule, horizon (7) |
| C1 | pivot rule and bar size, number of pullbacks, decay statistic, leg definition, normalization, horizon (6) |
| S1 (re-specified) | window, bar, statistic, horizon (4); all frozen to one cell |
| T3 | drive window, horizon, drive statistic (3); all fixed by the exchange clock |
| T2 | session definitions (fixed by exchanges), statistic, horizon (2–3) |
| E1 | window, frequency, estimator, sign-split rule, normalization reference (5) |
| Q1–Q3 | products of component choices: about 100–300+ latent branches → `HIGH_ADAPTIVE_SEARCH_RISK` |

### 2.4 Directionality

- **Intrinsically signed:** A1, A2, A4, A6, A7, S1, S2, I2, R1, E1, E5, X1, V2, V4, T2, T3, T4.
- **Sign only from the leg:** C1–C3, E2, R2.
- **Unsigned unless interacted:** A3 (decay), E3 (OI build; the sign is an added taker leg), E4 (coupling), I1 (composition).

## 3. All 41 verdicts

| ID | Title | Novelty | Observability | Directional | Replication | Verdict | Main reason |
|---|---|---|---|---|---|---|---|
| A1 | Internal range migration | ADJACENT | repairable | yes | PARTIAL | **REPAIR_NEEDED** | slope ≈ signed return; repair to an occupancy residual beyond the chord; atlas ruling |
| A2 | Close-location skew | ADJACENT | OK | yes | PARTIAL | REJECT_DUPLICATE | internal duplicate of S1 path asymmetry plus a C013-neighbour CLV |
| A3 | Midline-crossing decay | NEW | lookahead (moving midline) | **no** | PARTIAL | REJECT_NOT_DIRECTIONAL | decay is unsigned; the sign is position or occupancy |
| A4 | One-sided return speed | ADJACENT | censoring | yes | PARTIAL | REJECT_DUPLICATE | S1 restricted to a box; #353 speed neighbour |
| A5 | Envelope asymmetry | ADJACENT | pivot lag | yes | PARTIAL | REJECT_DUPLICATE | B1 + trend; hidden-divergence geometry (closed line) |
| A6 | Location-conditional aggression | COSMETIC | OK | yes | PARTIAL | REJECT_DUPLICATE | taker-imbalance subgroup (#358/H05); taker children barred |
| A7 | Value-area migration | ADJACENT | OK (fixed grid) | yes | PARTIAL | REJECT_DUPLICATE | weighting variant of A1 on the existing `volume_poc` object |
| B1 | Rejection-amplitude decay | UNCLEAR | repairable | yes | PARTIAL | **REPAIR_NEEDED** | canonical touches need ≥ 1.0X clearance; new event definition; levels row consumed |
| B2 | Inter-touch interval compression | ADJACENT | OK | yes | PARTIAL | REJECT_DUPLICATE | collinear with B1; already a #353 nuisance |
| B3 | Penetration creep | COSMETIC | circular | yes | PARTIAL | REJECT_DUPLICATE | H02/B2-02 overshoot child; forbidden wick/close-back rules |
| E1 | Flow-impact asymmetry | COSMETIC | OK | yes | PARTIAL | REJECT_DUPLICATE | B2-05 forbidden formulas ("price_move/IMB", "BUY-only/SELL-only"); B2-05 outcomes read on CORE |
| E2 | Swing efficiency decay | COSMETIC | pivot lag | via leg | NO | REJECT_DUPLICATE | unauthorized D7 child; closed exhaustion line |
| E3 | Signed OI build in flat | COSMETIC | OK | only via taker leg | NO | REJECT_DUPLICATE | DH3-P1 endpoint swap; #358 OI×taker ban; no pre-2020 OI |
| E4 | OI–price coupling regime | COSMETIC | alignment | unsigned | NO | REJECT_DUPLICATE | DH3-O3 template with OI; inconsistent with the catalog's own §6 |
| E5 | Effort without progress | ALREADY_TESTED | OK | yes | PARTIAL | REJECT_DUPLICATE | B2-05 low tertile at a forbidden W; exhaustion line |
| C1 | Pullback-magnitude decay | ADJACENT (weak) | repairable | via leg | PARTIAL | **REPAIR_NEEDED** | needs pivot spec and an H04-child ruling |
| C2 | Recovery-speed acceleration | ADJACENT | censoring | via leg | PARTIAL | REJECT_DUPLICATE | collinear sibling of C1 |
| C3 | Equilibrium recapture decay | ADJACENT | OK | via leg | PARTIAL | REJECT_DUPLICATE | anchor substitution of C1; trend by construction |
| F1 | Reclaimed-probe sequence | COSMETIC | rolling box | yes | PARTIAL | REJECT_DUPLICATE | H02/B2-02 failed-cell child; frozen box = opening-range object |
| F2 | Attempt-lifetime decay | ADJACENT | **lookahead** | yes | PARTIAL | REJECT_LOOKAHEAD | needs the current leg's end; repaired version = S1/C1 |
| S1 | Path asymmetry (re-specified) | NEW | OK | yes | PARTIAL | **SURVIVE** | simple, ex-ante, never measured; must beat signed momentum |
| S2 | Asymmetric shock persistence | ADJACENT | OK | yes | PARTIAL | REJECT_UNCLEAR | inherits C027's confounding problem (not "support") |
| I1 | Ignition composition | COSMETIC | OK | unsigned | PARTIAL | REJECT_DUPLICATE | C001 observable in B2-03's barred frame; trade_count semantics unpinned |
| I2 | Signed semivariance shift | NEW | OK | yes | PARTIAL | REJECT_DUPLICATE | merged into S1 (one frozen statistic) |
| R1 | Volume-elasticity asymmetry | COSMETIC | OK | yes | NO | REJECT_DUPLICATE | sign-split D7 IMPACT_PROXY; ERA consumed by D7 |
| R2 | Autocorrelation regime switch | ADJACENT | OK | via momentum | PARTIAL | REJECT_UNCLEAR | no mechanism pins the regime rule; closed continuation family |
| T1 | Quiet-before-activity tilt | UNCLEAR | ramp derivation | yes | PARTIAL | REJECT_UNCLEAR | owner's clock is Asia midday (G01-X8 closed); DST cannot identify Asian clocks |
| T2 | Session handoff | ADJACENT | OK | yes | PARTIAL | **REPAIR_NEEDED** | DH1-X4 and opening-range session-anchor bans → OWNER_DECISION |
| T3 | US open drive | ADJACENT | OK | yes | PARTIAL | **REPAIR_NEEDED** | D12 "equity-open child" ban and session-anchor ban → OWNER_DECISION |
| T4 | Settlement basis unwind | COSMETIC | OK | yes | NO | REJECT_DUPLICATE | M04 basis family; post-settlement paths already read by the funding unit |
| V1 | Venue leadership order | COSMETIC risk | tick only | yes | NO | **DEFER_DATA** | tick tapes needed; same function as blocked GV0R01-C002 |
| V2 | Coinbase premium | NEW | OK | yes | PARTIAL | **DEFER_DATA** | not in inventory; Coinbase + USDT-USD to pin |
| V3 | Cross-venue barrier disagreement | ALREADY_TESTED | unaudited wicks | yes | NO | REJECT_DUPLICATE | BLOCKED_METHOD cell (DH3-X6, C018); Bybit/OKX highs/lows unaudited |
| V4 | Basis–price divergence | COSMETIC | OK | yes | PARTIAL | REJECT_DUPLICATE | spot-excess/basis substitution (#364 SP2, DH1-X7) |
| X1 | Top trader vs crowd | COSMETIC risk | OK | yes | NO | REJECT_DUPLICATE | substitution around refuted P3; parser needed; PROSP only |
| Q1 | Migration → pressure | UNCLEAR | inherits | yes | PARTIAL | REJECT_UNCLEAR | HIGH_ADAPTIVE_SEARCH_RISK (≈300+ branches); successor-only |
| Q2 | Countermove decay → ceiling | UNCLEAR | inherits | yes | PARTIAL | REJECT_UNCLEAR | HIGH_ADAPTIVE_SEARCH_RISK; built on rejected B2 |
| Q3 | Failed probes → quiet → release | UNCLEAR | inherits | yes | PARTIAL | REJECT_UNCLEAR | built on rejected F1 and a barred H01 child |
| Q4 | Spring test | COSMETIC | inherits | yes | PARTIAL | REJECT_DUPLICATE | H02 sweep relabel, lower-only |
| Q5 | Impulse flag contraction | COSMETIC | inherits | yes | PARTIAL | REJECT_DUPLICATE | COMPOSITION_OF_CONSUMED (H03 + H04 + #355 dwell) |
| Q6 | Distribution upthrust | COSMETIC | inherits | yes | PARTIAL | REJECT_DUPLICATE | closed exhaustion line |

**Exposure, recorded per idea in the JSON:**
- On CORE 2020–24, the generic hourly 4h UP/DOWN-first race stream (LEVEL_RACE_FORECAST_V1 §8a: GB0, G1 with {1, SIGMA_T}) already read the unconditional O1 outcome at every hourly anchor. Each new state's conditional relation is unread.
- Exceptions where the input or the exact outcome relation was read:
  - **E1/E5:** B2-05 absorption outcomes;
  - **T4:** post-settlement paths;
  - **E3/E4/X1:** oi_buildup / leverage_crowding consumed;
  - **B-family:** levels consumed.

## 4. Corrected ranking

Old top-15 plus the two session ideas that rose.

| New # | ID | Old # | Verdict | Why it moved |
|---|---|---|---|---|
| 1 | S1 → SIGNED_PATH_ASYMMETRY_24H | 3 | SURVIVE | one frozen cell, no lookahead, never measured, testable now |
| 2 | T3 US_OPEN_DRIVE | — | REPAIR_NEEDED (owner key) | lowest DOF, clock fixed by the exchange; only governance blocks it |
| 3 | A1 → PATH_OCCUPANCY_RESIDUAL | 1 | REPAIR_NEEDED | the catalog version is mostly signed return; the repaired residual is new |
| 4 | C1 | 2 | REPAIR_NEEDED | weak novelty (sequence only); needs new swing code and an H04-child ruling |
| 5 | T2 SESSION_HANDOFF | — | REPAIR_NEEDED (owner key) | simple, but under the same session bans as T3 |
| 6 | B1 | 6 | REPAIR_NEEDED | new event definition; ≈7 DOF; confirmation essentially prospective |
| 7 | V2 | 13 | DEFER_DATA | new population, but acquisition first |
| 8 | V1 | 15 | DEFER_DATA | tick tapes; blocked-card duplicate risk |
| 9 | E1 | 5 | REJECT_DUPLICATE | B2-05 relabel; only via OWNER_DECISION on a fresh surface (§5.5) |
| 10 | S2 | 12 | REJECT_UNCLEAR | C027 confounding |
| 11 | T1 | 4 | REJECT_UNCLEAR | identification fails |
| 12 | F1 | 9 | REJECT_DUPLICATE | H02 failed-cell child |
| 13 | A7 | 7 | REJECT_DUPLICATE | A1 variant on `volume_poc` |
| 14 | A5 | 8 | REJECT_DUPLICATE | B1 + trend |
| 15 | R1 | 11 | REJECT_DUPLICATE | D7 child |
| 16+ | Q1, E3 | 10, 14 | REJECT | sequence search risk; DH3-P1 rescue |

## 5. Deep audits

### 5.1 A1 INTERNAL_RANGE_MIGRATION
- **What is new.** Only the part of the box path not fixed by its endpoints. With fixed H/L, the slope of slice medians ≈ (p_T − p_start)/W, i.e. signed return in box units. The new content is whether price spent more time high than the straight start-to-now path implies.
- **Strongest collision.**
  - DH3-P1 QUIET (bottom-tercile 48-bar range) with its "neighbouring endpoint" ban. A1 drops OI and adds a new feature, so it is not P1's state, but the reviewer must rule.
  - H01 prereg:14 "Non-directional mechanism test only" supports that direction is untested.
  - No "range internals" row exists: the nearest rows (compression, breakout, path_shape × CANDLES) all hold CORE units.
- **Frozen formula (proposal):**
  - **Anchors:** hourly T.
  - **Box:** the 48 5m bars ending at T; H = max high, L = min low; p_i = (c_i − L)/(H − L).
  - **Quiet:** log(H/L) ≤ the trailing 30-day lower-tercile of the same statistic at hourly anchors (point-in-time).
  - **State:** OR = mean(p_1..p_48) − (p_1 + p_48)/2.
  - **Outcome:** first touch of H vs L within 8h (three-way; NEITHER kept).
  - **Estimand:** the coefficient of OR on 1{H first}, offset by B0 = (ln c_T − ln L)/(ln H − ln L), with R_W, R_1h, width/σ, σ tercile and hour as nuisance. Week-clustered bootstrap.
- **Baseline that kills the trivial reading:** B0 + R_W + R_1h. If OR adds nothing beyond them, A1 was only position and momentum.
- **Data now:** CORE 2020–24 (discovery).
- **Independent replication:** BitMEX tradeBin 5m 2016–19 and spot 5m 2017–19.
  - These are TIME_DISJOINT_EXPOSED_SURFACE: the row is unread, but paths were read in bulk for other rows.
  - Plus PROSP.
- **Biggest leakage risk:** flat-end selection and sample-quantile thresholds.
- **Biggest p-hacking degree:** box window and flat threshold.
- **Verdict:** REPAIR_NEEDED. Executable after the formula above is frozen in a design note and an atlas novelty ruling is recorded.

### 5.2 C1 PULLBACK_MAGNITUDE_DECAY
- **What is new.** The trend of successive countertrend excursion depths inside one leg. H04 used one 60m pullback; B2-04 the recovery within one pullback; B2-03 shallowness within one 15–60m move. Novelty relies on the *sequence* (three pullbacks rather than one), so it is weak.
- **Strongest collision:**
  - H04/B2-04 ("No second H04-derived child... authorized");
  - PRICE_STRUCTURE.pullback × CANDLES is CLOSED_ON_SURFACE on CORE;
  - SEED-0002 hidden-divergence continuation, under the closed line.
- **Frozen formula (proposal):**
  - **Pivots:** SEED-0001's 3/3 fractal on 1h bars, each timestamped at its confirmation (bar i+3).
  - **Up-leg state at T:** the last three confirmed swing lows rise and the intervening swing highs rise.
  - **Depths:** d_k = (H_k − L_{k+1})/σ_1h.
  - **State:** d_3 < d_2 < d_1, vs not monotone.
  - **Outcome:** O1 oriented by the leg, 4h.
  - **Nuisance:** leg size in σ, d_last, R4, R24, σ tercile and σ change, hour. Mirror for down-legs.
- **Kill baseline:** leg size + d_last + R4/R24. If decay adds nothing, C1 is trend strength.
- **Data now:** CORE. **Replication:** ERA at 5m → 1h fractals (exposed-surface class); PROSP.
- **Biggest leakage risk:** dating pivots at the extreme instead of at confirmation.
- **Biggest p-hacking degree:** pivot rule and pullback count.
- **Verdict:** REPAIR_NEEDED (spec + ruling).

### 5.3 S1 TRAVERSAL_TIME_ASYMMETRY → SIGNED_PATH_ASYMMETRY_24H
- **What is new.** A signed path-shape state never measured in the repo: no semivariance, realized-skew state or passage-time code exists. D3's PATH_ASYMMETRY was a forward outcome functional removed before execution.
- **Strongest collision:**
  - D3 (unconditional forward excursions, NO_STRUCTURE);
  - the D2 "no nearby RV variants" rule (SPA is signed, a different function);
  - the H03/H05 quarantined asymmetries (not used).
- **Frozen formula:**
  - r_i = 5m log returns of the 288 bars ending at T, with at least 90 % present.
  - RS± = Σ r_i² over r_i ≷ 0; SPA = (RS+ − RS−)/(RS+ + RS−).
  - **Outcome:** O1 UP_FIRST_4H with the DH1 X (neither 0.5; three-way reported).
  - **Model:** LPM on SPA (standardized) with R24 and R4 in σ units (continuous), σ tercile, 4h UTC hour block, weekend flag; week-clustered bootstrap (2000).
  - **One cell.** The passage-time version and the 2–6h change version (I2) are not tested.
- **Kill baseline:** R24 + R4 (signed momentum) and RV. If SPA adds nothing, it was momentum.
- **Data now:** CORE 2020–24 at hourly anchors.
- **Replication:**
  - BitMEX tradeBin 5m closes 2016-05..2019-12 (22,728 zero-trade buckets → 90 % rule) and Binance spot 5m 2017-08..2019-12. The path_shape row is unread on both, but the surfaces are exposed for other rows, so the class is TIME_DISJOINT_EXPOSED_SURFACE.
  - PROSP on live `klines_1m`.
- **Biggest leakage risk:** none in time. The search risk was the choice among passage-time / semivariance / skewness, now frozen.
- **Verdict:** SURVIVE (as re-specified).

### 5.4 T1 QUIET_BEFORE_ACTIVITY_TILT
- **What is new.** Nothing that is identifiable.
- **Strongest collision:**
  - G01-X8: Asia lunch 02:30–05:00 UTC, "Not identifiable: Asian clocks have no DST".
  - D12: fixed DST calendars, no ramps, "selected UTC hours" banned.
  - DH1-X4.
  - R03: a weekend-structure question needs "a surface it has not seen".
- **Facts:**
  - The owner's 06:00→07:00 Kyiv is 03:00→04:00 UTC in summer (EEST) and 04:00→05:00 in winter: Asia midday.
  - The catalog's "Europe ramp (07:00 London local)" is wrong: LSE opens 08:00 London, Xetra 09:00 Berlin (07:00 UTC summer, 08:00 winter).
  - Its identification ("stays at UTC → clock/algorithm") fails for Asian sessions.
- **Frozen formula:** none possible without a barred ramp definition.
- **Verdict:** REJECT_UNCLEAR. The owner's observation is preserved as a question about the 03:00–05:00 UTC window. Under current rules it is closed by G01-X8 and can reopen only by OWNER_DECISION with a surface not yet seen.

### 5.5 E1 FLOW_IMPACT_ASYMMETRY
- **What is new.** A 24h, sign-split response function instead of B2-05's 15–60m window interaction. Scientifically this is the "response function" class the owner wants: price displacement conditional on signed aggressive flow.
- **Strongest collision.** B2-05, verbatim forbidden: "`IMB / price_move`, `price_move / IMB`, … a different impact formula, thresholded absorption, a BUY-only descriptor, a SELL-only descriptor, or a second interaction descriptor"; close: "ratio rescue, BUY rescue, SELL rescue, sign reversal, a new H, or a new W".
  - B2-05 outcomes were computed and archived (280,017,092 bytes on `refs/heads/research-evidence/batch02/B2-05/…`), never transcribed.
  - The catalog's own example (low sell impact → up) matches H05's quarantined SELL-side reversal.
- **Frozen formula (if reopened):**
  - λ_side from an OLS of 5m r on signed taker quote over the 288 bars ending at T, split by the sign of bar net flow.
  - State log(λ_sell/λ_buy) vs its own trailing 30 days.
  - Nuisance: 24h net flow, 24h return, their interaction, RV. O1 4h.
- **Data now:** CORE kline taker (but CORE is B2-05's outcome surface: CONFIRMATION_ON_EXPOSED and search-exposed).
- **Independent data:** BitMEX trades 2017-08..2019-12 (taker = trade side; FLOW rows unread; inverse contract; liquidation fills not flagged).
- **Biggest leakage risk:** simultaneity.
- **Biggest p-hacking degree:** estimator and window.
- **Verdict:** REJECT_DUPLICATE under current governance. The only legitimate route is an explicit OWNER_DECISION reopening the absorption family, with discovery on BitMEX 2017-08..2019 and confirmation prospective.

### 5.6 B1 REJECTION_AMPLITUDE_DECAY
- **What is new.** Amplitude between touches below X. The level engine cannot see it: a canonical touch needs a clearance ≥ 1.0·X (`level_touch_degradation_v1/events.py:173-181`), and DH3-V3 a retreat ≥ 1.0X. The catalog's own example (0.62 %, 0.31 % with X ≈ 0.6–0.8 %) would not register as separate touches.
- **Strongest collision:**
  - #353 excluded this observable on purpose: "Max excursion until the next touch is not used. That path lengthens with the wait."
  - #352's pseudo-level control: later touches at non-structural prices broke **more** (+7.3, +4.7 pp), which is the relevant prior for emergent barriers.
  - DH1-X1 composition precedent.
- **Frozen formula (proposal):**
  - **Barrier:** U = a cluster of ≥ 2 confirmed 1h fractal highs within w = 0.15 % in the last 72h, frozen at the second confirmation.
  - **Touches:** zone entries after a retreat ≥ 0.25X (new event definition).
  - **Amplitude:** a_k = max retreat between touches in σ units.
  - **State at touch n ≥ 4:** a_{n−1} < a_{n−2} < a_{n−3}.
  - **Outcome:** ±X race from the zone edge within 4h (BREAK / REJECT / NEITHER).
  - **Nuisance:** touch ordinal, inter-touch time, σ_now/σ_first, oriented R4/R24, hour, pseudo-barrier half-rotation.
- **Data now:** CORE.
- **Independent replication:** PRICE_STRUCTURE.levels is CONSUMED on XBTUSD 2017-09..2019-12 and on spot 2017–19 (DH3-V3 replication, which is missing from the surfaces ledger; FROZEN-HOUR [branch]). Clean surfaces:
  - XBTUSD tradeBin 2016-05..2017-08 (≈ 15 months);
  - PROSP.
- **Biggest leakage risk:** a touch defined as a confirmed extreme.
- **Biggest p-hacking degree:** the refractory and the zone width.
- **Verdict:** REPAIR_NEEDED; lower priority because of the degrees of freedom and the weak confirmation route.

### 5.7 Q1 MIGRATION_THEN_PRESSURE
- **What is new.** Only the ordering of two states.
- **Strongest collision.** Its components sit in consumed neighbourhoods: B1 near #352/#353; C1 near H04/B2-04.
- **Latent branches.** About 8 (A1) × 7 (B1) × ordering/gap choices, i.e. several hundred.
- **Verdict:** REJECT_UNCLEAR, `HIGH_ADAPTIVE_SEARCH_RISK`. A sequence is admissible only as a frozen successor after each component has shown structure on its own.

## 6. The proposed execution units U1–U5

| Unit | Grouped ideas | Problem | Recommendation |
|---|---|---|---|
| U1 | A1, A2, A3, A5, A7 | Five correlated features with no declared primary: hidden multiplicity and the best feature picked after the outcome. Four of five are now rejected. | Replace with a **single-estimand** unit, A1-repaired (PATH_OCCUPANCY_RESIDUAL). |
| U2 | C1, C2, C3, F2 | Siblings of one mechanism; C2/C3/F2 rejected. | Single-estimand C1 after the pivot spec and the H04-child ruling. |
| U3 | S1, S2, I2, R1 | Four path-asymmetry statistics; three rejected. | Single-cell SIGNED_PATH_ASYMMETRY_24H. |
| U4 | T1, T2, T3 | Ambiguous primary; T1 rejected. | Split: T3 and T2 as separate single-estimand units, each only after an OWNER_DECISION key. If run as a family, declare T3 primary and use Holm. |
| U5 | E1, E2, E4 | All three barred under current governance. | Drop. E1 only via OWNER_DECISION on BitMEX 2017–19 (§5.5). |

**Rule for any future grouping:**
- one primary estimand per unit;
- at most one predeclared secondary;
- Holm across a family;
- the whole declared search reported;
- no feature added after the outcome.

## 7. Surfaces each survivor can use now (R) and replication for the top 10 (S)

| ID | Discovery now | Independent replication | Status |
|---|---|---|---|
| S1 | CORE 1m→5m 2020-01..2024-12, hourly anchors | BitMEX tradeBin 5m 2016-05-13..2019-12-31 and spot 5m 2017-08-17..2019-12-31 (row unread, surfaces exposed for other rows); PROSP | PARTIAL |
| T3 | CORE 2020–24 (IANA America/New_York) | ERA 5m with a pinned NYSE holiday calendar for 2016–19 (not in the repo yet); pre-ETF/pre-CME era changes the mechanism; PROSP | PARTIAL |
| A1 | CORE 2020–24 | ERA 5m (exposed-surface class); PROSP | PARTIAL |
| C1 | CORE 2020–24 | ERA 5m → 1h fractals; PROSP | PARTIAL |
| T2 | CORE 2020–24 | ERA 5m plus pinned LSE/TSE/NYSE calendars; PROSP | PARTIAL |
| B1 | CORE 2020–24 | XBTUSD tradeBin 2016-05..2017-08 only; PROSP | PARTIAL (weak) |
| V2 | none (acquire Coinbase 1m + USDT-USD) | Coinbase 2025–26 premium is an unread observable, but Binance outcomes are product-open; 2016–19 vs BitMEX is a different construction | PARTIAL |
| V1 | none (acquire tick tapes) | none before 2020; live `klines_1m` cannot order venues; forward collector frozen | NO |
| E1 (rejected) | CORE is B2-05's outcome surface | BitMEX trades 2017-08..2019 | PARTIAL, governance-barred |
| S2 (rejected) | CORE | ERA 5m | PARTIAL |

## 8. Ideas wrongly claimed confirmable on 2016–2019 (T)

- **The general claim** "ERA unread for every row except levels" is false. The ERA surfaces were read for other rows:
  - BitMEX tradeBin: tail_risk and execution_impact CONSUMED, paths read in bulk; EVENTS exposed;
  - DH1 BitMEX trades: levels CONSUMED 2017-09..2019-12, SPOT_PERP exposed;
  - spot 2017–19: levels read (DH3-V3 replication; FROZEN-HOUR [branch]), range_forecast census [branch], SPOT_PERP exposed.

  So every candles idea there is at best TIME_DISJOINT_EXPOSED_SURFACE (row unread), not pristine. Specific errors:
- **R1 and E2:** their ERA (BitMEX volume) is D7's consumed confirmatory surface.
- **B1, B2, B3 and U6:** "spot 2017–19 cleaner" is false; the levels row is consumed there and on XBTUSD 2017-09..2019-12.
- **T1:** the DST identification fails for Asian clocks; only about 6–8 DST transitions per era.
- **T4:** no Binance perp before 2019-09; spot USDT vs XBTUSD USD mixes the USDT basis.
- **V4:** the same USDT/USD contamination.
- **V2:** the 2016–19 construction against BitMEX is a different observable.
- **E3, E4, X1:** the catalog offered "Bybit OI" robustness, which is not in the inventory; there is no OI before 2020-09 anywhere.
- **V1:** the catalog offered PROSP on `klines_1m`, which cannot resolve sub-minute order.

## 9. Factual errors in the catalog (X)

1. **"Explicitly listed as not killed"**, claimed for A1/H01, C1/H04+B2-04, S1/B2-03, I1/B2-03, E1 and R1/D7, E3/DH3-P1+MARKET-01, B1–B2/#352–#353, F1/H02+B2-02, T1/R03, T3/opening-range closure, V1/V3/#363 and Q5/H04. No such text exists in any record on any branch.
2. §2: "ERA … unread for every row except levels" — false (§8).
3. §1: "the flow_conditional_response row has never held a unit" — misleading. The object was studied as B2-05 (outcomes computed) and as LEVEL-FLOW-RESPONSE-STATE-DISCOVERY-V1.
4. E1: "an ORTHOGONAL_MECHANISM ruling … is required" — wrong route. It falls under B2-05's verbatim forbidden list, so OWNER_DECISION.
5. B2-05 "consumed … with no result" — outcomes were computed and archived; only the transcription is missing.
6. S2: "resolves C027's support blocker" — C027 is blocked for confounding control; support was D8's blocker.
7. S1: "V03L40-C023 (downside path share)" — C023 is an on-chain exchange-deposit card blocked for lookahead; DOWN_SHARE is its outcome.
8. I1: "participant_composition × PERP_FLOW NO_STRUCTURE (TWAP footprint)" — TWAP-V1 sits in × SPOT (CLOSED_ON_SURFACE); × PERP_FLOW holds DH3-S3 and C001.
9. X1: "These metrics columns are pinned" — only the raw zips are pinned. Every parser keeps create_time, sum_open_interest and count_long_short_ratio only.
10. E3/E4: "Bybit OI (robustness)" — not in the inventory.
11. A5: "#352 (touch count, killed)" — #352 is LIVE_SIGNAL, L2 permitted, PRODUCT_INTEGRATION_CANDIDATE=YES.
12. B1/B3: "#353 … overshoot" — that overshoot is past the reject-side barrier, not penetration of the level.
13. B1: quotes #352's −6.6 pp without the pseudo-level opposite sign (+7.3/+4.7 pp) or the record's survivor reading (REJECT ≈ 50 %).
14. A7: omits the existing `volume_poc` (`beta/levels.py:105-123`) and the DH1 / DH3-V2 POC level units.
15. A1/U1: "untested row" — no range-internals row exists; the nearest rows hold CORE units.
16. T1: "Europe ramp (07:00 London local)" — LSE opens 08:00 London. The owner's 06:00→07:00 Kyiv is 03:00→04:00 UTC in summer (Asia midday).
17. T1: "stays at UTC → clock/algorithm effect" — wrong for Asian sessions (no DST; G01-X8).
18. T1: "ramp times from the D12 activity profile" — D12 publishes no profile or ramps, and "selected UTC hours" is a banned neighbour.
19. T1: "direction is forbidden as a D12 child" — the actual ban list is "selected UTC hours, EU as primary, or an equity-open child". The catalog missed the equity-open ban, which applies to T3, and the −0.174 EU diagnostic.
20. T4: "BLOCKER_RESOLVED route" — same-venue spot–perp basis is the M04 family; DH1-X7 closed on "basis × SPOT NO_STRUCTURE"; FUNDING_STATE_HISTORICAL_STRUCTURE_V1 already read post-settlement 1h/4h/8h paths at these anchors.
21. T4: "08:00 UTC is also the Europe ramp" — winter only. The Friday Deribit expiry at 08:00 UTC is omitted.
22. V1: PROSP on `klines_1m` cannot order venues seconds apart (D9: synchronous 5m closes "cannot establish … WHICH_VENUE_MOVED_FIRST"). "Bybit MT4 label shift" is irrelevant to trade tapes.
23. V3: omits that `venue_disagreement × CROSS_VENUE` is BLOCKED_METHOD (DH3-X6, GV0R01-C018). Bybit/OKX highs and lows were never audited (#363 used closes only).
24. §7: "Only 5m is pinned for BitMEX/spot 2016–19 … BitMEX tick trades acquirable" — Binance spot aggTrades 2017-08..2024-12 and BitMEX 2017-08..2019 daily tick files are SHA-256-pinned by digest (raw re-download needed).
25. §2 lists five atlas reopen keys; atlas §5 has eight (NEW_CONFIRMATION_SURFACE, RECORDED_REOPEN_CONDITION, NEW_INDEPENDENT_UNITS are missing).
26. §2: "X ≈ 0.82 % (2020–24 mean)" and "0.57 % (2025–26)" — these are means over P3's crowd-state trades, not over all hours.
27. DH3-P1 described as "WEAK +13.4 %" — atlas state NO_STRUCTURE (the bot shows a WEAK line).
28. §6 rejects the realized-vol correlation idea as an O3 substitution but keeps E4, which is the same template — internally inconsistent.
29. V1 data: "Bybit trades from 2020-03-25" — verified only by a HEAD request in this session; not recorded in the repo.

**Surfaces ledger gap (not a catalog error):** `ATLAS_SURFACES_V1.yaml` does not list the DH3-V3 replication's read of spot 2017–19 levels under `DH1_BINANCE_SPOT_BTCUSDT_5M_V0`.

## 10. Was any market outcome read? (Y)

- **Catalog work (five collision auditors).**
  - They read docs, JSON, manifests and code, and made HEAD requests to archive URLs.
  - The data auditor printed the first 2–3 rows and line counts of five pinned files to check schemas: DH1 BitMEX 5m, D2 and D7 canonical 5m, Bybit and OKX 5m. That is a handful of raw bars from the files' first days. No statistic, state or outcome was computed.
  - No other data access.
- **This red team (three auditors).** Docs and code only; one `git ls-remote`. No rows read.
- **Before the catalog, in the same session (not recorded until now).** While reporting P3 to the owner, the architect computed on Binance BTCUSDT perp 5m klines 2025-01..2026-08-14 (the P3 cache):
  - for every hourly start, the frequency of +4.495 % before −1.226 % within 48 bars (and the mirror);
  - the mean gross result with time exits;
  - the distribution of |4h return| (median 0.40 %, p90 1.42 %).

  This is an unconditional 4h path read on a product-open surface. It involves no catalog state. It is now recorded in `RESEARCH_LEDGER.md`.
- **Governance deviation (P3_CONFIRMATION_V1, not catalog work).**
  - `DIRECTIONAL_HYPOTHESES_DECISION_V1` sets the DH confirmation surfaces as 2017–2019 plus live tracking, with "no 2025/2026 object". `PRODUCT_DECISION_V2` §4 says a research claim over product features "needs a different untouched window or a prospective test".
  - P3_CONFIRMATION_V1 nonetheless confirmed DH3-P3 on Binance 2025-01..2026-08-14. It acted on the owner's oral FORECAST FIRST directive of 2026-10-09 but cited no written owner permit for that surface.
  - Its prereg disclosed that the surface was not pristine; it did not cite this rule.
  - The registry change DH3-P3 → NOT_CONFIRMED rests on that run.
  - Recorded now in the ledger and the P3 result. The owner should ratify or reclassify it.

## 11. Repository changes from the catalog work (§27)

- **`MARKET_PHENOMENA_CATALOG_V1.md`:**
  - contains errors 1–29 above;
  - left unchanged except for an errata banner that points here.
- **`CURRENT_RESEARCH_STATE.md`:**
  - the CANDIDATE_UNITS line (U1–U5) is superseded by this audit and is updated to point here;
  - no NEXT_UNIT contradiction, since the block never set one.
- **`PROJECT_HISTORY.md` §26:**
  - "price response to flow … and temporal venue leadership were largely untested" is inaccurate;
  - B2-05 computed flow-response outcomes, and venue leadership is a blocked generator card (C002);
  - a correction line is appended.
- **`DOCUMENTATION_INDEX.md`:** correct; this record is added.
- **P3 changes:**
  - Discovery verdict text preserved and the confirmation appended.
  - Atlas state LIVE_SIGNAL → CLOSED_ON_SURFACE.
  - Registry DISCOVERY → NOT_CONFIRMED, plus the tests that pinned DISCOVERY.
  - These follow the AGENTS rule for a closed unit, but carry the governance deviation in §10.
- **No sealed verdict of any other unit was altered.**

## 12. Recommendation: the first three worth executing (Z)

None runs before its design note is committed and the batch has an owner go.

1. **SIGNED_PATH_ASYMMETRY_24H (S1 re-specified).** Ready now: one frozen cell, CORE discovery, ERA (exposed-surface class) and PROSP replication.
2. **US_OPEN_DRIVE (T3).** The lowest-DOF directional estimand in the catalog. It needs an explicit OWNER_DECISION key against D12's "equity-open child" ban and the opening-range session-anchor ban, plus a pinned NYSE holiday calendar for the ERA.
3. **PATH_OCCUPANCY_RESIDUAL (A1 repaired).** The one flat/accumulation object that survives the "is it just signed return?" test conceptually. It needs the §5.1 formula frozen and an atlas novelty ruling recorded.

**Next in line:** C1 (pivot spec plus H04-child ruling), then T2. V1 and V2 wait for data.
