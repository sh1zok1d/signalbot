# Cross-market predictability study — design note (written before outcomes)

Date: 2026-10-14. Branch `claude/pulsy-cross-market-yerlly`. Diagnostic study, not a research
unit under the evaluation contract. Nothing here changes product, production, the paired shadow,
or any sealed record. The E1 holdout is never requested (no object of August 2026 or later).

## Question

Does joint information across crypto assets carry predictive content about the next 1h / 4h that
a single-asset model does not, and is any of it economically usable after costs at comparable risk?

## Data

Binance USD-M perpetuals, 5m klines (open/high/low/close, quote volume, taker-buy quote volume),
monthly archives from data.binance.vision, 2020-01 .. 2026-07. Assets: BTC, ETH, SOL, BNB, XRP,
DOGE (in hand) plus ADA, LINK, LTC, AVAX, DOT, BCH (downloaded now). All bars close on the same
exchange clock, so cross-asset features at bar close t are synchronous; targets use bars
t+1 .. t+h. Missing bars: close forward-filled, volume zero (a venue-wide outage affects all assets
at once and is therefore not a cross-asset signal; the share of filled bars is reported).

## Exposure before this study

BTC 2020-01 .. 2026-07 and ETH/SOL/BNB/XRP/DOGE 2020-01 .. 2026-07 were read by the two earlier
investigations (direction/volatility walk-forward; the pre-registered high-volatility rule). The
project's own units read BTC/ETH 2020-2024 (D4, D10, MARKET-05), a weekly spot panel (D13, C013),
and six-symbol level/spot questions (DH2) — see the survey in the report. No alt surface is
reserved. ADA/LINK/LTC/AVAX/DOT/BCH are read for the first time here.

## Protocol

- **Development (exploration and candidate selection):** walk-forward with test years 2022, 2023,
  2024; training = all earlier years (purged so no training window ends inside the test year);
  train-only clipping and standardisation.
- **Confirmation:** 2025-01-01 .. 2026-07-31, read ONCE for a frozen list of configurations
  written in `CONFIRMATION_LIST.md` before the read. This surface is not pristine (it was read for
  the single-asset questions), but it was never read for a cross-market object, and the frozen
  list prevents selection on it.
- **Secondary disjoint check:** reverse-time (train 2022-2026, test 2020-2021) for the same frozen
  list, labelled as such.
- Uncertainty: week-block bootstrap (400 draws) on pooled test anchors; paired differences between
  models are bootstrapped on the same anchors.
- Multiplicity: the number of configurations tried in development is reported; the confirmation
  list is short (≤ 8 items).

## Experiments (fixed menu)

E1. **Lead-lag at fine scale.** Cross-correlations of 5m log returns between BTC and each alt at lags
−12..+12 by year; Granger-style regression of alt 5m/15m/1h return on lagged BTC returns controlling
own lags, and the reverse. Purpose: test "BTC leads" at the horizons where it could exist.

E2. **Cross-asset direction.** For target asset X and horizon h ∈ {1h, 4h}: logistic regression and a
small gradient-boosting model with (a) own 26 features; (b) own + BTC features (BTC returns 5m .. 7d,
BTC RV 1h/4h/24h, BTC position in 24h range, BTC taker share); (c) own + market index features
(equal-weighted alt index returns/RV); (d) own + all assets' returns 1h/4h/24h. Metric: AUC,
log-loss skill, paired ΔAUC with bootstrap. Also BTC as target with alt features.

E3. **Relative return / cross-section.** Target: X's h-return minus BTC's (and minus the equal-weight
index). (i) Sign prediction with own + BTC features vs own only; (ii) cross-sectional rank: at each
4h anchor predict each asset's h-return (and idiosyncratic return), rank, and evaluate Spearman rank
IC vs realized, plus a top-k minus bottom-k portfolio. Baselines: short-term reversal (rank by past
1h / 4h / 24h return, reversed), momentum (past 7d), beta-ranked (asset beta to BTC × sign of BTC's
own model forecast), random.

E4. **Catch-up / beta-state.** Idiosyncratic return idio = r_X − β·r_BTC with β from the trailing 30
days. Does the past 1h / 4h idiosyncratic return predict the next 1h / 4h idiosyncratic return
(negative = catch-up / reversal; positive = divergence persists)? Does the effect depend on the size
of the BTC move, on dispersion, on realized correlation?

E5. **Economics.** For each candidate that survives development: positions sized to equal
ex-ante risk (target the BTC 4h volatility), costs 4 and 8 bp per leg round trip (taker), funding
differentials at 8h settlement for pairs where known, hit rate, mean, Sharpe, max drawdown, share
of profit from the top 5 % of trades, by year.

## What counts as what

- A cross-market effect counts as *present* if ΔAUC or Δlog-loss over the own-only model has a
  bootstrap interval excluding zero in development AND the same sign on confirmation.
- It counts as *economically relevant* only if the equal-risk net return after 4 bp per leg is
  positive with an interval excluding zero on confirmation and is not concentrated in the top 5 %
  of trades (share ≤ 30 %).
- A result that is present but not economically relevant is reported as information, not as a
  signal.
