"""The external review of #346 + #348 (packages 2 and 3): research in the tab, stale statistics, the fallback
chance's note, /btc saying why, the checks' order and dedup, one precision for «обычно», and the checks."""
import asyncio
import re
from datetime import datetime, timedelta, timezone

from beta import decision_format as df
from beta import research_evidence as RE
from test_beta_v2_format import HOLDOUT, NOW, _bins, block, plain

UTC = timezone.utc


def _all_passed(p4=(0.3, 0.31, 200), p24=(0.4, 0.42, 120)):
    """A held-out record where every touch bin passed (each with the given predicted, realized and N)."""
    from beta.rangecast import TOUCH_CAL_BINS
    bins = list(zip(TOUCH_CAL_BINS[:-1], TOUCH_CAL_BINS[1:]))
    return {**HOLDOUT,
            "4h": {"coverage_realized": 0.81, "n_days": 365, "touch_bins": _bins(*[((lo, min(hi, 1.0)), True) + p4 for lo, hi in bins])},
            "24h": {"coverage_realized": 0.8, "n_days": 365, "touch_bins": _bins(*[((lo, min(hi, 1.0)), True) + p24 for lo, hi in bins])}}


def _conditional():
    """The DH1-L2 conditional of a zone of two levels, as `level_conditionals` builds it."""
    fs = RE.live_findings(None)
    return RE._match(fs["DH1-L2"], key="L_CONFLUENCE", arm="PENDING", at_ms=int(NOW.timestamp() * 1000),
                     relevance="CONDITIONAL", sources={}, values={"kinds": ["PDH", "ROUND"]}).to_dict()


def test_1_the_tab_shows_the_level_research_and_the_alert_matches_with_the_main_surfaces_off():
    from beta.config import BetaConfig
    from beta.formatter import format_research_tab
    blk = block(as_of=NOW.isoformat())
    cond = _conditional()
    blk["evidence"] = {"matches": [], "unavailable": [], "main_surfaces": False,
                       "zones": {"above": [[cond], [], []], "below": [[], []]},
                       "alerts": [{"kind": "level", "at": (NOW - timedelta(hours=2)).isoformat(), "level": 62950.0,
                                   "level_kind": "PDH", "move_pct": None, "matches": [cond]}]}
    # /levels is a main surface: no research line there while they are off (decision §6.1)
    assert "🔬" not in plain(df.format_levels(blk, "ru", now=NOW))
    tab = plain(format_research_tab(BetaConfig.load(), {"decision": blk}, "ru"))
    assert "Сейчас ни одно закрытое исследование не описывает состояние рынка." in tab       # no running match
    zone = tab.split("Если цена дойдёт до уровня")[1]
    assert "↑ 62 950 максимум вчера\n🔬 Если цена дойдёт сюда:" in zone
    alerts = tab.split("Сообщения за сутки")[1]
    assert "07:00 (Киев) · касание 62 950 максимум вчера\n🔬" in alerts


def test_1_alert_matching_runs_whatever_the_switch_and_the_view_keeps_the_last_days_alerts():
    from beta.decision import _recent_alert_evidence
    from beta.market_alerts import attach_evidence
    cand = {"kind": "level", "key": "level:PDH:x", "payload": {"at": NOW.isoformat(), "level_kind": "PDH",
                                                               "level": 64000.0, "side": 1}}
    attach_evidence(cand, {"as_of": NOW.isoformat(), "evidence": {"matches": [], "main_surfaces": False},
                           "levels": {"all": [{"kind": "PDH", "price": 64000.0}, {"kind": "ROUND", "price": 64000.0}]}},
                    {"bars": None})
    assert cand["payload"]["evidence"] and cand["payload"]["evidence_main"] is False

    class Conn:
        async def fetch_market_alerts(self, *, start, end, kinds):
            assert end - start == timedelta(hours=24) and set(kinds) == {"level", "move"}
            mk = lambda k, ev: {"kind": "level", "decision_ts": NOW - timedelta(hours=k),   # noqa: E731
                                "payload": {"at": (NOW - timedelta(hours=k)).isoformat(), "level": 1.0 + k,
                                            "level_kind": "PDH", "evidence": ev}}
            return [mk(k, [{"finding_id": "X"}] if k != 3 else []) for k in (9, 8, 7, 6, 5, 4, 3, 2)]
    got = asyncio.run(_recent_alert_evidence(Conn(), now=NOW))
    assert [a["level"] for a in got] == [3.0, 5.0, 6.0, 7.0, 8.0]        # newest first, with evidence, at most 5


