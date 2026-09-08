# B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0 snapshot evidence

**Status:** `SNAPSHOT_MATERIALIZED_NOT_RESEARCH_AUTHORIZED`
**Snapshot ID:** `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`
**Materializer commit:** `78d5bdf9d5686b740ebc48e46227bbf0f990cbbe`
**Materializer tree:** `2b3e48ba36dd19f40a00fabe5c1a548b0b94d72f`

These files are byte-identical copies of the runtime artifacts under the
gitignored dataset root `artifacts/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/`.

| Archival file | Runtime source | SHA-256 |
|---|---|---|
| `SNAPSHOT_5a9d036b.json` | `reports/snapshot_manifest.json` | `bb216f9abdb9fcd7c7648bbffb8541e811af06498d062faa5f31037793768e5e` |
| `OBJECT_LEDGER_5a9d036b.json` | `reports/object_ledger.json` | `521d42a471cc5fec74d808e8a4a3ea0078c87342b801df5dbf3836b4b69b4296` |
| `QUALITY_REPORT_5a9d036b.json` | `reports/quality_report.json` | `a6b46df8350871bd737f02197b201b58d6069b19896d1767bda4c286bdc6c7b3` |

Joint period `[2020-09-01, 2025-01-01)`:

- OI objects expected/fetched/accepted/rejected = 1583 / 1583 / 1583 / 0
- funding objects expected/fetched/accepted/rejected = 52 / 52 / 52 / 0
- raw container bytes = 18564934
- normalized JSONL bytes = 256788119

Authorization remains closed:

- `research_authorized = false`
- `outcome_access_authorized = false`
- `b2_06_evaluator_enabled = false`
- funding publication = `FUNDING_PUBLICATION_LATENCY_UNPROVEN`

## Durability

- Raw ZIP bytes are gitignored and not currently retained in Git.
- Normalized JSONL bytes are gitignored and not currently retained in Git.
- `.CHECKSUM` sidecars are transient corroborating evidence only; they are not Git-retained.
- This snapshot proves exact historical existence/identity at materialization time.
- Exact future recovery depends on upstream Binance Vision bytes remaining available and unchanged unless separate durable retention is added.
- This repository does not currently claim local recoverability of the raw or normalized bytes.
- Durability status: `IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED`.
- Checksum sidecar status: `TRANSIENT_CORROBORATING_EVIDENCE_NOT_GIT_RETAINED`.

Canonical repository manifest: `docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml`.
