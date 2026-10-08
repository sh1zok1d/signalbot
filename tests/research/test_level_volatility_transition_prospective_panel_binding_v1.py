"""Forward-panel binding of the #368 prospective protocol. Synthetic 1m rows only; no market data."""

from __future__ import annotations

import ast
import datetime as dt
import json
import math
from pathlib import Path

import pytest

from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_volatility_transition_prospective_confirmation_v1 import (
    constants as K,
    forward_panel,
    status,
    surface,
)

PKG = Path(__file__).resolve().parents[2] / "scripts" / "research" / "level_volatility_transition_prospective_confirmation_v1"
UTC = dt.timezone.utc
START = dt.datetime(2026, 10, 9, tzinfo=UTC)


def _manifest() -> dict:
    return surface.build_manifest("abc123", dt.datetime(2026, 10, 8, 11, 30, 26, tzinfo=UTC),
                                  code_version="abc123")


def _rows(first: dt.datetime, last: dt.datetime, *, skip=()) -> list[dict]:
    """Closed-minute rows with a slow oscillation, so daily highs and lows are retouched."""
    out = []
    t = first
    k = 0
    while t < last:
        if t not in skip:
            px = 60_000.0 * (1.0 + 0.02 * math.sin(k / 700.0))
            out.append({"ts": t, "open": px, "high": px * 1.0005, "low": px * 0.9995,
                        "close": px, "volume": 1.0, "source": "live"})
        t += dt.timedelta(minutes=1)
        k += 1
    return out


def _imports(name: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse((PKG / name).read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
        elif isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
    return found


def test_binding_reads_no_outcome_module():
    modules = set(_imports("forward_panel.py"))
    assert modules <= {"__future__", "datetime", "collections", "numpy", "asyncpg", "surface",
                       "scripts.research.dh1.data", "scripts.research.level_touch_degradation_v1"}
    source = (PKG / "forward_panel.py").read_text()
    for forbidden in ("import claim", "import evaluate", "import pairing", "from .rv", "outcomes", "attach("):
        assert forbidden not in source


def test_warmup_is_after_the_e1_holdout():
    assert forward_panel.warmup_start_ms() >= PARENT.E1_END_MS
    with pytest.raises(RuntimeError, match="E1-RUN-001"):
        forward_panel.closed_minutes(
            _rows(dt.datetime(2026, 8, 20, tzinfo=UTC), dt.datetime(2026, 8, 20, 0, 10, tzinfo=UTC)),
            surface.to_ms(START))


def test_before_start_counts_are_zero_and_status_awaits():
    now = dt.datetime(2026, 10, 8, 20, 3, 30, tzinfo=UTC)
    rows = _rows(dt.datetime(2026, 9, 1, tzinfo=UTC), now)
    payload = status.bound_status(now, _manifest(), rows)
    assert payload["status"] == "AWAITING_START"
    assert payload["panel_bound"] is True
    assert payload["structural_episodes"] == 0
    assert payload["real_first_touches"] == 0
    assert payload["matched_path_complete_provisional"] is None
    cov = payload["forward_panel"]["post_start_coverage"]
    assert cov["expected_minutes"] == 0 and cov["missing_minutes"] == 0


def test_after_start_counts_gaps_and_stays_outcome_blind():
    now = dt.datetime(2026, 10, 20, 0, 2, 30, tzinfo=UTC)
    hole = {dt.datetime(2026, 10, 12, 3, m, tzinfo=UTC) for m in (7, 8, 9)}
    partial = {dt.datetime(2026, 10, 20, 0, 2, tzinfo=UTC)}            # still open at `now`
    rows = _rows(dt.datetime(2026, 9, 1, tzinfo=UTC), now + dt.timedelta(minutes=1))
    rows = [r for r in rows if r["ts"] not in hole]
    assert any(r["ts"] in partial for r in rows)
    payload = status.bound_status(now, _manifest(), rows)
    assert payload["status"] == "ACCRUING"
    assert payload["completed_weeks"] == 1
    assert payload["exact_outcome_read"] is False
    assert payload["matched_path_complete_provisional"] is None
    assert payload["structural_episodes"] >= 1
    assert payload["real_first_touches"] >= 1
    assert sum(payload["family_counts"].values()) == payload["real_first_touches"]
    assert sum(payload["side_counts"].values()) == payload["real_first_touches"]
    cov = payload["forward_panel"]["post_start_coverage"]
    assert cov["expected_minutes"] == 11 * 1440 + 2
    assert cov["missing_minutes"] == 3
    assert cov["missing_runs"] == [{"from": "2026-10-12T03:07:00Z", "to": "2026-10-12T03:10:00Z",
                                    "minutes": 3}]
    assert cov["incomplete_5m_bins"] == 1                              # the 03:05 bin
    assert payload["bar_gaps_logged"] == 1
    assert payload["forward_panel"]["last_closed_minute"] == "2026-10-20T00:01:00Z"
    assert payload["forward_panel"]["rows_by_source"] == {"live": payload["forward_panel"]["rows_read"]}
    encoded = json.dumps(payload)
    for token in K.FORBIDDEN_STATUS_FIELDS:
        assert f'"{token}"' not in encoded
    for touch_key in ("outcome", "break", "reject", "neither"):
        assert f'"{touch_key}"' not in encoded


def test_empty_collection_refuses():
    with pytest.raises(RuntimeError, match="no closed BTCUSDT minute"):
        forward_panel.bind([], start_ms=surface.to_ms(START), now=dt.datetime(2026, 10, 10, tzinfo=UTC))
