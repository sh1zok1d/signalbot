# Signalbot — CORE_BTC_BINANCE_V0 Dataset Contract

**Status:** ACTIVE / RESEARCH DATA CONTRACT  
**Dataset:** `CORE_BTC_BINANCE_V0`  
**Created:** 2026-08-26  
**Purpose:** freeze the first long-history CORE dataset semantics before materialization or hypothesis discovery.

This contract defines what `CORE_BTC_BINANCE_V0` is allowed to mean. It is intentionally narrower than the full market-data platform and narrower than future RICH datasets.

The dataset exists to answer a first-order question:

> Can simple BTC market mechanisms be discovered and falsified over multiple regimes using long, reproducible exchange-native price/volume/taker-flow history before adding richer derivatives data?

It is **not** a forecasting model, trading strategy, feature-selection result or edge claim.

---

## 1. Frozen scope

### Venue / instrument

- provider: Binance;
- market: USDⓈ-M perpetual futures;
- symbol: `BTCUSDT`;
- source family: official Binance public-data archive;
- raw dataset: standard USD-M Futures `klines`;
- native interval used for canonical materialization: `1m`.

### Initial frozen time target

The first materialization target is:

```text
start_inclusive = 2020-01-01T00:00:00Z
end_exclusive   = 2026-08-26T00:00:00Z
```

This intentionally ends at the last complete UTC day before this contract was created.

The cutoff is part of the dataset identity. Extending the dataset later creates a new manifest revision/snapshot; it must not silently mutate a result already reported against an earlier frozen manifest.

### Included raw fields

The official USD-M Futures kline schema supplies:

1. `open_time_ms`
2. `open`
3. `high`
4. `low`
5. `close`
6. `base_volume`
7. `close_time_ms`
8. `quote_volume`
9. `trade_count`
10. `taker_buy_base_volume`
11. `taker_buy_quote_volume`
12. source `ignore` field

The canonical research table retains the first eleven semantic fields. The `ignore` column may be stored for raw fidelity but is not a research feature.

### Allowed arithmetic derivatives

Without creating a new source tier, materialization may derive:

```text
taker_sell_base_volume  = base_volume  - taker_buy_base_volume
taker_sell_quote_volume = quote_volume - taker_buy_quote_volume
```

and deterministic ratios/imbalances from the frozen raw columns.

These are arithmetic transformations, not independently observed feeds. Their provenance must remain `DERIVED_FROM_KLINE`.

### Explicitly excluded from V0

`CORE_BTC_BINANCE_V0` does **not** require or silently join:

- open interest;
- funding;
- liquidations / force orders;
- order book / L2;
- mark price;
- index price;
- premium index;
- spot BTCUSDT;
- Bybit / OKX data;
- vendor-normalized history;
- Signalbot live historical tables.

A hypothesis requiring one of those belongs to another dataset/version.

---

## 2. Authoritative source contract

Primary source:

```text
https://data.binance.vision/data/futures/um/{monthly|daily}/klines/BTCUSDT/1m/
```

Binance documents USD-M Futures kline archive rows as originating from `/fapi/v1/klines` and provides daily/monthly archive files with adjacent `.CHECKSUM` files.

Reference documentation:

- https://github.com/binance/binance-public-data/blob/master/README.md
- https://github.com/binance/binance-public-data/blob/master/python/README.md

The Binance helper tooling documents downloadable USD-M kline history from `2020-01-01`; this contract nevertheless requires the actual BTCUSDT archive to pass continuity and start-date validation before the start date is promoted from target to accepted observed coverage.

---

## 3. Archive acquisition policy

### Monthly vs daily objects

Use this precedence:

1. completed historical months: prefer the official monthly object;
2. current/incomplete month at acquisition: use official daily objects only;
3. when a monthly object later exists for a month previously assembled from daily objects, do not overwrite silently;
4. compare the replacement source revision and create a new dataset-manifest revision if adopted.

For the initial 2026-08-26 cutoff, the intended acquisition shape is approximately:

```text
monthly: 2020-01 through 2026-07
daily:   2026-08-01 through 2026-08-25
```

The actual source-object inventory is frozen only after download and is recorded in the manifest.

### Every source object must record

- archive path / URL;
- archive class: `monthly` or `daily`;
- requested period;
- download timestamp UTC;
- source-provided checksum text;
- expected SHA-256 from source checksum;
- locally computed SHA-256;
- byte size;
- contained filename(s);
- parser version/commit;
- first and last parsed `open_time_ms`;
- row count;
- checksum verification result.

### Checksum gate

No archive object may enter an accepted dataset when:

