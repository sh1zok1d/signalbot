"""Claim journal (docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md): writer, scorer, report, displays (pure)."""
import asyncio
import dataclasses
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from beta import claims as cj
from beta import decision_format as df
from beta.config import BetaConfig
from beta.hist_series import BAR_MS, bars_from_rows
from beta.state_tape import iso, sha256_json

UTC = timezone.utc
CFG = BetaConfig.load()
ROOT = Path(__file__).resolve().parents[2]
SLOT = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
MODEL = {"version": "BETA_RANGE_MODEL_V1",
         "horizons": {h: {"q_one": [0.01 * k for k in range(1, 100)] + [1.2, 1.5]} for h in ("1h", "4h", "24h")}}


def _zone(kinds, edge, dist, p4=0.3, p24=0.6):
    return {"low": edge, "high": edge, "edge": edge, "distance_pct": dist, "kinds": kinds,
            "members": [{"kind": k, "price": edge} for k in kinds], "touch": {"4h": p4, "24h": p24}}


def _block(**over):
    hz = {h: {"scale_pct": s, "half_width_pct": s * 1.2, "lower": 60000.0, "upper": 64000.0, "typical_move_pct": s / 2}
          for h, s in (("1h", 0.6), ("4h", 1.2), ("24h", 3.0))}
    b = {"available": True, "price": 62480.0, "price_ts": (SLOT - timedelta(minutes=1)).isoformat(),
         "corridor": {"coverage": 0.8, "horizons": hz}, "event_zone": {},
         "levels": {"above": [_zone(["PDH"], 62950.0, 0.75)], "below": [_zone(["ASIA_L"], 61900.0, -0.93, 0.4, 0.55)],
                    "at": None, "all": []},
         "analogues": {}}
    b.update(over)
    return b


def _grid(start, closes, highs=None, lows=None):
    rows = [{"open_time_ms": int((start + timedelta(minutes=5 * k)).timestamp() * 1000), "open": c,
             "high": (highs or closes)[k], "low": (lows or closes)[k], "close": c} for k, c in enumerate(closes)]
    return bars_from_rows(rows)


# ---- identities ----------------------------------------------------------------------------------
def test_dh3_p1_numbers_are_the_research_record():
    rec = json.loads((ROOT / "docs/research/DH3_RESULT_DISCOVERY.json").read_text())["CELLS"]["DH3-P1"]
    assert cj.DH3_P1_RECORD["adjusted_shift_log"] == rec["ADJUSTED_SHIFT"]
    assert cj.DH3_P1_RECORD["ci95_log"] == rec["CI95"]
    assert cj.DH3_P1_RECORD["raw_mean_state"] == rec["MEAN_STATE"]
    assert cj.DH3_P1_RECORD["raw_mean_comparator"] == rec["MEAN_COMPARATOR"]
    assert (cj.DH3_P1_RECORD["n"], cj.DH3_P1_RECORD["n_state"], cj.DH3_P1_RECORD["n_comparator"]) == \
        (rec["N"], rec["N_STATE"], rec["N_COMPARATOR"])
    assert cj.DH3_P1_RECORD["bar_log"] == rec["BAR"] and rec["ENDPOINT"] == "RANGE_4H"
    from beta.research_link import load_findings
    entry = next(f for f in load_findings() if f["id"] == "DH3-P1")
    assert entry["status"] == cj.DH3_P1_RECORD["status"] and entry["record"] == cj.DH3_P1_RECORD["record"]


def test_every_class_has_a_level_a_template_and_a_frozen_rule():
    for cls, (level, keys, rule) in cj.CLASSES.items():
        assert cls.startswith(level + "_") and rule in cj.EVAL_RULES
        assert len(cj.template_digest(cls)) == 64
        r = cj.eval_rule(rule)
        assert r["id"] == rule and r["journal"] == cj.JOURNAL_VERSION and sha256_json(r) == sha256_json(cj.eval_rule(rule))


def test_a_template_change_changes_the_digest(monkeypatch):
    from beta import i18n
    before = cj.template_digest("L3_LEVEL_TOUCH_4H")
    monkeypatch.setitem(i18n._CATALOG, "lv_touch", {"ru": "иначе", "en": "other"})
    assert cj.template_digest("L3_LEVEL_TOUCH_4H") != before


def test_printed_probability_is_what_the_surfaces_print():
    for p in (0.004, 0.012, 0.334, 0.995):
        assert cj.printed_prob(p) == df.fmt_prob(p, "ru").replace("&lt;", "<").replace("&gt;", ">")


# ---- hourly writer --------------------------------------------------------------------------------
def test_touch_claims_cover_every_zone_and_the_distance_grid():
    rows = cj.touch_claims(_block(), MODEL, now=SLOT + timedelta(seconds=40), slot=SLOT)
    level = [r for r in rows if r["claim_class"].startswith("L3_LEVEL_TOUCH_")]
    grid = [r for r in rows if r["claim_class"].startswith("L3_DISTANCE_TOUCH_")]
    assert len(level) == 4 and len(grid) == 3 * len(cj.TOUCH_GRID_PCT) * 2
    pdh = next(r for r in level if r["claim_class"] == "L3_LEVEL_TOUCH_24H" and r["subject_key"] == "+1:62950.00")
    assert pdh["numbers"] == {"probability": 0.6, "printed": "60%"} and pdh["subject"]["side"] == 1
    assert pdh["as_of"] == SLOT and pdh["horizon_end"] == SLOT + timedelta(hours=24)
    assert pdh["issue_slot"] == SLOT and pdh["eligible_reason"] == "LEVEL_ZONE_SHOWN"
    from beta.rangecast import touch_probability
    g = next(r for r in grid if r["claim_class"] == "L3_DISTANCE_TOUCH_4H" and r["subject_key"] == "-1:2.0")
    assert g["numbers"]["probability"] == round(touch_probability(MODEL, "4h", 1.2, 2.0), 4)
    assert g["subject"]["level"] == round(62480.0 * 0.98, 2)
    assert {r["claim_digest"] for r in rows}.__len__() == len(rows)


