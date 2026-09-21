# MARKET-06 preregistration amendment 001

- **Status:** `PRE_OUTCOME_AMENDMENT`
- **Unit ID:** `MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001`
- **Research ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-21
- **Machine-readable twin:** [`MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001.json`](MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001.json)

**Not a RESULT. Not an ARM. Not execution. Not an evaluator.**

This is a legal **pre-outcome** correction of scientific-definition drift
in the first frozen MARKET-06 preregistration. No MARKET outcomes,
OHLC-derived values, dislocation values, eligible-row counts, MAE,
coefficients, or holdout metrics were inspected.

```text
AMENDMENT_REASON = PRE_OUTCOME_SCIENTIFIC_DEFINITION_DRIFT_CORRECTION
OUTCOMES_INSPECTED_BEFORE_AMENDMENT = false
OLD_PREREG_CONTENT_HEAD = b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1
OLD_FREEZE_HEAD         = 5f14411abc926a2b486d83de5b696ec3cf362488
```

Exact historical bytes are retained in-tree:

- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.md`
- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.json`
- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V0.md`
- `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V0.json`

Those V0 files are unmodified copies of the first freeze payload and
freeze authority. They are **not** live scientific authority.

After this amendment is materialized, a **separate** docs-only re-freeze
becomes sole live authority. The V0 freeze remains historical evidence
only.

---

## F1 — MAD normalization

V0 used raw MAD as the z-score denominator
(`mad_consistency_constant_1_4826 = false`).

Amended definition:

```text
CENTER_T = median(D_reference)
MAD_T    = median(abs(D_reference - CENTER_T))
ROBUST_SCALE_T = 1.4826 * MAD_T
MAD_T <= 0 => ROW_NOT_ELIGIBLE
DISLOCATION_Z_T = (D_E - CENTER_T) / ROBUST_SCALE_T
ABS_DISLOCATION_Z_T = abs(DISLOCATION_Z_T)
MAD_CONSISTENCY_CONSTANT = 1.4826
MAD_CONSISTENCY_CONSTANT_ENABLED = true
```

Do not use raw MAD as the denominator.

---

## F2 — BTC baseline control

V0 used `ABS_Z_BTC = abs(BTC_RET_24H / RV_BTC_24H)` as a regressor.

Amended controls: `BTC_SIDE`, `ABS_BTC_RET_24H`, `RV_BTC_24H`.
No `ABS_Z_BTC` regressor.

```text
BASELINE  = Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H
CANDIDATE = Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H + ABS_DISLOCATION_Z
```

---

## F3 — Adverse-path outcome scale

V0 used logarithmic adverse excursion
(`ln(ENTRY / min_low)` / `ln(max_high / ENTRY)`).

Amended outcome is arithmetic fractional excursion. Name remains
`24H_DIRECTION_ALIGNED_BTC_MAE`. `Y_T >= 0`.

```text
ENTRY_PRICE = open of Binance perpetual 5m bar with bar_start == T
BTC_SIDE = +1: Y_T = max(0, (ENTRY_PRICE - min(FUTURE_LOW)) / ENTRY_PRICE)
BTC_SIDE = -1: Y_T = max(0, (max(FUTURE_HIGH) - ENTRY_PRICE) / ENTRY_PRICE)
```

---

## F4 — Gate 2 CI direction

V0 used the 95% bootstrap **upper** confidence bound for beta > 0.

Amended predicate uses the **lower** bound:

```text
GATE_2_DIRECTION_UNCERTAINTY = 95% bootstrap LOWER confidence bound
                               for BETA_ABS_DISLOCATION_Z > 0
GATE_2_EXACT_PREDICATE = BETA_ABS_DISLOCATION_Z_CI95_LOW > 0
```

---

## Unchanged

Identity, sources, snapshot, durable root, 5m grain, daily `00:05`,
`FEATURE_CUTOFF = T-5m`, 8640 refs excluding `D_E`, primary feature
`ABS_DISLOCATION_Z`, expected beta sign positive, 24h / 288-bar
horizon, train/holdout calendar, Dec 31 exclusion, no-refit, OLS, MAE
prediction metric, 2% materiality, circular MBB 14/5000/seed
`2026092106`, six gates, 2025/2026 protection, no-rescue.

```text
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_EXECUTED = false
MARKET_06_ARMED = false
MARKET_06_RESULT_CREATED = false
NEXT_UNIT = MARKET_06_PREREG_FREEZE
```
