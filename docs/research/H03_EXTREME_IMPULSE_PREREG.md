# H03 Extreme Impulse → Continuation vs Exhaustion — Preregistration

**Status:** PREREGISTERED_EXPLORATORY
**Hypothesis ID:** `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION`
**Machine-readable freeze:** `docs/research/H03_EXTREME_IMPULSE_PREREG.json`
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`

This document is frozen **before** any H03 development forward outcomes are computed. A clean null is a successful research result. This is not a trading strategy, PnL claim, liquidation hypothesis, news classifier, market-maker explanation, or product detector.

This is the **third** primary mechanism family in R2 Batch 01. H01 (Compression → Expansion) and H02 (Failed Breakout → Mean Reversion) are already closed `REJECTED_SPECIFIC_CLAIM`/`*_KILL`. H03 uses the same 2020–2024 discovery lab as H01/H02 — it is development/discovery only and is **not** independent confirmation of anything.

Authoritative source: `docs/research/H03_DESIGN_FROZEN_DRAFT.md` as corrected by `docs/reviews/H03_DESIGN_REDTEAM.md` and `docs/reviews/H03_DESIGN_MAINTAINER_ADDENDUM.md`. Where any earlier Claude-red-team wording conflicts with the maintainer addendum, the maintainer addendum wins; this preregistration follows the maintainer-corrected design throughout.

## 0. Global adaptivity disclosure (completed, frozen, may not be weakened after outcomes)

- H03's mechanism class predates both H01 and H02 outcomes: "extreme impulse → continuation versus exhaustion" is explicitly listed in the original R2 roadmap (`docs/RESEARCH_ROADMAP.md` §R2) alongside compression→expansion and failed-breakout→mean-reversion, before either was executed.
- Several conventions are intentionally **inherited as project-wide research conventions**, not selected from H01/H02 outcomes: the 15-minute decision grid and 30-calendar-day local-reference concept match H01; the 15/30/60/120/240-minute outcome ladder is shared by H01 and H02; 100 matched-random replicates, UTC-week block uncertainty, and a `+6h` same-day timing control follow prior research convention (H01/H02/E1 as applicable).
- **The 60-minute refractory is not copied from H02** — H02 used a 30-minute refractory. H03's 60-minute refractory is a new, pre-outcome choice made to reduce clustering of extreme-impulse triggers specifically, not a value selected because of any favorable H02 outcome.
- **`q90`/`q95`/`q98` is new to H03** — neither H01 nor H02 used this tail-percentile family. It is frozen as a coarse three-level tail-severity grid before H03 outcomes.
- **`W = {15, 30, 60}` minutes is not copied directly from either prior family** — H01 used 30/60/120m compression lookbacks; H02 used 60/120/240m range lookbacks. H03's impulse windows overlap in scale but were chosen independently for this mechanism.
- Prior H01/H02 experience with clustering/dependence concerns influenced the decision to make H03's refractory and dependence reporting explicit and disclosed — this batch-internal influence is stated plainly, not hidden.
- H01's post-hoc observation (low-volatility persistence) and H02's post-hoc observations (small generic short-horizon boundary-breach bounce; failed breakout did not outperform the successful-breakout control) did **not** define H03's mechanism, sign alternatives, or threshold ladder. Neither observation may rescue H01/H02 or seed H03 directly; both remain `POSTHOC_UNTESTED`.
- **Control formulations considered:** exactly one structural control (moderate-momentum band) and one negative control (`+6h` circular shift) were considered. No alternative formulation was tried and discarded.
- H03 is not independent confirmation. It uses the same 2020–2024 discovery lab as H01/H02.

This disclosure is copied from the corrected design (`docs/research/H03_DESIGN_FROZEN_DRAFT.md` §0) and is not weakened here.

## 1. Research question

After an unusually large short-horizon BTC directional move relative to its own recent local distribution, does subsequent price movement systematically:

- **A. continue** in the impulse direction,
- **B. exhaust/reverse** against the impulse direction, or
- **C.** show no practically meaningful robust conditional directional effect?

Both continuation and exhaustion are preregistered competing possibilities, fixed before any real outcome is inspected.

## 2. Dataset and information at T

Use accepted `CORE_BTC_BINANCE_V0` only, snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`. Fail closed if the repository manifest's `snapshot_id`, `status`, or `research_authorized` differ from what this document requires. The development runner loads 2020–2024 canonical 1m monthly parquet only and must not open 2025/2026 partitions.

