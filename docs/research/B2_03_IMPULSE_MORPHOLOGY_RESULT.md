# B2-03 Impulse Morphology — Development Result Closeout

**Formulation:** `B2-03_IMPULSE_MORPHOLOGY`
**Primary family:** F1 — directional persistence / continuation
**Research verdict:** `B2_03_CLOSED_NO_PROMOTION`
**Formulation status:** `CLOSED_NO_PROMOTION`
**Family status after closeout:** `ACTIVE` (B2-04 remains frozen and untested)
**2025 validation:** UNTOUCHED
**2026 OOS:** UNTOUCHED
**Rerun authorized by this closeout:** NO
**Scientific development executions that crossed `OUTCOME_ACCESS_CLAIMED`:** 1

## 1. Evidence boundary

This document records the one authorized B2-03 development verdict.

It does **not** rerun B2-03 and does not reopen or modify the persisted result
artifact. The execution identity, artifact digest, promotion gates, and cell
metrics below are transcribed from the archived canonical result after
independent remote readback of the durable evidence ref.

The frozen `V2_FORMULATION_INVENTORY` is intentionally **not modified** by this
closeout. Under the V2 charter it became immutable when the first real Batch02
outcome was read.

No B2-03 threshold, morphology component, weighting, window, horizon, target,
loss, sign, comparator, exhaustion reinterpretation, or child formulation is
authorized after this verdict inside current V2.

## 2. Identity

| Field | Value |
|---|---|
| Hypothesis ID | `B2-03_IMPULSE_MORPHOLOGY` |
| Execution SHA | `8a7490167e086a201ec7b3780878d2cf3252ecfd` |
| Execution tree | `b83f4f5dfa82da6d9ab219829bbcccd214d2f11a` |
| Prereg merge SHA | `61bc9cfde80c6a142ac147ebee6487a1ae710324` |
| Dataset ID | `CORE_BTC_BINANCE_V0` |
| Dataset snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| Stage | `development` |
| Authorized years | 2020, 2021, 2022, 2023, 2024 |
| Development window | 2020-02-01T00:00:00Z inclusive → 2025-01-01T00:00:00Z exclusive |
| Canonical runner | `scripts.research.b2_03_impulse_morphology.run_development` |
| Outcome-access flag | `outcome_access_acknowledged=True` |
| Placebo seed | `20260904` |
| Bootstrap seed | `20260905` |
| Primary cells | 15 (`W ∈ {15,30,60}` × `H ∈ {15,30,60,120,240}`) |
| Constructed events | 131469 |
| Tracked repo files modified by run | NO |
| 2025 accessed | NO |
| 2026 accessed | NO |

The canonical accepted dataset root used by the run was
`/workspace/artifacts/research_data/CORE_BTC_BINANCE_V0`. Forbidden-window
evidence is derived from the authorized view and loaded bytes: 60 monthly
partitions, calendar years 2020-2024 only,
`authorized_max_partition_year=2024`. January 2020 was warmup/reference only;
scored development began at 2020-02-01T00:00:00Z. No 2025 or 2026 objects were
selected.

Observed loaded max `available_at_ms` equals `1735689600000`
(2025-01-01T00:00:00Z), the exclusive development end. That exclusive endpoint
is not a 2025 validation access.

## 3. Durable evidence

| Field | Value |
|---|---|
| Evidence ref | `refs/heads/research-evidence/batch02/B2-03/8a7490167e086a201ec7b3780878d2cf3252ecfd` |
| RESERVED commit SHA | `5dec8d075e5e35db3946fef4e0b530fd719cc7d3` |
| OUTCOME_ACCESS_CLAIMED commit SHA | `7a7adf1e4236286d8c69bb67efd51271ffc5473e` |
| ARCHIVED commit SHA | `16854498afc34c69f62e46a387ef08e7896a5172` |
| Artifact SHA256 | `a3586344ac9c094eb38670a16b7566b8c1628300b6a1f6605fd69c369894b0c0` |
| Artifact size | 68487026 bytes |
| Archive path | `batch02/B2-03/8a7490167e086a201ec7b3780878d2cf3252ecfd/a3586344ac9c094eb38670a16b7566b8c1628300b6a1f6605fd69c369894b0c0.json` |
| Final durable state | `ARCHIVED` |

