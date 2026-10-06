"""The personal layer (PRE_BETA_SCOPE_DECISION_V1 §9 E; backlog C5, E1–E5): pure parts."""
from datetime import datetime, timezone

import pytest

from beta.i18n import fmt_clock, parse_tz, render_tz, t, tz_of, zone_name, KYIV

UTC = timezone.utc
T = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)          # 09:00 Kyiv (summer time)


@pytest.mark.parametrize("raw, stored", [
    ("+3", "UTC+03:00"), ("UTC-5", "UTC-05:00"), ("+05:30", "UTC+05:30"), ("−4", "UTC-04:00"), ("gmt+0", "UTC+00:00"),
    ("Europe/Warsaw", "Europe/Warsaw"), ("america/new_york", "America/New_York"),
    ("+15", None), ("+3:75", None), ("Mars/Base", None), ("Warsaw", None), ("", None), (None, None)])
def test_a_time_zone_is_an_iana_name_or_a_fixed_offset(raw, stored):
    assert parse_tz(raw) == stored


def test_kyiv_is_the_default_and_an_unreadable_value_never_breaks_a_message():
    assert tz_of(None) is KYIV and tz_of("Nowhere/Land") is KYIV and tz_of("Europe/Kyiv") is KYIV
    assert fmt_clock(T, "ru") == "09:00 (Киев)" and fmt_clock(T, "en") == "09:00 Kyiv"


def test_every_clock_follows_the_participant_zone_inside_a_rendering():
    with render_tz("UTC+05:30"):
        assert fmt_clock(T, "ru") == "11:30 (UTC+5:30)" and fmt_clock(T, "en") == "11:30 UTC+5:30"
        # a template that names the zone gets the participant's (the catalog's «Киев» is gone, C5)
        assert t("ru", "dc_stats_built", when="Вт 06.10 11:30") == "Статистика по истории собрана Вт 06.10 11:30 (UTC+5:30)."
        assert t("en", "ev_title") == "<b>Events</b> (UTC+5:30 time)"
    with render_tz("America/New_York"):
        assert fmt_clock(T, "ru") == "02:00 (UTC−4)" and zone_name("en", T) == "UTC−4"
    assert fmt_clock(T, "ru") == "09:00 (Киев)"                    # the scope ends with the rendering
    assert t("ru", "ev_title") == "<b>События</b> (время — Киев)"
