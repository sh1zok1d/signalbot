# Weekday / weekend reference-distribution calibration — design V1

**Status:** `DESIGN_DRAFT / NOT_FROZEN / NOT_EXECUTED`
**Kind:** PRODUCT_FIRST calibration unit (product evidence, not a research claim)
**Date:** 2026-10-03
**Authority:** `PRODUCT_FIRST_DECISION_V1.md` §3 row 7, §3.1b (the unusual-hour gate) and §6 (data maturity). This design changes nothing in that decision.
**Machine twin (draft, not frozen):** `WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1.json`
**Motivation (basis only):** `research/OWNER_CARDS_R03_RESULT.md`, hypothesis C1: weekend hours have a narrower range than the same weekday hour, about −0.4 comparator-SD in 2020–2024, below the research bar and classified `NO_INCREMENTAL_STRUCTURE`. That verdict is not reopened and the −0.4 SD figure is **not** an input to anything below.

## 0. The product question (and only this question)

> Does splitting the reference distributions behind the unusual-hour flags by weekday type (Monday–Friday vs Saturday–Sunday, UTC) improve the calibration of those flags against the actual frequency of unusual hours, without degrading holdout/prospective calibration and without raising false alerts in the other regimes?

What this is not:
- not a test of whether weekends are narrower (R03 asked that; it is closed);
- not a reduction of weekend alerts as a goal; an under-flagging weekend is as miscalibrated as an over-flagging one (§5);
- not a threshold search: `context.label_high = 0.95`, the 2-of-3 rule and the 2-of-3 venue rule are fixed inputs and are never tuned here;
- not a detector change: the 5m detector, its percentiles and its episodes are untouched; only the product-level reference distribution of the 1h ranks is under study.

## 1. Baseline: the current calibration (C0)

As specified in the decision and implemented in `beta/hour_gate.py` (`BETA_HOUR_GATE_V1`) and `beta/context.py::context_1h` at the PR #314 merge commit `93bf257` (an immutable reference; see §12 on the state of `main`):

| Element | Current definition |
|---|---|
| Evaluated object | rolling 1h window ending at a 5m bucket `t`: `range_width_pct_median`, `volume_notional_usd_sum`, signed `price_move_pct_median` (cross-venue consensus) |
| Reference sample for the rank at `t` | the same rolling-1h value at **every 5m step in `[t − 30d, t)`**, all hours and all weekdays pooled (frozen percentile core, timeframe `1h`, window `30d`) |
| Rank | percentile rank of the value at `t` against that sample |
| Maturity | confidence tier by sample **span** (`none < 3d`, `low < 7d`, `building < 30d`, `mature ≥ 30d`); only `mature` ranks count in the gate |
| Flag per metric | range rank ≥ 0.95; volume rank ≥ 0.95; price rank ≥ 0.95 or ≤ 0.05 |
| Unusual hour | at least 2 of the 3 metric flags, and at least 2 of 3 venues agree on the sign of the 1h move |
| Nominal rate implied by the construction | if the reference distribution matches the evaluated windows, each unsigned flag fires on 5% of windows and the price flag on 10% |
| Presentation baseline (secondary surface) | `beta/horizons.py` `BETA_HORIZON_TOD_V1`: median of same-UTC-time (±30 min) rolling-1h values over the 30 prior UTC days, mature at 20 days; also pools weekday types |

The implied-rate line is the calibration target: a rank computed against a correct reference is uniform on fresh windows, so the flag rate on fresh windows equals the nominal cut. Nothing in C0 or the candidates changes the cut.

## 2. Candidate: stratified reference (C1), and the one pre-declared variant

**C1 (primary).** Identical rule, identical cuts, identical maturity semantics. The only change: the reference sample for a window ending at `t` contains only the rolling-1h values at 5m steps in `[t − 30d, t)` whose window end falls on a UTC date of the **same weekday type** as `t` (weekday = Monday–Friday, weekend = Saturday–Sunday, by the UTC date of the window end).
- Weekday ranks see about 21–22 same-type days per 30 calendar days; weekend ranks see about 8–9.
- Because the tier is by span, a weekend reference can be `mature` on 8 days. C1 therefore adds an explicit **same-type day minimum**: a rank is usable only if its reference holds at least `MIN_SAME_TYPE_DAYS = 8` distinct same-type UTC dates. This is a maturity guard, not a threshold on the market value.
- Weekday type is a calendar fact of the window end; no holiday calendar enters C1.

