"""One-shot held-out read (design §5). Planning is outcome-free; loading refuses without a go.

Dry run (no download):  python -m scripts.research.level_race_forecast_v1.heldout --plan 2026-10-16
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from typing import Optional

from beta import history_data as HD

from scripts.research.level_touch_degradation_v1 import constants as K352

from . import constants as K

HELDOUT_START = date(2025, 1, 1)
WARMUP_START = date(2024, 12, 1)          # previous month for the Jan-2025 monthly levels; 24h sigma
OBJECT_GAP = (datetime(2026, 8, 16, tzinfo=timezone.utc), datetime(2026, 8, 26, tzinfo=timezone.utc))
E1 = (datetime(2026, 8, 16, tzinfo=timezone.utc), datetime(2026, 8, 25, 17, 20, tzinfo=timezone.utc))
FROZEN_MODEL_SHA: Optional[str] = None    # set by the freeze commit; the load refuses while None


def _ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


GAP_MS = (_ms(OBJECT_GAP[0]), _ms(OBJECT_GAP[1]))


def plan(freeze_date: date) -> tuple[list, list]:
    """5m kline objects from the product planner (E1-overlapping objects replaced or rejected),
    from the warm-up month to the day before the freeze date. Metrics objects are dropped."""
    planned, rejected = HD.plan_objects(freeze_date, klines_start=WARMUP_START, metrics_start=freeze_date)
    planned = [o for o in planned if o.kind.startswith("klines")]
    rejected = [o for o in rejected if o.kind.startswith("klines")]
    return planned, rejected


def assert_plan_legal(planned: list) -> None:
    for o in planned:
        a, z = o.period_ms
        if a < GAP_MS[1] and GAP_MS[0] < z:
            raise RuntimeError(f"object {o.key} intersects the E1 object gap")
        if HD.url_refusal(o.url) is not None:
            raise RuntimeError(f"object {o.key} refused by the product guard")


def event_span_ok(touch_open_ms: int) -> bool:
    """σ window (j-289 .. j-1), the touch bar and the 4h window (j+1 .. j+48) clear of the gap."""
    a = int(touch_open_ms) - (K352.SCALE_BARS + 1) * K352.BAR_MS
    z = int(touch_open_ms) + (K.WINDOW_BARS + 1) * K352.BAR_MS
    return not (a < GAP_MS[1] and GAP_MS[0] < z)


def event_in_window(touch_open_ms: int, freeze_date: date) -> bool:
    start = _ms(datetime(HELDOUT_START.year, HELDOUT_START.month, HELDOUT_START.day, tzinfo=timezone.utc))
    end = _ms(datetime(freeze_date.year, freeze_date.month, freeze_date.day, tzinfo=timezone.utc))
    close_48 = int(touch_open_ms) + (K.WINDOW_BARS + 1) * K352.BAR_MS
    return start <= int(touch_open_ms) and close_48 <= end


def require_go(go_token: Optional[str]) -> None:
    if FROZEN_MODEL_SHA is None:
        raise RuntimeError("held-out read refused: no frozen model version")
    if not go_token:
        raise RuntimeError("held-out read refused: no explicit go")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="freeze date YYYY-MM-DD (exclusive end)")
    a = ap.parse_args()
    fd = date.fromisoformat(a.plan)
    planned, rejected = plan(fd)
    assert_plan_legal(planned)
    for o in planned:
        print("GET", o.url)
    for o in rejected:
        print("REFUSED", o.url, HD.object_protected(o))
    print(f"planned {len(planned)} objects, refused {len(rejected)}; none intersects [2026-08-16, 2026-08-26)")


if __name__ == "__main__":
    main()


# ---- prequential publication with the live calibrator (one calibrator; mini-head 2026-10-08) -------
_OUT = {"BEYOND": "BREAK", "BACK": "REJECT", "NEITHER": "NEITHER"}


def calibration_records(level_rows: list, p_raw_level, generic_rows: list, p_raw_generic) -> list:
    """Records for beta.level_race_calibration.fit_calibrator. Level rows carry the raw of the
    published case: case A the champion (M1) raw, case B the fallback raw (G1@event). Generic rows
    carry G1 raw on the generic geometry (UP = BREAK slot). Each row needs issued_ms / resolved_ms."""
    recs = []
    for r, p in zip(level_rows, p_raw_level):
        recs.append({"cal_class": "LEVEL_T0" if r["landmark"] == "T0" else "LEVEL_T15", "p_raw": list(map(float, p)),
                     "outcome": _OUT.get(r["outcome"]), "issued_ms": int(r["issued_ms"]),
                     "resolved_ms": int(r["resolved_ms"]), "week": int(r["week"])})
    for r, p in zip(generic_rows, p_raw_generic):
        recs.append({"cal_class": "GENERIC", "p_raw": list(map(float, p)), "outcome": _OUT.get(r["outcome"]),
                     "issued_ms": int(r["issued_ms"]), "resolved_ms": int(r["resolved_ms"]), "week": int(r["week"])})
    return recs


def prequential_published(records: list, start_ms: int, end_ms: int, *, use_level_class: bool):
    """Published three outcomes for every level record: the calibrator in force at its issue time is
    fitted (from the identity prior) only on records resolved before the last batch cutoff at or
    before that time, with F3's live batching and generic row weight. Case B / fallback: GENERIC."""
    from beta import level_race_calibration as LRC   # the live calibrator (F3); imported, not copied
    priors = {h: LRC.identity_prior() for h in LRC.HEADS}
    cutoffs = [int(start_ms)] + LRC.batch_cutoffs(int(start_ms), int(end_ms))
    cache: dict = {}
    out = []
    for r in records:
        if r["cal_class"] == "GENERIC":
            continue
        c = max(x for x in cutoffs if x <= int(r["issued_ms"]))
        if c not in cache:
            cache[c] = LRC.fit_calibrator(records, priors, cutoff_ms=c)
        cls = r["cal_class"] if use_level_class else "GENERIC"
        out.append((r, LRC.apply_calibrator(cache[c], r["p_raw"], cls), cache[c].version))
    return out
