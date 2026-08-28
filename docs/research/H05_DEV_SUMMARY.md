# H05 Taker Imbalance → Subsequent Return — Development Results

**Status:** FROZEN_EVIDENCE / EXPLORATORY
**Hypothesis ID:** `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN`
**Machine promotion verdict:** `H05_REJECTED_SPECIFIC_CLAIM`
**Formal first-run status:** `C. H05_DEVELOPMENT_NOT_PROMOTED`
**Machine-readable:** `docs/research/H05_DEV_RESULTS.json` (exact runner output; numerical values not edited)
**Runner markdown:** `docs/research/H05_DEV_SUMMARY.runner.md` (byte-for-byte copy of the frozen CLI summary)
**Run provenance:** `docs/research/H05_RUN_PROVENANCE.json`
**Preregistration:** `docs/research/H05_TAKER_IMBALANCE_PREREG.md`

This document records the one authorized development-only outcome inspection of frozen H05. It is not confirmatory, not a trading system, not a preferred-sign selection, and not authorization to open 2025 validation, 2026 OOS, Batch01 synthesis, or H06.

The canonical formal decision is `results["promotion"]` from frozen `evaluate_promotion`. No human alternative is constructed.

H01 remains `H01_KILL`. H02 remains `H02_KILL`. H03 remains `H03_REJECTED_SPECIFIC_CLAIM`. H04 remains `H04_REJECTED_SPECIFIC_CLAIM`. None is reinterpreted here.

## Identity

| Field | Value |
|---|---|
| dataset | `CORE_BTC_BINANCE_V0` |
| snapshot_id | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| dataset root | `/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0` |
| snapshot manifest | `/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0/reports/snapshot_manifest.json` |
| selected partitions | 60 monthly files `2020-01.parquet` … `2024-12.parquet` |
| H05 design SHA | `deaf6503896920685f25a03230174d360a07ab9a` |
| H05_PREREG_SHA | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| H05_RESEARCH_CODE_FREEZE_SHA | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| Git HEAD at outcome run | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| research_code_sha in JSON | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| prereg_commit_sha in JSON | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| generated_at_utc | `2026-08-27T21:23:46Z` |
| run start UTC | `2026-08-27T21:22:22Z` (provenance) |
| development window | 2020-02-01T00:00:00Z → 2025-01-01T00:00:00Z |
| warmup_start_inclusive | 2020-01-01T00:00:00Z |
| t_max_inclusive | 2024-12-31T19:45:00Z |
| 2025 validation inspected | NO |
| 2026 OOS inspected | NO |
| Python | 3.12.3 |
| numpy | 2.1.3 |
| pandas | 2.2.3 |
| pyarrow | 17.0.0 |
| H05_DEV_RESULTS.json SHA256 | `37794ba525212681d0687cf4d35f9c5bf775ff63171c9efdb1b25a3acd947011` |

HEAD at the outcome run was the freeze SHA. No H05 source, test, or preregistration file was modified before or after the run.

Exact command, once:

```
PYTHONPATH=/tmp/signalbot python3 scripts/research/h05_taker_imbalance.py \
  --stage dev-run \
  --dataset-root /tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0 \
  --out-dir /tmp/signalbot/artifacts/h05 \
  --prereg-commit-sha faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1
```

## Search surface

3 lookbacks (`W=15/30/60`) × 3 nested percentiles (`q=0.80/0.90/0.95`) × 5 horizons (`H=15/30/60/120/240`) = **45 primary cells**.

Both preregistered orientations evaluated on the same 45 cells:

- continuation `S = +1`
- reversal `S = -1`

Sign multiplicity is disclosed separately from the 45-cell / Batch01 225-cell count. Anti-cherry-pick: a sign may not be selected because the other failed first.

Matched-random seed `20260904` × 100. Week-block bootstrap seed `20260905` × 2000, plus fixed 1w/2w/4w sensitivity. MPIE 0.10 vs matched-random. `CONTROL_DELTA_MIN=0.05` for overlap structural delta and same-support +6h.

## Formal promotion result (machine output, not reinterpreted)

