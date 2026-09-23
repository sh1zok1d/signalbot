# Generator V0 — pre-live repair (offline)

**Completion state:** `READY_FOR_INDEPENDENT_REVIEW` (not `READY_FOR_LIVE_SHADOW`)
**Base:** `71853f9b6c6b59c03d22e9a43cb52dd7e9699368`
**Machine-readable twin:** `docs/research/GENERATOR_V0_PRE_LIVE_REPAIR.json`
**Gate evidence:** `docs/research/generator_v0_repair/OFFLINE_GATE_REPORT.json`

No live campaign, no paid call, no protected 2025/2026 data, no scientific
outcome. Sealed `first-shadow-v6` and `first-shadow-v7` were not modified or
resumed. The v7 generation:3 cards were not used as a specification: 9 of 10
remain `HARD_FAIL` under the new contract.

## What changed and why

The audit found two design problems behind the v4–v7 one-failure-per-run
history: any single model-content deviation aborted the whole campaign
(and replayed identically on resume), and the validator enforced wording
rules the generator was never told, grown from inspected outputs.

| Finding | Change |
|---|---|
| F01 | Per-card `HARD_FAIL` quarantine at intake; per-card `REVIEW_FAILED` after bounded critic retries. Campaign stops only for budget (`STOPPED_BUDGET`), uncertain provider state (`PAUSED_UNCERTAIN_CALL`), provider throttling/rejection, integrity errors, or fewer than 25 admissible cards (`STOPPED_INSUFFICIENT_VALID`). |
| F02 | `contract.py` rule table (`GENERATOR_CONTRACT_V02`) is the single authority; the generator prompt's hard rules and the validator dispatch are both derived from it. Canonical `LEGAL_RANGE`: `YYYY-MM..YYYY-MM`, `pre-YYYY`, `per snapshot`; end month after 2024-12 cannot be expressed. Inspected-output wrappers are no longer accepted for new output. |
| F03 | Stated rule: never write 2025 or 2026 in any form. The exclusion-sentence parser is gone for new output. |
| F04 | Recency words are forbidden only in time-scope fields; explicit open-ended/post-2024 phrases in every field. Point-in-time "latest bar at or before T" wording is valid. |
| F05 | Previously hidden rules (missing observables, grid product, trading phrases, nearest signature) are stated in the prompt. Exact generation cardinality and slot identity enforced by the strict schema. |
| F06 | Novelty relations are objects keyed by exact signature and candidate IDs in the strict schema. |
| F07 | Critic caps: novelty 12000, red team 8000, feasibility 6000, selector 2000 tokens. A length stop is a billed failure with its usage cost, retried once. |
| F08 | Failure classes `FAILED_NOT_BILLED` (429/503 backoff-retry; other 4xx pause), `FAILED_WITH_COST`, `UNCERTAIN`; attempt-keyed retries; offline `reconcile`. |
| F09 | Deterministic ordinal order is authoritative; the selector LLM call is advisory and never aborts. |
| F10 | Lineage spend: derive carries every non-imported source charge; the ceiling check is lineage + journal + new reservation ≤ cap. |
| F13 | Derive records every non-imported source call as a prior attempt, with per-card intake verdicts for generator rounds. |
| F11 | Feasibility `LEGAL_RANGE` check defined (range end and catalog bounds only; coverage is data status). |
| F12 | Sealed journals refused by content hash at any path; archival reads are immutable and refuse a non-empty WAL. |
| F17 | Not-billed failures charge 0 instead of their reservation. |

## Legacy compatibility (option A)

`docs/research/GENERATOR_V0_LEGACY_V01_GRANDFATHER.json` lists the three
first-shadow generation:0/1/2 call keys and the exact digests of their 30
cards. Only those may be admitted, and only under the frozen v0.1 validator
(`legacy_v01_schema.py`). The manifest is recomputed from the sealed v7
journal in tests. New model output is judged only by V02.

## Frozen-design amendments (outcome-blind)

- Hard fail is per candidate (the design already measures a hard-fail rate).
- `MIN_VALID_CANDIDATES = 25` (the frozen batch lower bound).
- Diversity controls apply to the attempted slot plan, as they are phrased.
- Selector output is advisory; the ordinal ranking role is unchanged.

## Operator states

| Status | Resolution |
|---|---|
| `STOPPED_BUDGET` | `authorize-budget-extension` within the owner ceiling, then `resume` |
| `PAUSED_UNCERTAIN_CALL` | `reconcile --call-key … --resolution NOT_BILLED\|BILLED [--cost-usd …]`, then `resume` |
| `PAUSED_PROVIDER_THROTTLED` | `resume` later (not-billed attempts cost nothing) |
| `PAUSED_PROVIDER_REJECTED` | fix the request contract or credentials, then `resume` |
| `PAUSED_BACKGROUND_PENDING` | `resume` (polls the same response id) |
| `STOPPED_INSUFFICIENT_VALID` | terminal; derive a new run |

## Open items for the independent reviewer

- Provider acceptance of the new strict schemas is verified offline only
  against the documented subset.
- For a v7-derived run the worst-case remaining bound exceeds the remaining
  owner authority with the raised critic caps; this is an owner decision. A
  live run stops cleanly at `STOPPED_BUDGET` rather than overspending.
- The corpus and fault scenarios were written by the implementer.
- Derive imports generation rounds only; source critic calls are carried as
  lineage spend and re-run.
