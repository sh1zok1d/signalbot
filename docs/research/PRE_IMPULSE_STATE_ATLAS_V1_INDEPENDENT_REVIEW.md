# PRE_IMPULSE_STATE_ATLAS_V1 — independent review

**Status:** review of a finished discovery scan. No new market read. No successor executed.
**Reviewed result:** `docs/research/PRE_IMPULSE_STATE_ATLAS_V1.md` / `.json` / `_LEDGER.json` / `.png`, design `docs/research/PRE_IMPULSE_STATE_ATLAS_V1_DESIGN.md`.
**Read timestamp of the scan:** `2026-10-09T13:38:33Z`.
**Design SHA256:** `01b7eafb7d2231388503a0c523e1443eceba7666b774ec8d0c1dc5fb055c3a5b`.
**Ledger SHA256:** `29fbc898fd7ddea73407be5a417be40509d981a9f247c977b08c160ce3773a1b`.
**Evaluator digest that produced the numbers:** `b6e8d83f2d6f680b219edcfa3dab5ce96cfe0b3a4230b04e5c2952966acdb733`.
**Claim ceiling of the scan, unchanged:** `DISCOVERY_ONLY`.
**Evidence class, unchanged:** `HISTORICAL_DIRECTIONAL_DISCOVERY / ADAPTIVE_SEARCH`.
**This review's verdict:** `INTERESTING_BUT_TRIVIAL_CONFOUND_UNRESOLVED`.

The scan's own narrative is treated as a hypothesis. Numbers below are copied from the saved JSON. They were not recomputed, and the scanner was not rerun.

## 1. What was audited

| Artifact | Role |
|---|---|
| `docs/research/PRE_IMPULSE_STATE_ATLAS_V1_DESIGN.md` | Frozen search, hashed before the scan |
| `scripts/research/pre_impulse_state_atlas_v1/constants.py` | Bounds, feature registry, score, bootstrap seed `20261116` |
| `scripts/research/pre_impulse_state_atlas_v1/features.py` | Past-only formulas, including `close_pos_4h` and `_boundary` |
| `scripts/research/pre_impulse_state_atlas_v1/stats.py` | Spearman, hour demean, quintiles, week blocks, bootstrap, partial given `rv_4h` |
| `scripts/research/pre_impulse_state_atlas_v1/evaluate.py` | Anchors, `R_H`, cell loop, ranking |
| `docs/research/PRE_IMPULSE_STATE_ATLAS_V1.json` | 496 cells, top-10 bootstrap, quintiles |
| `docs/research/PRE_IMPULSE_STATE_ATLAS_V1_LEDGER.json` | Cell ledger, hash above |
| `docs/research/PRE_IMPULSE_STATE_ATLAS_V1.md` | Narrative under attack |
| `docs/research/PRE_IMPULSE_STATE_ATLAS_V1.png` | Quintile figure of the ranked cells |
| `docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.md`, `H02_DEV_SUMMARY.md` | Prior failed-breakout formula |
| `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.md`, `B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md` | Prior post-breach path formula |

`MARKET_PHENOMENA_CATALOG_V1` is not in the repository, not in the searched git history, and not in the accessible parent-agent transcript. The comparison in §5 uses the phenomenon labels named in the review request. It does not invent a catalog text and then match against that invention.

## 2. Implementation

Decision time `T` is the close time of a 5-minute bar. The anchor keeps index `i` when `i >= 96`, `i % 3 == 2`, and the bar closes before `2025-01-01`. The first anchor is `2020-01-01T08:15:00Z`. Anchor N is `175359`. Finite 1h targets: `175356`.

`R_H = log(close[i+h] / close[i])`. For 1h, `h = 12`. The future price is a later close. The feature at `i` does not read `close[i+1]` or later. A regression test locks that a future close does not change a feature. There is no centered window.

`close_pos_4h` at index `i` is

```text
(close[i] - min low[i-47 : i]) / (max high[i-47 : i] - min low[i-47 : i])
```

