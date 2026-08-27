# H03 Design Red-Team — Extreme Impulse → Continuation vs Exhaustion

**Scope:** pre-outcome design review only. No H03 run, no market outcomes computed, no 2025/2026 data inspected, no development started.
**Repo:** `sh1zok1d/signalbot`
**Canonical methodology reviewed against:** `research/r2-screening-protocol-v1` @ `6c729b1b605ed3f8d078ce64d40154b9083076a2`
**Accepted dataset snapshot:** `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` (verified present, `ACCEPTED_FOR_DISCOVERY`, `research_authorized: true`, `confirmatory_authorized: false` — unchanged by this review)
**Docs read completely before forming judgment:** `docs/R2_SCREENING_PROTOCOL_V1.md`, `docs/EDGE_RESEARCH_PROTOCOL.md`, `docs/RESEARCH_ROADMAP.md`, `docs/reviews/R2_SCREENING_PROTOCOL_V1_REDTEAM.md`, `docs/reviews/R2_SCREENING_PROTOCOL_V1_MAINTAINER_ADDENDUM.md`, `docs/manifests/CORE_BTC_BINANCE_V0.yaml`

---

## H01/H02 independence assessment (required before anything else)

**H03's mechanism class is not reactive to H01/H02.** "Extreme impulse → continuation versus exhaustion" is already named as one of the original R2 mechanism candidates in `docs/RESEARCH_ROADMAP.md` (§R2, written before H01/H02 were executed), alongside compression→expansion (H01) and failed-breakout→mean-reversion (H02). Choosing to test it next is not a reactive pivot invented after H01/H02 failed.

**However, the proposed design as submitted does not yet contain the disclosure the canonical protocol now requires.** `docs/R2_SCREENING_PROTOCOL_V1.md` §5 (as corrected by the maintainer addendum) requires: *"When a Batch 01 hypothesis's mechanism definition, threshold family, or feature construction was influenced by an unexpected observation from an earlier hypothesis in the same batch... that influence must be explicitly declared in the ledger... before that hypothesis's development results are opened."* The design brief reviewed here does not state, one way or the other, whether any of its specific numeric choices (refractory = 60m, horizon ladder 15/30/60/120/240m, percentile ladder q90/95/98) were carried over from H01/H02's actual implementation conventions, versus derived independently for H03. I cannot verify this myself without inspecting H01/H02's frozen implementation artifacts, which is out of scope for this pre-outcome review and unnecessary to answer the narrower question the protocol actually asks: **has the influence been declared?** It has not. This is **Finding M1** below — a required missing section, not a reason to distrust the mechanism choice itself.

I am not asserting H03 is fully independent, and I am not asserting it is not. **The honest position is: independence of the mechanism class is supported by the roadmap precedent; independence of the specific numeric design choices is undeclared and must be stated affirmatively before development opens, per §5.** The frozen draft below adds the required disclosure section with this exact honest framing rather than asserting either extreme.

---

## Findings

### BLOCKER

None. The proposed design correctly incorporates every major canonical-protocol correction that post-dates the original R2 freeze (see "Confirmed sound" below) and contains no defect that would make H03, as scoped, an unfair test in either direction. All findings below are fixable by disclosure or a narrow numerical safeguard, not a redesign.

### MAJOR

