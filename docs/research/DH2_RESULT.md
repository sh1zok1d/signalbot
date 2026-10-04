# DH2 — result: DH1 cells pooled over six coins

**Program:** `DIRECTIONAL_HYPOTHESES_DH2` (`DH2_POOLED_DESIGN.md`)
**Executed:** 2026-10-04, one shot. The preregistration was committed and pushed first (`1a4e354`; `DH2_PREREG.json` sha256 `cb8bef28…53b6`).
**Machine records:** `DH2_RESULT_DISCOVERY.json`, `DH2_RESULT_REPLICATION.json` (nothing to replicate)

```
DH2-L1 (spot-confirmed approach -> 4h hold)   INCONCLUSIVE             -1.75 pp, 95% CI -3.78..+0.36, Holm p 0.21
DH2-L3 (stale level -> 4h hold)               INCONCLUSIVE             -0.61 pp, 95% CI -3.49..+2.27, Holm p 0.67
DH2-B2 (spot share in a move -> barrier)      NO_INCREMENTAL_STRUCTURE +0.55 pp, 95% CI -1.78..+2.84, Holm p 0.64
PROMISING_PROTOTYPES = 0 | REPLICATION not opened | BOT_PROBABILITY_LINES = none
OBJECTS_2025_2026_USED = none | E1 / B2-06 untouched
```

## 1. What was tested

The three DH1 cells that were too small on BTC alone, pooled over BTC, ETH, BNB, XRP, DOGE and SOL (Binance USD-M and spot, 2020–2024):
- coin fixed effects;
- terciles within each coin;
- ISO-week clusters pooled across coins;
- Holm within each card.

The owner's decision overrides the atlas "no pooling to manufacture N" routing for this program only.

## 2. Results (discovery)

| Cell | N (state / comparator) | Rate state vs comparator | Adjusted shift | 95 % CI | Brier skill |
|---|---|---|---|---|---|
| DH2-L1 spot-confirmed approach | 16362 (13645 / 2717) | 45.2 % vs 46.1 % hold | −1.75 pp | −3.78 … +0.36 | +0.0001 |
| DH2-L3 stale level | 16373 (4777 / 11596) | 45.2 % vs 45.4 % hold | −0.61 pp | −3.49 … +2.27 | −0.0002 |
| DH2-B2 high spot share in a sharp move | 9629 (3143 / 6486) | 51.6 % vs 52.0 % move-direction edge first | +0.55 pp | −1.78 … +2.84 | −0.0001 |

**By coin** (descriptive; the coin gate passed with p 0.51–0.70, but its power is low, so heterogeneity could not be reliably assessed):

| Cell | BTC | ETH | BNB | XRP | DOGE | SOL |
|---|---|---|---|---|---|---|
| DH2-L1 | −5.1 | −3.6 | −2.3 | +1.1 | −2.9 | +0.8 |
| DH2-L3 | +3.9 | −2.0 | −1.5 | −0.2 | −4.5 | +0.3 |
| DH2-B2 | −3.3 | +3.5 | +0.3 | −0.4 | +0.5 | +0.6 |

**BTC alone** (descriptive, never gates):
- L1: −5.1 pp (CI −11.1 … +1.1);
- L3: +3.9 pp (−1.8 … +9.7);
- B2: −3.3 pp (−10.1 … +3.2).

## 3. Reading

- **Spot confirmation is not a good sign at a level.**
  - The trader belief is that a push into a level backed by spot buying breaks it more often. It did not hold.
  - If anything, spot-confirmed approaches held slightly *less* often, though not significantly.
  - A positive effect above +0.4 pp is excluded on the pooled data.
- **Stale vs fresh levels:** no detectable difference. Effects beyond about ±3.5 pp are excluded, and the coins disagree in sign.
- **Spot participation in a sharp move** does not change which edge is reached first. This is a clean null inside ±3 pp.
- **What this says about the bot.** For the bot's directional statements, none of these states makes the level or move probabilities more informative than "обычно". The honest output is what the bot already shows: the base rates with N, and no extra "probability up" line.

## 4. What the bot says

- **No probability line.** No «Гипотеза» and no «Проверено».
- **`/research` gets three `NOT_CONFIRMED` lines** (`config/beta_research_findings.yaml`: DH2-L1, DH2-L3, DH2-B2). Their priorities are above H02 and H03, so the alert texts do not change.

## 5. After DH1 and DH2

**Six cells were tested on free data, and none moved a directional probability by 3 pp.**
- DH1-L2 on BTC.
- DH2-L1, L3 and B2 pooled.
- DH1-L1 and L3 were contained in DH2.

**The defensible conclusion.** On objective levels and sharp moves, these spot/confluence/staleness states carry no directional information at the 3–4 pp scale on Binance 2020–2024. Smaller effects are not excluded for L1 and L3.

**Remaining routes** (each needs an owner go):
1. **Live tracking of the bot's own statements** (corridor, level base rates), which builds «Проверено» for what the bot already says. This is the most useful route.
2. **New mechanisms** rather than new states for the same endpoints. The atlas frontier still has order-book cells (OKX L2, deferred) and cross-venue cells.

## 6. Records

- `DH2_POOLED_DESIGN.md`
- `DH2_FEASIBILITY.{md,json}`
- `DH2_PREREG.json`
- `DH2_RESULT_{DISCOVERY,REPLICATION}.json`
- `SCIENTIFIC_TEST_LEDGER.json` (`TF-DH2-L-LEVEL-HOLD`, `TF-DH2-B-BARRIER`)
- `docs/research_data/DH2_*`
- `scripts/research/dh2/`
- `tests/research/test_dh2.py`
