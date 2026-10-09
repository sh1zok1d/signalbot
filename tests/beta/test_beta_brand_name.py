"""The bot is called Pulsy (owner, 2026-10-09). No user-facing string names the old project name;
internal identifiers (repo, package, units, /opt/signalbot, logger names) are unchanged."""
import re

from beta.i18n import LANGS, _CATALOG, t
from beta.i18n_decision import DECISION_CATALOG, DECISION_HELP, DECISION_TERMS

OLD = re.compile("signalbot", re.IGNORECASE)


def _strings():
    for key, by_lang in list(_CATALOG.items()) + list(DECISION_CATALOG.items()):
        for lang, text in by_lang.items():
            yield f"{key}/{lang}", text
    for name, block in (("DECISION_HELP", DECISION_HELP), ("DECISION_TERMS", DECISION_TERMS)):
        for lang, text in block.items():
            yield f"{name}/{lang}", text


def test_no_catalog_string_names_the_old_name():
    hits = [k for k, text in _strings() if isinstance(text, str) and OLD.search(text)]
    assert hits == [], hits


def test_the_new_name_is_where_the_old_one_was():
    for lang in LANGS:
        assert "Pulsy" in t(lang, "help")
        assert "Pulsy" in t(lang, "privacy") and "Pulsy" in t(lang, "welcome")
    assert t("ru", "team_reply").startswith("Ответ команды Pulsy") and t("en", "team_reply").startswith("Reply from the Pulsy team")


def test_the_owner_health_alert_header_uses_the_new_name():
    import inspect

    from beta import formatter
    src = inspect.getsource(formatter)
    assert "<b>Pulsy beta — owner health alert</b>" in src and "<b>Signalbot" not in src
