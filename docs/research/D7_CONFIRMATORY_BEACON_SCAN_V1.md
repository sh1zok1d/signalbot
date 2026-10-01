# D7 confirmatory beacon scan

Outcome-blind sequential NIST Beacon 2.0 scan. It starts strictly after pulse `1965184`, already classified `PULSE_1965184_OBJECTIVELY_INVALID`. The verifier is the frozen repair at commit `d7f7687a6b30f9d5193b77ec8f4c3f94ec54c379`, tree `8b47c2422f54d1e3f8f62aaf85e8eb37274cf3c3`, git blob `bed8a2aa33599b7ce4c0915eb410ad7413747b1d`, content SHA-256 `eff4533d2094e014fa2fb28ad2afb2b2395edaf766569930974d22954b2192e1`. This unit does not modify that verifier.

This unit does not parse the BitMEX target, compute D7, generate a confirmatory seed, or initialize the confirmatory RNG. `outputValue` is used only for chain continuity and the frozen output-integrity check.

## Scan range

| Fact | Value |
| --- | --- |
| First candidate | `2/1965185` at `2026-10-01T07:11:00.000Z` |
| Last candidate | `2/1965225` at `2026-10-01T07:51:00.000Z` |
| Examined | 41 |
| Index step | 1 |
| Timestamp step | 60 seconds |
| Chain transition | none; every examined pulse is chain 2 |

Traversal used `pulse/time/next`. The operational batch limit of 1000 was not reached.

## Classification

| Status | Count |
| --- | --- |
| `VALID` | 0 |
| `INVALID` | 41 |
| Incomplete | 1 |

Every examined pulse classified `PULSE_{pulseIndex}_OBJECTIVELY_INVALID` under certificate `87f27f431da3f584af6007fe045df13aaa81d831f335b6ee73f6334768f32d3ae10491e669b93a43e548b20370a6526c3def99643c25d8ad7bf5df95a3c2b45d`, the same certificate named by pulse `1965184`. Each row records modulus 256 bytes, signature 512 bytes, continuity `PASS`, signature verification `FAIL`, and output integrity `PASS`.

The chronological successor of `2/1965225` returned HTTP 404. That fetch is incomplete. It is not an `INVALID` classification, and the cursor was not advanced past it.

## Continuity

All 41 traversed edges passed `candidate.previous == previous_pulse.outputValue`.

## Selection

```
SELECTED_CONFIRMATORY_BEACON = NONE
```

## Cursor

```
LAST_COMPLETELY_CLASSIFIED_CANDIDATE = 2/1965225
NEXT_REQUIRED_CANDIDATE = chronological successor of 2/1965225
```

The raw body of `2/1965225` is `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1_CURSOR.json`, SHA-256 `f00f7cd52c24880f40bc85c0601d399936e06246a4ac503398fb53918768cbfb`. Compact rows are `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.jsonl`, SHA-256 `ddf2f01765b14104b31b7aee801e7c6f655285555d1b7543e0096157dda7a742`. The first examined raw SHA-256 is `31904dbc32a5b67779132d743af2d4d96f54b0f2cdedd1eda5c7b422a661290c`.

## Flags

```
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
NEXT_ACTION = BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE
```

A later invocation, if authorized, begins at the chronological successor of `2/1965225`. This invocation does not retry that 404 and does not inspect any later pulse.

## Resume at the successor of 2/1965225

Same scan identity `D7_CONFIRMATORY_BEACON_SCAN_V1`, invocation 2. The first 41 ledger rows are unchanged. The retry fetched the chronological successor of `2/1965225` again. That pulse is `2/1965226` at `2026-10-01T07:52:00.000Z`. It was not treated as invalid because of the earlier HTTP 404.

| Fact | Value |
| --- | --- |
| Retried first | chronological successor of `2/1965225`, fetched as `2/1965226` |
| Resume range | `2/1965226` at `2026-10-01T07:52:00.000Z` through `2/1965233` at `2026-10-01T07:59:00.000Z` |
| Resume examined | 8 |
| Resume `VALID` | 0 |
| Resume `INVALID` | 8 |
| Resume incomplete | 1, HTTP 404 on the successor of `2/1965233` |
| Resume continuity | `PASS` on all 8 edges |

Each new row is `PULSE_{pulseIndex}_OBJECTIVELY_INVALID`, modulus 256 bytes, signature 512 bytes, signature verification `FAIL`, output integrity `PASS`, on the same named certificate. The cumulative ledger is 49 rows, `2/1965185` through `2/1965233`, SHA-256 `64a6483dacbbb731554b27e155c73711e003345257f9354615bda98998662db3`. The first appended raw SHA-256 is `20e30f72face49eaeffc860715de47ddcb69f7be5ab465a2ecf93828b664a17c`. The cursor raw is `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1_CURSOR.json`, SHA-256 `04256546012ac5db352306c3f742784c6ff8687013b944d8518aa0bc298c0e26`.

```
SELECTED_CONFIRMATORY_BEACON = NONE
LAST_COMPLETELY_CLASSIFIED_CANDIDATE = 2/1965233
NEXT_REQUIRED_CANDIDATE = chronological successor of 2/1965233
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
NEXT_ACTION = BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE
```

The verifier blob remains `bed8a2aa33599b7ce4c0915eb410ad7413747b1d`. No seed was generated and the BitMEX target was not opened.

## Resume at the successor of 2/1965233

Same scan identity `D7_CONFIRMATORY_BEACON_SCAN_V1`, invocation 3. The first 49 ledger rows are unchanged. The retry fetched the chronological successor of `2/1965233` again. That pulse is `2/1965234` at `2026-10-01T08:00:00.000Z`.

| Fact | Value |
| --- | --- |
| Retried first | chronological successor of `2/1965233`, fetched as `2/1965234` |
| Resume range | `2/1965234` at `2026-10-01T08:00:00.000Z` through `2/1965250` at `2026-10-01T08:16:00.000Z` |
| Resume examined | 17 |
| Resume `VALID` | 0 |
| Resume `INVALID` | 17 |
| Resume incomplete | 1, HTTP 404 on the successor of `2/1965250` |
| Resume continuity | `PASS` on all 17 edges |

Each new row is `PULSE_{pulseIndex}_OBJECTIVELY_INVALID`, modulus 256 bytes, signature 512 bytes, signature verification `FAIL`, output integrity `PASS`, on the same named certificate. Chain index stayed 2. The cumulative ledger is 66 rows, `2/1965185` through `2/1965250`, SHA-256 `fc5e80600c243e634b02acd187627d8d83be417a10f6155db4ed65cc7c8d48d1`. The first appended raw SHA-256 is `9b78b80013b65228cdc47ca4184997bf224a33534c32f04bc285fc1d0c2122a6`. The cursor raw is `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1_CURSOR.json`, SHA-256 `ad52be1ffd51d6f50b85f9bcbea2815a5a76f318cd65d0d7d342c2bba2f6d8a6`.

```
SELECTED_CONFIRMATORY_BEACON = NONE
LAST_COMPLETELY_CLASSIFIED_CANDIDATE = 2/1965250
NEXT_REQUIRED_CANDIDATE = chronological successor of 2/1965250
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
NEXT_ACTION = BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE
```

The verifier blob remains `bed8a2aa33599b7ce4c0915eb410ad7413747b1d`. No seed was generated and the BitMEX target was not opened.
