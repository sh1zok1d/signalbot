"""Zone-traded activity discovery. No archive download and no late label."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import numpy as np
import pytest

from scripts.research.level_zone_traded_activity_discovery_v1 import claim, constants as K
from scripts.research.level_zone_traded_activity_discovery_v1.evaluate import refuse_if_recorded
from scripts.research.level_zone_traded_activity_discovery_v1.features import zone_features
from scripts.research.level_zone_traded_activity_discovery_v1.inference import (
    PROTECTED, bh_adjust, columns_for, drop_redundant, fit_matched, fit_rows, freeze_scales, spearman,
)
from scripts.research.level_zone_traded_activity_discovery_v1.trades import (
    _timestamps_ms, accumulate, assert_month_legal, empty_acc, finalize_record, notional_audit,
    quote_notional, sha256_file, stream_zip,
)
from scripts.research.level_zone_traded_activity_discovery_v1.windows import event_window, months_covering

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "scripts" / "research" / "level_zone_traded_activity_discovery_v1"


def test_archive_identity_and_months():
    assert "futures/um/monthly/aggTrades/BTCUSDT" in K.UM_KEY
    assert "spot" not in K.UM_KEY
    assert K.ARCHIVE_ID == "BINANCE_UM_TRADES_AGGTRADES_ARCHIVE"
    assert_month_legal("2020-03")
    assert_month_legal("2024-12")
    with pytest.raises(RuntimeError):
        assert_month_legal("2025-01")
    with pytest.raises(RuntimeError):
        assert_month_legal("2026-01")
    with pytest.raises(RuntimeError):
        assert_month_legal("2020-02")


def test_quote_notional_and_checksum(tmp_path: Path):
    price = np.asarray([50_000.0, 60_000.0])
    qty = np.asarray([0.01, 0.02])
    assert quote_notional(price, qty).tolist() == [500.0, 1200.0]
    audit = notional_audit(np.full(120, 50_000.0), np.full(120, 0.01))
    assert audit["median_quote_notional"] == pytest.approx(500.0)
    payload = tmp_path / "blob.bin"
    payload.write_bytes(b"aggtrades-bytes")
    assert sha256_file(payload) == hashlib.sha256(b"aggtrades-bytes").hexdigest()
    raw = np.asarray([1_620_000_000_000_000], dtype=np.int64)
    assert int(_timestamps_ms(raw)[0]) == 1_620_000_000_000


def test_event_window_bounds_and_months():
    row = {
        "episode_id": "e1", "open_ms": K.EVENT_START_MS, "zone_low": 100.0, "zone_high": 101.0,
    }
    window = event_window(row, "real")
    assert window["key"] == "real:e1"
    assert window["t_ms"] == K.EVENT_START_MS
    assert window["pre_ms"] == K.EVENT_START_MS - K.PRE60_MS
    assert window["d_ms"] == K.EVENT_START_MS + K.REACTION_MS
    assert window["zone_low"] == 100.0 and window["zone_high"] == 101.0
    assert months_covering(window["pre_ms"], window["d_ms"])[0] == "2020-03"
    late = dict(row, open_ms=K.EVENT_END_MS - K.BAR_MS)
    with pytest.raises(RuntimeError):
        event_window(late, "real")


def _event(key: str, t_ms: int, low: float, high: float) -> dict:
    return {
        "key": key, "pre_ms": t_ms - K.PRE60_MS, "t_ms": t_ms, "d_ms": t_ms + K.REACTION_MS,
        "touch_end_ms": t_ms + K.BAR_MS, "zone_low": low, "zone_high": high,
    }


def test_accumulate_zone_clock_and_tau():
    t_ms = 1_620_000_000_000
    ev = _event("real:a", t_ms, 100.0, 110.0)
    times = np.asarray([
        t_ms - 1, t_ms, t_ms + 1_000, t_ms + 1_500, t_ms + 2_000, t_ms + K.REACTION_MS,
        t_ms + 10_000,
    ], dtype=np.int64)
    prices = np.asarray([100.0, 100.0, 110.0, 110.0, 111.0, 100.0, 99.0])
    qty = np.ones(times.size)
    acc = {}
    got = accumulate(times, prices, qty, [ev], acc)
    record = finalize_record("real:a", acc["real:a"])
    assert record["pre60_notional"] == pytest.approx(100.0)
    assert record["zone_notional_15m"] == pytest.approx(100.0 + 110.0 + 110.0)
    assert record["total_notional_15m"] == pytest.approx(100.0 + 110.0 + 110.0 + 111.0 + 99.0)
    assert record["tau_ms"] == t_ms
    assert record["touch_in_zone"] == 3
    assert record["zone_active_seconds"] == 2
    assert got["assigned_trades"] >= 1
    feats = zone_features(record, t_ms)
    assert feats["TOUCH_OFFSET_SECONDS"] == pytest.approx(0.0)
    assert feats["ZONE_NOTIONAL_SHARE_15M"] == pytest.approx(record["zone_notional_15m"] / record["total_notional_15m"])
    assert feats["ZONE_ACTIVE_SECONDS_15M"] == pytest.approx(2 / 900)
    assert feats["ZONE_NOTIONAL_INTENSITY_15M"] == pytest.approx(
        np.log(record["zone_notional_15m"] / (record["pre60_notional"] / 4.0))
    )


def test_zero_intensity_is_missing_and_outside_zone_is_excluded():
    t_ms = 1_620_000_000_000
    missing = zone_features({
        "pre60_notional": 0.0, "zone_notional_15m": 10.0, "total_notional_15m": 10.0,
        "zone_active_seconds": 1, "tau_ms": t_ms, "touch_in_zone": 1,
    }, t_ms)
    assert missing["ZONE_NOTIONAL_INTENSITY_15M"] is None
    share = zone_features({
        "pre60_notional": 40.0, "zone_notional_15m": 0.0, "total_notional_15m": 8.0,
        "zone_active_seconds": 0, "tau_ms": None, "touch_in_zone": 0,
    }, t_ms)
    assert share["ZONE_NOTIONAL_SHARE_15M"] == 0.0
    assert share["ZONE_NOTIONAL_INTENSITY_15M"] is None
    assert share["ZONE_ACTIVE_SECONDS_15M"] == 0.0
    ev = _event("real:b", t_ms, 100.0, 110.0)
    times = np.asarray([t_ms + 5_000], dtype=np.int64)
    acc = {}
    accumulate(times, np.asarray([99.9]), np.asarray([1.0]), [ev], acc)
    record = finalize_record("real:b", acc["real:b"])
    assert record["zone_notional_15m"] == 0.0
    assert record["total_notional_15m"] == pytest.approx(99.9)
    assert record["tau_ms"] is None


def test_overlapping_events_are_not_deduplicated():
    t_ms = 1_620_000_000_000
    left = _event("real:a", t_ms, 100.0, 110.0)
    right = _event("real:b", t_ms + 60_000, 100.0, 110.0)
    times = np.asarray([t_ms + 120_000], dtype=np.int64)
    acc = {}
    got = accumulate(times, np.asarray([105.0]), np.asarray([2.0]), [left, right], acc)
    assert got["multi_event_trades"] == 1
    assert acc["real:a"]["zone_notional_15m"] == pytest.approx(210.0)
    assert acc["real:b"]["zone_notional_15m"] == pytest.approx(210.0)


def test_stream_zip_header_checksum_and_protected_stamp(tmp_path: Path):
    header = K.UM_HEADER + "\n"
    rows = []
    for i in range(150):
        rows.append(f"{i},50000,0.01,{i},{i},1620000000000,true\n")
    raw = tmp_path / "ok.zip"
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("BTCUSDT-aggTrades-2021-05.csv", header + "".join(rows))
    stats = stream_zip(raw, [], {}, surface_end_ms=K.EVENT_END_MS)
    assert stats["rows"] == 150
    assert stats["header"] is True
    assert stats["notional_audit"]["median_price"] == pytest.approx(50_000.0)
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("x.csv", "not,the,header\n1,2,3,4,5,6,7\n")
    with pytest.raises(RuntimeError):
        stream_zip(bad, [], {}, surface_end_ms=K.EVENT_END_MS)
    future = tmp_path / "future.zip"
    with zipfile.ZipFile(future, "w") as archive:
        archive.writestr("x.csv", header + "1,50000,0.01,1,1,1735689600000,true\n")
    with pytest.raises(RuntimeError):
        stream_zip(future, [], {}, surface_end_ms=K.EVENT_END_MS)


def test_redundancy_drops_the_later_feature():
    rows = []
    for i in range(30):
        rows.append({
            "ZONE_NOTIONAL_INTENSITY_15M": float(i),
            "ZONE_NOTIONAL_SHARE_15M": float(i) * 2.0,
            "ZONE_ACTIVE_SECONDS_15M": float((i % 3) - 1),
        })
    got = drop_redundant(rows, K.FEATURES)
    assert got["retained"] == ["ZONE_NOTIONAL_INTENSITY_15M", "ZONE_ACTIVE_SECONDS_15M"]
    assert got["dropped"][0]["feature"] == "ZONE_NOTIONAL_SHARE_15M"
    tied = [{"a": v, "b": v} for v in (1, 1, 2, 3)]
    assert spearman(tied, "a", "b") == pytest.approx(1.0)


def _sample_rows(n: int = 80) -> list[dict]:
    rows = []
    epochs = list(K.EPOCHS)
    for i in range(n):
        feature = float(i - n / 2)
        rows.append({
            "y": 1.0 if feature > 0 else 0.0,
            "END_POSITION_X": np.sin(i / 2.0),
            "OTHER_VENUE_MEDIAN_MOVE": np.cos(i / 3.0) * 0.01,
            "TOUCH_OFFSET_SECONDS": float((i * 3) % 50 + 1),
            "disp": np.sin(i / 5.0),
            "family": ("DAY", "WEEK", "MONTH")[(i // 4) % 3],
            "support": 1.0 if i % 2 == 0 else 0.0,
            "side": -1 if i % 2 == 0 else 1,
            "vol_tercile": (i // 3) % 3,
            "epoch": epochs[i % 5],
            "time_block": (i // 2) % 4,
            "cluster": i // 8,
            "ZONE_NOTIONAL_SHARE_15M": feature,
        })
    return rows


def test_baseline_columns_always_include_endpoint_cv1_and_offset():
    rows = _sample_rows()
    scales = freeze_scales(rows, ("ZONE_NOTIONAL_SHARE_15M",))
    cols = columns_for(rows, feature=True)
    assert {"endpos_z", "cv1_z", "offset_z", "feature_z"} <= set(cols)
    assert PROTECTED >= {"endpos_z", "cv1_z", "offset_z"}
    fit = fit_rows(rows, "ZONE_NOTIONAL_SHARE_15M", scales, draws=30, seed=K.stream_seed(1, 1))
    assert fit["includes_end_position"] and fit["includes_cv1"] and fit["includes_offset"]
    assert "endpos_z" in fit["columns"] and "cv1_z" in fit["columns"] and "offset_z" in fit["columns"]
    assert fit["coef"] is not None and fit["coef"] > 0.0


def test_matched_models_share_columns_and_move_pairs_together():
    real = _sample_rows()
    pseudo = []
    for i, row in enumerate(real):
        copied = dict(row)
        copied["ZONE_NOTIONAL_SHARE_15M"] = float(np.sin(i * 1.7))
        copied["y"] = 0.0 if i % 3 else 1.0
        copied["cluster"] = 10_000 + i
        pseudo.append(copied)
    scales = freeze_scales(real, ("ZONE_NOTIONAL_SHARE_15M",))
    pairs = [{"real": left, "pseudo": right} for left, right in zip(real, pseudo)]
    matched = fit_matched(pairs, "ZONE_NOTIONAL_SHARE_15M", scales, draws=40, seed=K.stream_seed(1, 100))
    assert matched["status"] == "ESTIMATED"
    assert matched["columns"][0] == "intercept"
    assert {"endpos_z", "cv1_z", "offset_z", "feature_z"} <= set(matched["columns"])
    assert matched["beta_real"] > 0.0
    assert matched["delta"] == pytest.approx(matched["beta_real"] - matched["beta_pseudo"])


def test_year_family_side_and_loyo_rules():
    def year(coef, n=40):
        return {"coef": coef, "n": n}

    five = [year(v) for v in (0.04, 0.02, 0.01, 0.03, -0.01)]
    assert claim.year_stability(0.04, five)["pass"] is True
    assert claim.year_stability(0.04, [year(v) for v in (0.04, 0.02, 0.01, -0.02, -0.01)])["pass"] is False
    four_small = [year(v) for v in (0.04, 0.02, 0.05, -0.02)]
    four_big = [year(v) for v in (0.04, 0.02, 0.05, -0.04)]
    assert claim.year_stability(0.04, four_small)["pass"] is True
    assert claim.year_stability(0.04, four_big)["pass"] is False
    assert claim.year_stability(0.04, [year(v) for v in (0.04, 0.02, 0.01)])["pass"] is True
    assert claim.year_stability(0.04, [year(v) for v in (0.04, 0.02, -0.001)])["pass"] is False
    assert claim.year_stability(0.04, [year(v) for v in (0.04, 0.02)])["pass"] is False
    assert claim.loyo_stability(0.04, [year(v) for v in (0.01, 0.02, 0.03, 0.04)])["pass"] is True
    assert claim.loyo_stability(0.04, [year(v) for v in (0.01, 0.02, -0.01, 0.04)])["pass"] is False
    families = [{"name": "DAY", "coef": 0.04, "n": 40}, {"name": "WEEK", "coef": -0.01, "n": 40}]
    assert claim.family_stability(families)["pass"] is True
    families[1]["coef"] = -0.04
    assert claim.family_stability(families)["pass"] is False
    sides = [{"name": "resistance", "coef": 0.05, "n": 40}, {"name": "support", "coef": -0.02, "n": 40}]
    assert claim.side_stability(sides)["pass"] is True
    sides[1]["coef"] = -0.05
    assert claim.side_stability(sides)["pass"] is False


def test_bh_and_statistical_gate_requires_offset():
    assert bh_adjust([0.01, 0.04, 0.20]) == pytest.approx([0.03, 0.06, 0.20])
    cell = {
        "coef": 0.05, "ci95": (0.01, 0.09), "q": 0.04,
        "includes_end_position": True, "includes_cv1": True, "includes_offset": False,
    }
    assert claim.statistical_pass(cell) is False
    cell["includes_offset"] = True
    assert claim.statistical_pass(cell) is True
    assert claim.support_sensitive(0.05, 0.01) is True
    assert claim.support_sensitive(0.05, -0.02) is True
    assert claim.support_sensitive(0.05, 0.04) is False
    assert claim.support_sensitive(0.05, None) is False


def test_route_order_and_rerun_refusal(tmp_path: Path):
    assert claim.route([], n_resolved=0, novelty_ok=False, touch_identity_ok=True, pre_outcome_ok=True) == (
        "BLOCKED_REOPENING_ZONE_TRADED_ACTIVITY_CELL"
    )
    assert claim.route([], n_resolved=10, novelty_ok=True, touch_identity_ok=False, pre_outcome_ok=False) == (
        "AGGTRADE_TOUCH_IDENTITY_FAILED"
    )
    assert claim.route([], n_resolved=10, novelty_ok=True, touch_identity_ok=True, pre_outcome_ok=False) == (
        "ZONE_TRADED_ACTIVITY_INFORMATION_INSUFFICIENT"
    )
    generic = [{
        "candidate_class": "GENERIC_TRADED_ACTIVITY_CANDIDATE",
        "specificity_status": "GENERIC", "statistical": True, "conjunction_pass": True, "ci95": (0.02, 0.08),
    }]
    assert claim.route(generic, n_resolved=300, novelty_ok=True, touch_identity_ok=True, pre_outcome_ok=True) == (
        "GENERIC_TRADED_ACTIVITY_STRUCTURE"
    )
    recorded = tmp_path / "result.json"
    recorded.write_text("{}\n")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        refuse_if_recorded(recorded, tmp_path / "missing.md")


def test_acquisition_cannot_read_a_late_label():
    banned = ("acquire.py", "preflight.py", "trades.py", "features.py", "windows.py", "inference.py", "claim.py")
    for name in banned:
        text = (PKG / name).read_text()
        assert "late_label" not in text
        assert "LATE_BREAK" not in text
    evaluate = (PKG / "evaluate.py").read_text()
    assert "from .analyze import run" in evaluate
    assert evaluate.split("def main")[0].count("analyze") == 0
    acquire = (PKG / "acquire.py").read_text()
    assert "unlink" in acquire
    assert "RAW_RETAINED" in acquire
    assert not list((ROOT / "docs" / "research_data").glob("**/*aggTrades*.zip"))
