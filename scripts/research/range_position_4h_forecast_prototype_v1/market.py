"""Pinned market adapter for the frozen forecast prototype.

The loader and the scorer run only after `OWNER_GO`. Until then `load_pinned_grids`,
`execute_pinned_market_fit`, `main`, and `run_market` exit `AWAITING_OWNER_GO`
before any price file is opened. Validators and frame construction are pure and
are what the synthetic tests exercise.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from scripts.research.range_position_4h_incremental_replication_v1.grid import features

from . import constants as K
from .eligibility import local_returns, replication_eligible
from .evaluate import TRAIN_SOURCES
from .folds import assign_folds
from .model import ImplementationInvalid

ROOT = Path(__file__).resolve().parents[3]
EXECUTION_JOURNAL = ROOT / "docs/research/range_position_4h_forecast_prototype_v1_execution"
SEGMENT_ORDER = ("BITMEX_2016_2019", "BINANCE_2020_2024", "BINANCE_2025_2026")
SURFACE_END = {
    "BITMEX_2016_2019": K.BITMEX_END_MS,
    "BINANCE_2020_2024": K.CORE_END_MS,
    "BINANCE_2025_2026": K.BINANCE_END_MS,
}
PINNED_CORE_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
FEATURE_ORDER = K.CANDIDATE_FEATURES
_OPTION_VALUES = {
    "min_train_rows": K.MIN_TRAIN_ROWS,
    "min_train_weeks": K.MIN_TRAIN_WEEKS,
    "bootstrap_draws": K.BOOT_DRAWS,
    "bootstrap_seed": K.BOOT_SEED,
    "horizon": K.HORIZON,
    "bar_ms": K.BAR_MS,
}
_FLAG_MAP = {
    "--min-train-rows": "min_train_rows",
    "--min-train-weeks": "min_train_weeks",
    "--bootstrap-draws": "bootstrap_draws",
    "--bootstrap-seed": "bootstrap_seed",
    "--horizon": "horizon",
    "--bar-ms": "bar_ms",
    "--allowed-train-segments": "allowed_train_segments",
}
_LOAD_TOKEN = object()
_SCORE_TOKEN = object()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_digest(path: Path, expected: str) -> None:
    """Hash one file. A mismatch is invalid. This does not interpret prices."""
    if sha256_file(path) != expected:
        raise ImplementationInvalid("HASH_MISMATCH")


def assert_amendment_pinned(path: Path | None = None) -> None:
    target = ROOT / K.AMENDMENT_A1 if path is None else Path(path)
    if sha256_file(target) != K.AMENDMENT_A1_SHA256:
        raise ImplementationInvalid("AMENDMENT_HASH_MISMATCH")


def assert_core_snapshot(snapshot: str) -> None:
    if snapshot != PINNED_CORE_SNAPSHOT or K.CORE_SNAPSHOT != PINNED_CORE_SNAPSHOT:
        raise ImplementationInvalid("CORE_SNAPSHOT_MISMATCH")


def assert_protocol_locked() -> None:
    """The market path uses the frozen constants. It does not accept a replacement."""
    if K.HORIZON != 12 or K.BAR_MS != 300_000:
        raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
    if K.MIN_TRAIN_ROWS != 1000 or K.MIN_TRAIN_WEEKS != 20:
        raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
    if K.BOOT_DRAWS != 2000 or K.BOOT_SEED != 20261120:
        raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
    if K.BASELINE_FEATURES != ("RET_4H", "RV_4H", "RET_1H", "RET_15M"):
        raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
    if K.CANDIDATE_FEATURES != ("RET_4H", "RV_4H", "RET_1H", "RET_15M", "RANGE_POSITION_4H"):
        raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
    if K.CLAIM_CEILING != "RETROSPECTIVE_FORECAST_PROTOTYPE":
        raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
    expected = {
        "BITMEX_2016_2019": ("BITMEX_2016_2019",),
        "BINANCE_2020_2024": ("BINANCE_2020_2024",),
        "BINANCE_2025_2026": ("BINANCE_2020_2024", "BINANCE_2025_2026"),
    }
    if TRAIN_SOURCES != expected:
        raise ImplementationInvalid("TRAINING_SOURCE_OVERRIDE")
    if sum(K.EXPECTED_TEST_ROWS.values()) != K.EXPECTED_TOTAL_TEST_ROWS:
        raise ImplementationInvalid("COVERAGE_MISMATCH")
    if sum(K.EXPECTED_TEST_WEEKS.values()) != K.EXPECTED_TOTAL_TEST_WEEKS:
        raise ImplementationInvalid("COVERAGE_MISMATCH")
    if K.EXPECTED_TOTAL_TEST_ROWS != 336293 or K.EXPECTED_TOTAL_TEST_WEEKS != 505:
        raise ImplementationInvalid("COVERAGE_MISMATCH")


def train_sources_for(name: str, caller_map=None) -> tuple[str, ...]:
    if caller_map is not None:
        raise ImplementationInvalid("TRAINING_SOURCE_OVERRIDE")
    try:
        return tuple(TRAIN_SOURCES[name])
    except KeyError as exc:
        raise ImplementationInvalid("SEGMENT_SET") from exc


def reject_overrides(options: dict | None) -> None:
    """Refuse a market-path replacement of a frozen parameter or of the train map."""
    if not options:
        return
    if "allowed_train_segments" in options:
        raise ImplementationInvalid("TRAINING_SOURCE_OVERRIDE")
    unknown = set(options) - set(_OPTION_VALUES)
    if unknown:
        raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
    for key, value in options.items():
        if value != _OPTION_VALUES[key]:
            raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")


def options_from_argv(argv: list[str] | None) -> dict:
    """Parse market CLI flags. The guarded entry calls this only after the owner go."""
    argv = list(argv or [])
    options: dict = {}
    index = 0
    while index < len(argv):
        flag = argv[index]
        if flag not in _FLAG_MAP:
            if flag.startswith("--"):
                raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
            index += 1
            continue
        if index + 1 >= len(argv):
            raise ImplementationInvalid("FROZEN_PARAMETER_OVERRIDE")
        name = _FLAG_MAP[flag]
        raw = argv[index + 1]
        options[name] = raw if name == "allowed_train_segments" else int(raw)
        index += 2
    return options


def _clock_ok(name: str, open_ms: np.ndarray) -> bool:
    """Half-open interval on the 5m open. A bar that closes on `surface_end` stays in.

    The last admitted open is `surface_end - BAR_MS`. The first refused open is
    `surface_end`. Feature eligibility is a separate rule and is not applied here.
    """
    open_ms = np.asarray(open_ms, dtype=np.int64)
    if open_ms.size == 0:
        return True
    if name == "BITMEX_2016_2019":
        return bool(np.all(open_ms < K.BITMEX_END_MS))
    if name == "BINANCE_2020_2024":
        return bool(np.all((open_ms >= K.CORE_START_MS) & (open_ms < K.CORE_END_MS)))
    if name == "BINANCE_2025_2026":
        return bool(np.all((open_ms >= K.BINANCE_START_MS) & (open_ms < K.BINANCE_END_MS)))
    return False


def labeled_rows(grid: dict, surface_end_ms: int, official_eligible: np.ndarray | None = None) -> dict:
    """Label one grid with the existing feature and eligibility functions.

    A missing close stays missing. Rows are not borrowed from another grid.
    """
    high = np.asarray(grid["high"], dtype=np.float64)
    low = np.asarray(grid["low"], dtype=np.float64)
    close = np.asarray(grid["close"], dtype=np.float64)
    opened = np.asarray(grid["grid_open"], dtype=np.int64)
    eligible = replication_eligible(opened, high, low, close, int(surface_end_ms))
    if official_eligible is not None:
        official = np.asarray(official_eligible, dtype=bool)
        if official.shape != eligible.shape or not np.array_equal(official, eligible):
            raise ImplementationInvalid("ELIGIBILITY_DIVERGED")
    feat = features(high, low, close)
    ret_1h, ret_15m = local_returns(close)
    finite = (
        np.isfinite(feat["rp"]) & np.isfinite(feat["ret4"]) & np.isfinite(feat["rv4"])
        & np.isfinite(feat["r1"]) & np.isfinite(ret_1h) & np.isfinite(ret_15m)
    )
    if np.any(eligible & ~finite):
        raise ImplementationInvalid("ELIGIBLE_ROW_MISSING_A_FEATURE")
    feature_ok = eligible & finite
    zero = feature_ok & (feat["r1"] == 0.0)
    labeled = feature_ok & ~zero
    if np.any(labeled & ~np.isfinite(close)):
        raise ImplementationInvalid("GAP_FILLED")
    close_ms = opened + np.int64(K.BAR_MS)
    chosen = close_ms[labeled]
    if chosen.size != np.unique(chosen).size:
        raise ImplementationInvalid("DUPLICATE_TIMESTAMP")
    matrix = np.column_stack([
        feat["ret4"][labeled],
        feat["rv4"][labeled],
        ret_1h[labeled],
        ret_15m[labeled],
        feat["rp"][labeled],
    ])
    target = (feat["r1"][labeled] > 0.0).astype(np.float64)
    if matrix.size and (not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(target))):
        raise ImplementationInvalid("NON_FINITE_LABELED_VALUE")
    return {
        "close_ms": chosen,
        "x": matrix,
        "y": target,
        "n_zero": int(zero.sum()),
        "labeled_mask": labeled,
    }


def adapt_segment(name: str, grid: dict, official_eligible: np.ndarray | None = None) -> dict:
    if name not in SEGMENT_ORDER:
        raise ImplementationInvalid("SEGMENT_SET")
    table = labeled_rows(grid, SURFACE_END[name], official_eligible)
    finite_close = np.asarray(grid["close"], dtype=np.float64)
    finite_open = np.asarray(grid["grid_open"], dtype=np.int64)
    present_open = finite_open[np.isfinite(finite_close)]
    if not _clock_ok(name, present_open):
        raise ImplementationInvalid("SEGMENT_CLOCK")
    table["name"] = name
    validate_labeled_table(name, table)
    return table


def validate_labeled_table(name: str, table: dict) -> None:
    if "allowed_train_segments" in table or "train_sources" in table:
        raise ImplementationInvalid("TRAINING_SOURCE_OVERRIDE")
    close_ms = np.asarray(table["close_ms"], dtype=np.int64)
    matrix = np.asarray(table["x"], dtype=np.float64)
    target = np.asarray(table["y"], dtype=np.float64)
    if close_ms.size != np.unique(close_ms).size:
        raise ImplementationInvalid("DUPLICATE_TIMESTAMP")
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURE_ORDER) or matrix.shape[0] != close_ms.shape[0]:
        raise ImplementationInvalid("FEATURE_WIDTH")
    if target.shape[0] != close_ms.shape[0]:
        raise ImplementationInvalid("FEATURE_WIDTH")
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(target)):
        raise ImplementationInvalid("NON_FINITE_LABELED_VALUE")
    open_ms = close_ms - np.int64(K.BAR_MS)
    if not _clock_ok(name, open_ms):
        raise ImplementationInvalid("SEGMENT_CLOCK")
    if name != "BITMEX_2016_2019" and np.any(open_ms < K.BITMEX_END_MS):
        raise ImplementationInvalid("SEGMENT_CLOCK")


def construct_segments(tables: dict) -> list[dict]:
    """Build scorer segments. Training sources come only from `TRAIN_SOURCES`."""
    if set(tables) != set(SEGMENT_ORDER):
        raise ImplementationInvalid("SEGMENT_SET")
    for name in SEGMENT_ORDER:
        validate_labeled_table(name, tables[name])
    segments = []
    for name in SEGMENT_ORDER:
        sources = train_sources_for(name)
        parts_t = []
        parts_y = []
        parts_x = []
        parts_name = []
        for source in sources:
            table = tables[source]
            count = int(np.asarray(table["close_ms"]).shape[0])
            parts_t.append(np.asarray(table["close_ms"], dtype=np.int64))
            parts_y.append(np.asarray(table["y"], dtype=np.float64))
            parts_x.append(np.asarray(table["x"], dtype=np.float64))
            parts_name.append(np.full(count, source))
        train_close = np.concatenate(parts_t)
        train_y = np.concatenate(parts_y)
        train_x = np.concatenate(parts_x)
        train_segment = np.concatenate(parts_name)
        order = np.argsort(train_close, kind="mergesort")
        train_close = train_close[order]
        train_y = train_y[order]
        train_x = train_x[order]
        train_segment = train_segment[order]
        identity = list(zip(train_segment.tolist(), train_close.tolist()))
        if len(identity) != len(set(identity)):
            raise ImplementationInvalid("DUPLICATE_TIMESTAMP")
        if name != "BITMEX_2016_2019" and np.any(train_segment == "BITMEX_2016_2019"):
            raise ImplementationInvalid("TRAINING_SOURCE_VIOLATION")
        test = tables[name]
        test_close = np.asarray(test["close_ms"], dtype=np.int64)
        test_order = np.argsort(test_close, kind="mergesort")
        segments.append({
            "name": name,
            "train_close_ms": train_close,
            "train_y": train_y,
            "train_x": train_x,
            "train_segment": train_segment,
            "test_close_ms": test_close[test_order],
            "test_y": np.asarray(test["y"], dtype=np.float64)[test_order],
            "test_x": np.asarray(test["x"], dtype=np.float64)[test_order],
        })
    return segments


def expected_coverage() -> dict:
    counts = {
        name: {"test_rows": K.EXPECTED_TEST_ROWS[name], "test_weeks": K.EXPECTED_TEST_WEEKS[name]}
        for name in SEGMENT_ORDER
    }
    counts["total_rows"] = K.EXPECTED_TOTAL_TEST_ROWS
    counts["total_weeks"] = K.EXPECTED_TOTAL_TEST_WEEKS
    return counts


def validate_coverage(counts: dict) -> None:
    """Fail closed when primary test rows or weeks differ from the amended census."""
    total_rows = 0
    total_weeks = 0
    for name in SEGMENT_ORDER:
        got = counts.get(name)
        rows = K.EXPECTED_TEST_ROWS[name]
        weeks = K.EXPECTED_TEST_WEEKS[name]
        if not isinstance(got, dict):
            raise ImplementationInvalid("COVERAGE_MISMATCH")
        if int(got.get("test_rows", -1)) != rows or int(got.get("test_weeks", -1)) != weeks:
            raise ImplementationInvalid("COVERAGE_MISMATCH")
        total_rows += rows
        total_weeks += weeks
    if total_rows != K.EXPECTED_TOTAL_TEST_ROWS or total_weeks != K.EXPECTED_TOTAL_TEST_WEEKS:
        raise ImplementationInvalid("COVERAGE_MISMATCH")
    if int(counts.get("total_rows", -1)) != K.EXPECTED_TOTAL_TEST_ROWS:
        raise ImplementationInvalid("COVERAGE_MISMATCH")
    if int(counts.get("total_weeks", -1)) != K.EXPECTED_TOTAL_TEST_WEEKS:
        raise ImplementationInvalid("COVERAGE_MISMATCH")


def coverage_from_support(payload: dict) -> dict:
    counts = {}
    total_rows = 0
    total_weeks = 0
    for name in SEGMENT_ORDER:
        segment = payload["segments"][name]
        rows = int(segment["primary_test_rows"])
        weeks = int(segment["primary_test_weeks"])
        counts[name] = {"test_rows": rows, "test_weeks": weeks}
        total_rows += rows
        total_weeks += weeks
    counts["total_rows"] = total_rows
    counts["total_weeks"] = total_weeks
    return counts


def assert_pinned_census_coverage(payload: dict | None = None) -> None:
    if payload is None:
        payload = json.loads((ROOT / K.SUPPORT).read_text(encoding="utf-8"))
    validate_coverage(coverage_from_support(payload))


def primary_fold_counts(segments: list[dict]) -> dict:
    counts = {}
    total_rows = 0
    total_weeks = 0
    for segment in segments:
        schedule = assign_folds(
            segment["test_close_ms"],
            segment["train_close_ms"],
            min_rows=K.MIN_TRAIN_ROWS,
            min_weeks=K.MIN_TRAIN_WEEKS,
        )
        rows = int(schedule["n_test_rows"])
        weeks = int(schedule["n_test_weeks"])
        counts[segment["name"]] = {"test_rows": rows, "test_weeks": weeks}
        total_rows += rows
        total_weeks += weeks
    counts["total_rows"] = total_rows
    counts["total_weeks"] = total_weeks
    return counts


def validate_and_construct(tables: dict, options: dict | None = None) -> tuple[list[dict], dict]:
    """Validate a frame and count its folds. Does not score and does not read prices."""
    reject_overrides(options)
    assert_protocol_locked()
    assert_amendment_pinned()
    segments = construct_segments(tables)
    return segments, primary_fold_counts(segments)


class MarketExecution:
    """Provenance marks set by the load and by the score, not by report arguments."""

    def __init__(self) -> None:
        self._loaded = False
        self._scored = False

    @property
    def series_loaded(self) -> bool:
        return self._loaded

    @property
    def scored(self) -> bool:
        return self._scored

    def mark_loaded(self, token: object) -> None:
        if token is not _LOAD_TOKEN:
            raise ImplementationInvalid("PROVENANCE_OVERRIDE")
        self._loaded = True

    def mark_scored(self, token: object) -> None:
        if token is not _SCORE_TOKEN or not self._loaded:
            raise ImplementationInvalid("PROVENANCE_OVERRIDE")
        self._scored = True


def jsonable(value):
    """Convert scorer output to JSON values. An unknown type is a hard failure."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(key): jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(child) for child in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        if not np.isfinite(number):
            raise ImplementationInvalid("RESULT_NOT_SERIALIZABLE")
        return number
    raise ImplementationInvalid("RESULT_NOT_SERIALIZABLE")


