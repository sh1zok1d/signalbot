"""Tests for analytics/forecasting_v2/event_factory.py's
build_v2_episode_event().

Proves the factory is a pure combination of an already-validated
V2EventProvenance and already-decided event-specific facts into a
V2EpisodeEvent — it decides nothing, cannot have its provenance-owned
fields overridden by a caller, and performs no I/O of any kind.
"""
from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from types import MappingProxyType

from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED, EARLY_SIGNAL, LIVE, LONG, REPLAY, SHORT,
    TREND_PULLBACK, V2EpisodeEvent, V2EventInputError,
)
from analytics.forecasting_v2.provenance import V2EventProvenance

UTC = timezone.utc
B = datetime(2026, 7, 22, 12, 15, 0, tzinfo=UTC)
H64 = "a" * 64
H16 = "b" * 16


def make_provenance(**over) -> V2EventProvenance:
    base = dict(
        run_kind=LIVE, run_id="live-shadow",
        model_family="v2", rules_version="v2-rules-v0.1.0",
        symbol="BTCUSDT", market_type="perp",
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-deadbeef",
    )
    base.update(over)
    return V2EventProvenance(**base)


def _event_kwargs(**over):
    base = dict(
        event_id="evt-1", episode_id="ep-1", direction=LONG,
        setup_family=TREND_PULLBACK, structural_anchor={"bucket_ts": "x"},
        episode_state=EARLY_SIGNAL, decision_boundary=B,
        decision_snapshot={"consensus_confidence": 87.5},
        event_payload={"entry_zone": {"low": 1.0}},
    )
    base.update(over)
    return base


def build(provenance=None, **over):
    return build_v2_episode_event(provenance or make_provenance(), **_event_kwargs(**over))


# ---- basic contract -----------------------------------------------------------
def test_returns_a_real_v2_episode_event():
    ev = build()
    assert type(ev) is V2EpisodeEvent


def test_returned_model_is_deeply_immutable():
    ev = build()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.event_id = "other"  # type: ignore[misc]
    assert isinstance(ev.event_payload, MappingProxyType)
    assert isinstance(ev.decision_snapshot, MappingProxyType)
    assert isinstance(ev.structural_anchor, MappingProxyType)


# ---- provenance fields copied exactly ------------------------------------------
def test_all_provenance_fields_equal_the_snapshot_exactly():
    p = make_provenance(run_kind=REPLAY, run_id="replay-007",
                        rules_version="v2-rules-v2.3.4", calculation_version="c" * 16,
                        config_hash="d" * 64, config_version="9.9.9", code_version="cafebabe",
                        decision_code_version="decision-cafebabe")
    ev = build(provenance=p)
    assert ev.run_kind == p.run_kind
    assert ev.run_id == p.run_id
    assert ev.model_family == p.model_family
    assert ev.rules_version == p.rules_version
    assert ev.symbol == p.symbol
    assert ev.market_type == p.market_type
    assert ev.feature_schema_version == p.feature_schema_version
    assert ev.calculation_version == p.calculation_version
    assert ev.config_hash == p.config_hash
    assert ev.config_version == p.config_version
    assert ev.code_version == p.code_version
    assert ev.decision_code_version == p.decision_code_version


def test_decision_code_version_distinct_from_code_version_through_factory():
    p = make_provenance(code_version="feature-code-v1", decision_code_version="decision-code-v9")
    ev = build(provenance=p)
    assert ev.code_version == "feature-code-v1"
    assert ev.decision_code_version == "decision-code-v9"


# ---- event-specific fields copied exactly --------------------------------------
def test_event_specific_fields_equal_supplied_values_exactly():
    ev = build(event_id="evt-42", episode_id="ep-42", direction=SHORT,
              setup_family=COMPRESSION_BREAKOUT, structural_anchor={"bucket_ts": "y"},
              episode_state=CONFIRMED, decision_boundary=B + timedelta(minutes=5),
              decision_snapshot={"k": 1}, event_payload={"k": 2})
    assert ev.event_id == "evt-42"
    assert ev.episode_id == "ep-42"
    assert ev.direction == SHORT
    assert ev.setup_family == COMPRESSION_BREAKOUT
    assert dict(ev.structural_anchor) == {"bucket_ts": "y"}
    assert ev.episode_state == CONFIRMED
    assert ev.decision_boundary == B + timedelta(minutes=5)
    assert dict(ev.decision_snapshot) == {"k": 1}
    assert dict(ev.event_payload) == {"k": 2}


# ---- no mutation of caller-owned objects ---------------------------------------
def test_factory_does_not_mutate_provenance():
    p = make_provenance()
    before = dataclasses.astuple(p)
    build(provenance=p)
    assert dataclasses.astuple(p) == before


