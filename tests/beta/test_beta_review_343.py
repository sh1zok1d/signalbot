"""The external review of #343 (package 1): honest numbers on every L2 line, the glossary, the registry."""
import math
import re
from datetime import datetime, timezone

from beta import decision_format as df

UTC = timezone.utc
T = datetime(2026, 10, 14, 6, 41, tzinfo=UTC)


def plain(html):
    return re.sub(r"<[^>]+>", "", html)


BASE = {"p_up": 0.51, "mean_log_range": 0.0}
CELL = {"n": 412, "days": 300, "p_up": 0.53, "baseline": BASE, "range_ratio": 1.3, "mean_log_range": math.log(1.25),
        "ci95": {"direction": [-0.011, 0.052], "range": [math.log(1.1), math.log(1.4)]}}
HIST = {"real": {"n": 812, "1h": {"hold_rate": 0.47, "further_median": 0.5, "back_median": 0.4}},
        "control": {"n": 4000, "1h": {"hold_rate": 0.43, "further_median": 0.5, "back_median": 0.4}},
        "verdicts": {"1h": "as_usual"}, "ci95": {"1h": [-0.012, 0.091]}}


def _card(cell, h="4h"):
    return {"window": h, "outcomes": {h: cell}}


def test_1_after_similar_without_an_interval_says_too_little_data():
    # n ≥ 30 on fewer days than the bootstrap needs: the statistics store no interval
    few_days = {k: v for k, v in CELL.items() if k not in ("ci95", "mean_log_range")} | {"days": 9}
    # the reason, never «мало данных» beside a large N (follow-up review of #350)
    assert df.analog_line(_card(few_days), "ru") == "↳ после похожих: мало разных дней (412 случаев за 9 дн.)"
    assert df.analog_line(_card(few_days), "en") == "↳ after similar: too few distinct days (412 cases over 9 days)"
    old = {k: v for k, v in CELL.items() if k != "ci95"}                 # statistics built before the interval
    assert df.analog_line(_card(old), "ru") == "↳ после похожих: интервал ещё не посчитан (412 случаев)"
    assert df.analog_line(_card({**CELL, "n": 12}), "ru") == "↳ после похожих: мало данных (12 случаев)"
    assert not df.analog_shown(few_days) and df.analog_shown(CELL)
    assert "п.п." in df.analog_line(_card(CELL), "ru")


def test_2_level_history_without_an_interval_says_too_little_data_on_levels_check_and_the_alert():
    bare = {k: v for k, v in HIST.items() if k != "ci95"}
    assert df._hist_lines(bare, "ru", 1) == ["↳ после первого касания: интервал ещё не посчитан (812 случаев)"]
    few = {**bare, "real": {**bare["real"], "periods": 9}}
    assert df._hist_lines(few, "ru", 1) == ["↳ после первого касания: мало разных периодов (812 случаев, периодов: 9)"]
    payload = {"at": T.isoformat(), "level_kind": "PDH", "level": 62950.0, "side": 1, "period": "day",
               "price": 62960.0, "price_ts": T.isoformat(), "history": bare, "next": None, "corridor_4h": None,
               "event_zone": {}}
    text = plain(df.format_alert("level", payload, "ru"))
    assert "После первого касания: интервал ещё не посчитан (812 случаев)" in text and "п.п." not in text
    few_alert = plain(df.format_alert("level", {**payload, "history": few}, "en"))
    assert "After the first touch: too few distinct periods (812 cases, 9 periods)" in few_alert
    with_ci = plain(df.format_alert("level", {**payload, "history": HIST}, "ru"))
    assert ("После первого касания (812 случаев): через 1ч цена выше уровня в 47% — у случайного уровня 43% "
            "(+4,0 п.п.; 95% интервал −1,2…+9,1)") in with_ci
    assert "За 1ч медиана: дальше 0,50%, обратно 0,40%" in with_ci           # the alert keeps its own wording


def test_3_the_glossary_describes_the_interval_without_a_decision_rule():
    from beta.i18n_decision import DECISION_TERMS
    for lang, zero in (("ru", "ноль"), ("en", "zero")):
        text = DECISION_TERMS[lang]
        assert zero not in text                                        # no «includes zero → differs» rule
        assert "×1" in text                                            # the usual point of the move ratio
    assert "неопределённость этой исторической оценки" in DECISION_TERMS["ru"]
    assert "uncertainty of this historical estimate" in DECISION_TERMS["en"]
    # no correction for multiplicity, said in words (follow-up review of #350)
    assert "без поправки на то, что строк много" in DECISION_TERMS["ru"]
    assert "no correction for there being many lines" in DECISION_TERMS["en"]
    # the level history's interval is bootstrapped over the level's periods, said where the random level is
    ru = DECISION_TERMS["ru"].split("Случайный уровень")[1].split("\n")[0]
    en = DECISION_TERMS["en"].split("Random level")[1].split("\n")[0]
    assert "считается по периодам уровня" in ru and "computed over the level's periods" in en


def test_4_the_move_ratio_follows_the_interval_not_the_mean_log_range():
    old = {k: v for k, v in CELL.items() if k != "ci95"}               # an older row keeps its mean log range
    assert "mean_log_range" in old
    assert df.analog_range(old, "ru") == (1.3, "")                     # the median ratio, as before
    ratio, rci = df.analog_range(CELL, "ru")
    assert round(ratio, 4) == 1.25 and rci == " (95% интервал ×1,10…×1,40)"


