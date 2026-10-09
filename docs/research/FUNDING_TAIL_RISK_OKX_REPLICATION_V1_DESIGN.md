# FUNDING_TAIL_RISK_OKX_REPLICATION_V1

Design frozen before any future-path score. This file does not contain its own hash.

## Governing principle

Signalbot does not require the market to produce a preselected effect magnitude. We freeze observables, estimands, controls and anti-overfitting rules before reading outcomes. The market determines effect magnitude, sign and usefulness.

«Мы не требуем от рынка заранее выбранной величины эффекта. Мы фиксируем observable, outcome и честную процедуру до чтения результата; знак, форму и magnitude даёт рынок.»

This unit does not use an effect-size floor, `rho >= 0.05`, `rho >= 0.10`, an excursion-difference floor, a percentile-gain floor, or the MARKET-03 funding percentile `55`. None of those is the question.

## Question

On OKX `BTC-USDT-SWAP`, is distance of the settled funding state from the neutral center of its own past associated with subsequent 8-hour path stress, and does that association remain after the current 8-hour realized volatility?

This is a cross-venue check of the tail/extremity formulation. It does not test the Binance numeric effect. It does not ask the market to match a Binance coefficient.

## Parent, unchanged

`FUNDING_STATE_HISTORICAL_STRUCTURE_V1` stays `INCREMENTAL_ASSOCIATION_UNCERTAIN`. It is not reread.

Its raw signed-rank Spearman of funding versus 8-hour long downside was `+0.055772530537571544`, interval `[+0.0014817922680213926, +0.11027730322243834]`. The partial given `RV_8H` was `+0.027762672485166194`, interval `[-0.008055043619315706, +0.062366554178786546]`. The bin means were not monotone. The highest funding decile had the largest mean downside. The lowest decile was also elevated versus its neighbor. That shape is a hypothesis-generating observation. It is not a confirmed tail effect.

`FUNDING_TAIL_RISK_CROSS_VENUE_V1` stays `BLOCKED_BY_CROSS_VENUE_FUNDING_PROVENANCE` with `outcome_read = false`. Bybit neither confirmed nor refuted the shape.

## Evidence class

`CROSS_VENUE_RETROSPECTIVE_REPLICATION / AVAILABILITY_LIMITED`.

The official archive is a next-day file. A publication clock is not proven. This read is not pristine prospective and not a point-in-time confirmation. Freshness is about this exact question. The OKX 5-minute path was already consumed by level-reaction units for other questions. Those reads are not a confirmation of this one.

## Feasibility, outcome-blind

Official source, and the only source used:

`GET https://www.okx.com/api/v5/public/market-data-history?module=3&instType=SWAP&instIdList=BTC-USDT-SWAP&dateAggrType=daily`

Each listed object is `https://static.okx.com/cdn/okex/traderecords/swaprates/daily/YYYYMMDD/allswap-fundingrates-YYYY-MM-DD.zip`.

The zip is every swap instrument. The research series keeps `instrument_name == BTC-USDT-SWAP` only. Header `instrument_name,funding_rate,funding_time`. `funding_rate` is a decimal fraction, not a percent. `funding_time` is Unix milliseconds in UTC.

`1110` daily files are present: `2021-09-01` through `2021-09-30`, and `2022-01-17` through `2024-12-31`. No listed day inside those spans is missing. Files dated `2025-01-01` or later were not downloaded. August 2021 listings are empty. `2021-10-01`, `2021-12-01`, `2022-01-01`, and `2022-01-16` return HTTP 404 on the static URL. The bounded pre-2025 `funding-rate-history` REST page returned an empty `data` list and is not the source. The live `funding-rate` endpoint was not called. CoinGlass, Kaggle, TradingView, unofficial mirrors, and paid captures were not used.

