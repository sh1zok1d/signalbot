# RANGECAST_V2 — result record

`MODE = DISCOVERY` · track `PRODUCT_EVIDENCE` · claim ceiling `DISCOVERY_ONLY` · no user-facing change

| Step | Commit | Record |
|---|---|---|
| Design note and loader, before any outcome | `1774cfb` | `RANGECAST_V2_DESIGN.md` |
| Candidate module, harness, development result (folds 2021–2024, frozen selection rule) | `2d5be72` | `RANGECAST_V2_DEVELOPMENT.json` |
| One time-disjoint exposed read, 2025-01-01 … 2026-10-11 | `078fa27` | `RANGECAST_V2_READ_2025_2026.json` |

Reproduce: `python -m scripts.research.rangecast_v2.evaluate develop` (LightGBM for the diagnostic model only, via `RANGECAST_V2_PYLIBS`). The read refuses a rerun. Data: Binance Vision USD-M BTCUSDT 5m, 112 checksum-verified objects (list digest `17eac792…0e45`); the 11 objects that overlap the E1-RUN-001 holdout were refused before any request.

## 1. What was found about V1

- **V1 is a strong baseline.** On the 4h task climatology's log loss is 15 % above V1's and a 24h-volatility-only model's is 4.2 % above it (per anchor, folds 2021–2024).
- **V1 over-states touch chances a little, steadily.** Out of sample 2021–2024, its middle bins read 1.0–1.2 pp above the realized share (4h: bin 30–50 % said 40.0 %, was 38.8 %). On 2025–2026, with the model fitted on 2020–2024, every bin is above the realized share (−0.4 to −1.3 pp) and the calibration intercept is −0.056 at 4h and −0.145 at 24h. The PIT of the realized excursion has excess mass in its lowest decile (0.110 to 0.112 instead of 0.100): moves smaller than forecast are too frequent. The 6–12 October live deviation (−12 pp) is far larger than this bias; the bias is a small, persistent part in the same direction.
- **Where the loss sits.** The scale features of V1 stop at 7 days and its clock is one hour-of-day table plus a weekend share. A longer memory, realized volatility of 5m returns and a day-of-week × hour clock are what the selected candidate adds; weekends gain most.

## 2. The ladder (4h, folds 2021–2024, 34 664 anchors, 210 ISO weeks)

Mean log loss per anchor over 32 events (16 log-spaced distances 0.2–5 %, both sides). Differences are against V1; week-cluster bootstrap 95 % intervals.

| Model | Log loss | Brier | vs V1 | 95 % interval | Years better than V1 | Calibration slope | Intercept |
|---|---|---|---|---|---|---|---|
| B_CLIM | 0.47588 | 0.15772 | +0.0619 | +0.0530 … +0.0714 | 0 of 4 | 0.976 | −0.202 |
| B_R24 | 0.43154 | 0.14140 | +0.0175 | +0.0159 … +0.0193 | 0 of 4 | 0.989 | −0.089 |
| **V1** | 0.41402 | 0.13503 | | | | 1.000 | −0.039 |
| L1 | 0.41060 | 0.13383 | −0.0034 | −0.0040 … −0.0028 | 4 of 4 | 0.996 | +0.005 |
| L2 | 0.41109 | 0.13397 | −0.0029 | −0.0035 … −0.0024 | 4 of 4 | 0.988 | −0.002 |
| L3 | 0.41192 | 0.13427 | −0.0021 | −0.0028 … −0.0013 | 4 of 4 | 0.981 | −0.005 |
| G (diagnostic) | 0.42720 | 0.13926 | +0.0132 | +0.0110 … +0.0155 | 0 of 4 | 0.957 | −0.045 |
| **W_L1 (selected)** | **0.41000** | **0.13362** | **−0.0040** | **−0.0047 … −0.0034** | **4 of 4** | 0.994 | +0.009 |

The frozen rule, step by step:

| Step | Against | Difference | 95 % interval | Years negative | Decision |
|---|---|---|---|---|---|
| L1, richer scale | V1 | −0.00342 | −0.00403 … −0.00281 | 4 | accepted |
| L2, state-dependent shape | L1 | +0.00049 | +0.00027 … +0.00069 | 1 | rejected |
| L3, up / down asymmetry | L1 | +0.00132 | +0.00078 … +0.00191 | 0 | rejected |
| Recency weights, half-life 365 days | L1 | −0.00061 | −0.00084 … −0.00038 | 3 | accepted |
| G, LightGBM means | W_L1 | +0.01720 | +0.01503 … +0.01935 | | no untapped nonlinear gain |

Guardrails of the selected model, all passed: 4h calibration slope 0.994; 1h −0.0037 (−0.0042 … −0.0033) and 24h −0.0043 (−0.0058 … −0.0029) against V1; near distances ≤ 0.5 % −0.0042 (−0.0052 … −0.0031); far distances ≥ 2 % −0.0012 (−0.0018 … −0.0006).

## 3. The 2025–2026 read (once; models fitted on 2020–2024, no refit)

| Horizon | Anchors | Weeks | V1 log loss | W_L1 log loss | Difference | 95 % interval | Relative | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| 1h | 14 624 | 88 | 0.35901 | 0.35535 | −0.00366 | −0.00418 … −0.00317 | −1.0 % | −0.0038 | −0.0034 |
| 4h | 14 522 | 88 | 0.37083 | 0.36513 | −0.00569 | −0.00669 … −0.00472 | −1.5 % | −0.0060 | −0.0052 |
| 24h | 13 842 | 88 | 0.38428 | 0.37704 | −0.00724 | −0.00971 … −0.00476 | −1.9 % | −0.0079 | −0.0062 |

