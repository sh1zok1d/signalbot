# PRE_IMPULSE_STATE_ATLAS_V1

Historical directional discovery. Claim ceiling `DISCOVERY_ONLY`. A shortlisted state is a `DISCOVERY_CANDIDATE`. It is not confirmed, not validated, not a current probability, and not an edge. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

We do not demand a preselected effect magnitude from the market. We inspect a bounded, fully logged historical state space, characterize what systematically precedes directional movement, and then freeze separate successor hypotheses for independent testing. Effect magnitude and useful structure are outputs of discovery, not admission thresholds.

Read `2026-10-09T13:38:33Z`. Design SHA256 `01b7eafb7d2231388503a0c523e1443eceba7666b774ec8d0c1dc5fb055c3a5b`. Evaluator digest `b6e8d83f2d6f680b219edcfa3dab5ce96cfe0b3a4230b04e5c2952966acdb733`. Ledger `docs/research/PRE_IMPULSE_STATE_ATLAS_V1_LEDGER.json` SHA256 `29fbc898fd7ddea73407be5a417be40509d981a9f247c977b08c160ce3773a1b`. Bootstrap seed `20261116`, `B = 1000`. A second scan returns `REFUSING_RERUN`.

## Sample

- Surface `CORE_BTC_BINANCE_V0`. Decision times from `2020-01-01T08:15:00Z` through `2024-12-31T23:45:00Z`. No bar open at or after `2025-01-01T00:00:00Z`.
- Anchors are 15-minute closes. Anchor N `175359`. ISO weeks `262`.
- Finite targets: 1h `175356`, 4h `175344`, 8h `175328`, 24h `175264`. The 24h horizon is logged and not ranked.
- Series `62` (50 base features plus 12 predeclared session interactions). Cells `496` (each series, each horizon, raw and UTC-hour-adjusted).
- Bybit closes SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`. OKX closes SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`. Exact open-time match. Missing prints stay missing.
- Open interest was not read. The level engine was not used. Funding was not used. Spot versus perpetual basis was not used. Product code was not changed.

Predeclared outcome cuts, before the feature loop. 1h: 10th percentile `-0.005975163152572849`, 90th `0.006181122603754451`. 4h: `-0.012456336364953479`, `0.013334843884966214`. 8h: `-0.018040788529564873`, `0.01985074021450342`.

## Market states discovered

The ranking is dominated by one geometric fact counted more than once. On a 4-hour window with positive range, `(close - low) / (high - low)` is both `close_pos_4h` and `dist_lower_4h`. `(high - close) / (high - low)` is `dist_upper_4h`, the complement. Their Spearmans match to numerical noise, with opposite sign for the complement. The mirror check agrees.

That state says: when the close sits in the lower part of the trailing 4-hour range, the next 1-hour return is up more often than the baseline. When it sits in the upper part, the next 1-hour return is up less often. The same sign appears at 4 hours, smaller. Every calendar year has the same sign. Leave-one-year-out keeps the sign. The UTC-hour adjustment does not remove it. The partial Spearman given 4-hour realized volatility does not remove it.

This is a discovery candidate for a later frozen test. It is not a claim that the level will hold, and it is not a trade.

Two further boundary descriptions are not the same ratio. A small pullback after the latest lower-band print (`last_rejection_lower_4h` low) and a recent lower-band print (`bars_since_lower_4h` low) also line up with a higher next-hour up rate. Their upper-side mirrors have the opposite Spearman sign.

## UP-associated structures

High `dist_upper_4h` means the close is far below the 4-hour high, which is the same event as a low close-location. At 1h, Spearman `0.057773446202884805`, N `175356`, 262 weeks. Top quintile P(UP) `0.5626425638686131` against baseline `0.5085312164967266`, delta P `0.0541113473718865`. Week-block interval for the Spearman `[0.05173738085805187, 0.06379903790435117]`. The interval for delta P is about `[0.0478, 0.0596]`. The interval for the mean-return gap includes values on both sides of zero. Years `2020` through `2024` are all positive: `0.0675`, `0.0404`, `0.0700`, `0.0649`, `0.0564`.

`last_rejection_upper_4h` at 4h, Spearman `0.04582108365643946`, N `145721`. A larger pullback after the latest upper-band print lines up with a higher later up rate. Top quintile P(UP) `0.5559444158517756` against baseline `0.5178251590367895`, delta P `0.03811925681498607`. All five years are positive. The lower-side mirror is negative, so the mirror agrees.

## DOWN-associated structures