```text
local_sha256 != source_checksum_sha256
```

A missing official checksum is a capability downgrade and must be recorded explicitly. Do not substitute "download succeeded" for integrity verification.

---

## 4. Upstream revision policy

Binance explicitly states that archived files can be replaced after discovered data issues.

Therefore:

- URL/path alone is not dataset identity;
- source checksum is part of identity;
- local SHA-256 is part of identity;
- raw files are immutable once ingested into a frozen research snapshot;
- a later upstream replacement is recorded as a new source revision;
- prior results retain the old manifest/source checksums;
- adopting corrected upstream history produces a new dataset manifest version/revision and requires result provenance to state which revision was used.

Never silently redownload an old path and overwrite the bytes that produced a published research result.

---

## 5. Timestamp semantics / no-lookahead

### 1m source bar

For a Binance 1m kline:

```text
bar_start = open_time
bar_end_exclusive = open_time + 60 seconds
```

The source also carries `close_time_ms`, conventionally the final millisecond inside the interval.

For Signalbot research, availability is modeled conservatively as:

```text
available_at = bar_end_exclusive
```

At a decision boundary `T`, the bar is eligible only when:

```text
bar_end_exclusive <= T
```

Do not use `open_time <= T` alone as the as-of eligibility rule.

### Timezone

All materialization and aggregation boundaries are UTC.

No local timezone, DST rule or display timezone may change bucket membership.

### Historical archive semantics

Archive files represent exchange historical records, not Signalbot-observed arrival times.

Therefore the evidence tier is:

```text
HISTORICAL_COMPARABLE / OFFICIAL_ARCHIVE
```

not `LIVE_EQUIVALENT` by default.

Hypotheses relying on sub-minute publication latency or transport arrival timing are outside this dataset's capability.

---

## 6. Raw row invariants

Each accepted row must satisfy at minimum:

### Identity

- symbol is exactly `BTCUSDT` under the source path;
- one canonical row per `open_time_ms`;
- `open_time_ms` aligned exactly to a UTC minute;
- `close_time_ms < bar_end_exclusive`;
- next expected minute is `open_time_ms + 60_000` unless a gap is explicitly recorded.

### Prices

```text
open  > 0
high  > 0
low   > 0
close > 0
high >= max(open, close)
low  <= min(open, close)
high >= low
```

### Volumes / counts

```text
base_volume >= 0
quote_volume >= 0
trade_count >= 0
taker_buy_base_volume >= 0
taker_buy_quote_volume >= 0
taker_buy_base_volume <= base_volume + numerical_tolerance
taker_buy_quote_volume <= quote_volume + numerical_tolerance
```

Use exact decimal parsing or a representation that does not create material binary-float artifacts in validation/accounting.

### Duplicate handling

A duplicate `open_time_ms` is never silently last-write-wins.

If two source rows share one timestamp:

- identical rows: record duplicate-source condition and deduplicate deterministically only in a clearly documented canonicalization step;
- non-identical rows: fail the acceptance gate for that source period until resolved.

---

## 7. Continuity / missingness contract

Expected one-minute grid:

```text
[start_inclusive, end_exclusive)
step = 60 seconds
```

The audit must report:

- expected row count;
- observed unique row count;
- missing minute count;
- duplicate minute count;
- longest contiguous gap;
- every gap start/end;
- missingness by calendar year/month;
- whether gaps overlap extreme-return/high-volume periods;
- number of rows rejected for schema/invariant violations.

Missing bars are **not** filled with zero and are **not** synthesized from neighboring prices.

For confirmatory research, any derived higher-timeframe bucket with incomplete required 1m membership is marked incomplete and unavailable.

Discovery research may inspect incomplete regions diagnostically, but must not silently include synthetic repaired bars.

---

## 8. Deterministic higher-timeframe aggregation

Derived canonical intervals initially allowed:

```text
5m
15m
1h
4h
```

All buckets are UTC epoch-aligned.

For target bucket `[B, E)` containing complete constituent 1m bars:

```text
open                     = first(open)
high                     = max(high)
low                      = min(low)
close                    = last(close)
base_volume              = sum(base_volume)
quote_volume             = sum(quote_volume)
trade_count              = sum(trade_count)
taker_buy_base_volume    = sum(taker_buy_base_volume)
taker_buy_quote_volume   = sum(taker_buy_quote_volume)
open_time                = B
bar_end_exclusive        = E
available_at             = E
```

Expected constituent counts:

```text
5m  = 5
15m = 15
1h  = 60
4h  = 240
```

A bucket is `COMPLETE` only if every expected minute exists exactly once after canonical duplicate resolution.

