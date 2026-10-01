# D7 beacon verifier repair

Pre-seed, outcome-blind repair of the NIST Beacon 2.0 verifier. This unit does not parse the BitMEX target, compute D7, generate a confirmatory seed, initialize the confirmatory RNG, or fetch any pulse after `1965184`.

## Validity

A NIST Beacon 2.0 pulse is `VALID` only when every required integrity and cryptographic check passes under the certificate identified by that pulse's own `certificateId`.

The named certificate is the only key used for signature verification. A pulse does not become valid because its signature verifies under some other historical certificate. Pulse `1965184` stays invalid if it does not verify under the certificate named by its own `certificateId`, including in the case where some older NIST key accepts the signature.

`outputValue` is a protocol-integrity check. It is not a selection score and it is not compared for randomness quality.

The signed preimage is fields F1–F19. UTF-8 strings and 64-byte hashes carry an unsigned uint32 big-endian length prefix of their actual byte length. `cipherSuite`, `period`, external `statusCode`, and pulse `statusCode` are uint32. `chainIndex` and `pulseIndex` are uint64.

The `outputValue` preimage is that signed preimage concatenated with the raw signature octets. Preserved NIST pulses match SHA-512 of that concatenation. The signature is not stored in a fixed 512-byte field. A 256-byte signature contributes 256 octets. A 512-byte signature contributes 512 octets.

PKCS#1 v1.5 SHA-512 verification requires:

`signature_length_bytes == ceil(public_key_modulus_bits / 8)`

for the named certificate, and the RSA representative condition `0 <= s < n`.

## Pulse 1965184

Preserved bytes only: `docs/research/D7_CONFIRMATORY_BEACON_PULSE_V1.json` and `docs/research/D7_CONFIRMATORY_BEACON_CERTIFICATE_V1.crt`.

| Fact | Value |
| --- | --- |
| `RSA_MODULUS_BITS` | 2048 |
| `RSA_MODULUS_BYTES` | 256 |
| `SIGNATURE_BYTES` | 512 |
| `SIGNATURE_INTEGER_LT_MODULUS` | false |
| `certificateId` vs SHA-512 of certificate DER | match |
| Named key | RSA |
| Classification | `PULSE_1965184_OBJECTIVELY_INVALID` |

The signature integer cannot be an RSA representative of the named 2048-bit key. That classification does not depend on the signed-preimage byte layout. The output-preimage check remains a protocol control on these same bytes.

## Future scan

A later candidate may be skipped only after it has been fetched completely and classified `INVALID`.

These are not `INVALID` and do not authorize advancing:

- HTTP timeout
- DNS or network failure
- TLS failure
- truncated response
- malformed transport response
- HTTP 5xx
- unexpected 404 where the pulse should exist
- failure to fetch the named certificate
- failure to finish cryptographic verification

Each of those stops the scan with `BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE`.

For every successfully fetched successor, continuity requires `candidate.listValues[type=previous].value == previous_pulse.outputValue`. If that link is not established, the scan stops with `BEACON_CHAIN_CONTINUITY_FAILED` and does not skip the gap.

The selection rule remains the first valid NIST Beacon 2.0 pulse. It is not "the first valid pulse on chain 2". Traversal uses the Beacon 2.0 chronological successor, the `pulse/time/next` endpoint. Every candidate records `chainIndex`, `pulseIndex`, and timestamp. A new chain index does not, by itself, make a candidate ineligible.

Scanned candidates after `1965184` are stored as compact records: `chainIndex`, `pulseIndex`, timestamp, SHA-256 of the raw pulse bytes, `certificateId`, RSA modulus bytes, signature bytes, chain-continuity status, cryptographic verification status, and classification. Full raw bodies are kept for the ultimately selected pulse and for materially diagnostic boundary cases. This unit does not create those scan records.

## Partial execution

Pulse `1965184` was never a selected beacon. It failed the pre-existing valid-pulse predicate: the signature did not verify under its named certificate. No confirmatory seed was generated. The confirmatory RNG was never initialized. The target source was never parsed. No D7 estimand was computed.

Searching forward for the first valid pulse under the already frozen selection rule is pre-selection beacon resolution. It is not a second beacon, not a second seed, and not a second statistical execution.

The statement "no new beacon or seed is created after a partial execution" still holds. No beacon was selected and no seed exists.

## Source replacement

This unit does not change the randomness-source rule. If the NIST Beacon 2.0 service remains unusable, a proposal to replace the source requires a separate outcome-blind contract amendment with its own independently server-timestamped future cutoff, written before any replacement-source output is observed. This repair neither authorizes nor permanently forbids that amendment.

## Flags

```
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CANDIDATES_AFTER_1965184_FETCHED = false
NEXT_ACTION = READY_FOR_SEQUENTIAL_NIST_BEACON_SCAN_FROM_AFTER_1965184
```

`NEXT_ACTION` is the status of this repair unit after its tests pass. This document does not perform that scan.
