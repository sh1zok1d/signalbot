# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — one-shot execution authorization

**Status:** `ONE_SHOT_SYNTHETIC_EXECUTION_AUTHORIZATION_READY_FOR_REDTEAM`  
**Machine authority:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json)

This document is not a RESULT, not a methodology verdict, and not market evidence.

```text
implementation frozen = YES
synthetic one-shot execution authorized = YES
production execution performed = NO
authorization consumed = NO
real-market access = NO
B2-06 execution = NO
2025 validation = NO
2026 OOS = NO
```

Permission is exactly one production calibration of the already frozen instrument. Authority is the tracked JSON blob in Git HEAD, plus independently verified prereg bytes and frozen implementation ancestry. Caller kwargs, environment variables, and alternate paths cannot authorize.

Consumption is not recorded in this authorization PR. A later immutable execution claim at `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json` is the durable transition to `AUTHORIZATION_CONSUMED`. A second production run using the same authorization must fail closed.

The Monte Carlo seam is reached after a minted proof and is not armed here. This PR does not run 3200 worlds.