def test_2_the_push_analogue_and_the_oi_usual_never_come_from_stale_statistics():
    from beta import decision as dec
    from beta.delivery import _analogue_source

    class Conn:
        def __init__(self, built):
            self.built = built

        async def fetch_latest_hist_stats_meta(self):
            return {"stats_pk": 1}

        async def fetch_latest_hist_stats(self):
            return {"stats_pk": 1, "built_at": self.built, "payload_digest": "d",
                    "payload": {"analogues": {"version": "a"}, "data": {"from_ms": 1577836800000},
                                "derivatives": {"oi_24h": {"n": 400}}}}
    for age_h, fresh in ((73, False), (71, True)):
        dec.reset_cache()
        conn = Conn(NOW - timedelta(hours=age_h))
        src = asyncio.run(_analogue_source(conn, NOW))
        assert (src == ({"version": "a"}, 2020)) is fresh and (src == (None, None)) is (not fresh)
        dec.reset_cache()
        assert (asyncio.run(dec.fresh_stats(conn, now=NOW)) is None) is (not fresh)
    dec.reset_cache()


def test_4_a_fallback_chance_on_btc_and_levels_carries_its_note_once():
    note = "* исторически в стольких случаях (история 2050 дн.); точность такой оценки не прошла проверку"
    blk = block(as_of=NOW.isoformat())
    lv = plain(df.format_levels(blk, "ru", now=NOW))
    assert lv.count(note) == 1 and "за 24ч исторически в 60% случаев" in lv
    btc = df.btc_lines({"decision": blk}, "ru")
    assert sum(1 for x in btc if x.startswith(note)) == 1
    passed = block(as_of=NOW.isoformat())
    passed["corridor"] = {**passed["corridor"], "holdout": _all_passed()}
    assert note not in plain(df.format_levels(passed, "ru", now=NOW))          # every chance «≈»: no note


def test_6a_the_levels_checks_go_by_hours():
    blk = block(as_of=NOW.isoformat())
    blk["corridor"] = {**blk["corridor"], "holdout": _all_passed()}
    cal = next(x for x in plain(df.format_levels(blk, "ru", now=NOW)).splitlines() if x.startswith("↳ шанс дойти"))
    assert cal.index("4ч 30%") < cal.index("24ч 40%")                       # never «24ч» before «4ч»


def test_6d_one_english_word_for_the_check():
    blk = block(as_of=NOW.isoformat())
    blk["corridor"] = {**blk["corridor"], "holdout": HOLDOUT}
    text = "\n".join(df.btc_lines({"decision": blk}, "en"))
    assert "said → happened" in text and "said → was" not in text


def test_check_b_a_stale_briefing_offers_no_level_buttons():
    from beta.formatter import btc_buttons
    view = {"kind": "brief", "decision": block(as_of=NOW.isoformat()), "market": {"complete": True}}
    datas = lambda v: [d for row in (btc_buttons(v, "ru", 7) or []) for _l, d in row]       # noqa: E731
    assert any(d.startswith("k:") for d in datas(view))
    assert not any(d.startswith("k:") for d in datas({**view, "product_status": "DATA STALE"}))


def test_check_e_a_degraded_view_links_no_analogue_claim():
    from beta.config import BetaConfig
    from beta.delivery import _link_brief_claims
    from beta.formatter import view_degraded
    assert view_degraded({"product_status": "DATA STALE", "market": {"complete": True}})
    assert view_degraded({"market": {"complete": False}}) and not view_degraded({"market": {"complete": True}})

    class Conn:
        async def view_has_claim_displays(self, view_pk):
            raise AssertionError("a degraded briefing links nothing")
    payload = {"requested_at": NOW.isoformat(), "product_status": "DATA DEGRADED", "market": {"complete": True}}
    asyncio.run(_link_brief_claims(Conn(), BetaConfig.load(), 7, payload, sent_at=NOW))


def test_check_a_the_data_time_is_the_close_of_the_price_bar():
    assert df.data_clock({"price_ts": "2026-10-14T05:52:00+00:00"}) == datetime(2026, 10, 14, 5, 53, tzinfo=UTC)
    assert re.search(r"· 08:53 \(Киев\)$", plain(df.format_levels(
        block(price_ts="2026-10-14T05:52:00+00:00"), "ru", now=NOW)).splitlines()[0])
