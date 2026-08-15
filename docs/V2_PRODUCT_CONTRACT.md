# V2 Product Contract

This document freezes **what V2 is supposed to be** — the intended product
behavior, scope, and vocabulary. It does **not** freeze the exact algorithms,
formulas, or thresholds used to build it — those are frozen in
**`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`** — nor the database schema
or state-machine implementation, which belong to the later
implementation-stage PRs (see [§0](#0-documentation-hierarchy) and
[§12](#12-deferred-to-later-contracts)).

This document exists so that later implementation PRs cannot quietly change
the intended product while claiming to be "V2." Any implementation PR whose
behavior contradicts this contract is either wrong, or must first amend this
contract explicitly — implementation must never silently redefine the
product.

Normative language in this document follows standard usage:

- **MUST** / **MUST NOT** — a hard requirement; violating it means the
  implementation is not V2 as defined here.
- **SHOULD** / **SHOULD NOT** — a strong expectation; a deviation is possible
  but must be deliberate and justified, not accidental.
- **MAY** — genuinely optional or explicitly out of scope for now.

No V2 code exists yet. This PR is documentation only. The currently deployed
V1 forecast (`analytics/forecasting/`) is unaffected — see
[§11](#11-v1--v2-coexistence).

---

## 0. Documentation hierarchy

To avoid two documents both claiming to be the authority on the same
question, the hierarchy is:

1. **`docs/FORECASTING_ROADMAP.md`** — canonical **product direction /
   roadmap**. Answers "where is the forecasting product headed, and why."
2. **`docs/V2_PRODUCT_CONTRACT.md`** (this document) — canonical definition
   of **what V2 product behavior means**. Answers "what must a V2
   implementation do, from a user/product point of view." Where this
   document is more specific than the roadmap about V2, this document
   governs V2 product behavior; it does not contradict or expand the scope
   the roadmap already adopted.
3. **`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`** — canonical
   **deterministic correctness and acceptance criteria**: exact formulas,
   thresholds, timestamp/no-lookahead mechanics, persistence identity,
   promotion criteria. Answers "how exactly is this computed and how do we
   know it's correct/good enough." **Frozen** — see that document's own
   traceability matrix (§24) for exactly which of this contract's §12
   deferrals it resolves.
4. **Historical Stage 2 documents** (`docs/STAGE2_SPEC.md`,
   `docs/STAGE2_IMPLEMENTATION_PLAN.md`, `docs/STAGE2_CLARIFICATIONS.md`,
   `docs/STAGE2_DATA_AUDIT.md`) — foundation/history. They record what was
   decided and built for Stage 2's ingestion/feature/consensus/percentile
   foundation, which remains valid and is reused by V2. They are **not** V2
   product authority, even where sections of them (e.g.
   `STAGE2_CLARIFICATIONS.md` §1 "Entry, invalidation, targets") describe an
   earlier, broader `signal_engine` concept that reads similarly to V2. Where
   such historical language conflicts with this contract, **this contract
   wins** for V2 product behavior.
5. **`docs/PRODUCT_SPEC_V0.md`** — the original product spec. Still the
   source for the hard gates carried forward into V2 ([§10](#10-hard-product-gates-carried-forward)),
   but its signal lifecycle (`EARLY → ARMED → TRIGGERED →
   INVALIDATED/EXPIRED`) is superseded by V2's episode lifecycle
   ([§5](#5-episode-lifecycle)) — the two are related in spirit, not
   identical, and this contract does not assume a 1:1 state mapping between
   them.

---

## 1. Product mission and scope

V2 **MUST** be a multi-timeframe intraday scenario-monitoring product,
intended for approximately **1–4 hour trades**.

Fixed scope for the initial V2:

- Symbol: **BTCUSDT**.
- Contract type: **USDT perpetual**.
- Active exchanges: **Binance, Bybit, OKX** (the same three exchanges the
  Stage 2 foundation and V1 already use).
- Data: **existing perp data only** —
  - price / volume;
  - taker flow;
  - open interest;
  - funding;
  - liquidations;
  - cross-exchange consensus.
- **Decision support only.** V2 **MUST NOT** execute trades automatically.

Explicitly **excluded** from the initial V2 (not deferred to "later in V2" —
excluded from this product's initial scope entirely; any future inclusion
requires its own product-direction decision, not an implementation PR):

- Spot ingestion.
- Orderbook ingestion.
- CoinGlass or any other third-party vendor data feed.
- Market-cap feeds.
- ML models.
- Automatic execution.
- Portfolio sizing.
- Multi-symbol expansion.

This contract **MUST NOT** be read as expanding V2's scope beyond what
`docs/FORECASTING_ROADMAP.md` §D/§F already adopted. Any implementation PR
that introduces one of the excluded items above is out of contract, no
matter how useful it seems.

---

## 2. Timeframe responsibilities

The role split across timeframes is frozen as:

| Timeframe | Responsibility |
|---|---|
| `4h` | Market regime |
| `1h` | Directional bias |
| `15m` | Setup formation |
| `5m` | Trigger and ongoing monitoring |

These four timeframes **MUST NOT** be treated as four independent votes to
be summed or averaged. Each has a distinct semantic responsibility, and an
implementation **MUST NOT** count the same underlying market move four times
just because it is visible on four timeframes (e.g. one strong impulsive move
MUST NOT simultaneously register as an independent "4h regime signal," an
independent "1h bias signal," and an independent "15m setup signal," as if
they were three unrelated pieces of evidence — they are one thing observed
at different resolutions).

A V2 implementation **MUST** use only fully closed candles/buckets as input
at every timeframe — no timeframe may read a bucket that has not yet closed.

The exact cross-timeframe timestamp alignment rules and no-lookahead
mechanics (how a 5m trigger reconciles its "current" state against a 4h
bucket that closed hours earlier, exact clock/latency handling, etc.) are
**FROZEN** in `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §1–§2
([§12](#12-deferred-to-later-contracts)). This contract only freezes the
role split and the closed-bucket-only requirement.

---

## 3. Scenario / episode product concept

V1 treats every closed 5m bucket as an independent forecast. V2 **MUST NOT**
do this. V2 **MUST** track one market idea as a single **episode** over
time.

The frozen product invariant:

> Repeated observations of the same underlying market scenario **MUST**
> update one episode rather than generating a new independent trading
> notification every five minutes.

This contract intentionally does **not** freeze:

- the database primary key or persistence identity for an episode;
- the exact algorithm used to decide whether two observations belong to the
  "same" scenario (deduplication logic).

Those are correctness-contract concerns
([§12](#12-deferred-to-later-contracts)). What **is** frozen here is the
product-level requirement: overlapping evidence representing the same market
idea **MUST NOT** cause duplicate user-facing scenario spam. An
implementation that satisfies the letter of "one row per bucket" while still
spamming the user with effectively-the-same scenario over and over does
**not** satisfy this contract.

---

## 4. Initial setup families

Exactly **three** setup families are allowed in the initial V2. An
implementation **MUST NOT** label a detected scenario with any setup family
other than these three, and **MUST NOT** invent a fourth family without a
new product-direction decision.

### 4.1 `TREND_PULLBACK`

An established higher-timeframe trend (regime + bias) experiences a
temporary retracement, and the setup anticipates **resumption in the
prevailing trend direction**. The defining characteristic is direction *with*
the higher-timeframe trend — this is a "the trend paused, now it
continues" setup, not a setup about a break of structure.

- `4h` establishes that a trending regime exists.
- `1h` establishes the directional bias the trend is moving in.
- `15m` forms/identifies the pullback structure itself (the retracement).
- `5m` provides the trigger that the pullback has ended and the trend is
  resuming, and continues monitoring the resumption.

### 4.2 `COMPRESSION_BREAKOUT`

A period of range contraction / reduced volatility (compression) forms on a
structural timeframe, and the setup anticipates a **breakout out of that
compression**. The defining characteristic is that the setup's significance
comes from the **preceding compression itself** — the breakout matters
because it emerged from a defined tight range, not merely because price
moved.

- `4h` provides the broader regime context the compression is forming
  within.
- `1h` provides directional bias context for which resolution direction
  would align with the higher-timeframe picture, when a bias exists — a
  compression can also form without a firm 1h bias.
- `15m` forms/identifies the compression structure itself (the setup
  formation).
- `5m` provides the breakout trigger and ongoing monitoring of the
  resulting move.

### 4.3 `CONFIRMED_BREAKOUT`

A break of a structural level that receives additional confirmation
(continuation / hold / sustained follow-through) before being treated as
actionable. This is the **general** breakout case: unlike
`COMPRESSION_BREAKOUT`, it does not require a preceding compression regime as
its defining precondition — it is defined by the break of a meaningful
structural level plus confirmation, whatever the price structure looked like
immediately beforehand.

- `4h` establishes that the structural level being broken is significant
  within the current regime.
- `1h` establishes directional context aligned with the break.
- `15m` forms the setup around the specific structural level and the
  confirmation requirement.
- `5m` provides the trigger/timing and ongoing monitoring of the
  confirmed break.

### 4.4 Boundaries

- **Countertrend trading signals are excluded** from the initial V2 release.
  V2 **MUST NOT** deliberately emit a scenario that trades **against** an
  established, firmly directional higher-timeframe context (a `4h` regime or
  `1h` bias that genuinely points a direction). Where the `4h` regime or
  `1h` bias is neutral, non-directional, or not firmly established, that
  **absence MUST NOT itself be treated as a countertrend condition** —
  `COMPRESSION_BREAKOUT` ([§4.2](#42-compression_breakout)) in particular may
  legitimately form without a firm `1h` bias, and this contract does not
  require every setup to have an explicit same-direction `4h`+`1h` vote
  before it is valid. The exact directional-context compatibility rules —
  how "established"/"firm" is determined, and how each setup family's
  detector must reconcile with `4h`/`1h` context — belong to the correctness
  contract ([§12](#12-deferred-to-later-contracts)).
  (`REVERSAL_CANDIDATE`, [§5](#5-episode-lifecycle), is a distinct episode
  concept — an independently-qualifying opposite scenario reported against
  an existing episode — not a countertrend variant of these three families.)
- This contract deliberately does **not** define numerical thresholds,
  scoring formulas, percentile cutoffs, ATR multiples, or confirmation
  constants for any of the three families. A detector implementation
  **MUST NOT** claim conformance with this contract merely because it
  produces a `TREND_PULLBACK` label — it must also match the semantic
  boundary above. Precise, numeric detection criteria are **FROZEN** in
  `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7
  ([§12](#12-deferred-to-later-contracts)).

---

## 5. Episode lifecycle

V2 adopts the following episode states:

- `EARLY_SIGNAL`
- `CONFIRMED`
- `WEAKENING`
- `INVALIDATED`
- `REVERSAL_CANDIDATE`
- `EXPIRED`
- `COMPLETED`

### 5.1 State meanings

- **`EARLY_SIGNAL`** — a scenario has been detected but has not yet met the
  bar for `CONFIRMED`. Non-terminal.
- **`CONFIRMED`** — the scenario has met its confirmation requirement (see
  [§10](#10-hard-product-gates-carried-forward) — price confirmation
  remains necessary) and is the episode's actionable core state.
  Non-terminal.
- **`WEAKENING`** — evidence for the scenario is deteriorating but has not
  yet reached invalidation. Non-terminal. Whether, and under what
  conditions, a `WEAKENING` episode can recover is **FROZEN** in
  `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §13.2/§13.2a (recovery to
  `CONFIRMED` is allowed) ([§12](#12-deferred-to-later-contracts)) — this
  contract does not itself draw the recovery edge, it only confirms one
  exists.
- **`INVALIDATED`** — the scenario's structural premise has broken.
  Terminal for this episode.
- **`REVERSAL_CANDIDATE`** — the **opposite** direction has independently
  begun satisfying its own scenario-entry requirements. See
  [§5.3](#53-reversal-is-never-automatic) — this is never a passive
  consequence of `INVALIDATED`.
- **`EXPIRED`** — the scenario's expected horizon elapsed without
  confirmation (from `EARLY_SIGNAL`) or without completion (from
  `CONFIRMED`, if applicable). Terminal.
- **`COMPLETED`** — the scenario played out to its evaluated conclusion (its
  expected horizon and outcome were reached from `CONFIRMED`). Terminal.

### 5.2 Illustrative lifecycle sketch (non-normative)

The sketch below shows one *possible* path through the states above, purely
to aid intuition. It is **not** a frozen transition graph: it does not
enumerate every allowed edge, and an implementation **MUST NOT** treat it as
an exhaustive specification of which state may follow which.

```text
EARLY_SIGNAL  ⇢  CONFIRMED  ⇢  WEAKENING  ⇢  INVALIDATED
                      ⇢  COMPLETED
```

What this contract actually freezes, at the product level:

- V2 **MUST** track **one episode over time**, rather than emitting a new
  independent signal every five minutes the way V1 does.
- An episode **MUST NOT** be forced through every state — e.g. an episode
  **MAY** move directly from `EARLY_SIGNAL` (or `CONFIRMED`) to
  `INVALIDATED` or `EXPIRED` without visiting the states in between, if
  evidence breaks abruptly rather than gradually.
- `INVALIDATED`, `EXPIRED`, and `COMPLETED` mark that this episode is **no
  longer being actively monitored in its original form** — they are the
  concepts that close out an episode, as opposed to the actively-tracked
  `EARLY_SIGNAL` / `CONFIRMED` / `WEAKENING` states.
- **Invalidation does not, by itself, imply reversal** — see
  [§5.3](#53-reversal-is-never-automatic).
- `REVERSAL_CANDIDATE` is **not** a fixed step along any single path — it is
  a cross-cutting observation that **MAY** be reported alongside an
  existing episode whenever the opposite scenario **independently**
  qualifies on its own merits ([§5.3](#53-reversal-is-never-automatic)). It
  is never implied by, or wired to, any specific state transition. The
  exact mechanics (when the event fires, what it attaches to, and how it
  relates to a newly created opposite-direction episode) are frozen in
  `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §13.3, consistent with —
  not overriding — this section.

The **exact allowed transition edges** — including whether/how `WEAKENING`
can recover, whether `EXPIRED` is reachable from `CONFIRMED` in every case,
and the full transition graph and its thresholds — are **FROZEN** in
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §13
([§12](#12-deferred-to-later-contracts)); the physical Episode State
Machine implementation itself remains a later stage
(`docs/FORECASTING_ROADMAP.md` §I, stage 6). This contract freezes the
**state set, their product meanings, and the invariants above** — not a
transition graph; the graph now lives in the correctness contract.

### 5.3 Reversal is never automatic

**A reversal MUST NOT be inferred merely because the original scenario
invalidated.** `REVERSAL_CANDIDATE` **MUST** require the opposite direction
to **independently** satisfy its own scenario-entry requirements (i.e. it
would have qualified as its own `EARLY_SIGNAL`/`CONFIRMED` episode on its own
merits). An implementation that emits `REVERSAL_CANDIDATE` purely as the
mechanical next step after `INVALIDATED` — without independently evaluating
the opposite scenario's own entry conditions — does not conform to this
contract.

---

## 6. User-visible scenario information contract

A V2 scenario **MUST** conceptually carry enough information for a user to
answer:

- What is happening?
- Which direction?
- Which setup?
- How mature is the scenario?
- Is an entry still realistically feasible?
- Where is the entry area?
- What structurally invalidates the idea?
- Roughly how long is the scenario expected to play out?
- How strong is the model's evidence?
- How complete/reliable is the underlying data?

Concretely, a V2 scenario **MUST** semantically provide at least:

- symbol;
- direction;
- setup family;
- episode state;
- scenario detection/reference time;
- entry zone;
- structural invalidation level;
- expected horizon;
- model confidence;
- evidence/reason summary;
- data coverage / data-quality context;
- actionable vs. late/non-actionable status;
- the reason a scenario was suppressed from notification, when applicable.

This is a **semantic** requirement, not a schema. This contract deliberately
does **not** invent field names, SQL column names, or a persistence layout —
those belong to the implementation and correctness contracts, and **MUST**
only reuse names already frozen elsewhere (e.g. the existing
`forecast_predictions` identity columns) where genuinely applicable, rather
than this document inventing new ones.

V2 **MUST NOT** add a mandatory take-profit / price target field. The
accepted product direction requires an entry zone, a structural invalidation
level, and an expected horizon — not a fixed target price. This is
deliberate, not an oversight: adding a take-profit target "because trading
systems usually have one" would expand scope beyond what
`docs/FORECASTING_ROADMAP.md` adopted.

---

## 7. Confidence semantics

V2 **MUST** maintain a clear distinction between:

- **model confidence** — an explicit, model-derived strength score (the same
  category of value V1's `confidence` already is); and
- **historically calibrated success probability** — a probability derived
  from enough comparable completed episodes, using an explicitly frozen
  calibration methodology.

V2 **MUST NOT** present model confidence as, or label it:

- a win probability;
- a success probability;
- a calibrated historical probability.

A calibrated probability **MAY** only be introduced once (a) enough
comparable completed episodes exist to support a calibration, and (b) the
calibration methodology has been explicitly frozen in a future contract.
This document does **not** invent a calibration methodology, a sample-size
threshold, or a formula — see
[§12](#12-deferred-to-later-contracts).

---

## 8. Entry feasibility and lateness

This is a core V2 product requirement, not a nice-to-have.

- V2 **MUST** be designed to identify scenarios **before most of the
  expected move has already occurred** — this is the product's reason to
  exist over V1's after-the-fact confirmation behavior (see
  `docs/FORECASTING_ROADMAP.md` §B).
- A scenario **MAY** be analytically valid but already too late to enter —
  entry feasibility is a distinct concept from analytical validity.
- A late/analytically-valid-but-infeasible scenario **MUST** still be
  retained for research/evaluation purposes. V2 **MUST NOT** silently drop
  it.
- A late/non-actionable scenario **MUST NOT** generate a normal actionable
  trading notification ([§9](#9-notification-product-contract)).
- Entry feasibility **MUST** account for real-world notification/decision
  delay — a scenario is not "feasible" merely because the entry zone was
  valid at the moment of detection if, realistically, the user cannot act on
  it in time.

This contract deliberately does **not** freeze exact delay seconds,
price-distance tolerances, ATR multiples, slippage assumptions, or any
feasibility formula. Those are **FROZEN** in
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §15
([§12](#12-deferred-to-later-contracts)).

---

## 9. Notification product contract

This section freezes anti-spam/product semantics for notification behavior.
It does **not** implement Telegram and does **not** change the current V1
Telegram notifier.

The initial V2 notification behavior **SHOULD** support:

- a first meaningful early actionable scenario;
- a confirmation update when the scenario materially strengthens;
- a meaningful weakening update;
- an invalidation update;
- an independently-qualified reversal candidate update
  ([§5.3](#53-reversal-is-never-automatic)).

The same scenario/episode **MUST NOT** generate another equivalent
notification simply because another 5m bucket closed with no material
change. Non-material internal state changes **MUST NOT** create notification
spam. A late/non-actionable decision **MUST** remain available for research
([§8](#8-entry-feasibility-and-lateness)), but **MUST NOT** trigger a normal
actionable notification.

This contract deliberately does **not** freeze:

- exact Telegram wording or formatting;
- cooldown duration;
- retry behavior;
- notifier persistence schema.

Those belong to the later `Telegram V2` implementation stage
(`docs/FORECASTING_ROADMAP.md` §I, stage 9). The current V1 Telegram
notifier (`runtime/telegram_cli.py`, `notifications/`) **MUST NOT** be
changed by this contract or by adopting it.

---

## 10. Hard product gates carried forward

The following hard rules from `docs/PRODUCT_SPEC_V0.md` remain in force for
V2, unless explicitly superseded above:

- **Missing data is not equivalent to zero.** Absence of a source, absence
  of history, and a genuine zero value **MUST** remain distinguishable — as
  they already are in the Stage 2 foundation's `NULL`-vs-zero handling that
  V1 relies on today.
- **OI, funding, and liquidations alone MUST NOT independently create a
  LONG/SHORT direction.** They remain context/confirming metrics, not a
  standalone directional signal, exactly as `PRODUCT_SPEC_V0.md` requires.
- **Price confirmation remains necessary** before a scenario can be
  considered fully confirmed/actionable. This is the invariant that carries
  forward from `PRODUCT_SPEC_V0.md`'s "`TRIGGERED` невозможен без ценового
  подтверждения" ("`TRIGGERED` is impossible without price confirmation") —
  see the terminology note below.
- **Data coverage MUST remain separately observable from the directional
  signal itself** — a user (or downstream evaluation) must be able to see
  how much cross-exchange data backed a scenario, independent of what
  direction the scenario claims.
- **Cross-exchange evidence MUST NOT be silently replaced with
  single-exchange certainty.** At every timeframe, V2 **MUST** use
  cross-exchange evidence: missing exchange data for a bucket **MUST NOT**
  be treated as if it were confirming certainty, and a single exchange's
  data **MUST NOT** masquerade as full cross-exchange consensus. Coverage
  **MUST** remain separately observable, per the requirement above.
- **A high setup/model score MUST NOT bypass a mandatory hard gate.** Same
  principle as `PRODUCT_SPEC_V0.md`'s "high Setup Score does not cancel the
  mandatory hard gates above," applied to V2's setup families and episode
  confirmation.

This contract freezes the **product invariants** above, not a specific
implementation mechanism. The Stage 2 foundation already implements a
per-family minimum-exchange-coverage consensus gate that satisfies these
invariants for the existing 5m pipeline (`docs/STAGE2_SPEC.md` §11,
`config/stage2.yaml`). Whether that exact gate — including its current
numeric parameters — carries over unchanged to `15m`/`1h`/`4h` feature
computation, or is adapted for multi-timeframe use, is now **FROZEN** in
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §6
([§12](#12-deferred-to-later-contracts)) — the same coverage ratio and
confidence floor are reused at every timeframe as the V2-v0 starting gate.
This document does not invent, and does not expand the frozen scope of, a
numerical consensus gate beyond what is already decided for the existing
pipeline.

### Terminology note: `TRIGGERED` is not renamed to `CONFIRMED`

`docs/PRODUCT_SPEC_V0.md`'s lifecycle (`EARLY → ARMED → TRIGGERED →
INVALIDATED/EXPIRED`) and V2's episode lifecycle
([§5](#5-episode-lifecycle)) are **not** the same state machine, and this
contract does **not** assume a 1:1 mapping between their state names — in
particular, V1/V0's `TRIGGERED` is not simply relabeled `CONFIRMED`. `TRIGGERED`
described a single-shot confirmation moment with no ongoing multi-state
episode tracking beyond `INVALIDATED`/`EXPIRED`; V2's `CONFIRMED` is one state
within a richer tracked episode that can further move to `WEAKENING`,
`INVALIDATED`, or `REVERSAL_CANDIDATE`. What carries forward is the
**underlying product invariant** — a scenario is not actionable without
price confirmation — not the specific state name or the shape of the state
machine around it.

---

## 11. V1 / V2 coexistence

- **V1 remains running and frozen** as a research baseline
  (`docs/FORECASTING_ROADMAP.md` §C).
- This PR does **not** disable V1.
- This PR does **not** change V1 predictions.
- This PR does **not** change V1 Telegram behavior.
- V2 **MUST** eventually run in **parallel shadow mode** before replacing
  any user-facing V1 behavior (`docs/FORECASTING_ROADMAP.md` §I, stage 10 —
  "Parallel Shadow Deployment").
- V2 **MUST** earn promotion through its later acceptance contract and
  evaluation — promotion is not automatic on completion of implementation.
- **No V2 production promotion is authorized by this PR.** This PR freezes
  product intent only.

---

## 12. Deferred to later contracts

Almost everything originally listed here is now **FROZEN** in
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` — see that document's §24
traceability matrix for the item-by-item disposition. This section is kept
short deliberately: it no longer restates formulas or thresholds (that
would duplicate, and risk drifting from, the correctness contract), it only
records what remains genuinely open after both contract PRs:

- **Calibration methodology** — genuinely **deferred beyond initial V2**
  (`V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §25): initial V2 has no
  calibrated win probability, `model_confidence` stays non-probabilistic,
  and calibration cannot be added without a future contract/version
  change. This is deferred for a substantive reason (no completed-episode
  sample can exist before V2 runs), not for difficulty.
- **Physical persistence** — table schema, database keys, config YAML, and
  runtime code are **not** decided by either contract PR (both are
  documentation-only by design, see
  `docs/FORECASTING_ROADMAP.md` §I stage 2 "Multi-model Framework"). The
  *logical* identities, semantics, and thresholds that schema/config will
  encode are frozen; their physical encoding is implementation work.

Everything else previously listed here — cross-timeframe alignment,
no-lookahead mechanics, closed-bucket selection, setup formulas, scoring,
thresholds, percentiles, confidence weighting, entry zone, invalidation,
entry-feasibility tolerance, notification delay, episode identity, state
transitions, cooldowns, material updates, replay/backtest methodology,
sample requirements, promotion thresholds, and acceptance metrics — is
**FROZEN** in `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`. Where that
document does not state a number, the same discipline applies as before:
it is deliberate, not an oversight.

---

## Status

- **V2 Product Contract: frozen** (this document).
- **V2 Correctness & Acceptance Contract: frozen**
  (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`).
- **V2: still not implemented.**
- **Next planned stage:** Stage 2 — Multi-model Framework
  (`docs/FORECASTING_ROADMAP.md` §I).
