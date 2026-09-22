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
CONTROL_P95_METHOD = NUMPY_LINEAR_INHERITED_FROM_D2
FROZEN_RULE1_N     = 1791 (2020=334, 2021=364, 2022=364, 2023=364, 2024=365)  # CONSTRUCTED population, never mask.sum()
FROZEN_SELECTOR_ABSTAIN_N = 163 (2020=10, 2021=48, 2022=32, 2023=23, 2024=50)
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

## Identity

```
IMPLEMENTATION_REVIEW                 = PASS
SCIENTIFIC_KERNEL_READY               = True
CANONICAL_ORCHESTRATION_READY         = True
PERMIT_VERIFIER_READY                 = True
EXACT_SELECTOR_IDENTITY_IMPLEMENTED   = True
CANONICAL_SELECTOR_DIGEST_FROZEN      = False
SELECTOR_IDENTITY_AUTHORITY_CREATED   = False
EXECUTION_READY                       = False
EXECUTION_AUTHORIZED                  = False
EXECUTION_PERMIT_PRESENT              = False
FROZEN_AUTHORITY_STATUS               = BOUND_NO_DRIFT
DESIGN_AUTHORITY_BLOCKERS             = []
DESIGN_JSON_SHA256                    = 485983701d6e05a57f7dc8bb578613467d6d8f6fb1ec1e28c68d7ca42767c75b
RUN_IDENTITY                          = bfe92af94df23d7aa6f3adc016dc6f558607d772977a1cc6613394ac9a92625f
FINAL_IMPLEMENTATION_COMMIT           = 019561384a2b9660a180ff4620c3a9b7f0393727
```

PASS is justified by implemented and tested machinery, not by a hardcoded
red-team table: Scientific kernel, dormant canonical orchestration, tracked-permit verifier, exact selector-identity machinery, and inherited D2 P95 method are implemented and covered by adversarial synthetic tests. PASS is not granted merely because the red-team table is hardcoded NOT_CONFIRMED. EXECUTION_READY remains false because the canonical selector digest is not frozen.

No execution permit exists and no selector-identity authority artifact
exists. `execute_decomposition` is the full dormant canonical route and
still fails closed before any CORE BTC OHLC is read. The route requires
the future tracked selector-identity authority (bound by permit SHA256)
and compares the reconstructed ordered digest to that frozen digest
before `evaluate_decomposition`. Constructed 1791/year census and historical
163/year abstain census are secondary; `RULE_1_N` means constructed N.

## Red-team (F1–F20)

- `F1_LOOKAHEAD_FEATURE_OUTCOME_OVERLAP`: **NOT_CONFIRMED** — Features (rv, ret, SIDE) come from frozen construct_discovery_row at cutoff E=T-5m. The target re-walk reads only bars opening at T..T+287*5m; a RecordingPerp test asserts min(read key) >= T.
- `F2_WRONG_FUTURE_BAR_WINDOW`: **NOT_CONFIRMED** — future_bars_for_row demands exactly 288 bars at T + k*BAR_MS for k=0..287, asserts each bar.open_time_ms equals the requested key, and fails closed on a missing or off-grid bar.
- `F3_CLOSES_INSTEAD_OF_HIGH_LOW`: **NOT_CONFIRMED** — MAE comes from frozen arithmetic_mae over PerpBar high/low. An AST test asserts the evaluator never reads DiscoveryRow.future_closes, and a high/low-collapsed perp map fails the severity cross-check.
- `F4_DIFFERENT_PATHS_FOR_SIDE_AND_MIRROR`: **NOT_CONFIRMED** — mae_pair calls arithmetic_mae twice on one bars sequence. AST tests assert exactly one future_bars_for_row call and one mae_pair call per row, and LONG+SHORT shares on one path sum to exactly 1.0.
- `F5_MAE_SIDE_SUBSTITUTION`: **NOT_CONFIRMED** — Recomputed MAE_SIDE is cross-checked bit-for-bit (tolerance 0.0) against the frozen DiscoveryRow.severity, so any substituted path fails closed.
- `F6_SELECTOR_DRIFT`: **NOT_CONFIRMED** — The selector is frozen C.rv_abstention_mask (identity-asserted), RV_TRAILING_WINDOW=250, RV_PCTL=90.0, strict >, t excluded, imported not redefined. Selector identity reports TWO censuses: constructed RULE_1 N=1791 / years 334,364,364,364,365 (FROZEN_RULE1_N, never mask.sum()) and historical selector abstain N=163 / years 10,48,32,23,50 bound to frozen D2 PRIMARY_METRICS.RV_ABSTENTION. Those count-only censuses are secondary integrity checks only. Exact identity is SHA256 of the ordered constructed-row t_ms plus selector flags; that machinery is implemented and tested. canonical_orchestration compares the reconstructed digest to a tracked selector-identity authority BEFORE evaluate_decomposition. The authority artifact is NOT created in this unit (CANONICAL_SELECTOR_DIGEST_FROZEN = false) because obtaining the true canonical digest would require opening real CORE BTC. Count-only identity is not called exact identity.
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
- `F18_ACCIDENTAL_REAL_OUTCOME_EXECUTION`: **NOT_CONFIRMED** — execute_decomposition is the full dormant canonical orchestration route, not a terminal firewall stub. Scientific authority is read only from a tracked permit artifact (UNIT, design/review/evaluator SHA256, CORE snapshot, RUN_IDENTITY, seed 20260922131, N=10000, EXECUTION_AUTHORIZED=true, ONE_SHOT=true, RERUN_AUTHORIZED=false). Caller kwargs cannot replace those fields. No permit exists in this unit, so the route fails closed before CORE BTC OHLC is opened. Adversarial tests cover forged caller authority, mutated permit bytes, and each bound-field mismatch.
- `F19_PROTECTED_2025_2026_ACCESS`: **NOT_CONFIRMED** — construct_discovery_row refuses decisions from 2025 onward and the target re-walk refuses any bar at or after PROTECTED_START_MS. No protected partition is opened.
- `F20_BITMEX_REUSE_FOR_NEW_TARGET`: **NOT_CONFIRMED** — An AST test asserts the evaluator imports no BitMEX module. The surface is CORE_BTC_BINANCE_V0 2020-02-01 -> 2025-01-01 only.

