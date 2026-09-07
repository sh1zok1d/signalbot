# B2-06 leverage-crowding data expansion

**Status:** `CONTRACT_FROZEN_NOT_MATERIALIZED`  
**Decision:** `DATA_EXPANSION_FEASIBLE_TO_FREEZE`  
**Dataset ID:** `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0`  
**Date:** 2026-09-07  
**Inventory mutability:** this unit does **not** edit `docs/research/V2_FORMULATION_INVENTORY.md`  
**Outcome access:** **NO**. B2-06 is not executed. No RESULT is created. 2025 validation and 2026 OOS remain unopened. B2-05 is not reinterpreted.

This is an outcome-blind data-expansion design unit. It freezes source identity, decision-time semantics, missing-vs-corrupt rules, same-support eligibility, and snapshot/provenance binding so a later materializer can exist without shopping for convenient OI/funding coverage after seeing B2-06 outcomes.

It is **not**:

- B2-06 scientific evaluation;
- crowding-threshold search;
- authorization to open `CORE_BTC_BINANCE_V0` for a B2-06 run;
- a silent extension of `CORE_BTC_BINANCE_V0` (that dataset remains kline-only and still excludes `open_interest` and `funding`).

Machine-readable twin: `docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.json`.  
Executable contract: `scripts/research/binance_um_oi_funding_v0_contract_lib.py`.  
Planning manifest: `docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml`.

---

## 1. Repository/data-contract audit (reuse vs new)

Existing machinery that **must be reused, not weakened**:

| Contract | What B2-06 reuses |
|---|---|
| `docs/manifests/CORE_BTC_BINANCE_V0.yaml` | Binance / USD-M / `BTCUSDT` / UTC venue identity for the **price/vol/flow baseline**. CORE still excludes OI/funding. |
| CORE `available_at = bar_end_exclusive` | Same no-lookahead predicate shape: `available_at <= T`. |
| `authorize_dataset_access` / snapshot identity | Git-tracked manifest + computed snapshot payload hash. Snapshot identity is **not** self-attested runtime metadata. |
| `.CHECKSUM` `sha256sum` sidecars | Filename identity + digest must both match. Mismatch is corrupt, not missing. |
| Inventory §10 missing-vs-corrupt | Unavailable/not-yet-mature → explicit missing. Checksum/schema/conflict → fail closed. No fill from another venue/symbol/contract/timeframe. |
| `paired_same_support` discipline | Candidate and baseline share one eligible key set declared from inputs, not outcomes. |

What B2-06 **genuinely requires additionally**:

- a **new dataset identity** (not a CORE partition);
- first-party OI and settled-funding series with explicit publication clocks;
- native 5m OI grain that must not be advertised as 1m information;
- funding-definition lock (settled `last_funding_rate` only);
- joint eligibility that CORE klines cannot provide.

Frozen E1/V2 Postgres OI/funding materializers and Tardis captures are **not** reusable as B2-06 authority.

---

## 2. Source feasibility and adjudication

Candidates were judged on provenance, temporal semantics, coverage, and reproducibility — not on which series would later look predictive.

| Candidate | Verdict | Why |
|---|---|---|
| Binance Vision USD-M `BTCUSDT` `monthly/fundingRate` + `daily/metrics` | **SELECTED** | First-party official archive, checksum sidecars, same venue/symbol as CORE, historically listable, schema-sampled in development years only |
| Binance REST `/futures/data/openInterestHist` | Rejected | ~30-day lookback; cannot reproduce 2020–2024 |
| Binance REST `/fapi/v1/fundingRate` as sole history | Rejected | Not the immutable archive object identity; Vision monthly files are the reproducible contract |
| Bybit OI/funding joined to Binance price | Rejected | Cross-venue fallback forbidden by inventory §10 |
| OKX funding/OI | Rejected | Different venue; shorter advertised history; would mix providers |
| Tardis vendor capture | Rejected | Paid / not authorized; vendor-captured, not first-party archive |
| HuggingFace or other concatenations | Rejected | Not first-party; revision identity unclear |
| Binance COIN-M `BTCUSD` | Rejected | Wrong contract type |
| Spot borrow / mark-premium as “funding” | Rejected | Wrong definition |
| Mixing Vision + REST + Tardis to fill holes | Rejected | Silent fallback |

**One primary identity is frozen now.** Later B2-06 execution may not reopen this menu.

---

## 3. Frozen source identity

