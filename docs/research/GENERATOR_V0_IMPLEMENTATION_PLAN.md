# Generator V0 implementation mapping

Base: 58a49d25d7a9b730db402eb5ebe7c7fa0165ff33. Authorized 0A:
64e39326630d92761ff1ef062d72f204bcba42fe. Design JSON remains authoritative.

Use the existing `python -m scripts.research.<unit>` / argparse convention.
Keep this isolated infrastructure in `scripts/research/generator_v0/`.
No production providers were found in the research tooling; provider-neutral
protocol with deterministic mock first, concrete adapter verified against
current official documentation before implementation. Python standard library
is sufficient at runtime; pytest is the test dependency.

| Checkpoint | Frozen requirements / implementation |
|---|---|
| 1 | `BLIND_MECHANISM_MAP_V0`, `GOVERNANCE_REGION_AUTHORITY_V0`, structural provenance, exact-byte source pins; context module |
| 2 | 27-field `CANDIDATE_SCHEMA`, `DATA_STATUS_TAXONOMY`, `PROVIDER_INTERFACE`, `MOCK_PROVIDER`, `BUDGET_GUARD`, transactional `RUN_LEDGER`, `HUMAN_MUTATION`, `DATA_GAP_LEDGER_V0` |
| 3 | `ROLE_CONTEXT_MATRIX` request construction, `NOVELTY_CRITIC`, `FEASIBILITY_CRITIC`, `RED_TEAM`, scoped authority, sanitized selector inputs |
| 4 | `GENERATOR`, `SELECTOR`, `SHADOW_BATCH_RUNNER`; round slots, 40 cards, diversity, separate ordinal judgments, two streams |
| 5 | Two clean deterministic zero-cost mock campaigns; semantic digests and meaningful varied fixtures |
| 6 | Real HTTP adapter, fake transport tests, explicit spend authorization and upper-bound reservation |
| 7 | CLI preflight/run/resume, environment template, human review and audit workflow |
| 8 | Adversarial tests, fixes, integration verification, final operator readiness and routing |

Never expose raw mechanism memory, RESULT artifacts, historical evidence
values, outcome-based rotation status, or full history to any automated role.
Generator additionally never sees governance authority or critic outputs;
selector sees only typed sanitized verdicts, data status and ordinal judgments.
No dataset reader or scientific evaluator is imported by this subsystem.

Implementation representations may give frozen text fields explicit types
and enforce bounds, without changing their meaning. Role prompts describe
output formats; frozen source-derived content retains its exact provenance.
Family/source slot allocation is orchestration configuration, not historical
scientific evidence. Unknown data sources cannot become DATA_READY.

SQLite transactions will bind reservations, provider responses, parsed cards,
critics, mutation events and terminal registry. On ambiguous in-flight paid
requests, resume stops for reconciliation instead of automatically replaying.
Mock campaign evidence validates infrastructure only.

Checkpoint records use Git-resolved SELF identity: resolve the commit that
first introduced each immutable record, then its tree. This avoids recursive
self-hashes. Actual predecessor SHA is embedded and all SHAs reported at end.

Local checkout omits `docs/research_data/` payloads. Their original index/tree
identities are preserved; publishing uses the exact base tree plus explicit
changed paths. This is not evidence that data-consuming integration tests pass.
