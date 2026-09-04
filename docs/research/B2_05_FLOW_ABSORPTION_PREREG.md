# B2-05 Flow Absorption / Price Impact — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`
**Formulation ID:** `B2-05_FLOW_ABSORPTION`
**Primary family:** F4 — participation / order-flow information
**Inventory:** `docs/research/V2_FORMULATION_INVENTORY.md`
**Machine-readable freeze:** [`B2_05_FLOW_ABSORPTION_PREREG.json`](B2_05_FLOW_ABSORPTION_PREREG.json)
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`

This is an outcome-blind preregistration only. It does not implement B2-05
runtime code, does not create a durable evidence reservation, does not
authorize dataset access, and does not run B2-05. `B2-05_FLOW_ABSORPTION` is
already `ADMIT_TO_V2_INVENTORY` (family F4) in the frozen
`V2_FORMULATION_INVENTORY.md` §9. This unit admits no new formulation; it
freezes the one finite statistical formulation the inventory already names,
before any B2-05 outcome-bearing implementation exists.

## 0. Scientific provenance

This design is derived from exactly two outcome-blind sources:

1. **The current immutable inventory** (`V2_FORMULATION_INVENTORY.md` §9),
   whose verbatim mechanism claim is: *"Conditional on comparable taker-flow
   imbalance and price/volatility state, a predeclared measure of
   contemporaneous price impact/absorption adds stable information about
   subsequent directional behavior."*
2. **The old outcome-blind B2-05 design**, historical PR #92, design head
   `5fe2c7de1358d0e5e68d85c460367d53d999f9a3` — inspected only at that exact
   commit, only for `docs/research/B2_05_FLOW_ABSORPTION_PREREG.md`/`.json`,
   as scientific-design provenance predating every later Batch02 outcome.
   PR #92 is **not merged** by this unit.

`B2-01` through `B2-04` are read only as `CLOSED_NO_PROMOTION` status facts
for governance/anti-rescue/sequencing context. No W, H, descriptor, sign,
target, baseline feature, candidate feature, threshold, state bin, training
N, placebo, bootstrap, gate, or side rule in this document was chosen or
altered because of any B2-01/02/03/04 outcome sign or magnitude. B2-05 is
not made "different" merely because a price-derived F1 formulation failed;
its mechanism (F4, participation/order-flow) was already frozen distinct in
the inventory before any Batch02 outcome existed.

**Material scientific ambiguities found: NONE.** The OLS numerical-solver
choice is resolved explicitly in §11.1 by freezing the historical
pre-outcome primitive as-is, not by asserting solver interchangeability.

## 1. Research question

H05 tested taker-imbalance magnitude directly against subsequent return and
found no promotion in 45/45 cells for either orientation. B2-05 cannot
promote imbalance itself. Its novel object is the **interaction between
aggressive taker flow and the contemporaneous price response to that
flow** — conceptually, strong aggressive buying that moves price
efficiently is a different state from strong aggressive buying that is
absorbed with little price response.

The tested claim: conditional on the same contemporaneous taker imbalance,
price response, activity, and realized volatility, does one predeclared
impact/absorption interaction add stable information about subsequent
movement in the flow direction?

## 2. Dataset, chronology and required source columns

Use accepted `CORE_BTC_BINANCE_V0` only. Source timeframe is canonical 1m;
decision grid is UTC-epoch-aligned 15m.

| Window | Start inclusive | End exclusive |
|---|---|---|
| Warmup/reference | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z |
| Development | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z |
| Untouched OOS | 2026-01-01T00:00:00Z | current snapshot boundary |

For scoring: `T + H < 2025-01-01T00:00:00Z`. Equality is illegal; no
truncation.

Required future source columns, verified against
`docs/manifests/CORE_BTC_BINANCE_V0.yaml` (`raw_schema`,
`availability_semantics`) and cross-checked against the exact accepted-parquet
column names already read by `scripts/research/h05_taker_imbalance_lib.py`:

```
open_time_ms
available_at_ms
close
base_volume
taker_buy_base_volume
```

`available_at_ms` is the canonical `bar_end_exclusive` availability field
(`available_at_ms = open_time_ms + 60000`). No quote_volume, trade_count,
order-book proxy, another venue, another contract, or inferred CVD
substitute is authorized.

## 3. Flow windows

`W ∈ {15, 30, 60}` minutes. At every UTC 15m decision `T`, use accepted 1m
rows wholly inside `[T-W, T)`.

```
TOTAL_W      = sum(base_volume)
TAKER_BUY_W  = sum(taker_buy_base_volume)
```

Require every source row: finite `base_volume`, finite
`taker_buy_base_volume`, `base_volume >= 0`,
`0 <= taker_buy_base_volume <= base_volume`. Require `TOTAL_W > 0`.
Malformed/corrupt flow data is an integrity/data failure for the affected
record and fails closed.

```
IMB     = (2*TAKER_BUY_W - TOTAL_W) / TOTAL_W
ABS_IMB = abs(IMB)
```

Exact `IMB == 0` is unavailable — flow direction is undefined. Flow side:
`BUY` if `IMB > 0`, `SELL` if `IMB < 0`. There is no imbalance
percentile/tail threshold and no H05-style extreme-flow event selection.

## 4. Baseline causal controls

```
d        = sign(IMB)
FLOW_RET = d * ln(close(T) / close(T-W))
RV_W     = sqrt(sum(r_1m^2))   over accepted 1m returns in [T-W,T)
LOG_ACTIVITY = ln(TOTAL_W)
```

Require `RV_W` finite and `> 0`; require `LOG_ACTIVITY` finite. These are
baseline controls, not candidate novelty: the baseline explicitly contains
`ABS_IMB` and `FLOW_RET`, so B2-05 cannot win by rediscovering raw imbalance
or raw contemporaneous price movement.

## 5. Exactly one structural object

```
IMPACT_INTERACTION = ABS_IMB * FLOW_RET
```

Interpretation: large positive — strong aggressive-flow imbalance
accompanied by aligned price response; near zero — meaningful flow with
weak aligned price response (absorption-like state); negative — price
moves opposite the aggressive-flow direction. This is a descriptive
interpretation only, not a trading-interpretation authorization.

Forbidden alternatives: `IMB / price_move`, `price_move / IMB`, epsilon
denominators, order-book proxy, CVD substitute, volume-delta substitute, a
different impact formula, thresholded absorption, a BUY-only descriptor, a
SELL-only descriptor, or a second interaction descriptor. Exactly one
descriptor.

## 6. Causal impact state

For each current record `(W, side, T)`, reference historical records with:
same `W`; same `BUY`/`SELL` side; `T_ref < T`; `T_ref >= T - 180 calendar
days`; finite `IMPACT_INTERACTION` known at `T_ref`. Current record
excluded. Minimum reference `N = 120`.

```
p = (count(ref < x) + 0.5*count(ref == x)) / N_ref
```

`LOW = [0,1/3)`, `MID = [1/3,2/3)`, `HIGH = [2/3,1]`. Every historical state
is computed exactly once as-of its own `T_e` and never recomputed using
later records.

Frozen directional ordering: **`HIGH > MID > LOW`** for subsequent
flow-direction-normalized outcome after baseline control. This expected
ordering is part of the preregistration and may not be reversed
post-outcome.

## 7. Target

`H ∈ {30, 60, 120, 240}` minutes.

```
FLOW_CONT_RET_H(T) = d * ln(close(T+H) / close(T))
Y_H(T) = FLOW_CONT_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)
```

`PAST_MEDIAN_ABS_RET_H(T) = median(abs(ln(close(t+H)/close(t))))` over all
canonical UTC 15m reference boundaries `t ∈ [T-30 calendar days, T)` with
`t+H <= T`. Current `T` excluded. The reference population is the
canonical aligned grid, **not** B2-05 candidate/trigger records. Require
the denominator finite and `> 0`. No future-informed floor, no
full-sample normalization.

## 8. Training model

Causal weekly walk-forward OLS. Refit at UTC ISO week start `S` (Monday
00:00:00Z), held fixed through the week.

Training rows: `T_e < S`, `T_e >= S - 365 calendar days`, `T_e + H <= S`.

**Baseline** features exactly: `intercept, ABS_IMB, FLOW_RET, RV_W,
LOG_ACTIVITY, SIDE_BUY` (`SIDE_BUY = 1` for BUY, `0` for SELL).

**Candidate** contains every baseline feature plus `IMPACT_LOW,
IMPACT_HIGH` (`MID` is the reference state). No interaction term other than
the frozen state itself; no polynomials; no feature search; no alternate
model.

## 9. Historical candidate eligibility and minimums

Baseline historical training may be broader. Candidate historical training
requires: a baseline-eligible row, a valid causal `IMPACT_STATE`, and both
valid causal placebo nuisance bins (§15).

Minimum baseline `N = 500`. Minimum candidate `N = 500`, with `>= 100`
records in each `LOW`/`MID`/`HIGH` state. If either weekly model is
unavailable, current scoring is unavailable for **both** candidate and
comparator. No fallback.

## 10. Preprocessing

Continuous columns `ABS_IMB, FLOW_RET, RV_W, LOG_ACTIVITY` are standardized
independently for each model using that model's own frozen causal training
rows at `S`: `z = (x - training_mean) / training_std`. Binary/state dummies
(`intercept, SIDE_BUY, IMPACT_LOW, IMPACT_HIGH`) are not standardized.
Require every continuous training std finite and strictly `> 0`.

Canonical row order — ascending `CANONICAL_SCORE_RECORD_ID` — is applied
before training statistics, matrix construction, fit, and audit hashes.

```
Baseline design:  [intercept, ABS_IMB_z, FLOW_RET_z, RV_W_z, LOG_ACTIVITY_z, SIDE_BUY]
Candidate design: [intercept, ABS_IMB_z, FLOW_RET_z, RV_W_z, LOG_ACTIVITY_z, SIDE_BUY,
                    IMPACT_LOW, IMPACT_HIGH]
