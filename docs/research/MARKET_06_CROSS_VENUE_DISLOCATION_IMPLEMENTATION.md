# MARKET-06 CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK — implementation identity

- **Status:** `IMPLEMENTED_OUTCOME_BLIND_NOT_EXECUTED`
- **Unit ID:** `MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION`
- **Research ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-21

**Not a RESULT. Not an ARM. Not MARKET-06 execution. Not outcome
inspection. Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This unit implements the live frozen MARKET-06 contract after
pre-outcome amendment 002. Scientific authority remains the frozen
preregistration bytes. This file does not authorize canonical
execution.

```text
IMPLEMENTATION_ID = MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION
PREREG_FREEZE_HEAD = e2d543eadb5425473b6d4b8d24c177c1d7ae7930
PREREG_FREEZE_TREE = a1706c775154fc65ad1d5eaaa5818f87b834a2b7
PREREG_CONTENT_HEAD = 6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59
PREREG_CONTENT_TREE = 11658516cab22774501daa8e2e966c9a8861c9a3
V0 / Amendment-001 preregs = HISTORICAL ONLY (not implemented)
```

Canonical evaluation of retained `MARKET_06_OKX_BINANCE_FEASIBILITY_V0`
bytes is refused. No ARM. No RESULT.

Machine-readable twin:
`docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION.json`.

---

## Modules

- `scripts/research/market_06_cross_venue_dislocation_authority.py`
- `scripts/research/market_06_cross_venue_dislocation_parsers.py`
- `scripts/research/market_06_cross_venue_dislocation_bootstrap.py`
- `scripts/research/market_06_cross_venue_dislocation_evaluator.py`
- `scripts/research/market_06_cross_venue_dislocation_runner.py`

Allowed sampler: `year_stratified_predictive_resample` from
`scripts/research/market_06_year_stratified_circular_mbb.py`.
Production modules must not import `concatenated_then_sample`.

---

## Frozen numerical convention

```text
TRAIN_SD_CONVENTION = numpy.std(x, ddof=0)
```

Population SD. Positive rescaling of a regressor leaves OLS predictions
and the sign of its coefficient invariant, so this convention cannot
change eligibility, gates, or final classification under the frozen
predicates. Zero or non-finite train SD is `MARKET_06_INCOMPLETE_EXECUTION`.

---

## RNG consumption order

One `numpy.random.Generator(numpy.random.PCG64(2026092106))`:

1. coefficient bootstrap, all 5000 TRAIN circular-MBB replicates;
2. predictive bootstrap, all 5000 replicates;
3. within every predictive replicate: sample 2023 first, then 2024.

No reroll. No predictive-model refit.

---

## Explicit state

```text
market_06_implemented                     = true
market_06_implementation_frozen           = false  (freeze is a later commit)
market_06_executed                        = false
market_06_armed                           = false
market_06_result_created                  = false
real_canonical_execution_refused          = true
scientific_outcomes_inspected             = false
protected_oos_authorized                  = false
2025_opened                               = false
2026_opened                               = false
```

---

## Next lifecycle state

```text
NEXT_UNIT = MARKET_06_IMPLEMENTATION_FREEZE
```

After freeze: `MARKET_06_IMPLEMENTATION_RED_TEAM_REVIEW`.
Not execution. Not ARM.
