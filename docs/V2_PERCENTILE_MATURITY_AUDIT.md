# V2 Percentile Maturity Audit — MATH-001 / issue #51

Status: **PARTIALLY CONFIRMED** — documentation/semantic mismatch is confirmed; a real future statistical-validity risk is confirmed, but no current production percentile-computation path exists on `main`, and the frozen Stage 2.1 contract deliberately defines `confidence_tier` as calendar-span maturity rather than statistical density. Therefore this audit does **not** invent a new row-count/density threshold and does **not** change V2-v0 market rules.

## 1. Finding

The original audit concern had two parts:

1. `confidence_tier >= MIN_PCTL_TIER` can be reached by an extremely sparse historical distribution; and
2. V2 readiness/evidence wording treated that tier as if it implied sufficiently materialized statistical history.

Part 1 is **confirmed by contract and implementation**. `STAGE2_SPEC.md` §12.6 explicitly states that tier is span-based, not row-count-based, and that row-count gating is a deferred future revision. Once `sample_size >= 2`, the age of the oldest included non-NULL sample relative to the current bucket determines the tier.

Part 2 is **confirmed as a semantic/documentation mismatch**. `activation_readiness.py` and the V2 correctness contract used wording stronger than the Stage 2 percentile contract. The real readiness/evidence implementation gates on `confidence_tier`, `value`, and `percentile_rank`; it does not independently prove sample density.

The stronger claim must therefore be removed. Reaching `building` means calendar maturity has reached the frozen span floor; it does **not** mean a statistically dense distribution exists.

## 2. Production reachability

Current `main` has the pure percentile core, storage schema/readers/writers, and downstream V2 consumers, but **no production percentile-computation orchestrator constructs `PercentileRequest` and materializes `percentile_snapshots` for live V2 decision use today**. V2 also remains disabled.

Therefore an automatically-produced sparse percentile row is **not currently live-production reachable through a completed runtime path**.

However, the consumer semantics are real: if such a valid snapshot exists (for example in a future orchestrator/replay or a test fixture), `normalized_evidence()`, `compression_score()`, and activation readiness accept it based on the span-derived tier without an independent density gate. That makes this a real research-validity blocker to revisit **before a percentile orchestrator ships and before percentile-based V2 evidence is treated as empirically meaningful**.

## 3. Separation of concepts

The audit keeps these concepts distinct:

| Concept | Current meaning / owner |
|---|---|
| calendar history span | age from current bucket to earliest included non-NULL sample |
| observation count | `PercentileSnapshot.sample_size` |
| expected timeframe buckets | structural expectation implied by timeframe/window; not currently a percentile usability gate |
| missingness / density | relationship between actual observations and expected observations; not encoded by `confidence_tier` |
| percentile statistical resolution | finite-N granularity of the empirical mid-rank estimator |
| Stage 2 maturity metadata | `confidence_tier`, deliberately span-based in Revision 0.2.4 |
| V2 evidence usability | current frozen `MIN_PCTL_TIER = building` plus non-NULL value/rank |
| activation readiness | whether all mandatory percentile identities have real evidence under those current V2 usability semantics |
| empirical-research eligibility | must additionally establish that evidence quality is fit for inference; issue #51/R-023 prevents silently equating this with calendar maturity |

No one field should be described as proving all eight concepts.

## 4. Finite-N percentile resolution

For historical sample size `N`, the frozen empirical mid-rank is:

```text
p = (less + 0.5 * equal) / N
```

With distinct historical values and a current value between observations, the no-tie lattice moves in steps of `1/N`. Equality can introduce half-steps, so observed ranks can differ by `1/(2N)` in tie cases.

Concrete examples:

| N | Example attainable ranks | Practical note |
|---:|---|---|
| 2 | `0, 0.25, 0.5, 0.75, 1` | extremely coarse; a single equality/outside-range relation causes a very large jump |
| 3 | `0, 1/6, 1/3, 1/2, 2/3, 5/6, 1` | still very coarse |
| 5 | half-step granularity `0.1`; no-tie step `0.2` | thresholds can be hit exactly by a small number of order relations |
| 10 | half-step granularity `0.05`; no-tie step `0.1` | better numerical resolution, still not a proof of inferential reliability |

This is numerical resolution only. It does not convert small `N` into statistically reliable evidence.

## 5. Relationship to frozen V2 gates

Frozen transforms/gates:

```text
positive normalized evidence: E = max(0, 2p - 1)
negative normalized evidence: E = -max(0, 1 - 2p)
compression_score = 1 - p

4h regime threshold: |E| >= 0.40
1h bias threshold:   |E| >= 0.25
compression threshold: score >= 0.75
```

Equivalent percentile cut points:

- positive 4h: `p >= 0.70`; negative 4h: `p <= 0.30`;
- positive 1h: `p >= 0.625`; negative 1h: `p <= 0.375`;
- compression: `p <= 0.25`.

