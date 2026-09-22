# D2 excess direction-aligned path-risk — implementation review

**Unit:** `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`
**Kind:** outcome-blind implementation review. **The decomposition was NOT executed.**

## Lineage

The frozen decomposition design
`docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.json` is authoritative and was not
redesigned. This unit adds an execution implementation plus an adversarial
synthetic test suite, without computing any real ADVERSE_SHARE, PATH_SCALE,
DELTA_SHARE, or classification.

The selector is unchanged: `D2_RULE_1_RV_ABSTENTION` — P90 of the previous
250 valid constructed-row RV observations, `t` excluded, strict `>`.

## Scientific contract

```
PRIMARY_SELECTOR   = D2_RULE_1_RV_ABSTENTION
PRIMARY_TARGET     = ADVERSE_SHARE
ADVERSE_SHARE      = MAE_SIDE / (MAE_SIDE + MAE_OPPOSITE)
PATH_SCALE         = MAE_SIDE + MAE_OPPOSITE
PRIMARY_COMPARATOR = YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION
CONTROL_STRATA     = calendar_year × frozen_SIDE
STATISTICAL_GATE   = MU_SHARE_RULE > CONTROL_SHARE_P95
PRACTICAL_GATE     = DELTA_SHARE >= 0.05
TEMPORAL_GATE      = DELTA_SHARE > 0 in at least 3 of 5 years
RANDOM_SEED        = 20260922131
N_RANDOM_CONTROLS  = 10000
FROZEN_RULE1_N     = 1791 (2020=334, 2021=364, 2022=364, 2023=364, 2024=365)
```

Classification order is unchanged and exhaustive:

1. `D2_DECOMPOSITION_INVALID`
2. `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PROMISING`
3. `D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`
4. `D2_DECOMPOSITION_NO_USEFUL_STRUCTURE`

## Future-path reconstruction

`DiscoveryRow` stores `future_closes` only, so `MAE_OPPOSITE` cannot be read
off a stored row. The implementation re-walks the exact 288 5m `PerpBar`
sequence opening at `T … T+287*5m` and calls frozen `arithmetic_mae` twice on
that one shared sequence. Recomputed `MAE_SIDE` is cross-checked bit-for-bit
against the frozen `DiscoveryRow.severity`, so a wrong window, a close-path
substitution, or a split path fails closed rather than producing a number.

Rows whose envelope is nonpositive or nonfinite are target-ineligible with
reason `TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE` and no epsilon. This never
rebuilds the D2 selector; the count of selector rows dropped by target
ineligibility is reported per year.

## Lifecycle status

These are distinct claims. Each is derived from a mechanical probe of the
reviewed code, not from the findings table.

```
IMPLEMENTATION_REVIEW          = PASS
SCIENTIFIC_KERNEL_READY        = True
CANONICAL_ORCHESTRATION_READY  = True
AUTHORITY_VERIFICATION_READY   = True
ROW_COUNT_IDENTITY_IMPLEMENTED = True
EXACT_SELECTOR_IDENTITY_VERIFIED = False
EXACT_SELECTOR_IDENTITY_STATUS = DIGEST_FUNCTION_IMPLEMENTED_EXPECTED_VALUE_NOT_YET_FROZEN
EXECUTION_READY                = False
EXECUTION_BLOCKED_BY           = ['EXPECTED_CANONICAL_SELECTOR_DIGEST_NOT_FROZEN', 'NO_EXECUTION_PERMIT', 'EXECUTION_AUTHORIZED_FALSE']
EXECUTION_AUTHORIZED           = False
```

`EXECUTION_READY` is deliberately **not** a synonym for a passing review. The
canonical route is implemented and reviewed, but the expected canonical
selector digest has not been frozen, and that value cannot legitimately be
produced by an outcome-blind unit. Until it exists, the one-shot must not run.

## Canonical route (dormant, not a stub)

```
1. permit gate            : True
2. frozen snapshot identity: True
3. frozen CORE BTC load    : True
4. frozen row reconstruction: True
5. frozen evaluation       : True
execute_is_terminal_stub   : False
```

## Frozen selector census

`RULE_1_ROW_COUNT = 1791` is the **constructed decision-row population**
(`RULE_ELIGIBLE_N`), not the abstention count. The frozen RULE_1 abstention
census is separate and smaller.