when the span is finite and positive. The window is 48 bars and **includes the bar that closes at T**. The current close sits in the numerator. The current bar's high and low sit inside the max and the min. If that bar prints the window high or the window low, the ratio is pushed toward 1 or 0 by construction. When the span is positive the ratio lies in `[0, 1]`, because `low[i] <= close[i] <= high[i]` and those prints are inside the window extrema.

`dist_lower_4h` is `(close[i] - min low) / span` on the same 48-bar window. `dist_upper_4h` is `(max high - close[i]) / span`.

Algebra, when `span > 0`:

```text
close_pos_4h = dist_lower_4h
dist_upper_4h = 1 - close_pos_4h
```

The saved 1h Spearmans match that identity. `close_pos_4h` and `dist_lower_4h` are the same recorded value, `-0.057773446228651215`. `dist_upper_4h` is `+0.057773446202884805`. The absolute gap versus the negated value is about `2.6e-14`, which is the floating-point residue of a complement, not a second series. The 4h copies match the same way. These three names are one object.

**Canonical name:** `RANGE_POSITION_4H`.

It means the fractional location of the decision close inside the trailing 4-hour high-low range, with the decision bar included. `dist_lower_4h` is that number. `dist_upper_4h` is one minus that number. Later text counts it once.

### Is the association a normalization identity?

No. `R_1h` depends on `close[i+12]`. `RANGE_POSITION_4H` does not. For a martingale, the future increment is independent of any function of prices up to `T`, including this ratio. A negative Spearman is not forced by dividing by the range.

Two construction channels stay open, and they are not lookahead:

1. `close[i]` is both the numerator of the position and the denominator of `R_H`. The feature and the target share `P0`.
2. Because the decision bar is inside the high-low window, "close near the extreme" is partly "the extreme was printed on a bar that is still inside the feature," often the last bar.

A future bar does not leak. The relation can still be a rewrite of the recent path. That is the confound in §6, not a bug in the clock of the data.

### Serializer note

`bool` was serialized as `0`/`1` in the first JSON write because `bool` is an `int`. Top-level flags were patched back to `false` without rescoring. The ledger hash is the hash above. Degenerate flags inside cells can still be `0`/`1`. The markdown states degeneracy in words. This does not move a Spearman.

## 3. What the market showed

Lead cell, one object, horizon 1h, N `175356`, ISO weeks in the anchor set `262`.

| Quantity | Value |
|---|---|
| Spearman | `-0.057773446228651215` |
| Same cell, outcome demeaned by UTC hour | `-0.05856563288220273` |
| Partial Spearman given `rv_4h` | `-0.057984258755084964` |
| Week-mean Spearman / SE | `-0.06805460359613863` / `0.0030986344742491615` |
| Week-block bootstrap Spearman, 1000 draws, seed `20261116` | `[-0.06379903806721994, -0.05173738086273271]` |
| Bottom-quintile P(UP) | `0.5626300932394286` |
| Cell baseline P(UP) | `0.5085312164967266` |
| ΔP versus that baseline | `+0.05409887674270197` |
| Bootstrap ΔP | `[0.04784072294247168, 0.059646968246885056]` |
| Bottom-quintile mean log return | `0.00014618759866201928` |
| Cell mean log return | `5.854599454186618e-05` |
| Mean difference | `8.76416041201531e-05` |
| Bootstrap mean difference | `[-5.430808699440813e-06, 0.0001745844131009732]` |
| Half split | `-0.05197429931505825` / `-0.06404413668590836` |

Years, all negative: 2020 `-0.06750` (N 35103), 2021 `-0.04039` (N 35040), 2022 `-0.07003`, 2023 `-0.06487`, 2024 `-0.05641` (N 35133). Leave-one-year-out stays between about `-0.0554` and `-0.0638`.

Quintile P(UP), low position to high position: `0.5626300932394286`, `0.5303527130677768`, `0.5085968463973083`, `0.48835219982321576`, `0.45272582116788324`. Bin counts `35071` four times and `35072` once.

Quintile mean log returns, same order: `0.00014619`, `-0.00003478`, `0.00003511`, `0.00006680`, `0.00007941`. Not monotone.

Quintile median log returns, same order: `+0.00055775`, `+0.00022739`, `+0.00005821`, `-0.00009243`, `-0.00038676`. Monotone.

