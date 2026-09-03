# B2-03 Impulse Morphology — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`
**Formulation ID:** `B2-03_IMPULSE_MORPHOLOGY`
**Primary family:** F1 — directional persistence / continuation
**Inventory:** `docs/research/V2_FORMULATION_INVENTORY.md`
**Machine-readable freeze:** `docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.json`
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
**Real B2-03 outcomes opened by this unit:** NO
**2025 validation opened:** NO
**2026 OOS opened:** NO
**B2-01 rerun by this unit:** NO
**B2-02 rerun by this unit:** NO

This is an outcome-blind preregistration only. It does not implement B2-03 runtime code, does not create a durable evidence reservation, does not authorize dataset access, and does not run B2-03. It admits no new formulation: `B2-03_IMPULSE_MORPHOLOGY` is already `ADMIT_TO_V2_INVENTORY` in the frozen `V2_FORMULATION_INVENTORY.md` §7. This unit freezes its one finite statistical formulation before any B2-03 outcome-bearing implementation exists.

## 1. Research question

Conditional on comparable signed displacement, current volatility state, and decision horizon, does the shape of the already-realized price path that produced that displacement add stable incremental information about subsequent directional persistence?

The tested object is the **realized path morphology** — how the displacement was built, not how large it was. Magnitude is a baseline control, not the candidate signal.

## 2. H03 inheritance and novelty boundary

H03 tested impulse **extremeness**: `W ∈ {15,30,60}` minutes, tail thresholds `q ∈ {0.90,0.95,0.98}`, continuation vs exhaustion of the impulse direction. It produced `H03_REJECTED_SPECIFIC_CLAIM` — a mixed/null, sign-unstable surface across its 45 cells. Impulse magnitude alone, at any tested tail severity, is not carried forward as a mechanism.

B2-03 does **not** retest extremeness in any disguised form. It specifically:

- does not retune `q` or introduce any tail-percentile trigger for event admission;
- does not select another extreme-move cutoff;
- does not promote one H03 cell or select a direction from H03 residuals;
- does not introduce a second extremeness definition;
- does not reinterpret `H03_REJECTED_SPECIFIC_CLAIM` as positive evidence for anything.

`W ∈ {15,30,60}` minutes is inherited only as the fixed **path-scale family** already established across H01/H02/H03/B2-01, not chosen because any H03 `(W,q)` cell looked attractive. Every displacement at every `W`, however small, is eligible — there is no admission threshold on `ABS_DISP_W(T)`. Magnitude enters this design only as a percentile **baseline control state** (§9.2), exactly as H02's boundary magnitude was a control in B2-02, never as an event-admission gate.

The distinct tested object is: **given two displacements of comparable size (same `DISPLACEMENT_MAG_STATE`) and comparable volatility (same `VOL_STATE`), does the *shape* of the sub-path that produced each displacement carry different forward information?** This is a claim about path morphology conditional on displacement, not a claim about which displacements are worth watching.

## 3. Dataset, chronology and decision-time rule

Use accepted `CORE_BTC_BINANCE_V0` only. Source is canonical 1m history; the morphology path representation is derived UTC-aligned complete 5-minute bars.

| Window | Start inclusive | End exclusive | Use |
|---|---|---|---|
| Warmup/reference | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features/history only |
| Development | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | authorized only after exact-SHA gate |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | forbidden |
| Untouched OOS | 2026-01-01T00:00:00Z | current snapshot boundary | forbidden |

`close(T)` is the close of the last complete canonical 1-minute bar whose bar-end-exclusive equals `T`; because every decision time `T` on the hourly grid is also a 5-minute-grid boundary, this is simultaneously the close of the last complete 5-minute bar ending at `T`. The still-forming bar is never used.

## 4. Decision grid — freeze without magnitude-trigger selection

Decision times `T` are frozen to **UTC hourly boundaries only**: `00:00, 01:00, ..., 23:00` on every calendar day from warmup start through the last full hour strictly before development end.

There is **no threshold-triggered event admission**. No refractory rule is needed: the hourly grid itself provides deterministic, non-overlapping event spacing. This is a structural preregistration choice made to avoid reopening H03's magnitude-threshold surface, to prevent dense adjacent detections of the same underlying move, and to provide deterministic event identity with enough 90-day causal training support — it is not selected because any hourly-grid result looked attractive; no B2-03 outcome exists to have looked at.

Event eligibility for a given `(T, W)` pair — independently per `W`, since each `W` defines its own displacement and its own morphology path — requires:

- `T` is an hourly UTC boundary with `T >= WARMUP_START` and `T` strictly before `2025-01-01T00:00:00Z`;
- `D_W(T) != 0` (§5);
- every source bar/bucket the record needs (the `W`-window 5m returns, the 60m PRE_VOL window) is fully available, with `available_at <= T` for every one of them (§5, §9.3).

