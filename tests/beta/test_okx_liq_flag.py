"""Decision (d), 2026-10-09 (docs/BETA_OKX_LATE_ARRIVAL_IMPACT.md): OKX liquidation events reach the
collector up to hours late, so `liquidations.okx_enabled: false` keeps OKX liquidations out of the beta.
Even with 30+ days of mature OKX percentiles, OKX is never shown and never votes. There is no automatic
enable. Binance and Bybit are unchanged. OKX price, OI and funding are untouched."""
import copy
from datetime import datetime, timezone

import pytest

from test_beta_btc_view import CFG, snap
from test_beta_rules_and_state_machine import snap as rsnap
from test_beta_multi_horizon_ux import _series, screens

from beta.config import BetaConfig, BetaConfigError
from beta.formatter import format_1h_tab, format_event_tab
from beta.horizons import build_horizons
from beta.liq_mapping import okx_liq_shown, without_okx_liq
from beta.readiness import family_readiness
from beta.rules import evaluate_bucket

AS_OF = datetime(2026, 10, 14, 11, 0, tzinfo=timezone.utc)
MATURE = {"value": 9e9, "rank": 0.999, "tier": "mature", "sample_size": 8640}       # 30 days of 5m buckets
HI = {"value": 5e6, "rank": 0.99, "tier": "mature", "sample_size": 8640}
OKX_KEYS = ("x:okx:long_liquidation_notional", "x:okx:short_liquidation_notional")
ENABLED = CFG.with_overrides(liquidations={"okx_enabled": True})


def test_the_shipped_config_has_okx_liquidations_off():
    assert BetaConfig.load().okx_liquidations_enabled is False
    assert CFG.okx_liquidations_enabled is False and ENABLED.okx_liquidations_enabled is True


@pytest.mark.parametrize("bad", ["false", 0, 1, None, "no"])
def test_the_flag_must_be_a_bool(bad):
    with pytest.raises(BetaConfigError, match="liquidations.okx_enabled must be a bool"):
        CFG.with_overrides(liquidations={"okx_enabled": bad})


def test_the_section_is_required_and_exact():
    with pytest.raises(BetaConfigError):
        CFG.with_overrides(liquidations={})
    with pytest.raises(BetaConfigError):
        CFG.with_overrides(liquidations={"okx_enabled": False, "bybit_enabled": True})


def test_the_flag_stays_out_of_the_rules_digest():
    """With the flag off the rule decides exactly as before (OKX was not yet mature): episode identity holds."""
    assert ENABLED.rules_digest == CFG.rules_digest


def test_mature_okx_never_votes_while_the_flag_is_off():
    calm = {**HI, "rank": 0.5}
    s = rsnap(liq={("binance", "long"): HI, ("bybit", "long"): calm, ("binance", "short"): calm,
                  ("bybit", "short"): calm, ("okx", "long"): MATURE, ("okx", "short"): MATURE})
    ev = evaluate_bucket(CFG, s, None)
    for et in ("LIQUIDATION_STRESS_LONG", "LIQUIDATION_STRESS_SHORT"):
        d = ev[et]["detail"]
        assert "okx" not in d["eligible"] and "okx" not in d["voting"]
        assert d["ineligible"]["okx"] == "OKX_LIQUIDATIONS_EXCLUDED"
    assert ev["LIQUIDATION_STRESS_LONG"]["status"] == "NOT_QUALIFIES"          # Binance alone is not 2 votes
    # the same snapshot with the flag on: mature OKX would vote and qualify (so the flag is what stops it)
    assert evaluate_bucket(ENABLED, s, None)["LIQUIDATION_STRESS_LONG"]["status"] == "QUALIFIES"
    # readiness never counts an excluded OKX as a venue on its way to readiness
    r = family_readiness(CFG, "LIQUIDATION_STRESS_LONG", {**s, "rule_evaluations": ev}, AS_OF, 30.0)
    from beta.readiness import UNAVAILABLE
    assert r["venues"]["okx"]["state"] == UNAVAILABLE and r["venues"]["okx"]["reason"] == "OKX_LIQUIDATIONS_EXCLUDED"


