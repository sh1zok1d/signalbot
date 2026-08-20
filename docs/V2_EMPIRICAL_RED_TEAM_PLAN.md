# V2 — Post-Stage-8 Empirical Red-Team / Model-Risk Gate

> Status: planned roadmap gate, docs/research only for now. This section does **not** change any frozen V2-v0 setup formula, threshold, lifecycle rule, `rules_version`, or current Stage 6–8 implementation scope. Its purpose is to define the empirical risks that must be attacked after the V2 Outcome Evaluator exists and before any claim of trading edge or user-facing promotion.

## Purpose

Engineering correctness is necessary but not sufficient. A deterministic, no-lookahead, replayable system can still implement a market description that has no predictive or economic edge. Post-Stage-8 validation therefore has an adversarial goal: **attempt to falsify V2's trading hypotheses, not optimize the reported metrics.**

A failed hypothesis is an acceptable research outcome. The platform must make it possible to conclude "no robust edge" without changing the evidence after seeing the result.

## Model-risk register — arguments against V2 that must remain explicit

1. **Market description != market prediction / formalized discretionary trading.**
   The three setup families may precisely formalize visually plausible market states without those states containing incremental information about future executable returns. Qualification accuracy is not evidence of predictive power.

2. **Setup-selection bias.**
   `TREND_PULLBACK`, `COMPRESSION_BREAKOUT`, and `CONFIRMED_BREAKOUT` were selected as hypotheses before empirical validation. The choice of these families is itself a research decision and may encode human hindsight or preference even when the implementation has zero code-level lookahead.

3. **Researcher degrees of freedom / human overfit.**
   Repeatedly inspecting failed historical/OOS cases and adding new filters, thresholds, regime exceptions, or features can turn the researcher into the optimizer. "It failed because this market was unusual" is not a valid exemption unless the regime distinction was predeclared.

4. **Parameter brittleness / magic-threshold risk.**
   Apparent edge may exist only at exact values such as one retracement bound, percentile threshold, lookback length, confirmation age, buffer multiplier, or quality gate. A robust effect should normally survive reasonable local perturbations rather than collapse around one isolated parameter point.

5. **Small sample / single-symbol concentration.**
   Initial V2 is BTCUSDT/perp only with three setup families. Even a calendar year may produce a small number of statistically useful independent episodes per family/direction/regime. Contract sample minimums are engineering promotion gates, explicitly not proof of statistical significance.

6. **Correlated observations / overstated effective sample size.**
   Consecutive or clustered episodes can be exposed to the same underlying market move/regime. Raw episode count can overstate the amount of independent evidence.

7. **Regime dependency / non-stationarity.**
   A family may look excellent in a trend, volatility expansion, or one market era and fail in chop, mean reversion, news shocks, or later market structure. Aggregate metrics can hide this dependency.

8. **Feature redundancy / complexity tax.**
   OI, funding, liquidations, taker flow, HTF context, and other derivatives features may add little or no incremental edge over simple price structure while increasing implementation and data-failure surface.

9. **Cross-exchange consensus may be decorative.**
   Binance + Bybit + OKX consensus is infrastructure-heavy. Its incremental contribution must be demonstrated against Binance-only and smaller-consensus baselines; complexity is not evidence of value.

10. **Simple-baseline risk.**
    V2 may not materially outperform a much simpler deterministic price-structure or V1 baseline after the same delay, costs, and evaluation rules. Beating zero is insufficient if the complexity does not beat simpler alternatives.

11. **Multiple-comparison / cherry-picking risk.**
    Splitting results by direction, setup family, confidence, volatility, regime, session, or other dimensions creates many opportunities to find an apparently strong subgroup by chance. Subgroup analyses must be predeclared or clearly labeled exploratory.

12. **30-day pilot misinterpretation.**
    A 30-day replay is an engineering/replay polygon, not evidence of durable trading edge. It may cover only one favorable BTC regime. Its purpose is to validate lifecycle, replay determinism, persistence, outcome computation, and report plumbing.

13. **Replay-to-live gap.**
    Historical replay can pass while live shadow fails because of publication timing, incomplete data, latency, outage behavior, or operational path differences. Historical evidence must never substitute for the separately required live-shadow gate.

14. **Cost/delay sensitivity.**
    Positive expectancy may depend on optimistic user-action delay, fees, spread/slippage assumptions, or exact entry-price semantics. Economic conclusions must be checked for reasonable adverse perturbations of these assumptions.

15. **Architecture can outrun evidence.**
    Adding more data sources, ML, order book, CoinGlass, more symbols, or more setup families before establishing whether the current three hypotheses add edge increases overfit surface and makes attribution harder. Expansion is not a remedy for an unvalidated core hypothesis.

## Required post-Stage-8 empirical red-team program

### A. Freeze before evaluation

- Freeze the candidate V2 rules/model identity before reading the designated OOS result.
- Record the exact `rules_version`, `calculation_version`, decision-code identity, data window, cost/delay assumptions, populations, metrics, baseline definitions, and planned subgroup/regime analyses.
- Do not silently retune thresholds or add filters under the same frozen identity.

### B. Separate engineering replay from edge validation

