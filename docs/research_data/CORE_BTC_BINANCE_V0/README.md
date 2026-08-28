# CORE_BTC_BINANCE_V0 accepted snapshot evidence

**Status:** FROZEN_EVIDENCE
**Snapshot ID:** `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
**Materializer commit:** `71d13afdae4456163316b850f340436af1eeed65`

These files are byte-identical copies of the runtime artifacts under the
gitignored dataset root `artifacts/research_data/CORE_BTC_BINANCE_V0/`.
No machine-local paths were stripped. Archival SHA-256 therefore equals
the runtime evidence hash.

| Archival file | Runtime source | SHA-256 |
|---|---|---|
| `SNAPSHOT_717d37a4.json` | `reports/snapshot_manifest.json` | `a104a4036ed7b4c7a4a9954ce1aeee247b6bbbb91d6abf2563b78b6bd9f84630` |
| `SOURCE_INVENTORY_717d37a4.json` | `reports/source_inventory.json` | `a4bb39245365b1cc49b626a3dfc2cdcdb00c5be8c622ecd1e123a18d85186ea6` |
| `QUALITY_REPORT_717d37a4.json` | `reports/quality_report.json` | `c59034e41be571142232d9c283ba898c786b69d6db485dfd2f4641bc84601242` |
| `QUALITY_REPORT_717d37a4.md` | `reports/quality_report.md` | `8ae41dfd777882c2456614ed1385536b2755edc4a6291661449e3627a0b8f85d` |

Identity fields frozen by the promotion:

- `snapshot_id` = `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- `quality_report_sha256` = `c59034e41be571142232d9c283ba898c786b69d6db485dfd2f4641bc84601242` (JSON file bytes)
- `source_inventory_sha256` = `a4bb39245365b1cc49b626a3dfc2cdcdb00c5be8c622ecd1e123a18d85186ea6`
- `contract_sha256` = `1c49c8205a92eb9491a065fa1e93bb1fa5592964babdf96fe30b09212e962d3e` (`docs/CORE_BTC_BINANCE_V0_CONTRACT.md`)
- `materializer_commit_sha` = `71d13afdae4456163316b850f340436af1eeed65`

Not committed here (and must not be): raw ZIP/CHECKSUM files, canonical 1m parquet, HTF parquet, lock/temporary files. Checksums for those outputs live inside `SNAPSHOT_717d37a4.json`.

Canonical repository manifest: `docs/manifests/CORE_BTC_BINANCE_V0.yaml`.