```text
provider              = Binance
venue                 = Binance
market_type           = USD_M_FUTURES
contract              = PERPETUAL
symbol                = BTCUSDT
OI series             = data.binance.vision daily/metrics/BTCUSDT
                       column sum_open_interest
funding series        = data.binance.vision monthly/fundingRate/BTCUSDT
                       column last_funding_rate
raw OI granularity    = 5m
raw funding interval  = 8h
time zone             = UTC
timestamp interpretation:
  OI create_time      = naive UTC datetime, 5m bucket start
  funding calc_time   = integer milliseconds UTC
availability rule     = available_at <= T, with series-specific available_at
missing-data rule     = explicit MISSING / NOT_READY; never fill
corruption rule       = fail closed; never reclassify as missing
```

Archive roots (no silent daily/monthly swap except the frozen series pairing above):

- funding: `https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/`
- OI metrics: `https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/`

There is no monthly metrics archive for this symbol. There is no daily fundingRate archive for this symbol. Those absences are **not** filled from another prefix.

---

## 4. Decision-time semantics

### 4.1 Open interest

| Clock | Frozen meaning |
|---|---|
| `source_event_time` | `create_time` parsed as UTC |
| `period_start` | that `create_time` (00:00, 00:05, …, 23:55 UTC) |
| `period_end` | `period_start + 300_000` ms |
| `published_at` / `available_at` | `period_end` |
| decision time `T` | the hypothesis decision clock (CORE 1m `bar_end_exclusive` when paired with CORE) |

A 5m OI snapshot labeled at bucket start is **not** treated as a point-in-time print at `create_time`. That would leak the window if the label is a period start. The conservative CORE-consistent rule delays a true instant snapshot by at most one native interval.

Last legally available OI at `T` is the latest snapshot with `available_at <= T` and `T - available_at <= 300_000` ms (one native interval). Older OI is **not-ready**, not forward-filled into fake 1m OI.

### 4.2 Funding

| Clock | Frozen meaning |
|---|---|
| `source_event_time` | `calc_time` (ms) |
| canonical settlement | nearest 8h UTC boundary iff `\|calc_time - settlement\| <= 1000` ms; otherwise **corrupt** |
| `period_end` | canonical settlement |
| `period_start` | `period_end - 8h` |
| `published_at` / `available_at` | **`calc_time` itself**, not the snapped label |
| decision time `T` | same `T` as OI/price |

Archive samples in development years sit on 8h UTC marks with millisecond jitter. Equating `calc_time` with the 8h label would allow using a rate up to the snap tolerance **before** the source timestamp. That is forbidden.

This series is **settled `last_funding_rate`**. It is not:

- predicted/next funding;
- premium-index implied funding;
- an announced but unsettled rate;
- a realized USDT payment notional.

If an optional explicit `published_at` is ever attached (backfill/revision metadata), legal time is `max(available_at, published_at)`. Retrieval wall-clock is provenance only and never becomes availability.

Last legally available funding at `T` requires `available_at <= T` and staleness `<= 8h`. A skipped settlement is missing/not-ready, not interpolated.

### 4.3 Usability predicate

An observation may be used only when its frozen availability semantics establish `legal_available_at <= T`.

---

## 5. Coverage feasibility (outcome-blind)

Inspection was limited to:

- S3 listing of official archive keys;
- schema samples from **2020–2024** objects (headers, cadence, checksum match, duplicate anatomy);
- no 2025/2026 object bodies;
- no returns, correlations, Sharpe, hit-rate, or crowding-threshold statistics.

**Archive-object completeness, development years**

| Series | Expected | Present | Gaps |
|---|---:|---:|---|
| funding monthly zip+checksum 2020-01 … 2024-12 | 60 | 60 | none |
| OI daily zip+checksum 2020-09-01 … 2024-12-31 | 1583 | 1583 | none |

Funding monthly files exist from 2020-01. OI daily files begin 2020-09-01. **Joint B2-06 crowding inputs therefore cannot start before 2020-09-01.** That is a restricted overlap window, not a license to borrow Bybit/Tardis OI for 2020-01…2020-08.

2025/2026 keys were counted as listing metadata only and were not opened as research windows.

**Intra-file notes (samples, not a full gap census)**

