# V2 Correctness & Acceptance Contract

This document freezes **how V2 decisions are computed deterministically and
how V2 earns promotion.** It is the second and final Stage 1 documentation
PR. No V2 code exists after this PR — this remains documentation only.

It **complements, not replaces**, `docs/V2_PRODUCT_CONTRACT.md`. The
documentation hierarchy is:

1. **`docs/FORECASTING_ROADMAP.md`** — product direction.
2. **`docs/V2_PRODUCT_CONTRACT.md`** — what V2 means as a product (mission,
   setup families, episode states, hard gates).
3. **This document** — exact deterministic behavior: formulas, thresholds,
   timestamp/no-lookahead mechanics, episode identity, promotion criteria.
4. **Implementation** — every future V2 implementation PR must conform to
   all three documents above. A future PR that contradicts this document
   is either wrong, or must first amend this document explicitly.

Where an exact rule here would contradict the merged Product Contract, this
document does **not** silently override it — any such case found during
drafting is called out explicitly and resolved conservatively (see
[§0.3](#03-product-contract-reconciliation)).

Normative language follows `V2_PRODUCT_CONTRACT.md` §0's usage: **MUST** /
**MUST NOT** (hard requirement), **SHOULD** / **SHOULD NOT** (strong
expectation, deviation must be deliberate), **MAY** (optional).

---

## 0.1 What this document is not

- **Not a schema.** No SQL, no migrations, no table creation, no Python
  dataclasses, no config YAML, no runtime code. Every "table" shown below is
  a Markdown illustration of a **logical record shape**, for clarity only —
  it does not exist in code and must not be treated as already implemented.
  Physical storage is the job of the upcoming Multi-model Framework
  implementation PRs (`docs/FORECASTING_ROADMAP.md` §I, stage 2).
- **Not a claim of predictive validity.** Every numeric parameter introduced
  below is labeled **V2-v0** — an explicit initial versioned hypothesis, not
  an empirically calibrated truth. None of them are backed by a completed
  V2 backtest (none exists yet — V2 is not implemented). Where this
  document states a number, it is because leaving it undefined would leave
  behavior-affecting logic for implementers to guess, which
  `docs/V2_PRODUCT_CONTRACT.md` §12 explicitly forbids. Future tuning of any
  V2-v0 parameter requires a new `rules_version` ([§3](#3-v2-modelversion-identity))
  — it can never silently rewrite the meaning of historical V2 decisions.
- **Not a V1 change.** Nothing here modifies `analytics/forecasting/`,
  `runtime/telegram_cli.py`, `notifications/`, or any other V1 runtime path.
  V1's `rule_version`, `calculation_version`, and Telegram behavior are
  untouched.

## 0.2 Grounding

Every field name, formula, and default value used below is taken directly
from the current repository — principally `docs/STAGE2_SPEC.md` §§10–13
(the frozen Consensus / Percentile / Data Quality contracts),
`analytics/feature_engine/models.py` and `consensus_models.py` (the actual
`ExchangeFeatureVector` / `ConsensusFeatureVector` field sets), and
`analytics/forecasting/{models,core,persistence,shadow_cycle,outcomes}.py`
(the actual V1 rule-set / decision / prediction / outcome shapes, which V2
reuses infrastructure from without becoming V1). No field is invented; where
a genuinely new derived value is needed (e.g. a rolling range-width proxy),
this document says so explicitly and defines it as a deterministic function
of already-ingested data, never as a new ingested source.

## 0.3 Product Contract reconciliation

One point needed a small, non-semantic clarification rather than a
contradiction: `V2_PRODUCT_CONTRACT.md` §5.2 describes `REVERSAL_CANDIDATE`
as "a cross-cutting observation" without pinning down its exact mechanics.
[§13.3](#133-reversal_candidate-mechanics) below resolves this precisely,
consistent with — not overriding — that section. A one-sentence pointer is
added to `V2_PRODUCT_CONTRACT.md` §5.2 (see the diff in this PR); no
semantic change to the Product Contract was required anywhere else.

---

## 1. The V2 decision clock

### 1.1 Logical decision time vs. wall clock

V2 operates from **closed 5m decision boundaries**, exactly as V1's shadow
cycle does today (`runtime/shadow_cli.py`). Two layers, kept strictly
separate:

- **Layer 1 — wall clock → decision boundary `T` (impure).** Maps
  "processing happened at real time `now`" to "the logical decision
  boundary this processing run is allowed to act on." This is the only
  place wall-clock time enters V2's decision logic.
- **Layer 2 — decision boundary `T` → selected buckets (pure).** Given
  `T`, deterministically selects the one legal closed bucket per timeframe.
  Never reads a clock. Same `T` always yields the same buckets, on any
  machine, at any wall-clock time.

**Invariant:** the runtime delay between a boundary closing and a process
actually handling it **MUST NOT** change which buckets that decision is
computed from. Processing at `T + 35s` and replaying the same logical
decision an hour, a day, or a year later **MUST** select the identical
input buckets, because both re-derive them from the same stored `T`
(Layer 2 is pure), never from "what's the latest bucket right now."

### 1.2 Layer 1 — `decision_boundary(now, soft_grace_s)`

Reused unchanged from the already-frozen and already-implemented
`runtime/shadow_cli.py::select_latest_closed_5m_bucket`, generalized only in
name (behavior is identical for the 5m case):

```text
decision_boundary(now, soft_grace_s):
    effective = now - soft_grace_s
    T = floor_to_grid(effective, 5m)     # latest 5m-grid instant <= effective
    return T                              # T is UTC, whole-minute, 5m-aligned
```

`soft_grace_s` is reused from the existing, frozen `stage2.bucket_close.soft_grace_s`
config value (currently `5`, `config/stage2.yaml`) — not a new V2 parameter.
Its purpose here is unchanged from its existing purpose in
`select_latest_closed_5m_bucket`: absorb the few seconds of cross-exchange
bar-close skew so a decision isn't run against a bucket whose data hasn't
actually landed yet. `T` represents **the close instant of the most
recently closed 5m bucket eligible for a decision** — i.e. the 5m bucket
`[T − 5m, T)` is the freshest legal 5m input.

V2 does **not** invent a second, contradictory clock. `stage2.bucket_close.hard_deadline_s`
(currently `15`) is a **write-path** concept (whether
`consensus_feature_vectors` is computed at full or partial coverage,
`STAGE2_SPEC.md` §5.2) and is orthogonal to Layer 1 — it does not change
which bucket Layer 1 selects.

### 1.3 Layer 2 — `selected_bucket(timeframe, T)` (pure)

```text
TF_MINUTES = {5m: 5, 15m: 15, 1h: 60, 4h: 240}

selected_bucket(timeframe, T):
    m = TF_MINUTES[timeframe]
    boundary = floor_to_grid(T, m)   # latest multiple of m minutes since
                                      # UTC epoch (1970-01-01T00:00:00Z) <= T
    return boundary - m               # the bucket's START (bucket_ts)
```

`floor_to_grid` is computed from minutes since the UTC epoch, not
minute-of-hour — this is what makes 4h boundaries land on `00:00, 04:00,
08:00, 12:00, 16:00, 20:00` UTC (the epoch is itself midnight UTC, and 240
divides a day evenly) without any special-casing. For `timeframe=5m` this
reduces exactly to `T − 5m`, matching `select_latest_closed_5m_bucket`'s
existing `bucket_ts = closed_boundary − 5m` line — Layer 2 is a strict
generalization of code that already exists and already ships, not a new
algorithm.

**Partially formed buckets are forbidden by construction.** `selected_bucket`
only ever returns a bucket whose closing instant (`boundary`) is `<= T`, and
`T` itself is only ever wall-clock-derived through the soft-grace layer
above. A bucket that has not fully closed can never be selected. This
composes with the already-frozen rule (`STAGE2_SPEC.md` §5.1) that a
higher-timeframe `consensus_feature_vectors` row is written **only** when
every constituent lower-timeframe bucket is present or explicitly
gap-accounted — V2 reuses that existing completeness guarantee rather than
re-deriving it.

### 1.4 Worked alignment vectors

All examples use `T` values that are themselves already 5m-aligned (as
Layer 1 always produces), so the grace-boundary example below is the only
one that also shows Layer 1.

| `T` (UTC) | `selected_bucket(5m, T)` | `selected_bucket(15m, T)` | `selected_bucket(1h, T)` | `selected_bucket(4h, T)` |
|---|---|---|---|---|
| `12:10:00` | `[12:05, 12:10)` | `[11:45, 12:00)` | `[11:00, 12:00)` | `[08:00, 12:00)` |
| `12:15:00` | `[12:10, 12:15)` | `[12:00, 12:15)` | `[11:00, 12:00)` | `[08:00, 12:00)` |
| `13:00:00` | `[12:55, 13:00)` | `[12:45, 13:00)` | `[12:00, 13:00)` | `[08:00, 12:00)` |
| `16:00:00` | `[15:55, 16:00)` | `[15:45, 16:00)` | `[15:00, 16:00)` | `[12:00, 16:00)` |

Reading `T=12:15:00`: the 15m bucket rolls to `[12:00,12:15)` (a new 15m
boundary just closed), but the 1h and 4h buckets are unchanged from
`T=12:10:00` — their own buckets haven't closed yet. Reading `T=16:00:00`:
this is the first `T` in the table where the 4h bucket rolls forward, since
`16:00` is itself a 4h grid boundary.

**Grace-boundary vector (Layer 1 + Layer 2 together).** `soft_grace_s = 5`
(current config). Two processing runs straddling a 5m close at `12:10:00`:

| Wall-clock `now` | `effective = now − 5s` | `T = decision_boundary(now, 5)` | `selected_bucket(5m, T)` |
|---|---|---|---|
| `12:10:04.999` | `12:09:59.999` | `12:05:00` | `[12:00, 12:05)` |
| `12:10:05.000` | `12:10:00.000` | `12:10:00` | `[12:05, 12:10)` |

At `12:10:04.999` — four-plus seconds after the `[12:05,12:10)` bucket
structurally closed on the wall clock — a V2 decision run still only sees
`[12:00,12:05)` as its latest legal 5m input; only once `now` reaches
`12:10:05.000` does the newly closed bucket become selectable. This is
identical behavior to the already-shipped `select_latest_closed_5m_bucket`,
reused rather than re-invented.

### 1.5 No-lookahead vector

Decision boundary `T = 12:10:00` selects 5m bucket `[12:05,12:10)`
(`bucket_ts = 12:05:00`, `bucket_end = 12:10:00`). A funding-rate poll
observation with `ts = 12:10:00` (i.e. exactly the bucket's close instant)
arrives. Per the already-frozen half-open membership rule enforced today in
`analytics/feature_engine/exchange_features.py` (`bucket_ts <= ts <
bucket_end`), `ts = 12:10:00` is **not** a member of `[12:05,12:10)` — it
belongs to the *next* bucket, `[12:10,12:15)`. Supplying it as an input to
the `12:05` bucket is not silently dropped; the existing feature-engine
validation raises rather than accepting a leaking observation
(`exchange_features.py` line ~299 and siblings). V2 makes no exception to
this: **an observation whose timestamp is at or after a bucket's close
instant MUST NOT affect that bucket's computed values, and the existing
code already fails loudly rather than silently if this is violated.**

---

## 2. No-lookahead semantics per input family

**General rule.** For a decision with logical cutoff `T`, no observation
whose *knowledge timestamp* is later than the cutoff implied by
`selected_bucket` may affect that decision. Knowledge timestamp is
distinguished from event timestamp per family below — for a bar-derived
family the two coincide with the bucket's own close instant; for a
poll-derived family the observation's own `ts` **is** its knowledge
timestamp (a poll's value is not knowable before the poll happened).

| Family | Source | Knowledge timestamp | No-lookahead mechanism |
|---|---|---|---|
| klines / price / volume | `klines_1m` via `KlineBar.ts` | bucket close (`bucket_ts + timeframe`) | Half-open `[bucket_ts, bucket_end)` membership, enforced in `exchange_features.py` (reused unchanged, [§1.5](#15-no-lookahead-vector)). |
| taker flow | same `klines_1m` rows, taker columns | same as above | Same mechanism — taker flow shares the OHLCV bar's close instant. |
| open interest | `open_interest` via `OpenInterestObservation.ts` | the poll's own `ts` | Half-open membership on `ts`; an observation with `ts >= bucket_end` is an invalid request, not silently dropped (`exchange_features.py`). |
| funding | `funding_rate` via `FundingObservation.ts` | the poll's own `ts` | Same mechanism as OI. |
| liquidations | `liquidations` via `LiquidationEvent.ts` (event-driven, never backfilled — `STAGE2_SPEC.md` §13.4) | event arrival `ts` | Same half-open membership; liquidations additionally have **no** historical backfill path (`STAGE2_DATA_AUDIT.md`), so a bootstrap bucket legitimately has `available=0` even when the live feed is healthy — this is a coverage fact, not a lookahead violation. |
| percentiles | `percentile_snapshots` | the sampled bucket's own `bucket_ts` | Reused verbatim from the frozen Percentile Contract (`STAGE2_SPEC.md` §12.2): a sample is in a `bucket_ts=B` snapshot's window iff `B − W <= s.bucket_ts < B` — the current/future bucket is excluded by construction, and the DB-level guard `sample_window_end < bucket_ts` already enforces this independent of application code. |
| data quality | `data_health_snapshots` | `snapshot_ts` (cadence-aligned) | A decision at boundary `T` for timeframe `tf` MUST only read a health snapshot whose `snapshot_ts <= selected_bucket(tf, T) + tf` (i.e. no later than that bucket's own close instant). Reused from the frozen Data Quality Contract (`STAGE2_SPEC.md` §13.1). |
| cross-exchange consensus | `consensus_feature_vectors` | the bucket's own close instant | A `ConsensusFeatureVector` at `bucket_ts=B` is built strictly from `ExchangeFeatureVector`s with the **same** `bucket_ts=B` (identity match, no cross-bucket mixing) — already guaranteed by the existing pipeline (`consensus_pipeline.py`, `consensus_models.py`). |
| rolling V2 context (regime/bias windows, compression windows, structural-level lookbacks — [§4](#4-multi-timeframe-context-contract), [§7](#7-setup-detectors)) | derived from the families above | the newest bucket's own close instant | A rolling window of `N` closed buckets ending at `B = selected_bucket(tf, T)` MUST only include buckets with `bucket_ts <= B`. This is the general rule every detector-specific window below inherits — it is not restated per formula. |

### 2.1 Replay behavior for late-arriving / corrected data

Stage 2 already has a frozen, implemented correction model
(`STAGE2_SPEC.md` §8.3): a corrected raw bar enqueues a `stage2_recompute_queue`
job that recomputes `exchange_feature_vectors` / `consensus_feature_vectors`
/ `percentile_snapshots` **as an upsert under the same `calculation_version`**
— i.e. the Stage 2 *feature* layer is allowed to silently repair itself in
place. V2 reuses this unchanged for the feature layer (it must — there is
no other supported way to fix a bad upstream bar).

**This does not, by itself, satisfy the product invariant that a historical
correction must not rewrite what V2 told the user.** The two are
reconciled by keeping the concepts at different layers, exactly the way V1
already does:

- **Historical live decision truth** — an immutable, insert-once record of
  what V2 actually computed and (if applicable) notified, captured **by
  value** at decision time. V1's `ForecastPrediction` already does this: it
  embeds a full copy of the `ConsensusFeatureVector` it was computed from
  (`consensus_snapshot` field, `analytics/forecasting/persistence.py`), and
  its own docstring states the storage layer "inserts it once and never
  rewrites it." **V2 episode events MUST follow the identical pattern** —
  every persisted episode event embeds the exact feature values (by value,
  not by reference/foreign key alone) it decided from. A later feature-layer
  correction to `consensus_feature_vectors` under the same
  `calculation_version` **MUST NOT** alter an already-persisted episode
  event's embedded values.
- **Later corrected / recomputed research truth** — a separate, explicitly
  provenanced recomputation (e.g. a research replay run) that reads the
  *corrected* feature history. It **MUST** carry its own distinct
  provenance (at minimum: a distinct replay/run identifier) from the live
  decision it is re-evaluating, and MUST NOT overwrite the live decision's
  own row under the live decision's own identity.

Concretely: a corrected 1m bar may legitimately change what
`consensus_feature_vectors` says about bucket `B` tomorrow. It MUST NOT
change what an already-notified V2 episode event dated today, referencing
bucket `B`, is recorded as having said. The correction produces a new,
separately-identified research fact; it does not time-travel into the old
one. This is a logical behavior freeze, not a schema — the exact storage
mechanism for "embed by value, insert-once" is Multi-model Framework
implementation work.

---

## 3. V2 model/version identity

V1 already establishes the pattern this section generalizes:
`ForecastRuleSet.rule_version` (e.g. `"forecast-rules-v0.1.0"`) identifies
*decision-rule* identity, while `calculation_version` (a hash of
`feature_schema_version` + `config_hash` + `code_version`, `STAGE2_SPEC.md`
§10) identifies *upstream feature-computation* identity. Both are already
part of every `ForecastDecision` / `ForecastPrediction`'s validated
identity (`analytics/forecasting/models.py`).

V2 reuses `calculation_version` **unchanged and shared with V1** — both
read the same underlying `exchange_feature_vectors` /
`consensus_feature_vectors` / `percentile_snapshots` infrastructure, and a
Stage 2 config/code change affects both identically. V2 does **not** get
its own parallel feature-computation identity.

V2 introduces one new logical identity of its own:

```text
model_family := "v2"                                  # logical constant, not yet a DB column
rules_version := "v2-rules-v<major>.<minor>.<patch>"   # e.g. "v2-rules-v0.1.0"
```

- **`model_family`** is a logical value, mirroring the roadmap's own framing
  (`docs/FORECASTING_ROADMAP.md` §A: "a `model_family` column... is
  explicitly future work"). This document does not create that column — it
  freezes the **naming rule** so that whenever the Multi-model Framework
  stage does add it, V1 and V2 rows are distinguishable by a value that was
  already decided, not invented ad hoc at implementation time. V1's own
  historical rows are never retroactively relabeled; `model_family="v1"` is
  implied for all rows that predate the column's existence, by
  construction (they came from `analytics/forecasting/`, the only pipeline
  that existed).
- **`rules_version`** is V2's analogue of V1's `rule_version`: it identifies
  the exact set of V2-specific numeric parameters this document freezes
  (regime/bias thresholds, setup-detector thresholds, confidence weights,
  the entry-feasibility delay assumption, the execution-cost assumption,
  cooldowns, material-update thresholds — every V2-v0 parameter in this
  document). It is **independent of** `calculation_version` (feature
  identity) and **independent of** V1's `rule_version` (a different
  namespace; a V2 `rules_version` string is never a valid V1 `rule_version`
  and vice versa — enforced by the `v2-rules-` prefix).

**Versioning invariants (hard):**

- Any change to a V2-v0 numeric parameter frozen in this document — a
  threshold, a weight, a window length, a delay assumption, a cost
  assumption — **MUST** result in a new `rules_version` string.
- An episode/decision record's `rules_version` is fixed at creation and
  **MUST NOT** change over that record's life, even if a newer
  `rules_version` becomes active mid-episode. (Whether an in-flight episode
  is allowed to *continue* under its original `rules_version` after a
  version bump, versus being force-terminated, is an implementation
  operational policy, not a correctness question — but it MUST NOT be
  silently reinterpreted under the new version's semantics.)
- Historical rows/events produced under an old `rules_version` **MUST NOT**
  be silently reprocessed, rescored, or reinterpreted as if produced by a
  newer version. A `GROUP BY rules_version` comparison (mirroring Stage 2's
  existing `calculation_version` retention model, `STAGE2_SPEC.md` §10)
  must remain possible.
- V1 and V2 histories **MUST** remain distinguishable forever — by
  `model_family` once that column exists, and in the interim by the simple
  fact that V2 rows do not exist until the Multi-model Framework
  implementation lands (there is no ambiguity today because there are zero
  V2 rows).

---

## 4. Multi-timeframe context contract

### 4.1 Normalized evidence primitive (used throughout §4–§7)

V2 scoring must combine fields on genuinely incompatible scales (percentage
price moves, USD notionals, ratios, rates — [§5](#5-normalized-evidence)
covers this generally). The context engines below share one signed
normalization primitive, built entirely from the already-frozen Percentile
Contract (`STAGE2_SPEC.md` §12) — no new percentile infrastructure, only a
deterministic use of the existing one:

```text
normalized_evidence(metric, scope, timeframe, window, B):
    snapshot = percentile_snapshot(scope, metric, timeframe, window, bucket_ts=B)
    if snapshot.percentile_rank is None:
        return UNAVAILABLE                      # never 0.0 — see §5.2
    if snapshot.confidence_tier not in {"building", "mature"}:
        return UNAVAILABLE                      # V2-v0: below "building" is too
                                                  # immature a distribution to score from
    return 2.0 * snapshot.percentile_rank - 1.0  # signed, range [-1, +1]
```

This maps `percentile_rank ∈ [0,1]` (§12.1, mid-rank/mean empirical
definition, already frozen) to a signed `[-1, +1]` value in one step: a
bucket whose signed metric (e.g. `price_move_pct_median`) sits at the *top*
of its own history scores near `+1` (a strong, historically-extreme
positive move); the *bottom* of its history scores near `−1`; the *middle*
of its history scores near `0`. This single existing percentile therefore
carries **both** direction and relative magnitude — it deliberately avoids
inventing a second "absolute value" percentile metric that isn't in the
frozen §12.4 allow-list. For **unsigned** magnitude metrics (currently only
`range_width_pct_median`, used for compression, [§7.2](#72-compression_breakout)),
the companion primitive is:

```text
compression_score(timeframe, window, B) = 1.0 - percentile_rank(range_width_pct_median, consensus, timeframe, window, B)
```
(same `UNAVAILABLE`/tier rule), so a *narrow* range relative to history
scores near `1.0` (tight/compressed) and a *wide* range scores near `0.0`.

**Confidence-tier floor is a V2-v0 parameter (`MIN_PCTL_TIER = "building"`).**
Reused reasoning: the 7d window can never reach `"mature"` at all
(`STAGE2_SPEC.md` §12.6, "window-reachability" — a 7-day window's oldest
possible sample is 7 days old, so it structurally cannot satisfy the
30-day `mature` threshold). Requiring `"mature"` everywhere would make
7d-windowed evidence permanently unusable; `"building"` is the loosest
floor that still excludes brand-new, single-digit-sample distributions
(`"none"`/`"low"`).

### 4.2 4h regime

**Inputs** (consensus scope, `timeframe=4h`, `window=30d`, at
`B = selected_bucket(4h, T)`):

```text
price_evi  = normalized_evidence(price_move_pct_median, consensus, 4h, 30d, B)
oi_evi     = normalized_evidence(oi_change_pct_median,  consensus, 4h, 30d, B)
comp       = compression_score(4h, 30d, B)
agreement  = ConsensusFeatureVector.price_direction_agreement   # 0..1, at bucket B
confidence = ConsensusFeatureVector.consensus_confidence         # 0..100, at bucket B
coverage   = ConsensusFeatureVector.min_coverage_ratio            # 0..1, at bucket B
```

**V2-v0 parameters:**

| Name | Value | Reuse / rationale |
|---|---|---|
| `REGIME_MIN_CONFIDENCE` | `50.0` | Reused verbatim from V1's `minimum_consensus_confidence` (`DEFAULT_FORECAST_RULES`) — same scale, same gating role. |
| `REGIME_MIN_COVERAGE` | `2/3` | Reused verbatim from V1's `minimum_coverage_ratio`. |
| `REGIME_TREND_THRESHOLD` | `0.40` | New V2-v0 hypothesis: `|price_evi| >= 0.40` means the 4h move sits in roughly the top/bottom 30% of its own 30d history. |
| `REGIME_MIN_AGREEMENT` | `2/3 ≈ 0.667` | Reused ratio, matching the existing `minimum_exchange_coverage=2`-of-3 consensus floor (`STAGE2_SPEC.md` §11.1) expressed as an agreement ratio, so the regime gate never requires *more* cross-exchange agreement than the consensus core already treats as a valid family. |
| `REGIME_OI_VETO` | `−0.40` | New V2-v0 hypothesis: OI evidence opposing the price direction at or beyond this magnitude vetoes a trend call — mirrors V1's `_oi_score` logic ("rising OI confirms the anchor; falling OI opposes it," `analytics/forecasting/core.py`), generalized to 4h. |
| `REGIME_COMPRESSION` | `0.75` | New V2-v0 hypothesis: 4h range sitting in the tightest quartile of its own 30d history. |

**Formula (deterministic decision tree, evaluated in order):**

```text
1. if any of price_evi/oi_evi/comp is UNAVAILABLE due to missing data
   (not merely tier), or confidence < REGIME_MIN_CONFIDENCE,
   or coverage < REGIME_MIN_COVERAGE:
       regime = INSUFFICIENT_DATA

2. elif |price_evi| >= REGIME_TREND_THRESHOLD
     and agreement >= REGIME_MIN_AGREEMENT
     and not (oi_evi is available and sign(oi_evi) != sign(price_evi) and oi_evi <= REGIME_OI_VETO):
       regime = BULLISH_TRENDING   if price_evi > 0
       regime = BEARISH_TRENDING   if price_evi < 0

3. else:
       regime = NON_DIRECTIONAL          # carries an is_compressed = (comp >= REGIME_COMPRESSION) flag
```

Four possible outputs: `BULLISH_TRENDING`, `BEARISH_TRENDING`,
`NON_DIRECTIONAL` (with an attached `is_compressed` boolean — deliberately
*one* state with a flag rather than a fifth enum value, since "how tight is
the non-trend" is a magnitude question, not a new regime identity), and
`INSUFFICIENT_DATA`. This is not "price up ⇒ bullish": direction requires
*both* a percentile-extreme move *and* cross-exchange agreement, and can be
**vetoed** by contradicting OI evidence even when price alone clears the
threshold.

### 4.3 1h bias

Same primitive, deliberately **lighter** and **faster-adapting** than
regime — a shorter window, a lower threshold, and no OI-confirmation
requirement (regime already owns OI confirmation; see [§4.4](#44-independence--anti-double-counting)).

**Inputs** (consensus scope, `timeframe=1h`, `window=7d`, at
`B = selected_bucket(1h, T)`):

```text
bias_evi   = normalized_evidence(price_move_pct_median, consensus, 1h, 7d, B)
agreement  = ConsensusFeatureVector.price_direction_agreement   # at bucket B
confidence = ConsensusFeatureVector.consensus_confidence
coverage   = ConsensusFeatureVector.min_coverage_ratio
```

`window=7d` is deliberate, not an oversight: the Percentile Contract's own
window-reachability rule ([§4.1](#41-normalized-evidence-primitive-used-throughout-47))
means a 7d window can only ever reach `"building"` tier, which is exactly
the floor `MIN_PCTL_TIER` already requires — bias is evaluated at the
fastest window the frozen infrastructure supports.

**V2-v0 parameters:** `BIAS_MIN_CONFIDENCE = 50.0` (reused, same as
regime), `BIAS_MIN_COVERAGE = 2/3` (reused), `BIAS_THRESHOLD = 0.25` (V2-v0
— lower than regime's `0.40`, since bias is meant to be easier to
establish than a full regime call), `BIAS_MIN_AGREEMENT = 2/3` (reused).

```text
1. if bias_evi is UNAVAILABLE, or confidence < BIAS_MIN_CONFIDENCE,
   or coverage < BIAS_MIN_COVERAGE:
       bias = UNAVAILABLE

2. elif bias_evi >= BIAS_THRESHOLD and agreement >= BIAS_MIN_AGREEMENT:
       bias = BULLISH
3. elif bias_evi <= -BIAS_THRESHOLD and agreement >= BIAS_MIN_AGREEMENT:
       bias = BEARISH
4. else:
       bias = NEUTRAL_NOT_ESTABLISHED
```

Per `V2_PRODUCT_CONTRACT.md` §10, a `NEUTRAL_NOT_ESTABLISHED` bias **MUST
NOT** by itself invalidate a `COMPRESSION_BREAKOUT` candidate
([§7.2](#72-compression_breakout)) — this document does not add such a
gate anywhere.

### 4.4 Independence / anti-double-counting

Regime and bias deliberately read **different evidence compositions**, not
the same weighted score replayed at a different timeframe:

| | 4h regime | 1h bias |
|---|---|---|
| Window | 30d | 7d |
| Threshold | `0.40` (stricter) | `0.25` (looser) |
| OI confirmation | **Required** (can veto) | Not used |
| Compression awareness | Yes (`is_compressed` flag) | Not used |
| Role | "Is there an established, OI-confirmed higher-timeframe trend?" | "Which way does the nearer-term tape lean, if at all?" |

A single strong impulsive 4h move is read by regime as one thing (a
30d-relative price+OI-confirmed extreme) and by bias as a *different* thing
(a 7d-relative price lean) — they can and often will agree, but they are
never computed from the same window, the same threshold, or the same
evidence set, so the same market impulse is never summed as two
independent votes. `TREND_PULLBACK` ([§7.1](#71-trend_pullback)) is the
only detector that requires both to agree — everywhere else they remain
genuinely separable (a `COMPRESSION_BREAKOUT` may legitimately form on a
`NEUTRAL_NOT_ESTABLISHED` bias, per the Product Contract).

---

## 5. Normalized evidence

[§4.1](#41-normalized-evidence-primitive-used-throughout-47) already
defines the exact signed-normalization formula
(`normalized = 2 * percentile_rank − 1`) and its unsigned companion
(`compression_score = 1 − percentile_rank`) used throughout this document.
This section freezes the remaining general rules.

### 5.1 Percentile lookback / window

- Regime and any 4h-scoped evidence: `window = 30d`.
- Bias and any 1h-scoped evidence: `window = 7d`.
- 15m-scoped setup-formation evidence (compression, retracement magnitude):
  `window = 30d` — a 15m distribution accumulates enough samples quickly
  (96 buckets/day), so the longer, more stable window is preferred over
  the faster-adapting 7d one; setup formation should not react to a few
  hours of unusual 15m noise the way bias intentionally does at 1h.
- 5m is deliberately **not** percentile-scored for context evidence
  ([§4.4](#44-independence--anti-double-counting) role separation) — 5m
  reads raw sign + agreement for trigger/confirmation purposes only
  (`ConsensusFeatureVector.price_direction_agreement`,
  `price_move_pct_median`'s ternary sign), never a percentile strength
  score. This keeps 5m's role as "trigger," not a fifth independent
  evidence vote.

### 5.2 Missing percentile handling — never `None == 0`

`normalized_evidence` / `compression_score` return the sentinel
`UNAVAILABLE`, never `0.0`, whenever:

- the current bucket's underlying metric value itself is `NULL` (per
  `STAGE2_SPEC.md` §12.5, "current value NULL → valid snapshot,
  `percentile_rank = NULL`");
- the sample is empty (`sample_size = 0`);
- `confidence_tier` is below `MIN_PCTL_TIER` ("building").

**Downstream treatment of `UNAVAILABLE` is context-specific and MUST be
stated explicitly at each use site — never implicitly coerced to zero:**

| Use site | Treatment of `UNAVAILABLE` |
|---|---|
| 4h regime, 1h bias ([§4](#4-multi-timeframe-context-contract)) | Hard fail for that evidence input → whole context result is `INSUFFICIENT_DATA` / `UNAVAILABLE` (regime/bias have few enough inputs that any missing one is disqualifying). |
| Setup detector evidence-score contribution ([§7](#7-setup-detectors)) | Excluded and the remaining applicable weights renormalized to their own sum — same pattern as the already-frozen Data Confidence family-score renormalization (`STAGE2_SPEC.md` §11.4). |
| Confidence formula components ([§8](#8-model-confidence-semantics)) | Excluded and renormalized, same rule; `UNAVAILABLE` never contributes a `0.0` toward the weighted sum and never increases confidence merely by disappearing. |

A missing percentile is therefore either a **hard fail**, a **neutral
(renormalized-out) contribution**, or a **setup-specific unavailable
state** depending on the use site named above — the general rule is: state
explicitly which of the three applies, and never let `None` silently
compute as `0`.

---

## 6. Cross-exchange correctness

### 6.1 The existing consensus engine is reused unchanged across all four timeframes

`ConsensusFeatureVector` and the Consensus Contract (`STAGE2_SPEC.md` §11)
are **already timeframe-generic** — `timeframe` is part of every request's
identity, and nothing in the frozen coverage/agreement/dispersion/outlier
formulas is 5m-specific. Per §5.1 of that spec, the bucket listener already
writes `consensus_feature_vectors` rows for `1m/5m/15m/1h/4h` uniformly.
**V2 does not invent a second consensus algorithm.** Every `4h`/`1h`/`15m`
context computation in this document reads real, already-computed
`ConsensusFeatureVector` rows at that timeframe — no new data source, no
parallel aggregation path.

### 6.2 What does NOT carry over unchanged: the numeric gate values

The Consensus Contract's *formulas* (coverage ratio, direction agreement,
dispersion, family confidence) are timeframe-independent by construction
and are reused as-is. What is **not** automatically timeframe-independent
is V1's specific *numeric decision gate* (`minimum_coverage_ratio=2/3`,
`minimum_consensus_confidence=50.0`) — those live in
`ForecastRuleSet`, V1's own 5m-only rule set, not in the Consensus
Contract itself, and V1's module docstring is explicit that its scope is
"the CURRENT shadow scope only: BTCUSDT / perp / 5m."

This document resolves the question `V2_PRODUCT_CONTRACT.md` §10 left
open ("whether that exact gate ... carries over unchanged to 15m/1h/4h ...
is DEFERRED") as follows: **the same numeric values (`2/3` coverage,
`50.0` confidence) are reused at every timeframe as the V2-v0 starting
gate**, because nothing about the underlying consensus formula changes
with timeframe — a 2-of-3 exchange requirement and a 50/100 confidence
floor are not 5m-specific facts, they are judgments about how much
cross-exchange evidence is "enough," which this document treats as
timeframe-invariant until evidence says otherwise. This is a **V2-v0
hypothesis, not a proof** — it is deliberately the same numbers V1 already
uses operationally, reused for consistency rather than re-derived from
scratch, and it is a `rules_version`-participating parameter like every
other number in this document.

### 6.3 Coverage / degraded behavior / fail-closed

| Coverage state | Direction computable? | Setup allowed? |
|---|---|---|
| `min_coverage_ratio >= 2/3` at the relevant timeframe(s), `consensus_confidence >= 50.0` | Yes | Yes, subject to the detector's own gates. |
| `min_coverage_ratio < 2/3` for a **context** timeframe (4h/1h) | No — that context input is `INSUFFICIENT_DATA`/`UNAVAILABLE` ([§4](#4-multi-timeframe-context-contract)) | Detector-dependent: `TREND_PULLBACK` requires both regime and bias, so it fails closed; `COMPRESSION_BREAKOUT` requires only that its own gates pass (a neutral/unavailable 1h bias is not itself disqualifying per the Product Contract, but `INSUFFICIENT_DATA` 4h regime **is** disqualifying — "insufficient data" is not the same as "neutral"). |
| `min_coverage_ratio < 2/3` for the **5m trigger** bucket | No | No new candidate may transition to `CONFIRMED` at that boundary; an already-`CONFIRMED` episode is not auto-invalidated by this alone (missing evidence is not structural invalidation, [§10](#10-structural-invalidation)) but also cannot be strengthened/re-confirmed on that boundary. |
| Single-exchange contribution to any family | Coverage `< 2/3` (1-of-3) → fails the gate above by construction (the frozen consensus minimum, `STAGE2_SPEC.md` §11.1, already refuses a single exchange). **A single exchange's data MUST NOT masquerade as consensus** — this is enforced by the existing `minimum_exchange_coverage` gate, reused unchanged, not re-implemented. | — |

**Every family affecting a setup's evidence score is subject to the same
renormalize-or-fail rule as [§5.2](#52-missing-percentile-handling--never-none--0):**
a family below its minimum coverage contributes `UNAVAILABLE`, which is
either excluded-and-renormalized (evidence scoring) or a hard fail
(context sufficiency gates), never a silent zero.

---

## 7. Setup detectors

Every detector shares the `selected_bucket` clock ([§1](#1-the-v2-decision-clock))
and the reference-price convention ([§11](#11-reference-price-semantics)).
Every ATR-style volatility reference below is the **range-width proxy**,
defined once here because three detectors use it:

```text
RANGE_PROXY_pct(timeframe, N, B) =
    mean(range_width_pct_median at consensus scope, timeframe, over the N
         most recent closed buckets with bucket_ts in [B - (N-1)*tf, B])
```

`N = 14` (V2-v0 — a conventional smoothing length, explicitly **not**
justified by tradition; it is used here only because Stage 2 has no
literal `ATR(14)` field and none is added by this document — `range_width_pct_median`
is already ingested and computed at every timeframe, so a rolling mean of
it is a "deterministic derived value computable from already-ingested
data," exactly what `V2_PRODUCT_CONTRACT.md` requires when substituting for
a conventional indicator). This is **not** literal Average True Range — no
ATR field exists in this codebase and this document does not invent one.

```text
protection_buffer(timeframe, B, reference_price) =
    max(3 * tick_size,                                                     # reused from STAGE2_CLARIFICATIONS.md §1's "minimum_tick_buffer = 3 × tick_size"
        reference_price * RANGE_PROXY_pct(timeframe, 14, B) / 100 * 0.5)   # BUFFER_MULTIPLIER = 0.5, V2-v0
```

`tick_size` is read from `exchange_instruments.tick_size` for the
reference exchange ([§11](#11-reference-price-semantics)) — already-ingested
instrument metadata, not a new source. `BUFFER_MULTIPLIER = 0.5` is a
V2-v0 hypothesis, generalizing Stage 2 Clarifications' "configurable
fraction × ATR buffer" idea with an explicit starting fraction instead of
leaving it unset.

### 7.1 `TREND_PULLBACK`

**Preconditions (candidate formation gate).**

```text
4h regime in {BULLISH_TRENDING, BEARISH_TRENDING}      # not INSUFFICIENT_DATA, not NON_DIRECTIONAL
1h bias == same direction as 4h regime                  # not NEUTRAL_NOT_ESTABLISHED, not opposite, not UNAVAILABLE
```

Per `V2_PRODUCT_CONTRACT.md` §4.1 ("4h establishes that a trending regime
exists... 1h establishes the directional bias the trend is moving in"),
both are required and must agree — this is the one detector where regime
and bias are jointly gating, by product definition.

**Retracement (15m).** Let `B15 = selected_bucket(15m, T)`. Using the
reference exchange's own `close_price` (`ExchangeFeatureVector`, 15m) over
a lookback of `LOOKBACK_15M = 48` closed buckets (12h, V2-v0):

```text
trend_leg_extreme = max(close_price) over the lookback, for a bullish trend
                   = min(close_price) over the lookback, for a bearish trend
retracement_pct = (trend_leg_extreme - current_close) / trend_leg_extreme * 100   # bullish
retracement_pct = (current_close - trend_leg_extreme) / trend_leg_extreme * 100   # bearish
```

Valid pullback range (V2-v0, expressed as multiples of the 15m range
proxy rather than a folklore Fibonacci ratio, so it is grounded in actually
measured recent volatility):

```text
PULLBACK_MIN_MULT = 0.5   # below this: "random sideways noise," not a real pullback
PULLBACK_MAX_MULT = 3.0   # above this: "trend failure," not a pullback

valid iff PULLBACK_MIN_MULT * RANGE_PROXY_pct(15m,14,B15)
          <= retracement_pct <=
          PULLBACK_MAX_MULT * RANGE_PROXY_pct(15m,14,B15)
```

**Candidate age.** Max `PULLBACK_MAX_AGE = 8` closed 15m buckets (2h,
V2-v0) from first detection to confirmation, else → `EXPIRED`
([§14](#14-lifecycle-transitions)).

**5m confirmation (trigger).** At `B5 = selected_bucket(5m, T)`: the
consensus `price_move_pct_median` sign matches the trend direction (ternary
sign, per `STAGE2_SPEC.md` §11.2) **and** `price_direction_agreement >=
2/3`, for **one** closed 5m bucket (`RESUMPTION_MIN_BUCKETS = 1`, V2-v0 —
deliberately the loosest possible, since 5m's role is trigger, not
strength-scoring, [§5.1](#51-percentile-lookback--window)).

**Structural invalidation.** `pullback_extreme` = the deepest `close_price`
reached during the retracement (min for bullish, max for bearish, reference
exchange, 15m):

```text
LONG:  invalidation_price = pullback_extreme_low  - protection_buffer(15m, B15, reference_price)
SHORT: invalidation_price = pullback_extreme_high + protection_buffer(15m, B15, reference_price)
```

Invalidated when the reference exchange's **closed 5m bucket** `close_price`
crosses beyond `invalidation_price` — a single closed candle, never a wick
([§10](#10-structural-invalidation) explains the close-vs-wick,
single-vs-multiple choice generally).

**Entry zone.**
```text
LONG:  [pullback_extreme_low,  confirmation_close_price]
SHORT: [confirmation_close_price, pullback_extreme_high]
```
Both bounds are already-observed structural prices (the deepest retracement
point and the confirming close), not an arbitrary ± band.

**Expected horizon:** `2h` from `CONFIRMED` ([§14](#14-candidate-expiry-and-expected-horizons)).

### 7.2 `COMPRESSION_BREAKOUT`

**Compression (15m).** Let `B15 = selected_bucket(15m, T)`,
`COMPRESSION_LOOKBACK = 16` closed 15m buckets (4h, V2-v0):

```text
compressed iff compression_score(15m, 30d, B15) >= COMPRESSION_THRESHOLD (0.75, V2-v0)
               for at least COMPRESSION_MIN_DURATION = 6 consecutive closed 15m
               buckets (1.5h, V2-v0) within COMPRESSION_LOOKBACK
```

`compression_score` is defined in [§4.1](#41-normalized-evidence-primitive-used-throughout-47)
— the *same* primitive as regime's `is_compressed` flag, deliberately, but
evaluated at `15m` instead of `4h`: 4h regime's compression flag answers
"is the broad regime non-trending," while this is the setup-formation-level
question "has a genuine, sustained tight range formed recently enough to
break out of." Requiring `COMPRESSION_MIN_DURATION` consecutive buckets
(not just one narrow bucket) is what prevents "price moved strongly,
therefore call it compression breakout" — a single quiet 15m bar is not a
compression regime.

**Context requirement.** 4h regime `!= INSUFFICIENT_DATA` (data must exist,
but the regime itself **MAY** be `NON_DIRECTIONAL` or even trending — per
`V2_PRODUCT_CONTRACT.md` §4.2, compression does not require an opposing
regime to be absent, only that it isn't itself unusable). 1h bias **MAY**
be `NEUTRAL_NOT_ESTABLISHED` (per Product Contract §10, this is explicitly
not disqualifying).

**Breakout boundary.** The compression range's bounds, from the same 15m
window used to establish compression:
```text
range_high = max(high) over the compression window, reference exchange
range_low  = min(low)  over the compression window, reference exchange
```

**Directional confirmation (5m trigger).** A closed 5m bucket (reference
exchange) closes beyond `range_high` (bullish) or `range_low` (bearish),
**and** consensus `price_direction_agreement(5m) >= 2/3` on that bucket.

**Volume/flow confirmation (required, V2-v0).** `taker_delta_notional_usd_sum`
(consensus, 5m) at the breakout bucket has the same sign as the breakout
direction — a breakout with taker flow opposing the direction of the break
does not confirm (reuses already-ingested consensus taker-flow sums, no
new field).

**False-break / invalidation.** A closed 5m bucket closing back inside the
compression range (`range_low < close < range_high`) within
`FALSE_BREAK_WINDOW = 3` closed 5m buckets (15 min, V2-v0) of the trigger
invalidates the candidate before confirmation. Once `CONFIRMED`, structural
invalidation is:
```text
LONG:  invalidation_price = range_low  - protection_buffer(15m, B15, reference_price)
SHORT: invalidation_price = range_high + protection_buffer(15m, B15, reference_price)
```
same close-based, single-bucket rule as [§7.1](#71-trend_pullback).

**Entry zone.** `[range boundary, range boundary ± protection_buffer]` —
i.e. `[range_high, range_high + protection_buffer]` (LONG) /
`[range_low − protection_buffer, range_low]` (SHORT): entry is anchored at
the broken structural boundary itself, with the protection buffer as the
zone's only width (there is no "confirmation price" analogous to
`TREND_PULLBACK`'s, since the breakout bucket's close **is** the
confirmation).

**Candidate expiry / horizon:** max age from trigger to confirmation `1h`
(`12` closed 5m buckets, V2-v0); expected horizon `1.5h` from `CONFIRMED`.

### 7.3 `CONFIRMED_BREAKOUT`

**Structural level (1h).** Let `B1 = selected_bucket(1h, T)`,
`LEVEL_LOOKBACK = 48` closed 1h buckets (48h, V2-v0). The level is defined
by **high/low extremes**, not closes (a structural level is physically an
extreme; closes govern breakout/invalidation acceptance, per the
close-based principle stated once in [§10](#10-structural-invalidation)):
```text
resistance_level = max(high) over the lookback, reference exchange, 1h
support_level     = min(low)  over the lookback, reference exchange, 1h
```

**Breakout requirement.** A closed 5m bucket (reference exchange) closes
beyond `resistance_level` (bullish) or `support_level` (bearish).

**Confirmation (what makes it "confirmed").** `CONFIRMATION_CLOSES = 2`
consecutive closed 5m buckets, both closing beyond the level (V2-v0) —
this is the structural difference from `COMPRESSION_BREAKOUT`, whose
trigger requires only **one** confirming close: `CONFIRMED_BREAKOUT` is the
general case with *no* preceding-compression precondition, so it demands
one extra closed bucket of follow-through in exchange for not requiring a
compression regime. `CONFIRMATION_MAX_AGE = 8` closed 5m buckets (40 min,
V2-v0) from the first breaking close to the second — if the second
confirming close doesn't arrive in time, the candidate is rejected (not
`EXPIRED`, since it never reached `EARLY_SIGNAL`'s candidate-age clock —
see [§14](#14-candidate-expiry-and-expected-horizons)).

**Invalidation.**
```text
LONG:  invalidation_price = support_level_or_resistance_level_broken - protection_buffer(1h, B1, reference_price)
SHORT: invalidation_price = ... + protection_buffer(1h, B1, reference_price)
```
i.e. beyond the broken level itself (not the retest extreme — unlike the
Stage 2 Clarifications' historical sweep/reclaim design, V2's
`CONFIRMED_BREAKOUT` has no retest-extreme concept; the broken level is the
only structural anchor).

**Entry zone.** `[level, level ± protection_buffer]`, same construction as
`COMPRESSION_BREAKOUT`'s.

**Difference from `COMPRESSION_BREAKOUT`, summarized:** `CONFIRMED_BREAKOUT`
requires **no** preceding compression precondition, uses a **1h** structural
lookback (vs. 15m compression window), requires **two** confirming closes
(vs. one trigger close), and has **no** taker-flow confirmation requirement
(compression's volume-confirmation gate does not carry over — a generic
level break is not defined by the preceding volatility regime the way a
compression breakout is).

**Candidate expiry / horizon:** confirmation deadline `40 min` (above);
expected horizon `2.5h` from `CONFIRMED`.

### 7.4 Setup-family precedence and deduplication

**Deterministic precedence order:** `COMPRESSION_BREAKOUT` >
`CONFIRMED_BREAKOUT` > `TREND_PULLBACK`.

Applied whenever two or more detectors would independently qualify a **new**
candidate over the **same direction** and **overlapping structural region**
(the breaking price level/zone) **at the same decision boundary**: the
lower-precedence detector's candidate is **suppressed** and instead
recorded as a cross-referenced reason/tag on the higher-precedence
episode — it never becomes an independent second episode.

Rationale for the order: `COMPRESSION_BREAKOUT`'s defining feature (the
preceding compression) is strictly more specific and more informative than
a bare structural-level break, so a break that qualifies as both is more
precisely described as the compression breakout. `CONFIRMED_BREAKOUT`
outranks `TREND_PULLBACK` because a fresh structural-level break is a
distinct, more specific event than "the trend resumed" when both would
otherwise fire on the same move.

Different-direction simultaneous qualifications are **not** deduplicated by
this rule — that is the `REVERSAL_CANDIDATE` mechanism
([§13.3](#133-reversal_candidate-mechanics)), a deliberately separate
concept. Different-family candidates of the **same** direction that do
**not** structurally overlap (e.g. a `TREND_PULLBACK` resuming a 4h trend
and, hours later and at an unrelated price level, a fresh
`COMPRESSION_BREAKOUT`) are **not** deduplicated — they are genuinely
different market ideas and may coexist as distinct episodes, subject to
the one-active-episode-per-`(direction, family)` rule in
[§12](#12-episode-identity-and-deduplication).

---

## 8. Model confidence semantics

V2 confidence is **not** win probability — per `V2_PRODUCT_CONTRACT.md` §7,
it remains an explicit, uncalibrated evidence/data-quality strength score,
the same category of value V1's `confidence` already is (`analytics/forecasting/models.py`
docstring: "an uncalibrated, deterministic ACTION-STRENGTH score... NOT a
probability of profit").

**Components** (each `∈ [0,1]` or `UNAVAILABLE`):

| Component | Definition |
|---|---|
| `regime_strength` | `|price_evi|` from [§4.2](#42-4h-regime) if regime is `BULLISH_TRENDING`/`BEARISH_TRENDING`; `comp` (compression_score) if `NON_DIRECTIONAL` with `is_compressed`; else `UNAVAILABLE`. |
| `bias_strength` | `|bias_evi|` from [§4.3](#43-1h-bias) if bias is `BULLISH`/`BEARISH`; `0.0` (a genuine, valid zero — "no lean" is a real measured value, not missing data) if `NEUTRAL_NOT_ESTABLISHED`; `UNAVAILABLE` if `UNAVAILABLE`. |
| `setup_strength` | Detector-specific: `TREND_PULLBACK` → `1 − (retracement_pct / (PULLBACK_MAX_MULT * RANGE_PROXY_pct))` clamped `[0,1]` (deeper-but-still-valid retracements score lower); `COMPRESSION_BREAKOUT` → `comp` at the compression bucket; `CONFIRMED_BREAKOUT` → `min(1.0, (breakout_distance_beyond_level) / protection_buffer)` clamped `[0,1]`. |
| `trigger_strength` | `price_direction_agreement` at the confirming 5m bucket (already `∈[0,1]`). |
| `data_confidence` | `consensus_confidence / 100.0` (already `∈[0,1]`) at the setup-formation timeframe's bucket. |

**Weights (V2-v0, `rules_version`-participating):**

| Component | Weight |
|---|---|
| `regime_strength` | `0.25` |
| `bias_strength` | `0.20` |
| `setup_strength` | `0.30` |
| `trigger_strength` | `0.15` |
| `data_confidence` | `0.10` |

Weights are finite, `>= 0`, sum to `1.0` — the same validation shape as
V1's `ForecastRuleSet.component_weights` (`analytics/forecasting/models.py`),
reused as a pattern, not as shared code. **Applicable-component
renormalization**, reusing the Data Confidence family-score pattern
(`STAGE2_SPEC.md` §11.4): any `UNAVAILABLE` component is excluded and the
remaining applicable weights are renormalized to their own sum before the
weighted sum is taken. If **all** components are `UNAVAILABLE`, confidence
is itself `UNAVAILABLE` and the episode cannot be scored (fails closed,
[§18](#18-failure--fail-closed-rules)).

```text
model_confidence = Σ (weight_c * component_c) / Σ (weight_c for c not UNAVAILABLE)     # range [0,1]
```

**Hard invariants:**

- `model_confidence` **MUST NOT** increase merely because a component
  became `UNAVAILABLE` and dropped out of the renormalized sum in a way
  that happens to raise the average — this is a known risk of naive
  renormalization. **V2-v0 mitigation:** whenever the number of available
  components drops below `4` (out of 5), `model_confidence` is capped at
  `0.70` regardless of the renormalized weighted sum — partial evidence can
  never present as unusually strong. This cap is itself a `rules_version`-participating
  V2-v0 parameter.
- Unavailable evidence **MUST NOT** be treated as confirming evidence
  anywhere in this formula — it is excluded, never substituted with a
  favorable value.
- `model_confidence` and `data_confidence` (coverage/quality) remain
  **separate, both-visible** quantities — `data_confidence` is one
  component *among* five, never conflated with the composite score itself.
- These weights are **initial scoring parameters to evaluate**, explicitly
  not empirically calibrated win-probability weights — no claim of
  optimality is made or implied.

---

## 9. Entry zone semantics

- **Lower/upper bound, reference-price source:** per-detector, defined in
  [§7](#7-setup-detectors) — always derived from already-observed
  structural prices (a retracement extreme, a confirming close, a broken
  level) plus/minus `protection_buffer`, never an arbitrary fixed
  percentage band.
- **When established:** at the same decision boundary the episode first
  reaches `EARLY_SIGNAL` (candidate formation) — an entry zone exists for
  the full life of the episode, not only after `CONFIRMED`.
- **May the zone move after first publication?** **Yes, but only while the
  episode remains `EARLY_SIGNAL`** (the structural inputs — retracement
  extreme, compression range, breaking level — can still be actively
  forming). **Once `CONFIRMED`, the entry zone is frozen** — it MUST NOT
  widen or narrow afterward. This mirrors [§10](#10-structural-invalidation)'s
  treatment of invalidation as a hard, stable gate once confirmed.
- **Historical-truth rule:** an entry zone already shown to the user
  (i.e. published in a `CONFIRMED` or later notification) **MUST NOT** be
  silently rewritten. If a pre-`CONFIRMED` update legitimately changes the
  zone, the prior published value is conceptually preserved in the
  episode's event history — reusing the same insert-once-per-event pattern
  frozen in [§2.1](#21-replay-behavior-for-late-arriving--corrected-data)
  for feature snapshots. This is a logical requirement; physical event-history
  persistence is implementation work, not specified here.
- **What update requires a new material notification:** a pre-`CONFIRMED`
  zone change is **not** itself material ([§16](#16-notification-materiality--anti-spam-thresholds));
  the `CONFIRMED` transition (which freezes the zone) is always material.

---

## 10. Structural invalidation

**Every detector's invalidation is defined in [§7](#7-setup-detectors)** as
a structural price level plus `protection_buffer`
([§7](#7-setup-detectors) preamble). This section freezes the rules common
to all three.

- **Evidence weakening vs. structural invalidation are distinct.** A drop
  in `model_confidence`, a coverage degradation, or a weakening trigger
  moves an episode toward `WEAKENING` ([§13](#13-lifecycle-transition-semantics))
  — it never by itself crosses `invalidation_price`. Only a price event
  can invalidate; a purely evidentiary/data-quality deterioration cannot.
- **Basis: closed 5m candle close, not a wick/intrabar touch, and a single
  closed bucket, not multiple.** Reasoning: (a) close-based judgment
  matches the existing repo convention that "using a candle's wick/extreme
  as entry is forbidden" (`STAGE2_CLARIFICATIONS.md` §1) — the same
  close-acceptance principle applies symmetrically to invalidation; (b) a
  *single* closed bucket, not a multi-close confirmation requirement, is
  deliberate — invalidation is a hard safety gate, and requiring extra
  confirming closes before recognizing a broken structural premise would
  let a broken scenario continue being presented as valid for longer
  purely because of the confirmation-count design, which directly
  contradicts the "high composite score MUST NOT bypass a mandatory hard
  gate" principle (`V2_PRODUCT_CONTRACT.md` §10). Confirmation
  (`EARLY_SIGNAL → CONFIRMED`) is allowed to require more evidence because
  it is not safety-critical the same way invalidation is.
- **A broken scenario MUST NOT survive merely because its composite
  `model_confidence` remains high.** Invalidation is checked
  **independently** of, and with **higher precedence than**, confidence —
  see the transition-precedence order in [§13.1](#131-transition-precedence).

---

## 11. Reference-price semantics

**Canonical V2 reference exchange: `binance`**, reusing V1's existing
operational default (`runtime/shadow_cli.py`:
`reference_exchange = ... or "binance"`) rather than introducing a second
convention.

**Reference price at a timeframe/bucket** is the reference exchange's own
`close_price` (`ExchangeFeatureVector`) for the relevant closed bucket —
identical convention to V1's `reference_price_source = f"{exchange}_close_5m"`
(`analytics/forecasting/shadow_cycle.py`), generalized to whichever
timeframe a given calculation needs (5m for triggers/invalidation
checks, 15m/1h for structural-level construction).

**Failover — fail closed, no silent switching.** Reusing V1's exact
`_resolve_reference_vector` gate (`shadow_cycle.py`): the reference
vector is usable only if `is_usable is True`, `has_gap is False`,
`bars_present` equals the timeframe's full expected bar count, and
`close_price is not None`. If Binance's reference vector for the selected
bucket fails this gate, **V2 MUST fail closed for any calculation that
needs it** — no silent failover to Bybit or OKX for exact price levels.
This satisfies the Product Contract's "no silent switching between
exchanges during one episode" requirement directly, by reuse rather than
new design. **A future, explicitly versioned V2-v0 fallback rule** (e.g. a
declared secondary reference exchange) **may** be added later, but is not
specified here — until it is, the fail-closed behavior above is the entire
rule.

**Cross-exchange evidence remains consensus-based** even though one
canonical exchange supplies exact price levels — regime/bias/setup
evidence scoring ([§4](#4-multi-timeframe-context-contract), [§7](#7-setup-detectors))
reads `ConsensusFeatureVector` fields (already cross-exchange aggregates),
while only the *exact tradable price levels* (entry zone bounds,
invalidation price, structural level price) come from the single canonical
reference exchange. These are deliberately different data paths for
different purposes — evidence strength vs. exact reproducible price — and
this document does not conflate them.

---

## 12. Episode identity and deduplication

**Logical identity (not a database key):**

```text
episode_logical_key = (symbol, market_type, direction, setup_family, structural_anchor)
```

`structural_anchor` is family-specific, always a deterministic function of
already-closed data:

| Family | `structural_anchor` |
|---|---|
| `TREND_PULLBACK` | the `bucket_ts` of the 15m bucket establishing `trend_leg_extreme` ([§7.1](#71-trend_pullback)). |
| `COMPRESSION_BREAKOUT` | the `bucket_ts` of the first 15m bucket in the qualifying compression window ([§7.2](#72-compression_breakout)). |
| `CONFIRMED_BREAKOUT` | the `(bucket_ts, price)` of the 1h extreme defining the broken level, price rounded to the reference exchange's `tick_size` ([§7.3](#73-confirmed_breakout)). |

**New observation vs. new episode.** A new detector qualification updates
an existing **active** (non-terminal) episode iff its
`episode_logical_key` matches exactly. A qualification with the same
`(direction, setup_family)` but a **materially different**
`structural_anchor` — defined as: for `TREND_PULLBACK`/`COMPRESSION_BREAKOUT`,
a different anchor bucket more than `ANCHOR_DRIFT_BUCKETS = 4` buckets
away at that family's own timeframe; for `CONFIRMED_BREAKOUT`, a level
price differing by more than `2 * protection_buffer` — is treated as
follows:

```text
at most ONE active (non-terminal) episode per (symbol, market_type, direction, setup_family)

if a materially-different candidate qualifies while an active episode of
the same (direction, family) already exists:
    the new candidate is SUPPRESSED (not created) until the active episode
    reaches a terminal state (INVALIDATED / EXPIRED / COMPLETED)
```

This directly resolves both failure modes the Product Contract flags: it
does **not** mint a new episode every 5m bucket (only a materially
different anchor is even eligible to be "new," and even then it queues
rather than spawning a concurrent duplicate), and it does **not** let one
old episode block *all* future BTC setups — only same-`(direction, family)`
candidates are suppressed; a different family, or the opposite direction,
is free to open independently.

**Different families, same direction:** MAY coexist as distinct episodes
(different market ideas), subject to the precedence/dedup rule in
[§7.4](#74-setup-family-precedence-and-deduplication) when they structurally
overlap.

**Opposite direction:** MAY open independently and concurrently at any
time — this is what makes `REVERSAL_CANDIDATE` possible
([§13.3](#133-reversal_candidate-mechanics)). Episodes are never mutually
exclusive across direction.

**Terminal-episode cooldown (V2-v0):**

| Terminal state | Cooldown before a new episode of the same `(direction, family)` may open |
|---|---|
| `INVALIDATED` | `3` closed 5m buckets (15 min) — prevents immediate flip-flop re-triggering right at the broken level. |
| `EXPIRED` / `COMPLETED` | `1` closed 5m bucket (5 min) — a clean resolution, not a broken premise, needs less cooldown. |

All of the above (`ANCHOR_DRIFT_BUCKETS`, cooldown lengths) are V2-v0
parameters, `rules_version`-participating.

---

## 13. Lifecycle transition semantics

### 13.1 Transition precedence

When multiple conditions are simultaneously true at one decision boundary,
evaluated in this fixed order (first match wins):

```text
1. structural invalidation      (§10 — always wins; a hard gate overrides
                                  confidence, confirmation, and completion)
2. completion / expiry           (mutually exclusive by construction — see
                                  §14; completion only evaluated for
                                  CONFIRMED/WEAKENING episodes at horizon
                                  end, expiry only for EARLY_SIGNAL episodes
                                  at candidate-age end)
3. confirmation                  (EARLY_SIGNAL -> CONFIRMED)
4. weakening / recovery          (evidence-quality transitions only)
```

Invalidation outranks everything, including a same-boundary confirmation
signal: a structurally broken premise cannot be "confirmed" no matter what
other evidence says, directly extending
`V2_PRODUCT_CONTRACT.md` §10's "a high score MUST NOT bypass a mandatory
hard gate" to state transitions.

### 13.2 Allowed transitions

```text
EARLY_SIGNAL -> CONFIRMED     confirmation criteria met (§7, per family)
EARLY_SIGNAL -> INVALIDATED   structural invalidation reached before confirming
EARLY_SIGNAL -> EXPIRED       max candidate age elapsed without confirming (§14)

CONFIRMED    -> WEAKENING     evidence-quality degradation (below)
CONFIRMED    -> INVALIDATED   structural invalidation reached
CONFIRMED    -> COMPLETED     horizon elapsed, MFE_R reached MIN_MFE_R_FOR_COMPLETION at some point (§17)
CONFIRMED    -> EXPIRED       horizon elapsed, MFE_R never reached MIN_MFE_R_FOR_COMPLETION, not invalidated

WEAKENING    -> CONFIRMED     recovery: evidence-quality criteria restored (below)
WEAKENING    -> INVALIDATED   structural invalidation reached
WEAKENING    -> COMPLETED     horizon elapsed, same MIN_MFE_R_FOR_COMPLETION rule as above
WEAKENING    -> EXPIRED       horizon elapsed, MIN_MFE_R_FOR_COMPLETION never reached
```

No other edges are allowed. `EXPIRED` is reachable from `EARLY_SIGNAL` (age
limit) or from `CONFIRMED`/`WEAKENING` (horizon limit without a meaningful
excursion) — both are covered above, resolving
`V2_PRODUCT_CONTRACT.md` §5.1's "(from `EARLY_SIGNAL`) or ... (from
`CONFIRMED`, if applicable)" language precisely.

**`WEAKENING → CONFIRMED` recovery is explicitly allowed** — this resolves
the Product Contract's deferred "whether, and under what conditions, a
`WEAKENING` episode can recover" ([§5.1](#51-state-meanings) there): yes,
it can, whenever the evidence-quality criteria that triggered `WEAKENING`
are no longer met and the episode has not since invalidated or completed.

**Completion vs. expiry, precisely (V2-v0):**

```text
MIN_MFE_R_FOR_COMPLETION = 0.5   # R-multiple, see §17
```

At horizon end (from `CONFIRMED` or `WEAKENING`), if the episode's `MFE_R`
(peak favorable excursion in R, [§17](#17-r-based-metrics)) reached `>=
0.5` at any point during its life, it transitions to `COMPLETED` — "the
scenario played out and moved meaningfully in the intended direction at
some point," even if it later gave the move back. If `MFE_R` never reached
`0.5`, it transitions to `EXPIRED` — "the trade never got going before
time ran out." This is a deterministic, evaluation-relevant distinction,
not a cosmetic label choice.

### 13.2a `WEAKENING` and recovery criteria (V2-v0)

`CONFIRMED → WEAKENING` when, on a closed 5m bucket after confirmation,
`price_direction_agreement(5m)` opposes the episode's direction (i.e. more
than half of contributing exchanges now disagree) for `WEAKEN_BUCKETS = 2`
consecutive closed 5m buckets — an evidence-quality signal, never itself a
price-level check (that's invalidation's job). `WEAKENING → CONFIRMED`
recovery requires the opposing-agreement condition to no longer hold for
`RECOVER_BUCKETS = 1` closed 5m bucket.

### 13.3 `REVERSAL_CANDIDATE` mechanics

Resolved per `V2_PRODUCT_CONTRACT.md` §5.3's guidance, modeled exactly as
that section's suggested shape: an event/update on the existing episode,
plus independent creation/qualification of a genuinely separate
opposite-direction episode — not a destructive conversion.

```text
REVERSAL_CANDIDATE event fires exactly when:
    a NEW opposite-direction episode reaches EARLY_SIGNAL (§7, any family)
    while there exists any ACTIVE (non-terminal) same-symbol episode of
    the other direction

effect:
    - the new opposite-direction episode is created and begins its own,
      fully independent lifecycle under this document's normal rules
      (§12, §13) — it is not a special episode type;
    - a REVERSAL_CANDIDATE event is attached to the pre-existing episode's
      history as an informational cross-reference; the pre-existing
      episode's own state is UNCHANGED by this event.
```

**Hard invariant:** `INVALIDATED` alone **never** creates a
`REVERSAL_CANDIDATE` event. The trigger is exclusively "a new opposite
episode independently reached `EARLY_SIGNAL`" — an episode transitioning to
`INVALIDATED` with no independently-qualifying opposite candidate produces
**no** `REVERSAL_CANDIDATE` event, full stop. This directly implements
`V2_PRODUCT_CONTRACT.md` §5.3's "MUST require the opposite direction to
independently satisfy its own scenario-entry requirements."

---

## 14. Candidate expiry and expected horizons

| Setup family | Max candidate age (`EARLY_SIGNAL → CONFIRMED` deadline) | Expected horizon (from `CONFIRMED`) |
|---|---|---|
| `TREND_PULLBACK` | 2h (8 × 15m buckets) | 2h |
| `COMPRESSION_BREAKOUT` | 1h (12 × 5m buckets, trigger→confirm) | 1.5h |
| `CONFIRMED_BREAKOUT` | 40 min (8 × 5m buckets, first→second confirming close) | 2.5h |

All V2-v0, `rules_version`-participating, chosen so every family's total
candidate-to-resolution lifecycle fits within the Product Contract's
"approximately 1–4 hour trades" target
(`V2_PRODUCT_CONTRACT.md` §1). No claim of optimality.

**Horizon begins at the `CONFIRMED` transition, uniformly across all three
families** — not at first detection, not at entry-feasible time. Rationale:
`CONFIRMED` is when an episode becomes actionable/entry-feasibility-evaluated
([§15](#15-entry-feasibility-evaluation)), which is the economically
meaningful start point for "how long until this plays out" — measuring
from first detection would conflate setup-formation time (which varies a
lot per family, [§7](#7-setup-detectors)) with the trade's own expected
duration.

`COMPLETED` vs. `EXPIRED` at horizon end are defined in
[§13.2](#132-allowed-transitions) (`MIN_MFE_R_FOR_COMPLETION`).

---

## 15. Entry-feasibility evaluation

Two genuinely distinct concepts:

1. **Analytical setup validity** — the detector's own gates in
   [§7](#7-setup-detectors) are satisfied. This alone does not mean the
   trade is still enterable.
2. **Real-world actionability** — whether, after a realistic reaction
   delay, price is still within reach of the published entry zone.

**V2-v0 delay assumption:**

```text
ASSUMED_NOTIFICATION_DELAY_S = 90   # seconds
```

This is an **evaluation assumption used to grade V2's own output**, not a
promise that any given user reacts within 90 seconds — stated explicitly,
per the Product Contract's requirement that this number not be read as a
guarantee. It is deliberately conservative (fast enough to be meaningful,
slow enough not to flatter V2 by assuming instant reaction).

```text
notification_reference_time = T of the decision boundary at which CONFIRMED was reached
assumed_entry_time = notification_reference_time + ASSUMED_NOTIFICATION_DELAY_S
```

**Price sampled after the delay:** the reference exchange's 1-minute kline
close of the bar whose close timestamp is the smallest one `>=
assumed_entry_time` — the same "sample at a well-defined discrete close
instant" convention V1's outcome evaluator already uses
(`analytics/forecasting/outcomes.py`: `target_bar_ts = end − 1m`, evaluated
at that bar's close).

**Feasibility (V2-v0):**

```text
OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(setup_timeframe, B, reference_price)

LONG:  feasible iff sampled_price <= entry_zone_upper + OVERSHOOT_TOLERANCE
                     AND invalidation_price not yet breached (reference exchange,
                         closed 5m bucket) as of assumed_entry_time
SHORT: feasible iff sampled_price >= entry_zone_lower - OVERSHOOT_TOLERANCE
                     AND invalidation_price not yet breached as of assumed_entry_time
```

A price that moved *further into* the zone (a deeper LONG pullback price,
a lower SHORT breakout retrace) is **more** favorable, never infeasible —
only price moving *away* from the zone by more than the tolerance is
"late." A price outside the tolerance is marked **infeasible/late**
regardless of how strong the analytical setup was — an obviously missed
move MUST NOT be counted as a successful actionable V2 call.

**If invalidation was already reached before the assumed entry time:** the
episode is marked infeasible for this purpose (no actionable notification
is generated for it) and still transitions to `INVALIDATED` through the
normal lifecycle rules ([§13](#13-lifecycle-transition-semantics)) — it is
retained for research ([§17](#17-outcome--evaluation-model)) but never
published as an actionable trade idea.

A late/infeasible `CONFIRMED` episode is **stored and evaluated exactly
like any other** — it simply never produces an actionable notification
([§16](#16-notification-materiality--anti-spam-thresholds)).

---

## 16. Notification materiality / anti-spam thresholds

| Event | Material? | V2-v0 condition |
|---|---|---|
| First `EARLY_SIGNAL` | Only if feasible at detection (rare — feasibility is mainly a `CONFIRMED`-time concept, but a pathologically late `EARLY_SIGNAL` is still suppressed) | — |
| `CONFIRMED` | **Always material, if feasible** ([§15](#15-entry-feasibility-evaluation)) | — |
| Confidence-only update | Material iff `|Δ model_confidence| >= 0.15` (V2-v0) on the unit-interval scale | — |
| Zone update | Material only pre-`CONFIRMED` (zone is frozen after, [§9](#9-entry-zone-semantics)) and only if the zone bound moves by more than `0.5 * protection_buffer` (V2-v0) | — |
| `WEAKENING` | Always material (state change) | — |
| Recovery (`WEAKENING → CONFIRMED`) | Always material (state change) | — |
| `INVALIDATED` | Always material (state change) | — |
| `REVERSAL_CANDIDATE` | Always material (state change, [§13.3](#133-reversal_candidate-mechanics)) | — |
| Routine 5m re-evaluation with no state change and `|Δconfidence| < 0.15` | **Never material** | — |

**Cooldown / duplicate suppression:** a material non-state-change update
(confidence-only or zone-only) is additionally suppressed if the episode's
last notification was fewer than `MATERIAL_COOLDOWN = 3` closed 5m buckets
ago (15 min, V2-v0) — **except** a state-change transition (`CONFIRMED`,
`WEAKENING`, recovery, `INVALIDATED`, `REVERSAL_CANDIDATE`), which
**always overrides cooldown** and is never suppressed.

Routine 5m re-evaluation that changes no state and moves confidence by
less than the threshold is, by construction, never notification-worthy —
this is the anti-spam invariant `V2_PRODUCT_CONTRACT.md` §3/§9 requires.

---

## 17. Outcome / evaluation model

Unlike V1's independent-per-bucket outcome record
(`analytics/forecasting/outcomes.py`), V2's outcome record is
**per-episode**, matching the episode model. Conceptual fields (Markdown
illustration only, [§0.1](#01-what-this-document-is-not)):

```text
episode outcome record (logical shape, not a schema):
  detection_timestamp            # first EARLY_SIGNAL decision boundary T
  notification_timestamp         # decision boundary T of CONFIRMED, if reached
  assumed_feasible_entry_timestamp   # §15
  feasible_entry_price_or_status     # actual sampled price + feasible/late verdict
  invalidation_reached_at        # decision boundary T, or null
  horizon_completion_status      # COMPLETED | EXPIRED, per §13.2
  directional_return_pct         # same sign convention as V1's outcomes.py
  mfe_pct / mae_pct              # same convention as V1's outcomes.py
  mfe_r / mae_r                  # §18 below
  terminal_return_r              # §18
  cost_adjusted_return_r         # §19
  lateness_status                # ACTIONABLE | LATE | INVALIDATED_BEFORE_ENTRY
  setup_family
  episode_state_history          # ordered list of (T, from_state, to_state, reason)
  rules_version                  # §3
  calculation_version             # §3
  data_coverage_at_confirmation   # min_coverage_ratio, consensus_confidence at CONFIRMED
```

**No take-profit target is required** (per `V2_PRODUCT_CONTRACT.md` §6):
outcome is measured purely via horizon-based MFE/MAE/terminal-return and
their R-normalized forms ([§18](#18-r-based-metrics)) — an episode that
never reaches a fixed target can still be a fully evaluated, meaningful
outcome (`COMPLETED` requires only `MIN_MFE_R_FOR_COMPLETION`, not a hit
target).

`directional_return_pct` / `mfe_pct` / `mae_pct` reuse V1's exact
direction-aware sign convention (`outcomes.py`: for `LONG`,
`mfe = max(0, peak_return)`, `mae = min(0, trough_return)`; mirrored for
`SHORT`) — the same formula, applied over the episode's own monitored
window instead of a fixed 15m/1h/4h horizon-from-prediction window.

---

## 18. R-based metrics

```text
R = |feasible_entry_price - invalidation_price|

MIN_VALID_R = 3 * tick_size   # V2-v0 — reused from the same tick-buffer
                                # reasoning as protection_buffer (§7)

if R is zero, non-finite, or R < MIN_VALID_R:
    FAIL CLOSED: the episode cannot reach CONFIRMED (this is checked at
    confirmation time, not only at evaluation time — a degenerate risk
    distance means the structural premise itself is not well-formed)
```

Given a valid `R` and a feasible entry (per [§15](#15-entry-feasibility-evaluation)):

```text
MFE_R  = mfe_pct_over_episode_life  * feasible_entry_price / 100 / R
MAE_R  = mae_pct_over_episode_life  * feasible_entry_price / 100 / R
terminal_return_R = directional_return_pct * feasible_entry_price / 100 / R
```

(the `* feasible_entry_price / 100` term converts a percentage return back
to an absolute price distance before dividing by the absolute distance
`R`, so `MFE_R`/`MAE_R`/`terminal_return_R` are dimensionless R-multiples).
Raw percentage metrics ([§17](#17-outcome--evaluation-model)) remain
available alongside the R-normalized ones — this section adds risk
normalization, it does not replace the percentage figures.

**Behavior when `R` is invalid:** the episode fails closed at
confirmation time (above); it never reaches an evaluable `CONFIRMED` state
that would need an `R`-based metric. There is no divide-by-zero case to
handle at evaluation time because it cannot occur — invalid `R` is
rejected earlier in the lifecycle, not caught after the fact.

---

## 19. Execution-cost assumptions

```text
ASSUMED_ROUND_TRIP_COST_BPS = 10   # V2-v0
```

An explicit, conservative **evaluation planning assumption** bundling an
estimated taker-fee-equivalent round trip plus slippage — **not** a
measured statistic, **not** a claim about any specific account's actual fee
tier, and **not** read from live account data (V2 core has no dependency
on live fee information, per `V2_PRODUCT_CONTRACT.md` scope). It is
versioned (`rules_version`-participating) so a future, more accurate cost
profile can be substituted without silently rewriting historical results
under the old assumption's identity.

```text
cost_adjusted_return_R = terminal_return_R - (ASSUMED_ROUND_TRIP_COST_BPS / 10000 * feasible_entry_price) / R
```

Evaluation infrastructure **MUST** support recomputing outcomes under an
alternative, separately versioned cost profile later without overwriting
results computed under this one — same insert-once-and-reprovenance
pattern as [§2.1](#21-replay-behavior-for-late-arriving--corrected-data).

---

## 20. Replay / backtest correctness

- **Same pure decision functions as live, wherever possible.** Every
  formula in this document ([§1](#1-the-v2-decision-clock) through
  [§9](#9-entry-zone-semantics)) is specified as a pure function of closed
  data — the same code path MUST serve live and replay.
- **Same versioned rules.** A replay run MUST pin an exact
  `(rules_version, calculation_version)` pair and MUST NOT silently mix
  versions mid-run.
- **Same closed-bucket semantics.** Replay uses the identical
  `selected_bucket(timeframe, T)` pure function ([§1.3](#13-layer-2--selected_buckettimeframe-t-pure))
  — a replayed `T` produces the same bucket selection as it would have
  live, by construction (the function reads no clock).
- **No future knowledge; chronological processing.** A replay run
  processes decision boundaries in ascending `T` order, exactly as the
  existing Stage 2 bootstrap already requires
  ("[computes] in ascending bucket order... so no step ever sees a future
  value," `STAGE2_SPEC.md` §8.2) — V2 reuses this ordering discipline.
- **No retroactive episode merging based on future information.** Episode
  identity ([§12](#12-episode-identity-and-deduplication)) and lifecycle
  transitions ([§13](#13-lifecycle-transition-semantics)) are evaluated
  strictly in `T` order; a later boundary's data MUST NOT cause an earlier
  boundary's episode-identity or transition decision to be revised.
- **State carried forward only from information available at that
  historical point.** An episode's in-progress state at decision boundary
  `T` is a pure function of the ordered sequence of decisions up to and
  including `T` — never of any `T' > T`.
- **Deterministic results from identical inputs/version.** A backtest run
  with the same `(rules_version, calculation_version)` over the same
  historical range MUST produce identical episodes, transitions, and
  outcome metrics on every run — no randomness, no wall-clock dependence
  (consistent with every pure core already in this codebase:
  `compute_forecast_decision`, the Consensus core, the Percentile core all
  share this property, and V2's core MUST too).
- **A backtest-specific implementation MUST NOT use a more favorable data
  path than live.** Concretely: replay MUST use the same coverage/gate
  thresholds ([§6](#6-cross-exchange-correctness)), the same fail-closed
  rules ([§21](#21-failure--fail-closed-rules)), and MUST NOT read a
  bucket that a live run at the equivalent wall-clock time would not yet
  have had access to (percentile windows, structural lookbacks, and
  regime/bias windows already enforce this by construction, since they are
  defined purely in terms of `bucket_ts <= B`).

**Handling of specific replay conditions:**

| Condition | Required behavior |
|---|---|
| Missing buckets | A missing `consensus_feature_vectors` row for a needed `bucket_ts` is treated as `INSUFFICIENT_DATA`/`UNAVAILABLE` exactly as it would be live ([§6.3](#63-coverage--degraded-behavior--fail-closed)) — never skipped-and-silently-interpolated. |
| Partial consensus | `is_partial_consensus=True` rows are used exactly as live would (the coverage/confidence gates already handle degraded consensus, [§6.3](#63-coverage--degraded-behavior--fail-closed)) — replay does not get a separate, looser partial-consensus rule. |
| Late-arriving data | Reuses the frozen Stage 2 correction model ([§2.1](#21-replay-behavior-for-late-arriving--corrected-data)) — a replay run reads whatever `consensus_feature_vectors` state exists **at replay time**, which may already reflect corrections; this is why replay results are explicitly labeled "corrected/recomputed research truth," never conflated with the original live decision truth. |
| Unavailable percentiles early in history | `normalized_evidence`/`compression_score` correctly return `UNAVAILABLE` for early-history buckets below `MIN_PCTL_TIER` — this is not a replay-specific rule, it is the same rule live decisions already follow ([§5.2](#52-missing-percentile-handling--never-none--0)). |
| Warm-up period | Reuses the frozen Stage 2 warm-up policy (`config/stage2.yaml`: `warmup.minimum_calendar_days=7`, `preferred_calendar_days=30`) — no V2-specific warm-up rule is invented; the percentile confidence-tier gate already enforces the practical effect (nothing scores above `"none"`/`"low"` until enough calendar history exists). |

---

## 21. Failure / fail-closed rules

V2 **MUST** refuse to emit an actionable scenario in each of the following
cases, and **MUST** distinguish the four listed outcome categories rather
than collapsing them into one:

| Category | Meaning | Examples |
|---|---|---|
| **Unavailable** | The required input simply does not exist / cannot be computed right now. | Required timeframe's `ConsensusFeatureVector` missing for the selected bucket; a percentile below `MIN_PCTL_TIER`; missing structural level history (fewer than the lookback requires). |
| **Neutral** | The input exists and is valid, but genuinely indicates "no lean" — a real measured value, not an absence. | `NEUTRAL_NOT_ESTABLISHED` 1h bias; `bias_strength = 0.0` in confidence scoring. |
| **Rejected** | The input exists, but a hard gate explicitly disqualifies it. | Insufficient cross-exchange coverage (`< 2/3`); malformed/non-finite numeric values; `calculation_version`/`rules_version` mismatch across inputs that must agree; contradictory context violating a setup's hard gate (e.g. `TREND_PULLBACK` attempted against a `NON_DIRECTIONAL` regime); `R < MIN_VALID_R` ([§18](#18-r-based-metrics)); an already-breached invalidation level discovered before confirmation. |
| **Late / non-actionable** | The input and gates are all otherwise satisfied, but real-world entry feasibility fails. | [§15](#15-entry-feasibility-evaluation)'s infeasible/late verdict — analytically valid, still stored for research, never published as actionable. |

Every failure additionally requires: no future/leaking data (enforced
structurally by [§1](#1-the-v2-decision-clock)/[§2](#2-no-lookahead-semantics-per-input-family));
malformed timestamps (not UTC, not aligned to the relevant grid, naive
datetimes) are rejected the same way the existing `_validate_scope_identity`
/ `_validate_bucket_alignment` validators already reject them for V1 — V2
reuses the identical validation posture (fail loudly, never coerce).

---

## 22. No silent fallback rule

Silence is better than fabricated certainty, across this entire document.
None of the following are permitted anywhere in V2, and any exception to
this list that a future implementation genuinely needs MUST be a new,
explicit, deterministic, provenance-visible, version-participating rule —
never an ad hoc runtime decision:

- missing → zero (explicitly forbidden throughout — [§5.2](#52-missing-percentile-handling--never-none--0), [§8](#8-model-confidence-semantics), [§17](#17-outcome--evaluation-model));
- missing exchange → treat remaining exchange(s) as full consensus (forbidden by the reused `minimum_exchange_coverage` gate, [§6.3](#63-coverage--degraded-behavior--fail-closed));
- missing 4h → infer from 1h (forbidden — [§4.2](#42-4h-regime) fails closed to `INSUFFICIENT_DATA` instead);
- missing 15m → infer from 5m (forbidden — no such substitution exists anywhere in [§7](#7-setup-detectors));
- missing structural level → synthesize one from current price (forbidden — [§18](#18-r-based-metrics)'s `R < MIN_VALID_R` fail-closed rule exists specifically to prevent this);
- unavailable percentile → assume median (forbidden — [§5.2](#52-missing-percentile-handling--never-none--0)'s `UNAVAILABLE` sentinel exists specifically to prevent this);
- unavailable canonical reference price → silently switch exchanges (forbidden — [§11](#11-reference-price-semantics) fails closed instead).

---

## 23. Configurability vs. frozen behavior

**Frozen semantics** (implementation cannot reinterpret without a version
change to this document itself): the decision clock ([§1](#1-the-v2-decision-clock)),
no-lookahead rules ([§2](#2-no-lookahead-semantics-per-input-family)), the
model/version identity model ([§3](#3-v2-modelversion-identity)), the
normalized-evidence formula ([§4.1](#41-normalized-evidence-primitive-used-throughout-47)),
the three detectors' qualitative structure ([§7](#7-setup-detectors)), the
confidence-formula shape and renormalization rule ([§8](#8-model-confidence-semantics)),
episode identity and precedence rules ([§12](#12-episode-identity-and-deduplication),
[§7.4](#74-setup-family-precedence-and-deduplication)), the lifecycle
transition graph and precedence ([§13](#13-lifecycle-transition-semantics)),
the fail-closed categories ([§21](#21-failure--fail-closed-rules)), and the
no-silent-fallback rule ([§22](#22-no-silent-fallback-rule)).

**Versioned parameters** (may live in config, but their V2-v0 *values* are
frozen by this document and every one of them participates in
`rules_version` identity — a config change to any of them is a
`rules_version` bump, never a silent behavior change under an unchanged
version): every numeric constant introduced in this document —
`REGIME_TREND_THRESHOLD`, `BIAS_THRESHOLD`, `REGIME_OI_VETO`,
`COMPRESSION_THRESHOLD`, `PULLBACK_MIN_MULT`/`PULLBACK_MAX_MULT`,
`BUFFER_MULTIPLIER`, all per-family age/horizon numbers ([§14](#14-candidate-expiry-and-expected-horizons)),
`ASSUMED_NOTIFICATION_DELAY_S`, `OVERSHOOT_TOLERANCE`'s multiplier,
`ASSUMED_ROUND_TRIP_COST_BPS`, `MIN_VALID_R`'s tick multiplier, confidence
weights and the partial-evidence cap, cooldown lengths, and the
materiality thresholds in [§16](#16-notification-materiality--anti-spam-thresholds).

**Config is not a loophole.** Because every versioned parameter above
participates in `rules_version` ([§3](#3-v2-modelversion-identity)),
changing one of them without bumping `rules_version` is itself a
correctness bug against this document — config can move the *value*, never
detach the value from its version identity.

---

## 24. Traceability matrix — `V2_PRODUCT_CONTRACT.md` §12

| Deferred item | Disposition | Where |
|---|---|---|
| Exact cross-timeframe timestamp alignment | **FROZEN HERE** | §1 |
| No-lookahead mechanics | **FROZEN HERE** | §2 |
| Exact closed-bucket selection rules | **FROZEN HERE** | §1.3 |
| Setup formulas (`TREND_PULLBACK`, `COMPRESSION_BREAKOUT`, `CONFIRMED_BREAKOUT`) | **FROZEN HERE** | §7 |
| Scoring formulas | **FROZEN HERE** | §4, §8 |
| Thresholds | **FROZEN HERE** | throughout, indexed in §23 |
| Percentile cutoffs | **FROZEN HERE** | §4.1, §5 |
| Confidence weighting | **FROZEN HERE** | §8 |
| Entry-zone calculation | **FROZEN HERE** | §7 (per family), §9 |
| Invalidation calculation | **FROZEN HERE** | §7 (per family), §10 |
| Entry-feasibility numerical tolerance | **FROZEN HERE** | §15 |
| Assumed human/notification delay | **FROZEN HERE** | §15 |
| Episode persistence identity / database key | **FROZEN HERE (logical identity only)** — the *logical* key (§12) is decided; the *physical* database key/schema remains implementation-level by this PR's own scope prohibition (§0.1), not because it is still undecided. | §12 |
| Exact state transition thresholds | **FROZEN HERE** | §13 |
| Cooldowns | **FROZEN HERE** | §12, §16 |
| Material-update thresholds | **FROZEN HERE** | §16 |
| Replay/backtest methodology | **FROZEN HERE** | §20 |
| Evaluation sample-size requirements | **FROZEN HERE** | §26 |
| Promotion thresholds | **FROZEN HERE** | §28 |
| Acceptance metrics | **FROZEN HERE** | §27 |
| Calibration methodology | **EXPLICITLY OUT OF INITIAL V2** — see §25's calibration statement. | §25 |

---

## 25. Calibration statement

Per `V2_PRODUCT_CONTRACT.md` §7/§H, initial V2 **MUST NOT** display a
calibrated historical success probability. This document does not change
that. Explicitly, for the initial V2:

- Initial V2 **has no calibrated win probability** anywhere in its output.
- `model_confidence` ([§8](#8-model-confidence-semantics)) remains
  **non-probabilistic** — an evidence/data-quality strength score on a
  fixed `[0,1]` scale, never a probability of profit, never passed through
  a sigmoid/logistic transform, exactly matching V1's existing posture.
- Calibration **cannot be added without a future contract/version change**
  — it requires both enough comparable completed episodes and an
  explicitly frozen calibration methodology, per
  `V2_PRODUCT_CONTRACT.md` §7. Neither exists today; this document does
  not invent one. This is the one item in [§24](#24-traceability-matrix--v2_product_contractmd-12)
  that remains genuinely deferred beyond initial V2, and it remains
  deferred because no completed-episode sample can exist before V2 is
  implemented and run — it is not deferred for difficulty, it is deferred
  because the precondition data does not exist yet.

---

## 26. Acceptance sample requirements

V2 is **not** promoted merely because implementation is complete. V2-v0
minimum evaluation sample (engineering acceptance thresholds, explicitly
**not** claims of statistical proof):

```text
MIN_COMPLETED_EPISODES_AGGREGATE = 100
MIN_CALENDAR_SPAN_DAYS           = 60
MIN_COMPLETED_EPISODES_PER_FAMILY = 30
```

"Completed" here means an episode that reached a terminal state
(`COMPLETED`, `EXPIRED`, or `INVALIDATED` — all three are evaluable
outcomes, [§17](#17-outcome--evaluation-model)), not only `COMPLETED`
episodes specifically.

**A setup family below `MIN_COMPLETED_EPISODES_PER_FAMILY`** is not
individually validated and **MUST NOT** be forced into user-facing
promotion merely because the aggregate V2 sample passes — it remains at
most `SHADOW_ELIGIBLE` ([§28.2](#282-promotion-levels)) for that family
specifically, however the other two families and the aggregate perform. A
setup family that is genuinely too rare to reach its minimum within a
reasonable evaluation period remains permanently `SHADOW_ELIGIBLE`
(research/comparison only) until either more data accumulates or a future
contract revision explicitly lowers its bar with a stated reason — it is
never silently exempted from the requirement.

---

## 27. Acceptance metric hierarchy

Preserving the roadmap's priority order (`docs/FORECASTING_ROADMAP.md` §H)
exactly, with concrete V2-v0 metrics/thresholds per priority:

| Priority | Roadmap priority | Metric | V2-v0 threshold |
|---|---|---|---|
| 1 | Entry feasibility after real delay | Actionable-entry feasibility rate (`ACTIONABLE / CONFIRMED`, [§15](#15-entry-feasibility-evaluation)) | `>= 0.60` |
| 1b | (complement) | Missed/late rate | `<= 0.40` |
| 2 | Low MAE | Median `MAE_R` | `<= 1.0R` |
| 2b | (tail) | 90th-percentile `MAE_R` | `<= 2.0R` |
| 3 | Sufficient MFE | Median `MFE_R` | `>= 1.0R` |
| 3b | (breadth) | Proportion of episodes reaching `MFE_R >= 0.5` before invalidation | `>= 0.50` |
| 4 | Performance after costs/delay | Mean `cost_adjusted_return_R` ([§19](#19-execution-cost-assumptions)) | `> 0.10R` |
| 5 | Ordinary directional accuracy | `CONFIRMED` episodes where `terminal_return_R > 0` | Reported only, **no threshold** — explicitly not a gate, per roadmap §H ("ordinary accuracy alone is not the promotion criterion"). |

All V2-v0, `rules_version`-participating, explicitly not empirically
proven. **Win rate is never the sole promotion criterion** — priority 5
above carries no gate at all, by design.

---

## 28. Promotion criteria and levels

### 28.1 Hard fail conditions

Any of the following alone fails promotion, regardless of any other metric:

- Sample requirements ([§26](#26-acceptance-sample-requirements)) not met (aggregate or per-family, as applicable).
- Mean `cost_adjusted_return_R <= 0` — a non-positive cost-adjusted expectancy is an unconditional fail, independent of accuracy or MFE.
- Median `MAE_R > 1.0` — exceeding the risk-control threshold.
- Actionable-entry feasibility rate `< 0.60` — a setup that's "usually right" but consistently too late to act on does not qualify (directly implementing the roadmap's stated rejection of that failure mode).

### 28.2 Promotion levels

```text
RESEARCH_ONLY        -> SHADOW_ELIGIBLE       -> USER_FACING_ELIGIBLE       (-> V1_RETIRABLE, separate)
```

| Level | Requirement | What it authorizes |
|---|---|---|
| `RESEARCH_ONLY` | Default — code exists and produces persisted episodes/outcomes. No gating. | Internal analysis only. No shadow run, no notifications. |
| `SHADOW_ELIGIBLE` | Aggregate sample minimums met ([§26](#26-acceptance-sample-requirements)). | Parallel shadow evaluation (`docs/FORECASTING_ROADMAP.md` §I, stage 10) — internally computed, not user-visible. This is precisely how the metric hierarchy in [§27](#27-acceptance-metric-hierarchy) gets evaluated; passing it is not a precondition of reaching this level. |
| `USER_FACING_ELIGIBLE` | Full acceptance metric hierarchy ([§27](#27-acceptance-metric-hierarchy)) passes at the **aggregate** level, **assessed independently per setup family** — a family that individually fails stays `SHADOW_ELIGIBLE` even if the aggregate and the other families pass. | User-facing V2 notifications for the qualifying family/families only. |
| `V1_RETIRABLE` | A **separate, explicit decision** comparing V2 against V1 on overlapping calendar periods, using only metrics genuinely comparable between the two ([§28.3](#283-v1-comparison)). Not automatic on reaching `USER_FACING_ELIGIBLE`. | V1 Telegram delivery may be paused/retired — requires its own explicit PR/deployment action, exactly as `docs/FORECASTING_ROADMAP.md` §C already states. |

No level above is reached automatically by finishing implementation. **No
production/notification action is authorized by this document** — every
transition above requires a subsequent, explicit human decision.

### 28.3 V1 comparison

Comparison against V1 for `V1_RETIRABLE` **MUST** use only **formally
persisted** V1 data (`forecast_predictions` / `forecast_outcomes`), never
the informal "~30%" operator observation
(`docs/FORECASTING_ROADMAP.md` §B, explicitly labeled "not a validated
statistic" there and not treated as one here). Where V1's evaluation
window/shape (single-bucket, 15m/1h/4h fixed horizons,
`analytics/forecasting/outcomes.py`) and V2's episode-shaped evaluation
([§17](#17-outcome--evaluation-model)) are not directly comparable, the
comparison **MUST** be restricted to genuinely **shared** metrics
(directional accuracy over an overlapping calendar period is the clearest
shared metric; R-normalized MFE/MAE are V2-only concepts with no V1
equivalent and MUST NOT be forced into a fabricated side-by-side). No
formal V1 baseline number is asserted anywhere in this document beyond
what the `forecast_outcomes` table would need to be queried to produce at
comparison time.

---

## 29. Test vectors

Normative worked examples, intended to be copied directly into future
unit tests.

### 29.1 Alignment vectors

See [§1.4](#14-worked-alignment-vectors) — the four-row table plus the
grace-boundary table are the alignment vectors.

### 29.2 No-lookahead vector

See [§1.5](#15-no-lookahead-vector).

### 29.3 Missing-data vector

```text
Given: consensus_feature_vectors row at (BTCUSDT, perp, 4h, B, calc_v1)
       with price_move_pct_median = NULL (family below minimum_exchange_coverage)

normalized_evidence(price_move_pct_median, consensus, 4h, 30d, B) = UNAVAILABLE
    (NOT 0.0 — a NULL feature value is an absent observation, per
    STAGE2_SPEC.md §12.5, "a NULL feature value is an absent observation,
    never numeric zero")

4h regime at B = INSUFFICIENT_DATA   (§4.2 step 1)

Contrast — given instead price_move_pct_median = 0.0 exactly (a genuine,
measured flat 4h bucket, all three exchanges agreeing on zero net move):

percentile_rank computed normally against history (a real value, ranked
    like any other); ternary sign = 0 (flat); if this bucket's percentile
    rank happens to sit near the middle of its own history,
    normalized_evidence ≈ 0.0 too — but this is a COMPUTED near-zero
    result from a real value, not a sentinel standing in for missing data.
    The two cases are NEVER the same code path.
```

### 29.4 Setup vectors

**Valid `TREND_PULLBACK` (LONG).** 4h regime `BULLISH_TRENDING`
(`price_evi=0.55`, `agreement=0.80`, `oi_evi=0.20` — no veto). 1h bias
`BULLISH` (`bias_evi=0.30`, `agreement=0.75`). 15m: `trend_leg_extreme
(high) = 65,000`, current `close = 64,350`,
`retracement_pct = (65000-64350)/65000*100 = 1.0%`;
`RANGE_PROXY_pct(15m,14,B) = 0.4%`; valid range is `[0.5*0.4, 3.0*0.4] =
[0.20%, 1.20%]` — `1.0%` is inside → valid pullback. 5m: consensus
`price_move_pct_median` sign `+1`, `price_direction_agreement = 0.75 >=
2/3` on one closed bucket → confirmed. `pullback_extreme_low = 64,300`,
`protection_buffer(15m,B,64350) ≈ max(3*tick, 64350*0.4%*0.5) ≈ 128.7` (using
`tick_size=0.1` for illustration) → `invalidation_price ≈ 64,171.3`.
`R = |64350 - 64171.3| ≈ 178.7 > MIN_VALID_R` → valid. Entry zone `[64,300,
64,350]`. → `TREND_PULLBACK`, `LONG`, `CONFIRMED`.

**Rejected `TREND_PULLBACK`.** Same 4h/1h context, but
`retracement_pct = 1.8%` against the same `[0.20%,1.20%]` valid range →
exceeds `PULLBACK_MAX_MULT` → classified as trend failure, not a pullback
→ **no candidate formed**.

**Valid `COMPRESSION_BREAKOUT` (SHORT).** `compression_score(15m,30d,B) =
0.82 >= 0.75` for `7 >= COMPRESSION_MIN_DURATION(6)` consecutive 15m
buckets. `range_low = 63,800`. Breakout 5m bucket closes at `63,740 <
63,800`, `price_direction_agreement(5m)=0.80`, `taker_delta_notional_usd_sum`
negative (sell-side, matching SHORT) → confirmed same bucket (single-close
rule). `invalidation_price = 63,800 + protection_buffer(...) ≈ 63,930`.
Entry zone `[63,800 - buffer, 63,800] ≈ [63,670, 63,800]`. →
`COMPRESSION_BREAKOUT`, `SHORT`, `CONFIRMED`.

**Rejected `COMPRESSION_BREAKOUT`.** `compression_score` reaches `0.75`
for only `4 < COMPRESSION_MIN_DURATION(6)` consecutive buckets before
dropping below threshold → compression never qualifies as sustained →
**no candidate formed**, even though a later strong directional 5m move
occurs — a big move alone, without the sustained-compression precondition,
never becomes `COMPRESSION_BREAKOUT`.

**Valid `CONFIRMED_BREAKOUT` (LONG).** `resistance_level = 66,200` (max
high, 48×1h lookback). 5m closes: bucket 1 closes `66,240`, bucket 2 (next)
closes `66,290` — two consecutive confirming closes within
`CONFIRMATION_MAX_AGE(8×5m)` → `CONFIRMED`. `invalidation_price = 66,200 -
protection_buffer(1h,...) ≈ 66,050`. Entry zone `[66,200,
66,200+buffer] ≈ [66,200, 66,350]`. → `CONFIRMED_BREAKOUT`, `LONG`,
`CONFIRMED`.

**Rejected `CONFIRMED_BREAKOUT`.** Bucket 1 closes `66,240` (beyond
level); bucket 2 closes back at `66,150` (below level) — second confirming
close never arrives → candidate rejected, never reaches `CONFIRMED` (and
never reaches `EARLY_SIGNAL`'s age clock either, since it was rejected
during the confirmation window itself, per [§7.3](#73-confirmed_breakout)).

### 29.5 Lifecycle vector

```text
T1: TREND_PULLBACK LONG detected -> EARLY_SIGNAL
T2 (2 closed 5m buckets later): 5m confirmation criteria met -> CONFIRMED
    (entry zone frozen at this point, §9)
T3 (WEAKEN_BUCKETS=2 later): price_direction_agreement(5m) opposes
    direction for 2 consecutive closed 5m buckets -> WEAKENING
T4 (RECOVER_BUCKETS=1 later): opposing-agreement condition no longer holds
    -> CONFIRMED (recovery, §13.2a)
T5 (horizon elapses, 2h after T2 per §14): MFE_R reached 0.7 at some point
    during T2..T5 (>= MIN_MFE_R_FOR_COMPLETION=0.5) -> COMPLETED
```

### 29.6 Reversal vector

```text
Episode E1: COMPRESSION_BREAKOUT LONG, CONFIRMED at T1.
T2: reference exchange 5m close crosses invalidation_price -> E1: INVALIDATED.
    No opposite-direction episode independently qualified at T2.
    => NO REVERSAL_CANDIDATE event. (§13.3 hard invariant)

T5 (separately, hours later): a NEW CONFIRMED_BREAKOUT SHORT candidate
    independently reaches EARLY_SIGNAL, satisfying §7.3's own gates from
    scratch (its own structural level, its own 5m trigger) — unrelated in
    formation to E1's invalidation.
    => a new episode E2 (CONFIRMED_BREAKOUT SHORT) is created under its
       own independent lifecycle, AND a REVERSAL_CANDIDATE event is
       attached to... there is no still-active opposite-direction episode
       at T5 (E1 is already terminal) — per §13.3, the REVERSAL_CANDIDATE
       event requires an ACTIVE opposite episode to exist; since E1 is
       terminal, T5 produces E2 with NO REVERSAL_CANDIDATE annotation.

Contrast: if E1 were still ACTIVE (e.g. WEAKENING, not yet INVALIDATED) at
    the moment E2 independently reaches EARLY_SIGNAL, THEN a
    REVERSAL_CANDIDATE event fires, cross-referencing E1 and E2 — driven
    entirely by E2's independent qualification, never by E1's own state.
```

### 29.7 Entry-feasibility vector

```text
CONFIRMED at T (TREND_PULLBACK LONG), entry_zone = [64,300, 64,350].
ASSUMED_NOTIFICATION_DELAY_S = 90 -> assumed_entry_time = T + 90s.
Sampled reference-exchange 1m close at/after assumed_entry_time: 64,410.
OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(...) ≈ 32.2
entry_zone_upper + OVERSHOOT_TOLERANCE = 64,350 + 32.2 = 64,382.2
64,410 > 64,382.2 -> INFEASIBLE / LATE.

=> The episode is analytically CONFIRMED and structurally sound (never
   invalidated), but is retained for research only (§17) — it MUST NOT
   generate an actionable notification, and MUST NOT count as a
   successful actionable V2 call in acceptance metrics' feasibility rate
   numerator (§27, priority 1).
```

### 29.8 Acceptance vector

```text
Sample: 120 completed CONFIRMED_BREAKOUT episodes over 65 calendar days
        (passes §26: >= 30 per-family, >= 60 days).

Directional accuracy: 68% of episodes have terminal_return_R > 0.
    (Looks strong in isolation.)

But:
  actionable-entry feasibility rate = 0.52   (< 0.60 threshold, §27 priority 1)
  median MAE_R = 1.35                          (> 1.0 threshold, §27 priority 2)
  mean cost_adjusted_return_R = -0.05          (<= 0, §28.1 hard fail)

=> PROMOTION FAILS for CONFIRMED_BREAKOUT despite the eye-catching 68%
   directional accuracy, because priority-1 feasibility, priority-2 MAE,
   and the cost-adjusted-expectancy hard-fail condition all fail. Per §27,
   ordinary accuracy alone was never the promotion criterion — this
   vector exists specifically to make that non-negotiable in a concrete
   case a future test can assert against.
```

---

## Status

- **V2 Product Contract: frozen** (`docs/V2_PRODUCT_CONTRACT.md`).
- **V2 Correctness & Acceptance Contract: frozen** (this document).
- **V2: still not implemented.** No runtime code, schema, or config
  exists for V2. Nothing about V1's running behavior changes as a result
  of this PR.
- **Next planned stage:** Stage 2 — Multi-model Framework
  (`docs/FORECASTING_ROADMAP.md` §I), starting with a small foundation PR
  (see `docs/FORECASTING_ROADMAP.md` §J for the specific next PR). No
  implementation begins as part of this PR.
