# D7 campaign close V1

**Status:** `D7_CAMPAIGN_CLOSED`
**Date:** 2026-10-01
**Machine-readable twin:** `docs/research/D7_CAMPAIGN_CLOSE_V1.json`

This record closes the D7 campaign (`KLINE_FLOW_IMPACT_STATE`, family E) from discovery through independent confirmation and the one product use. It recomputes nothing and changes no sealed artifact.

```
D7_CAMPAIGN_CLOSED              = true
D7_DISCOVERY_CLASSIFICATION     = D7_PROMISING_PROTOTYPE
D7_CONFIRMATION_LABEL           = CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS
D7_PRIMARY_RESULT_SHA256        = b4efa972cec9acfacb2987be7aef3ad1ed239c8279977374a18265dfe60df503
D7_RERUN_AUTHORIZED             = false
D7_SECOND_SEED_AUTHORIZED       = false
D7_CHILD_CARDS_AUTHORIZED       = false
D7_LIVE_HIT_RATE_MONITORING     = NOT_AUTHORIZED
PROTECTED_2025_2026_OPENED      = false
NEXT_UNIT                       = HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW
```

## 1. Campaign chain

| Step | Date | Record |
|---|---|---|
| Card defined (heterogeneous family rotation V1, Sprint 02) | 2026-09-22 | `DISCOVERY_SPRINT_02.{md,json}` |
| Discovery one-shot, Binance USD-M BTCUSDT 2020–2024 | 2026-09-22 | `DISCOVERY_SPRINT_02_D7_RESULT.{md,json}`; payload SHA-256 `7a7d38ef…` |
| BitMEX XBTUSD 5m activity data, outcome-blind pin | 2026-09 | `D7_BITMEX_ACTIVITY_V0.md` |
| Dependence and inference review; support and power | 2026-09 | `D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0`, `D7_BITMEX_SUPPORT_AND_POWER_V0` |
| Exact geometry, gap break, power gate | 2026-09-30 | `RESEARCH_LEDGER.md` entries of that date |
| Adapter, freeze manifest, decision rule | 2026-09-30 | `D7_CONFIRMATORY_ADAPTER_V1`, `D7_CONFIRMATORY_FREEZE_MANIFEST_V1`, `D7_DIRECTIONAL_CONFIRMATION_DECISION_RULE_V1` |
| Final contract integrity repair | 2026-10-01 | `D7_FINAL_CONTRACT_INTEGRITY_REPAIR_V1` |
| First opening attempt, failed before any target parse (`BEACON_SIGNATURE_INVALID`) | 2026-10-01 | `D7_CONFIRMATORY_TARGET_OPENING_V1` |
| Verifier repair; scan of 72 NIST pulses, all `INVALID`, none selected | 2026-10-01 | `D7_BEACON_VERIFIER_REPAIR_V1`, `D7_CONFIRMATORY_BEACON_SCAN_V1` |
| Seed-source amendment to `DETERMINISTIC_FIXED_SEED_V1`, before the target was opened | 2026-10-01 | `D7_CONFIRMATORY_SEED_SOURCE_AMENDMENT_V1` |
| Opening authorization | 2026-10-01 | `D7_DETERMINISTIC_SEED_OPENING_AUTHORIZATION_V1` |
| Confirmatory primary result, sealed | 2026-10-01 | `D7_CONFIRMATORY_PRIMARY_RESULT_V1.{md,json}` |

## 2. Evidence

**Discovery** (`ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`):
- `MU_D7_RULE = 0.1894` against `MU_D7_CONTROL = 0.0986` (rate-matched);
- `DELTA = 0.0909`, Monte Carlo `p = 0.0001`;
- positive in all five years 2020–2024 (0.101, 0.084, 0.105, 0.070, 0.097);
- `CANDIDATE_N = 4545`, `ANALYSIS_N = 42407`.

**Confirmation** (BitMEX XBTUSD 2016–2019, an independent era and venue):
- `theta_hat = 0.1293`, `SE = 0.0090`;
- dependent wild bootstrap (DWB), `R = 9999`, `p = 0.0001`;
- one-sided lower bound `L = 0.1139`;
- year `theta` 2017 0.156, 2018 0.127, 2019 0.095 (2016 is diagnostic only, 0.136);
- `D7_DIRECTIONAL_CONFIRMATION_PASS = true`, `MAGNITUDE_AT_0_05_SUPPORTED = true`.

**Established.** After a clock hour in the D7 high-impact state (absolute return per unit of relative quote volume above the trailing p90), the following hour was in the same state materially more often than at the rate-matched base. This holds under the maintained DWB assumptions, in the discovery era and in an independent earlier era on another venue.

**Not established:**
- price direction, size of the move, or profitability;
- cellwise or assumption-free confirmation;
- the external-beacon unpredictability guarantee (it was removed by the amendment);
- behaviour in 2025/2026, which stay sealed;
- Bybit and OKX;
- an order-book liquidity mechanism. The observable is a kline impact proxy.
- persistence fully beyond the persistence of volatility and relative volume. The baseline is a rate-matched random state within `calendar_year × RV_BUCKET`, where `RV_BUCKET` is one of four trailing quartiles of the hour's absolute return. That removes coarse volatility clustering. It does not remove volatility variation inside the top bucket, where state hours concentrate, and it does not match relative volume. See `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.md`.

## 3. Product use

**One claim was promoted.** It went through `docs/BETA_D7_REGIME_CONTEXT_GATE_V1.md`: a non-directional "High impact" hour context, worded "about 1 in 5 vs about 1 in 10".

**Parity.** The live implementation in `beta/regime_d7.py` matches the research definition:
- CI synthetic parity;
- owner-run real parity on Binance monthly 1m 2020–2024: 0 state mismatches over 42,407 hours with a state.

**Display.** The line needs both the committed hard allow and the owner state `/admin_d7_on`.

**Scope of the claim.** The promoted claim is the state frequency only. It does not depend on the residual persistence beyond volatility and relative volume, which was not tested (§2).

## 4. What closing means

- **No re-runs.** No rerun, no second seed, and no re-opening of the BitMEX target.
- **No children.** No D7 child cards. The anti-rescue list in `HETEROGENEOUS_FAMILY_ROTATION_V3` holds: no IMPACT_PROXY threshold, P85/P95/P99, 720h, or 30m/2h/4h child, and no L2 card justified as "better D7".
- **No live hit-rate monitoring.** Counting next-hour outcomes on 2026 data would evaluate protected data. That needs its own decision.
- **A decomposition is a new object.** A test of persistence beyond volatility and relative volume would be a new research object, like the D2 excess decomposition. It needs the adopted evaluation contract, a fresh preregistration, and an honest account of the support problem: conditioning on its own components makes the state nearly deterministic in the extreme cells. Nothing is authorized here.
- **Family E stays in cooldown.**

## 5. Routing

The roadmap's post-D7 gate now applies: `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW` (`docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.md`).