- Funding samples: header `calc_time,funding_interval_hours,last_funding_rate`; native 8h; no timestamp duplicates; interval column `8`.
- OI samples: frozen 8-column metrics header; native 5m labels; `symbol=BTCUSDT`.
- Early OI days (sampled 2020-09-01 … 2021-05-20) contain **byte-identical doubled rows** (576 rows / 288 unique timestamps). Conflicting duplicates were not observed in those samples. Collapse of identical duplicates is frozen; conflicting duplicates fail closed.
- Sampled missing 5m buckets exist (e.g. `2021-02-28 00:30:00`, `2021-05-28 09:00:00`). Those are **missing intervals**, not fill-from-elsewhere events.
- Full intra-file 5m completeness is **not** asserted at 100%. Materialization must emit a gap report. Occasional missing native buckets do not retire the observable class.

Coverage is adequate to freeze identity for the Batch02 development overlap `[2020-09-01, 2025-01-01)` without opening 2025/2026.

---

## 6. Snapshot and provenance contract

Materialization (a later unit) must bind all of:

- frozen source identity;
- retrieval method/version (`binance-vision-official-archive-sha256sum-v1`);
- retrieval time;
- requested intervals;
- raw file identities + SHA256s + checksum verification;
- normalized file identities + SHA256s;
- schema/availability/normalization versions;
- row counts and first/last timestamps;
- normalization module path + SHA256 of that source file;
- provenance git commit SHA;
- `snapshot_id = SHA256(canonical JSON identity payload)`.

`snapshot_id` is **computed**. Callers cannot supply it. Tracked authority is the Git manifest `docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml`. Caller-selected runtime metadata, substituted manifests, or substituted snapshot ids fail closed.

This unit does **not** materialize the historical bytes. `snapshot_id` remains `NOT_MATERIALIZED`. `research_authorized` remains `false`. `authorize_dataset_access` therefore cannot honestly open this dataset until a later Git-bound snapshot exists.

Upstream archive revision requires a new manifest/snapshot revision. It must not mutate this freeze in place after outcomes exist.

---

## 7. Missing vs corruption

**Missing / not-ready (explicit, eligible-set shrinking is predeclared):**

- native 5m OI bucket absent inside an otherwise valid file;
- last OI/funding older than the frozen staleness bound;
- `published_at > T`;
- joint crowding inputs not all legally available.

**Corrupt (fail closed; never “missing”):**

- checksum mismatch or checksum filename identity mismatch;
- schema mismatch;
- venue/symbol/contract/provider mismatch;
- OI unit/definition mismatch;
- funding definition/interval mismatch;
- conflicting duplicate timestamps;
- impossible or malformed timestamps;
- non-finite values where forbidden;
- negative `sum_open_interest`;
- funding `calc_time` more than 1000 ms from the 8h UTC grid;
- OI `create_time` off the 5m UTC grid;
- unexpected cadence changes not named in this contract;
- mixed-provider, mixed-venue, or mixed-timeframe batches;
- normalization code SHA mismatch;
- manifest/snapshot substitution;
- caller-selected alternate source.

No filling from another venue, provider, symbol, contract, calculation version, or timeframe.

---

## 8. Same-support contract (for a later B2-06 run)

Baseline (inventory, unchanged): comparable price displacement + current price/volatility/flow state **without** OI/funding, on CORE klines.

When B2-06 eventually runs:

1. Declare the candidate and baseline canonical event keys **identically** first (CORE decision buckets).
2. Keep only keys whose price bar is legally available at `T` **and** whose legally available OI **and** settled funding both exist under this contract.
3. Pair candidate and baseline **only** on that eligible key tuple.
4. Missingness is a denominator, not a post-hoc support shop. Outcomes must not rewrite eligibility.
5. Corrupt inputs abort the run; they do not drop rows as missing.

This unit does not choose crowding thresholds or forecast targets.

---

## 9. What remains blocked

`B2-06_LEVERAGE_CROWDING` remains `BLOCKED_MISSING_OBSERVABLE` in the frozen inventory and in the Batch02 status ledger **as a scientific formulation**. The observable class now has a frozen first-party identity, but:

- the snapshot is not materialized;
- the dataset is not `research_authorized`;
- no evaluator, promotion gate, or outcome window is opened.

A later materialization + authorization unit is required before any B2-06 development outcome. That unit still must not open 2025/2026 unless a frozen prereg says so.

---

## 10. Decision

`DATA_EXPANSION_FEASIBLE_TO_FREEZE`

Exact identity, first-party provenance, development-year archive-object coverage, decision-time clocks, and Git-bound snapshot mechanics can all be made defensible without lowering the bar. Intra-file 5m holes are handled as missingness rather than by mixing sources.

`READY_FOR_RED_TEAM = YES`  
`VERDICT = DATA_CONTRACT_FROZEN_AWAITING_MATERIALIZATION`