```json
{
  "continuation": {
    "promoted": false,
    "promoted_cells": []
  },
  "reversal": {
    "promoted": false,
    "promoted_cells": []
  },
  "verdict": "H05_REJECTED_SPECIFIC_CLAIM"
}
```

Neither orientation promoted. Verdict is not `AUDIT_FAILURE_BOTH_SIGNS_PROMOTED`. Formal first-run status is therefore **`C. H05_DEVELOPMENT_NOT_PROMOTED`**.

## Search completeness / integrity

| Check | Result |
|---|---|
| expected cells | 45 |
| observed unique W/q/H cells | 45 |
| continuation evaluated | YES |
| reversal evaluated | YES |
| machine `results["promotion"]` present | YES |
| year_breakdown years | 2020, 2021, 2022, 2023, 2024 (all five; none excluded) |
| concentration months | 2020-02 … 2024-12 (59 months; January 2020 is warmup) |
| 2025 partition in results | NO |
| 2026 partition in results | NO |
| `forbidden_windows_inspected` | `{"2025": false, "2026": false}` |
| `windows.validation_untouched` | true |
| `windows.oos_untouched` | true |
| unmatched candidate share | 0 … 0.00082 |
| raw outputs persisted | YES |

## Gate summary (descriptive counts over 45 cells)

Per-cell full-gate conjunction is frozen `_cell_all_gates_pass`: primary ∧ MPIE ∧ structural ∧ +6h ∧ bootstrap 1w ∧ 2w ∧ 4w ∧ year 4/5 ∧ BUY/SELL symmetry.

| Gate | Continuation (S=+1) | Reversal (S=-1) |
|---|---|---|
| primary `S * candidate_mean > 0` | 9 / 45 | 36 / 45 |
| MPIE `S * matched_delta >= 0.10` | 0 / 45 | 0 / 45 |
| structural `S * structural_delta >= 0.05` | 0 / 45 | 0 / 45 |
| +6h `S * shift_delta >= 0.05` | 0 / 45 | 9 / 45 |
| bootstrap 1w | 0 / 45 | 8 / 45 |
| bootstrap 2w | 0 / 45 | 8 / 45 |
| bootstrap 4w | 0 / 45 | 7 / 45 |
| year 4/5 | 2 / 45 | 22 / 45 |
| BUY/SELL (`direction_symmetry_gate`) | 0 / 45 | 8 / 45 |
| BUY oriented-primary only | 37 / 45 | 8 / 45 |
| SELL oriented-primary only | 0 / 45 | 45 / 45 |
| full per-cell conjunction | 0 / 45 | 0 / 45 |

## Robustness summary (frozen rules)

q and H adjacency are evaluated on **full per-cell gate-passing**, not on primary-only. W uses the frozen weaker adjacent **directional** rule (`ORIENTED_PRIMARY>0` AND `ORIENTED_MATCHED_DELTA>0` AND `ORIENTED_STRUCTURAL_DELTA>0`, magnitude thresholds not required).

| Rule | Continuation | Reversal |
|---|---|---|
| q adjacent full-gate pair support (cells sitting in such a neighborhood) | 0 / 45 | 0 / 45 |
| H adjacent full-gate pair support | 0 / 45 | 0 / 45 |
| W adjacent directional support (frozen neighbor rule) | 6 / 45 | 28 / 45 |
| cells with `directional_support=True` | 3 / 45 | 23 / 45 |

q adjacency and H adjacency are both **0** because **0** cells pass the full per-cell conjunction. W directional neighborhood exists for some cells (especially reversal) and **does not promote**: promotion still requires own full-gate pass plus q and H full-gate adjacency.

## All 45 primary cells

cand_mean = candidate mean of `X = NORM_TAKER_RET_H` (not multiplied by S in storage). matched_delta = candidate_minus_matched. struct_cand / struct_ctrl are the overlap like-with-like standardized means. +6h_cand / shifted_mean / shift_delta use the same-support estimand. boot C = continuation lower-bound>0; boot R = reversal upper-bound<0. years = count of 2020–2024 with `S * yearly_mean > 0`. BUY_ori / SELL_ori = oriented primary on that D side. C_full / R_full = full frozen per-cell conjunction.

