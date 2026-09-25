# GV0R01-C013 market test — preregistration V1

**Status:** `FROZEN_PREREGISTRATION_NOT_EXECUTED`
**Date:** 2026-09-25
**Authority:** `docs/research/GV0R01_C013_MARKET_TEST_PREREG.json` (this file is its summary)
**Prereg SHA256:** `49dff57b3e068d999c9c4467fb5117de9d73ad564425bf737df727a1096f7625`
**Test family:** `TF-GV0R01-C013-MT1`
**Search family:** `SF-GENERATOR_V0-GV0R01`
**Ledger:** `docs/research/SCIENTIFIC_TEST_LEDGER.json`

`EXECUTION_AUTHORIZED = false`. No outcome was computed. This design did not compute any forward wick, Spearman statistic, p-value, yearly sign or classification. Protected 2025/2026 data stay sealed. `CONSUMED` in Generator V0 memory is a governance region state only; it is not scientific support.

## Source

The scientific source authority is the exact card GV0R01-C013 as persisted in the sealed journal `docs/research/generator_v0_gv0r01/run.sqlite`. Details:
- call key `a6fa912f…`, round generation:1;
- canonical card SHA256 recorded in the JSON;
- card copied verbatim into `CARD_VERBATIM`.

The design base is HEAD `f428edec8bdcc9ddaf4ed6e73b9bd522219832bd`, tree `5a46326484de7c531c018e46a3b1dfb7b8bdb4ff`.

## Data and time

- Dataset `SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0`, fields open, high, low, close and quote volume.
- Snapshot `fdd698c6…`, file ledger digest `fc38ea13…`, exclusion list digest `35779ca5…`.
- The raw zips are gitignored. They are restored and verified against the frozen object ledger at execute time.
- Decision days run from 2020-01-06 to 2024-12-29 (1820 days). That is 260 ISO weeks, Monday 2020-01-06 to Monday 2024-12-23, 52 weeks in each year 2020–2024. December 2019 is warm-up only.
- No bar after 2024-12-31 is ever needed.
- Point in time: a bar for day d is available at d+1 00:00 UTC. At decision time t, predictor, controls and universe use only bars d ≤ t−1. The target uses bars from t onward. No bar is shared between the two sides.

## Frozen design