The 4h copy of the same object has Spearman `-0.04500998857220667`, N `175344`, same sign in every year. The sign-probability contrast is still there. The mean-difference interval again includes both signs.

### Which interpretations are still alive

| Label | Status |
|---|---|
| A. Ordinary short-horizon mean reversion, i.e. a rewrite of recent signed displacement | Alive. The signed 4h return was not a control. |
| B. Location versus trailing extrema carries information beyond that signed return | Alive as the formula's content. Unresolved until A is partialled out. |
| C. The position effect is a surrogate for a recent boundary contact | Alive. Rejection and bars-since were not partialled on position. |
| D. Intraday clock | Weakened, not closed. Hour-demeaning the outcome does not shrink the lead Spearman. The distribution of the position by hour was not stored. |
| E. Pure mathematical identity from the normalization | Closed. Future increment is not a function of the ratio. |
| E. Shared `P0` and decision bar inside the window | Open as a construction channel inside A, not as lookahead. |

Do not name this mean reversion. The sign pattern is the pattern mean reversion would have. The scan did not separate it from recent signed return, from boundary contact, or from the shared-`P0` construction.

## 4. Duplicate family

`close_pos_4h`, `dist_lower_4h`, and `dist_upper_4h` are one discovered object, `RANGE_POSITION_4H`. The automatic top three of the scan are that object three times. They are not three confirmations. The mirror check "agrees" because it is comparing a series with its complement.

## 5. Catalog collision

No catalog file was recovered. The labels below are the collision candidates named for this review. Range position is not forced onto A1.

| Cursor empirical finding | Nearest named phenomenon | Same? | Difference | Priority consequence |
|---|---|---|---|---|
| `RANGE_POSITION_4H` (`close_pos_4h` = `dist_lower_4h`, `dist_upper_4h` = complement), 1h Spearman `-0.058`, graded P(UP) | None of A1, A5, B, F. Nearest *implemented* neighbor is `midpoint_slope_4h` | No | Position is where the close sits inside the trailing high-low. A1 center drift, as a name, is a moving center. The scanned center-drift series is the 2h-midpoint change, Spearman `-0.0395` at 1h and `-0.0426` at 4h, smaller and a different formula | `EMPIRICALLY_DISCOVERED_OUTSIDE_TOP_CATALOG`. Do not mark A1 supported |
| `last_rejection_lower_4h` / `last_rejection_upper_4h` | B-family boundary pressure; adjacent to F failed attempts | Partial overlap of topic, different formula | Rejection is the adverse excursion after the last close inside 0.15 of the 4h extreme, and it is forced to 0 when that touch is the decision bar. H02/B2-02 require a breach of a prior range that excludes the event bar | Raise only as an incremental question given `RANGE_POSITION_4H`. No separate naive replication |
| `bars_since_lower_4h` / `bars_since_upper_4h` | B-family dwell / time since contact | Partial overlap of topic | Time since the last in-band close. A recent touch places the close near that extreme, so the clock is entangled with position | Same incremental estimand. Not a second discovery |
| Session interaction (`frac_near_upper_4h` in UTC `[21,24)`, 1h Spearman `+0.034`, N `21921`) | Clock / session | A small conditional slice of boundary occupancy | One session, one base, 2020 near zero (`+0.011`), and the 4h copy flips sign in 2021 | Leave as a logged slice. Do not promote |
| `flow_beta_1h` at 8h, Spearman `+0.020`, ineligible | Flow | The representation that was scanned | Years stay positive and 2022/2023 are about `+0.009` / `+0.007`. Collision was predeclared cosmetic | Keep ineligible. No successor |
| Compression (`rv_ratio_60_240` peak `+0.006` at 8h; `range_ratio_*` and `compression_slope_1h` near 0) | A5 one-sided compression, and any C1 that is these ratios | The exact scanned formulas are near zero | The atlas did not try every compression definition. It did try the frozen ratios and the 1h slope | Lower those exact formulations. Do not close the whole family |
| Countertrend (`adverse_share_4h` peak `-0.012` at 8h; `last_against_share_4h` and `countertrend_last_frac_4h` near 0) | Countermove decay | The exact scanned formulas are near zero | `adverse_share_4h` matches `-efficiency_4h` up to numerical noise, so this cell is path efficiency, already a small series | Lower those exact formulations |
| `bybit_leader_signed` / `okx_leader_signed` near `-0.017` at 1h, quintiles degenerate | Venue leadership | The exact 15m sign-of-largest-move feature | Mostly `{-1,0,1}`. Adjacent to D9/MARKET-06 only as a topic. Different object: perp-perp 15m timing, not a dislocation level | Lower this exact feature. Do not close cross-venue questions that use a different object |