**M1 — Missing mandatory Global-Adaptivity/design-influence disclosure (§5).**
- **Failure mode:** the design brief never states whether H03's specific parameter choices were influenced by H01/H02's execution or post-hoc findings, nor whether alternative control formulations were considered and discarded before settling on the ones proposed.
- **Risk:** false positive (an adaptively-shaped design smuggled in as if independent) — the exact failure mode §5 exists to close.
- **Concrete example:** if H03's 60-minute refractory or 15/30/60/120/240m horizon ladder happens to numerically match a convention established during H01/H02's implementation, a future reader has no way to tell whether that's coincidental convention-reuse or convention-reuse it should discount as non-independent, because nothing was declared either way.
- **Remediation:** add an explicit Global Adaptivity section to the frozen draft (done below) stating plainly what is and is not knowable from this review, and requiring the actual preregistration (written with access to H01/H02's real artifacts) to complete the declaration with specifics before development opens.

**M2 — Rolling reference-window statistics lack an effective-sample-size disclosure (Extremeness / Structural Control / Normalization sections).**
- **Failure mode:** `P_W(T)` (the extremeness percentile), the moderate-impulse control band, and `PAST_MEDIAN_ABS_RET_H(T)` (the normalization scale) are all computed from a 30-calendar-day trailing reference window sampled every 15 minutes. For `W = 60m` stepped every 15 minutes, each window shares 45 of 60 minutes with its neighbor; for `H = 240m` similarly. The *nominal* observation count (~2,880 over 30 days) materially overstates the *effective* (non-overlapping) sample size feeding a tail-percentile estimate — most severely for `q98` at `W = 60m`, where the effective count of genuinely non-overlapping 60-minute windows in 30 days is roughly 720, and the number of those actually exceeding a 98th-percentile cut is on the order of a few dozen.
- **Risk:** both directions. A noisily-estimated tail threshold can spuriously loosen (false positive: ordinary moves cross an artificially low threshold in some 30-day windows) or spuriously tighten (false negative: a genuine extreme fails to qualify because the trailing window was itself unusually volatile).
- **Concrete example:** a 30-day window dominated by one clustered volatility episode (common in BTC) can shift the estimated `q98` cutoff for `W=60m` up or down by a large relative amount from one month to the next, purely from estimation noise, before any real regime change has occurred.
- **Remediation (bounded, no new tunable parameter):** require every rolling percentile/median statistic used by the design (extremeness thresholds, moderate-control band, normalization scale) to report a fixed, non-selectable effective-N alongside its nominal N — computed as `floor(reference_window_days × 24 × 60 / W_or_H_minutes)`, i.e. the count of genuinely non-overlapping windows the reference period could contain. Cells whose effective-N for `q98` falls below a fixed, predeclared adequacy floor (200 non-overlapping observations) must be flagged for caution in the writeup. This is a disclosure requirement, not a new selectable knob, and does not change which cells are tested.
- **Partial mitigation already present:** candidate requirement #5 (coherent sign/plateau across `q90→q95→q98`) already provides some protection — a plateau is harder to produce by chance from independently noisy per-threshold estimates than a single isolated spike would be. This reduces but does not eliminate the risk (correlated estimation error across thresholds, since they share the same reference-window methodology, could still produce a spuriously coherent-looking plateau).

**M3 — No floor on the normalization denominator `PAST_MEDIAN_ABS_RET_H(T)`.**
- **Failure mode:** dividing by a rolling 30-day trailing median absolute return with no floor risks numerical blow-up during unusually quiet historical stretches (BTC has had genuine multi-week low-volatility periods).
- **Risk:** false positive. A handful of near-zero-denominator observations can produce enormous `NORM_CONT_RET_H` values that dominate a mean-based effect-size estimate, manufacturing an apparently large MPIE-crossing shift driven by a numerical artifact rather than a real conditional effect.
- **Concrete example:** during a historically quiet multi-week BTC stretch, `PAST_MEDIAN_ABS_RET_H(T)` for `H=240m` could be small enough that a single subsequent ordinary move produces a normalized outcome an order of magnitude larger than any other observation in the sample, dominating the reported mean.
- **Remediation (bounded, predeclared, outcome-independent):** floor `PAST_MEDIAN_ABS_RET_H(T)` at the corresponding statistic's own 5th percentile computed over the full development window (using only data available strictly before T, consistent with the design's own no-lookahead discipline) before it is used as a denominator. This is a fixed rule stated before outcomes, not a knob selected afterward.

### MINOR

**m1 — Decision boundary `T` should be explicitly defined as `bar_end_exclusive` of the 15m bar ending at T.** The design says "only information available at T may define the event" but never states T's own precise definition relative to the dataset's `bar_end_exclusive` availability convention (`docs/manifests/CORE_BTC_BINANCE_V0.yaml`). Left implicit, this is an easy place for an implementer to introduce an unintended one-bar lookahead or lag. **Fix:** state it explicitly in the frozen draft.

**m2 — "Month- and direction-composition-matched... where possible" is a silent-failure hedge.** Nothing requires disclosing how often matching was *not* possible for the structural control. **Fix:** require counting and reporting unmatched-comparison cases explicitly, not silently defaulting to an unmatched comparison.

