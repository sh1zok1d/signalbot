# LEVEL_RACE_FORECAST_V1 — held-out result (one-shot read)

**Stage:** the one held-out read of the frozen model (design §5, §11b–§11c). Evidence only; the claim decision follows the frozen rules. Machine-readable record: `LEVEL_RACE_FORECAST_V1_HELDOUT.json` (sha256 `6c6c5739314964d08e21a1727f9f90d6a35f34e725624b14c2ab6b7a236cbe34`).

## Provenance

- **Go:** architect, 2026-10-09T09:02:49Z, token `GO:454109c8b253`. Read plan red-teamed by the ОПГ-2 mini-head.
- **Run:** `python -c "from datetime import date; from scripts.research.level_race_forecast_v1 import heldout as HO; HO.run(date(2026,10,9), 'GO:454109c8b253')"`, run once, exit 0, 2026-10-09T09:02:57Z → 09:04:37Z.
- **Code:** clean worktree at main `bd35820bd89310b7e5db57b1afe5356bd79184f3`, recorded before the run (`git status --porcelain` empty). Frozen paths identical to the freeze merge `4c3b1a2a`.
- **Model:** `LEVEL_RACE_MODEL_V1.json`, sha256 `454109c8b2532906d54045b3f8fe3362afb0fb684cab18053ada1265d5480d3a`. Freeze commit `50eeb39b`, `FREEZE_DATE = 2026-10-09`.
- **Data:** 50 Binance USD-M BTCUSDT 5m kline objects via the product planner, each checksum-verified. The first is monthly 2024-12 (warm-up only); the last is daily 2026-10-08. The 2026-10-08 object was published at 09:01Z, with CHECKSUM `9963f007…59fe`, and all 50 HEADs returned 200 before the go. Plan output sha256 `0f91db6d…9d00`.
- **E1:** 11 objects refused before any request: monthly 2026-08 and daily 2026-08-16 … 08-25. The event span, generic anchors and incomplete periods around the gap were excluded as frozen.
- **Surface class:** `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`-like. The product's first-touch statistics had already read neighbouring outcomes on 2025/2026, so this read is not pristine.

## Information

| Landmark | Rows | AMBIGUOUS | Scored | Week clusters |
|---|---|---|---|---|
| T0 | 700 | 2 | 698 | 92 |
| T15 | 564 | 0 | 564 | 92 |

Generic stream: 60 919 rows (hourly anchors × 4 pairs) feed the calibrator.

## Evidence (raw outputs; log-loss gain in nats per event, week-clustered 95 % interval)

| Comparison | T0 | T15 |
|---|---|---|
| M1 vs B0 | +0.010 (−0.018 … +0.038) | −0.000 (−0.027 … +0.027) |
| M1 vs G1@event | +0.052 (+0.013 … +0.090) | +0.024 (−0.014 … +0.062) |
| G1@event vs B0 | −0.042 (−0.056 … −0.027) | −0.024 (−0.042 … −0.007) |

**Case by the frozen rule (§11b, Q6).** Case A requires the M1 gain over raw B0 and over raw G1@event to have intervals above 0. The interval over B0 includes 0 at both landmarks, so both T0 and T15 are **case B**.

**Published probabilities (case B = fallback: G1@event with the GENERIC calibration, prequential, 32 calibrator versions) against the frozen gates:**

| Gate | T0 | T15 |
|---|---|---|
| G0 (≥ 200) | 698, pass | 564, pass |
| G1: upper 95 % end of LL_published − LL_B0 ≤ 0.02 | +0.080, upper +0.102, fail | +0.059, upper +0.084, fail |
| G2 CITL BREAK (pp, 95 %) | +11.2 (+8.2 … +14.1), fail | +8.5 (+5.2 … +11.8), fail |
| G2 CITL REJECT | +7.6 (+4.1 … +11.2), fail | +7.2 (+3.4 … +11.1), fail |
| G2 CITL NEITHER | −18.8 (−22.3 … −15.3), fail | −15.7 (−19.6 … −11.8), fail |
| G3 slope head R (95 %) | 0.80 (0.22 … 1.38), pass | 1.24 (0.64 … 1.85), pass |
| G3 slope head B (95 %) | 0.87 (0.63 … 1.11), pass | 0.85 (0.65 … 1.05), pass |
| Fallback passes G2 | no | no |
| **State at the switch (frozen rules)** | **HIST** | **HIST** |

## Interpretation (not a claim)

- **B0 vs M1 against the development record.** On held-out level events, raw B0 is close to M1 at both landmarks. The development gain of +0.034 / +0.020 nats (T0 / T15) did not reappear beyond its interval.
- **Generic stream.** The generic-stream model G1 on level geometry is worse than B0 at both landmarks, as in development. The fallback under-predicts resolution at structural first touches: the NEITHER CITL is −19 / −16 pp, near the development diagnostic of −12.6 pp. This is a calibration gap of the generic fallback on level events; it is not a level-offset claim (§6b requires M1 to beat B0 and G1@event).
- **M1 over G1@event.** M1 still beats G1@event at T0, but by the frozen rule that does not make case A.
- **Level offset.** No level offset is claimed, internally or in text.
- **Display.** The model states would not display at either landmark. The Day-0 history line (HIST V1) stays the display.

## Claim decision

None. Level offset not claimed (§11b). No L3 state is reached; `level_race.model_states_enabled` stays off, and the frozen rules would place both classes in `HIST`. No user-facing change, journal write or flag change was made by this read. The C1 challenger was not evaluated (no venue data in this read).

## Limitations

- The surface was already exposed (class B).
- The week-clustered intervals rest on 92 clusters.
- The case decision was made on raw outputs, and the gates on the published fallback.
- T15 is nested in T0: the same events with nested windows, so the two landmarks are not independent evidence.
- One held-out surface; the E1-RUN-001 holdout is excluded; 2 AMBIGUOUS T0 events.
- No era adjustment was made, by design.
- The generic stream is a calibration feed only.

## Search exposure

One read, one frozen model, one frozen rule set. No variant, refit or rerun.
