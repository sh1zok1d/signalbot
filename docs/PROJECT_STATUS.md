# Signalbot — Current Project Status

**Status date:** 2026-09-22 (routing pointer updated 2026-09-29; product-first decision 2026-10-02)
**Operating mode:** `PRODUCT_FIRST / RESEARCH_SERVES_PRODUCT / PREDICTIVE_CLAIMS_FROZEN` (since 2026-10-02, `docs/PRODUCT_FIRST_DECISION_V1.md`). The earlier mode `RESEARCH_FIRST / DESCRIPTIVE_PRIVATE_BETA_V0_AUTHORIZED / PREDICTIVE_PRODUCT_FROZEN` is historical.
**Active phase:** see `docs/CURRENT_RESEARCH_STATE.md`. As of 2026-09-29 its latest entry is the GV0R03 generator feasibility contract, with `NEXT_UNIT = NONE_AUTHORIZED_AFTER_GV0R03_CONTRACT`. The earlier phase `POST_SPRINT03_DISCOVERY_PROGRAM_DECISION` is historical.

This file is intentionally concise. The pre-cleanup long-form status remains immutable in git at `b25d9ca99498630183813d0ccb8c6d67b93ad915`; experiment history remains in `docs/RESEARCH_LEDGER.md`.

## Current decision (2026-10-02)

**Product-first.** The canonical product decision is `docs/PRODUCT_FIRST_DECISION_V1.md`. It fixes the product hypothesis (a Russian-language market briefing that compresses "what happened, who dominates, how unusual"), the build-to-test MUST scope, the architectural constraint (one detector, one episodization, one context projection, one shared view builder, one outbox, one notifier), the DO-NOT-BUILD-YET list, the data maturity orientation (V2 tape since 2026-10-01; baselines about 2026-10-21; full 30d ranks about 2026-10-31) and the 30-day user test with its decision rules.

Research infrastructure is kept and research serves the product: only small, feasibility-confirmed units; no new programs, no new one-shot confirmations, no research surface widening for the hope of an edge. Signalbot still has no validated durable trading edge and makes no predictive claim.

The research conclusion below stays recorded: the program stopped repeating nearby “new observable -> short-horizon scalar BTC prediction” formulations. Research routing: `docs/CURRENT_RESEARCH_STATE.md`.

## Descriptive private beta V0.2 (2026-09-25)

A narrow descriptive private beta is authorized by `docs/PRIVATE_BETA_V0_RESTART_DECISION.md`. It covers BTCUSDT perp on Binance, Bybit and OKX, runs on Telegram, is capped at 20 users and uses deterministic `BETA_EVENT_RULES_V1`.
- **What it is:** a descriptive attention engine only. It carries no predictive claim, no trade instruction and no edge claim.
- **What stays frozen:** predictive product work, and the V1 and V2 semantics.
- **Current state (2026-10-02):** V0.2 ran for the owner only; the owner judged the 5m event feed unactionable (`CHANGE PRODUCT`). No external users yet. The implementation scope is now the build-to-test MUST list of `docs/PRODUCT_FIRST_DECISION_V1.md` §3; `BETA_V0_3_MARKET_BRIEFING.md` is superseded where it differs (briefing episodes, 24h label, 90-day baselines, separate notifier).
- **Next step:** build the MUST scope; external launch follows data maturity (§6 of the decision), then the 30-day user test (§7).
- **Research boundary:** beta events are not hypotheses, and beta outcomes are not confirmation.

## Current evidence

- V3 calibration closed; methodology not generally claimable; no V4.
- MARKET-01: `NO_EVIDENCE`.
- MARKET-02: `NO_EVIDENCE`.
- MARKET-03: external historical reproduction `REPRODUCED_DIRECTION`; not internal validated alpha/OOS.
- MARKET-04 / 04H: blocked by historical observable/provenance; not scientifically rejected.
- MARKET-05: `MARKET_05_NO_EVIDENCE`.
- MARKET-06: `MARKET_06_NO_EVIDENCE`; exact one-shot RESULT sealed at `80c7d19f622cc7b5576154de59dbb9cdf85d4dcf`; rerun forbidden.
- Internal historical candidates promoted: `0`.
- Protected 2025/2026 OOS: unopened.

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
