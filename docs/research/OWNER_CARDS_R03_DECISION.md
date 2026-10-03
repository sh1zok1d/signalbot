# Owner cards R03 — owner decision and program record

**Status:** `OWNER_AUTHORIZED / EXECUTED_ONCE / CLOSED` (result: `OWNER_CARDS_R03_RESULT.md`; six executed, all `NO_INCREMENTAL_STRUCTURE`; six closed at feasibility)
**Date:** 2026-10-03
**Search family:** `SF-OWNER-CARDS-R03`
**Owner instruction (2026-10-03, verbatim intent):** author three cards of four hypotheses each, oriented by the map of already-tested families; test them; freeze the viable ones under the existing plan; execute.

## 1. What this decision changes and what it does not

- `NEW_RESEARCH_PROGRAMS_AUTHORIZED = false` in `CURRENT_RESEARCH_STATE.md` was set by `PRODUCT_FIRST_DECISION_V1`. The owner's 2026-10-03 instruction is an explicit owner override for **this program only**. It is recorded here and at the top of `CURRENT_RESEARCH_STATE.md`; nothing earlier is rewritten.
- The program serves the product: every hypothesis is a `CONTEXT_DESCRIPTIVE` claim about the range of a scheduled or calendar-defined window relative to an ordinary-conditions comparator. That is the kind of statement the beta briefing makes (unusual hours against a same-hour baseline). No hypothesis is directional, none is a trade, none sets a threshold.
- Unchanged: the predictive-claims freeze, V3, E1-RUN-001, B2-06, the sealed 2025/2026 surfaces, the divergence-line closure, Generator V0 live-run status.

## 2. Pipeline (existing; no new process)

1. Cards and hypotheses are author-written planning objects under `GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1` (no LLM generator run).
2. Outcome-blind count pass and `GV0R02_SCHEMA_V2` compile for all twelve (`scripts/research/owner_cards_r03/support.py`). A hypothesis that the compiler or the paired-unit power screen rejects is closed as `INFORMATIONALLY_WEAK` and never executed.
3. Twin preregistration (`OWNER_CARDS_R03_PREREG.md/.json`), freeze with SHA256 digests of code, planning, feasibility and unit sets, and an execution permit committed before any outcome.
4. One one-shot (`execute.py`): discovery on Binance 2020-2024; BitMEX 2017-2019 replication for discovery prototypes whose card declares it. RESULT written once. No rerun.
5. Ledger (`SCIENTIFIC_TEST_LEDGER.json`), `CURRENT_RESEARCH_STATE.md`, `RESEARCH_LEDGER.md`, `DOCUMENTATION_INDEX.md`.

## 3. Data decisions

| Dataset | Use | Decision |
|---|---|---|
| `CORE_BTC_BINANCE_V0` 1m, 2020-01..2024-12 | discovery target and nuisance | pinned inventory, SHA256-verified; raw restored from the Binance Vision S3 origin |
| `D2_BITMEX_PRE2020_XBTUSD` 5m, 2017-01..2019-12 | historical replication for cards A and C | committed canonical file, digest verified against the D2 source authority. Hour ranges from 5m highs/lows are the same quantity as from 1m |
| `SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0` 2019-12..2024-12 | card B states (panel closes and quote volumes up to T) | frozen object ledger, every zip SHA256-verified |
| `NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0` | card C exclusions and the closure-day hypothesis | committed, pre-announced events only |
| `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` | **not used** | the snapshot is `SNAPSHOT_MATERIALIZED_NOT_RESEARCH_AUTHORIZED`; funding publication latency is unproven; B2-06 stays blocked. A positioning card was dropped rather than open that dataset under a general instruction |
| 2025/2026 | **not opened** | no object with a 2025 or 2026 month is selected by any loader; panel replication is prospective from 2027-01-01 |

The GV0R02 feature registry derived from `MANIFEST.json` files does not name the panel or the BitMEX file, although both have frozen ledgers. Rather than add manifests (which would change the frozen registry digest that earlier compiler goldens pin), `support.py` passes the compiler an **extended registry**: the frozen registry plus two rows built from the existing ledgers. The extended digest, the frozen digest it extends, and the two row ids are recorded in `OWNER_CARDS_R03_FEASIBILITY.json`. No earlier result is rescored and no ledger byte changes.

## 4. Family rotation (why these three)

Taken from `HETEROGENEOUS_FAMILY_ROTATION_V3` and the Sprint 04 close:

- **R03-A, family G (event response).** Scheduled derivative settlement. Not FOMC/CPI/NFP (D11 copies are forbidden), not D8. Deribit and CME settlement hours are calendar-defined and were never tested; S4-C05 was a pool candidate, not selected.
- **R03-B, family H (true cross-sectional panel).** D13 tested relative-return momentum (null); D9 tested two-venue share (null). Breadth, dispersion, volume-shock fraction and BTC share are different mechanisms on the same frozen panel; S4-C03 was a pool candidate, not selected.
- **R03-C, family J (participant clock).** D12 found a US-clock profile shift (prototype). R03-C asks about session structure (weekend, Monday US open, NYSE closures, Friday US close) with range as the target, which D12 did not test; S4-C10 was a pool candidate, not selected.

Anti-rescue rules observed: no RV threshold/window child (A/D2), no IMPACT_PROXY child (E/D7), no SHARE variant (H/D9), no FOMC child (G/D11), no external scalar to 24h MAE (B/MARKET-05/06), no momentum/reversal relabel (H/D13).

## 5. Rules fixed before any count

- Effect bar 0.5 comparator-SD of standardized log range, one bar for all twelve, product-relevance rationale in `constants.py`.
- Inference: sign-flip over time-separated units, two-sided; Holm within each card over the hypotheses that pass feasibility; epochs are calendar years; the nuisance diagnostic (prior RV, lagged target, time of day by construction) decides the wording, never the gate.
- Replication: BitMEX 2017-2019 for A and C (same frozen rule); the panel card is prospective from 2027-01-01 with a fixed stopping rule.
- A closed hypothesis is not re-scored, re-thresholded or re-horizoned. A later variant is a new search object.

## 6. What this record does not claim

No market outcome was computed when it was written; the outcome is in `OWNER_CARDS_R03_RESULT.md`. Nothing here is a trading edge, a direction, or a cause.
