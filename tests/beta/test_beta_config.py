"""Beta V0.2 config: strict validation, digest stability, hard switches, secrets."""
import copy
from pathlib import Path

import pytest
import yaml

from beta.config import (BetaConfig, BetaConfigError, BetaSecrets, EVENT_TYPES,
                         effective_d7_enabled, effective_push_enabled, resolve_switches)

# BETA_EVENT_RULES_V1 thresholds are unchanged; the digest covers state_schema_version.
PINNED_RULES_DIGEST = "9e9d2c631a1abfdb710dc2147835b3a0ccd4620512d3a0d6828140c96de17210"          # schema 2
PINNED_RULES_DIGEST_SCHEMA_V1 = "2e0afa4785675e7a3777627f45647f76268a7cdad3e0639c078ee5ccc7605f44"  # schema 1
REPO = Path(__file__).resolve().parents[2]


def _raw():
    return copy.deepcopy(yaml.safe_load((REPO / "config/beta_v0.yaml").read_text())["beta"])


def test_committed_config_loads_with_contract_minimum_keys():
    c = BetaConfig.load()
    # push_enabled: true is the committed hard allow (owner decision 2026-10-01); live push
    # still needs an explicit BETA_PUSH_ENABLED and the admin push state.
    assert c["enabled"] is False and c["push_enabled"] is True and c["outcome_tracking_enabled"] is True
    assert c.rules_version == "BETA_EVENT_RULES_V1" and c.state_schema_version == 2
    assert (c.symbol, c.market_type, c.timeframe) == ("BTCUSDT", "perp", "5m")
    assert c.exchanges == ("binance", "bybit", "okx")
    assert (c["max_state_age_s"], c["same_event_cooldown_min"], c["delivery_ttl_s"],
            c["max_new_pushes_per_utc_day"]) == (420, 20, 600, 3)
    assert c.horizons == ("15m", "30m", "1h", "4h", "24h")


def test_no_secret_or_owner_id_in_yaml():
    text = (REPO / "config/beta_v0.yaml").read_text().lower()
    for bad in ("token:", "owner_user_id", "chat_id", "password"):
        assert bad not in text


def test_rules_digest_is_pinned_and_key_order_independent():
    c = BetaConfig.load()
    assert c.rules_digest == PINNED_RULES_DIGEST
    raw = _raw()
    reordered = dict(reversed(list(raw.items())))
    reordered["rules"] = dict(reversed(list(raw["rules"].items())))
    assert BetaConfig.from_mapping(reordered).rules_digest == PINNED_RULES_DIGEST
    assert PINNED_RULES_DIGEST in (REPO / "docs/PRIVATE_BETA_V0_RESTART_DECISION.md").read_text()
    assert PINNED_RULES_DIGEST in (REPO / "docs/research/BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md").read_text()


def test_schema_v1_digest_is_the_historical_identity_and_only_the_schema_moved_it():
    v1 = BetaConfig.load().with_overrides(state_schema_version=1)
    assert v1.rules_digest == PINNED_RULES_DIGEST_SCHEMA_V1
    raw_v1, raw_v2 = dict(v1.raw), dict(BetaConfig.load().raw)
    assert {k for k in raw_v2 if raw_v1[k] != raw_v2[k]} == {"state_schema_version"}
    for doc in ("docs/PRIVATE_BETA_V0_RESTART_DECISION.md",
                "docs/research/BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md"):
        text = (REPO / doc).read_text()
        assert PINNED_RULES_DIGEST_SCHEMA_V1 in text and PINNED_RULES_DIGEST in text


def test_unsupported_state_schema_version_is_rejected():
    with pytest.raises(BetaConfigError):
        BetaConfig.load().with_overrides(state_schema_version=3)


def test_regime_d7_does_not_enter_the_rules_digest():
    raw = _raw()
    assert raw["regime_d7"]["enabled"] is True
    c = BetaConfig.from_mapping(raw)
    assert c.rules_digest == PINNED_RULES_DIGEST
    raw["regime_d7"] = {"enabled": False}
    off = BetaConfig.from_mapping(raw)
    assert off.rules_digest == PINNED_RULES_DIGEST
    assert off["regime_d7"]["enabled"] is False
    assert off.config_digest != c.config_digest


def test_feedback_limits_do_not_enter_the_rules_digest():
    raw = _raw()
    assert raw["feedback"] == {"max_chars": 1000, "max_per_utc_day": 5}
    raw["feedback"] = {"max_chars": 20, "max_per_utc_day": 1}
    c = BetaConfig.from_mapping(raw)
    assert c.rules_digest == PINNED_RULES_DIGEST
    assert c["feedback"]["max_chars"] == 20
    assert c.config_digest != BetaConfig.load().config_digest


