"""Private beta V0.2 — bounded operator wrapper around `main.py --beta-bootstrap`.

    python -m runtime.beta_bootstrap_runner [--max-iterations N]

Each iteration runs the EXISTING bootstrap command unchanged, as its own process
(`main.py --beta-bootstrap --beta-json`, one bounded batch of at most
`bootstrap.max_buckets_per_run` buckets). The loop:

* stops with an error immediately on any non-zero exit, unparsable output, or a
  status other than OK / PARTIAL (e.g. DISABLED, LOCKED, DB_UNAVAILABLE);
* stops with an error if a PARTIAL batch made no progress;
* stops with an error if the bootstrap is still incomplete after N iterations;
* after completion, runs ONE more bootstrap as an idempotency check. That run
  may only write the buckets that closed after the previous run's target
  (the target is "latest closed bucket" and moves with the clock); anything
  more is unexpected work and fails the wrapper.

Exit codes: 0 complete and verified; 2 bootstrap error; 3 iteration limit
reached; 4 idempotency verification failed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional, TextIO

DEFAULT_MAX_ITERATIONS = 40      # 30d = 8641 buckets / 288 per run -> 31 runs, plus slack
MAX_ITERATIONS_CAP = 100
BUCKET = timedelta(minutes=5)
ROOT = Path(__file__).resolve().parent.parent

EXIT_OK, EXIT_ERROR, EXIT_LIMIT, EXIT_VERIFY = 0, 2, 3, 4


class BootstrapRunError(Exception):
    pass


def invoke_bootstrap_subprocess() -> dict:
    """One `main.py --beta-bootstrap --beta-json` run; stdout carries exactly one JSON object."""
    proc = subprocess.run([sys.executable, str(ROOT / "main.py"), "--beta-bootstrap", "--beta-json",
                           "--log-level", "WARNING"], cwd=ROOT, capture_output=True, text=True)
    try:
        report = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        raise BootstrapRunError(f"bootstrap exited {proc.returncode} without a JSON report") from None
    if proc.returncode != 0:
        raise BootstrapRunError(f"bootstrap exited {proc.returncode} (status {report.get('status')})")
    return report


def _ts(v) -> Optional[datetime]:
    return datetime.fromisoformat(v) if isinstance(v, str) else v


def _progress(out: TextIO, label: str, rep: dict) -> None:
    print(f"[beta-bootstrap] {label}: status={rep.get('status')} written={rep.get('written')} "
          f"skipped_existing={rep.get('skipped_existing')} unmaterialized={rep.get('unmaterialized')} "
          f"last_bucket={rep.get('last_bucket')} target={rep.get('target')} "
          f"complete={rep.get('complete')}", file=out, flush=True)


def _checked(invoke: Callable[[], dict]) -> dict:
    rep = invoke()
    if rep.get("status") not in ("OK", "PARTIAL"):
        raise BootstrapRunError(f"bootstrap returned status {rep.get('status')}")
    return rep


def run_until_complete(invoke: Callable[[], dict], *, max_iterations: int = DEFAULT_MAX_ITERATIONS,
                       out: TextIO = sys.stdout) -> int:
    if not 1 <= max_iterations <= MAX_ITERATIONS_CAP:
        raise ValueError(f"max_iterations must be in [1, {MAX_ITERATIONS_CAP}]")
    last = None
    try:
        for i in range(1, max_iterations + 1):
            rep = _checked(invoke)
            _progress(out, f"iteration {i}/{max_iterations}", rep)
            if rep.get("complete") is True:
                last = rep
                break
            if (rep.get("written") or 0) + (rep.get("skipped_existing") or 0) == 0:
                raise BootstrapRunError("PARTIAL batch made no progress")
        else:
            print(f"[beta-bootstrap] FAILED: still incomplete after {max_iterations} iterations",
                  file=out, flush=True)
            return EXIT_LIMIT
        verify = _checked(invoke)
        _progress(out, "idempotency verification", verify)
    except BootstrapRunError as exc:
        print(f"[beta-bootstrap] FAILED: {exc}", file=out, flush=True)
        return EXIT_ERROR
    prev_target, new_target = _ts(last.get("target")), _ts(verify.get("target"))
    allowed = max(0, int((new_target - prev_target) / BUCKET)) if prev_target and new_target else 0
    written = verify.get("written") or 0
    if verify.get("complete") is not True or written > allowed:
        print(f"[beta-bootstrap] FAILED: verification wrote {written} bucket(s); only {allowed} "
              f"newly closed bucket(s) were expected", file=out, flush=True)
        return EXIT_VERIFY
    print(f"[beta-bootstrap] COMPLETE and verified (verification wrote {written} newly closed "
          f"bucket(s), allowed {allowed})", file=out, flush=True)
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the beta bootstrap until complete, then verify.")
    ap.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS,
                    help=f"hard bound on bootstrap runs (1..{MAX_ITERATIONS_CAP}, "
                         f"default {DEFAULT_MAX_ITERATIONS})")
    args = ap.parse_args(argv)
    if not 1 <= args.max_iterations <= MAX_ITERATIONS_CAP:
        ap.error(f"--max-iterations must be in [1, {MAX_ITERATIONS_CAP}]")
    return run_until_complete(invoke_bootstrap_subprocess, max_iterations=args.max_iterations)


if __name__ == "__main__":
    sys.exit(main())
