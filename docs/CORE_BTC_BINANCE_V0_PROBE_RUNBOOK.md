# CORE_BTC_BINANCE_V0 Source Probe — Runbook

**Status:** ACTIVE / RESEARCH INFRASTRUCTURE
**Tool:** `scripts/research/core_btc_binance_v0_probe.py`
**Contract:** `docs/CORE_BTC_BINANCE_V0_CONTRACT.md`
**Manifest:** `docs/manifests/CORE_BTC_BINANCE_V0.yaml`

## Purpose

Prove or falsify the basic source-capability assumptions behind
`CORE_BTC_BINANCE_V0` — that the official Binance USD-M futures BTCUSDT 1m
kline archive exists at the documented path shape, publishes a verifiable
checksum, and parses into the frozen 12-column schema with sane structural
properties — on a small, fixed set of historical months, **before** any
bulk multi-year acquisition is attempted.

## Explicit non-goals

- This is **not** the multi-year materializer. It never backfills 2020–2026
  in bulk.
- It does not change forecasting/V1/V2/E1 semantics, production ingestion,
  runtime, or config.
- It does not mark `docs/manifests/CORE_BTC_BINANCE_V0.yaml` as
  `research_authorized: true`, and it never promotes the manifest's
  `current_state` past `PLANNED_NOT_MATERIALIZED`.
- It does not consume a research/OOS window — the four probe months are
  source-capability probes, not development/discovery/confirmatory windows
  under `docs/EDGE_RESEARCH_PROTOCOL.md`.
- It does not repair, fill, or deduplicate anything. Missing bars, duplicate
  timestamps, and malformed rows are reported, never silently fixed.

## Commands

All commands are run from the repository root with the repo on
`PYTHONPATH` (matching the existing `scripts/research/v2_e1_*` convention),
e.g. via `python -m`:

```bash
# 1. inventory-only / dry-run: print the exact URLs, no network access
python -m scripts.research.core_btc_binance_v0_probe --mode inventory

# 2. probe: download + checksum-verify + structurally audit the requested
#    months into --output-dir
python -m scripts.research.core_btc_binance_v0_probe --mode probe \
  --output-dir artifacts/research_data_probe

# 3. audit-local: re-run the structural audit against already-downloaded
#    files with no network access at all
python -m scripts.research.core_btc_binance_v0_probe --mode audit-local \
  --output-dir artifacts/research_data_probe
```

Override the default probe months (`2020-01 2021-05 2024-03 2026-07`) with
`--months YYYY-MM [YYYY-MM ...]`. Do not use an override to start a bulk
backfill — this tool has no continuation/resume state and is not designed
for that.

## Output layout

```text
artifacts/research_data_probe/
  BTCUSDT-1m-2020-01.zip              # raw archive object, retained as-is
  BTCUSDT-1m-2020-01.zip.CHECKSUM     # raw checksum object, retained as-is
  BTCUSDT-1m-2021-05.zip
  BTCUSDT-1m-2021-05.zip.CHECKSUM
  ...
  CORE_BTC_BINANCE_V0_probe_inventory.json   # the machine-readable report
```

Both the raw `.zip` and its `.CHECKSUM` sidecar are kept exactly as
published so `audit-local` can re-verify and re-parse them without any
network access, and so a human can independently re-run `sha256sum` against
them.

## Interpreting the report

`CORE_BTC_BINANCE_V0_probe_inventory.json` has a `schema_version`, a `mode`,
and one record per requested month under `months`, each carrying:

- identity (`provider`, `market_type`, `symbol`, `interval`, `year_month`);
- the exact `source_url` / `checksum_url` used;
- `source_status` — `HTTP_200`, `HTTP_404`, `HTTP_<code>`,
  `NETWORK_ERROR:<...>`, `REUSED_IDENTICAL`, `REUSED_UNVERIFIED_NO_REFERENCE`,
  `REVISION_CONFLICT`, `NO_LOCAL_FILE` (audit-local), or `NOT_REQUESTED`
  (inventory). Source absence is always recorded explicitly — never
  silently treated as success;
- `expected_sha256` / `local_sha256` / `checksum_verification`
  (`VERIFIED`, `MISMATCH`, `NOT_VERIFIABLE_MISSING_CHECKSUM`,
  `NOT_ATTEMPTED`) — a mismatched or unverifiable checksum never receives
  `month_passed: true`;
