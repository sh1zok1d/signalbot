# Owner cards R03 — one-shot result

**Status:** `EXECUTED_ONCE / ALL_SIX_NO_INCREMENTAL_STRUCTURE / CLOSED`
**Executed:** 2026-10-03T01:35:45Z at `dea7b07` (the freeze commit), permit `OWNER_CARDS_R03_EXECUTION_PERMIT.json`
**Machine record:** `OWNER_CARDS_R03_RESULT.json` (per-unit differences included)
**Preregistration:** `OWNER_CARDS_R03_PREREG.md/.json`; design `OWNER_CARDS_R03_CARDS.md`; feasibility `OWNER_CARDS_R03_FEASIBILITY.md`

```
EXECUTED_HYPOTHESES = R03-A1, R03-A4, R03-B2, R03-C1, R03-C2, R03-C4
CLOSED_AT_FEASIBILITY = R03-A2, R03-A3, R03-C3 (compiler), R03-B1, R03-B3, R03-B4 (unit level)
DISCOVERY_CLASS = NO_INCREMENTAL_STRUCTURE for all six
REPLICATION_RUN = none (no discovery prototype; BitMEX 2017-2019 outcomes were not opened)
PROMISING_PROTOTYPES = 0
SUPPORTED = 0
RERUN_AUTHORIZED = false
PROTECTED_2025_2026_OPENED = false
```

## Primary results (discovery, Binance BTCUSDT perpetual 2020–2024)

Estimate = mean over units of the state-minus-comparator standardized log range, in comparator-SD units. Bar = 0.5 SD with the declared sign. p = two-sided sign-flip over units; Holm within the card.

| ID | Units | Estimate | SE (sign-flip / block) | p | Holm p | Statistical | Practical (bar 0.5, sign) | Class |
|---|---|---|---|---|---|---|---|---|
| A1 `WEEKLY_EXPIRY_HOUR` (+) | 260 | +0.077 | 0.077 / 0.074 | 0.32 | 0.61 | fail | fail | `NO_INCREMENTAL_STRUCTURE` |
| A4 `PRE_EXPIRY_PINNING` (−) | 260 | +0.067 | 0.064 / 0.058 | 0.30 | 0.61 | fail | fail (wrong sign) | `NO_INCREMENTAL_STRUCTURE` |
| B2 `BREADTH_SYNCHRONY` (+) | 53 | +0.037 | 0.057 / 0.057 | 0.53 | 0.53 | fail | fail | `NO_INCREMENTAL_STRUCTURE` |
| C1 `WEEKEND_HOURS` (−) | 260 | **−0.396** | 0.036 / 0.033 | <0.0001 | 0.0001 | **pass** | fail (0.40 < 0.50) | `NO_INCREMENTAL_STRUCTURE` |
| C2 `MONDAY_US_OPEN` (+) | 232 | +0.066 | 0.079 / 0.073 | 0.41 | 0.41 | fail | fail | `NO_INCREMENTAL_STRUCTURE` |
| C4 `FRIDAY_US_CLOSE` (+) | 246 | −0.123 | 0.071 / 0.069 | 0.077 | 0.15 | fail | fail (wrong sign) | `NO_INCREMENTAL_STRUCTURE` |

Every declared unit was evaluated; no window was unavailable (0 of 37 326 windows missing a bar). Moving-block and sign-flip standard errors agree, so dependence across units did not inflate the tests.

## Reading

- **Expiry clock (card A).** Neither the Deribit expiry hour nor the four hours before it differ from the same hours on other weekdays by anything close to the bar. The pre-expiry window is, if anything, slightly wider, not narrower. The larger monthly and CME settlements could not be tested at this bar (closed at feasibility).
- **Panel breadth (card B).** High breadth-synchrony days do not precede a wider BTC day. The three sibling states were closed outcome-blind for too few paired months; they were not executed.
- **Session clock (card C).** Weekend hours are narrower than the same hour on Tuesday–Thursday by about 0.4 comparator-SD, with a very small p, and the gap widened each year (−0.19 in 2020 to −0.65 in 2024; heterogeneity p 0.0005, no opposite-sign year, recorded `MAGNITUDE_VARIES_BY_EPOCH` and `NOT_ASSESSABLE` under the frozen compiler rule). Under the frozen bar this is below product relevance, so the class is `NO_INCREMENTAL_STRUCTURE`. It is not rescued here. The Monday US-open and Friday US-close hours show nothing.

## Nuisance diagnostic (wording only)

| ID | Raw | Adjusted (prior 24h RV, lagged target) | Retention | Wording |
|---|---|---|---|---|
| A1 | +0.077 | +0.013 | 0.16 | reflects the general volatility regime |
| A4 | +0.067 | −0.004 | −0.06 | reflects the general volatility regime |
| B2 | +0.037 | −0.173 | −4.7 | reflects the general volatility regime |
| C1 | −0.396 | −0.104 | 0.26 | reflects the general volatility regime |
| C2 | +0.066 | +0.220 | 3.3 | state-specific beyond the volatility regime |
| C4 | −0.123 | −0.110 | 0.90 | state-specific beyond the volatility regime |

Two caveats on the diagnostic, stated so they are not mistaken for findings: for C1 the lagged target of a Sunday hour is the Saturday hour, so the adjustment partly conditions on the state itself; for B2 and C2 the adjusted estimate moves away from zero. None of this changes a class: the diagnostic decides wording, not gates, and the primary gates failed on the raw comparator.

## Epoch record (descriptive; `NOT_ASSESSABLE` for every cell)

| ID | 2020 | 2021 | 2022 | 2023 | 2024 | Q-test p |
|---|---|---|---|---|---|---|
| A1 | +0.18 | +0.23 | +0.03 | +0.05 | −0.10 | 0.75 |
| A4 | +0.25 | +0.01 | −0.01 | +0.14 | −0.05 | 0.70 |
| B2 | −0.09 | −0.12 | +0.16 | +0.12 | +0.06 | 0.60 |
| C1 | −0.19 | −0.21 | −0.43 | −0.49 | −0.65 | 0.0005 |
| C2 | +0.04 | −0.03 | +0.04 | +0.16 | +0.12 | 0.96 |
| C4 | +0.12 | −0.09 | −0.23 | −0.14 | −0.25 | 0.72 |

## What this result is not

- Not a trading edge, not a direction, not a cause, not a probability.
- Not a rescue surface: no threshold, horizon, bar, unit or comparator may be changed for these twelve ids. A later weekend-structure or settlement-clock question is a new search object with its own test family and a surface it has not seen.
- The BitMEX 2017–2019 replication surface was declared but no outcome on it was opened; it remains unconsumed for these rules.
- The 2025/2026 surfaces were not touched.

## Product note (descriptive, allowed by the frozen interpretation)

The one effect with a clear signal, weekend hours, says that a same-hour baseline that mixes weekdays and weekends is mis-calibrated for the beta's unusual-hour flags by roughly 0.4 SD in 2020–2024 and more recently by more. That is a baseline-construction observation for the product, not a claim about what the market will do. Any product change from it goes through the product-first decision, not through this record.
