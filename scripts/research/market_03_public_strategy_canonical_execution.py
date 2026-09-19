#!/usr/bin/env python3
"""MARKET-03 one-shot canonical execution wrapper.

Lifecycle plumbing only. Scientific signals, wallet, MDD, and
classification remain in the frozen lib. This module authenticates,
consumes the unused reservation, loads bound snapshots after hash
verification, calls frozen scientific functions once, and seals RESULT.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from scripts.research.market_03_public_strategy_arm_authority import (
    ARM_JSON_REL,
    ARM_JSON_SHA256,
    ARM_MD_SHA256,
    AUTHORITY_SHA256,
    B2_06_EXECUTION_AUTHORIZED,
    CANONICAL_EXECUTIONS_AUTHORIZED,
    CANONICAL_EXECUTIONS_CONSUMED,
    EVALUATION_END_EXCLUSIVE,
    EVALUATION_START_INCLUSIVE,
    EXECUTE_SHA256,
    EXTERNAL_COMMIT,
    EXTERNAL_TREE,
    FROZEN_IMPLEMENTATION_HEAD,
    FROZEN_IMPLEMENTATION_TREE,
    FROZEN_MARKET_03_RUN_IDENTITY,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    FUNDING_DATA_SHA256,
    FUNDING_DATASET_ID,
    FUNDING_SNAPSHOT_ID,
    IMPL_FREEZE_JSON_SHA256,
    IMPL_FREEZE_MD_SHA256,
    LIB_SHA256,
    PROTECTED_OOS_AUTHORIZED,
    PROTECTED_OOS_START,
    REPLICATION_LEVEL,
    RESEARCH_ID,
    RESERVATION_JSON_REL,
    RESERVATION_JSON_SHA256,
    SPOT_DATA_SHA256,
    SPOT_DATASET_ID,
    SPOT_SNAPSHOT_ID,
    WARMUP_END_EXCLUSIVE,
    WARMUP_START_INCLUSIVE,
    authenticate_market_03_canonical_execution,
    canonical_json_bytes,
    consume_authorization_atomically,
    reject_protected_oos_extension,
    sha256_file,
)
from scripts.research.market_03_public_strategy_authority import (
    inspect_market_03_authorization_state,
)
from scripts.research.market_03_public_strategy_lib import (
    AUTHOR_MDD_BASELINE,
    AUTHOR_MDD_FILTERED,
    INITIAL_CAPITAL_USDT,
    advise_signals,
    classify_primary,
    descriptive_magnitude,
    mdd_from_daily_equity,
    require_frozen_indicator_origin_coverage,
    restrict_candles_to_indicator_origin,
    simulate_strategy,
    funding_series_from_observations,
)


REPO = Path(__file__).resolve().parents[2]
ARMED_HEAD = "e3c5de3bcb68173af0bfb08a8c42f4a5e8981c5a"
ARMED_TREE = "95af1b525c938117c0a17778283116d09bd1d84d"
SPOT_JSONL_REL = (
    "artifacts/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/"
    "canonical/BTCUSDT_SPOT_1h.jsonl"
)
FUNDING_JSONL_REL = (
    "artifacts/research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0/"
    "canonical/BTCUSDT_UM_fundingRate.jsonl"
)
LOCK_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_CONSUMPTION_LOCK.json"
RESULT_JSON_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.json"
RESULT_MD_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.md"
FAILURE_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_EXECUTION_FAILURE.json"
PROTECTED_OOS_MS = 1_735_689_600_000
EXPECTED_SPOT_ROWS = 47477
EXPECTED_FUNDING_ROWS = 5819


class PreConsumptionBlocker(RuntimeError):
    """Authority or bound-data failure before outcome-bearing evaluation."""


class Market03CanonicalExecutionReserved(RuntimeError):
    def __init__(
        self,
        message: str = "MARKET_03_CANONICAL_EXECUTION_RESERVED_FOR_EXECUTION_UNIT",
    ) -> None:
        super().__init__(message)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> str:
    raw = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return _sha256_bytes(raw)


def require_armed_head() -> None:
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    if head != ARMED_HEAD or tree != ARMED_TREE:
        raise PreConsumptionBlocker(
            f"MARKET_03_ARM_HEAD_MISMATCH:{head}/{tree}"
        )


def authenticate_pre_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or kwargs:
        raise PreConsumptionBlocker(
            "caller arguments cannot redefine MARKET-03 canonical execution"
        )
    try:
        bound = authenticate_market_03_canonical_execution()
    except Exception as exc:
        raise PreConsumptionBlocker(str(exc)) from exc
    reservation = bound["reservation"]
    if int(reservation["CANONICAL_EXECUTIONS_AUTHORIZED"]) != 1:
        raise PreConsumptionBlocker("MARKET_03_RESERVATION_AUTHORIZED_MISMATCH")
    if int(reservation["CANONICAL_EXECUTIONS_CONSUMED"]) != 0:
        raise PreConsumptionBlocker("MARKET_03_RESERVATION_ALREADY_CONSUMED")
    if CANONICAL_EXECUTIONS_AUTHORIZED != 1:
        raise PreConsumptionBlocker("MARKET_03_ARM_MODULE_AUTHORIZED_MISMATCH")
    if CANONICAL_EXECUTIONS_CONSUMED != 0:
        raise PreConsumptionBlocker("MARKET_03_ARM_MODULE_ALREADY_CONSUMED")
    if B2_06_EXECUTION_AUTHORIZED is not False:
        raise PreConsumptionBlocker("MARKET_03_B2_06_MUTATED")
    if PROTECTED_OOS_AUTHORIZED is not False:
        raise PreConsumptionBlocker("MARKET_03_PROTECTED_OOS_MUTATED")
    if bound["run_identity"] != FROZEN_MARKET_03_RUN_IDENTITY:
        raise PreConsumptionBlocker("MARKET_03_RUN_IDENTITY_MISMATCH")
    reject_protected_oos_extension(EVALUATION_END_EXCLUSIVE)
    frozen = inspect_market_03_authorization_state()
    if frozen["MARKET_03_ARMED"] is not False:
        raise PreConsumptionBlocker("MARKET_03_FROZEN_AUTHORITY_MUST_REMAIN_UNARMED")
    lock_path = REPO / LOCK_REL
    if lock_path.exists():
        raise PreConsumptionBlocker("MARKET_03_CONSUMPTION_LOCK_ALREADY_PRESENT")
    if (REPO / RESULT_JSON_REL).exists():
        raise PreConsumptionBlocker("MARKET_03_RESULT_ALREADY_PRESENT")
    return bound


def permit_canonical_scientific_execution(
    *args: Any, **kwargs: Any
) -> dict[str, Any]:
    bound = authenticate_pre_execution(*args, **kwargs)
    return {
        "permitted": True,
        "consumed": False,
        "run_identity": bound["run_identity"],
        "CANONICAL_EXECUTIONS_AUTHORIZED": 1,
        "CANONICAL_EXECUTIONS_CONSUMED": 0,
        "scientific_evaluation_reserved": True,
        "bound_rows_loaded": False,
    }


def evaluate_bound_after_arm_consumption(
    *args: Any, **kwargs: Any
) -> Mapping[str, Any]:
    """Kept as the ARM-era reserved stub. Live one-shot uses execute_once."""
    raise Market03CanonicalExecutionReserved(
        "MARKET_03_BOUND_SCIENTIFIC_EVALUATION_RESERVED_FOR_EXECUTION_UNIT"
    )


def run_canonical_market_03(*args: Any, **kwargs: Any) -> int:
    """ARM-era auth-only path. Does not consume or evaluate."""
    if args or kwargs:
        print(
            "caller arguments cannot redefine MARKET-03 canonical execution",
            file=sys.stderr,
        )
        return 2
    try:
        permit = permit_canonical_scientific_execution()
    except PreConsumptionBlocker as exc:
        print(f"PRE_CONSUMPTION_BLOCKER:{exc}", file=sys.stderr)
        return 3
    print("PRE_EXECUTION_AUTH_OK", file=sys.stderr)
    print(f"RUN_IDENTITY={permit['run_identity']}", file=sys.stderr)
    print("CANONICAL_EXECUTIONS_AUTHORIZED=1", file=sys.stderr)
    print("CANONICAL_EXECUTIONS_CONSUMED=0", file=sys.stderr)
    print(
        "MARKET_03_CANONICAL_EXECUTION_RESERVED_FOR_EXECUTION_UNIT",
        file=sys.stderr,
    )
    return 0


def write_consumption_lock() -> str:
    payload = {
        "schema": "market_03_public_strategy_consumption_lock",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "canonical_run_identity": FROZEN_MARKET_03_RUN_IDENTITY,
        "arm_artifact_sha256_unused": ARM_JSON_SHA256,
        "reservation_sha256_unused": RESERVATION_JSON_SHA256,
        "arm_head": ARMED_HEAD,
        "arm_tree": ARMED_TREE,
        "CANONICAL_EXECUTIONS_AUTHORIZED": 1,
        "CANONICAL_EXECUTIONS_CONSUMED": 1,
        "consumption_boundary": "BEFORE_OUTCOME_BEARING_FROZEN_SCIENTIFIC_CALL",
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": False,
        "not_a_scientific_result": True,
        "written_at_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return _write_json(REPO / LOCK_REL, payload)


def load_bound_spot() -> tuple[pd.DataFrame, dict[str, Any]]:
    path = REPO / SPOT_JSONL_REL
    if not path.is_file():
        raise PreConsumptionBlocker("MARKET_03_SPOT_JSONL_MISSING")
    digest = sha256_file(path)
    if digest != SPOT_DATA_SHA256:
        raise PreConsumptionBlocker("MARKET_03_SPOT_DATA_SHA256_MISMATCH")
    opens: list[int] = []
    dates: list[pd.Timestamp] = []
    ohlcv = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    max_ms = -1
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            open_ms = int(row["open_time_ms"])
            if open_ms >= PROTECTED_OOS_MS:
                raise PreConsumptionBlocker(
                    f"MARKET_03_SPOT_PROTECTED_OOS:{open_ms}"
                )
            max_ms = max(max_ms, open_ms)
            opens.append(open_ms)
            dates.append(pd.Timestamp(open_ms, unit="ms", tz="UTC"))
            ohlcv["open"].append(float(row["open"]))
            ohlcv["high"].append(float(row["high"]))
            ohlcv["low"].append(float(row["low"]))
            ohlcv["close"].append(float(row["close"]))
            ohlcv["volume"].append(float(row["volume"]))
    if len(opens) != EXPECTED_SPOT_ROWS:
        raise PreConsumptionBlocker(f"MARKET_03_SPOT_ROW_COUNT_MISMATCH:{len(opens)}")
    if max_ms >= PROTECTED_OOS_MS:
        raise PreConsumptionBlocker("MARKET_03_SPOT_REACHED_2025")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": np.asarray(ohlcv["open"], dtype=np.float64),
            "high": np.asarray(ohlcv["high"], dtype=np.float64),
            "low": np.asarray(ohlcv["low"], dtype=np.float64),
            "close": np.asarray(ohlcv["close"], dtype=np.float64),
            "volume": np.asarray(ohlcv["volume"], dtype=np.float64),
        }
    )
    meta = {
        "n_rows": int(len(frame)),
        "sha256": digest,
        "first_open_time_utc": dates[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_open_time_utc": dates[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_open_time_ms": int(max_ms),
        "protected_oos_opened": False,
    }
    return frame, meta


def load_bound_funding() -> tuple[pd.Series, dict[str, Any]]:
    path = REPO / FUNDING_JSONL_REL
    if not path.is_file():
        raise PreConsumptionBlocker("MARKET_03_FUNDING_JSONL_MISSING")
    digest = sha256_file(path)
    if digest != FUNDING_DATA_SHA256:
        raise PreConsumptionBlocker("MARKET_03_FUNDING_DATA_SHA256_MISMATCH")
    times: list[int] = []
    rates: list[float] = []
    max_ms = -1
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("symbol") not in (None, "BTCUSDT"):
                raise PreConsumptionBlocker("MARKET_03_FUNDING_SYMBOL_MISMATCH")
            time_ms = int(row["fundingTime"])
            if time_ms >= PROTECTED_OOS_MS:
                raise PreConsumptionBlocker(
                    f"MARKET_03_FUNDING_PROTECTED_OOS:{time_ms}"
                )
            max_ms = max(max_ms, time_ms)
            times.append(time_ms)
            rates.append(float(row["fundingRate"]))
    if len(times) != EXPECTED_FUNDING_ROWS:
        raise PreConsumptionBlocker(
            f"MARKET_03_FUNDING_ROW_COUNT_MISMATCH:{len(times)}"
        )
    if max_ms >= PROTECTED_OOS_MS:
        raise PreConsumptionBlocker("MARKET_03_FUNDING_REACHED_2025")
    series = funding_series_from_observations(times, rates)
    meta = {
        "n_rows": int(len(series)),
        "sha256": digest,
        "first_fundingTime_utc": series.index[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_fundingTime_utc": series.index[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_fundingTime_ms": int(max_ms),
        "b2_06_opened": False,
        "protected_oos_opened": False,
    }
    return series, meta


def _time_in_market_hours(trades: list[Any]) -> float:
    total = 0.0
    for trade in trades:
        if trade.close_date is None:
            continue
        delta = pd.Timestamp(trade.close_date) - pd.Timestamp(trade.open_date)
        total += float(delta.total_seconds()) / 3600.0
    return total


def run_frozen_scientific(
    candles: pd.DataFrame,
    funding: pd.Series,
) -> dict[str, Any]:
    restricted = restrict_candles_to_indicator_origin(candles)
    require_frozen_indicator_origin_coverage(restricted)
    if restricted["date"].max() >= pd.Timestamp(PROTECTED_OOS_START):
        raise PreConsumptionBlocker("MARKET_03_RESTRICTED_CANDLES_REACHED_OOS")
    baseline_advised = advise_signals(restricted, "baseline", funding=None)
    filtered_advised = advise_signals(restricted, "filtered", funding=funding)
    if not np.array_equal(
        np.asarray(baseline_advised["exit_long"]),
        np.asarray(filtered_advised["exit_long"]),
    ):
        raise PreConsumptionBlocker("MARKET_03_FUNDING_FILTER_MUTATED_EXITS")
    base_sim = simulate_strategy(
        baseline_advised,
        variant="baseline",
        origin="canonical",
        evaluation_start=EVALUATION_START_INCLUSIVE,
        evaluation_end=EVALUATION_END_EXCLUSIVE,
    )
    filt_sim = simulate_strategy(
        filtered_advised,
        variant="filtered",
        origin="canonical",
        evaluation_start=EVALUATION_START_INCLUSIVE,
        evaluation_end=EVALUATION_END_EXCLUSIVE,
    )
    mdd_b = mdd_from_daily_equity(base_sim.daily_equity)
    mdd_f = mdd_from_daily_equity(filt_sim.daily_equity)
    primary = classify_primary(mdd_f, mdd_b)
    magnitude = None
    if mdd_b is not None and mdd_f is not None:
        magnitude = descriptive_magnitude(mdd_f, mdd_b)
    baseline_entries = int((baseline_advised["enter_long"] == 1).sum())
    filtered_entries = int((filtered_advised["enter_long"] == 1).sum())
    rejected = int(
        ((baseline_advised["enter_long"] == 1) & (filtered_advised["enter_long"] == 0)).sum()
    )
    last_base = (
        float(base_sim.daily_equity.iloc[-1]) if len(base_sim.daily_equity) else None
    )
    last_filt = (
        float(filt_sim.daily_equity.iloc[-1]) if len(filt_sim.daily_equity) else None
    )
    return {
        "primary_classification": primary,
        "mdd_baseline": mdd_b,
        "mdd_filtered": mdd_f,
        "magnitude_descriptive": magnitude,
        "baseline": {
            "metrics": dict(base_sim.metrics),
            "trade_count": len(base_sim.trades),
            "n_signals_entry": base_sim.n_signals_entry,
            "n_signals_exit": base_sim.n_signals_exit,
            "force_exited": base_sim.force_exited,
            "final_daily_equity": last_base,
            "time_in_market_hours": _time_in_market_hours(base_sim.trades),
        },
        "filtered": {
            "metrics": dict(filt_sim.metrics),
            "trade_count": len(filt_sim.trades),
            "n_signals_entry": filt_sim.n_signals_entry,
            "n_signals_exit": filt_sim.n_signals_exit,
            "force_exited": filt_sim.force_exited,
            "final_daily_equity": last_filt,
            "time_in_market_hours": _time_in_market_hours(filt_sim.trades),
        },
        "funding_filter_entries_rejected": rejected,
        "baseline_entry_signals": baseline_entries,
        "filtered_entry_signals": filtered_entries,
        "n_restricted_candles": int(len(restricted)),
        "first_restricted_date": restricted["date"].iloc[0].strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "last_restricted_date": restricted["date"].iloc[-1].strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "max_scientifically_consumed_market_timestamp": restricted["date"]
        .max()
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "initial_capital_usdt": INITIAL_CAPITAL_USDT,
    }


def bind_canonical_result(
    scientific: Mapping[str, Any],
    *,
    lock_sha256: str,
    spot_meta: Mapping[str, Any],
    funding_meta: Mapping[str, Any],
    consumed: Mapping[str, str],
) -> dict[str, Any]:
    mdd_b = scientific["mdd_baseline"]
    mdd_f = scientific["mdd_filtered"]
    magnitude = scientific.get("magnitude_descriptive") or {}
    return {
        "schema": "market_03_public_strategy_canonical_result",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "MARKET_03_PHASE": "RESULT",
        "status": "CANONICAL_RESULT",
        "canonical_run_identity": FROZEN_MARKET_03_RUN_IDENTITY,
        "arm_head": ARMED_HEAD,
        "arm_tree": ARMED_TREE,
        "arm_md_sha256_unused": ARM_MD_SHA256,
        "arm_json_sha256_unused": ARM_JSON_SHA256,
        "reservation_sha256_unused": RESERVATION_JSON_SHA256,
        "arm_sha256_consumed": consumed["arm_sha256_consumed"],
        "reservation_sha256_consumed": consumed["reservation_sha256_consumed"],
        "consumption_lock_sha256": lock_sha256,
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "implementation_freeze_md_sha256": IMPL_FREEZE_MD_SHA256,
        "implementation_freeze_json_sha256": IMPL_FREEZE_JSON_SHA256,
        "frozen_implementation_head": FROZEN_IMPLEMENTATION_HEAD,
        "frozen_implementation_tree": FROZEN_IMPLEMENTATION_TREE,
        "lib_sha256": LIB_SHA256,
        "authority_sha256": AUTHORITY_SHA256,
        "execute_sha256": EXECUTE_SHA256,
        "external_commit": EXTERNAL_COMMIT,
        "external_tree": EXTERNAL_TREE,
        "replication_level": REPLICATION_LEVEL,
        "spot_dataset_id": SPOT_DATASET_ID,
        "spot_snapshot_id": SPOT_SNAPSHOT_ID,
        "spot_data_sha256": SPOT_DATA_SHA256,
        "funding_dataset_id": FUNDING_DATASET_ID,
        "funding_snapshot_id": FUNDING_SNAPSHOT_ID,
        "funding_data_sha256": FUNDING_DATA_SHA256,
        "warmup_start_inclusive": WARMUP_START_INCLUSIVE,
        "warmup_end_exclusive": WARMUP_END_EXCLUSIVE,
        "evaluation_start_inclusive": EVALUATION_START_INCLUSIVE,
        "evaluation_end_exclusive": EVALUATION_END_EXCLUSIVE,
        "spot_load": dict(spot_meta),
        "funding_load": dict(funding_meta),
        "CANONICAL_EXECUTIONS_AUTHORIZED": 1,
        "CANONICAL_EXECUTIONS_CONSUMED": 1,
        "MARKET_03_ARMED": True,
        "MARKET_03_STRATEGY_EXECUTED": True,
        "MARKET_03_OUTCOMES_INSPECTED": True,
        "MARKET_03_PARAMETER_SEARCH": False,
        "PROTECTED_OOS_AUTHORIZED": False,
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": False,
        "rerun_occurred": False,
        "primary_classification": scientific["primary_classification"],
        "mdd_baseline": mdd_b,
        "mdd_filtered": mdd_f,
        "baseline_mdd_magnitude": None if mdd_b is None else abs(float(mdd_b)),
        "filtered_mdd_magnitude": None if mdd_f is None else abs(float(mdd_f)),
        "mdd_absolute_pp_change": magnitude.get("OBS_ABS_REDUCTION_PP"),
        "mdd_relative_magnitude_change": magnitude.get("OBS_REL_REDUCTION"),
        "author_headline_descriptive_only": {
            "author_mdd_baseline": AUTHOR_MDD_BASELINE,
            "author_mdd_filtered": AUTHOR_MDD_FILTERED,
            "author_mdd_baseline_magnitude": 0.494,
            "author_mdd_filtered_magnitude": 0.338,
            "author_abs_reduction_pp": 15.6,
            "author_rel_reduction": 0.3157894736842105,
        },
        "magnitude_descriptive": dict(magnitude) if magnitude else None,
        "baseline": dict(scientific["baseline"]),
        "filtered": dict(scientific["filtered"]),
        "funding_filter_entries_rejected": scientific["funding_filter_entries_rejected"],
        "baseline_entry_signals": scientific["baseline_entry_signals"],
        "filtered_entry_signals": scientific["filtered_entry_signals"],
        "n_restricted_candles": scientific["n_restricted_candles"],
        "first_restricted_date": scientific["first_restricted_date"],
        "last_restricted_date": scientific["last_restricted_date"],
        "max_scientifically_consumed_market_timestamp": scientific[
            "max_scientifically_consumed_market_timestamp"
        ],
        "initial_capital_usdt": scientific["initial_capital_usdt"],
        "execution_head": "UNSET_UNTIL_THIS_COMMIT",
        "execution_tree": "UNSET_UNTIL_THIS_COMMIT",
    }


def write_result_markdown(payload: Mapping[str, Any]) -> str:
    mdd_b = payload["mdd_baseline"]
    mdd_f = payload["mdd_filtered"]
    primary = payload["primary_classification"]
    base = payload["baseline"]
    filt = payload["filtered"]
    text = f"""# MARKET-03 PUBLIC STRATEGY — canonical RESULT