A two-sample distribution can cross every one of these thresholds:

- `p = 0.75` gives positive `E = 0.50`, clearing both the 4h and 1h gates;
- `p = 1.00` gives `E = 1.00`;
- `p = 0.00` gives `compression_score = 1.00` and, for a negative signed raw metric, maximum negative evidence magnitude.

Therefore `MIN_PCTL_TIER` must never be described as an implicit small-N protection.

## 6. Adversarial vector matrix

The dedicated regression file `tests/analytics/test_percentile_maturity_audit.py` covers:

- `N = 2 / 3 / 5 / 10` over a 30d calendar span;
- two identical sparse samples;
- sparse-long-span versus dense-short-span behavior;
- exact 3d / 7d / 30d tier boundaries with only two observations;
- two closely-spaced old samples (e.g. `B-30d` and `B-30d+1m`, or the `7d` analog) proving the SECOND sample's position is irrelevant to maturity -- only the earliest sample's age relative to `bucket_ts` is evaluated (`test_two_closely_spaced_old_samples_still_reach_mature`, `test_two_closely_spaced_old_samples_still_reach_building_at_7d`; tech-lead amendment round 2);
- the four mandatory V2 percentile identities:
  - 4h / 30d `price_move_pct_median`;
  - 4h / 30d `range_width_pct_median`;
  - 1h / 7d `price_move_pct_median`;
  - 15m / 30d `range_width_pct_median`;
- concrete finite-N mid-rank examples;
- direct numerical reachability of the frozen 4h, 1h, and compression thresholds from `N=2`.

Existing branch regressions in `test_forecasting_v2_context_evidence.py` and `test_forecasting_v2_activation_readiness.py` separately prove that V2 evidence/readiness currently use the tier string and do not secretly apply `sample_size` as an alternate gate.

## 7. Classification

**CURRENT: `DOCUMENTATION_MISMATCH`.** Confirmed now, against the currently-live system. Existing V2 wording (`activation_readiness.py`, `V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §4.1) overstated what Stage 2 `confidence_tier` guarantees; the wording is corrected in this branch. No currently-reachable production defect exists, because no live percentile-computation orchestrator exists yet.

**FORWARD: `DEFERRED STATISTICAL_VALIDITY_GAP` — `R-023`.** The gap is real for any future consumer of a materialized `percentile_snapshots` row: `normalized_evidence()`/`compression_score()`/activation readiness accept a `confidence_tier`-usable row with no independent density check. Tracked as `docs/PROJECT_RISK_AND_DEBT_REGISTER.md` R-023, status `DEFERRED`, with an explicit re-entry condition (before a real percentile orchestrator ships, or before percentile-based V2 evidence is treated as empirically meaningful) — not resolved by this audit, and deliberately not resolved by inventing a density threshold here.

**`CORRECTNESS_BUG` — not established** in the percentile core. The core matches its frozen Revision 0.2.4 contract exactly.

## 8. Narrowest resolution

Current resolution:

1. correct V2 readiness/correctness wording so calendar maturity is never described as statistical density;
2. add named regressions exposing the sparse behavior rather than hiding it;
3. track the future density/materialization decision explicitly in the project risk register (`R-023`);
4. gate closure of that risk on the percentile orchestrator / empirical-research boundary;
5. do **not** invent a new minimum sample count in this audit.

A future orchestrator PR must either:

- introduce an explicit density/materialization invariant with a mathematical/structural rationale and appropriate identity/versioning treatment; or
- make an explicit reviewed decision that span-only maturity is permanently acceptable.

That decision must be made before percentile-based evidence is treated as empirically meaningful, not after looking at favorable/unfavorable future returns.

## 9. Versioning and replay impact

This audit changes no percentile formula, no Stage 2 config threshold, no V2 evidence transform, and no detector threshold.

- **`rules_version`: unchanged** (`v2-rules-v0.2.0`).
- **Stage 2 `calculation_version`: unchanged in semantics**; no feature/percentile/config computation rule changes.
- **Replay behavior:** unchanged for the same stored inputs. Sparse rows that were usable before remain usable under the frozen rule; the audit makes that fact explicit.
- **Historical identity:** no historical V2 decision meaning is rewritten by this audit.
- A future density gate that changes whether a historical decision is allowed to exist would be behavior-affecting and must receive explicit provenance/versioning treatment at that time; this audit does not pre-classify such a future change as harmless.

## 10. Non-changes

Explicitly unchanged:

- V2-v0 trading thresholds;
- setup formulas;
- lookbacks and horizons;
- OI semantics;
- agreement thresholds;
- setup-family definitions;
- percentile windows and ranking formula;
- `rules_version`;
- `config/v2.yaml` (`enabled: false`);
- Stage 6;
- deployment / VPS state.

The objective of this audit is to make the measuring instrument's limits explicit before testing the frozen model, not to improve the market model by preference.
