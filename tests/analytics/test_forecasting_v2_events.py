"""Unit tests for analytics/forecasting_v2/events.py (Multi-model Framework
PR 2). Pure model tests only — no DB, network, clock, or filesystem."""
from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from analytics.forecasting_v2 import events as events_module
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED, CONFIRMED_BREAKOUT, DIRECTIONS,
    EARLY_SIGNAL, EPISODE_STATES, EXPIRED, COMPLETED, INVALIDATED, LIVE,
    LONG, REPLAY, RUN_KINDS, SETUP_FAMILIES, SHORT, SUPPORTED_MARKET_TYPE,
    SUPPORTED_SYMBOL, TREND_PULLBACK, V2EpisodeEvent, V2EventInputError,
    WEAKENING,
)
from common.v2_config import MODEL_FAMILY


def _kwargs(**overrides):
    base = dict(
        run_kind="LIVE", run_id="live-shadow", event_id="evt-1", episode_id="ep-1",
        model_family="v2", rules_version="v2-rules-v0.1.0",
        symbol="BTCUSDT", market_type="perp", direction="LONG",
        setup_family="TREND_PULLBACK",
        structural_anchor={"bucket_ts": "2026-08-15T12:00:00+00:00"},
        episode_state="EARLY_SIGNAL",
        decision_boundary=datetime(2026, 8, 15, 12, 15, tzinfo=timezone.utc),
        feature_schema_version=1,
        calculation_version="a" * 16,
        config_hash="b" * 64,
        config_version="2.1.0",
        code_version="test-code-v0",
        decision_snapshot={"price_evi": 0.5},
        event_payload={"entry_zone": {"lower": 64000.0, "upper": 64100.0}},
    )
    base.update(overrides)
    return base


def _event(**overrides) -> V2EpisodeEvent:
    return V2EpisodeEvent(**_kwargs(**overrides))


# ---- valid construction ------------------------------------------------------
def test_valid_construction():
    ev = _event()
    assert ev.run_kind == "LIVE"
    assert ev.episode_state == "EARLY_SIGNAL"
    assert ev.direction == "LONG"
    assert ev.setup_family == "TREND_PULLBACK"


def test_valid_construction_all_setup_families():
    for family in SETUP_FAMILIES:
        ev = _event(setup_family=family)
        assert ev.setup_family == family


def test_valid_construction_all_episode_states():
    for state in EPISODE_STATES:
        ev = _event(episode_state=state)
        assert ev.episode_state == state


def test_valid_construction_both_directions():
    for direction in DIRECTIONS:
        ev = _event(direction=direction)
        assert ev.direction == direction


def test_valid_construction_both_run_kinds():
    for run_kind in RUN_KINDS:
        ev = _event(run_kind=run_kind, run_id="replay-001" if run_kind == REPLAY else "live-shadow")
        assert ev.run_kind == run_kind


# ---- model_family -------------------------------------------------------------
def test_model_family_must_be_exactly_v2():
    assert MODEL_FAMILY == "v2"
    ev = _event()
    assert ev.model_family == "v2"


@pytest.mark.parametrize("bad_family", ["v1", "V2", "v2 ", "", "2"])
def test_model_family_rejects_non_v2(bad_family):
    with pytest.raises(V2EventInputError, match="model_family"):
        _event(model_family=bad_family)


# ---- rules_version (reused validation, not a competing regex) -----------------
def test_rules_version_valid_shapes_accepted():
    for v in ("v2-rules-v0.1.0", "v2-rules-v1.0.0", "v2-rules-v12.34.56"):
        ev = _event(rules_version=v)
        assert ev.rules_version == v


def test_rules_version_reuses_common_v2_config_validator():
    # events.py must not define its own competing regex.
    src = inspect.getsource(events_module)
    assert "validate_rules_version" in src
    assert "RULES_VERSION_RE" not in src or "common.v2_config" in src


def test_v1_style_rule_version_rejected_as_v2_rules_version():
    with pytest.raises(V2EventInputError, match="rules_version"):
        _event(rules_version="forecast-rules-v0.1.0")


@pytest.mark.parametrize("bad_version", ["", "v2-rules-v0.1", "v2-rules-v", "v2-rules-0.1.0"])
def test_malformed_rules_version_rejected(bad_version):
    with pytest.raises(V2EventInputError, match="rules_version"):
        _event(rules_version=bad_version)


