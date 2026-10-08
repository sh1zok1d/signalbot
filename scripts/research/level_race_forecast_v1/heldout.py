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
