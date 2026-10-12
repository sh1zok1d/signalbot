"""Replay calibration monitor V2 on an anonymized claim export.

The census role cannot SELECT ``beta_claims`` or ``beta_claim_outcomes``. This script
does not open a database connection, does not read ``BETA_DSN``, and does not write
health rows. The executable export is ``scripts/beta/export_calibration_journal_v2.sh``
(SQL: ``scripts/beta/export_calibration_journal_v2.sql``). It keeps coverage, the
evaluation rule and the latest outcome revision, and it does not select subject or
price fields. This script refuses an export that still contains those keys.

Usage::

    python3 scripts/beta/replay_calibration_monitor_v2.py claims.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.calibration_monitor import evaluate, observations_from_claim_rows

_EXPORT_SQL_PATH = Path(__file__).with_name("export_calibration_journal_v2.sql")
READ_ONLY_EXPORT_SQL = _EXPORT_SQL_PATH.read_text(encoding="utf-8").strip()

# Prices, account identifiers and secrets. `level` is not listed: on a claim row it is
# the ladder name, and the export query does not select it.
FORBIDDEN_KEYS = frozenset({
    "subject", "subject_key", "price", "high", "low", "close",
    "chat_id", "user_id", "token", "password", "dsn", "secret",
    "api_key", "authorization",
})


def forbidden_keys(payload) -> set:
    found = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).lower() in FORBIDDEN_KEYS:
                    found.add(str(key))
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found


def load_jsonl(text: str) -> list:
    rows = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number} is not JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number} is not an object")
        leaked = forbidden_keys(row)
        if leaked:
            raise ValueError(f"line {line_number} contains forbidden keys: {', '.join(sorted(leaked))}")
        rows.append(row)
    return rows


def summary(report: dict) -> dict:
    books = []
    for book in report["books"]:
        books.append({
            "family": book["family"],
            "horizon": book["horizon"],
            "spec_id": book.get("spec_id"),
            "state": book["state"],
            "e_value": book["e_value"],
            "n_claims": book["n_claims"],
            "n_rows": book["n_rows"],
            "n_unfinished": book["n_unfinished"],
            "n_low_coverage": book["n_low_coverage"],
            "n_days": book["n_days"],
            "n_included_slots": book["n_included_slots"],
            "n_skipped_overlapping": book["n_skipped_overlapping"],
            "snapshot_ids": book["snapshot_ids"],
            "eval_rule_ids": book["eval_rule_ids"],
            "reason": book["reason"],
            "user_action": book["user_action"]["action"],
        })
    return {
        "monitor_version": report["monitor_version"],
        "shadow_component": report["shadow_component"],
        "thresholds": report["thresholds"],
        "books": books,
    }


def main(argv: list) -> int:
    if len(argv) != 2:
        print("usage: python3 scripts/beta/replay_calibration_monitor_v2.py claims.jsonl", file=sys.stderr)
        return 1
    path = Path(argv[1])
    try:
        rows = load_jsonl(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report = evaluate(observations_from_claim_rows(rows))
    json.dump(summary(report), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
