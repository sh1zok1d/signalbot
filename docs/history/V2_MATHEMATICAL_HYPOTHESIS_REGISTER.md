# V2 Mathematical Hypothesis & Measurement-Risk Register

> Status: research-governance document for frozen V2-v0 hypotheses.
>
> This document does **not** change any V2-v0 trading formula, threshold, setup-family definition, lifecycle rule, `rules_version`, or runtime behavior. It records what the current model assumes about market behavior and measurement quality, which assumptions remain unproven, and which measurement-layer defects must be resolved before strong empirical claims are allowed.

## 0. Research-freeze rule

The presence of an unresolved mathematical hypothesis is **NOT authorization to modify the frozen V2-v0 rule**.

V2-v0 formulas/parameters remain unchanged unless at least one of the following is true:

1. a correctness, measurement, or statistical-validity defect would make the experiment itself invalid or materially misleading; or
2. the frozen hypothesis has completed the predeclared empirical evaluation path and a new, explicitly-versioned hypothesis is approved.

In particular, the following are forbidden responses to an unresolved hypothesis:

- tuning a threshold because it "looks too strict/loose";
- replacing a monotonic score with a preferred nonlinear shape before evidence;
- adding a filter after inspecting unfavorable outcomes;
- using a viewed OOS/holdout period to choose a new rule while still calling that period untouched OOS;
- changing `v2-rules-v0.2.0` merely because a modelling assumption is debatable.

A frozen hypothesis is allowed to fail. Simplification or removal after evidence is a valid research outcome.

## 1. Relationship to the empirical red-team plan

This register answers:

> **What does V2-v0 currently assume, and what can go wrong mathematically or statistically?**

`docs/V2_EMPIRICAL_RED_TEAM_PLAN.md` answers:

> **How are those assumptions falsified without turning the researcher into the optimizer?**

The two documents are complementary:

```text
V2_MATHEMATICAL_HYPOTHESIS_REGISTER
        ↓ defines claims / risks / invariants
V2_EMPIRICAL_RED_TEAM_PLAN
        ↓ defines event studies / controls / ablations / OOS protocol
Evidence
        ↓
KEEP / SIMPLIFY / KILL / NEW VERSION
```

No item marked `FREEZE_AND_TEST` below should trigger an implementation change before the relevant empirical test is run.

## 2. Classification vocabulary

| Class | Meaning | Default action |
|---|---|---|
| `CORRECTNESS_BUG` | implementation violates the frozen rule or no-lookahead/data identity | fix before evaluation |
| `STATISTICAL_VALIDITY_GAP` | measurement/readiness logic can overstate evidence quality | investigate; fix narrowly if confirmed |
| `MEASUREMENT_ROBUSTNESS_GAP` | input aggregation may become fragile in an allowed data state | adversarial + historical audit first |
| `MARKET_HYPOTHESIS` | coherent but unproven statement about future market behavior | freeze and test |
| `REDUNDANCY_RISK` | component may duplicate information already represented elsewhere | ablation / matched controls |
| `MONOTONICITY_HYPOTHESIS` | larger score is assumed to mean stronger/better setup | ordering/reliability test |
| `NO_ACTION_YET` | issue is recorded but does not justify a model change | preserve V2-v0 |

## 3. Register summary