def test_no_claim_inside_an_event_zone_horizon():
    blk = _block()
    del blk["corridor"]["horizons"]["24h"]                       # decision.py drops it at the source
    for z in blk["levels"]["above"] + blk["levels"]["below"]:
        z["touch"].pop("24h")
    rows = cj.touch_claims(blk, MODEL, now=SLOT, slot=SLOT)
    assert rows and not [r for r in rows if r["claim_class"].endswith("_24H")]


def _stats(n=412, base=0.51):
    from beta.analogues import ANALOGUES_VERSION
    cell = {"n": n, "days": 300, "p_up": 0.53, "baseline": {"p_up": base}, "range_ratio": 1.3,
            "verdicts": {"direction": "as_usual", "range": "differs"}}
    return {"_stats_pk": 7, "_payload_digest": "a" * 64,
            "analogues": {"version": ANALOGUES_VERSION, "windows": {
                "1h": {"short_exit": {"n_anchors": n, "outcomes": {"1h": cell, "4h": {**cell, "n": 20}}}},
                "4h": {"squeeze": {"n_anchors": n, "outcomes": {"4h": cell, "24h": cell}}}}}}


def test_analog_claims_mark_what_is_stated_and_keep_the_baseline_cohort(monkeypatch):
    from beta import interpretation
    keys = {"1h": ("short_exit", interpretation.INTERPRETED), "4h": ("squeeze", interpretation.COMPRESSION)}
    monkeypatch.setattr(interpretation, "interpret", lambda cfg, ctx, horizon, liquidation_episodes=():
                        {"key": keys[horizon][0], "kind": keys[horizon][1]})
    b = _grid(SLOT - timedelta(days=40), [60000.0] * (40 * 288))
    state = {"context_version": "BETA_CONTEXT_1H_V3",
             "context_1h": {"window_end": iso(SLOT)}, "context_4h": {"window_end": iso(SLOT)}}
    rows = cj.analog_claims(CFG, state, _stats(), b, now=SLOT, slot=SLOT, context_pk=11)
    by = {r["claim_class"]: r for r in rows}
    assert set(by) == {"L2_STATE_ANALOG_1H_1H", "L2_STATE_ANALOG_1H_4H", "L2_STATE_ANALOG_4H_4H", "L2_STATE_ANALOG_4H_24H"}
    one = by["L2_STATE_ANALOG_1H_1H"]
    assert one["eligible_reason"] == cj.SHOWN and one["numbers"]["diff_pp"] == 2.0
    assert one["numbers"]["printed"] == {"observed": "53%", "baseline": "51%", "diff_pp": "+2.0", "interval_pp": None}
    assert one["numbers"]["interval_pp"] is None                     # a payload built before X1 has no interval
    with_ci = _stats()
    cell = with_ci["analogues"]["windows"]["1h"]["short_exit"]["outcomes"]["1h"]
    cell["ci95"] = {"direction": [-0.011, 0.052]}
    shown = {r["claim_class"]: r for r in cj.analog_claims(CFG, state, with_ci, b, now=SLOT, slot=SLOT)}
    nums = shown["L2_STATE_ANALOG_1H_1H"]["numbers"]
    assert nums["interval_pp"] == [-1.1, 5.2] and nums["printed"]["interval_pp"] == ["−1.1", "+5.2"]
    from beta import decision_format as df
    line = df.analog_line({"window": "1h", "outcomes": {"1h": cell}}, "en")
    assert "(+2.0 pp; 95% interval −1.1…+5.2)" in line                  # what is logged is what is printed
    assert one["context_pk"] == 11 and one["stats_pk"] == 7 and one["stats_digest"] == "a" * 64
    assert one["rule_version"].endswith("BETA_CONTEXT_1H_V3")
    assert by["L2_STATE_ANALOG_1H_4H"]["eligible_reason"] == cj.BASELINE_ONLY        # n = 20 < 30
    assert by["L2_STATE_ANALOG_4H_24H"]["eligible_reason"] == cj.BASELINE_ONLY       # not the line's horizon
    stale = {**state, "context_1h": {"window_end": iso(SLOT - timedelta(minutes=5))}}
    assert {r["subject"]["window"] for r in cj.analog_claims(CFG, stale, _stats(), b, now=SLOT, slot=SLOT)} == {"4h"}
    # a NORMAL hour has a card but no surface prints it: kept for the live baseline, never a stated claim
    keys["1h"] = ("short_exit", interpretation.NORMAL)
    normal = {r["claim_class"]: r for r in cj.analog_claims(CFG, state, _stats(), b, now=SLOT, slot=SLOT)}
    assert normal["L2_STATE_ANALOG_1H_1H"]["eligible_reason"] == cj.BASELINE_ONLY
    assert normal["L2_STATE_ANALOG_4H_4H"]["eligible_reason"] == cj.SHOWN


