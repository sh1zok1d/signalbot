# Generator V0 shadow campaign

Status: mixed transport. GENERATOR uses background Responses
(`POST /v1/responses`, `background=true`, `store=true`). Critics and the
selector remain Chat Completions with a 600-second HTTPS timeout. Frozen
scientific design is unchanged. A successful campaign still terminates at
`PENDING_HUMAN_REVIEW`. The archived partial paid runs
`artifacts/generator_v0/first-shadow`, `artifacts/generator_v0/first-shadow-v2`,
`artifacts/generator_v0/first-shadow-v3`,
`artifacts/generator_v0/first-shadow-v4`,
`artifacts/generator_v0/first-shadow-v5`, and
`artifacts/generator_v0/first-shadow-v6` are sealed and the operator
refuses to open them for run/resume/review. Offline `derive` may read
`first-shadow-v6` as an immutable source. One campaign generates
research cards, applies separate critics and produces a human-review queue.
It has no market-data reader, acquisition tool, evaluator or trading hook.
A successful run terminates at `PENDING_HUMAN_REVIEW`.

## Setup and canonical commands

Use a clean checkout with Python 3.11+. The runtime uses only the standard
library. For development tests install `pytest==8.3.5`; the rest of the
repository keeps its own `requirements-dev.txt`.

Set `OPENAI_API_KEY` in your environment or secret manager. Role-specific
models are pinned in `scripts/research/generator_v0/models.py`; do not set
`GENERATOR_V0_MODEL` or pass `--model`. The configuration template is
`docs/research/GENERATOR_V0.env.example`. Never commit the filled template.
A ChatGPT subscription is not an API credential.

Zero-cost checks:

```bash
python -m scripts.research.generator_v0 preflight
python -m scripts.research.generator_v0 run --provider mock --run-dir artifacts/generator_v0/mock-first
```

Real preflight (offline: validates credential presence, configuration and
context, does not contact the provider or check account entitlement):

```bash
python -m scripts.research.generator_v0 preflight --provider openai --allow-real-llm --budget-usd 30
```

**Canonical real shadow command**, after explicitly authorizing its
budget and supplying the credential. Use a **new** run directory. Do not
resume or overwrite `artifacts/generator_v0/first-shadow`,
`artifacts/generator_v0/first-shadow-v2`,
`artifacts/generator_v0/first-shadow-v3`,
`artifacts/generator_v0/first-shadow-v4`,
`artifacts/generator_v0/first-shadow-v5`, or
`artifacts/generator_v0/first-shadow-v6`.

Offline COMPLETE carry-forward (no provider POST). Source remains
byte-for-byte unchanged. Destination is a new run. Imported actual cost
counts once against the source campaign cap. Revalidation uses the
current application validator. `--through-generation 2` imports
generation:0/1/2 and then stops; it does not start generation:3.

```bash
python -m scripts.research.generator_v0 derive --source-run-dir artifacts/generator_v0/first-shadow-v6 --run-dir artifacts/generator_v0/first-shadow-v7 --through-generation 2
```

Derive revalidates imported COMPLETE rounds and stops at
`DERIVED_IMPORTED_REVALIDATED`. It does not write the `cards` table and
does not start remaining generator rounds. An explicit later
authorization is required before remaining rounds may run:

```bash
python -m scripts.research.generator_v0 authorize-derived-continuation --run-dir artifacts/generator_v0/first-shadow-v7 --actor owner --reason "revalidation passed; continue remaining generator rounds"
```

That command makes no provider call. Direct run/resume from
`DERIVED_IMPORTED_REVALIDATED` is refused. After
`DERIVED_CONTINUATION_AUTHORIZED`, resume may reuse imported COMPLETE
rounds and continue. Do not create a live first-shadow-v7 in this
LEGAL_RANGE / budget-extension unit; prove derive on a TEMP scratch
destination and derive v7 after merge.

Offline campaign-cap extension (no provider POST). Existing run required.
Actor, reason, and explicit new cap required. The new cap must exceed the
old cap, cannot decrease, cannot exceed the owner-authorized absolute
total of USD 10.000000, and cannot exceed the technical maximum of
USD 30. The command rewrites only `CAP_MICRO_USD` and records an
immutable `BUDGET_EXTENSION_AUTHORIZED` event (`OLD_CAP_MICRO_USD`,
`NEW_CAP_MICRO_USD`, `ACTOR`, `REASON`, `TIME`). Call identities,
responses, costs, and scientific state are unchanged. USD 10 is the
authorized campaign total, not an incremental +USD 10. Example after a
post-merge v7 derive (old USD 7.117536, new USD 10.000000):