Where the data-driven search and the named conceptual list meet: only loosely, on boundary contact (rejection, bars-since) and, more weakly, on center drift (`midpoint_slope_4h`). They do not meet on compression, countermove, flow, or venue leadership. The strongest cell is the one the named list did not isolate: current location inside the trailing range.

## 6. Momentum confound

`RANGE_POSITION_4H` is not the 4h signed log return.

The signed return already sitting in the feature code is `net4[i] = log(close[i] / close[i-48])`, the sum of 48 five-minute log returns. The range window is bars `[i-47, i]`. A close at the high can follow a small net move if the path was already high. A large net move can finish in the middle of a wider range. The two series share the path. They are not the same function.

Nothing in the saved result partials position on `net4`. The `rv_4h` partial answers a different question. Until that partial exists, "range position" and "recent signed return / momentum" are not distinguished.

**Successor estimand, not run.** On a surface this scan did not use for high-low geometry:

> Partial Spearman of `RANGE_POSITION_4H` with `R_1h`, given `net4` and `rv_4h`.

`RANGE_POSITION_4H`, `net4`, and `rv_4h` keep the formulas above. No new threshold. No new bin as the admission statistic. A within-bin view of position inside predeclared quintiles of `net4` may be logged beside the partial. It is not a second searched endpoint.

## 7. Range width, RV, trendiness

The partial given `rv_4h` moves the lead Spearman from `-0.05777` to `-0.05798`. Inside this scan, 4h realized volatility does not account for the association.

That control is not sufficient for the scientific question.

| Nuisance | What the scan actually shows | Enough? |
|---|---|---|
| `rv_4h` | Partial unchanged. `rv_4h` itself versus `R_1h` is only `+0.0166` | Enough to say "it is not merely the RV level." Not enough to say the position effect is constant across RV |
| Range width `log_range_4h` | Its own Spearman versus `R_1h` is `+0.0152`. No partial of position on width was stored | Width is a weak directional series on its own. Interaction with position was not estimated |
| Efficiency / trendiness `efficiency_4h` | `+0.0053` at 1h. `adverse_share_4h` is its negative | Position is not the efficiency series. A high-efficiency trend still tends to finish near an extreme, so efficiency is a cousin of the momentum confound, not a substitute for `net4` |
| `midpoint_slope_4h` | `-0.0395` at 1h, `-0.0426` at 4h, all years the same sign | A real neighbor. It is drift of the range center, closer to signed displacement than to fractional location. It stays below position and was not used as a control |

Position can still be a marker of trending states. The RV partial does not close that. The frozen controls in §19 are `net4` and `rv_4h`, with hour demeaning as a sensitivity. Range width is reported beside them and is not a third knob to tune after the outcome.

## 8. Clock

Hour adjustment subtracts the cell-sample mean of `R` inside each UTC hour. It does not residualize the feature, and it does not measure whether low or high positions pile up at particular hours.

On the lead cell the adjusted Spearman is `-0.05857` against the raw `-0.05777`. The association gets slightly larger. The only cell the scan flagged as shrunk after the clock rule is `speed_ratio_up_down` at 8h, N `27`.

Stored clock marginals for the 1h target, all anchors, show UTC-hour P(UP) from `0.4855` at 01:00 to `0.5472` at 20:00, a span of about `6.2` percentage points. Kyiv-hour P(UP) spans about `5.6` points. That is the same order as the position quintile's `+5.4` points versus the cell baseline. A concentration of extreme positions inside high-drift hours could still contribute. That concentration is not in the JSON. The outcome-hour control that *was* run does not explain the lead cell. Clock stays a residual caveat, not the leading account.

