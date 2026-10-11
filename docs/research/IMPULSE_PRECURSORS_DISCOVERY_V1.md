# IMPULSE_PRECURSORS_DISCOVERY_V1

`MODE = DISCOVERY | outcome_read = true | claim ceiling DISCOVERY_ONLY`
`EVIDENCE_CLASS = DISCOVERY / EXPOSED_HISTORY`
`ROUTE = PRECURSOR_DISCOVERY_PROMISING`
`PRODUCT_INTEGRATION_CANDIDATE = NO`

One exploratory pass on `CORE_BTC_BINANCE_V0`, snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`, decisions from 2020-01-01 through 2025-01-01 exclusive. Design SHA256 `ac1f4a8e046078fcab62fb3b97dfc095de6b90c42787ad96229cb481fec44a79`, pinned before any price read. A second `execute()` returns `REFUSING_RERUN`.

This is not H03. H03 scored the path after an impulse. This unit scores whether a barrier is hit after `T`. It is not the pre-impulse signed-return atlas, and it does not use the range-position forecast prototype as confirmation.

The first journal claim stopped before prices: the snapshot reader ignored the indented `materialization_identity.snapshot_id`. That preflight is `docs/research/impulse_precursors_discovery_v1_execution/PREFLIGHT_REJECTED.json`. No bar was opened. The reader was corrected to require both manifest lines to equal the pin, and the single price-backed pass then ran.

## Question

Is there a state known at `T` that forecasts `P(impulse during (T, T+4h])` better than the ordinary frequency and the volatility-scaled barrier geometry?

`Y = 1` when the next 48 completed 5-minute bars uniquely touch `close(T) * exp(±1.5 * sigma_4h)` first on one side. `sigma_4h` is the root-mean-square of the previous 288 completed 5-minute log returns, times `sqrt(48)`. `AMBIGUOUS` rows are excluded. `K = 1.0` and `K = 2.0` are counts only.

## Impulse atlas

| Object | Value |
|---|---|
| Clock rows | 175280 |
| Dropped for a gap or a malformed bar | 0 |
| Ambiguous at `K = 1.5` | 15 |
| Dropped for a non-finite feature | 4 |
| Kept decision rows | 175261 |
| Kept impulse rate | 0.2618323528908314 |
| Geometric `P(impulse)` | 0.26721521438310525 |
| Scored rows | 162110 |
| Scored impulse rate | 0.263950404046635 |
| Folds | 242 |

Distinct episodes, walking forward and ignoring a later impulse row until the earlier touch: `5846`. Up `2812`. Down `3034`. Raw positive decision rows `45889`, of which `40043` (`0.8726056353374447`) sit inside an earlier episode. Mean duration `163.64095107765993` minutes. Deciles of duration: 40, 195, and 240 minutes.

Episodes by year: 2020 `1105`, 2021 `1187`, 2022 `1184`, 2023 `1140`, 2024 `1230`.

Regime of `rv_ratio_4h_24h` at the episode start: `< 0.7` is `695`, `0.7–1` is `1923`, `1–1.4` is `2056`, `>= 1.4` is `1172`. Most episodes begin when the last 4 hours are not compressed against the last 24 hours.

Diagnostic counts, not fit and not in the route: `K = 1.0` kept `175229`, impulse rate `0.4908377038047355`, ambiguous `47`. `K = 2.0` kept `175257`, impulse rate `0.15138910286037077`, ambiguous `19`.

## Precursor map

On scored rows, the mean signed return before an impulse is close to the mean before a quiet row, because both tails raise the later hit rate and cancel:

| Feature | Mean when Y=1 | Mean when Y=0 |
|---|---|---|
| `ret_15m_z` | -0.0016668454296641304 | 0.002381529341578474 |
| `ret_1h_z` | -0.0035360444616920625 | 0.008783639675431087 |
| `ret_4h_z` | 0.0032777872272537994 | 0.03168442679176794 |
| `accel` | -0.0007828343142411155 | 0.00018561942272070204 |
| `range_pos_4h` | 0.5137900438859792 | 0.5230050091018855 |
| `rv_ratio_15m_1h` | 0.9419188667100444 | 0.9173877865450433 |
| `rv_ratio_1h_4h` | 1.005200873120604 | 0.9366931899793998 |
| `rv_ratio_4h_24h` | 1.0290593009821865 | 0.9185308936540736 |
| `range_vs_sigma_4h` | 1.7153816683756304 | 1.4853955295209134 |
| `vol_ratio_15m` | 1.3375461184293458 | 0.9204640994816609 |
| `vol_ratio_1h` | 1.2655388292611744 | 0.9355173240893676 |
| `vol_ratio_4h` | 1.1512283212379748 | 0.95996284740447 |

The averages hide the tails. A large move already in progress, a wide range, and elevated quote volume precede hits. A compressed range precedes fewer hits. Location inside the previous 4-hour range does not.

## Ranked evidence

Seventy state cells were stored. Fifty-six week-block intervals exclude zero. Thirteen cover zero. One joint, `active_squeeze`, has N `181` and is not scored. Sixty-five cells have a positive frozen score. That count is the search record, not sixty-five discoveries. The route is the single candidate-versus-B1 comparison. Cell intervals resample ISO weeks, `B = 2000`, seed `20261122` plus a salt of the cell name. Comparable baseline is the mean B1 probability on the same rows. The unconditional scored rate is `0.263950404046635`.

The named successor, because the route is `PROMISING` and this score is the largest, is `ret_1h_z|lt_-1`. It is not a started unit.

| Cell | N | Rate | B1 on the same rows | Delta | Ratio | Interval | Score |
|---|---|---|---|---|---|---|---|
| `ret_1h_z\|lt_-1` | 4132 | 0.44869312681510165 | 0.26792803353510314 | +0.1807650932799985 | 1.6746777890127544 | [0.15744456307435953, 0.2038415468828372] | 0.1807650932799985 |
| `ret_1h_z\|ge_1` | 4142 | 0.42370835345243846 | 0.27268331527589595 | +0.1510250381765425 | 1.5538477410095228 | [0.12646657872316977, 0.17549487945931183] | 0.1510250381765425 |
| `dow\|5` (Saturday) | 23136 | 0.1443637621023513 | 0.27894861379215913 | -0.13458485168980783 | 0.5175281573900016 | [-0.1532657354719592, -0.11696783217062447] | 0.13458485168980783 |
| `joint\|already_wide` | 4561 | 0.39245779434334577 | 0.27206018385603276 | +0.12039761048731301 | 1.4425403555230423 | [0.10294655162974542, 0.13865070623844847] | 0.12039761048731301 |
| `vol_ratio_15m\|ge_1.4` | 29942 | 0.392993120032062 | 0.27267977999363374 | +0.12031334003842825 | 1.4412257485363866 | [0.10828706235644839, 0.1328505291367213] | 0.12031334003842825 |

`ret_1h_z|lt_-1` year deltas, all N at least 200 and all positive: 2020 `0.2335` (N 467), 2021 `0.2036` (N 888), 2022 `0.1781` (N 1020), 2023 `0.1234` (N 787), 2024 `0.1838` (N 970).

`accel|lt_-1` has the largest absolute delta, `+0.3201817914756354` on N `215`, interval above zero, score `0` because the year slices are below the frozen support rule. It is not the successor.

## Forecast comparison

Same scored rows. Expanding ISO week. A training label is admitted only after the 4-hour window has closed. Training-only scaling. No penalty and no fallback. Bootstrap of stored probabilities, `B = 2000`, seed `20261121`, no refit. Recompute from `predictions.npz` disagrees by `0` on all six Brier and log-loss figures.

| Model | Brier | Log loss |
|---|---|---|
| B0, training frequency | 0.19435944443891975 | 0.5773573885013551 |
| B_geom, constant `race_raw` | 0.19429124723678626 | 0.577175780701207 |
| B1, `log_rv_24h` only | 0.19193111525941603 | 0.5709410619199643 |
| Candidate, 20 frozen columns | 0.18212248995632146 | 0.545445783939662 |

Candidate minus B1: Brier `-0.009808625303094565`, about `-5.11%` of the B1 Brier. Interval `[-0.01123806638240841, -0.008445818777423383]`. Log loss `-0.025495277980302267`, about `-4.47%` of the B1 log loss. Interval `[-0.028970542245865125, -0.022223715664192394]`. Valid draws `2000`.

B1 minus B0 on Brier is `-0.0024283291795037243`. The geometry is almost the unconditional frequency, which is what a symmetric barrier predicts. The candidate's increment over B1 is larger than B1's increment over B0.

AUROC, not a route input: B1 `0.574279297880195`, candidate `0.6627511039233882`.

Calibration of the candidate, not a recalibration: slope `1.0676098789752784`, intercept `0.02937088117383978`.

| Predicted bin | N | Mean predicted | Observed |
|---|---|---|---|
| `< 0.15` | 15483 | 0.12613917907392994 | 0.09584705806368275 |
| `[0.15, 0.25)` | 65084 | 0.20219869750188507 | 0.19262798844570095 |
| `[0.25, 0.35)` | 48811 | 0.29410426481013596 | 0.30138698244248224 |
| `[0.35, 0.45)` | 21714 | 0.3924072118016234 | 0.39463019250253295 |
| `>= 0.45` | 11018 | 0.5271141875562989 | 0.49809402795425667 |

The middle bins are close. The lowest bin and the top bin both overstate the hit rate.

Development 2020–2022, N `91953`: delta Brier `-0.006011884117970989`, delta log loss `-0.015816179668835195`. Diagnostic 2023–2024, N `70157`: delta Brier `-0.0147849176501971`, delta log loss `-0.03818142657608503`. The later block is on the same exposed surface. It is not a pristine confirmation. Every scored year has a negative delta Brier: 2020 `-0.005542232483420395` (N 21887), 2021 `-0.00303734986776516` (N 35040), 2022 `-0.00928108258347149` (N 35026), 2023 `-0.014705366740968284` (N 35037), 2024 `-0.01486428055471442` (N 35120).

Alert rule `p_candidate >= p_b1 + 0.05`, for counts only: `38876` alerts, `23.01716992303138` per scored day, precision `0.4058545117810474`, recall `0.3687396293439903`, missed share `0.6312603706560097`, false alarms `13.67554766133807` per day. Mean lift on an alert `0.13129167762285818`. Warned episodes `2941` of `5846`. Median lead from `T` to the touch `130` minutes. 90th percentile `235` minutes.

Candidate probabilities have mean `0.2701678522177388` and standard deviation `0.10737251323061812`, against B1 mean `0.2696407383985914` and standard deviation `0.05520746990123236`. Share of candidate probabilities at or above `0.5` is `0.03699339954351983`.

## Failure map

- Compression does not precede more barrier hits. `joint|compressed` N `11524`, rate `0.17502603262755986` versus B1 `0.26983569669877666`, delta `-0.0948096640712168`, interval below zero. `rv_ratio_4h_24h|lt_0.7` N `38962`, delta `-0.10060200127676289`. `joint|quiet_volume_tight` N `33449`, delta `-0.10797709295379307`. `joint|active_squeeze` has N `181` and no interval. This is the same direction as the closed H01 result, and H01 is not rescored.
- A close near the top of the previous 4-hour range is common and not informative. `range_pos_4h|0.8_to_1` N `28512`, rate `0.2680976430976431` versus B0 `0.263950404046635`, delta versus B1 `+0.004640678035172485`, interval covers zero.
- The bulk range bin is flat. `range_vs_sigma_4h|1_to_2` N `85804`, delta `-0.00022584963006505587`, interval covers zero.
- The Europe session interval covers zero. Asia is lower (N `47292`, delta `-0.0861217764502579`). Saturday is lower. Sunday is not a copy of Saturday: `dow|6` delta `+0.03747056977513685`, interval above zero. Monday is higher: `dow|0` delta `+0.0820332204205243`.
- Taker-buy quote coverage on the loaded bars is `1.0`. It is not a model column and not a ranked cell.
- The constant geometric probability does not beat B0 by a meaningful amount. Knowing only the 24-hour scale moves Brier by about `-0.00243`. The remaining candidate increment is the state, including the predeclared clock.

## Verdict

`PRECURSOR_DISCOVERY_PROMISING`

Both loss deltas are negative, both bootstrap upper bounds are negative, the calibration slope is positive, and both era blocks have a negative Brier delta. `PROMISING` is a reason to freeze a separate successor. It is not a confirmed edge, not a live probability, and not a trading result.

What a later 4-hour target-hit model can use from this pass: occurrence is forecastable beyond a volatility-scaled barrier, and the information sits in already-large short-horizon moves, elevated activity, and an expanded range, plus the clock. It does not sit in compression, and it does not sit in range location. The practical alert is frequent: about 23 times per day, precision about 0.41 against a base rate about 0.26, and about 63% of positive decision rows are missed. Neighboring 15-minute labels share the 4-hour path.

Not opened: 2025/2026, E1, open interest, funding, order book, another venue. No second pass. No new `K`. No product change.
