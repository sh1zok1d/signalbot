# D2 BitMEX replication implementation review

**Unit:** `D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`  
**Kind:** outcome-blind implementation review. **Not executed.**

## Lineage

The frozen prereg scientific contract is unchanged. The prereg-bound
evaluator SHA was a firewalled stub. This unit replaces that stub with a
reviewed execution implementation without inspecting BitMEX outcomes.

- `PREREG_SCIENTIFIC_CONTRACT` = `docs/research/D2_BITMEX_REPLICATION_PREREG.json`
- original stub SHA256 (`d2_bitmex_replication_evaluator.py`) =
  `e132f5ee24029b18aa971c4dda6a2e453282038a9527d8362d6656ecd40b75de`
- final reviewed SHA256 (`d2_bitmex_replication_evaluator.py`) =
  `087e7ea5892f2ab81f26bd61c82b2709b6812b6916554e5c92846a52496d77aa`

Scientific files `d2_bitmex_pre2020.py`, `common.py`, and
`market_06_cross_venue_dislocation_evaluator.py` are byte-identical to the
prereg-bound hashes.

## Identity

```
IMPLEMENTATION_REVIEW = PASS
EXECUTION_READY = True
EXECUTION_AUTHORIZED = False
EXPECTED_ELIGIBLE_N = 1069
FIRST_RULE_ELIGIBLE_T = 2017-01-24T00:05:00.000Z
LAST_RULE_ELIGIBLE_T = 2019-12-30T00:05:00.000Z
PREREG_ARTIFACT_SHA256 = 939fe29243956195f2ca97723a7b94b666ce59359c55e096f8fba4d65c7d9044
BITMEX_CANONICAL_SHA256 = b145013cbcda34294104a0234c89fa9e27965bded66e3bc18b23753dde03fd0f
RUN_IDENTITY = c56759992d28912128f4aaf7548b9ba27683bbdc76cf07a6794da61ae0cc1f88
RANDOM_SEED = 20260921125
N_CONTROLS = 10000
```

No execution permit exists. `execute_replication` fails closed.

## Red-team (F1–F14)

- `F1_LOOKAHEAD`: **NOT_CONFIRMED** — Features use frozen feature_cutoff E=T-5m and bars ending at E via construct_discovery_row.
- `F2_ENTRY_OVERLAP`: **NOT_CONFIRMED** — Entry uses get_perp_bar_opening_at(T). Feature close uses the bar that ended at E, a different open.
- `F3_OUTCOME_OVERLAP`: **NOT_CONFIRMED** — Future path is 288 bars opening at T, T+5m, ... through T+287*5m via frozen construct_discovery_row.
- `F4_BITMEX_TIMESTAMP`: **NOT_CONFIRMED** — Canonical rows are keyed by open_time_ms = official bucket-end timestamp minus 5m. Tests refuse keying by bucket end.
- `F5_GAP_LEAKAGE`: **NOT_CONFIRMED** — No fill. Missing feature or future open makes construct_discovery_row return None. Timestamp census still 1069.
- `F6_ROLLING_HISTORY`: **NOT_CONFIRMED** — rv_abstention_mask uses previous 250 valid constructed rows, not 250 calendar days. Warmup cannot abstain.
- `F7_PERCENTILE`: **NOT_CONFIRMED** — P90 of prior 250, t excluded, strict >. Equality does not fire.
- `F8_INVERSE_CONTRACT`: **NOT_CONFIRMED** — Severity is frozen arithmetic_mae last-trade price-path MAE, not inverse PnL, mark, index, or funding.
- `F9_COMPARATOR`: **NOT_CONFIRMED** — Controls draw exact K_y within each of 2017/2018/2019. Pooled-K sampling is not used.
- `F10_RNG`: **NOT_CONFIRMED** — numpy.random.Generator(numpy.random.PCG64(20260921125)). Matches frozen rate_matched_random_abstention masks.
- `F11_SAMPLE_DRIFT`: **NOT_CONFIRMED** — Timestamp census reproduces 1069 / 2017-01-24T00:05Z / 2019-12-30T00:05Z. Execution identity gate classifies INVALID on mismatch.
- `F12_RESULT_RESCUE`: **NOT_CONFIRMED** — classify_replication ignores yearly diagnostics. No 2/3-year gate. Discovery TEMPORAL_CONSISTENCY is not copied.
- `F13_AUTHORITY_DRIFT`: **NOT_CONFIRMED** — Sealed gz/jsonl/authority hashes fail closed. Reacquisition forbidden.
- `F14_ACCIDENTAL_OUTCOME_INSPECTION`: **NOT_CONFIRMED** — execute_replication and real OHLC load require a missing execution permit. No RESULT written.

## Next

`NEXT_UNIT = D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION`  
`D2_BITMEX_OUTCOME_COMPUTED = false`  
`PROTECTED_2025_OPENED = false`  
`PROTECTED_2026_OPENED = false`
