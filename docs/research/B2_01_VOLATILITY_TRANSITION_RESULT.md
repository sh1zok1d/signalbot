# B2-01 Volatility Transition — Development Result Closeout

**Formulation:** `B2-01_VOLATILITY_TRANSITION`  
**Primary family:** F3 — volatility-state dynamics  
**Research verdict:** `B2_01_CLOSED_NO_PROMOTION`  
**Formulation status:** `CLOSED_NO_PROMOTION`  
**Family status after closeout:** `CLOSED_NO_PROMOTION`  
**2025 validation:** UNTOUCHED  
**2026 OOS:** UNTOUCHED  
**Rerun authorized by this closeout:** NO

## 1. Evidence boundary

This document records the first real Batch02 development verdict for B2-01.

It does **not** rerun B2-01 and does not reopen the result artifact. The execution
identity, result hash, gates, and cell metrics below are recorded from the
authorized exact-SHA development-run report produced after the independently
reviewed implementation freeze.

The frozen `V2_FORMULATION_INVENTORY` is intentionally **not modified** by this
closeout. Under the V2 charter it became immutable when the first real Batch02
outcome was read.

No B2-01 threshold, state, window, lag, horizon, target, loss, sign, comparator,
or child formulation is authorized after this verdict inside current V2.

## 2. Exact execution identity

| Field | Value |
|---|---|
| Reviewed implementation SHA | `1a0709526d6fd4bf4799bf218dba53d2d33e5bb8` |
| Git tree | `43c8c62d703f0d83c70206fdbcad2a1774d65df5` |
| Implementation merge commit | `36360523acb20a7d70d063f409b1a327c0f4cf01` |
| Prereg SHA256 | `7fe105549d756a74fd9360449e7b464bf53f51560705ba1010d127ac943838fb` |
| Dataset ID | `CORE_BTC_BINANCE_V0` |
| Dataset snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| Authorized years | 2020, 2021, 2022, 2023, 2024 |
| Development window | 2020-02-01T00:00:00Z inclusive → 2025-01-01T00:00:00Z exclusive |
| Result artifact path at execution | `/tmp/signalbot-b2-01-1a07095/artifacts/b2_01/B2_01_DEV_RESULTS.json` |
| Result artifact SHA256 | `3fa3ad61752d4d7d56d1dbfa172af95bec7712aebe5d2e2edfccb725971d4d2a` |
| Placebo seed | `20260830` |
| Bootstrap seed | `20260831` |
| Tracked repo files modified by run | NO |
| 2025 accessed | NO |
| 2026 accessed | NO |

The canonical accepted dataset root used by the run was
`/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0`. Harness bound it
to the frozen snapshot before scoring. The run report recorded 60 monthly files
spanning calendar years 2020-2024 in the Harness-bound view. January 2020 was
warmup/reference only; scored development began at 2020-02-01T00:00:00Z.
Files dated 2025/2026 present on disk were not selected.

## 3. Overall verdict

```text
B2_01_CLOSED_NO_PROMOTION
```

No promotion neighborhood satisfied the frozen contract.

The formulation is spent. This is a completed research verdict, not a software,
data, or integrity abort.

## 4. Mandatory promotion gates

| Gate | Result |
|---|---|
| `primary_positive` | PASS |
| `material_relative_mae` | FAIL |
| `bootstrap_positive` | PASS |
| `placebo_separation` | FAIL |
| `transition_ordering` | FAIL |
| `horizon_robustness` | FAIL |
| `parameter_robustness` | FAIL |
| `year_stability` | FAIL |

Literal gate contract:

```text
primary_positive=true
material_relative_mae=false
bootstrap_positive=true
placebo_separation=false
transition_ordering=false
horizon_robustness=false
parameter_robustness=false
year_stability=false
```

No cell passed all five per-cell gates. Placebo was
`SKIPPED_FAIL_CLOSED_PRECONDITION` on every cell because cheaper mandatory
preconditions had already failed. The skip remains a fail-closed
`placebo_separation=false`; it is not a pass and cannot rescue a cell.

## 5. Frozen 16-cell surface

Per-cell gate shorthand below is:

`primary_positive / material_relative_mae / bootstrap_positive / placebo_separation / transition_ordering`.

