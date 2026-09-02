# B2-02 Boundary Interaction Path — Development Result Closeout

**Formulation:** `B2-02_BOUNDARY_INTERACTION_PATH`
**Primary family:** F1 — directional persistence / continuation
**Research verdict:** `B2_02_CLOSED_NO_PROMOTION`
**Formulation status:** `CLOSED_NO_PROMOTION`
**Family status after closeout:** `OPEN` (B2-03 and B2-04 remain frozen and unopened)
**2025 validation:** UNTOUCHED
**2026 OOS:** UNTOUCHED
**Rerun authorized by this closeout:** NO

## 1. Evidence boundary

This document records the authorized B2-02 development verdict.

It does **not** rerun B2-02 and does not reopen the result artifact. The execution
identity, result hash, gates, and cell metrics below are recorded from the one
authorized exact-SHA development-run report produced after the independently
reviewed implementation freeze and the separate post-merge outcome-access
authorization on PR #95 (`issuecomment-5506806925`).

The frozen `V2_FORMULATION_INVENTORY` is intentionally **not modified** by this
closeout. Under the V2 charter it became immutable when the first real Batch02
outcome was read.

No B2-02 threshold, state, window, lookback, horizon, path component, path-score
weight, close-location filter, target, loss, sign, comparator, or child
formulation is authorized after this verdict inside current V2.

## 2. Exact execution identity

| Field | Value |
|---|---|
| Reviewed implementation SHA | `37051de39f49b5b331a0ddbc3b37f8316811f9ef` |
| Git tree | `f220590be0a6323df29b8e35b47399d42c3ea137` |
| Implementation merge commit / execution SHA | `a976a3fa3143f7290851ab8b2ddc5a9d811c891a` |
| Prereg merge SHA | `cbf447276c1dc47c9a755038cfd6013199207eef` |
| Prereg JSON SHA256 | `3dd11009cd738ab02ab3a3a0a552de9a25a6c4db765d6510f63937c922a6d7b1` |
| Promotion-gate-contract SHA256 | `7e2683bb98018cfcac217f398ed7117dabb470e3e1bc9e3e631270844070d319` |
| Dataset ID | `CORE_BTC_BINANCE_V0` |
| Dataset snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| Authorized years | 2020, 2021, 2022, 2023, 2024 |
| Development window | 2020-02-01T00:00:00Z inclusive → 2025-01-01T00:00:00Z exclusive |
| Canonical runner | `scripts.research.b2_02_boundary_interaction_path.run_development` |
| Outcome-access flag | `outcome_access_acknowledged=True` |
| Result artifact path at execution | `/workspace/artifacts/b2_02_boundary_interaction_path/B2_02_BOUNDARY_INTERACTION_PATH_DEV_RESULTS.json` |
| Result artifact SHA256 | `971b645a0eb8b45293f7c2f589c9666a037fe602a6f228751162b13bf0054646` |
| Placebo seed | `20260902` |
| Bootstrap seed | `20260903` |
| Qualifying breaches | 107061 |
| Primary cells | 12 |
| Tracked repo files modified by run | NO |
| 2025 accessed | NO |
| 2026 accessed | NO |

The canonical accepted dataset root used by the run was
`/workspace/artifacts/research_data/CORE_BTC_BINANCE_V0`. The harness bound it
to the frozen snapshot before scoring. Forbidden-window evidence is derived from
the authorized view and loaded bytes: 60 monthly partitions, calendar years
2020-2024 only, `authorized_max_partition_year=2024`. January 2020 was
warmup/reference only; scored development began at 2020-02-01T00:00:00Z.
No 2025 or 2026 objects were selected.

Observed loaded max `available_at_ms` equals `1735689600000`
(2025-01-01T00:00:00Z), the exclusive development end. The fail-closed check is
strictly greater than that bound, so the exclusive endpoint is allowed and is
not a 2025 validation access.

## 3. Overall verdict

```text
B2_02_CLOSED_NO_PROMOTION
```

No promotion neighborhood satisfied the frozen contract.

The formulation is spent. This is a completed research verdict, not a software,
data, or integrity abort.

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

No cell passed all five per-cell gates. `selected_neighborhood` is empty and
`passed` is false. One cell (`L=60`, `H=30`) has `placebo_separation=true`
while remaining strictly negative on mean AE improvement; that isolated
placebo pass cannot rescue the formulation.

## 5. Frozen 12-cell surface

Per-cell gate shorthand below is:

`primary_positive / material_relative_mae / bootstrap_positive / placebo_separation / path_ordering`.

