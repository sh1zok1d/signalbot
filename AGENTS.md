# Signalbot — Codex repository instructions

This file is the root instruction map for Codex. Keep it short and treat the
linked repository documents as the source of truth. Do not duplicate large
contracts here.

## Project posture

Signalbot is a BTC perpetual decision-support / forecasting research project.
It is not an autonomous trading bot. Engineering correctness and market edge
are separate questions; never treat passing tests as evidence of predictive
validity.

V1 is a frozen research baseline. V2-v0 is research-frozen while it is being
implemented and empirically falsified.

## Read the right source of truth first

Before changing code, read the documents relevant to the task:

- Product direction / stage order: `docs/FORECASTING_ROADMAP.md`
- Frozen V2 product semantics: `docs/V2_PRODUCT_CONTRACT.md`
- Deterministic V2 formulas, thresholds, correctness and promotion rules:
  `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
- Empirical falsification protocol: `docs/V2_EMPIRICAL_RED_TEAM_PLAN.md`
- Mathematical hypotheses and freeze/test status:
  `docs/V2_MATHEMATICAL_HYPOTHESIS_REGISTER.md`
- Open risks and technical debt: `docs/PROJECT_RISK_AND_DEBT_REGISTER.md`
- Stage 2 percentile / feature contracts: `docs/STAGE2_SPEC.md` and
  `docs/STAGE2_CLARIFICATIONS.md`
- Runtime config: `config/v2.yaml` and `config/stage2.yaml`

The root `README.md` contains useful Stage-1 history but is not the canonical
source for current V2 semantics. When V2 docs and README wording differ, use
the V2 contracts/roadmap above.

## Scope discipline

- Make the smallest change that satisfies the explicit task and its acceptance
  criteria.
- Do not opportunistically refactor adjacent systems.
- If working on an existing PR, stay on that PR/branch unless explicitly told
  otherwise.
- Do not create, rename, merge, or retarget branches/PRs unless the task asks
  for it.
- Never merge or deploy unless explicitly authorized.
- Never touch production/VPS state unless explicitly authorized.
- Never expose or commit `.env`, tokens, credentials, chat IDs, private keys,
  or other secrets.

If the correct owner/layer of a change is genuinely unclear, investigate and
report the ambiguity instead of inventing architecture or broadening scope.

## V2 research freeze — load-bearing rule

An unresolved market or mathematical hypothesis is NOT authorization to modify
V2-v0.

Unless the task explicitly authorizes a versioned model change, do not change:

- `rules_version`
- `config/v2.yaml` `enabled`
- regime/bias/compression thresholds
- percentile windows or evidence transforms
- setup lookbacks, pullback multipliers, confirmation ages, horizons
- protection-buffer or setup-strength formulas
- OI semantics
- agreement thresholds
- setup-family definitions

Correctness/statistical-validity defects that would invalidate the experiment
may be fixed, but distinguish them explicitly from uncertain market hypotheses.
Do not invent a new numeric threshold merely because it looks more reasonable.

## Core correctness invariants

Preserve these unless a reviewed contract explicitly changes them:

- No lookahead: historical inputs for decision boundary `T` must be strictly
  available as-of `T` under the relevant contract.
- Exact bucket identity matters; do not replace timeframe-aligned bucket
  timestamps with a generic decision timestamp.
- Missing/immature data is different from malformed/corrupted data.
  Missingness may produce an unavailable/not-ready result; corruption must
  remain fail-closed with the owning domain error.
- Do not silently fall back across percentile windows, calculation versions,
  symbols, market types, or buckets.
- Preserve deterministic replay/provenance identity.
- Preserve raw-data no-downgrade behavior for optional fidelity fields.
- Multi-timeframe signals are roles, not independent statistical votes; do not
  double-count the same underlying move by inventing new voting logic.

## Research-governance behavior

When a task is an audit or empirical-validation task:

- Try to falsify the current hypothesis; do not optimize metrics toward a
  preferred result.
- Separate `BUG / CORRECTNESS`, `STATISTICAL_VALIDITY_GAP`, `HYPOTHESIS`,
  `REDUNDANCY_RISK`, and `OVERFITTING_RISK`.
- `HYPOTHESIS` findings are normally `FREEZE_AND_TEST`, not immediate formula
  edits.
- Do not use future returns to choose a measurement/correctness invariant.
- Prefer characterization/adversarial tests before behavioral changes when the
  contract is intentionally frozen.

## Qodo / review workflow

If the task references Qodo or an existing PR review:

1. Read the latest PR head and the full current review context.
2. Adjudicate every finding as `VALID`, `FALSE_POSITIVE`, or `OUT_OF_SCOPE`.
3. Fix valid findings in the same PR when possible; do not blindly implement
   every suggestion.
4. Explain rejected findings with code/contract evidence.
5. Re-run focused tests and the full required validation after amendments.
6. Re-check the new HEAD; a previously clean review does not cover later
   commits.

## Development environment and tests

CI uses Python 3.11 and installs `requirements-dev.txt`.

Default validation after code changes:

```bash
python -m compileall -q .
python -m pytest -q
git diff --check
```

Run focused tests for the touched module before the full suite. Mirror focused
CI suites from `.github/workflows/ci.yml` when relevant.

If touching storage/PostgreSQL behavior, run the real PostgreSQL regressions
when the environment supports them. CI uses PostgreSQL 16 and explicitly runs:

```bash
python -m pytest -q tests/storage/test_klines_no_downgrade.py -v
```

A skipped integration test is not proof that the database behavior is correct.
Do not claim real-DB validation if the required service was unavailable.

For docs-only changes, still run the programmatic checks required by the task
or the surrounding contract when feasible; at minimum run `git diff --check`
and any focused tests whose behavior the documentation describes.

## Before finishing

- Inspect the final diff for unintended files or semantic drift.
- Confirm V2 remains disabled unless the task explicitly says otherwise.
- Confirm frozen V2-v0 parameters/formulas are unchanged when the task is not a
  model-version change.
- Report focused test results, full-suite result, compile check, and
  `git diff --check` result accurately; never fabricate a test result.
- Report skipped/unavailable validations explicitly.
- Report changed files and any important non-changes.
- Do not merge or deploy unless explicitly authorized.

Prefer precise, narrow patches that are easy for a human reviewer and Qodo to
verify over broad "cleanup" changes.