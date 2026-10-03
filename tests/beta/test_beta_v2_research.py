"""Research ↔ bot: the findings registry, the «Проверено» lines and /research (PRODUCT_DECISION_V2 §2.4)."""
import re
from datetime import datetime, timezone

import pytest

from beta import decision_format as df
from beta import research_link as rl
from beta.calendar_events import STAT_KINDS
from beta.i18n import ForbiddenWordingError
from beta.i18n_decision import EVENT_NAMES, LEVEL_NAMES
from beta.interpretation import LABEL_KEYS

FINDINGS = rl.load_findings()


def _telegram_html_ok(html: str) -> bool:
    body = re.sub(r"</?(b|i)>", "", html)
    body = re.sub(r"&(lt|gt|amp|quot|#\d+);", "", body)
    return not any(ch in body for ch in "<>&")


def test_the_committed_registry_is_sound():
    assert rl.validate(FINDINGS) == []
    assert len(FINDINGS) >= 15
    statuses = {f["status"] for f in FINDINGS}
    assert {"CONFIRMED", "NOT_CONFIRMED", "SIDE_FINDING"} <= statuses


def test_every_context_names_a_place_the_bot_has():
    events = set(EVENT_NAMES) | set(STAT_KINDS) | {"EXPIRY_WEEKLY"}
    for f in FINDINGS:
        for c in f["contexts"]:
            kind, _, rest = c.partition(":")
            if kind == "label":
                key = rest.split(":")[-1]
                assert key in LABEL_KEYS, c
                if rest.count(":"):
                    assert rest.split(":")[0] in ("1h", "4h"), c
            elif kind == "level":
                assert not rest or rest in LEVEL_NAMES, c
            elif kind == "event":
                assert rest in events, c
            else:
                assert c in ("move", "corridor", "weekend"), c


@pytest.mark.parametrize("contexts,expected", [
    (rl.label_contexts("1h", "compression"), "H01"),
    (rl.label_contexts("4h", "compression_oi_na"), "H01"),
    (rl.label_contexts("1h", "long_build"), "MARKET-02"),
    (rl.label_contexts("4h", "long_build"), None),            # MARKET-02 measured the next hour only
    (["move"], "H03"),
    (["corridor"], "D2"),
    (["event:FOMC"], "D11"),
    (["event:CPI"], None),                                    # D11 forbids a CPI extension; C012 is underpowered
    (["event:EXPIRY_QUARTERLY"], "R03-A1"),
    (["weekend"], "R03-C1"),
    (["level:PDH", "level"], "H02"),
])
def test_context_lines_pick_the_matching_unit(contexts, expected):
    line = rl.context_line(contexts, "ru")
    if expected is None:
        assert line is None
    else:
        assert line.startswith("Проверено: ") and line.endswith(f"({expected})")


def test_an_underpowered_unit_is_never_a_checked_line():
    fake = [{"id": "X", "status": "UNDERPOWERED", "text_ru": "мало данных", "text_en": "too few",
             "data": "d", "record": "r", "contexts": ("move",), "priority": 1}]
    assert rl.context_line(["move"], "ru", fake) is None


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_research_list_fits_telegram_and_lists_every_unit_once(lang):
    parts = rl.format_research(lang)
    assert all(len(p) <= rl.TELEGRAM_SAFE_CHARS for p in parts)
    assert all(_telegram_html_ok(p) for p in parts)
    text = "\n".join(parts)
    for f in FINDINGS:
        assert text.count(f"({f['id']})") == 1, f["id"]
    assert parts[0].startswith("<b>") and parts[-1].endswith(rl.t(lang, "rs_footer"))
    small = rl.format_research(lang, limit=900)
    assert len(small) > len(parts) and all(len(p) <= 900 for p in small)
    assert "\n".join(small).count("•") == text.count("•")


def test_validate_reports_a_broken_registry():
    good = dict(FINDINGS[0])
    bad = [good, dict(good),                                                    # duplicate id
           {**good, "id": "LONG", "text_ru": "я" * (rl.MAX_TEXT + 1)},
           {**good, "id": "CALL", "text_ru": "покупаем на 64000"},
           {**good, "id": "NOREC", "record": "docs/research/NO_SUCH_RESULT.md"},
           {**good, "id": "PENDING", "record": "docs/research/NO_SUCH_RESULT.md", "pending_merge": True}]
    problems = rl.validate(bad)
    assert any("duplicate" in p for p in problems)
    assert any(p.startswith("LONG: text_ru longer") for p in problems)
    assert any(p.startswith("CALL: text_ru") for p in problems)
    assert any(p.startswith("NOREC: record") for p in problems)
    assert not any(p.startswith("PENDING") for p in problems)
    with pytest.raises(ForbiddenWordingError):
        rl.assert_descriptive("Берите лонг", "ru")


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_a_level_alert_with_its_research_line_stays_within_eight_lines(lang):
    hist = {"real": {"n": 812, "1h": {"hold_rate": 0.47, "further_median": 0.5, "back_median": 0.4}},
            "control": {"n": 4000, "1h": {"hold_rate": 0.43}}, "verdicts": {"1h": "as_usual"}}
    payload = {"at": datetime(2026, 10, 14, 9, 5, tzinfo=timezone.utc).isoformat(), "level_kind": "PWH",
               "also_kinds": ["PDH"], "level": 64000.0, "side": 1, "period": "week", "price": 64010.0,
               "history": hist, "corridor_4h": {"lower": 63000.0, "upper": 65000.0, "half_width_pct": 1.5},
               "next": {"low": 65000.0, "high": 65000.0, "edge": 65000.0, "distance_pct": 1.5,
                        "kinds": ["ROUND"], "members": [{"kind": "ROUND", "price": 65000.0}],
                        "touch": {"24h": 0.4}}}
    text = df.format_alert("level", payload, lang)
    lines = [x for x in text.splitlines() if x.strip()]
    assert len(lines) <= df.ALERT_MAX_LINES and _telegram_html_ok(text)
    assert " = " in lines[0]                                   # one touch of a shared price: one message
    move = df.format_alert("move", {"at": payload["at"], "start": payload["at"], "open": 64000.0, "close": 63000.0,
                                    "move_pct": -1.56, "ratio": 3.1, "every_days": 3.0, "corridor_1h": None,
                                    "near": []}, lang)
    assert move.splitlines()[-1].endswith("(H03)")
