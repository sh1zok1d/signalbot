"""One retrospective read of OKX funding extremity and later path stress.

A second official run returns REFUSING_RERUN before loading funding or price.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from . import constants as K
from . import model
from .data import build_frame

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_DESIGN.md"
DESIGN_JSON = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_DESIGN.json"
PRE_MANIFEST = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_PRE_OUTCOME_MANIFEST.json"
OUT_JSON = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_RESULT.json"
OUT_MD = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_RESULT.md"
OUT_MANIFEST = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_OKX_REPLICATION_V1_EVALUATOR_MANIFEST.json"
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


def render_markdown(payload: dict) -> str:
    raw_i = payload["interval"]["raw"]
    part_i = payload["interval"]["partial"]
    upper_i = payload["interval"]["upper_tail"]
    lower_i = payload["interval"]["lower_tail"]
    syn = payload["synthesis"]
    lines = [
        "# FUNDING_TAIL_RISK_OKX_REPLICATION_V1 — one historical read",
        "",
        "`outcome_read = true`",
        f"`evidence_class = {payload['evidence_class']}`",
        f"`interpretation = {payload['interpretation']['code']}`",
        "",
        "The route uses only the partial Spearman of funding extremity with the 8-hour absolute "
        "excursion, given current realized volatility, and the interval of that partial. "
        "There is no magnitude floor. Bins, tails, years, and funding-sign splits are descriptions.",
        "",
        f"Read `{payload['read_at']}`. Evaluator `{payload['pre_outcome_evaluator_commit'][:12]}`.",
        "",
        f"- Funding events `{payload['funding_n']}`",
        f"- Analysis N `{payload['n']}`",
        f"- ISO weeks `{payload['n_weeks']}`",
        f"- Zero raw rates `{payload['n_zero_rate']}`",
        f"- Dropped, schedule exception `{payload['dropped']['schedule_exception']}`",
        f"- Dropped, state undefined `{payload['dropped']['state_undefined']}`",
        f"- Dropped, path `{payload['dropped']['path']}`",
        f"- Dropped, volatility window `{payload['dropped']['rv']}`",
        f"- Raw Spearman `{_num(payload['spearman'])}` "
        f"interval `[{_num(raw_i['lo'])}, {_num(raw_i['hi'])}]`",
        f"- Partial Spearman `{_num(payload['partial'])}` "
        f"interval `[{_num(part_i['lo'])}, {_num(part_i['hi'])}]`",
        f"- Valid partial draws `{part_i['valid_draws']}` / `{payload['interval']['draws']}`",
        f"- Share of partial draws above zero `{_num(part_i['share_positive'])}`",
        "",
        "| bin | n | mean abs excursion | median | mean downside | mean upside |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["bins"]:
        lines.append(
            f"| {row['bin']} | {row['n']} | {_num(row['mean_abs_excursion'])} | "
            f"{_num(row['median_abs_excursion'])} | {_num(row['mean_downside'])} | "
            f"{_num(row['mean_upside'])} |"
        )
    lines.extend([
        "",
        f"- Upper tail minus center `{_num(payload['contrasts']['upper']['point'])}` "
        f"interval `[{_num(upper_i['lo'])}, {_num(upper_i['hi'])}]`",
        f"- Lower tail minus center `{_num(payload['contrasts']['lower']['point'])}` "
        f"interval `[{_num(lower_i['lo'])}, {_num(lower_i['hi'])}]`",
        "",
        "| year | n | spearman | partial |",
        "| --- | --- | --- | --- |",
    ])
    for row in payload["years"]:
        lines.append(
            f"| {row['year']} | {row['n']} | {_num(row['spearman'])} | {_num(row['partial'])} |"
        )
    lines.extend([
        "",
        "| side | n | signed rank | extremity |",
        "| --- | --- | --- | --- |",
    ])
    for row in payload["sides"]:
        lines.append(
            f"| {row['side']} | {row['n']} | {_num(row['spearman_rank'])} | "
            f"{_num(row['spearman_extremity'])} |"
        )
    lines.extend([
        "",
        payload["interpretation"]["code"],
        "",
        f"Conclusion `{syn['conclusion']}`. Shape `{syn['shape']}`. "
        f"Volatility control `{syn['attenuation']}`.",
        f"OKX partial `{_num(syn['okx_partial'])}`. "
        f"Frozen Binance parent partial `{_num(syn['parent_partial'])}`. "
        "No similarity cutoff. The venues are not pooled.",
        "",
        "Evidence class stays a cross-venue retrospective read with unproven publication time. "
        "Not a point-in-time confirmation. A positive structure is compatible with the historical "
        "drawdown reduction in MARKET-03 only as a description. It does not prove why that "
        "strategy result occurred. Not a product change unless the route itself is the supported "
        "code, and even then the owner decides implementation.",
        f"`PRODUCT_INTEGRATION_CANDIDATE = {payload['product_integration_candidate']}`.",
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


def assert_frozen_texts() -> None:
    if _sha256(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    if _sha256(DESIGN_JSON) != K.DESIGN_JSON_SHA256:
        raise SystemExit("DESIGN_JSON_HASH_MISMATCH")
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


def main() -> int:
    if OUT_JSON.exists() or OUT_MD.exists() or OUT_MANIFEST.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    assert_frozen_texts()
    head = assert_evaluator_matches_head()
    frame = build_frame()
    if int(frame["funding_n"]) != K.FUNDING_N:
        raise SystemExit(f"SAMPLE_DOES_NOT_MATCH_AUDIT n={frame['funding_n']}")
    try:
        summary = model.summarize(frame)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    if not math.isfinite(summary["partial"]):
        raise SystemExit("PARTIAL_DEGENERATE")
    label = model.interpret(summary)
    comparison = model.synthesis(summary, label)
    payload = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "outcome_read": True,
        "product_integration_candidate": label["product_integration_candidate"],
        "evidence_tier_raised": False,
        "causal_claim": False,
        "threshold_55_applied": False,
        "practical_rho_applied": False,
        "premium_scored": False,
        "oi_opened": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
        "parent_label_unchanged": "INCREMENTAL_ASSOCIATION_UNCERTAIN",
        "bybit_status_unchanged": "BLOCKED_BY_CROSS_VENUE_FUNDING_PROVENANCE",
        "design_sha256": K.DESIGN_SHA256,
        "design_json_sha256": K.DESIGN_JSON_SHA256,
        "funding_sha256": K.FUNDING_SHA256,
        "price_sha256": K.PRICE_SHA256,
        "pre_outcome_evaluator_commit": head,
        "evaluator_digest": code_digest(),
        "read_at": dt.datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "funding_n": int(frame["funding_n"]),
        "dropped": frame["dropped"],
        "n": summary["n"],
        "n_weeks": summary["n_weeks"],
        "n_zero_rate": summary["n_zero_rate"],
        "spearman": summary["spearman"],
        "partial": summary["partial"],
        "interval": summary["interval"],
        "bins": summary["bins"],
        "years": summary["years"],
        "sides": summary["sides"],
        "contrasts": summary["contrasts"],
        "interpretation": label,
        "synthesis": comparison,
    }
    manifest = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "outcome_read": True,
        "design_sha256": K.DESIGN_SHA256,
        "pre_outcome_evaluator_commit": head,
        "evaluator_digest": payload["evaluator_digest"],
        "read_at": payload["read_at"],
        "funding_n": payload["funding_n"],
        "n": payload["n"],
        "n_weeks": payload["n_weeks"],
        "spearman": payload["spearman"],
        "partial": payload["partial"],
        "interpretation": label["code"],
        "product_integration_candidate": label["product_integration_candidate"],
        "premium_scored": False,
        "oi_opened": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
        "threshold_55_applied": False,
        "practical_rho_applied": False,
    }
    write_outputs(payload, manifest)
    print(json.dumps({
        "interpretation": label["code"],
        "n": payload["n"],
        "n_weeks": payload["n_weeks"],
        "spearman": payload["spearman"],
        "partial": payload["partial"],
        "read_at": payload["read_at"],
        "product_integration_candidate": label["product_integration_candidate"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