def _hashes() -> dict:
    return {
        "design_sha256": K.DESIGN_SHA256,
        "design_json_sha256": K.DESIGN_JSON_SHA256,
        "amendment_a1_sha256": K.AMENDMENT_A1_SHA256,
        "support_sha256": K.SUPPORT_SHA256,
        "folds_sha256": K.FOLDS_SHA256,
        "adapter_manifest_sha256": K.ADAPTER_MANIFEST_SHA256,
        "bitmex_series_sha256": K.BITMEX_SHA256,
        "binance_series_sha256": K.BINANCE_SHA256,
        "core_snapshot": K.CORE_SNAPSHOT,
    }


def build_report(execution: MarketExecution, result: dict | None = None, hourly: dict | None = None,
                 **_caller) -> dict:
    """Flags follow the execution marks. The scorer payload is kept in full.

    Caller keywords are discarded. NumPy values are converted so the report can
    be written without dropping a metric or a stored probability.
    """
    loaded = bool(execution.series_loaded)
    scored = bool(execution.scored) and loaded
    report = {
        "unit": K.UNIT,
        "evidence_class": K.CLAIM_CEILING,
        "claim_ceiling": K.CLAIM_CEILING,
        "market_series_loaded": loaded,
        "probabilities_computed_on_market": scored,
        "model_metrics_computed": scored,
        "market_fit_executed": scored,
        "owner_go": bool(K.OWNER_GO),
        "product_ready": False,
        "live_validated": False,
        "prospective": False,
        "regularization_added": False,
        "fallback_fit": False,
        "hashes": _hashes(),
    }
    if result is not None:
        primary = jsonable(result)
        report["primary"] = primary
        report["route"] = primary.get("route")
        report["implementation_ok"] = bool(primary.get("implementation_ok"))
        report["reason"] = primary.get("reason")
    if hourly is not None:
        report["hourly"] = jsonable(hourly)
        report["hourly_diagnostic_only"] = True
        report["hourly_route"] = report["hourly"].get("route")
    return report


