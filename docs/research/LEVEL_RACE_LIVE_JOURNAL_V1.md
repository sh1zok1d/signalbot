# LEVEL_RACE_LIVE_JOURNAL_V1 — the L3 shadow journal and the C1 live input

Track F2 of ОПГ-2 (ORCHESTRATION_V1). It applies `docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.md` §7, §8 and §10 and FORECAST_LAYER_DECISION_V1 §5 and §7 to the live journal. It is written before any live L3 or C1 record exists and before any outcome of the records it governs is read. A change to it is a new version, not an edit.

Code: `beta/level_race_live.py` (`model_row`, `c1_block`, `c1_due`, `load_venue_closes`, `calibrator_version_at`, `report`) and `beta/claims.py` (`level_race_l3_claims`, `record_level_race_l3`).

## 1. When records are written

- Classes `L3_LEVEL_RACE_T0_4H` and `L3_LEVEL_RACE_T15_4H`, rule `LEVEL_RACE_4H_V1`.
- The events are the same eligible structural first touches and landmarks as the HIST records (`due_landmarks`). One record per event × landmark, whether it is shown or not.
- The journal starts at the model freeze: `level_race_live.MODEL_VERSION` is set, and the frozen model side is wired as `PROVIDER`. It runs whatever the display state (HIST included) and needs `level_race.journal_enabled`.
  - Before the freeze nothing is written.
  - It does not depend on `level_race.model_states_enabled`, so the prospective record exists from the freeze (design §8a and §11a).
- First write wins on (class, subject, landmark slot). A record is never rewritten or recomputed.

## 2. What a record holds

`subject`: the event, the landmark, the barrier prices, the window end, the frozen `model_version`, the calibrator version that applies at the landmark (F3's `calibrator_at`), and from F3's `display_contract`: the state, case, state reason and `since`, template ids, the probabilities source and the state version. Also the build SHA.

`numbers`:
- `inputs`: the model row as read (`model_row`) plus `OVMM`.
- `event_b0`.
- `raw` and `published` probabilities (up / dn / neither).
- `c1`: the C1 block as read:
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
- A T15 L3 record is written at the first run where all six closes are present, or at the first run at or after **landmark + 3 minutes** (`C1_WAIT_MS`) with C1 missing, whichever comes first.
- Until then the record is deferred and counted (`l3_deferred`). Three minutes is inside the 10-minute landmark write window.
- T0 records do not wait: C1 is 0 at T0.
- Waiting reads nothing after the landmark and changes no number other than the presence of C1. The champion's inputs and probabilities are the same whenever the record is written.

## 4. Missing C1 (declared before data)

- A missing close is never filled, carried forward or rebuilt from another source. A gap-fill that later rewrites `klines_1m` does not touch a written record.
- `report` gives, per T15 class, the number of records, the number complete and `missing_by_venue`. The writer logs the same counts each run (`c1_missing`).
- The C1 paired comparison (design §8, FORECAST_LAYER §7) uses only T15 records with C1 complete. A record with C1 missing is not a pair and does not count toward the 150 paired events.
- Selection check, reported beside every C1 look and changing no rule: the champion's published log loss and the outcome shares on the excluded records against those on the pairs, with N.
- The champion's own metrics, states and monitors use every record, C1 complete or not. A missing C1 is never a D0 data fault for the champion.

## 5. Not here

- The frozen predictor, the calibrator versions and the state machine. They come from F1 (freeze) and F3 (`beta/level_race_calibration.py`) through their public functions.
- The display of the model states.
- The generic stream `L3_GENERIC_RACE_4H`.

The L3 templates of design §9 are in the catalog (`lr_l3h_v1` … `lr_push_off_v1`) because every L3 record carries their digest. Nothing displays them until `level_race.model_states_enabled`.