- `zip_member_names` / `parser_status` / `header_present`;
- the structural audit: `expected_rows`, `observed_rows`,
  `observed_unique_open_times`, `missing_bucket_count`,
  `missing_open_time_ranges_ms` (exact `[start_ms, end_ms]` ranges, not just
  a count), `duplicate_count`, `duplicate_open_times`,
  `malformed_row_count`, `invariant_violation_count`,
  `invariant_violations`, `is_strictly_ordered_by_open_time`,
  `first_open_time_ms`, `last_open_time_ms`;
- `month_passed` — whether *that month* supports the basic source
  assumptions (see below).

The top-level `overall_status` is one of:

- `SOURCE_PROBE_PASSED` — every requested month was attempted and passed;
- `SOURCE_PROBE_FAILED` — every requested month was attempted, at least one
  failed;
- `SOURCE_PROBE_INCOMPLETE` — no months were requested, or `--mode
  inventory` was used (nothing was actually attempted).

### What `month_passed` means (and does not mean)

A month passes when: the source object was reachable, its checksum was
independently verified (`local_sha256 == expected_sha256`), the archive
parsed deterministically into the 12-column schema with **zero** malformed
rows, **zero** duplicate timestamps, **zero** row-level structural-invariant
violations, and the parsed rows are strictly ordered by `open_time`.

A **non-zero `missing_bucket_count` does not fail `month_passed`** —
`docs/CORE_BTC_BINANCE_V0_CONTRACT.md` §12 states a non-zero gap count does
not automatically kill the dataset. Continuity is a real, separate finding
that must still be inspected; it is just not the same question as "does
this source/schema/checksum behave the way the contract assumes."

## Why `SOURCE_PROBE_PASSED` != `DATASET_ACCEPTED`

`SOURCE_PROBE_PASSED` means four hand-picked months across different eras
were reachable, checksum-verified, and internally well-formed. It says
nothing about:

- continuity across the full `2020-01 → 2026-07` monthly range plus the
  `2026-08` daily tail;
- whether any month outside the four probed has a different archive shape,
  a missing checksum, or a revision history;
- the deterministic higher-timeframe aggregation (`5m/15m/1h/4h`);
- a frozen source-object inventory, output-checksum/snapshot identity, or a
  human-readable quality report.

`docs/CORE_BTC_BINANCE_V0_CONTRACT.md` §11–§12 defines the real promotion
sequence — `PLANNED_NOT_MATERIALIZED → MATERIALIZED_UNVERIFIED →
QUALITY_AUDITED → ACCEPTED_FOR_DISCOVERY` — and this probe does not advance
`docs/manifests/CORE_BTC_BINANCE_V0.yaml` along it. Only the full
materializer, continuity audit, and the explicit acceptance gates in the
contract may do that.

## Rerunning deterministically

Every URL, filename, and audit computation in this tool is a pure function
of `(provider, market, symbol, interval, year_month)` and the bytes
actually retrieved — see `scripts/research/core_btc_binance_v0_probe_lib.py`.
Re-running `--mode probe` against an output directory that already has a
verified `.zip`/`.CHECKSUM` pair reuses the existing file rather than
re-downloading (`REUSED_IDENTICAL`); it never silently overwrites a file
whose bytes disagree with the source's own published checksum
(`REVISION_CONFLICT` — the old revision is left untouched; move it aside or
use a different `--output-dir` to adopt a new one). `--mode audit-local`
re-derives the entire structural-audit section from the files already on
disk with no network calls at all, so its output is exactly reproducible
from the retained raw files alone.

## What evidence is required before bulk acquisition

Per `docs/DATA_CAPABILITY_MATRIX.md` §8 (Phase A) and
`docs/CORE_BTC_BINANCE_V0_CONTRACT.md` §15, this probe is only the first
deliverable. Before a full `2020-01 → 2026-07` monthly (+ `2026-08` daily)
acquisition begins, the next research-infrastructure work still needs:

1. a deterministic full-range archive downloader/inventory builder (this
   tool generalized past four fixed months, with resume/continuation
   state);
2. the same checksum-gate and structural audit applied to every month, not
   four samples;
3. a continuity + duplicate + invariant audit over the whole target range;
4. a deterministic higher-timeframe (`5m/15m/1h/4h`) aggregator;
5. population of `docs/manifests/CORE_BTC_BINANCE_V0.yaml`'s real source
   inventory, quality statistics, and materialization identity fields;
6. an immutable quality report/snapshot identity;
7. only then, evaluation against the `ACCEPTED_FOR_DISCOVERY` gates in
   `docs/CORE_BTC_BINANCE_V0_CONTRACT.md` §12.

`SOURCE_PROBE_PASSED` from this tool is necessary evidence to start that
work with confidence in the basic source assumptions — it is not a
substitute for any of it.