The 68 MB event-level artifact remains on the evidence ref. It is not copied
into `main`.

## 4. Frozen claim

B2-03 tested one frozen F1 claim:

> Conditional on comparable signed displacement, current volatility state, and
> decision horizon, the shape of the already-realized price path that produced
> that displacement adds stable incremental information about subsequent
> directional persistence.

Magnitude is a baseline control, not the candidate. The candidate is one finite
equal-weighted morphology descriptor
(`DISTRIBUTEDNESS`, `PATH_EFFICIENCY`, `DIRECTIONAL_BAR_SHARE`,
`COUNTERMOVE_SHALLOWNESS`) scored against a same-event displacement/volatility
baseline on the frozen 15-cell `(W,H)` surface.

This is not a retest of H03 impulse extremeness.

## 5. Final verdict

```text
B2_03_CLOSED_NO_PROMOTION
```

Promotion: `false`

The exact preregistered impulse-morphology formulation did not satisfy its
frozen promotion standard on the development design.

This is a completed research verdict, not a software, data, or integrity abort.
It does not mean bearish, bullish, or no-trade.

## 6. Promotion gates

| Gate | Result |
|---|---|
| `primary_positive` | FAIL |
| `material_relative_mae` | FAIL |
| `bootstrap_positive` | FAIL |
| `placebo_separation` | FAIL |
| `morphology_ordering` | FAIL |
| `horizon_robustness` | FAIL |
| `parameter_robustness` | FAIL |
| `year_stability` | FAIL |

Literal gate contract:

```text
primary_positive=false
material_relative_mae=false
bootstrap_positive=false
placebo_separation=false
morphology_ordering=false
horizon_robustness=false
parameter_robustness=false
year_stability=false
```

Qualifying neighborhoods: `[]`. No cell passed the frozen five-condition
primary standard.

## 7. Result summary

- constructed events: 131469
- 15 primary cells
- no qualifying neighborhoods
- negative pooled incremental loss result across all 15 cells
- `positive_years=0` throughout

Result shape, transcribed from the archive:

- all 15 cells had negative pooled mean AE improvement;
- all 15 cells had negative relative MAE improvement;
- all 15 bootstrap 95% intervals were entirely below zero;
- `positive_years = 0` for every cell;
- no cell passed the frozen five-condition primary standard;
- four cells passed local `morphology_ordering` only: W15/H240, W30/H120,
  W60/H120, W60/H240.

Those isolated ordering passes do **not** authorize rescue. The primary
loss-improvement conditions failed on every cell, including those four.

This is not a near miss.

## 8. Full primary-cell table

Values are transcribed from the archived artifact
`a3586344ac9c094eb38670a16b7566b8c1628300b6a1f6605fd69c369894b0c0`.
They are not recomputed.

