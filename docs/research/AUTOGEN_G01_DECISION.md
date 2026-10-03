# AUTOGEN_G01 — autonomous research generation 1: owner decision and program record

**Status:** `OWNER_AUTHORIZED / IN_PROGRESS`
**Date:** 2026-10-03
**Search family:** `SF-AUTOGEN-G01`
**Branch:** `research/autonomous-generation-g01`, from `main` at `a7d738f`
**Owner instruction (2026-10-03, intent):**
- act as an autonomous Signalbot research agent;
- generate new hypotheses from the research map;
- red-team, dedupe and run an outcome-blind feasibility pass;
- freeze and execute once only the survivors, then classify.

The full lifecycle is authorized within the rules below.

## 1. What this decision changes and what it does not

**Override.** `NEW_RESEARCH_PROGRAMS_AUTHORIZED = false`, set by `PRODUCT_FIRST_DECISION_V1` and restated after R03 and after the divergence line, is overridden by the owner for **this program only**. This follows the `OWNER_CARDS_R03_DECISION.md` precedent. Nothing earlier is rewritten.

**Product-serving and small.** The program stays within `PRODUCT_FIRST_DECISION_V1` §1 as far as it can:
- every surviving hypothesis is a `CONTEXT_DESCRIPTIVE` claim about calibration of the briefing's baselines;
- feasibility is decided before any outcome;
- no product code changes.

**Unchanged:**
- the predictive-claims freeze, V3, E1-RUN-001 and B2-06;
- the sealed 2025/2026 surfaces, including the six-symbol divergence surface, which is not used here;
- the closures of the divergence / selling-exhaustion line and of R03;
- Generator V0 live-run status (no LLM or API call is made).

## 2. Research map at the start (from the source of truth on `main`)

### Tested and closed

| Status | Units |
|---|---|
| `NO_EVIDENCE` | MARKET-01, -02, -05, -06 |
| External reproduction only | MARKET-03 |
| Blocked observable | MARKET-04 / 04H |
| Closed without promotion | H01–H05 and B2-01..04 |
| Archived | B2-05 |
| Blocked, not negative | B2-06 |
| `NO_USEFUL_STRUCTURE` | D3, D4-rolling, D5, D9, D10, D13 |
| Deferred | D1, D4 lead-lag, D6, D8 |

**Discovery prototypes, none supported:** D2 (BitMEX-replicated, decomposition consumed), D7, D11, D12 and GV0R01-C013.

**Closed programs:**
- OWNER_CARDS_R03: six hypotheses `NO_INCREMENTAL_STRUCTURE`, six `INFORMATIONALLY_WEAK`;
- the divergence / selling-exhaustion line (closed 2026-10-03);
- GV0V03L40 C033 (`DEFINITION_INCOMPLETE`) and C025-R1 (`INFORMATIONALLY_WEAK`).

**Generator signatures without scientific status:** GV0R01 and GV0V03L40 hold about 50 consumed mechanism signatures. Most are blocked for data, confounding or lookahead.

### Exhausted or forbidden neighbourhoods

These come from `HETEROGENEOUS_FAMILY_ROTATION_V3` and the closures:
- **A:** RV-threshold children of D2.
- **B:** BTC own-state → short-horizon scalar; OI continuation; external scalar → 24h MAE.
- **D:** BTC–ETH two-asset relatives.
- **E:** IMPACT_PROXY children of D7; book liquidity is in cooldown.
- **G:** FOMC/CPI/NFP copies; D8 weakening; settlement expiries (R03-A).
- **H:** D9 share variants; D13 momentum/reversal relabels; R03 breadth states.
- **J:** D12 DST and hour-slice neighbours; R03 sessions, including the weekend narrowing (no rescue).
- **Lines:** divergence, support and exhaustion.

### Not yet tested and data-feasible

- the day-of-month cash-flow clock (turn of month, month-end marks);
- ETF-era scheduled reference-rate fixing (US spot ETF NAV window).

Neither appears in any ledger, memory or generator record.

### Authorized data

- `CORE_BTC_BINANCE_V0`: 1m, 2020-01..2024-12;
- `D2_BITMEX_PRE2020_XBTUSD`: 5m, 2016-05..2019-12, the historical replication surface;
- the pinned calendars (NYSE, US OPM, CN State Council), which cover 2020–2024;
- the Sprint04 spot panel 2019-12..2024-12 is authorized, but no surviving card uses it.

### Forbidden or sealed

- E1-RUN-001;
- every 2025/2026 object, including the opened divergence surface, which is not authorized for unrelated families;
- B2-06 OI/funding;
- the divergence program's OI metrics, never used outside that program and treated as not authorized here;
- product telemetry;
- prospective surfaces.

## 3. Pipeline (existing; no new process)

1. **Inventory.** `AUTOGEN_G01_CANDIDATES.{md,json}` holds generation, red team and dedupe, written before any data read.
2. **Feasibility, outcome-blind.**
   - Unit counts come from timestamps and calendars only.
   - Planning objects follow `GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1`.
   - They are compiled under `GV0R02_SCHEMA_V2 / POLICY_V2` with the R03 extended registry (imported, unchanged).
   - A paired-unit power screen runs at the card's Holm first-step alpha.
   - A hypothesis that fails is closed and never executed.
3. **Freeze.** It covers the twin preregistration, the frozen unit sets with digests, the bound code digests (including the imported R03 inference module) and the execution permit. It is committed before any outcome.
4. **One-shot execution and classification** under the frozen rules, with BitMEX 2017–2019 replication only for discovery prototypes whose card declares it.
5. **Records.** `SCIENTIFIC_TEST_LEDGER.json`, `RESEARCH_LEDGER.md` and `CURRENT_RESEARCH_STATE.md` are updated.

## 4. Data decisions

| Dataset | Use | Decision |
|---|---|---|
| `CORE_BTC_BINANCE_V0` 1m 2020-01..2024-12 | discovery targets (trade count, quote volume, range) | pinned inventory `SOURCE_INVENTORY_717d37a4.json`; zips SHA256-verified from the Binance Vision S3 origin; the loader refuses any 2025/2026 URL |
| `D2_BITMEX_PRE2020_XBTUSD` 5m | historical replication of card A | committed canonical file, digest checked against the D2 source authority; fields: OHLC and trade count (no volume) |
| `NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0` | card B trading days (full closures and early closes excluded) | committed, pre-announced events only |
| Fixed-date holiday windows | card A exclusions: Dec 24–Jan 2 and Oct 1–7 | a deterministic date rule, identical on both surfaces (the pinned calendars do not cover 2017–2019) |
| 2025/2026, B2-06, divergence OI metrics | **not used** | not research-authorized for this program |

## 5. Stop conditions honoured

The program stops a card, rather than ask, if it would need any of the following:
- a new protected surface;
- a lower bar;
- a changed inference class after outcomes;
- product telemetry;
- an API spend;
- a production change;
- a merge or deploy;
- ambiguous provenance.

## 6. What this record does not claim

No market outcome was computed when it was written. Nothing here is a trading edge, a direction or a cause.
