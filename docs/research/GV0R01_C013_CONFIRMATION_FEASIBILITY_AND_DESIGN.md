# GV0R01-C013 independent confirmation — feasibility and design

**Unit:** `GV0R01_C013_CONFIRMATION_FEASIBILITY_AND_DESIGN`
**Kind:** outcome-blind confirmation feasibility and design
**Date:** 2026-09-25
**Machine-readable twin:** `docs/research/GV0R01_C013_CONFIRMATION_FEASIBILITY_AND_DESIGN.json`
**Power record:** `docs/research/GV0R01_C013_CONFIRMATION_POWER.json`, produced by `scripts/research/gv0r01_c013_confirmation_power.py`

No confirmation was executed and no protected value was opened. No permit was created and nothing was armed. The discovery result is unchanged. No provider was called.

## Verdict

| Field | Value |
|---|---|
| Hypothesis | GV0R01-C013 |
| Discovery test | `TF-GV0R01-C013-MT1`: `PROMISING_PROTOTYPE`, discovery tier, consumed |
| Reserved confirmation family | `TF-GV0R01-C013-CONF1` (not registered in the ledger) |
| `FRESH_SURFACE_DECISION` | `WAIT_FOR_MORE_FRESH_DATA` |
| `CONFIRMATION_FEASIBILITY` | `UNDERPOWERED_ON_EVERY_AVAILABLE_OR_FORESEEABLE_FRESH_SURFACE` |
| Minimum acceptable power | 0.80 (statistical + direction, at the assumed effect) |
| Fresh weeks for 0.80 at the discovery effect | about 468 (9 years); the full-pass upper bound stays below 0.80 up to 780 weeks |
| Prereg / harness / permit | not created |
| 2025 and 2026 | sealed and unspent |
| Next unit | `POST_GV0R01_C013_CONFIRMATION_FEASIBILITY_PROGRAM_DECISION` |

## Why

The discovery weekly series is dominated by year-level heterogeneity. The exposed yearly means are −0.0691, −0.0677, −0.0307, +0.0315 and +0.0363, with a between-year sd of about 0.049. That is 2.5 times the pooled discovery effect of −0.0199.

On any fresh surface of one or two years, the pooled statistic is mostly "which kind of year was it". The 2023–2024 sign reversal is treated as prior evidence of instability. It is not explained away, not dropped, and not turned into a regime filter.

### Power

Power uses only the exposed 2020–2024 series, which is the discovery result's stored weekly primary and adjacency series. No market data and no 2025/2026 data were used. The simulations use seed `7378747926481491535` and 20,000 replicates.

- **Authoritative method.** Whole exposed 52-week years sampled with replacement, plus one contiguous partial block, re-centred to the assumed effect. This keeps within-year serial dependence and the observed between-year spread.
- **Sensitivity.** Moving-block bootstraps with 13- and 26-week blocks.
- **Diagnostic only.** IID resampling.

Statistical + direction power under the authoritative method, with the full-pass upper bound (which excludes the control gate) in parentheses:

| Surface (weeks) | Discovery effect −0.0199 | 50% attenuated −0.0100 | Discovery-consistent minimum −0.0067 |
|---|---|---|---|
| 2025 only (51) | 0.600 (0.600) | 0.594 (0.497) | 0.599 (0.393) |
| 2025 + 2026 to 2026-08-30 (86) | 0.524 (0.476) | 0.499 (0.363) | 0.472 (0.349) |
| Full 2025–2026 (103) | 0.687 (0.367) | 0.358 (0.358) | 0.358 (0.358) |

- **Direction stability.** The probability of a negative pooled sign is 0.60 for 2025 only and 0.73 for 2025–2026 at the discovery effect.
- **Dependence gate.** Its power is 0.60 for 2025 only and 0.37 for 2025–2026.
- **Moving-block, 26 weeks.** At the discovery effect this gives 0.53 for 2025 only and 0.64 for 2025–2026.
- **IID diagnostic.** It gives 0.83 for 2025–2026 at the discovery effect. That figure ignores dependence and is not authoritative.

