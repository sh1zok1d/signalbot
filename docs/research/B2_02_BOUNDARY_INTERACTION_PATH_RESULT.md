# B2-02 Boundary Interaction Path — Development Result Closeout

**Formulation:** `B2-02_BOUNDARY_INTERACTION_PATH`  
**Primary family:** F1 — directional persistence  
**Research verdict:** `B2_02_CLOSED_NO_PROMOTION`  
**Formulation status:** `CLOSED_NO_PROMOTION`  
**Family status after closeout:** `ACTIVE`  
**2025 validation:** UNTOUCHED  
**2026 OOS:** UNTOUCHED  
**Rerun authorized by this closeout:** NO

## 1. Evidence boundary

This document records the one authorized frozen B2-02 development verdict.

It does **not** rerun B2-02 and does not reopen or modify the persisted result
artifact. The execution identity, artifact digest, promotion gates, and cell
metrics below are transcribed from the canonical one-shot execution report
produced from the merged reviewed implementation.

The frozen `V2_FORMULATION_INVENTORY` remains immutable. No B2-02 threshold,
state, window, horizon, target, training rule, placebo mapping, bootstrap rule,
sign, comparator, or child formulation is authorized after this outcome inside
current V2.

## 2. Exact execution identity

| Field | Value |
|---|---|
| Execution SHA | `a976a3fa3143f7290851ab8b2ddc5a9d811c891a` |
| Reviewed implementation parent | `37051de39f49b5b331a0ddbc3b37f8316811f9ef` |
| Git tree | `f220590be0a6323df29b8e35b47399d42c3ea137` |
| Previous main parent | `7c516e5b45f90b20eab9282716f3671075e2df9b` |
| Prereg merge SHA | `cbf447276c1dc47c9a755038cfd6013199207eef` |
| Dataset ID | `CORE_BTC_BINANCE_V0` |
| Dataset snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| Authorized partitions | 60 monthly partitions |
| Authorized years | 2020, 2021, 2022, 2023, 2024 |
| Development window | 2020-02-01T00:00:00Z inclusive → 2025-01-01T00:00:00Z exclusive |
| Result artifact path at execution | `/tmp/signalbot-b2-02-a976a3fa/artifacts/b2_02_boundary_interaction_path/B2_02_BOUNDARY_INTERACTION_PATH_DEV_RESULTS.json` |
| Result artifact SHA256 | `b5bc240bc30cff92e26b1cf5a7fca4e546c70c80b7f60d113f73f580b439e971` |
| Placebo seed | `20260902` |
| Bootstrap seed | `20260903` |
| Qualifying breaches | 107061 |
| Development executions | 1 |
| Tracked repo files modified by run | NO |
| 2025 accessed | NO |
| 2026 accessed | NO |

The local accepted dataset root used by the run was
`/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0`. Canonical
Batch02 authorization bound it to the frozen snapshot before scoring and
authorized only the 2020-2024 development view.

## 3. Overall verdict

```text
B2_02_CLOSED_NO_PROMOTION
```

No promotion neighborhood satisfied the frozen contract.

This is a completed market-development verdict, not a software, data, or
integrity abort. The formulation is terminal in current V2 and may not be rerun
or rescued by post-outcome parameter changes.

## 4. Mandatory promotion gates

| Gate | Result |
|---|---|
| `primary_positive` | FAIL |
| `material_relative_mae` | FAIL |
| `bootstrap_positive` | FAIL |
| `placebo_separation` | FAIL |
| `path_ordering` | FAIL |
| `horizon_robustness` | FAIL |
| `parameter_robustness` | FAIL |
| `year_stability` | FAIL |

Literal gate contract:

```text
primary_positive=false
material_relative_mae=false
bootstrap_positive=false
placebo_separation=false
path_ordering=false
horizon_robustness=false
parameter_robustness=false
year_stability=false
```

The selected promotion neighborhood is empty.

## 5. Frozen 12-cell surface

Per-cell gate shorthand is:

`primary_positive / material_relative_mae / bootstrap_positive / placebo_separation / path_ordering`.

