"""Pure tests for analytics/forecasting_v2/episode_identity.py (V2-H3,
docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1a).

No DB, network, clock, or filesystem access anywhere in this file's
SUBJECT module -- these are exclusively pure, deterministic-function
tests. Real-PostgreSQL retry/concurrency/rollback/restart proofs for the
identities THIS module produces live in
tests/storage/test_v2_episode_event_transactions.py.
"""
from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.episode_identity import (
    EPISODE_ID_HASH_ALGORITHM, EVENT_ID_HASH_ALGORITHM, ID_HEX_LENGTH,
    V2EpisodeIdentityError, compute_episode_id, compute_event_id,
)
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT, LONG, SHORT, TREND_PULLBACK,
)
from common.v2_config import MODEL_FAMILY

UTC = timezone.utc
T_CREATE = datetime(2026, 7, 22, 12, 15, 0, tzinfo=UTC)   # legal 5m boundary
H16 = "b" * 16
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _episode_id(**over) -> str:
    base = dict(
        model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
        calculation_version=H16, symbol="BTCUSDT", market_type="perp",
        direction=LONG, setup_family=TREND_PULLBACK,
        structural_anchor={"bucket_ts": "2026-07-22T12:00:00+00:00"},
        t_create=T_CREATE,
    )
    base.update(over)
    return compute_episode_id(**base)


# ============================================================================
# 1. hash algorithm / output representation
# ============================================================================
def test_hash_algorithm_is_sha256():
    assert EPISODE_ID_HASH_ALGORITHM == "sha256"
    assert EVENT_ID_HASH_ALGORITHM == "sha256"


def test_id_hex_length_is_full_64_not_truncated():
    # Deliberately NOT calculation_version's 16-char convention -- see
    # module docstring "Hash algorithm and representation" for why.
    assert ID_HEX_LENGTH == 64


def test_episode_id_is_64_lowercase_hex():
    eid = _episode_id()
    assert isinstance(eid, str)
    assert HEX64_RE.fullmatch(eid)


def test_event_id_is_64_lowercase_hex():
    eid = _episode_id()
    evid = compute_event_id(episode_id=eid, decision_boundary=T_CREATE)
    assert HEX64_RE.fullmatch(evid)


def test_module_reuses_canonical_json_not_a_second_implementation():
    import analytics.forecasting_v2.episode_identity as mod
    src = inspect.getsource(mod)
    assert "canonical_json" in src
    assert "json.dumps(" not in src   # no competing ad-hoc serialization


def test_module_never_uses_clock_uuid_random():
    import analytics.forecasting_v2.episode_identity as mod
    src = inspect.getsource(mod)
    for forbidden in ("datetime.now(", "datetime.utcnow(", "time.time(",
                      "uuid.uuid4(", "random."):
        assert forbidden not in src


# ============================================================================
# 2. determinism
# ============================================================================
def test_episode_id_deterministic_across_repeated_construction():
    assert _episode_id() == _episode_id()


def test_event_id_deterministic_across_repeated_construction():
    eid = _episode_id()
    assert (compute_event_id(episode_id=eid, decision_boundary=T_CREATE)
            == compute_event_id(episode_id=eid, decision_boundary=T_CREATE))


def test_episode_id_deterministic_across_many_calls():
    values = {_episode_id() for _ in range(20)}
    assert len(values) == 1


# ============================================================================
# 3. one-field semantic difference changes identity (episode_id)
# ============================================================================
_BASELINE_EID = _episode_id()


@pytest.mark.parametrize("override", [
    {"rules_version": "v2-rules-v0.2.0"},
    {"calculation_version": "c" * 16},
    {"symbol": "BTCUSDT"},  # placeholder overwritten below; kept for shape
    {"direction": SHORT},
    {"setup_family": COMPRESSION_BREAKOUT},
    {"structural_anchor": {"bucket_ts": "2026-07-22T12:15:00+00:00"}},
    {"t_create": T_CREATE + timedelta(minutes=5)},
])
def test_single_field_change_forks_episode_id(override):
    if override == {"symbol": "BTCUSDT"}:
        pytest.skip("BTCUSDT is the only supported symbol; no fork vector available")
    forked = _episode_id(**override)
    assert forked != _BASELINE_EID


def test_market_type_is_pinned_no_fork_vector_available():
    # 'perp' is the only supported market_type today -- included here to
    # document that this field participates in the identity even though
    # V2-v0's single-value scope means there is currently no OTHER legal
    # value to fork against.
    with pytest.raises(V2EpisodeIdentityError, match="market_type"):
        _episode_id(market_type="spot")