# ---- symbol / market_type (initial V2 scope) -----------------------------------
def test_initial_scope_constants():
    assert SUPPORTED_SYMBOL == "BTCUSDT"
    assert SUPPORTED_MARKET_TYPE == "perp"


@pytest.mark.parametrize("bad_symbol", ["ETHUSDT", "btcusdt", "", "BTCUSD"])
def test_unsupported_symbol_rejected(bad_symbol):
    with pytest.raises(V2EventInputError, match="symbol"):
        _event(symbol=bad_symbol)


@pytest.mark.parametrize("bad_market_type", ["spot", "futures", "PERP", ""])
def test_unsupported_market_type_rejected(bad_market_type):
    with pytest.raises(V2EventInputError, match="market_type"):
        _event(market_type=bad_market_type)


# ---- direction ------------------------------------------------------------------
def test_neutral_direction_rejected():
    # V2 episodes are never NEUTRAL, unlike V1 ForecastPrediction.
    with pytest.raises(V2EventInputError, match="direction"):
        _event(direction="NEUTRAL")


@pytest.mark.parametrize("bad_direction", ["long", "Short", "", "BUY"])
def test_malformed_direction_rejected(bad_direction):
    with pytest.raises(V2EventInputError, match="direction"):
        _event(direction=bad_direction)


# ---- setup_family -----------------------------------------------------------------
@pytest.mark.parametrize("bad_family", ["trend_pullback", "BREAKOUT", "", "PULLBACK"])
def test_malformed_setup_family_rejected(bad_family):
    with pytest.raises(V2EventInputError, match="setup_family"):
        _event(setup_family=bad_family)


# ---- episode_state / REVERSAL_CANDIDATE exclusion ----------------------------------
def test_reversal_candidate_rejected_as_episode_state():
    # Per §13.3, REVERSAL_CANDIDATE is a cross-cutting event attached to an
    # existing episode's history, never the episode's own persisted state.
    with pytest.raises(V2EventInputError, match="episode_state"):
        _event(episode_state="REVERSAL_CANDIDATE")


def test_episode_states_are_exactly_the_six_frozen_states():
    assert set(EPISODE_STATES) == {
        EARLY_SIGNAL, CONFIRMED, WEAKENING, INVALIDATED, EXPIRED, COMPLETED,
    }
    assert "REVERSAL_CANDIDATE" not in EPISODE_STATES


@pytest.mark.parametrize("bad_state", ["early_signal", "ACTIVE", "", "TRIGGERED"])
def test_malformed_episode_state_rejected(bad_state):
    with pytest.raises(V2EventInputError, match="episode_state"):
        _event(episode_state=bad_state)


# ---- run_kind ---------------------------------------------------------------------
@pytest.mark.parametrize("bad_run_kind", ["live", "Replay", "", "SHADOW", "BACKTEST"])
def test_malformed_run_kind_rejected(bad_run_kind):
    with pytest.raises(V2EventInputError, match="run_kind"):
        _event(run_kind=bad_run_kind)


def test_no_third_ambiguous_run_kind():
    assert RUN_KINDS == (LIVE, REPLAY)
    assert len(RUN_KINDS) == 2


# ---- nonblank identifiers ------------------------------------------------------------
@pytest.mark.parametrize("field", ["run_id", "event_id", "episode_id"])
@pytest.mark.parametrize("bad_value", ["", "   ", None, 123])
def test_blank_or_non_string_identifiers_rejected(field, bad_value):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: bad_value})


# ---- datetime validation ------------------------------------------------------------
def test_decision_boundary_must_be_datetime():
    with pytest.raises(V2EventInputError, match="decision_boundary"):
        _event(decision_boundary="2026-08-15T12:15:00Z")


def test_decision_boundary_must_be_tz_aware():
    with pytest.raises(V2EventInputError, match="decision_boundary"):
        _event(decision_boundary=datetime(2026, 8, 15, 12, 15))


def test_decision_boundary_must_be_utc():
    tz_plus_2 = timezone(timedelta(hours=2))
    with pytest.raises(V2EventInputError, match="decision_boundary"):
        _event(decision_boundary=datetime(2026, 8, 15, 14, 15, tzinfo=tz_plus_2))


