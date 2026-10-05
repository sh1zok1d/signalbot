# Evidence format shadow test — expectations, written before re-reading (V1)

**Status:** `EXPECTATIONS_COMMITTED_BEFORE_REREAD / SHADOW_FORMATTING_EXERCISE / NO_STATISTICAL_TEST / NO_PROMOTION`
**Date:** 2026-10-05
**Belongs to:** `EVIDENCE_AND_CLAIMS_DECISION_V1.md` §6 (the reporting record). Report: `EVIDENCE_FORMAT_SHADOW_REPORT_V1.md`.

## 1. What this checks

This exercise checks whether the new reporting record can tell three kinds of already-closed result apart, using only what their records already contain. It does not test any hypothesis, and it does not recompute, rerun or rescore anything. No unit changes status: the official verdicts in the records, the ledger and `config/beta_research_findings.yaml` stay as they are.

## 2. The three units, chosen by type before their records were re-read

The units were chosen from the `id`, `status`, `record` and `data` fields of `config/beta_research_findings.yaml` only.

| Type | Unit | Selection basis |
|---|---|---|
| Obvious null | `DH1-L2` (first touch of a key level → 4h hold) | `NOT_CONFIRMED`; directional endpoint; large N (4 622 touches); single preregistered cell |
| Strong but small | `R03-C1` (weekend hour vs same weekday hour) | named by the owner |
| Rare event / small N | `D12` (DST clock-change Sundays) | `DISCOVERY`; 10 events against 239 ordinary Sundays: the smallest event count with an estimate in the registry |

**Rejected alternative.** `C012` (`UNDERPOWERED`) was rejected because it was closed before any outcome was counted. It has no estimate or direction, so it cannot test whether the format keeps them.

**Exposure, stated honestly:**
- the headline numbers of `DH1-L2` (hold 46.5 % vs 46.3 %, CI −3.03..+3.06 pp) and `R03-C1` (Holm p = 0.0001, about −0.40 SD) were already seen in `CURRENT_RESEARCH_STATE.md` and in the owner discussion;
- `D12`'s numbers were not read before this file was committed.

This is therefore a test of the format, not of the units.

## 3. Expected behaviour of the format (not of the numbers)

### 1. `DH1-L2` (null)

- **Evidence fields:** an estimate close to zero, with an interval that covers zero and also covers any practically relevant shift.
- **Product use:** the record ends as "nothing useful to show as a tendency".
- **Allowed claim:** no L2 directional line on a live surface. A line like «+0.0 п.п.» beside every level touch would be noise. At most a `/research` mention that no difference from the baseline was found.
- **Must not happen:** the format must not invent a tendency, and must not turn a null into "unknown" when the interval is tight.

### 2. `R03-C1` (strong but small)

- **Evidence fields:** a real structure (interval away from zero, sign stable across years) whose magnitude is below the stronger claim's bar, both stated without contradiction.
- **Product use:** potentially useful for the product baseline (`WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md`).
- **Allowed claim:** at most L1, a quantified historical-context sentence. It is not directional, so it is never L2, and it is not an edge.
- **Must not happen:** the format must not record "no structure", and must not let "below the bar" erase the estimate.

### 3. `D12` (rare event)

- **Evidence fields:** the estimate and its direction are kept and shown, with the event count front and centre and the information marked insufficient.
- **Next step:** prospective accumulation, with the next event dates named.
- **Allowed claim:** no live claim beyond a `/research` mention that carries N.
- **Must not happen:** the format must not drop it as "nothing", and must not show it as a tendency.

## 4. When the format fails

- **Not distinguished:** two of the three units end with the same evidence summary and the same allowed claim.
- **Recomputation needed:** a mandatory field can be filled only by computing something new. A field the record does not hold is written `NOT_IN_RECORD`; it is never recomputed here.
- **Directional line slips through:** the null or the rare event gets an L2 line on a live surface, or R03-C1 gets an L2 or edge line.
- **Discriminating by hand:** the report needs a field that is a confidence adjective (weak / moderate / strong) to tell the units apart.