| ID | Component | Claim / risk | Class | Priority | Action now |
|---|---|---|---|---:|---|
| `MATH-001` | Percentile maturity / readiness | calendar span may admit statistically sparse distributions as usable V2 evidence | `STATISTICAL_VALIDITY_GAP` | P0 | investigate/fix-before-headline-evidence; issue #51 |
| `MATH-002` | 2-of-3 consensus | median loses 3-point robustness when only two venues contribute | `MEASUREMENT_ROBUSTNESS_GAP` | P0 | adversarial + historical audit; issue #52 |
| `MATH-003` | `normalized_evidence` | full signed percentile extremity is useful trend/bias evidence | `MARKET_HYPOTHESIS` | P1 | `FREEZE_AND_TEST` |
| `MATH-004` | `TREND_PULLBACK` | shallower current retracement is a stronger setup; current depth is sufficient structural summary | `MONOTONICITY_HYPOTHESIS` | P1 | `FREEZE_AND_TEST` |
| `MATH-005` | `COMPRESSION_BREAKOUT` | stronger/longer compression and selected historical run remain relevant to later breakout quality | `MARKET_HYPOTHESIS` | P1 | `FREEZE_AND_TEST` |
| `MATH-006` | OI confirmation | rising OI supports continuation of either price direction; falling OI opposes it | `MARKET_HYPOTHESIS` | P1 | `FREEZE_AND_TEST` / interaction ablation |
| `MATH-007` | `CONFIRMED_BREAKOUT.setup_strength` | larger breakout overshoot relative to protection buffer means stronger setup | `MONOTONICITY_HYPOTHESIS` | P1 | `FREEZE_AND_TEST` |
| `MATH-008` | Multi-timeframe chain | 4h/1h/15m/5m roles provide incremental structure rather than duplicated latent momentum | `REDUNDANCY_RISK` | P1 | ablation / matched baselines |
| `MATH-009` | Cross-exchange agreement | venue agreement adds useful robustness/information despite strongly correlated BTC venues | `REDUNDANCY_RISK` | P1 | contributor-count + venue ablation |

## 4. Detailed findings

### MATH-001 — Percentile maturity vs statistical materialization

**Status:** `INVESTIGATE / FIX-BEFORE-HEADLINE-EVIDENCE`

**Issue:** #51 — `research: audit percentile maturity vs V2 activation readiness`

Current Stage 2 percentile confidence tiers are span-based. Once at least two non-null samples exist, `analytics/percentile_engine/compute.py` derives the tier from calendar span. The test suite deliberately freezes a sparse vector where only two historical samples spanning roughly 30 days produce `confidence_tier = "mature"`.

V2 `activation_readiness.py`, however, treats `confidence_tier >= MIN_PCTL_TIER` as sufficient materialization and does not independently require an observation count/density invariant.

Therefore the implication

```text
confidence_tier >= building
    => statistically well-materialized percentile distribution
```

is not currently guaranteed.

**Why this is different from a trading hypothesis:** this can affect the trustworthiness of the measuring instrument itself. A percentile rank from a tiny sample has coarse resolution and can be admitted as usable evidence without proving that the market hypothesis deserves that confidence.

**Do not do yet:** invent an arbitrary minimum sample count or alter trading thresholds.

**Required resolution:** determine the narrow semantic fix across Stage 2 maturity metadata, V2 readiness, and/or research eligibility, with adversarial regression tests and explicit versioning/provenance implications.

---

### MATH-002 — `2/3` consensus robustness

**Status:** `INVESTIGATE`; no production-semantic change authorized.

**Issue:** #52 — `research: red-team 2-of-3 consensus robustness`

Stage 2 uses ordinary medians for several cross-exchange aggregates. With three venues:

```text
[1, 1, 100] -> median = 1
```

With two venues:

```text
[1, 100] -> median = 50.5
```

The usual one-outlier robustness intuition of a three-point median therefore disappears in the allowed `2/3` state. Coverage/agreement/dispersion confidence can still pass when both remaining venues share a direction.

**Hypothesis to test:** `2/3` may be operationally valuable as availability/fault tolerance while being statistically less robust than `3/3`.

**Required evidence:** adversarial vectors plus historical contributor-count stratification through the full chain:

```text
venue values
 -> consensus aggregate
 -> agreement / dispersion / confidence
 -> percentile rank
 -> V2 evidence
```

**Do not do yet:** remove partial consensus, change minimum exchange coverage, or substitute a new estimator based on inspected OOS performance.

