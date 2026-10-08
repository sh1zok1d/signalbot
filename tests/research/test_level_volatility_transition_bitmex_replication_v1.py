"""Replication guards. No BitMEX transition is read here."""

import ast
from pathlib import Path

import numpy as np
import pytest

from scripts.research.level_first_touch_resolution_confirmation_v1.cohort import first_touch_status
from scripts.research.level_volatility_transition_bitmex_replication_v1 import claim, constants as K, preflight
from scripts.research.level_volatility_transition_bitmex_replication_v1.cohort import _refuse_label
from scripts.research.level_volatility_transition_bitmex_replication_v1.evaluate import refuse_if_recorded
from scripts.research.level_volatility_transition_discovery_v1 import inference, rv, windows
from scripts.research.level_volatility_transition_discovery_v1 import constants as DISC

PKG = Path(__file__).resolve().parents[2] / "scripts" / "research" / "level_volatility_transition_bitmex_replication_v1"


def _source(name: str) -> str:
    return (PKG / name).read_text()


def test_exposure_class_is_not_pristine():
    assert K.MODE == "CONFIRMATION"
    assert K.SURFACE_EVIDENCE_CLASS == "TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION"
    assert K.EXACT_CLAIM_PREVIOUSLY_READ is False
    assert K.NEIGHBORING_POST_TOUCH_PATH_PREVIOUSLY_READ is True
    assert K.SURFACE_PRISTINE is False
    assert K.REPLICATION_ALLOWED is True
    assert "PRISTINE_CONFIRMATION" not in _source("constants.py")
    assert K.INDEPENDENCE_FROM_RESOLUTION_CLOCK == "UNRESOLVED"
    assert K.CLAIM_CEILING == "L2"
    assert K.CANONICAL_SHA256.startswith("df3c3292")
    assert K.PRACTICAL_LOG == pytest.approx(np.log(1.10))
    assert K.WINDOW_BARS == DISC.WINDOW_BARS == 12
    assert K.ALTERNATIVE_HORIZONS == ()
    assert K.USE_RESOLUTION_LABELS is False
    assert K.BOOT_DRAWS == 2000
    assert K.BOOT_SEED == 20261025
    assert K.MIN_EPOCH_PAIRS == 30


def test_event_constructor_is_the_confirmation_first_touch():
    start, end = K.EVENT_START_MS, K.EVENT_END_MS
    base = {"touch_number": 1, "open_ms": start, "window_ok_48": True, "side": 1, "x_primary": 0.01}
    assert first_touch_status(base, event_start_ms=start, event_end_ms=end) == "LEGITIMATE"
    assert first_touch_status(dict(base, touch_number=2), event_start_ms=start, event_end_ms=end) == "NOT_FIRST"
    assert first_touch_status(dict(base, open_ms=end), event_start_ms=start, event_end_ms=end) == "OUTSIDE_WINDOW"
    assert first_touch_status(dict(base, open_ms=start - 1), event_start_ms=start, event_end_ms=end) == "OUTSIDE_WINDOW"
    _refuse_label({"outcome": None})
    with pytest.raises(RuntimeError):
        _refuse_label({"outcome": "BREAK"})
    cohort_src = _source("cohort.py")
    assert "outcomes" not in cohort_src
    assert "classify" not in cohort_src
    analyze_src = _source("analyze.py")
    assert "classify" not in analyze_src
    assert "BREAK" not in analyze_src
    assert "first_hit" not in analyze_src
    assert "rmut" not in analyze_src.lower()