Price columns are canonical decimal strings; parse with `float(Decimal(...))` before arithmetic, never lexicographically.

## 3. Chronological windows (UTC)

| Window | Start inclusive | End exclusive | Outcome inspection |
|---|---|---|---|
| Warmup | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features only |
| Development / discovery | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | allowed |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | **forbidden** |
| Untouched OOS | 2026-01-01T00:00:00Z | 2026-08-26T00:00:00Z | **forbidden** |

An observation is eligible for horizon `H` only if its **entire** frozen future `H` path resolves strictly before `2025-01-01T00:00:00Z`. No horizon truncation. No future read across evidence-pool boundaries. The identical rule applies at the `2025 → 2026` boundary when validation/OOS phases are eventually opened.

## 4. Canonical timeframe and decision grid

UTC-aligned 15-minute boundaries. `T` is the `bar_end_exclusive` of the fully closed 15-minute bar ending at `T` — equivalently, `close(T)` is the close of the canonical 15-minute interval `[T-15m, T)`, i.e. the close of the final canonical 1m bar whose `bar_end_exclusive == T`. `close(T-W)` uses the corresponding fully available close at that boundary, with no off-by-one implementation discretion. The still-forming bar is never used.

## 5. Impulse windows

`W ∈ {15, 30, 60}` minutes.

```
IMPULSE_RET_W(T) = ln(close(T) / close(T-W))
```

Direction: `+1` if `> 0`, `-1` if `< 0`. Exact zero: excluded.

## 6. Extremeness

```
ABS_IMPULSE_W(T) = abs(IMPULSE_RET_W(T))
```

Reference distribution: same `W`, same UTC 15-minute grid, preceding 30 calendar days, strictly before `T` (current `T` excluded; no future observations; no full-dataset or year-wide percentile).

Frozen H01-compatible midrank percentile:

```
P_W(T) = (count(ref < x) + 0.5 * count(ref == x)) / N_ref,   x = ABS_IMPULSE_W(T)
```

Thresholds: `q ∈ {0.90, 0.95, 0.98}`. Candidate: `P_W(T) >= q`. No extra `q` values after outcomes.

## 7. Reference-overlap disclosure (descriptive only, not a pass/fail gate)

For the impulse-percentile reference, report:

- nominal `N_ref` (~2,880 for a complete 30-day 15m grid);
- `N_eff_W = floor(30*24*60 / W_minutes)` (2,880 / 1,440 / 720 for `W=15/30/60`);
- tail proxy `N_eff_W * (1-q)`;
- moderate-band proxy `0.20 * N_eff_W`;
- per-decile proxy `0.10 * N_eff_W`.

For the `H`-horizon normalization reference (§9), report separately: `N_eff_H = floor(30*24*60 / H_minutes)`.

These are conservative transparency diagnostics, **not** estimated iid sample sizes, and there is no arbitrary adequacy cutoff (e.g. no 200-observation pass/fail threshold).

## 8. Refractory

60 minutes. Within each `(W, q)`: after accepting one qualifying event at `T`, ignore further qualifying events of either direction during `(T, T+60m)`; keep the earliest. Report raw pre-refractory `N` and post-refractory `N`. Never retuned after outcomes.

## 9. Primary outcome and normalization

```
RET_H(T)      = ln(close(T+H) / close(T))
CONT_RET_H(T) = impulse_direction(T) * RET_H(T)
```

`CONT_RET_H > 0` → continuation. `CONT_RET_H < 0` → exhaustion. Never flip the sign after outcomes.

```
PAST_MEDIAN_ABS_RET_H(T) = median of H-horizon absolute returns on the same UTC 15m grid,
    over the preceding 30 calendar days, using ONLY observations fully resolved strictly
    before T. Current/future outcome excluded.

NORM_CONT_RET_H(T) = CONT_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)
```

