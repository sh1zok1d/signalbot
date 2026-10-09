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
from beta.ux.phrases import EMOJI, FORBIDDEN, MACHINE, PHRASES
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


def _degraded(reasons=("FAMILY_UNUSABLE:oi",)):
    v = _ranked(_calm(), range_rank=0.5, volume_rank=0.6)
    v["product_status"], v["status_reasons"] = "DATA DEGRADED", list(reasons)
    return v


def _all_renders():
    """Every P0 screen and level, both languages, over calm and busy states and the notifications."""
    out = []
    for v in (_calm(), _busy(), _view("stale_none"), _degraded()):
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
    blocks = plain(render("btc", 1, "ru", f)[0]).split("\n\n")
    # header · state line + one context sentence · «🎯 Рядом» with at most 2 levels · the calendar line
    assert len(blocks[1].splitlines()) <= 2 and len(blocks) <= 4
    near = [b for b in blocks if b.startswith("🎯 Рядом")]
    assert near and len(near[0].splitlines()) <= 3


def test_rule_B_l2_is_compact():
    heads = {lang: [PHRASES[k][0 if lang == "ru" else 1] for k in ("b_now", "b_hist", "b_not")] for lang in LANGS}
    for v in (_calm(), _busy()):
        f = from_view(v)
        for lang in LANGS:
            blocks = plain(render("btc", 2, lang, f)[0]).split("\n\n")[1:]
            assert 1 <= len(blocks) <= 3 and blocks[0].startswith(heads[lang][0])
            assert all(b.splitlines()[0] in heads[lang] for b in blocks)
            assert all(len(x) <= 160 for b in blocks for x in b.splitlines()[1:])


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
        lines = text.split("\n\n")[1].splitlines()
        assert lines[0].startswith("↑ " + high) and lines[1].startswith("↓ " + low)
    # the name is a function of the member kind only: a swapped kind swaps the name, nothing else can
    swapped = copy.deepcopy(v)
    swapped["decision"]["levels"]["above"][0]["members"][0]["kind"] = "PWL"
    assert plain(render("levels", 1, "ru", from_view(swapped))[0]).split("\n\n")[1].startswith(
        "↑ " + level_name({"kind": "PWL"}, "ru"))


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
        assert p.ok and not p.stack and "\x00" not in h, (screen, h)
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
HISTORICAL = (r"×", r"(обычно|usually)\W+\$?\d", r"\d+\s?(дн|days?)\b", r"(случа|cases)", r"(интервал|interval)",
              r"\bN\s?=", r"\d\s?% случаев", r"п\.п\.|\bpp\b")


def test_no_historical_number_on_l1():
    """L1 states current observations only: the move, the distance to a level, the calendar. No baseline,
    N, interval, share of history or ratio to «обычно»."""
    for v in (_calm(), _busy(), _view("stale_none"), _degraded()):
        for lang in LANGS:
            body = norm(plain(render("btc", 1, lang, from_view(v))[0]))
            for pat in HISTORICAL:
                assert not re.search(pat, body), (pat, body)


def test_no_machine_language_reaches_a_user():
    for screen, lvl, lang, (h, buttons) in _all_renders():
        txt = plain(h) + " ".join(label for row in buttons for label, _d in row)
        for tok in MACHINE:
            assert tok not in txt, (screen, lvl, lang, tok, txt)
        assert not re.search(r"\b[a-z]+_[a-z_]+\b", txt), (screen, txt)       # no snake_case ids
        assert not re.search(r"\b[A-Z]{3,}_[A-Z_]+\b", txt), (screen, txt)    # no CONSTANT_IDS


def test_notifications_have_one_headline_one_sentence_and_a_window():
    for screen, _l, lang, (h, buttons) in _all_renders():
        if screen not in ("hour", "level", "move", "brief"):
            continue
        head, body = plain(h).split("\n\n")
        assert re.search(r"\d", head) and head[0] in "".join(EMOJI), head          # the headline carries its number
        lines = body.splitlines()
        assert 1 <= len(lines) <= 3
        assert re.search(r"\d\d:\d\d(–\d\d:\d\d)? (Киев|Kyiv)$", lines[-1]), lines
        assert buttons and len(buttons) == 1


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
    ru, en = plain(render("btc", 1, "ru", f)[0]), plain(render("btc", 1, "en", f)[0])
    assert "💤 Спокойно. За час −0,84%." in norm(ru) and "💤 Calm. −0.84% over the hour." in norm(en)
    # with mature, ordinary ranks the calm line says range and volume are as usual
    v = _ranked(_calm(), range_rank=0.5, volume_rank=0.6)
    assert "💤 Спокойно. За час −0,84%, диапазон и объём как обычно." in norm(plain(render("btc", 1, "ru", from_view(v))[0]))


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
    assert ru.startswith("🎯 BTC у уровня: максимум вчера 62 950") and "цена 62 970" in ru


