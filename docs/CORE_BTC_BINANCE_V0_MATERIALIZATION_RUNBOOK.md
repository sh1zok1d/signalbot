# CORE_BTC_BINANCE_V0 Materialization Runbook

**Status:** ACTIVE / RESEARCH INFRASTRUCTURE
**Tool:** `scripts/research/core_btc_binance_v0_materializer.py`
**Contract:** `docs/CORE_BTC_BINANCE_V0_CONTRACT.md`
**Planning manifest:** `docs/manifests/CORE_BTC_BINANCE_V0.yaml` (unpromoted)
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

## Pipeline stages

| Stage | Network | Effect |
|---|---|---|
| `plan` | no | Enumerate the 104 source objects, URLs, expected ZIP/CSV names |
| `inventory` | HEAD only | Content-Length / conservative size estimate + disk-budget report |
| `acquire` | GET ZIP+CHECKSUM | Resume-safe download with PR #71 checksum filename identity, atomic adopt, fail-closed revision conflict |
| `audit-raw` | no | Re-verify every retained object (checksum, member name, schema, invariants) |
| `materialize-1m` | no | Canonical 1m parquet partitions parsed **from ZIP** (no permanent CSV) |
| `aggregate` | no | UTC-epoch 5m/15m/1h/4h with `is_complete` fail-closed incompleteness |
| `finalize` | no | Quality report, snapshot id, **candidate** manifest artifact |

`--stage all` runs them in order and requires `--allow-acquire` (bulk-history safety latch).

## Commands (later bulk execution)

From the repository root, with `PYTHONPATH` set as for other research scripts:

```bash
# 1. enumerate (no network)
python -m scripts.research.core_btc_binance_v0_materializer \
  --stage plan \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0

# 2. HEAD inventory + disk budget (no archive bodies)
python -m scripts.research.core_btc_binance_v0_materializer \
  --stage inventory \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0

# 3. acquire (explicit latch; one writer per dataset root)
python -m scripts.research.core_btc_binance_v0_materializer \
  --stage acquire --allow-acquire \
  --dataset-root artifacts/research_data/CORE_BTC_BINANCE_V0 \
  --disk-reserve-bytes 5368709120

# 4-7
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
implementation has passed.

## Output layout

```text
artifacts/research_data/CORE_BTC_BINANCE_V0/
  raw/monthly/YYYY-MM/BTCUSDT-1m-YYYY-MM.zip[.CHECKSUM]
  raw/daily/YYYY-MM-DD/BTCUSDT-1m-YYYY-MM-DD.zip[.CHECKSUM]
  canonical/1m/monthly/YYYY-MM.parquet
  canonical/1m/daily/YYYY-MM-DD.parquet
  canonical/5m/bars.parquet
  canonical/15m/bars.parquet
  canonical/1h/bars.parquet
  canonical/4h/bars.parquet
  reports/*.json, quality_report.md
  manifests/CORE_BTC_BINANCE_V0.candidate.json
```

`artifacts/` is gitignored. Dataset identity is snapshot hashes, not local
paths.

## Resume / revision / disk

- One writer per dataset root. No distributed lock.
- `.part` / leftover `.tmp` files are discarded and are never evidence.
- Verified ZIP bytes that still match the source checksum are reused
  (`REUSED_IDENTICAL`).
- A disagreeing checksum is `REVISION_CONFLICT`: ZIP **and** existing
  sidecar are left untouched (PR #71 RT-05).
- Canonical 1m partitions whose parquet bytes are unchanged are reused.
- Disk-safety gate: refuse acquire when
  `free < remaining_download + temp_bound + --disk-reserve-bytes`.
- Keep raw ZIPs (provenance). Do not extract CSVs permanently. Parse members
  from the ZIP in memory.

## Materialization / aggregation semantics

- 1m `available_at = open_time + 60s`. Never Binance `close_time`.
- Missing minutes are omitted, never filled.
- Identical duplicate rows: keep first (file order), record the duplicate.
- Conflicting duplicates (same `open_time`, different payload): drop the
  minute, record the conflict. Cross-object overlap is treated the same.
- Numeric validation uses `Decimal`. Canonical parquet stores OHLC/volume as
  **exact decimal strings** plus int64 timestamps/`trade_count` (zstd).
  Round-trip is deterministic. `taker_sell_*` is `DERIVED_FROM_KLINE`.
- HTF buckets are UTC epoch-aligned. A bucket is `is_complete=true` only
  with the exact constituent count (5/15/60/240). Incomplete buckets are
  **emitted** with null aggregates so research code can fail closed. They
  are never silently dropped and never presented as complete OHLC.
- HTF `available_at = bucket end`.

## Snapshot identity

`snapshot_id` is SHA-256 of a canonical JSON payload containing: dataset id,
contract file hash, frozen start/end, sorted per-object checksums, parser /
materializer / canonicalization / aggregation versions, quality-report hash,
and materialized output checksums. Timestamps and directory paths are not
the identity key.

## Quality report + gap diagnostic

`reports/quality_report.json` (and `.md`) record coverage, gaps, duplicates,
rejects, HTF incompleteness, sizes, and limitations.

Gap / extreme-market diagnostic (predeclared, not an edge rule): an adjacent
1m bar is flagged when `|close/open-1|` or `base_volume` is at or above the
**99th percentile** of the observed canonical 1m population. Gaps are never
repaired or excluded because of this flag.

A non-zero gap count does **not** automatically kill the eventual dataset
(contract §12). It must remain visible; incomplete HTF windows fail closed.

## Promotion vocabulary (this tool does not promote)

| State | Meaning |
|---|---|
| `PLANNED_NOT_MATERIALIZED` | Repository planning manifest today. `research_authorized: false`. |
| `MATERIALIZED_UNVERIFIED` | Candidate artifact after `finalize`. Bytes exist; not accepted. |
| `QUALITY_AUDITED` | Human reviewed the quality report. Still not discovery authorization. |
| `ACCEPTED_FOR_DISCOVERY` | Separate later gate. This CLI never writes that into `docs/manifests/CORE_BTC_BINANCE_V0.yaml`. |

`finalize` writes `manifests/CORE_BTC_BINANCE_V0.candidate.json` under the
dataset root only.

## Dependencies

Research/dev extra: `pyarrow` (see `requirements-dev.txt`) for parquet I/O.
Production `requirements.txt` is unchanged. pandas is already a project
dependency; pyarrow is the parquet engine and is **not** added to the
production image.