```

### 11.1 OLS solver contract — frozen to the historical pre-outcome primitive

The old outcome-blind design at PR #92 commit
`5fe2c7de1358d0e5e68d85c460367d53d999f9a3` froze:

```
coef, residuals, rank, singular_values = numpy.linalg.lstsq(X, y, rcond=None)
```

with an explicit post-hoc full-column-rank check (`rank ==
number_of_columns`) and an explicit finite-coefficients check. This
prereg restores and freezes that exact primitive, unchanged, rather than
the normal-equation (Gram-matrix Cholesky rank test followed by
`np.linalg.solve(X'X, X'y)`) pattern used by the already-merged B2-04
implementation.

Normal-equation solving through `X'X` is **not** numerically equivalent
to `numpy.linalg.lstsq` on all finite full-rank but ill-conditioned
designs; finite-precision divergence between the two paths can affect
fit availability, coefficients, predictions, AE improvement, and
promotion outcomes. The B2-04 Cholesky-vs-`lstsq` equivalence proof
(max absolute coefficient difference ≈5.6e-13 across 120 random
well-posed designs) does not license substituting one solver for the
other inside this prereg's frozen contract, so B2-05 does **not** adopt
the B2-04 substitution and instead freezes the historical primitive
as-is.

Required behavior:

- `X` and `y` finite before fit.
- `rank == number_of_columns` (full column rank required).
- All returned coefficients finite.
- No exception raised by the fit call.
- Fit unavailable ⇒ weekly model `UNAVAILABLE_FOR_DECISION`; no fallback.