def test_level_card_takes_its_zone_from_the_view_and_degrades_without_one():
    """Track B's finding: facts from `from_view` carry no `zone`. The card takes the level at the price, else
    the nearest level of either side; with none it says «Уровней рядом нет», never raises."""
    busy = from_view(_busy())                                   # has levels.at (PDL)
    ru = norm(plain(render("level_card", 1, "ru", busy)[0]))
    assert ru.splitlines()[0] == "🎯 минимум вчера 62 490"        # the zone at the price (its edge), not the nearest
    v = _view("unusual")                                       # no level at the price: the nearest one (+0.75%)
    ru = norm(plain(render("level_card", 1, "ru", from_view(v))[0]))
    assert ru.splitlines()[0] == "🎯 максимум вчера 62 950"
    for lang, none in (("ru", "Уровней рядом нет."), ("en", "No levels nearby.")):
        h, b = render("level_card", 1, lang, from_view(_calm()))
        assert none in plain(h) and b == [[(PHRASES["btn_back"][0 if lang == "ru" else 1], "ux:levels:1")]]
        h, _b = render("level_card", 1, lang, {})
        assert none in plain(h)


def test_l1_anatomy_and_l3_groups():
    f = from_view(_busy())
    ru = norm(plain(render("btc", 1, "ru", f)[0])).split("\n\n")
    assert ru[0] == "₿ BTC · $62 480 · 14:10 Киев"
    assert ru[1].splitlines()[0] == "⚡ BTC −0,84% за час"
    near = ru[2].splitlines()
    assert near[0] == "🎯 Рядом" and near[1] == "🎯 у цены: минимум вчера 62 490"      # at the price: no arrow, no 0,00 %
    assert all(x[0] in "↑↓" for x in near[2:]) and "0,00" not in ru[2]
    en = norm(plain(render("btc", 1, "en", f)[0])).split("\n\n")
    assert en[0] == "₿ BTC · $62,480 · 14:10 Kyiv"
    l3 = norm(plain(render("btc", 3, "ru", f)[0])).split("\n\n")
    assert [b.splitlines()[0] for b in l3[1:]] == ["📊 Цена и диапазон", "📊 Позиции и поток", "🎯 Уровни",
                                                    "🔎 История похожих"]
    hist = l3[4].splitlines()[1]
    assert "812" in hist and "43%" in hist and "интервал" in hist     # N, baseline and interval on L3
    en3 = norm(plain(render("btc", 3, "en", f)[0]))
    assert "Strong selling" in en3 and "buyer-initiated" not in en3 and "data as of" not in en3


def _l1_body(v, lang="ru"):
    return norm(plain(render("btc", 1, lang, from_view(v))[0])).split("\n\n", 1)[1]


def test_calm_family_states_read_differently():
    usual = _l1_body(_ranked(_calm(), range_rank=0.5, volume_rank=0.6))
    narrow = _l1_body(_ranked(_calm(), range_rank=0.05, volume_rank=0.6))          # compression
    thin = _l1_body(_ranked(_calm(), range_rank=0.5, volume_rank=0.05))
    both = _l1_body(_ranked(_calm(), range_rank=0.05, volume_rank=0.05))
    assert usual.startswith("💤 Спокойно. За час −0,84%, диапазон и объём как обычно.")
    assert narrow.startswith("💤 Тихо. За час −0,84%, диапазон уже обычного, объём как обычно.")
    assert thin.startswith("💤 Тихо. За час −0,84%, диапазон как обычно, объём ниже обычного.")
    assert both.startswith("💤 Тихо. За час −0,84%, диапазон уже обычного, объём ниже обычного.")
    weekend = _ranked(_calm(), range_rank=0.5, volume_rank=0.05)
    weekend["data_through"] = "2024-03-09T10:00:00+00:00"                            # a Saturday
    assert _l1_body(weekend).startswith("💤 Выходные. За час −0,84%")
    night = _ranked(_calm(), range_rank=0.05, volume_rank=0.05)
    night["market"] = {"window_hours": 8, "window": {
        "window_start": "2024-03-04T00:00:00+00:00", "window_end": "2024-03-04T08:00:00+00:00",
        "price_move_pct": 0.3, "high": 64390.0, "low": 63980.0}}
    assert "📅 За 8 ч (02:00–10:00 Киев): BTC +0,30%, диапазон 63 980–64 390." in _l1_body(night)
    assert len({usual, narrow, thin, both, _l1_body(weekend), _l1_body(night)}) == 6
    l2 = norm(plain(render("btc", 2, "ru", from_view(_ranked(_calm(), range_rank=0.05, volume_rank=0.05)))[0]))
    assert "меньше, чем обычно" in l2 and "Торгуют меньше" in l2