Records with `T` in `[2020-01-01T00:00:00Z, 2020-02-01T00:00:00Z)` (warmup) are constructible and may serve only as causal reference/training material for later records; they are never themselves scored. Records with `T >= 2020-02-01T00:00:00Z` are eligible to be scored, subject additionally to the per-horizon forward-availability rule in §14.

**This grid choice does not change what qualifies as an event based on morphology.** Exactly as the B2-02 repair established for its own qualifying-breach population, `(T,W)`-event existence here is defined only by §4-§5 (grid membership, `D_W(T)!=0`, source-bar availability) — never by whether the morphology descriptor, its percentile reference, the volatility/magnitude states, or the training history can be computed. A record whose morphology is unavailable remains a constructed event; it is simply `UNAVAILABLE_FOR_DECISION` for scoring (§13), never deleted from the population, and it never silently changes which records other events treat as valid percentile/training references.

## 5. Impulse/path windows

`W ∈ {15, 30, 60}` minutes.

```
D_W(T) = ln(close(T) / close(T-W))
```

Require `D_W(T) != 0`, finite inputs, and fully available source bars.

Direction: `d = sign(D_W(T))` → `UP` if `d=+1`, `DOWN` if `d=-1`.

Magnitude: `ABS_DISP_W(T) = abs(D_W(T))`.

Morphology interval `[T-W, T]` is represented by `N = W/5` complete 5-minute bars: `W=15 -> N=3`, `W=30 -> N=6`, `W=60 -> N=12`. Let `close_0, close_1, ..., close_N` be the 5m-bar closes at `T-W, T-W+5m, ..., T` respectively (`close_0 = close(T-W)`, `close_N = close(T)`). The 5m log returns are:

```
r_i = ln(close_i / close_{i-1}),   i = 1..N
```

By telescoping, `sum_i r_i = D_W(T)` exactly.

Every 5m source bucket entering `r_1..r_N`, and the anchor `close_0`, must carry an explicit availability timestamp and satisfy `available_at <= T`. No still-forming 5m bar may enter. Any morphology input with `available_at > T` makes the record fail closed (`UNAVAILABLE_FOR_DECISION`, jointly for candidate and baseline).

## 6. Canonical event identity

Deterministic event identity, frozen before outcomes:

```
snapshot_id | source_timeframe=1m | derived_timeframe=5m | decision_grid=1h | W | direction | T-W | T | H
```

at minimum: `snapshot_id`, `source_timeframe=1m`, `derived_timeframe=5m`, `decision_grid=1h`, `W`, `direction`, `window_start=T-W`, `window_end=T`, `T`, `H`. `H` is part of scored-record identity — a generic decision timestamp alone is not sufficient. Candidate and baseline retain exactly the same canonical ID on the same scored record.

### 6.1 Frozen canonical event-ID serialization

The exact, sole permitted serialization — no spaces around `|`, no quote characters anywhere in the string — is byte-for-byte:

```
CANONICAL_EVENT_ID = snapshot_id|1m|5m|1h|W_minutes|direction|window_start_ms|window_end_ms|T_ms|H_minutes
```

with these exact per-field rules:

- `snapshot_id`: the exact dataset snapshot identifier string, verbatim;
- the segments written above as `1m`, `5m`, `1h`: fixed ASCII literal segments, emitted unconditionally as exactly those three bare character sequences — not JSON-quoted, not wrapped in any quote mark, not otherwise decorated;
- `W_minutes`, `H_minutes`: plain base-10 integers with no leading zero and no unit suffix (`15`, not `15m` or `015`);
- `direction`: exactly `UP` or `DOWN` (uppercase ASCII; never `1`/`-1`, lowercase, or a synonym);
- `window_start_ms`, `window_end_ms`, `T_ms`: integer UTC epoch milliseconds (`window_end_ms == T_ms` always; `window_start_ms == T_ms - W_minutes*60000`);
- fields are joined, in exactly the order above, with a single literal `|` character between each pair, no surrounding whitespace on either side of any `|`, no other delimiter.

This mirrors the pipe-joined, epoch-millisecond, `str(int(...))`-normalized canonical ID convention already frozen and implemented for B2-02 (`_event_id` in `scripts/research/b2_02_boundary_interaction_path_lib.py`). No implementation-specific `repr()`, tuple, or dict-key ordering may be substituted for, or silently diverge from, this exact string — any future B2-03 implementation must reproduce it byte-for-byte from the fields above. Every canonical-ID-sort operation referenced elsewhere in this document (§9, §17) sorts, ultimately, on this exact string. This byte-level format is identical to `event_identity.canonical_serialization.format` in `docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.json`.

## 7. Simpler causal baseline

The candidate must beat: **signed displacement magnitude + current volatility state.** Baseline dimensions, frozen:

`W`, `DIRECTION`, `DISPLACEMENT_MAG_STATE`, `VOL_STATE`.

### 7.1 Direction