4h reliability on the read, predicted against realized:

| Bin | V1 | W_L1 |
|---|---|---|
| 0–5 % | 1.5 vs 1.1 | 1.4 vs 1.2 |
| 5–15 % | 9.4 vs 8.1 | 9.3 vs 9.0 |
| 15–30 % | 22.1 vs 20.9 | 22.1 vs 22.3 |
| 30–50 % | 40.0 vs 38.9 | 39.9 vs 40.6 |
| 50–70 % | 60.2 vs 59.3 | 60.2 vs 61.0 |
| 70–85 % | 76.9 vs 76.1 | 77.0 vs 77.2 |
| 85–100 % | 88.0 vs 87.2 | 87.8 vs 88.1 |

The gain is largest at 0.5–1.4 % (about −0.009 nats per event on the read) and fades towards 5 %, where both models are near zero. «Ни один» of two levels: 4h log loss 0.4715 → 0.4615 on the folds and 0.4478 → 0.4352 on the read.

## 4. What it means for a published number

On the 4h folds the candidate's chance differs from V1's by a median of 2.5–3.5 pp at 0.4–1.4 %, a 90th percentile of 7–9 pp, and on average 0.7–0.9 pp lower. At 5 % the median shift is 0.2 pp.

Largest standardized contributions in the full fit (2020-01 … 2026-10-11, 4h, |β·SD|): day-of-week × hour season 0.31; realized volatility 24h 0.13; range 7d 0.10; weekend share 0.09; realized volatility 4h 0.08; range 24h 0.06; range 30d 0.05. The recent-move inputs from Impulse V1 (|ret 1h|, |ret 4h| over the 24h range) add 0.002 and 0.013: beside a good volatility forecast they carry little.

## 5. Result record fields

| Field | Content |
|---|---|
| estimate | 4h log loss −0.0040 nats per anchor (−0.97 %) against V1 on folds 2021–2024; −0.0057 (−1.5 %) on 2025–2026 |
| uncertainty | ISO-week cluster bootstrap, B = 2000, 95 %: −0.0047 … −0.0034 (folds); −0.0067 … −0.0047 (read) |
| information | 34 664 scored 4h anchors in 210 weeks (folds); 14 522 in 88 weeks (read); 32 binary events per anchor |
| stability | negative in each of 2021, 2022, 2023, 2024, 2025, 2026; in each volatility tercile; larger on weekends (−0.0073) than weekdays (−0.0027); largest in 2023 (−0.0077) |
| falsification | climatology and a 24h-volatility baseline are far behind V1, so the scoring separates models; the two shape and asymmetry mechanisms in the menu were rejected by the same rule, and the nonlinear diagnostic lost |
| limitations | one venue and symbol; every year exposed (the production model is fitted on all of it and its held-out check reads the last year nightly); yearly refits instead of nightly; the menu was informed by an earlier read of 2022–2024; level-zone touches (a structural selection of prices) are not in the grid; the LightGBM result speaks for this specification only |
| search exposure | 8 models (2 baselines, V1, 3 ladder steps, 1 recency variant, 1 diagnostic), one selection rule fixed before outcomes, one read of 2025–2026 for the selected model only |
| method before outcome | `RANGECAST_V2_DESIGN.md`, commit `1774cfb` |
| evidence summary | A wider scale input set with recency weighting gives touch probabilities about 1–2 % better in log loss than V1 at 1h, 4h and 24h in every year from 2021 to 2026, and removes most of V1's small over-statement |
| claim decision | none for users. `PRODUCT_INTEGRATION_CANDIDATE = YES`, subject to an owner go and a paired shadow record in the claim journal. A historical improvement is not an L3 live calibration |

## 6. Where the approach is limited

Scale carries almost all the information in price-only 5m data. Two structural ideas that looked reasonable did not survive out of sample: a state-dependent excursion shape (L2) and up / down asymmetry from recent signed returns and range position (L3). A nonlinear model of the same inputs did worse. After V1, the remaining gain from these inputs is about 1–2 %.

A larger step needs a different source of information. The strongest candidate is option-implied volatility (Deribit DVOL): it is forward-looking, and the repository holds `DH3_DERIBIT_DVOL_1H_V0` for 2021-03 … 2024-12. The atlas cell `S4-C04` is blocked on point-in-time semantics, because the non-revision of historical DVOL values is unverified. That blocker can be lifted cheaply: re-fetch the same period and compare it with the stored file, then collect DVOL live from now on. This is a successor; it was not evaluated here.

## 7. What a production switch needs (owner decisions)

1. **Shadow first.** The nightly build fits W_L1 beside V1 (`fit_range_model_v2(level="L1", half_life_days=365)`: about 3 s, about 38 KB of JSON). The hourly claim writer journals W_L1's chances on the same distance grid as a separate, never-shown class. A paired comparison with a promotion rule frozen before it starts follows: at least 8 weeks for 4h, a week-clustered log-loss interval below zero, and calibration not worse.
2. **The surfaces need no new contract.** `forecast_v2` returns `rangecast.forecast`'s keys, and `as_v1_model` lets `rangecast.touch_probability`, `neither_probability` and `stop_stats` read the V2 scale unchanged; tests pin both.
3. **Kept on V1:** the sharp-move push. Its threshold is calibrated on V1's event-neutral 1h scale (`MOVE_STATISTIC`).
4. **Changed with the switch:** the held-out touch and «ни один» bins must be computed for V2 in the nightly build. The claim classes get a new rule version, so a new cohort starts, and the calibration monitor sees a specification change and starts a new stream.
5. **Live parity.** Activity uses base volume, which the live 1m tail carries exactly (its quote volume is approximated). The longest window is 30 days, and the decision block loads 70.