| W | H | N | UP | DOWN | mean_ae_improvement | relative_mae_improvement | bootstrap_lower_95 | bootstrap_upper_95 | placebo_q95 | morphology_separation_pooled | morphology_separation_up | morphology_separation_down | positive_years |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 15 | 32413 | 16291 | 16122 | -0.006493911 | -0.004125964 | -0.008353183 | -0.004685612 | -0.004473368 | -0.059344748 | -0.054756456 | -0.074031120 | 0 |
| 15 | 30 | 32413 | 16291 | 16122 | -0.007456659 | -0.004792817 | -0.009192188 | -0.005729273 | -0.004943495 | 0.012716590 | 0.039125354 | -0.007905500 | 0 |
| 15 | 60 | 32413 | 16291 | 16122 | -0.007088839 | -0.004424959 | -0.008834780 | -0.005346116 | -0.004989582 | 0.003670067 | 0.042497486 | -0.028349515 | 0 |
| 15 | 120 | 32397 | 16287 | 16110 | -0.008209882 | -0.005083986 | -0.009891846 | -0.006467100 | -0.005190317 | 0.013573018 | -0.002795767 | 0.031726638 | 0 |
| 15 | 240 | 32370 | 16272 | 16098 | -0.005839438 | -0.003618008 | -0.007395783 | -0.004218609 | -0.004686968 | 0.034472933 | 0.036038499 | 0.032830909 | 0 |
| 30 | 15 | 33530 | 16946 | 16584 | -0.005612020 | -0.003613857 | -0.007401268 | -0.003789918 | -0.005193960 | -0.082701430 | -0.092639159 | -0.069689764 | 0 |
| 30 | 30 | 33530 | 16946 | 16584 | -0.005886601 | -0.003842902 | -0.007681635 | -0.004119563 | -0.004459615 | -0.017117595 | -0.010820998 | -0.019002830 | 0 |
| 30 | 60 | 33529 | 16946 | 16583 | -0.006379830 | -0.004039799 | -0.008181739 | -0.004581250 | -0.004680666 | -0.005232627 | 0.043472187 | -0.041309734 | 0 |
| 30 | 120 | 33519 | 16941 | 16578 | -0.005649493 | -0.003527912 | -0.007429786 | -0.003896286 | -0.004234059 | 0.013347350 | 0.018510527 | 0.026664588 | 0 |
| 30 | 240 | 33483 | 16927 | 16556 | -0.005478058 | -0.003418507 | -0.006967932 | -0.003923700 | -0.004185423 | 0.006450003 | 0.039016949 | -0.028519407 | 0 |
| 60 | 15 | 33705 | 17428 | 16277 | -0.006226250 | -0.004006667 | -0.008160531 | -0.004342103 | -0.004633039 | -0.065596390 | -0.050197468 | -0.066124926 | 0 |
| 60 | 30 | 33705 | 17428 | 16277 | -0.004877197 | -0.003186521 | -0.006665826 | -0.003188749 | -0.004697975 | -0.048700756 | -0.053034364 | -0.041545877 | 0 |
| 60 | 60 | 33705 | 17428 | 16277 | -0.004972598 | -0.003169783 | -0.006516094 | -0.003514842 | -0.004429766 | -0.021576499 | -0.001176321 | -0.055138261 | 0 |
| 60 | 120 | 33694 | 17422 | 16272 | -0.005338713 | -0.003383378 | -0.006950412 | -0.003789522 | -0.003570477 | 0.011908888 | 0.022022313 | 0.009528974 | 0 |
| 60 | 240 | 33660 | 17407 | 16253 | -0.005317787 | -0.003351401 | -0.006730544 | -0.003853758 | -0.003642519 | 0.024464533 | 0.024173270 | 0.020457358 | 0 |

Per-cell gates (`primary_positive`, `material_relative_mae`,
`bootstrap_positive`, `placebo_separation`, `morphology_ordering`):

| W | H | primary_positive | material_relative_mae | bootstrap_positive | placebo_separation | morphology_ordering |
|---:|---:|---|---|---|---|---|
| 15 | 15 | false | false | false | false | false |
| 15 | 30 | false | false | false | false | false |
| 15 | 60 | false | false | false | false | false |
| 15 | 120 | false | false | false | false | false |
| 15 | 240 | false | false | false | false | true |
| 30 | 15 | false | false | false | false | false |
| 30 | 30 | false | false | false | false | false |
| 30 | 60 | false | false | false | false | false |
| 30 | 120 | false | false | false | false | true |
| 30 | 240 | false | false | false | false | false |
| 60 | 15 | false | false | false | false | false |
| 60 | 30 | false | false | false | false | false |
| 60 | 60 | false | false | false | false | false |
| 60 | 120 | false | false | false | false | true |
| 60 | 240 | false | false | false | false | true |

Mean AE improvement by fixed calendar year:

| W | H | 2020 | 2021 | 2022 | 2023 | 2024 | positive_years |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 15 | -0.008253709 | -0.006249907 | -0.008013934 | -0.005765401 | -0.004435634 | 0 |
| 15 | 30 | -0.005068959 | -0.007010582 | -0.008317571 | -0.008926140 | -0.007574673 | 0 |
| 15 | 60 | -0.003915181 | -0.004287796 | -0.008737143 | -0.008556094 | -0.009388988 | 0 |
| 15 | 120 | -0.007872488 | -0.008650764 | -0.006358115 | -0.008570936 | -0.009577582 | 0 |
| 15 | 240 | -0.005400756 | -0.005079404 | -0.006011593 | -0.007601538 | -0.005029718 | 0 |
| 30 | 15 | -0.006361615 | -0.006286303 | -0.005590232 | -0.003300291 | -0.006599543 | 0 |
| 30 | 30 | -0.005642899 | -0.008267583 | -0.003095060 | -0.004392518 | -0.008010574 | 0 |
| 30 | 60 | -0.006898820 | -0.004724885 | -0.005034764 | -0.006160159 | -0.009082311 | 0 |
| 30 | 120 | -0.007338344 | -0.005055153 | -0.003670306 | -0.005778095 | -0.006658539 | 0 |
| 30 | 240 | -0.005984312 | -0.001766957 | -0.006829846 | -0.007160531 | -0.005654906 | 0 |
| 60 | 15 | -0.004292135 | -0.008671386 | -0.006356382 | -0.003792280 | -0.007737868 | 0 |
| 60 | 30 | -0.004044142 | -0.004863625 | -0.004367008 | -0.006674578 | -0.004342411 | 0 |
| 60 | 60 | -0.003097675 | -0.005973429 | -0.005438428 | -0.005543718 | -0.004546627 | 0 |
| 60 | 120 | -0.005898934 | -0.005249396 | -0.005861547 | -0.005481495 | -0.004284797 | 0 |
| 60 | 240 | -0.005692099 | -0.005085425 | -0.005721593 | -0.005007642 | -0.005124556 | 0 |

## 9. Interpretation

The exact preregistered impulse-morphology formulation did not satisfy its
frozen promotion standard on the development design.

This rejects only that frozen B2-03 formulation. It does not imply market
direction. `NO_PROMOTION` is not bearish, not bullish, and not no-trade.

A more distributed / efficient / directionally persistent / shallow-countermove
path did not add stable incremental continuation information beyond the
same-event displacement and volatility baseline under the frozen contract.

## 10. Anti-rescue statement

```text
B2-03 rerun = FORBIDDEN
current-V2 morphology retune = FORBIDDEN
post-hoc threshold rescue = FORBIDDEN
exhaustion reinterpretation = FORBIDDEN
```

Also forbidden inside current V2:

- another W/H grid;
- another morphology component or weighting;
- a sign reversal of `MORPHOLOGY_SEPARATION`;
- a one-sided UP/DOWN rescue;
- a child based on W15/H240, W30/H120, W60/H120, W60/H240, or any other cell;
- opening 2025 or 2026 to rescue this development verdict.

Any such idea conceived after these outcomes remains future-program material
only and cannot enter current V2.

## 11. Deterministic state transition

```text
B2_03_IMPULSE_MORPHOLOGY = CLOSED_NO_PROMOTION
F1_DIRECTIONAL_PERSISTENCE = ACTIVE
B2_03_RERUN = NOT_AUTHORIZED
B2_03_REFORMULATION = NOT_AUTHORIZED_CURRENT_V2
2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```

F1 remains `ACTIVE` because B2-04 is still a frozen inventory member with no
real outcomes. B2-03's closeout does not close the family.

Next planned formulation: B2-04.

This closeout does not preregister, implement, or authorize B2-04 outcome
access.

## 12. Pre-claim operational abort

The first authorized invocation aborted before reservation and before
`OUTCOME_ACCESS_CLAIMED` because isolated evidence Git HTTPS authentication
could not prompt (`PRE_CLAIM_OPERATIONAL_ABORT`). That abort is not
`RUN_INTEGRITY_FAILURE` and is not a market verdict.

The later authorized retry is the only invocation that crossed
`OUTCOME_ACCESS_CLAIMED` and accessed CORE. Scientific development execution
count remains 1.

## 13. Final integrity statement

`No 2025 validation or 2026 OOS outcome was used in this B2-03 development decision.`
