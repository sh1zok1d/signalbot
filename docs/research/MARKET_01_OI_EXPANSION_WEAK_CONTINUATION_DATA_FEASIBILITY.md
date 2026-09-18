# MARKET-01 OI_EXPANSION_WEAK_CONTINUATION — outcome-blind data feasibility

- **Status:** `OUTCOME_BLIND_FEASIBILITY`
- **Hypothesis direction (not frozen):** `OI_EXPANSION_WEAK_CONTINUATION`
- **Inspected HEAD:** `3e5e4579672dceb582364f2fe29f83d52abb9f63`
- **Inspected tree:** `30563d323849698b47e5c9f572d330f8b7d97807`
- **Date:** 2026-09-17
- **Outcome inspection:** **NO**
- **Prereg created:** **NO**
- **MARKET-01 executed:** **NO**
- **B2-06 execution authorized:** **NO**

This unit inspects existing repository/data authorities to determine whether
point-in-time price and open-interest data are sufficient to preregister this
direction honestly later. It does **not** test the hypothesis, enumerate
candidates, compute future returns, choose windows from outcomes, create a
prereg or RESULT, open 2025/2026, or execute B2-06.

"Absorption" is only a possible mechanism interpretation. It is **not** an
observable and is not assumed true.

---

## 0. Working direction (conceptual only)

After a directional price impulse, expansion in open interest combined with
weak subsequent price continuation may represent a market state associated
with leverage accumulation / possible absorption and may contain information
about later reversal.

This paragraph is **not** a frozen claim, not a candidate definition, and not
an outcome result.

A defensible later causal order, if a prereg is written, would freeze a
decision time `T` only after every input window used to label the state is
legally available, and would place any reversal/continuation *outcome* strictly
after `T`. This unit does not freeze those windows.

---

## 1. Price data