Exactly `UP` / `DOWN`, from `d`. Direction is **not** pooled in the forecast stratum: it is an explicit baseline (and candidate) dimension, present in both the simpler comparator and the morphology candidate equally. Direction-normalization (`d *`) is used only inside the target and morphology component formulas, so that `UP`/`DOWN` cannot silently smuggle simple directional asymmetry into an apparent morphology effect — any such asymmetry is already absorbed by both models identically, since both are conditioned on the same `DIRECTION` cell.

### 7.2 Displacement magnitude state

Raw quantity: `ABS_DISP_W(T)`. Causal percentile: same `W`, eligible hourly B2-03 decision records over the preceding 30 calendar days, strictly before current `T`, current record excluded. `UP`/`DOWN` are **pooled** for this percentile reference — magnitude is unsigned. Use canonical `rolling_midrank_percentile`. Map to tertiles: `LOW=[0,1/3)`, `MID=[1/3,2/3)`, `HIGH=[2/3,1]`.

### 7.3 Current volatility state

Freeze exactly 60 one-minute returns per decision time; no 59-return or 61-return interpretation:

- anchor: `close_0 = close(T-60m)`;
- history: `close_1, ..., close_60`, the closes of the 60 consecutive complete canonical 1-minute bars whose bar-end-exclusive timestamps lie in `(T-60m, T]` — equivalently, the source bars exactly cover `[T-60m, T)`, and the 60th bar's bar-end-exclusive timestamp equals `T` exactly;
- `r_i = ln(close_i / close_{i-1})`, `i = 1..60`.

```
PRE_VOL_60(T) = sqrt(sum_{i=1..60} r_i^2)
```

Every one of the 60 source 1m bars, and the anchor `close_0`, must have `available_at <= T`. Fewer or more than exactly 60 returns is not a valid computation and fails the record closed (`UNAVAILABLE_FOR_DECISION`, jointly for candidate and baseline). Causal percentile: preceding 30 calendar days, hourly B2-03 decision grid, strictly before `T`, current record excluded. Same midrank tertiles as §7.2. No alternate volatility metric, quantile count, threshold, or fallback.

Malformed, empty, or non-finite causal reference for either §7.2 or §7.3 makes the record `UNAVAILABLE_FOR_DECISION` for both candidate and baseline. No side-specific, neighboring-`W`, or full-history fallback.

## 8. Frozen morphology descriptor

Exactly one descriptor, from exactly four 5m-path components computed on the same `[T-W,T]` interval as §5. No candlestick indicators, no RSI/MACD, no open-ended feature search.

Let `TV = sum_i abs(r_i)`. Require `TV > 0`; otherwise the record is jointly unavailable.

**Component 1 — DISTRIBUTEDNESS**

```
MAX_RETURN_SHARE  = max_i abs(r_i) / TV
DISTRIBUTEDNESS   = 1 - MAX_RETURN_SHARE
```

Higher means the displacement was less concentrated in one short shock.

**Component 2 — PATH_EFFICIENCY**

```
PATH_EFFICIENCY = abs(D_W(T)) / TV
```

Higher means less back-and-forth movement was required to produce the final displacement. Because `abs(D_W(T)) = abs(sum_i r_i) <= sum_i abs(r_i) = TV` always, this ratio is bounded in `[0,1]` by construction, not by a post-hoc clip.

**Component 3 — DIRECTIONAL_BAR_SHARE**

```
DIRECTIONAL_BAR_SHARE = count_i(d * r_i > 0) / N
```

A zero 5m return does not count as direction-supporting. Higher means pressure was distributed across more sub-bars in the eventual displacement direction.

**Component 4 — COUNTERMOVE_SHALLOWNESS**

Direction-normalized cumulative path: `z_0 = 0`, `z_j = d * sum_{i=1..j} r_i` for `j=1..N`. Running peak: `peak_j = max(z_0..z_j)`. Maximum counter-move drawdown:

```
MAX_COUNTERMOVE     = max_j(peak_j - z_j)
COUNTERMOVE_RATIO   = MAX_COUNTERMOVE / TV
COUNTERMOVE_SHALLOWNESS = 1 - COUNTERMOVE_RATIO
```

Require finite `0 <= COUNTERMOVE_RATIO <= 1` (a construction invariant — `peak_j - z_j` can never exceed the total absolute variation accrued since the running peak — enforced as a fail-closed integrity check, not merely assumed). Higher `COUNTERMOVE_SHALLOWNESS` means shallower adverse retracement while the displacement was forming.

No alternate counter-move formula, and no fifth component, after outcomes.