**No full-development statistical floor is used.** A floor estimated from the complete 2020–2024 scale series would let an early decision time depend on scale states occurring later in development, violating as-of semantics. The denominator must be finite and strictly positive using only trailing, fully-resolved pre-T history; if it is zero, non-finite, or unavailable, that outcome is ineligible and counted explicitly. No post-outcome floor or winsorization may be introduced.

For every `H`, report the denominator distribution (minimum, p01, p05, p25, p50) and the share of total absolute normalized-outcome magnitude contributed by the largest 1% of `|NORM_CONT_RET_H|` observations, as fixed diagnostics only.

## 10. MPIE and control materiality (frozen numbers)

```
MPIE (primary, matched-random gate):
  S * (mean_extreme - mean_matched) >= 0.10   normalized units

CONTROL_DELTA_MIN = 0.05   (half of MPIE, frozen pre-outcome)

Structural-control requirement:
  S * (mean_extreme - mean_moderate) >= 0.05

Timing-negative-control requirement:
  S * (mean_true - mean_shifted) >= 0.05
```

where `S` is the ultimately selected preregistered sign (`+1` continuation, `-1` exhaustion). Raw mean `CONT_RET_H` in bps must also be reported (descriptive; not PnL). `CONTROL_DELTA_MIN` freezes the otherwise-ambiguous word "materially" and may not be reinterpreted after outcomes.

## 11. Structural control

Moderate-impulse population: `0.60 <= P_W(T) < 0.80`, same `W`, same direction rule, same UTC grid, same 60-minute refractory, same future-outcome semantics. Month- and direction-matched against extreme candidates where possible; unmatched cases must be explicitly counted and reported (matched `N`, unmatched `N`, unmatched share), never silently dropped. No alternative structural control may be added after outcomes.

## 12. Matched-random baseline

For each `(W, q)`: preserve calendar-month event counts and UP/DOWN direction composition. Sampling is **without replacement inside each replicate**. The random pool **excludes every raw qualifying extreme-impulse timestamp** for that same `(W,q)` before refractory deduplication, but does **not** exclude surrounding hours or whole volatile regimes. Assign each matched observation the paired real candidate's direction label. Seed `20260831`, used exactly once, never re-rolled. 100 replicates. Report candidate-minus-matched mean `NORM_CONT_RET_H` and continuation positive-share.

Residual-imbalance diagnostic: day-of-week and day-of-month distributions for real candidates vs. matched draws, plus `TVD = 0.5 * sum_i |p_i - q_i|` for each. Descriptive only; does not create an alternative matched baseline.

## 13. Negative control

