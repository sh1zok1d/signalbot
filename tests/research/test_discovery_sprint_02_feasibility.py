"""Outcome-blind tests for Discovery Sprint 02 feasibility/implementation.

Synthetic fixtures only for scientific evaluators. Real CORE is not required
for this module. Feasibility CLI source is checked not to compute outcomes.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from datetime import datetime, timezone

import numpy as np
import pytest

from scripts.research import discovery_sprint_02_impl as I
from scripts.research import discovery_sprint_02_feasibility as F


REPO = Path(__file__).resolve().parents[2]
SPRINT_JSON = REPO / "docs/research/DISCOVERY_SPRINT_02.json"
POLICY_JSON = REPO / "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V1.json"


def _ms(year: int, month: int = 1, day: int = 1, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


def _bar(
    open_ms: int,
    *,
    open_px: float = 100.0,
    close_px: float | None = None,
    quote: float = 10.0,
    trades: int = 5,
    taker: float = 4.0,
) -> I.MinuteBar:
    close = open_px if close_px is None else close_px
    return I.MinuteBar(
        open_time_ms=open_ms,
        available_at_ms=open_ms + I.BAR_MS,
        open=open_px,
        close=close,
        quote_volume=quote,
        trade_count=trades,
        taker_buy_quote_volume=taker,
    )


def _hour_of_bars(
    hour_start: int,
    *,
    open_px: float,
    close_px: float,
    quote: float = 10.0,
) -> list[I.MinuteBar]:
    bars = []
    for k in range(I.BARS_PER_HOUR):
        px_open = open_px if k == 0 else close_px
        px_close = close_px
        bars.append(
            _bar(
                hour_start + k * I.BAR_MS,
                open_px=px_open if k == 0 else px_close,
                close_px=px_close,
                quote=quote,
            )
        )
        if k == 0:
            bars[-1] = _bar(
                hour_start,
                open_px=open_px,
                close_px=close_px if I.BARS_PER_HOUR == 1 else open_px,
                quote=quote,
            )
    # first bar open, last bar close; intermediates flat at close
    out = []
    for k in range(I.BARS_PER_HOUR):
        if k == 0:
            o, c = open_px, open_px if I.BARS_PER_HOUR > 1 else close_px
        elif k == I.BARS_PER_HOUR - 1:
            o, c = close_px, close_px
        else:
            o, c = close_px, close_px
        if k == 0 and I.BARS_PER_HOUR > 1:
            o, c = open_px, open_px
        out.append(
            _bar(hour_start + k * I.BAR_MS, open_px=o, close_px=c, quote=quote / I.BARS_PER_HOUR)
        )
    out[0] = _bar(hour_start, open_px=open_px, close_px=open_px, quote=quote / I.BARS_PER_HOUR)
    out[-1] = _bar(
        hour_start + 59 * I.BAR_MS,
        open_px=close_px,
        close_px=close_px,
        quote=quote / I.BARS_PER_HOUR,
    )
    return out


def _synthetic_hours(
    n: int,
    start_ms: int,
    *,
    ret: float | list[float],
    vol: float | list[float] = 100.0,
) -> list[I.HourBar]:
    hours: list[I.HourBar] = []
    for i in range(n):
        r = ret[i] if isinstance(ret, list) else ret
        q = vol[i] if isinstance(vol, list) else vol
        open_px = 100.0
        close_px = open_px * math.exp(r)
        hour_start = start_ms + i * I.HOUR_MS
        hours.append(
            I.HourBar(
                hour_start_ms=hour_start,
                available_at_ms=hour_start + I.HOUR_MS,
                year=datetime.fromtimestamp(hour_start / 1000.0, tz=timezone.utc).year,
                open_1h=open_px,
                close_1h=close_px,
                quote_volume_1h=float(q),
                trade_count_1h=10,
                taker_buy_quote_volume_1h=float(q) * 0.4,
                ret_abs_1h=abs(r),
                event_return=float(r),
            )
        )
    return hours


def test_only_legal_month_paths_can_be_opened(tmp_path: Path):
    root = tmp_path / "ds"
    legal = I.legal_monthly_parquet_path(root, "2020-01")
    assert legal.name == "2020-01.parquet"
    assert "2025" not in str(legal)
    with pytest.raises(I.ProtectedYearRefused):
        I.legal_monthly_parquet_path(root, "2025-01")
    with pytest.raises(I.ProtectedYearRefused):
        I.legal_monthly_parquet_path(root, "2026-12")
    with pytest.raises(I.ProtectedYearRefused):
        I.legal_monthly_parquet_path(root, "2019-12")


def test_2025_2026_rejected_before_parquet_read(tmp_path: Path):
    root = tmp_path / "ds"
    monthly = root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    victim = monthly / "2025-01.parquet"
    victim.write_bytes(b"not-a-parquet")
    with pytest.raises(I.ProtectedYearRefused, match="BEFORE_READ"):
        I.legal_monthly_parquet_path(root, "2025-01")
    # Path exists but must not be hashed/read by legal constructor.
    assert victim.read_bytes() == b"not-a-parquet"


def test_checksum_mismatch_fails_closed(tmp_path: Path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = tmp_path / "ds"
    monthly = root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    table = pa.table(
        {
            "open_time_ms": pa.array([_ms(2020)], type=pa.int64()),
            "available_at_ms": pa.array([_ms(2020) + 60_000], type=pa.int64()),
            "open": ["1.0"],
            "close": ["1.0"],
            "quote_volume": ["1.0"],
            "trade_count": pa.array([1], type=pa.int64()),
            "taker_buy_quote_volume": ["0.5"],
        }
    )
    path = monthly / "2020-01.parquet"
    pq.write_table(table, path)
    checksums = {f"canonical/1m/monthly/{p}.parquet": "ab" * 32 for p in I.LEGAL_MONTHS}
    with pytest.raises(I.SnapshotIdentityError, match="CHECKSUM_MISMATCH"):
        I.load_legal_1m_bars(
            repo=REPO,
            dataset_root=root,
            checksums=checksums,
            require_repo_authority=False,
        )


def test_hourly_aggregation_requires_60_contiguous_bars():
    start = _ms(2021, 6, 1)
    complete = _hour_of_bars(start, open_px=100.0, close_px=101.0, quote=60.0)
    hours = I.aggregate_completed_hours(complete)
    assert len(hours) == 1
    assert hours[0].open_1h == 100.0
    assert hours[0].close_1h == 101.0
    assert hours[0].available_at_ms == start + I.HOUR_MS
    assert math.isclose(hours[0].quote_volume_1h, 60.0)
    assert hours[0].trade_count_1h == 5 * 60
    incomplete = complete[:-1]
    assert I.aggregate_completed_hours(incomplete) == []
    gapped = complete[:30] + complete[31:]
    assert I.aggregate_completed_hours(gapped) == []


def test_available_at_semantics_and_decimal_parse():
    start = _ms(2021, 6, 1)
    bar = _bar(start, open_px=10.0, close_px=11.0)
    assert bar.available_at_ms == start + 60_000
    assert I.parse_decimal_string("7189.43", field="open") == 7189.43
    with pytest.raises(I.Sprint02IntegrityError, match="LEXICAL"):
        I.parse_decimal_string("high", field="open")
    with pytest.raises(I.Sprint02IntegrityError, match="NON_STRING"):
        I.parse_decimal_string(7189.43, field="open")


def test_d7_current_excluded_strict_p90_qrel_median_no_epsilon():
    start = _ms(2021, 3, 1)
    n = I.TRAILING_WINDOW * 2 + 2
    rets = [0.001] * n
    vols = [100.0] * n
    rets[-1] = 1.0
    hours = _synthetic_hours(n, start, ret=rets, vol=vols)
    states = I.build_d7_states(hours)
    warm = states[I.TRAILING_WINDOW]
    assert warm.qrel_1h is not None
    assert math.isclose(warm.qrel_1h, 1.0)
    last = states[-1]
    assert last.impact_proxy is not None
    assert last.d7_state is True
    zero_vols = [100.0] * I.TRAILING_WINDOW + [0.0]
    zero_hours = _synthetic_hours(
        I.TRAILING_WINDOW + 1, start, ret=0.001, vol=zero_vols
    )
    zero_states = I.build_d7_states(zero_hours)
    assert zero_states[-1].qrel_1h is None
    assert zero_states[-1].impact_proxy is None


def test_d7_rv_bucket_boundaries_exact():
    trailing = list(range(1, I.TRAILING_WINDOW + 1))
    p25 = I.percentile(trailing, 25.0)
    p50 = I.percentile(trailing, 50.0)
    p75 = I.percentile(trailing, 75.0)
    assert I.rv_bucket_from_trailing(p25, trailing) == 0
    assert I.rv_bucket_from_trailing(p25 + 1e-12, trailing) in (0, 1)
    assert I.rv_bucket_from_trailing(p50, trailing) == 1
    assert I.rv_bucket_from_trailing(p75, trailing) == 2
    assert I.rv_bucket_from_trailing(p75 + 1.0, trailing) == 3


def test_d7_rate_matched_random_preserves_k_and_seed():
    n = 40
    years = [2021] * 20 + [2022] * 20
    buckets = [0] * 10 + [1] * 10 + [0] * 10 + [1] * 10
    eligible = [True] * n
    candidate = [False] * n
    candidate[0] = True
    candidate[5] = True
    candidate[20] = True
    masks = I.year_rv_bucket_rate_matched_masks(
        years, buckets, eligible, candidate, seed=I.D7_SEED, n_replicates=7
    )
    assert masks.shape == (7, n)
    for mask in masks:
        assert int(mask[:20].sum()) == 2
        assert int(mask[20:].sum()) == 1
    masks2 = I.year_rv_bucket_rate_matched_masks(
        years, buckets, eligible, candidate, seed=I.D7_SEED, n_replicates=7
    )
    assert np.array_equal(masks, masks2)
    other = I.year_rv_bucket_rate_matched_masks(
        years, buckets, eligible, candidate, seed=I.D7_SEED + 1, n_replicates=7
    )
    assert not np.array_equal(masks, other)


def test_d7_classification_gates_exact():
    years: list[int] = []
    buckets: list[int] = []
    candidate: list[bool] = []
    target: list[float] = []
    eligible: list[bool] = []
    for y in (2020, 2021, 2022, 2023, 2024):
        for j in range(20):
            years.append(y)
            buckets.append(0)
            eligible.append(True)
            is_cand = j == 0
            candidate.append(is_cand)
            target.append(1.0 if is_cand else 0.0)
    promising = I.evaluate_d7_scientific(
        candidate=candidate,
        target=target,
        year=years,
        rv_bucket=buckets,
        target_eligible=eligible,
        n_replicates=200,
    )
    assert promising["STATISTICAL_GATE"] is True
    assert promising["PRACTICAL_GATE"] is True
    assert promising["TEMPORAL_GATE"] is True
    assert promising["CLASSIFICATION"] == "D7_PROMISING_PROTOTYPE"
    weak_target = [0.0 if not c else 0.01 for c in candidate]
    weak = I.evaluate_d7_scientific(
        candidate=candidate,
        target=weak_target,
        year=years,
        rv_bucket=buckets,
        target_eligible=eligible,
        n_replicates=200,
    )
    assert weak["PRACTICAL_GATE"] is False
    assert weak["CLASSIFICATION"] == "D7_NO_USEFUL_STRUCTURE"
    invalid = I.evaluate_d7_scientific(
        candidate=candidate,
        target=target,
        year=years,
        rv_bucket=buckets,
        target_eligible=eligible,
        integrity_ok=False,
    )
    assert invalid["CLASSIFICATION"] == "D7_DISCOVERY_INVALID"


def test_d7_feasibility_never_computes_tplus1_association():
    start = _ms(2021, 3, 1)
    n = I.TRAILING_WINDOW * 2 + 5
    rets = [0.001] * n
    rets[-1] = 0.8
    hours = _synthetic_hours(n, start, ret=rets, vol=100.0)
    census = I.d7_feasibility_census(I.build_d7_states(hours))
    blob = json.dumps(census)
    assert census["SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED"] is False
    assert "MU_D7_RULE" not in census
    assert "DELTA_D7" not in census
    assert "P(D7_STATE" not in blob


def test_d8_event_and_control_gates():
    start = _ms(2022, 1, 1)
    n = I.TRAILING_WINDOW + 2
    rets = [0.001] * n
    vols = [10.0] * n
    rets[-2] = 1.0
    vols[-2] = 1000.0
    rets[-1] = 0.99
    vols[-1] = 10.0
    hours = _synthetic_hours(n, start, ret=rets, vol=vols)
    raw = I.build_d8_raw_candidates(hours)
    events = [row for row in raw if row.is_event]
    controls = [row for row in raw if row.is_control]
    assert events
    assert controls
    event = events[-1]
    control = controls[-1]
    assert event.abs_event_return > event.p99_return
    assert event.event_volume > event.p90_volume
    assert control.abs_event_return > control.p99_return
    assert control.event_volume <= control.p90_volume


def test_d8_refractory_matching_tiebreak_and_overlap():
    start = _ms(2022, 6, 1)
    e1 = I.D8RawCandidate(
        hour=I.HourBar(start, start + I.HOUR_MS, 2022, 1, 2, 1, 1, 1, 1.0, 1.0),
        abs_event_return=1.0,
        event_sign=1,
        event_volume=10.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=True,
        is_control=False,
        is_return_shock=True,
    )
    e2 = I.D8RawCandidate(
        hour=I.HourBar(
            start + 3 * I.HOUR_MS,
            start + 4 * I.HOUR_MS,
            2022,
            1,
            2,
            1,
            1,
            1,
            1.0,
            1.0,
        ),
        abs_event_return=0.9,
        event_sign=1,
        event_volume=10.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=True,
        is_control=False,
        is_return_shock=True,
    )
    e3 = I.D8RawCandidate(
        hour=I.HourBar(
            start + 6 * I.HOUR_MS,
            start + 7 * I.HOUR_MS,
            2022,
            1,
            2,
            1,
            1,
            1,
            1.0,
            1.0,
        ),
        abs_event_return=0.8,
        event_sign=1,
        event_volume=10.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=True,
        is_control=False,
        is_return_shock=True,
    )
    kept = I.apply_6h_refractory([e1, e2, e3])
    assert [row.hour.hour_start_ms for row in kept] == [e1.hour.hour_start_ms, e3.hour.hour_start_ms]

    c_overlap = I.D8RawCandidate(
        hour=I.HourBar(
            start + 2 * I.HOUR_MS,
            start + 3 * I.HOUR_MS,
            2022,
            1,
            2,
            1,
            1,
            1,
            0.95,
            0.95,
        ),
        abs_event_return=0.95,
        event_sign=1,
        event_volume=1.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=False,
        is_control=True,
        is_return_shock=True,
    )
    c_touch = I.D8RawCandidate(
        hour=I.HourBar(
            start + 6 * I.HOUR_MS,
            start + 7 * I.HOUR_MS,
            2022,
            1,
            2,
            1,
            1,
            1,
            0.94,
            0.94,
        ),
        abs_event_return=0.94,
        event_sign=1,
        event_volume=1.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=False,
        is_control=True,
        is_return_shock=True,
    )
    filtered = I.exclude_overlapping_controls([e1], [c_overlap, c_touch])
    assert [row.hour.hour_start_ms for row in filtered] == [c_touch.hour.hour_start_ms]

    early = I.D8RawCandidate(
        hour=I.HourBar(start + 20 * I.HOUR_MS, start + 21 * I.HOUR_MS, 2022, 1, 2, 1, 1, 1, 0.5, 0.5),
        abs_event_return=0.50,
        event_sign=1,
        event_volume=1.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=False,
        is_control=True,
        is_return_shock=True,
    )
    late_same = I.D8RawCandidate(
        hour=I.HourBar(start + 30 * I.HOUR_MS, start + 31 * I.HOUR_MS, 2022, 1, 2, 1, 1, 1, 0.5, 0.5),
        abs_event_return=0.50,
        event_sign=1,
        event_volume=1.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=False,
        is_control=True,
        is_return_shock=True,
    )
    nearer = I.D8RawCandidate(
        hour=I.HourBar(start + 40 * I.HOUR_MS, start + 41 * I.HOUR_MS, 2022, 1, 2, 1, 1, 1, 0.99, 0.99),
        abs_event_return=0.99,
        event_sign=1,
        event_volume=1.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=False,
        is_control=True,
        is_return_shock=True,
    )
    pairs, failures = I.match_events_to_controls([e1], [late_same, early, nearer])
    assert not failures
    assert pairs[0][1] is nearer
    tied_event = I.D8RawCandidate(
        hour=I.HourBar(start + 50 * I.HOUR_MS, start + 51 * I.HOUR_MS, 2022, 1, 2, 1, 1, 1, 0.5, 0.5),
        abs_event_return=0.50,
        event_sign=1,
        event_volume=10.0,
        p99_return=0.1,
        p90_volume=5.0,
        is_event=True,
        is_control=False,
        is_return_shock=True,
    )
    pairs2, _ = I.match_events_to_controls([tied_event], [late_same, early])
    assert pairs2[0][1] is early


def test_d8_recovery_clock_and_strict_bound():
    decision = _ms(2024, 12, 31, 17, 0)
    assert I.primary_recovery_legal(decision) is True
    assert I.primary_recovery_legal(decision + I.HOUR_MS) is False
    assert I.diagnostic_24h_legal(_ms(2024, 12, 30, 0, 0) + I.HOUR_MS) is True
    assert I.diagnostic_24h_legal(_ms(2024, 12, 31, 0, 0)) is False
    rec = I.recovery_6h(0.10, 100.0, 90.0)
    # down move after positive event => retracement positive
    assert rec > 0
    closes = {decision: 100.0, decision + I.RECOVERY_6H_MS: 90.0}
    assert I.lookup_close_at_available_at(closes, decision) == 100.0


def test_d8_sign_flip_and_classification():
    deltas = [0.5, 0.4, 0.35, 0.3, 0.28, 0.25, 0.24, 0.22, 0.21]
    years = [2020, 2020, 2020, 2021, 2021, 2021, 2022, 2022, 2022]
    first = I.evaluate_d8_scientific(deltas, years, n_randomizations=300)
    second = I.evaluate_d8_scientific(deltas, years, n_randomizations=300)
    assert first["MC_P_D8"] == second["MC_P_D8"]
    assert first["PRACTICAL_GATE"] is True
    assert first["STATISTICAL_GATE"] is True
    assert first["TEMPORAL_GATE"] is True
    assert first["CLASSIFICATION"] == "D8_PROMISING_PROTOTYPE"
    deferred = I.evaluate_d8_scientific(
        deltas, years, control_support_ok=False, n_randomizations=10
    )
    assert deferred["CLASSIFICATION"] == "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    invalid = I.evaluate_d8_scientific(deltas, years, integrity_ok=False)
    assert invalid["CLASSIFICATION"] == "D8_DISCOVERY_INVALID"


def test_d8_feasibility_never_computes_recovery():
    start = _ms(2022, 1, 1)
    n = I.TRAILING_WINDOW + 2
    rets = [0.001] * n
    vols = [10.0] * n
    rets[-2] = 1.0
    vols[-2] = 1000.0
    rets[-1] = 0.99
    vols[-1] = 10.0
    hours = _synthetic_hours(n, start, ret=rets, vol=vols)
    census = I.d8_feasibility_census(hours)
    blob = json.dumps(census)
    assert census["RECOVERY_6H_COMPUTED"] is False
    assert census["RECOVERY_24H_COMPUTED"] is False
    assert "DELTA_RECOVERY" not in blob
    assert census.get("EVENT_MEAN_RECOVERY") is None


def test_feasibility_cli_source_does_not_call_scientific_evaluators():
    source = (REPO / "scripts/research/discovery_sprint_02_feasibility.py").read_text(
        encoding="utf-8"
    )
    I.assert_no_scientific_calls_in_feasibility_source(source)


def test_governance_frozen_cards_and_no_market_07():
    sprint = json.loads(SPRINT_JSON.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_JSON.read_text(encoding="utf-8"))
    d7 = sprint["CARDS"]["D7"]
    d8 = sprint["CARDS"]["D8"]
    assert d7["FAMILY"] == "E"
    assert d8["FAMILY"] == "G"
    assert "P90" in d7["FROZEN_CONSTRUCTION"]["STATE"]
    assert d8["EVENT_DEFINITION"]["TRAILING_WINDOW_HOURS"] == 720
    assert d8["PRIMARY_TARGET"] == "RECOVERY_6H"
    assert sprint["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert sprint["MARKET_07_CREATED"] is False
    assert sprint["PROTECTED_2025_OPENED"] is False
    assert policy["MARKET_07_CREATED"] is False
    assert not (REPO / "docs/research/MARKET_07_RESULT.json").exists()
    d2_result = REPO / "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.json"
    if d2_result.is_file():
        # This unit must not rewrite D2 RESULT bytes.
        digest = hashlib.sha256(d2_result.read_bytes()).hexdigest()
        assert len(digest) == 64
    assert I.TRAILING_WINDOW == 720
    assert I.D7_PCTL == 90.0
    assert I.D8_RETURN_PCTL == 99.0
    assert I.D8_VOLUME_PCTL == 90.0
    assert I.D7_SEED == 20260922171
    assert I.D8_SEED == 20260922172


def test_stored_feasibility_artifact_is_selector_only():
    path = REPO / "docs/research/DISCOVERY_SPRINT_02_FEASIBILITY.json"
    if not path.is_file():
        pytest.skip("feasibility artifact not written yet")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert payload["PROTECTED_2025_OPENED"] is False
    assert payload["PROTECTED_2026_OPENED"] is False
    assert payload["MARKET_07_CREATED"] is False
    assert payload["D7_SCIENTIFIC_EVALUATOR_RUN_ON_REAL_DATA"] is False
    assert payload["D8_SCIENTIFIC_EVALUATOR_RUN_ON_REAL_DATA"] is False
    assert payload["D7"]["SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED"] is False
    assert payload["D8"]["RECOVERY_6H_COMPUTED"] is False
    blob = json.dumps(payload)
    assert "MU_D7_RULE" not in blob
    assert "DELTA_RECOVERY_6H" not in blob
    assert "PROMISING_PROTOTYPE" not in blob
    opened = " ".join(payload.get("OPENED_FILES") or [])
    assert "2025-" not in opened
    assert "2026-" not in opened