**C1-LONG (secondary, reported, cannot decide).** Same as C1 but the reference is the most recent **30 same-type UTC dates** (about 42 calendar days back for weekdays, about 105 for weekends). It is recorded to show the recency/sample-size trade-off. If the owner prefers it as primary at freeze time, that choice is made before any outcome and C1 becomes the secondary; the two never swap after outcomes.

No third variant. Session-stratified, holiday-aware or hour-of-day-stratified references are out of scope for this unit; each would be a new design.

## 3. Evaluation objects and strata

- **Evaluation window:** every 5m step `t` in the evaluation period with usable (mature) ranks under the scheme being evaluated. Overlapping 1h windows are dependent; all interval estimates use **non-overlapping hourly windows** (window end on the hour) as the counting unit, and the 5m-step rates are reported beside them.
- **Primary strata:** `WEEKDAY`, `WEEKEND`, `AGGREGATE`.
- **Pre-declared guardrail cells** (fixed now, never added after outcomes): weekday type × UTC session band (`ASIA 00–08`, `EUROPE 08–13`, `US 13–21`, `LATE 21–24`) × trailing-30-day realized-volatility tercile of the evaluation period (terciles fixed from the discovery stage, §7). Twenty-four cells; a cell is assessable only with at least 100 non-overlapping hours.

## 4. Primary calibration metrics

For a scheme S, a stratum s and a metric m, with `cut = 0.95`:

- `E_S(s, m)` = share of evaluated hours in s whose rank of m is ≥ 0.95 (price: ≥ 0.95 or ≤ 0.05).
- `nominal(m)` = 0.05 (range, volume), 0.10 (price).
- **Exceedance gap** `G_S(s, m) = E_S(s, m) − nominal(m)`, signed. Positive = over-flagging, negative = under-flagging. Both are miscalibration.
- **Primary statistic** `P_S = max over s ∈ {WEEKDAY, WEEKEND}, m ∈ {range, volume, price} of |G_S(s, m)|` — the worst-stratum absolute gap.
- **Unusual-hour rate** `U_S(s)` = share of evaluated hours that the full 2-of-3 + venue rule qualifies, per stratum. No nominal value is claimed for it (the metrics are dependent); it is compared between schemes only through the guardrails of §5 and §6.
- **Uniformity diagnostic** (reported, not decisive): the Kolmogorov distance between the empirical distribution of ranks in s and the uniform distribution, per metric.

The decision compares `P_C1` with `P_C0` on the same evaluation hours (§9).

## 5. False-positive / false-alert guardrails

"False alert" is defined relative to the rule's own nominal rate, not relative to fewer alerts:

1. **No over-flagging anywhere:** for every primary stratum and metric, `G_C1(s, m) ≤ G_C0(s, m) + 0.01` (the candidate may not add more than 1 percentage point of exceedance over the baseline in any stratum).
2. **No under-flagging bought with the split:** for every primary stratum and metric, `G_C1(s, m) ≥ −0.02`. A weekend reference that makes weekend flags rarer than 3% for a 5% cut fails this guardrail even if `P_C1` improved. This is the explicit guard against "fewer weekend alerts at any cost".
3. **Weekday is not sacrificed:** `|G_C1(WEEKDAY, m)| ≤ |G_C0(WEEKDAY, m)| + 0.005` for every metric.
4. **Coverage guardrail (decision §3 row 7 diagnostic):** the share of `TRIGGERED` detector hours that the gate qualifies may not fall by more than 5 percentage points in any primary stratum relative to C0. On the historical proxy stage, where no detector episodes exist, this guardrail is evaluated against proxy 5m-detector-style exceedances only if those exist in the proxy; otherwise it is recorded `NOT_ASSESSABLE_ON_PROXY` and binds on the prospective stage.

## 6. Degradation guardrails (weekday, weekend, aggregate, cells)

- **Aggregate:** `|G_C1(AGGREGATE, m)| ≤ |G_C0(AGGREGATE, m)| + 0.005` for every metric. Splitting may not make the pooled flag rate worse.
- **Cells:** for every assessable guardrail cell of §3, `|G_C1(cell, m)| ≤ |G_C0(cell, m)| + 0.01`. A single breach is a FAIL; cells with fewer than 100 hours are reported but do not decide.
- **Rank-usability loss:** the share of evaluation hours whose ranks are unusable under C1 (the same-type day minimum) but usable under C0 may not exceed 10% in any primary stratum on the prospective stage. A scheme that calibrates by abstaining is not an improvement.
- **Staleness (C1-LONG only, descriptive):** median calendar age of the reference sample per stratum.