| Item | Frozen value |
|---|---|
| Universe | Top 50 eligible names by quote volume over [t−30, t−1]; ties broken by symbol. Later-delisted names are included. Pinned Sprint 04 exclusions apply. Listing age must be at least 35 days. The K predictor bars must be present and well-formed, with at least one non-zero range. |
| Predictor | CLV_K = mean over bars t−5..t−1 with H>L of (2C−H−L)/(H−L). Ranked within the analysis set; tied ranks are averaged. |
| Target | WICK = Σ over target bars of [ln(H/O) − ln(O/L)], horizon H=1 (bar t). |
| Residualization | WICK_RESID = OLS residual of WICK on [1, ln(C/O), ln(H/L)] of the same window, across the analysis set. |
| Daily statistic | Spearman correlation between rank of CLV and rank of WICK_RESID over the analysis set. The analysis set needs at least 45 names with a valid target. |
| Weekly / pooled | ISO-week mean of valid days (at least 5 valid days per week). Pooled value is the equal-weight mean of valid weeks. No Fisher transform. |
| Null | 1000 within-date permutations of rank(CLV) inside quote-volume terciles. Seed `639284419827364414`, derived as sha256 of `GV0R01-C013\|MARKET_TEST_V1\|PERMUTATION_NULL`. Generator is PCG64 via `SeedSequence([seed, variant, date ordinal])`, with numpy 2.1.3. |
| p-value | Two-sided rank p with +1 correction. The result is outside the central 95% of the null exactly when p ≤ 0.05. |
| Direction | Negative. By the card's own algebra, WICK_RESID is range-weighted future close location with its sign flipped, so persistence predicts ρ < 0. |
| Controls (card falsifier 3) | Partial rank correlation after removing rank of trailing ln(C/O), rank of trailing ln(H/L) and rank of trailing quote volume (the card's baseline controls). Its null uses the same permutation indices applied to the residualized predictor. |
| Year stability | At least 3 of the 5 yearly means (years 2020–2024, by week Monday) strictly share the pooled sign. |

### Primary variant (approach A)

The card allows K∈{1,5}, H∈{1,5}, N∈{50,100}. One primary variant is fixed by rules that do not depend on outcomes:
- **N=50.** It is the only card value that gives a constant cross-section on every date. Fewer than 100 names are eligible in early 2020.
- **H=1.** Target windows on consecutive dates do not overlap.
- **K=5.** The card claims a persistent state. A 5-day window also dilutes the close(t−1)/open(t) adjacency to one fifth.

The other 7 variants form a descriptive grid. Each gets a permutation p-value with Holm adjustment, and none can change the classification.

## Gates and classification

This design reuses the discovery taxonomy (`classify_from_summary`). The classification rule, applied in order:
1. `INVALID_DISCOVERY` if identity fails.
2. Otherwise `INCONCLUSIVE_DISCOVERY` if support fails. Support requires at least 250/260 valid weeks, at least 48 valid weeks in each year, and a missing-target rate of at most 2%.
3. Otherwise `PROMISING_PROTOTYPE` only if all six gates pass:
   - **STATISTICAL:** p ≤ 0.05 (card falsifier 1).
   - **DIRECTION:** pooled ρ < 0.
   - **TEMPORAL:** at least 3 of 5 years share the pooled sign (card falsifier 2).
   - **CONTROL:** the controlled statistic has p ≤ 0.05 and the same sign (card falsifier 3).
   - **DEPENDENCE:** Newey–West t of the weekly series, lag 4, has |t| ≥ 1.96 with the same sign.
   - **ADJACENCY:** the same predictor against the target bar t+1 has the same sign.
4. Otherwise `NO_USEFUL_STRUCTURE`. Its reasons list every failed gate. A significant wrong-sign result is labelled `OPPOSITE_DIRECTION_OUTSIDE_NULL`.

The DEPENDENCE and ADJACENCY gates were added in the pre-outcome adversarial review. They can only narrow support. A nominal p-value alone is never sufficient. There is no post-run change to the horizon, lookback, universe, strata, controls, years or sign, no promotion of a secondary variant, and no rerun.

Mapping to plain vocabulary:
- `PROMISING_PROTOTYPE` means SUPPORTED at discovery tier.
- `NO_USEFUL_STRUCTURE` means NO_EVIDENCE, or CONTRADICTED when the result is a significant opposite sign.
- `INCONCLUSIVE_DISCOVERY` means INCONCLUSIVE_SAMPLE.
- `INVALID_DISCOVERY` means INVALID_TEST.

Even `PROMISING_PROTOTYPE` only earns an independent confirmation. It is not a validated edge, and no trading or profitability claim is made.

## Multiplicity

`PRIMARY_TEST_COUNT = 1`, `SECONDARY_TEST_COUNT = 7`.
- The primary is tested at α = 0.05, two-sided.
- The gates form an intersection–union conjunction on that one hypothesis.
- The secondary grid is descriptive, with Holm adjustment.

The 30 GV0R01 generated cards are not market tests. This is test 1 of `SF-GENERATOR_V0-GV0R01`, registered in `SCIENTIFIC_TEST_LEDGER.json` before any outcome. Disclosure: D13 used the same panel for weekly close-to-close relative returns. This design did not read D13's outcome numbers.

## Adversarial review

These issues are resolved in the JSON `ADVERSARIAL_REVIEW` section:
- lookahead;
- overlapping horizons;
- survivorship;
- listing age;
- liquidity selection;
- cross-sectional dependence;
- unstable universe;
- calendar artifacts;
- mechanical OHLC identities;
- return/wick coupling;
- same-bar contamination;
- researcher degrees of freedom.

Tick-size discreteness (card confounder 1) is a declared limitation, since no tick-size data is catalogued. No outcome-motivated filter is added. `AMENDMENT_REQUIRED = false`.

## Harness, preflight and execution

- Library: `scripts/research/gv0r01_c013_market_test_lib.py`. It holds pure functions and reads no files.
- Runner: `scripts/research/gv0r01_c013_market_test.py`.
- Tests: `tests/research/test_gv0r01_c013_market_test.py`. These are synthetic random-walk panels only, with no planted real-data outcome.

```bash
python -m scripts.research.gv0r01_c013_market_test preflight   # offline, no target
python -m scripts.research.gv0r01_c013_market_test execute     # refuses without a permit
```

Preflight verifies:
- the prereg digest against the ledger, and that the test family is unused;
- the digests of the implementation and the Sprint 04 loaders;
- the seed, permutation count and time range;
- protected-data exclusion and the numpy version;
- the dataset ledger and exclusion/universe identity files;
- that no result file exists;
- that the scientific paths are clean.

Execute also requires two more things. First, an owner permit `docs/research/GV0R01_C013_MARKET_TEST_EXECUTION_PERMIT.json` bound to this prereg digest. Second, restored local bytes that match the object ledger. The result is written once, with exclusive create, to `docs/research/GV0R01_C013_MARKET_TEST_RESULT.json`. The ledger entry is then closed and the test family is consumed.