## 9. How to read the percentages

Quintile edges are `np.quantile` of the feature on the full cell sample, cuts `0.2 / 0.4 / 0.6 / 0.8`, then `np.digitize(..., right=False)`. For the lead cell the edges are `0.2636`, `0.4408`, `0.6137`, `0.7794`. They are not past-only, not expanding, and not frozen before seeing 2020–2024. They are exploratory bins. Using them as deployable cutpoints would be in-sample. The continuous Spearman does not use them.

ΔP in the state block is `P(R>0 | locked quintile) - P(R>0)` on the same cell. The baseline is `0.5085`, not one half. The visual pair `56.26%` versus `45.27%` is the bottom bin versus the top bin, an `11.0` point gap (`delta_p` of the quintile table is `-0.1099` in the top-minus-bottom orientation). That gap is larger than the `+5.4` points versus the cell baseline. Both use the same in-sample edges.

`175356` is not `175356` independent bets. Anchors are every 15 minutes. The 1h label uses 12 bars. Adjacent anchors share 9 of those 12 future bars. A non-overlapping hourly slice is on the order of `N/4`, and those hours are still dependent. The dependence unit declared before the scan is the ISO week of `T`. There are `262` such weeks.

## 10. Dependence, as implemented

`bootstrap_cell` draws ISO weeks with replacement, concatenates every anchor inside the drawn weeks, and recomputes Spearman and the locked-side quintile contrast. The side is locked from the full-sample sign. Quintile edges are recomputed inside the draw. Draws: `1000`. Seed: `20261116`. Valid draws on the lead cell: `1000/1000`.

That interval is a within-cell interval for a cell chosen after seeing all `496` cells. It is not a selection-corrected interval.

`weekly_spearman` drops weeks with fewer than `30` anchors and reports the mean and SE of the remaining within-week Spearmans. The bootstrap keeps every week, including the small ones. The weekly SE `0.0031` is the SE of that week-mean, not a naive iid SE of the pooled Spearman, and not a correction for having ranked `496` cells. Outside the bootstrap, the pooled Spearman and the quintile percentages are descriptive. No second, anchor-level SE is published as if the anchors were independent.

Yearly same sign is a stability check on one selected series. The five years were visible when the cell was ranked. They are not five replications.

## 11. Why the mean interval is weaker than the sign interval

The lead-cell bootstrap puts the Spearman and the ΔP entirely on one side of zero. The mean-difference interval includes a small negative number and a small positive number. The point mean difference is about `0.88` bps of log return.

The shape says why. P(UP) and the median return move monotonically with position. The mean return does not. From the second bin upward the means are flat to slightly positive while P(UP) keeps falling. A minority of large moves dominates the mean. The state changes how often the next hour is positive, and it changes the center of the distribution in the median, more clearly than it changes the expected log return.

For a forecast engine this is directional information about small sign moves. It is not, on this scan, a demonstrated expected-return edge. The `56%` figure must not be read as `56%` of a tradable magnitude.

## 12. Shape

P(UP) steps, low to high: about `-3.2`, `-2.2`, `-2.0`, `-3.6` percentage points. The middle bins move. The extreme-bin gap is the largest step, and it is not the whole pattern.

The continuous Spearman is the same sign in both halves, in every year, and in every leave-one-year-out. Its size stays near `-0.04` to `-0.07`. That is a shallow rank association, stable in sign, small in magnitude.

No threshold is declared. The graded shape argues against a single extreme-only rule as the summary of this scan. A successor that searches a cut on this surface would be a new search.

## 13. Boundary variables

`last_rejection_lower_4h` at 4h: Spearman `-0.05077`, N `136018` (missing when the window never touches the band). Bootstrap Spearman `[-0.06260, -0.03917]`. All five years negative. Mean-difference interval includes both signs. The 1h copy is `-0.05065`. The upper-side mirror at 4h is `+0.04582`.

`bars_since_lower_4h` at 1h: Spearman `-0.04796`, N `136030`. Bootstrap Spearman `[-0.05594, -0.03966]`. All five years negative. Here the mean-difference interval stays positive. That does not separate it from position.

