"""Tests for analytics/forecasting_v2/decision_provenance.py's
V2DecisionProvenance.

Mirrors tests/analytics/test_forecasting_v2_provenance.py's style for the
field validations `V2DecisionProvenance` shares with `V2EventProvenance`
(run_kind, model_family, rules_version, symbol, market_type,
feature_schema_version, calculation_version, config_hash, config_version,
code_version — reused via analytics/forecasting_v2/_validation.py, never a
second competing implementation) and adds coverage for the two fields
`V2DecisionProvenance` has that `V2EventProvenance` does not:
`decision_boundary` and `decision_code_version`.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt_module
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2._validation import (
    validate_calculation_version, validate_config_hash,
    validate_feature_schema_version, validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.decision_provenance import (
    V2DecisionProvenance, V2DecisionProvenanceError,
)
from analytics.forecasting_v2.events import LIVE, REPLAY
from common.v2_config import MODEL_FAMILY, validate_rules_version

H64 = "a" * 64
H16 = "b" * 16
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def make_provenance(**over) -> V2DecisionProvenance:
    base = dict(
        run_kind=LIVE, run_id="live-shadow",
        decision_boundary=T0,
        model_family="v2", rules_version="v2-rules-v0.2.0",
        symbol="BTCUSDT", market_type="perp",
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-code-v1",
    )
    base.update(over)
    return V2DecisionProvenance(**base)


# ---- basic construction -----------------------------------------------------
def test_valid_construction():
    p = make_provenance()
    assert p.run_kind == LIVE
    assert p.decision_boundary == T0
    assert p.model_family == "v2"
    assert p.rules_version == "v2-rules-v0.2.0"
    assert p.symbol == "BTCUSDT"
    assert p.market_type == "perp"
    assert p.feature_schema_version == 1
    assert p.calculation_version == H16
    assert p.config_hash == H64
    assert p.config_version == "2.1.0"
    assert p.code_version == "deadbeef"
    assert p.decision_code_version == "decision-code-v1"


def test_is_frozen_dataclass():
    p = make_provenance()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.run_id = "other"  # type: ignore[misc]


def test_determinism_same_inputs_equal_objects():
    assert make_provenance() == make_provenance()


# ---- decision_boundary (T) ---------------------------------------------------
def test_decision_boundary_must_be_datetime():
    with pytest.raises(V2DecisionProvenanceError, match="decision_boundary"):
        make_provenance(decision_boundary="2026-08-20T12:00:00Z")


def test_decision_boundary_must_be_aware():
    with pytest.raises(V2DecisionProvenanceError, match="decision_boundary"):
        make_provenance(decision_boundary=datetime(2026, 8, 20, 12, 0))


def test_decision_boundary_must_be_utc():
    non_utc = datetime(2026, 8, 20, 12, 0, tzinfo=timezone(timedelta(hours=1)))
    with pytest.raises(V2DecisionProvenanceError, match="decision_boundary"):
        make_provenance(decision_boundary=non_utc)


@pytest.mark.parametrize("bad", [
    datetime(2026, 8, 20, 12, 0, 1, tzinfo=timezone.utc),
    datetime(2026, 8, 20, 12, 0, 0, 1, tzinfo=timezone.utc),
])
def test_decision_boundary_must_be_whole_minute(bad):
    with pytest.raises(V2DecisionProvenanceError, match="decision_boundary"):
        make_provenance(decision_boundary=bad)


def test_decision_boundary_preserved_exactly():
    t = datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc)
    assert make_provenance(decision_boundary=t).decision_boundary == t


# ---- Qodo amendment round 1, finding 6: reuse the canonical alignment
# validator -- illegal (off-5m-grid) boundaries must be rejected, not just
# whole-minute ones ----------------------------------------------------------
@pytest.mark.parametrize("bad_minute", [1, 2, 3, 4, 6, 7, 8, 9])
def test_off_5m_grid_whole_minute_decision_boundary_rejected(bad_minute):
    """12:03 etc. are whole-minute but NOT aligned to the 5m grid --
    downstream alignment (`selected_bucket`) would reject the same T, so
    provenance must never accept it either."""
    off_grid = datetime(2026, 8, 20, 12, bad_minute, tzinfo=timezone.utc)
    with pytest.raises(V2DecisionProvenanceError, match="decision_boundary"):
        make_provenance(decision_boundary=off_grid)


def test_decision_boundary_validation_delegates_to_selected_bucket_no_duplicate_regex():
    """No locally-maintained weaker duplicate grid-alignment check."""
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.decision_provenance", fromlist=["decision_provenance"]))
    assert "selected_bucket(" in src
    assert "% 5" not in src  # no local re-derivation of the 5m-grid modulus check


def test_15m_1h_4h_grid_aligned_boundaries_accepted():
    """Every 5m-grid-aligned instant is a legal decision boundary --
    aligning to a COARSER grid (15m/1h/4h) is not itself required, only
    5m-grid alignment (matches alignment.selected_bucket()'s own
    contract)."""
    for t in (
        datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 12, 10, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc),
    ):
        assert make_provenance(decision_boundary=t).decision_boundary == t


# ---- tech-lead amendment: malformed tzinfo never leaks a raw exception -----
class _RaisingTzinfo(_dt_module.tzinfo):
    """A malformed/malicious custom `tzinfo` whose `utcoffset()` raises on
    every call."""
    def utcoffset(self, dt):  # noqa: D102 - deliberately misbehaving
        raise RuntimeError("malformed tzinfo: utcoffset() always raises")

    def tzname(self, dt):
        return "RAISING"

    def dst(self, dt):
        return timedelta(0)


def test_malformed_tzinfo_utcoffset_never_leaks_raw_exception():
    bad_dt = datetime(2026, 8, 20, 12, 0, tzinfo=_RaisingTzinfo())
    with pytest.raises(V2DecisionProvenanceError) as exc_info:
        make_provenance(decision_boundary=bad_dt)
    assert "RuntimeError" in str(exc_info.value) or isinstance(
        exc_info.value.__cause__, RuntimeError)


def test_validator_itself_never_calls_utcoffset_directly():
    """This module's own `_validate_decision_boundary` delegates entirely
    to `alignment.selected_bucket()` and never itself calls `.utcoffset()`
    -- confirmed by AST inspection of the function's actual CODE (not its
    docstring, which mentions `.utcoffset()` in prose), so a future edit
    can't silently reintroduce the un-translated multi-call pattern this
    amendment fixes."""
    import ast
    func = (
        __import__("analytics.forecasting_v2.decision_provenance", fromlist=["decision_provenance"])
        ._validate_decision_boundary)
    tree = ast.parse(inspect.getsource(func))
    utcoffset_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "utcoffset"
    ]
    assert utcoffset_calls == []


# ---- decision_code_version ---------------------------------------------------
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_decision_code_version_nonblank(bad):
    with pytest.raises(V2DecisionProvenanceError, match="decision_code_version"):
        make_provenance(decision_code_version=bad)


def test_decision_code_version_is_a_separate_field_from_code_version():
    """The load-bearing distinction §3.3 requires: decision_code_version
    (Stage 4/5/6 decision-code identity) and code_version (Stage 2
    feature-computation-code identity) are independently settable and
    never required to be equal or derived from one another."""
    p = make_provenance(code_version="feature-code-abc", decision_code_version="decision-code-xyz")
    assert p.code_version == "feature-code-abc"
    assert p.decision_code_version == "decision-code-xyz"
    assert p.code_version != p.decision_code_version

    # And they ARE allowed to coincide -- no artificial inequality is
    # enforced (a real coincidence is not a bug).
    same = make_provenance(code_version="same-value", decision_code_version="same-value")
    assert same.code_version == same.decision_code_version


# ---- run_kind / run_id -------------------------------------------------------
def test_live_accepted():
    assert make_provenance(run_kind=LIVE).run_kind == LIVE


def test_replay_accepted():
    assert make_provenance(run_kind=REPLAY).run_kind == REPLAY


@pytest.mark.parametrize("bad", ["BOTH", "live", "replay", "", "LIVE_REPLAY"])
def test_third_run_kind_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="run_kind"):
        make_provenance(run_kind=bad)


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_blank_run_id_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="run_id"):
        make_provenance(run_id=bad)


# ---- model_family / rules_version -------------------------------------------
def test_model_family_exactly_v2():
    assert make_provenance().model_family == MODEL_FAMILY == "v2"


@pytest.mark.parametrize("bad", ["v1", "V2", "2", "", None])
def test_v1_or_malformed_model_family_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="model_family"):
        make_provenance(model_family=bad)


@pytest.mark.parametrize("good", [
    "v2-rules-v0.1.0", "v2-rules-v1.0.0", "v2-rules-v10.20.30", "v2-rules-v0.0.0",
])
def test_valid_v2_rules_version_accepted(good):
    assert make_provenance(rules_version=good).rules_version == good


@pytest.mark.parametrize("bad", [
    "forecast-rules-v0.1.0", "v2-rules-v01.0.0", "v2-rules-v1.0", "v2-rules-0.1.0", "",
])
def test_v1_or_malformed_rules_version_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="rules_version"):
        make_provenance(rules_version=bad)


def test_rules_version_reuses_shared_validator_not_a_second_regex():
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.decision_provenance", fromlist=["decision_provenance"]))
    assert "validate_rules_version" in src
    assert "re.compile" not in src
    from analytics.forecasting_v2 import decision_provenance as _dp_mod
    assert _dp_mod.validate_rules_version is validate_rules_version


# ---- symbol / market_type ----------------------------------------------------
def test_btcusdt_accepted():
    assert make_provenance(symbol="BTCUSDT").symbol == "BTCUSDT"


@pytest.mark.parametrize("bad", ["ETHUSDT", "btcusdt", "", "BTCUSD"])
def test_unsupported_symbol_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="symbol"):
        make_provenance(symbol=bad)


def test_perp_accepted():
    assert make_provenance(market_type="perp").market_type == "perp"


@pytest.mark.parametrize("bad", ["spot", "futures", "PERP", ""])
def test_spot_or_malformed_market_type_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="market_type"):
        make_provenance(market_type=bad)


# ---- feature_schema_version --------------------------------------------------
def test_feature_schema_version_positive_int_accepted():
    assert make_provenance(feature_schema_version=3).feature_schema_version == 3


@pytest.mark.parametrize("bad", [0, -1, 1.5, "1", None])
def test_feature_schema_version_bad_values_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="feature_schema_version"):
        make_provenance(feature_schema_version=bad)


def test_bool_rejected_as_feature_schema_version():
    with pytest.raises(V2DecisionProvenanceError, match="feature_schema_version"):
        make_provenance(feature_schema_version=True)


# ---- calculation_version / config_hash / config_version / code_version -----
def test_calculation_version_exact_format():
    assert make_provenance(calculation_version=H16).calculation_version == H16


@pytest.mark.parametrize("bad", ["a" * 15, "a" * 17, "A" * 16, "g" * 16, ""])
def test_calculation_version_malformed_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="calculation_version"):
        make_provenance(calculation_version=bad)


def test_config_hash_exact_format():
    assert make_provenance(config_hash=H64).config_hash == H64


@pytest.mark.parametrize("bad", ["a" * 63, "a" * 65, "A" * 64, "g" * 64, ""])
def test_config_hash_malformed_rejected(bad):
    with pytest.raises(V2DecisionProvenanceError, match="config_hash"):
        make_provenance(config_hash=bad)


@pytest.mark.parametrize("field", ["config_version", "code_version"])
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_config_and_code_version_nonblank(field, bad):
    with pytest.raises(V2DecisionProvenanceError, match=field):
        make_provenance(**{field: bad})


# ---- purity: no clock / uuid / random / config / file / env / db access ----
def test_no_clock_uuid_random_config_file_env_db_access():
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.decision_provenance", fromlist=["decision_provenance"]))
    forbidden = (
        "datetime.now(", "time.time(", "uuid.uuid4(", "random.",
        "open(", "os.environ", "os.getenv", "yaml.safe_load", "asyncpg",
        "V2Config.load", "Stage2Config",
    )
    for token in forbidden:
        assert token not in src, f"forbidden token found in decision_provenance.py: {token!r}"


# ---- shared validation reuse (no duplicated hex regex) ----------------------
def test_module_defines_no_local_hex_regex():
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.decision_provenance", fromlist=["decision_provenance"]))
    assert "re.compile" not in src


def test_reuses_shared_validators_directly():
    from analytics.forecasting_v2 import decision_provenance as dp_mod
    assert dp_mod.validate_calculation_version is validate_calculation_version
    assert dp_mod.validate_config_hash is validate_config_hash
    assert dp_mod.validate_feature_schema_version is validate_feature_schema_version
    assert dp_mod.validate_symbol is validate_symbol
    assert dp_mod.validate_market_type is validate_market_type


# ---- §3.2: superset relationship with V2EventProvenance ---------------------
def test_field_superset_of_event_provenance():
    """V2DecisionProvenance carries every V2EventProvenance field PLUS
    exactly decision_boundary -- never a silently-diverged parallel field
    set. `decision_code_version` itself is now shared by BOTH (V2-H3
    closed the prior gap where V2EventProvenance lacked it, per §3.2's own
    "the tuple... follows the computation through every stage... to the
    persisted V2EpisodeEvent" requirement) -- decision_boundary remains
    the ONE field V2DecisionProvenance alone carries (it is resolved
    BEFORE Stage 3/4/5/6 computation begins, per decision_provenance.py's
    own module docstring; V2EventProvenance's caller supplies it
    separately, to event_factory.build_v2_episode_event(), not via
    provenance)."""
    from analytics.forecasting_v2.provenance import V2EventProvenance
    event_fields = {f.name for f in dataclasses.fields(V2EventProvenance)}
    decision_fields = {f.name for f in dataclasses.fields(V2DecisionProvenance)}
    assert event_fields <= decision_fields
    assert decision_fields - event_fields == {"decision_boundary"}
    assert "decision_code_version" in event_fields
    assert "decision_code_version" in decision_fields
