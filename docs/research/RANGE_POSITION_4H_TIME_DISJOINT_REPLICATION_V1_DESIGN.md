# RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1 — design (WITHDRAWN before any outcome)

> **Withdrawn 2026-10-09 on the owner's review, before any outcome was read.** It is replaced by two separate one-shot units:
> - `RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1` (Unit A, frozen);
> - `RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1` (Unit B, draft pending review).
>
> **Defects corrected:**
> - a joint both-epochs gate;
> - recent-path controls proposed near the primary;
> - BitMEX zero-trade buckets treated as missing, against the canonical source authority;
> - a discovery-strength argument used for promotion;
> - spot opened in the same unit;
> - a mean-shift label.
> The text below is kept as the withdrawn record. Its code was never executed and was removed.

**Date:** 2026-10-09. **Author:** chief architect (research director).
**Owner order:** RANGE_POSITION_4H first (2026-10-09).
**Mode:** `CONFIRMATION`, one shot per surface. **Track:** `STRUCTURE`.
**Rules:** `RESEARCH_RULES_DECISION_V1.md`.
**Parent discovery:** `PRE_IMPULSE_STATE_ATLAS_V1` (Cursor, CORE Binance perp 2020–24, 496 cells), reviewed in `PRE_IMPULSE_STATE_ATLAS_V1_INDEPENDENT_REVIEW.md` (verdict `INTERESTING_BUT_TRIVIAL_CONFOUND_UNRESOLVED`).
- Lead object `RANGE_POSITION_4H`: 1h Spearman −0.0578, week-block CI −0.064…−0.052, N 175,356.
- Every year is negative.
- P(UP) by quintile runs from 0.563 to 0.453. The Q1−Q5 mean-return difference interval includes 0.

**Sibling unit:** `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1` (Cursor, Bybit 2020–24, frozen). Under §3 of the rules decision, a same-period other venue is robustness against venue and data artifacts, not question-fresh replication. This unit is the time-disjoint replication. It runs regardless of the Bybit route.

**Claim ceiling:** L2 historical. Never a current probability. `PRODUCT_INTEGRATION_CANDIDATE = NO`. No fees, entries, stops or PnL.

## Question

On BTC data from **other years** than the discovery, does the position of the close inside its trailing 4h high–low range carry information about the next 1h return beyond:
- the signed 4h return and 4h realized volatility (primary);
- also the most recent 1h and 15m displacement (secondary: the "rewrite of recent path" alternative)?

The discovery sign is negative. A same sign alone is not the conclusion.

## Surfaces and classes (per question)

| Role | Surface | Class for this question | Construction |
|---|---|---|---|
| `ERA` (route) | BitMEX XBTUSD perpetual 5m, bars opening 2016-05-13T11:55Z … 2019-12-31T23:55Z | `QUESTION_FRESH_REPLICATION` (RANGE_POSITION never read; the surface was read for tail_risk, execution_impact and events) | `docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz` (in git). Bars with `trades == 0` are **missing**: BitMEX carries the last price into empty buckets, and that is a fill. Inverse contract: log returns of the USD price. |
| `RECENT` (route) | Binance USD-M BTCUSDT 5m, 2025-01-01 … 2026-10-08 | `QUESTION_FRESH_REPLICATION` (product-open for other features; RANGE_POSITION never read) | data.binance.vision, monthly 2025-01 … 2026-07 and daily 2026-08-01 … 2026-08-15 and 2026-08-26 … 2026-10-08. No object overlapping `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` is requested (the monthly 2026-08 object and the daily 2026-08-16 … 2026-08-25 objects are refused before any request). Microsecond open times are converted to ms. |
| `ERA_SPOT` (robustness, not a route) | Binance spot BTCUSDT 5m 2017-08-17 … 2019-12-31 | same-period other venue as ERA → robustness only | DH1 spot inventory, digest-verified (`load_spot_5m`), months ≤ 2019-12 only |

**Not read:** CORE Binance perp 2020–24 (discovery surface) and Bybit (sibling unit).

## Anchors and formulas (identical to the sibling unit)

**Grid and anchors:**
- Complete 5m grid per surface; missing bars stay missing; nothing is carried forward or interpolated.
- Anchor bar `i`: its open minute ≡ 10 (mod 15), so `T` = bar close at :00/:15/:30/:45 UTC.
- An anchor needs bars `i−48 … i` and bar `i+12` present.

**Definitions:**
- `W` = bars `i−47 … i`.
- `RP4H(T) = (close[i] − min low(W)) / (max high(W) − min low(W))`. Missing if the span is not finite and positive.
- `RET_4H = log(close[i]/close[i−48])`.
- `RV_4H = sqrt(Σ_{k=i−47..i} log(close[k]/close[k−1])²)`.
- `R_1H = log(close[i+12]/close[i])`.
- `RANGE_WIDTH_4H = log max high(W) − log min low(W)` (diagnostic).
- Secondary controls: `RET_1H_LAG = log(close[i]/close[i−12])` and `RET_15M_LAG = log(close[i]/close[i−3])`.
- Construction diagnostic `RP4H_PREV`: the same position computed on bars `i−48 … i−1` with `close[i−1]`, so the feature does not share `close[i]` with the target's base.

**Sample:** one analysis sample per surface, where every quantity above is finite. Plus, for the ERA, `R_1H`'s bar `i+12` opens before 2020-01-01, and for RECENT before 2026-10-09.

## Estimands (per route surface)

