"""One exploratory pass. The entry claims the journal before reading prices."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from scripts.research.dh1.data import load_binance_perp_5m
from scripts.research.owner_cards_r03.data import legal_months

from . import constants as K
from .evaluate import summarize, walk_forward
from .frame import build_frame
from .model import ImplementationInvalid, assign_verdict, brier, log_loss


ROOT = Path(__file__).resolve().parents[3]
JOURNAL = ROOT / K.JOURNAL


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_ids() -> list[str]:
    ids = []
    for line in (ROOT / K.MANIFEST).read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("snapshot_id:"):
            ids.append(stripped.split(":", 1)[1].strip().strip("'\""))
    return ids


def begin_attempt() -> None:
    JOURNAL.mkdir(parents=True, exist_ok=True)
    target = JOURNAL / "ATTEMPT.json"
    payload = json.dumps({
        "unit": K.UNIT,
        "status": "STARTED",
        "evidence_class": K.EVIDENCE_CLASS,
        "started_before_model_results": True,
    }, sort_keys=True).encode()
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise SystemExit("REFUSING_RERUN") from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def write_result(payload: dict) -> None:
    target = JOURNAL / "RESULT.json"
    temporary = JOURNAL / "RESULT.json.tmp"
    temporary.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True))
    os.replace(temporary, target)


def _failure_map(cells: list[dict]) -> list[dict]:
    popular = {"volatility_ratio", "range_compression", "volume", "range_position", "clock", "joint", "acceleration", "prior_return"}
    rows = []
    for cell in cells:
        if cell["family"] not in popular:
            continue
        lo = cell["interval_lo"]
        hi = cell["interval_hi"]
        covers_zero = lo is not None and hi is not None and lo <= 0.0 <= hi
        if cell["score"] == 0.0 or covers_zero or cell["low_n"]:
            rows.append({
                "cell": cell["cell"],
                "family": cell["family"],
                "n": cell["n"],
                "delta_vs_b1": cell["delta_vs_b1"],
                "score": cell["score"],
                "interval_lo": lo,
                "interval_hi": hi,
            })
    return rows


def _diagnostic_counts(bars: dict) -> list[dict]:
    rows = []
    for k in K.DIAGNOSTIC_K:
        frame = build_frame(bars, k=float(k))
        y = frame["y"]
        rows.append({
            "k": float(k),
            "kept": int(y.size),
            "impulse_rate": float(np.mean(y)),
            "ambiguous": int(frame["counts"]["ambiguous"]),
            "model_fit": False,
        })
    return rows


def execute() -> dict:
    begin_attempt()
    prices_loaded = False
    frame_built = False
    model_fit = False
    try:
        design_hash = _sha256(ROOT / K.DESIGN)
        if design_hash != K.DESIGN_SHA256:
            raise ImplementationInvalid("DESIGN_HASH_MISMATCH")
        if legal_months()[-1] != "2024-12":
            raise ImplementationInvalid("LEGAL_MONTHS_DRIFTED")
        if _snapshot_ids() != [K.CORE_SNAPSHOT, K.CORE_SNAPSHOT]:
            raise ImplementationInvalid("SNAPSHOT_MISMATCH")
        bars = load_binance_perp_5m()
        prices_loaded = True
        if np.any(np.asarray(bars["open_ms"]) >= K.SURFACE_END_MS):
            raise ImplementationInvalid("SURFACE_END_VIOLATION")
        taker = np.asarray(bars["taker_buy_quote"], dtype=np.float64)
        taker_coverage = float(np.mean(np.isfinite(taker)))
        frame = build_frame(bars, k=K.PRIMARY_K)
        frame_built = True
        if float(np.max(frame["p_geom"]) - np.min(frame["p_geom"])) > 1e-8:
            raise ImplementationInvalid("GEOMETRIC_PROBABILITY_NOT_CONSTANT")
        fitted = walk_forward(frame)
        model_fit = True
        summary = summarize(frame, fitted)
        pooled = summary["pooled"]
        boot = summary["bootstrap"]
        dev = summary["development_block"]
        diag = summary["diagnostic_block"]
        route = assign_verdict(
            pooled["delta_brier"], pooled["delta_logloss"], boot["brier_hi"], boot["logloss_hi"],
            summary["calibration_slope"],
            None if dev is None else dev["delta_brier"],
            None if diag is None else diag["delta_brier"],
            boot["valid_draws"], True,
        )
        ranked = [row for row in summary["cells"] if row["score"] > 0.0]
        successor = ranked[0]["cell"] if route == K.ROUTE_PROMISING and ranked else None
        predictions = summary.pop("predictions")
        episodes = summary.pop("catalog_episodes")
        np.savez_compressed(
            JOURNAL / "predictions.npz",
            close_ms=predictions["close_ms"], y=predictions["y"], p_b0=predictions["p_b0"],
            p_b1=predictions["p_b1"], p_candidate=predictions["p_candidate"], p_geom=predictions["p_geom"],
            week=predictions["week"], year=predictions["year"],
        )
        recomputed = {
            "brier_b0": brier(predictions["y"], predictions["p_b0"]),
            "brier_b1": brier(predictions["y"], predictions["p_b1"]),
            "brier_candidate": brier(predictions["y"], predictions["p_candidate"]),
            "logloss_b0": log_loss(predictions["y"], predictions["p_b0"]),
            "logloss_b1": log_loss(predictions["y"], predictions["p_b1"]),
            "logloss_candidate": log_loss(predictions["y"], predictions["p_candidate"]),
        }
        disagreement = {key: float(recomputed[key] - pooled[key]) for key in recomputed}
        report = {
            "unit": K.UNIT,
            "mode": K.MODE,
            "evidence_class": K.EVIDENCE_CLASS,
            "claim_ceiling": K.CLAIM_CEILING,
            "reopen_key": K.REOPEN_KEY,
            "product_integration_candidate": K.PRODUCT_INTEGRATION_CANDIDATE,
            "route": route,
            "implementation_ok": True,
            "reason": None,
            "prices_loaded": prices_loaded,
            "frame_built": frame_built,
            "model_fit": model_fit,
            "taker_in_model": False,
            "taker_coverage": taker_coverage,
            "design_sha256": design_hash,
            "core_snapshot": K.CORE_SNAPSHOT,
            "primary_k": K.PRIMARY_K,
            "p_geom": float(frame["p_geom"][0]),
            "frame_counts": frame["counts"],
            "kept_rows": int(frame["y"].size),
            "impulse_rate_kept": float(np.mean(frame["y"])),
            "scored_rows": summary["scored_n"],
            "n_folds": len(summary["folds"]),
            "pooled": pooled,
            "bootstrap": boot,
            "calibration_slope": summary["calibration_slope"],
            "calibration_intercept": summary["calibration_intercept"],
            "by_year": summary["by_year"],
            "development_block": dev,
            "diagnostic_block": diag,
            "practical": summary["practical"],
            "reliability": summary["reliability"],
            "cells": summary["cells"],
            "cell_count": len(summary["cells"]),
            "precursors": summary["precursors"],
            "catalog": summary["catalog_summary"],
            "catalog_episodes": episodes,
            "failure_map": _failure_map(summary["cells"]),
            "successor": successor,
            "diagnostic_k": _diagnostic_counts(bars),
            "recomputed": recomputed,
            "recompute_minus_stored": disagreement,
            "refit_inside_bootstrap": False,
            "regularization_added": False,
            "fallback_fit": False,
            "search_exposure": {
                "univariate_cells": 64,
                "joint_cells": 6,
                "diagnostic_k": 2,
                "model_comparison": 1,
                "material_cells": 73,
                "candidate_columns": len(K.CANDIDATE_FEATURES),
            },
        }
        write_result(report)
        return report
    except SystemExit:
        raise
    except Exception as exc:
        reason = exc.__class__.__name__ + ": " + str(exc)
        payload = {
            "unit": K.UNIT,
            "route": K.ROUTE_INVALID,
            "implementation_ok": False,
            "reason": reason,
            "prices_loaded": prices_loaded,
            "frame_built": frame_built,
            "model_fit": model_fit,
            "evidence_class": K.EVIDENCE_CLASS,
            "claim_ceiling": K.CLAIM_CEILING,
        }
        try:
            write_result(payload)
        except Exception:
            pass
        if isinstance(exc, ImplementationInvalid):
            return payload
        raise
