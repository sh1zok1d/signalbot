#!/usr/bin/env python3
"""Write /opt/signalbot/.env.paired-shadow from POSTGRES_* already in the environment.

Prints the path and the mode, not the URL. Refuses to overwrite unless --replace.
Does not read or change the product .env file by itself: the caller exports
POSTGRES_* first, for example from a root shell that has already loaded it.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.paired_shadow_host import ENV_FILE, write_env_file


def main(argv: list) -> int:
    replace = argv[1:] == ["--replace"]
    if argv[1:] not in ([], ["--replace"]):
        print("usage: python3 scripts/beta/write_paired_shadow_env.py [--replace]", file=sys.stderr)
        return 2
    try:
        from common.config import _build_postgres_dsn
        dsn = _build_postgres_dsn()
    except Exception as exc:  # noqa: BLE001
        print(type(exc).__name__, file=sys.stderr)
        return 1
    target = ENV_FILE
    try:
        info = write_env_file(target, dsn, replace=replace)
    except FileExistsError:
        print("env file already exists; pass --replace to overwrite it", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"wrote {info['path']} mode {info['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