**Authority:** `CORE_BTC_BINANCE_V0` snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`

| Item | Recorded fact |
|---|---|
| Venue/exchange | Binance |
| Instrument | `BTCUSDT` |
| Market type | USD-M perpetual futures (`USD_M_FUTURES`) |
| Evidence tier | `OFFICIAL_ARCHIVE` / `HISTORICAL_COMPARABLE` (not `LIVE_EQUIVALENT`) |
| Status | `ACCEPTED_FOR_DISCOVERY`; `confirmatory_authorized = false` |
| `research_authorized` | `true` (discovery) |
| Native granularity | 1m klines; derived 5m/15m/1h/4h exist under UTC-epoch aggregation |
| Timestamp fields | `open_time_ms` = bar start; `close_time_ms` = last millisecond inside source bar |
| Availability rule | `available_at = bar_end_exclusive = open_time + 60s`; eligible iff `bar_end_exclusive <= T` |
| Frozen range | `[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)` |
| Observed first/last open | `2020-01-01T00:00:00Z` … `2026-08-25T23:59:00Z` |
| Missing 1m minutes | **0** |
| Duplicate / corrupt rows | **0** / **0** |
| HTF incomplete buckets | **0** at 5m/15m/1h/4h |
| Excludes | open interest, funding, liquidations, order book, spot, other venues |
| Point-in-time safe for intended use? | **YES** for closed-bar decisions at `T`. Not for sub-minute publication/transport latency. |

Manifest: `docs/manifests/CORE_BTC_BINANCE_V0.yaml`.
Contract: `docs/CORE_BTC_BINANCE_V0_CONTRACT.md`.
Evidence: `docs/research_data/CORE_BTC_BINANCE_V0/`.

Canonical parquet/raw ZIP bytes are gitignored. This worktree does **not**
contain local `artifacts/research_data/CORE_BTC_BINANCE_V0` parquet. Identity
and checksums are Git-bound. Rematerialization uses the existing CORE
materializer; this unit did not rematerialize.

Protected prior-experiment windows remain unopened here: project convention
forbids 2025 validation and 2026 OOS for H01–H05 / Batch02. This unit did not
read 2025/2026 partitions (they are not present locally).

`PRICE_POINT_IN_TIME_USABLE = YES`

---

## 2. Open interest data

**Identity authority:** `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` snapshot
`5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`

This is the repository's only Git-bound first-party OI series. Citing it for
MARKET-01 is **not** B2-06 scientific execution. B2-06 remains
`BLOCKED_MISSING_OBSERVABLE` because **funding** publication latency is
unproven. MARKET-01 as conceptualized does **not** require funding.

| Item | Recorded fact |
|---|---|
| Source | Binance Vision `daily/metrics/BTCUSDT` official archive |
| Venue/instrument | Binance USD-M perpetual `BTCUSDT` |
| Series field | `sum_open_interest` (BTC units) |
| Timestamp field | `create_time` — naive UTC datetime, 5m **bucket start** |
| Period | `period_start = create_time`; `period_end = period_start + 300_000 ms` |
| Availability | `available_at = period_end` (conservative bar-end-exclusive) |
| Publication clock | `oi_decision_time_availability_proven = true` under that frozen rule |
| Native frequency | 5m. Must not be advertised as 1m information. No forward-fill to 1m. |
| Joint snapshot range | `[2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)` |
| First/last OI `create_time` | `1598918400000` = `2020-09-01T00:00:00Z` … `1735689300000` = `2024-12-31T23:55:00Z` |
| Normalized OI rows | 455273 |
| Expected native 5m buckets | 455904 (`1583` days × `288`) |
| Missing native 5m buckets | **631** across **70** daily objects (`MISSING`, not filled) |
| Unexplained missing periods | `false` |
| Rejected OI objects | **0** / 1583 accepted |
| Dataset `research_authorized` | `false` (dataset-level; driven by funding, not by OI clocks) |
| Local raw/normalized bytes | **not present**; Git status `IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED` |
| Point-in-time safe for intended use? | **YES** under the frozen OI bar-end-exclusive rule. Last legally available OI at `T` is the latest row with `available_at <= T` and staleness `<= 300_000 ms`. Older OI is `NOT_READY`, not 1m-filled. |

Manifest: `docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml`.
Contract: `docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md`.
Evidence: `docs/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/`.
OI clock primitive: `oi_available_at_ms` in
`scripts/research/binance_um_oi_funding_v0_contract_lib.py`.

Funding rows in the same snapshot remain **not** legally consumable
(`FUNDING_PUBLICATION_LATENCY_UNPROVEN`). MARKET-01 must not use them.

Live/Postgres/Tardis/Bybit/OKX OI are **not** substitute authorities.

`OI_POINT_IN_TIME_USABLE = YES`

Operational note (not a semantics NO): OI JSONL/ZIP are not locally recoverable
in this worktree. Later execution requires rematerialization against the frozen
object-ledger checksums using the **existing** OI materializer. This unit did
not rematerialize and did not download Vision bodies.

---

## 3. Alignment

| Item | Assessment |
|---|---|
| Common date range | `[2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)` |
| CORE-only extra price | `[2020-01-01, 2020-09-01)` and `[2025-01-01, 2026-08-26)` — **no first-party OI** in the bound snapshot; cannot support this OI hypothesis |
| Effective common frequency | **5m native OI grain**. Price may be used at 1m or aggregated to 5m; OI changes cannot be claimed at 1m resolution |
| Defensible timestamp rule | At decision `T`, use CORE bars with `bar_end_exclusive <= T` and OI rows with `available_at = create_time + 5m <= T`. Same UTC exclusive-end clock. A 5m price bar `[t, t+5m)` and the OI row labeled `create_time = t` both become legal at `t+5m` |
| Lookahead refusal | `open_time <= T` alone is illegal for price. Treating OI `create_time` as an instant print at bucket start is illegal |
| Missingness | 631 missing OI buckets stay `MISSING`. Pairing must fail closed or drop the episode; never fill from another venue/timeframe |
| Same-support | Candidate and baseline must share an input-declared eligible key set (`paired_same_support` discipline) |

`PRICE_OI_CAUSAL_ALIGNMENT_POSSIBLE = YES`

### Ambiguities that a later prereg must resolve (not resolved here)

These are design/governance sentences, not licenses to inspect outcomes:

1. Impulse lookback, OI-expansion lookback, and “weak continuation” window
   lengths — unspecified. Must be frozen outcome-blind. This unit does not
   choose them and does not copy consumed H03/B2-03/B2-05 window values as if
   they were unused.
2. Exact OI-expansion statistic (`ΔOI`, percent change, vs a trailing
   reference) and the definition of “weak continuation” as a **state at `T`**,
   with any reversal outcome strictly after `T`.
3. Handling of the 631 missing native OI buckets (exclude episode vs fail
   closed vs require complete lookback support).
4. Decision grid (5m vs 15m vs hourly). OI native grain is 5m; a coarser
   grid is allowed; a 1m OI claim is not.
5. Dataset-governance sentence: MARKET-01 may bind **OI-only** rows from
   snapshot `5a9d036b…` under the frozen OI availability rule **without**
   setting `research_authorized = true` on the B2-06 dataset, **without**
   using funding, and **without** enabling `b2_06_evaluator`. That sentence
   is not written as a prereg here.
6. Local rematerialization of CORE parquet and OI JSONL before any execution.
7. Development vs reserved 2025 / untouched 2026: OI snapshot already ends
   at `2025-01-01`. A MARKET-01 development window must not open protected
   2025/2026 price partitions.

---

## 4. Existing infrastructure (reuse; not modified)

Identified only. Not executed against MARKET data. Not modified.

| Need | Existing primitive | Notes |
|---|---|---|
| Chronological slicing / 2025–2026 exclusion | `scripts/research/h01_compression_expansion_lib.py` `list_development_parquet_paths`, `FORBIDDEN_YEAR_PREFIXES`, `assert_development_outcome_window` | Pattern only. H01 windows are consumed for H01, not for MARKET-01 |
| Dataset identity gate | `scripts/research/lib/research_harness.py` `authorize_dataset_access`, `verify_git_freeze`, `assert_no_lookahead` | Reuse |
| Price returns / displacement | `log_returns` (H01), `compute_impulse_returns` (H03), `path_log_returns` (B2-03) | Code primitives; do not import those hypotheses' frozen thresholds/windows as MARKET-01 truth |
| OI changes / availability | `normalize_oi_rows`, `oi_available_at_ms`, `last_legally_available`, `missing_oi_intervals`, `assert_no_lookahead` in `binance_um_oi_funding_v0_contract_lib.py` | OI-only path. **Do not** call `crowding_inputs_ready` / `eligible_decision_keys` — those require funding and would keep MARKET-01 blocked as if it were B2-06 |
| Episode-like event construction | B2-03 `construct_events`; H03 refractory helper | Frozen product V2 episode lifecycle is **out of scope** |
| Baseline / candidate evaluation | `paired_same_support_delta`, `fail_closed_gate_conjunction` (research harness); H01 matched-random / week-block bootstrap; B2 cell-gate pattern | Reuse the *discipline*, not B2-05/H03 consumed claims |
| V3 confirmatory instrumentation | `scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py` (`evaluate_v3_world`, stationary bootstrap, one-sided Wilson) | Available as instrumentation. `methodology_claimable = false`. Trap protection inadequate on the frozen synthetic trap DGP. V3 `DETECTED`/`PASS` is **not** market-edge evidence and was not used to design MARKET-01 |
| Rematerialization | `scripts/research/core_btc_binance_v0_materializer.py`; `scripts/research/binance_um_oi_funding_v0_materializer.py` | Existing; not run in this unit |

Do not build a new generic MARKET framework. Do not modify these primitives
in this unit.

---

## 5. Data sufficiency (mechanical)

```text
PRICE_POINT_IN_TIME_USABLE = YES
OI_POINT_IN_TIME_USABLE = YES
PRICE_OI_CAUSAL_ALIGNMENT_POSSIBLE = YES
MARKET_01_PREREG_FEASIBLE = YES
```

Reasons for YES:

- CORE 1m BTCUSDT USD-M klines have a frozen exclusive-end availability rule,
  zero missing minutes, and discovery authorization.
- First-party OI has a frozen exclusive-end availability rule, proven OI
  decision-time availability, native 5m grain, and a documented gap census.
- Price and OI share venue/symbol/UTC and a common interval
  `[2020-09-01, 2025-01-01)` on which causal as-of alignment is defensible
  without inventing 1m OI.

Not claimed:

- local bytes are present (they are not);
- B2-06 is unblocked (it is not);
- funding is usable (it is not);
- absorption is observed (it is not);
- any MARKET predictive result (none was computed);
- V3 methodology is generally claimable (it is not).

---

## 6. Explicit non-actions

- No future returns after candidate states.
- No candidate-event enumeration or outcome inspection.
- No correlation with future returns.
- No reversal/continuation test.
- No threshold/window search from outcomes.
- No backtest.
- No MARKET-01 prereg or RESULT.
- No 2025 validation / 2026 OOS partition access.
- No B2-06 evaluator enablement, funding consumption, or inventory status change.
- No V3 RESULT inspection for MARKET design.
- No new generic infrastructure.

---

## 7. Next step (not this unit)

`MARKET-01` preregistration, if authorized next, must remain outcome-blind,
bind CORE snapshot `717d37a4…` plus OI-only rows from snapshot `5a9d036b…`,
freeze windows without outcome search, keep 2025/2026 closed, and leave
B2-06 blocked.
