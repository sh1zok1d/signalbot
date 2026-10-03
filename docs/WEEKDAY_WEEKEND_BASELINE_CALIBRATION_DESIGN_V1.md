# Weekday / weekend reference-distribution calibration — design V1, revision 3

**Status:** `DESIGN_DRAFT / NOT_FROZEN / NOT_EXECUTED`
**Kind:** PRODUCT_FIRST calibration unit (product evidence, not a research claim)
**Date:** 2026-10-03 (revision 3: owner design review; written against the repaired `main` at `a7d738f`; supersedes revision 2 `6c1db7e` and the unmerged draft `38086d8`)
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
- Pre-declared guardrail cells (never added after outcomes): weekday type × UTC session band of the window start (`ASIA 00–08`, `EUROPE 08–13`, `US 13–21`, `LATE 21–24`) × trailing-30-day realized-volatility tercile. Tercile edges are fixed once from Stage H and carried unchanged into Stage P. A cell is assessable with ≥ 100 common-support hours.

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
- **What Stage H cannot do:** authorize a product change, or produce a confirmatory `PASS` on its own. Its outcome is one of `H_SUPPORTS_PROSPECTIVE` (go to Stage P), `H_REFUTES` (close C1), `H_INFEASIBLE`.
- Years are reported separately as a descriptive stability record, never as a selection rule.
- Stage H also reports surface B (availability) and the empirical date-cluster design effect, descriptively; the pinned 1m panel is gapless, so Stage H availability is calendar-driven and the C1 same-type rule never bites there.

### C1 calendar feasibility (outcome-blind; calendar arithmetic only, no data read)

For every clock hour, the number of distinct same-type UTC dates whose window starts fall in `[t − 30d, t)` is **9 or 10 for weekend hours (half each) and 21–23 for weekday hours**. The C1 minimum of 8 therefore sits one to two dates **below** the calendar floor, not at it: C1 tolerates one missing weekend date in every window and two in half of them, within the 10% missing-bucket tolerance of §8. The 8 is kept. What the calendar cannot tell is the tape's actual completeness; the prerequisite in §13 adds a **timestamp-only tape census** (presence per bucket and venue, no values) before freeze, to state the expected `A_C1(WEEKEND)`. If that census shows the §5 item 0 availability rule cannot be met by construction, the status becomes `DESIGN_BLOCKED_BY_FEASIBILITY`; C1-LONG does not become primary by that route (§2).


### Stage P — `PROSPECTIVE / CONFIRMATORY` (the only confirmatory object)

- Data: the beta state tape, schema V2, cross-venue consensus as in production; venue agreement evaluable; detector episodes and push decisions available for guardrails 4–5.
- **Start** is defined by counts, not by a calendar date: the first UTC 00:00 bucket at which **both** C0 and C1 have usable ranks (mature tier; C1 also the 8 same-type dates) for the weekend stratum and the weekday stratum, as determined mechanically from the tape's own history at freeze time plus the frozen rule. (Under decision §6 that falls around the end of October 2026; the date is an expectation, not the rule.) Every evaluated hour lies after the freeze commit and after the start bucket, so no Stage P hour has been seen by anyone.
- **Inference (frozen, cluster-aware, no multiplier).** Hourly observations inside a UTC date are dependent (volatility clustering, shared 30-day reference). The frozen method uses **UTC-date sufficient statistics**: for each date `d`, stratum `s`, scheme `S` and metric `m`: `n_{d}` = common-support hours, `x_{S,d,m}` = flagged hours, and for the pair the discordant counts `x_{C1 only}`, `x_{C0 only}`. Estimates and variances are ratio-of-sums with date clusters:
  - `E_S = Σ_d x_{S,d} / Σ_d n_d`, `G_S = E_S − nominal`;
  - `Var(E_S) = Σ_d (x_{S,d} − E_S n_d)² / (Σ_d n_d)²` (cluster-robust, dates as clusters);
  - paired change `Δ = E_C1 − E_C0 = Σ_d (x_{C1,d} − x_{C0,d}) / Σ_d n_d`, variance from the per-date differences in the same form.
  No bootstrap, block length or inflation factor enters the decision; the formulas above are the whole inference. The reference distribution's own 30-day memory induces correlation across dates too; the date-cluster variance is therefore reported together with an **ISO-week-cluster** variance of the same form as a sensitivity, and the decision uses the larger of the two standard errors.