`close_pos_4h` at 1h, Spearman `-0.057773446228651215`. Bottom quintile P(UP) `0.5626300932394286` against baseline `0.5085312164967266`, delta P `0.05409887674270197`. Mean return in that quintile `0.00014618759866201928` against baseline mean `5.854599454186618e-05`. Weekly mean Spearman `-0.06805460359613863`, weekly SE `0.0030986344742491615`. Partial given `rv_4h` `-0.057984258755084964`. First half `-0.05197429931505825`, second half `-0.06404413668590836`.

Quintile P(UP) from the bottom bin to the top bin: `0.5626300932394286`, `0.5303527130677768`, `0.5085968463973083`, `0.48835219982321576`, `0.45272582116788324`. The up-rate falls as the close sits higher in the range. The bin means of the signed return are not monotone. The medians move from positive in the bottom bin to negative in the top bin.

`dist_lower_4h` at 1h is the same series and the same numbers.

## Symmetric and null structures

Family peaks of absolute raw Spearman on primary horizons:

- Speed `0.17188215739868304` at `speed_ratio_up_down` / 1h, but N is `27`. The score is `0` because no year reaches N `200`. Both a 4-hour-volatility unit up and one down inside the same 48 bars almost never both complete. This is not a shortlist cell.
- Boundary and morphology `0.057773446228651215`, the close-location state above.
- Geometry `0.04258340406664516` at `midpoint_slope_4h` / 4h, score equal to the absolute Spearman, all five years negative.
- Acceptance `0.03555722593929278` at `extension_up` / 1h.
- Clock `0.03697812084300025` at `frac_near_lower_4h__late` / 8h.
- Cross-venue `0.017098754584277478` at `bybit_leader_signed` / 1h.
- Countertrend `0.011749914497548065` at `adverse_share_4h` / 8h.
- Compression `0.00595195784292189` at `rv_ratio_60_240` / 8h.

Small absolute associations, all logged, include `last_against_share_4h` at 4h `0.00014433642072972852`, `countertrend_last_frac_4h` at 4h `0.00021523710982616486`, `compression_slope_1h` at 8h `0.00022699809484760875`, and `range_ratio_120_240` at 1h `0.0002748066786844017`. Compression ratios and the countertrend-decay summaries do not separate later direction on this tape.

`adverse_share_4h` matches `-efficiency_4h` up to numerical noise. That pair is one path-efficiency fact, and it is small.

## Clock-conditioned structures

The hour main effect is a descriptive map in the result file and is not ranked.

The highest clock score is `frac_near_upper_4h__late` at 1h. Late means UTC hours `[21, 24)`. Spearman `0.033914670952973174`, N `21921`, score `0.033914670952973174`. Top quintile P(UP) `0.551964891282665` against baseline `0.5139364080105835`, delta P `0.038028483272081526`. Years are all positive, and `2020` is the small one (`0.011199317447841592`). Weekly SE `0.010409394658458346` is large next to the point. Europe/Kyiv summer offset Spearman `0.02638641682964085` (N `12852`); standard-time Spearman `0.04296512262849513` (N `9069`). The sign does not flip with daylight saving. This is not a hardcoded 06:00 Kyiv effect.

The same state at 4h changes sign in `2021` (`-0.029852913562357447`) while the other years stay positive. That horizon is less stable.

## Boundary and acceptance structures

Boundary pressure beyond the close-location identity:

- `last_rejection_lower_4h` at 4h, Spearman `-0.05076682453380103`, N `136018`. Bottom quintile P(UP) `0.55716071166005` against `0.509947212868885`, delta P `0.04721349879116499`. All five years negative. Mirror agrees. The Spearman interval is about `[-0.0626, -0.0392]`. The mean-return interval includes both signs.
- `bars_since_lower_4h` at 1h, Spearman `-0.047963537765399133`, N `136030`. Bottom quintile P(UP) `0.5640320903283316` against `0.5066676468426082`, delta P `0.05736444348572334`. All five years negative. Mirror agrees. A recent lower-band print, not a stale one, is the up-associated side.

Acceptance: `extension_up` at 1h, Spearman `-0.03555722593929278`, score `0.03555722593929278`, N `175356`. A recent 4-hour high that extends farther beyond the prior 4-hour high lines up with a lower later up rate. This is adjacent to H02 and B2-02 and is not their event.

## Flow and OI interaction structures

Open interest was not opened. MARKET-01 and MARKET-02 already closed that family here.

Flow was logged and kept out of the shortlist (`COSMETIC_NEIGHBORHOOD_H05_B205`). The strongest ineligible cell is `flow_beta_1h` at 8h, Spearman `0.020214202146930194`, N `175282`, score `0.020214202146930194`. Top quintile P(UP) `0.5292238354679522` against baseline `0.5161340012094796`, delta P `0.013089834258472544`. Every year is positive. `2022` and `2023` are near zero (`0.0091`, `0.0066`). No successor.

## Cross-venue timing structures