- First 30-day replay: engineering/replay validation only.
- The first serious edge evaluation must use a larger calendar span and satisfy the existing correctness-contract sample requirements, while remaining explicitly weaker than statistical proof.
- Historical replay and live-shadow evidence remain separate evidence sources exactly as the correctness contract requires.

### C. Untouched OOS and walk-forward

- Maintain a development/exploratory window separately from an untouched OOS window.
- Evaluate the frozen candidate on OOS without changing the candidate after seeing the result.
- If an OOS result causes a model change, the modified model becomes a new version and needs new untouched evidence; the consumed OOS period becomes development evidence for the new version.
- Add walk-forward evaluation across multiple chronological folds/market eras when sample size permits.

### D. Parameter-sensitivity / neighborhood stability

For every economically material versioned parameter, test a small predeclared neighborhood around the frozen value. The objective is not to search for the best value but to detect brittle "magic points".

Red flag: performance is exceptional only at one exact threshold and collapses under small neighboring perturbations.

Positive evidence: economically similar behavior persists across a reasonable local region, with no requirement that the frozen value be the numerical optimum.

### E. Ablation tests

At minimum compare full V2 against controlled removals where semantics permit:

- without OI contribution/gates;
- without funding;
- without liquidation evidence;
- without taker-flow evidence;
- without cross-exchange consensus;
- without 4h regime context;
- without 1h bias context;
- price-structure-only baseline.

The goal is attribution: determine which components add incremental value and which merely add complexity.

### F. Cross-exchange contribution test

Compare the same hypothesis/evaluation surface under:

- Binance-only evidence;
- Binance + Bybit where technically comparable;
- Binance + Bybit + OKX canonical consensus.

If full consensus provides negligible incremental benefit, simplification must remain an acceptable outcome.

### G. Baseline challenge

Compare V2, under identical delay/cost/population semantics, against at least:

- frozen V1 where metrics are genuinely comparable;
- a simple deterministic price-structure baseline;
- any intentionally trivial/null baseline needed to show that reported performance is not merely BTC drift or regime exposure.

A complex V2 should not be considered empirically justified merely because it has positive raw returns.

### H. Regime stability and concentration

- Report per-family results across a small, predeclared set of market-regime buckets when sample size is sufficient.
- Report concentration: how much aggregate PnL/expectancy depends on the best few episodes, one direction, or one calendar subperiod.
- Do not promote tiny regime cells as evidence; insufficient cells remain `NOT ENOUGH EVIDENCE` rather than being merged, omitted, or celebrated selectively.

### I. Statistical uncertainty / effective evidence

- Report sample counts and calendar span alongside every headline metric.
- Add uncertainty estimates appropriate to serially correlated time-series episodes; the exact method should be frozen in the future validation contract rather than improvised after seeing results.
- Distinguish raw episode count from effective independent evidence where clustering is material.
- Do not treat the current minimum sample thresholds as proof of significance; they remain engineering acceptance minima.

### J. Multiple-testing ledger

Maintain an explicit research ledger for:

- every parameter change motivated by historical results;
- every new filter/feature/setup added after inspecting failures;
- every subgroup/regime explored;
- every OOS window consumed.

Exploratory findings may motivate a future version but cannot be retroactively presented as confirmatory evidence for the version that generated them.

### K. Cost/delay stress

Re-run the economic evaluation under reasonable adverse perturbations of:

- notification/user-action delay;
- round-trip cost assumptions;
- entry feasibility/overshoot assumptions where the contract permits a research-only sensitivity view.

A model whose expectancy disappears under a small realistic worsening of execution assumptions is fragile even if the canonical point estimate passes.

## Kill / downgrade criteria

The empirical red-team phase must be allowed to reject or simplify V2. Strong warning/fail evidence includes:

- no positive cost-adjusted edge OOS;
- effect disappears under small parameter perturbations;
- one/few episodes dominate aggregate expectancy;
- performance exists only in one narrow historical regime without enough forward evidence;
- full V2 does not materially beat a simpler price-structure baseline;
- derivatives features or three-exchange consensus add negligible incremental value;
- repeated model changes are required after every OOS window;
- replay passes but live-shadow repeatedly fails the same family;
- the required sample size cannot be accumulated for a family in a reasonable period.

A failing family may remain research/shadow-only or be removed in a future version. Failure of one family does not justify averaging it into stronger families, consistent with the existing per-family promotion gate.

## Expansion rule

Until the core V2 families survive this empirical red-team program, do **not** treat additional feeds/features/setups/ML as the default response to weak results. New sources are justified only by a separately stated hypothesis and must later earn their own incremental value through ablation/baseline comparison.

## Required artifact before claiming V2 edge

Produce a version-pinned validation report containing, at minimum:

- exact evaluated identities and data windows;
- sample sizes/calendar spans;
- canonical acceptance metrics;
- OOS/walk-forward results;
- parameter-sensitivity results;
- ablation results;
- baseline and cross-exchange comparisons;
- regime/concentration analysis;
- execution cost/delay stress;
- all failed as well as passed tests;
- research-change/multiple-testing ledger;
- explicit conclusion: `NO ROBUST EDGE SHOWN`, `RESEARCH-ONLY`, `SHADOW-ELIGIBLE`, or the contract-defined promotion state supported by the evidence.

No user-facing claim of "proven edge", no calibrated win probability, and no expansion of the promotion semantics follows merely from passing one backtest or one 30-day replay.
