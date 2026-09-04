# B2-04 Moderate Pullback Structure — Development Result Closeout

**Formulation:** `B2-04_MODERATE_PULLBACK_STRUCTURE`  
**Primary family:** F1 — directional persistence / continuation  
**Research verdict:** `B2_04_CLOSED_NO_PROMOTION`  
**Formulation status:** `CLOSED_NO_PROMOTION`  
**Family status after closeout:** `CLOSED_NO_PROMOTION`  
**2025 validation:** UNTOUCHED  
**2026 OOS:** UNTOUCHED  
**Rerun authorized by this closeout:** NO  
**Scientific development executions that crossed `OUTCOME_ACCESS_CLAIMED`:** 1

## 1. Evidence boundary

This document records the single authorized B2-04 development verdict. It does
not rerun B2-04, reopen 2025/2026, or reinterpret the failed result.

The frozen `V2_FORMULATION_INVENTORY` is intentionally not modified. B2-04 was
the one explicitly admitted H04-derived `POSTHOC_UNTESTED` child. Under the
frozen inventory, failure of its full promotion contract closes both B2-04 and
the H04-derived child path inside current V2. No second moderate-pullback child
is admitted.

## 2. Exact execution identity

| Field | Value |
|---|---|
| Hypothesis ID | `B2-04_MODERATE_PULLBACK_STRUCTURE` |
| Execution SHA | `9c2ed3ca7fab24dca832065cf4bed9a5c860a362` |
| Execution tree | `cc4c3691e522b4f83681ce069d4dc40a7b15d0a6` |
| Prereg merge SHA | `bcc00d4a6180105991fd4828b7cfc7983c9c9ccf` |
| Dataset ID | `CORE_BTC_BINANCE_V0` |
| Dataset snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| Stage | `development` |
| Authorized years | 2020, 2021, 2022, 2023, 2024 |
| Development window | 2020-02-01T00:00:00Z inclusive → 2025-01-01T00:00:00Z exclusive |
| Canonical runner | `scripts.research.b2_04_moderate_pullback_structure.run_development` |
| Outcome-access flag | `outcome_access_acknowledged=True` |
| Placebo seed | `20260906` |
| Bootstrap seed | `20260907` |
| Primary cells | 15 (`L ∈ {240,480,960}` × `H ∈ {15,30,60,120,240}`) |
| Post-refractory events | 5100 |
| Tracked repo files modified by run | NO |
| 2025 accessed | NO |
| 2026 accessed | NO |

## 3. Durable evidence

| Field | Value |
|---|---|
| Evidence ref | `refs/heads/research-evidence/batch02/B2-04/9c2ed3ca7fab24dca832065cf4bed9a5c860a362` |
| RESERVED commit SHA | `f5a63e0b6c169bf2868e5d40357906b85e9ddbcd` |
| OUTCOME_ACCESS_CLAIMED commit SHA | `557f0df8be0ccfed712d30343b2e83be9cece4bd` |
| ARCHIVED commit SHA | `a75838482a8472148d6686c4864189c99ca2f19e` |
| Artifact SHA256 | `2e7c84cda547e8de25c7ab7f2f95beac26655b632d2ba202e4490e51c54fd4e3` |
| Artifact size | 3152434 bytes |
| Final durable state | `ARCHIVED` |

Remote readback confirmed the lifecycle `RESERVED → OUTCOME_ACCESS_CLAIMED → ARCHIVED`
and bound the receipt to the execution SHA/tree, dataset/snapshot, stage, and
artifact digest above.

## 4. Frozen claim

B2-04 tested whether one predeclared structural property of an established-trend
moderate pullback adds stable continuation information beyond trend state and
actual moderate pullback depth on exact same support.

The single structural property was `RECOVERY_FRACTION`. The primary models were:

- baseline: `Y_H = a + b*FINAL_DEPTH`;
- candidate: `Y_H = a + b*FINAL_DEPTH + c*RECOVERY_FRACTION`.

No second H04-derived child, alternate recovery descriptor, depth threshold,
trend indicator, sign reversal, or rescue formulation is authorized after this
outcome.

## 5. Final verdict

```text
B2_04_CLOSED_NO_PROMOTION
```

Promotion: `false`.

This is a completed scientific development verdict, not a software, data, or
integrity abort. It does not mean bearish, bullish, or no-trade.

## 6. Promotion gates

| Gate | Result |
|---|---|
| `primary_positive` | FAIL |
| `material_relative_mae` | FAIL |
| `bootstrap_positive` | FAIL |
| `placebo_separation` | FAIL |
| `structure_ordering` | FAIL |
| `horizon_robustness` | FAIL |
| `parameter_robustness` | FAIL |
| `year_stability` | FAIL |

Qualifying neighborhoods: `NONE`.

## 7. Result summary

The result is not a near miss:

