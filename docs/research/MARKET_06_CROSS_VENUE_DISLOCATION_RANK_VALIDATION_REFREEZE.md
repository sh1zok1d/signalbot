# MARKET-06 — Refreeze after explicit rank-validation repair

Status: `RANK_VALIDATION_REPAIRED_AND_REFROZEN_OUTCOME_BLIND`
Date: 2026-09-21

Supersedes `MARKET_06_CROSS_VENUE_DISLOCATION_LIFECYCLE_REFREEZE.json`
(implementation `0ff43e6`, freeze `c435158`), which remains historical
evidence for the commit it describes.

## Bound authority

- Repaired implementation head: `176dc6c817c1b2949d44a8d44855220c8759bc44`
- Repaired implementation tree: `04965d6faaf4e6f0387ccdf082f897f555f38aba`
- Live prereg freeze: `e2d543eadb5425473b6d4b8d24c177c1d7ae7930` (**unamended**)
- Canonical data source commit: `e2d543eadb5425473b6d4b8d24c177c1d7ae7930`
- Dataset `MARKET_06_OKX_BINANCE_FEASIBILITY_V0`, snapshot `e0403e40…183e68`,
  durable root `f4b9e16a…0cdc6f`
- Ten MARKET-06 modules bound by SHA-256 (exact digests in the JSON twin)

## RUN_IDENTITY changed

```
old = 28cfa4884b638f91dd1074e93673ed37215d42334eef1746c89967f4a356a88f
new = f3aa51372594d710a8f705d761d857f8385d0b848fb0ed59a36b27a16ce25c22
```

RUN_IDENTITY is a content hash over the module inventory, and this repair
changed the bootstrap/OLS module bytes, so the change is necessary and
expected.

**Consequence:** the two abandoned pre-repair authority commits — ARM
`2884d5a1c4e9d99f6f77a6a1de7695da27893498` and reservation
`67bbea0e554036eced53ff19b4518d31217cb896` — bind the superseded value and
are **not reusable**. They were never pushed and never executed.

## Identifiability

```
EXPLICIT_MATRIX_RANK_VALIDATION = true
rank predicate  = numpy.linalg.matrix_rank(X.T @ X) == number_of_columns
rank deficient  -> MARKET_06_INCOMPLETE_EXECUTION
CUSTOM_RANK_TOLERANCE = false
CONDITION_NUMBER_GATE = false
LinAlgError second layer retained = true
F04_STATUS = HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE
```

The check runs in the single shared `ols_solve`, so it covers both the
original TRAIN fits and every coefficient-bootstrap refit. A rank-deficient
replicate aborts the whole execution — there is no redraw, skip, or
replacement replicate.

This closes rank deficiency **only**. It introduces no near-singularity
policy and no new numerical threshold.

## Unchanged

The hypothesis, bar-end semantics, `D_E`, the 8640 reference window, MAD ×
1.4826, `ABS_DISLOCATION_Z`, the BTC controls, RV-288, the outcome,
train/holdout splits, standardization, the regressors, the OLS equation
itself, the bootstrap, RNG and seed, the six gates, the 2% threshold, the
classification rules, the lifecycle, data authority, result persistence,
and 2025/2026 protection.

## Live state

No ARM, reservation, claim, or RESULT. Canonical execution refuses with
`MARKET_06_NO_TRACKED_CLAIM`. `scientific_outcomes_inspected = false`;
2025/2026 unopened.

Next lifecycle state: `MARKET_06_EXECUTION_AUTHORITY_CREATION`.
