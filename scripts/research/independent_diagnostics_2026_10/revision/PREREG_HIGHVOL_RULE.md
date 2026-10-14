# Pre-registered check of the "direction skill concentrates in high volatility" rule
Written 2026-10-14 before any of the surfaces below were run. The rule was selected post hoc on
Binance BTCUSDT 2022-01..2026-07 (first investigation, econ_4h.txt). This file freezes it.

Rule (identical on every surface):
- 4h horizon, anchors every 48 five-minute bars (non-overlapping), decision at bar close t, outcome log(close[t+48]/close[t]); realistic variant: entry open[t+1], exit close[t+48].
- 26 features: the first investigation's 29 minus the three funding features (funding is not available on every surface and carried no information). Train-only clipping (0.1/99.9 %) and standardisation; training anchors whose horizon ends at or after the test start are purged.
- Model: L2 logistic regression, C = 0.1. Position = sign(p - 0.5) on every anchor (no confidence filter).
- Volatility terciles of lrv_24h with edges from the training set of each fold.
- Primary endpoint: mean gross return (bp) of the position in the TOP tercile, pooled over test folds, week-block bootstrap 95 % CI (400 draws). Secondary: hit rate, net at 4 bp round trip, AUC in the tercile, bottom-tercile mean, share of the top-tercile gross profit contributed by the 5 % largest |returns|, per-fold means.
- Surfaces not used for the selection: (a) Binance USD-M ETHUSDT 5m 2020-01..2026-07, folds test 2022, 2023, 2024, 2025, 2026H1 (train = earlier years); (b) BitMEX XBTUSD 5m 2017-08..2019-12 (DH1_BITMEX_XBTUSD_TRADES_5M_V0), folds test 2018H2 (train 2017-08..2018-06) and 2019 (train 2017-08..2018-12); (c) Binance BTCUSDT 2020-01..2021-12 in reverse time order (train 2022-01..2026-07, test 2020-2021) — a disjoint-period check, not a forward test.
- Pre-set reading: the rule is supported if the top-tercile CI excludes 0 and net-at-4bp > 0 on ETH AND on at least one of (b), (c); it is weakened if the top-tercile mean is positive but the CI includes 0; it is not supported otherwise. ETH is correlated with BTC in time, so (a) is only partly independent.
