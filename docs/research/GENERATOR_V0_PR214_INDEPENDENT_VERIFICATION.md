# Generator V0 PR #214 — independent verification

**Verdict:** `B. LIMITED OFFLINE REPAIR REQUIRED`

**Maximum allowed completion state:** `READY_FOR_PROVIDER_SMOKE_TEST` (not reached)

**Live campaign:** not authorized, not executed, not resumed.

**Repair candidate:** HEAD `ddda586dc7ea4a9589bc389eef7a6306d64f3d0c` TREE `1e749f1a7c8cf42926b0e3a84cca50c54d94b33b` PR https://github.com/sh1zok1d/signalbot/pull/214 base `71853f9b6c6b59c03d22e9a43cb52dd7e9699368`

This verifier did not implement the repair and did not reuse the implementer's gate corpus as the main adversarial set. Production code was not patched. No paid API call. Protected 2025/2026 market data were not opened. Scientific outcomes were not computed. first-shadow-v6/v7 were not resumed. The sealed v7 journal SHA256 remains `e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457`.

Machine-readable twin: `docs/research/GENERATOR_V0_PR214_INDEPENDENT_VERIFICATION.json`.
Audit tests: `tests/research/audit_pr214_independent/`.

---

## Why not A (`READY_FOR_PROVIDER_SMOKE_TEST`)

A 40-slot live shadow still has offline-discoverable holes that can stop or contaminate the next paid run:

1. Reservation-bound worst case for a **fresh** 40-slot campaign is **USD 22.144366**, above the owner ceiling **USD 17.100000**. A v7-derived continue (through generation:2) has remaining worst case **USD 17.526750** against remaining authority **USD 12.153250**. Both `FITS_AUTHORIZED_REMAINING = false`. `STOPPED_BUDGET` is fail-closed, but there is no legal extension above USD 17.10, so the intended 40-slot path cannot be shown offline to finish.
2. The novelty **prompt still describes relation lists**; the live provider schema requires **objects keyed by signature/candidate IDs**. That split is a billed failure or HTTP 400 risk on the first novelty call. Offline subset checking is not provider acceptance.
3. Phrase-list validators admit principle-level unsafe paraphrases (`post 2024`, `thru today`, fullwidth year digits, `signal to buy`, …). Listed phrases and ASCII `2025`/`2026` are caught.
4. Sealed-journal non-writability is **CLI-only**. `Ledger(copy)` can mutate a sealed-hash copy; after that write the hash changes and the CLI no longer treats it as sealed.

---

## Claim-by-claim

| Claim | Independent result | Severity | Confidence |
|---|---|---|---|
| F01 one bad card cannot kill the campaign | **Holds on the campaign path.** One `through today` card and one `PROTECTED_DATA_REQUIREMENT=true` card became `HARD_FAIL`; campaign reached `PENDING_HUMAN_REVIEW` with 38 valid. Critic `RoleContractError`/`BilledFailure` retry then `REVIEW_FAILED`. Residual: `Roles.request` still raises bare `ContractError` (not `RoleContractError`) if a non-VALID card is passed in; runner only sends VALID cards. `exact(judgments, PER_CANDIDATE_DIMENSIONS)` is outside `_review`'s try but the frozen dimension union matches, so it cannot fire on a successful critic triple. | residual low | high |
| F02 prompt / schema / validator one contract | **Partial.** Generator prompt says keyed candidates; provider schema is keyed. Novelty prompt still says `PRIOR_RELATIONS is a list of {SIGNATURE_ID, RELATION}`; live schema is a keyed object. Application schema still accepts arrays. `LEGAL_RANGE` pattern admits `2024-12..2020-01`; parser then quarantines (extra `HARD_FAIL`, not unsafe admission). | high (novelty split) | high |
| F03 never write 2025/2026 | **ASCII digits, FY/CY26, twenty twenty-five, numeric 2025 in SEARCH_SURFACE: quarantined.** Fullwidth `２０２５`/`２０２６`, spelled “two thousand twenty five”, and “twenty‑twenty‑five” with a non-breaking hyphen **admitted**. | medium | high |
| F04 open-ended / recency | **Listed phrases quarantined.** Principle paraphrases admitted: `post 2024`, `thru today`, `until now`, `after December 2024`, `present` in `HORIZON`, `currently` in `PRIMARY_TARGET`, etc. Recency list is token-exact. | medium | high |
| F05 hidden rules now stated | **Mostly holds** for listed missing-observables / grid product / trading phrases / nearest ID. Trading paraphrases (`signal to buy`, `PnL forecast`) admitted. | medium | high |
| F06 novelty coverage by decoding | **Conditional on the provider actually enforcing the keyed schema.** Application still re-checks coverage after payment. Prompt/schema split means a model that follows the prompt emits a shape the live schema forbids. | high until smoke | medium |
| F07 not-billed vs billed vs uncertain | **Holds for classified HTTP.** 429/503 → `FAILED_NOT_BILLED` charge 0, new transport key, COMPLETE never re-POSTed. Billed length → `FAILED_WITH_COST`, content retry under a new key. Timeout → `UNCERTAIN`, charged reserved, no auto replay. Retrieve non-200 is forced `UNCERTAIN` (including 404). | low residual | high |
| F08 crash / reconcile | **Auto-replay blocked.** Residual: critic crash after POST leaves `RESERVED` with **no response_id**. Reconcile `NOT_BILLED` then POSTs again (duplicate paid path). Implementer's own crash test trains that unsafe reconcile. Background generator persists `response_id` before poll, which is the safer path. | high (operator + critic) | high |
| F09 selector cannot destroy a complete campaign | **Holds.** Disagreement → `PENDING_HUMAN_REVIEW`, deterministic order authoritative. **Residual:** swallowed `CallUncertain` finishes the campaign with an `UNCERTAIN` selector row still charging the reserved bound; resume returns the saved result and never reconciles. | medium | high |
| F10 lineage-cumulative owner ceiling | **Holds for accounting.** Independent immutable sum of v7 calls = **4,946,750** micro-USD. Derive through generation:2 preserves that total across a nested derive. Discarded generation:3 remains in `PRIOR_ATTEMPTS` with intake verdicts. **Does not hold as “the next 40-slot live path fits.”** Fresh worst case 22,144,366 > 17,100,000; v7-derived remaining worst case 17,526,750 > 12,153,250. `remaining_campaign_budget_preflight` cannot run on a fresh journal (needs COMPLETE generator cards). Derive after critic work re-pays critics (carried as prior spend, then re-run) — by design, overcount. | high (fit) / low (sum) | high |
| F13 discarded attempts visible | **Holds** for derive `PRIOR_ATTEMPTS`. Residual: `attach_parsed` replaces `raw` with canonical JSON while `raw_sha256` stays the wire hash, so stored raw no longer hashes to the recorded SHA. | low | high |
| F12 sealed journal non-writable by path/copy/name | **False as stated.** CLI `refuse_sealed_or_archived` keys on content hash and refuses a byte-identical copy at a foreign path. `Ledger.__init__` does not consult the registry: a library write to a sealed-hash copy succeeds and changes the hash, after which CLI treats it as a new journal. | high (archive) | high |
| F11 / F17 | F11 feasibility range check is defined in the prompt. F17 not-billed charges 0 — independently reproduced. | — | high |

