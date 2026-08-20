# V2 Consensus Robustness — Historical Audit (MATH-002B / issue #52)

**Honest scope (tech-lead review round 1, finding 5): this PR is "MATH-002
deterministic completion + historical research harness" — it is NOT "MATH-002
end-to-end". Issue #52 / MATH-002B remains open and incomplete.**

Status: **DATA_ACCESS_BLOCKED for the historical study (§B). MATH-002A deterministic coverage repair (§A) is COMPLETE. §B's harness is PARTIAL** — the controlled `FULL3 -> BB/BO/BYO` recomputation (task §8's own designated PRIMARY measurement) and the `BINANCE_ONLY_RESEARCH_BASELINE` diagnostic are implemented and unit-tested; the natural (non-controlled) 2/3 prevalence study, percentile-variant series, regime/bias/Stage-5 replay, and extreme-example extraction are explicitly NOT implemented (§B.3, §B.8) — deliberately, rather than building unvalidated infrastructure with no real data to check it against.

This document is the required MATH-002B artifact (issue #52, following the
merged MATH-002A characterization in PR #56). It has two parts, matching the
task's own split:

- **§A — deterministic follow-up.** Repairs a real test-coverage gap in the
  merged `tests/analytics/test_consensus_robustness_math002.py` and makes
  the current V2 quality-gate characterization exact. Complete, tested,
  merged into this branch.
- **§B — historical study.** Was to determine real historical reachability,
  frequency, magnitude, and downstream effect of the 3/3 -> 2/3 robustness
  loss characterized synthetically in §A / PR #56. **Blocked**: no reachable
  historical PostgreSQL instance exists in this environment (see §B.1). A
  reproducible, read-only harness is committed and unit-tested against
  synthetic fixtures, ready to run the moment real historical data is
  reachable — but per the task's explicit instruction, no historical numbers
  are reported, because none were produced. Synthetic/unit-test results
  below are labeled as such and must never be read as historical evidence.

---

## A. MATH-002A deterministic follow-up (complete)

### A.1 What PR #56 got right

PR #56's numerical characterization is **correct** for the pair it actually
tested. `[1, 100] -> median 50.5, MAD 49.5, agreement 1.0, confidence
~73.433`, the `[1,1,100]` 3/3 control, the opposite-sign agreement-floor
failure, and the two-point robust-z symmetry (`ROBUST_Z_SCALE ~= 0.67449`,
below `robust_z_threshold=3.5`) are all reproduced identically in this
branch's expanded test matrix. **PR #56 is not reverted.**

### A.2 The coverage gap PR #56 had

`tests/analytics/test_consensus_robustness_math002.py`'s helper assigned
values via `zip(EXCHANGES, values, ...)` with
`EXCHANGES = ("binance", "bybit", "okx")`. Every N=2 vector therefore
always meant **Binance+Bybit, OKX excluded** — `Binance+OKX` and
`Bybit+OKX` were never exercised at all. This was a test/research coverage
gap, not a production correctness bug (`compute_consensus_features()`
itself has no venue-order dependency — see §A.4).

### A.3 The fix

`tests/analytics/test_consensus_robustness_math002.py` now:

- exposes `PAIRS = {"BB": (binance,bybit), "BO": (binance,okx), "BYO": (bybit,okx)}`;
- runs every required N=2 adversarial vector (`[1,100]`, `[-1,-100]`,
  `[0.1,10]`, `[-0.1,-10]`, `[1,-100]`, `[-1,100]`, `[1,1]`, `[-1,-1]`) under
  **all three** pairs, for both `price_structure` and `oi`, verifying
  contributing/excluded venue identity, coverage `2/3`, median, MAD,
  direction agreement, family `data_confidence`, outlier reporting, and
  `is_partial_consensus` for each;
- keeps the `[1,1,100]` 3/3 control unchanged;
- adds two dedicated symmetry tests
  (`test_math002_median_mad_are_identical_across_all_three_pairs_for_same_values`,
  `test_math002_swapping_which_venue_holds_which_value_does_not_change_median_mad`)
  proving the pure median/MAD math does not depend on venue label or venue
  ordinal position. **This proves the implementation's math is symmetric
  with respect to venue labels — it does NOT prove the three real exchanges
  are statistically equivalent data sources.** That is a historical-data
  question and belongs to §B, which is blocked.

### A.4 Exact current V2 quality-gate characterization

PR #56 imported only `REGIME_MIN_CONFIDENCE`/`REGIME_MIN_COVERAGE`/
`REGIME_MIN_AGREEMENT` and phrased its assertions more broadly than what it
actually checked. This branch adds, as separately-named, separately-checked
constants (never assumed equal to the regime floor merely because they
currently share the same numeric value):

| Layer | Coverage floor | Confidence floor | Agreement floor |
|---|---|---|---|
| 4h regime | `REGIME_MIN_COVERAGE` (2/3) | `REGIME_MIN_CONFIDENCE` (50.0) | `REGIME_MIN_AGREEMENT` (2/3) |
| 1h bias | `BIAS_MIN_COVERAGE` (2/3) | `BIAS_MIN_CONFIDENCE` (50.0) | `BIAS_MIN_AGREEMENT` (2/3) |
| Stage-5 shared setup | `SETUP_MIN_COVERAGE` (2/3) | `SETUP_MIN_CONFIDENCE` (50.0) | *(none of its own — see below)* |
| `COMPRESSION_BREAKOUT` | — | — | `BREAKOUT_MIN_AGREEMENT` (2/3) |

`trend_pullback.py` and `confirmed_breakout.py` were inspected directly and
declare **no** agreement constant of their own (checked, not assumed).

`test_math002_named_quality_constants_are_not_assumed_equal_they_are_checked`
records the current numeric coincidence explicitly, so a future PR that
diverges one floor from the others is caught by a failing named test, not
silently masked by an assumption baked into the other tests.

**Explicitly NOT claimed:** passing these row-level quality floors does
**not** mean a full Stage-5 setup would qualify — that requires the
detector's own structural conditions (fresh crossing, compression run,
retracement zone, taker-flow sign, etc.), none of which this
characterization touches.

