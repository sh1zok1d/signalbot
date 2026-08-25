# Signalbot — Codex repository instructions

This is the root instruction map for Codex. Keep it concise; linked repository documents are the source of truth. Do not duplicate large contracts here.

## Project posture

Signalbot is a BTC perpetual decision-support / forecasting research project, not an autonomous trading bot. Engineering correctness and market edge are separate questions; passing tests is not evidence of predictive validity.

V1 is a frozen research baseline. V2-v0 is research-frozen while it is implemented and empirically falsified.

Forecasting V2 is the current primary analytical engine and implementation program, but **Signalbot is not defined by the success of one forecasting hypothesis**. Project-wide future-extensibility, evidence/auditability, competitive posture, and post-roadmap strategy-review guardrails live in `docs/PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md`. Future product ideas live in `docs/PRODUCT_HYPOTHESES.md` and are not implementation authorization.

## Read the right source of truth first

Before changing code, read the documents relevant to the task:

- Project-wide strategy / architecture posture: `docs/PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md`
- Product direction / stage order: `docs/FORECASTING_ROADMAP.md`
- Frozen V2 product semantics: `docs/V2_PRODUCT_CONTRACT.md`
- Deterministic V2 formulas, thresholds, correctness and promotion rules: `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
- Tactical execution order / gates: `docs/PROJECT_EXECUTION_PLAN.md`
- Empirical falsification protocol: `docs/V2_EMPIRICAL_RED_TEAM_PLAN.md`
- Mathematical hypotheses and freeze/test status: `docs/V2_MATHEMATICAL_HYPOTHESIS_REGISTER.md`
- Future product hypothesis parking lot: `docs/PRODUCT_HYPOTHESES.md`
- Open risks and technical debt: `docs/PROJECT_RISK_AND_DEBT_REGISTER.md`
- Stage 2 feature / percentile contracts: `docs/STAGE2_SPEC.md` and `docs/STAGE2_CLARIFICATIONS.md`
- Runtime config: `config/v2.yaml` and `config/stage2.yaml`

The root `README.md` contains useful Stage-1 history but is not canonical for current V2 semantics. When README and V2 documents differ, follow the V2 contracts/roadmap.

## Scope discipline

- Make the smallest change that satisfies the explicit task and acceptance criteria.
- Do not opportunistically refactor adjacent systems.
- If working on an existing PR, stay on that PR/branch unless explicitly told otherwise.
- Do not create, rename, merge, or retarget branches/PRs unless the task asks for it.
- Never merge, deploy, or touch production/VPS state unless explicitly authorized.
- Never expose or commit `.env`, tokens, credentials, chat IDs, private keys, or other secrets.
- If the correct owner/layer is genuinely unclear, investigate and report the ambiguity instead of inventing architecture or broadening scope.
- Product hypotheses recorded in `docs/PRODUCT_HYPOTHESES.md` are a parking lot, not roadmap scope. Do not implement them without an explicit later product-direction decision.

## Future-extensibility guardrail

Preserve natural boundaries between reusable platform capabilities and V2-specific logic **when the current task actually exposes such a boundary**. Do not build speculative universal abstractions.

When ownership is ambiguous, use the two project-level design checks from `docs/PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md`:

1. **Second-engine test:** would a future independent analytical engine need private V2 internals to reuse the capability?
2. **Removal test:** would removing V2 unnecessarily delete a capability that is conceptually useful outside forecasting?

A positive answer is a reason to inspect the boundary, not automatic authorization to refactor. Current scope and frozen contracts still win.

Prefer structured, traceable analytical results over presentation-layer narrative as the source of truth. UI/Telegram/LLM wording must not silently become the mathematical contract.

## V2 research freeze — load-bearing rule

An unresolved market or mathematical hypothesis is NOT authorization to modify V2-v0.

Unless the task explicitly authorizes a versioned model change, do not change:

- `rules_version` or `config/v2.yaml` `enabled`
- regime/bias/compression thresholds
- percentile windows or evidence transforms
- setup lookbacks, pullback multipliers, confirmation ages, horizons
- protection-buffer or setup-strength formulas
- OI semantics, agreement thresholds, or setup-family definitions

Correctness/statistical-validity defects that would invalidate the experiment may be fixed, but distinguish them explicitly from uncertain market hypotheses. Do not invent a numeric threshold merely because it looks more reasonable.

## Core correctness invariants

Preserve these unless a reviewed contract explicitly changes them:

- No lookahead: historical inputs for decision boundary `T` must be available as-of `T` under the relevant contract.
- Exact bucket identity matters; do not replace timeframe-aligned bucket timestamps with a generic decision timestamp.
- Missing/immature data is different from malformed/corrupted data. Missingness may become unavailable/not-ready; corruption remains fail-closed with the owning domain error.
- Do not silently fall back across percentile windows, calculation versions, symbols, market types, or buckets.
- Preserve deterministic replay/provenance identity.
- Preserve raw-data no-downgrade behavior for optional fidelity fields.
- Multi-timeframe inputs are semantic roles, not independent statistical votes; do not invent double-counting/voting logic.

## Research-governance behavior

For audit / empirical-validation tasks:

- Try to falsify the current hypothesis; do not optimize toward a preferred result.
- Separate `BUG/CORRECTNESS`, `STATISTICAL_VALIDITY_GAP`, `HYPOTHESIS`, `REDUNDANCY_RISK`, and `OVERFITTING_RISK`.
- `HYPOTHESIS` findings are normally `FREEZE_AND_TEST`, not immediate formula edits.
- Do not use future returns to choose a measurement/correctness invariant.
- Prefer characterization/adversarial tests before behavioral changes when the contract is intentionally frozen.
- `UNKNOWN`, `NO EDGE`, and `INSUFFICIENT DATA` are valid outcomes; do not manufacture certainty or rescue a failed hypothesis with post-hoc tuning.

## Qodo / PR review workflow

If the task references Qodo or an existing PR review:

1. Read the latest PR HEAD and the full current review context.
2. Adjudicate every finding as `VALID`, `FALSE_POSITIVE`, or `OUT_OF_SCOPE`.
3. Fix valid findings in the same PR when possible; do not blindly implement every suggestion.
4. Explain rejected findings with code/contract evidence.
5. Re-run focused tests and required full validation after amendments.
6. Re-check the new HEAD; a clean review of an older commit does not cover later commits.

## Development environment and tests

CI uses Python 3.11 and installs `requirements-dev.txt`. Run focused tests for the touched module first, then the required wider suite. Mirror focused CI commands from `.github/workflows/ci.yml` when relevant.

Default validation after code changes:

```bash
python -m compileall -q .
python -m pytest -q
git diff --check
```

If touching storage/PostgreSQL behavior, run real PostgreSQL regressions when the environment supports them. CI uses PostgreSQL 16 and explicitly runs:

```bash
python -m pytest -q tests/storage/test_klines_no_downgrade.py -v
```

A skipped integration test is not proof of database correctness. Do not claim real-DB validation when the service was unavailable.

For docs-only changes, still run checks required by the task/contract when feasible; at minimum run `git diff --check` and any focused tests whose behavior the documentation describes.

## Before finishing

- Inspect the final diff for unintended files or semantic drift.
- Confirm V2 remains disabled unless the task explicitly says otherwise.
- Confirm frozen V2-v0 parameters/formulas are unchanged when the task is not a model-version change.
- Report focused tests, full-suite result, compile check and `git diff --check` accurately; never fabricate a result.
- Report skipped/unavailable validation explicitly, plus changed files and important non-changes.
- Do not merge or deploy unless explicitly authorized.

Prefer precise, narrow patches that are easy for a human reviewer and Qodo to verify over broad cleanup changes.