def test_preflight_does_not_import_the_transition():
    tree = ast.parse(_source("preflight.py"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.endswith(".rv") or name.endswith(".analyze") for name in imported)
    plan = preflight.planning(500, 254)
    assert plan["adequate"] is True
    assert plan["planning_ci_half_width"] < K.PRACTICAL_LOG
    thin = preflight.planning(500, 20)
    assert thin["adequate"] is False
    assert thin["gate"] == "REPLICATION_INFORMATION_LIMITED"
    assert preflight.planning(10, 200)["adequate"] is False


def test_windows_and_rv_are_the_discovery_functions():
    from scripts.research.level_volatility_transition_bitmex_replication_v1 import analyze

    assert analyze.event_transition is rv.event_transition
    s = windows.spans(100)
    assert set(range(s["pre_return_lo"], s["pre_return_hi"] + 1)) == set(range(88, 100))
    assert set(range(s["post_return_lo"], s["post_return_hi"] + 1)) == set(range(101, 113))
    close = np.full(30, np.nan)
    close[10:25] = 100.0
    flags = windows.path_flags(close, 20)
    assert flags["complete"] is False
    hole = np.full(40, 100.0)
    hole[21] = np.nan
    assert rv.event_transition(hole, 20) is None
    flat = np.full(40, 100.0)
    assert rv.event_transition(flat, 20) is None
    stepped = np.full(40, 100.0)
    stepped[8:20] = np.linspace(100.0, 106.0, 12)
    stepped[21:33] = np.linspace(106.0, 118.0, 12)
    out = rv.event_transition(stepped, 20)
    assert out is not None
    assert out["transition"] == pytest.approx(np.log(out["rv_post"] / out["rv_pre"]))


def test_bootstrap_keeps_the_pair_atomic():
    weeks = np.array([1, 1, 2])
    deltas = np.array([1.0, 3.0, 5.0])
    fitted = inference.bootstrap_mean(weeks, deltas, draws=2000, seed=K.BOOT_SEED)
    assert fitted["n"] == 3
    assert fitted["weeks"] == 2
    assert fitted["bootstrap_valid"] == 2000
    assert fitted["ci95"][0] <= fitted["delta"] <= fitted["ci95"][1]


def _epoch(name, n, delta):
    return {"name": name, "n": n, "delta": delta}


def _ok_slices(delta=0.12):
    epochs = [_epoch(name, 100, delta) for name in K.EPOCHS]
    families = [
        {"name": "DAY", "n": 200, "delta": delta},
        {"name": "WEEK", "n": 80, "delta": delta},
        {"name": "MONTH", "n": 5, "delta": None},
    ]
    sides = [
        {"name": "resistance", "n": 150, "delta": delta},
        {"name": "support", "n": 120, "delta": delta * 0.5},
    ]
    loeo = [_epoch(f"omit_{name}", 200, delta) for name in K.EPOCHS]
    return epochs, families, sides, loeo


def test_routes_are_frozen():
    epochs, families, sides, loeo = _ok_slices()
    ci = (0.04, 0.20)
    supported = claim.decide(
        pre_gate=True, delta=0.12, ci=ci, ci_withheld=False,
        epochs=epochs, families=families, sides=sides, loeo=loeo, loeo_ran=True, artifact=False,
    )
    assert supported["routing"] == "REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION"
    assert supported["evidence_label"] == "REPLICATED_ON_TIME_DISJOINT_EXPOSED_SURFACE"
    below = claim.decide(
        pre_gate=True, delta=0.04, ci=(0.01, 0.07), ci_withheld=False,
        epochs=epochs, families=families, sides=sides, loeo=loeo, loeo_ran=False, artifact=False,
    )
    assert below["routing"] == "REPLICATION_POSITIVE_BELOW_PRACTICAL_BAR"
    inconclusive = claim.decide(
        pre_gate=True, delta=0.02, ci=(-0.02, 0.15), ci_withheld=False,
        epochs=epochs, families=families, sides=sides, loeo=[], loeo_ran=False, artifact=False,
    )
    assert inconclusive["routing"] == "REPLICATION_INCONCLUSIVE"
    assert inconclusive["ci_contains_practical_bar"] is True
    contradicts = claim.decide(
        pre_gate=True, delta=-0.12, ci=(-0.20, -0.04), ci_withheld=False,
        epochs=[_epoch(name, 100, -0.12) for name in K.EPOCHS],
        families=families, sides=sides, loeo=[], loeo_ran=False, artifact=False,
    )
    assert contradicts["routing"] == "REPLICATION_CONTRADICTS_DISCOVERY"
    limited = claim.decide(
        pre_gate=False, delta=None, ci=None, ci_withheld=True,
        epochs=[], families=[], sides=[], loeo=[], loeo_ran=False, artifact=False,
    )
    assert limited["routing"] == "REPLICATION_INFORMATION_LIMITED"
    flipped = [_epoch("2017H2", 100, -0.02), _epoch("2018", 100, 0.12), _epoch("2019", 100, 0.12)]
    unstable = claim.decide(
        pre_gate=True, delta=0.12, ci=ci, ci_withheld=False,
        epochs=flipped, families=families, sides=sides, loeo=loeo, loeo_ran=True, artifact=False,
    )
    assert unstable["routing"] == "REPLICATION_POSITIVE_UNSTABLE"


def test_refuse_second_result(tmp_path):
    missing = tmp_path / "absent.json"
    refuse_if_recorded(missing, tmp_path / "absent.md")
    present = tmp_path / "done.json"
    present.write_text("{}")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        refuse_if_recorded(present, tmp_path / "other.md")
