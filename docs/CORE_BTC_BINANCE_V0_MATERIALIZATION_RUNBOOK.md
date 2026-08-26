# CORE_BTC_BINANCE_V0 Materialization Runbook

**Status:** ACTIVE / RESEARCH INFRASTRUCTURE
**Tool:** `scripts/research/core_btc_binance_v0_materializer.py`
**Contract:** `docs/CORE_BTC_BINANCE_V0_CONTRACT.md`
**Planning/accepted manifest:** `docs/manifests/CORE_BTC_BINANCE_V0.yaml`
**Accepted snapshot evidence:** `docs/research_data/CORE_BTC_BINANCE_V0/` (snapshot `717d37a4`)
**Depends on:** the PR #71 source probe (`docs/CORE_BTC_BINANCE_V0_PROBE_RUNBOOK.md`)

## Purpose

Implement the deterministic pipeline that can eventually materialize
`CORE_BTC_BINANCE_V0`. This runbook is the operator guide for a **future**
bulk run. Implementing the tool is not executing the bulk run.

The four-month source-capability probe (`2020-01`, `2021-05`, `2024-03`,
`2026-07`) already passed on real Binance data. That authorizes **design
and implementation** of this pipeline. It does **not** authorize dataset
acceptance, hypothesis discovery, or automatic promotion of the planning
manifest.

## Frozen source range (dataset identity)

```text
start_inclusive = 2020-01-01T00:00:00Z
end_exclusive   = 2026-08-26T00:00:00Z
```

Canonical packaging:

```text
monthly: 2020-01 .. 2026-07     (79 objects)
daily:   2026-08-01 .. 2026-08-25 (25 objects)
total:   104 ZIP + 104 CHECKSUM sidecars
```

Do not move the cutoff. Extending it is a new dataset revision.

## Pipeline stages and preconditions

| Stage | Network | Success requires |
|---|---|---|
| `plan` | no | Enumerate the 104 source objects |
| `inventory` | HEAD only | Size estimate; `Content-Length` missing/0/invalid is UNKNOWN (conservative default, never 0 bytes) |
| `acquire` | GET ZIP+CHECKSUM | All 104 objects `NEW`+`VERIFIED` or `REUSED_IDENTICAL`+`VERIFIED`. `REVISION_CONFLICT` is a failed stage even if the retained local pair still verifies. Non-zero exit otherwise |
| `audit-raw` | no | All 104 currently `VERIFIED` + parser OK |
| `materialize-1m` | no | Re-hash ZIP+sidecar immediately before parse; all partitions written with provenance |
| `aggregate` | no | Current canonical provenance matches current verified raw; streaming HTF |
| `finalize` | no | Raw complete, partitions not stale, HTF hashes match aggregate report |

`--stage all` runs them in order, requires `--allow-acquire`, and **stops on the first failed stage**. Stage completion is not success by itself.

## Commands (later bulk execution)

From the repository root, with `PYTHONPATH` set as for other research scripts:

```bash
pip install -r requirements-research.txt   # pyarrow==17.0.0; not production

python -m scripts.research.core_btc_binance_v0_materializer \
  --stage plan \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0

python -m scripts.research.core_btc_binance_v0_materializer \
  --stage inventory \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0

python -m scripts.research.core_btc_binance_v0_materializer \
  --stage acquire --allow-acquire \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0 \
  --disk-reserve-bytes 5368709120

python -m scripts.research.core_btc_binance_v0_materializer --stage audit-raw \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0
python -m scripts.research.core_btc_binance_v0_materializer --stage materialize-1m \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0
python -m scripts.research.core_btc_binance_v0_materializer --stage aggregate \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0
python -m scripts.research.core_btc_binance_v0_materializer --stage finalize \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0
```

Do not run `--stage acquire` / `--stage all` until a red-team review of this
implementation has passed. **Do not bulk-download 2020–2026 from this runbook
alone.**

`--disk-reserve-bytes 0` is refused unless `--unsafe-no-disk-reserve` is also set.

## Output layout

