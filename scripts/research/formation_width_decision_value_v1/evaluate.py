"""One decision-value read on the already consumed Binance and Bybit samples.

A second official run returns REFUSING_RERUN before loading either panel.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.formation_width_incremental_predictive_value_v1.evaluate import (
    load_binance,
    load_bybit,
)

from . import constants as K
from . import model

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_DECISION_VALUE_V1_DESIGN.md"
PRE_MANIFEST = ROOT / "docs" / "research" / "FORMATION_WIDTH_DECISION_VALUE_V1_PRE_OUTCOME_MANIFEST.json"
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_DECISION_VALUE_V1_RESULT.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_DECISION_VALUE_V1_RESULT.md"
OUT_MANIFEST = ROOT / "docs" / "research" / "FORMATION_WIDTH_DECISION_VALUE_V1_EVALUATOR_MANIFEST.json"
UTC = dt.timezone.utc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(PKG.glob("*.py")):
        rel = str(path.relative_to(ROOT))
        digest.update(rel.encode())
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    return digest.hexdigest()


def _num(value) -> str:
    if value is None:
        return "na"
    return json.dumps(value)


def _venue_lines(name: str, row: dict) -> list[str]:
    net_i = row["interval"]["net"]
    brier_i = row["interval"]["brier"]
    auc_i = row["interval"]["auroc"]
    lines = [
        f"## {name}",
        "",
        f"- OOS N `{row['n_oos']}`",
        f"- high rate `{_num(row['high_rate'])}`",
        f"- decision-change rate `{_num(row['decision_change_rate'])}`",
        f"- changed `{row['n_changed']}`",
        f"- correct changes `{row['n_correct_changes']}`",
        f"- harmful changes `{row['n_harmful_changes']}`",
        f"- upgrades `{row['n_upgrade']}` hit rate `{_num(row['upgrade_hit_rate'])}`",
        f"- downgrades `{row['n_downgrade']}` hit rate `{_num(row['downgrade_hit_rate'])}`",
        f"- net `{_num(row['net'])}` interval `[{_num(net_i['lo'])}, {_num(net_i['hi'])}]`",
        f"- Brier baseline `{_num(row['brier_baseline'])}`",
        f"- Brier candidate `{_num(row['brier_candidate'])}`",
        f"- Brier gain `{_num(row['brier_gain'])}` interval `[{_num(brier_i['lo'])}, {_num(brier_i['hi'])}]`",
        f"- AUROC baseline `{_num(row['auroc_baseline'])}`",
        f"- AUROC candidate `{_num(row['auroc_candidate'])}`",
        f"- AUROC change `{_num(row['auroc_change'])}` interval `[{_num(auc_i['lo'])}, {_num(auc_i['hi'])}]`",
        "",
        "| test start | n test | change rate | net | Brier gain |",
        "| --- | --- | --- | --- | --- |",
    ]
    for fold in row["folds"]:
        lines.append(
            f"| {fold['test_start']} | {fold['n_test']} | {_num(fold['decision_change_rate'])} "
            f"| {_num(fold['net'])} | {_num(fold['brier_gain'])} |"
        )
    lines.append("")
    return lines


def render_markdown(payload: dict) -> str:
    lines = [
        "# FORMATION_WIDTH_DECISION_VALUE_V1 — decision-value read",
        "",
        "`outcome_read = true`",
        f"`evidence_class = {payload['evidence_class']}`",
        f"`interpretation = {payload['interpretation']['code']}`",
        "",
        payload["interpretation"]["text"],
        "",
        "No magnitude floor is applied. Product labels 0.80 / 0.95 / 0.99 were not adopted. "
        "Venues are not pooled. Width does not enter the forecast architecture in this unit. "
        "`PRODUCT_INTEGRATION_CANDIDATE = NO`.",
        "",
        f"Read `{payload['read_at']}`. Evaluator `{payload['pre_outcome_evaluator_commit'][:12]}`.",
        "",
    ]
    for name in ("binance", "bybit"):
        lines.extend(_venue_lines(name, payload[name]))
    lines.extend([
        "Descriptive cuts and quartile slices are not route inputs.",
        "",
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
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _public(row: dict) -> dict:
    """Drop the per-day sequence from the markdown path; the JSON keeps it."""
    return row


def assert_frozen_texts() -> None:
    if _sha256(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    if not PRE_MANIFEST.exists():
        raise SystemExit("PRE_OUTCOME_MANIFEST_MISSING")
    pre = json.loads(PRE_MANIFEST.read_text(encoding="utf-8"))
    if pre.get("outcome_read") is not False:
        raise SystemExit("PRE_OUTCOME_MANIFEST_ALREADY_SCORED")
    if pre.get("evaluator_digest") != code_digest():
        raise SystemExit("PRE_OUTCOME_DIGEST_MISMATCH")
    if pre.get("design_sha256") != K.DESIGN_SHA256:
        raise SystemExit("PRE_OUTCOME_DESIGN_MISMATCH")


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
            frame["day_ms"], frame["rv"], frame["width"], frame["activity"], frame["week"],
            venue_start=venue_start, seed=seed,
        )
    except RuntimeError as exc:
        message = str(exc)
        for code in (
            "FOLD_BELOW_FROZEN_MINIMUM",
            "FOLD_RANK_DEFICIENT",
            "LOGISTIC_DID_NOT_CONVERGE",
            "CLASS_DEGENERATE",
        ):
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
        "product_labels_adopted": False,
        "evidence_tier_raised": False,
        "historical_practical_rho_applied": False,
        "design_sha256": K.DESIGN_SHA256,
        "pre_outcome_evaluator_commit": head,
        "evaluator_digest": code_digest(),
        "read_at": dt.datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": "unpenalized logistic on training-referenced rank scores",
        "primary_decision": "train upper quartile of ACTIVITY",
        "primary_proper_score": "brier",
        "binance": _public(binance),
        "bybit": _public(bybit),
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
        "binance_n_oos": binance["n_oos"],
        "bybit_n_oos": bybit["n_oos"],
        "binance_decision_change_rate": binance["decision_change_rate"],
        "bybit_decision_change_rate": bybit["decision_change_rate"],
        "binance_net": binance["net"],
        "bybit_net": bybit["net"],
        "binance_brier_gain": binance["brier_gain"],
        "bybit_brier_gain": bybit["brier_gain"],
        "binance_auroc_change": binance["auroc_change"],
        "bybit_auroc_change": bybit["auroc_change"],
        "interpretation": label["code"],
        "product_labels_adopted": False,
        "product_integration_candidate": False,
        "prospective_forward_read": False,
        "bitmex_opened": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
    }
    write_outputs(payload, manifest)
    print(json.dumps({
        "interpretation": label["code"],
        "binance_net": binance["net"],
        "bybit_net": bybit["net"],
        "binance_brier_gain": binance["brier_gain"],
        "bybit_brier_gain": bybit["brier_gain"],
        "binance_change_rate": binance["decision_change_rate"],
        "bybit_change_rate": bybit["decision_change_rate"],
        "read_at": payload["read_at"],
        "pre_outcome_evaluator_commit": head,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