def test_level_hold_claims_need_the_display_minimum():
    hist = {"real": {"n": 812, "1h": {"hold_rate": 0.47}, "4h": {"hold_rate": 0.44}},
            "control": {"n": 4000, "1h": {"hold_rate": 0.43}, "4h": {"hold_rate": 0.42}}, "verdicts": {"1h": "as_usual"}}
    at = datetime(2026, 10, 14, 9, 2, tzinfo=UTC)
    cand = {"kind": "level", "key": "level:PDH:2026-10-14",
            "payload": {"at": at.isoformat(), "level_kind": "PDH", "level": 62950.0, "side": 1, "period": "day",
                        "history": hist}}
    rows = cj.level_hold_claims(cand, now=at + timedelta(minutes=3))
    assert [r["claim_class"] for r in rows] == ["L2_LEVEL_FIRST_TOUCH_HOLD_1H", "L2_LEVEL_FIRST_TOUCH_HOLD_4H"]
    assert rows[0]["as_of"] == at + timedelta(minutes=5) and rows[0]["issue_slot"] == at
    assert rows[0]["numbers"]["diff_pp"] == 4.0 and rows[0]["subject_key"] == "level:PDH:2026-10-14"
    small = {**cand, "payload": {**cand["payload"], "history": {**hist, "real": {**hist["real"], "n": 29}}}}
    assert cj.level_hold_claims(small, now=at) == []


def _p1_bars(oi_growth, wide=False):
    n = 120
    start = SLOT - timedelta(minutes=5 * n)
    closes = [60000.0] * n
    highs = [60000.0 * (1.02 if wide and k % 7 == 0 else 1.001) for k in range(n)]
    lows = [60000.0 * 0.999] * n
    b = _grid(start, closes, highs, lows)
    oi = np.array([1.0e5 * (1 + oi_growth * k / n) for k in range(n)])
    return b, oi


def test_dh3_p1_writes_quiet_hours_with_their_arm():
    from beta.research_evidence import load_cuts
    cuts = load_cuts()
    b, oi = _p1_bars(0.05)
    rows = cj.dh3_p1_claim(b, oi, now=SLOT, slot=SLOT, cuts=cuts)
    assert len(rows) == 1 and rows[0]["subject"]["arm"] == "STATE" and rows[0]["claim_class"] == "L2_DH3_P1_RANGE_4H"
    assert rows[0]["numbers"]["claimed_shift_pct"] == 13.4 and rows[0]["horizon_end"] == SLOT + timedelta(hours=4)
    b, oi = _p1_bars(0.0)
    assert cj.dh3_p1_claim(b, oi, now=SLOT, slot=SLOT, cuts=cuts)[0]["subject"]["arm"] == "COMPARATOR"
    b, oi = _p1_bars(0.05, wide=True)
    assert cj.dh3_p1_claim(b, oi, now=SLOT, slot=SLOT, cuts=cuts) == []     # not a quiet hour: not in the cohort
    assert cj.dh3_p1_claim(b, None, now=SLOT, slot=SLOT, cuts=cuts) == []


class _Conn:
    """Writer-side fake: any outcome read at write time fails the test."""
    def __init__(self, state=None, have=()):
        self.rows, self.state, self.have = [], state, list(have)

    async def fetch_slot_claims(self, *, issue_slot, classes):
        return [{"claim_class": c, "subject_key": "x", "claim_pk": 1} for c in self.have if c in classes]

    async def fetch_latest_context_state(self, **_kw):
        return self.state

    async def insert_claim(self, row):
        if any((r["claim_class"], r["subject_key"], r["issue_slot"]) ==
               (row["claim_class"], row["subject_key"], row["issue_slot"]) for r in self.rows):
            return None
        self.rows.append(row)
        return len(self.rows)

    def transaction(self):
        conn = self

        class _Tx:                                   # rolls the group back like PostgreSQL would
            async def __aenter__(self):
                self.n = len(conn.rows)

            async def __aexit__(self, exc_type, *_):
                if exc_type is not None:
                    del conn.rows[self.n:]
                return False
        return _Tx()

    def __getattr__(self, name):
        if "outcome" in name or name.startswith("fetch_due"):
            raise AssertionError(f"outcome read at write time: {name}")
        raise AttributeError(name)


def test_an_interrupted_hour_leaves_no_partial_group_and_the_next_run_writes_it_whole():
    class _Failing(_Conn):
        async def insert_claim(self, row):
            if len(self.rows) == 3:
                raise ConnectionError("lost")
            return await super().insert_claim(row)
    blk, cap = _block(), {"stats": None, "bars": None, "model": MODEL}
    broken = _Failing()
    with pytest.raises(ConnectionError):
        asyncio.run(cj.record_claims(broken, CFG, blk, now=SLOT + timedelta(seconds=40), capture=cap))
    assert broken.rows == []                                   # nothing committed, so nothing is skipped
    whole = _Conn()
    rep = asyncio.run(cj.record_claims(whole, CFG, blk, now=SLOT + timedelta(minutes=1), capture=cap))
    assert rep["written"] == rep["candidates"] > 3