---

## New failure search (not in F01–F13)

| Finding | Location | What producer guarantees | What consumer assumes | Effect |
|---|---|---|---|---|
| N01 Mock vs live encoding | `mock.py` vs `output_schemas.py` | Mock returns `CANDIDATES` **array**; live schema is a **keyed object** | Implementer noisy E2E hand-encodes keyed objects; default mock E2E never exercises live encoding | Mock green ≠ provider-safe |
| N02 Selector schema does not pin IDs | `selector_schema` | Array of strings, no minItems, no uniqueness, no surviving-ID enum | Advisory path treats mismatch as DISAGREES | Not campaign-fatal |
| N03 State-machine tests set status without the causing row | `test_generator_v0_faults.py` | `PAUSED_UNCERTAIN_CALL` with no UNCERTAIN call | Resume is blocked | A labelled pause without a row **does run generation** (new keys). Implementer tests cannot reach the dangerous resume state. |
| N04 Budget property twin | `derive.charge` / `_charge` in implementer tests | Same CASE as `CHARGE_SQL` | Property test never runs `import_complete` or real `derive_complete_rounds` except the separate v7 test | Random sequences cannot reach derive/import holes |
| N05 Empty keyed batch object | `novelty_schema` `_batch_ids` | Strict empty object if batch-of-one | Campaign size 25–50 so unused | Low |
| N06 `remaining_campaign_budget_preflight` on CREATED | `derive.py` | Needs imported COMPLETE cards | Operator of a fresh run | Raises `no COMPLETE generator cards to bound remaining critics` |

---

## Independent corpus

207 cards, original wording (`Audit probe: lattice occupancy…`), labelled from the **rule text principle**, not by running the validator first.

- Listed open-ended / recency / trading / year / protected-flag / protected-source: **all quarantined**.
- Canonical in-catalog ranges: **all admitted**.
- Structural / range near-misses: **all quarantined**.
- Principle paraphrases: **47 admitted** (see `tests/research/audit_pr214_independent/PARAPHRASE_LEAKS.json`).

Confirmed admitted unsafe paraphrases include: `post 2024`, `thru today`, `until now`, `after December 2024`, `calendar year following 2024`, fullwidth `２０２５`, `signal to buy`, `PnL forecast`, `present` as a horizon recency paraphrase.

---

## Independent noisy E2E

Keyed live encoding (Responses background + Chat Completions critics) through a fake transport, **not** `MockResponder`. Faults: generator 429, dropped card, non-canonical range, novelty malformed, feasibility 429, red-team length stop, red-team crash-after-POST reconciled **BILLED** (to avoid the duplicate-POST path). Reached `PENDING_HUMAN_REVIEW` with ≥2 `HARD_FAIL` and no manual card-table patch.

