# Discovery Sprint 03 — Implementation Freeze

**Unit:** `DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION`
**Kind:** outcome-blind feasibility and implementation. No scientific outcomes.

```
EXECUTION_AUTHORIZED = False
SCIENTIFIC_OUTCOMES_COMPUTED = False
D9_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D10_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D11_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D9_PRIMARY_LOCATION_STATISTIC = MEDIAN_PERP_RESOLUTION_SHARE
D10_REGRESSION_SPECIFICATION = NO_INTERCEPT_OLS
D11_OFFICIAL_SOURCE_PINNED = True
PROTECTED_2025_OPENED = False
PROTECTED_2026_OPENED = False
MARKET_07_CREATED = False
NEXT_UNIT = DISCOVERY_SPRINT_03_IMPLEMENTATION_RED_TEAM_AND_EXECUTION_DECISION
```

Classification contracts are frozen. No card is classified in this unit.
Real scientific target values were not inspected.

Classification precedence (all cards): IDENTITY_OK false → INVALID_DISCOVERY, then SUPPORT_PASS false → INCONCLUSIVE_DISCOVERY, then PROMISING_PROTOTYPE iff STATISTICAL and PRACTICAL and TEMPORAL, else NO_USEFUL_STRUCTURE.

D9 repair freeze:

- Extreme bars (`IS_EXTREME_BAR`, trailing P90 on 8640 valid |D|) are classified independently of the 12-bar refractory rule.
- Primary events are keep-first retained extremes. Refractory-dropped extremes are neither primary events nor controls.
- Controls require `IS_EXTREME_BAR == false`, genuine closure, and 1:1 YEAR × SIGN_D × RV_BUCKET matching of closing retained events, without replacement, seed `202609221931`.
- Report `RAW_EXTREME_BAR_N`, `RETAINED_EVENT_N`, `REFRACTORY_DROPPED_EXTREME_N`, `RAW_ELIGIBLE_CLOSING_CONTROL_N`, `MATCHED_CLOSING_CONTROL_N`. No SHARE summaries.
- `P_HALF`: sign-flip vs 0.5, seed `20260922193`. `P_CONTROL`: two-sided stratified label permutation of median_event − median_matched_control inside YEAR × SIGN_D × RV_BUCKET, seed `202609221932`.
- `STATISTICAL_GATE_D9 = P_HALF < 0.05 AND P_CONTROL < 0.05`.
- Structural: events 8349; closing 7184; raw extreme 35157; refractory-dropped 26808; raw eligible closing controls 130238; matched closing controls 7184; cells balanced True.

D10 repair freeze:

- 1:1 YEAR × SIGN_E_T × ABS_BTC_RETURN_BUCKET matching from |e_t| ≤ trailing P50 non-events, seed `202609221941`.
- Report `RAW_ELIGIBLE_CONTROL_N` vs `MATCHED_CONTROL_N`.
- Permutation is stratified inside those frozen cells; event/control counts preserved per stratum; seed `20260922194`. No global shuffle.
- Residual discovery-stage limitation: events may cluster in calendar time. This repair does not add a post-hoc refractory or block bootstrap.
- Structural: events 4442; raw eligible controls 21368; matched controls 4442; cells balanced True.

D11: official scheduled FOMC only. Control windows exclude any of the 6 constituent hours that overlap FOMC event/aftermath. No scientific redesign.
- Structural: events 39; controls 551; min controls among events 44.