| W | q | H | N | cand_mean | matched_mean | matched_delta | struct_cand | struct_ctrl | struct_delta | +6h_cand | shifted_mean | shift_delta | boot1w C/R | boot2w C/R | boot4w C/R | years C/R | BUY_ori C/R | SELL_ori C/R | C_full | R_full |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 0.80 | 15 | 20696 | -0.0304 | -0.0029 | -0.0275 | -0.0313 | -0.0001 | -0.0313 | -0.0304 | +0.0089 | -0.0393 | N/N | N/N | N/N | 0/5 | Y/N | N/Y | N | N |
| 15 | 0.80 | 30 | 20696 | -0.0429 | -0.0011 | -0.0418 | -0.0431 | -0.0405 | -0.0026 | -0.0429 | +0.0040 | -0.0469 | N/Y | N/Y | N/Y | 1/4 | Y/N | N/Y | N | N |
| 15 | 0.80 | 60 | 20696 | -0.0395 | -0.0055 | -0.0340 | -0.0396 | -0.0417 | +0.0021 | -0.0395 | -0.0037 | -0.0358 | N/Y | N/Y | N/Y | 0/5 | Y/N | N/Y | N | N |
| 15 | 0.80 | 120 | 20696 | -0.0388 | -0.0061 | -0.0327 | -0.0391 | -0.0257 | -0.0135 | -0.0388 | -0.0100 | -0.0288 | N/Y | N/Y | N/Y | 1/4 | Y/N | N/Y | N | N |
| 15 | 0.80 | 240 | 20696 | -0.0070 | -0.0101 | +0.0031 | -0.0069 | +0.0171 | -0.0240 | -0.0070 | +0.0064 | -0.0134 | N/N | N/N | N/N | 3/2 | Y/N | N/Y | N | N |
| 15 | 0.90 | 15 | 12627 | -0.0227 | +0.0026 | -0.0253 | -0.0229 | -0.0049 | -0.0180 | -0.0227 | +0.0325 | -0.0552 | N/N | N/N | N/N | 0/5 | Y/N | N/Y | N | N |
| 15 | 0.90 | 30 | 12627 | -0.0418 | +0.0011 | -0.0429 | -0.0416 | -0.0466 | +0.0050 | -0.0418 | +0.0450 | -0.0868 | N/Y | N/Y | N/Y | 0/5 | N/Y | N/Y | N | N |
| 15 | 0.90 | 60 | 12627 | -0.0220 | -0.0031 | -0.0189 | -0.0213 | -0.0420 | +0.0207 | -0.0220 | +0.0268 | -0.0488 | N/N | N/N | N/N | 0/5 | Y/N | N/Y | N | N |
| 15 | 0.90 | 120 | 12627 | -0.0223 | -0.0067 | -0.0156 | -0.0219 | -0.0280 | +0.0061 | -0.0223 | +0.0184 | -0.0407 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 15 | 0.90 | 240 | 12627 | +0.0098 | -0.0083 | +0.0181 | +0.0100 | +0.0160 | -0.0060 | +0.0098 | +0.0373 | -0.0276 | N/N | N/N | N/N | 3/2 | Y/N | N/Y | N | N |
| 15 | 0.95 | 15 | 7226 | -0.0518 | +0.0000 | -0.0519 | -0.0518 | -0.0064 | -0.0455 | -0.0518 | +0.0333 | -0.0851 | N/Y | N/Y | N/Y | 1/4 | N/Y | N/Y | N | N |
| 15 | 0.95 | 30 | 7226 | -0.0348 | -0.0000 | -0.0348 | -0.0348 | -0.0475 | +0.0128 | -0.0348 | +0.0466 | -0.0814 | N/N | N/N | N/N | 1/4 | N/Y | N/Y | N | N |
| 15 | 0.95 | 60 | 7226 | -0.0111 | -0.0078 | -0.0033 | -0.0111 | -0.0394 | +0.0283 | -0.0111 | +0.0168 | -0.0279 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 15 | 0.95 | 120 | 7226 | -0.0441 | -0.0073 | -0.0369 | -0.0441 | -0.0277 | -0.0164 | -0.0441 | +0.0101 | -0.0542 | N/Y | N/Y | N/N | 1/4 | Y/N | N/Y | N | N |
| 15 | 0.95 | 240 | 7226 | +0.0126 | -0.0114 | +0.0239 | +0.0126 | +0.0186 | -0.0060 | +0.0126 | +0.0090 | +0.0036 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 30 | 0.80 | 15 | 18921 | -0.0336 | -0.0017 | -0.0319 | -0.0340 | -0.0276 | -0.0064 | -0.0336 | +0.0015 | -0.0351 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 30 | 0.80 | 30 | 18921 | -0.0417 | -0.0030 | -0.0387 | -0.0418 | -0.0291 | -0.0127 | -0.0417 | +0.0096 | -0.0513 | N/Y | N/Y | N/Y | 1/4 | N/Y | N/Y | N | N |
| 30 | 0.80 | 60 | 18921 | -0.0214 | -0.0048 | -0.0166 | -0.0214 | -0.0138 | -0.0076 | -0.0214 | +0.0065 | -0.0279 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 30 | 0.80 | 120 | 18921 | -0.0218 | -0.0101 | -0.0118 | -0.0221 | -0.0033 | -0.0188 | -0.0218 | +0.0124 | -0.0342 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 30 | 0.80 | 240 | 18921 | +0.0135 | -0.0109 | +0.0244 | +0.0133 | +0.0166 | -0.0033 | +0.0135 | +0.0171 | -0.0036 | N/N | N/N | N/N | 4/1 | Y/N | N/Y | N | N |
| 30 | 0.90 | 15 | 11377 | -0.0231 | +0.0012 | -0.0243 | -0.0235 | -0.0359 | +0.0124 | -0.0231 | -0.0031 | -0.0200 | N/N | N/N | N/N | 2/3 | N/Y | N/Y | N | N |
| 30 | 0.90 | 30 | 11377 | -0.0385 | +0.0006 | -0.0391 | -0.0385 | -0.0386 | +0.0001 | -0.0385 | -0.0108 | -0.0277 | N/N | N/N | N/N | 2/3 | N/Y | N/Y | N | N |
| 30 | 0.90 | 60 | 11377 | -0.0440 | -0.0005 | -0.0436 | -0.0439 | -0.0211 | -0.0228 | -0.0440 | -0.0189 | -0.0251 | N/Y | N/Y | N/Y | 1/4 | Y/N | N/Y | N | N |
| 30 | 0.90 | 120 | 11377 | -0.0142 | -0.0039 | -0.0103 | -0.0144 | -0.0092 | -0.0052 | -0.0142 | +0.0052 | -0.0194 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 30 | 0.90 | 240 | 11377 | +0.0342 | -0.0092 | +0.0434 | +0.0339 | +0.0109 | +0.0229 | +0.0342 | +0.0066 | +0.0276 | N/N | N/N | N/N | 3/2 | Y/N | N/Y | N | N |
| 30 | 0.95 | 15 | 6512 | +0.0025 | -0.0004 | +0.0029 | +0.0025 | -0.0372 | +0.0397 | +0.0025 | +0.0003 | +0.0022 | N/N | N/N | N/N | 3/2 | Y/N | N/Y | N | N |
| 30 | 0.95 | 30 | 6512 | -0.0207 | -0.0062 | -0.0146 | -0.0207 | -0.0399 | +0.0192 | -0.0207 | -0.0178 | -0.0030 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 30 | 0.95 | 60 | 6512 | -0.0315 | -0.0111 | -0.0204 | -0.0315 | -0.0224 | -0.0091 | -0.0315 | -0.0188 | -0.0127 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 30 | 0.95 | 120 | 6512 | -0.0169 | -0.0097 | -0.0071 | -0.0169 | -0.0135 | -0.0034 | -0.0169 | +0.0122 | -0.0291 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 30 | 0.95 | 240 | 6512 | +0.0317 | -0.0101 | +0.0418 | +0.0317 | +0.0105 | +0.0212 | +0.0317 | +0.0133 | +0.0184 | N/N | N/N | N/N | 3/2 | Y/N | N/Y | N | N |
| 60 | 0.80 | 15 | 15864 | -0.0001 | -0.0019 | +0.0019 | -0.0001 | -0.0153 | +0.0151 | -0.0001 | +0.0095 | -0.0096 | N/N | N/N | N/N | 3/2 | Y/N | N/Y | N | N |
| 60 | 0.80 | 30 | 15864 | -0.0366 | -0.0036 | -0.0329 | -0.0367 | +0.0030 | -0.0397 | -0.0366 | -0.0035 | -0.0330 | N/N | N/N | N/N | 1/4 | N/Y | N/Y | N | N |
| 60 | 0.80 | 60 | 15864 | -0.0238 | -0.0045 | -0.0193 | -0.0243 | +0.0057 | -0.0300 | -0.0238 | +0.0039 | -0.0277 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 60 | 0.80 | 120 | 15864 | -0.0225 | -0.0052 | -0.0173 | -0.0228 | +0.0060 | -0.0288 | -0.0225 | +0.0235 | -0.0460 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 60 | 0.80 | 240 | 15864 | +0.0201 | -0.0093 | +0.0294 | +0.0199 | +0.0247 | -0.0048 | +0.0201 | +0.0400 | -0.0199 | N/N | N/N | N/N | 4/1 | Y/N | N/Y | N | N |
| 60 | 0.90 | 15 | 9210 | -0.0015 | -0.0042 | +0.0027 | -0.0010 | -0.0164 | +0.0154 | -0.0015 | -0.0361 | +0.0346 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 60 | 0.90 | 30 | 9210 | -0.0311 | -0.0004 | -0.0307 | -0.0309 | +0.0022 | -0.0331 | -0.0311 | -0.0376 | +0.0065 | N/N | N/N | N/N | 2/3 | N/Y | N/Y | N | N |
| 60 | 0.90 | 60 | 9210 | -0.0098 | -0.0005 | -0.0093 | -0.0099 | +0.0083 | -0.0182 | -0.0098 | -0.0017 | -0.0082 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 60 | 0.90 | 120 | 9210 | -0.0098 | -0.0015 | -0.0082 | -0.0097 | +0.0106 | -0.0203 | -0.0098 | +0.0331 | -0.0429 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 60 | 0.90 | 240 | 9210 | +0.0207 | -0.0040 | +0.0248 | +0.0209 | +0.0254 | -0.0046 | +0.0207 | +0.0449 | -0.0241 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 60 | 0.95 | 15 | 5228 | -0.0165 | +0.0058 | -0.0223 | -0.0162 | -0.0262 | +0.0100 | -0.0165 | +0.0007 | -0.0172 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 60 | 0.95 | 30 | 5228 | -0.0442 | +0.0040 | -0.0482 | -0.0440 | -0.0076 | -0.0364 | -0.0442 | -0.0148 | -0.0293 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 60 | 0.95 | 60 | 5228 | -0.0190 | -0.0012 | -0.0178 | -0.0189 | +0.0016 | -0.0205 | -0.0190 | +0.0443 | -0.0633 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |
| 60 | 0.95 | 120 | 5228 | -0.0254 | -0.0013 | -0.0241 | -0.0250 | +0.0020 | -0.0270 | -0.0254 | +0.0677 | -0.0931 | N/N | N/N | N/N | 1/4 | Y/N | N/Y | N | N |
| 60 | 0.95 | 240 | 5228 | +0.0120 | -0.0067 | +0.0186 | +0.0122 | +0.0237 | -0.0115 | +0.0120 | +0.0623 | -0.0504 | N/N | N/N | N/N | 2/3 | Y/N | N/Y | N | N |