def test_model_family_change_rejected_not_forked():
    # model_family has exactly one legal value ("v2") -- a different value
    # is a validation error, not a legitimate fork vector.
    with pytest.raises(V2EpisodeIdentityError, match="model_family"):
        _episode_id(model_family="v1")


# ---- event_id fork vectors ---------------------------------------------------
def test_event_id_forks_on_episode_id_change():
    eid1 = _episode_id()
    eid2 = _episode_id(direction=SHORT)
    ev1 = compute_event_id(episode_id=eid1, decision_boundary=T_CREATE)
    ev2 = compute_event_id(episode_id=eid2, decision_boundary=T_CREATE)
    assert ev1 != ev2


def test_event_id_forks_on_decision_boundary_change():
    eid = _episode_id()
    ev1 = compute_event_id(episode_id=eid, decision_boundary=T_CREATE)
    ev2 = compute_event_id(episode_id=eid, decision_boundary=T_CREATE + timedelta(minutes=5))
    assert ev1 != ev2


# ============================================================================
# 4. excluded fields: run_kind/run_id/decision_code_version never participate
# ============================================================================
def test_episode_id_has_no_run_kind_run_id_parameters():
    sig = inspect.signature(compute_episode_id)
    assert "run_kind" not in sig.parameters
    assert "run_id" not in sig.parameters
    assert "decision_code_version" not in sig.parameters


def test_event_id_has_no_run_kind_run_id_decision_code_version_parameters():
    sig = inspect.signature(compute_event_id)
    assert "run_kind" not in sig.parameters
    assert "run_id" not in sig.parameters
    assert "decision_code_version" not in sig.parameters


def test_event_id_has_no_event_kind_or_ordinal_parameter():
    # §2.1a's own frozen same-T singular-event model makes an ordinal/
    # sequence number unnecessary -- (episode_id, decision_boundary) alone
    # is already unambiguous.
    sig = inspect.signature(compute_event_id)
    assert set(sig.parameters.keys()) == {"episode_id", "decision_boundary"}


# ============================================================================
# 5. LIVE/REPLAY and run-identity independence (proven via signature, then
#    semantically: identical episode-fact inputs -> identical episode_id,
#    regardless of which execution_stream a FUTURE caller will eventually
#    namespace the resulting event under)
# ============================================================================
def test_identical_episode_facts_yield_identical_id_regardless_of_intended_run():
    # episode_identity.py has no run_kind/run_id concept at all (proven by
    # signature above) -- this test demonstrates the INTENDED consequence:
    # a LIVE run and a REPLAY run computing the identical episode facts
    # must derive the identical episode_id, so the physical
    # (run_kind, run_id, episode_id, decision_boundary) namespace is the
    # ONLY thing that keeps their storage rows apart.
    live_style = _episode_id()
    replay_style = _episode_id()  # no run_kind/run_id input possible at all
    assert live_style == replay_style


# ============================================================================
# 6. timezone canonicalization
# ============================================================================
def test_utc_and_equivalent_fixed_offset_canonicalize_identically():
    t_utc = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)
    t_fixed_zero_offset = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone(timedelta(0)))
    eid_utc = _episode_id(t_create=t_utc)
    eid_fixed = _episode_id(t_create=t_fixed_zero_offset)
    assert eid_utc == eid_fixed


def test_naive_datetime_rejected():
    with pytest.raises(V2EpisodeIdentityError, match="t_create"):
        _episode_id(t_create=datetime(2026, 8, 21, 12, 0, 0))


def test_non_utc_offset_datetime_rejected():
    tz_plus_2 = timezone(timedelta(hours=2))
    with pytest.raises(V2EpisodeIdentityError, match="t_create"):
        _episode_id(t_create=datetime(2026, 8, 21, 14, 0, 0, tzinfo=tz_plus_2))


def test_off_5m_grid_t_create_rejected():
    # Unlike V2EpisodeEvent.decision_boundary (deliberately unchecked for
    # grid alignment, per that module's own comment), episode_identity.py
    # DOES require a legal V2 5m decision boundary for t_create/
    # decision_boundary -- T_create is frozen as "the episode's own
    # EARLY_SIGNAL decision boundary" (§2.1a), which is always a legal 5m
    # boundary by construction.
    with pytest.raises(V2EpisodeIdentityError, match="t_create"):
        _episode_id(t_create=datetime(2026, 8, 21, 12, 3, 0, tzinfo=UTC))


def test_off_5m_grid_decision_boundary_rejected():
    eid = _episode_id()
    with pytest.raises(V2EpisodeIdentityError, match="decision_boundary"):
        compute_event_id(episode_id=eid, decision_boundary=datetime(2026, 8, 21, 12, 3, 0, tzinfo=UTC))