def test_access_and_telemetry_do_not_enter_the_rules_digest():
    raw = _raw()
    raw["access"] = {"max_active_users": 7}
    raw["telemetry"] = {"retention_days": 90, "rejected_start_retention_days": 14}
    c = BetaConfig.from_mapping(raw)
    assert c.rules_digest == PINNED_RULES_DIGEST
    assert c["access"]["max_active_users"] == 7
    assert c.config_digest != BetaConfig.load().config_digest


def test_horizon_changes_do_not_enter_the_rules_digest():
    raw = _raw()
    changed = dict(raw["horizon_changes"])
    changed["oi_abs_pct_min"] = 2.5
    raw["horizon_changes"] = changed
    c = BetaConfig.from_mapping(raw)
    assert c.rules_digest == PINNED_RULES_DIGEST
    assert c.config_digest != BetaConfig.load().config_digest


def test_threshold_change_changes_rules_digest_but_policy_change_does_not():
    raw = _raw()
    raw["rules"]["PRICE_OI_CONTRACTION_DOWN"]["price_move_pct_median_max"] = 0.06
    assert BetaConfig.from_mapping(raw).rules_digest != PINNED_RULES_DIGEST
    raw = _raw()
    raw["delivery_ttl_s"] = 900
    c = BetaConfig.from_mapping(raw)
    assert c.rules_digest == PINNED_RULES_DIGEST and c.config_digest != BetaConfig.load().config_digest


@pytest.mark.parametrize("mutate", [
    lambda r: r.pop("delivery_ttl_s"),
    lambda r: r.update(extra_key=1),
    lambda r: r.update(symbol="ETHUSDT"),
    lambda r: r.update(active_exchanges=["binance", "bitget"]),
    lambda r: r.update(min_venue_coverage=1),
    lambda r: r.update(percentile_window="7d"),
    lambda r: r.update(rules_version="BETA_EVENT_RULES_V2"),
    lambda r: r.update(forward_horizons=["15m", "2h"]),
    lambda r: r.update(push_enabled="yes"),
    lambda r: r["rules"]["PRICE_OI_CONTRACTION_DOWN"].update(price_move_pct_median_max=1.5),
    lambda r: r["rules"]["POSITION_BUILDUP_COMPRESSION"].update(armed_at_streak=2),
    lambda r: r["rules"]["LIQUIDATION_STRESS"].update(min_eligible_venues=1),
    lambda r: r["rules"]["TAKER_FLOW_EXTREME"].pop("enabled"),
    lambda r: r["bootstrap"].update(lookback_days=45),
])
def test_invalid_configs_fail_loudly(mutate):
    raw = _raw()
    mutate(raw)
    with pytest.raises(BetaConfigError):
        BetaConfig.from_mapping(raw)


def test_switches_are_config_and_env_and_push_needs_explicit_env():
    on = BetaConfig.load().with_overrides(enabled=True, push_enabled=True)
    s = resolve_switches(on, {})
    assert s.enabled and s.detection and s.outcome_tracking and not s.push_hard
    assert resolve_switches(on, {"BETA_PUSH_ENABLED": "1"}).push_hard
    assert not resolve_switches(on, {"BETA_PUSH_ENABLED": "1", "BETA_ENABLED": "0"}).push_hard
    assert not resolve_switches(on, {"BETA_DETECTION_ENABLED": "false"}).detection
    assert not resolve_switches(on, {"BETA_OUTCOME_TRACKING_ENABLED": "0"}).outcome_tracking
    with pytest.raises(BetaConfigError):
        resolve_switches(on, {"BETA_PUSH_ENABLED": "maybe"})


def test_committed_config_is_safe_by_default():
    raw = _raw()
    assert raw["enabled"] is False and raw["push_enabled"] is True
    s = resolve_switches(BetaConfig.load(), {})
    assert not (s.enabled or s.detection or s.push_hard or s.outcome_tracking)
    assert s.telegram
    # the committed push allow alone never pushes: BETA_PUSH_ENABLED must be explicitly true
    for env in ({"BETA_ENABLED": "1"}, {"BETA_ENABLED": "1", "BETA_PUSH_ENABLED": ""},
                {"BETA_ENABLED": "1", "BETA_PUSH_ENABLED": "0"}, {"BETA_PUSH_ENABLED": "1"}):
        assert resolve_switches(BetaConfig.load(), env).push_hard is False


def test_committed_push_allow_still_needs_env_and_admin_state():
    s = resolve_switches(BetaConfig.load(), {"BETA_ENABLED": "1", "BETA_PUSH_ENABLED": "true"})
    assert s.push_hard
    assert effective_push_enabled(s, True) is True
    assert effective_push_enabled(s, False) is False          # /admin_pause_push still wins
    off = resolve_switches(BetaConfig.load(), {"BETA_ENABLED": "0", "BETA_PUSH_ENABLED": "true"})
    assert not off.push_hard                                  # BETA_ENABLED=0 still wins