```
CONSTRUCTED_N   = 1791
CONSTRUCTED_YEAR_N = {'2020': 334, '2021': 364, '2022': 364, '2023': 364, '2024': 365}
ABSTAIN_N       = 163
ABSTAIN_YEAR_N  = {'2020': 10, '2021': 48, '2022': 32, '2023': 23, '2024': 50}
CONTROL_P95_METHOD = NUMPY_LINEAR_INHERITED_FROM_D2
```

## Identity

```
FROZEN_AUTHORITY_STATUS    = BOUND_NO_DRIFT
DESIGN_AUTHORITY_BLOCKERS  = []
DESIGN_JSON_SHA256         = 485983701d6e05a57f7dc8bb578613467d6d8f6fb1ec1e28c68d7ca42767c75b
RUN_IDENTITY               = 3d0a7f09f9e514e1b8e5d7e9113df8182bedb186a9da9321fc08d1271e38bdfd
FINAL_IMPLEMENTATION_COMMIT = e5eff8a0f05194fe83e57c515ddcd94ad7aaeddd
EXECUTION_PERMIT_PRESENT   = False
```

No execution permit exists. `execute_decomposition` and
`load_canonical_core_btc_bars` fail closed before any CORE BTC byte is read.
A future permit must itself carry every field in `PERMIT_REQUIRED_FIELDS`;
caller arguments cannot supply scientific authority.

## Red-team (F1–F25)

