# Weekday / weekend reference-distribution calibration — design V1, revision 5

**Status:** `DESIGN_DRAFT / NOT_FROZEN / NOT_EXECUTED`
**Superseded as the plan to run (2026-10-05):** `WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md` under `research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`. This revision is kept unchanged below as history; it was never frozen or executed.
**Kind:** PRODUCT_FIRST calibration unit (product evidence, not a research claim)
**Date:** 2026-10-03 (revision 5: Stage H semantics, tercile rule and owner contract decisions after the owner's acceptance of revision 4 `8c8a5bf` as the pre-freeze design; written against the repaired `main` at `a7d738f`)
**Authority:** `PRODUCT_FIRST_DECISION_V1.md` §3 row 7, §3.1b, §6, §11. This design changes nothing in that decision and opens no amendment.
**Machine twin (draft, not frozen):** `WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1.json`
**Motivation, as a basis only:** `research/OWNER_CARDS_R03_RESULT.md`, hypothesis R03-C1 (weekend hours narrower than the same weekday hour on Binance 2020–2024; below the research bar; `NO_INCREMENTAL_STRUCTURE`). That verdict is not reopened. No R03 estimate, year value or unit file is an input, offset or prior here.

## 0. The product question

> Does splitting the reference distributions behind the unusual-hour flags by UTC weekday type (Monday–Friday vs Saturday–Sunday) improve the calibration of those flags against their nominal rates, without degrading prospective calibration and without raising false alerts in the other regimes?

Not this question: whether weekends are narrower (closed by R03); fewer weekend alerts as a goal (§5 forbids buying calibration with under-flagging); any threshold search (§1 inputs are fixed); any detector change.

## 1. Current product state (C0), read from the restored implementation

All references are to `main` at `a7d738f` (PR #314, #316–#318 restored by that commit).

| Element | Actual definition | Where |
|---|---|---|
| Tape | per-venue 5m OHLC, volume, taker delta, OI (`state_tape` schema V2, rows since 2026-10-01) | `beta/state_tape.py` |
| Rolling 1h values at bucket `t` | last 12 closed 5m buckets ending at `t`; **None if any bucket is missing**. Per venue: range% = (max high − min low)/first open, move% = (last close − first open)/first open; **consensus = median over venues** for range and move; volume = sum of the cross-venue 5m sums (2 or 3 contributing venues, count not retained) | `beta/context.py::rolling_window_values` |
| Reference sample for the rank at `t` | the rolling-1h value at **every present 5m bucket in `[t − 30d, t)`**, all hours and weekdays pooled; ranked by the frozen percentile core, timeframe `1h`, window `30d` | `beta/context.py::context_1h` |
| Maturity | Stage-2 confidence tiers by sample **span**: `none < 3d`, `low < 7d`, `building < 30d`, `mature ≥ 30d`; the gate uses `mature` ranks only | `config/stage2.yaml`, `beta/hour_gate.py::_rank` |
| Per-metric flag | range rank ≥ `label_high` (0.95); volume rank ≥ 0.95; signed price move rank ≥ 0.95 (rise) or ≤ 0.05 (drop) | `beta/hour_gate.py`, `config/beta_v0.yaml context` |
| Unusual hour (gate) | `MIN_EXTREME_METRICS = 2` of the 3 flags **and** venue agreement: venues whose 1h move has the sign of the median move ≥ `min_venue_coverage = 2` (`price_agreement`) | `beta/hour_gate.py::evaluate_hour`, `beta/interpretation.py` |
| Where the gate is evaluated | inside `push_policy` for every `TRIGGERED` detector episode, on the 1h reading computed **before** the decision; order `DATA_DEGRADED → DELIVERY_TOO_OLD → HOUR_NOT_UNUSUAL → SAME_EVENT_COOLDOWN (20 min) → GLOBAL_COOLDOWN (60 min) → QUIET_HOURS (23:00–07:00 Kyiv) → DAILY_CAP (2 per UTC day) → PUSH_DISABLED` | `beta/detector.py::push_policy`, `config/beta_v0.yaml` |
| User-visible surfaces fed by the gate | the push text; the «Необычные часы» block of `/catchup` and the morning briefing (at most 3 hours, one per hour, from gate-qualified decisions regardless of delivery-side suppression, decision §3.1b.3) | `beta/market_view.py::unusual_hours`, `beta/formatter.py` |
| Coverage diagnostic | share of sampled gate-unusual 1h windows that contain at least one `TRIGGERED` episode (`--beta-context-dry-run`) | `beta/dry_run.py::run_dry_run` |
| Presentation baseline (not the gate) | `BETA_HORIZON_TOD_V2`: for the same UTC time of day ±30 min, one median per prior UTC day over 30 days, then the median; mature at 20 days; tolerates bounded internal OHLC gaps (PR #317). Pools weekday types too. **Out of scope for this unit**; reported only as a secondary descriptive surface | `beta/horizons.py` |

**Nominal rates implied by the construction.** If the reference distribution is the right one for the evaluated window, the rank of a fresh window is uniform, so the range and volume flags fire on 5% of windows and the price flag on 10%. That uniformity is the calibration target; no cut is changed.

**The false-alert surface is gate qualification, not delivery.** Cooldowns, quiet hours and the daily cap suppress pushes but never remove an hour from `/catchup` or the briefing (§3.1b.3). The unit therefore measures qualification per hour; delivered-push counts are reported descriptively only.

## 2. Candidates

**C1 — primary.** Same rule, same cuts, same 30-day lookback, same maturity tiers. The only change: the reference sample for a window ending at `t` keeps only the present buckets in `[t − 30d, t)` whose window end falls on a UTC date of the **same weekday type** as `t`. Added guard: a C1 rank is usable only when its reference holds at least `MIN_SAME_TYPE_DAYS = 8` distinct same-type UTC dates (span tiers alone would call a weekend reference `mature` on 8–9 dates). C1 is the minimal change to the current construction and tests the found calibration problem without also changing the horizon.

**C1-LONG — secondary, sensitivity only.** Reference = the most recent 30 same-type UTC dates (about 42 calendar days back for weekdays, about 105 for weekends). Reported beside C1; it cannot decide and does not become primary after any result. Changing the primary to C1-LONG needs a written basis **before** any Stage H count and is recorded as a design amendment; an availability or calibration result of Stage H is not such a basis.

No third variant (session-, holiday- or hour-of-day-stratified references are separate designs).

## 3. Sampling unit, common support and the three metric surfaces

### 3.1 The prospective sampling unit (exact)

- **Grid.** The UTC clock hour. One candidate observation per clock hour `H` is the rolling-1h window whose **end bucket is `t = H:00`**, i.e. the 12 closed 5m buckets `H−1:00 … H−1:55` (`rolling_window_values(cfg, tape, end_bucket = H:00 − 5m, 12)` in production terms: the window `[H−1:00, H:00)`). Its date and weekday type are those of the **window start** `H−1:00` (so the `23:00–24:00` hour belongs to its own day; r2 used the window end, which moved that hour to the next date).
- **Exactly one observation** per (clock hour, stratum, metric, scheme). The eleven other rolling-1h windows that end inside the hour (`H:05 … H:55`) are the same hour seen through overlapping windows; they are **never** observations. 5m-step rates are not computed in Stage P.
- **No selection by content.** The grid is fixed in advance; an hour is never chosen or dropped because of a `TRIGGERED` episode, a flag, a push, or a value. The only exclusion is unusability (3.2), which is decided from timestamps, presence and reference size, never from a value.
- **Relation to the product.** The gate is evaluated by `push_policy` at the 5m bucket of a `TRIGGERED` decision, not on the hour grid. The hour grid measures the reference distribution's calibration; surface C (3.4) separately measures the gate at the product's own decision buckets.

### 3.2 Usability and its reasons (timestamp-only)

An observation is **usable under scheme S** when all of: the 12 buckets are present (`rolling_window_values` not None); the consensus needs at least `min_venue_coverage = 2` venues with complete OHLC in every bucket; the reference sample is `mature` (span tier); for C1 additionally at least `MIN_SAME_TYPE_DAYS = 8` distinct same-type dates with a present bucket in `[t − 30d, t)`. Every unusable hour is counted under exactly one reason, in this order: `MISSING_1H_BUCKET`, `VENUE_COVERAGE_BELOW_MIN`, `REFERENCE_IMMATURE`, `INSUFFICIENT_SAME_TYPE_DATES` (C1 only), `OTHER` (any reason the implementation raises that is not listed; reported verbatim). None of these reads a market value.

### 3.3 Common support

- The **primary comparison C0 vs C1 is paired on common support**: the clock hours usable under both schemes. `G_C0` and `G_C1` for the primary statistic are computed on exactly the same hours.
- Common support is a *subset* of each scheme's usable set. Calibration measured on it says nothing about hours C1 refuses to rank; that is why surface B exists and is a hard guardrail (3.4, §5).

### 3.4 The three surfaces, kept apart

| Surface | Population | Question | Role |
|---|---|---|---|
| **A. Calibration primary** | paired common support | are the ranks uniform at the cut (exceedance gap vs nominal), C0 vs C1 | decides (§4, §9) |
| **B. Operational availability** | all clock hours of the stratum | can the scheme produce a usable rank at all; usable-hour rate per scheme, common-support rate, unusable reasons | hard guardrail (§5 item 0); a candidate cannot PASS by refusing hours |
| **C. Product qualification** | the product's own gate evaluations: every `TRIGGERED` decision bucket (surface C1) and the dry-run grid of gate-unusual windows (surface C2) | how the reference change moves qualified unusual hours and the gate/detector interaction | guardrails (§5 items 4–5); descriptive push counts |

Push-delivery counts are never a primary metric and never decide.

### 3.5 Strata and guardrail cells

- Primary strata: `WEEKDAY`, `WEEKEND`, `AGGREGATE` (weekday type of the window start).
- Pre-declared guardrail cells (never added after outcomes): weekday type × UTC session band of the window start (`ASIA 00–08`, `EUROPE 08–13`, `US 13–21`, `LATE 21–24`): **eight calendar-defined cells**, no value enters their definition. A cell is assessable with ≥ 100 common-support hours.
- **Realized-volatility terciles are not part of the frozen primary contract** (revision 5). They are not needed for the primary decision or for any §5 guardrail; keeping them would have imported value-derived edges from a single-venue 2020–2024 proxy into a 2026–27 cross-venue tape, where they would be unbalanced and would give Stage H a value-based lever over Stage P cells. A volatility-tercile breakdown is reported **descriptively only** at the Stage P stop, from the Stage P hours themselves, by the deterministic rule in §3.6; it decides nothing.

### 3.6 Deterministic descriptive tercile rule (reporting only; never a gate)

- **Variable:** trailing-30-day realized variance at the window start `H−1:00`: the sum of squared 5m consensus log returns (`ln(close_median/prev close_median)`) over the present buckets in `[H−1:00 − 30d, H−1:00)`, scaled by `expected buckets / present buckets`; undefined (`MISSING`) if fewer than 80 % of buckets are present. Computed once, at the single run at the stop, never before.
- **Observations:** the common-support hours of the stratum being reported, each exactly once.
- **Quantile algorithm:** `numpy.quantile(values, [1/3, 2/3], method="linear")` over the defined values of that stratum; edges `e1 ≤ e2`.
- **Bins:** `LOW = [min, e1]`, `MID = (e1, e2]`, `HIGH = (e2, max]`; closed on the right.
- **Ties:** an hour equal to an edge goes to the lower bin (closed-right intervals); if `e1 == e2` the MID bin is empty and reported as such; no re-binning.
- **Missing:** `MISSING` hours are reported as a fourth group and excluded from the three bins.
- **Independence:** the inputs are the volatility values and the hour set only; no rank, flag, gap, C0 or C1 quantity enters; the number of bins (3) and the method are fixed here; edges are never recomputed after any C0/C1 result is seen.


## 4. Primary calibration metrics

For scheme S, stratum s, metric m ∈ {range, volume, price}:
- `E_S(s, m)` = share of **common-support** hours in s whose rank of m is in the flag region (≥ 0.95; price: ≥ 0.95 or ≤ 0.05).
- `nominal(m)` = 0.05 (range, volume), 0.10 (price).
- **Exceedance gap** `G_S(s, m) = E_S(s, m) − nominal(m)`, signed; over- and under-flagging are both miscalibration.
- **Primary statistic** `P_S = max over s ∈ {WEEKDAY, WEEKEND}, m of |G_S(s, m)|`.
- `U_S(s)` = share of hours the full gate qualifies (2-of-3 and venue agreement; venue agreement is `NOT_EVALUABLE` on the single-venue proxy of Stage H). No nominal value is claimed for `U`; it enters only through the guardrails.
- Inference: cluster-aware by UTC date (§7, Stage P). Diagnostics (never decisive): Kolmogorov distance of the ranks to uniform per stratum; the empirical day-cluster design effect.

## 5. False-positive / false-alert guardrails

0. **Operational availability (surface B, hard):** per primary stratum, `A_S(s)` = usable clock hours / all clock hours of the stratum in the period, and `CS(s)` = common-support hours / all clock hours. Required: `A_C1(s) ≥ A_C0(s) − 0.05` and `CS(s) ≥ A_C0(s) − 0.05`. The reasons of 3.2 are reported per scheme and stratum. The 5 pp tolerance is set now from the product's own tape-completeness tolerance (10% missing buckets, §8): a scheme may not lose more than half of that again on top. It is not chosen from any Stage H result. A candidate that improves surface A while breaching this item is `FAIL`.
1. **No over-flagging:** `G_C1(s, m) ≤ G_C0(s, m) + 0.01` for every primary stratum and metric.
2. **No under-flagging bought with the split:** `G_C1(s, m) ≥ −0.02` for every primary stratum and metric. A split that makes weekend flags rarer than 3% at a 5% cut fails even if `P_C1` improves. This is the guard against "fewer weekend alerts at any cost".
3. **Weekday not sacrificed:** `|G_C1(WEEKDAY, m)| ≤ |G_C0(WEEKDAY, m)| + 0.005`.
4. **Alert surface among detector episodes (Stage P only):** among `TRIGGERED` episodes per stratum, the share the gate qualifies under C1 may not fall more than 5 pp below C0 **and** may not rise more than 5 pp above it. On Stage H there are no detector episodes; recorded `NOT_ASSESSABLE_ON_PROXY`.
5. **Coverage diagnostic (Stage P only):** the decision's own diagnostic (share of gate-unusual windows containing a `TRIGGERED` episode) under C1 may not fall more than 5 pp below C0.

## 6. Degradation guardrails

- **Aggregate:** `|G_C1(AGGREGATE, m)| ≤ |G_C0(AGGREGATE, m)| + 0.005` per metric.
- **Cells:** `|G_C1(cell, m)| ≤ |G_C0(cell, m)| + 0.01` for every assessable cell; one breach fails. Cells under 100 hours are reported, not decisive.
- **Rank usability:** governed by §5 item 0 (surface B); not repeated here.
- **Staleness (C1-LONG, descriptive):** median calendar age of the reference per stratum.

## 7. Stages and data classification

### Stage H — `HISTORICAL / EXPOSED / PROXY EVALUATION`

- Data: pinned `CORE_BTC_BINANCE_V0` BTCUSDT perpetual 1m, 2020-01..2024-12, through the existing SHA256-verified loaders. 5m buckets from 1m bars; rolling-1h values with the product definitions; single venue, so consensus = that venue and venue agreement is `NOT_EVALUABLE`. Label: `PROXY_SINGLE_VENUE_EXPOSED`.
- **Classification.** The whole 2020–2024 surface is **historically exposed for this product decision**: R03 computed and published weekend-vs-weekday range differences on it, year by year. There is **no historical holdout** inside 2020–2024; none is created after the fact, and no sub-period is called holdout.
- **What Stage H can do:** check the mechanics (point-in-time ranks, same-type sampling, maturity), the **direction and rough size** of the calibration error under C0 and its change under C1, the feasibility numbers (usable hours, usability loss, cell support), fix the RV tercile edges, and sanity-check the guardrails.
- **What Stage H cannot do:** authorize a product change, produce a confirmatory `PASS`, or add evidentiary weight to one. It is an eligibility and sanity check only. Its outcome is one of `H_ELIGIBLE_FOR_PROSPECTIVE` (Stage P may be activated), `H_REFUTES` (C1 closed), `H_INFEASIBLE` (§8 not met). Confirmatory evidence comes from Stage P alone; `H_ELIGIBLE_FOR_PROSPECTIVE` and `P_PASS` are a gate and a test, not two independent confirmations.
- Years are reported separately as a descriptive stability record, never as a selection rule.
- Stage H also reports surface B (availability) and the empirical date-cluster design effect, descriptively; the pinned 1m panel is gapless, so Stage H availability is calendar-driven and the C1 same-type rule never bites there. Stage H fixes no edge, threshold or parameter for Stage P (the only pre-P amendment it can trigger is raising the information requirement).

### C1 calendar feasibility (outcome-blind; calendar arithmetic only, no data read)

For every clock hour, the number of distinct same-type UTC dates whose window starts fall in `[t − 30d, t)` is **9 or 10 for weekend hours (half each) and 21–23 for weekday hours**. The C1 minimum of 8 therefore sits one to two dates **below** the calendar floor, not at it: C1 tolerates one missing weekend date in every window and two in half of them, within the 10% missing-bucket tolerance of §8. The 8 is kept. What the calendar cannot tell is the tape's actual completeness; the prerequisite in §13 adds a **timestamp-only tape census** (presence per bucket and venue, no values) before freeze, to state the expected `A_C1(WEEKEND)`. If that census shows the §5 item 0 availability rule cannot be met by construction, the status becomes `DESIGN_BLOCKED_BY_FEASIBILITY`; C1-LONG does not become primary by that route (§2).


### Stage P — `PROSPECTIVE / CONFIRMATORY` (the only confirmatory object)

- Data: the beta state tape, schema V2, cross-venue consensus as in production; venue agreement evaluable; detector episodes and push decisions available for guardrails 4–5.
- **Start** is defined by counts, not by a calendar date: the first UTC 00:00 bucket at which **both** C0 and C1 have usable ranks (mature tier; C1 also the 8 same-type dates) for the weekend stratum and the weekday stratum, as determined mechanically from the tape's own history at freeze time plus the frozen rule. (Under decision §6 that falls around the end of October 2026; the date is an expectation, not the rule.) Every evaluated hour lies after the freeze commit and after the start bucket, so no Stage P hour has been seen by anyone.
- **Inference (frozen, cluster-aware, no multiplier).** Hourly observations inside a UTC date are dependent (volatility clustering, shared 30-day reference). Clusters are **UTC dates** `d = 1..G`, where `G` is the number of dates with at least one common-support hour in the stratum. For stratum `s`, scheme `S ∈ {C0, C1}` and metric `m`, the per-date sufficient statistics are the **same** `n_d` (common-support hours of date `d`) and `x_{S,d}` (flagged hours among them). With `N = Σ_d n_d`:
  - level: `E_S = Σ_d x_{S,d} / N`, `G_S = E_S − nominal(m)`;
  - level score: `u_{S,d} = x_{S,d} − E_S · n_d`; `Var(E_S) = [G / (G − 1)] · Σ_d u_{S,d}² / N²`;
  - paired change: `Δ = E_C1 − E_C0 = Σ_d (x_{C1,d} − x_{C0,d}) / N`;
  - paired score: `v_d = (x_{C1,d} − x_{C0,d}) − Δ · n_d`; `Var(Δ) = [G / (G − 1)] · Σ_d v_d² / N²`;
  - intervals and the non-inferiority comparisons use `t_{G−1}` quantiles.
  `G/(G−1)` is the only finite-cluster correction. **Small G:** a stratum with `G < 30` dates is `INCONCLUSIVE` (the requirement in the next item implies `G ≥ 94` on a complete tape, so this only bites under heavy gaps). **ISO-week sensitivity:** the same formulas with ISO-week clusters (`G_w` weeks) are computed and reported; the **decision uses the larger of the date-cluster and week-cluster standard errors** — this rule is fixed here, before any outcome. `DEFF = 2.5` below is a planning quantity for the sample size only; it never enters the inference.
- **Information requirement (counts only), per primary metric.** The stop cannot read a variance (that would read values), so the requirement is fixed in advance from the **planning** variance design effect `DEFF = 2.5` (intra-day correlation ρ ≈ 0.065 of hourly flags over 24-hour date clusters; set here, not from data) and the Bernoulli approximation at the metric's nominal rate, target standard error **1.0 pp** for every primary metric:
  - range, volume (`p = 0.05`): `n_indep = 0.05 × 0.95 / 0.01² = 475`; `n = 2.5 × 475 = 1 187.5 → 1 200`;
  - price (`p = 0.10`, either tail): `n_indep = 0.10 × 0.90 / 0.01² = 900`; `n = 2.5 × 900 = 2 250`.
  Price is a primary metric, so the stop waits for the largest requirement: **2 250 common-support hours per primary stratum**. (Revision 3's single figure of 1 200 was computed at `p = 0.05` only and is superseded.) The target SE and the PASS/FAIL bands are not changed to shorten the horizon; whether price should carry a different target SE or band, or be moved to a secondary surface, is an owner contract decision listed in §14, not taken here.
  Adequacy: with SE ≈ 1 pp the PASS band of ±2 pp is about two standard errors and the FAIL edge of 3 pp about three for every primary metric. If Stage H reports an empirical date-cluster design effect above 2.5, both requirements are raised proportionally (`ceil(DEFF_H × n_indep / 50) × 50`) by amendment **before** Stage P starts; they are never lowered.
- **Feasibility against the hard cap (calendar arithmetic).** A UTC week holds 48 weekend and 120 weekday clock hours. In 52 weeks: 2 496 weekend hours and 6 240 weekday hours. The weekday requirement (2 250) needs about 19 weeks at full availability and is comfortable. The weekend requirement (2 250) needs a common-support rate of at least `2 250 / 2 496 = 90.1 %` over the **entire** 52 weeks: essentially every weekend hour of a year, with less than 10 % lost to gaps, immature references or the C1 same-type minimum. Under the proposed availability rule (`CS ≥ A_C0 − 0.05`) this is feasible only if `A_C0(WEEKEND) ≥ 0.95` and C1 loses almost nothing; it has no margin. The census (§13) will state the observed rates; if the implied weekend horizon exceeds the cap, the design is `DESIGN_BLOCKED_BY_FEASIBILITY` and the owner chooses among the options in §14 (price target SE or band, price as secondary, a longer cap). None of those is taken here.
- **Temporal diversity.** No separate rule. With one observation per clock hour on a fixed grid, 2 250 weekend hours span at least 47 ISO weeks (one week holds at most 48) and 2 250 weekday hours at least 19 weeks (at most 120 per week), so any single week is at most 2.1 % / 5.3 % of a stratum and the sample necessarily covers more than three months. Revision 3's "≤ 10 % per ISO week, ≥ 3 months" rule followed from the sample size and the grid and is removed as redundant; no replacement threshold is invented. Temporal concentration beyond that cannot occur on a complete grid; gaps are governed by the availability rule (§5 item 0) and the completeness requirement (§8).
- **Start** is defined by counts, not by a calendar date: the first UTC 00:00 bucket at which **both** C0 and C1 have usable ranks (mature tier; C1 also the 8 same-type dates) for the weekend stratum and the weekday stratum, as determined mechanically from the tape's own history at freeze time plus the frozen rule. (Under decision §6 that falls around the end of October 2026; the date is an expectation, not the rule.) Every evaluated hour lies after the freeze commit and after the start bucket, so no Stage P hour has been seen by anyone.
- **Inference (frozen, cluster-aware, no multiplier).** Hourly observations inside a UTC date are dependent (volatility clustering, shared 30-day reference). Clusters are **UTC dates** `d = 1..G`, where `G` is the number of dates with at least one common-support hour in the stratum. For stratum `s`, scheme `S ∈ {C0, C1}` and metric `m`, the per-date sufficient statistics are the **same** `n_d` (common-support hours of date `d`) and `x_{S,d}` (flagged hours among them). With `N = Σ_d n_d`:
  - level: `E_S = Σ_d x_{S,d} / N`, `G_S = E_S − nominal(m)`;
  - level score: `u_{S,d} = x_{S,d} − E_S · n_d`; `Var(E_S) = [G / (G − 1)] · Σ_d u_{S,d}² / N²`;
  - paired change: `Δ = E_C1 − E_C0 = Σ_d (x_{C1,d} − x_{C0,d}) / N`;
  - paired score: `v_d = (x_{C1,d} − x_{C0,d}) − Δ · n_d`; `Var(Δ) = [G / (G − 1)] · Σ_d v_d² / N²`;
  - intervals and the non-inferiority comparisons use `t_{G−1}` quantiles.
  `G/(G−1)` is the only finite-cluster correction. **Small G:** a stratum with `G < 30` dates is `INCONCLUSIVE` (the requirement in the next item implies `G ≥ 94` on a complete tape, so this only bites under heavy gaps). **ISO-week sensitivity:** the same formulas with ISO-week clusters (`G_w` weeks) are computed and reported; the **decision uses the larger of the date-cluster and week-cluster standard errors** — this rule is fixed here, before any outcome. `DEFF = 2.5` below is a planning quantity for the sample size only; it never enters the inference.
- **Information requirement (counts only), per primary metric.** The stop cannot read a variance (that would read values), so the requirement is fixed in advance from the **planning** variance design effect `DEFF = 2.5` (intra-day correlation ρ ≈ 0.065 of hourly flags over 24-hour date clusters; set here, not from data) and the Bernoulli approximation at the metric's nominal rate, target standard error **1.0 pp** for every primary metric:
  - range, volume (`p = 0.05`): `n_indep = 0.05 × 0.95 / 0.01² = 475`; `n = 2.5 × 475 = 1 187.5 → 1 200`;
  - price (`p = 0.10`, either tail): `n_indep = 0.10 × 0.90 / 0.01² = 900`; `n = 2.5 × 900 = 2 250`.
  Price is a primary metric, so the stop waits for the largest requirement: **2 250 common-support hours per primary stratum**. (Revision 3's single figure of 1 200 was computed at `p = 0.05` only and is superseded.) The target SE and the PASS/FAIL bands are not changed to shorten the horizon; whether price should carry a different target SE or band, or be moved to a secondary surface, is an owner contract decision listed in §14, not taken here.
  Adequacy: with SE ≈ 1 pp the PASS band of ±2 pp is about two standard errors and the FAIL edge of 3 pp about three for every primary metric. If Stage H reports an empirical date-cluster design effect above 2.5, both requirements are raised proportionally (`ceil(DEFF_H × n_indep / 50) × 50`) by amendment **before** Stage P starts; they are never lowered.
- **Feasibility against the hard cap (calendar arithmetic).** A UTC week holds 48 weekend and 120 weekday clock hours. In 52 weeks: 2 496 weekend hours and 6 240 weekday hours. The weekday requirement (2 250) needs about 19 weeks at full availability and is comfortable. The weekend requirement (2 250) needs a common-support rate of at least `2 250 / 2 496 = 90.1 %` over the **entire** 52 weeks: essentially every weekend hour of a year, with less than 10 % lost to gaps, immature references or the C1 same-type minimum. Under the proposed availability rule (`CS ≥ A_C0 − 0.05`) this is feasible only if `A_C0(WEEKEND) ≥ 0.95` and C1 loses almost nothing; it has no margin. The census (§13) will state the observed rates; if the implied weekend horizon exceeds the cap, the design is `DESIGN_BLOCKED_BY_FEASIBILITY` and the owner chooses among the options in §14 (price target SE or band, price as secondary, a longer cap). None of those is taken here.
- **Temporal diversity rule.** Date minima are redundant with the hour requirement (one observation per hour, at most 24 per date) and are dropped. The genuine guardrail is regime diversity: in each primary stratum **no single ISO week may contribute more than 10% of the common-support hours** and the hours must span **at least 3 distinct calendar months**. Basis: volatility regimes persist for weeks, so a sample dominated by one or two weeks would be one regime measured many times; the numbers are set here, before any data.
- **Start** is defined by counts, not by a calendar date: the first UTC 00:00 bucket at which **both** C0 and C1 have usable observations (3.2) for the weekend stratum and the weekday stratum, determined from the tape's timestamps at freeze time plus the frozen rule. (Decision §6 makes the end of October 2026 the expectation; the date is not the rule.) Every Stage P hour lies after the freeze commit and after the start bucket.
- **Stop.** The first UTC Monday 00:00 at which both primary strata hold ≥ 2 250 common-support hours. Expected clock from the calendar alone at full availability: the weekend stratum sets it, 47 weekends (≈ 11 months); the weekday stratum needs about 19 weeks. A hard cap of 52 weeks after the start yields `INCONCLUSIVE`, never a continuation.
- **Pre-stop storage model (blindness).** Before the stop, the only artefact that may exist is the **timestamp census** (same definition as the pre-freeze census, §13, re-run on the Stage P period), whose fields are exactly: clock-hour timestamp; stratum (from the window-start date); ISO week and month identifiers; per-venue and cross-venue **presence** booleans of the 12 buckets (no OHLC, volume or any value); usable yes/no per scheme; the single fixed unusable reason per scheme (3.2); common-support yes/no; and the per-stratum totals of those. **Not stored, computed or previewed before the stop, for either scheme:** ranks, rank summaries, flags, exceedance or qualified counts, calibration gaps, C0-vs-C1 differences, and anything derived from a value. Detector state (`TRIGGERED` episodes) is scheme-independent raw detector output, but it is not needed for the stop and is **not** stored before it either; the surface C counts are computed once at the stop from `beta_episodes` and `beta_push_decisions`. At the stop a single run computes the per-date sufficient statistics (`n_d`, `x_{S,d,m}`, the paired per-date differences, qualified and triggered counts per date) and writes them, with the derived estimates, into the result file; those tables are the sealed sufficient statistics of the unit and are published with it.
- **Frozen before Stage P starts:** every threshold and tolerance in §4–§6 and §9, the stop rule, the start rule, the evaluator code and the product config snapshot. Nothing in Stage H's outcome may move any of them; the only path to a different threshold is a written amendment **before** Stage P starts, with a new design version, or a restart of Stage P on later data under a new preregistration.

### The 2025-01..2026-08-15 surface — provenance and status for this decision

Read only from existing ledgers and records; no byte was opened for this section.

| Fact | Source |
|---|---|
| Opened by the `DIVERGENCE_FULL_HISTORY_RESEARCH_V0` validation run (`fca3ab5`): BTC, ETH, SOL, BNB, DOGE, XRP Binance USD-M, 1m klines, bookDepth and OI metrics, 2025-01-01 up to the exclusive read horizon 2026-08-15; E1-RUN-001 untouched | `CURRENT_RESEARCH_STATE.md`, `DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3.md`, `DIVERGENCE_FULL_HISTORY_RESEARCH_V0_VALIDATION.json` |
| What was computed on it: swing-low episodes, arms A–D, +1R/−1R outcomes, and a 22-feature point-in-time covariate comparison with Holm, including **volatility covariates (log RV24, ATR%, 7-day return, new-30-day-low depth)** | `DIVERGENCE_FULL_HISTORY_RESEARCH_V0_REPORT.md` §features, `_DESIGN.md` mechanism-feature registry |
| `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0` read decisions 2023-01-01..2026-08-11 (3 005 support episodes, 48h state-blind outcomes for dependence calibration) | `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.md` |
| `DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1`: `PROTECTED_2025_2026_OPENED = false` (did not read it) | its report |
| Weekday/weekend, hour-of-day or unusual-hour calibration statistics on that surface: **none recorded** in any of the above | grep of the reports and ledgers; absence in records, not proof of absence in memory |
| Product side: the beta D7 regime backfill (`--beta-d7-backfill --days 90`) and the 30-day bootstrap read Binance 1m from about 2026-07 onward; the tape V2 rows start 2026-10-01. No weekday statistics are derived there | `PRIVATE_BETA_V0_DEPLOY.md`, `beta/regime_d7.py` |

**Independence verdict for this decision:** `NOT_PROVABLY_INDEPENDENT / EXPOSED_FOR_OTHER_PURPOSES`. The surface was read in full by a research program whose published reports include volatility covariate summaries on it, and the owner and agents have seen those reports. No weekday-type statistic is on record, so it is less exposed than 2020–2024, but independence cannot be demonstrated from provenance alone. Therefore it is **not** a confirmatory holdout for this unit. Its only admissible role, if the owner decides so later, is a second `EXPOSED` proxy slice reported as sensitivity beside Stage H; that would be an owner decision under `DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3` and is not assumed here. Nothing after 2026-08-15 outside the product tape is touched; E1-RUN-001 stays sealed.

## 8. Minimum information / feasibility requirements

| Requirement | Threshold | Else |
|---|---|---|
| Stage H common-support hours per stratum | ≥ 7000 weekday, ≥ 2800 weekend | `H_INFEASIBLE` |
| Stage H assessable cells | ≥ 12 of 24 | recorded; cells are guardrails only on Stage P |
| Stage P common-support hours per primary stratum | ≥ 2 250 (the price requirement; range and volume need 1 200) and `G ≥ 30` dates | stop not reached; `INCONCLUSIVE` at the hard cap |
| Stage P tape completeness | ≤ 10% of 5m buckets missing per stratum over the period | `INCONCLUSIVE` |
| Availability (surface B) | `A_C1 ≥ A_C0 − 0.05` and `CS ≥ A_C0 − 0.05` per primary stratum | guardrail FAIL |

## 9. Decision rule

**Stage H (not confirmatory):**
- `H_ELIGIBLE_FOR_PROSPECTIVE`: `P_C1 ≤ P_C0 − 0.01` on the proxy and every §5/§6 guardrail assessable on the proxy holds, and §8 met. Eligibility only: it carries no evidentiary weight into the product decision.
- `H_REFUTES`: `P_C1 > P_C0 + 0.005`, or a §5/§6 guardrail breached → C1 closed; a different scheme is a new design.
- `H_INFEASIBLE`: §8 not met.
- Nothing in Stage H authorizes a product change or counts as confirmatory evidence.

**Stage P (confirmatory, non-inferiority with tolerance):**
- `P_PASS`: §8 met (all three primary metrics at their own requirement, hence 2 250 hours); on common support `|G_C1(s, m)| ≤ 0.02` for both primary strata and all metrics and `P_C1 ≤ P_C0`; every §5 (item 0 availability included) and §6 guardrail holds.
- `P_FAIL`: any guardrail breached, or `|G_C1(s, m)| > 0.03` for a primary stratum and metric, or `P_C1 > P_C0 + 0.005`.
- `P_INCONCLUSIVE`: otherwise, or §8 not met at the hard cap.

**Product decision:** `PASS` = `H_ELIGIBLE_FOR_PROSPECTIVE` (gate) **and** `P_PASS` (the only confirmatory test) → a change may be **proposed** under `PRODUCT_FIRST_DECISION_V1` §11 (new context version label, config digest, deploy note); this design makes no change. `FAIL` = `H_REFUTES` or `P_FAIL`. `INCONCLUSIVE` otherwise. All numbers in §4–§9 are set now, before any count, and are not tuned after Stage H. The 52-week hard cap is `PROVISIONAL / NOT_FROZEN` (owner, 2026-10-03): it is not changed automatically by any result; a change is a separate owner authorization.

## 10. Stop conditions (→ `ABORTED`, no rate is computed)

- a product rule, cut, `min_venue_coverage`, context version or tape schema change during Stage P;
- the gate absent from `main` at the Stage P start (it is present at `a7d738f`; the condition stays as a check);
- tape completeness below 90% in a stratum over the period (→ `INCONCLUSIVE`);
- any pre-stop read of a Stage P rate or gap: the stage is void and must be re-declared on later data;
- an owner instruction to stop.

## 11. Allowed data, frozen inputs, forbidden inputs

**Allowed:** `CORE_BTC_BINANCE_V0` 1m 2020–2024 (Stage H, exposed proxy); beta state tape V2 rows (Stage P, read-only, after the start bucket); product config values at freeze (`label_high 0.95`, `rolling_buckets 12`, `percentile_window 30d`, tiers 3/7/30, `min_venue_coverage 2`, push policy parameters for the descriptive push counts); the UTC calendar.

**Frozen at freeze (digests recorded then):** this design and its twin; the evaluator; the config snapshot; the loader identities; the start and stop rules; the census spec and runner digests.

**Forbidden:** `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` and any OI/funding snapshot; research-protected 2025/2026 objects; the opened 2025-01..2026-08-15 surface (§7) unless the owner decides otherwise; E1-RUN-001 data; R03 unit files, results and estimates as inputs; holiday calendars; user-reaction telemetry.

## 12. No-lookahead rules

- A rank at `t` uses only buckets strictly before `t`; the weekday type of a sample is that of its own window end; the weekday type of the evaluated window is that of `t`.
- C1 is fixed now; it may not be modified after any Stage H count is seen.
- No value-derived stratification edge enters any gate; the descriptive tercile rule (§3.6) runs only at the stop.
- Stage P is read once, at the stop defined by counts.
- No R03 number is an input, prior or offset.
- No evaluation-period data sets a threshold.

## 13. Execution prerequisites (none is done here)

1. Owner authorization to **freeze** this design (not given).
2. **Timestamp-only tape census** (owner-authorized before the full freeze, 2026-10-03, on condition that its query is written and hashed first). Spec: `WEEKDAY_WEEKEND_CALIBRATION_CENSUS_SPEC_V1.md`; runner `scripts/product/weekday_weekend_census.py`; both digests are recorded in the JSON twin. It reads timestamps, bucket presence and per-venue OHLC presence booleans only; no OHLC, return, volume, OI, funding, rank, percentile, flag or episode outcome. Its only purpose is C1 operational feasibility and the prospective horizon. It cannot change C1 to C1-LONG or any parameter; a failing result is `DESIGN_BLOCKED_BY_FEASIBILITY` for the owner. **Status: spec and runner written and hashed; not run from this environment, which has no connection to the production tape.**
3. Evaluator as offline tooling only: no change to `beta/` detector, gate, context, horizons, config or schema; synthetic-tape tests including a point-in-time test (a shock after `t` changes no rank at `t`), a weekday-type test across DST and year boundaries, a one-observation-per-clock-hour test, a usability-reason test on synthetic gaps, and a test that the census path never touches a value column.
4. Owner authorization to run Stage H.
5. Freeze of thresholds, start/stop rules and tercile edges **before** Stage P starts; owner authorization to activate Stage P and, at its stop, to open it.

## 13a. Owner contract decisions recorded before the census (2026-10-03)

1. Primary candidate C1; `MIN_SAME_TYPE_DAYS = 8`; C1-LONG sensitivity only.
2. Price stays primary; target SE 1 pp; `PRIMARY_N_PRICE = 2 250`; range/volume 1 200; the Stage P stop follows the largest requirement, 2 250.
3. PASS/FAIL bands are not widened to shorten the horizon.
4. Availability tolerance stays the proposed 5 pp (`A_C1 ≥ A_C0 − 0.05`, `CS ≥ A_C0 − 0.05`); the census cannot change it.
5. 2025–2026: `NOT_PROVABLY_INDEPENDENT / EXPOSED_FOR_OTHER_PURPOSES`; never a confirmatory holdout. E1, B2_06, OI/funding are not opened or used.
6. The 52-week hard cap is `PROVISIONAL / NOT_FROZEN`; not changed automatically.
7. Census verdicts: `CENSUS_FEASIBLE` if 2 250 weekend common-support hours are attainable with reasonable headroom; else `DESIGN_BLOCKED_BY_FEASIBILITY`, in which case nothing in items 1–6 changes automatically and a decision memo with projected horizons is prepared instead.

## 13b. Census execution (owner-authorized; metadata only)

- **Authorized artefacts:** spec sha256 `d13913ee94a2e392397b5ea3ec68fb0c2378abc8867f9746a57a02cc78e2b56b`; runner sha256 `9f65b914b096009373b7703843ae26b529330da175505f36bb3ee9bc7d5e9a6a`. The operator verifies both with `sha256sum` before running; any mismatch is `CENSUS_SPEC_VIOLATION` and nothing runs.
- **Invocation (on the deploy host, which holds the tape):** `BETA_DSN=<postgres dsn> python -m scripts.product.weekday_weekend_census --calculation-version <current> --schema-version <current> --venues binance,bybit,okx`. The identity values are the ones `verify_versions` reports for the running beta. Output: `docs/WEEKDAY_WEEKEND_CALIBRATION_CENSUS_RESULT.json` (counts and rates only).
- **Status (2026-10-03):** the runner was re-verified against both digests in the development environment, which has **no connection to the production tape** (no DSN, no local PostgreSQL). The census therefore has **not run**; the feasibility fields below stay unmeasured until the operator runs it.
- **Projection rule after the census (no model):** with `CS_w` the observed weekend common-support rate, `weeks_to_N = N / (48 × CS_w)` and `N_at_52 = 52 × 48 × CS_w`; headroom `= N_at_52 − 2 250`. Weekday analogously with 120 hours per week. The same rule gives, before the census, the break-even `CS_w = 0.901` for 2 250 hours in 52 weeks.

## 14. Owner decisions pending

0. **Hard cap** if the census returns `DESIGN_BLOCKED_BY_FEASIBILITY`: a separate authorization, decided from the decision memo (§13a item 7); no option is pre-selected.
1. Freeze (with or without amendments).
2. Stage H execution.
3. Whether the opened 2025-01..2026-08-15 surface may be used as an additional `EXPOSED` sensitivity slice (never confirmatory; the owner confirmed on 2026-10-03 that it is not a confirmatory holdout).

4. Stage P activation; later, its opening at the stop.
5. On `PASS`: the product change under the decision's amendment process.

## 15b. Revision 5 changes (2026-10-03)

- `H_SUPPORTS_PROSPECTIVE` renamed `H_ELIGIBLE_FOR_PROSPECTIVE`; Stage H is an eligibility/sanity gate with no evidentiary weight; product PASS = gate and `P_PASS`, not two confirmations.
- Realized-volatility terciles removed from the frozen primary contract; guardrail cells are the eight calendar-defined weekday-type × session cells; a deterministic descriptive tercile rule (§3.6) is recorded for reporting at the stop only.
- Owner contract decisions before the census recorded (§13a); hard cap marked `PROVISIONAL / NOT_FROZEN`.
- Census execution section (§13b) with the authorized digests, operator invocation, projection rule, and the fact that it could not run from the development environment.

## 15a. Revision 4 changes (final design-only repair, 2026-10-03)

- Information requirement computed per primary metric at its nominal rate: 1 200 hours (range, volume) and 2 250 hours (price); the stop waits for 2 250. Target SE and bands unchanged; the price decision is escalated (§14 item 0).
- Hard-cap feasibility stated: 2 250 weekend hours need a 90.1 % common-support rate over all 52 weeks, no margin.
- Exact cluster-robust formulas for levels and the paired change with the same `n_d`, `G/(G−1)` correction, `t_{G−1}`, `G < 30 → INCONCLUSIVE`, week-cluster sensitivity and the frozen larger-SE rule; `DEFF` restricted to planning.
- Pre-stop storage limited to timestamp and presence metadata; `TRIGGERED` counts no longer stored before the stop; all scheme-dependent quantities exist only from the single run at the stop.
- Temporal diversity rule removed as redundant (shown from the grid and the sample size).
- Census spec and metadata-only runner written and hashed under the owner's authorization; not run (no tape access here).
- Owner confirmations recorded: C1 primary, `MIN_SAME_TYPE_DAYS = 8`, C1-LONG sensitivity, 2025–2026 status, Stage H non-confirmatory, 5 pp availability tolerance as a proposed frozen value.

## 15. Revision 3 changes (design review of 2026-10-03)

- Exact prospective sampling unit on the UTC clock-hour grid, typed by the window start; overlapping windows are one observation.
- Primary comparison on paired common support; surface B (availability) added as a hard guardrail with enumerated unusable reasons and a 5 pp rule set from the completeness tolerance.
- Calendar feasibility of C1 recorded (9–10 weekend same-type dates per window); timestamp-only tape census added as a prerequisite.
- Inference replaced by frozen UTC-date (and ISO-week sensitivity) cluster-robust ratio estimators; the information requirement is derived from a prespecified variance design effect 2.5 (1 200 common-support hours per stratum), raised but never lowered by a pre-P amendment if Stage H shows more clustering; date minima dropped as redundant; a week-share and month-span diversity rule added; hard cap 52 weeks.
- Counts-only storage model stated: a timestamp census only before the stop; sufficient statistics exist only from the single run at the stop.
- 2025–2026 status unchanged: `NOT_PROVABLY_INDEPENDENT / EXPOSED_FOR_OTHER_PURPOSES`, not a holdout.

## 16. What this revision does not do

No data opened; no rank, rate or gap computed; no product code, config or schema changed; nothing frozen; no amendment of `PRODUCT_FIRST_DECISION_V1` opened; R03 untouched.
