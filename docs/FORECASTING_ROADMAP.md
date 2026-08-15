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
These are planning labels, not identifiers minted anywhere in the schema —
see [§A](#a-decision-status) for what that does and does not imply.

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
schema distinguish V1 from a future V2 model at the row level, is explicitly
**future work** for a later PR (see [§I](#i-high-level-delivery-roadmap),
stage 2). Until that PR lands, "V1" and "V2" are documentation-level
concepts only.

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
| 6. Episode State Machine | 3 |
| 7. Entry Feasibility | 2 |
| 8. V2 Outcome Evaluator | 3 |
| 9. Telegram V2 | 2 |
| 10. Parallel Shadow Deployment | 2 |
| **Total planned scope** | **28** |

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
- **Stage 2 — Multi-model Framework: begun.** A small, self-contained
  **foundation PR** ("feat: add V2 multi-model foundation") introduces
  **only** the identity/config/module foundation the rest of the stage
  builds on: the `model_family` / `rules_version` identity conventions
  frozen in `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3, physically
  encoded as `config/v2.yaml` + `common/v2_config.py` (a strict loader,
  independent of `common/stage2_config.py`) and
  `analytics/forecasting_v2/identity.py` (a pure `V2ModelIdentity` value
  object); plus a DB-owned, additive `model_family` column on
  `forecast_predictions` / `forecast_outcomes` (defaulting existing and
  future V1 rows to `'v1'`, per §A below). This foundation PR deliberately
  implements **no** forecasting logic: no multi-timeframe alignment, no 4h
  regime / 1h bias / context engines, no setup detectors, no episode
  lifecycle/state machine, no entry-feasibility evaluation, no V2 outcome
  evaluator, no V2 Telegram, and no runtime wiring of any kind — `v2.enabled`
  stays `false` and nothing reads `config/v2.yaml` outside its own loader and
  tests. **V1 remains the running baseline**, entirely unaffected.
- **V2 still has no forecasting logic of any kind** beyond this identity
  foundation — no MTF alignment/context/setup/episode runtime exists yet.

**Next planned PR:** Multi-model Framework PR 2 of 3 (§I above) — not yet
Context Engines (stage 4); the Multi-model Framework stage's own remaining
scope comes first.
