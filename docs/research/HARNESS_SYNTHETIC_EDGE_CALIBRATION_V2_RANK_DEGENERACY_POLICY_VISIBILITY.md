# V2 GROUND_TRUTH_VISIBLE plumbing

**Status:** `AUTHENTICATED_CONTROL_CALIBRATION_VISIBILITY_EVIDENCE` at HEAD;
historical canonical visibility remains immutable at ARM
`710cad607ec6740e550698cdc212f7dd33004481` / SHA256 `9be8dceb…`.

HEAD `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json`
is the control-calibration run's own `GROUND_TRUTH_VISIBLE` evidence:

```text
ARM            = 710cad607ec6740e550698cdc212f7dd33004481
RUN_IDENTITY   = 90d38af4951b0bbe00fc5ffaf7989c8940d178c31aad987176901c7ce947ad1e
PLAN_SHA       = b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f
WORLD_RECORDS  = e8667f930a4acc7fb5dd26fa62414a8f4b359121336902aac651cb76f4e50dbf
INNER_RECORDS  = f0d18ca1c8ed654856abca03d9e0f8d22b72ab5f6f4683cc11e45f3353bc0559
VISIBILITY     = ed1c17f0e2eb8f04ed917a7c84811d10a0d152f770a9315d2ade1cac1be93f9b
```

The previous canonical V2 visibility artifact remains historical evidence
and is not reinterpreted:

```text
HISTORICAL_VISIBILITY     = 9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65
HISTORICAL_WORLD_RECORDS  = d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821
HISTORICAL_INNER_RECORDS  = 763a8ce802b7b5efa133ebe3132103cbb96c86d83c7c2dacc992147c8ee4ef66
```

**Independent review of the plumbing module:** `GO_FOR_RESULT_MINT`.
Per-world `GROUND_TRUTH_VISIBLE` uses the frozen V1 statistic. This file is
not itself a RESULT.

The formula below is unchanged.

Canonical WORLD_RECORDS of the *historical* V2 run remain immutable evidence:

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