def score_prepared(segments: list[dict], counts: dict, execution: MarketExecution) -> dict:
    """Score only a loaded execution whose fold counts match the pin.

    Coverage is checked first. An unmarked execution never reaches the scorer.
    """
    validate_coverage(counts)
    if not execution.series_loaded:
        raise ImplementationInvalid("MARKET_SERIES_NOT_LOADED")
    return _score_frame(
        segments,
        execution,
        draws=K.BOOT_DRAWS,
        seed=K.BOOT_SEED,
        min_rows=K.MIN_TRAIN_ROWS,
        min_weeks=K.MIN_TRAIN_WEEKS,
    )


def _primary_failed(primary: dict) -> bool:
    return (not primary.get("implementation_ok")) or primary.get("route") == K.ROUTE_INVALID


def _score_frame(segments: list[dict], execution: MarketExecution, *, draws: int, seed: int,
                 min_rows: int, min_weeks: int) -> dict:
    """Primary first. An invalid primary is returned as-is and does not start hourly."""
    from . import evaluate

    primary = evaluate.evaluate_frame(
        segments,
        draws=int(draws),
        seed=int(seed),
        min_rows=int(min_rows),
        min_weeks=int(min_weeks),
        cadence="primary_15m",
    )
    if _primary_failed(primary):
        report = build_report(execution, primary, hourly=None)
        report["hourly_diagnostic_ran"] = False
        report["stopped_before_hourly"] = True
        return report
    if execution.series_loaded and primary.get("stored_probabilities") is not None:
        execution.mark_scored(_SCORE_TOKEN)
    hourly = evaluate.evaluate_frame(
        segments,
        draws=int(draws),
        seed=int(seed),
        min_rows=int(min_rows),
        min_weeks=int(min_weeks),
        cadence="secondary_hourly",
    )
    report = build_report(execution, primary, hourly=hourly)
    report["hourly_diagnostic_ran"] = True
    report["stopped_before_hourly"] = False
    if _primary_failed(hourly) or hourly.get("route") is not None:
        report["hourly_diagnostic_failed"] = True
    return report