def test_the_hourly_writer_is_idempotent_reads_no_outcome_and_runs_only_early_in_the_hour():
    blk = _block()
    cap = {"stats": None, "bars": None, "model": MODEL}
    conn = _Conn()
    rep = asyncio.run(cj.record_claims(conn, CFG, blk, now=SLOT + timedelta(seconds=40), capture=cap))
    assert rep["written"] == rep["candidates"] == 4 + 36
    again = asyncio.run(cj.record_claims(conn, CFG, blk, now=SLOT + timedelta(minutes=2), capture=cap))
    assert again["written"] == 0
    late = asyncio.run(cj.record_claims(_Conn(), CFG, blk, now=SLOT + timedelta(minutes=11), capture=cap))
    assert late == {"written": 0, "candidates": 0}
    done = _Conn(have=["L3_DISTANCE_TOUCH_1H"])                    # the touch group already written this hour
    assert asyncio.run(cj.record_claims(done, CFG, blk, now=SLOT, capture=cap))["candidates"] == 0
    assert asyncio.run(cj.record_claims(_Conn(), CFG, {"available": False}, now=SLOT, capture=cap))["written"] == 0


# ---- scorer --------------------------------------------------------------------------------------
def _claim(rule, start, hours, subject):
    return {"claim_pk": 1, "eval_rule": {"id": rule}, "as_of": start, "horizon_end": start + timedelta(hours=hours),
            "subject": subject, "eval_rule_digest": "e" * 64}


def test_touch_outcome_is_a_fact_or_waits_for_coverage():
    b = _grid(SLOT - timedelta(hours=1), [60000.0] * 36, highs=[60000.0] * 20 + [60700.0] + [60000.0] * 15)
    up = _claim("TOUCH_V1", SLOT, 1, {"side": 1, "level": 60600.0})
    status, real = cj.evaluate(up, b, [], now=SLOT + timedelta(hours=2))
    assert status == "COMPLETE" and real["touched"] is True
    miss = _claim("TOUCH_V1", SLOT, 1, {"side": -1, "level": 59000.0})
    status, real = cj.evaluate(miss, b, [], now=SLOT + timedelta(hours=2))
    assert status == "COMPLETE" and real["touched"] is False and real["coverage"] >= 0.9
    gap = _claim("TOUCH_V1", SLOT + timedelta(hours=1), 24, {"side": -1, "level": 59000.0})
    assert cj.evaluate(gap, b, [], now=SLOT + timedelta(hours=26)) is None
    assert cj.evaluate(gap, b, [], now=SLOT + timedelta(hours=32))[0] == "NO_DATA"


def test_analog_hold_and_range_outcomes():
    closes = [60000.0] * 12 + [60000.0 + 30 * k for k in range(1, 61)]
    b = _grid(SLOT - timedelta(hours=1), closes, highs=[c + 50 for c in closes], lows=[c - 50 for c in closes])
    status, real = cj.evaluate(_claim("ANALOG_V1", SLOT, 4, {}), b, [], now=SLOT + timedelta(hours=5))
    at_4h = closes[12 + 47]                                    # the bar closing at SLOT + 4h
    assert status == "COMPLETE" and real["went_up"] is True and real["return_pct"] == round((at_4h / 60000.0 - 1) * 100, 4)
    hold = _claim("LEVEL_HOLD_V1", SLOT, 1, {"side": -1, "level": 60100.0})
    assert cj.evaluate(hold, b, [], now=SLOT + timedelta(hours=2))[1]["hold"] is False      # closed above a low
    status, real = cj.evaluate(_claim("DH3_P1_RANGE_4H_V1", SLOT, 4, {}), b, [], now=SLOT + timedelta(hours=5))
    hi, lo = max(closes[12:60]) + 50, min(closes[12:60]) - 50  # the 48 bars after SLOT
    assert status == "COMPLETE" and real["range_4h_log"] == round(math.log((hi - lo) / 60000.0), 6)
    with pytest.raises(ValueError):
        cj.evaluate(_claim("NOPE", SLOT, 1, {}), b, [], now=SLOT + timedelta(hours=2))


# ---- report ----------------------------------------------------------------------------------------
def _row(cls, at, **kw):
    return {"claim_class": cls, "as_of": at, "status": "COMPLETE", "shown": False, **kw}


def test_report_reliability_counts_independent_windows():
    rows = []
    midnight = SLOT.replace(hour=0)
    for k in range(48):                                         # two UTC days of hourly 24h claims at 30%
        at = midnight + timedelta(hours=k)
        rows.append(_row("L3_DISTANCE_TOUCH_24H", at, numbers={"probability": 0.3}, realized={"touched": k % 3 == 0}))
    rep = cj.claims_report(rows)["classes"]["L3_DISTANCE_TOUCH_24H"]
    assert rep["scored"] == 48 and rep["n_eff"] == 2
    assert rep["bins"] == [{"bin": [0.3, 0.5], "n": 48, "n_eff": 2, "predicted": 0.3, "realized": round(16 / 48, 4)}]
    assert rep["base_rate"] == round(16 / 48, 4) and rep["brier_skill"] is not None


def test_report_analog_reads_the_state_against_its_tercile_weighted_baseline():
    rows = []
    for d in range(10):
        at = SLOT + timedelta(days=d)
        rows.append(_row("L2_STATE_ANALOG_1H_1H", at, subject={"key": "short_exit", "tercile": 0}, eligible_reason=cj.SHOWN,
                         numbers={"diff_pp": 2.0}, realized={"went_up": d % 2 == 0}))
        rows.append(_row("L2_STATE_ANALOG_1H_1H", at + timedelta(hours=1), subject={"key": "calm", "tercile": 0},
                         eligible_reason=cj.SHOWN, numbers={"diff_pp": 0.0}, realized={"went_up": False}))
    rep = cj.claims_report(rows)["classes"]["L2_STATE_ANALOG_1H_1H"]["labels"]["short_exit"]
    assert rep["live_share_up"] == 0.5 and rep["live_baseline_share_up"] == 0.25 and rep["live_diff_pp"] == 25.0
    assert rep["claimed_diff_pp"] == 2.0 and rep["n_eff_days"] == 10


