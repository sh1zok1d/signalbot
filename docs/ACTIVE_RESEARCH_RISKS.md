# Signalbot — Active Research Risks

**Status:** ACTIVE RECORD  
**Scope:** risks that can invalidate or mislead the current research-first program.

The older `PROJECT_RISK_AND_DEBT_REGISTER.md` is preserved as a historical register of the V2 implementation era. Items from it do not automatically remain active work under the 2026-08-26 research-first pivot.

## Severity vocabulary

- `CRITICAL` — can invalidate the central empirical conclusion;
- `HIGH` — can materially bias edge discovery/validation;
- `MEDIUM` — meaningful research/engineering debt that should be controlled;
- `LOW` — hygiene/maintainability issue with limited immediate inference risk.

## Active risks

| ID | Severity | Risk | Required control / closure evidence |
|---|---|---|---|
| RR-001 | CRITICAL | **Insufficient historical regime coverage.** Roughly one month of rich overlap cannot establish durable edge. | Build multi-year CORE evidence spanning materially different regimes; scope claims to the actual coverage. |
| RR-002 | CRITICAL | **Researcher/backtest overfitting.** Repeated threshold/variant inspection can manufacture apparent edge. | Development/validation/OOS separation, search-surface accounting, frozen confirmatory candidates, consumed-window ledger. |
| RR-003 | CRITICAL | **Lookahead / timestamp-semantic leakage.** Historical reconstruction can accidentally use information unavailable at decision time `T`. | Exact as-of contracts, no-lookahead tests, timestamp/source manifests, fail-closed behavior. |
| RR-004 | HIGH | **Provider-granularity inflation.** Coarse source observations (for example 5m OI) may be forward-filled and mistaken for real fine-grained information. | Preserve native observation granularity; prohibit claims based on pseudo-minute timing created by resampling. |
| RR-005 | HIGH | **One regime mistaken for universal edge.** A candidate may only work in trend, squeeze, low-vol range, etc. | Predeclare regime definitions for confirmatory tests; report regime concentration; validate regime gating prospectively. |
| RR-006 | HIGH | **Post-hoc regime excuse.** A failed strategy can always be explained after the fact by saying the market regime was wrong. | Treat post-hoc regime explanations as exploratory only; require a frozen regime rule on new data. |
| RR-007 | HIGH | **Correlated observations / inflated N.** Repeated 5m signals from one impulse are not independent evidence. | Episode/time clustering, block-level uncertainty, effective-N/concentration reporting. |
| RR-008 | HIGH | **Rich-feature availability bias.** OI/funding/liquidations/cross-venue overlap is shorter and may select unusual periods. | Separate CORE mechanism proof from RICH incremental-feature tests; report exact capability/evidence tier by period. |
| RR-009 | HIGH | **Missingness is non-random.** Exchange outages/data gaps may cluster during volatile periods. | Denominator trees, gap reports, missingness-by-regime analysis; never silently drop hard cases or replace with zero. |
| RR-010 | HIGH | **Simple baseline equivalence.** Complex detector may only rediscover momentum/range/breakout behavior. | Always compare against simplest relevant price/matched-random/null baselines and ablations. |
| RR-011 | HIGH | **Parameter brittleness / magic thresholds.** One narrow optimum can be noise. | Neighborhood/plateau analysis, monotonic score-outcome checks, chronological development blocks. |
| RR-012 | HIGH | **Execution sensitivity.** Historical gross edge may disappear under realistic latency/costs. | Delay resolution consistent with available history; fixed cost/slippage stress before tradability claims. |
| RR-013 | HIGH | **OOS contamination.** A validation/holdout result used to change a rule cannot remain untouched evidence for that rule. | Version new hypotheses after consumed windows; record every consumption in `RESEARCH_LEDGER.md`. |
| RR-014 | HIGH | **E1-RUN-001 semantic contamination before final open.** The frozen experiment can be invalidated by changing TP/CB/FB or controls now. | Finish only with frozen evaluator/protocol; otherwise close explicitly as technically incomplete. |
| RR-015 | MEDIUM | **Architecture inertia / sunk-cost bias.** Existing V2 code may pull research toward defending already-built components. | Mechanism-first studies; no Stage 6+ restart without independently validated edge; complexity must earn incremental value. |
| RR-016 | MEDIUM | **Data-source shopping.** Adding new feeds after weak results can become another form of hypothesis rescue. | New sources require a declared research question; rich feeds enter only as incremental tests unless independently justified. |
| RR-017 | MEDIUM | **Cross-asset pseudo-replication.** BTC/ETH/SOL share market regimes and cannot simply be pooled as iid rows. | Report asset-level results and shared-regime dependence; use cross-asset evidence only where mechanism scope warrants it. |
| RR-018 | MEDIUM | **Unreproducible mutable datasets.** Later DB corrections/provider changes may alter historical results. | Versioned manifests, source/revision identity, reproducible materialization commands and immutable experiment artifacts. |
| RR-019 | MEDIUM | **Outcome metric shopping.** Switching between winrate/PnL/MFE/horizon after seeing results can create favorable narratives. | Define primary claim/outcomes before confirmatory evaluation; label post-hoc metrics exploratory. |
| RR-020 | MEDIUM | **No-edge result rejected psychologically.** Project goal wording may pressure researchers to “find something.” | Explicitly accept `NO EDGE`, `REJECTED`, `INCONCLUSIVE_SAMPLE`; stop/pivot hypothesis classes when evidence warrants it. |

## Frozen / historical debt

The following categories remain in repository history but are **not active blockers during R0–R6 unless a research task directly depends on them**:

- unfinished Stage-6 lifecycle implementation;
- Stage-7 feasibility/product semantics;
- Stage-8 full product outcome layer;
- Telegram/product promotion work;
- product maturity/config polish unrelated to research inference;
- speculative reusable framework refactors.

If product development restarts after validated edge, re-audit the historical V2 debt rather than blindly reopening every old item.

## Review cadence

Update this file when:

- a risk is closed with evidence;
- a new dataset/source introduces a new semantic risk;
- a confirmatory candidate is frozen;
- an OOS/validation window is consumed;
- project posture changes again.