Construction tie: a touch is a close inside `0.15` of the window extreme. `bars_since` is zero when the decision close is in that band, which is exactly when `RANGE_POSITION_4H` is near 0 or near 1. Rejection is forced to 0 when the last touch is the decision bar, the same states. A recent lower touch also leaves the close nearer the low on any path that has not travelled far. These series are built to agree with position.

**Second successor estimand, not run, and only if the first survives:**

> Partial Spearman of `last_rejection_lower_4h` with `R_1h` given `RANGE_POSITION_4H`, and the same partial for `bars_since_lower_4h`.

Mirrors are reported and not counted again. If the partials shrink to noise, the boundary cells are proxies and do not get their own replication.

## 14. Collision with H02, B2-02, and the level engine

H02 (`H02_KILL`) asks whether a bar that opens and closes inside a prior range, after wicking through one side, is followed by a move back toward that range. The prior range is bars strictly before the event bar, lookbacks 60/120/240 minutes, overshoot in `{0, 0.05, 0.10}`, 30-minute refractory, horizons 15–240 minutes. The event bar is not part of the range. The population is a breach event. The endpoint is a reversion-signed return. Development did not meet the promotion contract. The primary close-return was about 1 bp and the structural control failed.

B2-02 (`B2_02_CLOSED_NO_PROMOTION`) reuses that prior-range geometry and scores the path after a single-edge breach. The breach bar need not close back inside. No close-location rule defines the population. The endpoint is continuation in the breach direction. Promotion gates failed.

The level engine was not used. `LEVEL_ENGINE_USED` is false.

`RANGE_POSITION_4H` is the location of every 15-minute close inside a trailing 4-hour range that includes the decision bar, scored against the raw sign of `R_1h`, with no breach, no refractory, and no reversion-signed endpoint.

Classification: **adjacent, not already tested, not a cosmetic rescue of H02.** The shared words are "range" and "boundary." The formulas differ in the window (includes T versus excludes the event bar), the population (every anchor versus a wick-breach event), and the endpoint (raw future sign versus reversion after a breach). H02's kill does not answer this cell. This cell does not reopen H02.

The scan's own collision tag `NEW_LOCAL_GEOMETRY` on `close_pos_4h` matches that reading. The tag `ADJACENT_H02_B202_DIFFERENT_FORMULATION` on the distance and rejection rows is right for rejection. It is misleading for `dist_lower_4h` / `dist_upper_4h`, which are the position identity, not an H02 variant.

## 15. Multiplicity

`496` cells = series × `{1h, 4h, 8h, 24h}` × `{raw, hour-adjusted}`. Ranking used raw primary horizons and `eligible` only. The lead cell is the winner of that search.

Among raw 1h/4h/8h cells with N greater than `1000`, 15 have absolute Spearman at least `0.04`. Their ids collapse to `close_pos_4h`, `dist_lower_4h`, `dist_upper_4h`, the two rejection series, the two bars-since series, and `midpoint_slope_4h`. The N `27` speed-ratio cells are larger in absolute Spearman and have score 0. They are not a competing family.

So the winner is unusual relative to compression, flow, and venue timing, and ordinary relative to its own geometric copies. Coherence inside one family is evidence that the search found a repeated formula. It is not evidence that the formula survived an independent test.

The within-cell bootstrap, the five-year sign, and the monotone quintiles are diagnostics of the selected cell. They are not confirmation. No post-selection interval was frozen, and none is computed here.

## 16. Negative findings and priority

These exact representations came out near zero and lose priority:

- `range_ratio_30_240`, `range_ratio_60_240`, `range_ratio_120_240`, `rv_ratio_60_240`, `compression_slope_1h`
- `adverse_share_4h`, `last_against_share_4h`, `countertrend_last_frac_4h`
- `bybit_leader_signed`, `okx_leader_signed`, and the 15-minute cross-venue dispersion that stayed under about `0.013`
- `flow_beta_1h` and the other flow series, which stay ineligible

The families those names sit in are not closed. A different compression definition, a different flow object, or a different cross-venue object was not tested. H02 and B2-02 verdicts are unchanged.