def test_dh3_p1_is_retried_in_the_write_window_when_its_oi_arrives_late(monkeypatch):
    """The touch group was written on the first run; the slot's OI arrived a minute later."""
    b, oi = _p1_bars(0.05)
    late = {"oi": None}

    async def _oi(conn, cfg, bars, *, now, capture):
        return late["oi"]
    monkeypatch.setattr(cj, "_oi_for", _oi)
    blk, cap = _block(), {"stats": None, "bars": b, "model": MODEL}
    conn = _Conn(have=cj.HOURLY_GROUPS["touch"] + cj.HOURLY_GROUPS["analog"])
    first = asyncio.run(cj.record_claims(conn, CFG, blk, now=SLOT + timedelta(seconds=40), capture=cap))
    assert first["written"] == 0                                # no OI yet: nothing, and nothing frozen
    late["oi"] = oi
    second = asyncio.run(cj.record_claims(conn, CFG, blk, now=SLOT + timedelta(minutes=1, seconds=40), capture=cap))
    assert second["written"] == 1 and conn.rows[0]["claim_class"] == "L2_DH3_P1_RANGE_4H"
    assert conn.rows[0]["as_of"] == SLOT and conn.rows[0]["issue_slot"] == SLOT


def test_report_p1_shift_against_the_record():
    rows = []
    for k in range(12):
        at = SLOT + timedelta(days=k)
        rows.append(_row("L2_DH3_P1_RANGE_4H", at, subject={"arm": "STATE"}, realized={"range_4h_log": -4.4}))
        rows.append(_row("L2_DH3_P1_RANGE_4H", at + timedelta(hours=1), subject={"arm": "COMPARATOR"},
                         realized={"range_4h_log": -4.7}))
    rep = cj.claims_report(rows)["classes"]["L2_DH3_P1_RANGE_4H"]
    assert rep["n_state"] == rep["n_comparator"] == 12 and rep["live_raw_shift_log"] == 0.3
    assert rep["record_raw_shift_log"] == round(-4.5103062282920785 + 4.744302154078247, 4)


# ---- displays -----------------------------------------------------------------------------------------
def test_shown_keys_follow_what_each_surface_prints():
    from beta.interpretation import INTERPRETED
    blk = _block(analogues={"1h": {"key": "short_exit", "outcomes": {"1h": {"n": 412, "baseline": {"p_up": 0.5}}}},
                            "4h": {"key": "squeeze", "outcomes": {"4h": {"n": 12, "baseline": {"p_up": 0.5}}}}})
    market = {"interpretation": {"1h": {"kind": INTERPRETED}, "4h": {"kind": INTERPRETED}}}
    brief = cj.shown_keys("brief", blk, market=market)
    assert ("L2_STATE_ANALOG_1H_1H", "1h:short_exit") in brief
    assert not [k for k in brief if k[0] == "L2_STATE_ANALOG_4H_4H"]                    # «мало данных»: not stated
    assert ("L3_LEVEL_TOUCH_24H", "+1:62950.00") in brief
    assert len(cj.shown_keys("levels", blk)) == 4 and len(cj.shown_keys("risk", blk)) == 3 * 4 * 2
    assert cj.shown_keys("levels", {"available": False}) == []
    cand = {"kind": "level", "key": "level:PDH:2026-10-14",
            "payload": {"side": 1, "next": _zone(["ROUND"], 64000.0, 2.4), "event_zone": {}}}
    assert cj.shown_keys("alert", None, alert=cand) == [("L2_LEVEL_FIRST_TOUCH_HOLD_1H", "level:PDH:2026-10-14"),
                                                         ("L3_LEVEL_TOUCH_24H", "+1:64000.00")]


def test_display_links_never_fail_the_caller():
    class Broken:
        async def fetch_slot_claims(self, **_kw):
            raise RuntimeError("db down")
    assert asyncio.run(cj.record_displays(Broken(), surface="levels", shown=[("L3_LEVEL_TOUCH_4H", "x")],
                                          now=SLOT)) == 0


# ---- touch-chance calibration (docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md) ---------------------------
def test_calibration_constants_are_the_journal_and_display_constants():
    from beta import decision, rangecast as rc
    assert rc.TOUCH_CAL_GRID_PCT == cj.TOUCH_GRID_PCT and rc.TOUCH_CAL_BINS == cj.PROB_BINS
    assert rc.TOUCH_CAL_MIN_NEFF == df.MIN_N_SHOWN and rc.TOUCH_CAL_EVENT_POST_MS == decision.EVENT_ZONE_POST_MS
    assert rc.TOUCH_CAL_TOLERANCE == 0.05
    assert rc.touch_bin(0.34) == [0.3, 0.5] and rc.touch_bin(0.999) == [0.85, 1.0] and rc.touch_bin(0.0) == [0.0, 0.05]


def test_event_zone_anchors_are_left_out_as_live():
    from beta import rangecast as rc
    r = int(SLOT.timestamp() * 1000)
    hour = 3_600_000
    anchors = np.array([r - 2 * hour, r - hour, r - 1, r + hour - 1, r + hour], dtype=np.int64)
    assert rc.in_event_zone(anchors, {"CPI": [r]}, hour).tolist() == [False, True, True, True, False]
    assert not rc.in_event_zone(anchors, {}, hour).any()