## Observations (non-blocking)

- `O1_STATISTICAL_GATE_STRICT_INEQUALITY_AT_AN_EXACT_TIE` (HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE) — The frozen STATISTICAL_GATE is MU_SHARE_RULE > CONTROL_SHARE_P95. When the rule and control means are exactly tied, floating-point noise can decide the strict comparison. The frozen design is authoritative and is NOT changed here. Defense in depth is already frozen: PROMISING requires the practical (>= 0.05) and temporal (>= 3 of 5 years) gates too, so a lone float-noise statistical pass cannot change the classification. Covered by test_statistical_gate_alone_cannot_produce_promising.
- `O2_CONTROL_POOL_INCLUDES_THE_ABSTAINED_ROWS` (FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE) — year_side_matched_control_masks draws from every target-eligible row in the stratum, including the D2-abstained rows themselves. This is the frozen design function's own behaviour and matches the original D2 discovery comparator rate_matched_random_abstention. No new researcher convention was introduced.
- `O3_YEARLY_NAN_IS_STRUCTURALLY_IMPOSSIBLE_UNLESS_K_YEAR_IS_ZERO` (FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE) — Each replicate draws exactly K per stratum, so a year's replicate subset is empty only when that year has no candidate rows at all. Partial NaN across replicates is therefore impossible and is rejected explicitly rather than silently averaged.
- `O4_CONTROL_P95_METHOD_INHERITED_FROM_D2` (FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE) — CONTROL_P95_METHOD = NUMPY_LINEAR_INHERITED_FROM_D2. np.percentile(values, 95.0, method='linear') is the historical D2 convention made explicit. This is not a newly selected scientific threshold. CONTROL_SHARE_P95 and CONTROL_PATH_SCALE_P95 both use it.
- `O5_CANONICAL_SELECTOR_DIGEST_NOT_FROZEN_OUTCOME_BLIND` (HONEST_IDENTITY_GAP_NOT_A_RESCUE) — Exact selector-identity machinery is implemented (ordered t_ms + selector-flag SHA256) and the canonical route requires a tracked selector-identity authority whose SHA256 is bound by the future execution permit. The true canonical digest cannot be obtained in this unit without opening prohibited real CORE BTC, so the authority artifact is not created or guessed. CANONICAL_SELECTOR_DIGEST_FROZEN = false. The next unit only reconstructs and freezes that authority; it must not alter the reviewed scientific execution implementation.

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
SELECTOR_IDENTITY_AUTHORITY_CREATED = False
```

## Next

`NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE`

The canonical selector digest is not frozen in this outcome-blind unit
and the selector-identity authority artifact was not created. The next
unit only reconstructs and freezes that tracked authority; it must not
alter the reviewed scientific execution implementation. This review does
not authorize execution: no permit exists, `EXECUTION_READY = false`,
and `EXECUTION_AUTHORIZED = false`.
