# Heterogeneous Family Rotation V3

**Status:** FROZEN
**Parent:** `HETEROGENEOUS_FAMILY_ROTATION_V2` (preserved unchanged as historical policy)
**Application:** `DISCOVERY_SPRINT_04`
**Machine-readable record:** `docs/research/HETEROGENEOUS_FAMILY_ROTATION_V3.json`

V3 incorporates the consumed Sprint 03 results (D9 and D10
`NO_USEFUL_STRUCTURE`, D11 `PROMISING_PROTOTYPE`). The A–I taxonomy is
memory, not ontology. A single failed formulation never closes a whole
family; each family below separates the whole-family status from the
subfamilies actually tested.

| Family | Whole-family status | Tested / deprioritized subfamilies |
|---|---|---|
| A Conditional risk abstention | open, not selected | RV_ABSTENTION (D2): prototype, BitMEX-replicated, volatility-scale compatible; immediate neighbors forbidden. Dislocation abstention (D2 RULE_2): failed |
| B Directional expectation | low priority for BTC-own short-horizon scalar prediction | BTC own-state/flow → return (H02–H05, B2-02..05) closed; OI (MARKET-01/02) null; external scalar → 24h MAE (MARKET-05/06) repeated null. Cross-sectional relative return is **not** B (tested under H) |
| C Path morphology | open but deprioritized | unconditional close-path functionals (D3) null; impulse morphology (H03, B2-03) closed |
| D Relative cross-asset | open for other pairs/mechanisms | BTC-ETH rolling corr (D4) null; BTC-ETH residual persistence (D10) null; ETH additive MAE (MARKET-05) null; raw lead-lag deferred, rescue forbidden. BTC-ETH two-asset subfamily deprioritized |
| E Liquidity/execution state | cooldown after positive | kline IMPACT_PROXY persistence (D7) prototype, not replicated. True order-book liquidity untested |
| F Regime transition | deferred, blocker unresolved | D1 null-model mismatch; kline vol transition (H01, B2-01) closed |
| G Event response | cooldown after positive | scheduled FOMC → unsigned 6h RV (D11) prototype; D8 deferred, not negative. No D11-template copies |
| H Cross-sectional / venue | open; **true panel selected** | same-5m two-venue SHARE (D9) null; venue dislocation → MAE (MARKET-06) null; TRUE_CROSS_SECTIONAL_PANEL selected as **D13** |
| I External benchmarks | deferred, source not pinned | D6 deferred; MARKET-03 external reproduction |
| **J Participant clock anchoring (new)** | new, **selected** | US-DST participation-profile shift selected as **D12** |

## Why J is a genuine new family

Which institutional clock organizes crypto participation is an uncovered
region. Earlier cards treated UTC time as a nuisance stratum (D3) or a
matching key (D11) and never asked what anchors it. J is not event
response (no event outcome), not liquidity-state persistence, and not
regime transition.

## This rotation

```
SELECTED_THIS_ROTATION              = [H, J]
SELECTED_INTERNAL_CARDS             = [D12, D13]
NEW_FAMILY_PROPOSALS                = [J]
NO_VOLATILITY_LEVEL_CARD_THIS_ROTATION = true
WHOLE_FAMILY_CLOSED_BY_SINGLE_FORMULATION = false
```

## Anti-rescue rules (carried and extended)

- A/D2: no RV threshold/window/horizon child; no dislocation-abstention child; no D2+D7 composition.
- C: no generic path-morphology relabel.
- E/D7: no IMPACT_PROXY threshold, P85/P95/P99, 720h, or 30m/2h/4h child; no L2 card justified as "better D7".
- G/D8: do not weaken D8 thresholds or control semantics.
- H/D9: no SHARE clipping, denominator cutoff, threshold/horizon variant, same-5m leadership relabel, or MARKET-06 MAE reuse.
- D/D10: no beta-window, residual-percentile, horizon, refractory, block-bootstrap, ETH-replacement, or raw lead-lag rescue.
- G/D11: no FOMC horizon/direction/recovery child; no CPI/NFP/ECB/all-macro/news-NLP copy.
- B/MARKET-05/06: stay away from external scalar → additive BTC predictor → 24h MAE.

No scientific outcome was computed. Protected 2025/2026 remain sealed.
MARKET-07 is not created.