def test_accuracy_shows_the_held_out_touch_bins_and_marks_the_ones_outside_the_rule():
    bins = [{"bin": [0.3, 0.5], "n": 900, "n_eff": 365, "predicted": 0.401, "realized": 0.415, "passed": True},
            {"bin": [0.85, 1.0], "n": 96, "n_eff": 29, "predicted": 0.874, "realized": 0.833, "passed": False}]
    model = {"coverage": 0.8, "calibration": {"4h": {"coverage_realized": 0.79, "touch_bins": {"bins": bins}}}}
    ru = df.format_accuracy(model, {}, "ru").replace("&lt;", "<")
    assert "Шанс дойти</b>: говорили → было на отложенном годе" in ru
    assert "4ч: 40% → 42% (N=365) · 87% → 83% (N=29)*" in ru and "* вне правила (±5 п.п. при N ≥ 30)" in ru
    assert "Chance to reach" in df.format_accuracy(model, {}, "en")


def test_accuracy_shows_the_live_bins_and_keeps_a_diverged_one_visible_and_marked():
    """design note §3: the live line in /accuracy from N_eff >= 30; a diverged bin stays visible there."""
    live = {"days": 120, "computed_at": "2026-10-06T05:00:00Z",
            "horizons": {"1h": {"bins": [
                {"bin": [0.05, 0.15], "n": 400, "n_eff": 120, "predicted": 0.1, "realized": 0.08},
                {"bin": [0.3, 0.5], "n": 90, "n_eff": 45, "predicted": 0.4, "realized": 0.52},
                {"bin": [0.85, 1.0], "n": 20, "n_eff": 12, "predicted": 0.9, "realized": 1.0}]},
                "4h": {"bins": [{"bin": [0.15, 0.3], "n": 40, "n_eff": 20, "predicted": 0.2, "realized": 0.3}]}},
            "diverged": {"1h": [[0.3, 0.5]], "4h": [], "24h": []},
            "neither": {"1h": {"bins": [{"bin": [0.5, 0.7], "n": 300, "n_eff": 80, "predicted": 0.6, "realized": 0.58}]}},
            "diverged_neither": {}}
    ru = df.format_accuracy({"coverage": 0.8}, {}, "ru", touch_live=live)
    assert "Шанс дойти вживую</b> (журнал за последние 120 дн.)" in ru
    assert "1ч: 10% → 8% (N=120) · 40% → 52% (N=45)‼" in ru and "90%" not in ru     # N_eff 12 not shown
    assert "4ч: мало данных (N=20)" in ru
    assert "Ни один из двух уровней вживую" in ru and "1ч: 60% → 58% (N=80)" in ru
    assert "‼ вживую разошлось с правилом" in ru
    quiet = {**live, "diverged": {}}
    assert "‼" not in df.format_accuracy({"coverage": 0.8}, {}, "ru", touch_live=quiet)
    assert "Chance to reach, live" in df.format_accuracy({"coverage": 0.8}, {}, "en", touch_live=live)
    held = {"coverage": 0.8, "calibration": {"24h": {"neither_bins": {"bins": [
        {"bin": [0.5, 0.7], "n": 900, "n_eff": 305, "predicted": 0.59, "realized": 0.53, "passed": False}]}}}}
    assert "Ни один из двух уровней</b>: говорили → было на отложенном годе" in df.format_accuracy(held, {}, "ru")


def test_touch_chances_are_calibrated_on_the_real_held_out_year():
    """Binance 2022–2024 archives in the repository, held-out 2024: every bin meets the frozen rule."""
    import sys
    sys.path.insert(0, str(ROOT / "tests" / "beta"))
    from v2_fakes import repo_vision_zips
    from beta import history_data as hd, hist_series as hs, rangecast as rc
    from beta.calendar_events import event_times_ms, load_calendar
    b = hs.bars_from_rows(hd.rows_from_local_zips(repo_vision_zips([f"{y}-{m:02d}" for y in (2022, 2023, 2024)
                                                                      for m in range(1, 13)])))
    model = rc.fit_range_model(b, events=event_times_ms(load_calendar()))
    for h in ("1h", "4h", "24h"):
        tb = model["calibration"][h]["touch_bins"]
        assert tb["version"] == rc.TOUCH_CAL_VERSION and len(tb["bins"]) == 7
        for x in tb["bins"]:
            assert x["passed"] and abs(x["diff_pp"]) <= 5 and x["n_eff"] >= 30, (h, x)


def _cells(h, bin_k, days, n_per_day, hit_rate, p, slots_per_day=1):
    out = []
    for d in range(days):
        for s in range(slots_per_day):
            n = n_per_day // slots_per_day
            out.append({"claim_class": f"L3_DISTANCE_TOUCH_{h.upper()}", "bin": bin_k, "day": 20000 + d,
                        "slot": (20000 + d) * slots_per_day + s, "n": n, "hits": round(n * hit_rate), "psum": n * p})
    return out


