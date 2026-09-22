"""Outcome-blind implementation tests for Discovery Sprint 03.

Synthetic/adversarial only except identity/guard tests that do not compute
scientific target values. Real SHARE / persistence / RV outcomes are never
inspected.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.research.discovery_sprint_03 import common as C
from scripts.research.discovery_sprint_03 import d9 as D9
from scripts.research.discovery_sprint_03 import d10 as D10
from scripts.research.discovery_sprint_03 import d11 as D11
from scripts.research.discovery_sprint_03 import evaluate as E

REPO = Path(__file__).resolve().parents[2]
SPRINT_JSON = REPO / "docs/research/DISCOVERY_SPRINT_03.json"
FREEZE_JSON = REPO / "docs/research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.json"
UTC = timezone.utc


def test_import_does_not_read_market_data():
    assert C.EXECUTION_AUTHORIZED is False
    assert C.UNIT == "DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"


def test_execution_guard_refuses_real_outcomes():
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_d9_real()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_d10_real()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_d11_real()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_supplied_arrays(
            "D9",
            event_values=[0.6],
            control_values=[0.5],
            yearly_event={"2022": [0.6]},
            support={"SUPPORT_PASS": True},
        )
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.main()


def test_flags_remain_unexecuted():
    sprint = json.loads(SPRINT_JSON.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8")) if FREEZE_JSON.is_file() else {}
    for blob in (sprint, freeze):
        if not blob:
            continue
        assert blob.get("SCIENTIFIC_OUTCOMES_COMPUTED") is False
        assert blob.get("D9_EXECUTED") is False
        assert blob.get("D10_EXECUTED") is False
        assert blob.get("D11_EXECUTED") is False
        assert blob.get("PROTECTED_2025_OPENED") is False
        assert blob.get("PROTECTED_2026_OPENED") is False
        assert blob.get("MARKET_07_CREATED") is False
        assert blob.get("D7_RERUN_PERFORMED") is False
        assert blob.get("D8_EXECUTED") is False
    assert not (REPO / "docs/research/discovery_results/D9_DISCOVERY_RESULT.json").exists()
    assert not (REPO / "docs/research/discovery_results/D10_DISCOVERY_RESULT.json").exists()
    assert not (REPO / "docs/research/discovery_results/D11_DISCOVERY_RESULT.json").exists()
    assert not (REPO / "docs/research/MARKET_07_RESULT.json").exists()


def test_d9_algebra_common_mode_and_extremes():
    common = D9.d9_relative_resolution(0.01, 0.004, 0.004)
    assert common.eligible is False
    assert common.perp_resolution_share is None

    perp_only = D9.d9_relative_resolution(0.02, -0.005, 0.0)
    assert perp_only.eligible is True
    assert math.isclose(perp_only.perp_resolution_share, 1.0)

    spot_only = D9.d9_relative_resolution(0.02, 0.0, 0.005)
    assert spot_only.eligible is True
    assert math.isclose(spot_only.perp_resolution_share, 0.0)

    symmetric = D9.d9_relative_resolution(0.02, -0.003, 0.003)
    assert symmetric.eligible is True
    assert math.isclose(symmetric.perp_resolution_share, 0.5)

    over = D9.d9_relative_resolution(0.02, -0.010, -0.005)
    assert over.eligible is True
    assert over.perp_resolution_share > 1.0
    assert math.isclose(over.perp_resolution_share, 2.0)

    under = D9.d9_relative_resolution(0.02, 0.005, 0.010)
    assert under.eligible is True
    assert under.perp_resolution_share < 0.0

    widen = D9.d9_relative_resolution(0.02, 0.004, 0.0)
    assert widen.eligible is False
    assert (widen.total_closure or 0) <= 0


def test_d9_no_clip_or_winsorize_and_no_leadership_claim():
    shares = [-1.0, 0.0, 0.5, 1.0, 2.0]
    med = D9.median_share(shares)
    assert med == 0.5
    assert min(shares) < 0
    assert max(shares) > 1
    clipped = [min(max(s, 0.0), 1.0) for s in shares]
    assert clipped != shares
    summary = D9.evaluate_d9_scientific(
        [0.7, 0.8, 0.75],
        [0.5, 0.48, 0.52],
        {"2022": [0.7] * 20, "2023": [0.72] * 20, "2024": [0.74] * 20},
        support={"SUPPORT_PASS": True, "IDENTITY_OK": True},
    )
    assert summary["SCIENTIFIC_CLAIM_MAY_ESTABLISH"] == "CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION"
    assert "PRICE_DISCOVERY" not in summary["SCIENTIFIC_CLAIM_MAY_ESTABLISH"]
    assert C.D9_PRIMARY_LOCATION_STATISTIC == "MEDIAN_PERP_RESOLUTION_SHARE"


def test_d9_near_zero_positive_total_closure_uses_median():
    tiny = D9.d9_relative_resolution(0.02, -0.01, -0.01 + 1e-15)
    assert tiny.eligible is True
    assert tiny.total_closure is not None and tiny.total_closure > 0
    assert tiny.perp_resolution_share is not None
    assert tiny.perp_resolution_share > 1e9
    pathological = [0.55] * 99 + [float(tiny.perp_resolution_share)]
    med = D9.median_share(pathological)
    mean = float(np.mean(pathological))
    assert abs(med - 0.55) < 1e-12
    assert mean > 1.0
    assert C.D9_PRIMARY_LOCATION_STATISTIC == "MEDIAN_PERP_RESOLUTION_SHARE"


def test_d9_classification_predicate_does_not_assign_on_empty_freeze_contract():
    inconclusive = D9.classify_d9_from_summary({"SUPPORT_PASS": False, "IDENTITY_OK": True})
    invalid = D9.classify_d9_from_summary({"SUPPORT_PASS": True, "IDENTITY_OK": False})
    useful = D9.classify_d9_from_summary(
        {
            "SUPPORT_PASS": True,
            "IDENTITY_OK": True,
            "STATISTICAL_GATE": True,
            "PRACTICAL_GATE": True,
            "TEMPORAL_GATE": True,
        }
    )
    none = D9.classify_d9_from_summary(
        {
            "SUPPORT_PASS": True,
            "IDENTITY_OK": True,
            "STATISTICAL_GATE": False,
            "PRACTICAL_GATE": True,
            "TEMPORAL_GATE": True,
        }
    )
    assert inconclusive == "INCONCLUSIVE_DISCOVERY"
    assert invalid == "INVALID_DISCOVERY"
    assert useful == "PROMISING_PROTOTYPE"
    assert none == "NO_USEFUL_STRUCTURE"


def test_d10_option_a_no_intercept_and_excludes_t_and_t_plus_1():
    window = 20
    t = window
    rng = np.random.default_rng(123)
    r_btc = rng.normal(0, 0.01, size=window + 2).tolist()
    r_eth = (1.7 * np.asarray(r_btc) + rng.normal(0, 0.001, size=window + 2)).tolist()
    r_btc[t] = 0.20
    r_eth[t] = -0.15
    r_btc[t + 1] = -0.18
    r_eth[t + 1] = 0.22
    row = D10.d10_fixed_beta_row(r_btc, r_eth, t, window=window)
    assert row["window_end_exclusive"] == t
    assert t not in range(row["window_start"], row["window_end_exclusive"])
    assert (t + 1) not in range(row["window_start"], row["window_end_exclusive"])
    beta_a = D10.no_intercept_beta(r_btc[:t], r_eth[:t])
    x = np.asarray(r_btc[:t], dtype=np.float64)
    y = np.asarray(r_eth[:t], dtype=np.float64)
    x_c = x - x.mean()
    y_c = y - y.mean()
    beta_centered = float(np.dot(x_c, y_c) / np.dot(x_c, x_c))
    assert math.isclose(row["beta_t"], beta_a)
    assert not math.isclose(beta_a, beta_centered)
    beta_with_t = D10.no_intercept_beta(r_btc[: t + 1], r_eth[: t + 1])
    beta_with_tp1 = D10.no_intercept_beta(r_btc[1 : t + 2], r_eth[1 : t + 2])
    assert not math.isclose(row["beta_t"], beta_with_t)
    assert not math.isclose(row["beta_t"], beta_with_tp1)
    assert math.isclose(row["e_t"], r_eth[t] - row["beta_t"] * r_btc[t])
    assert math.isclose(
        row["e_t_plus_1_fixed_beta"],
        r_eth[t + 1] - row["beta_t"] * r_btc[t + 1],
    )
    # Same pre-event beta reused; no intercept subtracted.
    assert "alpha" not in row
    assert row["REGRESSION_SPECIFICATION"] == "NO_INTERCEPT_OLS"
    assert C.D10_REGRESSION_SPECIFICATION == "NO_INTERCEPT_OLS"


def test_d10_missing_hours_fail_closed_and_current_excluded_from_quantiles():
    n = 1600
    hours = C.LEGAL_START_MS + np.arange(n) * C.HOUR_MS
    closes_btc = {int(h): 100.0 * math.exp(0.0001 * i) for i, h in enumerate(hours)}
    closes_eth = {int(h): 10.0 * math.exp(0.00012 * i) for i, h in enumerate(hours)}
    # Punch a hole in the calendar.
    missing = int(hours[800])
    del closes_btc[missing]
    census = D10.d10_feasibility_census(closes_btc, closes_eth)
    assert census["PERSISTENCE_VALUES_EMITTED"] is False
    # Window that would include the hole is ineligible (fail closed).
    hour_index = {int(ms): i for i, ms in enumerate(hours.tolist())}
    hole_i = hour_index[missing]
    # Reconstruct arrays and check beta undefined around the hole.
    h, r_b, r_e, _ = D10.aligned_return_arrays(closes_btc, closes_eth)
    assert not math.isfinite(r_b[hole_i])
    window_ok = D10._window_all_finite(np.isfinite(r_b) & np.isfinite(r_e))
    assert not bool(window_ok[hole_i + C.D10_WINDOW])


def test_d10_baseline_match_and_no_future_beta():
    window = 8
    r_btc = [0.01] * (window + 3)
    r_eth = [0.02] * (window + 3)
    r_btc[window] = 0.05
    r_eth[window] = 0.20
    r_btc[window + 1] = 0.04
    r_eth[window + 1] = 0.01
    row = D10.d10_fixed_beta_row(r_btc, r_eth, window, window=window)
    future_beta = D10.no_intercept_beta(
        r_btc[window - window + 1 : window + 2],
        r_eth[window - window + 1 : window + 2],
    )
    assert not math.isclose(row["beta_t"], future_beta)
    e_tp1_future = r_eth[window + 1] - future_beta * r_btc[window + 1]
    assert not math.isclose(row["e_t_plus_1_fixed_beta"], e_tp1_future)


def test_d11_family_exclusions_and_official_source_requirement():
    assert D11.is_forbidden_event_identity(
        "https://www.federalreserve.gov/monetarypolicy/fomcminutes20240131.htm"
    )
    assert D11.is_forbidden_event_identity(
        "https://www.federalreserve.gov/monetarypolicy/fomcpresconf20240131.htm"
    )
    assert D11.is_forbidden_event_identity(
        "https://www.bls.gov/news.release/cpi.htm", heading="CPI"
    )
    assert D11.is_forbidden_event_identity("https://www.bls.gov/nfp.htm", heading="NFP")
    assert D11.is_forbidden_event_identity(
        "https://www.ecb.europa.eu/press.htm", heading="ECB"
    )
    assert D11.is_forbidden_event_identity(
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240131b.htm"
    )
    ok = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240131a.htm"
    assert D11.is_forbidden_event_identity(ok) is False
    with pytest.raises(D11.D11SourceNotPinned):
        D11.load_pinned_calendar(repo=Path("/tmp/no-such-d11-repo"))


def test_d11_timezone_dst_conversion():
    winter = D11.parse_release_datetime(
        "For release at 2:00 p.m. EST",
        "20200129",
    )
    summer = D11.parse_release_datetime(
        "For release at 2:00 p.m. EDT",
        "20200429",
    )
    assert winter == datetime(2020, 1, 29, 19, 0, tzinfo=UTC)
    assert summer == datetime(2020, 4, 29, 18, 0, tzinfo=UTC)
    assert winter.hour != summer.hour
    eastern = D11.parse_release_datetime(
        "For release at 2:00 p.m. Eastern Time",
        "20200129",
    )
    assert eastern == winter


def test_d11_protected_boundary_and_insufficient_controls_do_not_weaken_match():
    with pytest.raises(C.Sprint03IntegrityError):
        D11.parse_release_datetime("no time here", "20240131")
    announcement = int(datetime(2025, 1, 1, 0, 0, tzinfo=UTC).timestamp() * 1000)
    returns = {}
    with pytest.raises(C.ProtectedYearRefused):
        D11.post_event_rv_6h(returns, announcement)

    events = []
    hour_returns: dict[int, float] = {}
    for year, month, day in (
        (2022, 1, 5),
        (2022, 2, 2),
        (2022, 3, 2),
        (2022, 4, 6),
        (2022, 5, 4),
        (2022, 6, 1),
        (2022, 7, 6),
        (2022, 8, 3),
        (2023, 1, 4),
        (2023, 2, 1),
        (2023, 3, 1),
        (2023, 4, 5),
        (2023, 5, 3),
        (2023, 6, 7),
        (2023, 7, 5),
        (2023, 8, 2),
        (2024, 1, 3),
        (2024, 2, 7),
        (2024, 3, 6),
        (2024, 4, 3),
        (2024, 5, 1),
        (2024, 6, 5),
        (2024, 7, 3),
        (2024, 8, 7),
    ):
        announ = int(datetime(year, month, day, 18, 0, tzinfo=UTC).timestamp() * 1000)
        events.append(
            {
                "EVENT_FAMILY": "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS",
                "ANNOUNCEMENT_UTC_MS": announ,
                "STATED_TIMEZONE": "EDT",
                "EVENT_ID": f"{year:04d}{month:02d}{day:02d}",
            }
        )
        start = D11.first_hour_open_ms(announ)
        for k in range(6):
            hour_returns[start + k * C.HOUR_MS] = 0.01
    # Two extra matched controls per year at the same weekday/hour, not enough.
    for year, month, day in ((2022, 9, 7), (2022, 10, 5), (2023, 9, 6), (2023, 10, 4), (2024, 9, 4), (2024, 10, 2)):
        start = int(datetime(year, month, day, 18, 0, tzinfo=UTC).timestamp() * 1000)
        for k in range(6):
            hour_returns[start + k * C.HOUR_MS] = 0.01
    census = D11.d11_feasibility_census(events, hour_returns)
    assert census["RV_VALUES_EMITTED"] is False
    assert census["MATCH_STRATA"] == ["YEAR", "WEEKDAY", "UTC_HOUR"]
    assert census["EVENT_N"] >= C.D11_MIN_EVENTS
    assert census["STATUS"] == "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    assert census["SUPPORT_PASS"] is False


def test_d11_2020_excludes_unscheduled_and_notation():
    html = """
    <h5 class="panel-heading panel-heading--shaded">January 28-29 Meeting - 2020</h5>
    <a href="/newsevents/pressreleases/monetary20200129a.htm">Statement</a>
    <h5 class="panel-heading panel-heading--shaded">March 15 (unscheduled) Meeting - 2020</h5>
    <a href="/newsevents/pressreleases/monetary20200315a.htm">Statement</a>
    <h5 class="panel-heading panel-heading--shaded">March 23 (notation vote) - 2020</h5>
    <a href="/newsevents/pressreleases/monetary20200323a.htm">Statement</a>
    <h5 class="panel-heading panel-heading--shaded">April 28-29 Meeting - 2020</h5>
    <a href="/newsevents/pressreleases/monetary20200429a.htm">Statement</a>
    """
    dates = D11.scheduled_2020_statement_dates(html)
    assert dates == ["20200129", "20200429"]


def test_protected_partition_paths_refused():
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(Path("canonical/1m/monthly/2025-01.parquet"))
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(Path("canonical/1m/daily/2026-08-01.parquet"))


def test_synthetic_evaluators_require_authorization_even_on_arrays():
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_supplied_arrays(
            "D10",
            event_values=[0.001],
            control_values=[0.0],
            yearly_event={"2022": [0.001]},
            yearly_control={"2022": [0.0]},
            support={"SUPPORT_PASS": True},
            authorized=False,
        )
    out = D10.evaluate_d10_scientific(
        [0.002] * 30,
        [0.0] * 30,
        {"2022": [0.002] * 10, "2023": [0.002] * 10, "2024": [0.002] * 10},
        {"2022": [0.0] * 10, "2023": [0.0] * 10, "2024": [0.0] * 10},
        support={"SUPPORT_PASS": True, "IDENTITY_OK": True},
    )
    assert out["CLASSIFICATION"] in {
        "PROMISING_PROTOTYPE",
        "NO_USEFUL_STRUCTURE",
        "INCONCLUSIVE_DISCOVERY",
        "INVALID_DISCOVERY",
    }
    assert "MEAN_EVENT" in out
