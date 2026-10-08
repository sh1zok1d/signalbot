"""Level race, live side (beta/level_race_live.py): the HIST journal at T0 / T15, the outcome rule
LEVEL_RACE_4H_V1 against the #352 `classify`, the /levels and /check lines, the flags and the display
links. The parity of the outcome rule with #352 is in tests/research/test_level_race_outcome_parity.py
(tests/beta never imports scripts.research). Synthetic bars only."""
import asyncio
import math
import re
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from beta import claims as cj
from beta import level_race_live as LR
from beta.config import BetaConfig
from beta.hist_series import BAR_MS, BARS_PER_DAY, Bars
from beta.level_race import load_hist_table
from beta.i18n import assert_descriptive
from beta.levels import structural_first_touches

T0_2021 = 1609459200000
UTC = timezone.utc
TABLE = load_hist_table()
FORBIDDEN = re.compile(r"пробо|отбо|BREAK|REJECT|BEYOND|BACK\b|покуп|прода|лонг|шорт|long|short", re.IGNORECASE)


def _bars(days=80, seed=7, vol=0.0025):
    rng = np.random.default_rng(seed)
    n = days * BARS_PER_DAY
    c = 30000.0 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    o = np.r_[30000.0, c[:-1]]
    wig = np.abs(rng.normal(0, vol / 2, n))
    return Bars(t0=T0_2021, open=o, high=np.maximum(o, c) * (1 + wig), low=np.minimum(o, c) * (1 - wig), close=c,
                volume=np.ones(n), quote=np.ones(n), taker_buy_quote=np.full(n, np.nan), oi=np.full(n, np.nan))


