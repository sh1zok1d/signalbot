"""Geometry-only extractor for the unpublished D7 eligible-index gap break.

The only values that may leave this module are aggregate eligible counts,
the published gap identity, and provenance digests. Protected series stay
inside the process and are discarded.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from scripts.research.d7_bitmex_support_and_power_v0 import (  # noqa: E402
    ACTIVITY_FIELD,
    BARS_PER_HOUR,
    CANONICAL_REL,
    EXPECTED_CANONICAL_GZ_SHA256,
    HOUR_MS,
    aggregate_completed_hours,
    build_predictor_frame,
    load_5m_bars,
    structural_target_eligible,
)
from scripts.research.discovery_sprint_02_impl import (  # noqa: E402
    D7_PCTL,
    PERCENTILE_METHOD,
    TRAILING_WINDOW,
)
from scripts.research.d2_bitmex_pre2020 import BAR_MS  # noqa: E402

UTC = timezone.utc
PUBLISHED_GAP = "[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)"
PUBLISHED_YEAR_MASS = {
    2016: 4079,
    2017: 8757,
    2018: 8759,
    2019: 8759,
}
PUBLISHED_T = 30354
MINIMUM_REQUIRED_GEOMETRY = "ELIGIBLE_INDEX_GAP_BREAK"

_GAP_START_ISO = "2016-12-06T23:55:00.000Z"
_GAP_END_ISO = "2016-12-07T23:55:00.000Z"


def _epoch_ms(iso: str) -> int:
    parsed = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


GAP_START_MS = _epoch_ms(_GAP_START_ISO)
GAP_END_MS = _epoch_ms(_GAP_END_ISO)

ALLOWED_OUTPUT_KEYS = (
    "CONSISTENT",
    "DERIVATION_FILE_SHA256",
    "DERIVATION_RULE_SHA256",
    "ELIGIBLE_2016_TOTAL",
    "ELIGIBLE_2017_TOTAL",
    "ELIGIBLE_2018_TOTAL",
    "ELIGIBLE_2019_TOTAL",
    "ELIGIBLE_BEFORE_GAP_OUTSIDE_2016",
    "ELIGIBLE_COUNT_AFTER_GAP",
    "ELIGIBLE_COUNT_BEFORE_GAP",
    "ELIGIBLE_INDEX_GAP_BREAK",
    "ELIGIBLE_INSIDE_PUBLISHED_GAP",
    "ELIGIBLE_OTHER_YEAR",
    "EXTRACTOR_SHA256",
    "GAP_HALF_OPEN",
    "MINIMUM_REQUIRED_GEOMETRY",
    "SOURCE_CANONICAL_GZ_SHA256",
    "T",
    "T_MATCHES_PUBLISHED",
    "YEAR_MASSES_MATCH_PUBLISHED",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derivation_rule_digest() -> str:
    """Digest of the frozen eligibility functions and the constants they use."""

    functions = (
        aggregate_completed_hours,
        build_predictor_frame,
        structural_target_eligible,
    )
    parts = [inspect.getsource(fn) for fn in functions]
    constants = {
        "ACTIVITY_FIELD": ACTIVITY_FIELD,
        "BAR_MS": int(BAR_MS),
        "BARS_PER_HOUR": int(BARS_PER_HOUR),
        "D7_PCTL": float(D7_PCTL),
        "GAP_END_MS": int(GAP_END_MS),
        "GAP_START_MS": int(GAP_START_MS),
        "HOUR_MS": int(HOUR_MS),
        "PERCENTILE_METHOD": PERCENTILE_METHOD,
        "PUBLISHED_GAP": PUBLISHED_GAP,
        "TRAILING_WINDOW": int(TRAILING_WINDOW),
    }
    payload = json.dumps(
        {"constants": constants, "sources": parts},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(payload)


def count_eligible_geometry(
    hour_start_ms,
    year,
    eligible,
) -> dict[str, int]:
    """Count eligible hours around the published gap. Returns integers only."""

    import numpy as np

    hour = np.asarray(hour_start_ms)
    labels = np.asarray(year)
    mask = np.asarray(eligible, dtype=bool)
    if hour.ndim != 1 or hour.shape != labels.shape or hour.shape != mask.shape:
        raise RuntimeError("GEOMETRY_SHAPE")
    before = mask & (hour < GAP_START_MS)
    inside = mask & (hour >= GAP_START_MS) & (hour < GAP_END_MS)
    after_2016 = mask & (labels == 2016) & (hour >= GAP_END_MS)
    before_outside_2016 = before & (labels != 2016)
    counts = {
        "ELIGIBLE_COUNT_BEFORE_GAP": int(np.count_nonzero(before)),
        "ELIGIBLE_COUNT_AFTER_GAP": int(np.count_nonzero(after_2016)),
        "ELIGIBLE_INSIDE_PUBLISHED_GAP": int(np.count_nonzero(inside)),
        "ELIGIBLE_BEFORE_GAP_OUTSIDE_2016": int(np.count_nonzero(before_outside_2016)),
        "ELIGIBLE_2016_TOTAL": int(np.count_nonzero(mask & (labels == 2016))),
        "ELIGIBLE_2017_TOTAL": int(np.count_nonzero(mask & (labels == 2017))),
        "ELIGIBLE_2018_TOTAL": int(np.count_nonzero(mask & (labels == 2018))),
        "ELIGIBLE_2019_TOTAL": int(np.count_nonzero(mask & (labels == 2019))),
        "ELIGIBLE_OTHER_YEAR": int(
            np.count_nonzero(mask & (labels != 2016) & (labels != 2017) & (labels != 2018) & (labels != 2019))
        ),
        "T": int(np.count_nonzero(mask)),
    }
    for value in counts.values():
        if type(value) is not int:
            raise RuntimeError("GEOMETRY_COUNT_TYPE")
    return counts


def consistency_flags(counts: Mapping[str, int]) -> dict[str, bool]:
    year_match = all(
        int(counts[f"ELIGIBLE_{year}_TOTAL"]) == mass
        for year, mass in PUBLISHED_YEAR_MASS.items()
    )
    total = int(counts["T"])
    before = int(counts["ELIGIBLE_COUNT_BEFORE_GAP"])
    after = int(counts["ELIGIBLE_COUNT_AFTER_GAP"])
    partition = before + after == int(counts["ELIGIBLE_2016_TOTAL"]) == PUBLISHED_YEAR_MASS[2016]
    clean = (
        int(counts["ELIGIBLE_INSIDE_PUBLISHED_GAP"]) == 0
        and int(counts["ELIGIBLE_BEFORE_GAP_OUTSIDE_2016"]) == 0
        and int(counts["ELIGIBLE_OTHER_YEAR"]) == 0
    )
    t_match = total == PUBLISHED_T and total == sum(PUBLISHED_YEAR_MASS.values())
    return {
        "YEAR_MASSES_MATCH_PUBLISHED": bool(year_match and clean),
        "T_MATCHES_PUBLISHED": bool(t_match),
        "CONSISTENT": bool(year_match and partition and clean and t_match),
    }


def _seal(payload: Mapping[str, object]) -> dict[str, object]:
    if tuple(sorted(payload)) != tuple(sorted(ALLOWED_OUTPUT_KEYS)):
        raise RuntimeError("GEOMETRY_SEAL_KEYS")
    sealed: dict[str, object] = {}
    for key in ALLOWED_OUTPUT_KEYS:
        value = payload[key]
        if type(value) is bool or type(value) is int:
            sealed[key] = value
            continue
        if type(value) is not str:
            raise RuntimeError("GEOMETRY_SEAL_TYPE")
        if key == "MINIMUM_REQUIRED_GEOMETRY" and value != MINIMUM_REQUIRED_GEOMETRY:
            raise RuntimeError("GEOMETRY_SEAL_TYPE")
        if key == "GAP_HALF_OPEN" and value != PUBLISHED_GAP:
            raise RuntimeError("GEOMETRY_SEAL_TYPE")
        if key.endswith("_SHA256") and len(value) != 64:
            raise RuntimeError("GEOMETRY_SEAL_TYPE")
        sealed[key] = value
    return sealed


def extract_geometry(repo: Path | None = None) -> dict[str, object]:
    root = repo or Path(__file__).resolve().parents[2]
    canonical = root / CANONICAL_REL
    source_digest = _sha256_file(canonical)
    if source_digest != EXPECTED_CANONICAL_GZ_SHA256:
        raise RuntimeError("SOURCE_DIGEST_MISMATCH")
    bars = load_5m_bars(canonical)
    hours = aggregate_completed_hours(bars)
    del bars
    frame = build_predictor_frame(hours)
    del hours
    eligible = structural_target_eligible(frame.hour_start_ms, frame.state_defined)
    counts = count_eligible_geometry(frame.hour_start_ms, frame.year, eligible)
    del frame
    del eligible
    flags = consistency_flags(counts)
    break_index = int(counts["ELIGIBLE_COUNT_BEFORE_GAP"]) if flags["CONSISTENT"] else -1
    payload = {
        "MINIMUM_REQUIRED_GEOMETRY": MINIMUM_REQUIRED_GEOMETRY,
        "ELIGIBLE_INDEX_GAP_BREAK": break_index,
        "ELIGIBLE_COUNT_BEFORE_GAP": int(counts["ELIGIBLE_COUNT_BEFORE_GAP"]),
        "ELIGIBLE_COUNT_AFTER_GAP": int(counts["ELIGIBLE_COUNT_AFTER_GAP"]),
        "ELIGIBLE_INSIDE_PUBLISHED_GAP": int(counts["ELIGIBLE_INSIDE_PUBLISHED_GAP"]),
        "ELIGIBLE_BEFORE_GAP_OUTSIDE_2016": int(counts["ELIGIBLE_BEFORE_GAP_OUTSIDE_2016"]),
        "ELIGIBLE_OTHER_YEAR": int(counts["ELIGIBLE_OTHER_YEAR"]),
        "ELIGIBLE_2016_TOTAL": int(counts["ELIGIBLE_2016_TOTAL"]),
        "ELIGIBLE_2017_TOTAL": int(counts["ELIGIBLE_2017_TOTAL"]),
        "ELIGIBLE_2018_TOTAL": int(counts["ELIGIBLE_2018_TOTAL"]),
        "ELIGIBLE_2019_TOTAL": int(counts["ELIGIBLE_2019_TOTAL"]),
        "T": int(counts["T"]),
        "YEAR_MASSES_MATCH_PUBLISHED": flags["YEAR_MASSES_MATCH_PUBLISHED"],
        "T_MATCHES_PUBLISHED": flags["T_MATCHES_PUBLISHED"],
        "CONSISTENT": flags["CONSISTENT"],
        "GAP_HALF_OPEN": PUBLISHED_GAP,
        "SOURCE_CANONICAL_GZ_SHA256": source_digest,
        "EXTRACTOR_SHA256": _sha256_file(Path(__file__).resolve()),
        "DERIVATION_RULE_SHA256": derivation_rule_digest(),
        "DERIVATION_FILE_SHA256": _sha256_file(
            Path(inspect.getfile(structural_target_eligible)).resolve()
        ),
    }
    return _seal(payload)


def sealed_json(payload: Mapping[str, object]) -> str:
    sealed = _seal(payload)
    return json.dumps(sealed, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def main() -> int:
    try:
        text = sealed_json(extract_geometry())
    except Exception as exc:
        sys.stderr.write(f"GEOMETRY_EXTRACTOR_FAILED:{type(exc).__name__}\n")
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