- mean AE improvement is negative in all 15/15 primary cells;
- relative MAE improvement is negative in all 15/15 cells;
- no cell passes `primary_positive`, `material_relative_mae`,
  `bootstrap_positive`, or `placebo_separation`;
- `structure_ordering` is true only at `L=480,H=120`;
- maximum `positive_years` is 2/5;
- no robust adjacent-horizon / cross-L neighborhood exists.

In 11 of 15 cells, the bootstrap 95% upper bound is already below zero. The
candidate therefore did not merely miss a formal gate: in this exact frozen
specification, adding `RECOVERY_FRACTION` systematically failed to improve the
same-support depth-controlled forecast.

The negative sign is not authorization for a reverse-sign strategy or rescue.

## 8. Full primary-cell surface

Values below are transcribed from the accepted archived result; they are not
recomputed in this closeout.

| L | H | N | UP | DOWN | Mean AE Δ | Relative MAE Δ | Bootstrap 95% | Placebo q95 | Structure ordering | Positive years |
|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|
| 240 | 15 | 2455 | 1150 | 1305 | -0.002134455 | -0.001112126 | [-0.011476434, 0.007001573] | -0.000305558 | false | 2 |
| 240 | 30 | 2455 | 1150 | 1305 | -0.006752834 | -0.003504859 | [-0.016473316, 0.002520053] | -0.002159735 | false | 1 |
| 240 | 60 | 2455 | 1150 | 1305 | -0.016097141 | -0.007912706 | [-0.028091447, -0.005020753] | -0.006340033 | false | 0 |
| 240 | 120 | 2453 | 1149 | 1304 | -0.022068911 | -0.010570595 | [-0.037713255, -0.006732008] | -0.004948871 | false | 0 |
| 240 | 240 | 2453 | 1149 | 1304 | -0.008298708 | -0.004118495 | [-0.019081119, 0.002563615] | -0.006165949 | false | 1 |
| 480 | 15 | 1633 | 721 | 912 | -0.014772801 | -0.007173660 | [-0.028850555, -0.000987058] | -0.002939766 | false | 0 |
| 480 | 30 | 1633 | 721 | 912 | -0.030832980 | -0.014109880 | [-0.054395453, -0.008028773] | -0.009210454 | false | 0 |
| 480 | 60 | 1633 | 721 | 912 | -0.025119380 | -0.011573783 | [-0.038584985, -0.011778688] | -0.008167910 | false | 0 |
| 480 | 120 | 1633 | 721 | 912 | -0.022356903 | -0.010218971 | [-0.035266489, -0.010074775] | -0.003933414 | true | 0 |
| 480 | 240 | 1632 | 720 | 912 | -0.048362124 | -0.022140677 | [-0.078139498, -0.023840053] | -0.020815333 | false | 0 |
| 960 | 15 | 832 | 369 | 463 | -0.087913026 | -0.035316103 | [-0.175426302, -0.022781462] | -0.003327279 | false | 1 |
| 960 | 30 | 832 | 369 | 463 | -0.044611278 | -0.017680892 | [-0.114419208, 0.008833118] | -0.009187030 | false | 2 |
| 960 | 60 | 832 | 369 | 463 | -0.075559129 | -0.030148843 | [-0.169365777, -0.010560587] | -0.016853438 | false | 1 |
| 960 | 120 | 832 | 369 | 463 | -0.112181032 | -0.045040769 | [-0.234777505, -0.035971448] | -0.015301729 | false | 0 |
| 960 | 240 | 832 | 369 | 463 | -0.036958035 | -0.015798361 | [-0.069920120, -0.004156251] | -0.018092122 | false | 0 |

## 9. Deterministic state transition

```text
B2_04_MODERATE_PULLBACK_STRUCTURE = CLOSED_NO_PROMOTION
F1_DIRECTIONAL_PERSISTENCE = CLOSED_NO_PROMOTION
B2_04_RERUN = NOT_AUTHORIZED
B2_04_REFORMULATION_CURRENT_V2 = NOT_AUTHORIZED
H04_DERIVED_CHILD_PATH = CLOSED
2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
NEXT_FROZEN_FORMULATION = B2_05_FLOW_ABSORPTION
```

B2-02, B2-03, and B2-04 are now all closed without promotion. Since those are
the complete current-V2 F1 inventory entries, F1 closes for current V2.

## 10. Next allowed research unit

The next eligible current-CORE formulation is `B2-05_FLOW_ABSORPTION` in F4.
Its inventory claim is flow-to-price-response interaction, not imbalance alone.
This closeout does not preregister a new formulation, modify the frozen inventory,
or authorize B2-05 outcome access.

B2-06 remains `BLOCKED_MISSING_OBSERVABLE` pending a separately authorized
OI/funding data-expansion unit.

## 11. Final integrity statement

No 2025 validation or 2026 OOS outcome was used in this B2-04 development
decision. The one-shot is consumed and no rerun/rescue is authorized.
