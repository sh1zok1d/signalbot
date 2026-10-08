# LEVEL_RACE_LIVE_JOURNAL_V1 — the L3 shadow journal and the C1 live input

Track F2 of ОПГ-2 (ORCHESTRATION_V1). It applies `docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.md` §7, §8 and §10 and FORECAST_LAYER_DECISION_V1 §5 and §7 to the live journal. It is written before any live L3 or C1 record exists and before any outcome of the records it governs is read. A change to it is a new version, not an edit.

Code: `beta/level_race_live.py` (`model_row`, `c1_block`, `c1_due`, `load_venue_closes`, `calibrator_version_at`, `report`) and `beta/claims.py` (`level_race_l3_claims`, `level_race_c1_claims`, `record_level_race_l3`).

## 1. When records are written

- **Champion:** classes `L3_LEVEL_RACE_T0_4H` and `L3_LEVEL_RACE_T15_4H`, rule `LEVEL_RACE_4H_V1`.
  - One record per eligible structural first touch × landmark, for the same events and landmarks as the HIST records (`due_landmarks`), shown or not.
  - It is written at the **first run after the landmark**.
  - It never reads, waits for or carries C1. A missing venue or a failed venue read cannot delay it or change it.
- **C1 shadow:** class `L3_LEVEL_RACE_C1_T15_4H`, rule `LEVEL_RACE_4H_V1`, journal only, never shown.
  - One record per T15 champion record, with the same subject key and slot, which pairs them.
  - It is written under the wait rule of §3.
  - There are no C1 records at T0: OVMM is 0 there and the term enters head B on T15 rows only (design §8).
- **When the journal starts:** at the model freeze, once `level_race_live.MODEL_VERSION` is set and the frozen model side is wired as `PROVIDER`.
  - It runs whatever the display state (HIST included) and needs `level_race.journal_enabled`.
  - Before the freeze nothing is written.
  - It does not depend on `level_race.model_states_enabled`, so the prospective record exists from the freeze (design §8a and §11a).
- First write wins on (class, subject, landmark slot). A record is never rewritten or recomputed.

## 2. What a record holds

**Champion `subject`:**
- the event, the landmark, the barrier prices, the window end;
- the frozen `model_version`;
- the calibrator version that applies at the landmark (F3's `calibrator_at`);
- from F3's `display_contract`: the state, case, state reason and `since`, template ids, the probabilities source and the state version;
- the build SHA.

**Champion `numbers`:** `inputs` (the model row as read, `model_row`), `event_b0`, and `raw` and `published` probabilities (up / dn / neither).

**C1 shadow `numbers`:**
- `inputs` (the model row plus `OVMM`) and `event_b0`;
- C1's `raw` and `published` probabilities, or none when C1 is missing;
- `c1`, the block as read:
  - `value`;
  - the six closes (Binance, Bybit and OKX at close(j−1) and close(j+2));
  - their instants;
  - the read instant (`read_ms` / `read_at`);
  - `missing`, the list of venues without both closes, in the order binance, bybit, okx.

## 3. C1 ingestion wait (frozen)

The two closes sit at fixed instants at or before the T15 landmark: close(j−1) is the touch-bar open and close(j+2) is the landmark itself.
- Live, each is the close of the 1m bar ending at that instant. Stage-1 writes that bar to `klines_1m` only after it closes, when the next minute's first trade arrives.
- The notifier runs every minute at :40 s, so the first run after a landmark is landmark + 40 s.

Rule:
- The C1 shadow record is written at the first run where all six closes are present, or at the first run at or after **landmark + 3 minutes** (`C1_WAIT_MS`) with C1 missing, whichever comes first.
- Until then it is deferred and counted (`c1_deferred`). Three minutes is inside the 10-minute landmark write window.
- Waiting reads nothing after the landmark and changes nothing but whether C1 is present.

## 4. Missing C1 (declared before data)

- A missing close is never filled, carried forward or rebuilt from another source. A missing C1 gets no C1 forecast. A gap-fill that later rewrites `klines_1m` does not touch a written record.
- `report` gives, for the C1 class, the number of records, the number complete and `missing_by_venue`. The writer logs the same counts each run (`c1_missing`).
- **Pairs.** The C1 paired comparison (design §8, FORECAST_LAYER §7) uses only T15 champion records whose C1 shadow record has C1 complete. A record with C1 missing is not a pair and does not count toward the 150 paired events.
- **Selection check (statistic frozen here, reported beside every C1 look, changes no rule).**
  - Population: the scored T15 champion records of the look (AMBIGUOUS excluded and counted). They split into E (C1 missing) and I (C1 complete).
  - Reported:
    1. N and the week clusters of E and of I, and the share of E overall and per missing venue.
    2. The difference of the champion's published mean log loss, `mean_E − mean_I`, in nats per event, with a 95 % interval: a week-cluster bootstrap of the T15 records (product week, Monday 00:00 UTC), 2000 draws, seed `20261008`, percentile interval.
    3. The observed outcome shares (UP / DN / NEITHER) in E and in I, each with N, and the differences E − I in pp with the same bootstrap's 95 % intervals.
  - With fewer than 10 records in E, items 2–3 are reported as counts only.
- The champion's own metrics, states and monitors use every record, C1 complete or not. A missing C1 is never a D0 data fault for the champion.

## 5. Not here

- The frozen predictor, the calibrator versions and the state machine. They come from F1 (freeze) and F3 (`beta/level_race_calibration.py`) through their public functions.
- The display of the model states.
- The generic stream `L3_GENERIC_RACE_4H`.

The L3 templates of design §9 are in the catalog (`lr_l3h_v1` … `lr_push_off_v1`) because every L3 record carries their digest. Nothing displays them until `level_race.model_states_enabled`.
