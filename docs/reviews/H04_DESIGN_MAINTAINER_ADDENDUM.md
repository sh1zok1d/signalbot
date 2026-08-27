# H04 Design — Maintainer Addendum

**Reviewed PR:** #80  
**Claude red-team HEAD reviewed:** `e56acb4d6f3f5327d9cfc781e61f0e0abd3cfa88`  
**Maintainer correction commit:** `23c39f2fa38bab5cce4c5e63553c8cd3fb0e0b63`

The independent red-team correctly identified two material pre-outcome design problems: nested pullback thresholds and the mirror-extension structural control. Before accepting H04 for preregistration, the maintainer independently reviewed the corrected draft and closed two remaining degrees of freedom.

## 1. Structural control is narrowed again

The red-team replaced mirror-extension with "all established-trend moments irrespective of the recent P-window, excluding only the exact treated timestamps for the current depth band."

That is still not a clean structural counterfactual for H04.

For a shallow-band candidate, that control can contain:

- moderate/deep H04 pullbacks;
- same-direction extensions;
- other materially non-neutral recent moves.

So the control still mixes states that contain the very pullback/extension ingredient H04 is trying to isolate. This tends mainly toward false negatives by diluting the contrast, but it also makes the interpretation of a passed structural gate ambiguous.

The final frozen structural control is:

```
RECENT_RATIO(T) =
    SIGNED_PB_RET(T) / abs(TREND_RET_L(T))

TREND_PCTL_L(T) >= 0.80
AND
abs(RECENT_RATIO(T)) < 0.10
```

This uses the already-frozen shallow-depth edge `0.10`; no new numeric dial is introduced.

Interpretation:

**established trend + no material recent move on the H04 depth scale**

versus:

**established trend + material counter-trend pullback**.

The control is matched where possible on calendar month, trend direction, and frozen trend-strength bins `[0.80,0.90)` / `[0.90,1.00]`.

Primary structural gate remains:

`mean_pullback - mean_neutral_recent_trend >= 0.05`.

No mirror-extension and no "all trend moments" alternative remain selectable.

## 2. Exclusive-band robustness requirement is made fair

Once the red-team correctly changed the primary depth construction from nested thresholds to three mutually exclusive bands:

- shallow `[0.10,0.25)`
- moderate `[0.25,0.40)`
- deep `[0.40,1.00)`

the draft still effectively asked for "the three bands" to form a coherent neighborhood.

That is unnecessarily harsh. Exclusive bands no longer share the same events, so requiring all three could reject a real depth-local mechanism merely because the deepest band behaves differently.

The final frozen robustness rule is:

- at least **two adjacent depth bands** within the promoted `L` family must support the same positive primary sign with compatible control evidence;
- the third band may be weaker/null;
- one isolated band cannot promote H04.

This preserves protection against magic-band promotion without requiring a universal effect across all pullback depths.

## Final maintainer assessment

After these corrections:

- nested-threshold pseudo-robustness is closed;
- structural control now directly tests pullback-specific incremental value beyond established trend + no material recent move;
- candidate robustness has a fair path for a genuine depth-local effect;
- no unresolved methodological blocker remains before preregistration.

Validation state:

- 2025 inspected: **NO**
- 2026 inspected: **NO**
- H04 real outcomes computed: **NO**

**Maintainer verdict: READY TO PREREGISTER.**