### A.5 Frozen synthetic conclusion (unchanged from PR #56, now proven for all 3 pairs)

```text
3/3  [1,1,100]      -> median=1, MAD=0, agreement=1, extreme flagged via MAD_ZERO_NONMEDIAN
2/3  [1,100] (any pair) -> median=50.5, MAD=49.5, dispersion~=0.505, agreement=1, confidence~=73.4333
```

For any unequal 2-point pair, both observations are symmetric around the
midpoint median at robust-z magnitude `ROBUST_Z_SCALE ~= 0.67448975`; under
the frozen `robust_z_threshold=3.5`, neither point is ever identified as the
unique outlier by this mechanism. Opposite-sign pairs drop agreement to
`0.5` and fail every one of the three named agreement floors above.

Classification (unchanged): **SYNTHETICALLY CONFIRMED
MEASUREMENT_ROBUSTNESS_GAP.** No production fix implemented here.

---

## B. MATH-002B historical study

### B.1 Data access

- **Source attempted:** the project's existing PostgreSQL connection
  convention (`common.config.Config.load()` -> `load_secrets(cfg).postgres_dsn`,
  the same path `main.py`/`runtime/shadow_cli.py` use), pointed at
  `POSTGRES_HOST`/`PORT`/`USER`/`PASSWORD`/`DB` from `.env` (or an explicit
  `POSTGRES_DSN` override).
- **Result:** `DATA_ACCESS_BLOCKED`. This environment has no `.env` (only
  `.env.example`), `pg_isready` reports no listener on `127.0.0.1:5432`,
  `psql -h localhost` reports connection refused, and no `docker`/database
  container is running. There is no historical Stage 2 database reachable
  from this session.
- **Read-only guarantee (for when a real instance IS available):** every
  query in `scripts/research/math002b_consensus_robustness.py` is a
  `SELECT`; every DB session opens an explicit `READ ONLY` transaction
  (`conn.transaction(readonly=True)`); the script never calls `INSERT`/
  `UPDATE`/`DELETE`/any DDL/migration function; `--check-access` performs
  only `SELECT 1` inside a read-only transaction and touches nothing else.
- Per the task's explicit instruction: **no historical numbers are
  reported below.** They are not invented, approximated, or backfilled
  from synthetic data. Sections B.2–B.10 record the PREDECLARED methodology
  (written and reviewable before any real number exists) and the harness's
  own unit-test results (which characterize the HARNESS, not history).

### B.2 Actual historical support matrix

**Not determined** — requires the blocked database access (`exchange_feature_vectors`
row counts, date ranges, and per-venue/per-family completeness cannot be
read from documentation alone; `docs/STAGE2_DATA_AUDIT.md`/`STAGE2_CLARIFICATIONS.md`
§23.1/§23.2a describe DESIGN-TIME historical coverage expectations
(e.g. OI: binance ~29d23h, bybit 30d, OKX live-only per that document), but
this audit will not assert a live database's actual row counts without
reading them). A future run with real access must populate, per
`(symbol, market_type, timeframe, family)`:

