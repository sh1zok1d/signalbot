# D7 confirmatory primary result

One authorized opening under `DETERMINISTIC_FIXED_SEED_V1`. The sealed machine artifact is `docs/research/D7_CONFIRMATORY_PRIMARY_RESULT_V1.json`, SHA-256 `b4efa972cec9acfacb2987be7aef3ad1ed239c8279977374a18265dfe60df503`. This note does not recompute the estimand.

## Identity

| Pin | Value |
| --- | --- |
| `SEED_SOURCE` | `DETERMINISTIC_FIXED_SEED_V1` |
| Amendment commit | `b603f55d7b12492bf813abac1537aa21f85932e4` |
| Amendment tree | `094f8123a5bf629a6a4ec7ed2991c6b6f1dbe605` |
| `CONFIRMATORY_SEED_DIGEST` | `5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e` |
| Canonical source SHA-256 | `33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c` |
| Adapter digest | `260dd8f6a30ff48a1cecdb306b4d5bb7c90930d5123095d08b9400234c51b579` |
| Decision-rule digest | `39c5a727ee6ac5c6877924670a6acc1520584b312ae6ddf49a206a2656e34751` |
| Statistical implementation digest | `3347d43575ac7532b9ae34a831a1783d95a4b9b3def923b35d4b099562d87d20` |
| NumPy | `2.1.3` |
| RECORD SHA-256 | `ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1` |

Pre-open flags were false. The identity check passed before the target parse.

## Primary numbers

`T = 30354`. Year masses `2016=4079`, `2017=8757`, `2018=8759`, `2019=8759`. Gap break `3503`. Segments `[3503, 26851]`. `B_T = L_T = 721`.

| Quantity | Value |
| --- | --- |
| `theta_hat` | `0.12932529232325488` (`0x1.08dbb2e897979p-3`) |
| `V_obs` | `2.458771532240802` (`0x1.3ab9068ba7afep+1`) |
| `SE(theta_hat)` | `0.009000178507085975` (`0x1.26eaf82c4ce2cp-7`) |
| `T_obs` | `14.369191924519624` (`0x1.cbd06b95384a7p+3`) |
| `R` | `9999` |
| `exceedance_count` | `0` |
| `p` | `0.0001` (`1/10000`) |
| `STATISTICAL_REJECT` | `true` |
| `L` | `0.1138795303766755` (`0x1.d27357aa6d32ep-4`) |
| `c` | `1.716161733283256` |

Year-level `theta_hat`:

| Year | Value | Role |
| --- | --- | --- |
| 2016 | `0.1357945428437761` | diagnostic |
| 2017 | `0.1556649226614804` | temporal |
| 2018 | `0.1268447223183365` | temporal |
| 2019 | `0.09454730105201403` | temporal |

`TEMPORAL_PASS = true`. All three of `{2017, 2018, 2019}` are defined and positive.

`MAGNITUDE_AT_0_05_SUPPORTED = true` because `L >= 0.05`. `MAGNITUDE_CLASS = MAGNITUDE_AT_0_05_SUPPORTED`. Magnitude is not part of the directional pass conjunction.

`INTEGRITY_PASS = true`. `inference_status = PRIMARY_COMPLETED`. `target_mutated = false`.

```
D7_DIRECTIONAL_CONFIRMATION_PASS = true
EVIDENCE_LABEL = CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS
PRIMARY_RESULT_SEALED = true
POST_OPEN_UNTHRESHOLDED_DIAGNOSTICS_CANNOT_CHANGE_PRIMARY_LABEL = true
CONFIRMATORY_RNG_GENERATED = true
D7_BITMEX_PRIMARY_TARGET_OPENED = true
D7_PRIMARY_EFFECT_COMPUTED = true
```

## What this establishes

Under the maintained DWB assumptions and the precommitted deterministic seed, the directional confirmatory test rejects `H0: theta <= 0`, the 2017–2019 year estimates are positive, and the one-sided lower bound `L` is at least `0.05`.

This label does not establish cellwise confirmation, assumption-free confirmation, verified mixing, trading profitability, or product use. The external-beacon unpredictability guarantee was removed by the seed-source amendment before this opening. No second seed was drawn.
