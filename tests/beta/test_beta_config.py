"""Beta V0.2 config: strict validation, digest stability, hard switches, secrets."""
import copy
from pathlib import Path

import pytest
import yaml

from beta.config import (BetaConfig, BetaConfigError, BetaSecrets, EVENT_TYPES,
                         effective_push_enabled, resolve_switches)

PINNED_RULES_DIGEST = "2e0afa4785675e7a3777627f45647f76268a7cdad3e0639c078ee5ccc7605f44"
REPO = Path(__file__).resolve().parents[2]


def _raw():
    return copy.deepcopy(yaml.safe_load((REPO / "config/beta_v0.yaml").read_text())["beta"])


def test_committed_config_loads_with_contract_minimum_keys():
    c = BetaConfig.load()
    assert c["enabled"] is False and c["push_enabled"] is False and c["outcome_tracking_enabled"] is True
    assert c.rules_version == "BETA_EVENT_RULES_V1" and c.state_schema_version == 1
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
    off = BetaConfig.load()     # committed: enabled false -> env can never enable
    s = resolve_switches(off, {"BETA_ENABLED": "1", "BETA_PUSH_ENABLED": "1"})
    assert not (s.enabled or s.detection or s.push_hard or s.outcome_tracking)
    with pytest.raises(BetaConfigError):
        resolve_switches(on, {"BETA_PUSH_ENABLED": "maybe"})


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