`3329` unique `BTC-USDT-SWAP` rows. Cross-file duplicate timestamps `0`. Conflicting rates at one timestamp `0`. Rows at or after `2025-01-01T00:00:00Z` `0`. First `2021-08-31T16:00:00Z`. Last `2024-12-31T08:00:00Z`. Canonical extract SHA256 `4d8a132e286dc8135138672428673ca5d9740af3f106add22d259d7e36b175f9`. Source-zip manifest SHA256 `43990a6613dc8dc50fcc5e35480b99109157aabf8a8e598950540a162fd65a9b`.

`3327` timestamps sit on a UTC hour. One sits one second after `2022-12-29T08:00:00Z`. One sits at `2022-12-18T18:54:00Z`. Hours are `00:00`, `08:00`, and `16:00`, plus that one `18:54` print. The common interval is `28800` seconds.

Missing expected 8-hour slots, not filled:

- `2021-09-30T16:00:00Z`, because the next day's file does not exist;
- the archive hole from after `2021-09-30T08:00:00Z` until `2022-01-16T16:00:00Z`;
- `2022-02-25T08:00:00Z`, absent inside a present file;
- `2022-12-18T16:00:00Z`, where the archive prints `18:54` instead;
- `2024-12-31T16:00:00Z`, which would sit in the `2025-01-01` file that this unit does not download.

The series is settled historical funding at the settlement clock. It is not a predicted next-funding quote and not a premium index. The instrument is the linear USDT swap. Funding is not joined to Binance price or to OKX spot.