def test_decision_boundary_no_grid_alignment_enforced():
    # Deliberately NOT enforced here (belongs to a later Multi-timeframe
    # Alignment stage) -- an off-grid timestamp is still accepted.
    ev = _event(decision_boundary=datetime(2026, 8, 15, 12, 17, 23, tzinfo=timezone.utc))
    assert ev.decision_boundary == datetime(2026, 8, 15, 12, 17, 23, tzinfo=timezone.utc)


# ---- shared Stage 2 provenance -------------------------------------------------------
def test_feature_schema_version_must_be_positive_int():
    with pytest.raises(V2EventInputError, match="feature_schema_version"):
        _event(feature_schema_version=0)
    with pytest.raises(V2EventInputError, match="feature_schema_version"):
        _event(feature_schema_version=-1)
    with pytest.raises(V2EventInputError, match="feature_schema_version"):
        _event(feature_schema_version=1.5)
    with pytest.raises(V2EventInputError, match="feature_schema_version"):
        _event(feature_schema_version=True)  # bool is an int subclass


def test_calculation_version_must_be_16_lowercase_hex():
    with pytest.raises(V2EventInputError, match="calculation_version"):
        _event(calculation_version="A" * 16)  # uppercase
    with pytest.raises(V2EventInputError, match="calculation_version"):
        _event(calculation_version="a" * 15)  # wrong length
    with pytest.raises(V2EventInputError, match="calculation_version"):
        _event(calculation_version="g" * 16)  # non-hex


def test_config_hash_must_be_64_lowercase_hex():
    with pytest.raises(V2EventInputError, match="config_hash"):
        _event(config_hash="b" * 63)


@pytest.mark.parametrize("field", ["config_version", "code_version"])
def test_blank_provenance_strings_rejected(field):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: ""})


# ---- structural_anchor / decision_snapshot / event_payload shape --------------------
@pytest.mark.parametrize("field", ["structural_anchor", "decision_snapshot", "event_payload"])
def test_non_mapping_json_object_fields_rejected(field):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: "not-a-mapping"})
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: [1, 2, 3]})
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: None})


def test_empty_json_objects_accepted():
    ev = _event(structural_anchor={}, decision_snapshot={}, event_payload={})
    assert dict(ev.structural_anchor) == {}
    assert dict(ev.decision_snapshot) == {}
    assert dict(ev.event_payload) == {}


def test_non_string_mapping_keys_rejected():
    with pytest.raises(V2EventInputError, match="event_payload"):
        _event(event_payload={1: "x"})


def test_unsupported_nested_value_type_rejected():
    class Weird:
        pass
    with pytest.raises(V2EventInputError, match="event_payload"):
        _event(event_payload={"x": Weird()})


# ---- deep immutability ----------------------------------------------------------------
def test_structural_anchor_is_deeply_frozen():
    ev = _event(structural_anchor={"bucket_ts": "2026-08-15T12:00:00+00:00", "nested": {"a": 1}})
    assert isinstance(ev.structural_anchor, MappingProxyType)
    assert isinstance(ev.structural_anchor["nested"], MappingProxyType)
    with pytest.raises(TypeError):
        ev.structural_anchor["bucket_ts"] = "mutated"


def test_decision_snapshot_is_deeply_frozen():
    ev = _event(decision_snapshot={"price_evi": 0.5, "components": {"regime": "BULLISH"}})
    assert isinstance(ev.decision_snapshot, MappingProxyType)
    assert isinstance(ev.decision_snapshot["components"], MappingProxyType)
    with pytest.raises(TypeError):
        ev.decision_snapshot["price_evi"] = 0.0


def test_event_payload_is_deeply_frozen():
    ev = _event()
    assert isinstance(ev.event_payload, MappingProxyType)
    assert isinstance(ev.event_payload["entry_zone"], MappingProxyType)
    with pytest.raises(TypeError):
        ev.event_payload["entry_zone"] = {}


def test_nested_list_is_frozen_to_tuple():
    ev = _event(event_payload={"reasons": ["A", "B", "C"]})
    assert ev.event_payload["reasons"] == ("A", "B", "C")
    assert isinstance(ev.event_payload["reasons"], tuple)


