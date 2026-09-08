# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — Fixture implementation review

**Status:** `FIXTURE_IMPLEMENTATION_EXISTS_EXECUTION_UNAUTHORIZED`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`  
**Frozen prereg:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md) / [`.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json)  
**Prereg scientific status:** `FROZEN_BEFORE_IMPLEMENTATION` (bytes unchanged by this implementation stage)

This document records implementation-review state only. It does not rewrite frozen DGP, scenarios, thresholds, Wilson rules, or conclusion mapping.

```text
implementation_exists = true
synthetic_execution_authorized = false
production_calibration_executed = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

Code:

- `scripts/research/harness_synthetic_edge_calibration_v1_lib.py`
- `scripts/research/harness_synthetic_edge_calibration_v1.py`
- `tests/research/test_harness_synthetic_edge_calibration_v1.py`

The CLI and `run_frozen_production_grid` fail closed with `SYNTHETIC_EXECUTION_NOT_AUTHORIZED`. There is no environment-variable or `authorized=True` bypass. Tiny fixture configs are a separate type and cannot encode the frozen 3200-world production grid.

Fixture envelope (fail-closed OR): `n_rows <= 500`, each fixture replicate count `<= 50`, and explicit refusal of production N `{2500, 5000, 10000}` and of any replicate count reaching frozen production authority.

This stage does not produce a RESULT, does not inspect calibration outcomes, and does not authorize B2-06.

## Known review debt (MINORs not repaired in this focused pass)

Independent implementation review also reported non-blocking MINORs that this repair does not redesign:

- prereg constant representation;
- aggregation layer;
- chronology architecture;
- root-seed fixture ergonomics;
- `small_band`;
- ragged-era policy;
- N_eff;
- DGP draw-order specification.

MIN-8 (missing regression coverage for visibility diagnostic/world-validity asymmetry and near-production fixture-guard evasion) is closed by the focused tests in `tests/research/test_harness_synthetic_edge_calibration_v1.py`.