- `F1_LOOKAHEAD_FEATURE_OUTCOME_OVERLAP`: **NOT_CONFIRMED** — Features (rv, ret, SIDE) come from frozen construct_discovery_row at cutoff E=T-5m. The target re-walk reads only bars opening at T..T+287*5m; a RecordingPerp test asserts min(read key) >= T.
- `F2_WRONG_FUTURE_BAR_WINDOW`: **NOT_CONFIRMED** — future_bars_for_row demands exactly 288 bars at T + k*BAR_MS for k=0..287, asserts each bar.open_time_ms equals the requested key, and fails closed on a missing or off-grid bar.
- `F3_CLOSES_INSTEAD_OF_HIGH_LOW`: **NOT_CONFIRMED** — MAE comes from frozen arithmetic_mae over PerpBar high/low. An AST test asserts the evaluator never reads DiscoveryRow.future_closes, and a high/low-collapsed perp map fails the severity cross-check.
- `F4_DIFFERENT_PATHS_FOR_SIDE_AND_MIRROR`: **NOT_CONFIRMED** — mae_pair calls arithmetic_mae twice on one bars sequence. AST tests assert exactly one future_bars_for_row call and one mae_pair call per row, and LONG+SHORT shares on one path sum to exactly 1.0.
- `F5_MAE_SIDE_SUBSTITUTION`: **NOT_CONFIRMED** — Recomputed MAE_SIDE is cross-checked bit-for-bit (tolerance 0.0) against the frozen DiscoveryRow.severity, so any substituted path fails closed.
- `F6_SELECTOR_DRIFT`: **NOT_CONFIRMED** — The selector is frozen C.rv_abstention_mask (identity-asserted), RV_TRAILING_WINDOW=250, RV_PCTL=90.0, strict >, t excluded, imported not redefined. verify_selector_identity fails closed unless the constructed population is exactly 1791 / 334-364-364-364-365 AND the abstention census matches the frozen 163 / 10-48-32-23-50 (see F24), with exact timestamp identity deferred to the canonical digest (F23).
- `F7_SIDE_DRIFT`: **NOT_CONFIRMED** — SIDE is the frozen row.side = sign(BTC_RET_24H); encode_side accepts only +/-1 and rejects 0 and fractional sides.
- `F8_TARGET_INELIGIBILITY_HANDLING`: **NOT_CONFIRMED** — PATH_SCALE<=0 or nonfinite yields exactly TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE with no epsilon. The selector mask is never rebuilt: candidate = selector AND eligible, and SELECTOR_ROWS_TARGET_INELIGIBLE_N is reported per year.
- `F9_POOLED_K_OR_YEAR_ONLY_FALLBACK`: **NOT_CONFIRMED** — Draws are per (calendar_year, frozen SIDE) stratum. Tests assert every replicate reproduces K exactly in every stratum, and that an all-LONG candidate set never draws a SHORT control row while a pooled draw would.
- `F10_LONG_SHORT_COMPOSITION_MISMATCH`: **NOT_CONFIRMED** — Per-stratum K equality is asserted for both sides in every replicate; K=0 strata draw zero rows.
- `F11_RNG_SEED_DRIFT`: **NOT_CONFIRMED** — numpy.random.Generator(numpy.random.PCG64(20260922131)), N_RANDOM_CONTROLS=10000. Asserted distinct from the D2 discovery seed and the D2 BitMEX seed; same seed reproduces masks, different seed does not.
- `F12_REPLACEMENT_SAMPLING`: **NOT_CONFIRMED** — rng.choice(..., replace=False) per stratum; tests assert each replicate sets exactly K distinct bits, which a with-replacement draw could not.
- `F13_DIFFERENT_MASKS_FOR_SHARE_AND_SCALE`: **NOT_CONFIRMED** — AST tests assert exactly one year_side_matched_control_masks call and that both means_from_shared_masks calls consume the same masks object.
- `F14_SEPARATE_YEARLY_CONTROL_GENERATION`: **NOT_CONFIRMED** — Yearly DELTA_SHARE uses year_means_from_shared_masks on the same masks object, subset by year; AST asserts exactly one such call and no second mask system.
- `F15_FUTURE_INFORMATION_MATCHING`: **NOT_CONFIRMED** — The comparator receives only years, sides, target-eligibility and candidacy. No matching on PATH_SCALE, future volatility, future return, MAE, extrema or abs(BTC_RET_24H); an AST test asserts no share/scale array is passed.
- `F16_GATE_OR_CLASSIFICATION_RESCUE`: **NOT_CONFIRMED** — classify_decomposition is the frozen ordered rule. PROMISING requires all three primary gates; PATH_SCALE elevation can only reach VOLATILITY_SCALE_COMPATIBLE and never rescues a failed ADVERSE_SHARE gate; the classifier never reads yearly or subgroup values.
- `F17_AUTHORITY_HASH_DRIFT`: **NOT_CONFIRMED** — verify_design_authorities binds the D2 discovery RESULT, program decision, common.py, the D2 card and the arithmetic_mae module by SHA256 and currently returns no blockers; a mutated copy raises COMMON_SHA in test.
- `F18_ACCIDENTAL_REAL_OUTCOME_EXECUTION`: **NOT_CONFIRMED** — execute_decomposition and load_canonical_core_btc_bars require an execution permit that does not exist; EXECUTION_AUTHORIZED is False and a forged permit still raises RealDecompositionForbidden.
- `F19_PROTECTED_2025_2026_ACCESS`: **NOT_CONFIRMED** — construct_discovery_row refuses decisions from 2025 onward and the target re-walk refuses any bar at or after PROTECTED_START_MS. No protected partition is opened.
- `F20_BITMEX_REUSE_FOR_NEW_TARGET`: **NOT_CONFIRMED** — An AST test asserts the evaluator imports no BitMEX module. The surface is CORE_BTC_BINANCE_V0 2020-02-01 -> 2025-01-01 only.
- `F21_EXECUTION_READY_OVERSTATED_STUB_ROUTE`: **CONFIRMED_AND_REPAIRED** — The first review recorded EXECUTION_READY=true while execute_decomposition was a terminal stub that checked the permit and then unconditionally raised, so the canonical wiring would have been written AFTER the outcome-blind review. The complete dormant route is now implemented and reviewed: permit -> frozen snapshot identity -> frozen CORE BTC load -> C.build_rows(RULE1_INTERVAL_START, DISCOVERY_END) -> selector identity -> exact 288x5m re-walk -> frozen comparator at seed 20260922131 / 10000 replicates with identity enforcement and severity cross-check ON. An end-to-end test runs steps 3-8 over the real frozen interval against a synthetic surface. Frozen parameters are not caller-tunable: seed/N drift raises.
- `F22_PERMIT_AUTHORITY_UNDER_BOUND`: **CONFIRMED_AND_REPAIRED** — The first gate let caller kwargs supply design/review/implementation/snapshot values and bound only run_identity to the permit file. The gate now takes only `repo`: every authority value is read from the tracked permit artifact and compared against tracked/current authorities (unit, design SHA, review SHA, evaluator SHA, CORE BTC snapshot, RUN_IDENTITY equal to the review's, seed, N, EXECUTION_AUTHORIZED, ONE_SHOT, RERUN_AUTHORIZED, plus the frozen selector digest and its version). A CONSUMED permit cannot authorize a rerun. Parameterized tests cover every wrong/missing field, tampered design or review bytes, unparseable permits, and forged caller kwargs.
- `F23_SELECTOR_IDENTITY_PROVED_COUNTS_NOT_IDENTITY`: **CONFIRMED_AND_REPAIRED** — Counts are not identity. A canonical digest over the ordered (t_ms, selector_flag) sequence of the COMPLETE constructed-row population is now implemented and tested (equal counts with different firing positions produce different digests). ROW_COUNT_IDENTITY_VERIFIED and EXACT_SELECTOR_IDENTITY_VERIFIED are reported separately. No expected digest is invented here; the permit must carry one and the one-shot refuses metrics without a match.
- `F24_FROZEN_1791_MISREAD_AS_THE_ABSTAIN_COUNT`: **CONFIRMED_AND_REPAIRED** — Found while repairing F23. The frozen RULE_1_ROW_COUNT=1791 with 334/364/364/364/365 is the CONSTRUCTED decision-row population (RULE_ELIGIBLE_N), not the abstention count; the frozen RULE_1 abstention census in the same hash-bound discovery RESULT is 163 (10/48/32/23/50). The first implementation asserted mask.sum()==1791, which would have failed closed on correct canonical data and invited a post-hoc loosening. Both censuses are now checked against the frozen discovery result, which is outcome-blind for the new ADVERSE_SHARE target because it describes the selector only.
- `F25_CONTROL_PERCENTILE_CONVENTION_IMPLICIT`: **CONFIRMED_AND_REPAIRED** — P95 relied on NumPy's default interpolation. It is now explicit as np.percentile(values, 95.0, method='linear') behind control_percentile, recorded as CONTROL_P95_METHOD=NUMPY_LINEAR_INHERITED_FROM_D2, and tested to equal the historical np.percentile(x, 95) call form used by D2 discovery and D2 BitMEX. The threshold itself is unchanged.

## Observations (non-blocking)

- `O1_STATISTICAL_GATE_STRICT_INEQUALITY_AT_AN_EXACT_TIE` (HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE) — The frozen STATISTICAL_GATE is MU_SHARE_RULE > CONTROL_SHARE_P95. When the rule and control means are exactly tied, floating-point noise can decide the strict comparison. The frozen design is authoritative and is NOT changed here. Defense in depth is already frozen: PROMISING requires the practical (>= 0.05) and temporal (>= 3 of 5 years) gates too, so a lone float-noise statistical pass cannot change the classification. Covered by test_statistical_gate_alone_cannot_produce_promising.
- `O2_CONTROL_POOL_INCLUDES_THE_ABSTAINED_ROWS` (FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE) — year_side_matched_control_masks draws from every target-eligible row in the stratum, including the D2-abstained rows themselves. This is the frozen design function's own behaviour and matches the original D2 discovery comparator rate_matched_random_abstention. No new researcher convention was introduced.
- `O3_YEARLY_NAN_IS_STRUCTURALLY_IMPOSSIBLE_UNLESS_K_YEAR_IS_ZERO` (FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE) — Each replicate draws exactly K per stratum, so a year's replicate subset is empty only when that year has no candidate rows at all. Partial NaN across replicates is therefore impossible and is rejected explicitly rather than silently averaged.

No scientific ambiguity required a new researcher convention:
`SCIENTIFIC_AMBIGUITY_FOUND = False`.

## Firewall

```
REAL_DECOMPOSITION_OUTCOME_COMPUTED = False
CLASSIFICATION_ASSIGNED             = None
PROTECTED_2025_OPENED               = False
PROTECTED_2026_OPENED               = False
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = False
MARKET_07_CREATED                   = False
RESULT_CREATED                      = False
EXECUTION_PERMIT_CREATED            = False
```

## Next

`NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_IDENTITY_COMMIT`

Reconstruct the frozen RULE_1 rows from CORE_BTC_BINANCE_V0 and freeze the canonical selector digest BEFORE any ADVERSE_SHARE or PATH_SCALE metric is computed. That step is outcome-blind for this target: it touches the selector only. The one-shot permit must then carry the frozen digest, and the one-shot must block if the reconstructed digest differs.

Only after that does the explicit one-shot execution unit
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION` become possible. Neither is executed here, and
this review does not authorize either: a future permit must bind the design
hash, this review's hash, the evaluator hash, the CORE BTC snapshot, the run
identity above, the frozen selector digest, the seed and the control count.
