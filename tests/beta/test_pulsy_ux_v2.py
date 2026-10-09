"""Pulsy UX V2 P0 (docs/PULSY_UX_STANDARD_V2.md): the owner's rules A–G and the format, each a named test
(the standard's §6 maps rule → test). Pure; nothing here is wired to a user surface."""
import copy
import html.parser
import re
from datetime import timedelta

import pytest

from test_beta_multi_horizon_ux import screens
from test_beta_v2_format import HIST, NOW, _zone, block

from beta.config import BetaConfig
from beta.formatter import format_1h_tab, format_24h_tab
from beta.i18n import assert_descriptive
from beta.ux import SCREENS, enabled, facts_equivalent, from_alert, from_hour_gate, from_view, render
from beta.ux import select as sel
from beta.ux.phrases import EMOJI, FORBIDDEN, PHRASES
from beta.ux.render import CALLBACK_MAX_BYTES, NARROW_NBSP, NBSP, max_chars

CFG = BetaConfig.load()
LANGS = ("ru", "en")


def _view(name="unusual", **dec):
    v = copy.deepcopy(screens()[name])
    v["decision"] = block(**dec)
    return v


def _ranked(view, range_rank=None, volume_rank=None):
    if view.get("context_1h") is None:                     # the "unusual" fixture has no 1h context
        view["context_1h"] = copy.deepcopy(screens()["calm"]["context_1h"])
    p = view["context_1h"]["percentiles"]
    if range_rank is not None:
        p["range_width_pct_median"] = {"rank": range_rank, "tier": "mature"}
    if volume_rank is not None:
        p["volume_notional_usd_sum"] = {"rank": volume_rank, "tier": "mature"}
    return view


def _calm():
    return _view("calm", levels={"above": [], "below": [], "at": None, "all": []}, events=[])


def _busy():
    v = _ranked(_view("unusual"), range_rank=0.995, volume_rank=0.97)
    v["decision"]["levels"]["at"] = _zone(["PDL"], 62470.0, 62490.0, 0.0)
    return v


def _all_renders():
    """Every P0 screen and level, both languages, over calm and busy states and the notifications."""
    out = []
    for v in (_calm(), _busy(), _view("stale_none")):
        f = from_view(v)
        for lvl in SCREENS["btc"]:
            out += [("btc", lvl, lang, render("btc", lvl, lang, f)) for lang in LANGS]
        out += [("levels", 1, lang, render("levels", 1, lang, f)) for lang in LANGS]
        out += [("brief", 1, lang, render("brief", 1, lang, {**f, "window_hours": 8})) for lang in LANGS]
    card = {"zone": from_view(_busy())["levels"]["above"][0]}
    out += [("level_card", 1, lang, render("level_card", 1, lang, card)) for lang in LANGS]
    lvl = from_alert("level", {"at": NOW.isoformat(), "level_kind": "PDH", "level": 62950.0, "side": 1,
                              "period": "day", "price": 62970.0})
    move = from_alert("move", {"at": NOW.isoformat(), "start": (NOW - timedelta(minutes=15)).isoformat(),
                               "open": 63100.0, "close": 62250.0, "move_pct": -1.35, "every_days": 3.0})
    hour = from_hour_gate(NOW.isoformat(), {"window_start": (NOW - timedelta(hours=1)).isoformat(),
                                            "window_end": NOW.isoformat(), "values": {"price_move_pct": -0.84},
                                            "passed": {"range": True, "volume": True}})
    for screen, f in (("level", lvl), ("move", move), ("hour", hour)):
        out += [(screen, 1, lang, render(screen, 1, lang, f)) for lang in LANGS]
    return out


def plain(h):
    return re.sub(r"<[^>]+>", "", h).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def norm(s):
    return s.replace(NARROW_NBSP, " ").replace(NBSP, " ")


# ---- A–G ----------------------------------------------------------------------------------------
def test_rule_A_l1_is_compact():
    for screen, lvl, lang, (h, _b) in _all_renders():
        assert len(h) <= max_chars(screen, lvl), (screen, lvl, lang, len(h))
    f = from_view(_busy())
    assert len(sel.salient(f)) <= sel.L1_MAX
    body = plain(render("btc", 1, "ru", f)[0]).split("\n\n")[1]
    assert len(body.splitlines()) <= sel.L1_MAX


