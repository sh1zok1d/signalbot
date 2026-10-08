# EXPOSURE_WEIGHTING_DECISION_V1

Status: `OWNER_DECISION_RECORDED`. Date: 2026-10-08.

This decision is subordinate to `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`, `docs/research/DISCOVERY_FIRST_RESEARCH_DECISION_V1.md`, the protected-data rules, and any experiment-specific frozen design. It does not rewrite a past result. It does not add a claim rung. L0–L4 are unchanged. There is no L5.

## Rule

Exposure is metadata about evidentiary independence, not an automatic prohibition on research.

A surface is not discarded only because another study once read its data. The question that decides whether a replication may run is: was the exact claim defined before its result was read on the new surface, and is that claim carried over without change?

If yes, the replication is allowed. Exposure is disclosed. Neighboring information that was already read lowers the strength of the wording. It does not forbid the estimand.

## Evidence classes

**A. `PRISTINE_CONFIRMATION`.** The exact claim was not read, and a materially neighboring future outcome or path was not opened in a way that could have influenced the choice of the claim.

**B. `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`.** The exact claim was frozen on another discovery surface and has not yet been computed on the target surface, but the target surface was previously used for neighboring observables or outcomes. The result is new replication evidence. It is not called pristine.

**C. `EXACT_CLAIM_REANALYSIS`.** The exact estimand, or a practically exact one, was already computed on this surface. That is not an independent replication. It may be a robustness or reanalysis only when a separate authorization says so.

**D. `OUTCOME_DRIVEN_REDESIGN`.** After the result is read, a threshold, horizon, feature, transformation, comparator, subgroup, direction, or claim is changed. That is forbidden as a confirmation or replication rescue.

## What a pass is not

A replication that supports the frozen claim remains L2 historical evidence. It is not L3, not L4, not a current probability, and not a trading edge.

## Application to the volatility-transition replication

`LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1` froze `DELTA_TRANSITION` on Binance USD-M BTCUSDT 2020–2024 before any BitMEX replication. Design `54338b7faab9598152e2fa1270d2fb51a4beed18`. The 60-minute pre/post close RV transition was not computed on `DH1_BITMEX_XBTUSD_TRADES_5M_V0`.

`LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1` already read `RESOLVED_WITHIN_4H` on that BitMEX surface and scanned high/low on bars `j+1..j+48`. That is a neighboring post-touch path. It is not the RV estimand.

Class for the replication unit: `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`. Not `PRISTINE_CONFIRMATION`. Not an unqualified `OUTCOME_UNREAD_SURFACE`.
