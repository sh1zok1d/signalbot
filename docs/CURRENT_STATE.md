# Signalbot — Current State

**Status:** `ACTIVE SUMMARY` (a pointer document; it is not an authority)
**As of:** 2026-09-29
**Posture:** `RESEARCH_FIRST / DESCRIPTIVE_PRIVATE_BETA_V0_AUTHORIZED / PREDICTIVE_PRODUCT_FROZEN`

This page answers "where are we now?" in one screen. It restates facts recorded elsewhere and adds no new decisions. If this page ever disagrees with the documents below, they win:
- `CURRENT_RESEARCH_STATE.md`: canonical routing and the exact next research unit.
- `PROJECT_STATUS.md`: posture and freeze.
- `RESEARCH_LEDGER.md`: consumed windows and results.
- `PRIVATE_BETA_V0_RESTART_DECISION.md`: beta governance.

## 1. Headline

**Signalbot has no validated trading edge.** No result in this repository establishes direction prediction, profitability, a trading edge, or information beyond current volatility.

## 2. Active research stage

- **Research routing.** The latest entry in `CURRENT_RESEARCH_STATE.md` is the GV0R03 generator feasibility contract (2026-09-25), with `NEXT_UNIT = NONE_AUTHORIZED_AFTER_GV0R03_CONTRACT`. No new research unit is authorized by that routing.
- **Generator V0.**
  - The first 30-card campaign GV0R01 is sealed and memory-finalized.
  - C013 is a discovery-tier `PROMISING_PROTOTYPE` whose confirmation is deferred for low power.
  - C012, C004 and C020 closed outcome-blind as informationally weak or with insufficient inference support. They are the golden cases of the GV0R02 feasibility compiler.
- **MARKET program.** MARKET-01, -02, -05 and -06 ended `NO_EVIDENCE`. MARKET-03 is an external reproduction only. MARKET-04/04H is blocked on an observable and was not tested. Internal historical candidates promoted: `0`.
- **Discovery.** D2 is an `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`. Its excess path-risk decomposition is consumed with the result `D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`. D7, D11 and D12 are discovery-tier `PROMISING_PROTOTYPE`s. None of them is a validated edge.

## 3. Beta PRICE_OI_CONTRACTION historical follow-up (P4) — descriptive only

**Where the figures come from.**
- An owner-run semantic replay applied the current `PRICE_OI_CONTRACTION` rules to live-collected raw data.
- Provenance class: `RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA`. This is a reconstruction under current rules, not a record of historical production alerts.
- The replay tooling is on the unmerged draft PR #227 (`scripts/audit/live_archive_replay_preflight/`). The follow-up read model is on the unmerged PR #225 (`beta/followup.py`).
- The replay output itself is not committed. The figures below are the owner-reported results of that run.
- `AUTHORIZED_BUCKETS = 12434`. This matches `quorum_and_mature_buckets` in `docs/audit/live_archive_replay_preflight/phase_a_coverage_analysis.json` on the PR #227 branch.

| | DOWN | UP |
|---|---|---|
| Episodes reconstructed | 277 | 223 |
| Triggered | 25 | 19 |
| Follow-up eligible | 22 | 17 |
| Distinct UTC dates | 17 | 12 |
| Event median realized range, 1h | 0.9280488526070928 % | 1.3288664266566295 % |
| Event median realized range, 4h | 1.5765374076858096 % | 2.09441932438176 % |
| Ordinary same-time baseline, 1h | 0.31225251980032437 % | 0.3374713940875821 % |
| Ordinary same-time baseline, 4h | 0.6508845191856447 % | 0.6888552939953104 % |

**What this shows.** In this archive, realized range after triggered PRICE_OI_CONTRACTION states was larger than at ordinary same-time-of-day anchors. That is all it shows.

**What it does not show.**
- Direction prediction: `realized_range_pct` has no sign.
- Profitability or a trading edge.
- Information beyond the volatility that already existed at the event. The ordinary baseline is not an incremental-information test.

**The frozen matched-baseline design is not valid evidence.** Its known defects are:
1. The ±4h control exclusion around episodes looks forward. It conditions control eligibility on the future, and it biases the control pool toward calm periods.
2. Matching on prior-1h realized-range terciles is too coarse.
3. It has no adequate control for the recent price move that defines the event.

No matched-baseline figure should be quoted. A revised protocol has not been designed or implemented.

## 4. What is proven and what is not

**Proven**, in the sense of engineering correctness under tests:
- deterministic replay and provenance identities;
- no-lookahead bucket semantics;
- the `EVENT_COMPARABILITY_V0` identity and the follow-up read-model mechanics (PR #225, unmerged).

**Not proven:**
- any trading edge;
- any directional or predictive claim;
- that beta event states carry information beyond current volatility;
- durability across regimes. The live archive covers about 2.5 months, from 2026-07-17.

## 5. Next research step (high level)

There is no authorized next unit in the research routing (see §2). For the beta PRICE_OI follow-up, any further inference first needs a revised matched-baseline protocol that fixes the three defects in §3. It must be designed and reviewed before it is implemented or run. It is not authorized by this page.

## 6. Product validation status

- **Predictive product:** frozen.
- **Descriptive private beta V0.2:** authorized with narrow scope (`PRIVATE_BETA_V0_RESTART_DECISION.md`). Its code and units live only in `beta/`, `runtime/beta_*`, `storage/beta_v0_*`, `config/beta_v0.yaml` and `deploy/signalbot-beta-*`.
- **Last recorded state** (`PROJECT_STATUS.md`): implemented, push disabled, no users. The next operator step is the 7-day push-disabled shadow soak. This page did not verify runtime state.
- **Historical follow-up:** not wired into `/btc` (`BETA_HISTORICAL_FOLLOW_UP_V0.md` on PR #225).

## 7. Protected-data posture

- Binance 2025/2026 remain **sealed**. Opening them requires explicit owner authorization.
- Binance 2020–2024 is the discovery surface. BitMEX 2016–2019 is a historical replication surface.
- Binance-only history is a different detector identity from the three-venue beta detector. It must not be mixed into beta follow-up statistics.
