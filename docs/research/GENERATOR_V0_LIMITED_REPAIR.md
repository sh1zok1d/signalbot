# Generator V0 — limited offline repair after independent verification (PR #215)

**Completion state:** `READY_FOR_RE-VERIFICATION` (not `READY_FOR_PROVIDER_SMOKE_TEST`, not `READY_FOR_LIVE_SHADOW`)
**Base:** `ddda586dc7ea4a9589bc389eef7a6306d64f3d0c` (PR #214)
**Verification input:** PR #215, verdict `B. LIMITED OFFLINE REPAIR REQUIRED`
**Machine-readable twin:** `docs/research/GENERATOR_V0_LIMITED_REPAIR.json`
**Evidence:** `docs/research/generator_v0_repair/OFFLINE_GATE_REPORT.json`, `docs/research/generator_v0_repair/BUDGET_SCENARIOS.json`

No live shadow, no paid call, no protected 2025/2026 data, no scientific
outcome. Sealed `first-shadow-v6` and `first-shadow-v7` were not modified or
resumed (v7 SHA256 `e27eb1ce…f36457` unchanged; tests use tmp copies or
synthetic sealed journals). The verifier's strings were used as external
regression evidence only; none was copied into rule lists or tests.

## Blockers

### B1 — novelty prompt/schema mismatch: FIXED

- Before: `NOVELTY_PROMPT` asked for lists of `{SIGNATURE_ID, RELATION}`; the strict
  schema required objects keyed by exact IDs; the provider adapter and the
  background poller normalized keyed output into lists before any parser saw it.
- After: one keyed contract end to end.
  - Prompt: `PRIOR_RELATIONS` / `BATCH_RELATIONS` are objects keyed by exactly the leaf signature IDs (PARTIAL_OR_MIXED rows replaced by their `SUB_SIGNATURES`) and the other batch candidate IDs.
  - Strict per-request schema: those exact keys, all required, `additionalProperties: false`.
  - `Roles.ask` validates the exact per-request provider schema **before** normalizing; list forms raise `RoleContractError`.
  - `parse_json` rejects duplicate keys, so duplicate IDs cannot be decoded.
  - The provider layer keeps the model text verbatim (`raw`, `raw_sha256` = hash of that text, `wire_sha256` = envelope hash); `attach_parsed` is removed.
  - V02 generator rounds are consumed keyed; each card is checked against its slot's strict provider schema (`PROVIDER_SCHEMA`) before the V02 rules. Legacy v0.1 imports keep their stored list form.
  - `MockResponder` and the noisy harness emit the live keyed encodings.
- Final request/response structure (novelty): request context = `BLIND_MECHANISM_MAP_V0`, `GOVERNANCE_REGION_AUTHORITY_V0`, `GENERIC_ANTI_RESCUE_RULES`, `CURRENT_BATCH_SIGNATURES`, `CANDIDATE`; response = `{"PRIOR_RELATIONS": {<31 signature IDs>: RELATION}, "BATCH_RELATIONS": {<39 other candidate IDs>: RELATION without RESOLVES_BLOCKER}, "JUDGMENTS": {NOVELTY, MECHANISM_DISTANCE, NON_RESCUE: 0..3}}`.
- Files: `roles.py` (`NOVELTY_PROMPT`, `Roles.ask`), `schema.py` (`normalize_role_output`, `encode/decode_provider_card`, `parse_json`), `runner.py` (`parse_round`, `slot_violations_v02`, `_intake_round`), `derive.py`, `provider.py`, `openai_provider.py`, `ledger.py`, `mock.py`, `generator_v0_gate/noisy.py`.
- Tests: `tests/research/test_generator_v0_novelty_contract.py` (9).

### B2 — sealed journal enforced below the CLI: FIXED

- Before: only `__main__.refuse_sealed_or_archived`; `Ledger(path)` opened any file for writing.
- After: `Ledger.__init__` calls `sealed_reason(path)` **before** connecting (registry content hash, or meta `SEALED` read through an immutable connection) and refuses with `SealedJournal`. `Ledger.open_readonly` returns an immutable handle whose every mutator (`set`, `event`, `transaction`, `reserve`, `mark_dispatched`, `submit_background`, `finish`, `failed`, `reconcile`, `record_candidate`, `set_candidate_review`, `save_card`, `import_complete`, `mutate`) refuses. `Ledger.seal(actor, reason)` writes the meta marker and checkpoints. The CLI uses the same library check.
- Tests: `tests/research/test_generator_v0_sealed_library.py` (20). They cover synthetic meta-sealed journals at the same path, under a renamed file and in another directory; a registry-hash-only synthetic journal (temporary registry); a tmp copy of v7 under an unrelated name; every mutator through a read handle; and side-effect-free reads (hash unchanged, no `-wal`/`-shm`).

### B3 — crash-after-POST reconciliation: FIXED

- Before: a RESERVED row existed both before and after the POST, and `reconcile(..., NOT_BILLED)` accepted operator assertion alone, enabling a duplicate POST.
- After (dispatch protocol, meta `DISPATCH_PROTOCOL = 2`):
  - Every attempt is committed `DISPATCHED` before the transport is called.
  - `RESERVED` means never sent: it is re-dispatched under the same key, and it cannot be reconciled.
  - A possibly-POSTed row (`DISPATCHED`, `UNCERTAIN`, or `RESERVED` in a journal without the protocol) pauses `PAUSED_UNCERTAIN_CALL` and is never re-sent automatically. Reconciliation:
    - `BILLED` requires cost within the bound **and** evidence;
    - `NOT_BILLED` requires a provider-side evidence object naming the `response_id` recorded on that row, with `PROVIDER_STATUS` failed/cancelled and `BILLED_OUTPUT_TOKENS` 0 (operator assertion or free text is refused);
    - `UNKNOWN` needs no evidence, charges the reserved bound and closes the logical call (role and slot) in `closed_calls`. Every later content or transport attempt then raises `CallClosed` without a POST: critic → `REVIEW_FAILED`, generator round → slot `HARD_FAIL`, selector → `UNAVAILABLE`.
  - The CLI `reconcile` offers `BILLED | NOT_BILLED | UNKNOWN` with the same rules.
- Tests: `tests/research/test_generator_v0_crash_points.py` (11), crash points:
  - before POST → `RESERVED`, one POST total after resume;
  - immediately after dispatch → `DISPATCHED`, pause; NOT_BILLED refused with no, free-text or mismatched evidence;
  - after provider acknowledgement → same; BILLED with evidence allows one audited new content attempt; UNKNOWN closes the call;
  - before journal completion → `DISPATCHED`, pause, no new POST;
  - after journal completion → replay from the journal, no POST.
- The noisy E2E now shows `NOT_BILLED_WITHOUT_EVIDENCE_REFUSED` before `RECONCILED_BILLED`.

### B4 — temporal/protected normalization: FIXED (not semantically complete)

- New `textnorm.py`:
  - NFKC, dash/quote/comparison folding, zero-width and control removal, any Unicode decimal digit → ASCII, casefold, digit look-alike letters inside digit runs, letter/digit split;
  - then structural scanners (not phrase lists):
    - year references: digits, spaced digits, spelled numbers, digit words, Roman numerals, FY/CY/Q/H/year/apostrophe two-digit forms;
    - relation words before or after **any** year;
    - a boundary year used as a start;
    - extension words followed by open or unanchored endpoints;
    - open/unbounded/now-anchored windows and growing samples;
    - wall-clock recency in scope fields;
    - trade actions near instruction words or leads, position verbs + long/short, claim nouns near claim modifiers, success + probability words.
- `NO_PROTECTED_YEARS` now forbids any year after 2024 in text (4-digit 2025–2099); numeric JSON values 2025/2026 stay forbidden. Rule texts in the prompt list every structural word group (a test enforces it).
- Protected-source matching is normalized and also rejects a DATASET/OBSERVABLE containing the word "protected".
- Tests: `tests/research/test_generator_v0_textnorm.py` (96), freshly written, including compliant controls.
- External regression (PR #215 corpus, run from a scratch checkout, not copied): at `ddda586`, 47 of its quarantine-intent cards were admitted. Now 1 of 181 is admitted (`IV121`: bare "twenty-four / twenty-five" without a century is not treated as a year), and 0 of 26 admit-intent cards are rejected.
- Known limit: English-only lexical structure; paraphrases outside these structures can pass and are left to the critics.

### B5 — budget / run-shape decision support: FIXED (decision not taken)

- `campaign_bound` / `fresh_campaign_budget_preflight` / `remaining_campaign_budget_preflight` work on fresh, running and derived (including nested) journals.
- Ungenerated cards are proxies with size max(largest known card, 6008 B × 1.5) and a novelty signature of max(largest known, 1043 B × 1.5). 6008 B and 1043 B are the observed v7 maxima, recomputed by a test.
- Live `run`/`resume` refuse unless the worst case fits the authorized remainder, or the operator passes `--accept-budget-stop --actor --reason`. The acceptance is recorded as `LIVE_BUDGET_GATE`. This answers the verifier's FITS-false-resume finding.
- v7 lineage spend proof: imported generation:0–2 = 3,779,550; prior (generation:3) = 1,167,200; total = **4,946,750** micro-USD; remaining under 17,100,000 = 12,153,250. The v7 journal hash is identical before and after derive.
- Reconciliation with the previously reported values:
  - v7-derived worst case: 17,526,750 (old) → 18,265,201. The generator and novelty prompts are longer, and the 10 missing cards now use the documented 1.5 margin; margin 1.0 gives 17,724,436.
  - Fresh single attempt: 27,048,513 (the verifier's 22,144,366 used a different proxy).

| Scenario | Change kind | Size | Novelty cap | Content attempts | Worst case, single attempt (USD) | Worst case with content retries (USD) | E: min ceiling, journal only (USD) | E: min ceiling, campaign cumulative (USD) | Fits USD 17.10 |
|---|---|---|---|---|---|---|---|---|---|
| A_CURRENT_FRESH | NONE | 40 | 12000 | 2 | 27.048513 | 54.095088 | 54.095088 | 54.095088 | no |
| A_CURRENT_FRESH_COUNTED_IN_V7_CAMPAIGN | NONE | 40 | 12000 | 2 | 27.048513 | 54.095088 | 54.095088 | 59.041838 | no |
| A_CURRENT_V7_DERIVED | NONE | 40 | 12000 | 2 | 18.265201 | 36.528447 | 36.528447 | 41.475197 | no |
| B_NO_CONTENT_RETRIES_FRESH | OPERATIONAL | 40 | 12000 | 1 | 27.048513 | 27.048513 | 27.048513 | 27.048513 | no |
| B_NO_CONTENT_RETRIES_V7_DERIVED | OPERATIONAL | 40 | 12000 | 1 | 18.265201 | 18.265201 | 18.265201 | 23.211951 | no |
| C_NOVELTY_CAP_5000_FRESH | OPERATIONAL | 40 | 5000 | 2 | 24.248433 | 48.494928 | 48.494928 | 48.494928 | no |
| C_NOVELTY_CAP_5000_V7_DERIVED | OPERATIONAL | 40 | 5000 | 2 | 15.465121 | 30.928287 | 30.928287 | 35.875037 | no |
| C_NOVELTY_CAP_5000_NO_RETRIES_FRESH | OPERATIONAL | 40 | 5000 | 1 | 24.248433 | 24.248433 | 24.248433 | 24.248433 | no |
| C_NOVELTY_CAP_5000_NO_RETRIES_V7_DERIVED | OPERATIONAL | 40 | 5000 | 1 | 15.465121 | 15.465121 | 15.465121 | 20.411871 | no |
| C_NOVELTY_CAP_7000_FRESH | OPERATIONAL | 40 | 7000 | 2 | 25.048433 | 50.094928 | 50.094928 | 50.094928 | no |
| C_NOVELTY_CAP_7000_V7_DERIVED | OPERATIONAL | 40 | 7000 | 2 | 16.265121 | 32.528287 | 32.528287 | 37.475037 | no |
| C_NOVELTY_CAP_7000_NO_RETRIES_FRESH | OPERATIONAL | 40 | 7000 | 1 | 25.048433 | 25.048433 | 25.048433 | 25.048433 | no |
| C_NOVELTY_CAP_7000_NO_RETRIES_V7_DERIVED | OPERATIONAL | 40 | 7000 | 1 | 16.265121 | 16.265121 | 16.265121 | 21.211871 | no |
| C_NOVELTY_CAP_9000_FRESH | OPERATIONAL | 40 | 9000 | 2 | 25.848433 | 51.694928 | 51.694928 | 51.694928 | no |
| C_NOVELTY_CAP_9000_V7_DERIVED | OPERATIONAL | 40 | 9000 | 2 | 17.065121 | 34.128287 | 34.128287 | 39.075037 | no |
| C_NOVELTY_CAP_9000_NO_RETRIES_FRESH | OPERATIONAL | 40 | 9000 | 1 | 25.848433 | 25.848433 | 25.848433 | 25.848433 | no |
| C_NOVELTY_CAP_9000_NO_RETRIES_V7_DERIVED | OPERATIONAL | 40 | 9000 | 1 | 17.065121 | 17.065121 | 17.065121 | 22.011871 | no |
| D_BATCH_25_FRESH | DESIGN_CHANGE | 25 | 12000 | 2 | 16.553875 | 33.106096 | 33.106096 | 33.106096 | no |
| D_BATCH_25_FRESH_NO_RETRIES | DESIGN_CHANGE | 25 | 12000 | 1 | 16.553875 | 16.553875 | 16.553875 | 16.553875 | yes |
| D_BATCH_30_FRESH | DESIGN_CHANGE | 30 | 12000 | 2 | 19.256897 | 38.512047 | 38.512047 | 38.512047 | no |
| D_BATCH_30_FRESH_NO_RETRIES | DESIGN_CHANGE | 30 | 12000 | 1 | 19.256897 | 19.256897 | 19.256897 | 19.256897 | no |

Notes:
- Fresh rows compare against the full USD 17.10. `A_CURRENT_FRESH_COUNTED_IN_V7_CAMPAIGN` shows the other reading (a fresh run counted inside the v7 campaign authority).
- Scenario C caps are the visible novelty bound (2,562 B with whitespace: 31 + 39 keys) plus a 2,000/4,000/6,000-token reasoning allowance, rounded up to 500. No paid critic call has ever completed, so critic reasoning usage is unobserved. A length stop is a billed failure and can end `REVIEW_FAILED`.
- Scenario D changes the frozen batch size and needs an outcome-blind design amendment. It is not applicable to the v7-derived run: the imported slots follow the 40-slot plan and would leave no NEW_FAMILY_PROPOSAL slots.
- Worst cases bound every call at maximum output; realized v7 generator spend was about 65 percent of its bound.

## Residual items

| Item | State | Change |
|---|---|---|
| Selector `CallUncertain` hid reserved spend | FIXED | `SELECTOR_ADVISORY` names `CALL_KEY`, `CALL_STATE`, `CHARGED_MICRO_USD`; `SPEND.UNRESOLVED_CALLS` lists every open row |
| `attach_parsed` raw/raw_sha256 confusion | FIXED | removed; `raw` is verbatim, `raw_sha256` hashes it, `wire_sha256` hashes the envelope |
| Status-only pause states | FIXED | resume requires the latest `CAMPAIGN_*` event to be `CAMPAIGN_<status>` |
| start>end LEGAL_RANGE | DOCUMENTED + TESTED | the strict-schema regex cannot express ordering (no lookaround/backreferences); per-slot intake rejects it (`LEGAL_RANGE_GRAMMAR`) before any critic call |

## Noisy offline E2E

40 slots → `PENDING_HUMAN_REVIEW`:
- 37 VALID and 3 HARD_FAIL (`SLOT_IDENTITY`, `PROVIDER_SCHEMA`, `NO_PROTECTED_YEARS`); 2 REVIEW_FAILED and 35 REVIEWED.
- 125 POSTs = 125 journal rows (no duplicate POST); spend 4,218,734 micro-USD; no unresolved calls.
- Steps: crash after POST → pause → NOT_BILLED without evidence refused → BILLED with evidence → completion.

## Remaining blockers / open items for the re-verifier

- Provider acceptance of the keyed strict schemas is proven only offline against the documented subset.
- Worst-case budget does not fit USD 17.10 in any current-design scenario (owner decision; nothing chosen here).
- Structural text checks are not semantically complete (see B4).
- The dispatch protocol protects journals created by this code; journals without it treat RESERVED as possibly POSTed.
- Stricter wording rules may raise the live quarantine rate; unmeasured until a live run.
