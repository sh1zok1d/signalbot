# Generator V0 — Anthropic compact GENERATOR projection (offline repair)

**Completion state:** `OFFLINE_GATES_PASS / LIVE_RE_SMOKE_BLOCKED_MISSING_ANTHROPIC_API_KEY`
**Base:** `cde2035708c053f6f4b66442a0689542735a05fa` (PR #214)
**Machine-readable twin:** `docs/research/GENERATOR_V0_ANTHROPIC_COMPACT_PROJECTION.json`

## Why

The first Anthropic schema-acceptance smoke was rejected before generation:

- response: HTTP 400 `invalid_request_error`, "The compiled grammar is too large, which would cause performance issues. Simplify your tool schemas or reduce the number of strict tools.";
- no message, no tokens, cost USD 0;
- call key `767fd9e133e63a6e212277326252679724c3863d9d649e909c0eb1dc2bdf95a0`, request body 55,982 bytes.

The keyed exact schema repeats the full slot-pinned card schema once per slot.

## Change (wire format only)

The Anthropic GENERATOR request now sends `{"CANDIDATES": [card, ...]}` with **one** shared card schema.

- wire format `ANTHROPIC_COMPACT_CANDIDATE_ARRAY_V1`;
- route `STRUCTURED_OUTPUT = ANTHROPIC_OUTPUT_CONFIG_JSON_SCHEMA_COMPACT_CANDIDATE_ARRAY_V1`.

In the shared card schema:
- `CANDIDATE_ID` is an enum of the round's slot IDs;
- `MECHANISM_FAMILY` is the full family enum;
- `INFORMATION_SOURCE` is the full source-class enum;
- `PROTECTED_DATA_REQUIREMENT` is `[false]`;
- `LEGAL_RANGE` pattern appears once;
- every field is required and `additionalProperties=false`.

The exact keyed provider schema is unchanged and remains what intake enforces. OpenAI routes are unchanged.

Unchanged (no scientific change):
- 40 candidates, round size 10, slot plan;
- V02 contract, family/source assignments;
- protected-data and LEGAL_RANGE rules;
- novelty/feasibility/red-team semantics;
- `MIN_VALID_CANDIDATES`, deterministic selector, human-review boundary;
- owner ceiling and output caps.

## Grammar report (generation:0, 10 slots)

| Metric | Before (keyed) | After (compact) |
|---|---|---|
| Schema bytes | 31,936 | 3,525 |
| Request body bytes | 55,982 | 27,571 |
| Objects | 42 | 5 |
| Enums | 70 | 7 |
| Single-value enums | 40 | 1 (`PROTECTED_DATA_REQUIREMENT=[false]`) |
| Enum values | 490 | 75 |
| LEGAL_RANGE pattern occurrences | 10 | 1 |
| Reservation bound (USD) | 0.895672 | 0.782028 |

Size alone does not prove provider acceptance; only a live POST can.

## Relaxed constraints and where they are enforced

The keyed exact schema is relaxed only at the provider level. Intake (`runner._intake_round`) enforces everything before a card is VALID or reaches any critic:
1. It binds each returned item to a slot **only by its own `CANDIDATE_ID`**.
2. It validates the item against **that slot's exact provider schema** (`slot_violations_v02`).
3. It then applies the V02 rules.

| Relaxed constraint | Compact provider schema | Intake enforcement | Test |
|---|---|---|---|
| CANDIDATES keyed by exactly the slot IDs | array, minItems 1 | Missing slot → HARD_FAIL. Duplicate ID → HARD_FAIL, and it cannot fill another slot. Unknown or other-round ID → rejected (`EXTRA_GENERATED_CARDS_IGNORED`). Non-object or non-string ID → rejected (`MALFORMED_GENERATED_ITEMS_IGNORED`). | `test_adversarial_compact_rounds[nine_cards, eleven_cards, duplicate_*, unknown_id, malformed_*]` |
| CANDIDATE_ID one-value enum per slot | enum of round slot IDs | Exact slot schema; a card relabelled to another slot fails that slot's family/source enum | `card_assigned_to_another_slot`, e2e C031→C032 |
| MECHANISM_FAMILY one-value enum per slot | full family enum | Exact slot schema `string enum` | `wrong_family`, relaxed-constraint test |
| INFORMATION_SOURCE one-value enum per slot | full source enum | Exact slot schema `string enum` | `wrong_source`, relaxed-constraint test |
| SEARCH_SURFACE.MAX_VARIANTS 1..100 | integer (Anthropic has no min/max) | Exact slot schema `integer range` | relaxed-constraint test |
| DATA_REQUIRED maxItems 20 | array, minItems 1 (no maxItems) | Exact slot schema `array too long` | relaxed-constraint test |

A mutation check was run: replacing the exact slot-schema step with V02 rules only made 16 compact tests fail. The tests therefore depend on the exact-schema step.

## Identity

- Each Anthropic GENERATOR request carries `provider_wire_format` and `provider_schema_digest`, the digest of the exact schema sent. Both fields enter the call key.
- The adapter refuses a GENERATOR request whose format or digest does not match the schema it would send.
- New generation:0 key: `f8207e1f0fa229f24eec50b0c894d704dd32ad1fece59672e2d2440b47ea930e`. It differs from the failed key, and no round key equals the failed key (tested).
- Routing digest `ef21451e433da324430c15cbfda41e514ab114d8f9fd2fa0921d9cc266d32716`; router identity `e27ce3371280340aa45c7367027393c1da57e0e73514df1e0061beaa39ae9fc5`.
- Fresh 40-card routed worst case: USD 21.365889 single attempt (was 21.821289).

## Live re-smoke

- Budget precheck: ABSOLUTE_SMOKE_BUDGET_CAP_USD 3.00, prior spend 0. Reservations: Opus GENERATOR round 0.782028, Luna FEASIBILITY 0.003950, Sol NOVELTY 0.201984. Total 0.987962, which **fits**.
- Not performed: `ANTHROPIC_API_KEY` is not present in the agent environment. No Anthropic or OpenAI POST was made.
- Next step: provide the key via Cursor Dashboard → Cloud Agents → Secrets and run the one authorized Anthropic re-smoke.