**On magnitude equivalence (self-red-team item 13):** none of the four components is a re-binning of `ABS_DISP_W(T)`. `TV` (total absolute sub-return variation) and `abs(D_W(T))` (net displacement) are different quantities related only by the inequality above; `PATH_EFFICIENCY` is precisely the ratio that separates a single-bar shock path (`MAX_RETURN_SHARE` near 1, `TV` close to `abs(D_W(T))`, giving `PATH_EFFICIENCY` near 1) from a choppy path producing the same net displacement (`TV` much larger than `abs(D_W(T))`, giving `PATH_EFFICIENCY` near 0). The remaining three components (`DISTRIBUTEDNESS`, `DIRECTIONAL_BAR_SHARE`, `COUNTERMOVE_SHALLOWNESS`) are computed entirely from the internal shape of `r_1..r_N` and, for `DISTRIBUTEDNESS`/`COUNTERMOVE_SHALLOWNESS`, from `TV`-normalized internal structure — none is a monotone transform of `abs(D_W(T))` alone. Conditioning both candidate and baseline on the same `DISPLACEMENT_MAG_STATE` tertile additionally removes any residual scale channel before morphology is even evaluated.

## 9. Causal morphology normalization

For each of the four components separately: causal midrank percentile using the same `W`, preceding 30 calendar days, hourly B2-03 records, reference `T` strictly before current `T`, current event excluded. Components are already direction-normalized, so `UP`/`DOWN` are pooled for these percentile references. Every historical reference feature must have been fully available by its own event `T`. Canonical `rolling_midrank_percentile`. No full-development percentile, no yearly percentile, no future fill, no neighboring-`W` fallback.

If any required component/reference is unavailable, malformed, empty, or non-finite: `UNAVAILABLE_FOR_DECISION` for both candidate and baseline.

## 10. Morphology score and state

```
MORPHOLOGY_SCORE = mean(
  PCTL_DISTRIBUTEDNESS,
  PCTL_PATH_EFFICIENCY,
  PCTL_DIRECTIONAL_BAR_SHARE,
  PCTL_COUNTERMOVE_SHALLOWNESS
)
```

Equal weights only. State: `LOW=[0,1/3)`, `MID=[1/3,2/3)`, `HIGH=[2/3,1]`. No second score, no alternative weights, no component deletion/substitution, no "best 2 of 4", no PCA/clustering — before or after outcomes.

## 11. Expected morphology ordering

Frozen directional mechanism: **more distributed, more efficient, directionally persistent, shallow-countermove morphology should correspond to stronger continuation after `T`.** Expected ordering: `HIGH morphology > LOW morphology` on the direction-normalized continuation residual.

Exhaustion is **not** preregistered as an equal alternative here — H03 already tested continuation vs exhaustion of extreme magnitude and found sign instability. B2-03's frozen inventory claim is F1 directional persistence via distributed-pressure morphology specifically. A negative observed sign does not become a B2-03 exhaustion candidate after outcomes; it is a failed formulation, recordable only as `POSTHOC_UNTESTED` future-program material.

## 12. Future target

Horizons `H ∈ {15m, 30m, 60m, 120m, 240m}`.

```
DIR_RET_H(T) = d * ln(close(T+H) / close(T))
```

`PAST_MEDIAN_ABS_RET_H(T)` is the median absolute `H`-horizon close return sampled at prior canonical UTC 15-minute grid decision points in the preceding 30 calendar days, using only reference points whose own `H`-horizon outcome is fully known by current `T` (`ref_t + H <= T`). This reuses H03/B2-02's convention of a fixed, denser close-return grid dedicated to a robust local-scale estimate, decoupled from B2-03's own coarser hourly event grid — not chosen from any B2-03 outcome, since none exists.

```
Y_H(T) = DIR_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)
```

Denominator must be finite, positive, and known by `T`. No winsorization, no future-informed floor, no sign flip, no alternate target after outcomes.

## 13. Causal walk-forward prediction

Training history: preceding 90 calendar days. For a forecast at `T`, horizon `H`: every training record must satisfy `training_T + H <= current_T`. No training outcome still unresolved at current `T`.

```
BASE_PRED(T,H) = median historical Y_H  for same  W, DIRECTION, DISPLACEMENT_MAG_STATE, VOL_STATE
CAND_PRED(T,H) = median historical Y_H  for the same baseline context plus MORPHOLOGY_STATE
```

Minimum historical support: baseline cell `>= 80`; candidate joint cell `>= 40`. Frozen before outcomes.

No neighboring-bin fallback, no side pooling when the exact direction cell is sparse, no neighboring-`W` fallback, no shrinkage, no smoothing, no full-history fallback, no candidate-only support rule.

One joint eligibility predicate: if either candidate or baseline cannot produce a valid prediction, the scored record is unavailable for **both**.

## 14. Development evaluation boundary and per-horizon eligibility

A `(T,W)` event constructed under §4 is scored for horizon `H` only if `current_T + H < 2025-01-01T00:00:00Z` (strict, no truncation). This is a per-`(T,H)` scoring-eligibility check, independent of §4 event construction, mirroring the same qualification/decision-availability separation used throughout this document.

