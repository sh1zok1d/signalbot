"""Prospective setup guards. Synthetic clocks and bars only. No market transition."""

from __future__ import annotations

import ast
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pytest

from beta.hist_series import BAR_MS, BARS_PER_DAY, empty_bars
from scripts.research.level_volatility_transition_discovery_v1 import rv, windows
from scripts.research.level_volatility_transition_prospective_confirmation_v1 import (
    accrual,
    claim,
    constants as K,
    evaluate,
    events,
    pairing,
    status,
    surface,
)

PKG = Path(__file__).resolve().parents[2] / "scripts" / "research" / "level_volatility_transition_prospective_confirmation_v1"
UTC = dt.timezone.utc


def _ms(year, month, day) -> int:
    return int(dt.datetime(year, month, day, tzinfo=UTC).timestamp() * 1000)


def _source(name: str) -> str:
    return (PKG / name).read_text()


def _imports(name: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(_source(name))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
        elif isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
    return found


def _bars(start_ms: int, days: int, price_at) -> object:
    n = days * BARS_PER_DAY
    bars = empty_bars(start_ms, n)
    for i in range(n):
        px = float(price_at(i))
        bars.open[i] = px
        bars.high[i] = px * 1.001
        bars.low[i] = px * 0.999
        bars.close[i] = px
        bars.volume[i] = 1.0
        bars.quote[i] = px
        bars.taker_buy_quote[i] = px / 2.0
    return bars


def _episode(i: int, i0: int, *, kind: str = "PDH", anchor: float = 100.0) -> dict:
    return {
        "episode_id": f"{kind}:{i}:{i0}",
        "kind": kind,
        "family": "DAY" if kind.startswith("PD") else "WEEK",
        "struct_side": 1 if kind.endswith("H") else -1,
        "priority": 0,
        "anchor_price": anchor + i,
        "zone_low": anchor * 0.999,
        "zone_high": anchor * 1.001,
        "i0": i0,
        "i1": i0 + 10,
        "period_open": 100.0,
        "source_key": i,
        "period_key": i + 1,
        "member_kinds": [kind],
        "n_members": 1,
        "absorbed_later": [],
        "population": "real",
        "zone_half": K.ZONE_HALF,
    }


def test_start_is_the_next_utc_midnight_after_the_design_commit():
    commit = dt.datetime(2026, 10, 8, 11, 22, tzinfo=UTC)
    start = surface.first_utc_midnight_after(commit)
    assert start == dt.datetime(2026, 10, 9, tzinfo=UTC)
    assert start > commit
    exact = dt.datetime(2026, 10, 9, tzinfo=UTC)
    assert surface.first_utc_midnight_after(exact) == dt.datetime(2026, 10, 10, tzinfo=UTC)
    manifest = surface.build_manifest("abc123", commit, code_version="abc123")
    assert manifest["prospective_start_utc"] == "2026-10-09T00:00:00Z"
    assert surface.parse_utc(manifest["prospective_start_utc"]) > commit
    assert manifest["manifest_digest"] == surface.digest_of(manifest)
    assert manifest["exact_outcome_read"] is False
    with pytest.raises(RuntimeError):
        surface.assert_recovery_interval(manifest["prospective_start_ms"] - 1, manifest["prospective_start_ms"])


def test_pre_start_episode_is_rejected_and_warmup_is_not_an_event():
    start = _ms(2026, 10, 11)
    t0 = _ms(2026, 10, 9)
    early = _episode(0, 0)
    late = _episode(1, 2 * BARS_PER_DAY)
    assert events.active_start_ms(t0, early) < start
    assert events.eligible_episode(early, t0=t0, start_ms=start) is False
    assert events.eligible_episode(late, t0=t0, start_ms=start) is True
    assert K.PRE_START_DATA_ROLE == "WARMUP_ONLY"

    def price(i: int) -> float:
        day = i // BARS_PER_DAY
        if day == 0:
            return 100.0
        if day == 1:
            return 80.0 if i % BARS_PER_DAY < 10 else 120.0
        return 120.0

    bars = _bars(t0, 3, price)
    kept, _instances, info = events.prospective_episodes(bars, start)
    assert info["dropped_pre_start"] >= 1
    assert kept
    assert all(events.active_start_ms(bars.t0, ep) >= start for ep in kept)
    touches = events.first_touches(bars, kept, end_ms=bars.end_ms)
    assert touches
    assert {row["touch_number"] for row in touches} == {1}
    assert {row["kind"] for row in kept} <= set(K.LEVEL_KINDS)


def test_constructor_kinds_are_the_six_structural_levels():
    start = _ms(2026, 9, 1)
    bars = _bars(start, 70, lambda i: 100.0 + 5.0 * np.sin(i / 40.0))
    kept, _instances, _info = events.prospective_episodes(bars, _ms(2026, 10, 1))
    assert kept
    assert {ep["kind"] for ep in kept} <= set(K.LEVEL_KINDS)
    assert {ep["kind"] for ep in kept} & {"PDH", "PDL", "PWH", "PWL"}
    assert all(events.active_start_ms(bars.t0, ep) >= _ms(2026, 10, 1) for ep in kept)


def test_pseudo_is_deterministic_and_outcome_free():
    episodes = [_episode(i, i * 100, anchor=100.0 + i) for i in range(4)]
    first = pairing.build_pair_map(
        _bars(_ms(2026, 10, 9), 5, lambda i: 100.0 + (i % 17)),
        episodes,
        [],
        start_ms=_ms(2026, 10, 9),
        checkpoint_end_ms=_ms(2026, 10, 20),
        checkpoint_weeks=104,
    )
    second = pairing.build_pair_map(
        _bars(_ms(2026, 10, 9), 5, lambda i: 100.0 + (i % 17)),
        episodes,
        [],
        start_ms=_ms(2026, 10, 9),
        checkpoint_end_ms=_ms(2026, 10, 20),
        checkpoint_weeks=104,
    )
    assert first["pair_map_digest"] == second["pair_map_digest"]
    assert first["contains_transition"] is False
    pairing.assert_outcome_free(first)
    dirty = dict(first)
    dirty["rv_post"] = 1.0
    with pytest.raises(RuntimeError):
        pairing.assert_outcome_free(dirty)
    assert "control_episodes" not in _source("status.py")
    assert "control" not in _imports("status.py")


def test_stop_rule_is_outcome_blind():
    start = dt.datetime(2026, 10, 9, tzinfo=UTC)
    assert accrual.completed_weeks(start - dt.timedelta(hours=1), start) == 0
    assert accrual.next_checkpoint(0) == 104
    assert accrual.CHECKPOINT_WEEKS if False else K.CHECKPOINT_WEEKS == (104, 130, 156)
    early = accrual.stop_decision(completed=104, matched_pairs=5000, at_checkpoint=False)
    assert early["stop"] is False
    ready = accrual.stop_decision(completed=104, matched_pairs=600, at_checkpoint=True)
    assert ready["stop"] is True and ready["read_outcomes"] is False
    short = accrual.stop_decision(completed=104, matched_pairs=599, at_checkpoint=True)
    assert short["stop"] is False
    limited = accrual.stop_decision(completed=156, matched_pairs=599, at_checkpoint=True)
    assert limited["information_limited"] is True and limited["read_outcomes"] is False
    end = accrual.checkpoint_end(start, 104)
    episode = _episode(0, 0)
    assert events.complete_by(episode, t0=_ms(2026, 10, 9), checkpoint_end_ms=surface.to_ms(end))
    spanning = _episode(1, 0)
    spanning["i1"] = 104 * 7 * BARS_PER_DAY
    assert events.complete_by(
        spanning, t0=_ms(2026, 10, 9), checkpoint_end_ms=surface.to_ms(end)
    ) is False


def test_windows_match_the_discovery_formula():
    close = np.ones(40)
    close[8:20] = np.linspace(1.0, 1.2, 12)
    close[20] = 1.2
    close[21:33] = np.linspace(1.2, 1.5, 12)
    flags = windows.path_flags(close, 20)
    assert flags["complete"] is True
    got = rv.event_transition(close, 20)
    assert got is not None
    pre, post, touch = rv.assigned_returns(close, 20)
    assert pre.shape == (12,) and post.shape == (12,)
    assert touch == pytest.approx(float(np.log(close[20] / close[19])))
    assert pre[-1] == pytest.approx(float(np.log(close[19] / close[18])))
    assert post[0] == pytest.approx(float(np.log(close[21] / close[20])))
    assert windows.spans(20)["touch"] not in range(
        windows.spans(20)["pre_return_lo"], windows.spans(20)["pre_return_hi"] + 1
    )
    assert got["rv_pre"] == pytest.approx(float(np.sqrt(np.mean(pre ** 2))))
    assert got["transition"] == pytest.approx(float(np.log(got["rv_post"] / got["rv_pre"])))
    flat = close.copy()
    flat[:] = 1.0
    assert rv.event_transition(flat, 20) is None
    assert K.ALTERNATIVE_HORIZONS == ()
    assert K.WINDOW_BARS == 12


def test_status_and_evaluator_do_not_read_a_transition():
    for name in ("status.py", "accrual.py", "events.py", "surface.py"):
        joined = " ".join(_imports(name))
        assert "rv" not in joined
        assert "event_transition" not in joined
    assert "event_transition" not in _source("evaluate.py")
    assert "from .rv" not in _source("evaluate.py")
    manifest = surface.build_manifest(
        "abc123", dt.datetime(2026, 10, 8, 11, 22, tzinfo=UTC), code_version="abc123"
    )
    payload = status.build_status(dt.datetime(2026, 10, 8, 12, tzinfo=UTC), manifest)
    assert payload["exact_outcome_read"] is False
    assert payload["status"] == "AWAITING_START"
    assert payload["protocol"] == "PROSPECTIVE_CONFIRMATION_STARTED"
    assert payload["matched_path_complete_provisional"] is None
    assert payload["stop_condition_met"] is False
    encoded = json.dumps(payload)
    for token in K.FORBIDDEN_STATUS_FIELDS:
        assert f'"{token}"' not in encoded
    reason = evaluate.refusal(
        manifest_ok=True, cohort_closed=False, stop_met=False, pair_map_present=False,
        digest_ok=False, peek=False, result_exists=False, information_limited_without_read=False,
    )
    assert reason == "REFUSING_PREMATURE_PROSPECTIVE_EVALUATION"
    assert evaluate.refusal(
        manifest_ok=True, cohort_closed=True, stop_met=True, pair_map_present=True,
        digest_ok=True, peek=True, result_exists=False, information_limited_without_read=False,
    ) == "REFUSING_PREMATURE_PROSPECTIVE_EVALUATION"
    assert evaluate.refusal(
        manifest_ok=True, cohort_closed=True, stop_met=True, pair_map_present=True,
        digest_ok=True, peek=False, result_exists=True, information_limited_without_read=False,
    ) == "REFUSING_RERUN"
    with pytest.raises(SystemExit) as caught:
        evaluate.main()
    assert "REFUSING_PREMATURE_PROSPECTIVE_EVALUATION" in str(caught.value)
    evaluate.assert_package_has_no_result()


def test_routes_are_frozen():
    epochs = [{"n": 80, "delta": 0.11}, {"n": 80, "delta": 0.12}, {"n": 80, "delta": 0.10}]
    loeo = [{"n": 160, "delta": 0.10}, {"n": 160, "delta": 0.11}, {"n": 160, "delta": 0.12}]
    families = [{"name": "DAY", "n": 50, "delta": 0.10}, {"name": "WEEK", "n": 50, "delta": 0.11}]
    sides = [{"name": "resistance", "n": 100, "delta": 0.12}, {"name": "support", "n": 100, "delta": 0.08}]
    common = dict(stop_met=True, information_limited=False, provenance_ok=True, peek=False,
                  epochs=epochs, loeo=loeo, families=families, sides=sides)
    passed = claim.decide(delta=0.10, ci=(0.02, 0.18), **common)
    assert passed["routing"] == "PROSPECTIVE_CONFIRMATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION"
    assert passed["evidence_label"] == "PROSPECTIVELY_CONFIRMED_LEVEL_VOLATILITY_TRANSITION"
    assert passed["product_integration_candidate"] is True
    assert passed["claim_ceiling"] == "L2"
    below = claim.decide(delta=0.02, ci=(0.005, 0.04), **common)
    assert below["routing"] == "PROSPECTIVE_POSITIVE_BELOW_PRACTICAL_BAR"
    inconclusive = claim.decide(delta=0.04, ci=(-0.02, 0.15), **common)
    assert inconclusive["routing"] == "PROSPECTIVE_CONFIRMATION_INCONCLUSIVE"
    assert inconclusive["ci_contains_practical_bar"] is True
    contradicts = claim.decide(delta=-0.04, ci=(-0.08, -0.01), **common)
    assert contradicts["routing"] == "PROSPECTIVE_CONFIRMATION_CONTRADICTS_HISTORY"
    limited = claim.decide(delta=None, ci=None, information_limited=True, **{
        k: v for k, v in common.items() if k != "information_limited"
    })
    assert limited["routing"] == "PROSPECTIVE_CONFIRMATION_INFORMATION_LIMITED"
    thin = claim.epoch_stability([{"n": 10, "delta": 0.2}])
    assert thin["status"] == "TEMPORAL_STABILITY_INFORMATION_LIMITED"