```bash
python -m scripts.research.generator_v0 authorize-budget-extension --run-dir artifacts/generator_v0/first-shadow-v7 --actor owner --reason "set absolute authorized campaign total to USD 10" --new-cap-usd 10.000000
```

Do not run that command against sealed `first-shadow-v6`. A cap of
USD 17.117536 is not authorized.

Offline remaining-campaign budget preflight (no provider POST). Uses the
same `bound()` reservation path as live `ledger.reserve`. Ungenerated
cards are proxied by cloning the largest imported card. If
`FITS_AUTHORIZED_REMAINING` is false, do not make a real LLM call.

```bash
python -m scripts.research.generator_v0 remaining-budget-preflight --run-dir artifacts/generator_v0/first-shadow-v7
```

```bash
python -m scripts.research.generator_v0 run --provider openai --allow-real-llm --budget-usd 10 --run-dir artifacts/generator_v0/shadow
```

Budget may be lower. Live OpenAI run/resume cannot exceed the
owner-authorized absolute total of USD 10.000000. Technical mock and
offline preflight still accept the infrastructure maximum of USD 30.
Mock remains the default even
if API credentials exist. Every real call requires provider selection, key,
explicit authorization and a nonzero budget. No paid request was made during
this structured-output / routing change. Real generation quality and account
access are unmeasured.

Resume with the same options, budget and run directory:

```bash
python -m scripts.research.generator_v0 resume --provider openai --allow-real-llm --budget-usd 10 --run-dir artifacts/generator_v0/shadow
```

A completed provider response is persisted before parsing and reused. A
pending/uncertain billed attempt is never automatically replayed; preserve the
run and reconcile with provider billing before making any later decision.
GENERATOR create (`POST /v1/responses`) is exactly-once. If it fails before a
`response_id` is known, the call is `UNCERTAIN` and is never auto-replayed.
Once a `response_id` is committed (`BACKGROUND_SUBMITTED`), resume only
`GET`s that id. Polling timeouts and network errors do not create a new paid
request. If the operator wait expires while the provider is still
`queued`/`in_progress`, the call stays `BACKGROUND_SUBMITTED` (resumable),
not `UNCERTAIN`. Polling GETs do not reserve additional budget.
No automatic POST retries exist. A malformed persisted answer remains visible as a
failed run; resume does not repeatedly pay for the same malformed answer.
Configuration, implementation or context drift refuses resume.

## Artifacts and human decisions

The run directory contains:

- `run.sqlite`: authoritative transaction journal, raw model responses, hashes,
  reservations, actual usage estimates, candidate registry and human events;
- `run_ledger.json`: call metadata, parsed cards, critics and final decision;
- `shadow_registry.json`: all cards, critics, ten separate ordinal dimensions,
  Stream A/B, shortlist and normalized semantic digest;
- `data_gap_ledger.json`: demand grouped by missing-data class;
- `human_review_queue.json`: shortlist for review.

JSON files are derived views; manually editing them never changes authority.
Use `inspect` to read authoritative cards and human events. For example:

```bash
python -m scripts.research.generator_v0 inspect --run-dir artifacts/generator_v0/shadow
python -m scripts.research.generator_v0 review --run-dir artifacts/generator_v0/shadow --candidate-id C006 --decision DEFER --reason "Need to verify the observable definition" --actor owner --active-minutes 4
python -m scripts.research.generator_v0 mutate --run-dir artifacts/generator_v0/shadow --candidate-id C006 --field NAME --value-json '"Clarified mechanism name"' --reason "Clarify wording" --actor owner
```

Mutation records field/before/after/reason/actor/time atomically, invalidates
old decisions, and enters `MUTATED_REQUIRES_REVIEW`. It does not silently reuse
old critics. Acceptance is only `ACCEPT_FOR_FUTURE_DESIGN`; it never creates
an execution permit, scientific card D14, Sprint05, or MARKET-07.
Human review time is recorded, never inferred from runtime. There is no timed
historical baseline, so no achieved 70–80% reduction claim is made.

## Selection and limits