---

### MATH-003 — Signed percentile extremity as directional evidence

**Status:** `FREEZE_AND_TEST`

The frozen `normalized_evidence` primitive preserves raw sign and maps percentile rank to evidence magnitude:

```text
v > 0 -> max(0, 2p - 1)
v < 0 -> -max(0, 1 - 2p)
v = 0 -> 0
```

The percentile `p` is computed from the full signed historical distribution, not a sign-conditioned distribution. Therefore a modest positive move can rank highly after a strongly negative historical window, and vice versa.

This is internally coherent and matches the current contract. It is **not a correctness bug**.

**Unproven claim:** extremity in the full recent signed distribution contains useful incremental information about future continuation/context beyond simpler momentum/price-structure baselines.

**Test:** event-study separation, parameter-neighborhood stability, regime stratification, and price-only baselines.

---

### MATH-004 — TREND_PULLBACK depth and path shape

**Status:** `FREEZE_AND_TEST`

Formation uses current retracement relative to the selected trend-leg extreme and `RANGE_PROXY_pct`, with the valid band `[0.5R, 3.0R]`. `setup_strength` is monotonic: shallower current retracement inside the allowed band scores higher.

A path can theoretically experience a much deeper interim decline and later recover near the anchor while still having a shallow **current** retracement. The detector separately stores `pullback_extreme`, but current qualification/strength does not use a path-shape penalty.

This is a coherent frozen setup definition, not an implementation mismatch.

**Unproven claims:**

1. shallower current retracement monotonically corresponds to stronger continuation quality;
2. current retracement is a sufficient summary even when max path retracement was materially deeper.

**Required diagnostics:**

- `current_retracement / R`;
- `max_path_retracement / R`;
- anchor age;
- recovery fraction from deepest pullback;
- future MFE/MAE/utility conditional on these variables.

Do not replace the current score with a bell curve or new path penalty before evidence.

---

### MATH-005 — Compression strength, duration, and recency

**Status:** `FREEZE_AND_TEST`

`COMPRESSION_BREAKOUT` identifies maximal qualifying runs inside a fixed 16x15m lookback, requires at least six compressed buckets, and uses the selected run's compression-score mean as setup strength. The selected run need not end at the current `B15`; an earlier qualifying run can remain the structural source for a later fresh breakout.

**Unproven claims:**

- higher mean compression score implies better breakout quality;
- longer qualifying compression is beneficial rather than exhausted/stale;
- a compression range remains predictive after a non-zero delay from `compression_end` to breakout.

**Required diagnostics:**

```text
compression mean
run length
T_breakout - compression_end
range width / volatility regime
future MFE/MAE/false-break rate
```

No recency gate or alternate run-selection rule should be introduced before this study.

---

### MATH-006 — Symmetric OI confirmation

**Status:** `FREEZE_AND_TEST`

Current OI semantics deliberately do not choose LONG/SHORT. Rising OI confirms an already-established price anchor direction; falling OI opposes it.

This encodes a participation/continuation hypothesis:

```text
price up   + OI up   -> confirmation
price down + OI up   -> confirmation
price up   + OI down -> opposition
price down + OI down -> opposition
```

**Unproven claim:** this symmetry is useful for future continuation across both directions.

Potentially distinct market mechanisms such as short covering (`price up / OI down`) and long liquidation (`price down / OI down`) may have different future behavior.

**Test:** OI ablation plus price-direction x OI-sign interaction study. Do not rewrite OI semantics before that result.

---

### MATH-007 — CONFIRMED_BREAKOUT overshoot monotonicity

**Status:** `FREEZE_AND_TEST`

Current setup strength is:

```text
min(1, breakout_distance_beyond_level / protection_buffer)
```

Thus a larger fresh-close overshoot scores as stronger until saturation.

This can coexist with lower entry feasibility: a strong overshoot can already place the observed breakout close beyond the preferred entry zone. Stage 7 feasibility is a distinct downstream concept, so this is not an internal contradiction.