def test_live_bins_pool_classes_count_slots_and_flag_only_clear_divergence():
    cells = _cells("24h", 3, 40, 10, 0.40, 0.40) + _cells("24h", 5, 40, 10, 0.9, 0.775)
    bins = cj.live_touch_bins(cells, "24h")
    assert [b["bin"] for b in bins] == [[0.3, 0.5], [0.7, 0.85]]
    assert bins[0]["n"] == 400 and bins[0]["n_eff"] == 40 and bins[0]["diff_pp"] == 0.0
    assert bins[1]["diff_pp"] == 12.5 and bins[1]["interval_pp"][0] > 0
    assert cj.diverged_bins(bins) == [[0.7, 0.85]]
    few = cj.live_touch_bins(_cells("24h", 5, 20, 10, 0.9, 0.775), "24h")
    assert few[0]["n_eff"] == 20 and cj.diverged_bins(few) == []            # N_eff < 30: not judged yet
    assert cj.live_touch_bins(cells, "1h") == []


def test_divergence_is_sticky_and_refreshed_hourly():
    from beta.rangecast import RANGE_MODEL_VERSION

    class C:
        def __init__(self, cells):
            self.cells, self.health = cells, {}

        async def fetch_health(self):
            return self.health

        async def touch_claim_cells(self, *, since, classes):
            return self.cells

        async def record_health(self, component, *, now, success, detail=None, error_type=None):
            self.health[component] = {"last_success_at": now, "detail": detail}
    conn = C(_cells("4h", 5, 40, 10, 0.95, 0.775, slots_per_day=1))
    d1 = asyncio.run(cj.refresh_touch_calibration(conn, now=SLOT))
    assert d1["diverged"]["4h"] == [[0.7, 0.85]] and d1["model"] == RANGE_MODEL_VERSION
    assert asyncio.run(cj.refresh_touch_calibration(conn, now=SLOT + timedelta(minutes=30))) is None
    conn.cells = _cells("4h", 5, 40, 10, 0.78, 0.775)                   # the live rate came back
    d2 = asyncio.run(cj.refresh_touch_calibration(conn, now=SLOT + timedelta(hours=1)))
    assert d2["diverged"]["4h"] == [[0.7, 0.85]]                         # still fallen back for this model
    from beta.health import health_alerts
    from beta_fakes import ON
    alerts = health_alerts(CFG, now=SLOT, heartbeat={"healthy": True}, detector_watermark=None, latest_live=None,
                           runtime={"touch_live_cal": {"detail": d2}}, delivery_problems=0,
                           switches=dataclasses.replace(ON, detection=False, outcome_tracking=False))
    assert {"key": "TOUCH_CALIBRATION_DIVERGED", "detail": {"4h": [[0.7, 0.85]]}} in alerts
    assert not [a for a in alerts if a["key"] == "NEITHER_CALIBRATION_DIVERGED"]
    neither = {**d2, "diverged_neither": {"1h": [], "4h": [], "24h": [[0.5, 0.7]]}}
    alerts = health_alerts(CFG, now=SLOT, heartbeat={"healthy": True}, detector_watermark=None, latest_live=None,
                           runtime={"touch_live_cal": {"detail": neither}}, delivery_problems=0,
                           switches=dataclasses.replace(ON, detection=False, outcome_tracking=False))
    assert {"key": "NEITHER_CALIBRATION_DIVERGED", "detail": {"24h": [[0.5, 0.7]]}} in alerts


def test_touch_wording_follows_the_frozen_rule():
    hold = {"4h": {"touch_bins": {"bins": [
        {"bin": [0.3, 0.5], "n_eff": 365, "predicted": 0.401, "realized": 0.415, "passed": True},
        {"bin": [0.85, 1.0], "n_eff": 20, "predicted": 0.87, "realized": 0.83, "passed": False}]}}}
    assert cj.touch_wording(hold, None, "4h", 0.34) == {"mode": "B", "source": "holdout", "bin": [0.3, 0.5],
                                                        "predicted": 0.401, "realized": 0.415, "n_eff": 365}
    assert cj.touch_wording(hold, None, "4h", 0.9)["mode"] == "fallback"            # held-out bin did not pass
    assert cj.touch_wording(hold, None, "4h", 0.1)["mode"] == "fallback"            # bin never checked
    live = {"horizons": {"4h": {"bins": [{"bin": [0.3, 0.5], "n_eff": 30, "predicted": 0.39, "realized": 0.37}]}},
            "diverged": {"4h": []}}
    w = cj.touch_wording(hold, live, "4h", 0.34)
    assert w["source"] == "live" and w["n_eff"] == 30 and w["realized"] == 0.37
    live["horizons"]["4h"]["bins"][0]["n_eff"] = 29
    assert cj.touch_wording(hold, live, "4h", 0.34)["source"] == "holdout"
    assert cj.touch_wording(hold, {"diverged": {"4h": [[0.3, 0.5]]}}, "4h", 0.34)["mode"] == "fallback"
    assert cj.touch_wording(hold, None, "4h", None) == {"mode": "none"}


# ---- «ни один» (calibration note §7) --------------------------------------------------------------
def _joint_model():
    from beta import rangecast as rc
    q = [3.0 * p for p in rc.P_GRID]
    lv = np.array(rc.JOINT_LEVELS)
    u = list(np.interp(lv, rc.P_GRID, q))
    return {"version": rc.RANGE_MODEL_VERSION,
            "horizons": {h: {"q_one": q, "q_joint": {"u": u, "v": u, "F": [[float(a * b) for b in lv] for a in lv]}}
                         for h in ("1h", "4h", "24h")}}


