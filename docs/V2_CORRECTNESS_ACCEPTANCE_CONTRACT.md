# V2 Correctness & Acceptance Contract

This document freezes **how V2 decisions are computed deterministically and
how V2 earns promotion.** **This document originated as the second and
final Stage 1 documentation PR (#29), written before any V2 implementation
existed** — at that time, "no V2 code exists after this PR" was literally
true. **Current repository status (updated by `#43`'s pre-Stage-6
amendments, not a rewrite of the original Stage 1 framing above):** Stage
2 (Multi-model Framework), Stage 3 (Multi-timeframe Alignment), Stage 4
(Context Engines), and Stage 5 (Setup Detectors) have since been
implemented and merged (`docs/FORECASTING_ROADMAP.md` §J) — this document
now also serves as the frozen target those merged stages conform to, and
that `#43`'s clean-room audit re-verified them against. **Executable Stage
6 (Episode State Machine) has NOT started** — pre-Stage-6 contract/code
hardening is the current phase (`docs/FORECASTING_ROADMAP.md` §J).
`v2.enabled` remains `false` throughout; V1 remains the running baseline.

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

- **Not a schema.** This PR itself adds no SQL, no migrations, no table
  creation, no Python dataclasses, no config YAML, no runtime code — every
  "table" shown below remains a Markdown illustration of a **logical
  record shape**, for clarity only, and this PR does not implement any of
  them. **Status update:** the Multi-model Framework implementation PRs
  (`docs/FORECASTING_ROADMAP.md` §I, stage 2) have since **merged** and do
  physically implement the `v2_episode_events` persistence boundary
  (`storage/stage2_schema.sql`, `analytics/forecasting_v2/events.py`) —
  but Stage 6's own episode-state-machine schema/runtime code
  (`episode_id`/`event_id` construction, the state-machine orchestration
  itself) remains **not yet implemented**, exactly as this bullet's "not a
  schema" scope claims for this document's own remaining illustrations.
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
semantic change to the Product Contract was required anywhere else — **at
the time §0.3 was originally written (PR #29).**

**Update (`#43`'s clean-room audit — this claim no longer holds without
qualification):** a genuine contradiction was subsequently found and
corrected. `V2_PRODUCT_CONTRACT.md` §4.3's timeframe-role table claimed
"`15m` forms the setup" for `CONFIRMED_BREAKOUT`, directly contradicting
this document's own already-frozen, already-implemented [§7.3](#73-confirmed_breakout)
design (a `1h` structural level, `4h`/`1h` directional-context gating, a
`5m` fresh-cross trigger — deliberately **no** `15m` formation role for
this family, per `§7.3`'s own text and
`analytics/forecasting_v2/confirmed_breakout.py`'s docstring). Since
`§7.3` was already implemented and merged (`#42`) with this deliberate
design, the Product Contract's wording was corrected to match the
intended/implemented design (`V2_PRODUCT_CONTRACT.md` §4.3, amended by
`#43`) rather than retrofitting an artificial `15m` gate into working
code. This is the one place besides `§5.2`'s `REVERSAL_CANDIDATE` pointer
where this document's own drafting process required a Product Contract
edit — both are recorded here for an accurate audit trail.

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

### 2.1a Atomic persistence of one logical decision boundary
(clean-room audit finding — implementation debt, not yet fixed)

**Finding.** `Database.insert_v2_episode_events` (`storage/db.py`)
correctly validates and serializes its entire input batch **before**
acquiring a connection (so a malformed row can never partially write) and
correctly uses `ON CONFLICT ... DO NOTHING` per row (so a retried batch
never double-inserts or overwrites). It does **not**, however, wrap the
batch's `INSERT`s in one explicit SQL transaction — each row is its own
`fetchval` call inside a loop over one acquired connection, so each row
commits independently. A single logical Stage 6 decision boundary can
legitimately need to persist **more than one** `V2EpisodeEvent` at once
(e.g. a lifecycle transition plus a `REVERSAL_CANDIDATE` cross-reference,
[§13.4](#134-same-boundary-orchestration-order) step 8; or an entry-zone
update alongside a confirmation). If the DB connection fails or the
process crashes after row `N-1` of such a batch commits but before row `N`
does, that one logical decision boundary is left **partially persisted**.

**Frozen correctness requirement (implementation in a future pre-Stage-6
persistence hardening PR, not `#43`):** all `V2EpisodeEvent` rows produced
by **one** logical Stage 6 decision boundary **MUST** commit atomically —
either all of them are durably persisted, or none are. A future
implementation satisfying this MAY do so via one explicit database
transaction wrapping the whole batch's inserts (the natural mechanism,
compatible with the existing `ON CONFLICT DO NOTHING` per-row
idempotency), or via an equivalent deterministic recovery model that
provably reconstructs the same final history after a retry. This document
freezes the **requirement**, not the physical mechanism, per
[§0.1](#01-what-this-document-is-not).

**Retry model, stated precisely (amended — a prior draft's explanation
wrongly implied individual rows commit independently even inside the
target atomic transaction).** Inside one genuinely atomic transaction,
rows do **not** independently commit one at a time — the three possible
outcomes are:

```text
failure before COMMIT:
    NO rows from the transaction persist -- the whole attempt is void.

COMMIT definitely succeeded:
    ALL rows from the transaction persist.

client loses the connection during/around COMMIT and the outcome is
genuinely uncertain (the client cannot tell whether COMMIT reached the
server):
    retrying the IDENTICAL, deterministically-derived batch is safe
    regardless of which of the two outcomes above actually happened --
    if the prior attempt committed fully, every row's ON CONFLICT DO
    NOTHING guard makes the retry a pure no-op (deterministic IDs, per
    below, are what make this guard effective); if the prior attempt
    rolled back / never committed, the retry performs the original
    insert normally.
```

There is no state in which some, but not all, of one atomic
transaction's rows are durably visible — "partial persistence" is exactly
the failure mode atomicity rules out, not a residual case retry logic
needs to reason about row-by-row.

**Related, equally frozen requirement: deterministic, reproducible
`episode_id`/`event_id` — semantic dimensions frozen now (amended — a
prior draft's example wrongly included `execution_stream`/`(run_kind,
run_id)` inside the SEMANTIC identity).** This document deliberately does
not invent the exact digest/encoding function — that remains a future
`#46` implementation choice, reviewed separately, compatible with
`events.py`/`event_factory.py`'s existing `V2EpisodeEvent`/
`v2_episode_events` shape. What is frozen **now** is which inputs the ID
is a deterministic function of:

```text
episode_id MUST deterministically derive from canonical, JSON-safe
serialization of exactly:
    model_family
    rules_version
    calculation_version
    symbol
    market_type
    direction
    setup_family
    canonical creation structural_anchor   (JSON-safe representation per
                                             §12.5a for CONFIRMED_BREAKOUT's
                                             tick-index/decimal-string form)
    T_create   (the episode's own EARLY_SIGNAL decision boundary)

event_id, given the one-event-per-episode-per-T invariant below, MUST
derive from exactly:
    episode_id
    decision_boundary   (this event's own T)
```

`episode_id`/`event_id` MUST NOT be derived from, or otherwise depend on:

```text
run_kind, run_id (execution_stream, §12.10)    -- NOT semantic identity
wall-clock time                                -- non-deterministic
random UUID                                    -- non-deterministic
hostname / process identity                    -- non-deterministic
```

**Why `execution_stream` is excluded from the semantic ID, precisely:**
the physical `v2_episode_events` table already namespaces every row by
`(run_kind, run_id)` ([§12.10](#1210-execution-namespace-livereplay-history-scope)) —
that is the **physical** row-scoping dimension, entirely separate from an
episode/event's own **semantic** identity. Excluding it from the semantic
ID means a `REPLAY` run over identical historical data and rules
reproduces the exact same `episode_id`/`event_id` values a `LIVE` run
(or a different `REPLAY` run) over the same data would have produced —
enabling direct semantic comparison across independent runs — while the
physical `(run_kind, run_id, episode_id, decision_boundary)` composite
(below) still keeps their rows from ever colliding in storage. Conflating
the two would make cross-run comparison impossible and would incorrectly
suggest that identical episodes computed under different execution
streams are somehow different episodes.

With deterministic IDs, `ON CONFLICT (run_kind, run_id, event_id) DO
NOTHING` is an actually-safe retry mechanism (identical retried inputs
produce identical IDs, so the guard fires correctly) rather than merely a
duplicate-prevention heuristic that happens to work when IDs are already
known to match.

**Related, equally frozen requirement: ONE deterministic same-`T`
multi-event history model — option (a) frozen NOW, option (b) rejected
(amended — a prior draft left both options conforming, which does not
satisfy the pre-Stage-6 unambiguity goal).** V2-v0 invariant:

```text
AT MOST ONE persisted V2EpisodeEvent per:
    execution_stream (run_kind, run_id)
    episode_id
    decision_boundary (T)
```

Same-`T` secondary facts are **aggregated into that one immutable event**
— never split across multiple rows for the same episode at the same `T`.
Examples:

```text
lifecycle transition + REVERSAL_CANDIDATE cross-reference at the same T:
    ONE event carrying the new episode_state PLUS the reversal
    cross-reference fact(s) in its payload/annotations.

lifecycle transition + entry-zone finalization at the same T:
    ONE event carrying both.

no lifecycle transition, but a material zone update/reversal cross-
reference exists at this T:
    ONE same-episode_state event for this T carrying those facts.

no episode-visible change at this T (§12.11):
    NO event -- a legitimate no-op, per §12.11.
```

**Frozen future physical DB uniqueness invariant** (implementation work
for `#46`, not a schema change made by this docs-only PR, per
[§0.1](#01-what-this-document-is-not)): the `v2_episode_events` table's
uniqueness constraint MUST be equivalent to `(run_kind, run_id,
episode_id, decision_boundary)` — a stronger, semantically-scoped
constraint than the current `(run_kind, run_id, event_id)` alone (though
compatible with it, since `event_id` is itself deterministically derived
from `episode_id` + `decision_boundary` above, the two constraints are
equivalent once that derivation is in place). Option (b) (multiple rows
per episode per `T` with a frozen secondary ordering) is **not** conforming
V2-v0 behavior — only option (a) is.

### 2.1b Raw kline backfill must not downgrade an already-known fact
(clean-room audit finding — CONFIRMED against live-traced code, upgraded
from an earlier "unverified" status)

**Finding, confirmed with concrete code evidence.**
`Database.insert_klines` (`storage/db.py`) issues:

```text
INSERT INTO klines_1m (...) VALUES (...)
ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high,
    low = EXCLUDED.low, close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    taker_buy_volume = EXCLUDED.taker_buy_volume,
    taker_sell_volume = EXCLUDED.taker_sell_volume,
    trades_count = EXCLUDED.trades_count,
    source = EXCLUDED.source
```

— an **unconditional** per-field overwrite on conflict, with no `COALESCE`
or "only if not null" guard. `backfill/backfill.py`'s own comment
confirms: "Bybit/OKX/Bitget historical klines do not [carry taker-flow
data], so `taker_buy_volume`/`taker_sell_volume` are left `NULL` for their
backfilled rows (not zero...)," while live ingestion can hold real,
non-`NULL` values for the same `(exchange, symbol, ts)` key. Therefore: if
a backfill/recovery run for a `(exchange, symbol, ts)` already covered by
a richer live row executes **after** that live row, the backfill's `NULL`
`taker_buy_volume`/`taker_sell_volume`/`trades_count` values overwrite —
**downgrade** — the already-known live values to `NULL`, silently
destroying real historical data.

**Frozen storage correctness invariant (implementation in a future
pre-Stage-6 hardening PR, not `#43`):** a lower-fidelity overlapping write
**MUST NOT** downgrade an already-known non-`NULL` historical fact to
unknown `NULL`. At minimum, `taker_buy_volume`, `taker_sell_volume`, and
`trades_count` MUST be audited and fixed under this rule. A future
implementation PR MUST define **per-field conflict precedence explicitly**
— blindly wrapping every field in `COALESCE(EXCLUDED.x, klines_1m.x)` is
**not** automatically correct either (a genuine, deliberate correction —
e.g. a live value later proven wrong and re-backfilled with a better
number — must still be able to overwrite; a blanket "never overwrite
non-null" rule would prevent legitimate corrections just as much as it
prevents illegitimate downgrades). The implementation PR must also
preserve **truthful provenance/source semantics** — a hybrid row that
retains some richer fields from an earlier live write MUST NOT simply be
re-labeled `source = "backfill"` (or vice versa) without a deliberate,
documented source/provenance precedence rule; `source` itself is one of
the unconditionally-overwritten fields above and is subject to the same
precedence-definition requirement. This is a **storage correctness**
requirement — it does not change any V2 decision rule or threshold and
does not, by itself, require a `rules_version` bump, though a resulting
change to historical feature values V2 reads could, incidentally, expose
the version-integrity concern [§23](#23-configurability-vs-frozen-behavior)
already governs.

### 2.1c Aligned-input boundary must fail closed with a domain error, not a raw exception
(clean-room audit finding — CONFIRMED against live-traced code, upgraded
from an earlier "unverified" status)

**Finding, confirmed with concrete code evidence.**
`analytics/forecasting_v2/aligned_inputs.py` has at least two concrete
domain-error leaks: (1) `snapshot_ts` is checked only with
`isinstance(snapshot_ts, datetime)` and then directly compared
(`snapshot_ts > bucket_end`) — a **naive** `datetime` passes the
`isinstance` check but raises a raw `TypeError` ("can't compare
offset-naive and offset-aware datetimes") at the comparison, never the
domain `V2AlignedInputError`; (2) `sample_window_end` is read via
`row.get("sample_window_end")` and, when present, directly compared
(`sample_window_end < row.get("bucket_ts")`) with no type/awareness check
at all — a malformed or naive value raises the same kind of raw
`TypeError` (or `KeyError`, if `bucket_ts` itself is absent from a
malformed row).

**Frozen public boundary expectation (implementation in a future
pre-Stage-6 hardening PR, not `#43`):** a structurally-conforming
`V2AlignedInputReader` (`analytics/forecasting_v2/ports.py`'s
`Protocol`) that returns **malformed PRESENT data** MUST cause the public
V2 aligned-input boundary to fail with the domain error
`V2AlignedInputError` — **never** a raw `TypeError`/`KeyError`/etc.
leaking past the boundary. **Legitimately missing data remains
`None`/empty**, exactly as already frozen elsewhere in this document
([§5.2](#52-missing-percentile-handling--never-none--0)/
[§6.3](#63-coverage--degraded-behavior--fail-closed)) — this section is
about *malformed* present data, not missing data, which is a distinct,
already-solved case. A future hardening PR (`#44` or `#45`) MUST add
regression coverage for at least: a naive health-row `snapshot_ts`; a
malformed/naive `sample_window_end`; a malformed required raw-kline
timestamp/value. This is targeted defensive hardening of an existing
boundary, not a new architecture — it does not change any frozen
formula, threshold, or decision rule.

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
  `rules_version` becomes active mid-episode. It **MUST NOT** be silently
  reinterpreted under the new version's semantics. Whether an in-flight
  episode is allowed to *continue* under its original `rules_version` is
  **no longer open operational policy** — see §3.1's frozen V2-v0
  DRAIN-BEFORE-ACTIVATE policy (clean-room audit amendment), which
  resolves this precisely rather than leaving it undecided.
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

### 3.1 LIVE/REPLAY version-switch policy: DRAIN-BEFORE-ACTIVATE

_(V2-v0, clean-room audit amendment — closes an ambiguity a prior draft
left as "operational policy".)_

**`REPLAY`:** one replay `execution_stream` ([§12.10](#1210-execution-namespace-livereplay-history-scope))
pins **exactly one** semantic tuple — `rules_version`,
`calculation_version`, `decision_code_version` ([§3.2](#32-decision-provenance-tuple-frozen-normatively)
below) — for its **entire run**. A replay run never switches versions
mid-run; a version change requires a new, separately-identified replay
run.

**`LIVE`:** a logical `LIVE` stream **MUST NOT** switch to a different
active `(rules_version, calculation_version, decision_code_version)`
semantic tuple while it still has, under the *previous* tuple, **any**:

```text
non-terminal (ACTIVE) episodes
OR
active same-slot cooldowns (§12.8)
```

**V2-v0 uses DRAIN-BEFORE-ACTIVATE:**

```text
1. Old-version episodes continue under their ORIGINAL, frozen semantic
   tuple -- never reinterpreted under the new tuple's rules/thresholds.
2. Their terminal-episode cooldowns (§12.8) also complete under that SAME
   old semantic tuple.
3. NO new episodes under the new tuple are created in that same logical
   LIVE stream until every old-tuple active episode AND cooldown has
   fully drained (reached a terminal state, and that terminal state's own
   cooldown has elapsed).
4. Only AFTER full drain does the new tuple become active for new
   episode creation in that stream.
```

**Do NOT** reinterpret an old episode under a new rules/calculation/
decision-code tuple. **Do NOT** silently mix old-tuple active state with
new-tuple new creation within the same logical `LIVE` stream.

**Finite, exact V2-v0 switch state machine (re-amended — tech-lead/
red-team finding: the prior wording did not clearly forbid the OLD tuple
from continuing to create new episodes once a switch request started,
which could let OLD's active population keep replenishing itself and make
drain never actually finish; it also wrongly stated a `LIVE` stream
"has exactly one active-for-new-creation tuple" at every moment, which is
false during an active drain).** Assume an operator/runtime requests a
transition from `OLD = (rules_old, calculation_old, decision_code_old)`
to `NEW = (rules_new, calculation_new, decision_code_new)`, and the
request becomes effective at one legal 5m decision boundary `T_request`:

```text
At T_request:
    OLD enters DRAINING for new-episode creation.
    NEW is PENDING.

From T_request onward, while OLD is DRAINING:
    OLD:
        MAY continue lifecycle evaluation of episodes that already
        existed before T_request (confirmation, WEAKENING/recovery,
        invalidation, horizon resolution -- all still under OLD's own
        frozen semantics).
        MAY continue processing cooldowns (§12.8) belonging to those
        old episodes.
        MUST NOT create ANY new episode -- not even one that would,
        under OLD's own rules, otherwise have qualified. There is no
        "grandfathering" of new OLD-tuple episodes once DRAINING begins.
    NEW:
        MUST NOT create any new episode while OLD still has:
            any non-terminal episode
            OR
            any active cooldown.

Therefore, for the entire DRAINING interval:
    active_for_new_creation_tuple_count = 0

-- not 1. Zero tuples are creating new episodes during an active drain;
this is the mechanism that guarantees OLD's population can only shrink
(existing episodes terminalizing, cooldowns elapsing) and never
replenish, so drain is a strictly finite process that always reaches
zero non-terminal episodes and zero active cooldowns in bounded time.
```

**Exact drain-completion / activation boundary (avoids a same-`T`
provenance ambiguity).** At each legal 5m decision boundary while OLD is
DRAINING:

```text
1. Process OLD's lifecycle/cooldown state at this boundary under OLD's
   own provenance tuple, exactly as if no switch were pending.
2. Determine the post-boundary OLD drain state.
3. If, after processing boundary T_drain:
       old non-terminal episode count == 0
       AND
       old active cooldown count == 0
   then:
       drain_complete_at = T_drain
       NEW does NOT create an episode at T_drain itself -- T_drain's
       entire computation already belongs to OLD's provenance.
       NEW becomes active-for-new-creation beginning at the NEXT legal
       5m decision boundary:
           T_activate = T_drain + 5m
```

This deliberately rules out one logical decision boundary being partially
computed under OLD provenance and partially under NEW provenance — the
boundary that observes drain completion is still entirely an OLD-tuple
boundary (it only ever evaluates OLD state); NEW's first possible
new-creation boundary is strictly later. If OLD is already fully drained
(zero non-terminal episodes, zero active cooldowns) at `T_request` itself,
treat `T_request` as `drain_complete_at`, and NEW becomes active beginning
at `T_request + 5m` — never at `T_request` itself, for the same reason.

**Restart during drain.** A normal process/service restart **MUST NOT**:

```text
cancel the pending NEW tuple;
re-enable OLD new-episode creation;
activate NEW early;
reset drain progress.
```

The logical `LIVE` stream **MUST** reconstruct or durably retain enough
switch state (at minimum: that OLD is `DRAINING`, that NEW is `PENDING`,
and OLD's current non-terminal-episode/active-cooldown counts) to resume
the identical `OLD = DRAINING` / `NEW = PENDING` / drain-progress
semantics after restart, exactly as if the process had never stopped. The
physical mechanism (a persisted switch-state row, a recomputed-from-episode-
state derivation, or an equivalent durable representation) remains #45/#46
implementation work — this document freezes only the observable
correctness invariant that a restart cannot silently reopen OLD
new-episode creation or silently fast-forward NEW's activation.

**Reconciled invariant.** The correct statement, replacing the prior
"exactly one active-for-new-creation tuple at any moment" claim:

```text
Outside a version transition:
    exactly one tuple may be active for new creation.
During DRAINING:
    zero tuples are active for new creation.
Never, under any circumstance:
    more than one tuple active for new creation.

i.e. active_for_new_creation_tuple_count <= 1, and it is exactly 0
throughout DRAINING -- not "OLD, until NEW takes over," and never both.
```

This is deliberately the simplest correct V2-v0 policy — a future
explicit multi-version concurrent-dispatch design (e.g. running two
tuples' new-episode creation simultaneously in one stream) would be a
genuinely new architecture requiring its own versioned contract change,
not an extension of this one.

**Worked vectors:**

```text
A -- old episode remains active well past the request:
  T_request = 09:00 (rules_v1 -> rules_v2 requested).
  OLD has one non-terminal TREND_PULLBACK episode, still CONFIRMED at
  09:00, that does not reach a terminal state until 09:20.
  From 09:00 through 09:20: OLD is DRAINING (may keep evaluating that
  episode's lifecycle; MUST NOT create any new episode under rules_v1).
  NEW (rules_v2) MUST NOT create any episode in this window either --
  active_for_new_creation_tuple_count = 0 throughout.
  At 09:20 the episode reaches EXPIRED. Its terminal cooldown (§12.8,
  1x5m for EXPIRED) elapses at 09:25.
  At the 09:25 boundary: old non-terminal count == 0 AND old active
  cooldown count == 0 -> drain_complete_at = 09:25.
  NEW does NOT create at 09:25 itself. T_activate = 09:25 + 5m = 09:30.
  From 09:30 onward, rules_v2 is active for new-episode creation.

B -- old episode terminalizes, cooldown ends later, no replenishment:
  Same as A, but suppose at 09:05 (while DRAINING) OLD's detector would,
  under rules_v1, have otherwise produced a fresh qualifying
  COMPRESSION_BREAKOUT EARLY_SIGNAL for an unrelated slot.
  Per the frozen rule above: OLD MUST NOT create it -- DRAINING forbids
  ANY new OLD-tuple episode, regardless of slot. No new OLD episode
  exists to extend the drain. OLD's only remaining non-terminal episode
  (the TREND_PULLBACK from vector A) still terminalizes at 09:20 and its
  cooldown still elapses at 09:25, exactly as in A -- drain_complete_at
  is unaffected by the would-have-qualified candidate that was correctly
  refused.

C -- no old active/cooldown exists at request time:
  T_request = 14:00. OLD has zero non-terminal episodes and zero active
  cooldowns already, at 14:00.
  drain_complete_at = T_request = 14:00 (already-drained case).
  T_activate = 14:00 + 5m = 14:05 -- NEW does not activate at 14:00
  itself, for the same same-boundary-provenance reason as the general
  case, even though there was nothing to actually wait for.

D -- process restart while OLD is draining:
  At 09:10 (mid-drain, per vector A: OLD still has its one non-terminal
  episode, drain not yet complete), the LIVE process restarts.
  On restart, the stream reconstructs: OLD = DRAINING, NEW = PENDING,
  OLD's non-terminal-episode/cooldown state exactly as it stood before
  the restart (one non-terminal episode, still active).
  The restarted process MUST NOT: treat the restart as cancelling the
  pending rules_v2 switch; resume creating new episodes under rules_v1;
  or activate rules_v2 early because "the process is fresh."
  Drain continues exactly as in vector A -- the episode still
  terminalizes at 09:20, cooldown still elapses at 09:25,
  drain_complete_at = 09:25, T_activate = 09:30, unaffected by the
  restart.

E -- proof OLD cannot make drain infinite by replenishing itself
  (re-amended -- tech-lead/red-team finding: the round-5 proof's "a
  non-increasing, non-negative integer sequence reaches zero in finite
  time" is mathematically false on its own -- the constant sequence
  1, 1, 1, ... is non-increasing and bounded below by 0 but never
  reaches 0. The DRAIN behavior itself does not change; only the
  finiteness argument is corrected, below, to one that is actually
  valid):
  1. By construction (the frozen rule above), OLD MUST NOT create any
     new episode at any boundary from T_request onward, unconditionally
     -- not "unless it's a strong signal," not "unless the slot is
     empty." Therefore the SET of OLD-tuple episodes present at
     T_request can never grow -- it is exactly the finite set that
     already existed at T_request, for the rest of the drain.
  2. Every one of those pre-existing active episodes has an
     already-frozen, FINITE lifecycle deadline of its own: an
     EARLY_SIGNAL candidate has a finite max-candidate-age expiry
     (§14); a CONFIRMED/WEAKENING episode has a finite expected horizon
     (§14) or an earlier structural invalidation, whichever comes
     first (§13.1) -- every path through §13's transition graph reaches
     a terminal state in bounded time from T_request, for every
     individual episode.
  3. Every terminal-episode cooldown (§12.8) is itself finite (1x5m or
     3x5m depending on terminal state) -- a bounded additional delay
     after each episode's own terminal transition.
  4. Since the SET of episodes at T_request is finite (step 1) and each
     one's own remaining lifecycle-to-terminal-plus-cooldown duration is
     individually finite (steps 2-3), the MAXIMUM such duration across
     that finite set is itself a finite number -- not because the count
     is decreasing, but because it is a finite max of finite numbers.
  5. At T_request + (that finite maximum), by definition every
     pre-existing OLD episode has both reached a terminal state and had
     its cooldown elapse -- old non-terminal episode count = 0 AND old
     active cooldown count = 0 -- so drain_complete_at is reached no
     later than that bound.
  Drain is therefore guaranteed to complete in finite, bounded time by
  construction -- via a finite set of episodes each individually bounded
  in remaining lifetime, not via an unjustified "decreasing sequence
  must hit zero" claim.
```

### 3.2 Decision provenance tuple, frozen normatively

_(Clean-room audit amendment — a prior draft captured this only as
roadmap implementation debt; freezing it here makes it a correctness
requirement, not merely a future PR's design choice.)_

**Before ANY Stage 3/4/5/6 computation begins for one logical decision
boundary `T`, one immutable decision provenance tuple MUST be resolved,**
binding at minimum:

```text
execution_stream          (run_kind, run_id, §12.10)
decision boundary T
symbol
market_type

model_family
rules_version

feature_schema_version
calculation_version
config_hash / config_version
Stage 2 feature code version           (STAGE2_SPEC.md §10's code_version)

decision_code_version                  (see below -- DISTINCT from Stage 2's
                                         feature code_version)
```

**`decision_code_version` is distinct from Stage 2's feature
`code_version`.** Stage 2's `code_version` identifies *feature-computation*
code identity (`§3` above, `STAGE2_SPEC.md` §10) — the code that computes
`exchange_feature_vectors`/`consensus_feature_vectors`/
`percentile_snapshots`. `decision_code_version` identifies the *separate*
V2 decision/state-machine code identity — Stage 4's context engines,
Stage 5's detectors, and Stage 6's state machine itself. These MUST NOT be
conflated: a Stage 6 lifecycle-transition bug fix changes
`decision_code_version`, not Stage 2's feature `code_version`, and vice
versa — each identifies the correctness of a genuinely different code
layer.

**This same immutable provenance tuple follows the computation through
every stage:** Stage 3 (alignment) → Stage 4 (context) → Stage 5
(detector candidate) → Stage 6 (state machine) → the persisted
`V2EpisodeEvent`. **A candidate/result computed under provenance tuple A
MUST NOT later be wrapped/persisted as provenance tuple B.** Concretely:
the provenance a `V2EpisodeEvent` is stamped with at final construction
([§2.1](#21-replay-behavior-for-late-arriving--corrected-data)'s
`V2EventProvenance`) MUST be the exact same tuple that was already
resolved **before** Stage 3/4/5/6's math ran for that decision — never a
provenance value independently supplied at the end of the pipeline that
could, even in principle, differ from what was actually used to compute
the candidate.

This section does **not** require every small pure intermediate result
object (a `V2RegimeResult`, a `V2BiasResult`, a Stage 5 candidate) to
duplicate every field of the full tuple — a single immutable provenance
envelope threaded through the computation, and consulted (not
re-derived) at each stage, is sufficient to prove the association. The
implementation shape (envelope threading, context object, or another
equivalent mechanism) is a future `#45` implementation choice; **this
section's semantic requirement — provenance resolved before computation,
never rewritten after — is contract-level, frozen now.**

### 3.3 Feature-computation identity vs. deployment identity, and version activation readiness

_(Clean-room audit amendment — closes S/U as normative requirements, not
merely roadmap debt.)_

**Stage 2 feature-computation identity MUST represent Stage 2
feature-computation semantics — nothing else.** An unrelated change to
the V2 state machine, Telegram code, documentation, or other runtime code
**MUST NOT**, by itself, fork Stage 2's `calculation_version` namespace.
`calculation_version`'s `code_version` component (`STAGE2_SPEC.md` §10)
**MUST** represent feature-computation code identity specifically — if the
current implementation derives it from whole-repository git identity
(e.g. `git describe`), that is **non-conforming** the moment any
unrelated repository change (a docs-only commit, Stage 6-only code, an
unrelated runtime fix) would mint a new `calculation_version` with no
historical feature/percentile state behind it. A future `#45`
implementation MUST satisfy this via a dedicated feature-code/component
version (scoped to `analytics/feature_engine/`+`analytics/percentile_engine/`
and their direct dependencies) or an equivalent deterministic mechanism
that is genuinely insensitive to unrelated repository changes.

**Version activation readiness (fail-closed, no silent fallback).** A new,
legitimate `calculation_version` **MUST NOT** become eligible for V2
decision processing until **all** mandatory historical feature/percentile
prerequisites V2 requires for that version are sufficiently materialized
(the exact percentile-window/lookback requirements already frozen
throughout [§4](#4-multi-timeframe-context-contract)–[§7](#7-setup-detectors)).
There is **no silent fallback** to an older `calculation_version` if the
new one is not yet ready — that would silently reinterpret which rules
produced a decision. The following sequence is explicitly **not**
accepted normal behavior:

```text
deploy -> a fresh, empty calculation_version namespace becomes active
       -> V2 silently becomes unavailable (or silently falls back to an
          older calculation_version without saying so)
```

Instead, the activation/readiness state **MUST** be explicit and **fail
closed**: V2 decision processing for a not-yet-ready `calculation_version`
MUST report itself as unavailable (the existing `UNAVAILABLE`/fail-closed
vocabulary this document already uses throughout, e.g.
[§6.3](#63-coverage--degraded-behavior--fail-closed)) rather than either
silently reusing stale data under the new version's identity or silently
reverting to an old version's identity. The exact readiness-check
mechanism is `#45` implementation work; the **fail-closed requirement
itself** is frozen here.

### 3.4 One coherent data view per logical decision

_(Clean-room audit amendment — closes S as a normative requirement, not
merely roadmap debt.)_

**ONE logical V2 decision boundary `T` MUST consume ONE coherent data
view across every read that contributes to that decision** — Stage 3's
aligned exact-bucket reads, Stage 5's historical windows, Stage 5's
instrument facts ([§12.5a](#125a-tick-grid-is-frozen-at-episode-creation-confirmed_breakout)),
and any Stage 6 decision-time raw/reference facts, where applicable. **The
same logical decision MUST NOT combine pre-correction and post-correction
versions of the same underlying data merely because they share
`calculation_version`** — [§2.1](#21-replay-behavior-for-late-arriving--corrected-data)'s
correction model explicitly allows an upsert **under the same**
`calculation_version`, so identity checks on `calculation_version` alone
do **not**, by themselves, prove two reads observed the same underlying
values.

**Additionally:** V2 **MAY** only consume a Stage 2 correction
generation/publication that is **complete** as a coherent published unit
— never a state where some of a correction's outputs
(`exchange_feature_vectors`/`consensus_feature_vectors`/
`percentile_snapshots`/health) have committed and others have not.

The **visible invariant is normative now**: no logical V2 decision may be
computed from an internally half-published correction state, and no
logical decision may straddle two different correction generations of the
same underlying data. The **physical mechanism** remains `#45`
implementation work — one read-only `REPEATABLE READ` transaction/
connection spanning Stage 3+5 input assembly, a publication-generation
marker, an atomic correction-publication transaction, a completion
watermark, or another provably-equivalent mechanism. This document does
not prescribe which; it freezes that a mechanism satisfying the
invariant above is a correctness requirement, not an optional hardening
nicety.

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

### 4.1a Stage 4 numerical evidence must survive the Stage 4→5/6 boundary
(clean-room audit amendment — closes a broader gap than the
`COMPRESSION_BREAKOUT` `setup_strength` fix alone addressed)

**Finding.** `§8`'s `regime_strength`/`bias_strength` components require
the **numerical** `price_evi` ([§4.2](#42-4h-regime)), `compression_score`
([§4.1](#41-normalized-evidence-primitive-used-throughout-47)), and
`bias_evi` ([§4.3](#43-1h-bias)) values. The currently-merged Stage 4
result types do **not** carry them: `V2RegimeResult`
(`analytics/forecasting_v2/regime_4h.py`) exposes only `bucket_ts`,
`regime`, `is_compressed` (labels); `V2BiasResult`
(`analytics/forecasting_v2/bias_1h.py`) exposes only `bucket_ts`, `bias`
(a label). The underlying numeric evidence values are computed
**internally**, used to decide the label, and then discarded — never
returned. `V2ContextSnapshot` (`context_snapshot.py`) wraps these
label-only results, so nothing downstream of Stage 4 can compute §8's
`regime_strength`/`bias_strength` without **recomputing** `price_evi`/
`bias_evi`/`compression_score` from Stage 3 data all over again.

**Frozen handoff invariant (generalizes the `COMPRESSION_BREAKOUT`
`setup_strength` fix, [§8](#8-model-confidence-semantics), to the whole
Stage 4→5/6 boundary, and to the Stage 5→6 boundary alongside it):** a
stage that **owns** a semantic calculation — here, Stage 4's context
engines computing `price_evi`/`bias_evi`/`compression_score` to decide a
regime/bias/compression label — **MUST** preserve and expose, **by
value**, the canonical numerical evidence facts a later stage's
already-frozen formulas need. A later stage **MUST NOT** be required to
call `normalized_evidence()`/`compression_score()` (or any other Stage 4
scoring primitive) again against Stage 3 data merely to recover a value
Stage 4 already computed once. Concretely, a future Stage 4 hardening PR
MUST carry forward, at minimum, conceptually:

```text
4h context:  price_evi (the signed normalized-evidence value that decided
             regime, §4.2), compression_score where applicable (i.e.
             whenever is_compressed was evaluated, §4.1/§4.2)
1h context:  bias_evi (the signed normalized-evidence value that decided
             bias, §4.3)
```

The exact Python field names/types remain implementation work (this PR
does not prescribe a schema, per [§0.1](#01-what-this-document-is-not))
— what is frozen is that the **semantic output values themselves may
never be discarded** between computation and the point `§8`'s formula
needs them.

**The same invariant applies, symmetrically, to Stage 5 candidate/result
outputs and Stage 6.** Every canonical setup/scoring/quality fact `§8`
(or any other frozen Stage 6 formula) needs from a Stage 5 candidate —
the `COMPRESSION_BREAKOUT` per-run mean `compression_score` fixed above,
`CONFIRMED_BREAKOUT`'s `breakout_distance_beyond_level`/`protection_buffer`,
each family's `price_structure`/`taker_flow`-scoped confidence facts
([§8](#8-model-confidence-semantics)'s `data_confidence` component,
per-family sourcing frozen there) — MUST be carried forward **by value**
in the Stage 5 candidate/result object, never silently dropped and left
for Stage 6 to re-derive from raw Stage 2/3/4 data.

**Implementation debt:** a future pre-Stage-6 hardening PR (quality/scoring
boundary hardening) owns both the Stage 4 evidence handoff and the Stage 5
scoring/quality handoff — see the revised roadmap plan.

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
| Role | "Is there an established higher-timeframe price trend, optionally confirmed/vetoed by available OI context?" | "Which way does the nearer-term tape lean, if at all?" |

A single strong impulsive 4h move is read by regime as one thing (a
30d-relative price extreme, optionally OI-modulated per the row above) and
by bias as a *different* thing (a 7d-relative price lean) — they can and
often will agree, but they are
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
| `min_coverage_ratio < 2/3` for a **context** timeframe (4h/1h) | No — that context input is `INSUFFICIENT_DATA`/`UNAVAILABLE` ([§4](#4-multi-timeframe-context-contract)) | Detector-dependent: `TREND_PULLBACK` requires both regime and bias, so it fails closed on either. The breakout families (`COMPRESSION_BREAKOUT`, `CONFIRMED_BREAKOUT`) go through the shared `directional_context_gate` ([§7.0b](#70b-directional-context-compatibility-gate-amended--closes-a-countertrend-gap)): a genuinely measured `NEUTRAL_NOT_ESTABLISHED` 1h bias (or `NON_DIRECTIONAL` 4h regime) is **not** disqualifying — but `INSUFFICIENT_DATA` 4h regime **and** `UNAVAILABLE` 1h bias **both** fail closed for new episode formation, as two data-availability reasons distinct from the countertrend check. "Insufficient/unavailable data" is never treated the same as "neutral" for either timeframe. |
| `min_coverage_ratio < 2/3` for the **5m trigger** bucket | No | No new candidate may transition to `CONFIRMED` at that boundary; an already-`CONFIRMED` episode is not auto-invalidated by this alone (missing evidence is not structural invalidation, [§10](#10-structural-invalidation)) but also cannot be strengthened/re-confirmed on that boundary. |
| Single-exchange contribution to any family | Coverage `< 2/3` (1-of-3) → fails the gate above by construction (the frozen consensus minimum, `STAGE2_SPEC.md` §11.1, already refuses a single exchange). **A single exchange's data MUST NOT masquerade as consensus** — this is enforced by the existing `minimum_exchange_coverage` gate, reused unchanged, not re-implemented. | — |

**Every family affecting a setup's evidence score is subject to the same
renormalize-or-fail rule as [§5.2](#52-missing-percentile-handling--never-none--0):**
a family below its minimum coverage contributes `UNAVAILABLE`, which is
either excluded-and-renormalized (evidence scoring) or a hard fail
(context sufficiency gates), never a silent zero.

### 6.3a Per-family metric-scoped quality gates

_(Clean-room audit amendment — closes a global-worst-family gap that
contradicts an already-frozen invariant.)_

**The problem.** `ConsensusFeatureVector.min_coverage_ratio` /
`.consensus_confidence` (used throughout §6.3's table above, and by every
currently-merged Stage 4/5 quality gate —
`analytics/forecasting_v2/regime_4h.py`, `bias_1h.py`, `trend_pullback.py`,
`compression_breakout.py`, `confirmed_breakout.py`) are each the **global
minimum/worst-case across all six Stage 2 metric families**
(`analytics/feature_engine/consensus.py`:
`min_coverage_ratio = min(coverage[family].ratio for family in FAMILIES)`,
`consensus_confidence = min(family_scores)`, `FAMILIES = (price_structure,
volume, taker_flow, oi, funding, liquidations)`). Every currently-merged
V2 quality gate reads **only** this global rollup — none reads Stage 2's
separately-persisted, already-available per-family
`coverage_by_metric`/`data_confidence_by_metric` maps
(`ConsensusFeatureVector`, same module). This directly contradicts an
**already-frozen** invariant one layer up: `§4.2`'s own text (the "OI
role" row, [§4.4](#44-independence--anti-double-counting)) freezes that
"OI availability is **not** required to establish [4h regime] direction"
— yet the coarser, currently-merged global quality gate can fail closed
on 4h regime computation entirely merely because **OI** (or `funding`, or
`liquidations`) coverage is poor, even though `price_structure` coverage
— the only family 4h regime direction actually needs — is perfectly
adequate. The same problem applies, more severely, to a purely
price-based setup like `TREND_PULLBACK`: zero historical `liquidations`
coverage (a family `TREND_PULLBACK` never reads at all) would currently
suppress it via the global `min_coverage_ratio` gate, even though nothing
about `TREND_PULLBACK`'s own formula depends on liquidation data.

**Frozen resolution: gate on the metric families a decision actually
consumes, using data ALREADY persisted — no new field.** Every V2
decision below has an exact, frozen set of **required metric families**;
its quality gate MUST use `coverage_by_metric`/`data_confidence_by_metric`
restricted to *exactly* those families — never the global
`min_coverage_ratio`/`consensus_confidence` rollup as a precondition for a
decision that does not consume every family:

| V2 decision | Required metric families (must individually satisfy the family-scoped `2/3` coverage / `50.0` confidence gate) | Notes |
|---|---|---|
| 4h regime direction + compression flag | `price_structure` | `oi` is read for the veto only (below) — its absence never blocks direction, per the already-frozen §4.2 OI-role invariant this amendment now makes consistent with the quality gate. |
| 4h regime OI veto | `oi`, when present | `UNAVAILABLE` `oi` simply means the veto cannot apply — never a reason to fail the whole regime computation (§4.2, unchanged). |
| 1h bias | `price_structure` | Same shape as 4h regime direction. |
| `TREND_PULLBACK` formation + confirmation | `price_structure` | Uses only `close_price`-derived retracement/extreme facts — no `volume`/`taker_flow`/`oi`/`funding`/`liquidations` input anywhere in §7.1. |
| `COMPRESSION_BREAKOUT` formation (compression window) | `price_structure` | `compression_score` is a `price_structure`-derived (`range_width_pct`) quantity, [§4.1](#41-normalized-evidence-primitive-used-throughout-47). |
| `COMPRESSION_BREAKOUT` EARLY_SIGNAL trigger | `price_structure`, `taker_flow` | §7.2's fresh-cross AND the `price_direction_agreement >= 2/3` gate are both `price_structure`-family facts (`consensus.py`: `agreement["price_structure"] = _direction_agreement(price_move_pct values)` — `price_direction_agreement` is `price_structure`'s own agreement field, corrected here from an earlier draft that mislabeled it `taker_flow`); the `taker_delta_notional_usd_sum` sign check is the `taker_flow`-family fact. Both families remain mandatory for this decision — the required-family set is unchanged. |
| `COMPRESSION_BREAKOUT` confirmation (false-break/HOLD) | `price_structure` | Confirmation is a pure closed-5m-close check, §7.2. |
| `CONFIRMED_BREAKOUT` formation + confirmation | `price_structure` | §7.3 explicitly carries **no** `taker_flow` requirement at all (unlike `COMPRESSION_BREAKOUT`) — see `analytics/forecasting_v2/confirmed_breakout.py`'s own docstring, "no taker-flow confirmation requirement." |
| `WEAKENING` / recovery | `price_structure` | [§13.2a](#132a-weakening-and-recovery-criteria-v2-v0)/[§F below] use `price_move_pct_median`/`price_direction_agreement`, both `price_structure`-family facts. |

An unrelated missing/degraded metric family **MUST NOT** suppress a
decision that does not consume it — this directly resolves the concrete
example this amendment audited: historical `liquidations` coverage `= 0`
**MUST NOT** automatically suppress a `TREND_PULLBACK` candidate, because
`TREND_PULLBACK` never reads the `liquidations` family.

**This is an executable behavior correction, not a documentation-only
clarification.** Every currently-merged V2 quality-gate call site listed
above reads the global rollup fields today; switching to per-family
`coverage_by_metric`/`data_confidence_by_metric` scoped reads is a real
change to V2-v0's decision output on some inputs (a candidate that is
currently incorrectly suppressed by an unrelated family's poor coverage
will, after the fix, correctly proceed). Per
[§3](#3-v2-modelversion-identity)'s versioning invariants, this **MUST**
ship under a new `rules_version` — **`v2-rules-v0.2.0`** — when a future
executable hardening PR implements it; `config/v2.yaml` is **not** edited
by this docs-only amendment (`#43`), and `v2.enabled`/`rules_version`
remain unchanged here. See
[§23](#23-configurability-vs-frozen-behavior) for the "config is not a
loophole" principle this correction must respect: the family-scoped gate
threshold *values* themselves (`2/3` coverage, `50.0` confidence) are
**not** changing, only which family/families each decision's gate is
scoped to — but because it changes which candidates the same raw input
data produces, it is a `rules_version`-participating behavior change
regardless.

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
B5_detect  = selected_bucket(5m,  T_detect)          # the freshest legal 5m input at T_detect.
                                                       # Per §1.3, selected_bucket(5m, T) = [T-5m, T):
                                                       #   bucket_ts(B5_detect)  = T_detect - 5m
                                                       #   bucket_end(B5_detect) = T_detect
```

**Candidate age.** Max `PULLBACK_MAX_AGE = 8` closed 15m buckets (2h,
V2-v0) from `T_detect` to `T_confirm`, else → `EXPIRED`
([§13](#13-lifecycle-transition-semantics)).

**5m confirmation (trigger) — exact `CONFIRMED` decision boundary.** The
resumption trigger is evaluated at 5m decision boundaries (finer-grained
than the 15m boundary that produced `T_detect`). Confirmation may only be
evaluated at a **later** decision boundary `T' > T_detect` — never at
`T_detect` itself. At such a `T'`, let `B5_confirm = selected_bucket(5m,
T')` (per §1.3, `bucket_ts(B5_confirm) = T' - 5m`,
`bucket_end(B5_confirm) = T'`). The trigger condition (unchanged): the
consensus `price_move_pct_median` sign matches the trend direction
(ternary sign, per `STAGE2_SPEC.md` §11.2) **and**
`price_direction_agreement >= 2/3`, for **one** closed 5m bucket
(`RESUMPTION_MIN_BUCKETS = 1`, V2-v0 — deliberately the loosest possible,
since 5m's role is trigger, not strength-scoring,
[§5.1](#51-percentile-lookback--window)).

`T_confirm` is the **first** such `T' > T_detect` for which the trigger
condition holds on `B5_confirm`:

```text
CONFIRMED at T_confirm  iff  T' > T_detect
                              AND trigger condition holds for B5_confirm = selected_bucket(5m, T')
                              AND T_confirm = T'  (the first such T')
```

This is load-bearing by construction, not by a bucket-equality check:
confirmation is only ever *evaluated* at a decision boundary strictly
later than `T_detect`, so `B5_confirm` can never be `B5_detect` —
`bucket_end(B5_detect) = T_detect` while `bucket_end(B5_confirm) =
T_confirm > T_detect`, so the two buckets are never the same closed
interval. The earliest possible confirmation is `T_confirm = T_detect +
5m`, at which point `B5_confirm = selected_bucket(5m, T_detect + 5m) =
[T_detect, T_detect + 5m)` — i.e. `bucket_ts(B5_confirm) = T_detect` (**not**
`T_detect + 5m`; the bucket's *start*, not its *end*, coincides with
`T_detect`) and `bucket_end(B5_confirm) = T_detect + 5m`. `T_confirm >
T_detect` always holds, and a new episode can never be created and
immediately `CONFIRMED` from the same already-known 5m bucket — even
though `B5_confirm`'s own *start* is `T_detect`, `B5_confirm` itself is a
closed interval that did not exist as a closed bucket until `T_detect +
5m`, strictly after `EARLY_SIGNAL` was created.

**Concrete timestamp vector (agrees exactly with §1.3):**

```text
T_detect = 12:15
B15_detect = selected_bucket(15m, 12:15) = [12:00, 12:15)
B5_detect  = selected_bucket(5m,  12:15) = [12:10, 12:15)   # bucket_ts=12:10, bucket_end=12:15=T_detect

=> EARLY_SIGNAL at T_detect = 12:15.

Earliest possible confirmation:
T_confirm = 12:20 (= T_detect + 5m)
B5_confirm = selected_bucket(5m, 12:20) = [12:15, 12:20)    # bucket_ts=12:15=T_detect, bucket_end=12:20=T_confirm

trigger holds on B5_confirm => CONFIRMED at T_confirm = 12:20 > T_detect = 12:15.
```

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

*At `CONFIRMED` (`T_confirm`, using the confirming bucket `B5_confirm`):*
the zone updates **one final time**, now that
`confirmation_close_price = close_price(B5_confirm, reference_exchange)` exists:
```text
LONG:  [pullback_extreme_low,  confirmation_close_price]
SHORT: [confirmation_close_price, pullback_extreme_high]
```
and is then **frozen** — [§9](#9-entry-zone-semantics)'s generic
freeze-on-`CONFIRMED` and historical-truth rules apply unchanged: any
pre-`CONFIRMED` zone value already notified is preserved in event history,
never silently rewritten.

**Expected horizon:** `2h` from `CONFIRMED` ([§14](#14-candidate-expiry-and-expected-horizons)).

**Candidate self-validation invariant, frozen for a future `#44` hardening
pass (clean-room audit finding — `V2TrendPullbackCandidate`
(`analytics/forecasting_v2/trend_pullback.py`) currently validates only
positive/finite values, `entry_lower <= entry_upper`, and that
`invalidation_price` sits on the correct *side* of `pullback_extreme` —
weaker than `V2CompressionBreakoutCandidate`'s exact-formula
cross-checks).** At **formation time** (the `EARLY_SIGNAL` candidate,
using this section's own `EARLY_SIGNAL` entry-zone formula above), a
`TREND_PULLBACK` candidate's fields MUST satisfy the exact detector
geometry, not merely an inequality:

```text
LONG:  entry_zone_lower    == pullback_extreme_low
       entry_zone_upper    == current_close                  (= close_price(B15_detect))
       invalidation_price  == pullback_extreme_low  - protection_buffer

SHORT: entry_zone_lower    == current_close                  (= close_price(B15_detect))
       entry_zone_upper    == pullback_extreme_high
       invalidation_price  == pullback_extreme_high + protection_buffer
```

This is the formation-time shape only — a directly-constructed candidate
object always represents one formation-time (or pre-confirmation
re-evaluation) output, per [§12.2a](#122a-per-family-structural-mutability)'s
already-frozen per-family mutability rules; it never has to represent a
`CONFIRMED`-time zone in the same object shape. A future `#44` PR must
add the same kind of exact-formula cross-check `compression_breakout.py`
already performs (`entry_lower != range_high or entry_upper != range_high
+ buf: raise`) — `retracement_pct`'s own relationship to `current_close`/
`trend_leg_extreme` MAY remain a lighter, non-re-derived check (the
formula involves `RANGE_PROXY_pct`, an external percentile input the
candidate object does not itself carry) — this is targeted hardening, not
a redesign, and does not change any frozen formula.

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

**Structural invalidation — computable at `EARLY_SIGNAL`, active once
`CONFIRMED` (amended — an earlier draft's "once `CONFIRMED`" heading
wrongly implied this level does not exist until then).** `range_low` and
`range_high` are already fixed as of the compression window's own
selection (above), *before* `EARLY_SIGNAL` is even reached, so this level
is fully computable — and MUST be included in the `EARLY_SIGNAL`
notification's `invalidation_price` field
([§16.1](#161-early_signal-notification-content-and-history-invariants-v2-v0))
— from the moment the episode is created:

```text
LONG:  invalidation_price = range_low  - protection_buffer(15m, B15, reference_price)
SHORT: invalidation_price = range_high + protection_buffer(15m, B15, reference_price)
```

This is the same close-based, single-bucket formula as
[§7.1](#71-trend_pullback) and [§10](#10-structural-invalidation), and
applies in **two roles** with an intentionally clean handoff between them:

- **Pre-`CONFIRMED` (`EARLY_SIGNAL` only):** the **False-break rule above**
  is the operative, *stricter* invalidation check during this window — it
  fires on any close that no longer holds the breakout side (including a
  simple re-entry, well before price would reach this formula's wider
  `invalidation_price`). This planned `invalidation_price` is shown to the
  user in the `EARLY_SIGNAL` notification as the level the episode is
  *planning toward*, but it is **not yet the active invalidation trigger**
  — the False-break rule is.
- **At and after `CONFIRMED`:** this planned level **becomes** the active,
  frozen, post-confirmation structural invalidation trigger — unchanged
  from an earlier draft's behavior, just correctly described as already
  computed rather than newly created at `CONFIRMED`.

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

**Structural invalidation — computable at `EARLY_SIGNAL`, active once
`CONFIRMED`** (same amended shape as
[§7.2](#72-compression_breakout)'s: `resistance_level`/`support_level` are
already fixed as of the 1h structural lookback (above), before
`EARLY_SIGNAL` is reached, so this level is fully computable — and MUST be
included in the `EARLY_SIGNAL` notification's `invalidation_price` field
([§16.1](#161-early_signal-notification-content-and-history-invariants-v2-v0))
— from the moment the episode is created:

```text
LONG:  invalidation_price = resistance_level - protection_buffer(1h, B1h, reference_price)
SHORT: invalidation_price = support_level    + protection_buffer(1h, B1h, reference_price)
```

i.e. beyond the broken level itself (not the retest extreme — unlike the
Stage 2 Clarifications' historical sweep/reclaim design, V2's
`CONFIRMED_BREAKOUT` has no retest-extreme concept; the broken level is the
only structural anchor). As with `COMPRESSION_BREAKOUT`: pre-`CONFIRMED`,
the **False-break re-entry rule above** is the operative, stricter
invalidation check (this planned level is shown to the user but is not yet
the active trigger); at and after `CONFIRMED`, this planned level
**becomes** the active, frozen, post-confirmation structural invalidation
trigger.

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

#### 7.4.1 Structural region and overlap predicate (exact)

The prior text used "overlapping structural region" without a precise
predicate. This is now frozen using geometry Stage 5 already produces —
**no new field, tolerance, or geometry is invented.**

Every candidate exposes `entry_zone_lower`/`entry_zone_upper`
([§9](#9-entry-zone-semantics), with `entry_zone_lower <= entry_zone_upper`)
at the moment it qualifies (its `EARLY_SIGNAL` entry zone). For §7.4
arbitration, a candidate's **structural region** is exactly the closed
interval `[entry_zone_lower, entry_zone_upper]` — nothing else.

Two candidates' structural regions overlap **iff** their closed intervals
have a non-empty intersection:

```text
overlap(A, B) iff max(lower_A, lower_B) <= min(upper_A, upper_B)
```

Boundary-touching counts as overlap (the predicate uses `<=`, not `<`).
No percentage tolerance, extra tick tolerance, ATR tolerance, or "nearby
enough" fuzz is added — the already-versioned structural entry zones are
the entire comparison geometry.

Examples:

| A | B | Overlap? |
|---|---|---|
| `[100, 110]` | `[105, 120]` | Yes — intervals genuinely intersect. |
| `[100, 110]` | `[110, 120]` | Yes — touching at `110` counts. |
| `[100, 109.9]` | `[110, 120]` | No — `max(100,110)=110 > min(109.9,120)=109.9`. |

#### 7.4.2 Deterministic arbitration algorithm

For **new** episode candidates that have already survived same-slot
active/cooldown eligibility ([§12.3](#123-per-decision-classification-of-a-same-slot-candidate)/
[§12.6](#126-suppression-at-most-one-active-episode-per-slot)/
[§12.8](#128-terminal-episode-cooldown-exact-clock)) at one decision
boundary `T`, arbitrate **separately per direction**:

```text
1. Start with all independently-qualified, creation-eligible candidates
   for this direction at T.
2. Order them by family precedence, high to low:
       COMPRESSION_BREAKOUT > CONFIRMED_BREAKOUT > TREND_PULLBACK
3. Walk the ordered list. For each candidate:
   4. Accept it iff its structural region (§7.4.1) does NOT overlap the
      structural region of any candidate already accepted earlier in this
      walk (i.e. any already-accepted higher-or-equal-precedence
      candidate).
   5. Otherwise, suppress it (§12.7 — suppressed, not queued) and record a
      cross-reference from its family/reason to the accepted
      higher-precedence winner in that winner's event history.
```

Because the walk is strictly precedence-ordered and each step compares
only against already-*accepted* candidates, the result is deterministic
and order-independent with respect to any incidental input ordering.

Worked example: at one `T`, one direction, three independently-qualified
candidates — `COMPRESSION_BREAKOUT` region `[100,110]`, `CONFIRMED_BREAKOUT`
region `[105,115]`, `TREND_PULLBACK` region `[150,160]`. Walk:
`COMPRESSION_BREAKOUT` accepted first (nothing accepted yet).
`CONFIRMED_BREAKOUT` overlaps `[100,110]` (`max(105,100)=105 <=
min(115,110)=110`) → suppressed, cross-referenced to the `COMPRESSION_BREAKOUT`
episode. `TREND_PULLBACK` `[150,160]` does not overlap `[100,110]` (the only
accepted region so far) → accepted. Result: create `COMPRESSION_BREAKOUT`,
suppress `CONFIRMED_BREAKOUT`, create `TREND_PULLBACK`. If all three regions
had mutually overlapped instead, only `COMPRESSION_BREAKOUT` would be
created; `CONFIRMED_BREAKOUT` and `TREND_PULLBACK` would both be suppressed
against it.

**Invariant: §7.4 never changes detector cadence.** Step 1 above says
"independently-qualified... candidates for this direction at `T`" — this
means candidates that **actually, independently qualify at `T` under their
own family's Stage 5 contract**, never a hypothetical or synthesized
candidate. §7.4 arbitrates only among whatever candidates genuinely exist
at `T`; it never creates, backdates, or "waits for" a candidate from a
family whose own detector cannot form a new candidate at that `T`. Each
family's new-candidate formation cadence remains exactly as frozen in §7:

| Family | New-candidate (`EARLY_SIGNAL`) formation cadence |
|---|---|
| `TREND_PULLBACK` | Only at its own frozen **15m decision boundaries** — the first such boundary `T_detect` at which [§7.1](#71-trend_pullback)'s preconditions and valid-retracement test hold. `TREND_PULLBACK` has **no** new-candidate formation at 5m boundaries that are not also 15m boundaries. |
| `COMPRESSION_BREAKOUT` | Every legal 5m decision boundary `T` at which [§7.2](#72-compression_breakout)'s fresh-cross qualification holds. |
| `CONFIRMED_BREAKOUT` | Every legal 5m decision boundary `T` at which [§7.3](#73-confirmed_breakout)'s fresh-cross qualification holds. |

Consequently, at a 5m `T` that is not a 15m boundary, `TREND_PULLBACK`
simply has no new candidate to submit to §7.4 arbitration at all — this is
a fact about detector cadence, not a §7.4 rule, and §7.4 must not be read
to override it.

#### 7.4.3 Precedence applies to new creation only

§7.4 arbitrates **simultaneous new candidates at the same decision
boundary** — it is **not** an inter-family kill switch for
already-created episodes. Explicitly:

- §7.4 **MUST NOT** retroactively destroy, replace, or mutate an
  already-active episode merely because a higher-precedence family
  candidate qualifies at some later decision boundary.
- Different-family active episodes **MAY** coexist, exactly as
  [§12](#12-episode-identity-and-deduplication) already allows — the
  precedence order in this section governs only which brand-new
  candidate(s) get created when two or more independently qualify at the
  *same* `T` over overlapping regions.
- No active episode is ever terminally transitioned (`INVALIDATED` /
  `EXPIRED` / `COMPLETED`) because a higher-precedence family's candidate
  later appeared — an active episode's lifecycle transitions are governed
  exclusively by [§13](#13-lifecycle-transition-semantics), never by §7.4.

#### 7.4.4 Worked vectors

11. **Boundary-touching entry zones count as overlap.** Candidate A's entry
    zone `[100, 110]`, candidate B's entry zone `[110, 120]`, same
    direction, same `T`. `max(100,110)=110 <= min(110,120)=110` → overlap.
    If A is `COMPRESSION_BREAKOUT` and B is `TREND_PULLBACK`, A is created
    and B is suppressed, cross-referenced to A.
12. **Three-family precedence.** As worked in
    [§7.4.2](#742-deterministic-arbitration-algorithm):
    `COMPRESSION_BREAKOUT [100,110]`, `CONFIRMED_BREAKOUT [105,115]`,
    `TREND_PULLBACK [150,160]` → create `COMPRESSION_BREAKOUT`, suppress
    `CONFIRMED_BREAKOUT`, create `TREND_PULLBACK`. If all three regions
    mutually overlapped, only `COMPRESSION_BREAKOUT` would be created.
13. **Different direction is unaffected.** A `LONG` `COMPRESSION_BREAKOUT`
    candidate with region `[100,110]` and a `SHORT` `TREND_PULLBACK`
    candidate with region `[100,110]` at the same `T` are **never**
    arbitrated against each other by §7.4 — arbitration runs **separately
    per direction** ([§7.4.2](#742-deterministic-arbitration-algorithm)
    step 1). Both may be created independently; any cross-direction
    relationship is exclusively the `REVERSAL_CANDIDATE` mechanism
    ([§13.3](#133-reversal_candidate-mechanics)), never §7.4.

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
| `setup_strength` | Detector-specific: `TREND_PULLBACK` → `1 − (retracement_pct / (PULLBACK_MAX_MULT * RANGE_PROXY_pct))` clamped `[0,1]` (deeper-but-still-valid retracements score lower); `COMPRESSION_BREAKOUT` → the **mean** `compression_score` over the **entire selected compression run** — the exact formula is frozen below; `CONFIRMED_BREAKOUT` → `min(1.0, (breakout_distance_beyond_level) / protection_buffer)` clamped `[0,1]`. |
| `trigger_strength` | `price_direction_agreement` at the confirming 5m bucket (already `∈[0,1]`). |
| `data_confidence` | **Per family, frozen exactly below** — never the global `consensus_confidence` rollup ([§6.3a](#63a-per-family-metric-scoped-quality-gates)). |

**`COMPRESSION_BREAKOUT`'s `setup_strength`, frozen exactly (amended — a
prior draft's "score at `compression_end_bucket`, which by construction
always equals `B15`" was factually wrong).** `compression_end_bucket` does
**not** always equal `B15`: [§7.2](#72-compression_breakout)'s own
multi-run worked vector (`b[0]..b[5]` compressed, `b[6]` not, `b[7]..b[13]`
compressed, `b[14]..b[15]` **not** compressed) already, explicitly,
freezes a case where the *selected* run is `[b[7], b[13]]` while
`b[15] = B15` — the selected run's own end bucket, `b[13]`, is strictly
**before** `B15`. The compression precondition only requires *some*
qualifying run to exist somewhere in the lookback ([§7.2](#72-compression_breakout)
step 3: "if zero runs qualify, `compressed = False`") — it never requires
`B15` itself to be part of the selected run. A "current-moment, score at
the most recent bucket" framing is therefore not well-defined in general.

Frozen instead: `setup_strength` is the **mean** `compression_score` over
**every bucket in the full selected maximal compression run**, inclusive
from `compression_start_bucket` through `compression_end_bucket`:

```text
setup_strength = sum(compression_score(b) for b in selected_run) / compression_length
```

Every bucket in the selected run already, by construction, satisfies
`compression_score >= COMPRESSION_THRESHOLD` (that is what made it part of
a qualifying run, [§7.2](#72-compression_breakout) steps 1–2) — the mean
is therefore a deterministic strength summary of the **entire structure
the detector actually selected**, not one arbitrary bucket of it (whether
first, last, min, or max), and it requires no claim about which bucket is
"current." **Implementation debt (owned by a future Stage 5 hardening PR,
not `#43`):** `analytics/forecasting_v2/compression_breakout.py`'s
window-selection walk already necessarily computes `compression_score` for
every bucket in the lookback (it must know each bucket's compressed/
not-compressed status to identify runs) — it does not yet expose the
resulting per-run mean, or the individual per-bucket scores it was
computed from, as a candidate field; both are discarded after run
selection today. A future `#44` PR must carry the canonical mean **BY
VALUE** in the candidate/result (e.g. a `setup_strength_compression_score:
float` field) so Stage 6 never recomputes `compression_score()` against
Stage 2 data Stage 5 has already read — the general "a stage that owns a
calculation must expose the canonical downstream fact it computed, by
value, rather than making a later stage recompute it" handoff invariant
this document also applies to `CONFIRMED_BREAKOUT`'s
`tick_size`/`protection_buffer` inputs (§12.5a) and to Stage 4's
numerical-evidence handoff ([§4.1a](#41a-stage-4-numerical-evidence-must-survive-the-stage-456-boundary)
below).

**`data_confidence` source, frozen exactly per family (amended — a prior
draft generically used `price_structure`-family confidence for every
family, which silently ignores the quality of a family whose data is
**mandatory** for a setup's own `EARLY_SIGNAL` decision).** Reuses
[§6.3a](#63a-per-family-metric-scoped-quality-gates)'s
required-family table — a setup's `data_confidence` component must
represent **every** family that table marks mandatory for that setup's
`EARLY_SIGNAL` decision, never fewer:

```text
TREND_PULLBACK:
    data_confidence = price_structure family confidence
                       at its setup-formation 15m bucket / 100.0
    (price_structure is TREND_PULLBACK's only mandatory family, §6.3a)

CONFIRMED_BREAKOUT:
    data_confidence = price_structure family confidence
                       at its setup-formation 1h structural-level decision
                       context / canonical setup bucket (§7.3) / 100.0
    (price_structure is CONFIRMED_BREAKOUT's only mandatory family --
     §6.3a is explicit this family carries NO taker_flow requirement at
     all, unlike COMPRESSION_BREAKOUT below)

COMPRESSION_BREAKOUT:
    data_confidence = min(
        price_structure family confidence at the fresh 5m trigger bucket,
        taker_flow      family confidence at the SAME fresh 5m trigger bucket
    ) / 100.0
    (COMPRESSION_BREAKOUT's EARLY_SIGNAL decision has TWO mandatory
     families, §6.3a -- the conservative min() ensures data_confidence
     cannot overstate quality by reporting only the better of the two)
```

The global six-family rollup (`consensus_confidence`) remains forbidden
as a `data_confidence` source for every family, per
[§6.3a](#63a-per-family-metric-scoped-quality-gates).
This is the single, exact `data_confidence` definition for §8 — it does
not create a second, conflicting definition anywhere else in this
document; [§17](#17-outcome--evaluation-model)'s outcome-record
`data_coverage_at_confirmation` field is a **separate**, confirmation-time
fact (frozen on its own terms, not a restatement of this `§8`
setup-formation-time component — see the amendment there).

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
- **Historical-truth rule (amended — `EARLY_SIGNAL` is user-visible too,
  not only `CONFIRMED`).** An entry zone already shown to the user in
  **any** already-published episode event — the initial `EARLY_SIGNAL`
  notification, any subsequent material pre-`CONFIRMED` zone-update
  notification, or `CONFIRMED` itself — **MUST NOT** be silently
  rewritten. Concretely:
  - the zone published in the `EARLY_SIGNAL` notification
    ([§16.1](#161-early_signal-notification-content-and-history-invariants-v2-v0))
    is immutable historical truth from the moment it is sent;
  - a later pre-`CONFIRMED` zone change (material or not, per the next
    bullet) is recorded as a **new** episode event — it never edits the
    `EARLY_SIGNAL` notification's own recorded value;
  - `CONFIRMED` may compute and freeze a new, final zone value — again a
    new event, never a rewrite of any earlier one.

  Every such prior published value is conceptually preserved in the
  episode's event history — reusing the same insert-once-per-event pattern
  frozen in [§2.1](#21-replay-behavior-for-late-arriving--corrected-data)
  for feature snapshots. This is a logical requirement; physical
  event-history persistence is implementation work, not specified here.
- **What update requires a new material notification (see
  [§16](#16-notification-materiality--anti-spam-thresholds) for the exact,
  normative threshold — stated here only as a pointer, not restated, to
  avoid two normative copies of the same rule):** not every pre-`CONFIRMED`
  zone change is material — only one whose bound moves by more than
  `0.5 * protection_buffer` (V2-v0), subject to
  [§16](#16-notification-materiality--anti-spam-thresholds)'s cooldown.
  The `CONFIRMED` transition (which freezes the zone) is **always**
  material, regardless of how small the final move was.

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

### 12.1 Logical identity (not a database key)

```text
episode_logical_key = (symbol, market_type, direction, setup_family, structural_anchor)
```

`structural_anchor` is family-specific, always a deterministic function of
already-closed data:

| Family | `structural_anchor` |
|---|---|
| `TREND_PULLBACK` | the `bucket_ts` of the 15m bucket establishing `trend_leg_extreme` ([§7.1](#71-trend_pullback)). |
| `COMPRESSION_BREAKOUT` | the `bucket_ts` of the first 15m bucket in the qualifying compression window ([§7.2](#72-compression_breakout)). |
| `CONFIRMED_BREAKOUT` | the `(bucket_ts, price)` of the 1h extreme defining the broken level, price **tick-normalized** per the exact deterministic rule in [§12.5](#125-tick-normalization-confirmed_breakout-structural-price) ([§7.3](#73-confirmed_breakout)). |

### 12.2 Creation identity is immutable

`episode_logical_key` is established **exactly once**, at the decision
boundary an episode is first created (its `EARLY_SIGNAL`), and **MUST NOT
mutate** for the rest of that episode's life — regardless of what later
decisions observe. This is the resolution to an ambiguity the original
text left open: it distinguished a qualification's *creation* identity
from a *later, newly observed* candidate anchor only implicitly. This
section makes the distinction explicit and normative:

- The **creation identity** is the `episode_logical_key` (and, for
  `CONFIRMED_BREAKOUT`, the creation-time tick-normalized level price and
  the creation-time `protection_buffer`) recorded when the episode was
  first created. It is the episode's permanent historical identity.
- An **observed candidate anchor** on any later decision — a fresh
  `trend_leg_extreme`/`compression_start_bucket`/`level_anchor_bucket`
  independently produced by the Stage 5 detector at that decision boundary
  — is compared **against the active episode's creation identity**, never
  against another observation's anchor, and never against a running
  average. Observing a shifted anchor on a later decision does **not**, by
  itself, rewrite the episode's creation identity.

### 12.2a Per-family structural mutability

_(Amended — a generic one-sentence "all operational facts frozen at
creation" rule contradicted `TREND_PULLBACK`'s own already-frozen
§7.1/§9 pre-confirmation update mechanic; replaced with exact per-family
rules.)_

§12.2 freezes the **identity** tuple (`episode_logical_key`). This section
freezes, **separately per family**, whether/how the **operational**
structural facts a family's own lifecycle logic (confirmation,
false-break, invalidation, entry zone, [§7](#7-setup-detectors)/
[§9](#9-entry-zone-semantics)/[§13](#13-lifecycle-transition-semantics))
consumes may evolve before `CONFIRMED` — a prior draft of this section
wrongly generalized one single rule ("every operational fact is frozen at
creation for the entire active life") across all three families. That
generalization is **wrong for `TREND_PULLBACK`**, which §7.1/§9 already,
explicitly, deliberately allow to update its `pullback_extreme`/entry
zone/`invalidation_price` at later pre-confirmation 15m re-evaluations —
and it must not be read as license for the *other two* families to do the
same, since their own §7.2/§7.3 text describes their structural facts as
fixed at the compression-window/level-selection moment, before
`EARLY_SIGNAL` is even reached. The three families have genuinely
different pre-confirmation mutability shapes; one sentence cannot
correctly describe all three.

**Critically, two *different* mechanisms must never be conflated:**
(1) an episode's **own, continuous re-evaluation** of its own structural
leg as later closed buckets arrive — a same-episode, self-consistent
process explicitly frozen by a family's own §7 text (this is what
`TREND_PULLBACK`'s pre-confirmation update is); versus (2) a **freshly,
independently-run Stage 5 detector invocation** at a later decision
boundary producing a brand-new candidate that [§12.3](#123-per-decision-classification-of-a-same-slot-candidate)
classifies as case (A)/(B)/(C) against the *active episode's creation
identity*. Mechanism (1) is a family-specific, §7-governed process,
entirely separate from §12's dedup/identity machinery. Mechanism (2) is
what [§12.3](#123-per-decision-classification-of-a-same-slot-candidate)'s
case-(B) "non-material drift" governs, and **that** mechanism's outcome —
a case-(B) *candidate's own independently-detected anchor/level/range* —
is what the rules below forbid feeding into a family's operational logic
in place of the family's own frozen/updating facts.

**`TREND_PULLBACK`:**

- **Immutable from creation, for the entire active life:** the episode's
  logical identity ([§12.1](#121-logical-identity-not-a-database-key)/
  [§12.2](#122-creation-identity-is-immutable)) — i.e. the **creation**
  `structural_anchor` (`trend_leg_extreme.bucket_ts` as first observed at
  `T_detect`), used by §12's dedup/identity machinery. This never changes,
  regardless of anything below.
- **While `EARLY_SIGNAL`, at each later LEGAL 15m re-evaluation boundary
  (mechanism (1) above, exactly as §7.1/§9 already freeze):**
  `pullback_extreme_low`/`pullback_extreme_high` **MAY** update if the
  retracement deepens further (the "deepest close so far" rule, §7.1); the
  dynamic entry-zone bound **MAY** update correspondingly (§9); the
  planned `invalidation_price` tracks the currently-valid
  `pullback_extreme` +/- `protection_buffer` per §7.1's formula. Every
  such update that crosses §16's materiality threshold is recorded as a
  **new**, immutable history event — never a silent rewrite of an earlier
  published value ([§9](#9-entry-zone-semantics)'s historical-truth rule).
  **None of these updates ever mutate the episode's creation identity** —
  they are the same episode's own structural leg continuing to be
  measured, not a new anchor.
- **Confirmation itself** (§7.1's 5m trigger) does **not** reference
  `trend_leg_extreme`/`pullback_extreme` at all — it is a pure fresh-5m
  `price_move_pct_median`-sign + `price_direction_agreement` check,
  independent of this section's structural-fact tracking by construction.
- **At `CONFIRMED`:** the entry-zone/`pullback_extreme`/planned
  `invalidation_price` facts valid **at that exact confirmation decision**
  freeze for the rest of the episode's life (§9's freeze-on-`CONFIRMED`
  rule) — no further updates of any kind after this point.
- **What §12.3's case-(B) observation means for `TREND_PULLBACK`:** a
  later, independently-detected candidate's own freshly-computed
  `trend_leg_extreme` (mechanism (2)) is compared against the episode's
  frozen **creation** `structural_anchor` for dedup purposes only ([§12.3](#123-per-decision-classification-of-a-same-slot-candidate)/
  [§12.4](#124-exact-driftmateriality-formulas)) — it plays no role in,
  and is never substituted into, the pre-confirmation `pullback_extreme`
  update process above, which is driven exclusively by mechanism (1).

**`COMPRESSION_BREAKOUT`:**

- **Frozen from `EARLY_SIGNAL` creation, for the entire active life —
  no pre-confirmation mutability mechanism exists for this family (unlike
  `TREND_PULLBACK`):** `compression_start_bucket`, `compression_end_bucket`,
  `range_low`, `range_high`, the confirmation boundary (the same
  `range_low`/`range_high` the breakout broke), the creation
  `protection_buffer`, the entry-zone geometry, and the planned
  `invalidation_price` they produce ([§7.2](#72-compression_breakout)) —
  all of these are already fixed as of the compression window's own
  selection, **before** `EARLY_SIGNAL` is even reached (§7.2's own text).
- The False-break rule ("`SHORT` holds iff `close <= range_low`") and the
  post-`CONFIRMED` structural invalidation trigger **always** evaluate
  against these same creation-time values — **never** a
  `range_low`/`range_high`/confirmation-boundary/invalidation geometry
  re-derived from a later, independently-detected, non-materially-drifted
  case-(B) candidate ([§12.3](#123-per-decision-classification-of-a-same-slot-candidate)),
  even though such a candidate is a legitimate observation of the *same*
  episode for dedup purposes. Later confirmation always checks the
  **same** creation range boundary.

**`CONFIRMED_BREAKOUT`:**

- **Frozen from `EARLY_SIGNAL` creation, for the entire active life —
  likewise no pre-confirmation mutability mechanism:** `level_anchor_bucket`,
  the raw broken level, `creation_identity_tick_size`/the normalized
  identity tick ([§12.5](#125-tick-normalization-confirmed_breakout-structural-price)/
  [§12.5a](#125a-tick-grid-is-frozen-at-episode-creation-confirmed_breakout)),
  the creation `protection_buffer`, the entry-zone geometry, and the
  planned `invalidation_price` ([§7.3](#73-confirmed_breakout)).
- `§7.3`'s structural-invalidation trigger and confirmation check **always**
  use these same creation-time values — **never** a broken level/geometry
  re-derived from a later case-(B) candidate's own independently-detected
  level, even though such a candidate is a legitimate observation of the
  *same* episode for dedup purposes (already explicit in
  [§12.4](#124-exact-driftmateriality-formulas)'s "the episode's original
  `structural_anchor`/`episode_logical_key` stays frozen" — this section
  makes clear the identical freeze applies to the *operational*
  confirmation/invalidation check, not merely the identity comparison).
  Later confirmation always uses the **same** creation broken level.

**General, reconciling §9 and §12 so they cannot contradict each other:**
§9's "may move only pre-`CONFIRMED`" is the **general envelope** every
family's zone updates must fit inside (never after `CONFIRMED`, always
recorded as new history, never a silent rewrite) — but §9 does **not**, by
itself, claim every family's zone *actually* moves pre-`CONFIRMED`; per
this section, only `TREND_PULLBACK` genuinely has a pre-confirmation
update mechanism (its own continuous mechanism-(1) re-evaluation).
`COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT`'s zones are already fixed at
creation and simply never exercise §9's "may move" clause in practice —
this is consistent with, not a violation of, §9's "may," which permits but
does not require movement. A later case-(B) observation's freshly-detected
anchor/level/range ([§12.3](#123-per-decision-classification-of-a-same-slot-candidate))
**MAY**, for any family, still be recorded **by value** as an
observational fact in that decision's event `decision_snapshot` — this
section never forbids *recording* it, only forbids **operationally
substituting** it for the frozen/independently-updating creation-time fact
in confirmation/false-break/invalidation logic.

### 12.3 Per-decision classification of a same-slot candidate

Define `slot = (symbol, market_type, direction, setup_family)`. At most one
**active** (non-terminal) episode may exist per `slot`
([§12.6](#126-suppression-at-most-one-active-episode-per-slot)). When a
Stage 5 detector produces a qualifying candidate for a `slot` that already
has an active episode, the candidate's structural anchor is classified
against that active episode's **creation identity**
([§12.2](#122-creation-identity-is-immutable)) into exactly one of three
outcomes:

| Case | Condition | Outcome |
|---|---|---|
| **(A) Exact match** | Candidate's canonical structural anchor equals the active episode's creation `structural_anchor` exactly. For `TREND_PULLBACK`/`COMPRESSION_BREAKOUT`: the same 15m anchor bucket. For `CONFIRMED_BREAKOUT`: **both** dimensions of the `(level_anchor_bucket, tick-normalized price)` pair ([§12.1](#121-logical-identity-not-a-database-key)) match — `candidate.level_anchor_bucket == creation.level_anchor_bucket` **AND** `candidate.tick_index == creation.tick_index`. Identical price with a *different* `level_anchor_bucket` is **not** case (A) — see the note below. | **Observation/update** of the existing active episode. `episode_logical_key` is unchanged (it already matched). |
| **(B) Non-material drift** | Candidate's anchor differs from the active episode's creation anchor, but the drift is within the family's frozen non-material threshold ([§12.4](#124-exact-driftmateriality-formulas)). | **Also an observation/update** of the *same* active episode. `episode_logical_key` **remains the original creation key** — the original persisted `structural_anchor` (and, for `CONFIRMED_BREAKOUT`, the original tick-normalized level price) stays the episode's immutable historical identity. The newly observed candidate anchor **MAY** be recorded by value in the new event's `decision_snapshot`/event payload as an observational fact, but **MUST NOT** silently rewrite `episode_logical_key` or the episode's original `structural_anchor`. |
| **(C) Material drift** | Candidate's anchor differs from the active episode's creation anchor by more than the family's frozen materiality threshold. | The candidate is **suppressed** for that decision ([§12.6](#126-suppression-at-most-one-active-episode-per-slot)/[§12.7](#127-suppression-is-not-a-queue)) — no second episode is created in the same `slot` while the active episode remains non-terminal. |

**`CONFIRMED_BREAKOUT`'s exact-match dimension is the whole pair, never
price alone.** [§12.1](#121-logical-identity-not-a-database-key) freezes
`CONFIRMED_BREAKOUT`'s `structural_anchor` as `(level_anchor_bucket,
tick-normalized price)` — a pair, not a scalar. Case (A) therefore
requires **both** components to match; a candidate whose tick-normalized
price equals the creation price exactly but whose `level_anchor_bucket`
differs is **not** an exact match, because the two `structural_anchor`
tuples are unequal. Such a candidate falls to case (B) or (C) purely on
the [§12.4](#124-exact-driftmateriality-formulas) price-drift formula —
`level_anchor_bucket` inequality by itself never makes it case (A), and
(per §12.4) never makes it material either. Example: creation
`(level_anchor_bucket=10:00, tick_index=660000)`; candidate
`(level_anchor_bucket=11:00, tick_index=660000)` — same tick, different
bucket → **not** case (A); `level_drift = 0`, which is `<= 2 *
active_creation_protection_buffer` → case (B), non-material drift; update
the existing episode; the creation logical key remains `(10:00,
tick_index=660000)`.

Case (A) and case (B) are both "update the existing active episode" from
`episode_logical_key`'s point of view — the only operational difference is
whether a newly observed anchor exists to optionally record as an
observation. Neither case ever produces a second episode in the same
`slot`, and neither case ever mutates the creation identity.

### 12.4 Exact drift/materiality formulas

**`TREND_PULLBACK` / `COMPRESSION_BREAKOUT`** (both use 15m anchor buckets,
`ANCHOR_DRIFT_BUCKETS = 4`, kept frozen from the prior text):

```text
A = active episode's creation structural_anchor (15m bucket_ts)
C = candidate's newly observed structural_anchor (15m bucket_ts)

bucket_distance = abs(C - A) / 15m      # exact integer bucket-count distance,
                                          # never approximate wall-clock seconds

bucket_distance <= ANCHOR_DRIFT_BUCKETS (4)  -> NON-MATERIAL (case B, §12.3)
bucket_distance >  ANCHOR_DRIFT_BUCKETS (4)  -> MATERIAL     (case C, §12.3)
```

`bucket_distance` **MUST** be computed as an exact integer count of aligned
15m buckets (`abs(C - A)` is always an exact multiple of `15m` because both
`A` and `C` are 15m bucket boundaries) — never as an approximate wall-clock
`abs(C - A).total_seconds() / 900` comparison, which is equivalent here but
is not the frozen form. Exactly `4` buckets away passes as non-material;
`5` buckets away is material. This rule is identical, independently, for
both `TREND_PULLBACK` and `COMPRESSION_BREAKOUT` — same threshold, same
15m bucket-count semantics, evaluated against each family's own
`structural_anchor`.

**`CONFIRMED_BREAKOUT`** (tick-normalized structural level price, compared
using the **active episode's creation-time** `protection_buffer` — never a
buffer recomputed at the candidate's own decision boundary, so the
threshold cannot move merely because a later candidate observed a
different volatility environment):

```text
active_creation_normalized_level_price = tick-normalized level price recorded
                                          when the active episode was created,
                                          normalized against that episode's
                                          OWN creation_identity_tick_size (§12.5a)
                                          (a Decimal, per §12.5)
active_creation_protection_buffer      = protection_buffer recorded when the
                                          active episode was created (the
                                          detector's native numeric value)

candidate_comparison_normalized_level_price =
    candidate's newly observed RAW level price, normalized per §12.5's
    algorithm against the ACTIVE EPISODE'S creation_identity_tick_size
    (§12.5a) -- NEVER against the candidate's own current/decision-time
    tick_size, even if the instrument's tick_size has since changed
    (a Decimal)
```

**Decimal domain (frozen; matches §12.5's rule exactly — the comparison
never crosses back into binary `float`, and never uses an epsilon/
tolerance fudge):**

```text
creation_buffer_decimal = Decimal(str(active_creation_protection_buffer))
level_drift_decimal     = abs(candidate_comparison_normalized_level_price
                               - active_creation_normalized_level_price)
threshold_decimal       = Decimal("2") * creation_buffer_decimal

level_drift_decimal <= threshold_decimal  -> NON-MATERIAL (case B, §12.3)
level_drift_decimal >  threshold_decimal  -> MATERIAL     (case C, §12.3)
```

`active_creation_protection_buffer` — the detector's native numeric
value — is converted to `Decimal` the same way [§12.5](#125-tick-normalization-confirmed_breakout-structural-price)
converts prices: via `Decimal(str(x))`, **never** `Decimal(x)` applied
directly to a `float` (which would carry that float's binary-fraction
artifacts into the comparison), and the resulting `level_drift_decimal`/
`threshold_decimal` are **never** converted back to `float` for the
comparison — the comparison itself happens entirely in the `Decimal`
domain. This freezes the deterministic *arithmetic representation* only;
it does **not** change the threshold value, which remains exactly `2 *
active_creation_protection_buffer`.

Exactly `threshold_decimal` of drift passes as non-material (the boundary
itself is inclusive on the non-material side). A candidate whose
`level_anchor_bucket` differs from the active episode's creation
`level_anchor_bucket` does **not**, by itself, make the candidate material
— only `level_drift_decimal` is compared (see also the case-(A) note in
[§12.3](#123-per-decision-classification-of-a-same-slot-candidate) for why
a bucket difference alone is not even an exact match, let alone a reason
for materiality). The episode's original `structural_anchor`/
`episode_logical_key` stays frozen regardless of which 1h bucket a later
observation's extreme happened to land in, exactly as
[§12.2](#122-creation-identity-is-immutable) requires.

Both `active_creation_normalized_level_price` and
`candidate_comparison_normalized_level_price` above are normalized against
the **same** grid — the active episode's `creation_identity_tick_size`
([§12.5a](#125a-tick-grid-is-frozen-at-episode-creation-confirmed_breakout))
— which is what makes `level_drift_decimal` a genuine market-price-drift
measurement rather than an artifact of comparing two different rounding
grids.

**Worked decimal-arithmetic example** (deliberately awkward inputs, to
exercise the `Decimal(str(...))` conversion): creation normalized level
`Decimal("66000.1")`, creation `protection_buffer` the `float` `164.5`,
candidate normalized level `Decimal("66329.1")` (both normalized against
the same creation `tick_size`).

```text
creation_buffer_decimal = Decimal(str(164.5))  = Decimal("164.5")
threshold_decimal       = Decimal("2") * Decimal("164.5") = Decimal("329.0")
level_drift_decimal     = abs(Decimal("66329.1") - Decimal("66000.1")) = Decimal("329.0")

Decimal("329.0") <= Decimal("329.0")  -> exact boundary -> NON-MATERIAL
```

### 12.5 Tick normalization (`CONFIRMED_BREAKOUT` structural price)

The prior text said `CONFIRMED_BREAKOUT`'s structural price is "rounded to
the reference exchange's `tick_size`" without freezing the exact rounding
rule. This is now frozen as one deterministic algorithm, using decimal
arithmetic (never binary-float modulo tricks, and never Python's built-in
`round()`, whose binary-float/round-half-to-even semantics are not the
contract being frozen here):

```text
price_decimal = Decimal(str(raw_level_price))
tick_decimal  = Decimal(str(tick_size))

tick_index = (price_decimal / tick_decimal) rounded to the nearest integer
             using ROUND_HALF_UP

normalized_level_price = tick_index * tick_decimal
```

Inputs (`raw_level_price`, `tick_size`) are always positive. String
construction (`Decimal(str(x))`) is required specifically to avoid binary
float artifacts that `Decimal(x)` on a `float` would otherwise introduce.
The integer `tick_index` is the canonical **equality identity** for the
normalized price (two prices are the "same" tick iff their `tick_index`
values are equal); `normalized_level_price` is its human-readable decimal
equivalent.

**Ordering constraint (load-bearing):** this normalization happens **only
after** the raw structural extreme has already been selected at full
stored precision by [§7.0c](#70c-extreme-tie-breaking-deterministic-structural-anchor-selection)'s
tie-breaking rule. It **MUST NOT** influence, and **MUST NOT** run before,
`§7.0c`'s extreme comparison/tie-breaking — `level_anchor_bucket`/
`level_price` as exposed by the Stage 5 `CONFIRMED_BREAKOUT` detector
(`analytics/forecasting_v2/confirmed_breakout.py`'s `structural_anchor`
property) remain the RAW, un-normalized facts; tick normalization is a
Stage 6 episode-identity/materiality construction step applied strictly
downstream of that raw fact, never a preprocessing step applied to the
inputs `§7.0c` compares.

Worked examples (`tick_size = 0.1`):

| Raw price | `tick_index` | `normalized_level_price` |
|---|---|---|
| `66200.04` | `662000` | `66200.0` |
| `66200.05` | `662001` (half rounds up) | `66200.1` |
| `66200.06` | `662001` | `66200.1` |

### 12.5a Tick grid is frozen at episode creation (`CONFIRMED_BREAKOUT`)

§12.5 freezes *how* a raw price is normalized. It does not, by itself, say
*which* `tick_size` a later candidate's price is normalized against when
comparing it to an already-active episode — and that is ambiguous if the
reference exchange's instrument metadata (`tick_size`) changes during the
episode's life. This is now frozen:

```text
creation_identity_tick_size = the validated reference-exchange tick_size
                               KNOWN AT T_create -- the same decision-time
                               instrument input the Stage 5 detector itself
                               used to compute protection_buffer/entry
                               zone/invalidation at creation
```

`creation_identity_tick_size` is an **immutable creation-time supporting
fact** of the episode — like `structural_anchor` itself
([§12.2](#122-creation-identity-is-immutable)), it is fixed once, at
`EARLY_SIGNAL` creation, and **MUST NOT** change for the life of the
episode, regardless of any later instrument-metadata change. It is **not**
an extra dimension of `episode_logical_key` — the logical structural
anchor remains conceptually `(level_anchor_bucket, normalized_level_price)`
([§12.1](#121-logical-identity-not-a-database-key)) — it is the grid
`normalized_level_price` is defined against, frozen alongside it.

```text
identity_tick_decimal = Decimal(str(creation_identity_tick_size))
```

The active episode's own `creation_normalized_level_price`/`tick_index`
(§12.5) are computed against `identity_tick_decimal` once, at creation.

**Comparing a later candidate against this active episode**
([§12.3](#123-per-decision-classification-of-a-same-slot-candidate)/
[§12.4](#124-exact-driftmateriality-formulas)) **MUST** normalize the
candidate's `raw_level_price` using the **active episode's**
`creation_identity_tick_size` — **never** the candidate's own
decision-time (possibly different, if the instrument's `tick_size`
changed) `tick_size`:

```text
candidate_comparison_normalized_level_price =
    normalize(candidate.raw_level_price, active_episode.creation_identity_tick_size)   # §12.5's algorithm, active episode's grid
```

The current, decision-time instrument `tick_size` **MAY** still
legitimately affect the *candidate's own* Stage 5 outputs where an
existing detector rule already says so (e.g. its own freshly-computed
`protection_buffer`) — that is unrelated to, and unchanged by, this
freeze. What this section forbids is re-normalizing the *active episode's*
identity/comparison grid using anything other than that episode's own
creation-time `tick_size`. A brand-**new** episode, created after the old
one reaches a terminal state, uses the new candidate's own decision-time
validated `tick_size` as **its own** `creation_identity_tick_size` — grids
are per-episode, fixed at that episode's creation, never shared or
inherited across episodes.

**Persistence:** `creation_identity_tick_size` (and the `tick_index`/
`normalized_level_price` it produces) **MUST** be recorded **by value** in
the episode's creation event/history, so that state reconstruction after a
process restart ([§12.10](#1210-execution-namespace-livereplay-history-scope))
never needs to re-read *today's* instrument metadata to know what grid an
existing active episode's identity was built on. This document freezes the
required logical fact only — it does not prescribe a physical JSON
key/schema for it (that remains implementation work, per
[§0.1](#01-what-this-document-is-not)).

**Worked vector — instrument `tick_size` changes after episode creation:**

```text
Episode created:
    raw level = 100.04
    creation_identity_tick_size = 0.1
    -> identity_tick_decimal = Decimal("0.1")
    -> creation_normalized_level_price = Decimal("100.0")
    -> creation tick_index = 1000

Later, the reference exchange's instrument metadata changes:
    current (decision-time) tick_size is now 0.01

A candidate arrives with raw level = 100.04, compared against the
still-ACTIVE episode above:

  CORRECT (creation grid, per this section):
    candidate_comparison_normalized_level_price
        = normalize(100.04, creation_identity_tick_size=0.1)
        = Decimal("100.0")   (tick_index 1000)
    -> level_drift_decimal = abs(Decimal("100.0") - Decimal("100.0")) = 0
    -> exact match on price (case A/B per §12.3, depending on level_anchor_bucket)

  NON-CONFORMING (current grid -- MUST NOT be done):
    100.04 / 0.01 => tick_index 10004, normalized 100.04
    -> would introduce spurious drift purely from a metadata change,
       not a real market move -- forbidden by this section.
```

**Clean-room audit finding: instrument metadata has no as-of/historical
model today — this is a gap upstream of episode creation, not just of the
active-episode comparison above.** `creation_identity_tick_size` (frozen
above) solves comparison against an *already-created* episode. But the
detector's very first read of `tick_size` — at the moment a candidate is
first evaluated, before any episode exists — is itself not yet
historically reproducible: `storage/stage2_schema.sql`'s
`exchange_instruments` table holds **one mutable row per `(exchange,
symbol, market_type)`**, and `Database.fetch_v2_instrument`/
`storage/v2_setup_readers.py`'s `read_v2_instrument` read "the ONE row at
the EXACT `(exchange, symbol, market_type)`" — there is no `bucket_ts`/
as-of scoping. Replaying historical decision `T` **after** the reference
exchange's `tick_size` has since changed reads **today's** `tick_size`,
not the value that was actually in effect at `T` — so a REPLAY run cannot
exactly reproduce a LIVE run's historical `protection_buffer`, entry zone,
invalidation price, `normalized_level_price`, or
`MIN_VALID_PLANNED_RISK`-tick check for that historical decision. This is
a **genuine replay-correctness gap**, distinct from (and upstream of)
`creation_identity_tick_size`'s active-episode-comparison freeze above.
**Not fixed in this docs-only PR** — freezing the required target: every
Stage 5 candidate that depends on `tick_size` **MUST** carry the actual
validated decision-time `tick_size` **by value** in its own output (this
already effectively happens for `CONFIRMED_BREAKOUT`'s
`creation_identity_tick_size` once an episode is created downstream of
it — the gap is the *detector's own* read of "current" instrument
metadata, before that point). Whether the correct fix is (a) an as-of/
historical `exchange_instruments` model (versioned rows, each with an
effective-from `bucket_ts`), or (b) accepting that `tick_size` changes are
rare enough that "the value in effect at ingestion time was already
persisted somewhere in Stage 1/2 and Stage 5 should read *that* historical
value instead of the current row," is **implementation work for a future
pre-Stage-6 hardening PR** — this document freezes the requirement
("historical decisions MUST be exactly reproducible from data that was
actually in effect at that historical `T`"), not the physical mechanism.

**Clean-room audit finding: `Decimal` is a deterministic-arithmetic
mechanism, never a JSON persistence leaf.** [§12.5](#125-tick-normalization-confirmed_breakout-structural-price)
freezes `Decimal(str(...))`/`ROUND_HALF_UP` as the **arithmetic**
mechanism for tick normalization — but `analytics/forecasting_v2/events.py`'s
`V2EpisodeEvent` JSON-leaf validator (`_deep_freeze`) accepts only
`bool`/`str`/`int`/`None`/finite-`float`/UTC-`datetime` as leaves; a raw
`Decimal` is **not** an accepted leaf type and would raise
`V2EventInputError` at construction. This document therefore freezes the
persisted, JSON-safe representation of every `Decimal`-computed fact
**separately** from the arithmetic mechanism that produces it:

```text
tick_index                  -> persist as a plain int (the canonical
                                equality identity, §12.5 -- exact, no
                                precision loss possible for an int)
normalized_level_price       -> persist as a canonical decimal STRING
                                (str(the_decimal_value), e.g. "66200.1") --
                                NEVER as a bare float leaf, which could
                                silently reintroduce the exact binary-
                                float imprecision §12.5's whole point is
                                to avoid
creation_identity_tick_size  -> persist as a canonical decimal STRING
                                (str(the_validated_tick_size)), for the
                                same reason
raw_level_price               -> persist as the detector's own raw,
                                un-normalized numeric fact (a float, since
                                it is exactly what the Stage 5 candidate
                                already exposes, never re-derived through
                                Decimal) — kept as a SEPARATE historical
                                fact from normalized_level_price, never
                                conflated with it
```

`tick_index` (an exact `int`) remains the canonical equality identity for
comparisons reconstructed from persisted history (§12.5); the
decimal-string forms of `normalized_level_price`/
`creation_identity_tick_size` are exactly reconstructable back into
`Decimal(the_string)` without ever round-tripping through binary `float`.
This freezes the **required JSON-safe shape** only — the exact physical
JSON key names remain implementation work for the future Stage 6
foundation PR that first constructs `structural_anchor`/`decision_snapshot`
for a `CONFIRMED_BREAKOUT` episode, per
[§0.1](#01-what-this-document-is-not)'s "not a schema" scope limit.

### 12.6 Suppression: at most one active episode per slot

```text
at most ONE active (non-terminal) episode per (symbol, market_type, direction, setup_family)

if a candidate is classified as materially different (case C, §12.3) while
an active episode of the same slot already exists:
    the new candidate is SUPPRESSED (not created) until the active episode
    reaches a terminal state (INVALIDATED / EXPIRED / COMPLETED)
```

This directly resolves both failure modes the Product Contract flags: it
does **not** mint a new episode every 5m bucket (an exact match or
non-material drift both update the same episode, per
[§12.3](#123-per-decision-classification-of-a-same-slot-candidate)), and
it does **not** let one old episode block *all* future BTC setups — only
same-`slot` candidates are suppressed; a different family, or the opposite
direction, is free to open independently.

This same-slot suppression mechanism is scoped **exactly** to "an ACTIVE
episode occupies this slot" — it ends at the precise decision boundary
that episode becomes terminal, never one moment before or after. What
happens immediately after that boundary (the terminal-episode cooldown) is
a **separate** mechanism, frozen in
[§12.8](#128-terminal-episode-cooldown-exact-clock) and kept explicitly
distinct from this one in [§12.7](#127-suppression-is-not-a-queue).

### 12.7 Suppression is not a queue

A candidate can be suppressed under three distinct mechanisms — same-slot
active-episode existence ([§12.6](#126-suppression-at-most-one-active-episode-per-slot),
case C of [§12.3](#123-per-decision-classification-of-a-same-slot-candidate)),
terminal cooldown ([§12.8](#128-terminal-episode-cooldown-exact-clock)), or
family precedence ([§7.4](#74-setup-family-precedence-and-deduplication))
— and all three share one invariant: **suppressed, not queued**. No
suppressed candidate is ever stored as a pending future episode, and none
automatically becomes an episode later merely because a blocking condition
subsequently clears. The three mechanisms have **distinct** clearing
conditions, and only a mechanism's own condition ends *that* mechanism's
suppression — never a wall-clock timeout, never "the market moved back":

- **Same-slot ACTIVE suppression** ([§12.6](#126-suppression-at-most-one-active-episode-per-slot)):
  exists **only** while an `ACTIVE` (non-terminal) episode occupies that
  `slot`. This mechanism, specifically, ends **at** the decision boundary
  the active episode transitions to a terminal state
  (`INVALIDATED`/`EXPIRED`/`COMPLETED`, per [§13](#13-lifecycle-transition-semantics))
  — not one moment later. It does **not**, itself, extend into or overlap
  with the cooldown window below; the two are separate mechanisms with
  separate, non-overlapping reasons, evaluated back-to-back in time.
- **Cooldown suppression** ([§12.8](#128-terminal-episode-cooldown-exact-clock)):
  begins immediately once same-slot ACTIVE suppression ends (i.e. at
  `T_terminal`, the same boundary the episode became terminal — see
  §12.8) and blocks a new same-slot episode until the cooldown's first
  eligible decision boundary is reached. Between `T_terminal` and that
  first eligible boundary, a same-slot candidate is suppressed **by the
  cooldown mechanism**, not by same-slot ACTIVE suppression — the active
  episode that used to occupy the slot is already terminal by then, so
  there is nothing left for same-slot ACTIVE suppression to block on.
- **Family-precedence suppression** ([§7.4](#74-setup-family-precedence-and-deduplication)):
  blocks a lower-precedence candidate **only at the one decision boundary
  `T`** where the arbitration ran
  ([§7.4.2](#742-deterministic-arbitration-algorithm)). It is **not** a
  persistent blocker tied to the higher-precedence episode's lifecycle —
  that episode remaining `ACTIVE` at a later decision boundary is **not**,
  by itself, a reason to keep suppressing the lower-precedence family.
  [§7.4.3](#743-precedence-applies-to-new-creation-only) is explicit that
  precedence never retroactively affects an already-created episode and
  arbitrates only simultaneous new candidates at the same `T`; this
  section must not be read to contradict that. Concretely: if a
  lower-precedence candidate loses arbitration at `T`, and later — at any
  `T' > T` — the same detector independently qualifies again with a fresh
  candidate, that candidate is evaluated purely against **its own
  family's** same-slot/cooldown rules
  ([§12.3](#123-per-decision-classification-of-a-same-slot-candidate)/
  [§12.6](#126-suppression-at-most-one-active-episode-per-slot)/
  [§12.8](#128-terminal-episode-cooldown-exact-clock)) at `T'`. It is
  **not** compared against, and **not** blocked by, the still-active
  higher-precedence episode created at `T`; `§7.4` arbitration at `T'`
  runs only if another same-direction, overlapping, creation-eligible
  *new* candidate also exists at `T'` itself.

In every case, once the specific blocking condition clears, opening a new
episode still requires a candidate that **independently qualifies**
according to the normal detector/state-machine rules **at an eligible
decision boundary** — never a resurrection of the earlier, stale,
suppressed candidate. This matters because V2 must not open a stale setup,
anchored to a price/time the market has since moved away from, just
because an older episode or arbitration outcome happened to lapse.

**Worked vector — same-slot ACTIVE suppression and cooldown are sequential,
never merged into one mechanism:**

```text
An active episode in slot (symbol, market_type, LONG, TREND_PULLBACK)
transitions to INVALIDATED at T_terminal = 14:00.

At T=14:00 (T_terminal itself): same-slot ACTIVE suppression ENDS here --
  the episode that occupied the slot is now terminal, so there is no
  longer an ACTIVE episode for §12.6 to suppress against.

From T=14:00 onward, a DIFFERENT mechanism -- terminal cooldown (§12.8) --
  is what blocks a new same-slot episode:
    cooldown buckets (INVALIDATED, 3*5m): [14:00,14:05), [14:05,14:10), [14:10,14:15)
    T=14:05 and T=14:10: a same-slot candidate is suppressed BY COOLDOWN,
      not by same-slot ACTIVE suppression (nothing ACTIVE remains in the
      slot at that point).
    T=14:15: cooldown's first eligible boundary. A same-slot candidate
      that independently qualifies here MAY create a new episode.

Overall, the slot remains blocked continuously from 14:00 to 14:15, but
for two DIFFERENT, non-overlapping reasons in sequence -- never one merged
"still blocked somehow" mechanism: same-slot ACTIVE suppression accounts
for none of this window (it already ended exactly at 14:00); cooldown
accounts for all of it (14:00 through 14:15).
```

**Worked vector — family-precedence suppression is not a persistent
blocker.** `T=12:15` and `T=12:30` are both legal `TREND_PULLBACK`
new-candidate boundaries (both are 15m boundaries,
[§7.4.2](#742-deterministic-arbitration-algorithm)'s cadence invariant) —
this vector deliberately does **not** use a 5m-only boundary for
`TREND_PULLBACK`, since it has no new candidate to offer there at all:

```text
T=12:15: LONG COMPRESSION_BREAKOUT candidate, region [100,110]
         LONG TREND_PULLBACK    candidate, region [105,108]
         both independently qualified and creation-eligible
         (T=12:15 is a legal 15m boundary for TREND_PULLBACK's own cadence)

§7.4 arbitration at T=12:15 (§7.4.2): COMPRESSION_BREAKOUT precedes
TREND_PULLBACK; regions overlap (max(100,105)=105 <= min(110,108)=108)
  -> COMPRESSION_BREAKOUT episode created (ACTIVE)
  -> TREND_PULLBACK suppressed FOR T=12:15 ONLY, cross-referenced to the
     COMPRESSION_BREAKOUT episode's history

T=12:30: the NEXT legal 15m TREND_PULLBACK formation boundary.
         TREND_PULLBACK's own slot (symbol, market_type, LONG,
         TREND_PULLBACK) has no active episode and no cooldown in effect.
         TREND_PULLBACK independently qualifies again with a valid region.
         No other same-direction, overlapping, creation-eligible NEW
         candidate exists at T=12:30 (the COMPRESSION_BREAKOUT episode is
         already-created and ACTIVE -- it is not itself a "new candidate
         at T=12:30", so §7.4 has nothing to arbitrate at T=12:30).

  -> TREND_PULLBACK MAY create its own episode at T=12:30.
  -> The ACTIVE COMPRESSION_BREAKOUT episode created at T=12:15 does NOT
     block it -- family-precedence suppression does not persist past the
     decision boundary at which it was evaluated (§7.4.3), and §7.4 never
     alters TREND_PULLBACK's own 15m formation cadence
     (§7.4.2's cadence invariant).
```

### 12.8 Terminal-episode cooldown — exact clock

**Terminal-episode cooldown (V2-v0):**

| Terminal state | Cooldown before a new episode of the same `(direction, family)` may open |
|---|---|
| `INVALIDATED` | `3` closed 5m buckets (15 min) — prevents immediate flip-flop re-triggering right at the broken level. |
| `EXPIRED` / `COMPLETED` | `1` closed 5m bucket (5 min) — a clean resolution, not a broken premise, needs less cooldown. |

The exact clock, frozen precisely:

```text
T_terminal = the decision boundary of the terminal event (the decision at
             which the episode transitioned to INVALIDATED / EXPIRED / COMPLETED)

cooldown buckets = the CLOSED 5m buckets strictly AFTER T_terminal

earliest eligible new-episode decision boundary:
    INVALIDATED          -> T_terminal + 3 * 5m = T_terminal + 15m
    EXPIRED / COMPLETED  -> T_terminal + 1 * 5m = T_terminal + 5m
```

A candidate arriving at exactly the first eligible decision boundary
**MAY** create a new episode if it genuinely, independently qualifies at
that boundary — the boundary being reached is not itself a qualification.
Cooldown scope remains the `slot` — `(symbol, market_type, direction,
setup_family)` — **not** the structural anchor; it applies regardless of
whether a later candidate's anchor would have matched the terminated
episode's anchor. Cooldown suppression is governed by
[§12.7](#127-suppression-is-not-a-queue) — suppressed, not queued.

All of the above (`ANCHOR_DRIFT_BUCKETS`, the `2x` `CONFIRMED_BREAKOUT`
materiality multiplier, cooldown lengths) are V2-v0 parameters,
`rules_version`-participating.

### 12.9 Worked vectors

1. **Exact-key match.** Active `TREND_PULLBACK` episode created with
   `structural_anchor = 12:00` (15m bucket). A later candidate observes
   `trend_leg_extreme.bucket_ts = 12:00` again. Case (A): update the
   existing episode; `episode_logical_key` unchanged.
2. **`TREND_PULLBACK` drift exactly 4 buckets.** Creation anchor `12:00`;
   candidate anchor `13:00`. `bucket_distance = abs(13:00 - 12:00) / 15m =
   4`. `4 <= 4` → case (B), non-material: update the existing episode;
   `episode_logical_key` remains anchored at `12:00`.
3. **`TREND_PULLBACK` drift 5 buckets.** Creation anchor `12:00`; candidate
   anchor `13:15`. `bucket_distance = abs(13:15 - 12:00) / 15m = 5`. `5 >
   4` → case (C), material: candidate suppressed while the `12:00`-anchored
   episode remains active.
4. **`COMPRESSION_BREAKOUT`, same symmetric rule.** Creation
   `compression_start_bucket = 09:00`; candidate `10:00` → `bucket_distance
   = 4` → non-material, update. Candidate `10:15` → `bucket_distance = 5` →
   material, suppressed. Identical mechanics to vectors 2–3, evaluated
   against `COMPRESSION_BREAKOUT`'s own `structural_anchor`.
5. **`CONFIRMED_BREAKOUT` drift exactly `2 * creation_buffer`.** Active
   episode created at level `66000`, creation `protection_buffer = 150`.
   Candidate tick-normalized level `66300`: `level_drift = abs(66300 -
   66000) = 300 = 2 * 150`. `300 <= 300` → case (B), non-material: update
   the existing episode; original level `66000` remains the identity.
6. **`CONFIRMED_BREAKOUT` drift `> 2 * creation_buffer`.** Same active
   episode (`66000`, buffer `150`). Candidate tick-normalized level
   `66300.1` (assuming the tick-normalized difference genuinely exceeds
   `300`): `level_drift > 300` → case (C), material: candidate suppressed
   while the `66000`-anchored episode remains active. (Note: `66299` also
   remains non-material, `level_drift = 299 <= 300`.)
7. **Tick normalization, below/at/above the tick midpoint** (`tick_size =
   0.1`): `66200.04 → tick_index 662000 → 66200.0`; `66200.05 → tick_index
   662001 (exact half, rounds up) → 66200.1`; `66200.06 → tick_index 662001
   → 66200.1`.
8. **`INVALIDATED` terminal at `12:20`.** `T_terminal = 12:20`. Cooldown
   buckets: `[12:20,12:25)`, `[12:25,12:30)`, `[12:30,12:35)`. A same-slot
   candidate at `T=12:25` or `T=12:30` remains suppressed. The earliest
   eligible decision boundary for a new same-slot episode is `T=12:35`.
9. **`COMPLETED`/`EXPIRED` terminal at `12:20`.** `T_terminal = 12:20`.
   Cooldown bucket: `[12:20,12:25)`. Earliest eligible decision boundary is
   `T=12:25`.
10. **Suppressed candidate is not automatically resurrected.** A
    materially-different `TREND_PULLBACK` candidate is suppressed at `T=13:15`
    (vector 3) while an active episode anchored at `12:00` exists. The
    `12:00` episode later reaches `INVALIDATED` at `T=14:00`; cooldown
    clears at `T=14:15`. The `13:15` candidate is **not** resurrected at
    `T=14:15` merely because the blocker cleared — a new episode may only
    be created by a candidate that **independently qualifies** at an
    eligible decision boundary at or after `T=14:15`, evaluated fresh
    against that boundary's own data, per
    [§12.7](#127-suppression-is-not-a-queue).

### 12.10 Execution namespace: `LIVE`/`REPLAY` history scope

This is required before `#44` (the persisted-history read foundation)
because it defines the exact scope a state-machine history read is
allowed to see. The Multi-model Framework already stores every
`V2EpisodeEvent` namespaced by `run_kind` and `run_id`
([§3](#3-v2-modelversion-identity), `storage/stage2_schema.sql`'s
`v2_episode_events` key). This freezes the state-machine's read scope in
terms of that existing namespace — it adds **no** new schema:

```text
execution_stream = (run_kind, run_id)
```

Episode-identity reconstruction, same-slot/active-episode lookup
([§12.3](#123-per-decision-classification-of-a-same-slot-candidate)/
[§12.6](#126-suppression-at-most-one-active-episode-per-slot)), cooldown
lookup ([§12.8](#128-terminal-episode-cooldown-exact-clock)), and
`preexisting_opposite_active_set(T)` lookup
([§13.3.1](#1331-exact-cardinality-preexisting_opposite_active_set-and-pairwise-cross-references))
**MUST NEVER** mix:

- `LIVE` history with `REPLAY` history;
- one `REPLAY` `run_id`'s history with a different `REPLAY` `run_id`'s
  history.

**`REPLAY`:** every research replay run has its own explicitly-distinct
`run_id` and sees, and can ever see, only its own `execution_stream`'s
episode history. Two replay runs over the same or overlapping historical
data remain fully isolated from each other.

**`LIVE`:** a `LIVE` `run_id` represents a **logical live stream** — not
an individual OS process's lifetime. A `LIVE` `run_id` used by a
deployed/shadow V2 stream **MUST remain stable** across:

- process restart;
- systemd service restart;
- host process recreation;

for the same logical live deployment stream. **Do NOT generate a fresh
random `LIVE` `run_id` on every process start.** A restart that mints a
new `run_id` would make the state machine's `execution_stream` view start
empty — its active episodes and cooldowns would silently disappear from
that view — which would incorrectly permit duplicate/new episodes to be
created for slots that, from the real market's perspective, already have
an active episode. This is a correctness requirement, not an operational
nicety: the state machine's entire same-slot/cooldown/reversal apparatus
([§12](#12-episode-identity-and-deduplication)/[§13](#13-lifecycle-transition-semantics))
is meaningless if its own restart silently resets what it can see.

If an operator **intentionally** starts a genuinely new, isolated `LIVE`
stream under a deliberately different `run_id` (e.g. standing up a second
parallel shadow deployment), that is an explicit **new** execution
namespace by design — not a normal restart, and not a violation of the
stability requirement above.

**This does not add `run_id` to `episode_logical_key`.** Two distinct
concepts stay distinct:

```text
execution namespace:  (run_kind, run_id)                                            -- §3, this section
market episode logical key: (symbol, market_type, direction, setup_family,
                              structural_anchor)                                      -- §12.1
```

One-active-episode-per-`slot` and cooldown semantics
([§12.6](#126-suppression-at-most-one-active-episode-per-slot)/
[§12.8](#128-terminal-episode-cooldown-exact-clock)) are enforced
**within** one `execution_stream` — never across two different
`execution_stream`s, even for the identical `slot`.

**Worked vectors:**

- **`LIVE` process restart preserves the active-episode view.** A `LIVE`
  stream with `run_kind=LIVE`, `run_id="v2-shadow-live"` has an episode
  `ACTIVE` in some `slot` at `T=12:20`. The process crashes and a new
  process starts at `T=12:23`, resuming with the **same**
  `run_kind=LIVE`, `run_id="v2-shadow-live"`. The `#44` history
  reconstruction for this `execution_stream` **MUST** see the `12:20`
  active episode and its full lifecycle history — exactly as if the
  process had never restarted. Minting a new random `run_id` at restart
  would be **non-conforming** behavior for a normal `LIVE` restart.
- **`REPLAY` isolation.** A replay run `run_kind=REPLAY`,
  `run_id="replay-2026-08-17-001"` does not see, and cannot mutate, the
  `LIVE`/`"v2-shadow-live"` execution stream's history (or any other
  `REPLAY` run's history) — its same-slot/cooldown/reversal state is
  computed purely from its own `execution_stream`'s events.

### 12.11 Identity classification is not the same question as "does a persisted event exist"

Cases (A) and (B) in [§12.3](#123-per-decision-classification-of-a-same-slot-candidate)
say a matching/non-materially-drifted candidate is an "observation/update"
of the existing active episode. This answers **which episode** a
candidate belongs to — it does **not**, by itself, answer **whether this
decision boundary requires a new persisted history event**. These are two
separate questions, and conflating them would turn "the same episode
tracked over time" (the Product Contract's core requirement,
`V2_PRODUCT_CONTRACT.md` §5.2) into "the same `episode_id`, but an
immutable-history event spammed every single decision boundary solely
because the detector returned the same or similarly-anchored candidate
again" — which defeats the purpose of tracking one episode instead of
emitting a new signal every 5m the way V1 does.

Freeze the separation explicitly:

```text
identity classification (§12.3, case A or B)
    answers: WHICH episode does this decision's candidate belong to?
    -- routes the candidate to the existing episode;
    -- never creates a second episode;
    -- never mutates the episode's creation identity.

persisted-event necessity
    answers: DOES this decision boundary require a new immutable history
    event for that episode?
    -- governed by OTHER, already-frozen rules -- never implied merely by
       case A/B classification itself.
```

A new persisted event is required only when another already-frozen rule
says a history fact/event exists at that decision boundary — for example
(non-exhaustive, each already frozen elsewhere in this document):

- a lifecycle state transition ([§13](#13-lifecycle-transition-semantics));
- a required pre-`CONFIRMED` entry-zone change that
  [§9](#9-entry-zone-semantics)'s historical-truth rule requires recording
  as a new event (never a silent rewrite of an earlier notification's
  values);
- a required cross-reference/event, e.g. a `REVERSAL_CANDIDATE`
  ([§13.3](#133-reversal_candidate-mechanics)/[§13.3.1](#1331-exact-cardinality-preexisting_opposite_active_set-and-pairwise-cross-references))
  or a family-precedence suppression cross-reference
  ([§7.4.2](#742-deterministic-arbitration-algorithm));
- any other explicitly-frozen material/history-worthy update (e.g. a
  materiality-threshold-crossing notification update,
  [§16](#16-notification-materiality--anti-spam-thresholds)).

If **none** of those other rules require an event at that decision
boundary — no episode-visible fact changed, and no other section of this
document requires a record — then an exact-match or non-material-drift
re-observation **MAY** be a pure no-op with respect to the immutable
event history: it routes to the existing episode (per §12.3) but writes
**no** new `V2EpisodeEvent`. This document does **not** require, and does
**not** permit, minting one insert-only event every 5m *solely* because
the detector happened to return the same (or non-materially-drifted)
candidate again.

This distinction is load-bearing precisely because it prevents "the same
episode tracked over time" (correct) from silently becoming "the same
`episode_id`, but arbitrary event spam every decision boundary"
(incorrect, and a direct violation of the reduced-notification-noise
intent `V2_PRODUCT_CONTRACT.md` §5.2/§9 already establish). It does
**not** alter [§9](#9-entry-zone-semantics)'s existing historical-truth
requirement in the other direction either: when §9 says a zone change
**MUST** be recorded as a new event, it still **MUST** be recorded — this
section only clarifies that *routing* (§12.3) is not, by itself, a
sufficient condition to write one.

**Worked vector — Case A repeat observation, no changed episode-visible
fact, no persisted event required:** an active `TREND_PULLBACK` episode's
creation anchor is `12:00`. At `T=12:15`, a candidate is observed again
with `structural_anchor = 12:00` (case A, exact match) and no other
episode-visible fact has changed (no lifecycle transition, no §9 zone
change, no cross-reference to record). This decision boundary routes to
the same episode (§12.3, case A) and requires **no** new persisted
history event — it is a legitimate no-op in the event history, not a
violation of "one episode over time," and not evidence of a missing
event.

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

**The final candidate-age-eligible bucket is never simultaneously a
confirmation opportunity AND an expiry (clean-room audit amendment — closes
a potential off-by-one/precedence ambiguity).** Precedence level 2
(completion/expiry) is evaluated *before* level 3 (confirmation) at one
boundary — this ordering is only safe if candidate-age expiry's own
trigger condition, by construction, can **never** be true at a boundary
that also legitimately confirms. This is now frozen explicitly:
**candidate-age expiry (`§14`) fires iff the deadline decision boundary is
reached AND that same boundary's own confirmation check did not hold** —
never "age reached the limit" evaluated as an independent fact blind to
whether this exact boundary also confirmed. Concretely, for a family whose
`CONFIRMATION_MAX_AGE` (or `PULLBACK_MAX_AGE`) is `N` buckets: the `N`-th
eligible bucket **is** still a fully valid confirmation opportunity — "the
deadline elapses" means bucket `N` closed *without* the confirming
condition holding on it, not merely that bucket `N` was reached. If
bucket `N`'s own close satisfies the family's confirmation trigger, the
episode transitions to `CONFIRMED` at that boundary — `EXPIRED` is reached
only if bucket `N` closes and the confirming condition does **not** hold.
Framed the same way [§13.1](#131-transition-precedence) already frames
completion/expiry: **confirmation and candidate-age expiry are mutually
exclusive by construction**, exactly like completion/expiry above — this
is a clarification of an existing, already-intended shape, not a new rule,
and it removes any dependency on the precedence-order list to arbitrate
between the two at the exact deadline boundary (there is nothing left to
arbitrate, since they cannot both be true). See
[§14](#14-candidate-expiry-and-expected-horizons) for the exact worked
vectors, one per family, demonstrating this at the deadline bucket itself.

### 13.2 Allowed transitions

```text
EARLY_SIGNAL -> CONFIRMED     confirmation criteria met (§7, per family)
EARLY_SIGNAL -> INVALIDATED   structural invalidation reached before confirming
EARLY_SIGNAL -> EXPIRED       max candidate age elapsed without confirming (§14)

CONFIRMED    -> WEAKENING     evidence-quality degradation (below)
CONFIRMED    -> INVALIDATED   structural invalidation reached
CONFIRMED    -> COMPLETED     horizon elapsed, analytical_MFE_R reached MIN_MFE_R_FOR_COMPLETION at some point
                               (§18.2/§18.2a; terminal_reason=HORIZON_COMPLETION)
CONFIRMED    -> EXPIRED       horizon elapsed, analytical_MFE_R never reached MIN_MFE_R_FOR_COMPLETION on a
                               COMPLETE observed path (terminal_reason=HORIZON_NO_COMPLETION), OR the
                               observed path is incomplete and has not already proven the threshold
                               (terminal_reason=DATA_INCOMPLETE, §18.2a.1) -- not invalidated either way

WEAKENING    -> CONFIRMED     recovery: evidence-quality criteria restored (below)
WEAKENING    -> INVALIDATED   structural invalidation reached
WEAKENING    -> COMPLETED     horizon elapsed, same MIN_MFE_R_FOR_COMPLETION/terminal_reason rule as above
WEAKENING    -> EXPIRED       horizon elapsed, same terminal_reason rule as above (HORIZON_NO_COMPLETION or DATA_INCOMPLETE)
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

**Exact executable predicate (clean-room audit amendment — the prior text's
"`price_direction_agreement(5m)` opposes the episode's direction" was not,
by itself, computable).** `ConsensusFeatureVector.price_direction_agreement`
(`analytics/feature_engine/consensus.py`'s `_direction_agreement`) is an
**unsigned** `[0,1]` magnitude — "what fraction of exchanges agree with
*whichever* majority sign," with the majority's own sign discarded by
construction (`max(neg, flat, pos) / len(values)`). It cannot, alone,
answer "opposes the episode's direction," because it does not carry a
direction at all. The signed fact is a **separate** field,
`price_move_pct_median` (same module) — the frozen predicate combines
both:

```text
opposing_5m_bucket(direction, consensus_row) iff:
    LONG:  price_move_pct_median < 0  AND  price_direction_agreement > 0.5
    SHORT: price_move_pct_median > 0  AND  price_direction_agreement > 0.5
```

**`price_direction_agreement > 0.5`, STRICT — never `>=` (amended after a
tech-lead review found the prior `>=` draft wrong).** `_direction_agreement`
(`analytics/feature_engine/consensus.py`) is `max(neg, flat, pos) /
len(values)` — with **two** contributing exchanges, one opposing and one
non-opposing, this evaluates to exactly `0.5`: a **tie**, not a majority.
The frozen prose this predicate implements is "**more than half** of
contributing exchanges now disagree" — `0.5` is not more than half of
anything, it is exactly half. `price_direction_agreement == 0.5` is
therefore **not** opposition under any contributing-exchange count (for
`N` exchanges, `0.5` can only arise from an exact even split — never a
genuine majority). `CONFIRMED → WEAKENING` fires when `opposing_5m_bucket`
is `TRUE` for `WEAKEN_BUCKETS = 2` **consecutive** closed 5m buckets — an
evidence-quality signal, never itself a price-level check (that is
invalidation's job, [§10](#10-structural-invalidation)). `WEAKENING →
CONFIRMED` recovery requires `opposing_5m_bucket` to be `FALSE` (see the
streak semantics below) for `RECOVER_BUCKETS = 1` closed 5m bucket.

**Edge cases, frozen exactly:**

| Case | `opposing_5m_bucket` value |
|---|---|
| `price_direction_agreement == 0.5` exactly | **`FALSE`** — a tie is not "more than half" opposing, regardless of the sign condition. See the worked two-contributor vector below. |
| `price_direction_agreement > 0.5` and the sign condition holds | `TRUE`. |
| `price_move_pct_median == 0` | `FALSE` — neither `< 0` nor `> 0` holds for either direction; a flat median is neutral, not opposing. |
| `price_direction_agreement` or `price_move_pct_median` is `None`/missing from the consensus row | **`UNAVAILABLE`**, not `FALSE` and not `TRUE` — see below. |
| The `price_structure` family fails its own coverage/confidence gate ([§6.3a](#63a-per-family-metric-scoped-quality-gates)) for this bucket | **`UNAVAILABLE`** — a corrupted/unusable `price_structure` reading is never treated as evidence either way. |
| The 5m bucket itself is `UNAVAILABLE` (missing entirely, [§6.3](#63-coverage--degraded-behavior--fail-closed)) | **`UNAVAILABLE`**. |

**Worked vector — a two-exchange tie is NOT opposition.** Exactly two
contributing exchanges report `price_move_pct` for this 5m bucket: one
negative (opposing a `LONG` episode), one positive (non-opposing).
`_direction_agreement`: `neg=1, pos=1, flat=0`,
`max(1,0,1)/2 = 0.5`. `price_direction_agreement = 0.5`, which is **not**
`> 0.5` → `opposing_5m_bucket = FALSE` for this bucket, regardless of
`price_move_pct_median`'s sign. A 50/50 split MUST NOT be described as, or
treated as, a majority opposing the episode.

**`UNAVAILABLE` is a third value, never coerced to `FALSE` or `TRUE`.**
Missing/corrupted/unusable data is evidence of nothing — per this
document's general principle ([§5.2](#52-missing-percentile-handling--never-none--0),
[§6.3](#63-coverage--degraded-behavior--fail-closed)), it MUST NOT be
silently read as "recovery" (that would let a data outage masquerade as
the market un-opposing) and MUST NOT be silently read as "still opposing"
either (that would let a data outage manufacture a false weakening).

**Consecutive-streak semantics (amended — corrects a prior draft that
contradicted the already-frozen "consecutive" requirement): `UNAVAILABLE`
BREAKS consecutiveness — it resets the streak, exactly like a valid
non-opposing observation does, never merely "pauses" it.** The prior
draft's "pause, don't reset" framing is wrong: `WEAKEN_BUCKETS = 2
consecutive closed 5m buckets` is a claim about **consecutive, actually
observed** opposing evidence — `TRUE → UNAVAILABLE → TRUE` is **not** two
consecutive qualifying closed 5m buckets, it is one qualifying bucket,
then a gap with no evidence at all, then a second, independently-starting
qualifying bucket. Frozen exactly:

```text
Opposing streak (drives CONFIRMED -> WEAKENING, threshold WEAKEN_BUCKETS=2):
    opposing_5m_bucket == TRUE          -> increment opposing streak
    opposing_5m_bucket == FALSE         -> RESET opposing streak to 0
    opposing_5m_bucket == UNAVAILABLE   -> RESET opposing streak to 0

Recovery streak (drives WEAKENING -> CONFIRMED, threshold RECOVER_BUCKETS=1):
    opposing_5m_bucket == FALSE         -> increment recovery streak
    opposing_5m_bucket == TRUE          -> RESET recovery streak to 0
    opposing_5m_bucket == UNAVAILABLE   -> RESET recovery streak to 0
```

`UNAVAILABLE` is **never** counted as opposition and **never** counted as
recovery — in both directions it resets whichever streak is running,
because it breaks the run of *actually observed* consecutive evidence
that the frozen `WEAKEN_BUCKETS`/`RECOVER_BUCKETS` counts require. With
`RECOVER_BUCKETS = 1`, a single valid (`FALSE`) observed non-opposing
bucket is sufficient for recovery — but an `UNAVAILABLE` bucket is
**not** that single valid observation, so missing data alone can never,
by itself, recover an episode from `WEAKENING`, nor can it manufacture a
`WEAKENING` transition by masquerading as opposing evidence.

**Worked vector — `TRUE → UNAVAILABLE → TRUE` does NOT weaken.** Bucket 1:
`opposing_5m_bucket = TRUE` (streak = 1). Bucket 2: `UNAVAILABLE` (streak
resets to 0). Bucket 3: `opposing_5m_bucket = TRUE` (streak = 1, **not**
2). `WEAKEN_BUCKETS = 2` is never reached — `WEAKENING` does **not** fire.
A genuine 2-consecutive-bucket streak requires two directly adjacent
`TRUE` buckets with no `UNAVAILABLE`/`FALSE` bucket between them.

**§10 reconciliation — quality degradation does NOT itself create a second,
independent path to `WEAKENING`.** [§10](#10-structural-invalidation)'s
"a drop in `model_confidence`, a coverage degradation, or a weakening
trigger moves an episode toward `WEAKENING`" MUST NOT be read as freezing
two independent transition paths (one opposing-price-evidence path, above,
and a separate "quality itself degraded" path). There is exactly **one**
frozen `CONFIRMED → WEAKENING` predicate — `opposing_5m_bucket`, above.
Low/missing `price_structure` quality does not bypass this predicate or
trigger `WEAKENING` on its own; its **only** effect is making
`opposing_5m_bucket = UNAVAILABLE` for that bucket (per the coverage-gate
row in the edge-case table above), which — per the streak semantics just
frozen — **resets** any in-progress opposing streak, exactly like any
other `UNAVAILABLE` bucket. §10's "coverage degradation... moves an
episode toward `WEAKENING`" is therefore correct only in this indirect
sense (degraded quality can produce `UNAVAILABLE` buckets that reset a
*recovery* streak, delaying return to `CONFIRMED`) — it is never a second,
independent trigger.

### 13.3 `REVERSAL_CANDIDATE` mechanics

Resolved per `V2_PRODUCT_CONTRACT.md` §5.3's guidance, modeled exactly as
that section's suggested shape: an event/update on the existing episode,
plus independent creation/qualification of a genuinely separate
opposite-direction episode — not a destructive conversion.

```text
REVERSAL_CANDIDATE cross-references fire exactly when:
    one or more NEW opposite-direction episodes reach EARLY_SIGNAL at one
    decision boundary T (§7, any family)
    AND
    preexisting_opposite_active_set(T) (§13.3.1) is non-empty

effect (§13.3.1 freezes the exact cardinality):
    - each newly-created opposite-direction episode begins its own, fully
      independent lifecycle under this document's normal rules (§12, §13)
      — it is not a special episode type;
    - for EVERY newly-created episode N at T and EVERY episode E in
      preexisting_opposite_active_set(T), exactly ONE REVERSAL_CANDIDATE
      event is attached to E's history as an informational
      cross-reference E -> N; E's own state is UNCHANGED by this event.
```

**Hard invariant:** `INVALIDATED` alone **never** creates a
`REVERSAL_CANDIDATE` event. The trigger is exclusively "a new opposite
episode independently reached `EARLY_SIGNAL`" — an episode transitioning to
`INVALIDATED` with no independently-qualifying opposite candidate produces
**no** `REVERSAL_CANDIDATE` event, full stop. This directly implements
`V2_PRODUCT_CONTRACT.md` §5.3's "MUST require the opposite direction to
independently satisfy its own scenario-entry requirements."

#### 13.3.1 Exact cardinality: `preexisting_opposite_active_set` and pairwise cross-references

The prior text said a `REVERSAL_CANDIDATE` event attaches to "the
pre-existing episode" (singular), which is ambiguous — multiple
different-family episodes of one direction **MAY** be simultaneously
active ([§12](#12-episode-identity-and-deduplication)). This freezes
deterministic cardinality:

```text
preexisting_opposite_active_set(T) =
    the set of episodes, of the direction OPPOSITE the newly-created
    episode(s), that:
      - existed BEFORE decision boundary T (created at some T' < T);
      - remain ACTIVE (non-terminal) AFTER their own lifecycle
        transitions for T are applied (§13.4 step 2) -- i.e. are still
        non-terminal at the point new-episode creation for T is
        finalized (§13.4 step 7).

Episodes newly CREATED at T itself are NEVER members of this set --
"pre-existing" excludes same-T creations, on either side of the
direction split.
```

For **every** newly-created episode `N` at `T` and **every** `E` in
`preexisting_opposite_active_set(T)`, create exactly **one**
`REVERSAL_CANDIDATE` cross-reference `E -> N`. If `k` pre-existing
opposite episodes survive `T` and `m` new opposite-direction episodes are
created at `T`, exactly `k * m` pairwise cross-references are created —
never fewer (no "first-match-only" shortcut that drops some pairs), never
more (no duplicate cross-references, no cross-reference for a candidate
that did not survive to `EARLY_SIGNAL`).

**Only an episode that actually reaches `EARLY_SIGNAL` creation
participates.** A candidate suppressed under
[§12.6](#126-suppression-at-most-one-active-episode-per-slot)/
[§12.8](#128-terminal-episode-cooldown-exact-clock)/
[§7.4](#74-setup-family-precedence-and-deduplication) never reaches
`EARLY_SIGNAL` and therefore **never** generates, and never receives, a
`REVERSAL_CANDIDATE` cross-reference — a suppressed candidate is not an
episode at all ([§12.7](#127-suppression-is-not-a-queue) — suppressed,
not queued).

**Two brand-new opposite-direction episodes created at the same `T` do
NOT cross-reference each other.** Both are, by construction, excluded
from `preexisting_opposite_active_set(T)` — neither existed before `T` —
so no `REVERSAL_CANDIDATE` is created between them; simultaneous same-`T`
creation on both sides of the direction split is not itself a reversal
relationship.

**Worked vectors:**

- **Two pre-existing opposite episodes, one new episode.** Two `SHORT`
  episodes (`SHORT#1`, `SHORT#2`, different families) are `ACTIVE` and
  survive their own lifecycle evaluation at `T`. One new `LONG` episode
  is created at `T`. `preexisting_opposite_active_set(T) = {SHORT#1,
  SHORT#2}`. Result: exactly 2 cross-references — `SHORT#1 -> LONG_new`,
  `SHORT#2 -> LONG_new`.
- **Two pre-existing opposite episodes, two new episodes.** Same two
  surviving `SHORT` episodes; two independently-created `LONG` episodes
  at `T` (`LONG#1`, `LONG#2`, from two different families that both
  survived §7.4 arbitration with non-overlapping regions). Result:
  `2 * 2 = 4` pairwise cross-references — `SHORT#1 -> LONG#1`,
  `SHORT#1 -> LONG#2`, `SHORT#2 -> LONG#1`, `SHORT#2 -> LONG#2`.
- **Suppressed opposite candidate creates zero cross-references.** A
  `SHORT` candidate at `T` is suppressed by §7.4 family precedence (never
  reaches `EARLY_SIGNAL`). A pre-existing `ACTIVE` `LONG` episode exists.
  Result: **zero** `REVERSAL_CANDIDATE` cross-references — the suppressed
  candidate is not an episode and cannot participate as `N`.
- **No pre-existing opposite episode.** Two brand-new `LONG` episodes are
  created at the same `T` (different families, non-overlapping regions);
  no `SHORT` episode exists at all. `preexisting_opposite_active_set(T) =
  {}` (empty — the two new `LONG` episodes are excluded from each other's
  set by the "same-`T` creations are never pre-existing" rule, and there
  is no `SHORT` episode to populate it otherwise). Result: **zero**
  `REVERSAL_CANDIDATE` cross-references.

### 13.4 Same-boundary orchestration order

[§12.7](#127-suppression-is-not-a-queue)'s same-`T`-only family-precedence
scoping and [§13.3.1](#1331-exact-cardinality-preexisting_opposite_active_set-and-pairwise-cross-references)'s
`preexisting_opposite_active_set(T)` both depend on one deterministic
ordering of what happens at a single decision boundary `T`. This is a
**semantic** freeze — it constrains the required *outcome* at every `T`,
not a mandate that a Stage 6 implementation must literally execute these
as eight sequential passes:

```text
1. Reconstruct the episodes ACTIVE immediately before T (the outcome of
   the previous decision boundary).
2. Evaluate and apply lifecycle transitions (§13.1/§13.2/§13.2a) for
   those existing episodes, AT T. Record, for any episode that transitions
   to a terminal state (INVALIDATED/EXPIRED/COMPLETED) in this step, that
   its T_terminal = T (§12.8).
3. Derive TWO SEPARATE views from step 2's outcome -- they are NOT the
   same set, and neither may substitute for the other (see the
   "two distinct views" note below):
   3a. surviving_active_set(T) = the non-terminal episodes remaining
       after step 2. Used ONLY for same-slot ACTIVE occupancy (§12.6)
       and preexisting_opposite_active_set(T) (§13.3.1).
   3b. per-slot terminal/cooldown state as of T = each slot's most
       recent terminal episode and that episode's T_terminal, drawn from
       PERSISTED terminal-episode history -- which INCLUDES an episode
       that transitioned to terminal in step 2 of THIS SAME T
       (T_terminal = T is a valid, immediately-effective value, per
       §12.8). Used ONLY for cooldown eligibility (§12.8).
   Both views are fixed BEFORE any of steps 4-8 run.
4. Evaluate independently-qualified NEW detector candidates for T, per
   each family's own formation cadence (§7.4.2's cadence invariant).
5. Apply same-slot/cooldown creation eligibility to those NEW candidates:
   a slot is creation-eligible at T iff (i) surviving_active_set(T) (3a)
   has no episode in that slot, AND (ii) per 3b, T is at or after that
   slot's earliest eligible new-episode decision boundary (§12.8) --
   INCLUDING when the slot's most recent terminal episode became
   terminal at this very T (T_terminal = T), which always makes T itself
   ineligible (§12.8's cooldown is >= 1 bucket in every case).
6. Apply §7.4 family precedence among the creation-eligible NEW
   candidates that remain.
7. Create the accepted EARLY_SIGNAL episodes.
8. Emit REVERSAL_CANDIDATE pairwise cross-references (§13.3.1) from each
   E in preexisting_opposite_active_set(T) (3a, fixed BEFORE any of this
   T's own new creations) to each newly-created opposite-direction
   episode from step 7.
```

**Two distinct views, never conflated (this corrects an internal
inconsistency in an earlier draft of this section, which claimed a single
"active set at `T`" served both same-slot occupancy *and* cooldown
lookup):** `surviving_active_set(T)` (3a) answers "is there currently an
`ACTIVE` episode occupying this slot?" — an episode that became terminal
in step 2 of this same `T` is, correctly, **excluded** from it. Cooldown
eligibility (3b) answers a **different** question — "has enough time
elapsed since this slot's *most recent* terminal episode?" — and that
question's answer depends on the terminal episode's `T_terminal`
regardless of whether `T_terminal` is `T` itself or many boundaries
earlier; excluding a same-`T` terminal episode from 3a must **never** be
misread as excluding it from 3b's cooldown lookup too. Concretely: a slot
whose sole occupant became terminal *at this exact `T`* has **no**
surviving active episode (3a is empty for that slot) **and** is
**simultaneously** within its just-started cooldown window as of this
same `T` (3b) — [§12.6](#126-suppression-at-most-one-active-episode-per-slot)'s
same-slot ACTIVE blocker and [§12.8](#128-terminal-episode-cooldown-exact-clock)'s
cooldown blocker are sequential, never both empty at once, exactly as
[§12.7](#127-suppression-is-not-a-queue) already freezes — this section's
job is only to make sure the *orchestration order* doesn't accidentally
produce a gap between them by consulting the wrong view for cooldown.

This ordering exists specifically to prevent four order-dependent bugs:

- **A same-boundary terminal transition must not be treated as still
  `ACTIVE` for reversal purposes at that same `T`.** `surviving_active_set(T)`
  (3a) is derived *after* step 2 applies that `T`'s own lifecycle
  transitions, so an episode that became `INVALIDATED`/`EXPIRED`/
  `COMPLETED` at `T` is already excluded from it.
- **A same-boundary terminal transition must NOT be read as leaving the
  slot immediately open.** Because 3b's cooldown lookup is sourced from
  persisted terminal history (which includes this `T`'s own transition),
  not from 3a's survivor set, a fresh same-slot candidate at this exact
  `T` is still correctly cooldown-suppressed — see the worked vectors
  below.
- **Two new opposite-direction episodes created at the same `T` must not
  be treated as "pre-existing" relative to each other.** 3a is fixed
  *before* steps 4–7 run, so neither of two same-`T` creations can ever
  appear in the other's `preexisting_opposite_active_set(T)` — this is
  the same fact [§13.3.1](#1331-exact-cardinality-preexisting_opposite_active_set-and-pairwise-cross-references)
  states directly.
- **Candidate input iteration order must not change the reversal
  output.** 3a's membership does not depend on the order in which step
  4's candidates are enumerated or step 6's arbitration walk visits them.

This section does not require any future implementation PR to literally
structure its code as eight sequential passes, nor to maintain 3a/3b as
two physically separate data structures — only that the **observable
outcome** at every `T` is indistinguishable from having followed this
order and this two-view distinction. An implementation that computes an
equivalent result through a different internal mechanism (e.g. one
per-slot state lookup that already accounts for both facts) remains
conforming.

No contradiction with an already-frozen lifecycle rule was found while
deriving this ordering — in particular, it does not change
[§13.3](#133-reversal_candidate-mechanics)'s hard invariant that
`INVALIDATED` alone never creates a `REVERSAL_CANDIDATE` event (a
same-`T` `INVALIDATED` transition in step 2 simply removes that episode
from 3a's survivor set; it still never itself triggers a cross-reference).

**Worked vectors — same-`T` terminal transition and cooldown:**

```text
Before T=14:00: an ACTIVE LONG TREND_PULLBACK episode occupies slot
    (symbol, market_type, LONG, TREND_PULLBACK).

At T=14:00 (a legal 15m boundary, both for lifecycle transitions and for
TREND_PULLBACK's own new-candidate cadence):
    step 2: the existing episode transitions to INVALIDATED. T_terminal = 14:00.
    step 3a: surviving_active_set(14:00) does NOT include this episode
             (it is now terminal) -- the slot has no surviving ACTIVE occupant.
    step 3b: per-slot cooldown state for this slot: most recent terminal
             episode's T_terminal = 14:00 (INVALIDATED, 3*5m cooldown,
             §12.8) -- earliest eligible new-episode boundary = 14:15.
    step 4: a FRESH LONG TREND_PULLBACK candidate independently qualifies
             at this same T=14:00.
    step 5: same-slot/cooldown eligibility for this fresh candidate:
             (i) 3a has no ACTIVE occupant for this slot -- passes;
             (ii) 3b: T=14:00 is NOT >= 14:15 (the slot's earliest
                  eligible boundary) -- FAILS.
    -> the fresh candidate is SUPPRESSED BY COOLDOWN (§12.8), not created.
       No new episode at T=14:00, even though the same-slot ACTIVE
       blocker (§12.6) alone had already cleared.

Same structure, EXPIRED/COMPLETED terminal at T=14:00 (1*5m cooldown):
    T_terminal = 14:00 -> earliest eligible new-episode boundary = 14:05.
    A fresh same-slot candidate at this same T=14:00 is likewise
    SUPPRESSED BY COOLDOWN (14:00 is not >= 14:05).

In every one of these cases, the same-slot ACTIVE blocker (§12.6) and the
cooldown blocker (§12.8) are never simultaneously absent for a slot whose
occupant just went terminal -- the moment §12.6's blocker clears (exactly
at T_terminal), §12.8's cooldown blocker is already, unbrokenly, in
effect for that identical T, per [§12.7](#127-suppression-is-not-a-queue)'s
"sequential, never merged, never a gap" framing.
```

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

**Worked vectors — the final candidate-age-eligible bucket, per family
(clean-room audit amendment, [§13.1](#131-transition-precedence)):**

```text
TREND_PULLBACK (PULLBACK_MAX_AGE = 8 x 15m buckets = a 2h AGE WINDOW,
amended -- a prior draft of this vector incorrectly modeled
PULLBACK_MAX_AGE as "8 confirmation-check boundaries spaced 15m apart."
It is not: PULLBACK_MAX_AGE bounds the AGE of the candidate; confirmation
itself is checked at every LATER 5m decision boundary within that window,
per §7.1's own frozen text ("evaluated at 5m decision boundaries...
earliest possible confirmation is T_confirm = T_detect + 5m"). §7.1's
15m-only cadence governs NEW-CANDIDATE FORMATION (§7.4.2's cadence
invariant), never confirmation of an already-EARLY_SIGNAL episode.):

  T_detect = 12:00 (a legal 15m formation boundary).
  T_deadline = T_detect + PULLBACK_MAX_AGE = T_detect + 2h = 14:00.
  Eligible 5m confirmation boundaries: T_detect+5m (12:05), T_detect+10m
  (12:10), ... through T_detect+120m (14:00) -- 24 later 5m confirmation
  opportunities, one per closed 5m bucket strictly after T_detect, up to
  and including the deadline boundary itself.
  No qualifying resumption trigger holds on any of the first 23
  opportunities (12:05 through 13:55).
  At T=14:00 (the 24th and final eligible boundary, the deadline itself),
  the resumption trigger (price_move_pct_median sign matches the trend
  direction AND price_direction_agreement >= 2/3, §7.1 -- this trigger's
  own frozen threshold is unrelated to and unchanged by §13.2a's separate
  STRICT ">" WEAKENING threshold) DOES hold on B5_confirm = selected_bucket(5m, 14:00).
  => CONFIRMED at T=14:00 -- the deadline boundary is a valid confirmation
     opportunity like every other eligible 5m boundary, not an automatic
     expiry. Had the trigger NOT held at 14:00, T=14:00 would instead be
     EXPIRED (deadline elapsed without confirming) -- the two outcomes are
     mutually exclusive by construction, never both computed as
     independently "true" at 14:00 (§13.1).

COMPRESSION_BREAKOUT (CONFIRMATION_MAX_AGE = 3 x 5m buckets):
  EARLY_SIGNAL at T1=12:00. Eligible confirming buckets: T1+5m (12:05),
  T1+10m (12:10), T1+15m (12:15) -- bucket 3 (the deadline) closes at
  12:15. Buckets 1-2 neither confirm nor false-break (boundary-equality
  HOLD, §7.2). At T=12:15 (bucket 3), the close is strictly beyond the
  breakout boundary -- confirming.
  => CONFIRMED at T=12:15. Had bucket 3 instead been a HOLD (neither
     confirming nor invalidating), T=12:15 would be EXPIRED.

CONFIRMED_BREAKOUT (CONFIRMATION_MAX_AGE = 8 x 5m buckets): identical
  shape -- the 8th eligible bucket (T1 + 40m) is a valid confirmation
  opportunity; EXPIRED fires only if that same bucket does not confirm.
```

**Worked vector — invalidation and confirmation both apparent on the final
eligible bucket.** Same `COMPRESSION_BREAKOUT` setup as above
(`EARLY_SIGNAL` `SHORT` at `T1=12:00`, broken below `range_low`). Suppose
at the deadline bucket `T=12:15` the reference exchange's close is
**simultaneously** read two ways depending on which side of the range one
naively compares it to — this cannot actually happen under the frozen
one-sided direction-aware rule ([§7.2](#72-compression_breakout)): a
`SHORT` candidate's confirming condition ("closes strictly below
`range_low`") and its false-break/invalidating condition ("`close >
range_low`," the negation) are **logical complements** of the same
one-sided comparison — exactly one of them is true for any given close
value, never both. [§13.1](#131-transition-precedence)'s level-1
"invalidation always wins" therefore never actually has to arbitrate a
tie against level-3 confirmation at the deadline bucket either — like the
expiry/confirmation pair above, invalidation and confirmation are mutually
exclusive by construction at the same boundary, for the same underlying
reason (one-sided, complementary comparisons never both hold). The
precedence list's ordering remains correct and necessary for genuinely
independent conditions (e.g. a `CONFIRMED` episode's post-confirmation
invalidation trigger racing against an unrelated same-boundary
`WEAKENING`/recovery evidence-quality signal, where the two conditions are
**not** logical complements of one comparison) — it is not, however, ever
actually exercised between confirmation and either candidate-age-expiry or
structural invalidation at the `EARLY_SIGNAL -> CONFIRMED` boundary,
because those pairs cannot both be true there.

---

## 15. Entry-feasibility evaluation

Three genuinely distinct concepts (re-amended — separates a **LIVE,
no-future-data** notification gate from a **retrospective, future-data**
evaluation grade, which an earlier draft conflated by using a `T+90s`
sampled price to decide whether the earlier notification at `T` was sent —
impossible for a live notifier, which cannot wait for a bar that has not
closed yet):

1. **Analytical setup validity** — the detector's own gates in
   [§7](#7-setup-detectors) are satisfied. This alone does not mean the
   trade is still enterable.
2. **`send_time_notification_eligibility`**
   ([§15.1](#151-send_time_notification_eligibility)) — evaluated **at the
   moment an event is emitted** (`EARLY_SIGNAL` or `CONFIRMED`), using
   **only data already closed as of that event's own decision boundary**.
   This is the live gate deciding whether the event is allowed to produce
   a normal actionable notification *right now*. **No future data
   participates.**
3. **`assumed_entry_feasibility`**
   ([§15.2](#152-assumed_entry_feasibility)) — a retrospective,
   evaluation-only grade of an event that has *already* been emitted (or
   already suppressed), computed once the required future 1-minute bar
   actually exists. It answers "would the scenario still have been
   realistically enterable after a realistic reaction/delivery delay?" and
   feeds `lateness_status`/acceptance metrics. It **never** decides whether
   the earlier notification was sent — that data did not exist at send
   time.

Both checks apply **independently to both `EARLY_SIGNAL` and `CONFIRMED`**,
each scoped to that event's own decision boundary; no check — live or
retrospective — may use the *other event's* inputs (an `EARLY_SIGNAL`
check never uses `CONFIRMED`-time data, and vice versa, per
[§9](#9-entry-zone-semantics)'s historical-truth rule).

### 15.1 `send_time_notification_eligibility`

**LIVE — no future data.** Evaluated at the exact decision boundary an
event is emitted (`EARLY_SIGNAL`'s `detection_timestamp`, or `CONFIRMED`'s
own decision boundary), using only values the detector has **already
computed** to reach that event — never a separately sampled future price.

```text
event_reference_time  = detection_timestamp                          # EARLY_SIGNAL
                       = the CONFIRMED decision boundary (T_confirm)  # CONFIRMED
event_reference_price = the reference exchange's closed price the detector
                         already used to decide THIS event -- e.g.
                         close_price(B15_detect) for TREND_PULLBACK's
                         EARLY_SIGNAL, confirmation_close_price for any
                         family's CONFIRMED, the breakout bucket's own
                         close for a breakout family's EARLY_SIGNAL
                         (per-detector, §7 -- always a value already
                         computed to reach this event, never sampled
                         separately)
event_entry_zone_upper / event_entry_zone_lower = the entry zone AS IT
                         EXISTS at event_reference_time (the EARLY_SIGNAL
                         zone for EARLY_SIGNAL; the just-frozen CONFIRMED
                         zone for CONFIRMED, §9)
event_invalidation_price = the structural invalidation level known AS OF
                         event_reference_time (per-detector, §7)
OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(setup_timeframe, B, reference_price)

LONG:  send-eligible iff event_reference_price <= event_entry_zone_upper + OVERSHOOT_TOLERANCE
                          AND event_invalidation_price not yet breached (reference exchange,
                              closed 5m bucket) as of event_reference_time
SHORT: send-eligible iff event_reference_price >= event_entry_zone_lower - OVERSHOOT_TOLERANCE
                          AND event_invalidation_price not yet breached as of event_reference_time
```

Every input above already exists at `event_reference_time` because the
detector computed it to reach this event in the first place
([§2](#2-no-lookahead-semantics-per-input-family)'s no-lookahead rule) —
**no `T + delay` sample of any kind participates in this check.**

**If `send-eligible` is false:** the normal actionable notification for
this event is suppressed **immediately, at send time** — the episode is
still created/updated, stored, and evaluated exactly like any other
([§17](#17-outcome--evaluation-model)); it simply never produces that
particular actionable notification
([§16](#16-notification-materiality--anti-spam-thresholds)). This applies
independently to `EARLY_SIGNAL` and `CONFIRMED` — an `EARLY_SIGNAL`
suppressed at send time has **no bearing** on `CONFIRMED`'s own, later,
independent check, and vice versa. A `CONFIRMED` episode whose send-time
check fails still transitions through the normal lifecycle rules
([§13](#13-lifecycle-transition-semantics)) exactly as before.

### 15.2 `assumed_entry_feasibility`

**Retrospective evaluation only — future data permitted as outcome
input, never as a decision input.** This is a **grading concept, not a
send-time gate**, computed **after the fact**, once the required future
1-minute bar has actually closed — chronologically later than, and never
an input to, [§15.1](#151-send_time_notification_eligibility) above.

```text
ASSUMED_USER_ACTION_DELAY_S = 90   # seconds -- renamed from an earlier draft's
                                    # ASSUMED_NOTIFICATION_DELAY_S. That name
                                    # invited confusing "how long before
                                    # Telegram sends the message" (zero — see
                                    # §15.1) with "how long before a real user
                                    # could realistically act" (this constant).
```

This is an **evaluation assumption used to grade V2's own output**, not a
promise that any given user reacts within 90 seconds — stated explicitly,
per the Product Contract's requirement that this number not be read as a
guarantee. It is deliberately conservative (fast enough to be meaningful,
slow enough not to flatter V2 by assuming instant reaction). It
`rules_version`-participates exactly as its predecessor did
([§3](#3-v2-modelversion-identity)).

```text
assumed_entry_time = event_reference_time + ASSUMED_USER_ACTION_DELAY_S
   # event_reference_time as defined in §15.1, separately for EARLY_SIGNAL and CONFIRMED
```

**Price sampled after the delay:** the reference exchange's 1-minute kline
close of the bar whose close timestamp is the smallest one `>=
assumed_entry_time` — the same "sample at a well-defined discrete close
instant" convention V1's outcome evaluator already uses
(`analytics/forecasting/outcomes.py`: `target_bar_ts = end − 1m`, evaluated
at that bar's close). **This bar does not exist at `event_reference_time`**
— it is chronologically future data relative to the event, permitted here
**only** because this is outcome/evaluation computation run once that bar
has actually closed, never a live decision input
([§2](#2-no-lookahead-semantics-per-input-family) still governs every
*decision*; this is evaluation, not a decision).

**Feasibility (V2-v0):**

```text
LONG:  assumed-feasible iff sampled_price <= event_entry_zone_upper + OVERSHOOT_TOLERANCE
                             AND event_invalidation_price not yet breached (reference exchange,
                                 closed 5m bucket) as of assumed_entry_time
SHORT: assumed-feasible iff sampled_price >= event_entry_zone_lower - OVERSHOOT_TOLERANCE
                             AND event_invalidation_price not yet breached as of assumed_entry_time
```

(`event_entry_zone_upper`/`event_entry_zone_lower`/`event_invalidation_price`/
`OVERSHOOT_TOLERANCE` are the same values [§15.1](#151-send_time_notification_eligibility)
defines for the same event.)

A price that moved *further into* the zone (a deeper LONG pullback price,
a lower SHORT breakout retrace) is **more** favorable, never infeasible —
only price moving *away* from the zone by more than the tolerance is
"late." A price outside the tolerance is marked **infeasible/late**
regardless of how strong the analytical setup was — an obviously missed
move MUST NOT be counted as a successful actionable V2 call.

**`INVALIDATED_BEFORE_ENTRY` reachability under V2-v0 (clean-room audit
finding — reserved/currently-unreachable, not removed from the schema).**
`INVALIDATED_BEFORE_ENTRY` requires `event_invalidation_price` to have been
breached, on a **closed 5m bucket**, *as of* `assumed_entry_time =
T_confirm + ASSUMED_USER_ACTION_DELAY_S (90s)`. Under V2-v0's frozen
timing this is **not reachable** by the ordinary post-confirmation path:
structural invalidation is always checked on **closed 5m buckets**
([§10](#10-structural-invalidation)), and the earliest closed 5m bucket
strictly after the `CONFIRMED` bucket itself closes at `T_confirm + 5m
(300s)` — after `assumed_entry_time (T_confirm + 90s)`. As of
`assumed_entry_time`, the most recently closed 5m bucket is still the
`CONFIRMED` bucket itself (or earlier), and that bucket cannot itself have
been an invalidating close — [§13.1](#131-transition-precedence)'s
precedence rule means a boundary where invalidation and confirmation are
both true always resolves to `INVALIDATED`, never `CONFIRMED`, so an
episode that reached `CONFIRMED` at `T_confirm` provably did **not**
breach `event_invalidation_price` at `T_confirm` either. There is
therefore no closed 5m bucket, at or before `assumed_entry_time`, on which
a fresh invalidating close could have occurred for a genuinely `CONFIRMED`
episode. **`INVALIDATED_BEFORE_ENTRY` is accordingly reserved as a
currently-unreachable `lateness_status` value under V2-v0's frozen
`ASSUMED_USER_ACTION_DELAY_S = 90s` / 5m-close-only invalidation timing** —
it remains a valid enum value (a future `rules_version` could reach it,
e.g. by lengthening `ASSUMED_USER_ACTION_DELAY_S` past `300s`, or by
adding a legitimate faster invalidation check), but no current V2-v0
worked vector may present it as an ordinarily-occurring population member;
see the corrected [§29.12](#2912-acceptance-population-vector) vector.

**What this feeds:** `assumed-feasible` (for `CONFIRMED`) drives
`lateness_status` (`ACTIONABLE` vs. `LATE`/`INVALIDATED_BEFORE_ENTRY`,
[§17](#17-outcome--evaluation-model)), the feasibility acceptance metric
([§27](#27-acceptance-metric-hierarchy)), `feasible_entry_price`, and every
`execution_*` metric
([§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only)).
The `EARLY_SIGNAL`-event version of the same check is recorded purely as
research/evaluation context on the episode's own history — it never
retroactively edits whether the `EARLY_SIGNAL` notification was sent
([§16.1](#161-early_signal-notification-content-and-history-invariants-v2-v0)).

**It MUST NOT decide whether a notification was sent.** A scenario may
therefore legitimately be:

```text
send-eligible at event_reference_time (§15.1 -- notification IS emitted)
but later graded assumed-infeasible/LATE under the 90s evaluation (§15.2)
```

That is not a contradiction — it is precisely what the feasibility
acceptance metric measures: whether a scenario V2 was willing to publish
*live* would, in hindsight, still have been realistically enterable. The
converse also holds: an event already send-suppressed at
`event_reference_time` (§15.1) obviously will not later be counted as a
successful actionable call, regardless of what the 90s-delayed price does
— it never had a chance to be `ACTIONABLE` in the first place. A
`CONFIRMED` episode whose `assumed-feasible` check fails, or whose
invalidation was already reached before `assumed_entry_time`, is **stored
and evaluated exactly like any other** ([§17](#17-outcome--evaluation-model))
— it simply never counts in the `ACTIONABLE` population
([§26.1](#261-episode-population-definitions)).

---

## 16. Notification materiality / anti-spam thresholds

| Event | Material? | V2-v0 condition |
|---|---|---|
| First `EARLY_SIGNAL` | Only if `send_time_notification_eligibility` passes ([§15.1](#151-send_time_notification_eligibility)) — a live, no-future-data check; rare to fail, but a breakout already blown past its own zone+tolerance at the deciding close is suppressed immediately | — |
| `CONFIRMED` | **Always material, if `send_time_notification_eligibility` passes** ([§15.1](#151-send_time_notification_eligibility)) — same live, no-future-data check, evaluated at `CONFIRMED`'s own decision boundary | — |
| Confidence-only update | Material iff `|Δ model_confidence| >= 0.15` (V2-v0) on the unit-interval scale | — |
| Zone update | Material only pre-`CONFIRMED` (zone is frozen after, [§9](#9-entry-zone-semantics)) and only if the zone bound moves by more than `0.5 * protection_buffer` (V2-v0) | — |
| `WEAKENING` | Always material (state change) | — |
| Recovery (`WEAKENING → CONFIRMED`) | Always material (state change) | — |
| `INVALIDATED` | Always material (state change) | — |
| `REVERSAL_CANDIDATE` | Always material — **NOT itself a state change** on the episode it is attached to; it is an informational/cross-reference event fired because a *separate*, independently-created opposite-direction episode reached `EARLY_SIGNAL` ([§13.3](#133-reversal_candidate-mechanics)). The pre-existing episode's own `episode_state` is unchanged by this event — see the correction note below. | — |
| Routine 5m re-evaluation with no state change and `|Δconfidence| < 0.15` | **Never material** | — |

**Correction: `REVERSAL_CANDIDATE` is not a lifecycle state transition.**
An earlier draft of this table (and the cooldown-override sentence below)
grouped `REVERSAL_CANDIDATE` together with `WEAKENING`/recovery/
`INVALIDATED` under the label "state change." That mislabeling is fixed
here: [§13.3](#133-reversal_candidate-mechanics) is explicit that a
`REVERSAL_CANDIDATE` event leaves the pre-existing episode's own
`episode_state` **UNCHANGED** — it is purely an informational
cross-reference attached to that episode's history, never a transition in
[§13.2](#132-allowed-transitions)'s transition graph. It remains **always
material** (the notification-materiality behavior itself does not change)
for the independent reason that a newly-detected opposite-direction setup
is inherently noteworthy information for the user — not because it is a
state transition.

**Cooldown / duplicate suppression:** a material non-state-change update
(confidence-only or zone-only) is additionally suppressed if the episode's
last notification was fewer than `MATERIAL_COOLDOWN = 3` closed 5m buckets
ago (15 min, V2-v0) — **except** a genuine lifecycle state-change
transition (`CONFIRMED`, `WEAKENING`, recovery, `INVALIDATED`) or a
`REVERSAL_CANDIDATE` cross-reference (informational, not a state change,
but carrying the same "always overrides cooldown" treatment for the
independent reason above) — none of these five are ever suppressed by
this cooldown.

Routine 5m re-evaluation that changes no state and moves confidence by
less than the threshold is, by construction, never notification-worthy —
this is the anti-spam invariant `V2_PRODUCT_CONTRACT.md` §3/§9 requires.

**`assumed_entry_feasibility` ([§15.2](#152-assumed_entry_feasibility)) is
not a materiality input.** The retrospective 90-second evaluation grade —
computed later, once the required future 1-minute bar exists — does
**not** decide whether `First EARLY_SIGNAL` or `CONFIRMED` above was
material/emitted; that decision is made **once**, live, by
`send_time_notification_eligibility`. The 90s grade only later labels an
*already-emitted* event's `lateness_status` for research/acceptance
purposes ([§17](#17-outcome--evaluation-model),
[§27](#27-acceptance-metric-hierarchy)) — it never retroactively creates,
cancels, or un-sends a notification.

### 16.1 `EARLY_SIGNAL` notification content and history invariants (V2-v0)

When the first `EARLY_SIGNAL` notification is material —
`send_time_notification_eligibility` passes,
[§15.1](#151-send_time_notification_eligibility) — its content is a
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
  send_eligibility_status # eligible | suppressed -- computed LIVE, at detection_timestamp itself,
                           # from data the detector already has (§15.1). This is the ONLY
                           # feasibility-shaped field the notification record carries at
                           # EARLY_SIGNAL time.
```

**No field above may depend on data that does not exist yet at
`detection_timestamp`** — in particular none of them may read
`confirmation_close_price`, the `CONFIRMED`-time entry zone, any
`CONFIRMED`/`ACTIONABLE`-only metric
([§18](#18-risk-normalized-metrics-planned-risk-vs-execution-risk)), or the
`T + ASSUMED_USER_ACTION_DELAY_S` sampled price
([§15.2](#152-assumed_entry_feasibility)) — all of which are undefined
until `T_confirm`/`CONFIRMED`, or until the future 1-minute bar has
actually closed, respectively. This is the same no-future-information
constraint [§2](#2-no-lookahead-semantics-per-input-family) already
freezes for feature computation generally, applied here to the
notification content itself. The later `assumed_entry_feasibility` grade
([§15.2](#152-assumed_entry_feasibility)) is recorded **separately**, as a
later outcome/evaluation fact on the episode's outcome record
([§17](#17-outcome--evaluation-model): `assumed_feasible_entry_timestamp`,
`feasible_entry_price_or_status`) — it is never retroactively attached to
the `EARLY_SIGNAL` notification event itself, as if it had been known at
`detection_timestamp`. Replay reproduces these as **two separate
deterministic facts**: the same live `send_eligibility_status` from
event-time inputs, and — chronologically later — the same
`assumed_entry_feasibility` outcome from the same future inputs a live run
would eventually have observed too.

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
  terminal_reason                # HORIZON_COMPLETION | HORIZON_NO_COMPLETION |
                                  # DATA_INCOMPLETE, per §18.2a.1 -- distinguishes
                                  # a complete-data non-completion from an
                                  # incomplete-observation expiry; only meaningful
                                  # for COMPLETED/EXPIRED via the horizon path
                                  # (null for INVALIDATED/EARLY_SIGNAL-EXPIRED)
  analytical_path_complete       # bool|null, per §18.2a.1 -- TRUE iff EVERY
                                  # expected 1m bar on [T_confirm, T_terminal)
                                  # is present and valid, where T_terminal is
                                  # this episode's OWN terminal decision
                                  # boundary (horizon_end for COMPLETED/EXPIRED;
                                  # T_invalidation/invalidation_reached_at for
                                  # INVALIDATED); FALSE if any required bar is
                                  # missing/unusable. INDEPENDENT of
                                  # terminal_reason/episode_state -- a COMPLETED
                                  # episode CAN have analytical_path_complete =
                                  # FALSE (favorable-excursion threshold proven
                                  # by observed bars before a later gap, §18.2a.1
                                  # case A), and a CONFIRMED/WEAKENING ->
                                  # INVALIDATED episode has its OWN TRUE/FALSE
                                  # value from its own required
                                  # pre-invalidation path -- NEVER null merely
                                  # because it terminalized via INVALIDATED.
                                  # ALWAYS boolean for every episode that
                                  # reached CONFIRMED and later reached ANY
                                  # terminal state; null ONLY for an episode
                                  # that never reached CONFIRMED at all
                                  # (EARLY_SIGNAL -> INVALIDATED/EXPIRED),
                                  # which is outside the CONFIRMED acceptance
                                  # sample entirely (§26)
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
  data_coverage_at_confirmation   # per-family confidence/coverage facts, BY VALUE,
                                   # for the family/families mandatory to THIS setup's
                                   # confirmation decision (§6.3a) -- NEVER the global
                                   # min_coverage_ratio/consensus_confidence rollup;
                                   # see the exact per-family freeze below
```

**`data_coverage_at_confirmation`, frozen exactly per family (amended — a
prior draft used the global `min_coverage_ratio`/`consensus_confidence`
rollup, which directly contradicts [§6.3a](#63a-per-family-metric-scoped-quality-gates)'s
per-family quality model).** Reuses §6.3a's required-family table for each
family's **confirmation** decision — every family's confirmation is a
pure `price_structure` (5m) check (§7.1/§7.2/§7.3's confirmation triggers
never re-consult `taker_flow`, even for `COMPRESSION_BREAKOUT`, whose
`taker_flow` requirement is `EARLY_SIGNAL`-formation-only, §6.3a):

```text
TREND_PULLBACK confirmation:       price_structure 5m coverage + confidence
COMPRESSION_BREAKOUT confirmation: price_structure 5m coverage + confidence
CONFIRMED_BREAKOUT confirmation:   price_structure 5m coverage + confidence
```

recorded **by value** at the `CONFIRMED` decision boundary. The
setup-**formation**-time quality facts required earlier in the episode's
life (e.g. `COMPRESSION_BREAKOUT`'s `EARLY_SIGNAL`-time `taker_flow`
confidence, [§8](#8-model-confidence-semantics)'s `data_confidence`
component) remain separately persisted in the episode's own
`EARLY_SIGNAL`-time decision snapshot/candidate facts, per
[§9](#9-entry-zone-semantics)/[§16.1](#161-early_signal-notification-content-and-history-invariants-v2-v0) —
this section does not restate or duplicate that fact, only the
**confirmation-time** one. The global six-family rollup
(`consensus_confidence`/`min_coverage_ratio`) MAY remain a
diagnostics/reporting-only value elsewhere in the system; it is never a
V2 decision-rule or outcome-record input.

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
`ASSUMED_USER_ACTION_DELAY_S = 90` seconds **after** the `CONFIRMED`
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
`feasible_entry_price`.) `analytical_MFE_R` progress becomes knowable as
soon as a **closed** expected 1m bar proves it (never from an in-progress,
not-yet-closed 1m bar — see §18.2a's exact bar-time semantics below),
independent of whether the episode ever reaches `ACTIONABLE` status —
lifecycle state MUST NOT depend on whether a hypothetical human could have
entered 90 seconds later.

### 18.2a Analytical excursion source data

_(V2-v0, clean-room audit amendment — freezes the exact price-path
semantics `analytical_MFE_R` depends on, required before Stage 6's
`COMPLETED`/`EXPIRED` decision can be implemented, and reused unchanged
by the later Stage 8 V2 Outcome Evaluator rather than reimplemented
there.)_

**Canonical evaluation exchange:** `binance` (the same canonical reference
exchange [§11](#11-reference-price-semantics) already freezes).

**Source:** raw canonical Binance `klines_1m` (`storage`'s existing raw
1-minute kline table — the same source
[§7.0a](#70a-structural-highlow-derivation-amended--corrects-a-nonexistent-field-error)
already uses for structural high/low derivation; no new ingested source).

**Granularity:** exact 1-minute bars.

**Evaluation interval, for an episode confirmed at `T_confirm` with
expected horizon `H` ([§14](#14-candidate-expiry-and-expected-horizons)):**

```text
horizon_end = T_confirm + H

evaluation interval = [T_confirm, horizon_end)   -- half-open, matching
                       this document's own selected_bucket() convention
                       ([§1.3](#13-layer-2-selected_buckettimeframe-t-pure))

expected 1m bar grid (every whole-minute bar timestamp expected present):
    T_confirm, T_confirm + 1m, T_confirm + 2m, ..., horizon_end - 1m
```

**Exact bar-time semantics (re-amended — tech-lead/red-team finding: the
prior text wrongly claimed the `bucket_ts = T_confirm` bar is "already
closed data as of `T_confirm`"; it is not — Signalbot's raw-kline bucket
timestamp is the bar's START, not its end, exactly as every other bucket
convention in this document already uses,
[§1.3](#13-layer-2-selected_buckettimeframe-t-pure)).** For an expected
bar with `bucket_ts = B`, its interval is `[B, B + 1m)`, and — per this
document's general no-lookahead discipline
([§2](#2-no-lookahead-semantics-per-input-family)) — it becomes a usable,
closed observation only once:

```text
current logical observation/evaluation time >= B + 1m
```

**No partially formed 1m bar may be used**, without exception. Applied to
the expected grid above:

```text
At T_confirm itself:
    ZERO post-confirmation 1m bars from the evaluation interval are yet
    closed -- the bar with bucket_ts = T_confirm represents
    [T_confirm, T_confirm + 1m), which has only just started at
    T_confirm and is still future, in-progress data at that instant.

At T_confirm + 1m:
    the bar [T_confirm, T_confirm + 1m) is now closed and may first be
    consumed (it may now contribute its HIGH/LOW to MFE/MAE).

At horizon_end:
    every expected bar in [T_confirm, horizon_end) SHOULD by now be
    closed and available -- the final expected bar, bucket_ts =
    horizon_end - 1m, represents [horizon_end - 1m, horizon_end), which
    closes exactly at horizon_end -- unless there is a genuine data gap
    (§18.2a.1 below).
```

The `bucket_ts = T_confirm` bar being eligible for the interval (i.e.
belonging to the expected grid at all) is a separate fact from that same
bar being *closed* at `T_confirm` — it belongs to the grid because
`T_confirm` is the interval's own lower (inclusive) bound, but like every
other bar on the grid it is only *readable* once its own close has
passed, exactly `T_confirm + 1m` seconds later.

**Concrete bar-timing vector:**

```text
T_confirm = 10:00, H = 2h -> horizon_end = 12:00.

Expected first bar:
    bucket_ts = 10:00, interval = [10:00, 10:01).
    At 10:00: NOT closed -- cannot be read.
    At 10:01: closed -- may now contribute its HIGH/LOW to MFE/MAE.

Expected final bar:
    bucket_ts = 11:59, interval = [11:59, 12:00).
    At horizon_end = 12:00: now closed -- provides the terminal close,
    if present.
```

This aligns exactly with the rest of the repository's bucket-start
convention ([§1.3](#13-layer-2-selected_buckettimeframe-t-pure)): a
bucket's `bucket_ts` is always its START, never its end, and a bucket is
never readable before its own close has passed.

**MFE / MAE:** use 1-minute `HIGH`/`LOW` extrema across the evaluation
interval, direction-aware exactly like V1's existing outcome sign
convention (`analytics/forecasting/outcomes.py`: for `LONG`,
`mfe = max(0, peak favorable excursion)`, `mae = min(0, trough adverse
excursion)`; mirrored for `SHORT`) — reused here, not reinvented, applied
over `[T_confirm, horizon_end)` instead of V1's fixed prediction-horizon
window.

**Terminal return:** the `close` of the **final** expected 1m bar
(`horizon_end - 1m`).

**Reference baseline:** `confirmation_reference_price`, exactly as already
frozen ([§17](#17-outcome--evaluation-model)/[§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)
above).

#### 18.2a.1 Missing-bar behavior and `terminal_reason`

_(Does NOT add a new lifecycle state.)_

**Missing data MUST NOT be silently interpreted as "price never reached
the completion threshold."** At horizon resolution (the decision boundary
`horizon_end`, [§13.2](#132-allowed-transitions)):

```text
(A) If the AVAILABLE observed 1m bars already prove
        analytical_MFE_R >= MIN_MFE_R_FOR_COMPLETION
    -- REGARDLESS of whether any other expected 1m bar in the interval is
    missing -- favorable-excursion completion is already existentially
    proven by observed data. Subject to no higher-precedence structural
    invalidation having occurred (§13.1), terminal lifecycle resolves:
        episode_state  = COMPLETED
        terminal_reason = HORIZON_COMPLETION
    The analytical path is marked data-incomplete for full
    evaluator-metric purposes (a downstream evaluator computing e.g. an
    exact terminal return still needs the complete grid) but the
    existential completion threshold itself does not require it -- one
    observed bar crossing the threshold is sufficient proof regardless of
    what any other bar in the interval would have shown.

(B) If one or more expected 1m bars are missing AND the observed bars have
    NOT already proven the threshold:
    the system cannot truthfully claim "analytical_MFE_R never reached
    threshold" -- the missing interval could contain the favorable
    excursion. The episode still leaves the active lifecycle at horizon
    end (it cannot remain EARLY_SIGNAL/CONFIRMED/WEAKENING forever). Freeze:
        episode_state  = EXPIRED
        terminal_reason = DATA_INCOMPLETE
    DISTINCT from ordinary complete-data non-completion:
        episode_state  = EXPIRED
        terminal_reason = HORIZON_NO_COMPLETION

(C) If the full exact 1m grid is present for the entire evaluation
    interval:
        threshold reached at least once -> COMPLETED, terminal_reason = HORIZON_COMPLETION
        threshold never reached         -> EXPIRED,   terminal_reason = HORIZON_NO_COMPLETION
```

**No new lifecycle STATE is added** — `COMPLETED`/`EXPIRED` remain exactly
[§13.2](#132-allowed-transitions)'s two frozen terminal states.
`terminal_reason` is a **terminal-reason/outcome-quality fact**
alongside the state, not a third state, and not a fourth
`lateness_status` value ([§17](#17-outcome--evaluation-model) is
unaffected — `lateness_status` and `terminal_reason` are independent
facts on the same outcome record).

**`analytical_path_complete`, an explicit path-completeness fact,
independent of `terminal_reason` (re-amended — tech-lead/red-team
finding: the round-5 definition scoped the required path to
`[T_confirm, horizon_end)` unconditionally, which is correct for
horizon-terminal episodes but wrongly leaves `analytical_path_complete =
NULL` for `CONFIRMED`/`WEAKENING → INVALIDATED` episodes — silently
excluding every such episode from `PATH_COMPLETE_ACTIONABLE` and the
path-dependent acceptance metrics below regardless of whether its own,
shorter, actually-required observed path was complete. `INVALIDATED` is
frequently precisely the adverse outcome that MUST remain in the
performance population when its own price path is complete — excluding
it unconditionally is a survivorship bias, not a data-quality safeguard).**
Generalized to every episode that reached `CONFIRMED` at least once and
later reached **any** terminal state — `COMPLETED`, `EXPIRED`, or
`INVALIDATED` alike — by scoping the required path to that specific
episode's own terminal boundary, not always to `horizon_end`:

```text
T_confirm  = the episode's CONFIRMED decision boundary
T_terminal = the SAME T_terminal already frozen in
             [§12.8](#128-terminal-episode-cooldown-exact-clock) -- "the
             decision boundary of the terminal event (the decision at
             which the episode transitioned to INVALIDATED / EXPIRED /
             COMPLETED)":
                 horizon_end                      for COMPLETED/EXPIRED
                     (terminal_reason = HORIZON_COMPLETION,
                      HORIZON_NO_COMPLETION, or DATA_INCOMPLETE -- §14
                      already fixes the expected horizon per family, so
                      horizon_end is exactly §18.2a's existing value,
                      UNCHANGED from before this amendment)
                 T_invalidation (invalidation_reached_at, §17)
                                                   for INVALIDATED

required analytical path  = [T_confirm, T_terminal)
expected 1m bar grid      = T_confirm, T_confirm + 1m, ..., T_terminal - 1m
                             -- same frozen 1m bar-start / closed-bar rules
                             already defined above in this section (a bar
                             with bucket_ts = B is usable only once
                             observation time >= B + 1m)

analytical_path_complete = TRUE
    iff EVERY expected 1m bar on [T_confirm, T_terminal) is present and
    valid.

analytical_path_complete = FALSE
    iff one or more expected bars on [T_confirm, T_terminal) are
    missing/unusable.

analytical_path_complete = NULL
    iff the episode NEVER reached CONFIRMED at all (EARLY_SIGNAL ->
    INVALIDATED, EARLY_SIGNAL -> EXPIRED via candidate-age limit, §14) --
    there is no post-confirmation analytical path to evaluate at all in
    that case, which is a fundamentally different fact from "a path
    exists but wasn't fully observed."
```

**Invariant, frozen explicitly: inside the `CONFIRMED` acceptance sample
(every episode that reached `CONFIRMED` and later reached a terminal
state, [§26](#26-acceptance-sample-requirements)), `analytical_path_complete`
is ALWAYS boolean — `TRUE` or `FALSE` — and is NEVER `NULL`.** `NULL` is
reserved exclusively for episodes that never reached `CONFIRMED` in the
first place, which are outside the `CONFIRMED` acceptance sample by
construction ([§26](#26-acceptance-sample-requirements)) and therefore
never need to be checked for path completeness in an acceptance
computation.

**For horizon-terminal episodes (`COMPLETED`/`EXPIRED`), nothing changes
from the round-5 definition** — `T_terminal = horizon_end` exactly as
already frozen, so the required path remains exactly `[T_confirm,
horizon_end)`, the `(A)`/`(B)`/`(C)` missing-bar cases above are
unaffected, and `DATA_INCOMPLETE` continues to mean exactly what it
already means: one or more required bars before `horizon_end` missing
and the observed bars not already proving completion.

**For `INVALIDATED` episodes (`CONFIRMED → INVALIDATED` or `WEAKENING →
INVALIDATED`, [§13.2](#132-allowed-transitions)):** the episode's own
analytical path ends at `T_invalidation` — bars **after**
`T_invalidation` are irrelevant to `analytical_path_complete` and MUST
NOT be required, since the episode was already terminal at that point and
no further post-invalidation excursion is part of its own observed
history. `terminal_reason` is **not** touched by this amendment — it
remains exactly the horizon-terminal-reason vocabulary
(`HORIZON_COMPLETION`/`HORIZON_NO_COMPLETION`/`DATA_INCOMPLETE`), `null`
for `INVALIDATED` exactly as already frozen ([§17](#17-outcome--evaluation-model)) —
this section does **not** invent a `HORIZON_*`-style `terminal_reason`
for structural invalidation; the `episode_state = INVALIDATED` value
itself already explains that terminalization, and `analytical_path_complete`
is orthogonal to it, exactly as it is orthogonal to `terminal_reason` for
the horizon-terminal cases above.

This fact is orthogonal to `episode_state`/`terminal_reason` in every
case — it answers "was this episode's own required post-confirmation
price path actually observed," never "did the episode complete." The
combinations that matter:

```text
COMPLETE path, threshold reached (horizon-terminal):
    episode_state = COMPLETED, terminal_reason = HORIZON_COMPLETION,
    analytical_path_complete = TRUE.
INCOMPLETE path, observed bars already prove the threshold (case A):
    episode_state = COMPLETED, terminal_reason = HORIZON_COMPLETION,
    analytical_path_complete = FALSE.
INCOMPLETE path, threshold not proven (case B):
    episode_state = EXPIRED, terminal_reason = DATA_INCOMPLETE,
    analytical_path_complete = FALSE.
COMPLETE path, threshold never reached (case C):
    episode_state = EXPIRED, terminal_reason = HORIZON_NO_COMPLETION,
    analytical_path_complete = TRUE.
INVALIDATED, own required pre-invalidation path complete:
    episode_state = INVALIDATED, terminal_reason = null,
    analytical_path_complete = TRUE.
INVALIDATED, own required pre-invalidation path incomplete (a required
bar strictly before T_invalidation is missing):
    episode_state = INVALIDATED, terminal_reason = null,
    analytical_path_complete = FALSE.
Never reached CONFIRMED (EARLY_SIGNAL -> INVALIDATED/EXPIRED):
    analytical_path_complete = NULL -- outside the CONFIRMED acceptance
    sample entirely, per §26.
```

`terminal_reason = DATA_INCOMPLETE` therefore always implies
`analytical_path_complete = FALSE` (case B is exactly the "missing AND
not proven" branch), but the converse does not hold —
`analytical_path_complete = FALSE` can coexist with
`terminal_reason = HORIZON_COMPLETION` (case A), and can equally occur on
an `INVALIDATED` episode whose `terminal_reason` is `null`. Reading
`terminal_reason != DATA_INCOMPLETE` as "the path was complete" is
therefore **wrong** in every case — `analytical_path_complete` is the one
fact that answers that question, and it MUST be checked directly for
every `CONFIRMED`-then-terminal episode, never inferred from
`terminal_reason` alone, and never assumed `NULL`/inapplicable merely
because the episode terminalized via `INVALIDATED` rather than the
horizon path.

**`DATA_INCOMPLETE` / `analytical_path_complete = FALSE`, exact treatment
(no longer an open evaluator choice — re-amended, closes a contradiction
with §26.1's "no future evaluator chooses its own population" claim):**

- **MUST NOT** be counted as evidence that the setup failed to reach
  `MIN_MFE_R_FOR_COMPLETION` — it proves nothing about the missing
  interval, favorable or not.
- **MUST** be visible in data-quality/evaluation accounting (a distinct,
  queryable `terminal_reason` value, never silently merged into ordinary
  `HORIZON_NO_COMPLETION` expiry; likewise `analytical_path_complete`
  itself MUST be a distinct, queryable fact, not merged into
  `terminal_reason`).
- Remains part of the historical `CONFIRMED` episode population (still
  counted in `CONFIRMED`, per [§26.1](#261-episode-population-definitions)'s
  population definitions) but is **excluded by frozen rule** — not by a
  later evaluator's discretionary choice — from every acceptance/promotion
  metric whose truth requires a complete excursion path. The exact
  population split (`PATH_COMPLETE_ACTIONABLE`) and the deterministic
  no-silent-exclude-and-pass promotion safety rule this implies are frozen
  in [§26.1](#261-episode-population-definitions)/[§28.2](#282-promotion-levels)
  below — this is no longer an implementation choice left to a future
  acceptance-metric definition; it is fixed here and now. This treatment
  applies identically whether the episode's incomplete path arose from a
  horizon-terminal `DATA_INCOMPLETE` expiry or from a structurally
  `INVALIDATED` episode whose own pre-invalidation path had a data gap —
  both are `analytical_path_complete = FALSE`, both are excluded from
  path-dependent metrics by the same rule.

**Worked vectors (including `analytical_path_complete`):**

```text
Vector 1 -- complete path, threshold reached:
  T_confirm=10:00, H=2h -> evaluation interval [10:00, 12:00).
  Full 1m grid present (120 bars). analytical_MFE_R reaches 0.62 at 10:47.
  => at horizon_end=12:00: COMPLETED, terminal_reason=HORIZON_COMPLETION,
     analytical_path_complete=TRUE.

Vector 2 -- complete path, threshold not reached:
  Same interval, full 1m grid present. Peak analytical_MFE_R over the
  whole interval = 0.31 (< MIN_MFE_R_FOR_COMPLETION=0.5).
  => at horizon_end=12:00: EXPIRED, terminal_reason=HORIZON_NO_COMPLETION,
     analytical_path_complete=TRUE.

Vector 3 -- missing path, threshold ALREADY proven by observed bars:
  Bars 10:00-10:50 present; analytical_MFE_R computed from THOSE bars
  alone already reaches 0.71 at 10:33. Bars 10:51-11:59 are missing
  (data gap).
  => at horizon_end=12:00: COMPLETED, terminal_reason=HORIZON_COMPLETION,
     analytical_path_complete=FALSE -- the missing later bars cannot
     retroactively un-prove a threshold crossing that already-observed
     data established, but the path itself is still incomplete: this
     episode proves COMPLETED != proof of a complete analytical path.

Vector 4 -- missing path, threshold NOT proven by observed bars:
  Bars 10:00-10:50 present; peak analytical_MFE_R from those bars = 0.22.
  Bars 10:51-11:59 are missing.
  => at horizon_end=12:00: EXPIRED, terminal_reason=DATA_INCOMPLETE,
     analytical_path_complete=FALSE -- NOT HORIZON_NO_COMPLETION, because
     the missing 10:51-11:59 interval could have contained a favorable
     excursion the system never observed; the system cannot truthfully
     claim the threshold was never reached.

Vector 5 -- CONFIRMED -> INVALIDATED, complete own path:
  CONFIRMED at 10:00. Structural INVALIDATED at 10:25
  (T_invalidation=10:25). Required path = [10:00, 10:25) -- bars 10:00
  through 10:24, all present.
  => episode_state=INVALIDATED, terminal_reason=null,
     analytical_path_complete=TRUE. Bars after 10:25 (if any exist) are
     irrelevant and are never checked -- the episode was already
     terminal at 10:25.

Vector 6 -- CONFIRMED -> INVALIDATED, incomplete own path:
  Same episode as Vector 5, but the 10:13 bar is missing.
  => analytical_path_complete=FALSE -- a required bar strictly inside
     [T_confirm, T_invalidation) is missing, even though the episode's
     own terminal boundary (10:25) has long since passed and no
     "horizon" is even relevant to this episode's terminalization.
```

**Stage 8 MUST reuse this exact primitive rather than reimplement it** —
per [§4.1a](#41a-stage-4-numerical-evidence-must-survive-the-stage-456-boundary)'s
general handoff-invariant reasoning applied here: Stage 6's own horizon-
terminal-resolution logic and the later Stage 8 V2 Outcome Evaluator MUST
share one implementation of this section's exact 1m-grid/missing-bar
semantics, never two independently-written MFE/MAE computations that
could silently diverge on bar-granularity, no-lookahead, or missing-bar
behavior.

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
`ASSUMED_USER_ACTION_DELAY_S`, `OVERSHOOT_TOLERANCE`'s multiplier,
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
| `CONFIRMED` (sample base) | Episodes that reached `CONFIRMED` at least once and later reached a terminal lifecycle state (above — `COMPLETED`, `EXPIRED`, or `INVALIDATED`). Every episode in this population has a `planned_risk_distance`, which genuinely is fixed and available at `CONFIRMED` itself ([§18.1](#181-planned-risk-structural-available-at-confirmed)); and a **defined** `analytical_MFE_R` ([§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)) — but, corrected here (re-amended — tech-lead/red-team finding: the prior wording wrongly claimed `analytical_MFE_R` is "available at `CONFIRMED` itself" the same way `planned_risk_distance` is), `analytical_MFE_R`'s *value* only becomes knowable progressively as closed post-confirmation 1m bars arrive (§18.2's own already-correct statement — a closed bar is required before any excursion it would reveal is known) and is only **finalized** at the episode's own terminal boundary (`T_terminal`, [§12.8](#128-terminal-episode-cooldown-exact-clock)/[§18.2a.1](#182a1-missing-bar-behavior-and-terminal_reason)) — never at `CONFIRMED` itself. Membership in `CONFIRMED` does **not** depend on `analytical_path_complete` — an episode with `analytical_path_complete = FALSE` (e.g. `terminal_reason = DATA_INCOMPLETE`, a `COMPLETED` episode whose threshold was proven before a later gap, or an `INVALIDATED` episode with a gap in its own pre-invalidation path) is still fully counted here. Inside this population, `analytical_path_complete` is always boolean (`TRUE`/`FALSE`) — never `NULL` ([§18.2a.1](#182a1-missing-bar-behavior-and-terminal_reason)); `NULL` occurs only for episodes that never reached `CONFIRMED`, which are outside this population by definition. |
| `ACTIONABLE` | The subset of `CONFIRMED` with `lateness_status == ACTIONABLE` ([§15](#15-entry-feasibility-evaluation)) — has a defined `feasible_entry_price`, and therefore `execution_R` ([§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only)), which is a purely structural quantity (`\|feasible_entry_price - invalidation_price\|`) requiring no future price-path data. **`ACTIONABLE` membership alone does NOT imply a complete `execution_MFE_R`/`execution_MAE_R`/`execution_terminal_return_R`** (re-amended — tech-lead/red-team finding: an `ACTIONABLE` episode can still have `analytical_path_complete = FALSE`, since `execution_mfe_pct_over_episode_life`/`execution_mae_pct_over_episode_life`/`execution_directional_return_pct` are computed over the same underlying post-confirmation 1m price path as `analytical_MFE_R`, just baselined against `feasible_entry_price` instead of `confirmation_reference_price`, and — whether the episode is horizon-terminal or `INVALIDATED` — that price path is only fully observed once `analytical_path_complete = TRUE`). `ACTIONABLE` means **entry feasibility exists**; it does not by itself mean the episode's own required future path was fully observed — see `PATH_COMPLETE_ACTIONABLE` below for the population that means both. |
| `PATH_COMPLETE_ACTIONABLE` (new) | `ACTIONABLE` episodes with `analytical_path_complete == TRUE` ([§18.2a.1](#182a1-missing-bar-behavior-and-terminal_reason)) — i.e. entry feasibility exists **AND** the episode's own required post-confirmation price path (through `T_terminal` — `horizon_end` for `COMPLETED`/`EXPIRED`, or `T_invalidation` for `INVALIDATED`) was actually, fully observed. This correctly includes `ACTIONABLE` episodes that terminalized via `COMPLETED`, `EXPIRED`, **or** structural `INVALIDATED` alike, whenever each episode's own required path is complete — `INVALIDATED` is not itself grounds for exclusion; only an actually-incomplete own path is. This is the population every path-dependent execution-scoped R-normalized metric below actually requires; `ACTIONABLE` and `PATH_COMPLETE_ACTIONABLE` are deliberately **not** conflated. |
| `LATE` / `INVALIDATED_BEFORE_ENTRY` | The remaining `CONFIRMED` episodes ([§15](#15-entry-feasibility-evaluation)) — no `feasible_entry_price`, so no execution-scoped R-normalized metrics; still fully counted in `CONFIRMED`, in the percentage metrics ([§17](#17-outcome--evaluation-model), computed from `confirmation_reference_price`), and in `analytical_MFE_R` ([§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)) — which is why they still reach a deterministic lifecycle terminal state ([§13.2](#132-allowed-transitions)). A data gap after confirmation MUST NOT remove a `LATE`/`INVALIDATED_BEFORE_ENTRY` episode from the feasibility denominator — that denominator does not require future-path completeness at all (below). |

| Metric | Population (exact) |
|---|---|
| `MIN_COMPLETED_EPISODES_AGGREGATE` / `_PER_FAMILY` ([§26](#26-acceptance-sample-requirements)) | `CONFIRMED` (all lateness statuses, all `analytical_path_complete` values). |
| Actionable-entry feasibility rate, missed/late rate ([§27](#27-acceptance-metric-hierarchy) priority 1) | `CONFIRMED` — numerator `ACTIONABLE`, denominator `CONFIRMED`. `LATE` and `INVALIDATED_BEFORE_ENTRY` are exactly the episodes counted against the rate, not episodes that disappear from it. **This population does NOT require `analytical_path_complete` at all** — feasibility is decided at `assumed_feasible_entry_timestamp` ([§15](#15-entry-feasibility-evaluation)), long before the future price path in question even exists, so an incomplete future path can never change ACTIONABLE/CONFIRMED denominator membership. |
| Median/90th-percentile `execution_MAE_R`, median `execution_MFE_R`, proportion reaching `execution_MFE_R >= 0.5` ([§27](#27-acceptance-metric-hierarchy) priorities 2–3) | `PATH_COMPLETE_ACTIONABLE` (re-amended — was `ACTIONABLE`; these are path-dependent metrics and require the complete post-confirmation price path, not merely entry feasibility). Still undefined for `LATE`/`INVALIDATED_BEFORE_ENTRY` by construction (no `feasible_entry_price`). |
| Mean `execution_cost_adjusted_return_R` ([§27](#27-acceptance-metric-hierarchy) priority 4) | `PATH_COMPLETE_ACTIONABLE`, same reason. |
| Directional accuracy, `execution_terminal_return_R > 0` ([§27](#27-acceptance-metric-hierarchy) priority 5) | `PATH_COMPLETE_ACTIONABLE` — `execution_terminal_return_R` is itself a path-dependent, execution-scoped R-based metric. (A supplementary, non-gating percentage-based accuracy figure — `directional_return_pct > 0` over **all** `CONFIRMED` episodes — **MAY** additionally be reported, since that percentage metric's population is broader; it carries no threshold either way, consistent with priority 5 never being a gate.) |

**Path-dependent metrics MUST NOT silently exclude-and-renormalize over
`PATH_COMPLETE_ACTIONABLE` to reach a promotion decision** —
[§28.2b](#282b-path-completeness-promotion-safety-rule--no-silent-exclude-and-pass)
freezes the exact, conservative V2-v0 treatment: **any**
`analytical_path_complete = FALSE` episode inside a family's evaluated
`CONFIRMED` acceptance sample makes that family's path-dependent metrics
`NOT EVALUABLE` for the `USER_FACING_ELIGIBLE` gate on that sample, in
full — computing priorities 2–5 over only the remaining path-complete
episodes and declaring a pass is **not** conforming V2-v0 behavior. See
[§28.2b](#282b-path-completeness-promotion-safety-rule--no-silent-exclude-and-pass)
and [§29.14b](#2914b-path-completeness-acceptance-vectors)'s worked
vectors.

---

## 27. Acceptance metric hierarchy

Preserving the roadmap's priority order (`docs/FORECASTING_ROADMAP.md` §H)
exactly, with concrete V2-v0 metrics/thresholds per priority. **Population**
column values are defined precisely in
[§26.1](#261-episode-population-definitions) — no metric below has an
implicit or evaluator-chosen denominator. Priorities 2–5 are
**path-dependent, execution-scoped** metrics
(`PATH_COMPLETE_ACTIONABLE`-only, re-amended per
[§26.1](#261-episode-population-definitions) — `ACTIONABLE` alone is not
sufficient population membership for these, since an `ACTIONABLE` episode
can still have `analytical_path_complete = FALSE`,
[§18.3](#183-execution-risk-and-execution-r-normalized-metrics-actionable-only))
— distinct from [§18.2](#182-analytical-r-normalized-metrics-every-confirmed-episode)'s
`analytical_MFE_R`, which drives lifecycle completion for **every**
`CONFIRMED` episode but is not itself an acceptance-gating metric:

| Priority | Roadmap priority | Metric | Population | V2-v0 threshold |
|---|---|---|---|---|
| 1 | Entry feasibility after real delay | Actionable-entry feasibility rate (`ACTIONABLE / CONFIRMED`, [§15](#15-entry-feasibility-evaluation)) | `CONFIRMED` | `>= 0.60` |
| 1b | (complement) | Missed/late rate | `CONFIRMED` | `<= 0.40` |
| 2 | Low MAE | Median `execution_MAE_R` | `PATH_COMPLETE_ACTIONABLE` | `<= 1.0R` |
| 2b | (tail) | 90th-percentile `execution_MAE_R` | `PATH_COMPLETE_ACTIONABLE` | `<= 2.0R` |
| 3 | Sufficient MFE | Median `execution_MFE_R` | `PATH_COMPLETE_ACTIONABLE` | `>= 1.0R` |
| 3b | (breadth) | Proportion of episodes reaching `execution_MFE_R >= 0.5` before invalidation | `PATH_COMPLETE_ACTIONABLE` | `>= 0.50` |
| 4 | Performance after costs/delay | Mean `execution_cost_adjusted_return_R` ([§19](#19-execution-cost-assumptions)) | `PATH_COMPLETE_ACTIONABLE` | `> 0.10R` |
| 5 | Ordinary directional accuracy | `CONFIRMED` episodes where `execution_terminal_return_R > 0` | `PATH_COMPLETE_ACTIONABLE` | Reported only, **no threshold** — explicitly not a gate, per roadmap §H ("ordinary accuracy alone is not the promotion criterion"). |

**Priority 1/1b's population remains plain `CONFIRMED`/`ACTIONABLE`,
deliberately not `PATH_COMPLETE_ACTIONABLE`** — entry feasibility is
decided long before the future price path in question exists, so it is
not itself a path-dependent question, and requiring path-completeness
for it would incorrectly make a late-arriving data gap change how many
episodes even qualify as `ACTIONABLE`/`CONFIRMED` for the feasibility
rate ([§26.1](#261-episode-population-definitions)).

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
| `USER_FACING_ELIGIBLE` | **Both, evaluated per setup family, against that family's OWN population — never against the aggregate as a substitute** (amended, [§28.2's per-family gate](#282-promotion-levels) below): (a) the full acceptance metric hierarchy ([§27](#27-acceptance-metric-hierarchy)) passes over **that family's own** historical/replay sample meeting `MIN_COMPLETED_EPISODES_PER_FAMILY` ([§26](#26-acceptance-sample-requirements)), **and** (b) the live-shadow evidence requirement ([§28.2a](#282a-live-shadow-evidence-requirement)) is independently satisfied, also computed from **that family's own** live-shadow-only population. **Both (a) and (b) additionally require zero `analytical_path_complete = FALSE` episodes in the sample being evaluated** ([§28.2b](#282b-path-completeness-promotion-safety-rule--no-silent-exclude-and-pass)) — a sample containing any incomplete analytical path is `NOT EVALUABLE` for its path-dependent priorities, not silently passed on the remaining subset. A family failing (a), (b), or the path-completeness requirement — including a family with excellent historical replay metrics but insufficient live-shadow evidence, **or** a family whose own historical metrics fail despite the aggregate V2 sample passing and the other families performing well, **or** a family with an otherwise-passing sample that contains even one incomplete analytical path — stays `SHADOW_ELIGIBLE`. | User-facing V2 notifications for the qualifying family/families only. |
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

### 28.2b Path-completeness promotion safety rule — no silent exclude-and-pass

**New (tech-lead/red-team finding, closes a gap the `analytical_path_complete`
fact — [§18.2a.1](#182a1-missing-bar-behavior-and-terminal_reason) —
otherwise leaves open).** [§28.2](#282-promotion-levels)'s gate (a) and
this section's gate (b) both compute the full §27 acceptance metric
hierarchy over a family's own `CONFIRMED` sample. Priorities 2–5 of that
hierarchy are path-dependent (`PATH_COMPLETE_ACTIONABLE`-only,
[§26.1](#261-episode-population-definitions)/[§27](#27-acceptance-metric-hierarchy)).
Simply computing those priorities over whichever episodes happen to be
path-complete, silently dropping the rest, and declaring a pass is **not**
sufficient — that would let a family with real data-quality gaps still
reach `USER_FACING_ELIGIBLE` on an artificially cleaner subset, a
survivorship/data-quality bias this document does not accept.

**Frozen V2-v0 rule, deliberately conservative and deterministic — no new
percentage threshold:**

```text
For a setup family F's historical/replay acceptance gate (§28.2(a)):
    IF any episode in F's evaluated CONFIRMED acceptance sample has
        analytical_path_complete == FALSE
    THEN the path-dependent portion of F's §27 acceptance hierarchy
        (priorities 2-5) is: NOT EVALUABLE / INCOMPLETE DATA
    AND F MUST NOT pass the historical/replay USER_FACING_ELIGIBLE gate
        on that sample.
    F remains at most SHADOW_ELIGIBLE until the missing analytical path
    is repaired/recomputed (e.g. a backfill closes the data gap and the
    episode's outcome is recomputed) or a later, explicitly-versioned
    contract change revises this policy.

Likewise, for setup family F's live-shadow gate (§28.2a above):
    IF any episode in F's evaluated live-shadow CONFIRMED sample has
        analytical_path_complete == FALSE
    THEN that live-shadow USER_FACING_ELIGIBLE gate is NOT satisfied for F.

The V2-v0 requirement for a promotion-evaluable sample is exactly:
    ZERO incomplete analytical paths (analytical_path_complete == FALSE)
    inside that exact evaluated family sample (historical/replay OR
    live-shadow, evaluated independently for each).
```

**Do NOT treat `analytical_path_complete = FALSE` as a strategy failure**
(it is not evidence the setup underperformed) **and do NOT treat it as
successful evidence** (it is not evidence the setup performed well) — it
is **insufficient evaluation evidence**, and the family's path-dependent
promotion decision simply cannot be made from that sample yet.

**This does not touch [§26](#26-acceptance-sample-requirements)'s basic
`CONFIRMED` sample-size accounting.** `DATA_INCOMPLETE`/
`analytical_path_complete = FALSE` episodes remain historical `CONFIRMED`
episodes and remain fully visible in sample-size/data-quality accounting
([§26.1](#261-episode-population-definitions)) — the freeze here is
narrower and specific: they cannot be **silently excluded** so that a
`USER_FACING_ELIGIBLE` promotion gate passes on only the cleaner subset.
`SHADOW_ELIGIBLE` ([§28.2](#282-promotion-levels)) may still be reached
under the existing aggregate sample-minimum semantics regardless of this
rule — it only authorizes further parallel-shadow evaluation, not
user-facing delivery, so it carries no path-completeness requirement.
`USER_FACING_ELIGIBLE` is the level this rule actually gates, and it
requires **both** the relevant historical/replay **and** live-shadow
evaluation samples to be path-complete under the rule above, for that
family, independently.

See [§29.14b](#2914b-path-completeness-acceptance-vectors) for the
required worked vectors (an incomplete `ACTIONABLE` episode that must not
be silently dropped from the feasibility rate but does block the
path-dependent gate; a `COMPLETED` episode with an incomplete path,
proving `COMPLETED != analytical_path_complete`; and the fully
path-complete baseline case where §27's populations/thresholds apply
normally).

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
T1 = T_detect = 12:15 (a 15m decision boundary, also a 5m boundary):
   B15_detect = selected_bucket(15m, 12:15) = [12:00, 12:15).
   close(B15_detect) = 64,350.
   retracement_pct = (65,000-64,350)/65,000*100 = 1.0%;
   RANGE_PROXY_pct(15m,14,B15_detect) = 0.4%; valid range = [0.20%,1.20%] -> valid pullback.
   pullback_extreme_low = 64,300 (deepest close reached during the retracement).
   protection_buffer(15m,B15_detect,64,350) ≈ max(3*tick, 64,350*0.4%*0.5) ≈ 128.7
      (tick_size=0.1 for illustration).
   invalidation_price ≈ 64,300 - 128.7 = 64,171.3.
   B5_detect = selected_bucket(5m, 12:15) = [12:10, 12:15)
      (bucket_ts=12:10, bucket_end=12:15=T_detect -- per §1.3). B5_detect's
      own close (64,350) ALREADY satisfies the 5m resumption trigger on its
      own (price_move_pct_median sign +1, price_direction_agreement =
      0.75 >= 2/3) -- but per the T_confirm > T_detect rule above this does
      NOT confirm: confirmation is only ever evaluated at a decision
      boundary strictly later than T_detect, so B5_detect (whose bucket_end
      == T_detect itself) can never be the confirming bucket.
   => EARLY_SIGNAL at T1 = 12:15. detection_timestamp = 12:15.
      Entry zone (EARLY_SIGNAL entry-zone rule above): [pullback_extreme_low, close(B15_detect)]
                                        = [64,300, 64,350].

T2 = T_confirm = 12:20 (the earliest possible confirmation boundary,
    T_confirm = T_detect + 5m):
   B5_confirm = selected_bucket(5m, 12:20) = [12:15, 12:20)
      (bucket_ts=12:15=T_detect, bucket_end=12:20=T_confirm -- per §1.3;
      note bucket_ts(B5_confirm) == T_detect, NOT T_detect+5m -- it is the
      bucket's END, 12:20, that equals T_confirm). This is a different
      closed interval from B5_detect=[12:10,12:15), so it legitimately
      serves as the confirming bucket even though its start coincides with
      T_detect.
   B5_confirm closes at 64,350 (price steady). price_move_pct_median sign
   +1, price_direction_agreement = 0.75 >= 2/3 on B5_confirm -> resumption
   trigger holds on this later, distinct bucket.
   confirmation_close_price = close(B5_confirm) = 64,350.
   => CONFIRMED at T2 = 12:20 (T_confirm = 12:20 > T_detect = 12:15, strictly).
      Entry zone updates one final time and freezes (CONFIRMED entry-zone
      rule above): [64,300, 64,350] (numerically unchanged here since price
      was steady between T1 and T2 -- the zone still legitimately
      re-derives from confirmation_close_price, not from the stale
      EARLY_SIGNAL value).
      planned_risk_distance = |64,350 - 64,171.3| ≈ 178.7 > MIN_VALID_PLANNED_RISK -> valid.
```
→ `TREND_PULLBACK`, `LONG`, `EARLY_SIGNAL` at `T_detect = 12:15` (zone
`[64,300, 64,350]`, `invalidation_price ≈ 64,171.3`), `CONFIRMED` at
`T_confirm = 12:20 = T_detect + 5m` (zone frozen at `[64,300, 64,350]`) —
this is the precise case the `T_confirm > T_detect` rule guards against:
`B5_detect` already qualified for resumption at `T_detect` itself, yet the
episode is **not** confirmed until the next, distinct 5m bucket
`B5_confirm` at `T_confirm`.

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
`[compression_start_bucket, compression_end_bucket]` `= 63,800`;
`range_high` (same derivation, `HTF_high`) `= 64,100`
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
      SHORT invalidation_price = range_high + protection_buffer(...)
                                = 64,100 + buffer(≈96) ≈ 64,196
      (§7.2's frozen SHORT formula uses range_high, the OPPOSITE side of
      the compression range from the broken range_low boundary that
      triggered this SHORT episode — never range_low itself; an earlier
      draft of this vector incorrectly wrote "63,800 + buffer ≈ 63,930",
      which used the wrong boundary — already flagged, but not yet fixed
      here, by `docs/FORECASTING_ROADMAP.md`'s PR41 entry, which verified
      the correct value against the actual implemented formula).
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

### 29.11 Notification-eligibility and entry-feasibility vector

**Send-eligible now, graded `LATE` later ([§15.1](#151-send_time_notification_eligibility)
+ [§15.2](#152-assumed_entry_feasibility)).** Same `TREND_PULLBACK` `LONG`
`EARLY_SIGNAL` as [§29.6](#296-setup-vectors)'s valid vector:
`T_detect = 12:15`, entry zone `[64,300, 64,350]`, `invalidation_price ≈
64,171.3`.

```text
LIVE, at T_detect = 12:15 (§15.1 -- no future data):
   event_reference_time = T_detect = 12:15.
   event_reference_price = close(B15_detect) = 64,350 -- by construction
      the SAME value the EARLY_SIGNAL zone's dynamic bound is built from
      (§7.1), so for TREND_PULLBACK this value always sits exactly at the
      zone boundary at send time.
   OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(...) ≈ 32.2
   event_entry_zone_upper + OVERSHOOT_TOLERANCE = 64,350 + 32.2 = 64,382.2
   64,350 <= 64,382.2 (trivially, since it IS the zone bound) -> within tolerance.
      invalidation_price (64,171.3) not yet breached at T_detect.
   => send-eligible = TRUE. The first EARLY_SIGNAL notification is EMITTED
      at T_detect = 12:15, using only data closed as of T_detect.

RETROSPECTIVE, at assumed_entry_time = T_detect + 90s = 12:16:30 (§15.2
-- future data permitted as outcome input only):
   Sampled reference-exchange 1m close at/after 12:16:30: 64,420.
   64,420 > 64,382.2 -> outside tolerance, moved away from the zone.
   => assumed-feasible = FALSE. This EARLY_SIGNAL event's lateness_status
      = LATE (evaluation-only fact).
```
→ The notification **was already sent** at `T_detect = 12:15` — that
historical fact ([§16.1](#161-early_signal-notification-content-and-history-invariants-v2-v0))
is **never rewritten** by the later grade. The `LATE` grade only affects
whether this event counts in the `ACTIONABLE` numerator
([§26.1](#261-episode-population-definitions)) — it does **not** retract,
hide, or annotate the notification as "shouldn't have been sent." This is
exactly what the feasibility acceptance metric measures: a scenario V2 was
willing to publish live can still, in hindsight, have been unactionable —
future data grades the notification, it never decides whether the earlier,
already-historical notification was sent.

**Immediate send suppression ([§15.1](#151-send_time_notification_eligibility),
no future data needed).** `COMPRESSION_BREAKOUT` `SHORT`, reusing
[§29.6](#296-setup-vectors)'s valid vector's `range_low = 63,800`, entry
zone `[range_low - buffer, range_low] ≈ [63,670, 63,800]` — but with a far
more violent breaking 5m candle than that vector's `63,740`, closing
instead at `63,600`:

```text
LIVE, at T1 (§15.1 -- no future data):
   event_reference_time = T1.
   event_reference_price = 63,600 (the breakout bucket's own close -- the
      same value the detector already used to decide this EARLY_SIGNAL
      event, never sampled separately).
   OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(...) ≈ 32.2 (same order
      as the compression window's own protection_buffer).
   event_entry_zone_lower - OVERSHOOT_TOLERANCE = 63,670 - 32.2 = 63,637.8
   63,600 < 63,637.8 -> already beyond tolerance AT THE MOMENT OF DETECTION.
   => send-eligible = FALSE. No normal actionable notification is emitted
      for this EARLY_SIGNAL. The episode is still created and persisted /
      research-visible (§17) -- it simply never produces that particular
      actionable notification.
```
→ This is exactly the case the live send gate exists for: a breakout so
violent that price has already run past the entry zone's tolerance by the
time the detector's own deciding candle closes — recognizable
**immediately**, from data the detector already has; no `T+90s` sample is
needed or used.

**`CONFIRMED` graded `LATE` retrospectively ([§15.2](#152-assumed_entry_feasibility)).**

```text
CONFIRMED at T (TREND_PULLBACK LONG), entry_zone = [64,300, 64,350].
   event_reference_price = confirmation_close_price = 64,350 -> send-eligible
   = TRUE at T (same "trivially at the zone bound" property as EARLY_SIGNAL
   above) -> the CONFIRMED notification IS emitted at T.

ASSUMED_USER_ACTION_DELAY_S = 90 -> assumed_entry_time = T + 90s.
Sampled reference-exchange 1m close at/after assumed_entry_time: 64,410.
OVERSHOOT_TOLERANCE = 0.25 * protection_buffer(...) ≈ 32.2
entry_zone_upper + OVERSHOOT_TOLERANCE = 64,350 + 32.2 = 64,382.2
64,410 > 64,382.2 -> ASSUMED-INFEASIBLE / LATE. lateness_status = LATE.

=> The CONFIRMED notification was already sent (send-eligible at T); the
   episode is analytically CONFIRMED and structurally sound (never
   invalidated), but is retrospectively graded LATE — it MUST NOT count as
   a successful actionable V2 call in acceptance metrics' feasibility rate
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
  7 ACTIONABLE (feasible entry reached)
  3 LATE (feasibility check failed, §15)
  0 INVALIDATED_BEFORE_ENTRY -- reserved/currently-unreachable under
    V2-v0's frozen timing (§15.2's reachability note); a real acceptance
    sample under the current rules_version never populates this bucket

Sample-size count (§26, MIN_COMPLETED_EPISODES_*):        10  (all CONFIRMED, any lateness_status)
Actionable-entry feasibility rate (§27 priority 1):        7 / 10 = 0.70   (denominator = CONFIRMED = 10)
Missed/late rate:                                          3 / 10 = 0.30   (the 3 LATE; INVALIDATED_BEFORE_ENTRY unreachable under current rules)
Median execution_MAE_R / median execution_MFE_R / mean execution_cost_adjusted_return_R:  computed over the 7 ACTIONABLE episodes only
                                                             (denominator = 7, NOT 10 — the 3 non-actionable
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

### 29.14b Path-completeness acceptance vectors

Demonstrates [§18.2a.1](#182a1-missing-bar-behavior-and-terminal_reason)'s
`analytical_path_complete` fact and
[§28.2b](#282b-path-completeness-promotion-safety-rule--no-silent-exclude-and-pass)'s
no-silent-exclude-and-pass promotion safety rule:

```text
VECTOR A -- incomplete ACTIONABLE episode blocks the path-dependent gate
but not the feasibility rate:
  COMPRESSION_BREAKOUT's historical/replay sample: 100 CONFIRMED episodes,
  70 ACTIONABLE. One of those 70 ACTIONABLE episodes has
  analytical_path_complete = FALSE (a late data gap after a proven
  favorable-excursion threshold crossing -- COMPLETED, terminal_reason=
  HORIZON_COMPLETION, analytical_path_complete=FALSE, per §18.2a.1 case A).

  Actionable-entry feasibility rate (§27 priority 1, population = CONFIRMED,
  §26.1): 70 / 100 = 0.70 -- still valid and reportable exactly as
  computed; the one incomplete-path episode is NOT removed from either
  the numerator (it IS ACTIONABLE) or the denominator (it IS CONFIRMED) --
  feasibility does not require analytical_path_complete at all (§26.1/§27).

  Priorities 2-5 (population = PATH_COMPLETE_ACTIONABLE, §26.1/§27):
  => NOT EVALUABLE / INCOMPLETE DATA for this family's sample, per
     §28.2b -- because at least one episode in the evaluated CONFIRMED
     sample has analytical_path_complete = FALSE. The correct treatment
     is NOT to compute priorities 2-5 over the other 69 path-complete
     ACTIONABLE episodes and declare a pass -- that would be exactly the
     silent exclude-and-pass §28.2b forbids. COMPRESSION_BREAKOUT's
     historical/replay gate (§28.2(a)) is therefore NOT satisfied on this
     sample; the family remains at most SHADOW_ELIGIBLE until the gap is
     repaired/recomputed.

VECTOR B -- a COMPLETED episode with an incomplete path:
  T_confirm=14:00, H=1.5h -> evaluation interval [14:00, 15:30).
  analytical_MFE_R reaches 0.55 (>= MIN_MFE_R_FOR_COMPLETION=0.5) at 14:22,
  proven entirely from bars 14:00-14:30. Bars 14:31-15:29 are then missing
  (a later data-collection gap).
  => episode_state = COMPLETED, terminal_reason = HORIZON_COMPLETION,
     analytical_path_complete = FALSE (§18.2a.1 case A).
  This proves directly: COMPLETED does NOT imply a complete analytical
  path, and terminal_reason alone (HORIZON_COMPLETION, which contains no
  hint of incompleteness) does NOT fully encode path completeness --
  analytical_path_complete MUST be checked as its own, independent fact
  for every episode entering a path-dependent metric computation, exactly
  as §18.2a.1 freezes.

VECTOR C -- fully path-complete family sample (baseline case):
  CONFIRMED_BREAKOUT's historical/replay sample: 45 CONFIRMED episodes, 30
  ACTIONABLE, analytical_path_complete = TRUE for every one of the 45
  episodes (no data gaps in this sample).
  => ACTIONABLE == PATH_COMPLETE_ACTIONABLE for this sample (30 == 30, no
     episode excluded by the path-completeness rule). §27's existing
     populations/thresholds apply normally, with no NOT EVALUABLE
     qualifier -- §28.2b's rule is satisfied vacuously (zero incomplete
     paths), and the family's historical/replay gate (§28.2(a)) proceeds
     to evaluate priorities 1-5 exactly as already frozen.

VECTOR D -- survivorship-bias check: INVALIDATED outcomes MUST NOT
disappear from path-dependent metrics (re-amended, closes the round-5
gap where analytical_path_complete was unconditionally NULL for
INVALIDATED, §18.2a.1):
  TREND_PULLBACK's historical/replay sample: 70 ACTIONABLE episodes --
      50 reach a horizon terminal (COMPLETED/EXPIRED) with a complete
          own path (analytical_path_complete = TRUE);
      20 reach structural INVALIDATED, each with a complete own
          pre-invalidation path [T_confirm, T_invalidation)
          (analytical_path_complete = TRUE for all 20).
  => ALL 70 are members of PATH_COMPLETE_ACTIONABLE -- the 20 INVALIDATED
     episodes are NOT excluded merely because they are INVALIDATED.
     Median/90th-percentile execution_MAE_R, median execution_MFE_R, the
     >=0.5 proportion, mean execution_cost_adjusted_return_R, and
     execution_terminal_return_R directional accuracy (§27 priorities
     2-5) MUST be computed over all 70, including the 20 INVALIDATED
     outcomes' own execution_MAE_R/execution_MFE_R/execution_terminal_return_R
     -- an adverse INVALIDATED outcome is exactly the kind of result a
     path-dependent risk metric like execution_MAE_R exists to capture;
     computing these metrics from only the 50 horizon-terminal episodes
     would be a survivorship-bias exclusion, not conforming V2-v0
     behavior.

  Now suppose one of the 20 INVALIDATED episodes turns out to have one
  missing required 1m bar strictly inside its own
  [T_confirm, T_invalidation) interval (bars after its own
  T_invalidation remain irrelevant and are never checked, §18.2a.1):
  => that one episode's analytical_path_complete becomes FALSE.
     Per §28.2b: the family's historical/replay path-dependent
     USER_FACING gate becomes NOT EVALUABLE / INCOMPLETE DATA for this
     sample, in full -- exactly as it would if any horizon-terminal
     episode had an incomplete path. The evaluator MUST NOT simply drop
     that one INVALIDATED episode and compute priorities 2-5 from the
     remaining 69 -- that is precisely the silent exclude-and-pass
     §28.2b forbids, regardless of whether the excluded episode's own
     terminal state was COMPLETED, EXPIRED, or INVALIDATED.
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