## Failure attribution (diagnosis, not hypothesis modification)

H05 is **not promoted**. Universal blockers on both signs:

1. **no MPIE** — 0/45 cells satisfy `S * matched_delta >= 0.10`. Largest reversal oriented matched delta is ≈ 0.0519 (`W=15`, `q=0.95`, `H=15`), still below 0.10. Largest continuation oriented matched delta is ≈ 0.0434 (`W=30`, `q=0.90`, `H=240`).
2. **structural failure** — 0/45 cells satisfy `S * structural_delta >= 0.05` on the audited overlap estimand. Largest reversal oriented structural delta is ≈ 0.0455 (same `W=15 q=0.95 H=15` cell). Largest continuation oriented structural delta is ≈ 0.0397 (`W=30`, `q=0.95`, `H=15`).
3. **full per-cell conjunction 0/45** on both signs, therefore **q robustness 0** and **H robustness 0**.

Continuation-specific additional failures:

- **no primary effect on most of the surface** — only 9/45 cells have `candidate_mean > 0`; 36/45 are negative (reversal-leaning on the stored X).
- **BUY/SELL asymmetry** — SELL oriented-primary is 0/45 for continuation (`SELL` mean is negative in every cell). `direction_symmetry_gate` 0/45.
- **dependence/bootstrap failure** — 0/45 at 1w, 2w, and 4w.
- **yearly instability** — year gate 2/45.
- **+6h failure** — 0/45.
- **W isolation** relative to promotion: only 3 cells have directional_support; 6 sit next to a directionally-supporting W. That is irrelevant without MPIE/structural/full gates.