Caveats:
- Only five exposed years exist, so year-block estimates for surfaces of one year or less are quantized near multiples of 0.2.
- The controlled statistic cannot be simulated, because no controlled weekly series is stored. Full-pass values are therefore upper bounds.

The discovery-consistent minimum is the smallest magnitude the discovery supports at one-sided 95%: |pooled| − 1.645 × HAC SE. It was chosen by that reasoning, not to reach any power target.

**Finding.** Under the observed heterogeneity, the frozen within-date permutation gate passes almost every simulated single year, in either direction. That null does not model between-year variance. Direction and the HAC dependence gate are what actually bind, so any future confirmation must keep both as necessary conditions.

### Surfaces

| Surface | Decision dates | Status |
|---|---|---|
| A. 2025 only | 2025-01-06..2025-12-28 (51 weeks, 357 days) | underpowered |
| B1. 2025 + 2026 prefix | 2025-01-06..2026-08-30 (86 weeks, 602 days; latest complete week covered by published monthly files) | underpowered |
| B2. Full 2025–2026 | 2025-01-06..2026-12-27 (103 weeks, 721 days) | underpowered, and not available until 2027 |
| C. Pre-2019-12 Binance spot | — | not equivalent. Fewer than 50 USDT symbols have monthly files before 2019-07 (raw counts), which leaves at most about two months of an N=50 universe. No other catalogued panel is equivalent. |

Spending 2025 and 2026 on a knowingly weak confirmation would consume the only protected fresh surface for an uninformative answer. Both stay sealed.

## Protected-data boundary

The feasibility check was metadata only. It made 735 S3 ListBucket requests, one per enumerated USDT symbol's 1d monthly prefix, returning key names and sizes.
- 0 payload GETs.
- 0 checksum-sidecar GETs.
- 0 protected rows parsed.

Complete 2025 and 2026 monthly files exist through 2026-08, with 396 to 491 USDT symbols per month. No metadata binding was built, because no surface was chosen. A future prereg must bind every required object by its first-party checksum sidecar before any payload is opened.

## Design recorded for a future powered surface (not frozen)

These choices are recorded so a future prereg starts from them. Any change needs its own outcome-blind justification.

- **Primary.** Unchanged: K=5, H=1, N=50. The same CLV, WICK_RESID, trailing controls, ranking, top-50 liquidity selection, exclusions, 35-day listing age, weekly aggregation and negative direction. The seven secondary discovery variants can never become the confirmatory primary.
- **Gates.**
  - Statistical: permutation p ≤ 0.05, two-sided, with a new frozen seed.
  - Direction: pooled < 0.
  - Control: the controlled statistic has p ≤ 0.05 and is negative.
  - Dependence: Newey–West t ≤ −1.96, lag floor(4·(W/100)^(2/9)).
  - Adjacency: the bar t+1 statistic is negative.
  - Temporal: at least 60% of consecutive 26-week blocks are negative. This replaces the discovery's 3-of-5-year gate, which is undefined on a short surface, and must be re-derived for the actual surface length.
- **Warm-up.** Predictor and universe warm-up bars may predate the fresh surface. No discovery target is reused.
- **Labels.** `INVALID_CONFIRMATION_EXECUTION` / `INCONCLUSIVE_CONFIRMATION` / `CONFIRMED_ON_INDEPENDENT_SURFACE` / `NOT_CONFIRMED_ON_INDEPENDENT_SURFACE`. A nominal p-value alone is never enough, and no secondary diagnostic can rescue a failure.
- **Combination.** Discovery `PROMISING_PROTOTYPE` plus `CONFIRMED_ON_INDEPENDENT_SURFACE` gives `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE` (the existing label, as used for D2). That is still not a trading or profitability claim. `NOT_CONFIRMED` closes the exact C013 confirmatory claim, with no parameter, horizon, sign or regime rescue.
- **Tick size.** No point-in-time tick-size history is catalogued, so this remains a declared limitation. No tick-size filter is applied.

## Accounting

`SCIENTIFIC_TEST_LEDGER.json` is unchanged. No confirmation test is registered, and `EXECUTED_TESTS` stays at 1. Generator V0 memory is unchanged.
