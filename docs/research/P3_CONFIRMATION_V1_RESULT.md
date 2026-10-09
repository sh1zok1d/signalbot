# P3 confirmation V1 — result (one shot, 2026-10-09)

**Prereg:** `docs/research/P3_CONFIRMATION_V1_PREREG.md` (commit 1b31db13, frozen before any 2025/2026 outcome was read).
**Code:** `scripts/research/p3c/run.py`. **Numbers:** `P3_CONFIRMATION_V1_PARITY.json`, `P3_CONFIRMATION_V1_RESULT.json`.
**Mode:** `CONFIRMATION`. Run once. No variant was tried after the outcome.

## Pipeline parity (gate)
The 5m-archive pipeline reproduces DH3-P3 on the discovery surface exactly: shift −5.92 pp, N 14218 (7109 / 7109). `PARITY = PASS`.
- Frozen thresholds from discovery z: q20 −1.0324, q80 +1.2992.

## Statistical result on surface C (2025-01-01 … 2026-08-15, BTCUSDT perpetual)
| | crowd long (S=1) | crowd short (S=0) |
|---|---|---|
| hours | 2523 | 3248 |
| up first within 4h | 48.0 % | 50.3 % |

- **Adjusted shift:** −1.66 pp.
- **Uncertainty:** 95 % CI −5.45 … +2.19 (82 week clusters); bootstrap p 0.39.
- **Skill:** Brier skill of the frozen discovery model −0.0016, i.e. no out-of-sample skill.
- **Information:** MDE at 80 % power 5.45 pp. The surface could see an effect of the discovery size (5.92 pp); it cannot exclude an effect of about 2–5 pp.
- **Stability:** by epoch, 2025 −1.0 pp (SE 2.4) and 2026A −4.7 pp (SE 3.1). Two epochs, so heterogeneity is not assessable.
- **Frozen class:** `NOT_CONFIRMED` (the CI contains 0).

## Trading translation (frozen rule)
Rule: crowd short → long, crowd long → short; entry at close; exit at ±X or after 4h; one position at a time.

| | trades | win rate | mean per trade | 95 % CI of the mean | sum |
|---|---|---|---|---|---|
| gross (0 %) | 2447 | 49.3 % | +0.002 % | −0.020 … +0.024 % | +4.8 % |
| maker 0.04 % | 2447 | | −0.038 % | −0.060 … −0.016 % | −93 % |
| **taker 0.12 % (class)** | 2447 | | **−0.118 %** | −0.140 … −0.096 % | −289 % |

- **Typical X:** 0.57 %. Both sides lose after costs: long −0.122 %, short −0.114 %. By year: 2025 −0.122 %, 2026A −0.112 %.
- **Frozen class:** `TRADING_FAIL`.
- **Discovery reference (not evidence):** on 2020–2024 the same rule earned +0.052 % gross per trade. At 0.12 % it lost −0.068 % (CI −0.090 … −0.047), so it was `TRADING_FAIL` even on the data where the effect was found.

## Limitations
- BTC and Binance only.
- Funding is not modelled.
- The 2025/2026 klines and metrics were product-open (PRODUCT_DECISION_V2 §4) and partly exposed by the divergence program. They were not pristine, but DH3-P3 had never been evaluated on them.
- The E1-RUN-001 holdout was not touched: the last object requested is dated 2026-08-14.

## Search exposure
- One cell (DH3-P3), one surface, one cost class. No threshold, horizon, barrier or cost variant was tried.
- Under the prereg the lead is closed and is never rescued on this surface.

## What this means
- The crowd-positioning effect from 2020–2024 did not repeat at its discovered size on 2025–2026. What remains is at most a small effect that this data cannot separate from zero.
- As a trade rule it has no gross edge on new data, and it loses after any realistic fee.
- This was the strongest directional lead in the project. No directional result in the project now supports a trade signal.
