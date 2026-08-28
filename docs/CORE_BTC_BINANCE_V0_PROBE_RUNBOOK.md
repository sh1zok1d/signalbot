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

`CORE_BTC_BINANCE_V0_probe_inventory.json` has a `schema_version`
(currently `2`), a `probe_tool_version`, a `month_pass_predicate_version`,
a `provenance_git_commit_sha` (auto-detected via `git rev-parse HEAD`,
overridable with `--provenance-git-commit-sha`, `"UNKNOWN"` if neither is
available -- never allowed to crash the run), a `mode`, and one record per
requested month under `months`, each carrying:

- identity (`provider`, `market_type`, `symbol`, `interval`, `year_month`,
  and the exact `expected_zip_filename` / `expected_csv_member_name` this
  month must match);
- the exact `source_url` / `checksum_url` used;
- `source_status` — `HTTP_200`, `HTTP_404`, `HTTP_<code>`,
  `NETWORK_ERROR:<...>`, `REUSED_IDENTICAL`, `REUSED_UNVERIFIED_NO_REFERENCE`,
  `REVISION_CONFLICT`, `LOCAL_FILE_PRESENT` (audit-local -- **never**
  `HTTP_200`, even for a perfect local file: audit-local never confirms
  network reachability), `NO_LOCAL_FILE` (audit-local), or `NOT_REQUESTED`
  (inventory). Source absence is always recorded explicitly — never
  silently treated as success;
- `checksum_observed_filename` (the filename embedded in the `.CHECKSUM`
  text itself, GNU `*` binary-mode marker normalized), `expected_sha256` /
  `local_sha256` / `checksum_verification`:
  `VERIFIED` (sha256 matches **and** the checksum's own filename identifies
  exactly `expected_zip_filename` -- a correct hash paired with a wrong
  symbol/month/interval/daily filename, or no filename at all, is
  `FILENAME_IDENTITY_MISMATCH`, never `VERIFIED`), `MISMATCH`,
  `FILENAME_IDENTITY_MISMATCH`, `NOT_VERIFIABLE_MISSING_CHECKSUM`, or
  `NOT_ATTEMPTED` — a mismatched, misidentified, or unverifiable checksum
  never receives `month_passed`/`local_audit_passed: true`;
- `zip_member_names` (the archive's full, unfiltered member list --
  reported for diagnostics even when rejected) / `parser_status`
  (`OK`, `NO_SUCH_FILE`, `EMPTY_ARCHIVE`, `MISSING_EXPECTED_CSV_MEMBER`,
  `BAD_ZIP_FILE`) / `header_present`. **There is no "sole CSV in the
  archive" fallback** — the archive must contain the exact member
  `expected_csv_member_name`; a differently-named CSV (wrong symbol,
  interval, a daily-shaped filename, or a path-prefixed/path-traversal
  name) is `MISSING_EXPECTED_CSV_MEMBER` even if it is the only CSV
  present;
- the structural audit: `expected_rows`, `observed_rows`,
  `observed_unique_open_times`, `missing_bucket_count`,
  `missing_open_time_ranges_ms` (exact `[start_ms, end_ms]` ranges, not just
  a count), `duplicate_count`, `duplicate_open_times`,
  `malformed_row_count`, `invariant_violation_count`,
  `invariant_violations`, `is_strictly_ordered_by_open_time`,
  `first_open_time_ms`, `last_open_time_ms`. Every numeric market field
  (`open`/`high`/`low`/`close`/volumes) is checked for finiteness before any
  ordered comparison; NaN/Infinity/-Infinity is always reported as a
  `<field>_not_finite` violation (or excluded at parse time as malformed),
  never allowed to crash the audit;
- `month_passed` — whether *that month* supports the basic source
  assumptions AND was confirmed reachable over the network this run (see
  below);
- `local_audit_passed` — the `audit-local`-only counterpart (`null` in
  `probe`/`inventory` mode).

The top-level `overall_status` is one of:

- `SOURCE_PROBE_PASSED` / `SOURCE_PROBE_FAILED` / `SOURCE_PROBE_INCOMPLETE`
  — for `--mode probe`/`--mode inventory`, driven by `month_passed`;