def test_neither_claims_cover_the_pair_grid_and_stay_coherent():
    rows = cj.touch_claims(_block(), _joint_model(), now=SLOT, slot=SLOT)
    nei = [r for r in rows if r["claim_class"].startswith("L3_NEITHER_")]
    assert len(nei) == 3 * len(cj.NEITHER_GRID_PCT) ** 2
    r = next(x for x in nei if x["claim_class"] == "L3_NEITHER_4H" and x["subject_key"] == "1.0:2.0")
    n = r["numbers"]
    assert 1 - n["p_up"] - n["p_down"] - 1e-4 <= n["probability"] <= 1 - max(n["p_up"], n["p_down"]) + 1e-4
    assert r["subject"]["level_up"] == round(62480.0 * 1.01, 2) and r["subject"]["level_down"] == round(62480.0 * 0.98, 2)


def test_neither_outcome_and_report():
    b = _grid(SLOT - timedelta(hours=1), [60000.0] * 36, highs=[60100.0] * 36, lows=[59900.0] * 36)
    c = _claim("NEITHER_V1", SLOT, 1, {"level_up": 60600.0, "level_down": 59400.0})
    assert cj.evaluate(c, b, [], now=SLOT + timedelta(hours=2))[1]["neither"] is True
    c2 = _claim("NEITHER_V1", SLOT, 1, {"level_up": 60050.0, "level_down": 59400.0})
    assert cj.evaluate(c2, b, [], now=SLOT + timedelta(hours=2))[1]["neither"] is False
    rows = [_row("L3_NEITHER_1H", SLOT + timedelta(hours=k), numbers={"probability": 0.8},
                 realized={"neither": k % 5 != 0}) for k in range(10)]
    rep = cj.claims_report(rows)["classes"]["L3_NEITHER_1H"]
    assert rep["base_rate"] == 0.8 and rep["bins"][0]["bin"] == [0.7, 0.85]


def test_joint_table_margins_and_neither_chance():
    from beta import rangecast as rc
    rng = np.random.default_rng(1)
    zu, zd = rng.exponential(1.0, 20000), rng.exponential(1.0, 20000)
    tab = rc._joint_table(zu, zd)
    big = 1e6
    for a in (0.5, 1.0, 2.0):
        assert abs(rc.joint_cdf(tab, np.array([a]), np.array([big]))[0] - np.mean(zu <= a)) < 0.02
        assert abs(rc.joint_cdf(tab, np.array([a]), np.array([a]))[0] - np.mean((zu <= a) & (zd <= a))) < 0.02
    m = {"horizons": {"4h": {"q_joint": tab}}}
    assert rc.neither_probability(m, "4h", 1.0, 1.0, 1.0, p_up=0.37, p_down=0.37) == \
        pytest.approx(min(max(float(rc.joint_cdf(tab, np.array([1.0]), np.array([1.0]))[0]), 0.26), 0.63))


def test_neither_chances_on_the_real_held_out_year():
    """Binance 2022–2024, held-out 2024 (note §7, scored on the shown, clipped value since §9): 20 of 21
    cells pass; 24h, bin 50–70 % is outside the rule (−6.0 pp) and therefore falls back to the historical
    wording."""
    import sys
    sys.path.insert(0, str(ROOT / "tests" / "beta"))
    from v2_fakes import repo_vision_zips
    from beta import history_data as hd, hist_series as hs, rangecast as rc
    from beta.calendar_events import event_times_ms, load_calendar
    b = hs.bars_from_rows(hd.rows_from_local_zips(repo_vision_zips([f"{y}-{m:02d}" for y in (2022, 2023, 2024)
                                                                      for m in range(1, 13)])))
    model = rc.fit_range_model(b, events=event_times_ms(load_calendar()))
    failed = []
    for h in ("1h", "4h", "24h"):
        for x in model["calibration"][h]["neither_bins"]["bins"]:
            assert x["passed"] == (x["n_eff"] >= 30 and abs(x["diff_pp"]) <= 5), (h, x)
            if not x["passed"]:
                failed.append((h, x["bin"]))
    assert failed == [("24h", [0.5, 0.7])]


def test_the_held_out_neither_value_is_the_one_surfaces_show():
    """note §9: the check scores neither_probability with its two printed chances, not the raw table."""
    import sys
    sys.path.insert(0, str(ROOT / "tests" / "beta"))
    from v2_fakes import synthetic_rows
    from beta import hist_series as hs, rangecast as rc
    rows, _ois = synthetic_rows(datetime(2026, 1, 1, tzinfo=UTC), 131, seed=11)
    model = rc.fit_range_model(hs.bars_from_rows(rows), events={}, holdout_days=30)
    clipped = 0
    for h in ("1h", "4h", "24h"):
        m = model["horizons"][h]
        for du in (0.1, 0.5, 1.0, 2.0, 3.0):
            for dd in (0.1, 0.5, 1.0, 2.0, 3.0):
                pu, pd_ = rc.touch_probability(model, h, 1.0, du), rc.touch_probability(model, h, 1.0, dd)
                shown = rc.neither_probability(model, h, 1.0, du, dd, p_up=pu, p_down=pd_)
                assert abs(float(rc.neither_shown(m["q_one"], m["q_joint"], [du], [dd])[0]) - shown) < 1e-12
                raw = float(rc.joint_cdf(m["q_joint"], np.array([du]), np.array([dd]))[0])
                clipped += abs(raw - shown) > 1e-9
    assert clipped > 0                  # the clip binds somewhere, so the two values do differ


def test_neither_grid_is_the_calibration_grid():
    from beta import rangecast as rc
    assert rc.NEITHER_CAL_GRID_PCT == cj.NEITHER_GRID_PCT
    from beta import levels
    assert levels.DISTANCE_GRID_PCT == cj.TOUCH_GRID_PCT