The strongest cell is `bybit_leader_signed` at 1h, Spearman `-0.017098754584277478`, N `158745`, score `0.017098754584277478`. All five years are negative. The quintile table is degenerate: the series is mostly `{-1, 0, 1}` and every quintile edge is `0`, so there is no P(UP|state) from quintiles. `okx_leader_signed` at 1h is `-0.016834817576882904`. Dispersion `xdisp_std_15m` stays under `0.013` in absolute Spearman. These are small next to the close-location state. They do not repeat MARKET-06's dislocation level.

## Top successor candidates

The automatic top three names are `close_pos_4h`, `dist_lower_4h`, and `dist_upper_4h` at 1h. They are one state. The independent successor is that state, once.

1. Close location in the trailing 4-hour range, horizon 1h. Same formula on Bybit linear BTCUSDT 5-minute bars over the same pre-2025 span. This scan used Bybit only for 15-minute lead features, not for this geometry. Do not score the complement as a second hypothesis.
2. `last_rejection_lower_4h` at 4h, and its upper mirror in the same frozen test. Same Bybit tape. Not an H02 event replay.
3. `bars_since_lower_4h` at 1h, and its upper mirror in the same frozen test. Same Bybit tape.

Do not execute these here.

## Top 10 directional structures

The table is the score order. Rows 1–3 and 8–10 are the close-location identity and its 4-hour copy.

| rank | id | horizon | N | Spearman | P(UP\|state) | baseline | delta P | years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | close_pos_4h | 1h | 175356 | -0.057773446228651215 | 0.5626300932394286 | 0.5085312164967266 | 0.05409887674270197 | all negative |
| 2 | dist_lower_4h | 1h | 175356 | -0.057773446228651215 | same row as 1 | same | same | same |
| 3 | dist_upper_4h | 1h | 175356 | 0.057773446202884805 | 0.5626425638686131 | 0.5085312164967266 | 0.0541113473718865 | all positive |
| 4 | last_rejection_lower_4h | 4h | 136018 | -0.05076682453380103 | 0.55716071166005 | 0.509947212868885 | 0.04721349879116499 | all negative |
| 5 | last_rejection_lower_4h | 1h | 136030 | -0.050650114071307824 | 0.5618981107108726 | 0.5066676468426082 | 0.05523046386826436 | all negative |
| 6 | bars_since_lower_4h | 1h | 136030 | -0.047963537765399133 | 0.5640320903283316 | 0.5066676468426082 | 0.05736444348572334 | all negative |
| 7 | last_rejection_upper_4h | 4h | 145721 | 0.04582108365643946 | 0.5559444158517756 | 0.5178251590367895 | 0.03811925681498607 | all positive |
| 8 | dist_upper_4h | 4h | 175344 | 0.045009988609967036 | 0.5578431092988109 | 0.514240578519938 | 0.04360253077887288 | all positive |
| 9 | close_pos_4h | 4h | 175344 | -0.04500998857220667 | same geometry as 8 | same | same | all negative |
| 10 | dist_lower_4h | 4h | 175344 | -0.04500998857220667 | same geometry as 8 | same | same | all negative |

Full quintile rows, yearly values, half splits, and leave-one-year-out values are in `PRE_IMPULSE_STATE_ATLAS_V1.json`. The figure `PRE_IMPULSE_STATE_ATLAS_V1.png` shows every shortlisted quintile curve, including the duplicates.

Collision: close location is `NEW_LOCAL_GEOMETRY`. The distance and rejection cells are `ADJACENT_H02_B202_DIFFERENT_FORMULATION`. Mirrors agree where a mirror exists. `close_pos_4h` has no mirror pair in the registry; `dist_lower_4h` is that mirror in substance.

## Patterns that shrank after a control

The 90th percentile of absolute primary Spearman is `0.039632325545051944`. One cell crossed that line and then fell by more than half after the UTC-hour adjustment: `speed_ratio_up_down` at 8h, raw `-0.08304075810380425`, hour-adjusted `-0.02878591265810527`. Its N is `27`. It is a censored ratio, not a pattern that looked real and then failed a control.

None of the top 10 lost its sign or half its magnitude in the partial Spearman given `rv_4h`.

The mean signed-return gap is a weaker description than P(UP). For the leading close-location cell, the week-block interval of the mean gap includes zero, while the interval of delta P does not. Bin means of the signed return are not monotone. Medians and up-rates are.

## What is still unknown

Whether the close-location state, the rejection pullback, or the time since the band print survives on Bybit with the same formula. Whether a prospective window will keep the sign. Whether the up-rate gap is large enough to matter once costs and a decision rule exist. This pass does not answer those. It does not turn the historical up-rate into a current probability.

## Stop

Do not execute a successor from this unit. Each successor needs its own frozen design and an owner go.
