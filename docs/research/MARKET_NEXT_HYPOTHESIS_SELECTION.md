# MARKET next-hypothesis selection from orthogonal regions

Date: 2026-09-21
Unit: `MARKET_NEXT_HYPOTHESIS_SELECTION_FROM_ORTHOGONAL_REGIONS`
Current main: `635d391a77a8311d5dfa53188d5d975bedfda7e1`

Selection and search-space design only. No hypothesis was preregistered, no
MARKET-07 was created, no scientific outcome was computed, and protected
2025/2026 were not opened.

```
REGION_SELECTED  = R-A / STRUCTURAL_REGIME_STATE_DETECTION
SELECTION_STATUS = REGION_SELECTED_NOT_HYPOTHESIS_CREATED
```

## Two corrections recorded before selection

### 1. Retraction — 2020–2021 is not a fresh surface

An earlier draft claimed 2020–2021 was "unconsumed" because MARKET-06 used
only 2022–2024. **That claim was false and is retracted.** Verified in
repository history:

- H01 preregistration: `Development / discovery | 2020-02-01 | 2025-01-01 | allowed`
- H02 dev summary: same window; its runner loads 2020–2024 only
- 21 documents reference that development window
- MARKET-01 `common_legal_period.start_inclusive = 2020-09-01`, era splits through 2024/2025

**`HISTORICAL_2020_2024_EXPOSURE_CLASS`**

| exposure | units | nature |
|---|---|---|
| adaptive discovery, outcome inspection *allowed* | H01, H02, further H/BATCH work | threshold/feature/horizon adaptation against observed outcomes |
| confirmatory consumption | MARKET-01, MARKET-02 | one-shot sealed |
| confirmatory consumption | MARKET-05, MARKET-06 | one-shot sealed |

2020–2024 is therefore a **historically exposed/adapted program research
surface**. It remains usable for adaptive exploration, mechanism
feasibility and implementation development, but **not** as fresh
independent confirmation. Any future confirmatory claim on this period must
explicitly account for prior exposure.

**Wording rule.** A chronological split inside 2020–2024 must be called
**"chronological held-out evaluation on historically exposed research
data"**. It must not be called out-of-sample, clean OOS, or independent
confirmation.

### 2. Correction — search-concentration overstatement

| unit | function | target |
|---|---|---|
| MARKET-01 | conditional relationship, event/episode | 60m `reversal_return` |
| MARKET-02 | conditional relationship, event/episode | 60m continuation |
| MARKET-03 | **external strategy reproduction** | author `Max drawdown` direction |
| MARKET-04 / 04H | **never executed** | blocked on observable provenance |
| MARKET-05 | incremental predictor | 24h direction-aligned adverse path |
| MARKET-06 | incremental predictor | 24h direction-aligned adverse path |

Withdrawn: *"prediction (all six)"* and *"six differently-named hypotheses
occupy roughly two distinct search positions"*. Neither survives a
per-unit mapping.

Defensible statement: **internal hypothesis *generation* was
overconcentrated in short-horizon conditional scalar prediction —
MARKET-01/02/05/06 plus earlier H/B2 work.** MARKET-03 and MARKET-04/04H
sit outside that concentration, for different reasons.

## Regions not selected

| region | orthogonality | why not selected now |
|---|---|---|
| R-B abstention / tail selection | MEDIUM-HIGH | needs a fresh evaluation surface; none exists outside protected 2025/2026 or forward data. Rescue risk MEDIUM-HIGH. |
| R-C cross-sectional | **highest in the set** | no multi-instrument panel (only CORE BTC, CORE ETH); no listing/delisting/survivorship reconstruction anywhere. Reconsider ahead of R-D/R-E if panel acquisition is funded. |
| R-D liquidity / market structure | HIGH | no trade-level or L2 data retained; historical book data has no defensible available-at semantics. Forward-only. |
| R-E execution cost | HIGH | same missing tier; only quote/depth proxies constructible, and a proxy must never be labelled realized execution cost. |
| R-F composed joint state | LOW | highest rescue and multiple-testing risk; shares R-B's fresh-surface problem. |

R-C, R-D and R-E may require **materially different null/comparator
structures** from R-A.

## R-A — scientific object

> Can one pre-specified, low-degrees-of-freedom, price-derived discrete
> state representation at a frozen time scale exhibit **chronological
> held-out transition/persistence structure, on historically exposed
> research data**, that cannot be explained by a frozen lower-order null
> model?

Exactly one state-construction class. No cluster shopping, no sweeping `k`,
no trying feature families and keeping the prettiest, no choosing
horizon/window after label inspection, no return/MAE/alpha target. A
positive state model is **not** itself an edge claim.

**A negative result closes** only the tested class of low-dimensional,
price-derived, *discrete* state representations at the frozen time scale
and construction procedure, and lowers priority for work depending on that
representation.

**A negative result does NOT close:** continuous conditioning (which is
what MARKET-01/02/05/06 actually used); other discrete-state
constructions; other time scales; cross-sectional structure; order-book /
liquidity regimes; latent states using information outside CORE BTC; or
"BTC regimes" generally.

## Surrogate / null requirement

The null must **preserve every lower-order structure the claim does not
intend to label as regime structure**, and may destroy only the structure
under test.

A null preserving only the unconditional marginal distribution and linear
autocorrelation/spectrum is **not automatically acceptable** when the
candidate representation uses volatility clustering, vol-of-vol,
realized-volatility term structure, path roughness or nonlinear temporal
dependence — such a null can mechanically destroy the very second-order
dependence under test and manufacture a guaranteed positive contrast.

The surrogate/null family must be chosen **outcome-blind**, never after
seeing label persistence.

A defensible lower-order null construction would be reusable methodological
infrastructure for future **price-path / state-detection** studies that ask
whether apparent state persistence exceeds lower-order temporal dependence.
R-C, R-D and R-E may require materially different null/comparator
structures.

## Why R-A was selected

- materially changes **function**, from scalar outcome prediction to state detection;
- does not rescue MARKET-05 or MARKET-06;
- feasible with existing point-in-time price data (`CORE_BTC_BINANCE_V0`);
- a negative result removes a real, explicitly bounded representation class;
- researcher degrees of freedom are **HIGH** and are therefore the primary blocker;
- selection remains **provisional** until a defensible null model and one
  low-DoF construction class can both be defined.

It was **not** selected because it is cheap or easy, nor because it is
likely to produce a positive result, and it does **not** eliminate
regime-conditioned research generally.

## Next unit

```
NEXT_UNIT = STRUCTURAL_REGIME_STATE_DETECTION_MECHANISM_CLASS_AND_NULL_MODEL_FEASIBILITY
```

It must **not** preregister MARKET-07. Its job is to:

1. identify candidate lower-order null families;
2. state exactly what each preserves and destroys;
3. determine whether any null permits a non-tautological test;
4. define at most **one** low-DoF state-construction class;
5. define an allowed chronological train/held-out structure while
   explicitly labelling 2020–2024 historically exposed;
6. **stop with `REGION_NOT_READY` if no defensible null exists.**

No label-persistence outcome was computed in this recording unit.
