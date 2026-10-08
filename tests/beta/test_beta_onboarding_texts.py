"""Texts of the onboarding package (backlog J1, J2, J4, I2) that need no database."""
from beta.i18n import t


def test_stop_discloses_what_still_reaches_a_paused_participant():
    """/admin_reply reaches STOPPED participants and nothing else does (owner, 2026-10-08): privacy v8 and
    the pause reply say so, and no longer promise an offer after /stop."""
    for lang, phrase in (("ru", "кроме ответов команды на ваши сообщения."),
                         ("en", "except the team's replies to your messages.")):
        for key in ("privacy", "paused"):
            text = " ".join(t(lang, key).split())
            assert phrase in text and "предложени" not in text and "offer" not in text, (lang, key)


def test_no_interview_surface_is_reachable():
    """The owner removed the interviews on 2026-10-08: no command, button, copy or help line is left, and no
    code path writes the kept-for-history values (kind 'interview', cmd_interview, interview_booked)."""
    import pathlib
    import re
    from beta import i18n, i18n_decision
    from runtime.beta_bot import _help_buttons
    assert not any("interview" in k for k in i18n._CATALOG)
    for lang in ("ru", "en"):
        assert all("interview" not in d for row in _help_buttons(lang) for _l, d in row)
        assert "/interview" not in i18n_decision.DECISION_HELP[lang] and "/interview" not in t(lang, "privacy")
        assert "накануне" not in " ".join(str(v.get(lang, "")) for v in i18n._CATALOG.values() if isinstance(v, dict))
    root = pathlib.Path(__file__).resolve().parents[2]
    for src in ("runtime/beta_bot.py", "beta/admin.py", "beta/delivery.py", "storage/beta_v0_store.py"):
        code = (root / src).read_text(encoding="utf-8")
        assert not re.search(r"[\"']cmd_interview[\"']|[\"']interview_booked[\"']|kind=[\"']interview[\"']", code), src
    assert "x:interview" not in (root / "runtime/beta_bot.py").read_text(encoding="utf-8")


def test_privacy_names_plain_messages():
    """J4 stores plain messages as feedback for 120 days."""
    assert "обычные сообщения боту" in t("ru", "privacy") and "plain messages to the bot" in t("en", "privacy")


def test_the_guide_names_the_levels_and_the_race_line_without_attribution():
    for lang in ("ru", "en"):
        g = t(lang, "guide")
        assert "весь рынок" not in g and "whole market" not in g
    assert "максимумы и минимумы прошлого дня, недели и месяца" in t("ru", "guide")
    assert "the previous day's, week's and month's highs and lows" in t("en", "guide")
    # «обычно» is B0 (FORECAST_LAYER_DECISION_V1 §1/§3): a driftless path from the same point, no level effect
    assert "случайная цена с той же волатильностью из той же точки, без учёта уровня" in " ".join(t("ru", "guide").split())
    assert "a random price path with the same volatility from the same point" in " ".join(t("en", "guide").split())
    assert "без касания" not in t("ru", "guide") and "without a touch" not in t("en", "guide")


def test_no_text_says_the_whole_market_watches_the_levels():
    from beta.i18n_decision import DECISION_HELP
    for lang in ("ru", "en"):
        for text in (t(lang, "welcome"), DECISION_HELP[lang]):
            assert "весь рынок" not in text and "everyone watches" not in text and "whole market" not in text
    assert "первой была" in t("ru", "guide") and "не прогноз направления" in t("ru", "guide")
    assert "reached first" in t("en", "guide") and "not a direction forecast" in t("en", "guide")


def test_the_sample_alert_carries_no_corridor():
    """An example under «Это пример» never shows a corridor that could read as the current market."""
    from runtime.beta_bot import _sample_level_alert
    for lang in ("ru", "en"):
        text = _sample_level_alert(lang)
        assert "оридор" not in text and "orridor" not in text and "98 600" not in text