```text
artifacts/research_data/CORE_BTC_BINANCE_V0/
  raw/monthly/YYYY-MM/BTCUSDT-1m-YYYY-MM.zip[.CHECKSUM]
  raw/daily/YYYY-MM-DD/BTCUSDT-1m-YYYY-MM-DD.zip[.CHECKSUM]
  canonical/1m/monthly/YYYY-MM.parquet
  canonical/1m/monthly/YYYY-MM.provenance.json
  canonical/1m/daily/YYYY-MM-DD.parquet
  canonical/1m/daily/YYYY-MM-DD.provenance.json
  canonical/5m/bars.parquet
  canonical/15m/bars.parquet
  canonical/1h/bars.parquet
  canonical/4h/bars.parquet
  reports/*.json, quality_report.md
  manifests/CORE_BTC_BINANCE_V0.candidate.json
```

`artifacts/` is gitignored. Dataset identity is snapshot hashes, not local
paths.

## Streaming / chunk architecture

Canonical 1m is written **one source object at a time** (one month ≈ 40k
rows is the peak Python-object window for materialize).

`aggregate` and `finalize` **must not** load all 3.5 million 1m rows as
`CanonicalBar` / `Decimal` lists.

- Continuity/gaps: stream `open_time_ms` batches; keep `expected_next_ms`;
  emit compressed gap ranges. No `list(range(start, end, 60_000))`.
- HTF: one chronological scan of 1m partitions; four aggregators each hold
  only the active bucket (≤ 240 constituent minutes) and write parquet in
  batches. State is carried across month, monthly→daily, day, and year
  partitions.
- Finalize hashes files and streams timestamps; it does not rebuild a
  global bar list.

Expected peak RAM envelope for the full 2020–2026 build: **low hundreds of
MB**, not multi-GB. One in-flight Arrow batch (~16k rows) plus one HTF
bucket of Decimals plus gap metadata.

## Partition provenance (RT-M02 / RT-M13)

Each canonical 1m parquet has a sibling `.provenance.json` **metadata**
record. It is not the authority that binds raw to parquet.

Binding is a streaming **canonical content digest**:

- length-prefixed UTF-8 fields (uint32 big-endian length);
- field order: `open_time_ms`, `bar_end_exclusive_ms`, `available_at_ms`,
  `close_time_ms`, `open`, `high`, `low`, `close`, `base_volume`,
  `quote_volume`, `trade_count`, `taker_buy_base_volume`,
  `taker_buy_quote_volume`, `taker_sell_base_volume`,
  `taker_sell_quote_volume`;
- decimals `format(Decimal, "f")`; integers ASCII;
- rows in ascending `open_time_ms`.

At materialize time: digest admitted rows from the current ZIP, write
parquet, independently digest parquet row content, require equality, then
write provenance.

At aggregate/finalize: re-parse the **current** ZIP and digest it; stream
the **current** parquet and digest it; require equality. Then also check
parquet byte SHA and structural provenance fields (period, class, SHAs,
row count, first/last, versions). Editing provenance JSON source SHA
fields cannot bind parquet A to raw B.

Research rows do **not** repeat `source_sha256` 3.5 million times.

## Lock behavior

Mutating stages (`acquire`, `audit-raw`, `materialize-1m`, `aggregate`,
`finalize`, `all`) take an exclusive `fcntl` lock at
`<dataset-root>/.core_btc_binance_v0.lock`. A second writer fails closed.
The lock is released on process exit. This is not distributed locking.

## Resume / revision / disk

- One writer per dataset root (lock above).
- `.part` / leftover `.tmp` files are discarded and are never evidence.
- Verified ZIP bytes that still match the source checksum are reused
  (`REUSED_IDENTICAL`).
- A disagreeing checksum is `REVISION_CONFLICT`: ZIP **and** existing
  sidecar are left untouched. The acquire **stage fails** (non-zero) even
  when the retained pair A is internally `VERIFIED`. Frozen acquisition
  accepts only `NEW`+`VERIFIED` or `REUSED_IDENTICAL`+`VERIFIED`.
