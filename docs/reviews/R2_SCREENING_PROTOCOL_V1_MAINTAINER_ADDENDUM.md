# R2 Screening Protocol V1 — Maintainer Review Addendum

**Reviewed red-team PR:** #75  
**Red-team head reviewed:** `72850e948bea985d6bd887f6aa15cc7db5a6b5d6`  
**Maintainer correction commit:** `3dbab56ef81bd3e5573361e3255c7ecf1ea06770`

The independent red-team correctly identified one blocker and several material gaps in PR #74. Most proposed remediations were accepted. Three points were narrowed before adopting the protocol as canonical.

## 1. Boundary embargo: exclude, do not truncate

The red-team correctly identified contamination risk at the 2024→2025 and 2025→2026 pool boundaries.

However, allowing per-event outcome-horizon truncation would mix different outcome definitions near a boundary and silently change the estimand.

Canonical rule:

- an observation is eligible for horizon H only when the complete frozen H path resolves strictly inside its own evidence pool;
- otherwise that observation is excluded for H;
- no per-event horizon truncation.

This preserves both holdout cleanliness and outcome-definition consistency.

## 2. Regime scope: no named shock-year escape hatch

The red-team correctly identified a false-negative risk from forcing every legitimate regime-scoped mechanism into an unconditional 4-of-5-year claim.

However, a preregistered list such as "exclude 2020/2022" is still vulnerable to adaptive historical selection because those calendar episodes are already known during discovery.

Canonical rule:

- 4-of-5 applies to unconditional claims;
- named year/event deletion is not an authorized rescue path;
- a genuinely regime-scoped hypothesis must preregister a deterministic state classifier using only information available at decision time T;
- the full gated rule is then the hypothesis;
- any regime explanation created after per-year outcomes are viewed is `POSTHOC_UNTESTED`.

This preserves a path for real narrow mechanisms without legitimizing calendar cherry-picking.

## 3. MPIE: mechanism relevance, not hidden PnL

The red-team correctly required an outcome-independent anchor for MPIE.

Canonical rule prefers a distributional anchor independent of candidate outcomes, such as a fixed fraction of the unconditional/local median absolute move or volatility scale used by the normalized primary metric.

Execution cost may be an additional anchor only when the claim is explicitly about tradability. R2 mechanism discovery is not required to prove net profitability.

## Maintainer assessment

With these corrections, the red-team blocker and major findings are resolved narrowly without expanding market-outcome access or research scope.

- 2025 inspected: **NO**
- 2026 inspected: **NO**
- H03 started: **NO**

**Maintainer verdict:** protocol is methodologically sound enough to govern H03, subject to the separate operational requirement that H01/H02 history be durably preserved before H03 is opened.