Generation uses four rounds of ten for the default 40. At most five per
existing family, at least eight new-family attempts, at least six source
classes. New-data ideas survive in Stream B. The mock's explicitly synthetic
cards and deterministic scores exercise infrastructure and measure no LLM
capability. It produces 20 A / 15 B / 5 non-stream cases with the current
fixtures; these are not scientific outcomes.

Three critics produce separate typed judgments. Frozen novelty relations are
mapped by deterministic governance. D4 is evaluated by sub-signature. Selector
inputs contain no prior IDs, narrative rationales, history or authority rows.
Sort descending by mechanism distance, information gain, feasibility,
cheapness; tie-break ascending candidate ID. There is no combined score.
The selector's proposed ordering must equal this order; shortlist maximum five.

A deterministic exact-signature check complements model semantic novelty
review. Semantic novelty, causality and feasibility remain fallible model
judgments and need human adjudication. Passing mock tests is not proof that a
real model can detect every paraphrased rescue or hidden lookahead. Off-catalog
sources cannot be DATA_READY. Disagreement over data status is surfaced for
human review, not silently applied as a card edit.

Context source hashes are pinned. Runtime cannot regenerate the map. A reviewed
future source update needs explicit rematerialization and review; blind-map
regeneration is not an operator workaround. The frozen design received only
the authorized single-field provenance amendment.

JSON mode is not used. Structured Outputs (`json_schema`, `strict: true`)
are generated from the application role builders. Application validators
remain the second layer. Role-specific models and prices are in
`GENERATOR_V0_MODEL_ROUTING.md` / `models.py`. GENERATOR transport identity
includes `GENERATOR_ENDPOINT=RESPONSES`, `GENERATOR_BACKGROUND=true`,
`BACKGROUND_STORE_POLICY=STORE_TRUE_REQUIRED_FOR_RESUME` (official background
retention after the short polling window requires `store=true`; local
COMPLETE persist is followed by best-effort `DELETE`),
`GENERATOR_MAX_OUTPUT_TOKENS=32768`, and the polling
policy (interval 3s, GET timeout 45s, operator wait 3600s, create timeout
60s). Critic Chat Completions HTTPS timeout remains
`OPENAI_REQUEST_TIMEOUT_SECONDS = 600` and is part of run configuration
identity. A GENERATOR `TimeoutError` before `response_id` is `UNCERTAIN`
and is never automatically replayed. A terminal background Response with
trustworthy usage persists actual cost under `FAILED` and is never parsed
or retried.

Protected-data validation is a requirement check on `DATA_REQUIRED` and
`PROTECTED_DATA_REQUIREMENT`, not a whole-card search for the strings
`2025`/`2026`. The only recognized `NO_LOOKAHEAD_RULE` exclusion is
unambiguous "No 2025[/2026] <non-numeric subject> are/is permitted|allowed":
the body cannot contain a digit, another year, or `. ; : ! ?`, and
"not"/"forbidden" are not accepted. C018's "No 2025/2026 quotes ... are
permitted." still passes. Open-ended and post-2024 observation-window
aliases are applied recursively to all candidate content outside that
exclusion. Bare "latest" or "current" is not enough: point-in-time
wording such as "latest closed bar at or before T" or "current funding
rate as-of T" is allowed. Explicit forms such as "latest available",
"current bars", "through today", and "post-2024" fail. Ambiguous or
open-ended ranges on unknown sources fail closed. The exact annotated
form `Required historical window: <STRICT_RANGE>; <SAFE_COVERAGE_NOTE>`
classifies as `<STRICT_RANGE>` only; the coverage note does not extend
the window. Inspected generation:2 wrappers with exactly one strict range
and a bounded provenance/coverage suffix classify as that inner range
only: `Proposed <head> limited to|effective within|strictly <STRICT_RANGE>;
no catalog-authorized <NON_TEMPORAL_SUBJECT> coverage|archive is claimed.`;
event reconstruction with pre-YYYY ancestry that cannot extend the window;
required unproven-authority forms; and public-benchmark publication vintage
plus a legal evaluation range. `NON_TEMPORAL_SUBJECT` may not contain
digits, dates, protected years, or open-ended temporal language. Free
prose containing a range without a recognized wrapper remains AMBIGUOUS.
Protected-year tokens in operational fields are hard fails.
"outcomes measured in 2025" is not an exclusion.
Resumable implementation checkpoints: `generator_v0_checkpoints/`.