**Unproven claim:** greater overshoot monotonically improves economically useful setup quality after realistic delay/costs.

**Test:** setup-strength bins vs entry feasibility, post-delay MFE, MAE, and cost-adjusted utility.

---

### MATH-008 — Multi-timeframe latent-information duplication

**Status:** `FREEZE_AND_ABLATE`

The Product Contract correctly assigns distinct semantic responsibilities to 4h regime, 1h bias, 15m formation, and 5m trigger and explicitly forbids treating them as four independent votes.

Statistically, however, they can still be transformations of the same latent price impulse.

**Unproven claim:** adding each timeframe layer produces incremental predictive separation rather than only better narrative/structure.

**Test:** controlled ablations and matched simple baselines. Compare, where semantics permit:

- price-only lower-TF structure;
- +4h regime;
- +1h bias;
- full formation + trigger chain.

No timeframe layer should be removed merely because correlation is visually obvious; removal requires empirical non-contribution.

---

### MATH-009 — Cross-exchange agreement as evidence

**Status:** `FREEZE_AND_ABLATE`

Binance, Bybit, and OKX observe the same BTC market and are strongly economically coupled. Agreement can improve robustness against venue-specific defects, but `3/3 agrees` must not be psychologically interpreted as three independent experiments.

**Unproven claim:** cross-exchange agreement contributes predictive information beyond a robust reference-venue/median price structure.

**Test:** contributor-count stratification and venue-set ablation under identical decision timing/cost semantics.

This item is distinct from `MATH-002`: `MATH-002` is about measurement robustness when only two venues contribute; `MATH-009` is about incremental information when multiple correlated venues agree.

## 5. Research execution rules

For every `FREEZE_AND_TEST` item:

1. State the primary metric and expected direction before opening the target result.
2. Use the baselines, controls, chronological blocks, and denominator discipline from `V2_EMPIRICAL_RED_TEAM_PLAN.md`.
3. Record the exact `rules_version`, calculation/data identity, delay/cost assumptions, and data-equivalence tier.
4. Treat repeated 5m observations inside one episode as repeated measurements, not independent samples.
5. If an OOS result causes a model change, that OOS period is consumed and becomes development evidence for the new version.
6. A null or negative result is allowed to kill a component or family.
7. Do not promote a score to calibrated probability unless calibration is separately demonstrated.

## 6. Current action boundary

As of this register's creation:

### Allowed now

- investigate `MATH-001` and `MATH-002` at the measurement/statistical-validity layer;
- add adversarial tests/research reports that do not alter V2-v0 market semantics;
- implement coherent replay/event-study infrastructure;
- collect diagnostics required by `MATH-003` through `MATH-009`;
- preserve V2-v0 unchanged for falsification.

### Not allowed solely because of this register

- change `REGIME_TREND_THRESHOLD`, `BIAS_THRESHOLD`, compression threshold, pullback multipliers, lookbacks, horizons, confirmation ages, protection-buffer multiplier, setup-strength formulas, or agreement thresholds;
- add new external feeds, ML, adaptive thresholds, or a fourth setup family;
- bump `rules_version` to encode an untested preference;
- describe any current `model_confidence`/`setup_strength` value as a calibrated win probability.

## 7. Decision log template

When an item moves from hypothesis to evidence-backed decision, append a short record:

```text
Hypothesis ID:
Date:
Frozen version evaluated:
Data / calculation identity:
Predeclared primary metric:
Development window:
Validation/OOS window:
Baselines / negative controls:
Result: + / 0 / - / inconclusive
Decision: KEEP / SIMPLIFY / KILL / NEW VERSION
OOS consumed by model change?: yes/no
Follow-up issue / PR:
```

This keeps model evolution auditable and prevents a later implementation PR from silently converting exploratory intuition into production truth.
