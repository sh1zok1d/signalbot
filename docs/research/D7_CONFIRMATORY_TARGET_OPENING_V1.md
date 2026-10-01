# D7 confirmatory target opening — execution stop

Authorized opening of the protected BitMEX target. The run stopped at NIST Beacon 2.0 signature verification. No confirmatory seed was generated. The canonical source was not parsed. No primary estimand was computed.

`EXECUTION_STATUS = D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_SIGNATURE_INVALID`

This is an execution failure. It is not a scientific outcome for the D7 hypothesis.

## Identity

The driver checked these pins before any beacon fetch and before any parse of the canonical source:

| Pin | Value |
| --- | --- |
| `CONFIRMATORY_FREEZE_COMMIT` | `5b3e5cdcedd615ae63bc2c2ff8eb804b5485b92b` |
| `FREEZE_MANIFEST_SHA256` | `2aaa228c40a486f3b7fa208ec62f3c19bb63318a65e8d7d19b8c1e211c751e07` |
| `ADAPTER_DIGEST` | `260dd8f6a30ff48a1cecdb306b4d5bb7c90930d5123095d08b9400234c51b579` |
| `DECISION_RULE_DIGEST` | `39c5a727ee6ac5c6877924670a6acc1520584b312ae6ddf49a206a2656e34751` |
| Canonical source SHA-256 | `33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c` |
| Statistical implementation digest | `3347d43575ac7532b9ae34a831a1783d95a4b9b3def923b35d4b099562d87d20` |
| NumPy | `2.1.3` |
| NumPy RECORD SHA-256 | `ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1` |

`identity_checks_passed_before_beacon_fetch = true`

## Beacon

Eligible instant: `2026-10-01T07:09:59Z`.

Selected pulse:

- URI `https://beacon.nist.gov/beacon/2.0/chain/2/pulse/1965184`
- `timeStamp = 2026-10-01T07:10:00.000Z`
- chain `2`, pulse index `1965184`
- `outputValue = 970B73CBD4D75BFFECC793A9F2C1B29287A6496C181C0410ACA0B517A36307C5B7ECE86C0FE42FAB494DA1E52B6ECF38271BBB5DB23C3ED5E29A07013677115D`
- raw HTTP body SHA-256 `276779a2d1f7a627acd4e891ddf5233feca22b5db7e194a9f3b1606894720c9a`
- body path `docs/research/D7_CONFIRMATORY_BEACON_PULSE_V1.json`
- certificate path `docs/research/D7_CONFIRMATORY_BEACON_CERTIFICATE_V1.crt`
- certificate PEM SHA-256 `c342339ca0fe5f1c522e03471b32811310371c3adbb8f107c8d77b5f336bfce9`

The previous pulse is index `1965183` at `2026-10-01T07:09:00.000Z`, which is before the eligible instant. The saved pulse is the first pulse at or after the cutoff.

Verification under the live NIST Beacon 2.0 uint32 length-prefix encoding:

- `outputValue` matches SHA-512 of the serialized fields plus the raw signature bytes.
- `certificateId` matches SHA-512 of the certificate DER.
- The certificate subject CN is `engine.beacon.nist.gov`. The RSA key is 2048 bits.
- `signatureValue` is 512 bytes.
- PKCS#1 v1.5 SHA-512 verification of that signature under this certificate fails.

`BEACON_SIGNATURE_VALID = false`

The same verifier accepts the 4096-bit chain-2 pulse at `2026-09-02T12:00:00.000Z`. Pulses that use the 2048-bit certificate, including `2026-09-04T12:00:00.000Z` and this eligible pulse, fail the signature check. Those earlier pulses were verifier checks. Their outputs were not used as a seed.

## What did not run

```
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
PRIMARY_RESULT_SEALED = false
target_source_parsed = false
```

`D7_DIRECTIONAL_CONFIRMATION_PASS`, `STATISTICAL_REJECT`, `TEMPORAL_PASS`, `INTEGRITY_PASS`, `theta_hat`, and the magnitude class are unevaluated. No second beacon and no second seed were created.
