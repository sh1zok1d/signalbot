# Signalbot — Current Project Status

**Status date:** 2026-09-22 (routing pointer updated 2026-09-29; product-first decision 2026-10-02; decision support 2026-10-03)
**Operating mode:** `PRODUCT_FIRST / DECISION_SUPPORT / NO_DIRECT_TRADE_CALLS` (since 2026-10-03, `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md`). The earlier modes `PRODUCT_FIRST / RESEARCH_SERVES_PRODUCT / PREDICTIVE_CLAIMS_FROZEN` (2026-10-02) and `RESEARCH_FIRST / DESCRIPTIVE_PRIVATE_BETA_V0_AUTHORIZED / PREDICTIVE_PRODUCT_FROZEN` are historical.
**Active phase:** see `docs/CURRENT_RESEARCH_STATE.md`. As of 2026-09-29 its latest entry is the GV0R03 generator feasibility contract, with `NEXT_UNIT = NONE_AUTHORIZED_AFTER_GV0R03_CONTRACT`. The earlier phase `POST_SPRINT03_DISCOVERY_PROGRAM_DECISION` is historical.

This file is intentionally concise. The pre-cleanup long-form status remains immutable in git at `b25d9ca99498630183813d0ccb8c6d67b93ad915`; experiment history remains in `docs/RESEARCH_LEDGER.md`.

## Current decision (2026-10-03)

**Research transition (2026-10-05).** The compiler V3 variance line is closed as a negative methodological result. Research now follows `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`:
- evidence is reported apart from the claim decision;
- an L0–L4 ladder of allowed claims sets what may be said, with quantitative L2 historical-direction wording and L3 probabilities only after live calibration;
- every claim is logged prospectively;
- there is no pre-certification gate.

Next unit: `WEEKDAY_WEEKEND_BASELINE_UNIT_V2` (product evidence, not run). Routing: `docs/CURRENT_RESEARCH_STATE.md`.

**Decision support.** The owner, reading the V1 surface as a trader, found no answer to "what do I do with this", and lifted the predictive freeze for the product: `docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md`. The bot now forecasts the range (1h / 4h / 24h corridor, checked on a held-out year and tracked live), shows the levels the whole market watches with the chance to reach them and what happened at their first touch beside a random level, «что было после похожих» for the 1h / 4h states, the CPI / FOMC / expiry calendar (name and time only; no event-size multiplier since 2026-10-03), `/risk` and personal `/alert`, and sends timely market alerts. Direct trade calls stay forbidden. Binance 2025/2026 is opened for product statistics. Implemented and deployed to production (main `a16b876`, owner-reported 2026-10-03; see "Production state"); deploy steps in `PRIVATE_BETA_V0_DEPLOY.md`, "Decision support V2".

**Product-first (2026-10-02, kept where V2 does not differ).** The canonical product decision is `docs/PRODUCT_FIRST_DECISION_V1.md`. It fixes the product hypothesis (a Russian-language market briefing that compresses "what happened, who dominates, how unusual"), the build-to-test MUST scope, the architectural constraint (one detector, one episodization, one context projection, one shared view builder, one outbox, one notifier), the DO-NOT-BUILD-YET list, the data maturity orientation (V2 tape since 2026-10-01; baselines about 2026-10-21; full 30d ranks about 2026-10-31) and the 30-day user test with its decision rules.

Research infrastructure is kept and research serves the product: only small, feasibility-confirmed units; no new programs, no new one-shot confirmations, no research surface widening for the hope of an edge. Signalbot still has no validated durable trading edge and makes no predictive claim.

The research conclusion below stays recorded: the program stopped repeating nearby “new observable -> short-horizon scalar BTC prediction” formulations. Research routing: `docs/CURRENT_RESEARCH_STATE.md`.

## Descriptive private beta V0.2 (2026-09-25)