- `LOCAL_AUDIT_PASSED` / `LOCAL_AUDIT_FAILED` / `LOCAL_AUDIT_INCOMPLETE` —
  for `--mode audit-local`, driven by `local_audit_passed`. This vocabulary
  is deliberately kept separate from `SOURCE_PROBE_*`: `audit-local` never
  makes a network request, so it can never honestly claim
  `SOURCE_PROBE_PASSED` — see "Local audit vs. network probe" below.

Process exit code: `0` for `SOURCE_PROBE_PASSED`/`LOCAL_AUDIT_PASSED` (and
always for `--mode inventory`), non-zero (`1`) otherwise.

### What `month_passed` / `local_audit_passed` mean (and do not mean)

For **this four-month source-capability probe**, a month passes only when
the canonical monthly grid is **exactly complete**: checksum-verified
(including filename identity), the archive parsed deterministically into
the 12-column schema with **zero** malformed rows, **zero** duplicate
timestamps, **zero** rows outside the month's own bounds, **zero** row-level
structural-invariant violations, rows strictly ordered by `open_time`,
`observed_unique_open_times == expected_rows`, and the first/last observed
minute landing exactly on the month's own UTC start/end boundaries. An
empty CSV, a header-only CSV, a single row, a gap of any size (first
minute, last minute, or one internal minute), or rows drawn from the wrong
month **all fail** this check.

**This is intentionally stricter than the later full-dataset policy.** Do
NOT read this as "the eventual multi-year dataset must contain zero
exchange gaps" — `docs/CORE_BTC_BINANCE_V0_CONTRACT.md` §12 states a
non-zero gap count does not automatically kill that later, much larger
dataset; genuine historical gaps are a separate question the full
materializer's continuity audit answers on its own terms. This probe asks a
narrower, prior question: *did the expected official monthly archive
object, for these four hand-picked, low-risk months, contain a canonical,
complete monthly 1m grid?* A tool that let an empty or partial response
answer "yes" to that question was the exact defect this predicate exists to
close.

### Local audit vs. network probe (`local_audit_passed` vs. `month_passed`)

`--mode audit-local` never makes a network request, so it can prove
checksum-verified, structurally complete evidence from whatever `.zip`/
`.CHECKSUM` pair is already on disk — but it can never prove Binance
currently serves that object at the documented path. `local_audit_passed`
carries that (weaker, local-only) claim; `month_passed` stays `False` for
every `audit-local` record regardless of how clean the local evidence is.
A perfect local ZIP + matching checksum + complete valid month is fully
capable of reaching `local_audit_passed: true` / `overall_status:
LOCAL_AUDIT_PASSED` — it is just never mislabeled as an HTTP acquisition.

## Why `SOURCE_PROBE_PASSED`/`LOCAL_AUDIT_PASSED` != `DATASET_ACCEPTED`

`SOURCE_PROBE_PASSED` means four hand-picked months across different eras
were reachable, checksum-verified (identity included), and internally
calendar-complete. `LOCAL_AUDIT_PASSED` means the same, minus the network-
reachability claim. Neither says anything about:

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

### Write safety

On a `REVISION_CONFLICT`, this tool writes **nothing at all** for that
month — neither the existing `.zip` nor its `.CHECKSUM` sidecar is touched,
even though the checksum request itself has already completed by the time
the conflict is detected (the freshly observed remote checksum is recorded
in the report only). Every other write (a freshly downloaded `.zip`, a
missing `.CHECKSUM` sidecar being filled in, the JSON report itself) goes
through a temp-file-plus-`os.replace` atomic write, and an existing
sidecar file is never overwritten once present. This tool assumes **one
writer per output directory** — it does not implement process locking; do
not run two probes concurrently against the same `--output-dir`.

### Provenance

Every report records `probe_tool_version`, `month_pass_predicate_version`,
and `provenance_git_commit_sha`, so a later reader can tell which version of
this tool's completeness/identity predicates produced a given result,
independent of the report's own `schema_version`.

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
