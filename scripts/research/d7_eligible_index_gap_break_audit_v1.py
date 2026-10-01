"""Target-blind audit of the D7 gap-break extractor and its sealed output.

This module does not read activity, notional, return, or state series.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

from scripts.research.d7_eligible_index_gap_break_v1 import (
    ALLOWED_OUTPUT_KEYS,
    PUBLISHED_GAP,
    derivation_rule_digest,
)

EXTRACTOR_REL = Path("scripts/research/d7_eligible_index_gap_break_v1.py")
FORBIDDEN_ATTRS = {
    "state",
    "ret_abs_1h",
    "foreign_notional_1h",
    "foreign_notional",
    "rv_bucket",
    "qrel_1h",
    "impact_proxy",
    "open",
    "high",
    "low",
    "close",
    "open_1h",
    "close_1h",
}
FORBIDDEN_CALLS = {"nonzero", "where", "tolist", "support_from_frame"}
FORBIDDEN_OUTPUT_TOKENS = (
    "state_defined",
    "foreignNotional",
    "ret_abs",
    "rv_bucket",
    "autocorrelation",
    "transition",
    "notional",
    "X_t",
    "hour_start",
    "open_time",
    "candidate",
    "persistence",
    '"state"',
)
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T")


def audit_extractor_source(repo: Path) -> list[str]:
    path = repo / EXTRACTOR_REL
    source = path.read_text(encoding="utf-8")
    findings: list[str] = []
    if "raw_pages" in source:
        findings.append("SOURCE_REFERENCES_RAW_PAGES")
    tree = ast.parse(source)
    method_calls = {
        node.func
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            if node in method_calls and node.attr == "open":
                continue
            findings.append(f"SOURCE_ATTR:{node.attr}")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in FORBIDDEN_CALLS:
                findings.append(f"SOURCE_CALL:{name}")
    return findings


def audit_output_text(text: str, repo: Path) -> list[str]:
    findings: list[str] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ["OUTPUT_NOT_JSON"]
    if not isinstance(payload, dict):
        return ["OUTPUT_NOT_OBJECT"]
    if tuple(sorted(payload)) != tuple(sorted(ALLOWED_OUTPUT_KEYS)):
        findings.append("OUTPUT_KEYS")
    for key, value in payload.items():
        if key.endswith("_SHA256"):
            if not isinstance(value, str) or len(value) != 64:
                findings.append("OUTPUT_DIGEST_SHAPE")
        elif key in {"MINIMUM_REQUIRED_GEOMETRY", "GAP_HALF_OPEN"}:
            if not isinstance(value, str):
                findings.append("OUTPUT_STRING")
        elif type(value) not in {int, bool}:
            findings.append("OUTPUT_VALUE_TYPE")
    if payload.get("MINIMUM_REQUIRED_GEOMETRY") != "ELIGIBLE_INDEX_GAP_BREAK":
        findings.append("OUTPUT_GEOMETRY_FIELD")
    if payload.get("GAP_HALF_OPEN") != PUBLISHED_GAP:
        findings.append("OUTPUT_GAP_IDENTITY")
    stripped = text.replace(PUBLISHED_GAP, "")
    if TIMESTAMP_RE.search(stripped):
        findings.append("OUTPUT_EXTRA_TIMESTAMP")
    for token in FORBIDDEN_OUTPUT_TOKENS:
        if token in stripped:
            findings.append("OUTPUT_FORBIDDEN_TOKEN")
            break
    extractor = repo / EXTRACTOR_REL
    extractor_digest = __import__("hashlib").sha256(extractor.read_bytes()).hexdigest()
    if payload.get("EXTRACTOR_SHA256") != extractor_digest:
        findings.append("OUTPUT_EXTRACTOR_DIGEST")
    if payload.get("DERIVATION_RULE_SHA256") != derivation_rule_digest():
        findings.append("OUTPUT_DERIVATION_DIGEST")
    return findings


def audit(repo: Path, output_text: str) -> dict[str, object]:
    findings = audit_extractor_source(repo) + audit_output_text(output_text, repo)
    unique = sorted(set(findings))
    return {
        "GEOMETRY_EXTRACTOR_TARGET_BLIND": len(unique) == 0,
        "FINDING_CODES": unique,
    }


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("AUDIT_USAGE\n")
        return 2
    repo = Path(__file__).resolve().parents[2]
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    result = audit(repo, text)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if result["GEOMETRY_EXTRACTOR_TARGET_BLIND"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