def test_binance_and_bybit_decide_exactly_as_before():
    for liq in ({("binance", "long"): HI, ("bybit", "long"): HI},
                {("binance", "long"): HI},
                {("binance", "long"): HI, ("bybit", "long"): {**HI, "rank": 0.5}}):
        off = evaluate_bucket(CFG, rsnap(liq={**liq, ("okx", "long"): MATURE}), None)
        on = evaluate_bucket(ENABLED, rsnap(liq=liq), None)                  # without any OKX value
        for et in ("LIQUIDATION_STRESS_LONG", "LIQUIDATION_STRESS_SHORT"):
            assert off[et]["status"] == on[et]["status"]
            assert off[et]["detail"]["voting"] == on[et]["detail"]["voting"]
            assert off[et]["detail"]["eligible"] == [e for e in on[et]["detail"]["eligible"] if e != "okx"]


def test_mature_okx_amounts_are_never_shown_while_the_flag_is_off():
    mature = {k: {"tier": "mature"} for k in OKX_KEYS}
    assert okx_liq_shown(mature, enabled=False) is False
    assert okx_liq_shown(mature, enabled=True) is True
    # the market view blanks OKX before the horizons are built: «OKX н/д», never an amount
    series = {b: {**m, **{k: 7.7e6 for k in OKX_KEYS}} for b, m in _series(AS_OF, days=31, vol=1e6).items()}
    shown = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket={b: without_okx_liq(m) for b, m in series.items()})
    plain = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=_series(AS_OF, days=31, vol=1e6))
    for h in ("1h", "24h"):
        v = shown[h]["liquidations"]["venues"]
        assert v["okx"]["long"]["missing"] is True and v["okx"]["long"]["amount"] is None
        for ex in ("binance", "bybit"):                                     # Binance and Bybit unchanged
            assert v[ex] == plain[h]["liquidations"]["venues"][ex]
    for lang, nd in (("ru", "OKX н/д"), ("en", "OKX n/a")):
        text = format_1h_tab(CFG, {"horizons": shown, "active_episode": None, "last_event": None}, lang, "abcd1234")
        liq = [ln for ln in text.splitlines() if ln.startswith(("Ликвидации ", "Long liquidations", "Short liquidations"))]
        assert liq and all(nd in ln for ln in liq) and "7,7" not in text and "7.7" not in text


def test_an_event_view_never_shows_okx_unless_it_voted():
    """Anchor views print OKX only where it was eligible; with the flag off it never is."""
    view = copy.deepcopy(screens()["unusual"])
    for side in ("long", "short"):
        view["active_episode"]["anchor"]["view"]["liquidations"][side]["per_venue"]["okx"] = 7.7e6
    for lang, nd in (("ru", "OKX н/д"), ("en", "OKX n/a")):
        text = format_event_tab(CFG, view, lang, "abcd1234")
        assert nd in text and "7,7" not in text and "7.7" not in text


def test_okx_price_oi_and_funding_are_untouched():
    """Scope is OKX liquidations only (owner, 2026-10-09)."""
    h = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=_series(AS_OF, days=31, vol=1e6),
                       oi_by_boundary=None)
    assert "okx" in CFG.exchanges and "okx" in CFG.raw["active_exchanges"]
    for h_name in ("1h", "24h"):
        assert "okx" in h[h_name]["funding_by_venue"] or h[h_name]["funding_venues_of"] == len(CFG.exchanges)
    assert h["1h"]["funding_venues_of"] == 3
    # the snapshot's OKX kline OHLC (price, range) still enters every horizon and the 1h tab names OKX OI
    s = snap(liq={})
    off, on = evaluate_bucket(CFG, s, None), evaluate_bucket(ENABLED, s, None)
    assert {k: v for k, v in off.items() if not k.startswith("LIQUIDATION")} == \
        {k: v for k, v in on.items() if not k.startswith("LIQUIDATION")}       # non-liquidation rules identical
    text = format_1h_tab(CFG, {"horizons": screens()["unusual"]["horizons"], "active_episode": None,
                               "last_event": None}, "en", "abcd1234")
    assert "OKX +0.1%" in text or "OKX" in text.split("OI")[1].splitlines()[0]
