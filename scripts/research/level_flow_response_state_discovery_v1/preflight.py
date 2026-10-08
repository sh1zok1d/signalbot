"""Outcome-blind census, scaler and state partition. No barrier label is read."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.owner_cards_r03 import data as RD

from . import cluster, constants as K
from .cohort import assemble, population, predictors_ok
from .inference import freeze_activity
from .oi import load_bound_oi

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1_PREFLIGHT.json"

PARITY_KEYS = (
    "real_legitimate",
    "predictor_complete",
    "training_digest",
    "selected_k",
    "centroid_hex",
    "scaler_hex",
    "state_counts",
    "selected_silhouette_hex",
    "selected_ari_hex",
    "activity_hex",
)


def _py(value):
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if not math.isfinite(number) else number
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return _py(value.tolist())
    return value


def _hex(value) -> str | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value).hex()


def _corr(raw: np.ndarray) -> list[list[float | None]]:
    out = []
    for i in range(raw.shape[1]):
        row = []
        for j in range(raw.shape[1]):
            if raw.shape[0] < 3:
                row.append(None)
                continue
            a = raw[:, i]
            b = raw[:, j]
            if float(a.std()) == 0.0 or float(b.std()) == 0.0:
                row.append(None)
            else:
                row.append(float(np.corrcoef(a, b)[0, 1]))
        out.append(row)
    return out


def _diagnose(z: np.ndarray, k: int) -> dict:
    fitted = cluster.fit_kmeans(z, k)
    if fitted is None:
        return {
            "k": int(k), "passes_size": False, "silhouette": None, "median_ari": None,
            "min_n": 0, "min_share": 0.0, "counts": [], "inertia": None, "init": None,
            "median_jaccard": [],
        }
    sizes = cluster.size_report(fitted["labels"])
    sil = cluster.silhouette(z, fitted["labels"])
    stable = cluster.stability(z, fitted["labels"], k)
    return {
        "k": int(k),
        "passes_size": sizes["passes_size"],
        "silhouette": sil,
        "median_ari": stable["median_ari"],
        "median_jaccard": stable["median_jaccard"],
        "min_n": sizes["min_n"],
        "min_share": sizes["min_share"],
        "counts": sizes["counts"],
        "shares": sizes["shares"],
        "inertia": fitted["inertia"],
        "init": fitted["init"],
    }


def discover(rows: list[dict]) -> dict:
    """Fit the scaler and choose K. Raises on a zero IQR."""
    raw = cluster.matrix_of(rows)
    scaler = cluster.fit_scaler(raw)
    z, clipped = cluster.transform(raw, scaler)
    diagnostics = [_diagnose(z, k) for k in K.K_GRID]
    chosen = cluster.select_k(diagnostics)
    model = None
    if chosen is not None:
        fitted = cluster.fit_kmeans(z, int(chosen["k"]))
        if fitted is None:
            raise RuntimeError("selected K failed to refit")
        labels = [cluster.state_name(int(v)) for v in fitted["labels"]]
        counts = dict(Counter(labels))
        ordered = [cluster.state_name(i) for i in range(int(chosen["k"]))]
        model = {
            "k": int(chosen["k"]),
            "centroids": fitted["centroids"].tolist(),
            "centroid_hex": [cluster.hex_list(row) for row in fitted["centroids"]],
            "descriptions": [cluster.describe_centroid(row.tolist()) for row in fitted["centroids"]],
            "state_names": ordered,
            "state_counts": [int(counts.get(name, 0)) for name in ordered],
            "labels": labels,
            "silhouette": chosen["silhouette"],
            "median_ari": chosen["median_ari"],
            "median_jaccard": chosen["median_jaccard"],
            "init": fitted["init"],
        }
    return {
        "scaler": scaler,
        "clipped_counts": clipped.tolist(),
        "correlations": _corr(raw),
        "diagnostics": diagnostics,
        "model": model,
        "training_digest": cluster.row_digest(rows),
    }


def summarize(bars, oi, oi_meta: dict, built: dict | None = None) -> dict:
    built = population(bars) if built is None else built
    assembled = assemble(bars, oi, built)
    real = assembled["real_rows"]
    training = [row for row in real if predictors_ok(row)]
    digest = RD.btc_dataset_digest()
    if digest != K.CORE_ZIP_LIST_SHA256:
        raise RuntimeError("CORE zip-list digest drifted")
    discovered = discover(training) if training else {"model": None, "diagnostics": [], "scaler": None,
                                                      "clipped_counts": [], "correlations": [], "training_digest": None}
    model = discovered["model"]
    activity_rows = [row for row in training if row.get("nuisance_ok")]
    activity = freeze_activity(activity_rows)
    pseudo_assigned = 0
    if model is not None:
        centroids = np.asarray(model["centroids"], dtype=float)
        for pair in assembled["pairs"]:
            pseudo = pair["pseudo"]
            if not predictors_ok(pseudo):
                continue
            raw = cluster.matrix_of([pseudo])
            z, _outside = cluster.transform(raw, discovered["scaler"])
            label = int(cluster.assign_nearest(z, centroids)[0])
            if cluster.state_name(label) in model["state_names"]:
                pseudo_assigned += 1
    opens = [int(row["open_ms"]) for row in training]
    body = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_blind": True,
        "proceed_to_outcomes": model is not None,
        "blocked_reason": None if model is not None else "NO_STABLE_PREDICTOR_STATE_PARTITION",
        "core": {
            "dataset_id": K.CORE_DATASET_ID,
            "zip_list_sha256": digest,
            "bars": int(bars.n),
            "t0": int(bars.t0),
            "end_ms": int(bars.end_ms),
        },
        "oi": oi_meta,
        "event_window": {"start": K.EVENT_START, "end_exclusive": K.EVENT_END},
        "structural_episodes": assembled["structural_episodes"],
        "real_status": assembled["real_status"],
        "pseudo_status": assembled["pseudo_status"],
        "real_legitimate": assembled["real_status"]["LEGITIMATE"],
        "pseudo_legitimate": assembled["pseudo_status"]["LEGITIMATE"],
        "geometry_pairs": len(assembled["pairs"]),
        "predictor_complete": len(training),
        "nuisance_complete": len(activity_rows),
        "first_open_ms": int(min(opens)) if opens else None,
        "last_open_ms": int(max(opens)) if opens else None,
        "counts": {
            "epoch": dict(Counter(row["epoch"] for row in training)),
            "family": dict(Counter(row["family"] for row in training)),
            "side": dict(Counter(int(row["side"]) for row in training)),
        },
        "correlations": discovered["correlations"],
        "feature_names": list(K.FEATURES),
        "scaler": discovered["scaler"],
        "scaler_hex": None if discovered["scaler"] is None else {
            "median": cluster.hex_list(discovered["scaler"]["median"]),
            "iqr": cluster.hex_list(discovered["scaler"]["iqr"]),
        },
        "clipped_counts": discovered["clipped_counts"],
        "diagnostics": discovered["diagnostics"],
        "selected_k": None if model is None else model["k"],
        "centroid_hex": None if model is None else model["centroid_hex"],
        "centroids": None if model is None else model["centroids"],
        "descriptions": None if model is None else model["descriptions"],
        "state_names": None if model is None else model["state_names"],
        "state_counts": None if model is None else model["state_counts"],
        "selected_silhouette_hex": None if model is None else _hex(model["silhouette"]),
        "selected_ari_hex": None if model is None else _hex(model["median_ari"]),
        "median_jaccard": None if model is None else model["median_jaccard"],
        "training_digest": discovered["training_digest"],
        "pseudo_assigned": pseudo_assigned,
        "activity": activity,
        "activity_hex": {"mean": _hex(activity["mean"]), "sd": _hex(activity["sd"])},
        "kmeans": {
            "seed": K.KMEANS_SEED,
            "n_init": K.KMEANS_N_INIT,
            "max_iter": K.KMEANS_MAX_ITER,
            "stability_draws": K.STABILITY_DRAWS,
            "ari_min": K.STABILITY_ARI_MIN,
        },
    }
    return body


def main() -> None:
    if OUT.exists():
        raise SystemExit("REFUSING_RERUN: an outcome-blind preflight is already recorded")
    bars = load_discovery_bars()
    oi, meta = load_bound_oi()
    if meta["funding_jsonl_opened"]:
        raise RuntimeError("funding was opened")
    body = _py(summarize(bars, oi, meta))
    OUT.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "proceed_to_outcomes": body["proceed_to_outcomes"],
        "blocked_reason": body["blocked_reason"],
        "selected_k": body["selected_k"],
        "predictor_complete": body["predictor_complete"],
        "state_counts": body["state_counts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