On the hourly grid, the last legal `T` per horizon is:

| H | boundary check | last legal T | T+H |
|---|---|---|---|
| 15m | `T < 23:45` | 2024-12-31T23:00:00Z | 23:15:00Z |
| 30m | `T < 23:30` | 2024-12-31T23:00:00Z | 23:30:00Z |
| 60m | `T < 23:00` | 2024-12-31T22:00:00Z | 23:00:00Z |
| 120m | `T < 22:00` | 2024-12-31T21:00:00Z | 23:00:00Z |
| 240m | `T < 20:00` | 2024-12-31T19:00:00Z | 23:00:00Z |

(`T = 2024-12-31T23:00:00Z` is itself the last hourly grid point strictly inside the development window; it exists as an event and remains eligible for `H=15m/30m`, but is ineligible for `H=60/120/240m`.)

## 15. Primary incremental metric

```
BASE_AE = abs(Y_H - BASE_PRED)
CAND_AE = abs(Y_H - CAND_PRED)
AE_IMPROVEMENT = BASE_AE - CAND_AE
```

Positive favors morphology. Per primary cell, on the pooled scored support: `N`; mean/median AE improvement; relative MAE improvement `1 - mean(CAND_AE)/mean(BASE_AE)`; bootstrap 95% interval; `MORPHOLOGY_SEPARATION_POOLED` (§16); placebo q95. Additionally, on the `UP`-only and `DOWN`-only partitions of that same scored support: `N`; mean AE improvement; `MORPHOLOGY_SEPARATION_UP` / `MORPHOLOGY_SEPARATION_DOWN` (§16, §20.1, §21).

## 16. Structural morphology diagnostic

```
BASE_RESIDUAL = Y_H - BASE_PRED
MORPHOLOGY_SEPARATION(subset) = median(BASE_RESIDUAL | MORPHOLOGY_STATE=HIGH, subset) - median(BASE_RESIDUAL | MORPHOLOGY_STATE=LOW, subset)
```

computed on the exact same scored support used by the candidate/baseline comparison for that cell (§13), restricted to `subset`. Three variants are computed and reported for every primary cell, all on that identical scored support:

- `MORPHOLOGY_SEPARATION_POOLED` — `subset` = all scored records in the cell (`UP`+`DOWN`);
- `MORPHOLOGY_SEPARATION_UP` — `subset` = scored records with `DIRECTION=UP`;
- `MORPHOLOGY_SEPARATION_DOWN` — `subset` = scored records with `DIRECTION=DOWN`.

Frozen expected sign for all three: `MORPHOLOGY_SEPARATION > 0` (§11). `MID` is reported but is never used to invent a post-outcome U-shape or threshold. The `morphology_ordering` gate requires all three to be finite and strictly positive (§20, §20.1).

## 17. Negative control / placebo

Causal permutation of historical `MORPHOLOGY_STATE` labels only. Seed `20260904`, 100 replicates.

For each current forecast event, work only inside its eligible causal 90-day training set with `training_T + H <= current_T`. Stratify by the exact baseline stratum `W × DIRECTION × DISPLACEMENT_MAG_STATE × VOL_STATE`. Within each stratum:

- sort by canonical event ID (§6.1) before RNG;
- permute historical morphology-state labels only;
- leave historical `Y` fixed;
- leave the current evaluation event's own morphology state fixed;
- never use a future record to preserve eventual calendar composition.

### 17.1 Frozen baseline-stratum-ID serialization

No spaces around `|`, no quote characters — byte-for-byte:

```
BASELINE_STRATUM_ID = W_minutes|direction|DISPLACEMENT_MAG_STATE|VOL_STATE
```

with the same per-field rules as §6.1 (`W_minutes` a plain base-10 integer with no leading zero; `direction` exactly `UP`/`DOWN`, uppercase ASCII), plus `DISPLACEMENT_MAG_STATE`, `VOL_STATE` each exactly one of `LOW`, `MID`, `HIGH` (uppercase ASCII), joined in exactly that order by a single literal `|` character with no surrounding whitespace. This byte-level format is identical to `controls.baseline_stratum_id_serialization.format` in `docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.json`.

### 17.2 Frozen per-replicate seed derivation

`current_T` is frozen to `T_ms`, the same integer UTC epoch-millisecond representation used in §6.1. The per-replicate seed is the deterministic hash of the ordered part sequence

```
[20260904, replicate_index, W_minutes, H_minutes, T_ms, BASELINE_STRATUM_ID]
```

joined and hashed by the same deterministic string→integer seed primitive already frozen and implemented for B2-02 (`_seed_int` in `scripts/research/b2_02_boundary_interaction_path_lib.py`: pipe-join `str(part)` for each ordered part, UTF-8 encode, SHA-256, take the first 16 hex digits as an integer). No alternate hash, truncation, or seed-mixing scheme may be substituted. `BASELINE_STRATUM_ID` already contains internal `|` characters (§17.1); this is not ambiguous because `_seed_int` never reverse-parses the joined string, only reproduces it deterministically from the same ordered parts.

