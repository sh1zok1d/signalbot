# V2 GROUND_TRUTH_VISIBLE plumbing

**Status:** `VISIBILITY_PLUMBING_AWAITING_INDEPENDENT_REVIEW`

**Not a RESULT. Not a second canonical execution. Not a methodology amendment.**

This unit supplies the already pre-outcome-defined `GROUND_TRUTH_VISIBLE`
input required by frozen Amendment_003 visibility-dependent conclusions.
It does not rerun V2 candidate evaluation, replace WORLD_RECORDS, create a
reservation, or mint RESULT.

Canonical WORLD_RECORDS remain immutable evidence:

```text
WORLD_RECORDS_PATH = docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_WORLD_RECORDS.json
WORLD_RECORDS_SHA256 = d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821
INNER_RECORDS_SHA256 = 763a8ce802b7b5efa133ebe3132103cbb96c86d83c7c2dacc992147c8ee4ef66
```

Visibility evidence path:

[`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json)

## Frozen formula (unchanged)

```text
BASE_PRED = expanding OLS on X1, X2 only
VISIBILITY_STAT = mean(Y-BASE_PRED | S=1) - mean(Y-BASE_PRED | S=0)
GROUND_TRUTH_VISIBLE = q025 > 0
replicates = 500
block_rows = 50
rng = PCG64(namespace_seed(world_seed(world_identity), "VISIBILITY"))
invalid replicate => not visible
```

Authority: V1 prereg §10, frozen `visibility_from_residuals`, V1 production
`evaluate_production_candidate` / `_oracle_visible`, Amendment_003
`VISIBILITY_FLOOR` and `TINY_NOISY_ORACLE_DIAGNOSTIC`.

`production.py` and `inherited_ladder.py` remain ARM-bound live bytes.
Result derivation consumes this evidence through
`scripts/research/harness_synthetic_edge_calibration_v2_visibility.py`.
Canonical RESULT is not minted by this unit.
