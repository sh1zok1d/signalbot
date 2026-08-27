# H05 — Taker Imbalance -> Subsequent Return Distribution: Preregistration

**Status:** PREREGISTERED_EXPLORATORY. This document, together with
`docs/research/H05_TAKER_IMBALANCE_PREREG.json` (the machine-readable
frozen spec) and `scripts/research/h05_taker_imbalance_lib.py` /
`scripts/research/h05_taker_imbalance.py` (the frozen implementation),
constitutes the H05 prereg + code freeze. No real H05 market outcomes
have been computed. 2025 and 2026 remain untouched.

**Amendment history:** this preregistration underwent one PRE-OUTCOME
STRUCTURAL-SUPPORT CORRECTION (this revision), which supersedes
`H05_PREREG_SHA_V1 = 9502006eb4797a9947c61d8d04acd1345ed41e5e` (preserved,
unamended, `SUPERSEDED_PRE_OUTCOME`). An independent pre-outcome audit
found that V1's structural gate compared the FULL (unrestricted)
candidate-population mean against a control mean standardized only over
overlap strata — quantities on different support, letting unmatched
-candidate-stratum outcomes move the gate without any corresponding
control observation. See section 6 for the corrected, like-with-like
estimand. **No real H05 outcome was inspected to make this correction.**
No design parameter (mechanism, signs, `W`/`q`/`H` surface, seeds, `MPIE`,
`CONTROL_DELTA_MIN`, strata definitions) changed.

