# D7 confirmatory seed-source amendment

Pre-target execution-contract amendment. The BitMEX target is unopened, theta is unknown, no confirmatory seed has been drawn into the bootstrap, and no confirmatory RNG stream has been consumed.

```
SEED_SOURCE_CHANGE = NIST_BEACON_2_0 -> DETERMINISTIC_FIXED_SEED_V1
```

The precommitted NIST Beacon 2.0 source is currently unusable for this confirmation. Eligible pulses examined after the cutoff name an RSA-2048 certificate and carry 512-byte signatures that cannot verify under that named key. The scan classified 72 consecutive pulses `INVALID` and selected none. This amendment removes NIST Beacon 2.0 as the D7 confirmatory seed source. It does not classify NIST itself as permanently unusable.

```
D7_NIST_BEACON_SCAN_STATUS = SUPERSEDED_BY_SEED_SOURCE_AMENDMENT
```

Pulse `1965184`, the verifier repair, the 72 `INVALID` ledger rows, the scan cursor, and the NIST provenance stay in the repository as the historical audit trail.

## Seed message

`SEED_MESSAGE_ENCODING = UTF-8`

`SEED_MESSAGE_TRAILING_NEWLINE = false`

`SEED_MESSAGE_CANONICALIZATION = EXACT_BYTES_ABOVE`

Exact UTF-8 bytes, with no trailing newline:

```
{"hypothesis":"D7","profile":"SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1","project":"signalbot","purpose":"CONFIRMATORY_DWB_MULTIPLIERS","r_confirmatory":9999,"scheme":"DETERMINISTIC_FIXED_SEED_V1"}
```

Independently recomputed SHA-256:

```
CONFIRMATORY_SEED_DIGEST = 5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e
```

The digest is not derived from the canonical target SHA-256, the adapter digest, cell margins, candidate margins, `K`, `pi_s`, year masses, target bytes, any BitMEX statistic, or `FREEZE_MANIFEST_SHA256`.

## Downstream RNG

The amendment changes only the source of the 256-bit seed digest. Downstream remains:

```
CONFIRMATORY_BIT_GENERATOR = NUMPY_PCG64
NUMPY_VERSION = 2.1.3
NUMPY_RECORD_SHA256 = ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1
```

All 256 bits are the entropy input of the existing `seed_sequence_from_digest` conversion: eight little-endian uint32 words, no truncation, no additional hashing, no salt, and no HMAC. This amendment unit does not construct the confirmatory PCG64 stream and does not draw multipliers.

## Statistical identity

```
STATISTICAL_PROCEDURE_CHANGED = false
```

Unchanged: the estimand, `H0: theta <= 0`, `STUDENTIZED_FULL_IF_DWB`, `R_CONFIRMATORY = 9999`, `B = L = 721`, the full-IF construction, deterministic-year variance centering, bootstrap studentizer recomputation, the temporal rule, the directional confirmation rule, magnitude classification, and integrity checks unrelated to NIST.

## Guarantee change

The external-beacon design protected against choosing a favorable PRNG seed after the contract was frozen. The deterministic replacement uses a target that stays procedurally sealed until this amendment is committed and externally timestamped, one fixed literal seed message, and one fixed digest. There is no menu of alternative seeds after target access.

```
EXTERNAL_UNPREDICTABILITY_GUARANTEE = REMOVED
PRE_TARGET_SEED_COMMITMENT = PRESERVED
```

These are not the same guarantee.

## Flags

```
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
SELECTED_CONFIRMATORY_BEACON = NONE
```
