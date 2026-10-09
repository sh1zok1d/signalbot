"""One OOS predictive-value read on the already consumed Binance and Bybit samples.

A second official run returns REFUSING_RERUN before loading either panel.
The model, folds, and metric are the frozen design. This module does not retune them.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.formation_width_regime_v1 import amendment_a1 as A1
from scripts.research.opening_range_object_v1 import census as parent_census

from . import constants as K
from . import model

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1_DESIGN.md"
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1_RESULT.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1_RESULT.md"
OUT_MANIFEST = ROOT / "docs" / "research" / "FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1_EVALUATOR_MANIFEST.json"
UTC = dt.timezone.utc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(PKG.glob("*.py")):
        rel = str(path.relative_to(ROOT))
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(rel.encode())
        digest.update(file_hash.encode())
    return digest.hexdigest()


def _frame_from_forms(close: np.ndarray, forms: list[dict]) -> dict:
    width = []
    rv = []
    activity = []
    day_values = []
    years = []
    weeks = []
    for row in forms:
        form = int(row["form"])
        p0 = float(row["p0"])
        width.append((float(row["high"]) - float(row["low"])) / p0)
        rv.append(A1.realized_variation(A1.log_returns(close, A1.formation_return_pairs(form))))
        activity.append(A1.realized_variation(A1.log_returns(close, A1.future_return_pairs(form))))
        day_values.append(int(row["day_ms"]))
        years.append(int(row["year"]))
        weeks.append((int(row["week"][0]), int(row["week"][1])))
    return {
        "day_ms": np.asarray(day_values, dtype=np.int64),
        "year": np.asarray(years, dtype=np.int64),
        "week": weeks,
        "width": np.asarray(width, dtype=np.float64),
        "rv": np.asarray(rv, dtype=np.float64),
        "activity": np.asarray(activity, dtype=np.float64),
    }


def assert_identity(frame: dict, *, n: int, weeks: int, years: dict[int, int]) -> None:
    got_n = int(len(frame["day_ms"]))
    got_weeks = len(set(frame["week"]))
    got_years = Counter(int(year) for year in frame["year"])
    stamps = frame["day_ms"]
    increasing = got_n > 1 and bool(np.all(stamps[1:] > stamps[:-1]))
    finite = bool(
        np.all(np.isfinite(frame["width"]))
        and np.all(np.isfinite(frame["rv"]))
        and np.all(np.isfinite(frame["activity"]))
    )
    expected_years = {int(year): int(count) for year, count in years.items()}
    if got_n != n or got_weeks != weeks or dict(got_years) != expected_years or not increasing or not finite:
        raise SystemExit("SAMPLE_DOES_NOT_MATCH_PUBLISHED")


def load_binance() -> dict:
    from scripts.research.formation_width_regime_v1.evaluate import eligible_forms
    from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

    bars = load_discovery_bars()
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    forms = eligible_forms(high, low, close, int(bars.t0))
    frame = _frame_from_forms(close, forms)
    assert_identity(
        frame,
        n=K.BINANCE_EXPECTED_N,
        weeks=K.BINANCE_EXPECTED_WEEKS,
        years=K.BINANCE_EXPECTED_YEARS,
    )
    return frame


def load_bybit() -> dict:
    from scripts.research.formation_width_activity_bybit_feasibility_v1 import constants as BK
    from scripts.research.formation_width_activity_bybit_feasibility_v1 import support

    high, low, close, provenance = support.load_ohlc()
    if provenance["canonical_sha256"] != BK.CANONICAL_SHA256:
        raise SystemExit("CANONICAL_SHA_MISMATCH")
    forms = []
    n_days = int(high.shape[0]) // BK.BARS_PER_DAY
    for day in range(n_days):
        day_ms = support.GRID_START_MS + day * BK.DAY_MS
        if day_ms < support.EVENT_START_MS or day_ms >= support.SURFACE_END_MS:
            continue
        form = day * BK.BARS_PER_DAY
        geo = parent_census._geometry(high, low, close, form)
        if geo is None or not geo["usable"]:
            continue
        rv_start, rv_count = A1.formation_close_span(form)
        rv_ok = support.span_complete(close, rv_start, rv_count)
        next_ok = support.span_complete(close, form + BK.FORMATION_BARS - 1, BK.HORIZON_BARS + 1)
        if not (rv_ok and next_ok):
            continue
        stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=UTC)
        iso = stamp.isocalendar()
        forms.append({
            "form": form,
            "day_ms": day_ms,
            "year": stamp.year,
            "week": (int(iso.year), int(iso.week)),
            "high": float(geo["high"]),
            "low": float(geo["low"]),
            "p0": float(geo["p0"]),
        })
    frame = _frame_from_forms(close, forms)
    assert_identity(
        frame,
        n=K.BYBIT_EXPECTED_N,
        weeks=K.BYBIT_EXPECTED_WEEKS,
        years=K.BYBIT_EXPECTED_YEARS,
    )
    return frame


def _num(value) -> str:
    if value is None:
        return "na"
    return json.dumps(value)


def render_markdown(payload: dict) -> str:
    lines = [
        "# FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1 — OOS read",
        "",
        "`outcome_read = true`",
        f"`evidence_class = {payload['evidence_class']}`",
        f"`interpretation = {payload['interpretation']['code']}`",
        "",
        payload["interpretation"]["text"],
        "",
        "The historical rule `rho >= +0.10` is not applied. The Bybit route "
        f"`{K.BYBIT_HISTORICAL_ROUTE}` is unchanged. Venues are not pooled. "
        "A future dedicated validation is not decided here. "
        "`PRODUCT_INTEGRATION_CANDIDATE = NO`.",
        "",
        f"Read `{payload['read_at']}`. Evaluator `{payload['pre_outcome_evaluator_commit'][:12]}`.",
        "",
    ]
    for name in ("binance", "bybit"):
        row = payload[name]
        interval = row["interval"]
        lines.extend([
            f"## {name}",
            "",
            f"- analysis N `{row['n_analysis']}`",
            f"- OOS N `{row['n_oos']}`",
            f"- OOS ISO weeks `{row['oos_iso_weeks']}`",
            f"- MSE baseline `{_num(row['mse_baseline'])}`",
            f"- MSE candidate `{_num(row['mse_candidate'])}`",
            f"- absolute improvement `{_num(row['delta_mse'])}`",
            f"- relative improvement `{_num(row['relative'])}`",
            f"- relative percent `{_num(row['relative_percent'])}`",
            f"- interval `[{_num(interval['lo'])}, {_num(interval['hi'])}]`",
            f"- share of bootstrap means above zero `{_num(interval['share_positive'])}`",
            f"- Spearman baseline `{_num(row['spearman_baseline'])}`",
            f"- Spearman candidate `{_num(row['spearman_candidate'])}`",
            "",
            "| test start | n train | n test | MSE baseline | MSE candidate | delta | relative |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for fold in row["folds"]:
            lines.append(
                "| {test_start} | {n_train} | {n_test} | {mse_b} | {mse_c} | {delta} | {rel} |".format(
                    test_start=fold["test_start"],
                    n_train=fold["n_train"],
                    n_test=fold["n_test"],
                    mse_b=_num(fold["mse_baseline"]),
                    mse_c=_num(fold["mse_candidate"]),
                    delta=_num(fold["delta_mse"]),
                    rel=_num(fold["relative"]),
                )
            )
        lines.append("")
    lines.extend([
        payload["interpretation"]["code"],
        "",
        "Not a confirmation. Not a cause. Not a product change. Prospective forward association was not read.",
        "",
    ])
    return "\n".join(lines)


def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.floating, np.integer)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def assert_frozen_texts() -> None:
    if _sha256(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")


def assert_evaluator_matches_head() -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in sorted(PKG.glob("*.py")):
        rel = str(path.relative_to(ROOT))
        committed = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != hashlib.sha256(path.read_bytes()).hexdigest():
            raise SystemExit("EVALUATOR_DIFFERS_FROM_HEAD")
    return head


def write_outputs(payload: dict, manifest: dict) -> None:
    if OUT_JSON.exists() or OUT_MD.exists() or OUT_MANIFEST.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    OUT_JSON.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    OUT_MANIFEST.write_text(json.dumps(_json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _score(frame: dict, *, venue_start: str, seed: int) -> dict:
    try:
        return model.evaluate_surface(
            frame["day_ms"],
            frame["rv"],
            frame["width"],
            frame["activity"],
            frame["week"],
            venue_start=venue_start,
            seed=seed,
        )
    except RuntimeError as exc:
        message = str(exc)
        for code in ("FOLD_BELOW_FROZEN_MINIMUM", "FOLD_RANK_DEFICIENT", "BASELINE_LOSS_DEGENERATE"):
            if message.startswith(code):
                raise SystemExit(message) from exc
        raise


def main() -> int:
    if OUT_JSON.exists() or OUT_MD.exists() or OUT_MANIFEST.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    assert_frozen_texts()
    head = assert_evaluator_matches_head()
    binance = _score(load_binance(), venue_start=K.BINANCE_START, seed=K.BINANCE_SEED)
    bybit = _score(load_bybit(), venue_start=K.BYBIT_START, seed=K.BYBIT_SEED)
    label = model.interpret(binance, bybit)
    payload = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "outcome_read": True,
        "future_association_read": False,
        "prospective_forward_read": False,
        "product_integration_candidate": False,
        "evidence_tier_raised": False,
        "historical_practical_rho_applied": False,
        "bybit_historical_route_unchanged": K.BYBIT_HISTORICAL_ROUTE,
        "binance_historical_partial": K.BINANCE_HISTORICAL_PARTIAL,
        "bybit_historical_partial": K.BYBIT_HISTORICAL_PARTIAL,
        "design_sha256": K.DESIGN_SHA256,
        "pre_outcome_evaluator_commit": head,
        "evaluator_digest": code_digest(),
        "read_at": dt.datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": "OLS on training-referenced rank scores",
        "primary_metric": "delta_mse",
        "secondary_metric": "oos_spearman_prediction_vs_raw_activity",
        "binance": binance,
        "bybit": bybit,
        "interpretation": label,
        "bitmex_opened": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
    }
    manifest = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "outcome_read": True,
        "design_sha256": K.DESIGN_SHA256,
        "pre_outcome_evaluator_commit": head,
        "evaluator_digest": payload["evaluator_digest"],
        "read_at": payload["read_at"],
        "binance_n": binance["n_analysis"],
        "bybit_n": bybit["n_analysis"],
        "binance_delta_mse": binance["delta_mse"],
        "bybit_delta_mse": bybit["delta_mse"],
        "binance_interval": [binance["interval"]["lo"], binance["interval"]["hi"]],
        "bybit_interval": [bybit["interval"]["lo"], bybit["interval"]["hi"]],
        "interpretation": label["code"],
        "historical_practical_rho_applied": False,
        "prospective_forward_read": False,
        "product_integration_candidate": False,
        "bitmex_opened": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
    }
    write_outputs(payload, manifest)
    print(json.dumps({
        "interpretation": label["code"],
        "binance_delta_mse": binance["delta_mse"],
        "bybit_delta_mse": bybit["delta_mse"],
        "binance_n": binance["n_analysis"],
        "bybit_n": bybit["n_analysis"],
        "read_at": payload["read_at"],
        "pre_outcome_evaluator_commit": head,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