**Method:**
- Average ranks (midranks).
- OLS residualization with an intercept on the ranks.
- Pearson correlation of the two residuals (partial Spearman).
- A residual is degenerate if its RSS ≤ 1e-12 × TSS.

**Estimands:**
1. **Raw:** Spearman(RP4H, R_1H).
2. **Primary:** partial Spearman(RP4H, R_1H | RET_4H, RV_4H).
3. **Secondary (recent-path control, not a route):** partial Spearman(RP4H, R_1H | RET_4H, RV_4H, RET_1H_LAG, RET_15M_LAG).

**Diagnostics (no route):**
- partial given RET_4H only;
- partial given RET_4H, RV_4H, RANGE_WIDTH_4H;
- partial of `RP4H_PREV` given RET_4H, RV_4H;
- quintiles of RP4H (edges 0.2/0.4/0.6/0.8): N, P(R_1H > 0), mean and median R_1H;
- Q1 − Q5 difference in P(UP) and in mean R_1H;
- calendar-year and half-sample raw and primary.

**Uncertainty:**
- ISO-week blocks of `T`, B = 2000, seed `20261118`, percentile 2.5/97.5.
- Raw, primary, secondary and the two Q1 − Q5 differences are recomputed in every draw, ranks included.
- Degenerate draws are omitted.
- Fewer than 1900 valid draws for raw or primary → `ESTIMATE_UNAVAILABLE` for that surface.

## Routes (per route surface; discovery sign negative)

| Route | Rule |
|---|---|
| `SUPPORTED` | raw < 0, primary < 0, primary interval entirely below 0 |
| `RAW_ONLY` | raw interval entirely below 0, primary interval includes 0 |
| `COMPATIBLE_UNCERTAIN` | raw < 0, raw interval includes 0, `SUPPORTED` not fired |
| `NOT_REPLICATED` | raw ≥ 0 |
| `INCREMENTAL_SIGN_OPPOSES` | raw interval entirely below 0, primary interval entirely above 0 |
| `ESTIMATE_UNAVAILABLE` | fewer than 1900 valid draws |

**Overall class:**
- `TIME_DISJOINT_REPLICATED_BOTH`: ERA and RECENT both `SUPPORTED`.
- `TIME_DISJOINT_REPLICATED_ONE`: one `SUPPORTED`, the other `RAW_ONLY` or `COMPATIBLE_UNCERTAIN`.
- `TIME_DISJOINT_CONFLICT`: one `SUPPORTED`, the other `NOT_REPLICATED` or `INCREMENTAL_SIGN_OPPOSES`.
- `TIME_DISJOINT_NOT_REPLICATED`: neither `SUPPORTED`.
- `UNAVAILABLE`: either surface `ESTIMATE_UNAVAILABLE`.

**Recent-path label** (secondary, per surface, never changes a route):
- `SURVIVES_RECENT_PATH`: secondary interval below 0;
- `ABSORBED_BY_RECENT_PATH`: interval includes 0;
- `OPPOSITE`: above 0.

**Economic label** (per surface, information only):
- `MEAN_SHIFT_PRESENT`: the Q1 − Q5 mean interval excludes 0;
- otherwise `SIGN_ONLY`. A sign shift with no mean shift is not an edge for a time-exit holding.

## What would change our mind
- **`SUPPORTED` on both eras with `SURVIVES_RECENT_PATH`:** location inside the trailing 4h range carries next-hour information beyond the recent path, in other years. Next: an economic test (barrier race and costs) as its own unit.
- **`RAW_ONLY` or `ABSORBED_BY_RECENT_PATH`:** the pattern is the ordinary recent-path state (short-horizon reversal), not a new object.
- **`NOT_REPLICATED`:** the 2020–24 pattern does not generalize in time. The exact candidate stops.
- **`SIGN_ONLY` everywhere:** even a replicated association is not an expected-return edge at 1h.

## Search exposure and penalty
- **Parent:** 496 cells on CORE DIRECTION. Lead week-mean t ≈ −22 (−0.068 / 0.0031). This passes the decision's promotion bound (Bonferroni α 0.10) for any plausible `m_ST`, so promotion to question-fresh replication is justified.
- **Counters before this unit** (`EXPOSURE_COUNTERS_V1.md`): BitMEX 2016–19 × DIRECTION = 0; Binance perp 2025–26 × DIRECTION ≈ 72\*; CORE × DIRECTION ≈ 813\*.
- **This unit adds, per route surface:** 3 inferential cells (raw, primary, secondary) on DIRECTION. The counters for ERA (BitMEX 2016–19) and RECENT (Binance perp 2025–26) are incremented when read.
- **Variants:** one feature, one target, one horizon, one primary control pair, one secondary control set. No threshold, no other horizon, no other window. Year and half splits are reports, not searched endpoints.

## Information (before reading)
- ERA ≈ 3.6 years, RECENT ≈ 1.75 years (minus the E1 gap and missing bars).
- The week-mean SE at discovery was 0.0031 over 262 weeks. Expected SE is about 0.0037 (ERA, about 190 weeks) and 0.0052 (RECENT, about 92 weeks).
- The discovery raw effect (−0.058) is far outside both. Exact anchor counts come from the outcome-blind census at run time.

## Execution
- **Code:** `scripts/research/rp4h_time_disjoint_v1/run.py`, committed with tests before the run.
- **Commands:** `census` (outcome-blind counts) and `run --go`. `run --go` refuses if the result exists.
- **Result:** `RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1_RESULT.json` / `.md`.
- **Prerequisite:** an owner go.