A narrow descriptive private beta is authorized by `docs/PRIVATE_BETA_V0_RESTART_DECISION.md`. It covers BTCUSDT perp on Binance, Bybit and OKX, runs on Telegram, is capped at 20 users and uses deterministic `BETA_EVENT_RULES_V1`.
- **What it is:** a descriptive attention engine only. It carries no predictive claim, no trade instruction and no edge claim.
- **What stays frozen:** predictive product work, and the V1 and V2 semantics.
- **Current state (2026-10-02):** V0.2 ran for the owner only; the owner judged the 5m event feed unactionable (`CHANGE PRODUCT`). No external users yet. The implementation scope is now the build-to-test MUST list of `docs/PRODUCT_FIRST_DECISION_V1.md` §3; `BETA_V0_3_MARKET_BRIEFING.md` is superseded where it differs (briefing episodes, 24h label, 90-day baselines, separate notifier).
- **Build-to-test (2026-10-02):** the MUST scope is implemented in code (see the decision's §11 amendment log and `PRIVATE_BETA_V0_DEPLOY.md`, "Product-first V1").
- **Decision support V2 (2026-10-03):** implemented on top of V1 (`PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §7); the morning briefing is committed on. Merged into `main` at `a16b8761e45c15473664021cad03b285f747132e` and deployed to production (owner-reported, 2026-10-03; see "Production state" below).
- **Next step:** owner test and red-team of V2, then deploy to the owner-only beta (history sync, first build, V2 tape rewind, history timer), run the gate coverage diagnostic and the owner review of the interpretation dry run; external launch follows data maturity (§6 of `PRODUCT_FIRST_DECISION_V1.md`), then the 30-day user test of `PRODUCT_FIRST_DECISION_V1.md` §7 on the V2 surface.
- **Research boundary:** beta events are not hypotheses, and beta outcomes are not confirmation.

## Production state (updated 2026-10-06; owner-reported deploy of 2026-10-05)

| Item | State |
|---|---|
| Production commit | `c980fae` (merge of #329) |
| Last deploy | C1 same-UTC-day-type reference, 2026-10-05 12:44 UTC; smoke 27 PASS / 0 WARN / 0 FAIL (owner-reported) |
| Versions after that deploy | context `BETA_CONTEXT_1H_V3`, TOD `BETA_HORIZON_TOD_V3`, analogues `BETA_ANALOGUES_V2` |
| In production | #319, #322, #326 (research evidence engine), #327 (its deploy plan, a document), #329 (C1) |
| `BETA_RESEARCH_EVIDENCE_ENABLED` on the server | not recorded (owner action, `PRE_BETA_SCOPE_DECISION_V1.md` §9) |
| `main` after `c980fae` | research and pre-beta documents (#330–#333), track A and track B pre-beta work (#334–#340 and later); **not deployed** — deploy is forbidden until the owner says otherwise (owner, 2026-10-06) |

Sources: `BETA_C1_DAY_TYPE_BASELINE_V1.md` (status), `PRE_BETA_SCOPE_DECISION_V1.md` §10. The 2026-10-03 table below is kept as the record of the V2 deploy.

### Earlier record: the V2 deploy (recorded 2026-10-03, owner-reported)

V2 decision support is merged and deployed to production.

| Item | State |
|---|---|
| V2 merged into `main` | `a16b8761e45c15473664021cad03b285f747132e` |
| Production deploy | SUCCESS |
| History sync | OK |
| Statistics build | OK |
| 30-day bootstrap | COMPLETE |
| Bot | active / running |
| Health | OK |
| Smoke: `/events` | PASS |
| Smoke: `/research` | PASS |
| Smoke: invalid `/alert nan` | handled |
| Smoke: `/btc` after invalid input | PASS |

Source: the owner's deploy report. No host, identifier, token or secret is recorded here. Deployment does not change research posture: no research claim follows from it, and beta outcomes are not confirmation.

## Current evidence

- V3 calibration closed; methodology not generally claimable; no V4.
- MARKET-01: `NO_EVIDENCE`.
- MARKET-02: `NO_EVIDENCE`.
- MARKET-03: external historical reproduction `REPRODUCED_DIRECTION`; not internal validated alpha/OOS.
- MARKET-04 / 04H: blocked by historical observable/provenance; not scientifically rejected.
- MARKET-05: `MARKET_05_NO_EVIDENCE`.
- MARKET-06: `MARKET_06_NO_EVIDENCE`; exact one-shot RESULT sealed at `80c7d19f622cc7b5576154de59dbb9cdf85d4dcf`; rerun forbidden.
- Internal historical candidates promoted: `0`.
- Regular bullish divergence / selling-exhaustion program: `COMPLETED`, closed as an active research route on 2026-10-03.
  - **Results:** about +1–3 pp inside support, with +15 pp ruled out by validation. `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0 = INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON`.
  - **Not authorized:** any further unit or SEED. `RSI_GRADIENT_SUPPORT_CANDIDATE` is archived. See `CURRENT_RESEARCH_STATE.md`.
- Protected 2025/2026 OOS: not globally unopened.
  - **Opened (2026-10-02).** The six-symbol USD-M divergence/support surface 2025-01-01..2026-08-15 (exclusive): BTC, ETH, SOL, BNB, DOGE and XRP 1m klines, bookDepth and OI metrics. It is no longer pristine OOS for divergence/support/mechanism hypotheses, and it stays usable as exposed data for estimation and feasibility.
  - **Still protected:** the E1-RUN-001 holdout and everything at or after 2026-08-15.
  - **Fields:** `DIVERGENCE_SUPPORT_2025_2026_SURFACE_OPENED = true`; `E1_RUN_001_OPENED = false` (holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)`).
  - **Unrelated families:** this does not declare all of 2025/2026 spent for them; their use is an owner decision. See `docs/research/DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3.md`.

The exact M05/M06 additive 24h adverse-path MAE cell is `REPEATED_NULL / LOW_PRIORITY_FOR_NOW`. The broader short-horizon BTC conditional scalar-prediction family is `LOW_PRIORITY / SATURATED_FOR_NOW` as a program search-priority conclusion only.

## Active work

The current next unit is in `docs/CURRENT_RESEARCH_STATE.md`. The text below records the state as of 2026-09-22. Its former "Next: Discovery Sprint 03 post-result program decision" (`DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION`) has since been superseded by Sprint 04 and Generator V0 work.

`HETEROGENEOUS_FAMILY_ROTATION_V2` remains frozen. Sprint 03 canonical
scientific execution is consumed: D9 `NO_USEFUL_STRUCTURE`, D10
`NO_USEFUL_STRUCTURE`, D11 `PROMISING_PROTOTYPE`. Do not rescue D9/D10.
D11 is unsigned scheduled-FOMC 6h RV only; not D8 rescue; not a FOMC
trading strategy. Sprint 04 hypotheses are **not** selected here. D7
`KLINE_FLOW_IMPACT_STATE` is `PROMISING_PROTOTYPE` and a confirmation
candidate, but confirmation is **not** selected now. Family E is in
cooldown. D8 remains `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` and is not
a negative scientific result. Do not rerun D7. Do not execute D8.
Do not create MARKET-07. Do not open 2025/2026.

D2 remains an `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE` from the
independent pre-2020 BitMEX surface, not a validated trading edge. The
excess direction-aligned path-risk one-shot is consumed. Canonical
classification (evaluator, not reinterpreted):
`D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`.
`RERUN_AUTHORIZED = false`. Binance 2025/2026 remain sealed. Product
build remains frozen. MARKET-07 is not created. Do not rerun the
decomposition from this routing file.

`FORWARD_MARKET_OBSERVABILITY_V1` remains available as infrastructure; authoritative collection is not started by this cleanup. B2-06 remains blocked.

## Authority order

1. `docs/CURRENT_RESEARCH_STATE.md`
2. `docs/PROJECT_STATUS.md`
3. `docs/RESEARCH_ROADMAP.md`
4. frozen prereg/result artifacts for the experiment being reproduced
5. `docs/RESEARCH_LEDGER.md`

Historical status text elsewhere must not be mistaken for current authorization.