def test_5_points_and_intervals_share_their_precision_edges_keep_their_sign_shares_split_when_equal():
    cell = {**CELL, "mean_log_range": math.log(1.04), "ci95": {"direction": [-0.0004, 0.031],
                                                               "range": [math.log(1.01), math.log(1.08)]}}
    ru = df.analog_line(_card(cell), "ru")
    assert "ход ×1,04 к обычному (95% интервал ×1,01…×1,08)" in ru      # never ×1,0 beside ×1,01…×1,08
    assert "95% интервал −0,0…+3,1" in ru                                # the edge just below zero keeps «−»
    assert df.fmt_pp(-0.0004, "en") == "−0.0" and df.fmt_pp(0.0004, "en") == "+0.0" and df.fmt_pp(0.0, "en") == "0.0"
    close = {**CELL, "p_up": 0.5249, "baseline": {**BASE, "p_up": 0.5151}}
    assert "выше в 52,5% против 51,5% обычно (+1,0 п.п." in df.analog_line(_card(close), "ru")
    assert df.share_pair(0.53, 0.51, "en") == ("53%", "51%")
    hist = {**HIST, "real": {**HIST["real"], "1h": {**HIST["real"]["1h"], "hold_rate": 0.4749}},
            "control": {**HIST["control"], "1h": {**HIST["control"]["1h"], "hold_rate": 0.4651}}}
    assert "в 47,5% — у случайного уровня 46,5%" in df._hist_lines(hist, "ru", 1)[0]


def test_5_the_journal_prints_the_shares_as_the_screen_does():
    from beta import claims as cj
    hist = {**HIST, "real": {**HIST["real"], "1h": {"hold_rate": 0.4749}},
            "control": {**HIST["control"], "1h": {"hold_rate": 0.4651}}}
    cand = {"kind": "level", "key": "level:PDH:2026-10-14",
            "payload": {"at": T.isoformat(), "level_kind": "PDH", "level": 62950.0, "side": 1, "period": "day",
                        "history": hist}}
    (row,) = cj.level_hold_claims(cand, now=T)
    assert row["numbers"]["printed"]["observed"] == "47.5%" and row["numbers"]["printed"]["baseline"] == "46.5%"


def test_7_the_weekend_finding_carries_the_volatility_regime_caveat_of_its_record():
    from beta.research_link import load_findings
    f = next(x for x in load_findings() if x["id"] == "R03-C1")
    record = open(f["record"], encoding="utf-8").read()
    assert "| C1 | −0.396 | −0.104 | 0.26 | reflects the general volatility regime |" in record
    assert "−0,40 → −0,10 SD" in f["text_ru"] and "−0.40 → −0.10 SD" in f["text_en"]
    assert "режим волатильности" in f["live"]["limitations_ru"]
    assert "volatility regime" in f["live"]["limitations_en"]


def test_8_the_l2_cohorts_include_the_interval_templates():
    from beta import claims as cj
    for cls, (level, keys, _rule) in cj.CLASSES.items():
        if cls.startswith("L2_STATE_ANALOG_"):
            assert {"dc_pp_ci", "dc_ratio_ci"} <= set(keys), cls
        if cls.startswith("L2_LEVEL_FIRST_TOUCH_HOLD_"):
            assert "dc_pp_ci" in keys, cls


def test_9_the_dead_research_line_key_is_gone():
    from beta.i18n import _CATALOG
    assert "rs_line" not in _CATALOG and "rs_line_confirmed" in _CATALOG


def test_follow_up_shares_split_whenever_their_difference_disagrees_with_the_printed_one():
    """Follow-up review of #350: whole percents only when their difference is the rounded difference."""
    assert df.share_pair(0.5249, 0.5251, "ru") == ("52,5%", "52,5%")        # was «52% против 53%» beside −0,0
    assert df.share_pair(0.5249, 0.5350, "ru") == ("52,5%", "53,5%")        # was «52% против 54%» beside −1,0
    assert df.share_pair(0.5249, 0.5151, "en") == ("52.5%", "51.5%")
    assert df.share_pair(0.53, 0.51, "ru") == ("53%", "51%") and df.share_pair(0.534, 0.512, "ru") == ("53%", "51%")
    mirror = {**CELL, "p_up": 0.5249, "baseline": {**BASE, "p_up": 0.5350}}
    assert "выше в 52,5% против 53,5% обычно (−1,0 п.п." in df.analog_line(_card(mirror), "ru")


def test_follow_up_the_bootstrap_minimums_equal_the_statistics():
    from beta import analogues, levels
    assert df.MIN_DAYS_SHOWN == analogues.MIN_DAYS and df.MIN_PERIODS_SHOWN == levels.MIN_PERIODS


def test_follow_up_a_weak_finding_never_repeats_its_status_in_its_text():
    """«Ниже порога практической величины: …, ниже порога 15%»: the status heading or prefix says it once."""
    from beta.research_link import load_findings
    for f in load_findings():
        if f["status"] == "WEAK":
            assert "ниже порога" not in f["text_ru"] and "below the" not in f["text_en"], f["id"]
            if f["id"] in ("DH3-P1", "DH3-O2", "DH3-L3", "DH3-S1", "R03-C1"):             # the bar's number stays
                assert "порог —" in f["text_ru"] and "bar:" in f["text_en"], f["id"]
