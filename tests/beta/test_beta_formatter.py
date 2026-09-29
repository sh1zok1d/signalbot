"""Beta formatter: descriptive wording only; forbidden trade/predictive language rejected."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import EVENT_TYPES
from beta.formatter import (CLOSED_BETA_TEXT, EVENT_DESCRIPTIONS, EVENT_LABELS, HELP_TEXT,
                            PRIVACY_NOTICE, ForbiddenWordingError, assert_descriptive,
                            format_details, format_history, format_push, format_status)
from beta.models import Episode

T = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def _ep(et, **kw):
    base = dict(episode_pk=1, public_id="EV-ABCDEF0123", symbol="BTCUSDT", event_type=et,
                state="TRIGGERED", opened_bucket=T, opened_at=T, armed_at=T, triggered_at=T,
                terminal_at=None, terminal_reason=None, rules_version="BETA_EVENT_RULES_V1",
                rules_digest="a" * 64, code_version="c", calculation_version="0" * 16,
                opening_tape_digest="b" * 64, trigger_tape_digest="b" * 64, last_bucket=T,
                last_streak=2, reference_price=65000.0, reference_exchanges=("binance", "okx"))
    base.update(kw)
    return Episode(**base)


@pytest.mark.parametrize("text", [
    "BUY now", "consider a SELL", "LONG NOW", "short now please", "go long", "entry at 65k",
    "stop-loss 64k", "take profit", "target 70k", "use leverage", "position sizing",
    "70% probability", "likely to pump", "an impulse is coming", "win rate 60%", "a loss",
    "MFE 2%", "we recommend", "trading signal", "forecast up", "we predict",
])
def test_forbidden_wording_rejected(text):
    with pytest.raises(ForbiddenWordingError):
        assert_descriptive(text)


def test_static_texts_are_descriptive():
    for t in (CLOSED_BETA_TEXT, PRIVACY_NOTICE, HELP_TEXT, *EVENT_LABELS.values(), *EVENT_DESCRIPTIONS.values()):
        assert_descriptive(t)
    assert set(EVENT_LABELS) == set(EVENT_TYPES) == set(EVENT_DESCRIPTIONS)
    assert "closed private beta" in CLOSED_BETA_TEXT.lower()
    assert "/delete_me" in PRIVACY_NOTICE and "30 days" in PRIVACY_NOTICE


@pytest.mark.parametrize("et", EVENT_TYPES)
def test_push_shows_decision_time_and_passes_wording(et):
    text = format_push(_ep(et))
    assert "Decision time: 2026-03-01 12:00 UTC" in text and "EV-ABCDEF0123" in text


def test_status_history_details_render():
    st = {"status": "DATA STALE", "reasons": ["EVALUATION_TOO_OLD"], "last_good_bucket": T}
    out = format_status(st, [], None)
    assert "DATA STALE" in out and "cannot be claimed" in out
    rows = [dict(episode_pk=1, public_id="EV-ABCDEF0123", event_type=et, state="ENDED",
                 terminal_reason="CONDITION_FAILED", correction_flag=(et == EVENT_TYPES[0]),
                 opened_at=T, triggered_at=T, decision="SUPPRESSED", suppression_reason="PUSH_DISABLED",
                 delivery_states=None) for et in EVENT_TYPES]
    outs = {1: [{"horizon": "4h", "status": "COMPLETE", "realized_range_pct": 1.23, "revision": 2}]}
    h = format_history(rows, outs)
    assert "SUPPRESSED (PUSH_DISABLED)" in h and "corrected input" in h and "4h range 1.23%*" in h
    d = format_details(_ep(EVENT_TYPES[0], correction_flag=True, correction_note="input corrected"),
                       [{"decision_ts": T, "to_state": "ARMED", "reason": "CONDITION_MET"}],
                       [{"horizon": "1h", "status": "COMPLETE", "realized_range_pct": 1.0, "max_up_pct": 0.5,
                         "max_down_pct": 0.5, "close_return_pct": 0.1, "revision": 1}])
    assert "max up +0.50%" in d and "max down -0.50%" in d


def test_formatter_has_no_legacy_direction_fields():
    import ast
    import beta.formatter as f
    tree = ast.parse(open(f.__file__).read())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
        {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not names & {"NotificationCandidate", "final_score", "confidence", "direction"}
    assert not {m for m in mods if m and (m.startswith("notifications") or "forecast" in m)}
