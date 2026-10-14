# Frozen confirmation list (written after development 2022-2024, before any read of 2025-01 .. 2026-07)

Surface: Binance USD-M 5m, 2025-01-01 .. 2026-07-31 (test years 2025 and 2026H1; models trained on 2020-2024
with the same purge). Read once. Secondary disjoint check for fixed rules only: 2020-2021 (no fitting involved).

Development findings that define the expectations (all on 2022-2024):
- E2: adding BTC / market / all-asset features to an asset's own 26 features changes the direction AUC by -0.009 .. +0.015;
  72 comparisons; intervals exclude zero only for DOGE 1h own+btc (+0.0036 logit, +0.0048 gbm), DOGE 4h gbm (+0.011 .. +0.015),
  BNB 4h gbm own+btc (+0.011), SOL 1h gbm own+all (+0.007); the same comparisons with the other model are ~0.
- E3 pairs: idiosyncratic-return sign AUC 0.51-0.56 (model), 0.52-0.55 (fixed reversal rule); pair gross 0-4 bp, net negative.
- E3 cross-section (12 assets, 4h): reversal rank IC 0.029 (1h), 0.048 (4h), 0.031 (24h); 7d momentum IC -0.016; beta x BTC-forecast IC +0.015.
- E6: reversal long/short gross 1.9-2.8 bp per anchor, net < 0 at >= 1 bp per leg; top 5 % of anchors carry > 100 % of profit.
- E5: BTC / market RV add <= 0.002 R^2 to an alt's own HAR+clock volatility forecast.

Items (expected direction in brackets; a result "confirms" only if the sign matches AND the interval excludes zero):
1. E2 DOGE 1h: dAUC own+btc vs own, logit and gbm  [positive, ~+0.004].
2. E2 DOGE 4h: dAUC own+mkt vs own, gbm  [positive, ~+0.01].
3. E2 all five alt targets, 1h, logit: mean dAUC own+btc vs own  [~0; a general "BTC leads" would show > +0.005].
4. E3 pairs DOGE 4h, BNB 4h, XRP 4h: model AUC [0.53-0.56] and fixed-rule AUC [0.52-0.55]; pair gross bp [0-5]; net at 4 bp per leg [< 0].
5. E3 cross-section rev_4h (12 assets): rank IC [+0.03 .. +0.05, t > 3]; rev_1h IC [+0.02 .. +0.04]; mom_7d IC [negative].
6. E3 cross-section beta x btcdir: IC [small positive].
7. E6 rev_4h k=1/3: gross bp [+1 .. +4], net at 2 bp per leg [< 0], top-5 % share [> 1].
8. E5 vol spillover ETH/SOL/DOGE: dR^2 of +BTC RV over own HAR+clock [|dR^2| < 0.005].
Reverse-time (fixed rules only, 2020-2021): items 5 and 7 (E6 and rank IC with fixed rules).
