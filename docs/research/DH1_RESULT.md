# DH1 — result: directional hypotheses for the bot

**Program:** `DIRECTIONAL_HYPOTHESES_DH1` (`DIRECTIONAL_HYPOTHESES_DECISION_V1.md`)
**Executed:** 2026-10-04, one shot. The preregistration was committed first (`3e584f3`; `DH1_PREREG.json` sha256 `20ee090c…ebe00`).
**Machine records:** `DH1_RESULT_DISCOVERY.json`, `DH1_RESULT_REPLICATION.json`

```
CANDIDATES               = 15 (9 closed at red team, 1 deferred, 5 to feasibility)
EXECUTABLE_AT_FEASIBILITY = DH1-L2 only (frozen rule: discovery MDE <= 6 pp)
DH1-L2 DISCOVERY          = INCONCLUSIVE (frozen class) — shift +0.05 pp, 95% CI -3.03..+3.06 pp, Brier skill -0.0008
REPLICATION               = nothing to replicate (no PROMISING_PROTOTYPE); no replication outcome read
PROMISING_PROTOTYPES      = 0 | SUPPORTED = 0
BOT_PROBABILITY_LINES     = none («Гипотеза» / «Проверено» need a passing cell)
OBJECTS_2025_2026_USED    = none | E1 / B2-06 untouched
```

## 1. What was asked

The owner asked for hypotheses that make the bot's directional percentages more informative, for example how often price holds beyond a level after its first touch. The bot would state them as «Гипотеза» or «Проверено». The aim is honest numbers, not maximum accuracy.

## 2. What was tested, and what was not

| Cell | Question | Feasibility | Result |
|---|---|---|---|
| DH1-L2 | Does a level that coincides with another level (a zone) hold differently from a lone level 4h after its first touch? | executable (N 4622, MDE 5.8 pp) | **no difference**: 46.5 % vs 46.3 % |
| DH1-L1 | Spot buying/selling on the approach to a level → hold | `INFORMATIONALLY_WEAK` (MDE 8.5 pp) | not run |
| DH1-L3 | Stale level (not traded for 24h) → hold | `INFORMATIONALLY_WEAK` (MDE 7.4 pp) | not run |
| DH1-B1 | Sharp 15-minute move confirmed by spot flow → which 4h barrier first | `INFORMATIONALLY_WEAK` | not run (see below) |
| DH1-B2 | High spot share in a sharp move → which barrier first | `INFORMATIONALLY_WEAK` (MDE 11 pp) | not run |

**DH1-B1 is degenerate as defined.** In 97.6 % of the sharp moves on 2020–2024, spot taker net flow pointed in the move's direction, so there was almost nothing to compare against (45 cases). The finding comes from outcome-blind counts and is useful by itself: in a sharp BTC move, spot takers almost always go the same way as the perp. A sign-based "spot does not confirm" state practically never happens.

## 3. DH1-L2 in numbers (discovery, Binance 2020–2024)

**Population:**
- 4622 first touches of the product's key levels (previous day/week/month high and low, round numbers, previous day's POC), 261 week clusters;
- 2049 confluent (another level kind within 0.15 %) and 2573 lone.

**Rates:**
- 4h hold: 46.5 % confluent vs 46.3 % lone; 46.4 % overall;
- after the nuisance adjustment (hour, 24h volatility, prior 4h return, level type): **+0.05 pp**, 95 % CI **−3.03 … +3.06 pp**, p 0.95;
- Brier skill of adding the state: −0.0008, so it does not improve the forecast.

**By year:** 2020 −6.9, 2021 +5.3, 2022 −0.3, 2023 −4.2, 2024 +1.2 pp. The heterogeneity test is not significant (p 0.13), and its power is low, so heterogeneity could not be reliably assessed at this N.

**Class.** The frozen rule calls a result `NO_INCREMENTAL_STRUCTURE` only when the whole 95 % interval lies inside ±3 pp. Here it reaches ±3.03 / 3.06 pp, so the class is `INCONCLUSIVE` by 0.03–0.06 pp. In plain terms, nothing was found, and a difference larger than about 3 pp is all but ruled out.

## 4. What the bot may say

- **No probability line.** No cell reached `PROMISING_PROTOTYPE`, so there is no «Гипотеза» or «Проверено» probability.
- **One `/research` line:** "a level in a zone held no more often than a lone level" (`config/beta_research_findings.yaml`, id `DH1-L2`, status `NOT_CONFIRMED`, priority 35). It is a popular trader belief that did not hold on 2020–2024. The level-alert line stays H02, which has the lower priority, so the alert text does not change.

## 5. What we learned

1. **The binding constraint is the number of events, not the idea.** One venue, one symbol and five years give about 900 level touches and about 375 sharp moves a year.
   - On discovery, a conditional state can show at most a 6–11 pp shift. On the free 2017–2019 era, the floor is 10–26 pp.
   - The owner's 3 pp bar is far below either.
   - "Проверено" for a 3–5 pp directional effect needs several thousand independent events. Live tracking alone gives about 900 level touches a year, so that is years of BTC data.
2. **Zones are not stronger levels.** At least, not in the 4h hold, on Binance 2020–2024.
3. **"Spot confirmation" as a sign is not a usable state in sharp moves.** Spot almost always follows. A usable version would need a relative measure (spot imbalance vs perp imbalance), which is a new candidate, not a repair.

## 6. Options for a next program (not started; each needs an owner go)

- **More events from free data.**
  - Pool the same level rules over other Binance USD-M symbols, 2020–2024: ETH (`CORE_ETH_BINANCE_V0` is pinned), SOL, BNB, XRP, DOGE.
  - This needs a homogeneity assumption across coins, stated up front. Alt 2020–2024 surfaces carry divergence/support exposure, which is fine for discovery but not for confirmation.
  - Confirmation would then be live tracking over several symbols.
- **A wider level population for the same cells (L1, L3):** session highs and lows, day/week/month opens, VWAP. The bot already shows these levels, so the claim would cover what it displays.
- **Relative spot intensity during sharp moves** (a new B-type candidate), with a frozen definition chosen outcome-blind.
- **Live tracking** of the bot's own level and corridor statements, which accumulates «Проверено» evidence for whatever the bot already shows.

## 7. Records

- `DIRECTIONAL_HYPOTHESES_DECISION_V1.md`
- `DH1_CANDIDATES.md`
- `DH1_FEASIBILITY.{md,json}`
- `DH1_PREREG.json`
- `DH1_RESULT_DISCOVERY.json`, `DH1_RESULT_REPLICATION.json`
- `SCIENTIFIC_TEST_LEDGER.json` (`TF-DH1-L-LEVEL-HOLD`)
- `docs/research_data/DH1_*`
- `scripts/research/dh1/`
- `tests/research/test_dh1.py`