Explicitly forbidden: `numpy.linalg.pinv`, a Gram-matrix Cholesky
decomposition of `X'X`, `np.linalg.solve(X'X, X'y)` or any other
normal-equation substitution, silent minimum-norm fits, column dropping,
ridge/lasso regularization, any solver fallback, a new condition-number
cutoff, and any singular-value threshold beyond the `lstsq`-returned
rank. Preprocessing (§10) is unchanged by this resolution.

## 12. Same support

Current scoring requires: valid current B2-05 features, valid
`IMPACT_STATE`, both frozen weekly models, valid mature `Y_H`, and legal
development boundary. Candidate and comparator must score the **exact
same `CANONICAL_SCORE_RECORD_ID` set**. Baseline may have more historical
training rows; baseline may **not** have more current evaluation rows. No
BUY-only rescue, SELL-only rescue, year-only support, horizon-only
support, or post-outcome support filter.

## 13. Canonical event identity

```
CANONICAL_BASE_EVENT_ID  = snapshot_id|1m|15m|W_minutes|side|interval_start_ms|interval_end_ms|T_ms
CANONICAL_SCORE_RECORD_ID = CANONICAL_BASE_EVENT_ID|H_minutes
```

where `interval_start_ms = T_ms - W_minutes*60000`, `interval_end_ms =
T_ms`, `T_ms` is decision time `T` as integer UTC epoch milliseconds, and `side`
is exactly `BUY` or `SELL` (uppercase ASCII, `W_minutes`/`H_minutes` plain
base-10 integers, no leading zero). No
generic T-only identity; no dedup by `T` alone. Baseline and candidate
carry identical score-record IDs on the same support.