def test_rule_B_l2_is_compact():
    for v in (_calm(), _busy()):
        f = from_view(v)
        for lang in LANGS:
            l1 = plain(render("btc", 1, lang, f)[0]).split("\n\n")[1].splitlines()
            l2 = plain(render("btc", 2, lang, f)[0]).split("\n\n")[1].splitlines()
            assert len(l2) == len(l1) and all(len(x) <= 140 for x in l2)


def test_rule_C_exact_historical_meaning():
    for key, (ru, en, _rule) in PHRASES.items():
        for s in (ru.lower(), en.lower()):
            assert not any(w in s for w in ("пробой", "пробил", "закреп", "удержал", "breakout", "held above",
                                            "held below")), key
    assert PHRASES["l3_oi_down"][0].startswith("Открытых позиций стало меньше")
    # an OI decline on L3 is worded as such, never as a direction
    ru = plain(render("btc", 3, "ru", from_view(_busy()))[0])
    assert "Открытых позиций стало меньше: −0,60" in norm(ru)


def test_rule_D_l3_numbers_equal_the_facts_and_todays_render():
    v = _busy()
    f = from_view(v)
    for lang in LANGS:
        l3 = norm(plain(render("btc", 3, lang, f)[0]))
        old_1h = norm(plain(format_1h_tab(CFG, {"horizons": v["horizons"], "active_episode": None,
                                                "last_event": None}, lang, "abcd1234")))
        old_24h = norm(plain(format_24h_tab(CFG, {"horizons": v["horizons"], "active_episode": None,
                                                  "last_event": None}, lang, "abcd1234")))
        h1, h24 = f["h1"], f["h24"]
        from beta.i18n import fmt_plain_pct, fmt_price, fmt_signed_pct, fmt_usd
        for s, old in ((fmt_signed_pct(h1["price_move_pct"], lang), old_1h),
                       (fmt_plain_pct(h1["range_width_pct"], lang), old_1h),
                       (fmt_usd(h1["volume_notional_usd"], lang), old_1h),
                       (fmt_price(h24["high"], lang), old_24h), (fmt_price(h24["low"], lang), old_24h)):
            assert s in l3 and s in old, (lang, s)
        c = f["corridor_24h"]
        assert fmt_price(c["lower"], lang) in l3 and fmt_price(c["upper"], lang) in l3
        n = h1["baseline_days"]["range_width_pct_median"]
        assert (f"медиана {n} дн." if lang == "ru" else f"median of {n} days") in l3


def test_rule_D_level_names_come_from_the_data():
    from beta.decision_format import level_name
    v = _view("unusual", levels={"above": [_zone(["PWH"], 64000.0, 64000.0, 2.4)],
                                 "below": [_zone(["PWL"], 61000.0, 61000.0, -2.4)], "at": None, "all": []})
    f = from_view(v)
    for lang in LANGS:
        text = plain(render("levels", 1, lang, f)[0])
        high, low = level_name({"kind": "PWH"}, lang), level_name({"kind": "PWL"}, lang)
        assert high != low
        above, below = text.split("\n\n")[1], text.split("\n\n")[2]
        assert high in above and low not in above and low in below and high not in below
    # the name is a function of the member kind only: a swapped kind swaps the name, nothing else can
    swapped = copy.deepcopy(v)
    swapped["decision"]["levels"]["above"][0]["members"][0]["kind"] = "PWL"
    assert level_name({"kind": "PWL"}, "ru") in plain(render("levels", 1, "ru", from_view(swapped))[0]).split("\n\n")[1]


