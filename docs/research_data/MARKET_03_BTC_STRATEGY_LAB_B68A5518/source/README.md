# btc-strategy-lab

**I backtested 42 public Bitcoin trading strategies on 8 years of data. 33 of them lost money. This repo shows which ones didn't — and the validation harness that separates the two.**

![Equity curve](docs/img/hero.png)

[![Stars](https://img.shields.io/github/stars/wiktorj137/btc-strategy-lab?style=flat&color=00E39B&label=stars)](https://github.com/wiktorj137/btc-strategy-lab/stargazers)
[![License: GPL v3](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Freqtrade](https://img.shields.io/badge/built%20on-Freqtrade-brightgreen.svg)](https://github.com/freqtrade/freqtrade)
[![Backtest only](https://img.shields.io/badge/status-backtest%20only-orange.svg)](#what-this-is-not)

> [!TIP]
> ### ⭐ Star it to find it later
> Your star list is a bookmark folder.

---

## Quick start

```bash
git clone https://github.com/wiktorj137/btc-strategy-lab.git
cd btc-strategy-lab
./scripts/setup.sh          # venv + dependencies
./scripts/download_data.sh  # BTC/USDT candles since 2018 + funding rate

# reproduce the headline result
.venv/bin/freqtrade backtesting -c config.json -s EmaCrossFunding \
  --timeframe 1h --timerange 20191001- --fee 0.001
```

Takes about ten minutes end to end, most of it downloading candles.

---

## Why this exists

Every trading repo shows one equity curve going up and to the right. Almost none of them tell you how many curves were thrown away to get it.

This started as my own strategy. It returned +268% in backtest, which felt great until I ran it through an overfitting test and got a **PBO of 1.00 — the worst possible score**. Every single parameter set that looked best on past data ranked near the bottom on unseen data. The strategy was memorizing history, not finding an edge.

So I deleted it and did the boring thing instead: benchmark everything public, on identical data, with identical fees, and let the validation gates decide.

**The failed strategy is still in this repo** (`user_data/strategies/BtcHybrid.py`), because how it failed is more instructive than the winner.

---

## Results

All numbers: BTC/USDT spot, 1h candles, 0.1% fee per side, no leverage, single position.

| | This strategy | BTC buy & hold | S&P 500 |
|---|---|---|---|
| Total return | **+1,604%** | +781% | +189% |
| CAGR | **50.9%** | 37.1% | 16.7% |
| Max drawdown | **−33.8%** | −76.6% | −33.7% |
| Sharpe | **1.31** | 0.83 | 0.88 |
| Sortino | **1.42** | 1.13 | 0.89 |
| Calmar | **1.51** | 0.48 | 0.49 |
| Time in market | 61% | 100% | — |
| Trades | 96 | — | — |

Roughly the drawdown of the S&P 500 with three times the return of Bitcoin. The trade-off is that it sits in cash 39% of the time and only trades about 14 times a year.

![Return vs risk](docs/img/risk_return.png)

### It works in every regime

This is the test my own strategy failed. Splitting the period into four distinct market environments:

![Regimes](docs/img/regimes.png)

Positive in all four — including 2022, when buy & hold lost 65% and this strategy lost 24%.

### Drawdown

![Drawdown](docs/img/drawdown.png)

---

## The benchmark

42 public Freqtrade strategies with more than 20 trades, run on identical data and fees:

![Benchmark](docs/img/benchmark.png)

| | |
|---|---|
| Strategies tested | 42 |
| Beat BTC buy & hold | 3 |
| Lost money outright | 33 |
| Median return | −81% |

Sources: [freqtrade/freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) and [paulcpk/freqtrade-strategies-that-work](https://github.com/paulcpk/freqtrade-strategies-that-work). Fetch them with `./scripts/fetch_benchmark_strategies.sh` — they are not redistributed here.

Full results: [`research/out/benchmark.csv`](research/out/benchmark.csv).

### Day trading does not survive fees

A separate finding worth its own line. Of 22 strategies on 5-minute candles:

| | |
|---|---|
| Profitable | **1** |
| Unprofitable | 21 |
| Median return | **−95.6%** |

At 0.1% per side, a bot making 6,000 round trips pays **twelve times its own capital** in fees. `EMASkipPump` made 5,953 trades and paid 1,191% of capital to the exchange. No indicator edge covers that.

Watch out for the win-rate trap: `Strategy001` won **88.6%** of its trades and finished at **−98.6%**. Many small wins, rare catastrophic losses.

---

## The strategy

Four rules. That is the entire thing.

1. Take the 600-hour EMA of price (~25 days)
2. Price crosses **above** it → buy
3. Price closes **2% below** it → sell
4. Skip entries when perpetual funding rate is in the top 45% of its trailing 180-day range

![Signals](docs/img/signals.png)

Rules 1–3 are a parameterised version of [`EMAPriceCrossoverWithThreshold`](https://github.com/paulcpk/freqtrade-strategies-that-work) by Paul Csapak (MIT), which won the benchmark. Rule 4 is the only thing I added.

### Why only four rules

My discarded strategy had five tuned parameters and failed validation. This one has three, and the funding filter adds a fourth. Every parameter you add is another chance to fit noise.

The proof is in the parameter sweep: returns vary **smoothly** with EMA length (600 > 800 > 400 > 1000 > 1200) instead of jumping around randomly. A real effect produces a gradient. Overfitting produces a lottery.

### What rule 4 buys you

The baseline that actually tests rule 4 is not buy & hold — it is rules 1–3 on
their own, which is [`EmaCross.py`](user_data/strategies/EmaCross.py):

| | Return | Max drawdown |
|---|---|---|
| Rules 1–3 only (`EmaCross`) | +1,353% | −49.4% |
| **Rules 1–4 (`EmaCrossFunding`)** | **+1,604%** | **−33.8%** |

The funding rule buys drawdown, not return. Verified across both halves of the
data and three EMA lengths — 6 out of 6 independent checks showed reduced
drawdown.

The filter is set to 55, not the best-performing 60. Picking the exact peak of a
sweep is how you fool yourself; 50, 55 and 60 all work, so take the middle.

> **A note on drawdown numbers if you use Freqtrade.** Its summary reports the
> largest drawdown *in absolute currency*, then prints the percentage that
> represented at the time. On a compounding account those are different things —
> a late drawdown is large in dollars and small in percent. Freqtrade reports
> −23.6% for this strategy where the true maximum percentage drawdown is −33.8%.
> Everything in this README is the latter, computed in
> [`research/metrics.py`](research/metrics.py).

---

## Validation

Every strategy here passes through the same gates. Most candidates do not.

| Gate | Threshold | This strategy | My discarded one |
|---|---|---|---|
| **Walk-forward** (params chosen on past data only) | majority of windows | **8 of 13**, +1,125% ✅ | not run |
| **PBO** (overfitting probability) | < 0.50 | **0.21** ✅ | 1.00 ❌ |
| **Look-ahead bias** | none | **clean** ✅ | detected ❌ |
| **Deflated Sharpe** p-value | > 0.95 | 0.994, but see caveat ⚠️ | 0.850 ❌ |
| **Minimum backtest length** | — | needs 706d, has 3,100d ✅ | needs 3,361d, has 3,138d ❌ |
| **Profitable in all regimes** | yes | 4 of 4, thin samples ⚠️ | 1 of 4 ❌ |
| **Works on other assets** | yes | **fails** ❌ | not run |

```bash
.venv/bin/python research/sweep_emacross.py   # parameter sweep
.venv/bin/python research/overfit.py sweep_emacross.feather
```

**PBO** ([Bailey et al.](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253)) splits the data combinatorially and asks how often the in-sample winner underperforms out-of-sample. Above 0.5 means your backtest is worse than a coin flip at predicting the future.

**Deflated Sharpe Ratio** discounts your Sharpe for how many variants you tried. Test 25 parameter sets and one will look good by luck alone — DSR prices that in.

Data quality is gated too. `research/data_scrub.py` checks for missing bars, duplicate timestamps, broken OHLC relationships and stale candles before anything is backtested.

### Walk-forward

The strongest test here, and the one that answers "did you just tune this on the
whole history". Parameters are chosen on a trailing 24-month window, then tested
on the next 6 months, which the selection never saw. Roll forward, repeat.

```bash
.venv/bin/python research/walk_forward_fast.py
```

| | |
|---|---|
| Windows | 13 |
| Profitable | 8 |
| Compound out-of-sample return | **+1,125%** |
| BTC buy & hold, same period | +734% |
| Worst window | −25.4% |

**Caveat that matters:** one window (H2 2020, +182%) carries a lot of this.
Drop it and the remainder compounds to +335% against BTC's +734% — it
underperforms. The chosen EMA also drifts between 500 and 1200 across windows,
so there is no stable "correct" parameter, which is itself a sign that part of
what the sweep picks up is noise.

### Where this does not hold up

Published because the failures are the useful part.

**It does not generalise to other coins.** Same rules, same parameters, no
re-tuning, 1h candles since 2018:

| Coin | Strategy | Buy & hold |
|---|---|---|
| ETH | +84% | +53% |
| DOGE | +36% | +9% |
| AVAX | −53% | −60% |
| BNB | +21% | +122% |
| LINK | −9% | +51% |
| SOL | +62% | +294% |
| XRP | −48% | +274% |
| **BTC** | **+1,419%** | **+653%** |

Three lost money outright, four lost to simply holding. Either Bitcoin genuinely
trends differently from altcoins, or the BTC result is fitted to one lucky
series. I cannot separate those two, so treat the second as live.

**The Deflated Sharpe number is optimistic.** It deflates for the 25 variants in
the EmaCross sweep, but the strategy was also picked as the winner of a 42-way
benchmark and then had a fourth rule added, and neither of those selection steps
is in the trial count. Trial count alone barely moves it (0.994 at 25 trials,
0.985 at 150). What moves it is the spread of the trial Sharpes: my sweep has a
spread of 0.16 because the variants are near-identical, while the 42-strategy
pool ranged from −100% to +1,312%. At twice that spread the p-value drops to
0.88, at three times to 0.51. **The shipped strategy does not clear this gate.**

**The benchmark is unfair to multi-pair strategies.** It runs everything on a
single pair with `max_open_trades: 1`. Much of `freqtrade-strategies` is written
for a 30-pair whitelist with several slots open, so most of those strategies
never got to place the trades they were designed for. Some of the losers there
are strategies I ran wrong, not bad strategies.

**Regime buckets are thin.** 12, 19, 25 and 40 trades. The first two carry
nothing on their own.

Thanks to the r/algotrading commenter who worked out the first three of these
before I did.

---

## What's in here

```
user_data/strategies/
  EmaCrossFunding.py     # the strategy
  EmaCross.py            # same, without the funding filter
  BtcHybrid.py           # the one that failed. kept on purpose
research/
  data_scrub.py          # data quality gate
  benchmark_strategies.py# runs every public strategy on identical data
  sweep_emacross.py      # parameter sweep -> equity matrix
  pbo.py                 # PBO + Deflated Sharpe, self-contained implementation
  overfit.py             # runs the gates, prints a verdict
  walk_forward_fast.py   # rolling re-fit, parallelised
  fetch_orderflow.py     # 5m open interest / taker / positioning since 2021
  test_orderflow_edge.py # does any of it beat the fee floor?
  test_onchain_edge.py   # does funding rate actually predict price?
  compare.py             # strategy vs BTC vs S&P 500
  metrics.py             # 25 risk metrics
  chart_signals.py       # interactive signals + trade list
  report_simple.py       # plain-language HTML report
dashboard/app.py         # Streamlit dashboard
```

Reports:

```bash
.venv/bin/python research/chart_signals.py   # signals + full trade list
.venv/bin/python research/report_simple.py   # HTML summary
.venv/bin/streamlit run dashboard/app.py     # live dashboard
```

---

## Things I tested that did not work

Published because negative results save other people time.

**Different coins don't help.** Tested ETH, SOL, DOGE, XRP, BNB, AVAX and LINK on 5m candles. Raw edge was under 1 bps against a 4 bps cost floor everywhere. AVAX had the strongest mean-reversion signal (autocorrelation −0.22) and still made nothing — that signal is bid-ask bounce, which you pay for rather than earn. **BTC had the best raw edge of the eight.**

**Funding rate doesn't work intraday.** It predicts returns, but the effect needs days to play out: +7.6 bps at 4h, +27 bps at 24h, +69 bps at 72h. And the sign **flipped in 2023** — before that, low funding preceded rallies; after, the opposite. A directional rule fitted on 2019–2022 data would have quietly stopped working. That's why it is used here only as a one-sided "don't buy into froth" filter.

**Fear & Greed adds nothing** beyond funding rate. Heavily correlated, weaker signal.

**Order flow does not give an intraday edge either.** Binance publishes 5-minute
open interest, taker buy/sell volume and long/short account ratios back to 2021
([`research/fetch_orderflow.py`](research/fetch_orderflow.py), 592k rows). Tested
seven features against a 4 bps maker cost floor, split-half for stability:

| Horizon | Best edge found | Verdict |
|---|---|---|
| 15m | 0.7 bps | below cost |
| 1h | 2.6 bps | below cost |
| 4h | 9.4 bps | sign flips between halves |
| 24h | 42.7 bps | stable, but see below |

Nothing clears costs at day-trading horizons. That is now three independent
attempts — candle indicators, funding rate, order flow — reaching the same
answer, so I consider the question closed for retail fee tiers.

**Crowd positioning looks like a real signal and still is not worth shipping.**
The long/short account ratio was the one feature that kept its sign across both
halves and cleared the cost floor at 24h: −42.7 bps, meaning returns are lower
after the crowd piles into longs. Adding it as an entry filter on top of the
shipped strategy:

| Crowd filter | 2021–23 | 2024–26 |
|---|---|---|
| none | +150% | **+66%** |
| 80th pct | +155% | +82% |
| 70th pct *(best overall)* | **+169%** | +38% |
| 60th pct | +184% | +10% |

The setting with the best full-sample result is worse than no filter over the
last two years, and the edge itself decays from −76 bps in the first half to
−14 bps in the second. Same shape as the funding-rate sign flip in 2023. Only
the 80th percentile improves both halves, by too little to justify a fourth data
source and another unaccounted selection step. Not shipped.

**Averaging the EMA length instead of picking one does not help.** Walk-forward
showed the optimal EMA drifting between 500 and 1200, so the obvious fix is to
use the whole range and trade on the fraction of EMAs price sits above — which
removes the parameter selection that the Deflated Sharpe has to deflate for.
Tested on the same window: +1,513% at −34.5% max drawdown, against +1,604% at
−33.8% for the shipped strategy. Worse on both axes. Kept in
[`user_data/strategies/EmaEnsemble.py`](user_data/strategies/EmaEnsemble.py)
because the reasoning was sound even though the result was not.

---

## What this is not

- **Not financial advice.** I am not a licensed advisor and this is not a recommendation to trade anything.
- **Not live-tested.** Every number here is a backtest. Real fills, latency, outages and slippage are not fully modelled.
- **Not a guarantee.** A backtest describes the past. Regimes shift — the funding rate result above is a concrete example of an edge that reversed.
- **Not a money printer.** −34% drawdown means a $1,000 account showing $660 for months. Most people abandon a strategy at that point, which converts a paper gain into a real loss.

If you run it, run `--dry-run` first. The strategy trades ~14 times a year, so you need **four months minimum** before live results mean anything.

---

## Roadmap

- [x] Walk-forward optimisation with rolling re-fit
- [x] Order-flow features — tested, no intraday edge
- [ ] Trial ledger so the Deflated Sharpe counts the whole selection pipeline
- [ ] Re-run the benchmark with each strategy's intended pair whitelist
- [ ] Live paper-trading log, published as it happens

---

## Credits

- [Freqtrade](https://github.com/freqtrade/freqtrade) — the backtesting engine
- [Paul Csapak](https://github.com/paulcpk/freqtrade-strategies-that-work) — `EMAPriceCrossoverWithThreshold`, the strategy that won the benchmark (MIT)
- Bailey, Borwein, López de Prado & Zhu — PBO and Deflated Sharpe Ratio

---

**Made it this far?** [Star it](https://github.com/wiktorj137/btc-strategy-lab) so you can find it again when you need the harness.

Found a hole in the methodology? [Open an issue](https://github.com/wiktorj137/btc-strategy-lab/issues). I would rather be corrected than agreed with.

---

## License

GPL-3.0, inherited from Freqtrade. The original MIT-licensed strategy by Paul Csapak is incorporated with attribution.
