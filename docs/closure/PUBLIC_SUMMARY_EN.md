# Pulsy: project summary

*Draft of a public text. Publication requires a separate owner permission (`docs/PROJECT_CLOSURE_DECISION_V1.md` §6).*

## What it was

Pulsy (formerly Signalbot) was a Telegram bot about the bitcoin market and a research programme around one question: can publicly available market data yield a forecast that is honestly verifiable and useful to a trader. The project ran from 2025 and was closed in October 2026 by owner decision.

## Data

Binance USD-M BTCUSDT: 1-minute and 5-minute candles, open interest, funding, position ratios, 2020 to mid-2026; BitMEX XBTUSD 2016–2019 as an independent period; OKX and Bybit for cross-venue questions; eleven Binance altcoins for cross-market questions. All data from the exchanges' public archives.

## Method

Every hypothesis was registered before its outcome was read: what is measured, on which data, what counts as support. Data surfaces read for a hypothesis were logged in an exposure ledger and no longer counted as independent. Level events were compared against paired controls (pseudo-levels at the same distance from the period open). Results were reported as evidence (estimate, interval, stability by year), not as verdicts. The project atlas registers 207 research units; these are not 207 executed experiments: about 80 reached an outcome read, the rest were closed earlier because the method or the data could not give an answer, the information was insufficient, or the candidate was never started. The mechanism × data × state map is kept in the atlas.

## What was found

**Price direction over 1–4 hours.** The best models on candle data reach an AUC of about 0.55 in an honest 2022–2026 walk-forward (4h: 0.553, 95 % 0.543–0.563). This is short-term reversal, long known. Its gross value per 4h trade is +1.7 basis points with an interval from −0.2 to +4.0, against costs of 4–10. Three generations of the project's forecast engines did not change this; the first version, read as a direction predictor, was worse than random (AUC 0.48–0.49).

**Cross-market relations.** Altcoins do not follow bitcoin with a lag at minute scales. Features of other assets add at most +0.005 AUC to direction. Cross-sectional reversal among altcoins has a positive rank IC every year, but in an executable simulation with real turnover and funding its net value at 1 bp per unit traded is about zero in 2022–2024, its gross value about zero in 2025–2026, and positive only in 2020–2021; the intervals include zero.

**Levels.** The first touch of the previous day's, week's or month's high or low is a distinguishable event: after it, price reaches the ±X barriers more often and sooner than after touching a pseudo-level (+5 pp paired, +10 pp unpaired, 2020–2026), and realised volatility in the following hour is 7–12 % higher. This is volatility expansion, not direction: the share of breaks among resolved touches equals that of pseudo-levels. Where price stands 15 minutes after the touch predicts the outcome as a random walk between two barriers would, and more strongly at pseudo-levels. Cross-venue data adds nothing: it repeats Binance's own move (correlation 0.996). Every tradeable expression tested (symmetric stops at the barriers, holding in the approach direction, a model-directed entry 15 minutes later) has a gross point estimate between −2.9 and +1.5 bp per trade with intervals about ±6 bp wide, all containing zero, against costs of 4–10 bp. The data rule out a large edge; they cannot rule out a small one that costs would still consume.

**Positioning.** The only directional effect to pass discovery: when Binance accounts are unusually long, price goes up first less often over the next 4 hours (−5.9 pp, 95 % −8.3 to −3.5; 2020–2024, BTC only). It was never tested on an independent period: positioning data do not exist for 2017–2019. On the already-exposed 2025–2026 data the frozen rule gave −2.3 pp with an interval through zero (−6.3 to +1.7). A second discovery effect from the same study (a retested daily level holds more often, +3.9 pp) was checked on 2017–2019 and was inconclusive (−0.7 pp, interval −4.8 to +3.1).

**Volatility.** Predictable: R² of log realised volatility 0.5–0.7 at 4 hours. The project's corridor model is at the level of simple HAR models; its improved version gains 1–2 % in log loss. This is the only part of the system that worked as described.

**Synthetic and methodological lines.** Calibration on synthetic data does not transfer to the market. An attempt to certify in advance that a test would be both safe and useful ran into sample size: at the project's sample sizes the two cannot be guaranteed together.

## Outcome

Validated trading edges: zero. Confirmed objects: one context object (market regime) and one event property of levels without direction. The predictable quantity: volatility.

The project is closed. The code, the records of all 207 units, the exposure ledgers and the data are preserved.