Placebo candidate prediction is reconstructed from the permuted historical morphology labels; the historical stratum must be sorted by canonical event ID (not left in chronological order) before permutation, matching the frozen B2-02 mapping repair. Primary true mean AE improvement must exceed placebo q95, the 95th percentile of the 100 replicate values (§20).

## 18. Dependence / bootstrap

UTC-week block bootstrap. Seed `20260905`, 2000 replicates, 95% interval for mean AE improvement. No rerolling seed. No selecting a block size after seeing B2-03 results.

## 19. Frozen primary surface

Exactly `3 W × 5 H = 15` primary cells (`W = 15,30,60m`; `H = 15,30,60,120,240m`). No `q` threshold, no extreme-tail grid, no second morphology window, no alternate component family, no alternate weighting, no exhaustion orientation, no one-sided rescue. This absence of a `q`-search surface is intentional.

## 20. Mandatory promotion gates

Required gate names — exactly eight, unchanged: `primary_positive`, `material_relative_mae`, `bootstrap_positive`, `placebo_separation`, `morphology_ordering`, `horizon_robustness`, `parameter_robustness`, `year_stability`.

Per-cell (all five required):

- `primary_positive`: **pooled** mean AE improvement `> 0` **and** **`UP`** mean AE improvement `> 0` **and** **`DOWN`** mean AE improvement `> 0`; all three finite (§20.1).
- `material_relative_mae`: pooled relative MAE improvement `>= 0.02`, where relative MAE improvement `= 1 - mean(CAND_AE)/mean(BASE_AE)` on the pooled scored support (§15).
- `bootstrap_positive`: pooled 95% UTC-week block-bootstrap lower bound for mean AE improvement `> 0` (§18).
- `placebo_separation`: pooled true mean AE improvement `>` placebo q95, where placebo q95 is the 95th percentile of the frozen 100 causal permutation replicates (§17) on the pooled scored support.
- `morphology_ordering`: **pooled** `MORPHOLOGY_SEPARATION > 0` **and** **`UP`** `MORPHOLOGY_SEPARATION > 0` **and** **`DOWN`** `MORPHOLOGY_SEPARATION > 0` (§16); all three finite, all three computed on the exact same scored support as the candidate/baseline comparison for that cell (§20.1).

### 20.1 Anti-rescue side-symmetry subconditions

Pooling `UP`+`DOWN` into one `(W,H)` cell does **not**, by itself, prevent a one-sided effect from promoting: a sufficiently strong positive effect on one direction can dominate a null or negative effect on the other while the pooled metric still reads positive. B2-03 is not preregistered as a direction-specific interaction formulation, so an `UP`-only or `DOWN`-only effect must not promote.

`primary_positive` and `morphology_ordering` are therefore strengthened with mandatory `UP`-only and `DOWN`-only subconditions, computed on the exact `UP`/`DOWN` partition of the same scored cell support used for the pooled statistic. Both subconditions must hold, in addition to the pooled statistic, for either gate to pass. This does **not**:

- add a ninth gate name;
- create a direction-specific promotion path or a direction-specific child formulation;
- introduce an `UP`-only candidate or a `DOWN`-only candidate;
- permit a post-outcome direction switch;
- drop, add, or resplit `DIRECTION` out of the candidate/baseline strata (§7.1) to manufacture a passing side.

The pooled `(W,H)` cell remains the sole primary statistical unit that is promoted or closed; `UP`/`DOWN` values are mandatory subconditions of two existing gates, not an alternative promotion route.

`material_relative_mae`, `bootstrap_positive`, and `placebo_separation` remain pooled-only. They are magnitude/uncertainty/negative-control gates on the primary statistical unit, not directional-consistency gates: a one-sided effect that already fails a pooled uncertainty or negative-control gate is already blocked by that gate, so the rescue path closed here is specific to a gate that checks only a single pooled point estimate's sign — exactly `primary_positive` and `morphology_ordering`.

**Horizon robustness:** for one `W`, at least two adjacent horizons in `[15,30,60,120,240]` (adjacent pairs exactly `15/30`, `30/60`, `60/120`, `120/240`) pass all five per-cell gates (including the §20.1 subconditions).

**Parameter robustness:** the exact same adjacent-`H` pair also passes all five per-cell gates for at least one **other** `W`. No single `W` may promote alone.

**Year stability:** for every cell in the proposed promotion neighborhood, pooled mean AE improvement `> 0` in at least 4 of 5 development years `2020,2021,2022,2023,2024`. No year exclusions, no shock-year deletion.

Missing/non-finite mandatory values — pooled or side-specific — are non-passes. A formulation whose pooled cells fail cannot be rescued by a single direction, and (per §20.1) a pooled cell whose apparent positive effect is concentrated in only one direction cannot promote either.