@pytest.mark.parametrize("env,expected", [
    ({}, False), ({"BETA_ENABLED": ""}, False), ({"BETA_ENABLED": "  "}, False),
    ({"BETA_ENABLED": "1"}, True), ({"BETA_ENABLED": "true"}, True), ({"BETA_ENABLED": "YES"}, True),
    ({"BETA_ENABLED": "0"}, False), ({"BETA_ENABLED": "false"}, False),
])
def test_beta_enabled_env_overrides_committed_disabled_config(env, expected):
    s = resolve_switches(BetaConfig.load(), env)
    assert s.enabled is expected and s.detection is expected and s.outcome_tracking is expected
    assert s.push_hard is False          # push needs an explicit BETA_PUSH_ENABLED as well


@pytest.mark.parametrize("env,expected", [
    ({}, True), ({"BETA_ENABLED": "1"}, True), ({"BETA_ENABLED": "0"}, False), ({"BETA_ENABLED": "no"}, False),
])
def test_beta_enabled_env_overrides_enabled_config(env, expected):
    assert resolve_switches(BetaConfig.load().with_overrides(enabled=True), env).enabled is expected


def test_env_enable_never_enables_push_or_unrestricts_kill_switches():
    off = BetaConfig.load()
    s = resolve_switches(off.with_overrides(push_enabled=False), {"BETA_ENABLED": "1", "BETA_PUSH_ENABLED": "1"})
    assert s.enabled and not s.push_hard  # a committed push_enabled: false can never be overridden
    s = resolve_switches(off, {"BETA_ENABLED": "1", "BETA_DETECTION_ENABLED": "0",
                               "BETA_OUTCOME_TRACKING_ENABLED": "0"})
    assert s.enabled and not s.detection and not s.outcome_tracking
    s = resolve_switches(off.with_overrides(detection_enabled=False), {"BETA_ENABLED": "1",
                                                                      "BETA_DETECTION_ENABLED": "1"})
    assert not s.detection               # config kill switch still wins
    with pytest.raises(BetaConfigError):
        resolve_switches(off, {"BETA_ENABLED": "maybe"})


def test_no_telegram_shadow_mode_is_explicit_and_consistent():
    off = BetaConfig.load()
    assert resolve_switches(off, {"BETA_ENABLED": "1"}).telegram            # default: Telegram on
    s = resolve_switches(off, {"BETA_ENABLED": "1", "BETA_TELEGRAM_ENABLED": "0"})
    assert s.enabled and s.detection and not s.telegram and not s.push_hard
    assert s.as_dict()["BETA_TELEGRAM_ENABLED"] is False
    with pytest.raises(BetaConfigError):     # a configured bot contradicts the mode
        resolve_switches(off, {"BETA_ENABLED": "1", "BETA_TELEGRAM_ENABLED": "0",
                               "BETA_TELEGRAM_BOT_TOKEN": "123:abc"})
    on_push = off.with_overrides(enabled=True, push_enabled=True)
    with pytest.raises(BetaConfigError):     # enabled push contradicts the mode
        resolve_switches(on_push, {"BETA_TELEGRAM_ENABLED": "0", "BETA_PUSH_ENABLED": "1"})
    assert not resolve_switches(on_push, {"BETA_TELEGRAM_ENABLED": "0"}).telegram


def test_admin_state_can_only_restrict_d7():
    cfg = BetaConfig.load()
    assert cfg["regime_d7"]["enabled"] is True
    assert effective_d7_enabled(cfg, False) is False
    assert effective_d7_enabled(cfg, True) is True
    hard_off = cfg.with_overrides(regime_d7={"enabled": False})
    assert effective_d7_enabled(hard_off, True) is False


def test_admin_state_can_only_restrict_push():
    on = BetaConfig.load().with_overrides(enabled=True, push_enabled=True)
    hard_off = resolve_switches(on, {})
    assert effective_push_enabled(hard_off, True) is False
    hard_on = resolve_switches(on, {"BETA_PUSH_ENABLED": "true"})
    assert effective_push_enabled(hard_on, True) is True
    assert effective_push_enabled(hard_on, False) is False


def test_secrets_from_env_only_and_never_repr_leaked():
    s = BetaSecrets.from_env({"BETA_TELEGRAM_BOT_TOKEN": "123:SECRET", "BETA_OWNER_TELEGRAM_USER_ID": "42"})
    assert s.owner_user_id == 42 and "SECRET" not in repr(s) and "42" not in repr(s)
    with pytest.raises(BetaConfigError):
        BetaSecrets.from_env({"BETA_OWNER_TELEGRAM_USER_ID": "abc"})


def test_event_types_cover_core_and_gated_without_level_sweep():
    assert "LEVEL_SWEEP" not in EVENT_TYPES and len(EVENT_TYPES) == 7