def begin_attempt(journal_dir: Path) -> None:
    """Claim the one-shot attempt before any model result is read.

    `O_EXCL` is the lock. A file left by an interrupted attempt refuses the next
    start. This function does not read `RESULT.json`.
    """
    directory = Path(journal_dir)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / "ATTEMPT.json"
    payload = json.dumps({
        "evidence_class": K.CLAIM_CEILING,
        "owner_go": bool(K.OWNER_GO),
        "started_before_model_results": True,
        "status": "STARTED",
        "unit": K.UNIT,
    }, indent=2, sort_keys=True) + "\n"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise SystemExit("REFUSING_RERUN") from exc
    try:
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def write_result(journal_dir: Path, report: dict) -> Path:
    """Atomically publish one result. The attempt lock stays in place."""
    directory = Path(journal_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "RESULT.json"
    temporary = directory / f".RESULT.{os.getpid()}.json.tmp"
    text = json.dumps(jsonable(report), indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return target


def _persist_failure(journal_dir: Path, reason: BaseException) -> None:
    report = build_report(MarketExecution())
    report["route"] = K.ROUTE_INVALID
    report["implementation_ok"] = False
    report["reason"] = str(reason)
    report["hourly_diagnostic_ran"] = False
    report["stopped_before_hourly"] = True
    try:
        write_result(journal_dir, report)
    except Exception:
        return


def execute_fixture_sequence(tables: dict, journal_dir: Path, *, draws: int, seed: int,
                             min_rows: int, min_weeks: int) -> dict:
    """Validate, score, and persist one prepared frame.

    The attempt is claimed before `evaluate_frame`. A second call raises
    `REFUSING_RERUN` and does not score again.
    """
    begin_attempt(journal_dir)
    try:
        segments = construct_segments(tables)
        execution = MarketExecution()
        report = _score_frame(
            segments,
            execution,
            draws=draws,
            seed=seed,
            min_rows=min_rows,
            min_weeks=min_weeks,
        )
        write_result(journal_dir, report)
        return report
    except Exception as exc:
        _persist_failure(journal_dir, exc)
        raise


def _guard_owner() -> None:
    if not K.OWNER_GO:
        raise SystemExit("AWAITING_OWNER_GO")


def _call_loader(fn):
    try:
        return fn()
    except SystemExit as exc:
        if str(exc) == "AWAITING_OWNER_GO":
            raise
        raise ImplementationInvalid(str(exc)) from exc


def load_pinned_grids(execution: MarketExecution | None = None) -> dict:
    """Read the three pinned sources. The owner check is the first statement."""
    _guard_owner()
    assert_core_snapshot(K.CORE_SNAPSHOT)
    require_digest(ROOT / K.BITMEX_SERIES, K.BITMEX_SHA256)
    require_digest(ROOT / K.BINANCE_SERIES, K.BINANCE_SHA256)
    from . import support

    grids = {
        "BITMEX_2016_2019": _call_loader(support._bitmex_grid),
        "BINANCE_2020_2024": _call_loader(support._core_grid),
        "BINANCE_2025_2026": _call_loader(support._modern_grid),
    }
    if execution is not None:
        execution.mark_loaded(_LOAD_TOKEN)
    return grids


def execute_pinned_market_fit(options: dict | None = None) -> dict:
    """Future market sequence. It returns before any price read while the go is off.

    After the go, the attempt file is created before prices are read and before
    `evaluate_frame`. An existing attempt returns `REFUSING_RERUN`.
    """
    _guard_owner()
    reject_overrides(options)
    assert_protocol_locked()
    assert_amendment_pinned()
    assert_pinned_census_coverage()
    begin_attempt(EXECUTION_JOURNAL)
    try:
        execution = MarketExecution()
        grids = load_pinned_grids(execution)
        tables = {name: adapt_segment(name, grids[name]) for name in SEGMENT_ORDER}
        segments, counts = validate_and_construct(tables)
        validate_coverage(counts)
        report = _score_frame(
            segments,
            execution,
            draws=K.BOOT_DRAWS,
            seed=K.BOOT_SEED,
            min_rows=K.MIN_TRAIN_ROWS,
            min_weeks=K.MIN_TRAIN_WEEKS,
        )
        write_result(EXECUTION_JOURNAL, report)
        return report
    except Exception as exc:
        _persist_failure(EXECUTION_JOURNAL, exc)
        raise