def test_factory_does_not_mutate_caller_mappings():
    payload = {"entry_zone": {"low": 1.0}}
    snapshot = {"a": {"nested": [1, 2, 3]}}
    anchor = {"bucket_ts": "x"}
    build_v2_episode_event(
        make_provenance(), event_id="e", episode_id="ep", direction=LONG,
        setup_family=TREND_PULLBACK, structural_anchor=anchor,
        episode_state=EARLY_SIGNAL, decision_boundary=B,
        decision_snapshot=snapshot, event_payload=payload)
    assert payload == {"entry_zone": {"low": 1.0}}
    assert snapshot == {"a": {"nested": [1, 2, 3]}}
    assert anchor == {"bucket_ts": "x"}


# ---- LIVE / REPLAY provenance flows through -----------------------------------
def test_live_provenance_produces_live_event():
    ev = build(provenance=make_provenance(run_kind=LIVE, run_id="live-shadow"))
    assert ev.run_kind == LIVE


def test_replay_provenance_produces_replay_event():
    ev = build(provenance=make_provenance(run_kind=REPLAY, run_id="replay-001"))
    assert ev.run_kind == REPLAY


# ---- determinism / equality -----------------------------------------------------
def test_same_args_same_provenance_produce_equal_events():
    p = make_provenance()
    assert build(provenance=p) == build(provenance=p)


def test_different_rules_version_provenance_produces_different_event():
    ev1 = build(provenance=make_provenance(rules_version="v2-rules-v0.1.0"))
    ev2 = build(provenance=make_provenance(rules_version="v2-rules-v0.2.0"))
    assert ev1.rules_version != ev2.rules_version
    assert ev1 != ev2


# ---- copied, never recomputed/inferred -----------------------------------------
def test_calculation_version_is_copied_never_recomputed():
    p = make_provenance(calculation_version="f" * 16)
    ev = build(provenance=p)
    assert ev.calculation_version == "f" * 16 == p.calculation_version


def test_rules_version_is_copied_never_inferred_from_calculation_version():
    p = make_provenance(rules_version="v2-rules-v5.6.7", calculation_version="1" * 16)
    ev = build(provenance=p)
    assert ev.rules_version == "v2-rules-v5.6.7"
    assert ev.rules_version != ev.calculation_version


# ---- caller cannot override provenance-owned fields ----------------------------
@pytest.mark.parametrize("field,value", [
    ("model_family", "v1"),
    ("rules_version", "v2-rules-v9.9.9"),
    ("feature_schema_version", 999),
    ("calculation_version", "9" * 16),
    ("config_hash", "9" * 64),
    ("config_version", "9.9.9"),
    ("code_version", "override"),
    ("decision_code_version", "override"),
    ("run_kind", REPLAY),
    ("run_id", "other-run"),
    ("symbol", "ETHUSDT"),
    ("market_type", "spot"),
])
def test_caller_cannot_override_provenance_owned_field(field, value):
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        build_v2_episode_event(
            make_provenance(), **_event_kwargs(), **{field: value})


def test_factory_signature_has_no_provenance_owned_parameters():
    sig = inspect.signature(build_v2_episode_event)
    provenance_owned = {
        "run_kind", "run_id", "model_family", "rules_version", "symbol",
        "market_type", "feature_schema_version", "calculation_version",
        "config_hash", "config_version", "code_version", "decision_code_version",
    }
    assert provenance_owned.isdisjoint(sig.parameters.keys())


# ---- malformed event-specific fields fail through V2EpisodeEvent --------------
def test_malformed_direction_fails_through_v2_episode_event_validation():
    with pytest.raises(V2EventInputError, match="direction"):
        build(direction="NEUTRAL")


def test_malformed_episode_state_fails_through_v2_episode_event_validation():
    with pytest.raises(V2EventInputError, match="episode_state"):
        build(episode_state="REVERSAL_CANDIDATE")


def test_naive_decision_boundary_fails_through_v2_episode_event_validation():
    with pytest.raises(V2EventInputError, match="decision_boundary"):
        build(decision_boundary=datetime(2026, 7, 22, 12, 15, 0))


def test_non_mapping_event_payload_fails_through_v2_episode_event_validation():
    with pytest.raises(V2EventInputError, match="event_payload"):
        build(event_payload="not-a-mapping")


# ---- purity: no DB/network/clock/config access ---------------------------------
def test_factory_contains_no_db_network_clock_config_access():
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.event_factory", fromlist=["event_factory"]))
    forbidden = (
        "datetime.now(", "time.time(", "uuid.uuid4(", "random.",
        "open(", "os.environ", "os.getenv", "yaml.safe_load", "asyncpg",
        "await ", "async def", "insert_v2_episode_events",
    )
    for token in forbidden:
        assert token not in src, f"forbidden token found in event_factory.py: {token!r}"


def test_factory_is_a_plain_sync_function():
    assert not inspect.iscoroutinefunction(build_v2_episode_event)