- exact date range;
- available exchanges;
- complete 3/3 bucket count;
- 2/3 bucket count (stratified by omitted venue and by reason — missing
  data / gap / stale / unusable / feed absence / structural unsupported,
  never mixed together);
- structural limitations (e.g. if OKX genuinely has no historical OI feed
  for the queried window, that is `STRUCTURAL_UNSUPPORTED`, not an
  "outage").

### B.3 Predeclared methodology (§11 of the task, written BEFORE any historical number exists)

**Primary measurement (§8):** for every bucket where `exchange_feature_vectors`
has all 3 canonical venues with valid, non-null required fields for a family
(`price_structure`: `price_move_pct`, `range_width_pct`, `close_price`,
`is_usable=true`; `oi`: `oi_change_pct`, no usability gate — see
`analytics.feature_engine.consensus._USABLE_GATED`), recompute via the REAL
`compute_consensus_features()`:

```text
FULL3 = Binance + Bybit + OKX          (minimum_exchange_coverage=2, unchanged)
BB    = Binance + Bybit,  omit OKX     (minimum_exchange_coverage=2, unchanged)
BO    = Binance + OKX,    omit Bybit   (minimum_exchange_coverage=2, unchanged)
BYO   = Bybit + OKX,      omit Binance (minimum_exchange_coverage=2, unchanged)
```

`BINANCE_ONLY_RESEARCH_BASELINE` is a SEPARATE, clearly-labeled diagnostic
request with `minimum_exchange_coverage=1` — used ONLY to see what a
single-venue reference would have shown, **never** presented as, or
substituted for, current `2/3` production behavior (task §8 explicit
prohibition). **Amendment (tech-lead review round 1, finding 5): this is
now actually computed and reported** by
`compute_binance_only_diagnostic()`, not merely imported/labeled as an
earlier revision of this harness left it.

**Amendment (tech-lead review round 1, findings 2/3/4): request
construction now reuses production semantics exactly**, not a hand-rolled
approximation:

- per-family exclusion facts for every PRESENT venue are derived via the
  SAME `analytics.feature_engine.bucket_coordinator._derive_family_exclusions()`
  production uses — a venue whose row is guaranteed valid for the TARGET
  family (the price/OI discovery SQL below only guarantees THAT family's
  own fields) can legitimately have `NULL`s in a non-target family, and is
  now excluded from exactly those families honestly, rather than either
  fabricated or left to make `compute_consensus_features()`'s own
  validation fail before the target family is ever reached;
- `config_hash`/`config_version`/`feature_schema_version`/
  `calculation_version`/confidence weights/`robust_z_threshold`/
  `minimum_exchange_coverage` for the FULL3/BB/BO/BYO path all come from
  the real `analytics.feature_engine.consensus_input_adapter.
  build_consensus_feature_request()` against a resolved `Stage2Config` —
  never independently hardcoded. If a historical row's stored
  `calculation_version` cannot be reproduced by the currently-resolved
  config, the run raises `Math002BCalculationVersionUnsupported`
  explicitly rather than silently mixing identities;
- exact-3/3 bucket discovery and per-bucket row fetch SQL are restricted
  explicitly to `exchange IN ('binance','bybit','okx')` — `HAVING
  COUNT(DISTINCT exchange) = 3` alone could otherwise admit any three
  exchange names, and `complete_3of3_bucket_count` now counts only buckets
  actually analyzed as canonical Binance+Bybit+OKX.

**Secondary measurement (§9):** naturally-degraded 2/3 buckets, stratified
by family / timeframe / missing venue / date period / reason. Reconstructing
a missing venue's counterfactual value is only attempted where it is
recoverable from ALREADY-STORED historical data with exact as-of semantics
(e.g. the venue's own later-arriving row for the same bucket, if the gap
was transient); otherwise the missing observation is left missing, never
invented.

**Predeclared metrics (§11-§12)**, implemented in
`scripts/research/math002b_lib.py` and exercised end-to-end (on synthetic
fixtures) by `compare_bucket()`/`_summarize_study()` in
`scripts/research/math002b_consensus_robustness.py`:

- complete 3/3 bucket count; natural 2/3 bucket count/rate; counts by
  omitted/missing venue;