## 14. Placebo nuisance bins

For placebo stratification only (never a candidate feature), compute/store
as-of each `T_e` deterministic trailing-180-day same-`W`/side midrank
quintiles for `ABS_IMB` and `FLOW_RET`, each with reference `T_ref ∈
[T_e-180 calendar days, T_e)`, `T_ref < T_e` explicitly, minimum `N = 120`,
current row excluded.

`Q1=[0.0,0.2)`, `Q2=[0.2,0.4)`, `Q3=[0.4,0.6)`, `Q4=[0.6,0.8)`,
`Q5=[0.8,1.0]`. An exact boundary value belongs to the bin whose lower
bound it equals; `p=1.0` belongs to `Q5`. Each bin is computed once as-of
its own `T_e` and stored; never recomputed. A missing nuisance bin makes a
candidate historical row ineligible; baseline eligibility is unaffected if
baseline fields and mature target are valid. This exists solely so real
and placebo candidate training use identical support.

## 15. Placebo

`N_PLACEBO = 100`, `SEED_PLACEBO = 20260907`.

For every causal weekly candidate fit, use exactly the real candidate's
causal training rows. Strata: `calendar_month_utc(T_e) × side × ABS_IMB
quintile × FLOW_RET quintile`, exact string
`YYYY-MM|SIDE=<BUY|SELL>|IMB_Q=<Q1..Q5>|FLOW_Q=<Q1..Q5>`.

