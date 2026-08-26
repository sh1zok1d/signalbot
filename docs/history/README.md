# Signalbot — Historical Archive Index

**Status:** ACTIVE HISTORY INDEX  
**Purpose:** make earlier project phases directly browsable without restoring obsolete plans as current authority.

This directory is the bridge between the concise current tree and the repository's immutable historical snapshots.

The current project direction is defined by `../PROJECT_STATUS.md` and `../RESEARCH_ROADMAP.md`.  
The narrative explanation of how Signalbot evolved is `../PROJECT_HISTORY.md`.

---

## Why this archive exists

Signalbot changed direction several times for evidence-driven reasons. Old plans are valuable because they show:

- what the project believed at a given time;
- what was actually built;
- what assumptions were frozen;
- what later evidence contradicted or weakened them;
- why the next architectural decision was made.

At the same time, leaving every old roadmap in the active tree at full length created a second problem: a new reader or coding agent could mistake an obsolete Stage-6/7/8 plan for today's work.

The cleanup therefore uses this rule:

> **Keep current authority short and unambiguous; keep historical meaning directly discoverable and immutable.**

Some old paths now contain a short `SUPERSEDED/HISTORICAL` pointer. Their complete pre-pivot contents are linked below.

---

## Immutable pre-pivot snapshot

The main historical snapshot immediately before the 2026-08-26 research-first cleanup is:

`a9c383355690c5ab9bcc577454da3ebec75d8d89`

It contains the complete V2-era documentation exactly as it existed before the project changed direction.

[Browse the full repository at the pre-pivot snapshot](https://github.com/sh1zok1d/signalbot/tree/a9c383355690c5ab9bcc577454da3ebec75d8d89)

---

## Phase 1 — Data-platform origin

Signalbot first focused on trustworthy acquisition/storage before forecasting.

Historical reading:

- [Stage 1 acceptance](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/STAGE1_ACCEPTANCE.md)
- [Stage 2 specification](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/STAGE2_SPEC.md)
- [Stage 2 clarifications](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/STAGE2_CLARIFICATIONS.md)
- [Stage 2 data audit](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/STAGE2_DATA_AUDIT.md)
- [Stage 2 implementation plan](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/STAGE2_IMPLEMENTATION_PLAN.md)

What survived this phase into the current philosophy:

- no-lookahead/as-of discipline;
- provenance/version identity;
- explicit missingness;
- source granularity awareness;
- deterministic storage/replay.

---

## Phase 2 — V1 shadow forecasting

V1 was the first working forecasting/shadow baseline. It combined a closed 5m market state with price/flow/derivatives/cross-exchange components and produced LONG/SHORT outputs.

The important historical lesson is not merely that V1 underperformed expectations. Its later autopsy showed that the project had confused a reactive short-term state classifier with a longer-horizon forecasting product.

Current narrative summary: `../PROJECT_HISTORY.md` §3.  
Current experiment/diagnostic record: `../RESEARCH_LEDGER.md`.

V1 code is retained under `analytics/forecasting/` as a `FROZEN_BASELINE`; see `../CODEBASE_STATUS.md`.

---

## Phase 3 — V2 multi-timeframe architecture

V2 attempted to solve V1 weaknesses with explicit timeframe roles, setup families and a formal lifecycle/product contract.

Complete historical documents:

- [Forecasting roadmap](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/FORECASTING_ROADMAP.md)
- [V2 product contract](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/V2_PRODUCT_CONTRACT.md)
- [V2 correctness acceptance contract](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md)
- [Project execution plan](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/PROJECT_EXECUTION_PLAN.md)
- [Project strategy / architecture principles — V2-era version](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md)
- [Project risk/debt register — V2-era version](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/PROJECT_RISK_AND_DEBT_REGISTER.md)
- [Product specification V0](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/PRODUCT_SPEC_V0.md)
- [Product hypotheses — pre-pivot version](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/PRODUCT_HYPOTHESES.md)

These files explain why V2 became so formal and where much of the current correctness infrastructure came from. They are not current implementation authorization.

---

## Phase 4 — Empirical red-team / falsification turn

As V2 matured, the project explicitly separated engineering correctness from predictive validity.

Historical reading:

- [V2 empirical red-team plan](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/V2_EMPIRICAL_RED_TEAM_PLAN.md)
- [Consensus robustness historical audit](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md)
- [Percentile maturity audit](https://github.com/sh1zok1d/signalbot/blob/a9c383355690c5ab9bcc577454da3ebec75d8d89/docs/V2_PERCENTILE_MATURITY_AUDIT.md)

This phase introduced the durable idea that **correctness is necessary but cannot be promoted into evidence of alpha**.

---

## Phase 5 — E1-RUN-001 detector separation

Before building more lifecycle architecture, E1 asked whether frozen Stage-5 detector qualifications changed future outcome distributions relative to simple/matched controls.

Unlike superseded product plans, the E1 files in the current tree remain **frozen experiment records** and should be read directly rather than through old snapshots:

- `../E1_DETECTOR_SEPARATION_PREREG.md`
- `../E1_DATA_INVENTORY_2026-08-25.md`
- `../e1/`
- `../RESEARCH_LEDGER.md`

Development evidence materially weakened parts of the V2 thesis; the final chronological holdout remained unopened at the research-first pivot.

Do not rewrite these files to make the historical experiment agree with later project philosophy.

---

## Phase 6 — 2026-08-26 research-first pivot

The current pivot was driven by two converging observations:

1. E1 development evidence did not justify automatically building more V2 complexity;
2. the richest fully overlapping historical sample was roughly one month, far too short to establish durable edge across regimes.

The new order became:

`DATA -> HYPOTHESIS -> FALSIFICATION -> DEVELOPMENT -> FREEZE -> OOS -> EDGE -> ARCHITECTURE -> PRODUCT`

Current reading:

- `../PROJECT_STATUS.md`
- `../RESEARCH_ROADMAP.md`
- `../EDGE_RESEARCH_PROTOCOL.md`
- `../HISTORICAL_DATA_STRATEGY.md`
- `../ACTIVE_RESEARCH_RISKS.md`
- `../PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md`
- `../CODEBASE_STATUS.md`

---

## Historical interpretation rules

When reading an old document:

1. treat its claims/plans as belonging to its historical phase unless a current canonical doc explicitly carries them forward;
2. do not silently edit old preregistration/result artifacts to match later knowledge;
3. distinguish “we believed/planned this” from “the data later supported this”;
4. a superseded architecture can still contain valuable engineering ideas;
5. a failed hypothesis remains useful evidence about what not to assume next time.

For current-vs-historical authority rules, see `../DOCUMENTATION_INDEX.md`.
