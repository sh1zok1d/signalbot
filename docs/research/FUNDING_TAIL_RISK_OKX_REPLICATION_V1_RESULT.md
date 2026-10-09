# FUNDING_TAIL_RISK_OKX_REPLICATION_V1 — one historical read

`outcome_read = true`
`evidence_class = CROSS_VENUE_RETROSPECTIVE_REPLICATION / AVAILABILITY_LIMITED`
`interpretation = CROSS_VENUE_EXTREMITY_ASSOCIATION_UNCERTAIN`

The route uses only the partial Spearman of funding extremity with the 8-hour absolute excursion, given current realized volatility, and the interval of that partial. There is no magnitude floor. Bins, tails, years, and funding-sign splits are descriptions.

Read `2026-10-09T12:30:31Z`. Evaluator `0f2c2c6d0e3e`.

- Funding events `3329`
- Analysis N `3238`
- ISO weeks `156`
- Zero raw rates `2`
- Dropped, schedule exception `1`
- Dropped, state undefined `90`
- Dropped, path `0`
- Dropped, volatility window `0`
- Raw Spearman `0.06664979748104755` interval `[0.025176203970000286, 0.10808444189750395]`
- Partial Spearman `0.028873821844373516` interval `[-0.004485352423566223, 0.060993529736847574]`
- Valid partial draws `2000` / `2000`
- Share of partial draws above zero `0.954`

| bin | n | mean abs excursion | median | mean downside | mean upside |
| --- | --- | --- | --- | --- | --- |
| [0, 0.10) | 140 | 0.026316626460178443 | 0.0205825544408591 | 0.016994005955688986 | 0.016194484809174663 |
| [0.10, 0.25) | 397 | 0.019100748339424333 | 0.014882776162979294 | 0.011832182170002405 | 0.012218813458518201 |
| [0.25, 0.75) | 1709 | 0.017603469339081048 | 0.013731429938823137 | 0.011382297500561718 | 0.010808220168295277 |
| [0.75, 0.90) | 533 | 0.01791609285434317 | 0.013816582555434484 | 0.01175428334600912 | 0.010938193191886039 |
| [0.90, 1] | 459 | 0.018805473345256504 | 0.013984122667490578 | 0.012237320584214818 | 0.012035065240255242 |

- Upper tail minus center `0.0012020040061754556` interval `[-0.0009943390564229563, 0.00335524393492153]`
- Lower tail minus center `0.008713157121097395` interval `[0.004199146516901795, 0.013220252969804202]`

| year | n | spearman | partial |
| --- | --- | --- | --- |
| 2022 | 1046 | 0.05531890659980287 | 0.0025807432610314334 |
| 2023 | 1095 | 0.10486421193346844 | 0.05997025307219011 |
| 2024 | 1097 | 0.11145393598009805 | 0.06367189879527216 |

| side | n | signed rank | extremity |
| --- | --- | --- | --- |
| positive_funding | 2288 | 0.05712322634468358 | 0.05389576922029213 |
| negative_funding | 948 | -0.10056374704904374 | 0.10056374704904374 |

CROSS_VENUE_EXTREMITY_ASSOCIATION_UNCERTAIN

Conclusion `B_POINT_POSITIVE_UNCERTAIN`. Shape `BOTH_TAILS_ABOVE_CENTER`. Volatility control `CONTROL_REDUCED_THE_POINT`.
OKX partial `0.028873821844373516`. Frozen Binance parent partial `0.027762672485166194`. No similarity cutoff. The venues are not pooled.

Evidence class stays a cross-venue retrospective read with unproven publication time. Not a point-in-time confirmation. A positive structure is compatible with the historical drawdown reduction in MARKET-03 only as a description. It does not prove why that strategy result occurred. Not a product change unless the route itself is the supported code, and even then the owner decides implementation.
`PRODUCT_INTEGRATION_CANDIDATE = False`.