**Design authority:** `docs/research/H05_TAKER_IMBALANCE_DESIGN.md` @
`deaf6503896920685f25a03230174d360a07ab9a` (branch
`research/h05-design-redteam`, PR #82, OPEN/DRAFT/UNMERGED). This
preregistration encodes that design; it does not redesign H05. Every
number, formula, and rule below is taken directly from that design
document and from `docs/reviews/H05_DESIGN_REDTEAM.md`. Any place where
the design left an implementation detail unstated is resolved explicitly
in `docs/reviews/H05_PREREG_IMPLEMENTATION_AUDIT.md`, not silently chosen
here.

**Batch position:** H05 is the fifth and **final** primary mechanism
family of R2 Batch 01 (H01 REJECTED/KILL, H02 REJECTED/KILL, H03
`H03_REJECTED_SPECIFIC_CLAIM`, H04 `H04_REJECTED_SPECIFIC_CLAIM`). After
H05 closes, the next mandatory step is **Batch01 synthesis** — not a new
H06. This task does not start either.

For the full, itemized rationale behind every frozen number below (why
nested `q`, why the fixed `[0.60, 0.80)` ordinary band, why both signs,
why the `S`-oriented gate formalism, why activity and price-alignment are
mandatory strata, etc.), see the design document and its red-team review;
this file states the frozen result, cross-referenced to the machine
-readable JSON for exact reproducibility.

---

## 1. Dataset and windows

`CORE_BTC_BINANCE_V0`, snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`,
`ACCEPTED_FOR_DISCOVERY`, `research_authorized: true`,
`confirmatory_authorized: false`. Development pool `2020-02-01` ->
`2025-01-01` (exclusive). 2025 (batch validation) and 2026 (final OOS,
through `2026-08-26`) remain untouched by this preregistration and its
implementation. Complete-path horizon embargo: a candidate's full outcome
path must resolve strictly before `2025-01-01T00:00:00Z`; candidates
whose horizon would cross the boundary are excluded, never truncated.
See `windows` in the JSON.

## 2. Primary flow feature

```
BUY_W(T)   = sum(taker_buy_base_volume) over [T-W, T)
SELL_W(T)  = sum(base_volume - taker_buy_base_volume) over [T-W, T)
TOTAL_W(T) = BUY_W(T) + SELL_W(T) == sum(base_volume) over [T-W, T)
TAKER_IMBALANCE_W(T) = (BUY_W(T) - SELL_W(T)) / TOTAL_W(T)
```

Base-volume is primary; quote-volume is computed identically but is
diagnostic-only and can never rescue a failed base-volume result.
`TOTAL_W(T) == 0` or non-finite is explicit ineligibility (never coerced
to zero, always counted). `D(T) = sign(TAKER_IMBALANCE_W(T))`; `D=0`
(exact tie) is excluded. See `primary_flow_feature`/`direction` in the
JSON.

## 3. Decision grid, W, q

15-minute UTC decision grid, `T` = `bar_end_exclusive`. Feature/lookback
windows `W ∈ {15, 30, 60}` minutes. Flow extremeness
`ABS_IMBALANCE_W(T) = abs(TAKER_IMBALANCE_W(T))`, referenced against its
own trailing 30-calendar-day, same-grid, strictly-causal midrank
percentile. Threshold family `q ∈ {0.80, 0.90, 0.95}`, **nested**:
candidate membership at `q` is `ABS_IMBALANCE_PCTL_W(T) >= q`. See
`flow_extremeness` in the JSON for the nested-construction justification
(both preregistered signs predict a monotonic severity dose-response;
unlike H04's pullback depth, there is no "could mean either regime"
ambiguity here).

## 4. Claim orientation (S) — both signs preregistered together

```
S = +1  FLOW CONTINUATION   (sign(outcome) == D)
S = -1  FLOW EXHAUSTION / REVERSAL   (sign(outcome) == -D)
```

The stored primary metric `X = NORM_TAKER_RET_H` (section 7) is **never**
multiplied by `S` or re-signed; `S` and the four oriented gate quantities
below are computed only at the gate-evaluation layer, from the same
naturally-signed `candidate_mean`/`matched_mean`/`structural_delta`/
`shifted_mean` for both orientations:

```
ORIENTED_PRIMARY           = S * candidate_mean
ORIENTED_MATCHED_DELTA     = S * (candidate_mean - matched_mean)
ORIENTED_STRUCTURAL_DELTA  = S * structural_delta
ORIENTED_SHIFT_DELTA       = S * (candidate_mean - shifted_mean)
```

`candidate_mean` is the FULL (unrestricted) candidate-population mean of
`X`, used for the primary/matched/shift deltas. `structural_delta` is
**not** a mean differenced against `candidate_mean` here — per the
structural-support correction (section 6), it is the already-computed,
like-with-like overlap comparison
(`candidate_overlap_standardized_mean - structural_control_standardized_mean`).

**Anti-cherry-pick rule (frozen):** a sign may not be selected or
promoted because the other sign failed first. Both checklists are
evaluated in full against the same 45 cells; both results are recorded.
This is **one 45-cell search surface**, not two — sign multiplicity is
disclosed separately (section 12). See `claim_orientation` in the JSON.

## 5. MPIE and control gates (restored/exact semantics)

```
Primary:    ORIENTED_PRIMARY           > 0
MPIE:       ORIENTED_MATCHED_DELTA     >= 0.10
Structural: ORIENTED_STRUCTURAL_DELTA  >= 0.05   (CONTROL_DELTA_MIN)
+6h:        ORIENTED_SHIFT_DELTA       >= 0.05   (CONTROL_DELTA_MIN)
```

`MPIE` gates the matched-random separation specifically (not the
structural delta, not the candidate mean alone, not a statistical
-significance test) — the established Batch01 meaning, restored exactly.
All four are mandatory. See `mpie`, `control_materiality`,
`primary_sign_gate` in the JSON.

## 6. Structural control (the non-negotiable control)

Fixed "ordinary" flow population `0.60 <= ABS_IMBALANCE_PCTL_W(T) < 0.80`
— identical across all three `q` cells, reused verbatim from H03's
frozen moderate band. `PRICE_RET_W(T) = ln(close(T)/close(T-W))`;
`SIGNED_PRICE_RET_W(T) = D(T) * PRICE_RET_W(T)`; `price_alignment` =
`ALIGNED` if `> 0` else `OPPOSED` (exact zero -> `OPPOSED`, frozen,
deterministic, kept binary). `price_strength_bin` and `activity_bin`
(on `TOTAL_W`) are each a causal `LOWER`/`UPPER` split at their own
trailing-30d midrank percentile `0.50`. **Five mandatory match strata:**
`calendar_month × D × price_alignment × price_strength_bin ×
activity_bin`. Candidate-weighted standardization: control means are
weighted per overlap stratum by candidate frequency
(`w_s = candidate_N_s / sum(candidate_N over overlap strata)`).

**PRE-OUTCOME STRUCTURAL-SUPPORT CORRECTION (this revision, supersedes
`H05_PREREG_SHA_V1`):** the structural comparison is **like-with-like** —
both sides of the comparison are restricted to, and weighted over,
exactly the same overlap strata:

```
candidate_overlap_standardized_mean    = sum_s w_s * candidate_mean_s
structural_control_standardized_mean   = sum_s w_s * control_mean_s
structural_delta = candidate_overlap_standardized_mean
                  - structural_control_standardized_mean
```

V1 instead compared the FULL (unrestricted) `candidate_mean` against
`structural_control_standardized_mean` alone — quantities on different
support. If unmatched candidate strata had systematically different
outcomes, they could move the full candidate mean while having no
corresponding structural-control observation at all, letting the gate
pass or fail on composition the control never actually saw. The full,
unrestricted candidate-population mean remains the estimand for every
OTHER gate (primary, matched, shift, bootstrap, year stability, BUY/SELL
symmetry) — matched-random and `+6h` have their own candidate/reference
semantics and are not restricted by structural-control overlap; only the
structural estimand changes here. Control-only strata get zero weight;
unmatched candidates are reported, never dropped; insufficient overlap
support (zero overlap strata) routes to `INCONCLUSIVE`, never a
post-outcome loosening or a fabricated numeric effect. See
`structural_control` in the JSON.

## 7. Primary outcome and normalization

```
RAW_FUTURE_RETURN(T,H) = ln(close(T+H)/close(T))
signed_ret(T,H) = D(T) * RAW_FUTURE_RETURN(T,H)
X = NORM_TAKER_RET_H(T) = signed_ret(T,H) / trailing_30d_median_abs_H_return(T)
```

`H ∈ {15, 30, 60, 120, 240}` minutes. Normalization is strictly causal
(trailing 30-day median of `|RAW_FUTURE_RETURN_H|`, fully resolved before
`T`, no floor, no future/full-development normalization). See `returns`,
`normalization` in the JSON.

## 8. Refractory

60-minute, either-direction suppression, keep earliest. No
direction-aware exception. See `refractory` in the JSON.

## 9. Matched-random baseline and +6h negative control

Matched-random: match on calendar month + `D` only (deliberately not
price/activity-matched, to avoid duplicating the structural control);
seed `20260904`, 100 replicates, without replacement, membership-safe
(`np.isin`) pool exclusion of every raw qualifying candidate timestamp
for the same `(W, q)`. `+6h` same-UTC-day circular shift, preserving each
candidate's own `D`; collision fraction reported; gate is the exact
`ORIENTED_SHIFT_DELTA >= CONTROL_DELTA_MIN` contrast. See
`matched_random`, `negative_control` in the JSON.

## 10. Dependence and candidate-clustering diagnostic

UTC-week block bootstrap on the candidate primary mean `X` only (never
the matched/structural/shift deltas — three distinct estimands, never
substituted), master seed `20260905`, 2000 replicates, with 1w/2w/4w
block-size sensitivity wired in from this initial implementation commit
(terminal partial block retained, never discarded; `block_size_weeks==1`
uses the bare seed, `{2,4}` derive `SeedSequence([seed, size])` children).
Bootstrap sign gate: `p025 > 0` at 1w AND 2w AND 4w for continuation;
`p975 < 0` at 1w AND 2w AND 4w for reversal. The **outcome-independent,
cell-specific candidate-clustering diagnostic** (renamed from the design
review's "candidate-independent" label, computation unchanged) uses the
post-refractory candidate indicator series (never outcome/return values)
at fixed lags `{1,2,4,8,16,32,64}` days, `|ACF|>=0.20`, reporting the
largest qualifying lag; descriptive only, never gates promotion. See
`uncertainty`, `candidate_clustering_diagnostic` in the JSON.

## 11. Robustness (q, H, W), year stability, direction symmetry

- `q`: at least 2 of 3 adjacent cells gate-passing (`0.80↔0.90`,
  `0.90↔0.95`). Isolated `q` cannot promote.
- `H`: at least 2 adjacent horizons gate-passing (`15↔30↔60↔120↔240`).
  Isolated `H` cannot promote.
- `W`: at least one adjacent `W` (`15↔30↔60`) with directional support
  (`ORIENTED_PRIMARY>0 AND ORIENTED_MATCHED_DELTA>0 AND
  ORIENTED_STRUCTURAL_DELTA>0`, direction only, not the full numeric
  gates). A fully isolated `W` cannot promote.
- Year stability: `S * yearly_candidate_primary_mean(y) > 0` in at least
  4 of 5 years (2020-2024). No shock-year exclusion path exists.
- Direction symmetry: `ORIENTED_PRIMARY > 0` independently for `D=+1` and
  `D=-1` under the same `S`. A one-sided result is `POSTHOC_UNTESTED` and
  cannot promote.

See `parameter_robustness`, `chronological_stability`,
`direction_symmetry` in the JSON.

## 12. Search surface and sign-multiplicity accounting

`W=3 × q=3 × H=5 = 45` primary cells. Batch01 cumulative:
`H01(45) + H02(45) + H03(45) + H04(45) + H05(45) = 225`. Both
continuation and reversal are evaluated on the **same** 45 cells; this
sign multiplicity is disclosed separately and is **not** added to the
225-cell total. See `search_surface` in the JSON.

## 13. Verdict labels and audit-failure rule

```
H05_FLOW_CONTINUATION_CANDIDATE_FOR_FREEZE
H05_FLOW_REVERSAL_CANDIDATE_FOR_FREEZE
H05_INCONCLUSIVE
H05_REJECTED_SPECIFIC_CLAIM
```

If both continuation and reversal appear to satisfy conflicting
promotion conditions simultaneously (an implementation error or
impossible result), that is treated as an **audit failure** — the
implementation does not silently choose one. See `verdict_labels`,
`both_signs_cannot_pass_simultaneously` in the JSON.

## 14. Post-hoc quarantine

The following (and anything like them) are `POSTHOC_UNTESTED` if
proposed after real H05 outcomes are inspected, and cannot rescue a kill:
a single passing `q`/`H`/fully-isolated `W`; BUY-only or SELL-only
results; quote-volume-only results; a price/imbalance divergence
"discovered" after outcomes; any alternative activity threshold, price
bin, ordinary-flow band, refractory rule, `W`/`H`/`q` value, or `+6h`
shift adopted after outcomes; regime rescue; year exclusion; or sign
reinterpretation. See `posthoc_quarantine` in the JSON and section 24 of
the design document for the full, itemized list. No child H05 experiment
is created in this task.

## 15. Implementation carry-forwards and no-real-data-access constraint

Membership-based pool exclusion; real-timestamp calendar keys;
candidate-weighted deterministic structural standardization; 1w/2w/4w
dependence sensitivity wired in from the first commit; complete-horizon
embargo enforced at eligibility time — all carried forward from the
H03/H04 implementation lessons, not from any H01-H04 outcome-derived
market conclusion. This preregistration round used only repository
governance/design documents and the `CORE_BTC_BINANCE_V0` manifest schema
(metadata, not row data); the implementation
(`scripts/research/h05_taker_imbalance_lib.py`,
`scripts/research/h05_taker_imbalance.py`) is exercised only against
local synthetic fixtures in
`tests/research/test_h05_taker_imbalance.py` — `--stage dev-run` is not
invoked against real accepted parquet in this task. See
`docs/reviews/H05_PREREG_IMPLEMENTATION_AUDIT.md` for the independent
pre-outcome audit of this freeze.