- absolute aggregate delta (always computed); relative aggregate delta
  (computed ONLY when `|FULL3| ` is not near-zero — `math.isclose(...,
  abs_tol=1e-9)` — otherwise `None`, never an unstable/fabricated
  percentage);
- sign flip rate;
- agreement delta (kept as a SEPARATE diagnostic, never folded into the
  family-quality gate below -- a passing gate does not by itself mean a
  regime/bias/setup would "qualify"); family-confidence delta; outlier-report
  flip rate;
- family-quality-gate flip rate: the GENERIC §6.3a per-family
  coverage/confidence gate (`analytics.forecasting_v2.family_quality.
  FAMILY_MIN_COVERAGE`/`FAMILY_MIN_CONFIDENCE`), used identically across
  every timeframe/family this harness studies. **Amendment (tech-lead
  review round 2):** an earlier version of this harness sourced this check
  from `regime_4h.REGIME_MIN_COVERAGE`/`REGIME_MIN_CONFIDENCE` instead --
  the 4h-regime-specific floors from §A.4. The two constant pairs are
  numerically equal today (2/3, 50.0) but are owned by different consumers;
  conflating them would misrepresent a generic per-family diagnostic as a
  4h-regime-specific one. The harness now imports `FAMILY_MIN_COVERAGE`/
  `FAMILY_MIN_CONFIDENCE` from `analytics.forecasting_v2.family_quality`
  directly, and `PairComparison`'s fields/JSON output are named
  `full3_family_quality_gate_pass`/`pair_family_quality_gate_pass`/
  `family_quality_gate_flip`/`family_quality_gate_flip_rate` so the metric
  cannot be mistaken for a complete V2 regime/bias/setup decision gate. See
  `tests/analytics/test_math002b_consensus_robustness_script.py::
  test_family_quality_gate_sources_from_family_quality_module_not_regime`
  for the regression proving semantic sourcing (not numeric coincidence);
- distribution summaries: count/median/p75/p90/p95/p99 (p99 withheld below
  n=100, never presented from an inadequate sample)/max.
- No `"bad distortion > X%"` threshold is defined anywhere in the harness —
  none may be invented after seeing results (task §11 explicit prohibition).

**Percentile/evidence/regime/bias/Stage-5 layers (§14-§17): designed, NOT
implemented in this PR.** Reason, stated explicitly rather than silently
skipped: building a percentile-variant series recompute (per-variant
chronological history, no lookahead, respecting the merged MATH-001
`sample_size`/`sample_window_start`/`sample_window_end`/`confidence_tier`
semantics) or a regime/bias/Stage-5 replay layer with zero real historical
data to validate it against would be exactly the "fake infrastructure
merely to produce a number" the task explicitly forbids (§17). The §8
controlled-pair study is this task's own designated PRIMARY measurement and
is the layer actually built and unit-tested. If/when real historical access
exists, extending `scripts/research/math002b_consensus_robustness.py` to
those layers is the natural next step — not attempted here.

### B.4 Controlled FULL3 -> BB/BO/BYO results

**Not available (DATA_ACCESS_BLOCKED).** See B.9 for what the harness's own
unit tests (synthetic fixtures only) confirm about its correctness.

### B.5 Natural 2/3 prevalence

**Not available (DATA_ACCESS_BLOCKED).**

### B.6 Outlier / dispersion results

**Not available historically.** The synthetic §A characterization already
answers the task's §13 question in the deterministic regime: current
MAD/outlier reporting does **not** protect a 2-point consensus from one
distorted venue — a same-sign 2/3 pair can move the aggregate by a large
absolute amount while reporting **zero** outliers (both points are
symmetric around the midpoint by construction, robust-z magnitude fixed at
`ROBUST_Z_SCALE ~= 0.674`, always under the frozen threshold). Whether this
is *frequent* or *material* historically is exactly what B.4/B.6 would
answer with real data — blocked.

### B.7 Quality-gate results

**Not available historically.** Synthetically (§A.4): same-sign 2/3 passes
every current named floor (regime/bias/setup coverage+confidence,
regime/bias/breakout agreement); opposite-sign passes coverage+confidence
but fails every named agreement floor. Historical flip *rate* is undetermined.

### B.8 Percentile / evidence, regime, bias, Stage-5 setup flips

**Not implemented this PR** — see B.3's explicit reasoning.

### B.9 Harness self-verification (NOT historical evidence)