class _Html(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ok = [], True

    def handle_starttag(self, tag, attrs):
        self.ok &= tag == "b" and not attrs
        self.stack.append(tag)

    def handle_endtag(self, tag):
        self.ok &= bool(self.stack) and self.stack.pop() == tag


def test_rule_E_telegram_format():
    for screen, lvl, lang, (h, buttons) in _all_renders():
        p = _Html()
        p.feed(h)
        assert p.ok and not p.stack, (screen, h)
        assert "\n\n\n" not in h and not h.startswith("\n") and not h.endswith("\n")
        assert not re.search(r"\d \d", h), (screen, lang, h)               # thousands: narrow NBSP only
        emoji = {c for c in h if ord(c) > 0x2600 and not c.isalpha()} - {"→", "−", "–", "·", "…", NARROW_NBSP}
        assert all(any(e.startswith(c) for e in EMOJI) for c in emoji if c != "️"), (screen, emoji)
        assert len(buttons) <= 3 and all(1 <= len(row) <= 2 for row in buttons)
        for row in buttons:
            for label, data in row:
                assert len(data.encode("utf-8")) <= CALLBACK_MAX_BYTES and data.startswith("ux:")
                scr, lv = data.split(":")[1:]
                assert int(lv) in SCREENS[scr]


def test_rule_F_no_drama():
    for _s, _l, lang, (h, _b) in _all_renders():
        low = plain(h).lower()
        assert not any(w in low for w in FORBIDDEN), low
    for ru, en, _rule in PHRASES.values():
        assert not any(w in ru.lower() or w in en.lower() for w in FORBIDDEN)


def test_rule_G_every_phrase_has_a_rule_and_the_doc_lists_them():
    import pathlib
    doc = (pathlib.Path(__file__).resolve().parents[2] / "docs" / "PULSY_UX_STANDARD_V2.md").read_text("utf-8")
    listed = set(re.findall(r"^\| `([a-z0-9_]+)` \|", doc, re.M))
    assert listed == set(PHRASES)
    for key, (ru, en, rule) in PHRASES.items():
        assert ru and en and rule and len(rule) >= 3, key


# ---- the other P0 checks --------------------------------------------------------------------------
def test_no_historical_number_on_l1():
    for v in (_calm(), _busy(), _view("stale_none")):
        for lang in LANGS:
            body = plain(render("btc", 1, lang, from_view(v))[0]).split("\n\n", 1)[1]
            assert not re.search(r"\d+[,.]?\d*\s?(%|×|дн|days|N=)", body), body
            assert not re.search(r"(обычно|usually)\W+\$?\d", norm(body)), body   # no «обычно 0,49%»


def test_ru_en_pairs_complete():
    for key, (ru, en, _rule) in PHRASES.items():
        assert set(re.findall(r"{(\w+)}", ru)) == set(re.findall(r"{(\w+)}", en)), key
    for _s, _l, lang, (h, _b) in _all_renders():
        if lang == "en":
            assert not re.search("[а-яё]", h, re.I), h


def test_assert_descriptive_on_every_render():
    for _s, _l, lang, (h, _b) in _all_renders():
        assert_descriptive(plain(h), lang)


def test_nothing_notable_for_a_calm_state():
    f = from_view(_calm())
    assert sel.salient(f) == ["nothing"]
    assert "Сейчас ничего заметного." in plain(render("btc", 1, "ru", f)[0])
    assert "Nothing notable right now." in plain(render("btc", 1, "en", f)[0])


def test_salience_is_frozen_and_ordered():
    assert sel.SALIENCE_VERSION == "PULSY_SALIENCE_V1"
    assert [k for k, _p in sel.SALIENCE] == ["stale", "episode", "level_at", "range_extreme", "range_high",
                                             "volume_high", "event_today", "corridor_edge"]
    assert sel.salient(from_view(_busy())) == ["episode", "level_at", "range_extreme"]


def test_facts_are_copies_and_equivalence_detects_drift():
    v = _busy()
    f = from_view(v)
    assert facts_equivalent(f, v) == []
    drifted = copy.deepcopy(v)
    drifted["horizons"]["1h"]["range_width_pct"] = 9.99
    assert facts_equivalent(f, drifted) == ["h1"]


def test_the_flag_is_off_and_render_refuses_unknown_screens():
    assert enabled(CFG) is False
    with pytest.raises(ValueError):
        render("check", 1, "ru", {})
    with pytest.raises(ValueError):
        render("btc", 4, "ru", from_view(_calm()))


def test_level_alert_uses_the_level_name_from_its_kind():
    f = from_alert("level", {"at": NOW.isoformat(), "level_kind": "PDH", "level": 62950.0, "side": 1,
                            "period": "day", "price": 62970.0, "history": HIST})
    ru = norm(plain(render("level", 1, "ru", f)[0]))
    assert ru.startswith("📍 Касание уровня: максимум вчера 62 950") and "Цена 62 970" in ru