def test_event_is_a_frozen_dataclass():
    ev = _event()
    assert dataclasses.is_dataclass(ev)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.episode_state = "CONFIRMED"  # type: ignore[misc]


# ---- caller nested-mutation isolation (the load-bearing §2.1 test) ------------------
def test_caller_payload_mutation_after_construction_does_not_leak():
    payload = {"entry_zone": {"lower": 64000.0, "upper": 64100.0}}
    ev = _event(event_payload=payload)
    payload["entry_zone"]["lower"] = 1.0
    payload["entry_zone"]["new_key"] = "should not appear"
    assert ev.event_payload["entry_zone"]["lower"] == 64000.0
    assert "new_key" not in ev.event_payload["entry_zone"]


def test_caller_decision_snapshot_mutation_after_construction_does_not_leak():
    snapshot = {"price_evi": 0.5, "nested": {"x": 1}}
    ev = _event(decision_snapshot=snapshot)
    snapshot["nested"]["x"] = 999
    snapshot["price_evi"] = -1.0
    assert ev.decision_snapshot["nested"]["x"] == 1
    assert ev.decision_snapshot["price_evi"] == 0.5


def test_caller_structural_anchor_mutation_after_construction_does_not_leak():
    anchor = {"bucket_ts": "2026-08-15T12:00:00+00:00"}
    ev = _event(structural_anchor=anchor)
    anchor["bucket_ts"] = "tampered"
    assert ev.structural_anchor["bucket_ts"] == "2026-08-15T12:00:00+00:00"


def test_caller_list_mutation_after_construction_does_not_leak():
    payload = {"reasons": ["A", "B"]}
    ev = _event(event_payload=payload)
    payload["reasons"].append("C")
    assert ev.event_payload["reasons"] == ("A", "B")


# ---- run/event identity (LIVE vs. REPLAY coexistence at the model level) -----------
def test_live_and_replay_may_carry_the_same_event_id():
    live = _event(run_kind="LIVE", run_id="live-shadow", event_id="evt-shared")
    replay = _event(run_kind="REPLAY", run_id="replay-001", event_id="evt-shared")
    assert live.event_id == replay.event_id == "evt-shared"
    assert live.run_kind != replay.run_kind
    assert (live.run_kind, live.run_id, live.event_id) != (replay.run_kind, replay.run_id, replay.event_id)


def test_separate_replay_runs_do_not_collide():
    replay_a = _event(run_kind="REPLAY", run_id="replay-001", event_id="evt-1")
    replay_b = _event(run_kind="REPLAY", run_id="replay-002", event_id="evt-1")
    assert replay_a.run_id != replay_b.run_id
    assert (replay_a.run_kind, replay_a.run_id, replay_a.event_id) != \
           (replay_b.run_kind, replay_b.run_id, replay_b.event_id)


def test_episode_id_preserved_exactly_as_supplied():
    ev = _event(episode_id="episode-abc-123")
    assert ev.episode_id == "episode-abc-123"


# ---- no clock / random / uuid -------------------------------------------------------
def test_module_does_not_import_time_random_or_uuid():
    src = inspect.getsource(events_module)
    for forbidden in ("import random", "import uuid", "import time\n", "datetime.now(", "datetime.utcnow("):
        assert forbidden not in src, f"events.py must not use {forbidden!r}"


def test_no_created_at_field_on_the_model():
    # created_at is DB-owned metadata (table DEFAULT now()), never a model
    # field -- mirrors ForecastPrediction's own created_at exclusion.
    model_fields = {f.name for f in dataclasses.fields(V2EpisodeEvent)}
    assert "created_at" not in model_fields


def test_construction_is_deterministic_given_identical_inputs():
    kwargs = _kwargs()
    ev1 = V2EpisodeEvent(**kwargs)
    ev2 = V2EpisodeEvent(**kwargs)
    assert ev1 == ev2


# ---- episode logical dimensions (§12) are recorded, not derived --------------------
def test_structural_anchor_stored_verbatim_no_detector_math():
    # The model must not recompute or reinterpret structural_anchor -- it is
    # an opaque, already-computed value from a future detector.
    anchor = {"bucket_ts": "2026-08-15T12:00:00+00:00", "arbitrary_future_field": 12345}
    ev = _event(structural_anchor=anchor)
    assert dict(ev.structural_anchor) == anchor


