# Turn-of-month baseline evaluation — product-evidence unit V1 (G01-A1 / A2 successor)

**Status:** `DESIGN_NOTE / COMMITTED BEFORE ANY OUTCOME / NOT_RUN / RUN ONLY AFTER A SEPARATE OWNER GO`
**Date:** 2026-10-05
**Owner routing:** 2026-10-05, after `research/EVALUATOR_VARIANTS_COMPARISON_V1.md` (decision O1): "G01-A1/A2 as a product baseline evaluation; first a design note before the outcome, run only after the owner's go".
**Authority:** `research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` §3 (design note) and §4 (claims). The template is `WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md`.

**Tracks.**
- **`PRODUCT_EVIDENCE` (primary, Part B):** are the bot's activity and range labels calibrated the same way on turn-of-month days as in mid-month?
- **`STRUCTURE` (secondary, Part A):** how large is the day-level turn-of-month shift?

There is no directional claim and no `EDGE` track.

**Relation to G01.** G01-A1 (`TOM_PARTICIPATION`) and G01-A2 (`TOM_RANGE`) stay closed as recorded (`research/AUTOGEN_G01_DECISION.md`). This is a new object with its own id. It reuses G01's frozen day sets unchanged and drops the 0.5 SD bar and the replication gate, as the evidence model does. Nothing in the G01 records changes. Audit context: `research/RESEARCH_HISTORY_AUDIT_V1.md` §6.A and `research/RESEARCH_HISTORY_AUDIT_V1_ERRATUM_1.md`.

## 1. Question (estimand)

> Do the bot's reference distributions fire at the same rates on turn-of-month days as on mid-month days of the same months, under the construction on `main`? And how large is the day-level participation and range shift on those days?

**Day sets.** These are G01's, imported unchanged from `scripts/research/autogen_g01/states.py`.

