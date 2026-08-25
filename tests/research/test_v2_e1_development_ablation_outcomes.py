from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.research import v2_e1_development_ablation_outcomes as mod


def _row(variant: str, T: str, direction: str = "LONG"):
    return {"variant": variant, "T": T, "direction": direction}


def test_validate_inventory_accepts_required_nested_populations(monkeypatch):
    rows = []
    # Keep this unit test small by monkeypatching the frozen FULL-count sanity
    # counts; the production constants themselves are separately asserted by
    # the real artifact before any DB read.
    monkeypatch.setattr(mod, "EXPECTED_FULL_COUNTS", {
        mod.TP_FULL: 1, mod.CB_FULL: 1, mod.FB_FULL: 1,
    })
    t = "2026-08-10T12:00:00+00:00"
    for v in (mod.TP_FULL, mod.TP_NO_4H, mod.TP_NO_1H, mod.TP_NO_CONTEXT,
              mod.CB_FULL, mod.CB_NO_TAKER, mod.CB_SIMPLE,
              mod.FB_FULL, mod.FB_NO_CONTEXT, mod.FB_DUMB):
        rows.append(_row(v, t))
    rows.append(_row(mod.CB_ORDINARY, "2026-08-10T12:05:00+00:00"))
    keys = mod._validate_inventory(rows)
    assert keys[mod.TP_FULL] <= keys[mod.TP_NO_CONTEXT]
    assert keys[mod.FB_NO_CONTEXT] == keys[mod.FB_DUMB]


def test_validate_inventory_rejects_holdout_row(monkeypatch):
    monkeypatch.setattr(mod, "EXPECTED_FULL_COUNTS", {})
    with pytest.raises(RuntimeError, match="outside frozen development window"):
        mod._validate_inventory([
            _row(mod.CB_ORDINARY, "2026-08-16T00:00:00+00:00")
        ])


def test_full_horizon_cutoff_is_four_hours_before_holdout():
    assert mod.DEV_LAST_FULL_HORIZON_T == datetime(
        2026, 8, 15, 20, 0, tzinfo=timezone.utc
    )
