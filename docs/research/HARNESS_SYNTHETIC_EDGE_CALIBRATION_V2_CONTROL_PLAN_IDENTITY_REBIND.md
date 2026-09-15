# V2 control plan identity rebind

**Status:** `IMPLEMENTATION_COMPLETE_AWAITING_IDENTITY_REBIND_REVIEW`  
**Unit:** identity/provenance repair only  
**Not:** a freeze, ARM, reservation, calibration, RESULT mint, or scientific change

The independently reviewed confirmatory-power repair at
`dfd05b6b45eee12660ea4c5914fc781bd327104b` produces:

```text
canonical_v2_plan.sha256 =
b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f
world_count = 3200
```

`canonical_v2_plan` embeds the V2 rank-policy source digest. The repaired
rank-policy bytes therefore change the plan SHA even though the 3200-world
job list is unchanged (`v1_planned_jobs_sha256` remains
`5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6`).

This unit rebinds production authority to that live plan identity:

```text
FROZEN_CANONICAL_V2_PLAN_SHA256 =
b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f
```

The previous hardcoded identity
`7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800`
remains the historical plan SHA of the unrepaired implementation
`baf9f23045f4c19418eaaf3a9a7a1b69e21aff98` and of already-minted canonical
evidence. Those artifacts are not rewritten.

## Unchanged

- rank-policy scientific bytes versus the reviewed repair
- inherited ladder
- DGP / scenarios / sample sizes / candidate library
- world count and world identities
- bootstrap / placebo / MODEL_DETECTED / STRICT_PASS / materiality / Wilson floors
- old WORLD_RECORDS `d372eb00…`
- old VISIBILITY `9be8dceb…`
- old RESULT `761cc9af…`

## Not done in this unit

- production freeze
- ARM
- reservation
- 3200-world execution
- RESULT mint
