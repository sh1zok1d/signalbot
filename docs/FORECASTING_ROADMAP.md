# Forecasting Roadmap — V1 Freeze and V2 Product Direction

This is the **canonical source of truth for the forecasting product
direction**. It supersedes any other document as the place to look for "what
is the forecasting product doing next" — historical Stage 2 planning
documents (`STAGE2_SPEC.md`, `STAGE2_IMPLEMENTATION_PLAN.md`,
`STAGE2_CLARIFICATIONS.md`, `STAGE2_DATA_AUDIT.md`) remain valid records of
what was decided and built for the Stage 2 **foundation** (ingestion,
per-exchange/consensus feature computation, data confidence, percentile
engine), but they do not describe the current or future forecasting product
direction going forward.

Once V2 planning moves past this roadmap's high-level direction, more
detailed contracts take over: **`docs/V2_PRODUCT_CONTRACT.md`** freezes what
V2 product behavior must be (mission/scope, setup families, episode
lifecycle, confidence semantics, notification rules), and
**`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`** freezes the exact
deterministic formulas/thresholds and promotion criteria. Both are now
frozen. See §D and §I below.

This document uses the conceptual labels **V1** and **V2** to distinguish the
current shadow forecast heuristic from the planned multi-timeframe product.
They started as planning labels only; `model_family` now physically encodes
them as a schema-level identity (`'v1'` pinned on `forecast_predictions` /
`forecast_outcomes`, `'v2'` pinned on the new `v2_episode_events` table) —
see [§A](#a-decision-status) and [§J](#j-current-and-next-status) for
exactly what that does and does not imply.

---

## A. Decision status

- Further **product development of the current V1 forecast logic is
  frozen** as of this PR. "Product development" means tuning V1's
  behavior or signal output — see [§C](#c-v1-freeze-policy) for the exact
  boundary between allowed maintenance and disallowed product work.
- **V1 remains an operational research baseline.** It keeps running exactly
  as deployed: the shadow forecast timer, the Telegram notifier, prediction
  persistence, and outcome evaluation are unaffected by this decision.
- The project now moves to **V2 planning and implementation**, starting with
  this transition PR and continuing through the staged roadmap in
  [§I](#i-high-level-delivery-roadmap).
- This decision does **not** disable or pause ingestion, feature computation,
  prediction persistence, outcome evaluation, shadow recovery/catch-up, or
  any other existing infrastructure. Nothing about the running system
  changes as a result of this PR.

This PR does **not** rename or reinterpret any persisted `rule_version` or
`calculation_version` value — those remain exactly what they are today,
scoped to V1. A `model_family` column / model registry, which would let the
schema distinguish V1 from a future V2 model at the row level, was
**future work** for a later PR at the time this transition PR was written
(see [§I](#i-high-level-delivery-roadmap), stage 2). That later PR
("feat: add V2 multi-model foundation") has since landed: `forecast_predictions`
and `forecast_outcomes` now carry a DB-owned, additive `model_family` column
pinned to `'v1'` by CHECK constraint, and `config/v2.yaml` /
`common/v2_config.py` / `analytics/forecasting_v2/identity.py` physically
encode the `model_family` / `rules_version` identity conventions a future V2
model will use. "V1" and "V2" are no longer purely documentation-level
concepts — see [§J](#j-current-and-next-status) for the current, precise
state of what physically exists versus what is still unimplemented
forecasting/runtime logic.

---

## B. Honest characterization of V1

V1 is the forecast logic implemented in `analytics/forecasting/core.py`
(`compute_forecast_decision`) together with its rule set in
`analytics/forecasting/models.py`. Concretely, and verified directly against
the current code:

- It is a **5m cross-exchange momentum/continuation baseline**: a weighted
  combination of price, taker flow, open interest, funding, liquidation, and
  cross-exchange agreement component scores, gated by coverage/confidence/
  primary-signal thresholds (`analytics/forecasting/core.py`,
  `analytics/forecasting/models.py`).
- It is **computed from one closed 5m consensus bucket** — the module
  docstring is explicit that scope is "the CURRENT shadow scope only:
  BTCUSDT / perp / 5m", and `runtime/shadow_cli.py` hardcodes
  `_TIMEFRAME = "5m"` for the live pipeline. `analytics/forecasting/
  shadow_cycle.py` is, in its own words, "a thin composition boundary for
  one caller-selected, already closed 5m bucket."
- It has been **useful for validating the engineering platform** — ingestion,
  feature computation, consensus aggregation, prediction persistence,
  outcome evaluation, recovery/catch-up, and now durable Telegram delivery
  all exist and are exercised end to end because V1 gave the platform
  something concrete to compute and deliver.
- It has been useful for **testing a simple forecast hypothesis**: does a
  single-bucket weighted heuristic over price/flow/OI/funding/liquidation
  agreement produce an actionable directional signal.
- It is **not currently accepted as a useful intraday trading assistant**.
  See the limitations below and the operator observation at the end of this
  section.

### Observed product limitations

- **Signals may repeat every five minutes during one market episode.** Since
  V1 evaluates one closed 5m bucket independently each cycle, a single
  sustained move can produce a new `LONG`/`SHORT` prediction on consecutive
  buckets.
- **Repeated signals are correlated observations, not independent
  forecasts.** Nothing in the current design links consecutive bucket
  decisions into one tracked episode — each is scored and persisted on its
  own.
- **Signals can arrive after the visible move has already started.** A 5m
  bucket only closes, and is only evaluated, after the price action within
  it has already happened.
- **V1 lacks 4h/1h/15m structural context.** The single consensus vector fed
  into `compute_forecast_decision` carries no higher-timeframe regime, bias,
  or setup information.
- **The current 15m/1h/4h horizons are outcome-evaluation windows, not
  forecast inputs.** `analytics/forecasting/outcomes.py` computes horizon
  outcome metrics (return, MFE/MAE) for what happens in the 15m/1h/4h
  *after* a 5m prediction — its own docstring calls it "the Stage 2 shadow
  forecast OUTCOME evaluator (15m/1h/4h)." These horizons measure the
  prediction's future performance; they are not read by
  `compute_forecast_decision` as multi-timeframe context.
- **Telegram output can therefore behave more like momentum confirmation or
  nowcasting than an early 1–4 hour forecast** — the mechanics above mean a
  notification is more likely to describe a move already underway than to
  anticipate one 1–4 hours ahead.

### Operator observation (not a validated statistic)

The operator has **informally observed** low practical accuracy — roughly
around 30% — and substantial lateness when using V1's live Telegram output
during manual review. This is stated here explicitly as an **informal
operator observation that still requires formal reporting**, not as a number
computed from `forecast_outcomes` or any other database aggregate. No
statement in this document should be read as claiming V1 has a formally
measured or validated win rate, nor that V1 has proven negative expectancy —
the repository does not currently contain that analysis. Producing a rigorous
accuracy/expectancy report from the persisted `forecast_predictions` /
`forecast_outcomes` history is out of scope for this PR and is not listed as
a precondition for the V1 freeze: the freeze is a product-direction decision,
not a claim that a formal evaluation has already been completed.

---

## C. V1 freeze policy

V1 stays in place and keeps running so it can serve as a **stable comparison
baseline for V2** — future evaluation work can compare V2 episodes against
what the simpler single-bucket heuristic would have said, using an unchanged
reference implementation.

### Allowed V1 changes

- Critical bug fixes.
- Security fixes.
- Data-loss prevention.
- Operational reliability fixes (e.g. the durable Telegram outbox/retry work,
  recovery/catch-up correctness).
- Compatibility fixes required to keep the baseline running (dependency
  upgrades, deprecated API replacements, etc.).
- Corrections necessary to preserve **valid historical evaluation** (e.g. a
  bug that would corrupt outcome measurement for already-persisted
  predictions).

### Disallowed V1 product work

- Tuning V1's component weights or actionability thresholds.
- Adding new V1 signal reasons.
- Redesigning V1's confidence calculation.
- Adding more V1 trading setups.
- Trying to improve V1's Telegram signal frequency.
- Adding external market data sources specifically to improve V1.
- Turning V1 into the future multi-timeframe model through incremental
  patches — that work belongs to V2's dedicated contract and implementation
  PRs ([§I](#i-high-level-delivery-roadmap)), not to changes layered onto V1.

This PR makes **no runtime or Telegram behavior change** to V1. Any future
operational notification change (e.g. pausing V1 Telegram delivery once V2
ships) requires its own explicit PR or deployment action — it is not implied
or authorized by this document.

---

## D. Adopted V2 product direction

**V2** is adopted as the forecasting product's direction going forward: a
**multi-timeframe intraday scenario-monitoring system** targeting
approximately **1–4 hour trades**.

Its purpose:

- Detect a trade scenario **before most of the expected move is completed**.
- Provide an **early scenario notification**.
- Provide **model confidence**, clearly distinguished from a calibrated
  historical success probability (see [§H](#h-v2-evaluation-priorities)).
- Provide an **entry zone**.
- Provide a **structural invalidation** level.
- Provide an **expected horizon**.
- **Continue monitoring** the same scenario over time rather than emitting
  one-off independent signals.
- Send **material updates** when evidence strengthens or weakens.
- **Invalidate** a broken scenario.
- Report a **reversal candidate** only when the opposite scenario
  **independently** begins satisfying its own entry conditions — a reversal
  is never inferred merely from the original scenario invalidating.
- **Suppress trading notifications** when the entry zone has already been
  missed.
- Still **retain late/non-actionable model decisions for research
  statistics**, even when no notification is sent.
- Remain **decision support only**: the user performs their own chart
  analysis and decides whether to enter. V2 does not tell the user to
  execute a trade.
- **Never execute trades automatically** in the initial V2 scope.

This direction is a return to, and a formalization of, the multi-timeframe
context (`docs/PRODUCT_SPEC_V0.md`: "Контекст (старшие таймфреймы): 15m, 1h,
4h") and staged signal lifecycle (`EARLY → ARMED → TRIGGERED →
INVALIDATED/EXPIRED`) already present in the original product spec, which
V1 deliberately simplified away in order to validate the platform first.

The detailed, normative freeze of what V2 product behavior means — mission
and scope boundaries, the setup-family definitions, the full episode
lifecycle, the user-visible scenario information contract, confidence
semantics, entry-feasibility/lateness behavior, and the notification
anti-spam contract — lives in **`docs/V2_PRODUCT_CONTRACT.md`**, not in this
section. This roadmap remains the canonical source for *product direction*;
that document is the canonical source for *what V2 must do*.

---

## E. Multi-timeframe responsibilities

The high-level role split across timeframes is frozen as:

| Timeframe | Responsibility |
|---|---|
| `4h` | Market regime |
| `1h` | Directional bias |
| `15m` | Setup formation |
| `5m` | Trigger and ongoing monitoring |

These four timeframes do **not** provide four independent votes. Each has a
distinct semantic responsibility specifically so the same underlying price
movement is not double-counted across timeframes (e.g. a single strong move
should not simultaneously register as "4h regime confirmation" and "1h bias
confirmation" and "15m setup" as if they were three independent pieces of
evidence).

**Only fully closed buckets may be used** as input at every timeframe — no
timeframe may read a bucket that has not yet closed. The precise timestamp
alignment and no-lookahead semantics across four simultaneous timeframes are
non-trivial and are now **frozen in
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §1–§2** rather than decided
here.

---

## F. Initial V2 setup scope

The initial V2 scope contains exactly **three** setup families:

1. `TREND_PULLBACK`
2. `COMPRESSION_BREAKOUT`
3. `CONFIRMED_BREAKOUT`

**Countertrend trading signals are excluded** from the initial V2 release.

The first V2 implementation must use only **existing perp data** already
ingested by this platform:

- Price and volume.
- Taker flow.
- Open interest.
- Funding.
- Liquidations.
- Binance / Bybit / OKX consensus.

Explicitly deferred (not in the initial V2 scope):

- Spot ingestion.
- Orderbook ingestion.
- CoinGlass or other third-party vendor data.
- Market-cap feeds.
- ML models.
- Automatic execution.
- Portfolio sizing.
- Multi-symbol expansion.

---

## G. Signal episode concept

V2 adopts a set of high-level episode states — their full product meaning
is frozen in `docs/V2_PRODUCT_CONTRACT.md` §5:

- `EARLY_SIGNAL`
- `CONFIRMED`
- `WEAKENING`
- `INVALIDATED`
- `REVERSAL_CANDIDATE`
- `EXPIRED`
- `COMPLETED`

V2 tracks **one episode over time** — instead of emitting a new independent
signal every five minutes the way V1 does. An episode need not visit every
state before reaching `INVALIDATED`/`EXPIRED`/`COMPLETED`; invalidation does
**not**, by itself, imply reversal; and `REVERSAL_CANDIDATE` requires the
opposite direction to **independently** satisfy its own scenario-entry
requirements, rather than being inferred from the original scenario
breaking.

This roadmap deliberately does **not** diagram an exact transition graph.
Which edges are allowed, exact recovery behavior from `WEAKENING`, and
terminal-state mechanics are now **frozen in
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §13**; only the physical
Episode State Machine implementation remains a later stage
([§I](#i-high-level-delivery-roadmap): "6. Episode State Machine"). This
section freezes the *state set and the product invariants above*, not a
transition graph — the graph itself now lives in the correctness contract.

---

## H. V2 evaluation priorities

The order of evaluation priorities is frozen as:

1. **Entry feasibility after real notification delay** — can a user
   realistically still take the trade after the time it takes to notice and
   act on a notification.
2. **Low MAE** (maximum adverse excursion) — how much the trade moves against
   the entry before resolving.
3. **Sufficient MFE** (maximum favorable excursion) — enough favorable room
   for the scenario to be worth taking.
4. **Performance after estimated fees and execution delay.**
5. **Ordinary directional accuracy.**

**Ordinary accuracy alone is not the promotion criterion** for V2 — a setup
that is "usually right" but consistently late, or right in a way that leaves
no feasible entry, does not qualify on accuracy alone.

A **calibrated historical success probability must not be displayed** to
users until (a) enough comparable completed episodes exist to support a
calibration, and (b) the calibration methodology itself has been frozen in a
future contract PR. Until then, V2 confidence is reported the same way V1's
is today: an explicit model confidence, never presented as a calibrated
probability.

---

## I. High-level delivery roadmap

The accepted ten implementation stages after this transition PR:

1. V2 Product Contract
2. Multi-model Framework
3. Multi-timeframe Alignment
4. Context Engines
5. Setup Detectors
6. Episode State Machine
7. Entry Feasibility
8. V2 Outcome Evaluator
9. Telegram V2
10. Parallel Shadow Deployment

Planned PR sizing:

| Stage | Planned PRs |
|---|---|
| This transition PR | 1 |
| 1. V2 Product Contract | 2 |
| 2. Multi-model Framework | 3 |
| 3. Multi-timeframe Alignment | 3 |
| 4. Context Engines | 3 |
| 5. Setup Detectors | 4 |
| Pre-Stage-6 hardening (new phase; contract consolidation + quality/scoring + replay/provenance/coherence + persistence/idempotency) | 4 (revised from 0; see §J) |
| 6. Episode State Machine | 5 (revised from 3; see §J — the hardening work above was split OUT of this stage, not added to it; five distinct implementation units are listed in the prose, not forced into four merely to preserve an old count) |
| 7. Entry Feasibility | 2 |
| 8. V2 Outcome Evaluator | 3 |
| 9. Telegram V2 | 2 |
| 10. Parallel Shadow Deployment | 2 |
| **Total planned scope** | **~34** |

This sizing is a **planning estimate**, not a requirement to force unsafe or
poorly-reviewable changes into fixed PR boundaries. A PR may be split further
whenever reviewability or risk requires it — the numbers above describe
current intent, not a contract that overrides sound engineering judgment.

---

## J. Current and next status

- **V1**: implemented, running as a frozen baseline (see
  [§C](#c-v1-freeze-policy)).
- **V2**: adopted direction. Its **forecasting/runtime behavior is still not
  implemented** — no multi-timeframe alignment, context engine (4h regime /
  1h bias), setup detector, episode state machine, entry-feasibility
  evaluation, V2 outcome evaluator, Telegram V2, or runtime V2 execution
  exists anywhere in the codebase. The Multi-model Framework's
  identity/config/schema **foundation** now exists (see the Stage 2 bullet
  below) — that is physical scaffolding for later stages to build on, not
  forecasting logic itself. Product behavior is frozen in
  `docs/V2_PRODUCT_CONTRACT.md`
  (mission/scope, timeframe responsibilities, episode concept, initial setup
  families, episode lifecycle, confidence semantics, entry-feasibility/
  notification product rules, and hard gates carried forward from
  `docs/PRODUCT_SPEC_V0.md`), and its exact deterministic behavior and
  acceptance criteria are frozen in
  `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` (alignment/no-lookahead,
  model/version identity, context formulas, setup-detector formulas,
  confidence/entry-zone/invalidation semantics, episode identity/lifecycle,
  entry feasibility, evaluation/replay methodology, acceptance sample and
  promotion criteria).
- **Stage 1 — V2 Product Contract documentation phase: complete.** Both
  planned documentation PRs are authored, reviewed, and merged to `main` —
  `docs/V2_PRODUCT_CONTRACT.md` (PR #28) and
  `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` (PR #29).
- **Stage 2 — Multi-model Framework: COMPLETE.** All three planned PRs are
  merged to `main`.
  - **PR 1 of ~3 — foundation: merged.** A small, self-contained
    **foundation PR** ("feat: add V2 multi-model foundation") introduced
    **only** the identity/config/module foundation the rest of the stage
    builds on: the `model_family` / `rules_version` identity conventions
    frozen in `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3, physically
    encoded as `config/v2.yaml` + `common/v2_config.py` (a strict loader,
    independent of `common/stage2_config.py`) and
    `analytics/forecasting_v2/identity.py` (a pure `V2ModelIdentity` value
    object); plus a DB-owned, additive `model_family` column on
    `forecast_predictions` / `forecast_outcomes` (pinned to `'v1'` by CHECK
    constraint on both the fresh-create and upgrade paths, per §A above).
    That foundation PR deliberately implemented **no** forecasting logic: no
    multi-timeframe alignment, no 4h regime / 1h bias / context engines, no
    setup detectors, no episode lifecycle/state machine, no
    entry-feasibility evaluation, no V2 outcome evaluator, no V2 Telegram,
    and no runtime wiring of any kind.
  - **PR 2 of ~3 — immutable episode-event persistence: merged.**
    ("feat: add immutable V2 episode event persistence"). Added the durable
    **persistence boundary** for future V2 episode events: a
    `V2EpisodeEvent` value object (`analytics/forecasting_v2/events.py`),
    an additive `v2_episode_events` table
    (`storage/stage2_schema.sql`, keyed on `(run_kind, run_id, event_id)`
    so `LIVE` and `REPLAY` runs never collide), and an insert-once writer
    (`storage/v2_serialization.py`, `Database.insert_v2_episode_events`)
    that stores an already-decided event's inputs/outputs **by value** and
    never rewrites a stored row (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
    §2.1). That PR deliberately implemented **no** episode state machine: it
    does not decide whether an event should exist, compute
    `structural_anchor`, run MTF alignment/context/setup-detector logic, or
    wire anything into a runtime path.
  - **PR 3 of ~3 — event construction boundary: merged.**
    ("feat: complete V2 multi-model event boundary"), the **final planned
    PR** of the Multi-model Framework stage. Completed the framework with a
    pure, narrow event-construction/provenance boundary so later V2 modules
    do not each hand-assemble `V2EpisodeEvent`'s twenty fields at every call
    site: `V2EventProvenance` (`analytics/forecasting_v2/provenance.py`), a
    frozen snapshot of one event-construction operation's run/model/shared
    Stage 2 provenance; `build_v2_episode_event()`
    (`analytics/forecasting_v2/event_factory.py`), the one canonical pure
    factory combining a `V2EventProvenance` with already-decided
    event-specific facts into a `V2EpisodeEvent` — provenance-owned fields
    (`run_kind`, `run_id`, `model_family`, `rules_version`, `symbol`,
    `market_type`, and the shared Stage 2 provenance fields) are not
    parameters of this function, so a caller cannot override them; and
    `V2EpisodeEventWriter` (`analytics/forecasting_v2/ports.py`), a narrow
    structural-typing `Protocol` future orchestration code depends on
    instead of importing `storage.db.Database` directly. This PR also
    hardens `V2EpisodeEvent`'s JSON-leaf validation (non-finite floats and
    naive/non-UTC datetimes inside `structural_anchor`/`decision_snapshot`/
    `event_payload` now fail at construction, aligned with the canonical
    serializer) and makes **no** DB schema change beyond a comment. Like PR
    2, this PR deliberately implements **no** episode state machine, no MTF
    alignment, no context engine, no setup detector, and no runtime wiring
    — `v2.enabled` stays `false` and nothing calls the new factory/writer
    port outside its own tests.
  - `v2.enabled` remained `false` throughout Stage 2. **V1 remains the
    running baseline**, entirely unaffected by any Stage 2 PR.
  - **V2 still had no forecasting logic of any kind** beyond the identity,
    persistence, and construction-boundary foundation Stage 2 built — no
    MTF alignment/context/setup-detector/episode-state-machine runtime
    existed yet, and nothing yet decided what a `V2EpisodeEvent` should
    contain. (See the Stage 3 bullet below for what has since begun.)
- **Stage 3 — Multi-timeframe Alignment: COMPLETE.** All three planned PRs
  are merged to `main`.
  - **PR 1 of ~3 — deterministic decision clock + closed-bucket alignment:
    MERGED** (#33, "feat: add V2 multi-timeframe decision alignment").
    Implemented exactly the two pure timestamp-selection layers
    `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §1 freezes:
    `decision_boundary(now, soft_grace_s=...)` (wall-clock processing time
    -> the logical closed-5m decision boundary `T`, reusing —
    re-implemented locally, never imported, to avoid an `analytics ->
    runtime` dependency — the exact algorithm already frozen and shipped in
    `runtime/shadow_cli.py::select_latest_closed_5m_bucket`, proven
    equivalent by test) and `selected_bucket(timeframe, T)` (given `T`,
    deterministically selects the legal closed bucket START for `5m`/
    `15m`/`1h`/`4h`, using integer minutes-since-UTC-epoch grid math so 4h
    boundaries land on `00:00/04:00/08:00/12:00/16:00/20:00` UTC without
    special-casing hours). That PR's scope was exactly Layer 1/Layer 2
    timestamp selection — it did **not** read
    `exchange_feature_vectors`/`consensus_feature_vectors`/
    `percentile_snapshots`/`data_health_snapshots`, did not implement 4h
    regime/1h bias/normalized evidence/OI confirmation, and did not touch
    any setup detector, episode identity, episode state machine, entry
    feasibility, outcome evaluation, Telegram, or runtime wiring.
  - **PR 2 of ~3 — deterministic Stage 2 aligned input readers: MERGED**
    (#34, "feat: add V2 aligned input readers"). Answers the read-side
    question PR 1 left open: given an already-selected legal timestamp/
    cutoff, how to read EXACTLY the corresponding Stage 2 data row(s), not
    what those rows mean. Adds `storage/v2_alignment_readers.py` (three
    read primitives — `read_v2_consensus_feature`,
    `read_v2_consensus_percentiles`, `read_v2_data_health_at_cutoff` — plus
    matching `storage.db.Database` wrappers): the ONE
    `consensus_feature_vectors` row at an EXACT `bucket_ts` (never `<=`,
    never a latest-bucket fallback); every consensus-scope
    `percentile_snapshots` row at that same EXACT `bucket_ts`
    (`scope='consensus'`/`exchange=''`, exchange-scoped percentiles out of
    scope); and, for `data_health_snapshots`, the bounded-latest row per
    `(exchange, metric)` with `snapshot_ts <= cutoff_ts` — an explicit,
    caller-supplied historical cutoff, never `now()`/wall clock, with a
    row exactly at the cutoff eligible. `calculation_version` is required
    and explicit on every read; a missing exact-bucket row returns `None`/
    `()`, never an older bucket; a missing requested health pair is
    explicitly `None` in the result, never fabricated as healthy.
    `computed_at` is never used to decide historical legality (Stage 2
    corrections upsert in place under the same `calculation_version`,
    §2.1). No context/scoring interpretation, no raw structural OHLC
    (`klines_1m`) reads, no `exchange_feature_vectors` reads. `v2.enabled`
    stays `false`; `v2.rules_version` is unchanged (`v2-rules-v0.1.0`) —
    this PR implements already-frozen data-selection semantics, not a new
    or tuned V2-v0 parameter; no schema/config change.
  - **PR 3 of ~3 — aligned-input snapshot assembly: MERGED** (#35,
    "feat: complete V2 multi-timeframe input alignment"), the **final
    planned PR** of the Multi-timeframe Alignment stage. Includes both
    the initial implementation and a pre-merge hardening amendment (fixed
    head `8deaa3e`): deep immutability at the aligned-snapshot boundary
    (every family — consensus/percentiles/health/reference_feature/
    reference_klines — is recursively detached into new
    `MappingProxyType`/`tuple` structures before being stored, so the
    snapshot never retains a reader-owned mutable reference), the
    explicit health-missingness contract enforced defensively at this
    boundary too (the result mapping always contains EVERY requested
    `(exchange, metric)` key, explicit `None` when no eligible snapshot
    exists — a reader silently omitting or adding a key is treated as
    corruption), strengthened percentile identity re-validation, and
    fail-closed raw-kline timestamp validation (a malformed `ts` raises
    the documented domain error, never a bare `TypeError`/`AttributeError`).
    Composes PR 1's decision clock and PR 2's exact-bucket/bounded-cutoff
    Stage 2 readers,
    plus two NEW canonical Binance reference-exchange read primitives
    (`read_v2_reference_feature` — the ONE `exchange_feature_vectors` row
    at an EXACT `(exchange, symbol, market_type, timeframe, bucket_ts,
    calculation_version)` identity; `read_v2_reference_klines` — raw
    `klines_1m` bars inside a caller-supplied half-open `[bucket_start,
    bucket_end)` interval, storage-layer-generic about `exchange`), into
    ONE immutable, deterministic `V2AlignedInputs` snapshot
    (`analytics/forecasting_v2/aligned_inputs.py::load_v2_aligned_inputs`)
    future Stage 4 Context Engines will consume. Pins the canonical V2
    reference exchange (§11) to exactly `V2_REFERENCE_EXCHANGE = "binance"`
    — no caller-overridable parameter, no silent Bybit/OKX failover ever;
    if Binance's reference vector for a bucket fails the frozen §11 gate
    (`is_usable`/`has_gap`/`bars_present==bars_expected`/`close_price`),
    only that timeframe's `reference_extrema` becomes `None` — the whole
    snapshot never fails for legitimately missing/ungated reference data.
    Implements §7.0a's per-bucket `HTF_high`/`HTF_low`
    (`derive_reference_extrema`) for `15m`/`1h` only, from the reference
    exchange's own exact constituent raw 1m bars — never a partial/gapped
    set; if the reference vector CLAIMS full/usable coverage but the raw
    bar set is actually incomplete or misaligned, this is treated as
    internally INCONSISTENT reader output and raises
    `V2AlignedInputError`, never silently downgraded to "unavailable" —
    missingness and corruption are deliberately never conflated. Enforces
    the load-bearing rule that each timeframe's health-at-cutoff read uses
    THAT bucket's own `bucket_end` as the cutoff, never the global decision
    boundary `T`. No context/scoring/detector logic of any kind — no
    `normalized_evidence`, `compression_score`, regime, bias, OI
    confirmation, or setup-detector logic exists anywhere in this PR.
    `v2.enabled` stays `false`; `v2.rules_version` is unchanged
    (`v2-rules-v0.1.0`) — this PR implements already-frozen §7.0a/§11
    semantics, not a new or tuned V2-v0 parameter; no schema/config change.
  - **V2 still has no context, setup-detector, or episode/state-machine
    logic of any kind** — this stage has established which closed bucket
    timestamps are legal (PR 1), how to read exactly the Stage 2 data those
    timestamps identify (PR 2), and how to assemble those reads plus the
    canonical reference-exchange path into one immutable snapshot (PR 3) —
    not what to do with any of it.
- **Stage 4 — Context Engines: COMPLETE.** All three planned PRs are
  merged to `main`.
  - **PR 1 of ~3 — shared context evidence primitives: MERGED** (#36,
    "feat: add V2 context evidence primitives"). Includes both the
    initial implementation and a pre-merge hardening amendment (fixed
    head `48466b0`): a corruption-precedence fix (every PRESENT field a
    primitive reads is now validated for corruption BEFORE any
    missingness/tier-floor short-circuit, so e.g. a `NaN` value can no
    longer be masked by a coincidentally-low confidence tier), plus
    `find_consensus_percentile` row-type and timestamp domain-error
    hardening (a malformed percentile-row type or a naive/non-UTC
    timestamp now raises `V2ContextEvidenceError` instead of leaking a
    bare `TypeError`/`AttributeError`). Begins the first stage where V2
    starts INTERPRETING already-aligned market data, but implements ONLY
    the small, reusable mathematical vocabulary the future 4h regime
    engine and 1h bias engine both need — no classification of either
    yet. Adds `analytics/forecasting_v2/context_evidence.py`:
    `find_consensus_percentile()` (exact `(metric, percentile_window)`
    lookup over one `V2TimeframeInputs`' already-aligned percentile rows,
    no cross-window fallback); `normalized_evidence()` (§4.1's corrected
    signed-evidence primitive — the raw metric's own sign chooses the
    evidence's sign, percentile rank chooses magnitude/extremity within
    that sign ONLY, so a positive raw value can never produce bearish
    evidence and a negative raw value can never produce bullish
    evidence); `compression_score()` (§4.1's unsigned companion,
    `1.0 - percentile_rank` of `range_width_pct_median`, no signed math);
    `oi_confirmation()` (§4.2's corrected OI confirmation/opposition
    primitive — a one-sided tail distance relative to `oi_raw`'s own
    sign, never `abs(oi_rank - 0.5)`; OI never selects LONG/SHORT, it only
    confirms or opposes whichever anchor direction is established
    elsewhere; its public signature accepts no `direction`/`regime`/`bias`
    parameter). `MIN_PCTL_TIER = "building"` (frozen V2-v0 parameter,
    reusing `analytics.percentile_engine.models.CONFIDENCE_TIERS`'
    canonical ordering rather than a second one). Missing/UNAVAILABLE is
    always `None`, never `0.0`; malformed/impossible data (an unknown
    confidence tier, a non-finite or out-of-range numeric value, a
    duplicate exact percentile row, a lookahead-violating
    `sample_window_end`) raises `V2ContextEvidenceError`. Pure module —
    no DB, no network, no clock, no config loading; consumes only the
    already-immutable Stage 3 `V2TimeframeInputs`. No 4h regime, no 1h
    bias, no `REGIME_*`/`BIAS_*` threshold, no
    `directional_context_gate`, no setup-detector logic of any kind
    exists anywhere in this PR — those are Stage 4 PR 2/~3, PR 3/~3, and
    Stage 5 respectively. `v2.enabled` stays `false`; `v2.rules_version`
    is unchanged (`v2-rules-v0.1.0`) — this PR implements already-frozen
    §4.1/§4.2 formulas, not a new or tuned V2-v0 parameter; no
    schema/config change.
  - **PR 2 of ~3 — 4h regime engine: MERGED** (#37,
    "feat: add V2 4h regime engine"). Includes both the initial
    implementation and a pre-merge hardening amendment (fixed head
    `510c492`): the exact §4.2/§23.1 `price_evi >= 0.40`/`oi_confirmation
    <= -0.40` boundaries are compared through a narrow, IEEE-754
    ULP-derived inclusive comparison (`_ge_inclusive`/`_le_inclusive`,
    `math.nextafter`-based) rather than a plain `>=`/`<=`, because those
    values are OUTPUTS of `normalized_evidence`'s affine transform/
    `oi_confirmation`'s product, not literals — e.g. the frozen bullish
    boundary `percentile_rank=0.70` computes `2.0*0.70-1.0 ==
    0.3999999999999999` in real Python arithmetic, a few ULPs below the
    `0.40` literal, which a plain comparison incorrectly rejected (the
    mirrored bearish boundary at `p=0.30` happens to round-trip exactly,
    which is why the asymmetry was easy to miss); this is numeric-
    representation hardening only, never a model/product tolerance — no
    public threshold value changed, nothing became configurable, no
    `rules_version` bump. The amendment also hardened `V2RegimeResult.
    __post_init__` to fail closed on a hand-constructed `bucket_ts` that
    is naive, non-UTC, or not a whole minute. Answers exactly one
    question with PR 1's shared evidence primitives — §4.2's own framing
    — "what is the established 4h market regime?" Adds
    `analytics/forecasting_v2/regime_4h.py`:
    `classify_4h_regime(inputs: V2TimeframeInputs) -> V2RegimeResult`,
    deterministically classifying one already-aligned 4h bucket into
    exactly one of `BULLISH_TRENDING`/`BEARISH_TRENDING`/
    `NON_DIRECTIONAL` (carrying an `is_compressed: bool` flag)/
    `INSUFFICIENT_DATA`, per §4.2's frozen decision tree and its six
    exact V2-v0 thresholds (`REGIME_MIN_CONFIDENCE=50.0`,
    `REGIME_MIN_COVERAGE=2/3`, `REGIME_TREND_THRESHOLD=0.40`,
    `REGIME_MIN_AGREEMENT=2/3`, `REGIME_OI_VETO=-0.40`,
    `REGIME_COMPRESSION=0.75`). Direction is decided by `price_evi`'s own
    sign ALONE; cross-exchange `price_direction_agreement` is a GATE only
    (it can never itself create direction); `oi_confirmation` is an
    OPTIONAL, symmetric VETO only, evaluated ONLY once a price+agreement
    candidate already exists — rising OI can never veto, falling OI vetoes
    either candidate direction symmetrically, and an unavailable OI
    reading does not by itself force `INSUFFICIENT_DATA`. Carefully
    preserves §4.2's "missing DATA (not merely tier)" distinction: a
    genuinely-missing exact price/compression percentile row (or a
    `None` `value`/`percentile_rank`) forces `INSUFFICIENT_DATA`, but a
    fully-PRESENT row whose `confidence_tier` merely sits below
    `MIN_PCTL_TIER` is a *different*, non-`INSUFFICIENT_DATA` case (falls
    through to `NON_DIRECTIONAL`) — re-derived independently via PR 1's
    own `find_consensus_percentile()`, never conflated with
    `normalized_evidence()`/`compression_score()`'s collapsed `None`.
    `consensus_confidence`/`min_coverage_ratio` are mandatory step-1 hard
    gates (missing or below floor -> `INSUFFICIENT_DATA`);
    `price_direction_agreement` is not (missing simply means the trend
    condition cannot be established -> `NON_DIRECTIONAL`, assuming step 1
    otherwise passes). Every PRESENT consensus field this engine reads is
    validated for corruption BEFORE any missingness/threshold
    short-circuit can hide it (mirroring PR 1's own corruption-precedence
    posture); a `V2ContextEvidenceError` from a PR 1 primitive is
    re-raised as `V2RegimeError`, exception-chained, never silently
    downgraded to `INSUFFICIENT_DATA`. Pure module — no DB, no network,
    no clock, no config loading, no `T`/reader/wall-clock parameter;
    consumes only the already-immutable Stage 3 `V2TimeframeInputs` and
    PR 1's public evidence primitives. No 1h bias, no combined context
    snapshot, no setup-detector, no `directional_context_gate`, no
    episode/state-machine/runtime logic of any kind exists anywhere in
    this PR — those are Stage 4 PR 3/~3 and Stage 5. `v2.enabled` stays
    `false`; `v2.rules_version` is unchanged (`v2-rules-v0.1.0`) — this
    PR implements already-frozen §4.2 formulas/thresholds, not a new or
    tuned V2-v0 parameter; no schema/config change.
  - **PR 3 of ~3 — 1h bias engine + final combined context snapshot:
    MERGED** (#38, "feat: complete V2 context engines"), the **final
    planned PR** of the Context Engines stage. Includes both the initial
    implementation and a pre-merge hardening amendment (fixed head
    `97d69dd`): a package-docstring status-truth fix (the docstring
    briefly claimed Stage 4 was already complete while #38 was still
    open — corrected to defer to this document's own merge-state truth),
    and a builder-level source-identity hardening gap fix —
    `build_v2_context_snapshot()` now calls a private
    `_validate_context_input_identity()` for `"4h"`/`"1h"` BEFORE
    classification, tying each `V2TimeframeInputs`' `bucket_ts` and any
    PRESENT `consensus`/`percentiles` row's `symbol`/`market_type`/
    `timeframe`/`bucket_ts`/`calculation_version`/`feature_schema_version`
    back to `aligned`'s own top-level identity — closing a gap where a
    hand-constructed `V2AlignedInputs` (never `load_v2_aligned_inputs()`
    itself, which already guarantees this by construction) could
    silently mislabel evidence from one logical identity (e.g. a
    different symbol) under another's top-level identity. `None`
    consensus and empty `percentiles` remain legitimate missingness, not
    corruption. Adds
    `analytics/forecasting_v2/bias_1h.py`:
    `classify_1h_bias(inputs: V2TimeframeInputs) -> V2BiasResult`,
    deterministically classifying one already-aligned 1h bucket into
    exactly one of `BULLISH`/`BEARISH`/`NEUTRAL_NOT_ESTABLISHED`/
    `"UNAVAILABLE"`, per §4.3's frozen decision tree and its four exact
    V2-v0 thresholds (`BIAS_MIN_CONFIDENCE=50.0`, `BIAS_MIN_COVERAGE=2/3`,
    `BIAS_THRESHOLD=0.25`, `BIAS_MIN_AGREEMENT=2/3`) — a deliberately
    lighter, faster-adapting sibling of the 4h regime (7d window vs.
    30d, a looser `0.25` threshold vs. `0.40`), reusing PR 1's
    `normalized_evidence()` and **nothing else** from PR 1: no
    `oi_confirmation`/`oi_change_pct_median`/`oi_direction_agreement`, no
    `compression_score`/`range_width_pct_median` — §4.4's independence/
    anti-double-counting boundary assigns OI/compression to the 4h regime
    exclusively. Direction is decided by `bias_evi`'s own sign ALONE;
    `price_direction_agreement` is a GATE only. Unlike the 4h regime's
    "missing DATA vs. tier-only UNAVAILABLE" distinction, §4.3 is
    unconditional — every cause `normalized_evidence()` collapses into
    `None` yields `bias = "UNAVAILABLE"` here, with no special-casing.
    `NEUTRAL_NOT_ESTABLISHED` is a real, successfully-computed result
    (usable-but-below-threshold evidence, a genuinely flat raw price, or
    weak/missing agreement) kept strictly distinct from `"UNAVAILABLE"`
    (the computation could not run at all) — Stage 5's `directional_
    context_gate` (§7.0b) will rely on this exact distinction. Verified
    directly that `BIAS_THRESHOLD=0.25`'s own exact percentile boundaries
    (`p=0.625` for `+0.25`, `p=0.375` for `-0.25`) land bit-exact through
    `normalized_evidence`'s arithmetic on both signed branches, so no ULP
    tolerance (unlike PR 2's `0.40`/`-0.40`) was needed or added here.
    Every PRESENT consensus field this engine reads is validated for
    corruption BEFORE any unavailable/threshold short-circuit can hide it
    (mirroring PR 1/PR 2's corruption-precedence posture); a
    `V2ContextEvidenceError` from `normalized_evidence()` is re-raised as
    `V2BiasError`, exception-chained. Also adds
    `analytics/forecasting_v2/context_snapshot.py`:
    `build_v2_context_snapshot(aligned: V2AlignedInputs) -> V2ContextSnapshot`,
    the ONE canonical way to combine an already-aligned Stage 3 snapshot's
    already-computed 4h regime and 1h bias into one immutable
    `V2ContextSnapshot` (`T`, `symbol`, `market_type`,
    `calculation_version`, `feature_schema_version`, `regime_4h`,
    `bias_1h`) — deliberately accepting exactly ONE `V2AlignedInputs`
    (never two independent `regime_inputs`/`bias_inputs` objects), since
    Stage 3's entire purpose is that every timeframe is selected from ONE
    explicit decision boundary `T`; a `regime_inputs`/`bias_inputs`-shaped
    API could let a caller accidentally pair contexts computed from two
    different `T`s. `V2ContextSnapshot.__post_init__` fails closed against
    exactly that: it re-validates `T` as a legal V2 decision boundary via
    `selected_bucket("5m", T)`, then requires `regime_4h.bucket_ts ==
    selected_bucket("4h", T)` and `bias_1h.bucket_ts == selected_bucket
    ("1h", T)` exactly — whether the snapshot is built through
    `build_v2_context_snapshot` or hand-constructed directly. A
    legitimately-computed `INSUFFICIENT_DATA` 4h regime or
    `"UNAVAILABLE"` 1h bias is a VALID context result, not a failure — the
    snapshot is still built and returned; `V2ContextSnapshotError` is
    reserved for malformed containers, an impossible mixed-boundary
    pairing, and wrapped classifier errors. `V2ContextSnapshot` carries NO
    overall/combined direction field (`overall_direction`/
    `trade_direction`/`setup_allowed`/`trade_allowed`/a compatibility
    score) — §4.4 keeps regime and bias deliberately independent so
    different Stage 5 detector families can consume them differently;
    collapsing them here would destroy information Stage 5 needs. Only
    `aligned.by_timeframe["4h"]`/`["1h"]` are ever read — `5m`/`15m` are
    never inspected for a Stage 4 context decision. Both new modules are
    pure — no DB, no network, no clock, no config loading, no `T`/reader/
    wall-clock parameter beyond what `aligned.T` already fixes. No
    `directional_context_gate` (§7.0b), no setup-detector
    (`TREND_PULLBACK`/`COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT`), no
    episode/state-machine/runtime logic of any kind exists anywhere in
    this PR — those are Stage 5. `v2.enabled` stays `false`;
    `v2.rules_version` is unchanged (`v2-rules-v0.1.0`) — this PR
    implements already-frozen §4.3 formulas/thresholds, not a new or
    tuned V2-v0 parameter; no schema/config change.
- **Stage 5 — Setup Detectors: COMPLETE.**
  - **PR 1 of ~4 — shared detector foundation: MERGED** (#39, "feat:
    add V2 setup detector foundation"). Includes both the initial
    implementation and a pre-merge hardening amendment (fixed head
    `3d2cde1`): a shared `_require_row_fields()` returned-row shape
    validator wired into all four `storage/v2_setup_readers.py` readers
    (a broken/fake connection returning `{}`/a partial row/a non-Mapping
    value now raises `V2SetupReaderError` instead of leaking a bare
    `KeyError`/`AttributeError`/`TypeError`; a present key that is
    legitimately SQL `NULL` remains unaffected), a `range_proxy_pct()`
    bucket-grid alignment check (`bucket_ts` must now be aligned to
    `timeframe`'s own canonical UTC grid, reusing `alignment.py`'s
    `selected_bucket()` round-trip rather than a new grid convention),
    top-level `rows`/`candidates` container hardening (`None`/`str`/
    `bytes` now raise `V2SetupFoundationError` instead of an incidental
    Python iteration error), and `V2ExtremeAnchor.__post_init__`
    self-validation (naive/non-UTC/non-whole-minute `bucket_ts` and
    non-finite/`bool` `value` now rejected on direct construction).
    Implements ONLY the
    detector-independent shared math/context-compatibility/historical-
    read infrastructure all three Stage 5 families need — ZERO actual
    setup detection. Adds `analytics/forecasting_v2/setup_common.py`:
    `directional_context_gate(context: V2ContextSnapshot,
    breakout_direction: str) -> V2DirectionalContextDecision` — §7.0b's
    frozen decision tree (4h availability, 4h opposition, 1h
    availability, 1h opposition, otherwise ACCEPT, evaluated in that
    exact order), preserving all FOUR distinct rejection categories
    (`REJECT_REGIME_UNAVAILABLE`/`REJECT_REGIME_OPPOSES`/
    `REJECT_BIAS_UNAVAILABLE`/`REJECT_BIAS_OPPOSES`) rather than
    collapsing them into an opaque `bool`; consumed by
    `COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT` only — never
    `TREND_PULLBACK`, whose own stricter "4h trending AND 1h same
    direction" precondition makes this gate redundant there.
    `range_proxy_pct(rows, *, timeframe, bucket_ts) -> Optional[float]`
    — §7's `RANGE_PROXY_pct(timeframe, N=14, B)` rolling-mean volatility
    proxy, restricted to exactly `SETUP_RANGE_TIMEFRAMES = ("15m",
    "1h")` (the only timeframes the frozen detectors use), `N=14`
    hard-coded (not caller-tunable, since §23 freezes its V2-v0 value as
    a versioned parameter); returns `None` for an incomplete exact-14
    window or a present-but-missing metric value, never a partial mean;
    every PRESENT row is validated for corruption BEFORE the
    completeness check (mirroring PR #36-#38's precedence posture).
    `protection_buffer(*, reference_price, range_proxy_pct_value,
    tick_size) -> Optional[float]` — §7's `max(MIN_TICK_BUFFER_TICKS=3 *
    tick_size, reference_price * range_proxy_pct_value / 100 *
    BUFFER_MULTIPLIER=0.5)`, a pure function of an already-computed
    `range_proxy_pct` value (no I/O, no timeframe/window concept of its
    own); returns `None` only because the volatility input itself is
    unavailable, after `reference_price`/`tick_size` are already
    confirmed valid. `select_extreme_anchor(candidates, *, mode) ->
    Optional[V2ExtremeAnchor]` — §7.0c's deterministic most-recent-tie
    rule for identity-bearing lookback extrema (compares full stored
    precision, no rounding; input order never affects the result), for
    `TREND_PULLBACK`'s `trend_leg_extreme`/`CONFIRMED_BREAKOUT`'s
    `resistance_level`/`support_level` — never `COMPRESSION_BREAKOUT`'s
    plain-numeric `range_high`/`range_low`, which §7.0c explicitly
    excludes. Also adds `storage/v2_setup_readers.py`:
    `read_v2_consensus_feature_window`/`read_v2_consensus_percentile_
    window`/`read_v2_reference_feature_window` (deterministic historical
    rows over a caller-supplied INCLUSIVE `[bucket_start, bucket_end]`
    bucket-START interval — missing buckets are preserved as absence,
    never fabricated) and `read_v2_instrument` (a single-row, read-only
    `exchange_instruments` lookup grounding `protection_buffer`'s
    `tick_size` input directly in the existing schema, reusing
    `storage/stage2_readers.py::INSTRUMENT_SQL`'s column set as its own
    standalone read rather than a second pseudo-schema). Raw `klines_1m`
    history reuses Stage 3's existing `read_v2_reference_klines`
    UNCHANGED — no second raw-kline window API. A NEW, separate
    `V2SetupHistoryReader` `Protocol` (`ports.py`) names this read
    surface; `V2AlignedInputReader` is UNCHANGED (no inheritance between
    the two Protocols). `storage.db.Database` gains matching
    `fetch_v2_consensus_feature_window`/`fetch_v2_consensus_percentile_
    window`/`fetch_v2_reference_feature_window`/`fetch_v2_instrument`
    wrappers, validating BEFORE `pool.acquire()` (same defense-in-depth
    posture as the Stage 3 wrappers). No `TREND_PULLBACK`/
    `COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT` detection logic, no
    `EARLY_SIGNAL`/`CONFIRMED` transition, no entry zone, no per-episode
    invalidation price, no `structural_anchor`/episode-identity
    construction, no episode lifecycle/state machine, no confidence
    scoring, no entry feasibility, no runtime wiring exists anywhere in
    this PR. `v2.enabled` stays `false`; `v2.rules_version` is unchanged
    (`v2-rules-v0.1.0`) — this PR implements already-frozen §7/§7.0b/
    §7.0c formulas/thresholds, not new or tuned V2-v0 parameters; no
    schema/config change.
  - **PR 2 of ~4 — `TREND_PULLBACK`: MERGED** (#40, "feat: add V2 trend
    pullback detector"), the FIRST actual V2 setup detector. Adds
    `analytics/forecasting_v2/trend_pullback.py`: `detect_trend_pullback(
    inputs: V2TrendPullbackInputs) -> Optional[V2TrendPullbackCandidate]`
    — §7.1's frozen STRICT precondition, deliberately NOT §7.0b's
    `directional_context_gate` (never imported here): candidate `LONG`
    iff 4h regime `== BULLISH_TRENDING` AND 1h bias `== BULLISH`;
    candidate `SHORT` iff 4h regime `== BEARISH_TRENDING` AND 1h bias
    `== BEARISH`; every other combination (`NON_DIRECTIONAL`,
    `INSUFFICIENT_DATA`, `NEUTRAL_NOT_ESTABLISHED`, `UNAVAILABLE`, or an
    opposite-direction regime/bias) never qualifies. Evaluated ONLY on
    legal 15m formation boundaries (`B15 = selected_bucket(15m, T)`,
    valid iff `B15 + 15m == T` — `T=12:15` qualifies, `T=12:20`/`T=12:25`
    do not, never floored) — this is what stops the same closed 15m
    structure from being independently "detected" three times as `T`
    walks forward on the 5m grid. Requires the EXACT `LOOKBACK_15M=48`-
    bucket reference-close window (canonical `V2_REFERENCE_EXCHANGE`
    only, §11's exact usability gate reused unchanged, no partial window,
    no failover); `trend_leg_extreme` is `max`/`min` `close_price` over
    that window, tie-broken per §7.0c via PR 1's own `select_extreme_
    anchor()` (most-recent tie wins — reused, never re-implemented).
    `retracement_pct` uses the exact §7.1 formulas and must fall within
    the INCLUSIVE `[PULLBACK_MIN_MULT=0.5, PULLBACK_MAX_MULT=3.0] *
    RANGE_PROXY_pct(15m,14,B15)` band (PR 1's `range_proxy_pct()` reused
    unchanged for both the exact-14-bucket math and the bucket-grid
    validation). `pullback_extreme` (the deepest close reached DURING the
    retracement) is derived ONLY from the contiguous span from `trend_
    leg_extreme`'s own anchor bucket THROUGH `B15` inclusive — buckets
    strictly older than the anchor never participate, even though they
    contributed to selecting the anchor itself. `protection_buffer()`
    (PR 1, reused unchanged) and `invalidation_price = pullback_extreme
    -/+ protection_buffer` (LONG/SHORT) are STRUCTURAL FACTS computed at
    `T`, never a live invalidation check. The `EARLY_SIGNAL`-time entry
    zone uses ONLY already-known `T`-time data (`current_close =
    close_price(B15)`) — never a future `confirmation_close_price`.
    Verified bit-for-bit against the exact §29.6 worked LONG vector
    (`trend_leg_extreme=65,000`, `current_close=64,350`,
    `retracement_pct=1.0%`, `proxy=0.4%`, `pullback_extreme=64,300`,
    `protection_buffer≈128.7`, `invalidation_price≈64,171.3`,
    `zone=[64,300,64,350]`) and a symmetric SHORT vector, proving LONG/
    SHORT formula symmetry directly. Also adds `analytics/forecasting_v2/
    trend_pullback_inputs.py`: `load_trend_pullback_inputs(reader:
    V2SetupHistoryReader, *, context: V2ContextSnapshot) ->
    Optional[V2TrendPullbackInputs]`, a narrow async assembler mirroring
    Stage 3's own pure-detector/async-assembler module split — returns
    `None` WITHOUT any storage read for a non-15m-formation `T`;
    otherwise issues exactly the three reads this detector needs (the
    48-bucket reference window, the 14-bucket consensus window, the
    single instrument row) and ZERO percentile-window/raw-kline/5m/1h/4h/
    health/OI/funding/liquidation reads — the already-computed `context`
    already supplies the 4h/1h facts. **Deliberately implements ONLY the
    qualification question, never episode/lifecycle logic (load-bearing
    Stage 5/6 boundary):** a stateless detector cannot know whether a
    qualification is a brand-new episode's `T_detect` or a
    pre-confirmation re-evaluation of an already-active `EARLY_SIGNAL`,
    so this PR never constructs `episode_id`/`event_id`, never
    transitions `EARLY_SIGNAL`/`CONFIRMED`/`WEAKENING`/`INVALIDATED`/
    `EXPIRED`/`COMPLETED`, never evaluates the §7.1 5m resumption/
    confirmation trigger (only meaningful relative to an already-existing
    episode's own `T_detect`), never counts candidate age against
    `PULLBACK_MAX_AGE_15M_BUCKETS` (exposed only as frozen family
    metadata alongside `RESUMPTION_MIN_BUCKETS`/`EXPECTED_HORIZON=2h`),
    and never computes `model_confidence` (§8) — all Stage 6 (Episode
    State Machine). No `COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT`, no
    runtime wiring, no schema/config change anywhere in this PR.
    `v2.enabled` stays `false`; `v2.rules_version` is unchanged
    (`v2-rules-v0.1.0`) — this PR implements already-frozen §7.1/§7.0c
    formulas/thresholds, not new or tuned V2-v0 parameters.
  - **PR 3 of ~4 — `COMPRESSION_BREAKOUT`: MERGED** (#41, "feat: add V2
    compression breakout detector"). Adds `analytics/forecasting_v2/
    compression_breakout.py`: `detect_compression_breakout(inputs:
    V2CompressionBreakoutInputs) -> Optional[V2CompressionBreakoutCandidate]`
    — §7.2's compression-precondition + fresh-breakout qualification.
    **Decision clock differs from `TREND_PULLBACK` (load-bearing):**
    evaluated at EVERY legal 5m V2 decision boundary `T` (`B5 =
    selected_bucket(5m, T)`, `B15 = selected_bucket(15m, T)`), NOT
    restricted to 15m formation boundaries — the breakout trigger is a
    5m-close event. For each of the EXACT `COMPRESSION_LOOKBACK=16`
    expected 15m buckets ending at `B15`, a bucket counts as compressed
    iff its OWN 15m consensus row passes the same frozen §6.2/§6.3
    quality gate (`min_coverage_ratio>=2/3`, `consensus_confidence>=50`)
    AND `context_evidence.compression_score(15m, "30d", b)` (PR 1 of
    Stage 4's own primitive, reused unchanged — never a private
    `1.0 - percentile_rank` reimplementation) is available and
    `>= COMPRESSION_THRESHOLD=0.75` (boundary-inclusive). This PR owns an
    EXTRA identity pre-validation layer over every PRESENT percentile row
    (`scope`/`exchange`/`symbol`/`market_type`/`metric`/`timeframe`/
    `percentile_window`/`calculation_version`/`feature_schema_version`/
    `bucket_ts`) that `find_consensus_percentile()` alone does not check,
    since a bare `V2TimeframeInputs` carries no `symbol`/`market_type`.
    The 16 chronological buckets are partitioned into MAXIMAL consecutive
    compressed runs; a run qualifies iff its length
    `>= COMPRESSION_MIN_DURATION=6` (full run length used, never
    truncated to the most recent 6); among all qualifying runs, the one
    with the MOST RECENT end bucket is deterministically selected — `B15`
    itself need not be part of, or adjacent to, the selected run. The
    selected run's structural `range_high = max(HTF_high)`/
    `range_low = min(HTF_low)` are derived via `aligned_inputs.derive_
    reference_extrema()` (§7.0a, reused unchanged) over ONLY that run's
    own buckets — an enormous high/low from an UNSELECTED older run never
    leaks in; any selected-run bucket's extrema being unavailable makes
    the whole range unavailable, fail-closed. The fresh 5m-crossing check
    uses the current AND immediately-previous closed Binance 5m reference
    closes (`LONG: previous<=range_high AND current>range_high`; `SHORT:
    previous>=range_low AND current<range_low`) — distinguishes a NEW
    cross from merely remaining outside an already-broken level; a
    non-fresh outside-range condition never repeatedly re-qualifies every
    5m tick. Once a fresh direction is derived, the current `B5` 5m
    trigger row must independently pass the same §6.2/§6.3 quality gate,
    `price_direction_agreement >= BREAKOUT_MIN_AGREEMENT=2/3` (a quality
    gate only — direction is NEVER derived from agreement), and
    `taker_delta_notional_usd_sum` matching sign (`>0` LONG, `<0` SHORT,
    zero matches neither), plus the shared §7.0b `directional_context_
    gate()` (PR 1, reused unchanged — deliberately NOT `TREND_PULLBACK`'s
    own stricter precondition) returning `accepted is True`.
    `protection_buffer()` (PR 1, reused unchanged) uses the canonical
    Binance 15m `close_price` AT `B15` as its reference price — never the
    5m breakout close itself (§7 scopes the buffer to `timeframe=15m`).
    Entry zone/`invalidation_price` are STRUCTURAL FACTS
    (`LONG: entry=[range_high,range_high+buffer],
    invalidation=range_low-buffer`; `SHORT: entry=[range_low-buffer,
    range_low], invalidation=range_high+buffer`) computed once at `T`,
    never a live false-break/HOLD/CONFIRMED check. Verified against a
    worked SHORT vector matching §29.6's structural setup (16-bucket
    lookback, selected run `b[9..15]` length 7, `range_low=63,800`,
    `range_high=64,100`, fresh SHORT cross `63,820 -> 63,740`) and a
    symmetric LONG vector, proving formula symmetry directly — **note:**
    §29.6's own prose illustration for the resulting `invalidation_price`
    (`≈63,930`, apparently derived from `range_low + buffer`) did not
    match §7.2's own frozen SHORT formula (`invalidation_price =
    range_high + protection_buffer`); this PR implements the frozen
    formula exactly (`range_high=64,100` + `buffer≈96` ⇒
    `invalidation_price≈64,196`), per this document's own §0.2 grounding
    rule that the frozen formula wins over an illustrative approximate
    number — flagged here when first found by PR41, and since corrected
    directly in §29.6 by the pre-Stage-6 contract audit (#43 amendment 3).
    Also adds
    `analytics/forecasting_v2/compression_breakout_inputs.py`:
    `load_compression_breakout_inputs(reader: V2SetupHistoryReader, *,
    context: V2ContextSnapshot) -> V2CompressionBreakoutInputs` — UNLIKE
    `trend_pullback_inputs.py`, there is no formation-boundary skip (every
    5m boundary is a possible breakout instant), so this loader always
    issues its full read set: exactly 7 reads (the 16-bucket 15m
    consensus window, the matching 16-bucket percentile window, the
    matching 16-bucket reference-feature window, ONE raw-1m-kline window
    covering the whole lookback, the two closed 5m reference buckets, the
    current 5m consensus trigger row, and the instrument row) — zero
    percentile/kline/OI/funding/liquidation/health reads beyond that, and
    no second 14-row `RANGE_PROXY` query (reuses the 16-bucket consensus
    window's own final 14 rows). **Deliberately implements ONLY the
    qualification question, never episode/lifecycle logic (same Stage 5/6
    boundary as PR 2):** never constructs `episode_id`/`event_id`, never
    transitions `EARLY_SIGNAL`/`CONFIRMED`/`WEAKENING`/`INVALIDATED`/
    `EXPIRED`/`COMPLETED`, never evaluates the direction-aware false-break
    rule or the boundary-equality HOLD convention (§7.2), never counts
    candidate age against `COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS`
    (exposed only as frozen family metadata alongside
    `EXPECTED_HORIZON=90m`, exported at package level as
    `COMPRESSION_BREAKOUT_EXPECTED_HORIZON` to avoid colliding with
    `TREND_PULLBACK`'s already-exported package-level `EXPECTED_HORIZON`),
    and never applies §7.4 family precedence against `CONFIRMED_BREAKOUT`/
    `TREND_PULLBACK` — all Stage 6 (Episode State Machine) or later. No
    runtime wiring, no schema/config change anywhere in this PR.
    `v2.enabled` stays `false`; `v2.rules_version` is unchanged
    (`v2-rules-v0.1.0`) — this PR implements already-frozen §7.2/§7.0a/
    §7.0b formulas/thresholds, not new or tuned V2-v0 parameters.
  - **PR 4 of ~4 — `CONFIRMED_BREAKOUT` + Stage 5 completion: MERGED**
    (#42, "feat: add V2 confirmed breakout detector"), the FINAL planned
    Stage 5 detector PR. Adds `analytics/forecasting_v2/
    confirmed_breakout.py`: `detect_confirmed_breakout(inputs:
    V2ConfirmedBreakoutInputs) -> Optional[V2ConfirmedBreakoutCandidate]`
    — §7.3's structural-level-break qualification. Evaluated at EVERY
    legal 5m V2 decision boundary `T` (`B5 = selected_bucket(5m, T)`,
    `B1h = selected_bucket(1h, T)`), no 1h-boundary restriction — a
    physically natural instant is `T=13:05` (`B1h=[12:00,13:00)` already
    closed, `B5=[13:00,13:05)` the newly closed 5m bucket that may break
    it). The structural level uses the EXACT `LEVEL_LOOKBACK=48`-bucket
    1h grid ending at `B1h`: `resistance_level = max(HTF_high(1h, b))`,
    `support_level = min(HTF_low(1h, b))` over ALL 48 buckets, via
    `aligned_inputs.derive_reference_extrema()` (§7.0a, reused
    unchanged, from raw Binance `klines_1m` — never `close_price`/
    consensus/current-5m-price). ANY one of the 48 buckets being
    unavailable makes the WHOLE level unavailable — intentionally
    stricter than `COMPRESSION_BREAKOUT`'s selected-run subset, since
    there is no "selected run" concept for this family: every bucket
    structurally contributes. The tie-broken anchor bucket (§7.0c) uses
    the real `setup_common.select_extreme_anchor()` for both
    `mode="max"` (resistance) and `mode="min"` (support) — never a
    private tie-break; a latest-bucket-wins tie test proves input order
    never influences the result. The fresh 5m-crossing check
    (`LONG: previous<=resistance AND current>resistance`;
    `SHORT: previous>=support AND current<support`) uses the current and
    immediately-previous closed Binance 5m reference closes, the same
    clean interpretation `COMPRESSION_BREAKOUT` established.
    **`CONFIRMED_BREAKOUT` is deliberately NOT `COMPRESSION_BREAKOUT`
    without compression (load-bearing, §7.3, do not cargo-cult #41):**
    no preceding-compression precondition, a 1h (not 15m) structural
    lookback, a 40-minute (not 15-minute) confirmation window (metadata
    only — never evaluated by this Stage 5 PR), and critically **no
    taker-flow confirmation requirement and no invented
    `price_direction_agreement >= 2/3` EARLY_SIGNAL gate** — §7.3
    freezes exactly two EARLY_SIGNAL requirements: the fresh
    reference-exchange 5m crossing, and
    `directional_context_gate(candidate_direction, context) == ACCEPT`
    (§7.0b, reused unchanged). `V2ConfirmedBreakoutCandidate` therefore
    carries NO `price_direction_agreement`/`taker_delta_notional_usd_sum`
    fields at all, and the detector reads no current-B5 5m consensus row
    of any kind. `protection_buffer()`/entry-zone/`invalidation_price`
    are structural facts computed once, using the canonical Binance 1h
    `close_price` AT `B1h` (never the 5m breakout close) and a SEPARATE,
    smaller 14-bucket 1h consensus window for `RANGE_PROXY_pct(1h,14,
    B1h)` and the current-B1h §6.2/§6.3 quality gate — distinct from the
    48-bucket structural window, which carries no consensus rows at all.
    The structural anchor (`level_anchor_bucket`/`level_price`, exposed
    at full stored precision) is the RAW Stage 5 fact only — §12's
    actual `episode_logical_key` (tick-normalized price) remains Stage
    6's job; this PR invents no rounding algorithm. Also adds
    `analytics/forecasting_v2/confirmed_breakout_inputs.py`:
    `load_confirmed_breakout_inputs(reader: V2SetupHistoryReader, *,
    context: V2ContextSnapshot) -> V2ConfirmedBreakoutInputs` — like
    `COMPRESSION_BREAKOUT`'s loader, no formation-boundary skip (every
    5m boundary is a possible breakout instant), issuing exactly 5 reads
    (14-bucket 1h consensus window, 48-bucket 1h reference-feature
    window, one raw-1m-kline window covering the 48h lookback, the two
    closed 5m reference buckets, the instrument row) — deliberately NO
    current-B5 5m consensus read (load-bearing difference from #41's
    seven-read loader, since this family has no taker-flow/agreement
    gate to feed), no percentile read, no 15m/4h historical window.
    **Deliberately implements ONLY the qualification question**,
    exactly like `TREND_PULLBACK`/`COMPRESSION_BREAKOUT`: never
    constructs `episode_id`/`event_id`/`episode_logical_key`, never
    transitions `EARLY_SIGNAL`/`CONFIRMED`/`WEAKENING`/`INVALIDATED`/
    `EXPIRED`/`COMPLETED`, never evaluates the direction-aware
    false-break rule or the boundary-equality HOLD convention, never
    counts candidate age against
    `CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS=8` (exposed only
    as frozen family metadata alongside `EXPECTED_HORIZON=2.5h`, exported
    at package level as `CONFIRMED_BREAKOUT_EXPECTED_HORIZON` to avoid
    colliding with `TREND_PULLBACK`'s and `COMPRESSION_BREAKOUT`'s own
    already-exported package-level `EXPECTED_HORIZON` names), and never
    applies §7.4 family precedence against `COMPRESSION_BREAKOUT`/
    `TREND_PULLBACK` — all Stage 6 (Episode State Machine) or later. No
    runtime wiring, no schema/config change anywhere in this PR.
    `v2.enabled` stays `false`; `v2.rules_version` is unchanged
    (`v2-rules-v0.1.0`) — this PR implements already-frozen §7.3/§7.0a/
    §7.0b/§7.0c formulas/thresholds, not new or tuned V2-v0 parameters.
  - This PR-count split is an IMPLEMENTATION/reviewability plan, not a
    new correctness contract — the existing Product/Correctness
    contracts remain authoritative, and this split may be adjusted if
    reviewability or risk requires it.

**Stage 5's detector-implementation portion is COMPLETE — #39, #40, #41,
#42 are all MERGED.** All three frozen setup families (`TREND_PULLBACK`,
`COMPRESSION_BREAKOUT`, `CONFIRMED_BREAKOUT`) now have a deterministic
Stage 5 qualification implementation. This does NOT mean the V2 trading
product is complete — Stage 6 (Episode State Machine), which owns episode
identity/dedup, family precedence (§7.4), confirmation, false-break
transitions, expiry, weakening, and persistence orchestration, has NOT
started.

**Executable Stage 6 has NOT started.** `#43` — including its two
post-open amendment rounds and this clean-room pre-Stage-6 contract
consolidation and cross-stage audit — is documentation-only contract work
that precedes Stage 6, never Stage 6 implementation itself. The correct
status, corrected here after this audit found the prior "Stage 6: IN
PROGRESS" framing to be inaccurate:

- **Stage 6 — Episode State Machine: NOT STARTED.**
- **PRE-STAGE-6 HARDENING: IN PROGRESS.** `#43` is the contract-consolidation
  member of this phase; the audit below identified additional cross-stage
  correctness gaps between the currently-merged Stage 2–5 implementation
  and the frozen contracts that must be closed — in code, not just docs —
  before executable Stage 6 can safely consume Stage 2–5's boundaries.

**`#43` — contract consolidation and cross-stage audit (this PR, amended
three times post-open).** Round 1 froze creation identity vs.
later-observed anchor drift, exact non-material/material drift math per
family, `Decimal`/`ROUND_HALF_UP` tick normalization, "suppressed, not
queued," the exact terminal-cooldown clock, the `§7.4` structural-overlap
predicate, and deterministic family-precedence arbitration. Round 2 fixed
an invalid precedence worked vector (illegal `TREND_PULLBACK` cadence),
fully separated same-slot suppression from cooldown, froze
`creation_identity_tick_size` (`§12.5a`), froze `REVERSAL_CANDIDATE`
pairwise cardinality (`§13.3.1`), froze one same-boundary orchestration
order (`§13.4`), froze the `LIVE`/`REPLAY` execution-namespace scope
(`§12.10`), and separated identity-routing from persisted-event necessity
(`§12.11`). Round 3 (this audit) is a clean-room rebuild from the actual
merged Stage 2–5 implementation, independent of the prior two rounds'
conclusions — it found and fixed: a same-`T` terminal-transition/cooldown
contradiction introduced by round 2's own `§13.4` (`§13.4`'s "active set"
wording incorrectly implied cooldown consults the same view as same-slot
occupancy — corrected by splitting `surviving_active_set(T)` from
per-slot terminal/cooldown history); a genuine executable defect where
every currently-merged V2 quality gate reads the **global** worst-family
`min_coverage_ratio`/`consensus_confidence` rollup instead of the
metric-family(ies) a given decision actually consumes, contradicting the
already-frozen "OI availability is not required" invariant (`§6.3a`,
targeted for a future `v2-rules-v0.2.0` executable correction); an
ambiguous `COMPRESSION_BREAKOUT` `setup_strength` bucket, now frozen as
`compression_score` at `compression_end_bucket` (`§8`); the missing
freeze of exactly which bucket a `Decimal`-computed fact is persisted as
in `V2EpisodeEvent`'s JSON-only leaf model, and the missing freeze of
historical/as-of instrument-metadata reproducibility for replay (`§12.5a`);
an unexecutable `§13.2a` `WEAKENING` predicate (`price_direction_agreement`
is an unsigned magnitude — the predicate needed `price_move_pct_median`'s
sign too), now frozen exactly with `UNAVAILABLE`-pauses-the-streak
semantics; a wrong `COMPRESSION_BREAKOUT` SHORT worked-vector number
(`§29.6`, `range_low + buffer` used where the frozen formula is
`range_high + buffer` — already flagged but not yet fixed by `#41`'s own
roadmap entry, now corrected in `§29.6` directly); a `V2_PRODUCT_CONTRACT.md`
§4.3 timeframe-role claim ("`15m` forms the setup") that contradicted the
already-implemented, deliberately-15m-free `§7.3` `CONFIRMED_BREAKOUT`
design (corrected in the Product Contract); a `REVERSAL_CANDIDATE`
notification-materiality table entry mislabeled as a "state change" when
`§13.3` is explicit it is not; and confirmed `INVALIDATED_BEFORE_ENTRY` is
currently unreachable under V2-v0's frozen 90s-delay/5m-close-only
invalidation timing (marked reserved, its `§29.12` sample vector
corrected to `0` occurrences). `v2.enabled` stays `false`;
`v2.rules_version` remains `v2-rules-v0.1.0` for `#43` itself — the
metric-family quality-gate correction is real executable behavior change
and is explicitly targeted at a future `v2-rules-v0.2.0`, not bundled into
this docs-only PR.

**`#43` amendment round 4 (tech-lead corrective pass).** A live tech-lead
review of the round-3 clean-room audit found several of its own contract
resolutions were themselves wrong, and several findings marked
"implementation debt" were actually still-open contract ambiguity.
Corrected: the `WEAKENING` threshold (`price_direction_agreement > 0.5`
STRICT, not `>=` — a two-exchange 50/50 tie is not a majority) and its
consecutive-streak semantics (`UNAVAILABLE` RESETS the streak, it does
not merely pause it — `TRUE → UNAVAILABLE → TRUE` is not two consecutive
buckets); a wrong `TREND_PULLBACK` deadline worked vector (confirmation
is checked at every later 5m boundary within the 2h age window, not at
8 boundaries spaced 15m apart — 15m cadence governs only new-candidate
*formation*); §12.2a's generic "all operational facts frozen at
creation" rule, which contradicted `TREND_PULLBACK`'s own already-frozen
pre-confirmation `pullback_extreme` update mechanic (rewritten per
family: `TREND_PULLBACK` genuinely updates pre-confirmation,
`COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT` do not); `COMPRESSION_BREAKOUT`
`setup_strength`'s "`compression_end_bucket` always equals `B15`" claim,
which the contract's own already-frozen multi-run worked vector disproves
(`setup_strength` is now the mean `compression_score` over the full
selected run); the broader Stage 4→5/6 numerical-evidence handoff gap
(`§4.1a`, not just the compression fix); `§8`'s `data_confidence` source
(now exact per family, `COMPRESSION_BREAKOUT` using `min()` of its two
mandatory families); a mislabeled `§6.3a` family note
(`price_direction_agreement` is `price_structure`, not `taker_flow`); `G`
(analytical excursion) fully frozen with exact 1m-grid semantics and a
new `DATA_INCOMPLETE` vs. `HORIZON_NO_COMPLETION` `terminal_reason`
distinction (no new lifecycle state); `H`'s same-`T` event model
(option (a), at most one event per episode per decision boundary, is now
the ONLY conforming V2-v0 model — option (b) rejected) and semantic ID
dimensions (`execution_stream` explicitly excluded — physical row
namespace, never semantic identity); `I`'s transaction-retry explanation
(no partial row commits inside one atomic transaction); `J` and `P`
upgraded from unverified to CONFIRMED against live-traced code
(`insert_klines`'s unconditional `ON CONFLICT` overwrite; `aligned_inputs.py`'s
naive-datetime `TypeError` leak); `O`'s residual gap made concrete
(`TREND_PULLBACK`'s candidate lacks `COMPRESSION_BREAKOUT`-grade
exact-formula self-validation); `S`/`T`/`U` promoted from roadmap-only
debt to normative Correctness Contract requirements (`§3.2`–`§3.4`); a
`§3` LIVE/REPLAY version-switch policy gap closed with a frozen
DRAIN-BEFORE-ACTIVATE policy (`§3.1`); and `§17`'s outcome-record
`data_coverage_at_confirmation` field, which still used the forbidden
global rollup. `v2.enabled` stays `false`; `v2.rules_version` remains
`v2-rules-v0.1.0` for `#43` itself.

**Revised pre-Stage-6 sequence (a reviewability plan, not a new
correctness contract — subject to change if audit findings evolve):**

- **`#44` — Quality/scoring boundary hardening.** Implements `§6.3a`'s
  per-family metric-scoped quality gates across every Stage 4/5 call site
  (`regime_4h.py`, `bias_1h.py`, `trend_pullback.py`,
  `compression_breakout.py`, `confirmed_breakout.py`); adds the Stage 4
  numerical-evidence handoff (`§4.1a`: `price_evi`/`compression_score`/
  `bias_evi` carried forward by value, not discarded after
  regime/bias-label computation) and the Stage 5 scoring/quality handoff
  (the `COMPRESSION_BREAKOUT` per-run mean `compression_score`, and every
  other canonical setup/scoring/quality fact `§8`/Stage 6 needs, carried
  forward by value); hardens `TREND_PULLBACK` candidate self-validation to
  `COMPRESSION_BREAKOUT`-grade exact-formula invariants (`§7.1`'s
  self-validation note); adds a lightweight rules/version integrity check
  (a version-participating constant changing without a `rules_version`
  bump fails CI). Ships under `v2-rules-v0.2.0`. **MUST NOT** touch
  episode identity/lifecycle (`§12`/`§13`) or any Stage 6 concept — Stage
  6 still does not exist.
- **`#45` — Replay/provenance/data-coherence hardening.** Implements
  `§3.4`'s one-coherent-data-view-per-decision invariant (Stage 3+5 input
  assembly; Stage 2 correction-publication completeness); `§3.2`'s
  decision-provenance-tuple continuity (resolved before Stage 3/4/5/6
  computation begins, including the new `decision_code_version`
  dimension, distinct from Stage 2's own feature `code_version`); `§3.3`'s
  feature-code/calculation-version identity isolation (an unrelated repo
  change MUST NOT fork Stage 2's `calculation_version`) and version
  activation readiness (fail-closed, no silent fallback); an as-of/
  historical model (or equivalent) for `exchange_instruments` so a
  historical decision's `tick_size` is exactly reproducible under replay
  (`§12.5a`); `§2.1b`'s raw-kline-backfill no-downgrade fix (CONFIRMED
  against live-traced `insert_klines`/`backfill.py` code — an
  unconditional `ON CONFLICT` overwrite currently lets a lower-fidelity
  backfill NULL out known live `taker_buy_volume`/`taker_sell_volume`/
  `trades_count`); `§2.1c`'s residual aligned-input defensive hardening
  (CONFIRMED against live-traced `aligned_inputs.py` — a naive
  `snapshot_ts`/malformed `sample_window_end` currently leaks a raw
  `TypeError` instead of the domain `V2AlignedInputError`). **MUST NOT**
  implement Stage 6 state transitions.
- **`#46` — Persistence/idempotency hardening.** Implements `§2.1a`'s NOW
  singular same-`T` event model (option (a) only: at most one
  `V2EpisodeEvent` per `(execution_stream, episode_id, decision_boundary)`,
  same-`T` facts aggregated into it — option (b), multiple rows with a
  secondary ordering, is explicitly rejected as non-conforming); `§2.1a`'s
  deterministic semantic `episode_id`/`event_id` construction (frozen
  semantic input dimensions — `model_family`/`rules_version`/
  `calculation_version`/`symbol`/`market_type`/`direction`/`setup_family`/
  creation `structural_anchor`/`T_create` for `episode_id`;
  `episode_id`+`decision_boundary` for `event_id` — explicitly EXCLUDING
  `execution_stream`/`run_kind`/`run_id`, which remain the physical row
  namespace only, never semantic identity); the corresponding
  `(run_kind, run_id, episode_id, decision_boundary)` DB uniqueness
  invariant; wraps one logical Stage 6 decision boundary's full
  event-insert batch in one true atomic transaction
  (`Database.insert_v2_episode_events` currently validates the whole batch
  before I/O but does not yet transactionally guarantee all-or-nothing
  persistence — `§2.1a`'s corrected retry-model explanation is the target
  behavior); confirms/hardens `LIVE` `run_id` stability across restart
  (`§12.10`). **MUST NOT** implement Stage 6 state transitions.
- **Stage 6 — Episode State Machine** (**5 PRs** — corrected from an
  earlier "4" that force-fit five genuinely distinct implementation units
  into four merely to preserve an old count; unchanged in *content* from
  the prior plan, renumbered to follow the pre-Stage-6 hardening above):
  (1) episode identity + persisted-history read foundation (consumes
  `#44`–`#46`'s hardened boundaries, including `§3.2`'s provenance tuple
  and `§2.1a`'s deterministic IDs/one-event-per-T model); (2) candidate
  classification/arbitration/`EARLY_SIGNAL` creation/same-slot/cooldown
  eligibility; (3) family confirmation/false-break/candidate-expiry
  transitions; (4) `CONFIRMED`/`WEAKENING`/structural invalidation/horizon
  terminal resolution (requires `§18.2a`'s now-fully-frozen analytical-
  excursion primitive — shared with, not duplicated against, the later
  Stage 8 V2 Outcome Evaluator); (5) same-boundary orchestration order
  (`§13.4`) + `REVERSAL_CANDIDATE` cardinality (`§13.3.1`) integration +
  Stage 6 completion.

This split is an implementation/reviewability plan; the existing Product/
Correctness contracts (as amended by `#43`) remain authoritative, and this
split may be adjusted if reviewability, risk, or further audit findings
require it. It is not a claim that the exact PR count, numbering, or
boundaries are immutable.

**Next planned work (after `#43` merges):** `#44` — quality/scoring
boundary hardening (not yet started).