| W | D | H | N | Mean AE Δ | Median AE Δ | Rel MAE Δ | Bootstrap 95% | Transition separation | Gates | Year stability | Placebo |
|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|
| 60 | 60 | 30 | 163494 | +0.000724 | +0.000327 | +0.00242 | [0.000357, 0.001109] | -0.0654 | P/F/P/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 60 | 60 | 60 | 163427 | +0.001188 | +0.000319 | +0.00405 | [0.000701, 0.001707] | -0.0805 | P/F/P/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 60 | 60 | 120 | 163351 | +0.001657 | +0.000400 | +0.00559 | [0.001097, 0.002221] | -0.0855 | P/F/P/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 60 | 60 | 240 | 163212 | +0.001807 | +0.000348 | +0.00600 | [0.001146, 0.002517] | -0.0861 | P/F/P/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 60 | 120 | 30 | 162815 | +0.001047 | +0.000340 | +0.00350 | [0.000648, 0.001466] | -0.0670 | P/F/P/F/F | PASS | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 60 | 120 | 60 | 162720 | +0.001317 | +0.000286 | +0.00449 | [0.000766, 0.001869] | -0.0781 | P/F/P/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 60 | 120 | 120 | 162644 | +0.001330 | +0.000650 | +0.00449 | [0.000594, 0.002068] | -0.0899 | P/F/P/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 60 | 120 | 240 | 162497 | +0.001856 | +0.000292 | +0.00617 | [0.001043, 0.002698] | -0.0909 | P/F/P/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 60 | 30 | 170924 | +0.000071 | 0.000000 | +0.00023 | [-0.000346, 0.000494] | +0.0624 | P/F/F/F/P | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 60 | 60 | 170885 | -0.000780 | -0.000187 | -0.00264 | [-0.001215, -0.000352] | +0.0431 | F/F/F/F/P | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 60 | 120 | 170845 | -0.001447 | -0.000567 | -0.00486 | [-0.001873, -0.001040] | +0.0223 | F/F/F/F/P | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 60 | 240 | 170781 | -0.001439 | -0.000621 | -0.00477 | [-0.001808, -0.001068] | +0.00389 | F/F/F/F/P | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 120 | 30 | 169828 | -0.000451 | -0.000368 | -0.00148 | [-0.000814, -0.000060] | -0.0222 | F/F/F/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 120 | 60 | 169745 | -0.000925 | -0.000421 | -0.00312 | [-0.001406, -0.000427] | -0.0330 | F/F/F/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 120 | 120 | 169645 | -0.001240 | -0.000730 | -0.00417 | [-0.001843, -0.000631] | -0.0439 | F/F/F/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |
| 120 | 120 | 240 | 169533 | -0.000934 | -0.000444 | -0.00310 | [-0.001701, -0.000158] | -0.0466 | F/F/F/F/F | FAIL | SKIPPED_FAIL_CLOSED_PRECONDITION |

Maximum observed relative MAE improvement was approximately **0.617%** at
W=60, D=120, H=240, far below the frozen 2% materiality threshold.

## 6. Year stability

Mean AE improvement by fixed calendar year:

| W | D | H | 2020 | 2021 | 2022 | 2023 | 2024 | 4/5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 60 | 60 | 30 | +0.001219 | +0.000989 | +0.001896 | -0.000134 | -0.000497 | FAIL |
| 60 | 60 | 60 | +0.001964 | +0.001752 | +0.002835 | -0.000400 | -0.000435 | FAIL |
| 60 | 60 | 120 | +0.002877 | +0.002751 | +0.003053 | -0.000308 | -0.000333 | FAIL |
| 60 | 60 | 240 | +0.003120 | +0.002557 | +0.003851 | -0.000444 | -0.000329 | FAIL |
| 60 | 120 | 30 | +0.001753 | +0.001553 | +0.001668 | +0.000033 | +0.000119 | PASS |
| 60 | 120 | 60 | +0.001765 | +0.001940 | +0.002881 | -0.000086 | -0.000143 | FAIL |
| 60 | 120 | 120 | +0.002707 | +0.002179 | +0.003094 | -0.000977 | -0.000612 | FAIL |
| 60 | 120 | 240 | +0.002909 | +0.002914 | +0.003897 | -0.000699 | -0.000058 | FAIL |
| 120 | 60 | 30 | -0.000647 | -0.000929 | -0.000728 | +0.001027 | +0.001546 | FAIL |
| 120 | 60 | 60 | -0.001262 | -0.001539 | -0.001392 | -0.000169 | +0.000401 | FAIL |
| 120 | 60 | 120 | -0.001492 | -0.001751 | -0.001818 | -0.001096 | -0.001085 | FAIL |
| 120 | 60 | 240 | -0.001184 | -0.001314 | -0.001419 | -0.001915 | -0.001333 | FAIL |
| 120 | 120 | 30 | +0.000470 | -0.000103 | -0.000167 | -0.001434 | -0.000920 | FAIL |
| 120 | 120 | 60 | -0.000184 | -0.000222 | -0.000324 | -0.002215 | -0.001592 | FAIL |
| 120 | 120 | 120 | -0.000426 | -0.000307 | -0.000583 | -0.002680 | -0.002106 | FAIL |
| 120 | 120 | 240 | +0.000262 | +0.000253 | +0.000071 | -0.003019 | -0.002093 | FAIL |

Only W=60, D=120, H=30 was positive in 4/5 or more fixed years. It still
failed the materiality and transition-ordering gates and could not form a
promotion neighborhood.

## 7. Interpretation under the frozen contract

B2-01 did not establish stable material incremental information beyond current
volatility level.

The result is not a near-miss that authorizes threshold relaxation:

- all 16 cells failed the 2% relative-MAE materiality threshold;
- W=60 cells showed only small positive error improvements;
- W=120 cells were mostly worse than the current-level-only baseline;
- no adjacent-horizon robust neighborhood existed;
- no second W,D pair supplied parameter robustness;
- year stability failed in 15/16 cells;
- all W=60 cells had transition separation opposite the frozen expected sign;
- no cell reached the five-gate per-cell conjunction.

The observed weak/local structure is not promoted evidence and cannot seed a
current-V2 B2-01 rescue.

## 8. Deterministic state transition

```text
B2_01_VOLATILITY_TRANSITION = CLOSED_NO_PROMOTION
F3_VOLATILITY_DYNAMICS = CLOSED_NO_PROMOTION
B2_01_RERUN = NOT_AUTHORIZED
B2_01_REFORMULATION = NOT_AUTHORIZED_CURRENT_V2
2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```

F3 closes because B2-01 is the only frozen-inventory formulation assigned to F3
and it is now terminal as `CLOSED_NO_PROMOTION`.

The next eligible frozen formulation is:

`B2-02_BOUNDARY_INTERACTION_PATH`

This closeout does not preregister, implement, or authorize B2-02 outcome access.

## 9. Final integrity statement

`No 2025 validation or 2026 OOS outcome was used in this B2-01 development decision.`
