# RANGE_POSITION_4H on Binance 2025–26 — exposure audit V1 (before freeze; no outcome read)

**Date:** 2026-10-09.
**Question:** Q = `RANGE_POSITION_4H → R_1H` (DIRECTION, 1h), and its partial given `RET_4H`, `RV_4H`.
**Surface:** S = Binance USD-M BTCUSDT perpetual, 2025-01-01 … 2026-10-08, minus the E1-RUN-001 holdout.
**Rule:** `RESEARCH_RULES_DECISION_V1.md` §3.
**Method:** a read-only audit of every recorded read of S (records, code, ledger). Nothing was computed or downloaded.

## Verdict

**S as a whole is not `QUESTION_FRESH_REPLICATION` for Q.** One recorded read is an **exact-class** exposure: **E1-RUN-001 development, `CB_ORDINARY_RANGE_BREAKOUT`**.
- **What it computed:** direction-aligned returns at +15m … +4h after a fresh 5m close beyond the max high / min low of the previous 16 closed 15m buckets (a trailing 4h range), on live Binance BTCUSDT perp `klines_1m`.
- **Where:** decisions [2026-08-02T00:00Z, 2026-08-15T20:00Z], outcomes read to 2026-08-16T00:00Z. 149 rows, adverse at every horizon.
- **Records:** `docs/e1/E1_RUN_001_DEVELOPMENT_ABLATIONS.md`; `scripts/research/v2_e1_development_ablation_inventory.py`; `analytics/forecasting_v2/alignment.py`.
- **Why it is exact-class:** it is a threshold/subgroup of RP4H (the top or bottom of the trailing 4h range) with an overlapping horizon. `CB_FULL` / `CB_SIMPLE_COMPRESSION_BREAKOUT` on the same slice is a window-neighbour equivalent.

**Decision, recorded before freeze:** the slice [2026-08-02T00:00Z, 2026-08-16T00:00Z) is **cut at the object level**.
- The daily objects 2026-08-02 … 2026-08-15 are never requested.
- Together with the product's E1 refusal of 2026-08-16 … 2026-08-25, no daily object dated 2026-08-02 … 2026-08-25 is requested.
- Anchors that need those bars drop as missing.

**Outside the cut,** S is question-fresh for Q but not pristine. No other read conditioned on RP4H or an equivalent.

## Reads of S

| # | Read | Conditioned on | Outcome | Class |
|---|---|---|---|---|
| 1 | E1-RUN-001 development, CB ordinary range breakout (2026-08-02 … 08-15) | fresh close beyond the trailing 16×15m high/low | DIRECTION 15m–4h | **EXACT** → cut |
| 2 | E1 CB_FULL / CB simple compression breakout (same slice) | cross of a 1.5–4h compression range | DIRECTION 15m–4h | EXACT-class → cut |
| 3 | E1 FB 48h breakout, trend pullbacks (same slice) | 48×1h high/low; pullback from the 12h extreme | DIRECTION 15m–4h | ADJACENT (inside the cut) |
| 4 | V1 Telegram shadow autopsy 2026-07-25 … 08-25 | V1 5m momentum signals | short-horizon direction | ADJACENT (signed recent return) |
| 5 | Product `analogue_stats`, 2020 → yesterday | signed 1h/4h move rank bands, OI, taker, width | P(up) and median at 1h/4h/24h | ADJACENT (Q's nuisance) |
| 6 | Product `level_reaction_stats` | first touch of PDH/PDL/PWH/PWL/PMH/PML, round numbers, previous-day POC | hold/further/back at 1h/4h | ADJACENT |
| 7 | Product `distance_reaction_stats` | touch of a level d % from an hourly close | hold at 1h/4h | ADJACENT (weak) |
| 8 | LEVEL_RACE_FORECAST_V1 held-out read, 2025-01 … 2026-10-08 | structural first touches; B0 start position; σ | LEVEL_RESOLUTION 4h | ADJACENT |
| 9 | Same read: generic stream, 60,919 rows | σ only, barrier pairs | 4h up/down first | UNRELATED (unconditional) |
| 10 | P3_CONFIRMATION_V1 | crowd z; nuisance includes the signed prior-4h return and TREND24 terciles | UP_FIRST_4H, trading translation | UNRELATED state; ADJACENT internal fit of a signed 4h-return nuisance |
| 11 | Architect's disclosed unconditional read | nothing | 4h first passage; \|4h return\| | UNRELATED |
| 12 | DIVERGENCE_FULL_HISTORY_V0 validation (to 2026-08-15) | swing lows; depth from the 48-bar high; RSI/CVD/book | 1R brackets at 48h/96h | ADJACENT (horizon outside the class) |
| 13 | Product rangecast and its touch calibration | past log ranges (4h width = RP4H's denominator) | RANGE_VOL | UNRELATED |
| 14 | Event-day sizes, sharp-move threshold, OI 24h | events, \|15m\| | RANGE_VOL / ACTIVITY | UNRELATED |
| 15 | P4 follow-up, live 2026-07-17 → 09-29 | PRICE_OI_CONTRACTION | realized range 1h/4h | UNRELATED |
| 16 | Live claim journal and tracker | analog, level hold, race, touch | various | ADJACENT; touch unconditional; no scored cohort in the repo |
| 17 | Research-evidence live matching | states only | none | UNRELATED |

**Discovery chain check.** The discovery (`PRE_IMPULSE_STATE_ATLAS_V1`) and the Bybit successor read no bar at or after 2025-01-01. Their constants refuse it, and their ledgers record `OBJECTS_2025_2026_USED = none`. Unit A read BitMEX only.

## Special windows on S

| Window | Status | Rule in Unit B |
|---|---|---|
| E1-RUN-001 holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` | RESERVED (pristine status `INVALIDATED_FOR_P4_OVERLAP`) | **Excluded.** The product guard (`beta.history_data` `PROTECTED_WINDOWS`, `url_refusal`, `drop_protected`) refuses every overlapping object before any request: the monthly 2026-08 and the daily 2026-08-16 … 08-25, the 25th whole. It is opened only with a separate owner approval, never after a result. |
| E1-RUN-001 development slice `[2026-08-02, 2026-08-16)` | exact-class exposure of Q | **Excluded** (this audit) at the object level, with the same fail-closed pattern |
| P3 hard stop 2026-08-15; divergence read horizon 2026-08-15; P4-exposed window `[2026-07-17T19:30Z, 2026-09-29T04:00Z)` | boundaries of other units | not exposures of Q; disclosed |

## Corrections to earlier records
- The withdrawn `RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1_DESIGN.md` said "RANGE_POSITION never read" on RECENT. That was inaccurate: E1 development read an exact-class equivalent on 2026-08-02 … 08-16.
- The Unit B draft omitted E1 development and the V1 autopsy.
- `EXPOSURE_COUNTERS_V1` attributed the E1 development cells to "Live forward 2026". Under §3 (same venue and period) they belong to BINANCE_PERP_BTC_2025_2026 × DIRECTION.
