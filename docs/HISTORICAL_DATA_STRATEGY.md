# Signalbot Historical Data Strategy

**Status:** ACTIVE

The research program must not let the shortest/highest-fidelity dataset define the history available to every hypothesis.

## 1. Principle: separate mechanism evidence from enrichment evidence

Use layered datasets.

### Tier A — CORE / long-history

Purpose: test whether a simple market mechanism exists at all.

Preferred fields:
- OHLCV / price structure;
- volume;
- taker-side flow where historical semantics are reliable;
- funding where reliable;
- OI only where timestamps/granularity are defensible.

Target: multi-year BTC history spanning materially different regimes. Prefer 2021–present where source coverage supports it; earlier history is welcome when semantically comparable.

### Tier B — RICH / shorter overlap

Purpose: test whether richer context adds incremental value to an already-promising CORE mechanism.

Potential fields:
- venue-specific OI;
- liquidations;
- cross-exchange agreement/divergence;
- richer derivatives context;
- live-equivalent raw feeds;
- future order-book/spot/vendor data only if a hypothesis justifies them.

A one-month RICH overlap is not used to claim the underlying mechanism is durable.

## 2. Avoid lowest-common-denominator history

Do not require every experiment to contain every source.

Bad design:

> price + taker + OI + funding + liquidation + all venues are mandatory, therefore the entire research history starts when the youngest source starts.

Preferred design:

1. validate price/core mechanism on long history;
2. validate OI increment on OI-capable history;
3. validate liquidation increment on liquidation-capable history;
4. validate cross-venue increment on comparable multi-venue history.

Each claim is scoped to the evidence actually available.

## 3. Evidence tiers by source/period

Every dataset manifest should classify source-period semantics, for example:

- `LIVE_EQUIVALENT`
- `HISTORICAL_COMPARABLE`
- `PARTIAL`
- `COARSE_GRANULARITY`
- `NON_COMPARABLE`
- `NOT_AVAILABLE`

Do not silently promote a partial/coarse feed to live-equivalent evidence.

## 4. Provider granularity

A provider observation may not gain temporal information when upsampled.

Example: if OI is observed every 5m, forward-filling to 1m does not make minute-level OI timing real.

Research features must preserve the provider's actual observation time/granularity and avoid deriving slopes/events at unsupported resolution.

## 5. Dataset manifest

Every materialized research dataset should have a versioned manifest containing at least:

- dataset ID/version;
- creation timestamp;
- code commit;
- symbol/market type;
- exchanges/sources;
- raw time range;
- per-source time range;
- source/evidence tier;
- known semantic changes;
- gap/missingness statistics;
- resampling/forward-fill rules;
- instrument metadata identity;
- calculation/version identity;
- checksum or immutable snapshot identity where practical.

A research result without enough identity to reproduce the exact population is weaker evidence.

## 6. No-lookahead requirements

For decision boundary `T`:

- only use observations available by `T` under the historical source semantics;
- respect publication/close timing;
- do not use a later corrected/current instrument state as though it existed at `T`;
- explicitly model coarse-source observation timestamps;
- fail closed when the as-of state is ambiguous for confirmatory research.

## 7. Missingness

Missing data are part of the evidence.

Track:
- missing bars/observations;
- outages;
- provider gaps;
- gaps by volatility/regime;
- incomplete future paths;
- candidate exclusions caused by missingness.

Do not fill unavailable metrics with zero. Do not report only the survivor population without the denominator.

## 8. Regime coverage

Calendar length alone is not enough.

The long-history dataset should be inspected for representation of:
- high/low volatility;
- sustained bull/bear trends;
- ranges/chop;
- liquidation/deleveraging shocks;
- squeeze/impulse periods;
- post-shock normalization.

Regime labels used for confirmatory gating must themselves be computed without lookahead.

## 9. Cross-asset extension

After BTC CORE is reproducible, add a small number of liquid markets (initially ETH/SOL are reasonable candidates) when useful for testing whether a mechanism is general.

Rules:
- report assets separately;
- do not treat simultaneous BTC/ETH/SOL rows as independent market regimes;
- do not add many symbols merely to manufacture sample size;
- scope claims honestly when a mechanism is BTC-specific.

## 10. Rich-data acquisition priority

Do not spend money or engineering time acquiring perfect historical liquidation/order-book feeds before a simpler CORE mechanism demonstrates evidence.

Priority order:

1. long, clean CORE history;
2. reproducibility/no-lookahead validation;
3. candidate mechanism discovery;
4. independent validation;
5. only then acquire/backfill expensive rich sources needed for a specific incremental-value hypothesis.

## 11. Live accumulation continues to matter

Even after historical expansion, retain ongoing live raw data because:

- public historical archives may have different semantics;
- some high-fidelity sources exist only live;
- forward shadow is independent evidence;
- future RICH overlap grows over time.

Live accumulation complements historical research; it does not replace it.

## 12. Initial deliverables for R1

When implementation work resumes for research purposes, produce:

1. `DATA_CAPABILITY_MATRIX` — source x venue x date range x granularity;
2. `CORE_BTC_MANIFEST` — first reproducible multi-year core dataset;
3. missingness/gap report;
4. provider-granularity audit;
5. deterministic materialization command/script;
6. small verification suite for no-lookahead/as-of semantics;
7. only after those pass, begin broad hypothesis discovery.