**m3 — The `+6h` circular-shift negative control mildly confounds with diurnal/session timing.** A quarter-day shift moves most control observations into a different part of the UTC day, which could introduce mild session/time-of-day differences rather than a pure "same regime, different specific trigger" placebo. This matches the project's own established E1-RUN-001 convention (`docs/RESEARCH_LEDGER.md`: "fixed +6h same-day circular time-shift control") and is not materially flawed enough to warrant a replacement per the design brief's own instruction ("if materially flawed, propose ONE replacement" — it is not). **Fix:** disclose this as a known, accepted scope limitation of the control rather than an unstated assumption; no replacement needed.

**m4 — Explicitly state the matched-random-control seed (`20260831`) is used exactly once and is never re-rolled after any early inspection.** The design already fixes one seed, which is correct; this just makes the "never reseed" discipline an explicit, checkable commitment rather than an implicit inference.

**m5 — No statement on whether alternative control formulations were considered and discarded.** Feeds directly into the canonical protocol's control-shopping ledger requirement (§5). **Fix:** the frozen draft states plainly that the structural control (moderate-momentum band) and negative control (`+6h` circular shift) are the only formulations considered for this design, and that no alternative was tried and discarded.

### NO ISSUE (explicitly checked, found sound)

- **H03 family framing** — a genuine three-way falsifiable question (continuation / exhaustion / no effect), explicitly disclaiming trading-strategy, PnL, liquidation, news-classifier, and market-maker framing. Matches `docs/RESEARCH_ROADMAP.md`'s original phrasing.
- **Decision grid / no-lookahead discipline** — UTC-aligned, information available strictly at T only.
- **Impulse-window and extremeness construction itself** — a rolling, local (not global/static) percentile-rank definition is the right way to operationalize "extreme relative to its recent local distribution"; only the effective-N disclosure (M2) is missing, not the construction.
- **Fixed threshold set (q90/95/98), no extra thresholds** — correctly bounds the search surface.
- **Refractory design** — correctly scoped as a trigger-deduplication mechanism, correctly delegates outcome-level dependence to the block-bootstrap machinery rather than conflating the two.
- **Outcome horizons + the boundary rule** — this is the strongest part of the proposal. The stated rule ("A development observation is eligible for horizon H only when the ENTIRE frozen future H path resolves strictly before 2025-01-01T00:00:00Z. No horizon truncation.") is a verbatim, correct implementation of the maintainer-adopted canonical fix for the pool-boundary embargo (`R2_SCREENING_PROTOCOL_V1.md` §1, "exclude, do not truncate"). This is direct, checkable evidence the design tracks the current canonical protocol rather than an earlier or ad hoc understanding of it.
- **Primary outcome sign convention** — fixed before outcomes, explicit "do not flip the sign after outcomes" instruction.
- **Normalization anchor's independence from candidate outcomes** — `PAST_MEDIAN_ABS_RET_H(T)` uses only trailing, pre-T data, satisfying the canonical protocol's maintainer-corrected MPIE-anchoring rule (§8: "a fixed fraction of the unconditional/local median absolute move... used by the primary normalized metric"). Sound in principle; only needs the M3 floor.
- **MPIE magnitude (0.10)** — a defensible order of magnitude: neither trivially small nor implausibly large, sits in a reasonable "practically noticeable, not extreme" zone comparable to established small-to-medium market-microstructure effect sizes. Correctly anchored to a pre-T distributional scale, not derived from the candidate's own result.
- **Structural control (moderate-momentum band, `0.60 ≤ P_W(T) < 0.80`)** — the simplest available control that isolates "extremeness" as the specific incremental ingredient while holding "directional momentum exists at all" constant. Directly answers the design brief's own audit question affirmatively.
- **Matched random control** — fixed deterministic seed, 100 replicas, correctly framed as estimating a control distribution rather than new market evidence (`docs/EDGE_RESEARCH_PROTOCOL.md` §18).
- **Search surface (3×3×5 = 45 cells)** — matches H01/H02's own stated 45-cell precedent; H03 is not silently expanding the per-family search surface.
- **Chronological stability rule** — correctly implements the maintainer's no-named-shock-year-exclusion correction verbatim, and correctly declines to make H03 regime-specific in this task per explicit instruction (a regime-conditioned hypothesis, if ever wanted, would need its own separate deterministic-state preregistration).
- **Direction/symmetry scope** — correctly implements §11 exactly, matching the canonical protocol's own worked H03 example.
- **Candidate-for-freeze requirements list** — a faithful, complete restatement of §15 applied to H03's specific design.

