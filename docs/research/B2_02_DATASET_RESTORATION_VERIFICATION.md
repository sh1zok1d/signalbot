# B2-02 Dataset Restoration Verification

**Status:** `FROZEN_EVIDENCE / INFRASTRUCTURE_ONLY`  
**Kind:** independent restoration verification against frozen snapshot `717d37a4`  
**GitHub abort comment:** PR #95 `issuecomment-5506886454`  
**Authorization comment:** PR #95 `issuecomment-5506806925`  
**Market verdict produced by this unit:** NO  
**`run_development()` called by this unit:** NO  
**2025 validation accessed:** NO  
**2026 OOS accessed:** NO

## 1. Why this record exists

Comment `5506886454` records a **pre-outcome environment abort**: the authorized
B2-02 execution SHA was present, identity passed, and the accepted
`CORE_BTC_BINANCE_V0` parquet/raw materialization was absent. That abort is
not a B2-02 research verdict.

The permitted next action from that comment is dataset restoration and
independent verification against frozen snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.

This document records that verification. It does not authorize a B2-02 rerun
and does not open 2025 or 2026.

## 2. Scope

Verified runtime root:

`/workspace/artifacts/research_data/CORE_BTC_BINANCE_V0`

Frozen checksum source:

`docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json`

Allowed restored objects: calendar years **2020, 2021, 2022, 2023, 2024** only.

Forbidden: any 2025 validation or 2026 OOS object, and any
`run_development()` call.

## 3. Independent byte verification

| Check | Result |
|---|---|
| Frozen snapshot file SHA256 | `a104a4036ed7b4c7a4a9954ce1aeee247b6bbbb91d6abf2563b78b6bd9f84630` MATCH |
| Frozen source-inventory file SHA256 | `a4bb39245365b1cc49b626a3dfc2cdcdb00c5be8c622ecd1e123a18d85186ea6` MATCH |
| Runtime `reports/snapshot_manifest.json` byte-identical to frozen snapshot | MATCH |
| Runtime `snapshot_id` | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| Canonical 1m monthly parquet 2020-2024 | **60 / 60** SHA256 MATCH |
| Canonical 1m monthly provenance 2020-2024 | **60 / 60** SHA256 MATCH |
| Raw monthly ZIP 2020-2024 vs snapshot `expected_sha256` and sidecar CHECKSUM | **60 / 60** MATCH |
| On-disk paths containing `2025` or `2026` | **none** |
| `run_development()` invoked during this verification | NO |

Machine-readable companion (not committed):
`/opt/cursor/artifacts/b2_02_dataset_restoration_verification.json`

Status: `VERIFIED_2020_2024_NO_2025_2026`.

## 4. Relation to the authorized development run

This verification does **not** un-consume a completed market verdict.

In this same restored environment, the one authorized
`run_development(a976a3fa…, outcome_access_acknowledged=True)` call already
persisted result SHA256
`971b645a0eb8b45293f7c2f589c9666a037fe602a6f228751162b13bf0054646` with
verdict `B2_02_CLOSED_NO_PROMOTION`. See
`docs/research/B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md`.

Comment `5506886454` remains a valid abort record for any environment that
lacked the accepted parquet/raw bytes and did not call `run_development()`.
It is not a license to treat this environment's already-read development
outcomes as unopened, and it does not authorize a second development run.

```text
ABORT_5506886454 = PRE_OUTCOME_INFRASTRUCTURE_ABORT
DATASET_2020_2024 = VERIFIED_AGAINST_717d37a4
B2_02_RERUN = NOT_AUTHORIZED
2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```

## 5. Final integrity statement

`No 2025 validation or 2026 OOS object was restored or hashed as part of this verification.`
