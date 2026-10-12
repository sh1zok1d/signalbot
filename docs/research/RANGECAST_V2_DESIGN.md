# RANGECAST_V2 — design note (committed before any outcome of this unit)

`MODE = DISCOVERY` · track `PRODUCT_EVIDENCE` · claim ceiling `DISCOVERY_ONLY` · `PRODUCT_INTEGRATION_CANDIDATE = owner decision after the result`

**Owner go:** 2026-10-12, «передаю тебе основной прогнозный трек Pulsy»: improve the probabilities of the existing range model (`beta/rangecast.py`), BTC first, 4h first, an arbitrary target above or below the price. No production change and no change of a user-facing probability without a separate owner go.

## 1. Question and estimand

For an anchor at the close of a 5m bar and a horizon H, the chance that Binance USD-M BTCUSDT reaches a price `d` % above (or below) the anchor close within H. Realized: the maximum high (minimum low) of the next H/5m bars is at least `d` % away. This is the quantity behind every «шанс дойти» surface (`/check`, `/levels`, `/risk`, level lines).

Estimand of the comparison: the out-of-sample difference in a proper score between a candidate's touch probabilities and those of the production model V1, on the same anchors, the same distances and the same years.

## 2. Data surface and exposure

- **Source:** Binance Vision USD-M BTCUSDT 5m klines from 2020-01-01 to 2026-10-11, planned by the product planner `beta.history_data.plan_objects`, checksum-verified (`scripts/research/rangecast_v2/data.py`). The 11 objects that overlap the E1-RUN-001 final holdout are refused before any request; there is no bar in `[2026-08-16, 2026-08-26)` and no anchor whose window touches it.
- **Exposure:** this is the product statistics surface (PRODUCT_DECISION_V2 §4). The production model is fitted nightly on all of it, and its held-out check reads the last 365 days every night. Nothing here is an independent confirmation.
- **Prior reads that informed the menu:** the 2026-10-12 audit of V1 on the repository's 2022–2024 archives (R² of the log range by feature set, calibration by scale quintile, one descriptive up/down split after a 24h fall or rise). The 2025–2026 outcomes were not read by this unit's author.

## 3. Task, anchors and folds

- **Horizons:** primary 4h (48 bars). Secondary, reported and used as guardrails: 1h (12 bars), 24h (288 bars).
- **Anchors:** closes on the full hour (stride 12, as production). A row needs a complete forward window and finite features of the largest menu, so every model is scored on the same rows. Rows in a CPI / FOMC event zone (`rangecast.in_event_zone`) are fitted but not scored, as the product shows nothing there.
- **Rolling origin by year:** for a test year Y ∈ {2021, 2022, 2023, 2024}, fit on every anchor whose forward window closes before January 1 of Y (expanding from 2020); score the anchors of Y.
- **Time-disjoint exposed read, once:** the selected candidate and V1, fitted on 2020–2024, scored on 2025-01-01 … 2026-10-11 without refit. Reported; never used to reselect.

## 4. Scores

- **Distances:** 16 log-spaced points per horizon, both sides (32 binary events per anchor): 1h 0.1–2.5 %, 4h 0.2–5 %, 24h 0.5–12.5 %. A log grid weights every relative target size equally, which is the closest fixed stand-in for an arbitrary user target.
- **Probabilities** are clipped to [0.001, 0.999] for every model (production prints «<1 %» and «>99 %»).
- **Primary:** mean log loss per anchor over its 32 events, 4h, pooled over the four test years.
- **Secondary:** Brier on the same events; log loss on the claim-journal grid (0.25, 0.5, 1, 2, 3, 5 %); per distance; per year; by trailing-30-day volatility tercile; weekend and weekday; reliability in the journal's probability bins; pooled calibration intercept and slope (logistic recalibration over events); the probability integral transform (PIT) of each side's realized excursion; «ни один» log loss on the journal's 16 pairs where a model defines it.
- **Uncertainty:** ISO-week cluster bootstrap of the per-anchor score difference, B = 2000, seed 20261012, 95 % percentile interval.

## 5. Models (the whole menu; count 8)

All features use bars at or before the anchor only. `range_k` is the high–low range of the last k bars in % of the close; logs are floored as in V1.

| Id | What | Why it is in the menu |
|---|---|---|
| B_CLIM | Training frequency of each side reaching each distance; no state | floor |
| B_R24 | V1 structure with the 24h range only | the common "trailing volatility" baseline (Impulse V1's B1) |
| V1 | `beta.rangecast._fit_one` + `touch_probability`, unchanged | production |
| L1 | V1 structure (OLS on log range, one pooled standardized excursion distribution) with a richer scale: log ranges of 15m, 1h, 4h, 24h, 7d, 30d; log realized volatility of 5m returns over 1h, 4h, 24h; log base-volume activity of the last 1h and 24h against the 30-day mean; recent move size \|ret 1h\| and \|ret 4h\| over the 24h range; a day-of-week × hour season (168 cells, hour-only fallback below 30 rows); weekend share; CPI; FOMC | better scale forecast; Impulse V1's informative states (large recent moves, activity, range expansion, clock) as scale inputs |
| L2 | Per-side location–scale on log(side % + 0.02): one symmetric mean model (L1 features) for both sides, a heteroskedastic scale σ(x) from an OLS of log \|residual\| on the same features, one pooled empirical distribution of standardized residuals | the shape of the excursion distribution conditional on the state |
| L3 | L2 with a separate mean and σ for the up and down side, and signed inputs in the means: return over 1h, 4h, 24h over the 24h range; close position in the 4h, 24h, 7d range | up / down asymmetry |
| W | The selected linear level with recency weights 0.5^(age / 365 days) in every regression and empirical quantile | regime adaptation |
| G | Diagnostic only: L3 with the two means fitted by LightGBM (fixed: 31 leaves, rate 0.05, 400 trees, min 200 rows per leaf, row subsample 0.8, seed 1; no tuning) | is there nonlinear information a linear model leaves out |

«Ни один» for L2 / L3: the joint table of the two standardized residuals (the V1 `_joint_table` construction on residuals), kept coherent with the single chances as in V1.

## 6. Selection rule (frozen)

1. Reference V1. Steps L1, L2, L3 are judged in order, each against the last accepted model. A step is accepted when its pooled 4h primary improvement has a 95 % interval entirely below 0 **and** a negative point difference in at least 3 of the 4 test years. A rejected step is skipped; the next one is judged against the last accepted model.
2. W is accepted on top of the selected level by the same rule.
3. G is never a production candidate here. If it beats the selected model by more than 1 % of V1's primary score with an interval below 0, that is recorded as untapped nonlinear information (a successor), not acted on.
4. **Guardrails** for the selected model, each a blocker for a production recommendation: pooled 4h calibration slope within [0.9, 1.1]; at 1h and 24h no worse than V1 with an interval above 0; at 4h, the far-distance group (d ≥ 2 %) and the near group (d ≤ 0.5 %) each no worse than V1 with an interval above 0.

## 7. What would change our mind

- No step is accepted: V1 stays, and the result says where the losses are.
- An accepted step whose gain sits in one year, or that disappears on the 2025–2026 read: no production recommendation.
- G well ahead of every linear model: the linear architecture is limiting, and a nonlinear successor is designed separately.

## 8. Limitations known before the outcome

One venue and one symbol. All years are exposed. The folds refit yearly while production refits nightly. Hourly anchors overlap within a horizon, so the clusters (ISO weeks) carry the information. The menu was informed by an earlier read of 2022–2024. A historical improvement is not a live calibration; the path to production is a shadow challenger in the claim journal.