---

## State machine

Resumable statuses without a campaign result still generate. Terminal statuses post nothing. `PAUSED_UNCERTAIN_CALL` **with** an UNCERTAIN row does not auto-replay; reconcile `NOT_BILLED` then continues. `PAUSED_UNCERTAIN_CALL` **without** a row is not a pause.

---

## Budget properties

Random reserve/finish/fail/reconcile sequences never exceeded cap; independent charge oracle matched journal spend. v7 cumulative independently 4,946,750 micro-USD before any new reservation. Nested derive does not refund.

---

## Implementer tests — circularity

The 52-ish gate tests are not an independent oracle:

- `test_every_rule_has_one_check_and_one_prompt_line` asserts that `RULES[].TEXT` appears in the prompt generated from `RULES`. That checks rendering, not that the rule is the right rule.
- `test_property_pattern_and_parser_agree` compiles `LEGAL_RANGE_PATTERN` and `parse_legal_range` from the **same module**.
- Gate corpus `EXPECT` labels were authored with the repair; they are not an external spec.
- `MockResponder` selector uses the **same ordinal sort** as `runner.py`.
- Noisy E2E uses `MockResponder` plus hand-encoded keyed objects and a `Crash(BaseException)` that the runner does not catch as `InfrastructureStop`.
- State-machine tests assign `status` without inserting the pause-causing call row.
- Budget property uses a Python twin of `CHARGE_SQL` and synthetic `PRIOR_SPEND` children, not full derive/import.
- `test_crash_after_post_leaves_reserved_charged_until_reconciled` reconciles `NOT_BILLED` after a POST that the fake transport already logged — the unsafe duplicate path.

This review did **not** merely re-run that suite.

---

## Strict schema vs documented subset (no live call)

Offline `assert_strict_subset` reports clean. Remaining **REQUIRES_REAL_PROVIDER_SMOKE_TEST** (not implementation correctness):

1. Unnamed **capturing groups** in `LEGAL_RANGE_PATTERN` (non-capturing groups were avoided on purpose).
2. **One-value enums** (`CANDIDATE_ID`, `MECHANISM_FAMILY`, `INFORMATION_SOURCE`, `PROTECTED_DATA_REQUIREMENT: [false]`).
3. **Dynamically keyed objects**: per-round `CANDIDATES` keyed by `C001`…; novelty `PRIOR_RELATIONS` keyed by signature IDs including `D4.ROLLING_CORRELATION_90D` and `B2-06` (names match `^[A-Za-z0-9_.-]{1,64}$`).
4. Per-request novelty schemas (property set depends on the batch).
5. `additionalProperties: false` and all properties required: used.
6. Mixed transports: GENERATOR `text.format` Responses vs critics `response_format` Chat Completions — both built from the same schema helper, neither accepted by a real endpoint in this review.

A failing smoke test here is `PAUSED_PROVIDER_REJECTED` on the first generation or novelty call, not a silent admission.

---

## Exact remaining blockers (offline, before any smoke test)

1. Align `NOVELTY_PROMPT` with the keyed provider schema (or drop keyed decoding and accept post-payment coverage checks — currently they disagree).
2. Owner decision on budget: reduce batch/caps, or raise the ceiling, or accept a designed `STOPPED_BUDGET` that cannot be extended. Publish a `FITS_AUTHORIZED_REMAINING=true` preflight for the **intended** next run shape. Fresh-journal preflight currently cannot run.
3. Close F12 in `Ledger` (or equivalent library gate), not only `__main__`.
4. Critic crash-after-POST: persist enough identity to retrieve, or forbid `NOT_BILLED` reconcile of `RESERVED` without a provider-side negative. Do not document that path as the happy resume.
5. Phrase-list / unicode: at least ASCII-fold and NFKC year digits; `post 2024` vs `post-2024`. Phrase lists will never be complete; do not claim they are.

After those, the maximum honest next state is `READY_FOR_PROVIDER_SMOKE_TEST` (schema + one cheap not-campaign call), **not** another full paid shadow.

---

## What does not need redesign

Per-card `HARD_FAIL` / `REVIEW_FAILED`, `STOPPED_INSUFFICIENT_VALID`, billed vs not-billed vs uncertain taxonomy, COMPLETE never re-POSTed, lineage sum on derive, discarded generation:3 visibility, advisory selector, and grandfather isolation of gen0/1/2 vs v7 gen3 are real repairs. This is not `D. ARCHITECTURAL REDESIGN STILL REQUIRED`.

---

## Validation actually run

```
python3 -m pytest -q tests/research/audit_pr214_independent/test_independent_audit.py
# 35 passed
```

No full-repo pytest (environment missing unrelated deps). `git diff --check` on audit files: clean. No network. v7 SHA unchanged.