def test_non_datetime_t_create_rejected():
    with pytest.raises(V2EpisodeIdentityError, match="t_create"):
        _episode_id(t_create="2026-08-21T12:00:00+00:00")


# ============================================================================
# 7. malformed version/run identity rejection
# ============================================================================
@pytest.mark.parametrize("bad", ["", "   ", None, "v2-rules-v01.0.0", "forecast-rules-v0.1.0"])
def test_malformed_rules_version_rejected(bad):
    with pytest.raises(V2EpisodeIdentityError, match="rules_version"):
        _episode_id(rules_version=bad)


@pytest.mark.parametrize("bad", ["", "a" * 15, "a" * 17, "A" * 16, "g" * 16])
def test_malformed_calculation_version_rejected(bad):
    with pytest.raises(V2EpisodeIdentityError, match="calculation_version"):
        _episode_id(calculation_version=bad)


@pytest.mark.parametrize("bad", ["ETHUSDT", "btcusdt", "", None])
def test_unsupported_symbol_rejected(bad):
    with pytest.raises(V2EpisodeIdentityError, match="symbol"):
        _episode_id(symbol=bad)


@pytest.mark.parametrize("bad", ["NEUTRAL", "long", "", None])
def test_invalid_direction_rejected(bad):
    with pytest.raises(V2EpisodeIdentityError, match="direction"):
        _episode_id(direction=bad)


@pytest.mark.parametrize("bad", ["UNKNOWN_FAMILY", "trend_pullback", "", None])
def test_invalid_setup_family_rejected(bad):
    with pytest.raises(V2EpisodeIdentityError, match="setup_family"):
        _episode_id(setup_family=bad)


@pytest.mark.parametrize("bad", ["not-a-mapping", 123, ["a", "b"], None])
def test_non_mapping_structural_anchor_rejected(bad):
    with pytest.raises(V2EpisodeIdentityError, match="structural_anchor"):
        _episode_id(structural_anchor=bad)


# ---- compute_event_id's own episode_id shape validation ---------------------
@pytest.mark.parametrize("bad", ["", "   ", None, "not-a-hash", "a" * 63, "a" * 65, "A" * 64, "g" * 64])
def test_compute_event_id_rejects_malformed_episode_id(bad):
    with pytest.raises(V2EpisodeIdentityError, match="episode_id"):
        compute_event_id(episode_id=bad, decision_boundary=T_CREATE)


def test_compute_event_id_accepts_a_real_compute_episode_id_output():
    eid = _episode_id()
    evid = compute_event_id(episode_id=eid, decision_boundary=T_CREATE)
    assert HEX64_RE.fullmatch(evid)


# ============================================================================
# 8. canonicalization ambiguity resistance
# ============================================================================
def test_structural_anchor_key_order_does_not_affect_id():
    anchor_a = {"bucket_ts": "2026-07-22T12:00:00+00:00", "price": 66000.0}
    anchor_b = {"price": 66000.0, "bucket_ts": "2026-07-22T12:00:00+00:00"}
    assert _episode_id(structural_anchor=anchor_a) == _episode_id(structural_anchor=anchor_b)


def test_structural_anchor_list_boundary_ambiguity_resistance():
    # ["a|b", "c"] must not collide with ["a", "b|c"] -- proves the hash
    # input is genuine structural JSON, never a naively delimiter-joined
    # string.
    eid_1 = _episode_id(structural_anchor={"tags": ["a|b", "c"]})
    eid_2 = _episode_id(structural_anchor={"tags": ["a", "b|c"]})
    assert eid_1 != eid_2


def test_structural_anchor_nested_vs_flat_does_not_collide():
    eid_nested = _episode_id(structural_anchor={"a": {"b": 1}})
    eid_flat = _episode_id(structural_anchor={"a.b": 1})
    assert eid_nested != eid_flat


def test_structural_anchor_int_vs_string_number_does_not_collide():
    eid_int = _episode_id(structural_anchor={"tick_index": 662000})
    eid_str = _episode_id(structural_anchor={"tick_index": "662000"})
    assert eid_int != eid_str


def test_structural_anchor_datetime_leaf_canonicalizes_to_isoformat():
    # A raw, already-UTC datetime leaf (as events.py's _deep_freeze itself
    # accepts) must canonicalize identically to its own pre-stringified
    # ISO form -- matching storage/stage2_serialization.py::to_jsonable's
    # convention exactly, so the same logical value hashes the same way it
    # will eventually be persisted.
    dt = datetime(2026, 7, 22, 12, 10, 0, tzinfo=UTC)
    eid_dt = _episode_id(structural_anchor={"bucket_ts": dt})
    eid_str = _episode_id(structural_anchor={"bucket_ts": dt.isoformat()})
    assert eid_dt == eid_str