## 7. Two stages, and the holdout / prospective split

**Stage H — historical proxy (discovery, exposed data).**
- Data: pinned `CORE_BTC_BINANCE_V0` BTCUSDT perpetual 1m, 2020-01..2024-12, via the existing SHA256-verified loaders. Single venue, so the venue-agreement rule is not evaluable; range, volume and price flags are.
- Proxy construction: 5m buckets from 1m bars; rolling-1h values with the product definitions (range = (max high − min low)/first open; price = (last close − first open)/first open; volume = sum of quote volume). This is a **proxy of the product tape**, labelled `PROXY_SINGLE_VENUE_EXPOSED`; it is never presented as the product's own calibration.
- Split inside Stage H: **discovery 2020-01..2022-12**, **proxy holdout 2023-01..2024-12**. The volatility terciles for the guardrail cells are fixed from the discovery years only. Nothing about C1 may be changed after the discovery years are seen; the proxy holdout is read once.
- Role: the only stage with real statistical power (about 520 weekend days and 1300 weekday days over five years; exceedance-rate standard errors near 0.2 pp on hourly units).

**Stage P — prospective, product tape (confirmation, product evidence).**
- Data: the beta state tape, schema V2, rows from 2026-10-01 (decision §6), read through the existing tape loaders; cross-venue consensus as in production; venue rule evaluable.
- Evaluation period: starts at `PROSPECTIVE_START`, set at freeze to the first UTC date on which **both** C0 and C1 weekend ranks are usable (C0 needs a 30-day span, C1 needs 8 weekend dates inside 30 days: both about **2026-10-31**); ends at `PROSPECTIVE_END = PROSPECTIVE_START + 56 days` or when the minimum N of §8 is met, whichever is later, with a hard stop at `PROSPECTIVE_START + 84 days`.
- Rule: no interim look at any exceedance rate; only counts (usable hours per stratum) are monitored until the stop. One analysis at the stop.
- Power: honest statement — with about 16 weekend days (≈ 380 hours) a 2 pp gap has a standard error near 1.1 pp. Stage P is therefore a **non-inferiority check with the tolerance bands of §5–6**, not a precise re-estimation. The decision in §9 reflects that.

**No other surface.** The research-protected 2025/2026 Binance data are not part of this design. The six-symbol divergence surface that was opened for the divergence program (2025-01..2026-08-15) would be a better proxy holdout than 2023–2024; using it for a product calibration is **an owner decision**, not assumed here (§13).

## 8. Minimum information / feasibility requirements

| Requirement | Threshold | Else |
|---|---|---|
| Stage H discovery hours per stratum | ≥ 5000 weekday, ≥ 2000 weekend non-overlapping hours with usable ranks under both schemes | `INFEASIBLE_PROXY` |
| Stage H proxy-holdout hours per stratum | ≥ 3000 weekday, ≥ 1200 weekend | `INFEASIBLE_PROXY` |
| Stage P usable hours at the stop | ≥ 700 weekday and ≥ 300 weekend non-overlapping hours with usable ranks under **both** schemes; ≥ 8 distinct weekend dates and ≥ 20 weekday dates | `INCONCLUSIVE` |
| Tape completeness in Stage P | ≤ 10% of 5m buckets missing in each stratum | `INCONCLUSIVE` |
| Assessable guardrail cells | at least 12 of 24 on Stage H; cells below 100 hours are descriptive | recorded |
| Rank-usability loss (C1 vs C0) | ≤ 10% per stratum (§6) | FAIL on the guardrail |

## 9. Decision rule

Evaluated mechanically at the end of each stage; each stage has its own record. The product decision requires both.

**Stage H (proxy):**
- `H_PASS`: on the proxy holdout, `P_C1 ≤ P_C0 − 0.01` (the worst-stratum gap improves by at least 1 pp) **and** every §5 and §6 guardrail holds.
- `H_FAIL`: `P_C1 > P_C0 + 0.005`, or any §5/§6 guardrail breached.
- `H_INCONCLUSIVE`: neither (improvement under 1 pp with no breach), or §8 not met.

**Stage P (prospective, non-inferiority):**
- `P_PASS`: §8 met; `|G_C1(s, m)| ≤ 0.02` for both primary strata and all metrics (within 2 pp of nominal); every §5/§6 guardrail holds against C0 on the same hours.
- `P_FAIL`: any guardrail breached, or `|G_C1(s, m)| > 0.03` for any primary stratum and metric.
- `P_INCONCLUSIVE`: §8 not met at the hard stop, or neither of the above.