## 21. Reporting contract

For every one of the 15 primary cells, report at minimum, on the pooled scored support: support `N`; unique UTC days/weeks/months; `UP` count; `DOWN` count; yearly 2020..2024 mean AE improvement; baseline-state counts; morphology-state counts; largest-month and top-5-month support share; mean/median AE improvement; relative MAE improvement; bootstrap lower/upper 95%; `MORPHOLOGY_SEPARATION_POOLED`; placebo q95.

Additionally, for every one of the 15 primary cells, report on the `UP`-only and `DOWN`-only partitions of that same scored support: `UP N`; `DOWN N`; `UP` mean AE improvement; `DOWN` mean AE improvement; `MORPHOLOGY_SEPARATION_UP`; `MORPHOLOGY_SEPARATION_DOWN` (§16, §20.1).

Also report morphology component distributions descriptively. A descriptive component metric never becomes a rescue gate beyond the mandatory §20.1 subconditions.

## 22. Verdict

Exactly one market verdict after a future, separately authorized development run:

### `B2_03_PROMOTED_CANDIDATE`

Only if the complete frozen promotion contract passes.

### `B2_03_CLOSED_NO_PROMOTION`

If the frozen formulation does not satisfy the promotion contract.

An integrity/data/retention failure is **not** a market verdict; it aborts/fails closed. Promotion does not authorize 2025 validation, 2026 OOS, live use, or trading use. No second current-V2 extreme-move-morphology child is allowed after failure.

## 23. Durable-retention integration — preregister now, implement later

Future B2-03 execution **shall** use the merged B2-03+ ceremony from PR #99 (`docs/research/BATCH02_DURABLE_EVIDENCE_RETENTION_V1.md`), not the historical B2-01/B2-02 path:

```
verify_batch02_code
prepare_batch02_evidence_reservation
prepare_batch02_retained_run     # remote RESERVED -> OUTCOME_ACCESS_CLAIMED, before dataset authorization
load_authorized_parquet_table
compute exactly once
persist_batch02_retained_result
archive_batch02_result           # exact bytes + independent remote readback
```

Durable one-shot slot: `B2-03`. Production evidence namespace: `refs/heads/research-evidence/batch02/B2-03/<execution_code_sha>`.

This preregistration does **not** create that reservation. It occurs only in the future implementation/execution unit, at the exact reviewed/merged execution SHA, after this preregistration and the B2-03 implementation independently pass CI, CodeRabbit, and independent adversarial review.

## 24. No-lookahead requirements

- Every morphology input: `available_at <= T`.
- Every causal state reference (magnitude, volatility, morphology-component percentiles): `reference_T < current_T`.
- Every training outcome: `training_T + H <= current_T`.
- Every development evaluation outcome: `current_T + H < 2025-01-01T00:00:00Z`.
- Every local normalization outcome used at current `T` must already be fully resolved by `T`.
- No later revision/backfill with availability after `T` may be used as if contemporaneously known.
- Malformed timestamps fail closed.

## 25. Adaptivity disclosure

- H03 outcomes (`H03_REJECTED_SPECIFIC_CLAIM`) are already known.
- B2-03 was admitted to the frozen V2 inventory (`ADMIT_TO_V2_INVENTORY`, §7 of `V2_FORMULATION_INVENTORY.md`) before Batch02 outcome inspection — before B2-01 or B2-02 development access, and therefore before this document was written.
- B2-03 does not reinterpret H03 as positive evidence; H03 remains `H03_REJECTED_SPECIFIC_CLAIM`, untouched.
- H03's `q90/q95/q98` tail-severity surface is not reused as a B2-03 signal surface in any form, including as an admission threshold.
- `W ∈ {15,30,60}` is inherited as the fixed path-scale family already used across H01/H02/H03/B2-01, not chosen from a favorable H03 cell.
- The hourly event grid is chosen to avoid magnitude-trigger selection and dense overlapping detections, and to give the 90-day causal training minima enough support at deterministic, non-overlapping decision times — not because an hourly H03-style result looked attractive; H03 never used an hourly grid.
- The four morphology components (`DISTRIBUTEDNESS`, `PATH_EFFICIENCY`, `DIRECTIONAL_BAR_SHARE`, `COUNTERMOVE_SHALLOWNESS`) were frozen as a single economic representation of concentrated shock vs. distributed directional pressure, matching the "return concentration / path efficiency / counter-move depth" examples already named in `V2_FORMULATION_INVENTORY.md` §7.
- The `D_W(T) != 0` exclusion is a structural degenerate-input exclusion (undefined direction), the same kind of rule as H03's "exact zero: excluded", not a magnitude gate.
- No real B2-03 outcome was consulted to choose any of the above; none exists.

## 26. Self-red-team (answered before push, outcome-blind)