- **Information requirement (counts only).** The stop cannot read a variance (that would read values). It is therefore fixed in advance from a **prespecified variance design effect** `DEFF = 2.5` for 24-hour date clusters (intra-day correlation ρ ≈ 0.065 of hourly flags; conservative relative to typical volatility clustering, and the value is set here, not from any data). Target: standard error of a single exceedance rate at nominal 5% of **1.0 pp**:
  `n_indep = p(1−p)/SE² = 0.05 × 0.95 / 0.01² = 475`, `n_hours = DEFF × n_indep = 2.5 × 475 = 1 187.5 → 1 200` common-support hours per primary stratum.
  Adequacy: with SE ≈ 1 pp the PASS band of ±2 pp is about two standard errors and the FAIL edge of 3 pp about three; a true gap of 0 passes with high probability and a true gap of 3 pp fails with high probability, which is what a non-inferiority decision needs. If Stage H reports an empirical date-cluster design effect above 2.5, the Stage P requirement is raised to `ceil(DEFF_H × 475 / 100) × 100` by amendment **before** Stage P starts; it is never lowered. (Revision 2's "720 hours with inflation 1.5" treated 1.5 as a variance design effect; it is superseded.)
- **Temporal diversity rule.** Date minima are redundant with the hour requirement (one observation per hour, at most 24 per date) and are dropped. The genuine guardrail is regime diversity: in each primary stratum **no single ISO week may contribute more than 10% of the common-support hours** and the hours must span **at least 3 distinct calendar months**. Basis: volatility regimes persist for weeks, so a sample dominated by one or two weeks would be one regime measured many times; the numbers are set here, before any data.
- **Start** is defined by counts, not by a calendar date: the first UTC 00:00 bucket at which **both** C0 and C1 have usable observations (3.2) for the weekend stratum and the weekday stratum, determined from the tape's timestamps at freeze time plus the frozen rule. (Decision §6 makes the end of October 2026 the expectation; the date is not the rule.) Every Stage P hour lies after the freeze commit and after the start bucket.
- **Stop.** The first UTC Monday 00:00 at which both primary strata hold ≥ 1 200 common-support hours and the diversity rule holds. Expected clock from the calendar alone: the weekend stratum sets it, about 25 weekends (≈ 6 months); the weekday stratum needs about 10 weeks. A hard cap of 52 weeks after the start yields `INCONCLUSIVE`, never a continuation.
- **Counts-only storage model (blindness).** Before the stop nothing is computed from values. The only artefact maintained is a **timestamp census** derived from bucket presence and reference size: per date, stratum and scheme, the number of usable clock hours, the unusable reasons of 3.2, common-support hours, distinct ISO weeks and months, the missing-bucket share, and the number of `TRIGGERED` decision buckets. Ranks, flags, gaps, qualified shares and guardrail values are **not** computed, stored or previewed. At the stop a single run computes the date sufficient statistics (`n_d`, `x_{S,d,m}`, discordant counts, qualified and triggered counts per date) and writes them, with the derived estimates, into the result file; those per-date tables are the sealed sufficient statistics of the unit and are published with it. No value from the Stage P period exists anywhere before that run.
- **Frozen before Stage P starts:** every threshold and tolerance in §4–§6 and §9, the stop rule, the start rule, the RV tercile edges from Stage H, the evaluator code and the product config snapshot. Nothing in Stage H's outcome may move any of them; the only path to a different threshold is a written amendment **before** Stage P starts, with a new design version, or a restart of Stage P on later data under a new preregistration.

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
| Stage P common-support hours per primary stratum | ≥ 1 200; no ISO week above 10% of them; ≥ 3 calendar months | stop not reached; `INCONCLUSIVE` at the hard cap |
| Stage P tape completeness | ≤ 10% of 5m buckets missing per stratum over the period | `INCONCLUSIVE` |
| Availability (surface B) | `A_C1 ≥ A_C0 − 0.05` and `CS ≥ A_C0 − 0.05` per primary stratum | guardrail FAIL |

## 9. Decision rule

**Stage H (not confirmatory):**
- `H_SUPPORTS_PROSPECTIVE`: `P_C1 ≤ P_C0 − 0.01` and every §5/§6 guardrail assessable on the proxy holds, and §8 met.
- `H_REFUTES`: `P_C1 > P_C0 + 0.005`, or a §5/§6 guardrail breached → C1 closed; a different scheme is a new design.
- `H_INFEASIBLE`: §8 not met.
- Neither `H_SUPPORTS_PROSPECTIVE` nor anything else in Stage H authorizes a product change.

**Stage P (confirmatory, non-inferiority with tolerance):**
- `P_PASS`: §8 met; on common support `|G_C1(s, m)| ≤ 0.02` for both primary strata and all metrics and `P_C1 ≤ P_C0`; every §5 (item 0 availability included) and §6 guardrail holds.
- `P_FAIL`: any guardrail breached, or `|G_C1(s, m)| > 0.03` for a primary stratum and metric, or `P_C1 > P_C0 + 0.005`.
- `P_INCONCLUSIVE`: otherwise, or §8 not met at the hard cap.

**Product decision:** `PASS` = `H_SUPPORTS_PROSPECTIVE` and `P_PASS` → a change may be **proposed** under `PRODUCT_FIRST_DECISION_V1` §11 (new context version label, config digest, deploy note); this design makes no change. `FAIL` = `H_REFUTES` or `P_FAIL`. `INCONCLUSIVE` otherwise. All numbers in §4–§9 are set now, before any count, and are not tuned after Stage H.

## 10. Stop conditions (→ `ABORTED`, no rate is computed)

- a product rule, cut, `min_venue_coverage`, context version or tape schema change during Stage P;
- the gate absent from `main` at the Stage P start (it is present at `a7d738f`; the condition stays as a check);
- tape completeness below 90% in a stratum over the period (→ `INCONCLUSIVE`);
- any pre-stop read of a Stage P rate or gap: the stage is void and must be re-declared on later data;
- an owner instruction to stop.

## 11. Allowed data, frozen inputs, forbidden inputs

**Allowed:** `CORE_BTC_BINANCE_V0` 1m 2020–2024 (Stage H, exposed proxy); beta state tape V2 rows (Stage P, read-only, after the start bucket); product config values at freeze (`label_high 0.95`, `rolling_buckets 12`, `percentile_window 30d`, tiers 3/7/30, `min_venue_coverage 2`, push policy parameters for the descriptive push counts); the UTC calendar.

**Frozen at freeze (digests recorded then):** this design and its twin; the evaluator; the config snapshot; the loader identities; the start and stop rules; the RV tercile edges after Stage H.

**Forbidden:** `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` and any OI/funding snapshot; research-protected 2025/2026 objects; the opened 2025-01..2026-08-15 surface (§7) unless the owner decides otherwise; E1-RUN-001 data; R03 unit files, results and estimates as inputs; holiday calendars; user-reaction telemetry.

## 12. No-lookahead rules

- A rank at `t` uses only buckets strictly before `t`; the weekday type of a sample is that of its own window end; the weekday type of the evaluated window is that of `t`.
- C1 is fixed now; it may not be modified after any Stage H count is seen.
- Tercile edges come from Stage H only and are carried into Stage P unchanged.
- Stage P is read once, at the stop defined by counts.
- No R03 number is an input, prior or offset.
- No evaluation-period data sets a threshold.

## 13. Execution prerequisites (none is done here)

1. Owner authorization to **freeze** this design (not given).
2. **Timestamp-only tape census** before freeze: bucket and per-venue OHLC presence from the state tape (no values), to compute expected `A_C0`, `A_C1` and common support per stratum and to fix `PROSPECTIVE_START`. It reads no market value; if the repository's data rules are read as forbidding even that, it is run as the first step after freeze and before Stage H.
3. Evaluator as offline tooling only: no change to `beta/` detector, gate, context, horizons, config or schema; synthetic-tape tests including a point-in-time test (a shock after `t` changes no rank at `t`), a weekday-type test across DST and year boundaries, a one-observation-per-clock-hour test, a usability-reason test on synthetic gaps, and a test that the census path never touches a value column.
4. Owner authorization to run Stage H.
5. Freeze of thresholds, start/stop rules and tercile edges **before** Stage P starts; owner authorization to activate Stage P and, at its stop, to open it.

## 14. Owner decisions pending

1. Freeze (with or without amendments); confirm C1 as primary.
2. Stage H execution.
3. Whether the opened 2025-01..2026-08-15 surface may be used as an additional `EXPOSED` sensitivity slice (never confirmatory).
4. Stage P activation; later, its opening at the stop.
5. On `PASS`: the product change under the decision's amendment process.

## 15. Revision 3 changes (design review of 2026-10-03)

- Exact prospective sampling unit on the UTC clock-hour grid, typed by the window start; overlapping windows are one observation.
- Primary comparison on paired common support; surface B (availability) added as a hard guardrail with enumerated unusable reasons and a 5 pp rule set from the completeness tolerance.
- Calendar feasibility of C1 recorded (9–10 weekend same-type dates per window); timestamp-only tape census added as a prerequisite.
- Inference replaced by frozen UTC-date (and ISO-week sensitivity) cluster-robust ratio estimators; the information requirement is derived from a prespecified variance design effect 2.5 (1 200 common-support hours per stratum), raised but never lowered by a pre-P amendment if Stage H shows more clustering; date minima dropped as redundant; a week-share and month-span diversity rule added; hard cap 52 weeks.
- Counts-only storage model stated: a timestamp census only before the stop; sufficient statistics exist only from the single run at the stop.
- 2025–2026 status unchanged: `NOT_PROVABLY_INDEPENDENT / EXPOSED_FOR_OTHER_PURPOSES`, not a holdout.

## 16. What this revision does not do

No data opened; no rank, rate or gap computed; no product code, config or schema changed; nothing frozen; no amendment of `PRODUCT_FIRST_DECISION_V1` opened; R03 untouched.