### Revised research priority (recommendation of this review)

The catalog file is absent, so this list is not an edit of that file. It is the order implied by the scan plus the open confound.

1. `RANGE_POSITION_4H` versus `R_1h`, partial on `net4` and `rv_4h`, on Bybit high-low geometry. Not started.
2. Only if (1) keeps the sign: `last_rejection_*_4h` and `bars_since_*_4h` partial on `RANGE_POSITION_4H`.
3. Only if (1) keeps the sign: the same conditional estimand on BitMEX.
4. `midpoint_slope_4h` stays a nuisance neighbor of signed drift, not a separate lead, unless (1) shows that position survives `net4`.
5. Exact compression ratios above: lowered.
6. Exact countertrend shares above: lowered.
7. Exact 15-minute leader sign: lowered.
8. Flow beta: unchanged, ineligible, no successor.
9. Session slices of near-boundary occupancy: logged only.
10. H02 and B2-02: closed verdicts, not reopened. A1 is not declared supported.

## 17. Successor hierarchy

The scan's automatic successor says: replicate `close_pos_4h`, `dist_lower_4h`, and `dist_upper_4h` on Bybit. That spends a fresh high-low surface three times on one unconditional question, and it leaves the momentum confound for later. If the unconditional copy "works," the result is still compatible with recent signed return.

**First successor.** Bybit linear BTCUSDT 5-minute bars, decision times in the same pre-2025 span, same 15-minute anchor rule, same `RANGE_POSITION_4H`, same `R_1h`. Bybit closes were already used for 15-minute lead signs. Bybit highs and lows were not used for this geometry. That is the independent surface for this object.

**Primary estimand.** Partial Spearman of `RANGE_POSITION_4H` with `R_1h` given `net4` and `rv_4h`.

**Frozen nuisance controls.**

- `net4 = log(close[T] / close[T-4h])`, the 48-return sum already defined in the atlas feature code
- `rv_4h`, the same square root of summed squared 5-minute log returns
- UTC-hour demean of `R_1h` as a predeclared sensitivity, using the same `hour_adjust` construction
- `log_range_4h` reported beside the partial, not tuned
- no new threshold, no searched quintile cut, no fee, no entry

**Reading, declared before the outcome.** The discovery sign is negative for position versus the next return. Survival means the partial association stays negative and its week-block interval stays below zero. An interval that includes zero, or a sign flip, stops the line. This review does not run that test.

**Second successor, only if the first survives.** The boundary partial in §13, on the same Bybit specification or on a surface still unread for that partial. If the first fails, the boundary cells are not promoted as a rescue.

**BitMEX.** Useful after that survival, as an older tape and a third venue. It does not answer the confound more cleanly than Bybit, so it is not first.

Unconditional Bybit replication of the raw Spearman is dominated by the conditional estimand. It is not the first test.

## 18. Product target

The forecast question is whether price reaches a stated level by a stated time. `RANGE_POSITION_4H` was scored against `sign(R_1h)`.

Conceptual route, not an integration:

- As a directional prior, it is a small, sign-level tilt of the next hour. The mean contrast is unresolved.
- As a feature in a target-hit model, it could enter only after the conditional successor survives, and only as a state known at `T`. A hit probability is not the same functional as `P(R_1h > 0)`.
- As a state variable, "close in the bottom fifth of the trailing 4h range" is intelligible. The fifths in this scan are in-sample.

`PRODUCT_INTEGRATION_CANDIDATE` stays no. No bot line. No fee, no entry, no stop, no PnL. Decision value is downstream of a replicated conditional association.

## 19. Verdict

`INTERESTING_BUT_TRIVIAL_CONFOUND_UNRESOLVED`

The implementation does not leak future closes. The three leading names are one geometric object, `RANGE_POSITION_4H`, and that object was not the H02 event. The sign-probability gradient is graded and the hour and RV checks that were actually stored do not remove it. The association is still compatible with a rewrite of recent signed 4h return, with a boundary-contact proxy, and with selection across 496 cells. The mean-return interval includes zero. None of that is confirmation, and none of it is a reason to call the cell an algebraic illusion.