def test_stale_shows_nothing_current_and_degraded_names_the_partial_input():
    stale = from_view(_view("stale_none"))
    for lang in LANGS:
        l1 = plain(render("btc", 1, lang, stale)[0])
        assert l1.startswith("₿ BTC\n\n🔎") and "$" not in l1 and len(l1.split("\n\n")) == 2
        l3 = plain(render("btc", 3, lang, stale)[0])
        assert not re.search(r"%|\$", l3), l3                                  # no current number at all
    deg = from_view(_degraded())
    ru = norm(plain(render("btc", 1, "ru", deg)[0]))
    assert ru.startswith("₿ BTC · $") and "🔎 Неполные данные: открытые позиции. Остальное — ниже." in ru
    assert "💤 Спокойно. За час −0,84%, диапазон и объём как обычно." in ru              # the valid rest still shows
    l3 = norm(plain(render("btc", 3, "ru", deg)[0]))
    assert "Открытых позиций" not in l3 and "Диапазон за час" in l3
    vol = norm(plain(render("btc", 1, "ru", from_view(_degraded(("FAMILY_UNUSABLE:volume",))))[0]))
    assert "Неполные данные: объём." in vol and "объём" not in vol.split("Остальное — ниже.")[1].split("🎯")[0]
    assert _l1_body(_view("stale_none")) != _l1_body(_degraded())


def test_architect_text_fixes():
    f = from_view(_ranked(_busy(), range_rank=0.5, volume_rank=0.5))
    f["episode"] = {"event_type": "PRICE_OI_CONTRACTION_DOWN", "state": "TRIGGERED", "triggered": True}
    l2 = norm(plain(render("btc", 2, "ru", f)[0]))
    assert "Идёт резкое падение: цена за пять минут упала сильнее обычного" in l2 and "условия выполняются" not in l2
    assert "Sharp drop: the price fell more than usual" in norm(plain(render("btc", 2, "en", f)[0]))
    for lang in LANGS:                                                  # 📊 is data only; L2 block titles plain
        h = render("btc", 2, lang, f)[0]
        assert "📊" not in h and h.startswith("<b>🔎")
    l3 = norm(plain(render("btc", 3, "ru", from_view(_busy()))[0]))
    assert "Оценка диапазона на 24 ч:" in l3 and "Обычный диапазон" not in l3
    assert "24h range estimate:" in norm(plain(render("btc", 3, "en", from_view(_busy()))[0]))
    assert "оценки суточного диапазона" in PHRASES["cx_corridor_edge"][0]
    mv = from_alert("move", {"at": "2024-03-04T06:00:00+00:00", "start": "2024-03-04T05:45:00+00:00", "price": 62250.0,
                             "open": 63100.0, "close": 62250.0, "move_pct": -1.35, "every_days": 9, "near": []})
    assert "Для 15 минут это резкое движение." in plain(render("move", 1, "ru", mv)[0])
    assert "For 15 minutes, this is a sharp move." in plain(render("move", 1, "en", mv)[0])


_THRESHOLDS = re.compile(r"\d+\s*%|\b30\b|\b45\b|дн(ей|я)\b|\bdays?\b|\b30d\b|медиан|median|5м|\b5m\b|"
                         r"bottom|top |нижних|верхних|бакет|bucket|delta", re.I)


def test_every_event_type_has_a_trader_line_without_thresholds():
    from beta.config import EVENT_TYPES
    from beta.ux.phrases import EPISODES
    assert set(EPISODES) == set(EVENT_TYPES)
    for et in EVENT_TYPES:
        for prefix in ("ep_", "epn_"):
            ru, en, rule = PHRASES[prefix + EPISODES[et]]
            assert ru and en and rule
        f = from_view(_ranked(_busy(), range_rank=0.5, volume_rank=0.5))
        f["episode"] = {"event_type": et, "state": "TRIGGERED", "triggered": True}
        for lang in LANGS:
            i = 0 if lang == "ru" else 1
            names = (PHRASES["epn_" + EPISODES[et]][i].lower(), PHRASES["ep_" + EPISODES[et]][i].split(":")[0].lower())
            assert not _THRESHOLDS.search(PHRASES["ep_" + EPISODES[et]][0 if lang == "ru" else 1])
            for lv in (1, 2):                          # the rendered episode lines carry no rule threshold
                lines = [x for x in norm(plain(render("btc", lv, lang, f)[0])).splitlines() if any(n in x.lower() for n in names)]
                assert lines and not any(_THRESHOLDS.search(x) for x in lines), (et, lang, lv, lines)
        assert not re.search(r"Идёт (агрессивные|ликвидации)|Идут (резк|набор)", norm(plain(render("btc", 2, "ru", f)[0])))
    en = norm(plain(render("btc", 2, "en", f)[0]))
    assert "initiated" not in en