No forward-fill or partial aggregation is allowed for confirmatory bars.

### Native higher-timeframe archive data

Binance also provides native higher-interval klines. They are **not** the canonical research source for V0.

They may be used only as a validation cross-check against locally aggregated 1m data. Disagreement must be audited rather than resolved by silently switching source.

---

## 9. Research feature boundary

Features constructed from this dataset must be reproducible from information available by the decision boundary.

Allowed mechanism families include, for example:

- returns / momentum;
- realized range / volatility;
- compression / expansion;
- breakout / failed-breakout structure;
- trend/pullback geometry;
- volume state;
- taker-buy/taker-sell imbalance derived from kline totals;
- price-volume interactions.

This contract does not validate any of them.

### Forbidden semantic inflation

Do not describe:

- taker imbalance as order-book pressure;
- kline taker flow as complete trade-level sequence information;
- archive timestamps as live arrival latency;
- a higher-timeframe feature as known before all constituent bars close.

---

## 10. Dataset identity

A materialized dataset identity must include at least:

```text
dataset_id
manifest_version
snapshot_id
contract_version
source provider/market/symbol/type/interval
start_inclusive
end_exclusive
source object inventory
source checksum per object
local sha256 per object
raw parser commit/version
canonicalization commit/version
aggregation commit/version
quality-report checksum
accepted row count
missing/duplicate statistics
materialized output checksum(s)
created_at UTC
```

Two datasets with different source checksums, cutoffs, parser versions or quality decisions are not automatically the same evidence population even if both are called BTCUSDT 1m.

---

## 11. Initial manifest lifecycle

The repository contains a machine-readable planning manifest at:

`docs/manifests/CORE_BTC_BINANCE_V0.yaml`

Before acquisition it must remain:

```text
status: PLANNED_NOT_MATERIALIZED
research_authorized: false
```

After download/audit, populate actual source inventory and quality statistics.

Promotion sequence:

```text
PLANNED_NOT_MATERIALIZED
    -> MATERIALIZED_UNVERIFIED
    -> QUALITY_AUDITED
    -> ACCEPTED_FOR_DISCOVERY
```

`ACCEPTED_FOR_CONFIRMATORY` is a separate stronger state and is not granted automatically merely because discovery work began.

---

## 12. Acceptance gates for discovery

`CORE_BTC_BINANCE_V0` may become `ACCEPTED_FOR_DISCOVERY` only when all are true:

1. every used raw archive object passes source checksum verification;
2. target start/end are confirmed against actual parsed rows;
3. schema parse is deterministic;
4. duplicate report exists and unresolved conflicting duplicates = 0;
5. gap report exists;
6. all price/volume invariants have been audited;
7. incomplete periods are explicitly represented, not silently repaired;
8. UTC timestamp/as-of semantics are tested;
9. 5m/15m/1h/4h aggregation is deterministic and complete-count gated;
10. source-object inventory and local checksums are frozen in the manifest;
11. output dataset checksum/snapshot identity is frozen;
12. a human-readable quality report states any limitations that constrain claims.

A non-zero gap count does not automatically kill the dataset. It does prevent the project from pretending the history is perfectly continuous; affected windows must be handled explicitly.

---

## 13. Additional gate for confirmatory research

Before a frozen OOS/confirmatory experiment can rely on this dataset, additionally require:

- research code pins the exact accepted manifest/snapshot ID;
- outcome paths fail closed across missing/incomplete bars;
- no development-time repair is introduced only after viewing confirmatory outcomes;
- known archive revisions since snapshot creation are reviewed and dispositioned;
- dataset limitations do not contradict the hypothesis's required information timing;
- the confirmatory experiment records the dataset identity in its preregistration/results.

---

## 14. What materialization does not authorize

Completing this dataset does not authorize:

- V3 or replacement forecasting architecture;
- Stage 6+ restart;
- parameter mining without development/OOS discipline;
- paid rich-data purchase;
- describing exploratory performance as validated edge;
- merging E1 semantics with the new research program.

The dataset is infrastructure for falsification, not evidence by itself.

---

## 15. Next implementation deliverables

Once an environment suitable for bulk acquisition is available, the next research-infrastructure work is:

1. deterministic Binance archive downloader/inventory builder;
2. checksum verifier;
3. parser/canonical 1m materializer;
4. continuity + duplicate + invariant audit;
5. deterministic higher-timeframe aggregator;
6. machine-readable manifest population;
7. immutable quality report/snapshot identity;
8. only then broad mechanism discovery.

No forecasting/product code is required for these steps.