- **Status:** `RESULT`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_RESULT`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Date:** 2026-09-19

Canonical machine-readable twin:
`docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.json`.

This document restates the sealed mechanical classification. It does
not reinterpret it. Magnitude figures are descriptive only.

```text
PRIMARY_CLASSIFICATION = {primary}
CANONICAL_EXECUTIONS_AUTHORIZED = 1
CANONICAL_EXECUTIONS_CONSUMED = 1
MARKET_03_STRATEGY_EXECUTED = YES
MARKET_03_OUTCOMES_INSPECTED = YES
MARKET_03_PARAMETER_SEARCH = NO
PROTECTED_OOS_TOUCHED = NO
B2_06_EXECUTION_AUTHORIZED = NO
```

```text
RUN_IDENTITY = {payload["canonical_run_identity"]}
ARM_HEAD = {payload["arm_head"]}
ARM_TREE = {payload["arm_tree"]}
ARM_MD_SHA256_UNUSED = {payload["arm_md_sha256_unused"]}
ARM_JSON_SHA256_UNUSED = {payload["arm_json_sha256_unused"]}
```

```text
MDD_BASELINE = {mdd_b}
MDD_FILTERED = {mdd_f}
BASELINE_MDD_MAGNITUDE = {payload["baseline_mdd_magnitude"]}
FILTERED_MDD_MAGNITUDE = {payload["filtered_mdd_magnitude"]}
MDD_ABSOLUTE_PP_CHANGE = {payload["mdd_absolute_pp_change"]}
MDD_RELATIVE_MAGNITUDE_CHANGE = {payload["mdd_relative_magnitude_change"]}
BASELINE_TRADES = {base["trade_count"]}
FILTERED_TRADES = {filt["trade_count"]}
```

Frozen author headline (descriptive context only; not a gate):

```text
author baseline MDD magnitude = 49.4%
author filtered MDD magnitude = 33.8%
author absolute reduction = 15.6 percentage points
author relative reduction ≈ 31.6%
```

Supporting descriptives from the same frozen run:

```text
BASELINE_TOTAL_RETURN = {base["metrics"].get("Total return")}
FILTERED_TOTAL_RETURN = {filt["metrics"].get("Total return")}
BASELINE_FINAL_DAILY_EQUITY = {base["final_daily_equity"]}
FILTERED_FINAL_DAILY_EQUITY = {filt["final_daily_equity"]}
BASELINE_TIME_IN_MARKET_HOURS = {base["time_in_market_hours"]}
FILTERED_TIME_IN_MARKET_HOURS = {filt["time_in_market_hours"]}
FUNDING_FILTER_ENTRIES_REJECTED = {payload["funding_filter_entries_rejected"]}
MAX_CONSUMED_MARKET_TIMESTAMP = {payload["max_scientifically_consumed_market_timestamp"]}
```

`REPRODUCED_DIRECTION` means only: finite signed
`MDD_filtered > MDD_baseline` on the frozen interval. It does not
authorize current alpha, live profitability, causal funding effect,
independent replication, OOS confirmation, or a second run.

No rerun is authorized.
"""
    path = REPO / RESULT_MD_REL
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return _sha256_bytes(text.encode("utf-8"))


def seal_result(payload: Mapping[str, Any]) -> str:
    digest = _write_json(REPO / RESULT_JSON_REL, payload)
    sidecar = (REPO / RESULT_JSON_REL).with_suffix(".json.sha256")
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return digest


def write_post_consumption_failure(exc: BaseException, lock_sha256: str | None) -> str:
    payload = {
        "schema": "market_03_public_strategy_execution_failure",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "canonical_run_identity": FROZEN_MARKET_03_RUN_IDENTITY,
        "consumption_lock_sha256": lock_sha256,
        "CANONICAL_EXECUTIONS_CONSUMED": 1,
        "rerun_occurred": False,
        "PROTECTED_OOS_TOUCHED": False,
        "B2_06_EXECUTION_AUTHORIZED": False,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
        "adjudication_required": True,
    }
    return _write_json(REPO / FAILURE_REL, payload)


def execute_authorized_canonical_market_03() -> int:
    try:
        require_armed_head()
        authenticate_pre_execution()
        print("PRE_EXECUTION_AUTH_OK", file=sys.stderr)
        spot, spot_meta = load_bound_spot()
        print("BOUND_SPOT_AUTH_OK", file=sys.stderr)
        funding, funding_meta = load_bound_funding()
        print("BOUND_FUNDING_AUTH_OK", file=sys.stderr)
    except PreConsumptionBlocker as exc:
        print(f"PRE_CONSUMPTION_BLOCKER:{exc}", file=sys.stderr)
        return 3

    lock_sha256 = write_consumption_lock()
    print(f"CONSUMPTION_BOUNDARY_ENTERED lock_sha256={lock_sha256}", file=sys.stderr)
    consumed = consume_authorization_atomically()
    print("RESERVATION_CONSUMED", file=sys.stderr)
    scientific: dict[str, Any] | None = None
    post_exc: BaseException | None = None
    try:
        scientific = run_frozen_scientific(spot, funding)
    except BaseException as exc:  # noqa: BLE001 - consume even on failure
        post_exc = exc
    if post_exc is not None:
        failure_sha = write_post_consumption_failure(post_exc, lock_sha256)
        print(f"POST_CONSUMPTION_FAILURE sha256={failure_sha}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 4
    assert scientific is not None
    package = bind_canonical_result(
        scientific,
        lock_sha256=lock_sha256,
        spot_meta=spot_meta,
        funding_meta=funding_meta,
        consumed=consumed,
    )
    result_sha = seal_result(package)
    md_sha = write_result_markdown(package)
    print(f"RESULT_SEALED path={RESULT_JSON_REL} sha256={result_sha}", file=sys.stderr)
    print(f"RESULT_MD_SHA256={md_sha}", file=sys.stderr)
    print(f"PRIMARY_CLASSIFICATION={package['primary_classification']}", file=sys.stderr)
    print(f"MDD_BASELINE={package['mdd_baseline']}", file=sys.stderr)
    print(f"MDD_FILTERED={package['mdd_filtered']}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else []
    if args == ["--execute-once"]:
        return execute_authorized_canonical_market_03()
    if args:
        print(
            "caller arguments cannot redefine MARKET-03 canonical execution",
            file=sys.stderr,
        )
        return 2
    return run_canonical_market_03()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