- ZIP is never adopted unless the ZIP+CHECKSUM **pair currently on disk**
  verifies. `VERIFIED` is never reported from a fetched checksum while the
  on-disk sidecar disagrees. Missing ZIP + existing sidecar + changed
  remote checksum is `REVISION_CONFLICT` (no new ZIP written).
- Unverified HTML/error bodies are not written as ZIP files.
- Canonical 1m partitions whose parquet bytes are unchanged are reused
  only after the current ZIP still matches provenance.
- Disk-safety gate: refuse acquire when
  `free < remaining_download + .part/.tmp + canonical_estimate + HTF_estimate
  + temp_bound + --disk-reserve-bytes`.
  Default reserve is 5 GiB. HEAD `Content-Length` 0/missing/invalid uses a
  conservative per-class default, never zero.
- Keep raw ZIPs (provenance). Do not extract CSVs permanently.

## Materialization / aggregation semantics

- 1m `available_at = open_time + 60s`. Never Binance `close_time`.
- Canonical 1m stores `close_time_ms` (int64) for source fidelity. It does
  **not** change availability.
- Missing minutes are omitted, never filled.
- Identical duplicate rows: keep first (file order), record the duplicate.
- Conflicting duplicates (same `open_time`, different payload): drop the
  minute, record the conflict.
- Numeric validation uses `Decimal`. Canonical parquet stores OHLC/volume as
  **canonical decimal strings** (`format(Decimal(value), "f")`) plus int64
  timestamps/`trade_count`/`close_time_ms` (zstd).
- **Decimal-string rule:** these columns are numeric values stored as text.
  Research code MUST parse/cast before comparison, sorting, arithmetic, or
  aggregation. Never compare them lexicographically. `Decimal("1.0")` and
  `Decimal("1.00")` are distinct canonical text.
- HTF buckets are UTC epoch-aligned. A bucket is `is_complete=true` only
  with the exact constituent count (5/15/60/240). Incomplete buckets are
  **emitted** with null aggregates so research code can fail closed.
- HTF `available_at = bucket end`.

## Snapshot identity

`snapshot_id` is SHA-256 of a canonical JSON payload containing: dataset id,
contract file hash, frozen start/end, sorted per-object checksums, parser /
materializer / canonicalization / aggregation versions, **SHA-256 of the
exact persisted `quality_report.json` bytes**, and materialized output
checksums (parquet + provenance files + HTF).

`quality_report.json` does **not** contain `snapshot_id` or
`quality_report_sha256` (acyclic: file bytes → snapshot manifest).

Timestamps and directory paths are not the identity key.

## Quality report + gap diagnostic

`reports/quality_report.json` (and `.md`) record coverage, gaps, duplicates,
rejects, HTF incompleteness, sizes, and limitations.

Gap / extreme-market diagnostic (predeclared, not an edge rule): an adjacent
1m bar is flagged when `|close/open-1|` or `base_volume` is at or above the
**99th percentile** of the observed canonical 1m population. Gaps are never
repaired or excluded because of this flag. The streamed diagnostic may use
float64 only for that percentile; it never changes admission.

A non-zero gap count does **not** automatically kill the eventual dataset
(contract §12). It must remain visible; incomplete HTF windows fail closed.

## Finalize ≠ acceptance

A successful finalize emits `SNAPSHOT_CANDIDATE_READY`. It does **not**
mean `ACCEPTED_FOR_DISCOVERY`.

The generated candidate remains:

```text
status: MATERIALIZED_UNVERIFIED
research_authorized: false
```

Incomplete, mixed-revision, or missing-provenance inputs make finalize
**fail** (non-zero exit). They do not produce a candidate snapshot.

This CLI never writes `ACCEPTED_FOR_DISCOVERY` into
`docs/manifests/CORE_BTC_BINANCE_V0.yaml`.

## Research dependency

Parquet I/O needs `pyarrow==17.0.0`.

```bash
pip install -r requirements-research.txt
```

CI/dev can use `requirements-dev.txt`, which layers the same pin. Production
`requirements.txt` stays unchanged. If pyarrow is missing, materialize /
aggregate / finalize fail at startup with an explicit message naming
`requirements-research.txt`.