# ============================================================================
# §11 hardening (Multi-model Framework PR 3): JSON-leaf validation aligned
# with the canonical serializer (storage/stage2_serialization.py's
# to_jsonable) -- a malformed float/datetime leaf must fail HERE, at
# V2EpisodeEvent construction, never survive to serialize_batch() time.
# Exercised across all three by-value JSON fields, and both top-level and
# nested-inside-a-list positions.
# ============================================================================
JSON_FIELDS = ["structural_anchor", "decision_snapshot", "event_payload"]


@pytest.mark.parametrize("field", JSON_FIELDS)
def test_finite_float_leaf_accepted(field):
    ev = _event(**{field: {"value": 64123.456, "negative": -0.001, "zero": 0.0}})
    assert dict(getattr(ev, field))["value"] == 64123.456


@pytest.mark.parametrize("field", JSON_FIELDS)
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_leaf_rejected_at_construction(field, bad):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: {"value": bad}})


@pytest.mark.parametrize("field", JSON_FIELDS)
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_leaf_rejected_nested_in_list(field, bad):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: {"values": [1.0, 2.0, bad]}})


@pytest.mark.parametrize("field", JSON_FIELDS)
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_leaf_rejected_nested_in_mapping(field, bad):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: {"nested": {"deep": {"value": bad}}}})


def test_non_finite_float_leaf_fails_before_serialize_batch_not_only_there():
    # This is the load-bearing distinction §11 asks for: construction must
    # already reject it, not merely the storage-layer serializer later.
    with pytest.raises(V2EventInputError):
        _event(event_payload={"value": float("nan")})
    # And prove the storage-layer serializer independently rejects the same
    # shape too, for defense in depth (both layers agree, neither is looser).
    from storage.stage2_serialization import Stage2SerializationError, to_jsonable
    with pytest.raises(Stage2SerializationError):
        to_jsonable({"value": float("nan")})


@pytest.mark.parametrize("field", JSON_FIELDS)
def test_timezone_aware_utc_datetime_leaf_accepted(field):
    dt = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    ev = _event(**{field: {"as_of": dt}})
    assert getattr(ev, field)["as_of"] == dt


@pytest.mark.parametrize("field", JSON_FIELDS)
def test_naive_datetime_leaf_rejected_at_construction(field):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: {"as_of": datetime(2026, 8, 15, 12, 0)}})  # no tzinfo


@pytest.mark.parametrize("field", JSON_FIELDS)
def test_non_utc_datetime_leaf_rejected_at_construction(field):
    non_utc = datetime(2026, 8, 15, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: {"as_of": non_utc}})


@pytest.mark.parametrize("field", JSON_FIELDS)
def test_naive_datetime_leaf_rejected_nested_in_list(field):
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: {"timestamps": [datetime(2026, 8, 15, 12, 0)]}})


@pytest.mark.parametrize("field", JSON_FIELDS)
def test_non_utc_datetime_leaf_rejected_nested_in_tuple(field):
    non_utc = datetime(2026, 8, 15, 12, 0, tzinfo=timezone(timedelta(hours=-5)))
    with pytest.raises(V2EventInputError, match=field):
        _event(**{field: {"timestamps": (non_utc,)}})


def test_naive_datetime_leaf_fails_before_serialize_batch_not_only_there():
    with pytest.raises(V2EventInputError):
        _event(decision_snapshot={"as_of": datetime(2026, 8, 15, 12, 0)})
    from storage.stage2_serialization import Stage2SerializationError, to_jsonable
    with pytest.raises(Stage2SerializationError):
        to_jsonable({"as_of": datetime(2026, 8, 15, 12, 0)})


def test_valid_construction_still_accepts_finite_floats_and_utc_datetimes_together():
    # Regression guard: the hardening must not become over-strict and reject
    # legitimate values that were always allowed.
    ev = _event(event_payload={
        "confidence": 87.5,
        "as_of": datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc),
        "nested": {"values": [1, 2.5, "x", None, True], "when": [
            datetime(2026, 8, 15, 12, 5, tzinfo=timezone.utc)]},
    })
    assert ev.event_payload["confidence"] == 87.5
