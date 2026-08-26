# Signalbot Edge Research Protocol

**Status:** ACTIVE  
**Purpose:** prevent the new research-first direction from becoming unrestricted backtest mining.

The objective is to discover and independently validate robust conditional market structure. The objective is **not** to force a profitable rule out of historical data.

## 1. Evidence labels

Every hypothesis/configuration must be labeled as one of:

- `EXPLORATORY` — outcome data may be inspected and rules may change;
- `CANDIDATE` — rule is frozen for a declared confirmatory test;
- `VALIDATED_CANDIDATE` — survived the declared independent validation;
- `REJECTED` — evidence does not justify continued use in its current form;
- `INCONCLUSIVE_SAMPLE` — insufficient evidence to distinguish survival from failure.

Do not promote `EXPLORATORY` results by rhetoric.

## 2. Mechanism before parameter

Before scanning thresholds, write down:

- what market behavior is hypothesized;
- why it could persist;
- what information is available before decision time `T`;
- what outcome should change if the mechanism is real;
- the simplest meaningful baseline;
- at least one negative control.

Prefer mechanisms such as compression/expansion, failed-break mean reversion or trend continuation over arbitrary indicator recipes.

## 3. Dataset separation

Use chronological separation whenever possible:

- **discovery/development** — allowed to influence rules and parameters;
- **validation** — tests a frozen candidate;
- **untouched OOS** — final confirmatory evidence for that candidate/version;
- **forward shadow** — subsequent live evidence.

Once results from a validation/OOS window influence a rule change, that window is consumed and cannot be described as untouched for the new rule.

## 4. Threshold and parameter tuning

Threshold tuning is legitimate on development data.

A threshold is credible when evidence suggests a stable conditional relationship, for example:

- stronger score -> stronger expected outcome;
- several neighboring thresholds behave similarly;
- the conclusion survives chronological development blocks;
- the selected threshold is not one isolated optimum among noisy neighbors.

Avoid selecting values such as `0.837` solely because they maximize one historical PnL result.

Before confirmatory validation, freeze:

- exact threshold(s);
- lookbacks;
- direction rule;
- regime rule;
- outcome horizons;
- missingness rules;
- delay/cost assumptions;
- baselines/controls;
- verdict criteria.

## 5. Multiple testing / search-surface accounting

Track tested hypothesis families and material variants.

If dozens/hundreds of configurations are explored, the final result must not be interpreted as though one prespecified strategy was tested once.

At minimum record:

- number/classes of variants searched;
- parameters varied;
- datasets inspected;
- metrics used for selection;
- whether the final rule emerged post-hoc.

If the search surface becomes large, add explicit multiple-testing/PBO-style analysis before making strong claims.

## 6. Baselines

Every directional candidate should face the simplest relevant alternatives, for example:

- unconditional drift/null;
- same direction at matched random times;
- simple momentum/mean-reversion rule;
- ordinary price breakout/pullback;
- candidate without the feature/gate being claimed as incremental value.

A complicated model matching a simple price baseline has not earned its complexity.

## 7. Negative controls

Use controls that attack the claimed information source, where semantically valid:

- same-T direction inversion;
- time shift;
- feature removal/permutation;
- venue removal/permutation;
- matched random timing;
- regime-matched random timing.

A negative control that performs similarly may reveal generic regime exposure rather than edge.

## 8. Outcomes and metrics

Do not judge a strategy by win rate alone.

Report as appropriate:

- directional return distribution;
- mean and median;
- positive share;
- MFE/MAE;
- tail losses/gains;
- drawdown/path properties for actual trade simulations;
- time-to-MFE/time-to-MAE;
- candidate frequency;
- path completeness/missingness;
- performance under delay and costs.

For probabilistic/non-directional hypotheses report the metric appropriate to the claim rather than forcing PnL onto every research question.

## 9. Effective sample size and concentration

Raw 5m observations are not iid evidence.

Always inspect:

- time clustering;
- repeated events from the same market impulse;
- UTC-day/week/month concentration;
- regime concentration;
- asset concentration;
- direction imbalance.

Prefer episode/block-level uncertainty methods when dependence is material.

## 10. Regime analysis

Regime dependence is a valid hypothesis, not an automatic excuse for failure.

If a candidate is expected to work only in a regime, define the regime using information available at `T` and validate the complete gating rule prospectively.

Post-hoc statements such as “it failed because volatility was low” are exploratory until a frozen regime classifier reproduces the effect on new data.

## 11. Parameter robustness

Before promoting a candidate, inspect a local parameter neighborhood.

Good sign:

> a broad region of thresholds/lookbacks produces similar qualitative behavior.

Bad sign:

> one narrow parameter point is profitable while adjacent values collapse or reverse.

Robustness is not permission to choose the best OOS point after inspection.

## 12. Cross-time validation

A durable-edge claim should cover materially different market conditions appropriate to its scope.

For BTC, prefer evidence spanning multiple years/regimes rather than one month. A candidate that only survives one localized period must be described as regime/local evidence until independently reproduced.

## 13. Cross-asset validation

Use other liquid assets such as ETH/SOL only when the mechanism is claimed to be market-general.

Do not pool all rows and call them independent. Report per asset and account for shared crypto-market regime exposure.

A BTC-specific mechanism does not need to work on every asset; its claim must simply be scoped honestly.

## 14. Rich-feature incremental tests

OI, funding, liquidations, taker flow and cross-venue features should usually be tested as additions to a simpler validated core.

Required comparison:

`CORE + FEATURE` versus `CORE`

under the same candidate population semantics and comparable data-quality window.

A feature earns complexity only when it adds stable information, not because it sounds economically relevant.

## 15. Delay and economic sensitivity

Historical edge must be tested under the delay resolution actually supported by the data.

Do not synthesize sub-minute execution precision from 1m history.

Stress reasonable total friction values and report when conclusions disappear. Detector research may remain gross, but a tradability claim may not ignore execution.

## 16. Missing data

Never replace unavailable evidence with zero or silently drop hard cases.

Report denominator trees and path completeness. Missingness may be correlated with outages/volatility and therefore can bias results.

## 17. Minimum standard for a `VALIDATED_CANDIDATE`

There is no single numeric magic threshold. A candidate should normally demonstrate all of:

1. deterministic/frozen rule before confirmatory inspection;
2. meaningful separation from appropriate simple/matched controls;
3. qualitatively stable behavior across more than one chronological block/regime;
4. no dependence on one magic parameter point;
5. transparent effective sample/concentration;
6. acceptable missingness/data semantics;
7. delay/cost robustness appropriate to the intended claim;
8. no post-hoc rescue of the same OOS window.

`VALIDATED_CANDIDATE` still does not mean permanent alpha. It means the mechanism has earned the next level of evidence.

## 18. What does not count as more evidence

The following do not create additional market regimes:

- bootstrapping the same month;
- Monte Carlo reshuffling of the same returns;
- synthetic price paths used as proof of alpha;
- counting overlapping 5m rows as independent observations;
- trying more indicators/thresholds until one passes;
- ML trained and evaluated on the same narrow regime.

These tools can be useful for diagnostics/uncertainty, but they cannot substitute for real out-of-time market evidence.

## 19. Research ledger requirement

Every confirmatory run and every material post-hoc hypothesis must be recorded in `docs/RESEARCH_LEDGER.md` or a versioned machine-readable successor.

Failed/null experiments remain part of the record.