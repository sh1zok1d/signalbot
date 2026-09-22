"""D12 participation-clock DST natural experiment.

Pure functions may later compute profiles and A_k. Feasibility on real CORE
BTC counts complete days/windows only and must not emit A, D(L), or profiles.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_04 import common as C


def hourly_quote_volume(minute_quote: Sequence[float]) -> np.ndarray:
    arr = np.asarray(minute_quote, dtype=np.float64)
    if arr.size != C.MINUTE_BARS_PER_DAY:
        raise C.Sprint04IntegrityError(f"D12_DAY_MINUTE_SHAPE:{arr.size}")
    if not np.all(np.isfinite(arr)):
        raise C.Sprint04IntegrityError("D12_MINUTE_NONFINITE")
    hours = arr.reshape(C.HOURS_PER_DAY, C.BARS_PER_HOUR).sum(axis=1)
    return hours


def day_complete(minute_present: Sequence[bool], minute_quote: Sequence[float]) -> bool:
    present = np.asarray(minute_present, dtype=bool)
    if present.size != C.MINUTE_BARS_PER_DAY:
        return False
    if not bool(present.all()):
        return False
    hours_present = present.reshape(C.HOURS_PER_DAY, C.BARS_PER_HOUR).all(axis=1)
    if not bool(hours_present.all()):
        return False
    vol = float(np.asarray(minute_quote, dtype=np.float64).sum())
    return math.isfinite(vol) and vol > 0.0


def normalized_profile(hourly: Sequence[float]) -> np.ndarray:
    v = np.asarray(hourly, dtype=np.float64)
    if v.size != C.HOURS_PER_DAY:
        raise C.Sprint04IntegrityError("D12_PROFILE_SHAPE")
    if not np.all(np.isfinite(v)):
        raise C.Sprint04IntegrityError("D12_PROFILE_NONFINITE")
    total = float(v.sum())
    if total <= 0.0:
        raise C.Sprint04IntegrityError("D12_PROFILE_ZERO_VOLUME")
    return v / total


def mean_profile(daily_profiles: Sequence[Sequence[float]]) -> np.ndarray:
    if not daily_profiles:
        raise C.Sprint04IntegrityError("D12_EMPTY_WINDOW_PROFILE")
    stacked = np.vstack([normalized_profile(p) for p in daily_profiles])
    return stacked.mean(axis=0)


def shifted_distance(p_after: Sequence[float], p_before: Sequence[float], shift: int) -> float:
    a = np.asarray(p_after, dtype=np.float64)
    b = np.asarray(p_before, dtype=np.float64)
    if a.size != 24 or b.size != 24:
        raise C.Sprint04IntegrityError("D12_DISTANCE_SHAPE")
    shifted = np.array([b[(h + shift) % 24] for h in range(24)], dtype=np.float64)
    dist = float(np.square(a - shifted).sum())
    if not math.isfinite(dist):
        raise C.Sprint04IntegrityError("D12_DISTANCE_NONFINITE")
    return dist


def clock_anchoring_index(
    p_after: Sequence[float],
    p_before: Sequence[float],
    delta: int,
) -> float:
    d0 = shifted_distance(p_after, p_before, 0)
    if d0 == 0.0:
        raise C.Sprint04IntegrityError("D12_D0_ZERO_INELIGIBLE")
    d_delta = shifted_distance(p_after, p_before, delta)
    return C.finite((d0 - d_delta) / d0, name="A_k")


def window_eligible(included_n: int) -> bool:
    return included_n >= C.D12_MIN_INCLUDED_DAYS


def assert_weekday_matched_windows(sunday: date) -> tuple[list[date], list[date]]:
    before, after = C.window_days(sunday)
    if [d.weekday() for d in before] != [0, 1, 2, 3, 4, 5]:
        raise C.Sprint04IntegrityError("D12_BEFORE_WEEKDAYS")
    if [d.weekday() for d in after] != [0, 1, 2, 3, 4, 5]:
        raise C.Sprint04IntegrityError("D12_AFTER_WEEKDAYS")
    if sunday in before or sunday in after:
        raise C.Sprint04IntegrityError("D12_TRANSITION_DAY_IN_WINDOW")
    return before, after


def one_sided_mc_pvalue(
    observed_mean: float,
    null_means: Sequence[float],
    *,
    n: int = C.D12_N_RANDOMIZATIONS,
) -> float:
    arr = np.asarray(list(null_means), dtype=np.float64)
    if arr.size != n:
        raise C.Sprint04IntegrityError("D12_MC_N")
    if not np.all(np.isfinite(arr)) or not math.isfinite(observed_mean):
        raise C.Sprint04IntegrityError("D12_MC_NONFINITE")
    return float((1.0 + float(np.sum(arr >= observed_mean))) / (1.0 + n))


def sample_null_means(
    plus_pool: Sequence[float],
    minus_pool: Sequence[float],
    *,
    n_plus: int,
    n_minus: int,
    n: int,
    seed: int,
) -> list[float]:
    rng = np.random.Generator(np.random.PCG64(seed))
    plus = np.asarray(list(plus_pool), dtype=np.float64)
    minus = np.asarray(list(minus_pool), dtype=np.float64)
    if plus.size < n_plus or minus.size < n_minus:
        raise C.Sprint04IntegrityError("D12_NULL_POOL_SHORT")
    out: list[float] = []
    for _ in range(n):
        p = rng.choice(plus, size=n_plus, replace=False)
        m = rng.choice(minus, size=n_minus, replace=False)
        out.append(float(np.concatenate([p, m]).mean()))
    return out


def practical_gate(a_values: Sequence[float], *, eligible_n: int) -> bool:
    if eligible_n < C.D12_MIN_US_ELIGIBLE:
        return False
    positive = sum(1 for a in a_values if math.isfinite(a) and a > 0.0)
    return positive >= C.D12_PRACTICAL_POSITIVE_N


def temporal_gate(yearly_mean: Mapping[str, float]) -> bool:
    positive_years = [
        year
        for year, value in yearly_mean.items()
        if math.isfinite(value) and value > 0.0
    ]
    return len(positive_years) >= C.D12_TEMPORAL_YEARS_REQUIRED


def evaluate_d12_scientific(
    us_a: Sequence[float],
    us_delta: Sequence[int],
    us_years: Sequence[int],
    plus_pool: Sequence[float],
    minus_pool: Sequence[float],
    *,
    support: Mapping[str, Any],
) -> dict[str, Any]:
    """Pure evaluator on supplied A arrays. Must not be called on real CORE here."""

    identity_ok = bool(support.get("IDENTITY_OK"))
    support_pass = bool(support.get("SUPPORT_PASS"))
    summary: dict[str, Any] = {
        "IDENTITY_OK": identity_ok,
        "SUPPORT_PASS": support_pass,
        "STATISTICAL_GATE": False,
        "PRACTICAL_GATE": False,
        "TEMPORAL_GATE": False,
        "RANDOM_SEED": C.D12_RANDOM_SEED,
        "N_RANDOMIZATIONS": C.D12_N_RANDOMIZATIONS,
    }
    if not identity_ok:
        summary["CLASSIFICATION"] = C.classify_from_summary(summary)
        return summary
    if not support_pass:
        summary["CLASSIFICATION"] = C.classify_from_summary(summary)
        return summary
    a = [C.finite(x, name="A") for x in us_a]
    mean_a = float(np.mean(a))
    n_plus = sum(1 for d in us_delta if d == 1)
    n_minus = sum(1 for d in us_delta if d == -1)
    null = sample_null_means(
        plus_pool,
        minus_pool,
        n_plus=n_plus,
        n_minus=n_minus,
        n=C.D12_N_RANDOMIZATIONS,
        seed=C.D12_RANDOM_SEED,
    )
    p_value = one_sided_mc_pvalue(mean_a, null)
    yearly: dict[str, float] = {}
    by_year: dict[int, list[float]] = {}
    for year, value in zip(us_years, a):
        by_year.setdefault(int(year), []).append(value)
    for year, values in sorted(by_year.items()):
        yearly[str(year)] = float(np.mean(values))
    summary.update(
        {
            "MEAN_A": mean_a,
            "US_A": list(a),
            "MC_P": p_value,
            "STATISTICAL_GATE": p_value < C.D12_MC_ALPHA,
            "PRACTICAL_GATE": practical_gate(a, eligible_n=len(a)),
            "TEMPORAL_GATE": temporal_gate(yearly),
            "YEARLY_MEAN_A": yearly,
        }
    )
    summary["CLASSIFICATION"] = C.classify_from_summary(summary)
    return summary


def classify_d12_from_summary(summary: Mapping[str, Any]) -> str:
    return C.classify_from_summary(summary)


def legal_range_ok(days: Sequence[date]) -> bool:
    return all(date(2020, 1, 1) <= d <= C.LEGAL_END_INCLUSIVE for d in days)


def pseudo_sundays(us: Sequence[date], eu: Sequence[date]) -> list[date]:
    transitions = set(us) | set(eu)
    out: list[date] = []
    sunday = date(2020, 1, 5)
    while sunday + timedelta(days=6) <= C.LEGAL_END_INCLUSIVE:
        if sunday not in transitions:
            before, after = C.window_days(sunday)
            if legal_range_ok(before + after):
                if len({C.eu_in_dst(d) for d in before + after}) == 1:
                    if len({C.us_in_dst(d) for d in before + after}) == 1:
                        out.append(sunday)
        sunday += timedelta(days=7)
    return out


def census_complete_days(complete_days: Mapping[date, bool]) -> dict[str, Any]:
    """Window constructibility from complete-day flags only. No profiles."""

    us = C.us_transition_dates()
    eu = C.eu_transition_dates()
    if len(us) != 10 or len(eu) != 10:
        raise C.Sprint04IntegrityError("D12_TRANSITION_COUNT")

    def window_count(sunday: date) -> dict[str, Any]:
        before, after = assert_weekday_matched_windows(sunday)
        b_n = sum(1 for d in before if complete_days.get(d, False))
        a_n = sum(1 for d in after if complete_days.get(d, False))
        return {
            "sunday": sunday.isoformat(),
            "before_included": b_n,
            "after_included": a_n,
            "eligible": window_eligible(b_n) and window_eligible(a_n),
            "before_weekdays": [d.weekday() for d in before],
            "after_weekdays": [d.weekday() for d in after],
            "eu_dst_constant": len({C.eu_in_dst(d) for d in before + after}) == 1,
            "us_dst_changes": C.us_in_dst(before[-1]) != C.us_in_dst(after[0]),
            "transition_in_window": False,
        }

    us_rows = [window_count(s) for s in us]
    eu_rows = [window_count(s) for s in eu]
    # EU diagnostic windows must hold the US clock constant.
    for sunday, row in zip(eu, eu_rows):
        before, after = C.window_days(sunday)
        row["us_dst_constant"] = len({C.us_in_dst(d) for d in before + after}) == 1
        row["eu_dst_changes"] = C.eu_in_dst(before[-1]) != C.eu_in_dst(after[0])
    pseudo = []
    for sunday in pseudo_sundays(us, eu):
        before, after = C.window_days(sunday)
        b_n = sum(1 for d in before if complete_days.get(d, False))
        a_n = sum(1 for d in after if complete_days.get(d, False))
        if window_eligible(b_n) and window_eligible(a_n):
            pseudo.append(sunday.isoformat())
    us_eligible = sum(1 for r in us_rows if r["eligible"])
    eu_eligible = sum(1 for r in eu_rows if r["eligible"])
    support = (
        us_eligible >= C.D12_MIN_US_ELIGIBLE
        and len(pseudo) >= C.D12_MIN_PSEUDO_SUNDAYS
        and all(r["before_weekdays"] == r["after_weekdays"] == [0, 1, 2, 3, 4, 5] for r in us_rows)
        and all(r["eu_dst_constant"] for r in us_rows)
        and all(r["us_dst_changes"] for r in us_rows)
    )
    return {
        "US_TRANSITIONS_TOTAL": 10,
        "US_TRANSITIONS_FEASIBLE": us_eligible,
        "EU_TRANSITIONS_TOTAL": 10,
        "EU_TRANSITIONS_FEASIBLE": eu_eligible,
        "PSEUDO_SUNDAY_N": len(pseudo),
        "US_WINDOWS": us_rows,
        "EU_WINDOWS": eu_rows,
        "SUPPORT_PASS": support,
        "RANDOM_SEED": C.D12_RANDOM_SEED,
        "COMPLETE_DAY_N": int(sum(1 for v in complete_days.values() if v)),
    }


def legal_monthly_checksum_key(period: str) -> str:
    return f"canonical/1m/monthly/{period}.parquet"


def btc_legal_parquet_checksums(repo: Path | None = None) -> dict[str, str]:
    base = repo or C.repo_root()
    identity = json.loads((base / C.CORE_BTC_SNAPSHOT_DOC_REL).read_text(encoding="utf-8"))
    payload = identity.get("identity_payload") or identity
    bound = payload.get("snapshot_id") or identity.get("snapshot_id")
    if bound != C.CORE_BTC_SNAPSHOT_ID:
        raise C.SnapshotIdentityError(f"BTC_SNAPSHOT_MISMATCH:{bound}")
    checksums = payload.get("output_checksums") or {}
    out: dict[str, str] = {}
    for period in C.LEGAL_MONTHS_CORE:
        key = legal_monthly_checksum_key(period)
        digest = checksums.get(key)
        if not digest:
            raise C.SnapshotIdentityError(f"BTC_MISSING_CHECKSUM:{period}")
        out[period] = str(digest)
    return out


def verify_core_identity(*, repo: Path | None = None) -> dict[str, Any]:
    """Exact-byte identity of legal 2020-2024 monthly parquet. No profiles."""

    base = repo or C.repo_root()
    checksums = btc_legal_parquet_checksums(base)
    root = base / C.CORE_BTC_ROOT_REL
    if not root.is_dir():
        raise C.MissingLocalData(f"CORE_BTC_MISSING_ROOT:{root}")
    opened: list[str] = []
    quote_volume_field = False
    for period in C.LEGAL_MONTHS_CORE:
        path = root / "canonical" / "1m" / "monthly" / f"{period}.parquet"
        C.assert_openable(path)
        if not path.is_file():
            raise C.MissingLocalData(f"CORE_BTC_MISSING_MONTH:{period}")
        digest = C.sha256_bytes(path.read_bytes())
        if digest != checksums[period]:
            raise C.SnapshotIdentityError(f"CORE_BTC_CHECKSUM_MISMATCH:{period}")
        opened.append(str(path.relative_to(base)))
        import pyarrow.parquet as pq

        names = set(pq.read_schema(path).names)
        if "open_time_ms" not in names:
            raise C.Sprint04IntegrityError(f"CORE_BTC_MISSING_OPEN_TIME:{period}")
        if "quote_volume" not in names:
            raise C.Sprint04IntegrityError(f"CORE_BTC_MISSING_QUOTE_VOLUME:{period}")
        quote_volume_field = True
        if C.path_is_protected_partition(path):
            raise C.ProtectedYearRefused(str(path))
    return {
        "IDENTITY_OK": True,
        "DATASET_ID": C.CORE_BTC_DATASET_ID,
        "SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT_ID,
        "MONTHS": list(C.LEGAL_MONTHS_CORE),
        "MONTH_N": len(C.LEGAL_MONTHS_CORE),
        "QUOTE_VOLUME_FIELD": quote_volume_field,
        "OPENED_FILES": opened,
        "DATA_IDENTITY_MODE": "TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION",
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
    }


def load_complete_day_flags(*, repo: Path | None = None) -> dict[date, bool]:
    """Minute completeness + positive daily quote_volume. No hourly profiles."""

    import pyarrow.parquet as pq

    base = repo or C.repo_root()
    checksums = btc_legal_parquet_checksums(base)
    root = base / C.CORE_BTC_ROOT_REL
    present: dict[int, float] = {}
    for period in C.LEGAL_MONTHS_CORE:
        path = root / "canonical" / "1m" / "monthly" / f"{period}.parquet"
        C.assert_openable(path)
        raw = path.read_bytes()
        if C.sha256_bytes(raw) != checksums[period]:
            raise C.SnapshotIdentityError(f"CORE_BTC_CHECKSUM_MISMATCH:{period}")
        table = pq.read_table(path, columns=["open_time_ms", "quote_volume"])
        opens = table.column("open_time_ms").to_pylist()
        quotes = table.column("quote_volume").to_pylist()
        for open_ms, quote in zip(opens, quotes):
            ts = int(open_ms)
            if ts >= C.PROTECTED_START_MS:
                raise C.ProtectedYearRefused(f"PROTECTED_TIMESTAMP:{period}:{ts}")
            if ts < C.LEGAL_START_MS:
                continue
            vol = C.parse_decimal_string(quote, field="quote_volume")
            if ts in present and present[ts] != vol:
                raise C.Sprint04IntegrityError(f"D12_DUPLICATE_CONFLICT:{ts}")
            present[ts] = vol
    flags: dict[date, bool] = {}
    day = date(2020, 1, 1)
    while day <= C.LEGAL_END_INCLUSIVE:
        start = C.date_to_ms(day)
        complete = True
        volume = 0.0
        for k in range(C.MINUTE_BARS_PER_DAY):
            ts = start + k * C.BAR_1M_MS
            if ts not in present:
                complete = False
                break
            volume += present[ts]
        flags[day] = bool(complete and math.isfinite(volume) and volume > 0.0)
        day += timedelta(days=1)
    return flags


def feasibility_census(*, repo: Path | None = None) -> dict[str, Any]:
    identity = verify_core_identity(repo=repo)
    flags = load_complete_day_flags(repo=repo)
    census = census_complete_days(flags)
    census["IDENTITY_OK"] = bool(identity["IDENTITY_OK"])
    census["DATA_IDENTITY"] = {
        "DATASET_ID": identity["DATASET_ID"],
        "SNAPSHOT_ID": identity["SNAPSHOT_ID"],
        "MONTH_N": identity["MONTH_N"],
        "QUOTE_VOLUME_FIELD": identity["QUOTE_VOLUME_FIELD"],
        "DATA_IDENTITY_MODE": identity["DATA_IDENTITY_MODE"],
    }
    census["PROFILES_COMPUTED"] = False
    census["A_VALUES_COMPUTED"] = False
    census["D_VALUES_COMPUTED"] = False
    census["SCIENTIFIC_OUTCOME_COMPUTED"] = False
    census["RANDOM_SEED"] = C.D12_RANDOM_SEED
    census["N_RANDOMIZATIONS"] = C.D12_N_RANDOMIZATIONS
    return census