---

## Final dependence diagnostic (as required, defined exactly once)

The canonical protocol (§12, red-team-fixed) requires "a fixed, non-selectable autocorrelation-decay or effective-sample-size diagnostic," described only in the abstract. This review defines it concretely for H03:

**ACF-crossing dependence-half-life proxy.** On the full development window (embargo-respecting), compute the **daily** series of total absolute 15-minute log-returns (a standard realized-volatility-activity proxy, computed independently of any candidate event or outcome). Compute its autocorrelation function at the fixed, predeclared lag set **{1, 2, 4, 8, 16, 32} calendar days**. Report the diagnostic as **the smallest lag in that fixed set at which the ACF first falls below 0.2** (a fixed, non-tuned "weak correlation" threshold). If the ACF has not fallen below 0.2 by lag 32, report the diagnostic as `>32 days`.

- Not a new selectable block length — it is a single reported number, not a knob.
- Exposes multi-month dependence directly: a value at or beyond 16–32 days is a direct signal that 1w/2w/4w block sensitivity may understate true persistence, which must be disclosed and flagged for qualitative caution per the canonical protocol's existing rule — it does not by itself gate promotion.
- Fully reproducible and interpretable from the frozen dataset and this fixed formula alone; no "inspect ACF and decide" judgment call.

---

## Final control recommendation

Keep the structural control (moderate-momentum band) and negative control (`+6h` circular shift) exactly as proposed — both are appropriate, and the negative control matches established project convention (E1-RUN-001). Add only: (a) the m3 disclosure of the negative control's mild diurnal-confounding limitation, and (b) the m5 disclosure that no alternative control formulations were tried and discarded, so the ledger's control-shopping requirement is satisfied by an honest "none" rather than silence.

---

## False-positive risks

Concentrated in M2 (noisy tail-percentile thresholds at `W=60m`/`q98`) and M3 (normalization denominator blow-up during quiet markets) — both could inflate an apparent effect through estimation/numerical artifacts rather than a real conditional relationship.

## False-negative risks

Also concentrated in M2 — an unusually volatile trailing 30-day reference window could push the extremeness threshold up enough to under-select genuine extreme events in the following period, weakening a real effect's apparent strength. No other false-negative risk was found: the design's symmetry, chronological-stability, and parameter-neighborhood rules all correctly preserve a path for a real, narrow mechanism to survive (per the canonical protocol's own already-sound design in those areas).

## Fixes

Applied (3 MAJOR, 5 MINOR) as the corrected design in `docs/research/H03_DESIGN_FROZEN_DRAFT.md` — still a design draft, not a preregistration (H01/H02 remote durability is a separate operational precondition not addressed by this review).

- fix branch: `research/h03-design-redteam`
- fix SHA: `483b0c71e9450b4101a450a09ed144f874e8d5d6` (created from exact base `6c729b1b605ed3f8d078ce64d40154b9083076a2`)
- fix PR: opened as **draft** against `research/r2-screening-protocol-v1`, not merged

## Validation contamination

- 2025 inspected: **NO**
- 2026 inspected: **NO**
- H03 real outcomes computed: **NO**

## Final verdict

**B — H03 DESIGN SOUND WITH FIXES — CORRECTED DESIGN READY AFTER H01/H02 REMOTE DURABILITY.**

No blocker was found; the design already correctly incorporates every canonical-protocol correction that post-dates the original R2 freeze (boundary embargo, MPIE anchoring, no-shock-exclusion, symmetry scoping). Three MAJOR gaps (missing adaptivity disclosure, missing effective-N disclosure for rolling percentile statistics, missing normalization floor) and five MINOR clarity gaps are fixed narrowly in the frozen draft below. This is still a design document, not a preregistration — per the task's own framing, actual preregistration additionally requires H01/H02's remote durability to be completed first, which is outside this review's scope to satisfy.