`+6` hour circular shift within the same UTC day, preserving `W`, `q`, and the original direction. Do not redetect an impulse at the shifted `T`. Require valid past/future coverage at the shifted `T`. Report the fraction of shifted timestamps that coincide with a raw true extreme-impulse timestamp for the same `(W,q)`; do not remove such collisions post hoc. Known limitation, disclosed and accepted: a quarter-day shift can introduce mild diurnal/session-timing differences (matches E1-RUN-001's established `+6h` convention). No alternative time-shift value after outcomes.

## 14. Primary search surface

`3 W × 3 q × 5 H = 45` primary cells. Both continuation and exhaustion are preregistered competing interpretations of the same signed statistic. H03 is the **third** tested mechanism family in R2 Batch 01 (H01 = 45 cells, H02 = 45 cells) — never written as if one isolated cell were tested once.

## 15. Primary metrics

For all 45 cells: `N`; mean/median `NORM_CONT_RET_H`; mean `CONT_RET_H` in bps; `P(CONT_RET_H>0)`, `P(CONT_RET_H<0)`; p05/p25/p75/p95 of `NORM_CONT_RET_H`. No PnL, no Sharpe, no leverage.

## 16. Decile diagnostic

Fixed bins `[0,10), [10,20), ..., [90,100]` of `P_W(T)` using the same frozen midrank percentile convention: `N`, mean `NORM_CONT_RET_H`, `P(CONT_RET_H>0)` per bin. Diagnostic only — no new thresholds may be selected from deciles inside H03. The §7 effective-N disclosure applies identically to each decile bin.

## 17. Secondary path metrics

Over `[T, T+H]`: MFE in the impulse direction, MAE against it, each normalized by the same valid pre-T local scale. Also `P(MFE_impulse > MAE_opposite)`. Secondary only; cannot rescue a failed primary close-return outcome. MFE/MAE cannot satisfy the adjacent-horizon coherence gate (§20 item 6) because they are mechanically monotonic across nested horizons by construction.

## 18. Dependence / concentration

Report: raw `N`; post-refractory `N`; unique UTC days/weeks/months; events by year; events by month; largest-month share; top-5-month share; UP share; DOWN share; median event spacing.

## 19. Uncertainty and the long-dependence diagnostic

Primary: UTC-week block bootstrap, seed `20260901`, 2000 replicates. Candidate-for-freeze sensitivity: 1-week, 2-week, 4-week blocks — fixed, not selectable.

**Long-dependence diagnostic (fixed, non-selectable, descriptive only):** on the daily series of total absolute 15-minute log-returns (candidate/outcome-independent), compute the ACF at the fixed lag set `{1,2,4,8,16,32,64}` calendar days. Freeze:

```
L_dep = max{ L : |ACF(L)| >= 0.20 }
```

Report `<1 day` if no lag qualifies; `>=64 days` if lag 64 qualifies. **This uses the largest qualifying lag, not the first ACF crossing below 0.20** — a non-monotone ACF that dips early and rises again must not be reported as short dependence.

## 20. Year stability, direction symmetry, parameter robustness

Report 2020–2024 separately. No shock-year exclusion, no deletion of 2020/2022, no regime rescue. For an unconditional H03 candidate, the selected sign should appear in at least 4 of 5 years.

H03 is symmetric: a continuation candidate requires both UP and DOWN impulses to show continuation overall; an exhaustion candidate requires both to show exhaustion overall. If only one side survives, the symmetric claim is `REJECTED_SPECIFIC_CLAIM` and the one-sided result is `POSTHOC_UNTESTED` — it cannot enter Batch 01 validation.

No best-cell promotion: report `q90/q95/q98` neighborhoods and `W=15/30/60` separately; require a coherent same-sign neighborhood, not one isolated optimum. At least two adjacent horizons must support the primary `CONT_RET_H`/`NORM_CONT_RET_H` sign — MFE/MAE cannot satisfy this gate.

Candidate-for-freeze requirements (either sign), all of:

1. primary close-return effect has the sign;
2. candidate-minus-matched normalized mean meets or exceeds MPIE (0.10, §10);
3. extreme impulse separates from moderate momentum by `CONTROL_DELTA_MIN=0.05` (§10–§11);
4. the `+6h` negative control is weakened by at least `CONTROL_DELTA_MIN=0.05` (§10, §13);
5. `q90/q95/q98` form a coherent same-sign neighborhood;
6. at least two adjacent horizons support the same sign on the primary metric (not MFE/MAE);
7. the sign appears in at least 4/5 development years;
8. UP and DOWN both support the symmetric claim;
9. no single month/regime dominates;
10. dependence-aware uncertainty (block bootstrap + §19 diagnostic) is compatible with a real effect;
11. the §19 dependence diagnostic does not reveal a misleading effective-N interpretation without explicit caution disclosed;
12. the primary outcome itself, not only MFE/MAE, supports the mechanism.

## 21. Development verdict (choose exactly one)

- `H03_CONTINUATION_CANDIDATE_FOR_FREEZE`
- `H03_EXHAUSTION_CANDIDATE_FOR_FREEZE`
- `H03_INCONCLUSIVE`
- `H03_REJECTED_SPECIFIC_CLAIM`

No validation is opened at this point. No R3 optimization is started inside the development run. After the development run: **do not inspect 2025 or 2026**. Stop before R3 regardless of verdict.

## 22. Implementation notes

Tooling: `scripts/research/h03_extreme_impulse.py` + `_lib.py`. Tests: `tests/research/test_h03_extreme_impulse.py`. Not a universal backtester. Does not modify H01/H02 implementations or production forecasting code. H01 remains `H01_KILL`/`REJECTED`; H02 remains `H02_KILL`/`REJECTED`; neither is reinterpreted here.
