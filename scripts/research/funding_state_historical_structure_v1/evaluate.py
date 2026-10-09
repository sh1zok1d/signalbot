"""One retrospective read of funding state and later long-side path stress.

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
DESIGN_PATH = ROOT / "docs" / "research" / "FUNDING_STATE_HISTORICAL_STRUCTURE_V1_DESIGN.md"
PRE_MANIFEST = ROOT / "docs" / "research" / "FUNDING_STATE_HISTORICAL_STRUCTURE_V1_PRE_OUTCOME_MANIFEST.json"
OUT_JSON = ROOT / "docs" / "research" / "FUNDING_STATE_HISTORICAL_STRUCTURE_V1_RESULT.json"
OUT_MD = ROOT / "docs" / "research" / "FUNDING_STATE_HISTORICAL_STRUCTURE_V1_RESULT.md"
OUT_MANIFEST = ROOT / "docs" / "research" / "FUNDING_STATE_HISTORICAL_STRUCTURE_V1_EVALUATOR_MANIFEST.json"
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
    lines = [
        "# FUNDING_STATE_HISTORICAL_STRUCTURE_V1 — historical structure",
        "",
        "`outcome_read = true`",
        f"`evidence_class = {payload['evidence_class']}`",
        f"`interpretation = {payload['interpretation']['code']}`",
        "",
        "The route uses only the incremental partial Spearman and its interval. "
        "There is no magnitude floor. Bins, years, shorter horizons, the absolute excursion, "
        "and the funding-sign split are descriptions.",
        "",
        f"Read `{payload['read_at']}`. Evaluator `{payload['pre_outcome_evaluator_commit'][:12]}`.",
        "",
        f"- Funding events `{payload['funding_n']}`",
        f"- Analysis N `{payload['n']}`",
        f"- ISO weeks `{payload['n_weeks']}`",
        f"- Zero raw rates `{payload['n_zero_rate']}`",
        f"- Dropped, state undefined `{payload['dropped']['state_undefined']}`",
        f"- Dropped, path `{payload['dropped']['path']}`",
        f"- Dropped, volatility window `{payload['dropped']['rv']}`",
        f"- Spearman `{_num(payload['spearman'])}` "
        f"interval `[{_num(raw_i['lo'])}, {_num(raw_i['hi'])}]`",
        f"- Partial Spearman `{_num(payload['partial'])}` "
        f"interval `[{_num(part_i['lo'])}, {_num(part_i['hi'])}]`",
        f"- Valid partial draws `{part_i['valid_draws']}` / `{payload['interval']['draws']}`",
        f"- Share of partial draws above zero `{_num(part_i['share_positive'])}`",
        "",
        "| bin | n | mean adverse 8h |",
        "| --- | --- | --- |",
    ]
    for row in payload["bins"]:
        lines.append(f"| {row['bin']} | {row['n']} | {_num(row['mean_adverse'])} |")
    lines.extend([
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
        "| side | n | spearman |",
        "| --- | --- | --- |",
    ])
    for row in payload["sides"]:
        lines.append(f"| {row['side']} | {row['n']} | {_num(row['spearman'])} |")
    lines.extend([
        "",
        "| secondary | spearman | partial | route input |",
        "| --- | --- | --- | --- |",
    ])
    for row in payload["secondary"]:
        lines.append(
            f"| {row['name']} | {_num(row['spearman'])} | {_num(row['partial'])} | {row['route_input']} |"
        )
    lines.extend([
        "",
        payload["interpretation"]["code"],
        "",
        "Evidence class stays retrospective and availability-limited. "
        "Not a point-in-time confirmation. Not a cause of the MARKET-03 drawdown change. "
        "Not a product change. Premium was not scored. Open interest was not opened.",
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
    payload = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "outcome_read": True,
        "product_integration_candidate": False,
        "evidence_tier_raised": False,
        "market_04_rewritten": False,
        "causal_claim": False,
        "threshold_55_applied": False,
        "practical_rho_applied": False,
        "premium_scored": False,
        "oi_opened": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
        "product_change": False,
        "design_sha256": K.DESIGN_SHA256,
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
        "secondary": summary["secondary"],
        "interpretation": label,
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
        "product_integration_candidate": False,
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
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