`tests/analytics/test_math002b_research_helpers.py` (pure `math002b_lib.py`
unit tests) and
`tests/analytics/test_math002b_consensus_robustness_script.py` (synthetic
`ExchangeFeatureVector` fixtures, stamped with the REAL identity
`config/stage2.yaml` resolves, run through the harness's real
`compare_bucket()`/`compute_binance_only_diagnostic()`/`_summarize_study()`)
confirm the harness itself is correct: it reproduces the exact MATH-002A
`[1,1,100]`/`[1,100]` numbers via its own independent recomputation path,
correctly detects sign flips, correctly reports a POSITIVE
`absolute_median_delta` even when the pair median drops relative to FULL3,
correctly recomputes a target family when a present venue has legitimate
non-target-family `NULL`s, correctly raises
`Math002BCalculationVersionUnsupported` for an EFV whose stored identity
doesn't match what the resolved config derives, and its distribution/delta
helpers handle the near-zero-denominator and small-sample-p99 edge cases
safely. Writing this second, independent test surface caught two real
harness bugs before either could run against real data:

1. (original round) `_build_request()` hardcoded a synthetic `code_version`
   instead of reusing the fetched row's own, which would have made every
   real historical `compute_consensus_features()` call raise
   `ConsensusError: EFV identity mismatch` immediately.
2. (tech-lead review round 1) `absolute_median_delta` returned the raw
   SIGNED difference under an "absolute" name (finding 1); request
   construction excluded only the deliberately-omitted variant venue and
   never derived honest per-family exclusions for the two remaining
   present venues, so a present-but-non-target-family-NULL row would have
   made `compute_consensus_features()` raise before reaching the target
   family (finding 2); `_WEIGHTS`/`_ROBUST_Z_THRESHOLD` were independently
   hardcoded rather than coupled to the resolved config identity (finding
   3); exact-3/3 discovery SQL was not restricted to the three canonical
   study venues (finding 4). All four fixed in this amendment; see this
   module's own docstring for the exact production functions now reused
   (`build_consensus_feature_request()`,
   `bucket_coordinator._derive_family_exclusions()`).

### B.10 Extreme historical examples

**Not available (DATA_ACCESS_BLOCKED).**

### B.11 Binance-only research baseline

**Historical numbers: not available (DATA_ACCESS_BLOCKED). Implementation:
COMPLETE as of this amendment.** `compute_binance_only_diagnostic()`
actually computes this SEPARATE `minimum_exchange_coverage=1` diagnostic
request (reusing the resolved config's real confidence weights/
`robust_z_threshold`, never the production `minimum_exchange_coverage=2`
path) and `_summarize_study()` reports it under
`binance_only_research_baseline` with `implemented: true` and an explicit
`RESEARCH ONLY` note — exercised end-to-end by
`test_compute_binance_only_diagnostic_is_actually_computed` against
synthetic fixtures; never yet against real data.

---

## C. Classification

Per the task, classification A (`NO_MATERIAL_PRACTICAL_GAP`), B
(`REPORT_STRATIFICATION_REQUIRED`), or C
(`MEASUREMENT_REMEDY_REQUIRED_BEFORE_HEADLINE_EVALUATION`) is chosen
**after historical analysis**. No historical analysis was possible in this
environment.

**This audit does not assign A, B, or C.** Defaulting to A would silently
treat "we could not check" as "we checked and it's fine" — exactly the
kind of unfounded claim the task instructs against. The honest state is:

> Synthetic characterization (§A, MATH-002A) is CONFIRMED. Real historical
> reachability/frequency/magnitude/downstream-effect (§B, MATH-002B) is
> **DATA_ACCESS_BLOCKED** and remains an open question. issue #52 should
> stay open until a real historical run (using the harness committed here)
> produces the numbers needed to choose A, B, or C.

No versioning consequences are discussed because no remedy is proposed —
none of A/B/C was reached, and the task explicitly forbids implementing a
remedy in this PR regardless.

---

## D. Non-changes (explicit)

- `analytics/feature_engine/consensus.py` behavior: unchanged.
- `minimum_exchange_coverage` (production value, `2`): unchanged. The
  harness's `BINANCE_ONLY_RESEARCH_BASELINE` uses a separate,
  clearly-labeled `minimum_exchange_coverage=1` request that is never
  presented as production behavior.
- Confidence weights, `robust_z_threshold`, outlier filtering, consensus
  estimator, percentile formulas/windows, `MIN_PCTL_TIER`, `REGIME_*`,
  `BIAS_*`, setup thresholds/formulas, `rules_version`,
  `config/v2.yaml enabled`: all unchanged.
- No exchange added. No CoinGlass/external feed added. No Stage 6 built.
  No deploy performed.