def _ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def _cut(b, ms):
    """The live tape at `ms`: the 5m bars closed by then."""
    return b.slice(0, (ms - b.t0) // BAR_MS)


def _events(b):
    return [e for e in structural_first_touches(b) if e["eligible"] and e["j"] + 60 < b.n and e["j"] > 300]


def _cfg(**lr):
    base = BetaConfig.load()
    return base.with_overrides(level_race={**dict(base.raw["level_race"]), **lr})


B = _bars()
EVS = _events(B)


def _t15_event(b=B):
    for e in _events(b):
        v = LR.landmark_view(_cut(b, LR.landmark_ms(e, "T15")), e, "T15", TABLE)
        if v is not None:
            return e, v
    raise AssertionError("no T15-eligible event in the synthetic tape")


def test_registry_holds_every_race_name_once():
    assert set(LR.CLASSES) == {"L2_LEVEL_RACE_HIST_T0_4H", "L2_LEVEL_RACE_HIST_T15_4H", "L3_LEVEL_RACE_T0_4H",
                               "L3_LEVEL_RACE_T15_4H", "L3_GENERIC_RACE_4H"}
    assert LR.CLASSES["L3_GENERIC_RACE_4H"]["display"] == ()              # journal only, never shown
    assert LR.SETTINGS["model_states"] == "level_race.model_states_enabled"
    for cls in LR.HIST_CLASS.values():                                   # the journal knows the HIST classes
        assert cj.CLASSES[cls][2] == "LEVEL_RACE_4H_V1" and cls in LR.CLASSES
        assert all(k in LR.TEMPLATE_KEYS.values() for k in cj.CLASSES[cls][1])
        assert re.fullmatch(r"[0-9a-f]{64}", cj.template_digest(cls))


def test_flags_are_off_by_default_and_the_mode_stays_hist_without_a_model():
    cfg = BetaConfig.load()
    assert dict(cfg.raw["level_race"]) == {"journal_enabled": False, "display_enabled": False,
                                           "model_states_enabled": False, "push_trigger": "legacy"}
    assert LR.mode(_cfg(model_states_enabled=True)) == "HIST"          # no frozen model yet: the switch is inert
    with pytest.raises(Exception):
        BetaConfig.load().with_overrides(level_race={"journal_enabled": True})


def test_landmarks_are_due_only_within_the_write_window_and_from_closed_bars():
    e = EVS[0]
    t0 = LR.landmark_ms(e, "T0")
    assert t0 == e["t0_ms"] and LR.landmark_ms(e, "T15") == e["t15_ms"]
    due = LR.due_landmarks(_cut(B, t0), _ts(t0 + 60_000), TABLE)
    mine = [v for v in due if v["event_id"] == e["event_id"]]
    assert [v["landmark"] for v in mine] == ["T0"]
    assert mine[0]["position"] == float(B.close[e["j"]])               # the touch bar's close, nothing later
    late = LR.due_landmarks(_cut(B, t0 + 15 * 60_000), _ts(t0 + 11 * 60_000 + 60_000), TABLE)
    assert not [v for v in late if v["event_id"] == e["event_id"] and v["landmark"] == "T0"]
    before = LR.due_landmarks(_cut(B, t0 - BAR_MS), _ts(t0 - 1), TABLE)
    assert not [v for v in before if v["event_id"] == e["event_id"]]


def test_t15_has_no_statement_after_a_barrier_on_j1_or_j2():
    e, v = _t15_event()
    j = e["j"]
    b = _bars()
    b.high[j + 1] = v["p_up"] * 1.0001
    assert LR.landmark_view(_cut(b, e["t15_ms"]), e, "T15", TABLE) is None
    b = _bars()
    b.low[j + 2] = v["p_dn"] * 0.9999
    assert LR.landmark_view(_cut(b, e["t15_ms"]), e, "T15", TABLE) is None


def test_claim_rows_carry_the_shown_numbers_b0_prices_and_mode():
    e, v = _t15_event()
    now = _ts(e["t15_ms"] + 30_000)
    rows = cj.level_race_claims([v], now=now)
    assert len(rows) == 1
    r = rows[0]
    assert r["claim_class"] == "L2_LEVEL_RACE_HIST_T15_4H" and r["level"] == "L2"
    assert r["issue_slot"] == r["as_of"] == _ts(e["t15_ms"]) and r["horizon_end"] == _ts(e["window_end_ms"])
    assert r["subject_key"] == f"{e['event_id']}:T15" and r["eval_rule_id"] == "LEVEL_RACE_4H_V1"
    s, n = r["subject"], r["numbers"]
    assert s["mode"] == "HIST" and s["table_sha256"] == TABLE["table_sha256"] and s["cell"] == v["cell"]
    from beta.build import build_sha
    assert s["build_sha"] == build_sha() and s["versions"]["event"] == "BETA_STRUCTURAL_TOUCH_V1"
    assert s["p_up"] == v["p_up"] and s["p_dn"] == v["p_dn"] and s["p_dn"] < s["position"] < s["p_up"]
    assert math.isclose(sum(n["event_b0"].values()), 1.0, abs_tol=1e-5)
    if v["template"] != "LR_HIST_LOW_N_V1":
        assert sum(n["printed"]["h"].values()) == 100 and sum(n["printed"]["b"].values()) == 100
    assert r["eligible_reason"] == "LANDMARK_T15"
    assert "mode:HIST" in r["rule_version"]


def test_t15_window_starts_at_j_plus_3():
    e, v = _t15_event()
    b = _bars()
    j = e["j"]
    for k in range(j + 3, j + 49):                       # nothing reaches a barrier inside the window ...
        b.high[k] = min(b.high[k], v["p_up"] * 0.999)
        b.low[k] = max(b.low[k], v["p_dn"] * 1.001)
    assert LR.classify(b, touch_open_ms=e["touch_open_ms"], landmark="T15", p_up=v["p_up"], p_dn=v["p_dn"])["outcome"] \
        == "NEITHER"
    b.high[j + 3] = v["p_up"] * 1.001                     # ... the first bar of the T15 window counts
    b.low[j + 3] = v["p_dn"] * 0.999
    assert LR.classify(b, touch_open_ms=e["touch_open_ms"], landmark="T15", p_up=v["p_up"], p_dn=v["p_dn"])["outcome"] \
        == "AMBIGUOUS"


def test_the_journal_scores_once_the_window_is_in_the_tape():
    e, v = _t15_event()
    row = cj.level_race_claims([v], now=_ts(e["t15_ms"]))[0]
    claim = {**row, "eval_rule": row["eval_rule"]}
    end = e["window_end_ms"]
    assert cj.evaluate(claim, _cut(B, end - BAR_MS), [], now=_ts(end)) is None            # not closed yet
    status, realized = cj.evaluate(claim, _cut(B, end), [], now=_ts(end + 60_000))
    assert status == "COMPLETE" and realized["outcome"] in ("UP", "DN", "NEITHER", "AMBIGUOUS")
    assert realized == LR.classify(B, touch_open_ms=e["touch_open_ms"], landmark="T15", p_up=v["p_up"], p_dn=v["p_dn"])
    holes = _bars()
    holes.high[e["j"] + 10:e["j"] + 20] = np.nan
    holes.low[e["j"] + 10:e["j"] + 20] = np.nan
    assert cj.evaluate(claim, _cut(holes, end), [], now=_ts(end + 60_000)) is None          # < 90 %: wait ...
    st, rz = cj.evaluate(claim, _cut(holes, end), [], now=_ts(end) + timedelta(hours=7))    # ... then NO_DATA
    assert st == "NO_DATA" and rz["usable"] is False


def test_report_keeps_cells_and_modes_apart_and_excludes_ambiguous():
    e, v = _t15_event()
    row = cj.level_race_claims([v], now=_ts(e["t15_ms"]))[0]
    rows = [{**row, "status": "COMPLETE", "realized": {"usable": True, "outcome": y}} for y in ("UP", "DN", "AMBIGUOUS")]
    model = {**row, "subject": {**row["subject"], "mode": "MODEL"}, "status": "COMPLETE",
             "realized": {"usable": True, "outcome": "NEITHER"}}
    rep = cj.claims_report(rows + [model])["classes"]["L2_LEVEL_RACE_HIST_T15_4H"]
    hist = rep["cells"][f"HIST:{v['cell']}"]
    assert hist["scored"] == 2 and hist["ambiguous"] == 1
    assert rep["cells"][f"MODEL:{v['cell']}"]["scored"] == 1


def _block(b, now, price):
    return {"available": True, "price": price, "price_ts": (now - timedelta(minutes=1)).isoformat(),
            "as_of": now.isoformat(), "levels": {"above": [], "below": [], "at": None, "all": []},
            "level_race": LR.display_block(b, now, TABLE, price=price)}


def test_t15_line_is_shown_until_the_race_is_decided_and_never_says_break_or_reject():
    from beta.decision_format import format_levels, race_lines
    e, v = _t15_event()
    at = e["t15_ms"] + 2 * 60_000
    b = _cut(B, e["t15_ms"])
    price = float(b.close[-1])
    blk = _block(b, _ts(at), price)
    assert [r["event_id"] for r in blk["level_race"]["races"]] == [e["event_id"]]
    for lang in ("ru", "en"):
        lines = race_lines(blk, lang, "levels")
        assert len(lines) == 2 and not FORBIDDEN.search(" ".join(lines))
        text = format_levels(blk, lang, now=_ts(at))
        assert lines[1] in text
    ru = race_lines(blk, "ru", "levels")[1]
    if v["template"] == "LR_HIST_V1":
        assert "верхняя" in ru and "нижняя" in ru and "ни одна" in ru and "обычно" in ru and "2020–2024" in ru
        assert ru.count("разница") == 3 and ru.count("95 % интервал") == 3 and "±" not in ru
        r0 = blk["level_race"]["races"][0]
        d = r0["printed_h"]["up"] - r0["printed_b"]["up"]          # the shown difference = the shown numbers
        assert f"разница {'0' if d == 0 else (f'+{d}' if d > 0 else f'−{-d}')} п.п." in ru
        assert assert_descriptive(ru, "ru") and "↳ цена вошла в зону" in race_lines(blk, "ru", "levels")[0]
    # before T0: nothing; between T0 and T15 the T0 statement (the push's full line) unless the touch close
    # lies outside the barrier pair; after a barrier is reached: nothing; after the window: nothing
    assert not [r for r in _block(_cut(B, e["t0_ms"] - BAR_MS), _ts(e["t0_ms"] - 1), price)["level_race"]["races"]
                if r["event_id"] == e["event_id"]]
    early = [r for r in _block(_cut(B, e["t0_ms"]), _ts(e["t0_ms"] + 60_000), float(B.close[e["j"]]))["level_race"]["races"]
             if r["event_id"] == e["event_id"]]
    assert all(r["landmark"] == "T0" for r in early)
    assert _block(b, _ts(at), v["p_up"] * 1.001)["level_race"]["races"] == []
    end = e["window_end_ms"]
    assert not [r for r in _block(_cut(B, end), _ts(end + 60_000), price)["level_race"]["races"]
                if r["event_id"] == e["event_id"]]
    # /check shows the race of the zone a checked price lies in, and only that
    assert len(race_lines(blk, "ru", "check", check_levels=[(e["zone_low"] + e["zone_high"]) / 2])) == 2
    assert race_lines(blk, "ru", "check", check_levels=[e["zone_high"] * 1.05]) == []
    # an unverified table is state OFF: no number
    assert LR.display_block(b, _ts(at), None) == {"state": "OFF", "races": []}
    assert race_lines({**blk, "level_race": {"state": "OFF", "races": blk["level_race"]["races"]}}, "ru", "levels") == []


class _Conn:
    def __init__(self):
        self.rows, self.links, self.queries = [], [], []

    async def insert_claim(self, row):
        key = (row["claim_class"], row["subject_key"], row["issue_slot"])
        if any((r["claim_class"], r["subject_key"], r["issue_slot"]) == key for r in self.rows):
            return None
        self.rows.append(row)
        return len(self.rows)

    async def fetch_slot_claims(self, *, issue_slot, classes):
        self.queries.append(issue_slot)
        return [{"claim_pk": k + 1, "claim_class": r["claim_class"], "subject_key": r["subject_key"]}
                for k, r in enumerate(self.rows) if r["issue_slot"] == issue_slot and r["claim_class"] in classes]

    async def insert_claim_displays(self, rows):
        self.links += rows
        return len(rows)


def test_writer_follows_its_flag_is_idempotent_and_links_displays_on_the_claims_own_slot():
    e, v = _t15_event()
    cap = {"bars": _cut(B, e["t15_ms"])}
    now = _ts(e["t15_ms"] + 60_000)
    conn = _Conn()
    assert asyncio.run(cj.record_level_race(conn, BetaConfig.load(), now=now, capture=cap)) == {"race_written": 0}
    on = _cfg(journal_enabled=True)
    rep = asyncio.run(cj.record_level_race(conn, on, now=now, capture=cap))
    assert rep["race_written"] >= 1 and any(r["subject_key"] == f"{e['event_id']}:T15" for r in conn.rows)
    assert asyncio.run(cj.record_level_race(conn, on, now=now, capture=cap))["race_written"] == 0
    blk = _block(cap["bars"], now + timedelta(minutes=70), float(cap["bars"].close[-1]))
    keys = cj.shown_keys("levels", blk)
    assert (f"L2_LEVEL_RACE_HIST_T15_4H", f"{e['event_id']}:T15", _ts(e["t15_ms"])) in keys
    n = asyncio.run(cj.record_displays(conn, surface="levels", shown=keys, now=now + timedelta(minutes=70)))
    assert n == 1 and conn.queries == [_ts(e["t15_ms"])] and conn.links[0]["surface"] == "levels"
    mid = (e["zone_low"] + e["zone_high"]) / 2
    assert cj.shown_keys("check", blk, check_levels=[mid]) == [k for k in keys if k[0].startswith("L2_LEVEL_RACE")]
    assert cj.shown_keys("check", blk, check_levels=[mid * 1.1]) == []


def test_decision_block_is_off_when_the_table_does_not_verify(monkeypatch):
    from beta import decision, level_race
    e, _v = _t15_event()
    b = _cut(B, e["t15_ms"])

    def bad(*_a, **_k):
        raise RuntimeError("level race HIST table digest mismatch")
    monkeypatch.setattr(level_race, "load_hist_table", bad)
    out = decision._level_race(b, _ts(e["t15_ms"] + 60_000), float(b.close[-1]))
    assert out["state"] == "OFF" and out["races"] == [] and out["error_type"] == "RuntimeError"
    monkeypatch.undo()
    assert decision._level_race(b, _ts(e["t15_ms"] + 60_000), float(b.close[-1]))["state"] == "HIST"


def test_a_hidden_line_never_comes_back():
    """A barrier reached on a closed bar after T15 hides the line for good, even after the price returns
    inside; a barrier inside the current 5m bar (closed 1m bars only) hides it too."""
    e, v = _t15_event()
    j = e["j"]
    b = _bars()
    b.high[j + 4] = v["p_up"] * 1.0005                     # reached on a closed bar after T15 ...
    later = _cut(b, e["t15_ms"] + 5 * BAR_MS)
    back_inside = (v["p_up"] + v["p_dn"]) / 2               # ... then back inside the pair
    for k in range(1, 4):                                   # on every later request, not only the first
        at = _ts(e["t15_ms"] + (4 + k) * BAR_MS + 60_000)
        shown = LR.display_block(_cut(b, e["t15_ms"] + (4 + k) * BAR_MS), at, TABLE, price=back_inside)
        assert all(r["event_id"] != e["event_id"] for r in shown["races"])
    tape = _cut(B, e["t15_ms"])
    one_min = [{"ts": _ts(e["t15_ms"]), "high": v["p_up"] * 1.0005, "low": v["p_dn"] * 1.0005, "close": back_inside}]
    shown = LR.display_block(tape, _ts(e["t15_ms"] + 90_000), TABLE, price=back_inside, closed_1m=one_min)
    assert all(r["event_id"] != e["event_id"] for r in shown["races"])


def test_journal_off_writes_nothing_and_reads_no_bars():
    class NoBars(dict):
        def get(self, key, default=None):
            raise AssertionError(f"bars read with the journal off: {key}")

        def __getitem__(self, key):
            raise AssertionError(f"bars read with the journal off: {key}")

    class NoWrites:
        def __getattr__(self, name):
            raise AssertionError(f"journal touched with the flag off: {name}")
    assert asyncio.run(cj.record_level_race(NoWrites(), BetaConfig.load(), now=_ts(EVS[0]["t0_ms"]),
                                            capture=NoBars())) == {"race_written": 0}


def test_coverage_counts_expected_against_written_and_shows_an_outage():
    end = B.t0 + B.n * BAR_MS
    since, until = end - 20 * 86_400_000, end
    rows = []
    for e in EVS:
        for lm in ("T0", "T15"):
            at = LR.landmark_ms(e, lm)
            if since < at <= until - LR.WRITE_WINDOW_MS:
                v = LR.landmark_view(B, e, lm, TABLE)
                if v is not None:
                    rows += cj.level_race_claims([v], now=_ts(at))
    full = LR.coverage(B, rows, since_ms=since, until_ms=until, table=TABLE)
    assert full["T0"]["expected"] > 5 and full["T0"]["missing"] == 0 and full["T0"]["unexpected"] == 0
    assert full["T15"]["written"] == full["T15"]["expected"]
    lost = rows[:3]                                       # a notifier outage: three records never written
    part = LR.coverage(B, rows[3:], since_ms=since, until_ms=until, table=TABLE)
    assert sum(part[lm]["missing"] for lm in ("T0", "T15")) == 3
    assert {r["subject_key"] for r in lost} <= set(part["T0"]["missing_keys"] + part["T15"]["missing_keys"])

def test_display_needs_the_journal():
    base = BetaConfig.load()
    with pytest.raises(Exception, match="journal"):
        _cfg(display_enabled=True)
    with pytest.raises(Exception, match="journal"):
        base.with_overrides(decision={**dict(base.raw["decision"]), "claim_journal": False},
                            level_race={**dict(base.raw["level_race"]), "journal_enabled": True,
                                        "display_enabled": True})
    assert LR.setting(_cfg(journal_enabled=True, display_enabled=True), "display_enabled")


def test_journal_and_registry_agree_on_every_template():
    for cls, spec in LR.CLASSES.items():
        if cls in cj.CLASSES:
            assert set(cj.CLASSES[cls][1]) == {LR.TEMPLATE_KEYS[t] for t in spec["templates"]}, cls
            assert cj.CLASSES[cls][2] == spec["rule"]
    assert set(LR.HIST_CLASS.values()) <= set(cj.CLASSES)


def test_display_only_journaled_lines_and_none_in_an_event_zone():
    from beta.decision import race_display
    e, v = _t15_event()
    b = _cut(B, e["t15_ms"])
    now = _ts(e["t15_ms"] + 2 * 60_000)
    price = float(b.close[-1])

    class Conn:
        def __init__(self, rows):
            self.rows = rows

        async def fetch_slot_claims(self, *, issue_slot, classes):
            return [{"claim_class": r["claim_class"], "subject_key": r["subject_key"]} for r in self.rows
                    if r["issue_slot"] == issue_slot and r["claim_class"] in classes]
    none = asyncio.run(race_display(Conn([]), b, now, price, zones={}))
    assert none["races"] == [] and none["not_journaled"] >= 1                # not written yet: not shown
    rows = cj.level_race_claims([v], now=_ts(e["t15_ms"]))
    shown = asyncio.run(race_display(Conn(rows), b, now, price, zones={}))
    assert [r["event_id"] for r in shown["races"]] == [e["event_id"]]
    hidden = asyncio.run(race_display(Conn(rows), b, now, price, zones={"4h": [{"kind": "CPI"}]}))
    assert hidden == {"state": "HIST", "races": [], "hidden": "EVENT_ZONE"}
    cal = {"events": [{"kind": "CPI", "at": _ts(e["t15_ms"] + 3_600_000)}]}
    flagged = cj.level_race_claims([v], now=_ts(e["t15_ms"]), calendar=cal)[0]
    assert flagged["subject"]["event_zone"] is True                          # still written, flagged
    assert cj.level_race_claims([v], now=_ts(e["t15_ms"]), calendar={"events": []})[0]["subject"]["event_zone"] is False


def test_head_names_the_level_and_dates_an_earlier_day():
    from beta.decision_format import race_lines
    e, v = _t15_event()
    b = _cut(B, e["t15_ms"])
    blk = _block(b, _ts(e["t15_ms"] + 120_000), float(b.close[-1]))
    ru = race_lines(blk, "ru", "levels")[0]
    en = race_lines(blk, "en", "levels")[0]
    assert f"зону {e['kind']} (" in ru and f"the {e['kind']} (" in en and " zone at " in en
    late = {**blk, "as_of": _ts(e["t15_ms"] + 3 * 3_600_000 + 86_400_000).isoformat()}
    assert re.search(r"в [А-Яа-я]{2} \d\d\.\d\d \d\d:\d\d", race_lines(late, "ru", "levels")[0])