**Product decision:**
- `PASS` = `H_PASS` and `P_PASS` → a config/baseline change may be **proposed** under `PRODUCT_FIRST_DECISION_V1` (new context version label, amendment log); this design does not make that change.
- `FAIL` = `H_FAIL` or `P_FAIL` → C1 is closed; a different scheme is a new design.
- `INCONCLUSIVE` otherwise → recorded; extending Stage P is a new preregistration on later data, never a continuation.

The thresholds above (1 pp improvement, 2 pp and 3 pp bands, 0.5 pp and 1 pp tolerances, 5 pp coverage, 10% usability loss) are set now, before any count. They are not tuned after Stage H.

## 10. Stop conditions

Stop and record `ABORTED` with the reason, no analysis of exceedance rates:
- the product rule changes during Stage P (`context.label_high`, the 2-of-3 rule, `min_venue_coverage`, the context version, the tape schema);
- the product-first gate is not present in `main` at the start of Stage P (§12);
- Stage P hard stop reached below §8 (then `INCONCLUSIVE`, not `ABORTED`);
- tape completeness below 90% in a stratum over the whole period;
- any read of Stage P exceedance rates before the stop (integrity failure; the stage is void and must be re-declared on later data);
- an owner instruction to stop.

## 11. Allowed data, frozen inputs, forbidden inputs

**Allowed data**
- `CORE_BTC_BINANCE_V0` 1m, 2020-01..2024-12 (Stage H), pinned and verified.
- Beta state tape schema V2 rows from 2026-10-01 (Stage P), read-only.
- Product config values as frozen at freeze time: `context.label_high`, `rolling_buckets`, `percentile_window = 30d`, tier thresholds (`3 / 7 / 30` days), `min_venue_coverage = 2`.
- UTC calendar (weekday type).

**Frozen inputs at freeze (digests recorded then):** this design and its JSON twin; the evaluator code; the config snapshot; the loader identities; `PROSPECTIVE_START`/`END`; the volatility tercile edges after Stage H discovery.

**Forbidden**
- `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` and any OI/funding snapshot.
- Research-protected 2025/2026 Binance objects (unless the owner decides §13 item 3); E1-RUN-001 data.
- The R03 unit files, results or the −0.4 SD estimate as inputs, offsets or priors.
- Any holiday calendar (out of scope for C1).
- Any product-side telemetry about user reactions (this is calibration, not usefulness).

## 12. Execution prerequisites (none of them is done by this design)

1. **Repair of `main`.** The merge commit of PR #303 (`04e1300`) took the research branch's tree for `beta/`, `runtime/`, `storage/`, `config/beta_v0.yaml` and `tests/beta` wholesale and thereby removed the product-first implementation of PRs #314, #316, #317 and #318 from `main` (37 files, −3468 lines; `beta/hour_gate.py`, `beta/market_view.py`, `BETA_CONTEXT_1H_V2`, the push policy and their tests are absent at `7bbc9bb`). PR #320 did not touch these paths and neither fixed nor worsened this. Until it is repaired, the gate this design calibrates does not exist in `main` and Stage P cannot start. This is an owner decision (restore from `93bf257`/`0fc1cb0` state via a merge, not a history rewrite).
2. **Owner authorization to freeze** this design (digests, permit) — not given yet.
3. **Evaluator implementation** as offline tooling only (`beta/` presentation and detector untouched), tested on synthetic tapes, including a point-in-time test (a shock after `t` changes no rank at `t`) and a weekday-type test across DST and year boundaries.
4. **Tape maturity** per decision §6: weekend ranks under C1 usable from about 2026-10-31.
5. **Owner authorization to execute** Stage H, and separately to open Stage P at its stop.

## 13. Decisions that need the owner

1. Freeze this design (or amend it first); choose C1 or C1-LONG as primary before any count.
2. Repair of `main` (§12.1) and how (merge of the product-first state over `main`).
3. Whether the opened six-symbol 2025-01..2026-08-15 surface may serve as the Stage H proxy holdout instead of 2023–2024 (research-governance call under `DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3`).
4. Execution of Stage H; later, opening of Stage P.
5. If `PASS`: the product change itself, under the decision's amendment process.

## 14. What this design does not do

No data was opened. No rank, rate or gap was computed. No product code, config or schema was changed. Nothing is frozen. R03 is not reopened and its verdict stands.