Reversal-specific additional failures:

- **BUY/SELL asymmetry** — SELL oriented-primary is 45/45; BUY oriented-primary is only 8/45; `direction_symmetry_gate` 8/45.
- **+6h** passes 9/45 but never together with MPIE+structural.
- **bootstrap** passes 8/45 (1w/2w) and 7/45 (4w) but never together with MPIE+structural.
- **yearly** passes 22/45; still not a promoting neighborhood because MPIE/structural/full gates are 0.
- W adjacent directional support 28/45 is **not** a promotion path under the frozen evaluator.

This is not an audit failure: `evaluate_promotion` returned `H05_REJECTED_SPECIFIC_CLAIM` with both `promoted=false` and empty `promoted_cells`.

## POST-HOC DESCRIPTIVE — NOT PART OF H05 ACCEPTANCE

The following does not change the H05 verdict.

- Largest |candidate_mean| cells are negative (reversal-leaning on stored X) at short-to-medium H and higher q: `W=15 q=0.95 H=15` (−0.0518), `W=60 q=0.95 H=30` (−0.0442), `W=15 q=0.95 H=120` (−0.0441), `W=30 q=0.90 H=60` (−0.0440).
- Strongest matched separation on the reversal orientation is the same short-H high-q region and still below MPIE 0.10.
- Continuation-leaning cells concentrate at `H=240` (8 of the 9 primary-positive continuation cells). Those cells have positive BUY means and negative SELL means, so they fail direction symmetry.
- SELL-side means are negative in all 45 cells. BUY-side means are positive in 37/45. That is a directional split, not a two-sided claim.
- Structural unmatched share is negligible (max 0.00082). Failure is not an overlap-support artifact.
- `+6h` collision fraction ranges ≈ 0.07–0.22.

Each of the above is **`POSTHOC_UNTESTED`**. None may rescue H05, choose a sign, drop a year, or start a child test in this task.

## Development verdict

**`H05_REJECTED_SPECIFIC_CLAIM`** — extreme taker imbalance as a subsequent-return continuation or reversal claim, as preregistered (45 cells, both signs, MPIE 0.10, overlap structural 0.05, same-support +6h 0.05, 1w/2w/4w bootstrap, 4/5 years, BUY and SELL, adjacent q, adjacent H, adjacent-W directional support), did not earn promotion.

Do not choose continuation or reversal after the fact. Do not retune q/W/H. Do not drop years. Do not inspect 2025. Do not inspect 2026. Do not start Batch01 synthesis. Do not start H06.

2025 inspected: **NO**
2026 inspected: **NO**
analytical code changed after outcome access: **NO**
