# MARKET-06 preregistration amendment 002

- **Status:** `PRE_OUTCOME_AMENDMENT`
- **Unit ID:** `MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002`
- **Research ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-21
- **Machine-readable twin:** [`MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002.json`](MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002.json)

**Not a RESULT. Not an ARM. Not execution. Not an evaluator.**

This is a legal **pre-outcome** correction of predictive-bootstrap
sampling structure. No MARKET outcomes, OHLC-derived values,
dislocation values, eligible-row counts, MAE, coefficients, or holdout
metrics were inspected.

```text
AMENDMENT_REASON = PRE_OUTCOME_PREDICTIVE_BOOTSTRAP_STRATIFICATION_CORRECTION
OUTCOMES_INSPECTED_BEFORE_AMENDMENT = false
OLD_LIVE_PREREG_HEAD  = b4459ab96addd6c39d4baec35248410a8f5cf8e0
OLD_LIVE_FREEZE_HEAD  = 371f71dd49e2c2c445269aeed1b75a39f33b3422
```

Amendment 001 and V0 remain historical evidence. Exact Amendment-001
live bytes are retained as:

- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V1.md`
- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V1.json`
- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V1.md`
- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V1.json`

Those V1 files are **not** live scientific authority.

---

## What changed

Amendment 001 (and V0) resampled the **concatenated** 2023+2024 holdout
sequence with one circular moving-block bootstrap. That allowed a block
to cross the calendar-year boundary and did not preserve `N_2023` and
`N_2024` inside each replicate.

Amended predictive bootstrap:

```text
PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR = true
CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED = false
YEAR_SAMPLE_SIZE_PRESERVED_PER_REPLICATE = true
PREDICTIVE_MODEL_REFIT_IN_BOOTSTRAP = false
PREDICTIVE_BOOTSTRAP_2023_N = original eligible N_2023
PREDICTIVE_BOOTSTRAP_2024_N = original eligible N_2024
```

Models remain fit once on 2022 TRAIN. For each of 5000 replicates:

1. circular MBB **only** on 2023 holdout tuples, wrap only within 2023,
   trim the final block to exactly `N_2023`;
2. independently, circular MBB **only** on 2024 holdout tuples, wrap
   only within 2024, trim the final block to exactly `N_2024`;
3. concatenate bootstrapped 2023 then bootstrapped 2024;
4. compute `RELATIVE_MAE_IMPROVEMENT_REP` from that concatenated
   replicate.

Coefficient bootstrap on TRAIN is unchanged.

---

## What did not change (Amendment 001 F1–F4 preserved)

```text
ROBUST_SCALE_T = 1.4826 * MAD_T
BASELINE  = Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H
CANDIDATE = Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H + ABS_DISLOCATION_Z
Y_T = arithmetic fractional adverse excursion
GATE_2_EXACT_PREDICATE = BETA_ABS_DISLOCATION_Z_CI95_LOW > 0
```

Sources, snapshot, durable root, `00:05`, `T-5m`, 8640 refs, 288 bars,
train/holdout dates, no Dec 31, OLS, train-only standardization, 14-day
blocks, 5000 reps, seed `2026092106`, 2% materiality, six gates, G6,
2025/2026 protection, and no-rescue remain frozen.

```text
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_EXECUTED = false
MARKET_06_ARMED = false
MARKET_06_RESULT_CREATED = false
NEXT_UNIT = MARKET_06_PREREG_FREEZE
```
