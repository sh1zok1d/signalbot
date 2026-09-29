"""CLI for the free overlap audit.

    python -m scripts.audit.tardis_free_overlap_v0 report --vendor-dir ... --out-dir ...
    python -m scripts.audit.tardis_free_overlap_v0 compare --gold-dir ...

`compare` without a gold export prints WAITING_FOR_SIGNALBOT_EXPORT and does
not invent metrics. `report` writes the inventory artifacts for the files
already downloaded.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import DECISION_INCOMPLETE, WAITING_FOR_EXPORT
from .gold import REQUIRED_FILES
from .inventory import inventory_vendor_dir
from .report import build_incomplete_payload, load_incidents, write_outputs


def _base_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            check=True, capture_output=True, text=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "UNKNOWN"


def _gold_ready(path: str | None) -> bool:
    if not path:
        return False
    root = Path(path)
    return all((root / name).is_file() for name in REQUIRED_FILES)


def cmd_report(args) -> int:
    inventory = inventory_vendor_dir(args.vendor_dir)
    incidents = load_incidents(args.exchange_meta_dir) if args.exchange_meta_dir else {
        name: {"loaded": False, "incidents": []}
        for name in ("binance-futures", "bybit", "okex-swap")
    }
    manifest, summary = build_incomplete_payload(
        base_sha=args.base_sha or _base_sha(),
        inventory=inventory,
        incidents_raw=incidents,
    )
    write_outputs(Path(args.out_dir), manifest, summary)
    print(WAITING_FOR_EXPORT)
    print(DECISION_INCOMPLETE)
    print(f"wrote {args.out_dir}")
    return 0


def cmd_compare(args) -> int:
    if not _gold_ready(args.gold_dir):
        print(WAITING_FOR_EXPORT)
        print(DECISION_INCOMPLETE)
        print(
            "No gold export. Run extract_signalbot_readonly.py on the database host. "
            "This command will not invent comparison metrics.",
            file=sys.stderr,
        )
        return 2
    from .engine import run_gold_comparison
    return run_gold_comparison(
        vendor_dir=args.vendor_dir,
        gold_dir=args.gold_dir,
        exchange_meta_dir=args.exchange_meta_dir,
        out_dir=args.out_dir,
        base_sha=args.base_sha or _base_sha(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tardis_free_overlap_v0")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report")
    report.add_argument("--vendor-dir", required=True)
    report.add_argument("--exchange-meta-dir", default=None)
    report.add_argument("--out-dir", required=True)
    report.add_argument("--base-sha", default=None)
    report.set_defaults(func=cmd_report)

    compare = sub.add_parser("compare")
    compare.add_argument("--vendor-dir", required=True)
    compare.add_argument("--gold-dir", default=None)
    compare.add_argument("--exchange-meta-dir", default=None)
    compare.add_argument("--out-dir", required=True)
    compare.add_argument("--base-sha", default=None)
    compare.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