Price identity, open times only, high/low/close not used as an outcome during this audit: `docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/okx_btc_usdt_swap_5m.csv.gz`, SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`, `499968` bars, first open `2020-04-01T00:00:00Z`, last open `2024-12-31T23:55:00Z`, duplicates `0`, off-grid `0`, missing slots `0`, opens at or after `2025-01-01` `0`.

Feasibility is PASS. The official settled series is the right instrument, starts before 2025, is hash-bound, and can be joined to that price file. No minimum-N gate is applied. The counts above are the coverage.

## Rank and warmup

Past OKX funding only. For event `i`:

`rank_i = (1 + #{past < x_i} + 0.5 * #{past == x_i}) / (n_past + 1)`

The current rate and every later rate are outside the reference multiset. The off-grid `18:54` print stays in that history. It is a real settled rate.

Warmup is the parent rule `n_past >= 90`. The OKX clock is the same 8-hour settlement schedule, with the holes and the single off-grid print above. Ninety prior events are about thirty days of that clock, the same minimum history as the parent. The warmup is not chosen from a result.

Counted from funding timestamps only: the segment before the archive hole is 90 events. The first event with a defined rank is therefore the first event after the hole. The warmup was not shortened or lengthened to make that true.

## Extremity

`FUNDING_EXTREMITY = abs(FUNDING_RANK - 0.5)`

The range is about `0` to `0.5`. A larger value is a funding state farther from the middle of its own past. There is no exponent and no transform search.

The child asks the extremity question because the Binance bins were elevated at both ends while the signed line was weak. That choice is declared here, before the OKX path is read.

## Decision time

`T` is the OKX settlement hour.

A row is on the settlement grid when `funding_time` is within `5000` ms of a UTC hour in `{0, 8, 16}`. `T` is that hour, the floor of `funding_time`. The floor does not move `T` forward. The one-second print at `2022-12-29T08:00:01Z` takes `T = 2022-12-29T08:00:00Z`. Five seconds is inside one 5-minute bar and does not reach the next bar.

The `18:54` print is not on that grid. Flooring it to `18:00` would pair the rate with a price path that starts before the rate was printed. That row is a schedule exception: it remains in the rank history and it is not an analysis row. It is not imputed, and the missing `16:00` slot is not filled.

`P0` is the close of the 5-minute bar that closes at `T` (open `T - 5min`). No price after `T` enters `P0`.

## Outcome

Primary outcome is the parent's `absolute_excursion`, reused exactly:

`max(abs(log(H_max / P0)), abs(log(L_min / P0)))`

`H_max` and `L_min` come only from bars whose open lies in `[T, T+8h)`. That is 96 bars. A bar that opens at or after `2025-01-01T00:00:00Z` is not read. An incomplete window is dropped and counted.

Descriptive components, not route inputs:

- downside: the parent's `adverse_long`, `max(0, -log(min low / P0))` on the same window;
- upside: `max(0, log(max high / P0))` on the same window.

## Control

`RV_8H = sqrt(sum r_k^2)` over the 96 completed 5-minute log close-to-close returns that end at `T`. The last close is `P0`. No return after `T` enters the control. An incomplete window is dropped and counted. Same venue, OKX `BTC-USDT-SWAP` only.

## Primary statistics

Raw Spearman of `FUNDING_EXTREMITY` with `ABS_EXCURSION_8H`.

Primary: partial Spearman of `FUNDING_EXTREMITY` with `ABS_EXCURSION_8H` given `RV_8H`, the project's rank-residualization (`partial_spearman` in `scripts/research/formation_width_regime_v1/amendment_a1.py`). A degenerate residual stops the read. It is not given a ridge.

The route reads only that partial point and its interval:

- point `> 0` and interval lower bound `> 0`: `CROSS_VENUE_EXTREMITY_ASSOCIATION_SUPPORTED`;
- point `> 0` and the interval includes `0`: `CROSS_VENUE_EXTREMITY_ASSOCIATION_UNCERTAIN`;
- point `<= 0`: `CROSS_VENUE_EXTREMITY_ASSOCIATION_NOT_OBSERVED`;
- fewer than 90 percent finite partial draws, or a non-finite point: `INFERENCE_NOT_INTERPRETABLE`.

Exact zero is not positive. There is no magnitude floor. `PRODUCT_INTEGRATION_CANDIDATE` is true only for `CROSS_VENUE_EXTREMITY_ASSOCIATION_SUPPORTED`. The owner still decides any implementation. This unit changes no production code, no `/btc` screen, and no push.

## Bootstrap

ISO-week blocks of `T`. `B = 2000`. Seed `20261115`. Two-sided 95 percent. Quantiles `0.025` and `0.975`, numpy linear. Each draw recomputes the raw Spearman and the partial Spearman. The past-only rank is a property of the event; a draw does not rebuild it. The share of finite partial draws above zero is descriptive and is not a route input.

## Descriptions that do not route

Five bins of the rank, the parent's edges: `[0, 0.10)`, `[0.10, 0.25)`, `[0.25, 0.75)`, `[0.75, 0.90)`, `[0.90, 1]`. Each reports N, mean absolute excursion, median absolute excursion, mean downside, and mean upside.

Two contrasts, mean absolute excursion: `[0.90, 1]` minus `[0.25, 0.75)`, and `[0, 0.10)` minus `[0.25, 0.75)`. The same week draws supply an interval when the bin is non-empty. They do not replace the continuous primary and they do not promote one side after the score.

Signed funding, descriptive: positive rates and negative rates, each with N, Spearman of the signed rank, and Spearman of extremity. Zero rates are counted and sit in neither subset.

Calendar years of `T` that the surface contains, each with N, raw extremity Spearman, and partial extremity Spearman. No three-year gate. A sign change is heterogeneity.

## After the score

Compare OKX with the frozen Binance partial above. Do not pool the venues. Record whether the extremity point is positive, whether the volatility control reduces it, whether each tail mean sits above the center, and both partial points side by side. No similarity cutoff.

A positive structure may be described as compatible with the historical drawdown reduction in MARKET-03. It does not prove why `EmaCrossFunding` worked. There is no causal claim.

Conclusion class follows the route: supported, point-positive but uncertain, or no positive extremity relation. Opposite signs of the two tail contrasts are recorded as an asymmetric shape. That note does not change the route.
