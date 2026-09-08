# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — Fixture implementation review

**Status:** `IMPLEMENTATION_FROZEN_BEFORE_PRODUCTION_EXECUTION`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`  
**Frozen prereg:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md) / [`.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json)  
**Prereg scientific status:** `FROZEN_BEFORE_IMPLEMENTATION` (bytes unchanged by this implementation stage)

This document records implementation-review and freeze state only. It does not rewrite frozen DGP, scenarios, thresholds, Wilson rules, or conclusion mapping.

## Frozen implementation authority

```text
reviewed implementation HEAD = c996ba08c49961afde5daba2bd97832fded4725a
reviewed implementation tree = f8c239aafca06f807c02c38ed1a726d1dda9ee31
base = 1f72e505b283498ed6f05f48710e135409ea495b
focused independent review verdict = GO_FOR_IMPLEMENTATION_FREEZE
review blockers = 0
review majors = 0
exact reviewed-head CI run = 34229846184
exact reviewed-head CI conclusion = success
```

The implementation bytes reviewed above are frozen before any production synthetic execution. This freeze does not itself authorize execution. One-shot production authorization, if present, lives in the separate tracked artifact [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json) and does not rewrite this freeze record's scientific bytes.

```text
implementation_exists = true
implementation_frozen_before_production_execution = true
synthetic_execution_authorized = true   # one-shot tracked authorization; see EXECUTION_AUTHORIZATION.json
production_calibration_executed = false
authorization_consumed = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

Code:

- `scripts/research/harness_synthetic_edge_calibration_v1_lib.py`
- `scripts/research/harness_synthetic_edge_calibration_v1.py`
- `scripts/research/harness_synthetic_edge_calibration_v1_auth.py`
- `tests/research/test_harness_synthetic_edge_calibration_v1.py`

The CLI and `run_frozen_production_grid` fail closed with `SYNTHETIC_EXECUTION_NOT_AUTHORIZED`. There is no environment-variable or `authorized=True` bypass. Tiny fixture configs are a separate type and cannot encode the frozen 3200-world production grid.

Fixture envelope (fail-closed OR): `n_rows <= 500`, each fixture replicate count `<= 50`, and explicit refusal of production N `{2500, 5000, 10000}` and of any replicate count reaching frozen production authority.

This stage does not produce a RESULT, does not inspect calibration outcomes, and does not authorize B2-06.

## Focused closure review

The prior independent implementation red-team reported two MAJOR findings and one associated regression-coverage MINOR relevant to freeze. The focused repair and independent closure review established:

- MAJ-1 visibility diagnostic/world-validity asymmetry: CLOSED;
- MAJ-2 fixture production-boundary bypass: CLOSED;
- MIN-8 regression coverage: CLOSED;
- scientific-core regression: NO;
- production execution locked: YES;
- frozen prereg unchanged: YES;
- final focused verdict: `GO_FOR_IMPLEMENTATION_FREEZE`.

## Known review debt (MINORs not repaired in this focused pass)

Independent implementation review also reported non-blocking MINORs that this freeze does not redesign:

- prereg constant representation;
- aggregation layer;
- chronology architecture;
- root-seed fixture ergonomics;
- `small_band`;
- ragged-era policy;
- N_eff;
- DGP draw-order specification.

These remain recorded debt and do not authorize any scientific or production boundary change.