1. **Reintroduced H03 extremeness through another threshold?** No. There is no admission threshold on `ABS_DISP_W(T)`; every nonzero displacement is eligible. `DISPLACEMENT_MAG_STATE` is a percentile baseline control shared identically by candidate and baseline, not a trigger.
2. **Can morphology change event eligibility?** No. §4 defines `(T,W)` event existence from grid membership, `D_W(T)!=0`, and source-bar availability only. Morphology unavailability makes a record `UNAVAILABLE_FOR_DECISION`, never deletes it from the population or lets it silently drop out of another event's causal reference/training pool.
3. **Can candidate and baseline ever score different event IDs?** No. §13 uses one joint eligibility predicate; a record is scored for both or neither, under the identical canonical ID of §6.
4. **Can a component use a bar available after T?** No. §5/§24 require `available_at <= T` for every 5m return input and the anchor close; violation fails the record closed.
5. **Can training use an H outcome unresolved at current T?** No. §13 requires `training_T + H <= current_T` for every training record.
6. **Can 2025 enter through a late-December H target?** No. §14's per-`(T,H)` table enforces `current_T + H < 2025-01-01T00:00:00Z` exactly, with the boundary worked out per horizon (e.g. `T=23:00` is legal for `H=15/30m` but not `H=60/120/240m`).
7. **Can percentile references use future events?** No. §7.2/§7.3/§9 all require `reference_T` strictly before current `T`, current event excluded, no future fill.
8. **Can morphology weights/components be changed after outcome?** No. §10 freezes exactly four equal-weighted components; no substitution, deletion, or reweighting is defined anywhere in this document.
9. **Can LOW/HIGH sign be reversed after outcome?** No. §11 freezes the expected ordering `HIGH > LOW`; a negative sign is a failed formulation (`POSTHOC_UNTESTED`), not a preregistered exhaustion alternative.
10. **Can one W or one H isolated optimum promote?** No. §20's horizon-robustness and parameter-robustness gates require the same adjacent-`H` pair to pass on at least two distinct `W` values; no single `W`/`H` promotes alone.
11. **Can UP-only or DOWN-only behavior rescue the formulation?** No — but pooling `UP`+`DOWN` into one `(W,H)` cell does not, by itself, block this: a strong positive effect on one direction can dominate a null or negative effect on the other while the pooled statistic still reads positive. B2-03 closes this by strengthening two gates, not merely by pooling: `primary_positive` requires pooled **and** `UP` **and** `DOWN` mean AE improvement each `> 0` and finite, and `morphology_ordering` requires pooled **and** `UP` **and** `DOWN` `MORPHOLOGY_SEPARATION` each `> 0` and finite, all on the identical scored support (§20, §20.1). No ninth gate, direction-specific promotion child, `UP`-only candidate, `DOWN`-only candidate, or post-outcome direction switch is introduced; the pooled `(W,H)` cell remains the sole primary statistical unit, matching the program's existing rejection of BUY/SELL-only rescue.
12. **Can a result be persisted without PR #99 durable retention later?** No. §23 requires the merged B2-03+ retained-run ceremony; the merged `batch02_contracts` module already rejects numbered B2-03+ hypothesis IDs from the historical `prepare_batch02_run`/`persist_batch02_result` path at the code level.
13. **Is any feature mathematically equivalent to re-binning displacement magnitude?** No — addressed explicitly in §8's closing note; `TV` and `abs(D_W(T))` are distinct quantities, and conditioning on `DISPLACEMENT_MAG_STATE` further removes residual scale before morphology percentiles are computed.
14. **Does the design contain an unbounded feature/search menu?** No. Exactly four frozen components, one score, `3W×5H=15` cells, no `q` grid, no second window.
15. **Ambiguous boundary inclusivity left to implementation discretion?** Resolved explicitly in this document: `close(T)` definition (§3), exact 5m-return indexing `r_1..r_N` with anchor `close_0` (§5), per-horizon last-legal-`T` table (§14), and the warmup-vs-development event/scoring split (§4).

No blocker was found requiring repair before push. No real market outcome was read to answer any of the above.

## 27. Implementation gate

Planned paths (not created by this unit):

- runner: `scripts/research/b2_03_impulse_morphology.py`
- library: `scripts/research/b2_03_impulse_morphology_lib.py`
- tests: `tests/research/test_b2_03_impulse_morphology.py`

Before development outcomes:

- use the canonical Batch02 contracts merged by PR #99, via the B2-03+ retained-run ceremony (§23), not historical `prepare_batch02_run`/`persist_batch02_result`;
- exact clean Git identity;
- authorized development-only dataset;
- exact same-support event IDs;
- explicit no-lookahead checks for morphology/context/training availability;
- immutable canonical persistence/provenance with durable remote archival;
- hypothesis-specific regression tests;
- exact-SHA CI + CodeRabbit + one independent completion review.

`outcome_access_authorized = false` until that sequence is complete.