Within each non-empty stratum: sort the real candidate's training rows
ascending by `CANONICAL_BASE_EVENT_ID`; encode stored state labels as a
NumPy `int64` vector (`LOW=0, MID=1, HIGH=2`) in that order; instantiate
the frozen seed's `numpy.random.default_rng`; compute `permuted_labels =
rng.permutation(input_label_vector)`; assign positionally back to the
same sorted rows. Do not permute `Y`, baseline features, timestamps, row
IDs, or nuisance bins. The current evaluation event's own impact state
remains real/fixed. A zero-record stratum is not instantiated. A
one-record stratum still instantiates its RNG and calls `rng.permutation`
on the one-element vector, leaving the label unchanged; no replacement
labels, no changed support.

Seed raw UTF-8:

```
20260907|replicate_index|W_minutes|H_minutes|week_start_ms|stratum_id
```

`replicate_index ∈ {0,...,99}` zero-based, `week_start_ms` is integer UTC
epoch milliseconds for Monday 00:00:00Z.

```
digest   = sha256(raw_utf8).digest()
seed_int = int.from_bytes(digest[:8], "big", signed=False)
rng      = numpy.random.default_rng(seed_int)
```

No Python `hash()`, no alternate byte order, no alternate digest slice, no
1-based replicate numbering.

### 15.1 Placebo failure semantics (frozen fail-closed, B2-04-repaired rule)

Exactly 100 nominal placebo replicates. A cell has a valid `placebo_q95`
**only if all 100 replicate cell statistics are finite**. If the finite
count is `< 100`: `placebo_q95` is unavailable and `placebo_separation =
False`. No resampling, no replacement replicate, no partial `q95`. If a
replicate fails to produce a finite statistic for even one scored
evaluation event in the cell, the **whole cell-level replicate** at that
index is invalid — it may not become a partial replicate. When `100/100`
are valid, use `numpy.quantile(..., 0.95, method="linear")`.

## 16. Bootstrap

`N_BOOTSTRAP = 2000`, `SEED_BOOTSTRAP = 20260908`, block = UTC ISO week.

Per cell `(W,H)`: `week_id = ISOYEAR-Www` from decision time `T`
(`datetime.isocalendar()`, UTC — **not** the Gregorian calendar year). Sort
unique week IDs ascending lexicographically. Within each block sort score
IDs ascending. Seed raw UTF-8 `20260908|W_minutes|H_minutes`; `seed_int =
int.from_bytes(sha256(raw).digest()[:8], "big", signed=False)`; one
`numpy.random.default_rng(seed_int)` per cell, a single generator stream
for all 2000 replicates in ascending order.

Per replicate: `rng.integers(0, n_week_blocks, size=n_week_blocks,
dtype=np.int64)`; concatenate whole selected week blocks in draw order,
preserving block multiplicity and within-week canonical order. Statistic:
`mean(AE_IMPROVEMENT)`. Intervals: percentiles `0.025`/`0.975`, method
`linear`.

`n_week_blocks == 0`: bootstrap unavailable, `bootstrap_positive = False`.
`n_week_blocks == 1`: that one whole block is used once in every
replicate.

## 17. Metrics

```
BASE_AE = abs(Y_H - BASE_PRED)
CAND_AE = abs(Y_H - CAND_PRED)
AE_IMPROVEMENT = BASE_AE - CAND_AE
```

Positive favors candidate.
`RELATIVE_MAE_IMPROVEMENT = 1 - mean(CAND_AE)/mean(BASE_AE)`, requiring
`mean(BASE_AE)` finite and `> 0`. Materiality threshold `>= 0.02`. No
squared-error rescue.

## 18. Structural diagnostic

`BASE_RESIDUAL = Y_H - BASE_PRED`. Per cell, compute median `BASE_RESIDUAL`
in `LOW`, `MID`, `HIGH`. Expected `median_LOW < median_MID < median_HIGH`.
Also compute `HIGH - LOW` separation separately for `BUY` and `SELL`.

## 19. Search surface

Exactly `W ∈ {15, 30, 60}` × `H ∈ {30, 60, 120, 240}` = **12 primary
cells**. One descriptor, one model family, no thresholds, no parameter
additions.

## 20. Per-cell conditions (exactly six)

- `primary_positive`: pooled `mean(AE_IMPROVEMENT) > 0`. (The old
  outcome-blind design's `primary_positive` predicate is pooled-only; side
  symmetry is enforced separately, in full, by `side_stability` below —
  preserved exactly, not invented.)
- `material_relative_mae`: pooled relative MAE improvement `>= 0.02`.
- `bootstrap_positive`: pooled UTC-week bootstrap 95% lower bound `> 0`.
- `placebo_separation`: pooled `mean(AE_IMPROVEMENT) >` frozen placebo
  `q95` (§15.1's 100/100 validity rule).
- `impact_ordering`: `median(BASE_RESIDUAL|LOW) < median(BASE_RESIDUAL|MID)
  < median(BASE_RESIDUAL|HIGH)`, all three states non-empty and finite.
- `side_stability`: for **each** of `BUY` and `SELL` independently, `mean
  (AE_IMPROVEMENT) > 0` **and** `median(BASE_RESIDUAL|HIGH) -
  median(BASE_RESIDUAL|LOW) > 0`. Both sides required.

## 21. Promotion neighborhood (three more gates)

Adjacent `H` pairs: `{30,60}`, `{60,120}`, `{120,240}`.

- `horizon_robustness`: for one `W`, both cells of an adjacent-`H` pair
  pass all six per-cell conditions.
- `parameter_robustness`: the **same** adjacent-`H` pair also passes all
  six per-cell conditions at **another** `W`. No single `W` may promote
  alone.
- `year_stability`: every cell in the qualifying neighborhood (the
  adjacent-`H` pair at both promoting `W` values — four cells) has pooled
  mean AE improvement `> 0` in at least 4 of 5 years `{2020,2021,2022,
  2023,2024}`. No year exclusions.

A neighborhood is one adjacent-`H` pair crossed with exactly two distinct
`W` values (four cells). Enumerate deterministically in frozen `H`-pair
order `[30,60],[60,120],[120,240]`, then ascending `W`-pair; select the
first qualifying neighborhood. No ranking by effect size. No mosaic
promotion.

## 22. Nine top-level gates (exact)

```
primary_positive
material_relative_mae
bootstrap_positive
placebo_separation
impact_ordering
side_stability
horizon_robustness
parameter_robustness
year_stability
```

No tenth hidden gate. Missing/nonfinite/invalid mandatory evidence is
`False`.

## 23. Verdicts

Exactly `B2_05_PROMOTED_CANDIDATE` or `B2_05_CLOSED_NO_PROMOTION`.
Integrity/source/execution/retention failures are **neither** verdict.
`B2_05_CLOSED_NO_PROMOTION` forbids afterward: a second impact descriptor,
imbalance threshold rescue, ratio rescue, BUY rescue, SELL rescue, sign
reversal, a new `H`, or a new `W`. No further taker-imbalance threshold
child is admitted in current V2.

## 24. Future durable-evidence ceremony (not executed in this unit)

The future implementation **must** use the already-accepted B2-03+
contract:

```
verify_batch02_code
prepare_batch02_evidence_reservation
prepare_batch02_retained_run
load_authorized_parquet_table
evaluate_b2_05
persist_batch02_retained_result
archive_batch02_result
```

Protected production slot: **`B2-05`**. Production endpoint:
`https://github.com/sh1zok1d/signalbot.git`. Evidence ref:
`refs/heads/research-evidence/batch02/B2-05/<execution_code_sha>`. Future
local result: `artifacts/b2_05_flow_absorption/
B2_05_FLOW_ABSORPTION_DEV_RESULTS.json`. No historical `prepare_batch02_run`
/`persist_batch02_result`. No direct parquet reads in the production B2-05
runner. No result may be returned before durable archive and readback
succeed. The default future runner must refuse before reservation unless
`outcome_access_acknowledged` is the literal boolean `True`.

This preregistration unit:

- `B2_05_RESERVATION_CREATED = NO`
- `B2_05_OUTCOME_ACCESS_CLAIMED = NO`
- `B2_05_RUN = NO`

`outcome_access_authorized = false`.

## 25. Implementation prohibition (this unit)

This unit must **not** create:

- `scripts/research/b2_05_*.py`
- a B2-05 result artifact
- a runner, evaluator, CORE loader invocation, reservation, or claim