| L | H | N | Mean AE Δ | Median AE Δ | Rel MAE Δ | Bootstrap 95% | PATH_SEPARATION | Gates | Year stability | Placebo q95 |
|---:|---:|---:|---:|---:|---:|---|---:|---|---|---:|
| 60 | 30 | 24673 | -0.007643 | -0.002135 | -0.00476 | [-0.010456, -0.004923] | -0.1584 | F/F/F/P/F | FAIL | -0.00806 |
| 60 | 60 | 24651 | -0.007889 | -0.002371 | -0.00485 | [-0.010594, -0.005051] | -0.1625 | F/F/F/F/F | FAIL | -0.00751 |
| 60 | 120 | 24631 | -0.008495 | -0.004426 | -0.00520 | [-0.011158, -0.005812] | -0.1464 | F/F/F/F/F | FAIL | -0.00744 |
| 60 | 240 | 24578 | -0.010483 | -0.003340 | -0.00640 | [-0.013051, -0.007875] | -0.1304 | F/F/F/F/F | FAIL | -0.00777 |
| 120 | 30 | 10627 | -0.012203 | -0.002964 | -0.00684 | [-0.016628, -0.007757] | -0.1557 | F/F/F/F/F | FAIL | -0.00942 |
| 120 | 60 | 10614 | -0.009177 | -0.001092 | -0.00514 | [-0.013352, -0.005091] | -0.1678 | F/F/F/F/F | FAIL | -0.00860 |
| 120 | 120 | 10601 | -0.010009 | -0.003158 | -0.00562 | [-0.013983, -0.005728] | -0.1688 | F/F/F/F/F | FAIL | -0.00905 |
| 120 | 240 | 10575 | -0.009824 | -0.000933 | -0.00566 | [-0.014241, -0.005713] | -0.1688 | F/F/F/F/F | FAIL | -0.00721 |
| 240 | 30 | 2821 | -0.009076 | -0.003472 | -0.00465 | [-0.019772, +0.002157] | -0.2007 | F/F/F/F/F | FAIL | -0.00475 |
| 240 | 60 | 2814 | -0.009226 | -0.002095 | -0.00463 | [-0.020197, +0.001099] | -0.2035 | F/F/F/F/F | FAIL | -0.00473 |
| 240 | 120 | 2804 | -0.008600 | -0.001155 | -0.00458 | [-0.017552, +0.000162] | -0.1830 | F/F/F/F/F | FAIL | -0.00526 |
| 240 | 240 | 2793 | -0.009195 | -0.002063 | -0.00515 | [-0.019048, -0.000327] | -0.0487 | F/F/F/F/F | FAIL | -0.00532 |

Every cell has negative mean AE improvement. Maximum observed relative MAE
improvement is therefore below zero and far below the frozen 2% materiality
threshold. `PATH_SEPARATION` is negative in every cell, opposite the frozen
expected positive sign.

Support is large and mixed-side. Example at `L=60`, `H=30`: N=24673,
UPPER=12346, LOWER=12327, PATH_STATE counts LOW=7372 / MID=8996 / HIGH=8305,
58 unique UTC months, largest-month share 2.20%. The L=240 cells are smaller
(N≈2800) but still mixed-side and not an integrity abort.

## 6. Year stability

Mean AE improvement by fixed calendar year:

| L | H | 2020 | 2021 | 2022 | 2023 | 2024 | 4/5 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 60 | 30 | -0.003044 | -0.010229 | -0.008964 | -0.006693 | -0.007954 | FAIL |
| 60 | 60 | -0.006415 | -0.012454 | -0.007985 | -0.005303 | -0.006926 | FAIL |
| 60 | 120 | -0.008220 | -0.009140 | -0.007879 | -0.007334 | -0.009789 | FAIL |
| 60 | 240 | -0.011021 | -0.011794 | -0.005499 | -0.011659 | -0.013055 | FAIL |
| 120 | 30 | -0.001629 | -0.010317 | -0.009810 | -0.020890 | -0.017006 | FAIL |
| 120 | 60 | -0.005491 | -0.014615 | -0.010714 | -0.002032 | -0.011885 | FAIL |
| 120 | 120 | -0.012604 | -0.012313 | -0.005600 | -0.010764 | -0.009632 | FAIL |
| 120 | 240 | -0.013970 | -0.010870 | -0.005982 | -0.013082 | -0.006465 | FAIL |
| 240 | 30 | -0.013079 | -0.007906 | -0.018492 | -0.017612 | +0.009277 | FAIL |
| 240 | 60 | -0.003095 | -0.015705 | +0.012236 | -0.021438 | -0.008466 | FAIL |
| 240 | 120 | -0.009964 | -0.009714 | -0.005184 | -0.004943 | -0.012699 | FAIL |
| 240 | 240 | -0.011556 | -0.014106 | -0.007088 | -0.018158 | +0.007415 | FAIL |

No cell is positive in 4 of 5 fixed years. The only positive yearly means are
isolated L=240 slices (2024 at H=30 and H=240; 2022 at H=60). They do not form
a promotion neighborhood.

## 7. Interpretation under the frozen contract

B2-02 did not establish stable material incremental information from the
post-breach interaction path beyond the frozen pre-breach baseline state.

The result is not a near-miss that authorizes threshold relaxation:

- all 12 cells have negative mean AE improvement;
- all 12 cells fail the 2% relative-MAE materiality threshold;
- all 12 cells have `PATH_SEPARATION` opposite the frozen expected sign;
- 11 of 12 cells fail placebo; the one placebo pass remains a worse-than-baseline forecast;
- no cell reached the five-gate per-cell conjunction;
- no adjacent-horizon robust neighborhood existed;
- no second L supplied parameter robustness;
- year stability failed in all 12 cells.

The observed negative/local structure is not promoted evidence and cannot seed
a current-V2 B2-02 rescue. A more acceptance-like path corresponded to *less*,
not more, continuation after controlling for breach magnitude and pre-breach
state. That reverse ordering is **not** a new authorized hypothesis.

## 8. Deterministic state transition

```text
B2_02_BOUNDARY_INTERACTION_PATH = CLOSED_NO_PROMOTION
F1_DIRECTIONAL_PERSISTENCE = OPEN
B2_02_RERUN = NOT_AUTHORIZED
B2_02_REFORMULATION = NOT_AUTHORIZED_CURRENT_V2
2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```

F1 remains `OPEN` because B2-03 and B2-04 are still frozen inventory members
with no real outcomes. B2-02's closeout does not close the family.

The next eligible frozen formulation is:

`B2-03_IMPULSE_MORPHOLOGY`

This closeout does not preregister, implement, or authorize B2-03 outcome access.

## 9. Final integrity statement

`No 2025 validation or 2026 OOS outcome was used in this B2-02 development decision.`
