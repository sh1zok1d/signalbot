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
a genuinely new derived value is needed (e.g. a rolling range-width proxy,
[§7](#7-setup-detectors); or a higher-timeframe high/low extreme derived
from raw `klines_1m` OHLC rather than a nonexistent
`ExchangeFeatureVector.high`/`.low` field, [§7.0a](#70a-structural-highlow-derivation-amended--corrects-a-nonexistent-field-error)),
this document says so explicitly and defines it as a deterministic function
of already-ingested data, never as a new ingested source. `ExchangeFeatureVector`
itself is audited against `analytics/feature_engine/models.py` directly —
it exposes `price_move_pct`, `range_width_pct`, `close_price`, and the
volume/OI/funding/liquidation/quality fields, and **no** `high`/`low`
fields; every place in this document that needs a timeframe-level extreme
goes through the `HTF_high`/`HTF_low` derivation instead of assuming a
field that does not exist.

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

**Correctness note (amended).** An earlier draft of this primitive defined
`normalized = 2*percentile_rank − 1` and used *that value's sign* as the
evidence's direction. That was mathematically wrong: percentile rank
describes a value's *position inside its historical distribution*, not the
sign of the value itself. A genuinely positive raw move can rank low in its
own history (e.g. `price_move_pct_median = +0.20%` with
`percentile_rank = 0.10`, if history is usually far more strongly
positive than that) and `2*0.10 − 1 = −0.80` would have wrongly reported
that positive move as strongly *bearish* evidence — inverting the raw
metric's actual sign. The corrected primitive below fixes this by treating
direction and relative strength as **two separate questions**: direction
always comes from the raw value's own sign (the same ternary sign already
frozen in `STAGE2_SPEC.md` §11.2 — negative/flat/positive), and percentile
rank is used **only** to ask "how extreme is this same-signed value within
its history," never to flip that sign.

`percentile_snapshots` already carries both the raw value and its rank in
one row (`STAGE2_SPEC.md` §2/§12.9: `value`, `percentile_rank`) — no new
field or second distribution is needed to read both:

```text
normalized_evidence(metric, scope, timeframe, window, B):
    snapshot = percentile_snapshot(scope, metric, timeframe, window, bucket_ts=B)
    if snapshot.value is None or snapshot.percentile_rank is None:
        return UNAVAILABLE                      # never 0.0 — see §5.2
    if snapshot.confidence_tier not in {"building", "mature"}:
        return UNAVAILABLE                      # V2-v0: below "building" is too
                                                  # immature a distribution to score from
    v = snapshot.value                            # the RAW signed metric — sign source
    p = snapshot.percentile_rank                  # 0..1 — magnitude-within-history source only
    if v > 0:
        return max(0.0, 2.0 * p - 1.0)            # >= 0 always: a positive raw value can
                                                    # NEVER produce negative (bearish) evidence
    elif v < 0:
        return -max(0.0, 1.0 - 2.0 * p)           # <= 0 always: a negative raw value can
                                                    # NEVER produce positive (bullish) evidence
    else:
        return 0.0                                 # raw zero: genuine neutral evidence,
                                                     # not a missing-data sentinel
```

The output range is still `[-1, +1]`. **Invariants, by construction:**

```text
v > 0  ⇒  normalized_evidence >= 0     (raw positive value never becomes bearish evidence)
v < 0  ⇒  normalized_evidence <= 0     (raw negative value never becomes bullish evidence)
v == 0 ⇒  normalized_evidence == 0.0   (genuine neutral, matching the frozen ternary "flat" sign)
missing (v or p is None, or tier too low) ⇒ UNAVAILABLE, never 0.0
```

**Why the thresholds elsewhere in this document still read the same way.**
For `v > 0`, `normalized_evidence >= X` holds iff `p >= (1+X)/2` — e.g. for
`X = 0.40`, `p >= 0.70`, i.e. "top 30% of the full historical distribution."
For `v < 0`, `normalized_evidence <= -X` holds iff `p <= (1-X)/2` — e.g.
`p <= 0.30`, "bottom 30%." This is the **same** "top/bottom 30%" reading
every V2-v0 threshold in this document was already described with — the
correction changes *which side of zero the magnitude is measured from* (the
raw value's own side, not an unconditional `2p-1`), not the "how extreme"
interpretation of the threshold numbers themselves. Every threshold
comparison below that reads `|normalized_evidence(...)| >= T` therefore
keeps its originally-stated meaning; see
[§23.1](#231-threshold-re-audit-after-the-percentile-sign-correction)
for the explicit per-threshold re-audit.

For **unsigned** magnitude metrics (currently only
`range_width_pct_median`, used for compression, [§7.2](#72-compression_breakout)),
there is no sign to preserve — the metric is a non-negative range measure,
not a directional one — so the unsigned companion primitive is unaffected
by this correction:

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

**Open interest is not directional (amended).** An earlier draft compared
`sign(oi_evi) != sign(price_evi)`, treating OI as if it had its own
independent bullish/bearish reading. Per `V2_PRODUCT_CONTRACT.md` §10 ("OI,
funding, and liquidations alone MUST NOT independently create a LONG/SHORT
direction") and the actual behavior of `analytics/forecasting/core.py::_oi_score`,
that framing is wrong: OI's real semantic role is **confirmation/opposition
of whatever anchor direction price already established**, not a second
directional vote. V1's exact invariant —

```text
rising OI  (oi_change_pct_median > 0)  confirms the anchor, whichever direction it is
falling OI (oi_change_pct_median < 0)  opposes the anchor, whichever direction it is
```

— means rising OI must be able to confirm **both** a bullish *and* a
bearish price anchor (it is symmetric), and OI alone must never be able to
select LONG vs. SHORT. The corrected formula below expresses OI purely as a
**confirmation/opposition signal relative to the candidate anchor**, never
as a second direction.

**Inputs** (consensus scope, `timeframe=4h`, `window=30d`, at
`B = selected_bucket(4h, T)`):

```text
price_evi      = normalized_evidence(price_move_pct_median, consensus, 4h, 30d, B)
comp           = compression_score(4h, 30d, B)
agreement      = ConsensusFeatureVector.price_direction_agreement   # 0..1, at bucket B
confidence     = ConsensusFeatureVector.consensus_confidence         # 0..100, at bucket B
coverage       = ConsensusFeatureVector.min_coverage_ratio            # 0..1, at bucket B

oi_raw         = ConsensusFeatureVector.oi_change_pct_median          # raw signed %, at bucket B
oi_rank        = percentile_rank(oi_change_pct_median, consensus, 4h, 30d, B)   # 0..1, magnitude only
oi_agreement   = ConsensusFeatureVector.oi_direction_agreement        # 0..1, at bucket B
```

**OI confirmation primitive (re-amended — corrects a percentile-distance
sign error).** A prior draft of this primitive used
`oi_magnitude = 2.0 * abs(oi_rank - 0.5) * oi_agreement` — the *distance of
`oi_rank` from the median*, regardless of which side of the median it fell
on. That repeats, inside the OI formula specifically, the same category of
error [§4.1](#41-normalized-evidence-primitive-used-throughout-47) already
corrected generally: `abs(oi_rank - 0.5)` cannot distinguish "a rising OI
reading that is extreme *because it is unusually large*" from "a rising OI
reading that is extreme *because it is unusually small*" — both sit equally
far from `0.5`. Concretely, `oi_raw = +0.10%` (rising, but weak — a small
positive move) with `oi_rank = 0.10` (this bucket's OI change ranks in the
bottom decile of its own history) produced
`oi_magnitude = 2*|0.10-0.5| = 0.80` — reporting a *weak* rising-OI
observation as **strong** confirmation, simply because its rank happened to
fall on the low side of the median rather than the high side.

The fix reuses [§4.1](#41-normalized-evidence-primitive-used-throughout-47)'s
already-frozen shape directly: direction comes from `oi_raw`'s own sign
only (never from rank), and `oi_rank` is read as a **one-sided tail
distance in the direction consistent with that sign** — the upper tail for
a positive raw value, the lower tail for a negative one — never as an
undirected distance from `0.5`:

```text
oi_confirmation(B):
    if oi_raw is None or oi_rank is None or oi_agreement is None
       or the oi_rank snapshot's confidence_tier is below "building":
        return UNAVAILABLE                       # never 0.0
    if oi_raw > 0:
        oi_strength = max(0.0, 2.0 * oi_rank - 1.0)      # 0..1; grows toward 1 ONLY as
                                                            # oi_rank approaches the UPPER tail
        return +oi_strength * oi_agreement    # rising OI: CONFIRMS the anchor, whichever direction it is
    elif oi_raw < 0:
        oi_strength = max(0.0, 1.0 - 2.0 * oi_rank)      # 0..1; grows toward 1 ONLY as
                                                            # oi_rank approaches the LOWER tail
        return -oi_strength * oi_agreement    # falling OI: OPPOSES the anchor, whichever direction it is
    else:
        return 0.0               # flat OI: neither confirms nor opposes
```

`oi_confirmation` is **not** a directional evidence value like `price_evi` —
it never appears on its own as "bullish" or "bearish"; it only ever
modulates a price-established candidate direction, and it is symmetric by
construction (rising OI always confirms, falling OI always opposes,
regardless of which direction the price anchor points). By construction
this also preserves every invariant the prior formula was already required
to satisfy — **and now additionally guarantees**:

```text
positive OI + upper-tail rank (oi_rank -> 1)   =>  oi_strength -> 1  =>  strong confirmation
positive OI + lower-half rank (oi_rank <= 0.5) =>  oi_strength == 0  =>  weak/zero confirmation
negative OI + lower-tail rank (oi_rank -> 0)   =>  oi_strength -> 1  =>  strong opposition
negative OI + upper-half rank (oi_rank >= 0.5) =>  oi_strength == 0  =>  weak/zero opposition
rising OI  (oi_raw > 0)  =>  oi_confirmation >= 0   (rising OI can never oppose)
falling OI (oi_raw < 0)  =>  oi_confirmation <= 0   (falling OI can never confirm)
oi_raw == 0               =>  oi_confirmation == 0.0
OI's sign never depends on price_evi, and OI never selects LONG vs. SHORT
  — see the surrounding formula in §4.2/§4.3, which use oi_confirmation only
  as a confirm/veto modulator on a price-established candidate direction.
```

**V2-v0 parameters:**

| Name | Value | Reuse / rationale |
|---|---|---|
| `REGIME_MIN_CONFIDENCE` | `50.0` | Reused verbatim from V1's `minimum_consensus_confidence` (`DEFAULT_FORECAST_RULES`) — same scale, same gating role. |
| `REGIME_MIN_COVERAGE` | `2/3` | Reused verbatim from V1's `minimum_coverage_ratio`. |
| `REGIME_TREND_THRESHOLD` | `0.40` | New V2-v0 hypothesis: `|price_evi| >= 0.40` means the 4h move sits in roughly the top/bottom 30% of its own 30d history — see [§23.1](#231-threshold-re-audit-after-the-percentile-sign-correction) for why this reading still holds after the percentile-sign correction. |
| `REGIME_MIN_AGREEMENT` | `2/3 ≈ 0.667` | Reused ratio, matching the existing `minimum_exchange_coverage=2`-of-3 consensus floor (`STAGE2_SPEC.md` §11.1) expressed as an agreement ratio, so the regime gate never requires *more* cross-exchange agreement than the consensus core already treats as a valid family. |
| `REGIME_OI_VETO` | `−0.40` | New V2-v0 hypothesis: OI **opposing** the candidate anchor (falling OI, `oi_confirmation <= −0.40`) vetoes a trend call — mirrors V1's `_oi_score` ("falling OI opposes... weakens... either directional move"). Rising OI (`oi_confirmation > 0`) can **never** trigger this veto, by construction — it only ever confirms. |
| `REGIME_COMPRESSION` | `0.75` | New V2-v0 hypothesis: 4h range sitting in the tightest quartile of its own 30d history. Unaffected by the OI/percentile-sign correction (uses the unsigned `compression_score` primitive). |

**Formula (deterministic decision tree, evaluated in order):**

```text
1. if price_evi or comp is UNAVAILABLE due to missing data (not merely tier),
   or confidence < REGIME_MIN_CONFIDENCE, or coverage < REGIME_MIN_COVERAGE:
       regime = INSUFFICIENT_DATA
   # Note: oi_confirmation UNAVAILABLE does NOT by itself force INSUFFICIENT_DATA
   # here — OI is a modulating veto input, not a required directional input;
   # see step 2's "oi_confirmation is available" guard below.

2. elif |price_evi| >= REGIME_TREND_THRESHOLD
     and agreement >= REGIME_MIN_AGREEMENT
     and not (oi_confirmation is available and oi_confirmation <= REGIME_OI_VETO):
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
*both* a percentile-extreme move *and* cross-exchange agreement, **direction
is always decided by price alone**, and a candidate direction (either one)
can be **vetoed** by falling/opposing OI evidence even when price alone
clears the threshold — OI never independently selects LONG vs. SHORT, only
confirms or vetoes whichever side price already picked.

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
| OI role | Optional confirm/veto modulator — falling, sufficiently strong OI (`oi_confirmation <= REGIME_OI_VETO`, [§4.2](#42-4h-regime)) **may veto** a would-be trending call; OI **availability is not required** to establish direction (`oi_confirmation UNAVAILABLE` does not by itself make regime `INSUFFICIENT_DATA`, [§4.2](#42-4h-regime)); OI never selects `LONG`/`SHORT` on its own | Not used |
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
defines the exact signed-normalization formula — raw-value sign preserved,
percentile rank used only to modulate strength within that sign
(`normalized_evidence`) — and its unsigned companion
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
| Confidence formula components ([§8](#8-model-confidence-semantics)) | Excluded from the sum **without** renormalizing the denominator (deliberately *not* the same renormalization pattern as the row above) — `UNAVAILABLE` contributes no term at all, which provably guarantees confidence can never rise merely by evidence disappearing; see [§8](#8-model-confidence-semantics)'s worked proof. |

A missing percentile is therefore either a **hard fail**, a **neutral
(excluded) contribution**, or a **setup-specific unavailable state**
depending on the use site named above — the general rule is: state
explicitly which of the three applies, and never let `None` silently
compute as `0`. Note that the exclusion treatment itself has two different
shapes (renormalized vs. non-renormalized) depending on whether
monotonicity is required at that use site — [§8](#8-model-confidence-semantics)
explains why confidence specifically needs the non-renormalized form.

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

### 7.0a Structural high/low derivation (amended — corrects a nonexistent-field error)

An earlier draft defined `COMPRESSION_BREAKOUT`'s and `CONFIRMED_BREAKOUT`'s
structural boundaries as `max(high)` / `min(low)` "over the window,
reference exchange," as if `ExchangeFeatureVector` exposed per-timeframe
`high`/`low` fields. It does not — audited against
`analytics/feature_engine/models.py`, `ExchangeFeatureVector` exposes only
`price_move_pct`, `range_width_pct`, `close_price` (plus volume/OI/funding/
liquidation/quality fields), never `high`/`low`. This was a genuine error,
not a simplification — corrected below rather than silently smoothed over,
and the `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §0.2 grounding
statement now covers this derived value explicitly.

Raw `klines_1m` bars **do** carry OHLC (`KlineBar.high`, `KlineBar.low`,
`analytics/feature_engine/models.py`), so a higher-timeframe extreme is a
legitimate deterministic derived value — computed from exactly that
bucket's constituent closed 1m bars, gated by the **same** completeness
signal an `ExchangeFeatureVector` at that timeframe already carries
(`bars_expected`, `bars_present`, `has_gap`, `is_usable` — no new gap
logic is invented):

```text
HTF_high(timeframe, B, reference_exchange):
    efv = ExchangeFeatureVector(reference_exchange, symbol, market_type, timeframe, bucket_ts=B)
    if efv is missing, or efv.is_usable is not True, or efv.has_gap is not False,
       or efv.bars_present != efv.bars_expected:
        return UNAVAILABLE                       # fail closed — reuses §11's exact reference-vector gate
    return max(bar.high for bar in the reference exchange's closed klines_1m
               bars with ts in [B, B + timeframe))   # exactly the bucket's own
                                                       # constituent 1m bars — bars_present
                                                       # == bars_expected already guarantees
                                                       # this set is complete

HTF_low(timeframe, B, reference_exchange):
    # symmetric: min(bar.low for the same bar set), same gate
```

**Required constituent count:** exactly `bars_expected` for that timeframe
(e.g. 15 one-minute bars for a 15m bucket, 60 for 1h) — enforced by the
reused `bars_present == bars_expected` gate, not recomputed independently.
**Gap behavior:** any gap (`has_gap = True` or `bars_present !=
bars_expected`) makes `HTF_high`/`HTF_low` `UNAVAILABLE` for that bucket —
no partial-window extreme is ever computed from an incomplete set of 1m
bars. **Reference exchange:** the same canonical reference exchange as
everywhere else in this document ([§11](#11-reference-price-semantics)) —
no per-detector exchange substitution. **No-lookahead:** automatic by
construction — `B` is already a `selected_bucket`-produced closed bucket
([§1](#1-the-v2-decision-clock)), so every constituent bar in
`[B, B+timeframe)` is, by definition, no later than `B+timeframe <= T`;
this derivation adds no new lookahead surface. **Failure when incomplete:**
`UNAVAILABLE` propagates upward — a structural level built from a lookback
of several `HTF_high`/`HTF_low` calls ([§7.2](#72-compression_breakout),
[§7.3](#73-confirmed_breakout)) is itself `UNAVAILABLE` if **any** bucket
in that lookback is `UNAVAILABLE` — the whole level fails closed rather
than being computed from a partial lookback ([§21](#21-failure--fail-closed-rules),
"Unavailable" category).

### 7.0b Directional-context compatibility gate (amended — closes a countertrend gap)

An earlier draft gated `COMPRESSION_BREAKOUT` on nothing more than "4h
regime `!= INSUFFICIENT_DATA`," which could emit a breakout candidate
**against** a firmly established opposite 4h regime — a countertrend
signal, forbidden by `V2_PRODUCT_CONTRACT.md` §4.4: "V2 MUST NOT
deliberately emit a scenario that trades against an established, firmly
directional higher-timeframe context." `CONFIRMED_BREAKOUT` lacked an
explicit compatibility gate at all. Both are corrected by one shared,
explicit gate, reused by both families ([§7.2](#72-compression_breakout),
[§7.3](#73-confirmed_breakout)):

**Correctness note (re-amended — `UNAVAILABLE` is not the same as
`NEUTRAL`).** An earlier draft of this gate treated `bias == UNAVAILABLE`
identically to `NEUTRAL_NOT_ESTABLISHED` ("a genuinely unreadable bias
represents no established opposing view either"). That blurs a distinction
this document elsewhere treats as fundamental
([§21](#21-failure--fail-closed-rules): **Unavailable** — a required input
simply could not be computed right now — is a different category from
**Neutral** — a real, measured value that genuinely says "no lean").
`NEUTRAL_NOT_ESTABLISHED` is a successful measurement the 1h bias detector
actually produced; `UNAVAILABLE` means the detector could not run at all.
Treating an unreadable input the same as a successfully-computed neutral
reading would let a **new** actionable breakout episode form while a
required context check was never actually performed —
`V2_PRODUCT_CONTRACT.md` §4.4's "missing context is not a countertrend
signal" does not mean V2 should pretend a check that could not run actually
passed. The gate now fails closed on an `UNAVAILABLE` 1h bias for new
episode formation, as its own distinct reason, separate from the
countertrend check:

```text
directional_context_gate(breakout_direction, B4h, B1h):
    # 4h regime
    regime = 4h regime at B4h (§4.2)
    if regime == INSUFFICIENT_DATA:
        REJECT   # data-availability failure — distinct reason from countertrend
    if regime in {BULLISH_TRENDING, BEARISH_TRENDING}
       and regime's direction OPPOSES breakout_direction:
        REJECT   # established opposite regime — countertrend, forbidden
    # otherwise (NON_DIRECTIONAL, or regime ALIGNED with breakout_direction): pass

    # 1h bias
    bias = 1h bias at B1h (§4.3)
    if bias == UNAVAILABLE:
        REJECT   # data-availability failure — distinct reason from countertrend;
                 # UNAVAILABLE is NEVER treated as NEUTRAL_NOT_ESTABLISHED (amended)
    if bias in {BULLISH, BEARISH} and bias's direction OPPOSES breakout_direction:
        REJECT   # established opposite bias — countertrend, forbidden
    # otherwise (NEUTRAL_NOT_ESTABLISHED, or bias ALIGNED with breakout_direction): pass

    ACCEPT
```

`4h regime == INSUFFICIENT_DATA` already failed closed in the prior draft
(unchanged, restated above for symmetry); `1h bias == UNAVAILABLE` now
fails closed the same way and for the same reason — a required context
input that could not be computed, never an established opposing view.
**`NEUTRAL_NOT_ESTABLISHED` remains fully accepted**, unchanged: per
`V2_PRODUCT_CONTRACT.md` §4.4, "a neutral/non-directional/not-firmly-established
4h regime or 1h bias is explicitly NOT itself a countertrend condition," and
`COMPRESSION_BREAKOUT` specifically "may legitimately form without a firm
1h bias" — a **real, measured** `NEUTRAL_NOT_ESTABLISHED` reading is exactly
that permitted case. An `UNAVAILABLE` reading is not the same thing and
does not inherit that permission. This distinction governs **new** episode
formation (`EARLY_SIGNAL`) for both breakout families — see
[§7.2](#72-compression_breakout)/[§7.3](#73-confirmed_breakout) for how each
invokes this gate; it does **not** retroactively invalidate an
already-`CONFIRMED` episode merely because a later 1h bias reading becomes
`UNAVAILABLE` — that is a data-availability condition for detector
evaluation, not one of [§10](#10-structural-invalidation)'s structural
invalidation triggers.

This gate does **not** apply to `TREND_PULLBACK`, which already requires 4h
regime and 1h bias to both *firmly agree* with the candidate direction as
its own, stricter precondition ([§7.1](#71-trend_pullback)) — a gate that
additionally rejects neutral/unavailable context would be redundant there.

`V2_PRODUCT_CONTRACT.md` §4.3's `CONFIRMED_BREAKOUT` description ("1h
establishes directional context aligned with the break") describes the
**typical** case, not an unconditional requirement that a firm bias must
exist — the general boundary rule in Product Contract §4.4 governs all
three families uniformly, so this document does **not** turn a neutral 1h
bias into an automatic `CONFIRMED_BREAKOUT` rejection; only an established
**opposite** bias rejects.

### 7.0c Extreme tie-breaking (deterministic structural-anchor selection)

**New — freezes a case the prior draft left unspecified.** Two structural
anchors are defined as "the bucket achieving an extreme value over a
lookback": `TREND_PULLBACK`'s `trend_leg_extreme`
([§7.1](#71-trend_pullback)) and `CONFIRMED_BREAKOUT`'s
`resistance_level`/`support_level` ([§7.3](#73-confirmed_breakout)). Both
feed `structural_anchor`, which participates in `episode_logical_key`
([§12](#12-episode-identity-and-deduplication)). If two or more buckets in
the relevant lookback share the *identical* extreme value, the prior draft
did not say which `bucket_ts` becomes the anchor — meaning two conforming
implementations, given byte-identical input data, could compute two
different episode identities. This document does not permit that kind of
ambiguity anywhere else, and closes it here with one rule, applied
globally:

```text
when two or more buckets/bars in the relevant lookback share the identical
extreme value (the same max, or the same min, compared at full stored
precision — no rounding before comparison):
    select the MOST RECENT bucket_ts among the tied candidates as the
    anchor bucket
```

**Rationale.** "Most recent" needs no further justification beyond
determinism itself, but it is also the same directional bias this document
already uses whenever a choice among otherwise-equal candidates is
required (e.g. [§7.2](#72-compression_breakout)'s "most recent qualifying
[compression] run" selection) — a tied, more recent bucket is, all else
equal, at least as representative of the *current* structural context as
an older one, so preferring it is never a worse choice than preferring the
older tie.

**Applies to** (anchors where *which* bucket achieved the extreme is
identity-bearing):

- `TREND_PULLBACK`'s `trend_leg_extreme` ([§7.1](#71-trend_pullback)) —
  `max(close_price)`/`min(close_price)` over `LOOKBACK_15M`;
- `CONFIRMED_BREAKOUT`'s `resistance_level`/`support_level`
  ([§7.3](#73-confirmed_breakout)) — `max`/`min` of `HTF_high`/`HTF_low`
  over `LEVEL_LOOKBACK`.

**Does not apply to** `COMPRESSION_BREAKOUT`'s `range_high`/`range_low`
([§7.2](#72-compression_breakout)): those are plain numeric price levels —
`max()`/`min()` of a set of numbers is already fully deterministic
regardless of *which* bucket achieved it, so no bucket-identity ambiguity
exists there. That family's identity-bearing anchor
(`compression_start_bucket`) is instead determined by the compression-window
selection rule ([§7.2](#72-compression_breakout)), which is its own
separately-frozen deterministic rule.

**Test vector (deterministic tie).** Two 15m buckets in a `TREND_PULLBACK`
LONG's `LOOKBACK_15M` window both close at exactly `65,000.0` — the
lookback's highest close, tied: `b[10]` (older) and `b[30]` (more recent,
still within the lookback). Under the tie-break rule: `trend_leg_extreme`'s
value is `65,000.0` (unambiguous — both candidates agree on the number
itself), and its anchor `bucket_ts` is `b[30]`'s (the more recent of the
two), **not** `b[10]`'s. `structural_anchor` for this episode is therefore
deterministically `b[30]`'s `bucket_ts` — a second, independently-running
conforming implementation given the identical input data **MUST** compute
the same `b[30]` anchor and therefore the same `episode_logical_key`
([§12](#12-episode-identity-and-deduplication)), never a different one
depending on which tied bucket it happened to iterate to first.

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

`trend_leg_extreme`'s anchor `bucket_ts` (used for `structural_anchor`,
[§12](#12-episode-identity-and-deduplication)) is tie-broken per
[§7.0c](#70c-extreme-tie-breaking-deterministic-structural-anchor-selection)
when two or more buckets in the lookback share the identical extreme
`close_price`.

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

**`EARLY_SIGNAL` creation (exact decision boundary, V2-v0).** `T_detect` is
the **first** 15m decision boundary `T` at which both the Preconditions
above hold **and** a valid retracement (per the range above) exists. The
episode is created in `EARLY_SIGNAL` **at `T_detect`**, exactly once
(subsequent 15m boundaries while still `EARLY_SIGNAL` are pre-confirmation
re-evaluations of the same episode, not new detections):

```text
detection_timestamp = T_detect
B15_detect = selected_bucket(15m, T_detect)          # == B15 evaluated at T_detect
B5_detect  = selected_bucket(5m,  T_detect)          # most recent closed 5m bucket as of T_detect;
                                                       # since 15m boundaries are also 5m boundaries,
                                                       # bucket_ts(B5_detect) == T_detect
```

**Candidate age.** Max `PULLBACK_MAX_AGE = 8` closed 15m buckets (2h,
V2-v0) from `T_detect` to `T_confirm`, else → `EXPIRED`
([§13](#13-lifecycle-transition-semantics)).

**5m confirmation (trigger) — exact `CONFIRMED` decision boundary.** The
resumption trigger is evaluated at 5m decision boundaries (finer-grained
than the 15m boundary that produced `T_detect`). At a 5m decision boundary
`T'`, let `B5' = selected_bucket(5m, T')`. The trigger condition
(unchanged): the consensus `price_move_pct_median` sign matches the trend
direction (ternary sign, per `STAGE2_SPEC.md` §11.2) **and**
`price_direction_agreement >= 2/3`, for **one** closed 5m bucket
(`RESUMPTION_MIN_BUCKETS = 1`, V2-v0 — deliberately the loosest possible,
since 5m's role is trigger, not strength-scoring,
[§5.1](#51-percentile-lookback--window)).

`T_confirm` is the **first** such `T'` for which the trigger condition
holds on a bucket `B5'` that is **strictly later** than the detection-time
bucket:

```text
CONFIRMED at T_confirm  iff  trigger condition holds for B5'
                              AND bucket_ts(B5') > bucket_ts(B5_detect)
```

This last clause is load-bearing: because `bucket_ts(B5_detect) ==
T_detect` (a 15m boundary always coincides with a 5m boundary), the 5m
bucket that was *already closed and already known* at the moment
`EARLY_SIGNAL` was created can never itself serve as the confirming
bucket, even if it happens to already satisfy the trigger condition. The
earliest possible `B5'` is the *next* closed 5m bucket after `B5_detect`,
so `T_confirm >= T_detect + 5m`, strictly — `T_confirm > T_detect` always
holds, and a new episode can never be created and immediately `CONFIRMED`
from the same already-known 5m bucket.

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

**Entry zone.** No field of the `EARLY_SIGNAL` zone may depend on data that
does not exist yet at `T_detect` — in particular `confirmation_close_price`
(defined below) does not exist until `T_confirm` and MUST NOT appear in the
`EARLY_SIGNAL` zone ([§9](#9-entry-zone-semantics)).

*At `EARLY_SIGNAL` (established at `T_detect`, using only data already
known at `T_detect`):*
```text
LONG:  [pullback_extreme_low,  close_price(B15_detect, reference_exchange)]
SHORT: [close_price(B15_detect, reference_exchange), pullback_extreme_high]
```
The dynamic bound is the current 15m close — the same already-observed
structural price the retracement itself is measured against — never
`confirmation_close_price`.

*Pre-confirmation updates (while still `EARLY_SIGNAL`, per
[§9](#9-entry-zone-semantics)'s general "may move only pre-`CONFIRMED`"
rule):* at each later 15m decision boundary `T'` with `T_detect < T' <
T_confirm`, the dynamic bound re-evaluates against `B15' =
selected_bucket(15m, T')`, using only data already closed as of `T'`:
```text
LONG:  [pullback_extreme_low,  close_price(B15', reference_exchange)]
SHORT: [close_price(B15', reference_exchange), pullback_extreme_high]
```
`pullback_extreme_low`/`pullback_extreme_high` themselves update only if
the retracement deepens further (same "deepest close so far" rule above) —
never as a function of anything not yet closed.

*At `CONFIRMED` (`T_confirm`, using the confirming bucket `B5'`):* the zone
updates **one final time**, now that
`confirmation_close_price = close_price(B5', reference_exchange)` exists:
```text
LONG:  [pullback_extreme_low,  confirmation_close_price]
SHORT: [confirmation_close_price, pullback_extreme_high]
```
and is then **frozen** — [§9](#9-entry-zone-semantics)'s generic
freeze-on-`CONFIRMED` and historical-truth rules apply unchanged: any
pre-`CONFIRMED` zone value already notified is preserved in event history,
never silently rewritten.

**Expected horizon:** `2h` from `CONFIRMED` ([§14](#14-candidate-expiry-and-expected-horizons)).

### 7.2 `COMPRESSION_BREAKOUT`

**Compression (15m) — a detector-internal precondition, not an episode
state.** Let `B15 = selected_bucket(15m, T)`, `COMPRESSION_LOOKBACK = 16`
closed 15m buckets (4h, V2-v0):

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
compression regime. "Compressed" is purely a fact about the market's recent
15m history; it does not by itself create an episode — no `EARLY_SIGNAL`
exists yet at this point (mirroring how `TREND_PULLBACK`'s regime/bias
precondition, [§7.1](#71-trend_pullback), is also detector-internal, not an
episode state).

**Deterministic compression-window selection (amended — "the compression
window" was previously underspecified).** `>= COMPRESSION_MIN_DURATION`
consecutive compressed buckets *somewhere* within `COMPRESSION_LOOKBACK`
does not, by itself, identify a unique window — a 16-bucket lookback can
contain one run of 6 followed later by a run of 7, one continuous run of 9,
two distinct runs of exactly 6, or other shapes, and `range_high`/`range_low`
(below) need one unambiguous window to be computed from. This is now
frozen precisely:

```text
1. Within the COMPRESSION_LOOKBACK most recent closed 15m buckets ending at
   B15, partition the compressed buckets (compression_score >=
   COMPRESSION_THRESHOLD) into MAXIMAL runs of CONSECUTIVE compressed
   buckets — a run is bounded by a non-compressed bucket, or by the edge
   of the lookback window.
2. A run QUALIFIES iff its length >= COMPRESSION_MIN_DURATION (6).
3. If zero runs qualify: compressed = False; no COMPRESSION_BREAKOUT
   candidate can form from this bucket.
4. If one or more runs qualify: select the run whose END bucket (its most
   recent bucket) is closest to B15 — i.e. the MOST RECENT qualifying run.
   (Precedence, stated in full for robustness even though a unique run
   already follows from step 4 alone — two distinct maximal runs can never
   share an end bucket, so "longest run" and "latest end bucket"
   tie-breaks below are never actually invoked in practice, only defined
   for completeness: (a) most recent qualifying run wins; (b) if that were
   ever ambiguous, the longest qualifying run wins; (c) if still tied, the
   run with the latest end bucket wins.)
5. compression_start_bucket = the selected run's oldest (first) bucket_ts
   compression_end_bucket   = the selected run's most recent (last) bucket_ts
   compression_length       = number of buckets in the selected run (>= 6)
6. "The compression window" (below, and in range_high/range_low) means the
   FULL selected run, inclusive of every bucket from compression_start_bucket
   through compression_end_bucket — not merely a truncated 6-bucket slice
   of it. A longer qualifying run contributes its entire observed tight
   range, not just the minimum qualifying length.
```

`compression_start_bucket` is exactly the value `COMPRESSION_BREAKOUT`'s
`structural_anchor` already uses for episode identity
([§12](#12-episode-identity-and-deduplication)) — this section is what
makes that value itself unambiguous. `compression_end_bucket` and
`compression_length` are additionally frozen here because a future
detector/evaluator needs them to reconstruct the exact window
deterministically, not only its start.

**Breakout boundary.** The compression range's bounds, from the exact
selected window (`compression_start_bucket` through
`compression_end_bucket`, above — never an ambiguous "somewhere in the
lookback"), using the [§7.0a](#70a-structural-highlow-derivation-amended--corrects-a-nonexistent-field-error)
extrema derivation (never a nonexistent `ExchangeFeatureVector.high/low`):

```text
range_high = max(HTF_high(15m, b, reference_exchange) for b in [compression_start_bucket, compression_end_bucket])
range_low  = min(HTF_low(15m, b, reference_exchange)  for b in [compression_start_bucket, compression_end_bucket])
```
`UNAVAILABLE` for any bucket `b` in the window makes `range_high`/`range_low`
`UNAVAILABLE` for the whole window ([§7.0a](#70a-structural-highlow-derivation-amended--corrects-a-nonexistent-field-error)) — no candidate can form.

**`EARLY_SIGNAL` — the one exact moment this episode is created.** At the
**first** closed 5m bucket (reference exchange) whose close crosses beyond
`range_high` (candidate direction `LONG`) or `range_low` (candidate
direction `SHORT`), **all** of the following must hold simultaneously:

```text
1. Directional confirmation: consensus price_direction_agreement(5m) >= 2/3
   on that bucket.
2. Volume/flow confirmation: taker_delta_notional_usd_sum (consensus, 5m)
   at that bucket has the same sign as the candidate direction — a breakout
   with taker flow opposing the direction of the break does not qualify
   (reuses already-ingested consensus taker-flow sums, no new field).
3. Directional-context compatibility: directional_context_gate(candidate_direction,
   B4h = selected_bucket(4h, T), B1h = selected_bucket(1h, T)) == ACCEPT
   (§7.0b) — an established OPPOSITE 4h regime or 1h bias rejects (countertrend);
   4h INSUFFICIENT_DATA or 1h UNAVAILABLE also rejects (data-availability,
   distinct reason); a NON_DIRECTIONAL regime or a real measured
   NEUTRAL_NOT_ESTABLISHED bias does NOT reject, per V2_PRODUCT_CONTRACT.md §4.4.
```

If all three hold, the episode is created in state `EARLY_SIGNAL` at this
decision boundary `T` (`detection_timestamp = T`, [§17](#17-outcome--evaluation-model)).
The entry zone is established here ([§9](#9-entry-zone-semantics)). If any
one fails, **no episode is created** — this is not a rejected candidate
with hidden state, it simply never begins.

**`CONFIRMED`.** Within `CONFIRMATION_MAX_AGE = 3` closed 5m buckets (15
min, V2-v0) of the `EARLY_SIGNAL` bucket, the **first subsequent** closed
5m bucket (reference exchange) that closes **strictly beyond** the
**same** boundary (same candidate direction) → `CONFIRMED` — **provided no
intervening closed 5m bucket produced an invalidating close** (False-break,
below). This confirming close is **not** required to be the immediately
next bucket: any number of intervening buckets that neither confirm (don't
close strictly beyond the boundary) nor invalidate (don't close on the
wrong side; a boundary-equality close, below, does neither) may sit
between the `EARLY_SIGNAL` bucket and the confirming one, up to
`CONFIRMATION_MAX_AGE`.

V2-v0 deliberately does **not** describe this as "consecutive" qualifying
closes — the episode's confirmation shape is **first breakout close**
(`EARLY_SIGNAL`) **+ a later confirming close, with no intervening
invalidating close** in between. This is the same shape `CONFIRMED_BREAKOUT`
uses, [§7.3](#73-confirmed_breakout), so both breakout families now share
one canonical confirmation shape.

**False-break, direction-aware, one-sided → `INVALIDATED` (re-amended —
covers overshoot through the opposite side, not only re-entry).** An
earlier draft invalidated only when a later pre-confirmation close fell
strictly **inside** the compression range (`range_low < close < range_high`).
That predicate cannot fire for a violent reversal that closes **through**
the entire range and beyond its *opposite* boundary — e.g. for a `LONG`
`EARLY_SIGNAL` broken above `range_high`, a later close below `range_low`
does not satisfy `range_low < close < range_high` (it fails the "inside the
range" test on the low side too), so under the old rule it would **not**
have been recognized as a false break — even though it is a *stronger*
repudiation of the breakout than an ordinary re-entry. The rule is now
direction-aware and one-sided: it checks only whether the **breakout side**
still holds, not whether price happens to sit back inside the original
range specifically:

```text
LONG EARLY_SIGNAL (broken above range_high):
    holds       iff close >= range_high
    INVALIDATED on ANY closed 5m bucket (reference exchange, before the
        confirming close) with close < range_high — this covers
        BOTH ordinary re-entry (range_low < close < range_high) AND
        overshoot clean through to the opposite side (close <= range_low)
        with the same single check.

SHORT EARLY_SIGNAL (broken below range_low):
    holds       iff close <= range_low
    INVALIDATED on ANY closed 5m bucket with close > range_low — covers
        BOTH re-entry AND overshoot beyond range_high (close >= range_high)
        with the same single check.
```

**Boundary equality (V2-v0 convention, stated explicitly):** a close
**exactly at** the broken level (`close == range_high` for `LONG`,
`close == range_low` for `SHORT`) is a **neutral HOLD** — it neither
confirms nor invalidates. It does not invalidate: the level has been
retested, not yet reclaimed on the wrong side (see False-break above,
which requires `close < range_high` / `close > range_low`, strictly, to
fire). It does not confirm either: `CONFIRMED` (above) requires a close
**strictly beyond** the boundary, and equality is not beyond it. A
boundary-equality bucket simply consumes one bucket of
`CONFIRMATION_MAX_AGE` while the episode continues waiting. A close on the
wrong side of the level by any amount, including the smallest tick, does
invalidate — the structural premise has broken → `INVALIDATED` (not a
silent non-creation — the episode already exists as `EARLY_SIGNAL` at this
point, and this is a real lifecycle transition,
[§13](#13-lifecycle-transition-semantics)). A stronger failure is never
exempted from invalidation merely because it moved "too far" to still be
sitting inside the original range.

**Deadline elapses → `EXPIRED`.** If `CONFIRMATION_MAX_AGE` elapses with
neither a confirming close (strictly beyond the boundary) nor a
false-break (wrong-side close) — e.g. every intervening bucket sits
exactly at the boundary, or on the correct side but never strictly beyond
it — → `EXPIRED`.

These three outcomes (`CONFIRMED` / `INVALIDATED` via false break /
`EXPIRED` via timeout) are mutually exclusive and exhaustive for an
`EARLY_SIGNAL` `COMPRESSION_BREAKOUT` episode — there is no fourth, hidden
resolution.

**Structural invalidation once `CONFIRMED`.**
```text
LONG:  invalidation_price = range_low  - protection_buffer(15m, B15, reference_price)
SHORT: invalidation_price = range_high + protection_buffer(15m, B15, reference_price)
```
same close-based, single-bucket rule as [§7.1](#71-trend_pullback) and
[§10](#10-structural-invalidation).

**Entry zone.** `[range boundary, range boundary ± protection_buffer]` —
i.e. `[range_high, range_high + protection_buffer]` (LONG) /
`[range_low − protection_buffer, range_low]` (SHORT): entry is anchored at
the broken structural boundary itself, with the protection buffer as the
zone's only width (there is no "confirmation price" analogous to
`TREND_PULLBACK`'s, since the `EARLY_SIGNAL` bucket's close **is** the
initial qualifying event).

**Candidate expiry / horizon:** max age from `EARLY_SIGNAL` to `CONFIRMED`
is `15 min` (`3` closed 5m buckets, above); expected horizon `1.5h` from
`CONFIRMED` ([§14](#14-candidate-expiry-and-expected-horizons)).

### 7.3 `CONFIRMED_BREAKOUT`

**Structural level (1h).** Let `B1h = selected_bucket(1h, T)`,
`LEVEL_LOOKBACK = 48` closed 1h buckets (48h, V2-v0). The level is defined
by **high/low extremes**, not closes (a structural level is physically an
extreme; closes govern breakout/invalidation acceptance, per the
close-based principle stated once in [§10](#10-structural-invalidation)),
using the [§7.0a](#70a-structural-highlow-derivation-amended--corrects-a-nonexistent-field-error)
extrema derivation (never a nonexistent `ExchangeFeatureVector.high/low`):

```text
resistance_level = max(HTF_high(1h, b, reference_exchange) for b in the LEVEL_LOOKBACK buckets)
support_level     = min(HTF_low(1h, b, reference_exchange)  for b in the LEVEL_LOOKBACK buckets)
```
`UNAVAILABLE` for any bucket `b` in the lookback makes `resistance_level`/
`support_level` `UNAVAILABLE` — no candidate can form. The anchor
`bucket_ts` used for `structural_anchor`
([§12](#12-episode-identity-and-deduplication)) is tie-broken per
[§7.0c](#70c-extreme-tie-breaking-deterministic-structural-anchor-selection)
when two or more buckets in the lookback share the identical extreme
`HTF_high`/`HTF_low` value.

**`EARLY_SIGNAL` — the one exact moment this episode is created (amended,
resolves a prior EARLY_SIGNAL/candidate inconsistency).** An earlier draft
had the first breaking close start a "confirmation window" whose failure
"never reaches `EARLY_SIGNAL`," while other parts of this document (e.g.
the reversal vector) referred to a new `CONFIRMED_BREAKOUT` candidate
independently reaching `EARLY_SIGNAL` — an internal contradiction. Resolved
by the same clean mapping `COMPRESSION_BREAKOUT` now uses
([§7.2](#72-compression_breakout)): the **first** closed 5m bucket
(reference exchange) whose close crosses beyond `resistance_level`
(candidate direction `LONG`) or `support_level` (candidate direction
`SHORT`) creates the episode in state `EARLY_SIGNAL`, **provided**
`directional_context_gate(candidate_direction, B4h = selected_bucket(4h, T),
B1h)` (§7.0b) is `ACCEPT` — an established opposite 4h regime or 1h bias
rejects (no episode is created); otherwise `detection_timestamp = T` and
the entry zone is established here ([§9](#9-entry-zone-semantics)). There
is no taker-flow confirmation requirement for this family (see the
comparison below).

**`CONFIRMED`.** Within `CONFIRMATION_MAX_AGE = 8` closed 5m buckets (40
min, V2-v0) of the `EARLY_SIGNAL` bucket, the **first subsequent** closed
5m bucket that closes **strictly beyond** the level (same candidate
direction) → `CONFIRMED` — provided no intervening closed 5m bucket
produced an invalidating close (False-break, below). As with
`COMPRESSION_BREAKOUT` ([§7.2](#72-compression_breakout)), this confirming
close is **not** required to be the immediately next bucket, and V2-v0 does
not describe this as "consecutive" closes — the confirmation shape is
**first breakout close** (`EARLY_SIGNAL`) **+ a later confirming close,
with no intervening invalidating close**. This is the structural
difference from `COMPRESSION_BREAKOUT`'s 15-minute window:
`CONFIRMED_BREAKOUT` is the general case with *no* preceding-compression
precondition, so it allows more time for the confirming close in exchange
for not requiring a compression regime.

**Boundary equality (V2-v0 convention, same as `COMPRESSION_BREAKOUT`,
[§7.2](#72-compression_breakout)):** a close **exactly at** the level
(`close == resistance_level` for `LONG`, `close == support_level` for
`SHORT`) is a **neutral HOLD** — it neither confirms (`CONFIRMED` above
requires a close strictly beyond the level) nor invalidates (False-break,
below, requires closing back beyond the level on the *opposite* side). It
simply consumes one bucket of `CONFIRMATION_MAX_AGE` while the episode
continues waiting.

**False-break re-entry → `INVALIDATED`.** If, before a confirming close
arrives, a closed 5m bucket (reference exchange) closes back beyond the
level on the **opposite** side (i.e. undoes the break: below
`resistance_level` for a `LONG` candidate, above `support_level` for a
`SHORT` candidate) → `INVALIDATED` — the same false-break-re-entry pattern
as `COMPRESSION_BREAKOUT` ([§7.2](#72-compression_breakout)), not a silent
non-creation.

**Deadline elapses → `EXPIRED`.** If `CONFIRMATION_MAX_AGE` elapses with
neither a confirming close (strictly beyond the level) nor a false-break
(wrong-side close) — e.g. every intervening bucket sits exactly at the
level — → `EXPIRED`.

Both breakout families therefore now share **one canonical lifecycle
shape** — `EARLY_SIGNAL` on the first qualifying close, `CONFIRMED` on the
first later close that closes strictly beyond the same boundary with no
intervening invalidating close, a boundary-equality close treated as a
neutral hold (consumes a bucket of the deadline but neither confirms nor
invalidates), false-break re-entry → `INVALIDATED`, deadline timeout →
`EXPIRED` — differing only in `CONFIRMATION_MAX_AGE`/window length and
each family's own qualification checks
([§7.4](#74-setup-family-precedence-and-deduplication)'s comparison table
records the differences).

**Invalidation once `CONFIRMED`.**
```text
LONG:  invalidation_price = resistance_level - protection_buffer(1h, B1h, reference_price)
SHORT: invalidation_price = support_level    + protection_buffer(1h, B1h, reference_price)
```
i.e. beyond the broken level itself (not the retest extreme — unlike the
Stage 2 Clarifications' historical sweep/reclaim design, V2's
`CONFIRMED_BREAKOUT` has no retest-extreme concept; the broken level is the
only structural anchor).

**Entry zone.** `[level, level ± protection_buffer]`, same construction as
`COMPRESSION_BREAKOUT`'s.

**Difference from `COMPRESSION_BREAKOUT`, summarized:** `CONFIRMED_BREAKOUT`
requires **no** preceding compression precondition, uses a **1h** structural
lookback (vs. 15m compression window), allows a **40-minute** confirmation
window (vs. 15 minutes), and has **no** taker-flow confirmation requirement
(compression's volume-confirmation gate does not carry over — a generic
level break is not defined by the preceding volatility regime the way a
compression breakout is). Both share the same **first breakout close +
later confirming close, no intervening invalidating close** shape and the
same `directional_context_gate` compatibility check (§7.0b).

**Candidate expiry / horizon:** max age from `EARLY_SIGNAL` to `CONFIRMED`
is `40 min` (above); expected horizon `2.5h` from `CONFIRMED`.

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
reused as a pattern, not as shared code.

**Formula (amended — corrects a monotonicity violation).** An earlier draft
renormalized the weighted sum to the *available* weight total (mirroring
the Data Confidence family-score pattern, `STAGE2_SPEC.md` §11.4) and
relied on a count-based cap ("below 4 of 5 available, cap at 0.70") to stop
confidence from rising when evidence disappears. That cap did not actually
prevent the violation it was meant to prevent: removing any
below-weighted-mean component from a renormalized average *always* raises
the average of what remains — a general property of weighted means, not an
edge case — and this could happen while still at 4-of-5 or 5-of-5
available, entirely below the count-based cap's trigger point. Concretely,
with two components (`w1=0.9, v1=0.5`) and (`w2=0.1, v2=0.0`): available
average `= 0.9*0.5 = 0.45`; drop the second component (still "available"
under any count-based cap with only 2 total) → renormalized average
`= 0.45 / 0.9 = 0.50` — confidence **rose** purely because a low-valued
component vanished, exactly the forbidden behavior.

**The corrected formula removes renormalization entirely** — missing
components are excluded from the sum, but the **denominator is not
shrunk to match**:

```text
model_confidence =
    UNAVAILABLE                                   if availability_mass == 0.0   # all 5 missing — fails closed
    Σ (weight_c * component_c) for c available    otherwise                     # NOT divided by availability_mass

where availability_mass = Σ (weight_c for c available)     # 0..1
```

**Proof of monotonicity.** Every term `weight_c * component_c` is `>= 0`
(weights `>= 0`, components `∈ [0,1]`), and the terms for still-available
components are **literally unchanged** when another component becomes
unavailable — the sum simply has fewer non-negative terms. A sum of fewer
non-negative terms can never exceed the original sum. Removing a component
can therefore only decrease or exactly preserve `model_confidence`, never
increase it — by construction, not by an empirically-tuned cap. (The
count-based `0.70` cap from the earlier draft is removed: it is no longer
needed — the corrected formula is self-limiting, since any weight mass
belonging to an unavailable component can never contribute a positive term,
capping the achievable value at whatever weight mass remains available.)

**Worked example (required by this amendment).** Weights
`0.25/0.20/0.30/0.15/0.10` (regime/bias/setup/trigger/data), all 5 available
with values `0.6/0.5/0.8/0.7/0.2`:

```text
model_confidence(5 available) = .25*.6 + .20*.5 + .30*.8 + .15*.7 + .10*.2
                                = 0.15 + 0.10 + 0.24 + 0.105 + 0.02 = 0.615
```

Now `data_confidence` (weight `0.10`, value `0.2`) becomes `UNAVAILABLE`:

```text
model_confidence(4 available) = .25*.6 + .20*.5 + .30*.8 + .15*.7
                                = 0.15 + 0.10 + 0.24 + 0.105 = 0.595
```

`0.595 <= 0.615` — confidence strictly decreased, as it must: the removed
term (`0.10*0.2 = 0.02`) was positive, so its removal strictly lowers the
sum. This holds for **any** available-to-unavailable transition, not just
this example — see the proof above.

**Hard invariants:**

- `model_confidence` **MUST NOT** increase merely because a component
  became `UNAVAILABLE` — this is now guaranteed by construction (proof
  above), not by a count-based mitigation.
- `availability_mass == 0.0` (every component `UNAVAILABLE`) is a distinct
  `UNAVAILABLE` result, never a computed `0.0` — the episode cannot be
  scored and fails closed ([§21](#21-failure--fail-closed-rules)), preserving
  "missing `!=` zero" exactly at this boundary case.
- Unavailable evidence **MUST NOT** be treated as confirming evidence
  anywhere in this formula — a missing component contributes **no term** to
  the sum (not a zero-valued term standing in for "confirmed absence" —
  the distinction is that its weight is never assigned to anything, rather
  than being asserted to have observed a bearish/unconfirming value).
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
CONFIRMED    -> COMPLETED     horizon elapsed, analytical_MFE_R reached MIN_MFE_R_FOR_COMPLETION at some point (§18.2)
CONFIRMED    -> EXPIRED       horizon elapsed, analytical_MFE_R never reached MIN_MFE_R_FOR_COMPLETION, not invalidated

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
`WEAKENING` episode can recover" (`V2_PRODUCT_CONTRACT.md` §5.1 there):
yes, it can, whenever the evidence-quality criteria that triggered
`WEAKENING` are no longer met and the episode has not since invalidated or
completed.

**Completion vs. expiry, precisely (V2-v0; re-amended — uses the
all-`CONFIRMED` analytical metric, never an `ACTIONABLE`-only one).** An
earlier draft gated this transition on `MFE_R`, which (per
[§18](#18-risk-normalized-metrics-planned-risk-vs-execution-risk)) is
defined only for `ACTIONABLE` episodes — that left every `LATE` /
`INVALIDATED_BEFORE_ENTRY` `CONFIRMED` episode with **no deterministic
terminal state** at horizon end, since it has no `feasible_entry_price` and
therefore no `MFE_R` to compare. Lifecycle state MUST NOT depend on whether
a hypothetical human could have entered 90 seconds later — analytical
episode lifecycle and execution/actionability evaluation are separate
concerns. This transition now uses
[§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)'s
`analytical_MFE_R`, which is defined for **every** `CONFIRMED` episode
regardless of `lateness_status`:

```text
MIN_MFE_R_FOR_COMPLETION = 0.5   # R-multiple, see §18.2
```

At horizon end (from `CONFIRMED` or `WEAKENING`), if the episode's
`analytical_MFE_R` (peak favorable excursion from
`confirmation_reference_price`, normalized by `planned_risk_distance`,
[§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode))
reached `>= 0.5` at any point during its life, it transitions to
`COMPLETED` — "the scenario played out and moved meaningfully in the
intended direction at some point," even if it later gave the move back. If
`analytical_MFE_R` never reached `0.5`, it transitions to `EXPIRED` — "the
trade never got going before time ran out." This is a deterministic,
evaluation-relevant distinction, not a cosmetic label choice, and it is now
computable for `LATE` episodes exactly the same way as for `ACTIONABLE`
ones — only the separate, `ACTIONABLE`-only `execution_MFE_R`
([§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only))
remains undefined for `LATE` episodes, and it plays no role in lifecycle
state.

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
| `COMPRESSION_BREAKOUT` | 15 min (3 × 5m buckets, `EARLY_SIGNAL` → later confirming close, [§7.2](#72-compression_breakout)) | 1.5h |
| `CONFIRMED_BREAKOUT` | 40 min (8 × 5m buckets, `EARLY_SIGNAL` → later confirming close, [§7.3](#73-confirmed_breakout)) | 2.5h |

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

This section freezes **two separate, decision-boundary-scoped** feasibility
checks — [§15.1](#151-confirmed_actionability_feasibility) for the
`CONFIRMED` transition, and [§15.2](#152-early_notification_feasibility)
for the first `EARLY_SIGNAL`. Each is evaluated using only the data
available at its own decision boundary; neither may use the other's
(earlier- or later-arriving) inputs.

### 15.1 `confirmed_actionability_feasibility`

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

### 15.2 `early_notification_feasibility`

The first `EARLY_SIGNAL` notification ([§16](#16-notification-materiality--anti-spam-thresholds))
is graded by a **structurally identical but independently-scoped** check —
using only values that exist **at the `EARLY_SIGNAL` decision boundary
itself**, never the (later, not-yet-existing) `CONFIRMED` zone,
`confirmation_close_price`, or any subsequent price data.

```text
early_notification_reference_time = detection_timestamp        # T_detect, per-detector (§7)
early_assumed_entry_time = early_notification_reference_time + ASSUMED_NOTIFICATION_DELAY_S
```

The same `ASSUMED_NOTIFICATION_DELAY_S = 90` is reused (V2-v0 does not
freeze a second, separate delay constant), and the same sampled-price
convention as [§15.1](#151-confirmed_actionability_feasibility) applies:
the reference exchange's 1-minute kline close of the bar whose close
timestamp is the smallest one `>= early_assumed_entry_time`.

**Feasibility (V2-v0):** the same shape as
[§15.1](#151-confirmed_actionability_feasibility), but every input is the
`EARLY_SIGNAL`-time value — the entry zone as it existed at
`detection_timestamp` (its initial value, [§9](#9-entry-zone-semantics))
and the structural invalidation level known as of that same event
(per-detector, [§7](#7-setup-detectors)):

```text
early_entry_zone_upper / early_entry_zone_lower = the EARLY_SIGNAL entry zone AS OF detection_timestamp
early_invalidation_price = the structural invalidation level known AS OF detection_timestamp
OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(setup_timeframe, B, reference_price)   # same as §15.1

LONG:  early-feasible iff sampled_price <= early_entry_zone_upper + OVERSHOOT_TOLERANCE
                            AND early_invalidation_price not yet breached (reference exchange,
                                closed 5m bucket) as of early_assumed_entry_time
SHORT: early-feasible iff sampled_price >= early_entry_zone_lower - OVERSHOOT_TOLERANCE
                            AND early_invalidation_price not yet breached as of early_assumed_entry_time
```

**Suppression ("already late" at `EARLY_SIGNAL`):** if `early-feasible` is
false, the first `EARLY_SIGNAL` notification
([§16](#16-notification-materiality--anti-spam-thresholds)) is suppressed —
the episode is still created, stored, and evaluated exactly like any other
([§17](#17-outcome--evaluation-model)); it simply never produces the
initial actionable notification. This suppression has **no effect** on the
later, independent [§15.1](#151-confirmed_actionability_feasibility) check
at `CONFIRMED`: an episode suppressed at `EARLY_SIGNAL` for being already
late can still notify normally at `CONFIRMED` if `CONFIRMED`'s own
check (using `CONFIRMED`-time inputs) passes, and vice versa. The later
`CONFIRMED` zone or later price data MUST NOT retroactively decide whether
the earlier `EARLY_SIGNAL` notification was feasible — each check is
frozen to its own decision boundary's inputs, permanently
([§9](#9-entry-zone-semantics)'s historical-truth rule).

---

## 16. Notification materiality / anti-spam thresholds

| Event | Material? | V2-v0 condition |
|---|---|---|
| First `EARLY_SIGNAL` | Only if `early-feasible` ([§15.2](#152-early_notification_feasibility)) — rare to suppress, but a pathologically late `EARLY_SIGNAL` is still not notified | — |
| `CONFIRMED` | **Always material, if `confirmed_actionability_feasibility` holds** ([§15.1](#151-confirmed_actionability_feasibility)) | — |
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

### 16.1 `EARLY_SIGNAL` notification content and history invariants (V2-v0)

When the first `EARLY_SIGNAL` notification is material
([§15.2](#152-early_notification_feasibility)), its content is a
**complete, user-visible semantic record**, entirely determined by data
already closed as of `detection_timestamp`:

```text
EARLY_SIGNAL notification content:
  direction               # LONG | SHORT — per-detector, §7
  setup_family            # TREND_PULLBACK | COMPRESSION_BREAKOUT | CONFIRMED_BREAKOUT
  state                   # EARLY_SIGNAL
  entry_zone              # the EARLY_SIGNAL zone AS OF detection_timestamp, §9 / per-detector §7
  invalidation_price      # the structural invalidation level AS OF detection_timestamp, §10 / per-detector §7
  expected_horizon        # per-family, §14 (informational at EARLY_SIGNAL — the horizon clock
                           # itself only starts counting from CONFIRMED, §14)
  model_confidence        # §8, computed from data closed as of detection_timestamp
  data_coverage           # min_coverage_ratio / consensus_confidence, as of detection_timestamp
  feasibility_status      # early-feasible | suppressed, §15.2
```

**No field above may depend on data that does not exist yet at
`detection_timestamp`** — in particular none of them may read
`confirmation_close_price`, the `CONFIRMED`-time entry zone, or any
`CONFIRMED`/`ACTIONABLE`-only metric
([§18](#18-risk-normalized-metrics-planned-risk-vs-execution-risk)), all of
which are undefined until `T_confirm`/`CONFIRMED`. This is the same
no-future-information constraint
[§2](#2-no-lookahead-semantics-per-input-family) already freezes for
feature computation generally, applied here to the notification content
itself.

**History preservation.** A value already published in the `EARLY_SIGNAL`
notification (the initial entry zone, invalidation level, confidence,
etc.) is never silently rewritten by a later event. `CONFIRMED` **may**
update and then freeze the entry zone ([§9](#9-entry-zone-semantics)) and
re-evaluate confidence/coverage, but this is recorded as a **new** event in
`episode_state_history` ([§17](#17-outcome--evaluation-model)) alongside
the episode — it never overwrites or erases the historical `EARLY_SIGNAL`
notification's own recorded values. This reuses the same
insert-once-per-event pattern
[§2.1](#21-replay-behavior-for-late-arriving--corrected-data) already
freezes for feature snapshots.

**Replay determinism.** Given the same input data and the same
`rules_version`/`calculation_version` ([§3](#3-v2-modelversion-identity)),
replay MUST produce **exactly the same sequence** of `EARLY_SIGNAL` and
`CONFIRMED` events — same `detection_timestamp`, same `T_confirm` (or
`EXPIRED`/`INVALIDATED` outcome), same zone/invalidation values at each
step — as the original live evaluation. This follows directly from
[§2](#2-no-lookahead-semantics-per-input-family)'s no-lookahead,
closed-bucket-only decision clock ([§1](#1-the-v2-decision-clock)): every
field in the record above is a pure function of already-closed data as of
its own decision boundary, so there is nothing for replay to compute
differently.

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
  confirmation_reference_price   # reference exchange close_price at the
                                  # CONFIRMED decision boundary — always
                                  # present for any CONFIRMED episode
  assumed_feasible_entry_timestamp   # §15
  feasible_entry_price_or_status     # actual sampled price + feasible/late verdict —
                                      # present only when lateness_status == ACTIONABLE
  invalidation_reached_at        # decision boundary T, or null
  horizon_completion_status      # COMPLETED | EXPIRED, per §13.2
  directional_return_pct         # §17 population: ALL CONFIRMED episodes
  mfe_pct / mae_pct              # §17 population: ALL CONFIRMED episodes
  planned_risk_distance          # §18.1 population: ALL CONFIRMED episodes
                                  # (available at CONFIRMED itself — no future info)
  analytical_mfe_r               # §18.2 population: ALL CONFIRMED episodes —
                                  # drives the COMPLETED/EXPIRED lifecycle decision (§13.2)
  execution_r                    # §18.3 population: ACTIONABLE episodes only
  execution_mfe_r / execution_mae_r   # §18.3 population: ACTIONABLE episodes only
  execution_terminal_return_r    # §18.3 population: ACTIONABLE episodes only
  execution_cost_adjusted_return_r    # §19 population: ACTIONABLE episodes only
  lateness_status                # ACTIONABLE | LATE | INVALIDATED_BEFORE_ENTRY
  setup_family
  episode_state_history          # ordered list of (T, from_state, to_state, reason)
  rules_version                  # §3
  calculation_version             # §3
  data_coverage_at_confirmation   # min_coverage_ratio, consensus_confidence at CONFIRMED
```

**No take-profit target is required** (per `V2_PRODUCT_CONTRACT.md` §6):
outcome is measured purely via horizon-based MFE/MAE/terminal-return and
their R-normalized forms
([§18](#18-risk-normalized-metrics-planned-risk-vs-execution-risk)) — an
episode that never reaches a fixed target can still be a fully evaluated,
meaningful outcome (`COMPLETED` requires only `MIN_MFE_R_FOR_COMPLETION` via
`analytical_MFE_R`, not a hit target).

**Two distinct price baselines, and why (amended for population clarity).**
`directional_return_pct` / `mfe_pct` / `mae_pct` are computed against
`confirmation_reference_price` (the reference exchange's `close_price` at
the `CONFIRMED` decision boundary) — a price that **exists for every
`CONFIRMED` episode**, regardless of whether the assumed delayed entry
later turned out feasible. This is deliberate: these percentage metrics
answer "how did price behave after this scenario was confirmed," a
question meaningful even for a `LATE` episode. They reuse V1's exact
direction-aware sign convention (`outcomes.py`: for `LONG`,
`mfe = max(0, peak_return)`, `mae = min(0, trough_return)`; mirrored for
`SHORT`), applied over the episode's own monitored window instead of a
fixed 15m/1h/4h horizon-from-prediction window.
[§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)'s
`analytical_MFE_R` normalizes this same all-`CONFIRMED` percentage metric
by `planned_risk_distance`, so it shares this population — it does **not**
require `feasible_entry_price`. The `ACTIONABLE`-only
`execution_MFE_R`/`execution_MAE_R`/`execution_terminal_return_R`
([§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only)),
by contrast, require `feasible_entry_price`, which is only defined when
`lateness_status == ACTIONABLE` — this is why those execution-scoped
R-normalized metrics have a narrower population than the percentage ones
and `analytical_MFE_R`; [§26.1](#261-episode-population-definitions) freezes
this distinction precisely so a future evaluator never has to choose its
own denominator.

---

## 18. Risk-normalized metrics: planned risk vs. execution risk

**Correctness note (re-amended — separates two previously-conflated
concepts).** An earlier draft defined a single `R = |feasible_entry_price -
invalidation_price|` and used it **both** as a hard fail-closed gate at
`CONFIRMED` **and** as the denominator for every R-normalized outcome
metric. That is an impossible timing dependency: `feasible_entry_price`
([§15](#15-entry-feasibility-evaluation)) is sampled only
`ASSUMED_NOTIFICATION_DELAY_S = 90` seconds **after** the `CONFIRMED`
decision boundary, and only exists at all when `lateness_status ==
ACTIONABLE`. A quantity that does not yet exist at `CONFIRMED` cannot gate
whether an episode is allowed to reach `CONFIRMED`. This section fixes that
by defining two genuinely distinct, separately-named concepts — **never
both called simply `R`** anywhere in this document from this point on.

### 18.1 Planned risk (structural, available at `CONFIRMED`)

```text
planned_risk_distance = |confirmation_reference_price - invalidation_price|
```

Both inputs are already fixed no later than the `CONFIRMED` decision
boundary: `confirmation_reference_price` is the reference exchange's
`close_price` at that exact boundary ([§17](#17-outcome--evaluation-model)),
and `invalidation_price` is the detector's structural level
([§7](#7-setup-detectors), [§10](#10-structural-invalidation)), which has
already stopped moving by `CONFIRMED` (mirroring the entry zone's freeze
rule, [§9](#9-entry-zone-semantics)). `planned_risk_distance` therefore
requires **no future information** and is computable at the exact instant
an episode reaches `CONFIRMED` — unlike the old single `R`, it genuinely
CAN gate confirmation.

```text
MIN_VALID_PLANNED_RISK = 3 * tick_size   # V2-v0 — reused from the same tick-buffer
                                            # reasoning as protection_buffer (§7);
                                            # replaces the old MIN_VALID_R name/role

if planned_risk_distance is zero, non-finite, or < MIN_VALID_PLANNED_RISK:
    FAIL CLOSED: the episode cannot reach CONFIRMED (checked at
    confirmation time — a degenerate structural risk distance means the
    structural premise itself is not well-formed)
```

Because this is now a hard gate on a quantity that genuinely exists at
`CONFIRMED`, every `CONFIRMED` episode has a valid `planned_risk_distance`
by construction — "invalid planned risk" is never a separate
acceptance-population case to handle; it is excluded upstream, before an
episode can even become `CONFIRMED`.

**`planned_risk_distance` is used for:** the confirmation-time
structural-validity / degenerate-risk fail-closed gate above, and
[§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)'s
`analytical_MFE_R` — any quantity that must exist for **every** `CONFIRMED`
episode, including `LATE` ones, never only for `ACTIONABLE` ones.

### 18.2 Analytical R-normalized metrics (every `CONFIRMED` episode)

Normalizes the percentage metric [§17](#17-outcome--evaluation-model)
already computes for every `CONFIRMED` episode (against
`confirmation_reference_price`) by `planned_risk_distance`, so a
risk-normalized figure exists **regardless of `lateness_status`**. This is
what makes the lifecycle's `COMPLETED`/`EXPIRED` decision well-defined for
`LATE` episodes too ([§13.2](#132-allowed-transitions),
[§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only)
below remains `ACTIONABLE`-only and plays no role in lifecycle state):

```text
analytical_MFE_R = mfe_pct_over_episode_life * confirmation_reference_price / 100 / planned_risk_distance
```

(`mfe_pct_over_episode_life` here is the exact same all-`CONFIRMED`
population value already defined in [§17](#17-outcome--evaluation-model),
computed against `confirmation_reference_price` — **never** against
`feasible_entry_price`.) `analytical_MFE_R` becomes available the instant a
favorable excursion is observed after `CONFIRMED`, independent of whether
the episode ever reaches `ACTIONABLE` status — lifecycle state MUST NOT
depend on whether a hypothetical human could have entered 90 seconds later.

### 18.3 Execution risk and execution R-normalized metrics (`ACTIONABLE` only)

Distinct from planned risk — this is the risk distance from the price an
`ACTIONABLE` user could actually have entered at, meaningful only once that
price exists:

```text
execution_R = |feasible_entry_price - invalidation_price|
```

`feasible_entry_price` exists only when `lateness_status == ACTIONABLE`
([§15](#15-entry-feasibility-evaluation)), so `execution_R` — and every
metric normalized by it below — is defined **only** for `ACTIONABLE`
episodes. `execution_R` is **never** used as a confirmation-time gate (that
is exclusively `planned_risk_distance`'s role,
[§18.1](#181-planned-risk-structural-available-at-confirmed)); by the time
`execution_R` can exist, the episode is already `CONFIRMED`.

```text
execution_MFE_R             = execution_mfe_pct_over_episode_life * feasible_entry_price / 100 / execution_R
execution_MAE_R             = execution_mae_pct_over_episode_life * feasible_entry_price / 100 / execution_R
execution_terminal_return_R = execution_directional_return_pct    * feasible_entry_price / 100 / execution_R
```

(renamed from an earlier draft's bare `MFE_R`/`MAE_R`/`terminal_return_R` —
same formulas, now unambiguously scoped by name; the `* feasible_entry_price
/ 100` term converts a percentage return back to an absolute price distance
before dividing by `execution_R`, so these remain dimensionless
R-multiples). `execution_mfe_pct_over_episode_life` /
`execution_mae_pct_over_episode_life` / `execution_directional_return_pct`
are recomputed against `feasible_entry_price`, not
`confirmation_reference_price` — distinct from
[§17](#17-outcome--evaluation-model)'s all-`CONFIRMED` percentage metrics
and from [§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)'s
`analytical_MFE_R`. All three — the `CONFIRMED`-population percentage
metrics, the `CONFIRMED`-population `analytical_MFE_R`, and the
`ACTIONABLE`-only `execution_*` metrics — are legitimate, differently-scoped
measurements; none substitutes for another, and
[§26.1](#261-episode-population-definitions) states exactly which
population each feeds into an acceptance metric.

**`LATE` and `INVALIDATED_BEFORE_ENTRY` episodes are never dropped from the
evaluation sample** — they simply have no `execution_R` /
`execution_MFE_R` / `execution_MAE_R` / `execution_terminal_return_R` /
`execution_cost_adjusted_return_R` ([§19](#19-execution-cost-assumptions),
population = `ACTIONABLE` only, by definition of requiring
`feasible_entry_price`). They remain fully counted in the percentage
metrics and in `analytical_MFE_R`
([§17](#17-outcome--evaluation-model),
[§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)), in
the sample-size requirement ([§26](#26-acceptance-sample-requirements)),
and — critically — in the feasibility-rate metric's denominator
([§27](#27-acceptance-metric-hierarchy) priority 1), which is precisely how
a family that is frequently late gets penalized rather than having its late
episodes silently vanish from acceptance. **They also always reach a
deterministic lifecycle terminal state**
([§13.2](#132-allowed-transitions)) via `analytical_MFE_R`, regardless of
`lateness_status`.

**Behavior when `planned_risk_distance` is invalid:** the episode fails
closed at confirmation time
([§18.1](#181-planned-risk-structural-available-at-confirmed)); it never
reaches an evaluable `CONFIRMED` state at all, so no
`execution_R`-based metric question can even arise. There is no
divide-by-zero case to handle at evaluation time because it cannot occur.

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
execution_cost_adjusted_return_R = execution_terminal_return_R - (ASSUMED_ROUND_TRIP_COST_BPS / 10000 * feasible_entry_price) / execution_R
```

(renamed from an earlier draft's `cost_adjusted_return_R` /
`terminal_return_R` / bare `R` —
[§18](#18-risk-normalized-metrics-planned-risk-vs-execution-risk)'s
naming split applies here identically: this is an `ACTIONABLE`-only,
execution-scoped metric, built from `execution_terminal_return_R` and
`execution_R`, never from `planned_risk_distance` or `analytical_MFE_R`.)

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
| **Rejected** | The input exists, but a hard gate explicitly disqualifies it. | Insufficient cross-exchange coverage (`< 2/3`); malformed/non-finite numeric values; `calculation_version`/`rules_version` mismatch across inputs that must agree; contradictory context violating a setup's hard gate (e.g. `TREND_PULLBACK` attempted against a `NON_DIRECTIONAL` regime); `planned_risk_distance < MIN_VALID_PLANNED_RISK` ([§18.1](#181-planned-risk-structural-available-at-confirmed)); an already-breached invalidation level discovered before confirmation. |
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
- missing structural level → synthesize one from current price (forbidden — [§18.1](#181-planned-risk-structural-available-at-confirmed)'s `planned_risk_distance < MIN_VALID_PLANNED_RISK` fail-closed rule exists specifically to prevent this);
- unavailable percentile → assume median (forbidden — [§5.2](#52-missing-percentile-handling--never-none--0)'s `UNAVAILABLE` sentinel exists specifically to prevent this);
- unavailable canonical reference price → silently switch exchanges (forbidden — [§11](#11-reference-price-semantics) fails closed instead).

---

## 23. Configurability vs. frozen behavior

**Frozen semantics** (implementation cannot reinterpret without a version
change to this document itself): the decision clock ([§1](#1-the-v2-decision-clock)),
no-lookahead rules ([§2](#2-no-lookahead-semantics-per-input-family)), the
model/version identity model ([§3](#3-v2-modelversion-identity)), the
normalized-evidence formula and its sign-preservation invariants
([§4.1](#41-normalized-evidence-primitive-used-throughout-47)), the OI
confirmation/opposition (never independent-direction) rule
([§4.2](#42-4h-regime)), the directional-context compatibility gate
([§7.0b](#70b-directional-context-compatibility-gate-amended--closes-a-countertrend-gap)),
the three detectors' qualitative structure and shared breakout confirmation
shape — first breakout close + later confirming close, no intervening
invalidating close ([§7](#7-setup-detectors)), the confidence-formula shape and
its non-renormalizing, provably-monotonic sum rule
([§8](#8-model-confidence-semantics)), episode identity and precedence
rules ([§12](#12-episode-identity-and-deduplication),
[§7.4](#74-setup-family-precedence-and-deduplication)), the lifecycle
transition graph and precedence ([§13](#13-lifecycle-transition-semantics)),
the acceptance-metric population definitions
([§26.1](#261-episode-population-definitions)), the historical-replay vs.
live-shadow evidence distinction
([§28.2](#282-promotion-levels)–[§28.2a](#282a-live-shadow-evidence-requirement)),
the fail-closed categories ([§21](#21-failure--fail-closed-rules)), and the
no-silent-fallback rule ([§22](#22-no-silent-fallback-rule)).

**Versioned parameters** (may live in config, but their V2-v0 *values* are
frozen by this document and every one of them participates in
`rules_version` identity — a config change to any of them is a
`rules_version` bump, never a silent behavior change under an unchanged
version): every numeric constant introduced in this document —
`REGIME_TREND_THRESHOLD`, `BIAS_THRESHOLD`, `REGIME_OI_VETO`,
`COMPRESSION_THRESHOLD`, `PULLBACK_MIN_MULT`/`PULLBACK_MAX_MULT`,
`BUFFER_MULTIPLIER`, `CONFIRMATION_MAX_AGE` for both breakout families,
all per-family age/horizon numbers
([§14](#14-candidate-expiry-and-expected-horizons)),
`ASSUMED_NOTIFICATION_DELAY_S`, `OVERSHOOT_TOLERANCE`'s multiplier,
`ASSUMED_ROUND_TRIP_COST_BPS`, `MIN_VALID_PLANNED_RISK`'s tick multiplier, confidence
weights (the count-based partial-evidence cap from an earlier draft has
been **removed**, [§8](#8-model-confidence-semantics) — the corrected
formula is self-limiting and needs no separate cap), cooldown lengths, the
materiality thresholds in [§16](#16-notification-materiality--anti-spam-thresholds),
the acceptance sample/metric thresholds in [§26](#26-acceptance-sample-requirements)/
[§27](#27-acceptance-metric-hierarchy), and the `LIVE_SHADOW_MIN_*` gate in
[§28.2a](#282a-live-shadow-evidence-requirement).

**Config is not a loophole.** Because every versioned parameter above
participates in `rules_version` ([§3](#3-v2-modelversion-identity)),
changing one of them without bumping `rules_version` is itself a
correctness bug against this document — config can move the *value*, never
detach the value from its version identity.

### 23.1 Threshold re-audit after the percentile-sign correction

Item required by this amendment: re-evaluate every threshold that was
originally interpreted against the earlier (incorrect)
`normalized = 2*percentile_rank − 1` primitive, now that
[§4.1](#41-normalized-evidence-primitive-used-throughout-47) preserves the
raw value's sign. **None of the numeric values below needed to change** —
only their justification needed re-derivation, because (as
[§4.1](#41-normalized-evidence-primitive-used-throughout-47) shows) the
corrected `max(0, 2p−1)` / `−max(0, 1−2p)` construction reduces to exactly
the same "top/bottom `X`%" reading as the original `2p−1` formula did, once
gated by the raw value's own sign. Each threshold below was individually
re-checked, not merely carried forward unexamined:

| Threshold | Original (incorrect-primitive) reading | Re-audited reading under the corrected primitive | Changed? |
|---|---|---|---|
| `REGIME_TREND_THRESHOLD = 0.40` | "top/bottom 30% of 30d history" | Identical: for `v>0`, `>= 0.40` iff `p >= 0.70` (top 30%); for `v<0`, `<= −0.40` iff `p <= 0.30` (bottom 30%) — and now **only** reachable by a raw value whose own sign matches. | No — reading preserved, sign bug fixed. |
| `BIAS_THRESHOLD = 0.25` | "top/bottom ~37.5% of 7d history" | Identical derivation, `p >= 0.625` / `p <= 0.375` for the matching-signed raw value. | No. |
| `REGIME_COMPRESSION = 0.75` | Uses the unsigned `compression_score` primitive, never affected by the sign bug. | Unchanged. | No. |
| `REGIME_OI_VETO = −0.40` | Previously compared `oi_evi`'s sign against `price_evi`'s sign — a category error ([§4.2](#42-4h-regime)). | Re-derived entirely: now a threshold on `oi_confirmation` ([§4.2](#42-4h-regime)), a magnitude-and-rising/falling-only value, never compared to price's sign. The **number** `0.40` is kept as the same V2-v0 magnitude-strength hypothesis (a rising/falling OI move at or beyond the top/bottom 30% of its own history, cross-exchange-agreement-weighted) — only its role changed, from an incorrect sign-comparison to a correct confirmation/opposition-only gate. | Reinterpreted; number retained deliberately, not merely because it was already typed. |

No threshold was kept "merely because it was already typed into this PR" —
each row above was re-derived from the corrected primitive independently;
the fact that most numbers happened to remain valid is a consequence of the
`max(0, 2p−1)` construction's algebra, not an assumption.

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

"Completed" here means an episode that **reached `CONFIRMED` at least once
and later reached a terminal lifecycle state** (`COMPLETED`, `EXPIRED`, or
`INVALIDATED` — all three are evaluable outcomes,
[§17](#17-outcome--evaluation-model)), not only `COMPLETED` episodes
specifically. **Episodes that never reached `CONFIRMED`** — rejected or
never created while only a detector-internal candidate ([§7](#7-setup-detectors)),
or an `EARLY_SIGNAL` that reached `EXPIRED`/`INVALIDATED` without ever
confirming ([§13](#13-lifecycle-transition-semantics)) — are **excluded**
from this count entirely. This is a deliberate population boundary, not an
oversight: the acceptance metric hierarchy ([§27](#27-acceptance-metric-hierarchy))
is fundamentally about entry feasibility and R-normalized performance from
a `CONFIRMED` decision point onward, which is not a meaningful question for
a candidate that never confirmed. A candidate-rejection/never-confirmed
rate **MAY** be reported separately as an informational, non-gating
statistic, but it is not part of this sample-size requirement or the
acceptance metric hierarchy.

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

### 26.1 Episode population definitions

Every acceptance metric below has an explicit, reproducible denominator —
no future evaluator chooses its own population:

| Population name | Definition |
|---|---|
| `CONFIRMED` (sample base) | Episodes that reached `CONFIRMED` at least once and later reached a terminal lifecycle state (above). Every episode in this population has a `planned_risk_distance` and an `analytical_MFE_R` ([§18.1](#181-planned-risk-structural-available-at-confirmed)/[§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)) — both available at `CONFIRMED` itself, independent of `lateness_status`. |
| `ACTIONABLE` | The subset of `CONFIRMED` with `lateness_status == ACTIONABLE` ([§15](#15-entry-feasibility-evaluation)) — has a defined `feasible_entry_price`, and therefore `execution_R`, `execution_MFE_R`, `execution_MAE_R`, `execution_terminal_return_R`, `execution_cost_adjusted_return_R` ([§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only), [§19](#19-execution-cost-assumptions)). |
| `LATE` / `INVALIDATED_BEFORE_ENTRY` | The remaining `CONFIRMED` episodes ([§15](#15-entry-feasibility-evaluation)) — no `feasible_entry_price`, so no execution-scoped R-normalized metrics; still fully counted in `CONFIRMED`, in the percentage metrics ([§17](#17-outcome--evaluation-model), computed from `confirmation_reference_price`), and in `analytical_MFE_R` ([§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)) — which is why they still reach a deterministic lifecycle terminal state ([§13.2](#132-allowed-transitions)). |

| Metric | Population (exact) |
|---|---|
| `MIN_COMPLETED_EPISODES_AGGREGATE` / `_PER_FAMILY` ([§26](#26-acceptance-sample-requirements)) | `CONFIRMED` (all lateness statuses). |
| Actionable-entry feasibility rate, missed/late rate ([§27](#27-acceptance-metric-hierarchy) priority 1) | `CONFIRMED` — numerator `ACTIONABLE`, denominator `CONFIRMED`. `LATE` and `INVALIDATED_BEFORE_ENTRY` are exactly the episodes counted against the rate, not episodes that disappear from it. |
| Median/90th-percentile `execution_MAE_R`, median `execution_MFE_R`, proportion reaching `execution_MFE_R >= 0.5` ([§27](#27-acceptance-metric-hierarchy) priorities 2–3) | `ACTIONABLE` only — undefined for `LATE`/`INVALIDATED_BEFORE_ENTRY` by construction (no `feasible_entry_price`). |
| Mean `execution_cost_adjusted_return_R` ([§27](#27-acceptance-metric-hierarchy) priority 4) | `ACTIONABLE` only, same reason. |
| Directional accuracy, `execution_terminal_return_R > 0` ([§27](#27-acceptance-metric-hierarchy) priority 5) | `ACTIONABLE` only — `execution_terminal_return_R` is itself an execution-scoped R-based metric. (A supplementary, non-gating percentage-based accuracy figure — `directional_return_pct > 0` over **all** `CONFIRMED` episodes — **MAY** additionally be reported, since that percentage metric's population is broader; it carries no threshold either way, consistent with priority 5 never being a gate.) |

---

## 27. Acceptance metric hierarchy

Preserving the roadmap's priority order (`docs/FORECASTING_ROADMAP.md` §H)
exactly, with concrete V2-v0 metrics/thresholds per priority. **Population**
column values are defined precisely in
[§26.1](#261-episode-population-definitions) — no metric below has an
implicit or evaluator-chosen denominator. Every metric here is
**execution-scoped** (`ACTIONABLE`-only, [§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only)) —
distinct from [§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)'s
`analytical_MFE_R`, which drives lifecycle completion for **every**
`CONFIRMED` episode but is not itself an acceptance-gating metric:

| Priority | Roadmap priority | Metric | Population | V2-v0 threshold |
|---|---|---|---|---|
| 1 | Entry feasibility after real delay | Actionable-entry feasibility rate (`ACTIONABLE / CONFIRMED`, [§15](#15-entry-feasibility-evaluation)) | `CONFIRMED` | `>= 0.60` |
| 1b | (complement) | Missed/late rate | `CONFIRMED` | `<= 0.40` |
| 2 | Low MAE | Median `execution_MAE_R` | `ACTIONABLE` | `<= 1.0R` |
| 2b | (tail) | 90th-percentile `execution_MAE_R` | `ACTIONABLE` | `<= 2.0R` |
| 3 | Sufficient MFE | Median `execution_MFE_R` | `ACTIONABLE` | `>= 1.0R` |
| 3b | (breadth) | Proportion of episodes reaching `execution_MFE_R >= 0.5` before invalidation | `ACTIONABLE` | `>= 0.50` |
| 4 | Performance after costs/delay | Mean `execution_cost_adjusted_return_R` ([§19](#19-execution-cost-assumptions)) | `ACTIONABLE` | `> 0.10R` |
| 5 | Ordinary directional accuracy | `CONFIRMED` episodes where `execution_terminal_return_R > 0` | `ACTIONABLE` | Reported only, **no threshold** — explicitly not a gate, per roadmap §H ("ordinary accuracy alone is not the promotion criterion"). |

All V2-v0, `rules_version`-participating, explicitly not empirically
proven. **Win rate is never the sole promotion criterion** — priority 5
above carries no gate at all, by design. `LATE`/`INVALIDATED_BEFORE_ENTRY`
episodes are never dropped from acceptance — they are exactly what lowers
priority 1's feasibility rate ([§26.1](#261-episode-population-definitions)),
which is how a family that is frequently late gets penalized rather than
having those episodes silently vanish from the evaluation.

---

## 28. Promotion criteria and levels

### 28.1 Hard fail conditions

Any of the following alone fails promotion, regardless of any other metric:

- Sample requirements ([§26](#26-acceptance-sample-requirements)) not met (aggregate or per-family, as applicable).
- Mean `execution_cost_adjusted_return_R <= 0` — a non-positive cost-adjusted expectancy is an unconditional fail, independent of accuracy or MFE.
- Median `execution_MAE_R > 1.0` — exceeding the risk-control threshold.
- Actionable-entry feasibility rate `< 0.60` — a setup that's "usually right" but consistently too late to act on does not qualify (directly implementing the roadmap's stated rejection of that failure mode).

### 28.2 Promotion levels

**Two evidence sources, kept explicitly distinct (amended — closes a
replay-only promotion gap).** An earlier draft's level requirements were
satisfiable purely from **historical replay/backtest** evidence
([§20](#20-replay--backtest-correctness)), which left open the possibility
of reaching `USER_FACING_ELIGIBLE` — the level that authorizes real
notifications — without a single live decision ever having been observed.
That is not acceptable: the roadmap requires V2 to earn promotion through
**parallel shadow** evaluation before any user-facing behavior
(`docs/FORECASTING_ROADMAP.md` §I stage 10, `V2_PRODUCT_CONTRACT.md` §11).
This document now distinguishes the two evidence sources explicitly:

```text
historical replay/backtest evidence   — produced by §20's replay methodology,
                                          run over already-elapsed history
live parallel-shadow evidence         — produced by the live decision path
                                          actually running forward in real time,
                                          exactly as it would for a user-facing
                                          notification, but not yet notifying
```

Historical replay evidence **is** sufficient to reach `SHADOW_ELIGIBLE` —
that is precisely what authorizes starting the live parallel-shadow run in
the first place. It is **not** sufficient, on its own, to reach
`USER_FACING_ELIGIBLE`.

```text
RESEARCH_ONLY        -> SHADOW_ELIGIBLE       -> USER_FACING_ELIGIBLE       (-> V1_RETIRABLE, separate)
```

| Level | Requirement | What it authorizes |
|---|---|---|
| `RESEARCH_ONLY` | Default — code exists and produces persisted episodes/outcomes. No gating. | Internal analysis only. No shadow run, no notifications. |
| `SHADOW_ELIGIBLE` | Aggregate sample minimums met ([§26](#26-acceptance-sample-requirements)), from historical replay and/or live evidence. | Parallel shadow evaluation (`docs/FORECASTING_ROADMAP.md` §I, stage 10) — internally computed, not user-visible. This is precisely how the metric hierarchy in [§27](#27-acceptance-metric-hierarchy) *and* the live-shadow requirement below get evaluated; passing either is not a precondition of reaching this level. |
| `USER_FACING_ELIGIBLE` | **Both, evaluated per setup family, against that family's OWN population — never against the aggregate as a substitute** (amended, [§28.2's per-family gate](#282-promotion-levels) below): (a) the full acceptance metric hierarchy ([§27](#27-acceptance-metric-hierarchy)) passes over **that family's own** historical/replay sample meeting `MIN_COMPLETED_EPISODES_PER_FAMILY` ([§26](#26-acceptance-sample-requirements)), **and** (b) the live-shadow evidence requirement ([§28.2a](#282a-live-shadow-evidence-requirement)) is independently satisfied, also computed from **that family's own** live-shadow-only population. A family failing either — including a family with excellent historical replay metrics but insufficient live-shadow evidence, **or** a family whose own historical metrics fail despite the aggregate V2 sample passing and the other families performing well — stays `SHADOW_ELIGIBLE`. | User-facing V2 notifications for the qualifying family/families only. |
| `V1_RETIRABLE` | A **separate, explicit decision** comparing V2 against V1 on overlapping calendar periods, using only metrics genuinely comparable between the two ([§28.3](#283-v1-comparison)). Not automatic on reaching `USER_FACING_ELIGIBLE`. | V1 Telegram delivery may be paused/retired — requires its own explicit PR/deployment action, exactly as `docs/FORECASTING_ROADMAP.md` §C already states. |

No level above is reached automatically by finishing implementation. **No
production/notification action is authorized by this document** — every
transition above requires a subsequent, explicit human decision.

**Per-family promotion gate (re-amended — closes an aggregate-substitution
gap).** An earlier draft's `USER_FACING_ELIGIBLE` wording required "the
full acceptance metric hierarchy passes over **the aggregate sample**" for
part (a), combined with a **per-family** live-shadow requirement for part
(b). That shape allows a historically poor setup family to reach
`USER_FACING_ELIGIBLE` by riding on the other families' good aggregate
performance — e.g. the aggregate V2 sample clears every §27 threshold
because `COMPRESSION_BREAKOUT` and `TREND_PULLBACK` are excellent, while
`CONFIRMED_BREAKOUT`'s own historical metrics are actually poor; under the
old wording, `CONFIRMED_BREAKOUT` could still reach `USER_FACING_ELIGIBLE`
purely because it separately satisfied its own live-shadow minimum. That is
not acceptable — a setup family's own historical performance must stand on
its own. Both (a) and (b) are now evaluated **per family, against that
family's own population, with no aggregate substitution for either**:

```text
For setup family F to reach USER_FACING_ELIGIBLE, BOTH of the following
MUST independently hold for F specifically:

(a) Historical/replay gate for F:
    - F has >= MIN_COMPLETED_EPISODES_PER_FAMILY completed episodes (§26)
      in its own historical/replay population;
    - the full §27 acceptance metric hierarchy passes when computed ONLY
      over F's own historical/replay population (never the aggregate
      V2-wide population as a stand-in).

(b) Live-shadow gate for F ([§28.2a](#282a-live-shadow-evidence-requirement)):
    - F has >= LIVE_SHADOW_MIN_CONFIRMED_EPISODES_PER_FAMILY live-shadow
      episodes over >= LIVE_SHADOW_MIN_CALENDAR_DAYS;
    - the full §27 acceptance metric hierarchy passes when computed ONLY
      over F's own live-shadow-only population.

The aggregate V2-wide population (§26/§27 computed over all families
combined) MAY still be reported and MAY serve as an additional global
health gate (e.g. "is V2 as a whole minimally viable at all") — but it
MUST NOT substitute for, or be averaged into, any individual family's own
gates above. A family failing either (a) or (b) on its OWN population stays
SHADOW_ELIGIBLE, even if the aggregate V2 population passes and the other
two families are excellent.
```

**Normative promotion vector (aggregate cannot rescue a failing family):**

```text
Aggregate V2 population (all 3 families combined): passes every §26 sample
    minimum and every §27 acceptance metric threshold.
TREND_PULLBACK's OWN historical/replay population: fails §27 priority 2
    (median execution_MAE_R = 1.4 > 1.0) — its own metrics do not pass,
    even though the aggregate (dominated by the other two families' larger,
    better-performing samples) does.
TREND_PULLBACK's live-shadow sample: passes every LIVE_SHADOW_MIN_* minimum
    and every §27 threshold computed over that live-shadow-only population.

=> TREND_PULLBACK is NOT USER_FACING_ELIGIBLE — gate (a) failed on TREND_
   PULLBACK's own historical population, and passing the aggregate instead
   of TREND_PULLBACK's own population is exactly the substitution this
   amendment forbids. TREND_PULLBACK remains SHADOW_ELIGIBLE regardless of
   its live-shadow gate (b) having passed, and regardless of how well
   COMPRESSION_BREAKOUT/CONFIRMED_BREAKOUT perform. See
   [§29.14a](#2914a-promotion-per-family-gate-aggregate-cannot-rescue-a-failing-family-vector)
   for the full worked vector, and
   [§29.14](#2914-promotion-live-shadow-requirement-vector) for the
   companion live-shadow-only failure case.
```

### 28.2a Live-shadow evidence requirement

An explicit, deliberately **smaller** V2-v0 minimum than the full
historical sample ([§26](#26-acceptance-sample-requirements)) — this is an
**engineering promotion safety gate**, not a claim of statistical proof,
and it exists specifically so `USER_FACING_ELIGIBLE` cannot be reached from
replay alone:

```text
LIVE_SHADOW_MIN_CALENDAR_DAYS               = 30    # vs. 60 for the full historical sample
LIVE_SHADOW_MIN_CONFIRMED_EPISODES_AGGREGATE = 40    # vs. 100
LIVE_SHADOW_MIN_CONFIRMED_EPISODES_PER_FAMILY = 10   # vs. 30
```

`CONFIRMED` here uses the exact same population definition as
[§26.1](#261-episode-population-definitions) — the only difference is that
every episode counted **MUST** have been produced by the live decision
path actually running forward, using the exact live data path
([§20](#20-replay--backtest-correctness)'s "no more favorable data path
than live" rule applies symmetrically here — a live-shadow episode MUST
NOT secretly benefit from information a genuinely live run wouldn't have
had, and MUST NOT be a replayed/backtested episode relabeled as live).

**Additional requirements for `USER_FACING_ELIGIBLE`, beyond the sample
minimums above:**

- **No correctness/reliability blocker.** No unresolved systematic
  fail-closed anomaly (e.g. a persistent spike in `UNAVAILABLE`/`REJECTED`
  decisions indicating a broken data path, [§21](#21-failure--fail-closed-rules))
  during the live-shadow evaluation window. This is a qualitative
  operational review gate, not a numeric threshold — consistent with every
  other promotion transition in this document requiring an explicit human
  decision, not an automatic one.
- **Acceptance metrics computed from the live-shadow sample itself.** The
  full acceptance metric hierarchy ([§27](#27-acceptance-metric-hierarchy))
  is evaluated **against the live-shadow-only population** meeting the
  minimums above, in addition to (not instead of) that same family's own
  historical/replay population ([§28.2](#282-promotion-levels)'s per-family
  gate) — both must independently pass, both computed from **that specific
  family's own data**, never from the aggregate V2-wide population as a
  substitute for either.

**A family without enough live-shadow evidence remains non-user-facing even
if its historical replay looks excellent** — this is the explicit,
intended consequence of this gate, not an edge case to work around.
`V1_RETIRABLE` ([§28.3](#283-v1-comparison)) remains a still-separate,
later decision, unaffected by this gate beyond depending on
`USER_FACING_ELIGIBLE` having been reached first.

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

### 29.4 Signed percentile direction vector

Demonstrates the [§4.1](#41-normalized-evidence-primitive-used-throughout-47)
correction directly, using the exact example from the amendment that
identified the original bug:

```text
Case A: raw value positive, low percentile rank
  price_move_pct_median = +0.20%, percentile_rank = 0.10
  v = +0.20 > 0  =>  normalized_evidence = max(0, 2*0.10 - 1) = max(0, -0.80) = 0.0
  Result: WEAK bullish evidence (zero strength), NEVER bearish.
  (The pre-amendment formula computed 2*0.10-1 = -0.80 — wrongly bearish.
   This case is exactly what the amendment forbids from recurring.)

Case B: raw value negative, high percentile rank
  funding_rate = -0.0001 (mild negative), percentile_rank = 0.90
  v = -0.0001 < 0  =>  normalized_evidence = -max(0, 1 - 2*0.90) = -max(0, -0.80) = -0.0
  Result: WEAK bearish evidence (zero strength), NEVER bullish.

Case C: raw value strongly positive, high percentile rank (contrast — evidence should be strong)
  price_move_pct_median = +0.80%, percentile_rank = 0.95
  v > 0  =>  normalized_evidence = max(0, 2*0.95 - 1) = max(0, 0.90) = 0.90
  Result: STRONG bullish evidence, correctly signed and strongly weighted.

Case D: raw value exactly zero
  price_move_pct_median = 0.0 (genuine flat bucket)
  v == 0  =>  normalized_evidence = 0.0   (not UNAVAILABLE — a real measured flat value)
```

In every case, `sign(normalized_evidence)` matches `sign(v)` or is exactly
`0.0` — never the opposite sign of `v`. This is the concrete "raw price
positive + low percentile MUST NOT become bearish" / "raw price negative +
high percentile MUST NOT become bullish" pair the amendment requires,
worked with real numbers.

### 29.5 OI confirmation vectors

Demonstrates [§4.2](#42-4h-regime)'s corrected, symmetric OI treatment —
rising OI confirms **either** direction; falling OI opposes **either**
direction; OI never independently picks LONG vs. SHORT; and (re-amended)
that a same-signed OI reading with a rank on the *wrong* side of its own
history produces weak/zero strength, never strong strength:

```text
Vector 1 — bullish price + rising OI, upper-tail rank (confirms, strongly):
  price_evi = +0.55 (candidate direction: BULLISH), agreement = 0.80
  oi_raw = +2.1% (rising), oi_rank = 0.92, oi_agreement = 0.85
  oi_strength = max(0, 2*0.92 - 1) = max(0, 0.84) = 0.84
  oi_confirmation = +0.84*0.85 = +0.714   (rising OI => positive, regardless of price direction)
  veto check: oi_confirmation <= REGIME_OI_VETO(-0.40)? +0.714 <= -0.40 is FALSE => no veto
  => regime = BULLISH_TRENDING (rising OI confirmed, did not veto)

Vector 2 — bearish price + rising OI, upper-tail rank (ALSO confirms — the required symmetry):
  price_evi = -0.55 (candidate direction: BEARISH), agreement = 0.80
  oi_raw = +2.1% (rising — SAME raw OI reading as Vector 1), oi_rank = 0.92, oi_agreement = 0.85
  oi_strength = 0.84 (identical computation — oi_confirmation does not read price_evi at all)
  oi_confirmation = +0.714   (rising OI => positive, SAME sign as Vector 1, despite opposite price direction)
  veto check: +0.714 <= -0.40 is FALSE => no veto
  => regime = BEARISH_TRENDING (rising OI ALSO confirmed the bearish anchor)
  This is the required invariant: the identical rising-OI reading confirmed
  BOTH a bullish anchor (Vector 1) and a bearish anchor (Vector 2) — OI
  never independently selected a direction; price_evi's own sign did.

Vector 3 — falling OI, lower-tail rank, opposes either anchor (veto):
  price_evi = +0.55 (candidate direction: BULLISH), agreement = 0.80
  oi_raw = -1.8% (falling), oi_rank = 0.08, oi_agreement = 0.90
  oi_strength = max(0, 1 - 2*0.08) = max(0, 0.84) = 0.84
  oi_confirmation = -0.84*0.90 = -0.756   (falling OI => negative)
  veto check: -0.756 <= -0.40 is TRUE => VETOED
  => regime = NON_DIRECTIONAL (price alone cleared REGIME_TREND_THRESHOLD,
     but falling OI vetoed the trend call)
  Symmetric case (bearish price + the same falling OI) would ALSO be
  vetoed — falling OI opposes whichever anchor price proposes, never just one side.

Vector 4 — weak positive OI, LOW rank (bug-repro: must be weak/zero
confirmation, not strong). This is the exact case the amendment fixes —
under the prior, incorrect `oi_magnitude = 2*|oi_rank-0.5|*oi_agreement`
formula, this vector produced `2*|0.10-0.5| = 0.80` (reported as STRONG
confirmation, which was wrong):
  oi_raw = +0.10% (rising, but a small/weak move), oi_rank = 0.10
    (this bucket's OI change ranks in the bottom decile of its own history
    — i.e. RISING OI THAT IS UNUSUALLY SMALL, not unusually large),
    oi_agreement = 0.85
  oi_strength = max(0, 2*0.10 - 1) = max(0, -0.80) = 0.0   (correct: a rising
    move that ranks in the LOWER half of its history is not an extreme
    rising move, so it must not be reported as strong)
  oi_confirmation = +0.0*0.85 = 0.0   (weak/zero confirmation — CORRECTED
    from the prior formula's erroneous +0.68)
  => rising OI still confirms in sign (>= 0), but contributes no strength —
     matches "positive OI + lower-half rank -> weak/zero confirmation."

Vector 5 — strong negative OI, HIGH rank (symmetric bug-repro: must be
weak/zero opposition, not strong):
  oi_raw = -0.10% (falling, but a small/weak move), oi_rank = 0.90
    (this bucket's OI change ranks in the top decile — i.e. FALLING OI
    THAT IS UNUSUALLY SMALL/SHALLOW relative to typically deeper declines
    in its own history), oi_agreement = 0.85
  oi_strength = max(0, 1 - 2*0.90) = max(0, -0.80) = 0.0
  oi_confirmation = -0.0*0.85 = 0.0   (weak/zero opposition, not strong)
  => falling OI still opposes in sign (<= 0), but contributes no strength —
     matches "negative OI + upper-half rank -> weak/zero opposition."
```

**Normative invariant vectors (exhaustive quadrant, re-stated for
traceability):**

```text
positive OI + upper-tail rank  -> strong confirmation   (Vector 1/2, oi_rank=0.92)
positive OI + lower-half rank  -> weak/zero confirmation (Vector 4, oi_rank=0.10)
negative OI + lower-tail rank  -> strong opposition       (Vector 3, oi_rank=0.08)
negative OI + upper-half rank  -> weak/zero opposition    (Vector 5, oi_rank=0.90)
```

### 29.6 Setup vectors

**Valid `TREND_PULLBACK` (LONG), full `EARLY_SIGNAL → CONFIRMED` lifecycle
(`T_detect`/`T_confirm`, [§7.1](#71-trend_pullback)).** 4h regime
`BULLISH_TRENDING` (`price_evi=0.55`, `agreement=0.80`,
`oi_confirmation=+0.20` — no veto, per [§4.2](#42-4h-regime)'s corrected OI
treatment). 1h bias `BULLISH` (`bias_evi=0.30`, `agreement=0.75`).
Directional context: both regime and bias already align with the candidate
`LONG` direction by precondition ([§7.1](#71-trend_pullback) requires exact
agreement, stricter than the
[§7.0b](#70b-directional-context-compatibility-gate-amended--closes-a-countertrend-gap)
gate used by the breakout families). `trend_leg_extreme (high) = 65,000`.

```text
T1 (15m decision boundary = T_detect; also a 5m boundary):
   close(B15_detect) = 64,350.
   retracement_pct = (65,000-64,350)/65,000*100 = 1.0%;
   RANGE_PROXY_pct(15m,14,B15_detect) = 0.4%; valid range = [0.20%,1.20%] -> valid pullback.
   pullback_extreme_low = 64,300 (deepest close reached during the retracement).
   protection_buffer(15m,B15_detect,64,350) ≈ max(3*tick, 64,350*0.4%*0.5) ≈ 128.7
      (tick_size=0.1 for illustration).
   invalidation_price ≈ 64,300 - 128.7 = 64,171.3.
   B5_detect = selected_bucket(5m, T1); bucket_ts(B5_detect) == T1 (a 15m
      boundary always coincides with a 5m boundary). B5_detect's own close
      (64,350) ALREADY satisfies the 5m resumption trigger on its own
      (price_move_pct_median sign +1, price_direction_agreement =
      0.75 >= 2/3) -- but per the T_confirm > T_detect rule above this does
      NOT confirm: bucket_ts(B5_detect) == T_detect, not strictly later, so
      it can never itself serve as the confirming bucket.
   => EARLY_SIGNAL at T1. detection_timestamp = T1.
      Entry zone (EARLY_SIGNAL entry-zone rule above): [pullback_extreme_low, close(B15_detect)]
                                        = [64,300, 64,350].

T2 (the very next 5m decision boundary, B5' with bucket_ts(B5') =
    T1 + 5m > bucket_ts(B5_detect)):
   B5' closes at 64,350 (price steady). price_move_pct_median sign +1,
   price_direction_agreement = 0.75 >= 2/3 on B5' -> resumption trigger
   holds on this later, distinct bucket.
   confirmation_close_price = close(B5') = 64,350.
   => CONFIRMED at T2 (T2 = T1 + 5m > T1, strictly).
      Entry zone updates one final time and freezes (CONFIRMED entry-zone
      rule above): [64,300, 64,350] (numerically unchanged here since price
      was steady between T1 and T2 -- the zone still legitimately
      re-derives from confirmation_close_price, not from the stale
      EARLY_SIGNAL value).
      planned_risk_distance = |64,350 - 64,171.3| ≈ 178.7 > MIN_VALID_PLANNED_RISK -> valid.
```
→ `TREND_PULLBACK`, `LONG`, `EARLY_SIGNAL` at `T1` (zone `[64,300,
64,350]`, `invalidation_price ≈ 64,171.3`), `CONFIRMED` at `T2 = T1 + 5m`
(zone frozen at `[64,300, 64,350]`) — this is the precise case the
`T_confirm > T_detect` rule guards against: `B5_detect` already qualified
for resumption at `T1` itself, yet the episode is **not** confirmed until
the next, distinct 5m bucket at `T2`.

**Rejected `TREND_PULLBACK` (invalid retracement magnitude — no candidate
ever formed).** Same 4h/1h context, but `retracement_pct = 1.8%` against
the same `[0.20%,1.20%]` valid range → exceeds `PULLBACK_MAX_MULT` →
classified as trend failure, not a pullback → **no candidate formed**
(never reaches `EARLY_SIGNAL`).

**`TREND_PULLBACK` expiry vector (`EARLY_SIGNAL` formed, resumption never
arrives).** Same `EARLY_SIGNAL` at `T1` as the valid vector above (valid
retracement, `detection_timestamp = T1`, `B5_detect` at `T1` already
showing a matching-sign move that — per the `T_confirm > T_detect` rule —
cannot itself confirm). Over the following `PULLBACK_MAX_AGE(8×15m)`
closed 15m buckets, no 5m bucket strictly after `B5_detect` ever satisfies
the resumption trigger (`price_move_pct_median` sign matching **and**
`price_direction_agreement >= 2/3`) — price chops sideways without a
qualifying resumption close. The entry zone may still update
pre-confirmation at each later 15m boundary per the pre-confirmation
update rule above, but no `T_confirm` is ever reached. At
`T1 + PULLBACK_MAX_AGE`
→ `EXPIRED` ([§13](#13-lifecycle-transition-semantics)). The episode
**did** exist from `T1` onward (`EARLY_SIGNAL`), so this is a real
lifecycle transition with a recorded outcome, not a silent non-creation.

**Valid `COMPRESSION_BREAKOUT` (SHORT), full `EARLY_SIGNAL → CONFIRMED`
lifecycle.** Within the 16-bucket `COMPRESSION_LOOKBACK` ending at `B15`,
exactly one maximal run of compressed buckets qualifies: buckets `b[9]`
through `b[15]` (the 7 most recent), `compression_score(15m,30d,B15) =
0.82 >= 0.75` throughout. Compression-window selection
([§7.2](#72-compression_breakout)): one qualifying run of length
`7 >= COMPRESSION_MIN_DURATION(6)` → trivially selected (the "most recent
qualifying run" rule has nothing else to choose among here — see the
dedicated multi-run vector below for the disambiguating case) →
`compression_start_bucket = b[9]`, `compression_end_bucket = b[15] = B15`,
`compression_length = 7`. `range_low = HTF_low`-derived over
`[compression_start_bucket, compression_end_bucket]` `= 63,800`
([§7.0a](#70a-structural-highlow-derivation-amended--corrects-a-nonexistent-field-error)).
4h regime `NON_DIRECTIONAL`, 1h bias `NEUTRAL_NOT_ESTABLISHED` →
`directional_context_gate(SHORT, ...) = ACCEPT` (neither is an established
opposite, [§7.0b](#70b-directional-context-compatibility-gate-amended--closes-a-countertrend-gap)) —
this is the "valid breakout with neutral HTF context" case,
`V2_PRODUCT_CONTRACT.md` §4.2's explicitly permitted compression-without-firm-bias
scenario.

```text
T1 (bucket 1): reference exchange closes at 63,740 < 63,800 (range_low).
   price_direction_agreement(5m) = 0.80 >= 2/3. taker_delta_notional_usd_sum
   negative (sell-side, matching SHORT). directional_context_gate = ACCEPT.
   => EARLY_SIGNAL at T1. detection_timestamp = T1. Entry zone established:
      [range_low - buffer, range_low] ≈ [63,670, 63,800].

T2 (bucket 2, next closed 5m bucket): reference exchange closes at 63,710
   (strictly < 63,800 — same side as T1, no intervening invalidating close).
   => later confirming close reached => CONFIRMED at T2.
      invalidation_price = 63,800 + protection_buffer(...) ≈ 63,930.
```
→ `COMPRESSION_BREAKOUT`, `SHORT`, `EARLY_SIGNAL` at T1, `CONFIRMED` at T2.

**`COMPRESSION_BREAKOUT` false-break vector (re-entry case).** Same
`EARLY_SIGNAL` (`SHORT`, broken below `range_low = 63,800`) as above at T1.
At T2 (before a confirming close arrives), the reference exchange instead
closes at `63,850`. Under the direction-aware rule: `SHORT` holds iff
`close <= range_low (63,800)`; `63,850 > 63,800` → does **not** hold →
`INVALIDATED` at T2, never reaching `CONFIRMED`. (This is also, incidentally,
back inside the compression range — but the rule that fires is "the
breakout side no longer holds," not "price re-entered the range"; see the
overshoot vector below for why that distinction matters.) The episode
existed (it was `EARLY_SIGNAL` from T1), so this is a real lifecycle
transition, not a silent non-creation.

**`COMPRESSION_BREAKOUT` false-break vector (overshoot case — the exact
gap the amendment fixes).** Same `EARLY_SIGNAL` (`SHORT`, `range_low =
63,800`, `range_high = 64,100` for this vector) as above at T1. At T2, a
violent reversal closes at `64,150` — **beyond `range_high`**, i.e. it blew
straight through the entire compression range to the opposite side, not
merely back inside it. Under the **prior** "inside range" predicate
(`range_low < close < range_high`, i.e. `63,800 < 64,150 < 64,100`), this
is **FALSE** (`64,150` is not `< 64,100`) — the old rule would have
incorrectly let this episode continue toward `CONFIRMED` despite an even
stronger repudiation than a simple re-entry. Under the **corrected**
direction-aware rule: `SHORT` holds iff `close <= range_low (63,800)`;
`64,150 > 63,800` → does not hold → `INVALIDATED` at T2. The one-sided
check catches this case exactly because it never asks "is price back
inside the range," only "does the breakout side still hold."

**`COMPRESSION_BREAKOUT` boundary-equality hold vector (later qualifying
close within deadline).** Same `EARLY_SIGNAL` (`SHORT`, broken
below `range_low = 63,800`) as above at T1.

```text
T2 (next closed 5m bucket): reference exchange closes at exactly 63,800
   (boundary equality). Neither confirms (CONFIRMED requires a close
   strictly beyond the boundary, i.e. strictly < 63,800 for SHORT) nor
   invalidates (SHORT holds iff close <= range_low, and 63,800 <= 63,800).
   => neutral HOLD at T2 -- consumes one bucket of CONFIRMATION_MAX_AGE(3x5m),
      episode remains EARLY_SIGNAL.

T3 (next closed 5m bucket, still within CONFIRMATION_MAX_AGE): reference
   exchange closes at 63,720 (strictly < 63,800, no intervening
   invalidating close between T1 and T3 -- T2's boundary-equality close
   does not count as one).
   => later confirming close reached => CONFIRMED at T3.
```
→ `COMPRESSION_BREAKOUT`, `SHORT`, `EARLY_SIGNAL` at T1, neutral hold at
T2, `CONFIRMED` at T3 — demonstrating the confirming close is not required
to be immediately adjacent to `EARLY_SIGNAL`, only to arrive within
`CONFIRMATION_MAX_AGE` with no intervening invalidating close.

**`COMPRESSION_BREAKOUT` expiry vector.** Same `EARLY_SIGNAL` at T1. Over
the next `CONFIRMATION_MAX_AGE(3×5m)` closed buckets, price oscillates
exactly at `63,800` (boundary equality, neutral hold each time) without
ever closing strictly beyond it and without closing back inside the range
either → deadline elapses → `EXPIRED`.

**Rejected `COMPRESSION_BREAKOUT` (insufficient compression duration).**
`compression_score` reaches `0.75` for only `4 < COMPRESSION_MIN_DURATION(6)`
consecutive buckets before dropping below threshold → compression never
qualifies as sustained → **no episode is ever created**, even though a
later strong directional 5m move occurs — a big move alone, without the
sustained-compression precondition, never becomes `COMPRESSION_BREAKOUT`.

**`COMPRESSION_BREAKOUT` multi-run window-selection vector (deterministic
disambiguation, [§7.2](#72-compression_breakout)).** Within the 16-bucket
`COMPRESSION_LOOKBACK` ending at `B15`, compression status by bucket index
(`b[0]` oldest .. `b[15] = B15` most recent):

```text
b[0]..b[5]:   compressed (score >= 0.75)   -> a maximal run of length 6, qualifies
b[6]:         NOT compressed                -> breaks the first run
b[7]..b[13]:  compressed (score >= 0.75)   -> a maximal run of length 7, qualifies
b[14]..b[15]: NOT compressed

Two DISTINCT qualifying runs exist: [b[0]..b[5]] (length 6) and
[b[7]..b[13]] (length 7).

Selection: "most recent qualifying run" -> the run ending at b[13] is more
recent than the run ending at b[5] -> [b[7]..b[13]] is selected, REGARDLESS
of the other run being shorter.
  compression_start_bucket = b[7]
  compression_end_bucket   = b[13]
  compression_length       = 7

range_high/range_low are computed ONLY over [b[7], b[13]] — buckets
b[0]..b[5] (the earlier, non-selected qualifying run) contribute NOTHING
to the structural range, even though they also satisfied
COMPRESSION_MIN_DURATION on their own.
```

This resolves all three ambiguous shapes the amendment was written to
cover: "one run of 6 and a later run of 7" (exactly this vector — the later
run wins regardless of the shorter run's earlier qualification); "one
continuous run of 9" (a single maximal run — no ambiguity, the whole run of
9 becomes the window per step 6's "full selected run" rule, not a truncated
6-bucket slice); and "two distinct runs of exactly 6" (the more recent of
the two wins by the same "most recent end bucket" rule, with no need for
the length or latest-end-bucket tiebreakers, since two distinct maximal
runs can never share an end bucket).

**Valid `CONFIRMED_BREAKOUT` (LONG), full `EARLY_SIGNAL → CONFIRMED`
lifecycle, aligned HTF context.** `resistance_level = HTF_high`-derived
`= 66,200` (48×1h lookback,
[§7.0a](#70a-structural-highlow-derivation-amended--corrects-a-nonexistent-field-error)).
4h regime `BULLISH_TRENDING`, 1h bias `BULLISH` → `directional_context_gate(LONG,
...) = ACCEPT` (aligned, not merely non-opposing) — this is the "valid
breakout with aligned HTF context" case.

```text
T1: reference exchange closes at 66,240 (beyond resistance_level).
   directional_context_gate = ACCEPT.
   => EARLY_SIGNAL at T1. detection_timestamp = T1.

T2 (next closed 5m bucket, within CONFIRMATION_MAX_AGE(8×5m)):
   reference exchange closes at 66,290 (strictly beyond resistance_level,
   no intervening invalidating close between T1 and T2).
   => later confirming close reached => CONFIRMED at T2.
      invalidation_price = 66,200 - protection_buffer(1h,...) ≈ 66,050.
```
→ `CONFIRMED_BREAKOUT`, `LONG`, `EARLY_SIGNAL` at T1, `CONFIRMED` at T2.
Entry zone `[66,200, 66,200+buffer] ≈ [66,200, 66,350]`.

**`CONFIRMED_BREAKOUT` false-break vector (replaces the earlier
"rejected, never reaches `EARLY_SIGNAL`" framing).** Same `EARLY_SIGNAL` at
T1 as above. At T2, the reference exchange instead closes at `66,150`
(back below `resistance_level` — undoing the break) → false-break re-entry
→ `INVALIDATED` at T2. The episode **did** exist from T1 onward
(`EARLY_SIGNAL`, `detection_timestamp = T1`) — this corrects the earlier
draft's inconsistent claim that a failed second close meant the episode
"never reached `EARLY_SIGNAL`."

**Rejected `CONFIRMED_BREAKOUT` (countertrend — established opposite HTF
context).** Same breakout mechanics as the valid vector above
(`resistance_level = 66,200`, closing beyond it), but 4h regime is
`BEARISH_TRENDING` (`price_evi = -0.62`, `agreement = 0.85` — firmly
established) and candidate direction is `LONG` →
`directional_context_gate(LONG, ...)`: regime is `BEARISH_TRENDING` and
opposes `LONG` → **REJECT**. → **No episode is created**, even though the
breakout mechanics themselves were satisfied — this is the "rejected
breakout against firmly established HTF context" case, directly enforcing
`V2_PRODUCT_CONTRACT.md` §4.4's countertrend prohibition, which an earlier
draft of this document did not gate for `COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT`
at all.

### 29.7 Countertrend-context gate vectors

Consolidates the four required cases from
[§7.0b](#70b-directional-context-compatibility-gate-amended--closes-a-countertrend-gap)
in one place (the first three also appear inline above with full detector
mechanics):

```text
1. Valid breakout, NEUTRAL/non-established HTF context (allowed — a REAL
   measured neutral reading, not missing data):
   regime = NON_DIRECTIONAL, bias = NEUTRAL_NOT_ESTABLISHED
   => directional_context_gate(either direction) = ACCEPT
   (§29.6's valid COMPRESSION_BREAKOUT vector)

2. Valid breakout, ALIGNED HTF context (allowed):
   regime = BULLISH_TRENDING, bias = BULLISH, candidate = LONG
   => directional_context_gate(LONG) = ACCEPT
   (§29.6's valid CONFIRMED_BREAKOUT vector)

3. Rejected breakout, ESTABLISHED OPPOSITE HTF context (forbidden — countertrend):
   regime = BEARISH_TRENDING (firmly established), candidate = LONG
   => directional_context_gate(LONG) = REJECT, no episode created
   (§29.6's rejected CONFIRMED_BREAKOUT vector)

4. Rejected breakout, UNAVAILABLE 1h bias (forbidden — data-availability,
   NOT the same rejection reason as case 3, and NOT the same outcome as
   case 1's NEUTRAL_NOT_ESTABLISHED despite both being "absence of a firm
   bias" in casual language):
   regime = NON_DIRECTIONAL (or even BULLISH_TRENDING aligned with candidate),
   bias = UNAVAILABLE (the 1h bias detector could not compute a reading —
     e.g. consensus coverage below minimum, or percentile confidence tier
     below "building", §4.1/§5.2), candidate = LONG
   => directional_context_gate(LONG): bias == UNAVAILABLE => REJECT
      (data-availability failure) — no episode created, even though regime
      alone would have permitted or even supported the direction.
   Contrast with case 1: had bias been a genuinely computed
   NEUTRAL_NOT_ESTABLISHED instead of UNAVAILABLE, the identical regime
   would have ACCEPTed. The only difference between ACCEPT and REJECT here
   is whether the 1h bias detector actually produced a measurement —
   exactly the distinction this amendment exists to enforce.
```

### 29.8 Confidence monotonicity vector

See [§8](#8-model-confidence-semantics)'s worked example: `model_confidence`
computed at `0.615` with all 5 components available, and `0.595` — strictly
lower, never higher — after `data_confidence` becomes `UNAVAILABLE`. The
general proof (removing a term from a sum of non-negative terms cannot
increase the sum) is stated there; this is the required "removing one
component cannot increase confidence" vector.

### 29.9 Lifecycle vector

```text
T1: TREND_PULLBACK LONG detected -> EARLY_SIGNAL
T2 (2 closed 5m buckets later): 5m confirmation criteria met -> CONFIRMED
    (entry zone frozen at this point, §9)
T3 (WEAKEN_BUCKETS=2 later): price_direction_agreement(5m) opposes
    direction for 2 consecutive closed 5m buckets -> WEAKENING
T4 (RECOVER_BUCKETS=1 later): opposing-agreement condition no longer holds
    -> CONFIRMED (recovery, §13.2a)
T5 (horizon elapses, 2h after T2 per §14): analytical_MFE_R (peak favorable
    excursion from confirmation_reference_price, normalized by
    planned_risk_distance, §18.2) reached 0.7 at some point during T2..T5
    (>= MIN_MFE_R_FOR_COMPLETION=0.5) -> COMPLETED. This holds regardless of
    this episode's lateness_status — see §29.11 for the same deterministic
    resolution on a LATE episode.
```

### 29.10 Reversal vector

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

### 29.11 Entry-feasibility vector

**`EARLY_SIGNAL` feasibility — eligible ([§15.2](#152-early_notification_feasibility)).**
Same `TREND_PULLBACK` `LONG` `EARLY_SIGNAL` as [§29.6](#296-setup-vectors)'s
valid vector: `detection_timestamp = T1`, entry zone `[64,300, 64,350]`,
`invalidation_price ≈ 64,171.3`.

```text
early_notification_reference_time = T1.
early_assumed_entry_time = T1 + 90s.
Sampled reference-exchange 1m close at/after early_assumed_entry_time: 64,360.
OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(...) ≈ 32.2
early_entry_zone_upper + OVERSHOOT_TOLERANCE = 64,350 + 32.2 = 64,382.2
64,360 <= 64,382.2 -> within tolerance. invalidation_price (64,171.3) not
   breached as of early_assumed_entry_time.
=> early-feasible = TRUE. The first EARLY_SIGNAL notification is sent,
   using exactly the EARLY_SIGNAL-time zone/invalidation/confidence/coverage
   (§16.1) -- never any later CONFIRMED-time value.
```

**`EARLY_SIGNAL` feasibility — suppressed ([§15.2](#152-early_notification_feasibility)).**
Same `EARLY_SIGNAL` as above (`T1`, zone `[64,300, 64,350]`,
`invalidation_price ≈ 64,171.3`), but price moves away from the zone
faster:

```text
Sampled reference-exchange 1m close at/after early_assumed_entry_time (T1+90s): 64,420.
early_entry_zone_upper + OVERSHOOT_TOLERANCE = 64,382.2 (same as above).
64,420 > 64,382.2 -> outside tolerance, moved away from the zone.
=> early-feasible = FALSE. The first EARLY_SIGNAL notification is
   suppressed as already late -- the episode is still created, stored, and
   evaluated exactly like any other (§17); it simply never produces the
   initial actionable notification. This has no effect on the later,
   independent CONFIRMED-time check (§15.1): if this same episode later
   reaches CONFIRMED and CONFIRMED's own feasibility check
   (using CONFIRMED-time inputs only) passes, the CONFIRMED notification
   fires normally regardless of the earlier suppression.
```

**`CONFIRMED` feasibility — infeasible/late ([§15.1](#151-confirmed_actionability_feasibility)).**

```text
CONFIRMED at T (TREND_PULLBACK LONG), entry_zone = [64,300, 64,350].
ASSUMED_NOTIFICATION_DELAY_S = 90 -> assumed_entry_time = T + 90s.
Sampled reference-exchange 1m close at/after assumed_entry_time: 64,410.
OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(...) ≈ 32.2
entry_zone_upper + OVERSHOOT_TOLERANCE = 64,350 + 32.2 = 64,382.2
64,410 > 64,382.2 -> INFEASIBLE / LATE. lateness_status = LATE.

=> The episode is analytically CONFIRMED and structurally sound (never
   invalidated), but is retained for research only (§17) — it MUST NOT
   generate an actionable notification, and MUST NOT count as a
   successful actionable V2 call in acceptance metrics' feasibility rate
   numerator (§27, priority 1). directional_return_pct/mfe_pct/mae_pct are
   still computed for it (against confirmation_reference_price, §17); its
   execution_MFE_R/execution_MAE_R/execution_terminal_return_R are
   undefined (no feasible_entry_price, §26.1) — it is excluded from the
   ACTIONABLE population but counted in CONFIRMED.

Lifecycle completion for this same LATE episode (re-amended — resolves what
was previously an undefined case, §13.2): planned_risk_distance was already
fixed at CONFIRMED (T), e.g. `planned_risk_distance ≈ 178.7` (§29.6's
TREND_PULLBACK vector). Suppose price later reaches a peak favorable
excursion of `mfe_pct_over_episode_life = +0.28%` against
`confirmation_reference_price = 64,350` before horizon end:

```text
analytical_MFE_R = 0.28/100 * 64,350 / 178.7 ≈ 1.008   (>= MIN_MFE_R_FOR_COMPLETION=0.5)
=> COMPLETED at horizon end — a deterministic terminal state, even though
   this episode's lateness_status is LATE and it has no execution_MFE_R at
   all. Lifecycle state never depended on whether a hypothetical delayed
   entry was feasible.
```

### 29.12 Acceptance-population vector

Demonstrates [§26.1](#261-episode-population-definitions)'s exact
denominators with a small concrete sample:

```text
Sample: 10 CONFIRMED TREND_PULLBACK episodes, all later terminal:
  6 ACTIONABLE (feasible entry reached)
  3 LATE (feasibility check failed, §15)
  1 INVALIDATED_BEFORE_ENTRY (invalidation reached before assumed_entry_time)

Sample-size count (§26, MIN_COMPLETED_EPISODES_*):        10  (all CONFIRMED, any lateness_status)
Actionable-entry feasibility rate (§27 priority 1):        6 / 10 = 0.60   (denominator = CONFIRMED = 10)
Missed/late rate:                                          4 / 10 = 0.40   (the 3 LATE + 1 INVALIDATED_BEFORE_ENTRY)
Median execution_MAE_R / median execution_MFE_R / mean execution_cost_adjusted_return_R:  computed over the 6 ACTIONABLE episodes only
                                                             (denominator = 6, NOT 10 — the 4 non-actionable
                                                             episodes have no feasible_entry_price and are
                                                             correctly excluded from this population, not
                                                             silently dropped from the sample as a whole)

An episode that was ALSO EARLY_SIGNAL for 3 other TREND_PULLBACK candidates
that never reached CONFIRMED (rejected/expired while still EARLY_SIGNAL) is
NOT counted anywhere above — those 3 are outside the acceptance sample
entirely (§26), reportable only as an informational, non-gating
candidate-rejection statistic.
```

### 29.13 Acceptance vector

```text
Sample: 120 completed CONFIRMED_BREAKOUT episodes over 65 calendar days
        (passes §26: >= 30 per-family, >= 60 days).

Directional accuracy: 68% of ACTIONABLE episodes have execution_terminal_return_R > 0.
    (Looks strong in isolation.)

But:
  actionable-entry feasibility rate = 0.52   (< 0.60 threshold, §27 priority 1, population = CONFIRMED)
  median execution_MAE_R = 1.35                (> 1.0 threshold, §27 priority 2, population = ACTIONABLE)
  mean execution_cost_adjusted_return_R = -0.05   (<= 0, §28.1 hard fail, population = ACTIONABLE)

=> PROMOTION FAILS for CONFIRMED_BREAKOUT despite the eye-catching 68%
   directional accuracy, because priority-1 feasibility, priority-2 MAE,
   and the cost-adjusted-expectancy hard-fail condition all fail. Per §27,
   ordinary accuracy alone was never the promotion criterion — this
   vector exists specifically to make that non-negotiable in a concrete
   case a future test can assert against.
```

### 29.14 Promotion (live-shadow requirement) vector

```text
CONFIRMED_BREAKOUT: historical replay over 90 days produces 150 CONFIRMED
episodes, passing every §26 sample minimum and every §27 acceptance metric
threshold computed over CONFIRMED_BREAKOUT's OWN historical/replay
population — by replay evidence alone, this family "looks" ready for
USER_FACING_ELIGIBLE.

Live parallel-shadow evaluation (§28.2a) has been running for only 12
calendar days with 6 live CONFIRMED episodes for this family — below
LIVE_SHADOW_MIN_CALENDAR_DAYS(30) and LIVE_SHADOW_MIN_CONFIRMED_EPISODES_PER_FAMILY(10).

=> NOT USER_FACING_ELIGIBLE for CONFIRMED_BREAKOUT, regardless of how
   strong the historical replay metrics are. §28.2's evidence-source
   distinction is explicit: replay evidence alone reaches SHADOW_ELIGIBLE
   (already true here) but MUST NOT, by itself, authorize user-facing
   notifications — the live-shadow minimum in §28.2a must be independently
   satisfied first, for this specific family.
```

### 29.14a Promotion (per-family gate, aggregate cannot rescue a failing family) vector

Demonstrates [§28.2](#282-promotion-levels)'s re-amended per-family gate —
the aggregate V2-wide population passing is **not** a substitute for a
family's own historical metrics:

```text
Aggregate V2 population (TREND_PULLBACK + COMPRESSION_BREAKOUT +
CONFIRMED_BREAKOUT combined): 340 CONFIRMED episodes, passes every §26
sample minimum and every §27 acceptance metric threshold — driven mostly by
COMPRESSION_BREAKOUT's and CONFIRMED_BREAKOUT's strong, larger samples.

TREND_PULLBACK's OWN historical/replay population (35 CONFIRMED episodes,
passes MIN_COMPLETED_EPISODES_PER_FAMILY(30)):
  median execution_MAE_R = 1.40   (> 1.0 threshold, §27 priority 2 — FAILS
    on TREND_PULLBACK's own population, even though the aggregate figure
    computed across all 340 episodes would have passed).

TREND_PULLBACK's live-shadow sample: 14 live CONFIRMED episodes over 32
calendar days — passes every LIVE_SHADOW_MIN_* minimum, and passes every
§27 threshold when computed over TREND_PULLBACK's live-shadow-only
population.

=> TREND_PULLBACK is NOT USER_FACING_ELIGIBLE. Gate (a) — the historical/
   replay gate — failed on TREND_PULLBACK's OWN population; passing
   live-shadow (gate (b)) does not compensate for that, and the aggregate
   V2 population passing does not either, because gate (a) is defined
   against that family's own population, never the aggregate. TREND_PULLBACK
   remains SHADOW_ELIGIBLE. COMPRESSION_BREAKOUT and CONFIRMED_BREAKOUT are
   each evaluated entirely independently on their own (a)/(b) gates and are
   unaffected by TREND_PULLBACK's result in either direction.
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
