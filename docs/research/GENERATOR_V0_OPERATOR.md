# Generator V0 shadow campaign

Status: structured-output + role-specific routing adapter with a 600-second
real Chat Completions timeout. Frozen scientific design is unchanged. A
successful campaign still terminates at `PENDING_HUMAN_REVIEW`. The archived
partial paid runs `artifacts/generator_v0/first-shadow` and
`artifacts/generator_v0/first-shadow-v2` are sealed and the operator refuses
to open them. One campaign generates
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
resume or overwrite `artifacts/generator_v0/first-shadow` or
`artifacts/generator_v0/first-shadow-v2`.

```bash
python -m scripts.research.generator_v0 run --provider openai --allow-real-llm --budget-usd 10 --run-dir artifacts/generator_v0/shadow
```

Budget may be lower, but cannot exceed USD 30. Mock remains the default even
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
No automatic retries exist. A malformed persisted answer remains visible as a
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
`GENERATOR_V0_MODEL_ROUTING.md` / `models.py`. Real Chat Completions
HTTPS timeout is `OPENAI_REQUEST_TIMEOUT_SECONDS = 600` and is part of
run configuration identity. A `TimeoutError` after dispatch is `UNCERTAIN`
and is never automatically replayed.
Resumable implementation checkpoints: `generator_v0_checkpoints/`.