| L | H | N | Mean AE Δ | Median AE Δ | Rel MAE Δ | Bootstrap 95% | Path separation | Placebo q95 | Gates | Positive years |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---:|
| 60 | 30 | 24673 | -0.007643 | -0.002135 | -0.004758 | [-0.010456, -0.004923] | -0.158384 | -0.008062 | F/F/F/P/F | 0 |
| 60 | 60 | 24651 | -0.007889 | -0.002371 | -0.004852 | [-0.010594, -0.005051] | -0.162512 | -0.007514 | F/F/F/F/F | 0 |
| 60 | 120 | 24631 | -0.008495 | -0.004426 | -0.005203 | [-0.011158, -0.005812] | -0.146398 | -0.007442 | F/F/F/F/F | 0 |
| 60 | 240 | 24578 | -0.010483 | -0.003340 | -0.006396 | [-0.013051, -0.007875] | -0.130354 | -0.007766 | F/F/F/F/F | 0 |
| 120 | 30 | 10627 | -0.012203 | -0.002964 | -0.006841 | [-0.016628, -0.007757] | -0.155685 | -0.009419 | F/F/F/F/F | 0 |
| 120 | 60 | 10614 | -0.009177 | -0.001092 | -0.005141 | [-0.013352, -0.005091] | -0.167814 | -0.008604 | F/F/F/F/F | 0 |
| 120 | 120 | 10601 | -0.010009 | -0.003158 | -0.005618 | [-0.013983, -0.005728] | -0.168773 | -0.009049 | F/F/F/F/F | 0 |
| 120 | 240 | 10575 | -0.009824 | -0.000933 | -0.005657 | [-0.014241, -0.005713] | -0.168834 | -0.007212 | F/F/F/F/F | 0 |
| 240 | 30 | 2821 | -0.009076 | -0.003472 | -0.004650 | [-0.019772, +0.002157] | -0.200692 | -0.004752 | F/F/F/F/F | 1 |
| 240 | 60 | 2814 | -0.009226 | -0.002095 | -0.004633 | [-0.020197, +0.001099] | -0.203514 | -0.004728 | F/F/F/F/F | 1 |
| 240 | 120 | 2804 | -0.008600 | -0.001155 | -0.004583 | [-0.017552, +0.000162] | -0.183006 | -0.005258 | F/F/F/F/F | 0 |
| 240 | 240 | 2793 | -0.009195 | -0.002063 | -0.005150 | [-0.019048, -0.000327] | -0.048725 | -0.005319 | F/F/F/F/F | 1 |

Every cell had negative mean incremental AE improvement and negative relative
MAE improvement. Every path-separation estimate was negative. No cell passed
the five-gate conjunction. The only isolated true per-cell gate was
`placebo_separation` at L=60, H=30; it could not rescue the failed primary,
materiality, bootstrap, and path-ordering gates.

## 6. Year stability

Mean AE improvement by fixed calendar year:

| L | H | 2020 | 2021 | 2022 | 2023 | 2024 | Positive years |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 60 | 30 | -0.003044 | -0.010229 | -0.008964 | -0.006693 | -0.007954 | 0 |
| 60 | 60 | -0.006415 | -0.012454 | -0.007985 | -0.005303 | -0.006926 | 0 |
| 60 | 120 | -0.008220 | -0.009140 | -0.007879 | -0.007334 | -0.009789 | 0 |
| 60 | 240 | -0.011021 | -0.011794 | -0.005499 | -0.011659 | -0.013055 | 0 |
| 120 | 30 | -0.001629 | -0.010317 | -0.009810 | -0.020890 | -0.017006 | 0 |
| 120 | 60 | -0.005491 | -0.014615 | -0.010714 | -0.002032 | -0.011885 | 0 |
| 120 | 120 | -0.012604 | -0.012313 | -0.005600 | -0.010764 | -0.009632 | 0 |
| 120 | 240 | -0.013970 | -0.010870 | -0.005982 | -0.013082 | -0.006465 | 0 |
| 240 | 30 | -0.013079 | -0.007906 | -0.018492 | -0.017612 | +0.009277 | 1 |
| 240 | 60 | -0.003095 | -0.015705 | +0.012236 | -0.021438 | -0.008466 | 1 |
| 240 | 120 | -0.009964 | -0.009714 | -0.005184 | -0.004943 | -0.012699 | 0 |
| 240 | 240 | -0.011556 | -0.014106 | -0.007088 | -0.018158 | +0.007415 | 1 |

No cell was positive in four of five years.

## 7. Interpretation under the frozen contract

B2-02 did not establish incremental predictive value from the frozen
boundary-interaction path descriptor beyond the frozen breach/context baseline.

The result is not a near-miss that authorizes a rescue:

- mean incremental AE was negative in all 12 cells;
- relative MAE improvement was negative in all 12 cells;
- path separation had the opposite sign in all 12 cells;
- no cell satisfied the frozen five-gate conjunction;
- no cell satisfied the 4/5 year-stability rule;
- no adjacent-horizon promotion neighborhood existed;
- no parameter-robust neighborhood existed;
- all eight mandatory overall gates failed.

Observed isolated structure, including the one placebo-separation pass, is not
promoted evidence and cannot seed a current-V2 B2-02 child.

## 8. Deterministic state transition

```text
B2_02_BOUNDARY_INTERACTION_PATH = CLOSED_NO_PROMOTION
B2_02_RERUN = NOT_AUTHORIZED
B2_02_REFORMULATION_CURRENT_V2 = NOT_AUTHORIZED

F1_DIRECTIONAL_PERSISTENCE = ACTIVE
B2_03_IMPULSE_MORPHOLOGY = PLANNED
B2_04_MODERATE_PULLBACK_STRUCTURE = PLANNED

NEXT_FROZEN_FORMULATION = B2_03_IMPULSE_MORPHOLOGY

2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```

F1 remains `ACTIVE` because the frozen inventory still contains B2-03 and
B2-04 as eligible planned formulations. Under the charter a family closes only
when all of its frozen formulations are terminal and none remains planned,
active, blocked, or promoted.

## 9. Final integrity statement

`No 2025 validation or 2026 OOS outcome was used in this B2-02 development decision.`