def test_structural_anchor_naive_datetime_leaf_rejected():
    with pytest.raises(V2EpisodeIdentityError, match="structural_anchor"):
        _episode_id(structural_anchor={"bucket_ts": datetime(2026, 7, 22, 12, 10, 0)})


def test_structural_anchor_non_utc_datetime_leaf_rejected():
    tz_plus_2 = timezone(timedelta(hours=2))
    with pytest.raises(V2EpisodeIdentityError, match="structural_anchor"):
        _episode_id(structural_anchor={"bucket_ts": datetime(2026, 7, 22, 14, 10, 0, tzinfo=tz_plus_2)})


def test_structural_anchor_non_finite_float_leaf_rejected():
    with pytest.raises(V2EpisodeIdentityError, match="structural_anchor"):
        _episode_id(structural_anchor={"price": float("nan")})
    with pytest.raises(V2EpisodeIdentityError, match="structural_anchor"):
        _episode_id(structural_anchor={"price": float("inf")})


def test_structural_anchor_non_string_key_rejected():
    with pytest.raises(V2EpisodeIdentityError, match="structural_anchor"):
        _episode_id(structural_anchor={1: "x"})


def test_structural_anchor_unsupported_type_leaf_rejected():
    with pytest.raises(V2EpisodeIdentityError, match="structural_anchor"):
        _episode_id(structural_anchor={"anchor": object()})


def test_structural_anchor_confirmed_breakout_worked_vector_reproducible():
    # §12.5a's exact JSON-safe shape for CONFIRMED_BREAKOUT: tick_index as
    # a plain int, normalized_level_price/creation_identity_tick_size as
    # canonical decimal STRINGS (never bare floats, per §12.5a's own
    # persisted-representation freeze). Confirms this module hashes that
    # exact shape deterministically without reinterpreting it.
    anchor = {
        "level_anchor_bucket": "2026-07-22T10:00:00+00:00",
        "tick_index": 662000,
        "normalized_level_price": "66200.0",
        "creation_identity_tick_size": "0.1",
    }
    eid1 = _episode_id(
        direction=LONG, setup_family=CONFIRMED_BREAKOUT, structural_anchor=anchor)
    eid2 = _episode_id(
        direction=LONG, setup_family=CONFIRMED_BREAKOUT, structural_anchor=dict(anchor))
    assert eid1 == eid2
    assert HEX64_RE.fullmatch(eid1)


def test_tuple_and_list_structural_anchor_values_hash_identically():
    # canonical_json's own _to_plain treats tuple/list interchangeably --
    # proven here at this module's own boundary, not merely assumed from
    # common/versioning.py's docstring.
    eid_list = _episode_id(structural_anchor={"path": [1, 2, 3]})
    eid_tuple = _episode_id(structural_anchor={"path": (1, 2, 3)})
    assert eid_list == eid_tuple


# ============================================================================
# 9. decision_boundary vs t_create -- episode identity is fixed at creation
# ============================================================================
def test_episode_id_uses_t_create_not_a_later_decision_boundary():
    # An episode's identity must NOT shift as later decision boundaries
    # observe/update it -- t_create is the ONLY boundary episode_id ever
    # sees; a later re-evaluation at a DIFFERENT T must not change it.
    eid_at_creation = _episode_id(t_create=T_CREATE)
    # Simulate "the same episode, observed again 15 minutes later" -- the
    # caller passes the SAME t_create (creation is immutable per §12.2),
    # never the later boundary, so this reproduces the identical id.
    eid_observed_later = _episode_id(t_create=T_CREATE)
    assert eid_at_creation == eid_observed_later


def test_event_id_at_different_boundaries_for_same_episode_are_distinct():
    eid = _episode_id(t_create=T_CREATE)
    ev_at_creation = compute_event_id(episode_id=eid, decision_boundary=T_CREATE)
    ev_15m_later = compute_event_id(
        episode_id=eid, decision_boundary=T_CREATE + timedelta(minutes=15))
    assert ev_at_creation != ev_15m_later
    # ...but both events legitimately belong to the SAME episode_id.
    assert ev_at_creation != eid and ev_15m_later != eid


# ============================================================================
# 10. purity
# ============================================================================
def test_module_is_free_of_io_imports():
    import analytics.forecasting_v2.episode_identity as mod
    src = inspect.getsource(mod)
    for banned_import in ("import asyncio", "import asyncpg", "import os",
                          "import uuid", "import random"):
        assert banned_import not in src