| Set | Definition | Unit |
|---|---|---|
| **TOM** (`tom_state_days`) | the last UTC day of the previous month (dropped when it is that month's last-Friday expiry day) and days 1–3 of month m | month m |
| **MID** (`comparator_days`) | days 8–21 of month m | month m |
| both | minus the fixed holiday windows Dec 24–Jan 2 and Oct 1–7 (`in_holiday_window`) | — |

Days in neither set are not compared. They stay in every reference, as in production.

## 2. Data and exposure

- **Data.** `CORE_BTC_BINANCE_V0` BTCUSDT perpetual 1m, `[2020-01-01, 2025-01-01)`.
  - It comes through the pinned, SHA-verified loader `scripts/research/owner_cards_r03/data.py::load_btc_1m`.
  - Trade count, for Part A only, is column 8 of the **same** pinned zips (`btc_pinned_sources`, the same SHA-256). It is read beside the loader and asserted to align with its `open_ms`. No new data object is used.
  - This is a single-venue proxy (label `PROXY_SINGLE_VENUE`). The production 3-venue median, venue agreement, OI and taker ranks are not evaluated.
- **Exposure.**
  - The surface is exposed: R03, DH3, the weekday/weekend unit and others read it.
  - **No turn-of-month contrast has ever been computed on it, for any metric:**
    - G01 closed outcome-blind;
    - the committed weekday/weekend result holds only weekday / weekend × year aggregates. Only its key names were checked for this note, not its values.
  - The result is retrospective product evidence, not a confirmation.
- **Not used:**
  - **BitMEX 2017–2019,** G01's declared replication surface. It stays unread for this contrast and remains available as a later labelled check (trade count and OHLC; no volume).
  - **The 2025/2026 product surface.** `PRODUCT_DECISION_V2` §4 opened BTCUSDT 5m klines for product statistics, minus the E1 holdout. The owner may add it at go time as a labelled secondary slice (about 19 more months), through its own loader. Default: not used.
  - **The live beta tape.**

## 3. Constructions measured (no new candidate)

| Id | What | Status on 2026-10-05 |
|---|---|---|
| **C1** (primary) | same UTC day type inside the 30-day window: `BETA_CONTEXT_1H_V3` for 1h / 4h ranks of range, move and volume; `BETA_HORIZON_TOD_V3` for the 1h TOD range / volume baseline (≥ 8 same-type days) | on `main` (#329), not deployed |
| **C0** (secondary) | pooled 30-day reference (`BETA_CONTEXT_1H_V2`, `BETA_HORIZON_TOD_V2`) | deployed |

The 24h baseline is the same in both: production `_baseline_24h`, the median of the prior 30 days' rolling 24h values, with ≥ 20 days.

**No correction candidate is evaluated here.** Only one construction would fit the TOM case: a point-in-time TOM factor, as C3 was for weekends. A same-type split like C1 is impossible: about 4 TOM days fall in any 30-day window, against the 8 needed. If a correction is warranted, it is a follow-up unit (§6).

## 4. Method (chosen before outcomes)

**Frequentist, month-clustered; no prior.** Decision O1 allows a posterior per unit. It is not used here, because no commensurable reference set exists for the participation endpoint (`EVALUATOR_VARIANTS_COMPARISON_V1.md` §4.2). A vague prior would reproduce this interval.

### Part B — label calibration (primary)

- **Values, ranks, bands, flags and TOD.** These are exactly as in `WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md` §9.2–§9.4: production rolling values from 5m buckets; mid-rank; 1h windows on every UTC clock hour; 4h windows on 4h boundaries.
  - They are implemented by importing that unit's frozen evaluator functions read-only (`scripts/product/weekday_weekend_baseline_v2/evaluate.py`): `to_5m`, `rolling`, `RefBuilder.indices` for C0 / C1 only, `mid_rank`, `tod_above`, `labels_1h` and `clustered`.
  - C2 / C3 are not evaluated.
- **24h.** One window per UTC day D (evaluated at D+1 00:00), with values from the production `rolling_24h_values` rule. "Above usual" means the value exceeds the `_baseline_24h` median of the 30 prior days.
- **Typing.**
  - 1h and 4h windows and TOD are typed by the UTC date of the window start, as C1 types them.
  - A 24h window is typed by its day D.
  - A window is TOM or MID if its date is in that set. Its month unit is the set's month m, so the last day of month m − 1 belongs to unit m.
- **Labels and nominal rates.**

  | Family | Labels | Nominal | Tolerance τ |
  |---|---|---|---|
  | 1h flags | range ≥ 0.95, volume ≥ 0.95 | 5 % each | 2 pp |
  | 1h flags | price ≥ 0.95 or ≤ 0.05 | 10 % | 2 pp |
  | 1h bands | range ≤ 0.20, move ≥ 0.80, move ≤ 0.20 | 20 % each | 4 pp |
  | 4h bands | the same three | 20 % each | 4 pp |
  | TOD 1h above median | range, volume | 50 % each | 4 pp |
  | 24h above median | range, volume | 50 % each | 4 pp |
  | gate qualification | ≥ 2 of the 3 1h flags | no nominal (reported only) | — |

  The tolerances are the weekday/weekend unit's under-flag tolerances, reused unchanged.
- **Estimand per label L and construction C.** `D_L = r_TOM − r_MID`. Each rate is pooled over the usable windows of its set, from the C0 / C1 maturity date (2020-01-31) on.
  - Secondary: `r_TOM − nominal` and `r_MID − nominal`.
- **Uncertainty.**
  - **Cluster-robust SE of the difference by month unit.** Per-month linearized contributions of both sets, with a `G/(G−1)` correction.
  - **Beside it, a date-clustered SE.** The larger of the two is used.
  - **Interval:** 95 %, `D_L ± t(0.975, G − 1) · SE`.
- **Stability:** `D_L` by calendar year of the month unit.
- **Also reported:**
  - availability per set and construction;
  - the label-switch rate C1 vs C0 on TOM windows;
  - median reference size.

### Part A — day-level shift (secondary, descriptive)

- **Outcomes, per UTC day.** Production metrics come first.
  1. log quote volume (the bot's participation metric);
  2. log trade count (G01-A1's original outcome);
  3. log range ln(max high / min low) (G01-A2).
- **Standardization.** z per calendar year and weekday class (Mon–Fri / Sat–Sun), over all UTC days of that year-class (label-blind; holiday days included in the standardization, excluded from both sets).
- **Estimand.** `d_m` = mean z over the month's TOM days − mean z over its MID days. The estimate is the equal-weight mean of `d_m` over months that have both sets.
- **Uncertainty.** A 95 % t-interval over months.
  - For continuity with R03, beside it: the sign-flip p over months (20 000 draws, seed 20261005) and the moving-block SE (block 3 months). Both use R03's `scripts/research/owner_cards_r03/evaluate.py::signflip_p` and `moving_block_se`, imported unchanged.
- **Stability:** mean `d_m` by year.
- **No nuisance adjustment.** The state is calendar-exogenous, and month pairing removes slow regimes. A lagged-target adjustment would condition on the state itself, because TOM days are consecutive; R03 recorded the same caveat for weekend hours.

## 5. Amount of information (planning; calendar arithmetic only, no outcome read)

- **Calendar counts** from G01's day functions over `[2020-01-31, 2025-01-01)`:
  - 58 month units with both sets;
  - 202 TOM days (147 weekday, 55 weekend) and 826 MID days;
  - about 4 850 TOM / 19 800 MID 1h windows, about 1 210 TOM 4h windows, and 202 TOM 24h windows.
- **Expected interval half-widths for `D_L`.** These assume binomial variance inflated by the weekday/weekend unit's recorded overdispersion (about 2× in SD):

  | Labels | Half-width | Against τ |
  |---|---|---|
  | 1h flags | ≈ 1.4–1.9 pp | 2 pp |
  | 1h bands | ≈ 2.6 pp | 4 pp |
  | TOD | ≈ 3.2 pp | 4 pp |
  | 4h bands | ≈ 5 pp | 4 pp |
  | 24h | ≈ 8–15 pp | 4 pp |

  **So 4h and 24h labels can only show large shifts, and will often be `NOT_RESOLVED` (§6).** This is stated now, so it is not read as a finding later.
- **Part A.** The recorded stress SE is 0.174 SD. In executed R03 one-window-per-day cells, realized SE was 0.41–0.55 of the stress SE. The expected 95 % half-width is therefore about 0.14–0.19 SD.

## 6. What would change our mind (decision rules, fixed now)

### Part B (decides; primary construction C1; C0 gets the same rule, reported only)

Each label L gets one status:

| Status | When |
|---|---|
| `WITHIN_TOLERANCE` | the 95 % interval of `D_L` lies inside [−τ, +τ] |
| `BEYOND_TOLERANCE` | the interval lies wholly above +τ or wholly below −τ, **and** the yearly `D_L` has that sign in ≥ 4 of 5 years |
| `NOT_RESOLVED` | otherwise |

**Recommendation:**
- **`PROPOSE_CORRECTION_UNIT`** if any label is `BEYOND_TOLERANCE`.
  - A follow-up unit is then proposed, with its own design note and candidate constructions (for example a point-in-time TOM factor) and its own go.
  - This unit changes nothing.
- **`NO_CHANGE`** otherwise.
  - The result lists the labels `WITHIN_TOLERANCE` (calibration shown to hold on TOM days) and those `NOT_RESOLVED` (not enough information).
  - For the latter it states the prospective option: monthly TOM-day rates from the live tape, read-only, or the claim journal once it exists. Nothing is built.

**Multiplicity.** There are 13 decision labels × 95 % intervals. `BEYOND_TOLERANCE` needs the interval past the tolerance, not merely past zero, plus year consistency. A chance trigger therefore needs a true shift near τ. `NO_CHANGE` is the safe default.

### Part A (claim decision only; changes nothing)

| Claim decision | When |
|---|---|
| **no product-relevant shift** | the 95 % interval lies inside ±0.15 SD (audit §6.A) |
| **an L1 context line is permitted** | the interval excludes 0 and the yearly means share its sign in ≥ 4 of 5 years. Example: «в 2020–2024 в дни смены месяца объём был на X SD выше середины месяца (интервал …, 58 месяцев)». A `config/beta_research_findings.yaml` entry still needs its own product go |
| **information insufficient** | otherwise: the estimate and interval are recorded, and no line is shown |

## 7. Search exposure and limits

- **Variants, fixed now:**
  - Part B: 2 constructions × 13 labels plus the gate, as differences, with gaps to nominal secondary;
  - Part A: 3 outcomes;
  - years are reported, not selected on.
- **What stays fixed.** The TOM definition is G01's, exactly; no other day window (days 1–5, the last two days, and so on) is tried. Any added label, window, construction, outcome or surface is a new unit.
- **Claim ceiling:**
  - Part A: L1 at most;
  - Part B: a baseline construction question, not a claim;
  - no direction, edge or cause.
- **Limits:**
  - single venue;
  - Binance only;
  - floating holidays (CN New Year, US Labor Day) remain as noise, as in G01;
  - 2020 starts in February for the references.

## 8. Implementation and run (only after the owner's go)

- **Code:** `scripts/product/turn_of_month_baseline_v1/evaluate.py`. It is offline and imports read-only: the weekday/weekend evaluator, G01 `states`, the R03 loader and R03 `evaluate`. It writes only its result files.
- **Tests:** `tests/product/test_turn_of_month_baseline_v1.py`.
  - **Parity:**
    - TOM / MID typing equals G01 `tom_state_days` / `comparator_days` for every month 2020–2024;
    - the 24h rolling value and `_baseline_24h` match `beta.horizons` on a synthetic tape;
    - the trade-count column aligns with the loader's `open_ms`.
  - **Point-in-time:** a shock after `t` changes nothing at `t`; the 24h baseline uses only days before D.
  - **Calendar edges:** the year boundary, the holiday windows, last-Friday-expiry month ends, and the previous month's last day assigned to unit m.
  - **Known answers:**
    - a stationary synthetic series gives nominal rates and `D_L ≈ 0`;
    - a synthetic TOM shift is recovered with its sign.
  - **Uncertainty:** the month-clustered difference SE on a synthetic clustered series.
- **Run:** once, after the tests pass. The output is `docs/TURN_OF_MONTH_BASELINE_UNIT_V1_RESULT.{md,json}`, with the evaluator digest and per-month sufficient statistics.
- **On closure:**
  - add the unit to `research/atlas/ATLAS_UNITS_V1.yaml` and the exposure ledger, with its hash-chained event;
  - update `RESEARCH_LEDGER.md` and `CURRENT_RESEARCH_STATE.md`.
- **Time-box:** 2 working days.
- **Stop rules:**
  - if the pinned data cannot be loaded, stop with that blocker;
  - if the unit appears to need new research infrastructure, stop and ask the owner (`EVIDENCE_AND_CLAIMS_DECISION_V1.md` §7);
  - nothing is added after any outcome is read.
- **Not built:** no change to `beta/`, config, schema, wording or deploy.
