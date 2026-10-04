# Research evidence integration V1

**Status:** IMPLEMENTED and merged to `main` (PR #326, merge `423b9b8`; owner task, 2026-10-04). Not deployed; the feed units are not enabled. Deploy plan: `docs/RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md`.

**Owner authorization:** the task "INTEGRATE ALL RESEARCH EVIDENCE INTO LIVE MARKET ANALYSIS" (2026-10-04).
- It authorizes **read-only, free, public** market-data collectors and derived features when a closed research unit needs them for live matching.
- **No** order-book heatmap or UI, **no** exchange keys, **no** execution, **no** second detector engine.
- **No** new research campaign, **no** P3 prospective confirmation, **no** deploy.

**What it is.** A product integration of results that already exist. No verdict changes and no study is reinterpreted. The bot recognises, from live data, the frozen state of each live-relevant closed research unit. It then states what the research found after such states, in the wording its status allows.

**What it is not.** It is not a change of:
- the corridor, the touch probabilities or the tracked forecasts;
- detector thresholds, episode rules, push triggers or gating.

## 1. Audit (Phase A)

**Sources:**
- `config/beta_research_findings.yaml`: 40 findings;
- the atlas (`docs/research/atlas/ATLAS_UNITS_V1.yaml`, 187 units);
- `docs/RESEARCH_LEDGER.md`;
- the DH1/DH2/DH3, D-series, H-series, MARKET and R03 records;
- the live code: `beta/decision.py`, `market_view.py`, `interpretation.py`, `market_alerts.py`, `levels.py` and the Stage-1 collectors.

**What the bot collected live before this change:**
- Stage 1: perp 1m klines on 4 venues (with Binance taker volume), OI 1m, funding, mark price and liquidations;
- Binance Vision history: 5m klines and OI.

It had no long/short ratio, no DVOL, no order book, no spot and no trade-level data.

**Classes:**
- `ALREADY_SUPPORTED` (AS): the state was recognised and the finding was used;
- `DATA_EXISTS_BUT_NOT_CONNECTED` (NC): the finding was shown without checking its state;
- `DERIVABLE_FROM_EXISTING_DATA` (DV);
- `MISSING_LIVE_DATA` (MD);
- `NOT_PRODUCT_USEFUL` or not live (NL).

| Finding | Status | Live state (frozen definition) | Before | Class | Action | Surfaces |
|---|---|---|---|---|---|---|
| D7 | CONFIRMED | D7 hour (impact > p90) | D7 line; on move alerts H03 always won | AS | matched on the stored D7 state | /btc, move, /risk, Details |
| D2 | CONFIRMED | RV 24h > P90 of the previous 250 valid days (00:05 UTC) | shown on /risk unconditionally | NC | exact RULE_1 matcher | /btc, /risk, brief, /catchup |
| DH3-P3 | DISCOVERY | crowd z (30 days) ≥ q80 / ≤ q20 | — | MD | long/short ratio feed | /btc, brief, /catchup |
| DH3-V3 | DISCOVERY | second touch of PDH/PDL after a retreat ≥ X | — | DV | retest matcher | /levels, /btc, /catchup |
| D11 | DISCOVERY | after FOMC | — | NL | design §9 keeps sizes away from CPI/FOMC | /research |
| D12 | DISCOVERY | the week of a US clock change | — | DV | calendar | brief, /catchup |
| DH3-P1 | WEAK | quiet 4h (≤ q33) and 4h OI change ≥ q67 | — | DV (+ REST tail) | matcher | /btc, /risk, brief |
| DH3-O2 | WEAK | 1h DVOL change ≥ q90 | — | MD | DVOL feed | /risk, /btc |
| DH3-L3 | WEAK | ±1 % book not recovered 30 min after a DH1 sharp move | — | MD | depth feed | /risk, /btc |
| DH3-S1 | WEAK | stress hour led by spot or by the perp (1-second lead score) | — | MD | stress-hour aggTrades | /risk, /btc |
| DH3-V2 | WEAK | first touch of a key level | — | DV | matcher | level alert, /btc |
| R03-C1 | WEAK | weekend | today block | AS | engine | brief, /btc, /risk |
| H03 | NOT_CONFIRMED | 15/30/60-min impulse ≥ q90 of 30 days | on every move alert | NC | exact matcher | move, /btc |
| H02 | NOT_CONFIRMED | failed breakout of the last 1–4h range | on every level alert | NC | exact matcher | /btc, /catchup |
| DH1-L2 | NOT_CONFIRMED | touched level coincides with another (±0.15 %) | generic level context | NC | matcher | level alert, /levels |
| DH2-L1 | NOT_CONFIRMED | approach hour with spot taker flow the same way | — | MD | spot feed | /btc, /catchup |
| DH2-L3 | NOT_CONFIRMED | level not traded for 24h before its touch | — | DV | matcher | level alert, /levels |
| DH3-P2 | NOT_CONFIRMED | 1h OI change ≤ q10 | — | DV | matcher | /risk, /btc |
| DH3-L1 | NOT_CONFIRMED | ±1 % depth ≤ q20 of its 7-day median | — | MD | depth feed | /risk |
| DH3-L2 | NOT_CONFIRMED | log(bid/ask) ±1 % ≥ q80 / ≤ q20 | — | MD | depth feed | /btc |
| DH3-O1 | NOT_CONFIRMED | implied/realized ≥ q67 | — | MD | DVOL feed | /risk |
| DH3-O3 | NOT_CONFIRMED | 24h corr(ΔDVOL, Δprice) > 0 | — | MD | DVOL feed | /btc |
| DH3-V1 | NOT_CONFIRMED | first touch of a session extreme within 24h | — | DV | matcher | /levels |
| DH3-S3 | NOT_CONFIRMED | perp prints ≥ $1M in a stress hour > q67 | — | MD | stress-hour aggTrades | /risk |
| DH2-B2 | NOT_CONFIRMED | DH1 sharp move with spot share above its 24h share | — | MD | spot feed | move, /btc |
| MARKET-02 | NOT_CONFIRMED | 30m impulse ≥ q90, OI > q75, continuation > 0.25 | 1h label only | AS | exact matcher (label kept) | /btc, /catchup |
| MARKET-01 | NOT_CONFIRMED | same, continuation ≤ 0.25 | — | DV | matcher | /btc, /catchup |
| H05 | NOT_CONFIRMED | \|taker imbalance\| 15/30/60 min ≥ q80 of 30 days | — | DV (Stage-1 base taker) | matcher | /btc |
| H04 | NOT_CONFIRMED | trend ≥ q80, 60-min pullback depth 0.1–1 | — | DV | matcher | /btc |
| R03-A1, R03-A4 | NOT_CONFIRMED | Deribit expiry day | today block | AS | engine | brief |
| R03-C2-C4 | NOT_CONFIRMED | Monday US open / Friday US close | — | DV | calendar | brief |
| H01 | SIDE_FINDING | compression label | label line | AS | engine (context) | /catchup, brief |
| DIVERGENCE | NOT_CONFIRMED | bullish divergence at ±5 % book support | generic level context | NL | ±5 % depth cannot be reproduced live (REST ≤ 1000 levels) | /research |
| MARKET-05, MARKET-06 | NOT_CONFIRMED | ETH / OKX spot states | — | NL | the bot shows neither; nothing to refute | /research |
| R03-B2 | NOT_CONFIRMED | altcoin breadth | — | NL | multi-asset scanner forbidden | /research |
| TWAP, DIVERGENCE-RSI | SIDE_FINDING | spot TWAP detector / exploratory RSI | — | NL | not shown | /research |
| C012 | UNDERPOWERED | — | — | NL | excluded by rule | /research |

**Not in the registry** (13 units with an outcome), all NL:
- D3, D4, D5, D9, D10 and D13: discovery-sprint nulls with no trader-language statement;
- B2-01 … B2-04: development only;
- MARKET-03: an external strategy reproduction;
- GV0R01-C013: an altcoin cross-section, so a multi-asset scanner;
- SEED-0001: inconclusive.

About 90 more units closed without any outcome (feasibility, blocked or not selected) and are not live by definition.

```
TOTAL_RESEARCH_FINDINGS = 53 (40 registry + 13 outside it)
LIVE_RELEVANT           = 32
ALREADY_IN_BOT          = 6  (+4 shown without a state check: D2, H03, H02, DH1-L2)
DERIVABLE_NOW           = 11
NEED_NEW_DATA           = 11 (P3, O1-O3, L1-L3, S1, S3, DH2-L1, DH2-B2)
NOT_LIVE_USABLE         = 21 (8 registry + 13 outside it)
```

**Governance check.** No blocker:
- every source is free and public: Binance futures data, depth, aggTrades and klines; Binance spot market data; Deribit DVOL;
- no key and no account endpoint;
- the REST backfill covers at most the last 30 days, so no E1 holdout row (`[2026-08-16, 2026-08-25 17:20)`) is fetched or stored; every feed drops rows inside a protected window before storing them;
- the 2025/2026 Binance metrics files are the product-opened BTC OI metrics (PRODUCT_DECISION_V2 §4).

## 2. Data (read-only feeds, `beta/research_feeds.py`)

| Feed | Source | Table | For | Rule |
|---|---|---|---|---|
| OI hist + global long/short account ratio (5m) | `fapi.binance.com/futures/data/openInterestHist`, `globalLongShortAccountRatio` | `beta_feed_metrics_5m` | P1, P2, P3, MARKET-01/02 | live tail of the Vision `metrics` series; same label, used from label + 5m on |
| Vision `count_long_short_ratio` | existing daily `metrics` objects | `beta_hist_oi_5m.ls_account_ratio` | P3 history | parsed from objects synced from now on |
| DVOL 1h | `www.deribit.com/api/v2/public/get_volatility_index_data` (resolution 3600; the DH3 source) | `beta_feed_dvol_1h` | O1–O3 | closed candles only |
| ±1 % depth | `fapi.binance.com/fapi/v1/depth?limit=1000` | `beta_feed_depth` | L1–L3 | a side counts only if the snapshot reaches 1 % on it; otherwise it is stored as NULL, never as a partial sum |
| Spot 5m klines | `data-api.binance.vision/api/v3/klines` | `beta_feed_spot_5m` | DH2-L1, DH2-B2 | closed bars only |
| Stress hours | perp 1h klines; then `fapi/v1/aggTrades` and `data-api…/api/v3/aggTrades` for stress hours only | `beta_feed_stress_hours` | S1, S3 | 1-second lead score and $1M prints, computed exactly as `scripts/research/dh3/aggtrades.py`; perp requests paced at 1 per second |

**Runtime.**
- `main.py --beta-feeds-once`, every 5 min (`deploy/signalbot-beta-feeds.{service,timer}`).
- `main.py --beta-stress-once`, hourly at HH:02 (`deploy/signalbot-beta-stress.{service,timer}`).
- Health is recorded under `research_feeds`, `research_feeds_definition` and `research_stress_hours`.
- Config: `decision.research_evidence.{enabled, feeds_enabled, stress_hours_enabled, main_surface_max ≤ 2}`.

**Definition check.**
- **What it checks:** the REST tail of OI and the ratio is used only after it matches the Vision rows of the same labels. The check passes at offset 0 with ≥ 100 overlapping labels and ≥ 95 % within a 1e-6 relative difference.
- **Before it passes** (`PENDING`, until the first nightly Vision object with the ratio column): the states that need the tail are unavailable with that reason.
- **If it fails:** the same applies, and the failure is visible in health.

**Frozen cut points.**
- `config/beta_research_cuts.json` is written by `python -m scripts.research.evidence.freeze_live_cuts`. It runs the frozen DH3 feature builders unchanged and records each quantile they compute. No outcome is read.
- A recount with the frozen `cell_rows` reproduces every recorded N, including the state arms: P1 3581/12397, P3 7109/14218, S1 967/4299.
- Live data never recomputes a quantile.

## 3. Engine (`beta/research_evidence.py`)

`evaluate(EvidenceInputs) → {matches, unavailable, not_live, checked}`. Each match is a `ResearchEvidenceMatch` with these fields:
- `finding_id`, `status`, `live_state` (key, arm, live values);
- `matched_at` (the research decision time) and `valid_until` (+ horizon);
- `scope`, `historical_effect`, `comparator`, `sample_size`, `replication_status`, `limitations`;
- `relevance` (STATE_EXACT / CONDITIONAL / CONTEXT) and `interpretation_direction` (SUPPORTS / REFUTES / DESCRIPTIVE);
- `topic` and `mechanism`;
- `provenance` (each source and its as-of time) and `record`.

**Live state functions.** They are in `beta/research_states.py`. `tests/research/test_research_evidence_parity.py` runs them against the frozen research code: DH1 sigma and sharp moves, DH3 window range, retests and aggTrades features, H03 midrank and H02 failed breakouts.

**Rules (owner task §5–§9):**
- **Exact state only.** A missing or stale source becomes `unavailable` with its reason, never evidence.
- **Hierarchy.** CONFIRMED > DISCOVERY > WEAK > NOT_CONFIRMED > SIDE_FINDING. UNDERPOWERED is never live (the registry validator forbids it). A surface shows at most one finding per topic.
- **Veto.** A NOT_CONFIRMED match vetoes every SUPPORTS match of the same mechanism (`vetoed_by`).
- **Wording by status:**
  - CONFIRMED: «Проверено на двух биржах»;
  - DISCOVERY: «Гипотеза (найдено на истории, не подтверждено)»;
  - WEAK: «…эффект есть, но ниже нашего порога значимости»;
  - NOT_CONFIRMED: «Историческая проверка эффекта не нашла»;
  - SIDE_FINDING: «Побочный результат проверки».

  Every line carries its unit id, and the registry context lines are status-worded too. A discovery is never «Проверено».
- **Read-only.** The engine reads the decision block after it is built and never writes into it. A test builds the block with the evidence on and off and compares corridor, levels, touch probabilities, events and analogues. Alert evidence is attached after detection and never read by the push decision (tested).

## 4. Surfaces

| Surface | What | Limit |
|---|---|---|
| /btc | running matches, by the hierarchy | 2 |
| /catchup, briefing | matches of the window, by the hierarchy; these replace the scattered label and calendar lines | 2 |
| /risk | range and calendar-volatility topics | 2 |
| /levels | per zone, the strongest conditional finding ("если цена дойдёт сюда"): retest (V3), session extreme (V1), several levels (DH1-L2), a level untraded for 24h (DH2-L3) | 1 per zone |
| level alert | what is known at the touch: key level (V2), several levels (DH1-L2), untraded for 24h (DH2-L3) | 2, within 8 lines |
| move alert | running matches of the move surface (H03, D7, DH2-B2 when their states hold) | 2, within 8 lines |
| Details «🔬 Исследования» | every running match with comparator, N, replication and limits; vetoed ones marked; the findings that cannot be checked now, with the reason | full |

## 5. Unavailable findings

- **DIVERGENCE:** its ±5 % book support cannot be reproduced live.
- **D11:** around CPI/FOMC the product shows no size (design §9).
- **Conditional at runtime:**
  - L1, L2 and L3 hold only while the 1000-level snapshot reaches ±1 % (reported in health);
  - P1, P2, P3 and MARKET-01/02 need the REST tail; until the definition check passes, only the Vision history (up to yesterday) is usable.

## 6. MODEL_INTEGRATION_CANDIDATES (owner decision; nothing changed)

| Finding | Expected use | Model to change | Validation needed |
|---|---|---|---|
| D2 | a wider 24h swing after a D2 day | `beta/rangecast.py` 24h corridor (a regime term) | holdout coverage of the 24h corridor split by D2 state; re-calibration; tracked live accuracy before and after |
| D7 | the next hour after a D7 hour | 1h corridor | 1h coverage split by D7 state on the holdout and live |
| D11 | 1.76× volatility in the 6h after FOMC | the corridor's event term (EVCORR-K1-FOMC natural accumulation) | the K1 design's release counts (12 / 38 / 127 releases to detect a coverage gap) |
| DH3-P3 | a 4h "up first" probability | none until confirmed | live tracking (about 3,300 qualifying hours a year); P3 live tracking is **not started** (owner, 2026-10-04) |

DH3-P1, O2, L3, S1 and V2 are below the 15 % materiality bar, so they are not candidates.

## 7. Records

- **Code:**
  - `beta/research_states.py`, `beta/research_evidence.py`, `beta/research_inputs.py`, `beta/research_feeds.py`, `beta/research_render.py`;
  - `scripts/research/evidence/freeze_live_cuts.py`.
- **Registry and config:**
  - `config/beta_research_findings.yaml` (`live:` blocks);
  - `config/beta_research_cuts.json`;
  - `config/beta_v0.yaml` (`decision.research_evidence`).
- **Schema:** the `beta_feed_*` tables, `beta_hist_oi_5m.ls_account_ratio`, and the `research` tab and `tab_research` action.
- **Tests:**
  - `tests/beta/test_research_evidence.py`;
  - `tests/beta/test_research_evidence_pg.py`;
  - `tests/research/test_research_evidence_parity.py`.
