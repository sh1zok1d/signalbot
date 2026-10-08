"""The level race outcome rule LEVEL_RACE_4H_V1 (beta/level_race_live.classify) equals the #352 `classify`
on the original window from T0. Synthetic bars only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "beta"))

from beta import level_race_live as LR  # noqa: E402
from test_level_race_live import B, EVS  # noqa: E402


def test_outcome_rule_equals_the_352_classify():
    from scripts.research.level_touch_degradation_v1.outcomes import classify as r352
    names = {}
    checked = 0
    for e in EVS:
        y = r352(B.high, B.low, e["j"], e["side"], e["zone_low"], e["zone_high"], e["x"], 48)
        mine = LR.classify(B, touch_open_ms=e["touch_open_ms"], landmark="T0", p_up=e["zone_high"] * (1 + e["x"]),
                           p_dn=e["zone_low"] * (1 - e["x"]))
        up_is_break = e["side"] > 0
        want = {"BREAK": "UP" if up_is_break else "DN", "REJECT": "DN" if up_is_break else "UP"}.get(y, y)
        assert mine["usable"] and mine["outcome"] == want, (e["event_id"], y, mine)
        names[want] = names.get(want, 0) + 1
        checked += 1
    assert checked > 15 and len(names) >= 2
