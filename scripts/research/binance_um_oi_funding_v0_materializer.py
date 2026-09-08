#!/usr/bin/env python3
"""Acquire the frozen B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0 Vision snapshot.

This CLI does not:

- authorize B2-06 science or crowding thresholds;
- invent funding publication latency;
- open 2025 validation or 2026 OOS;
- accept a period/source override.

Production acquisition requires ``--allow-acquire`` against a clean Git HEAD
that already contains the materializer/contract blobs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.research.binance_um_oi_funding_v0_materializer_lib import (
    DEFAULT_DATASET_ROOT,
    MATERIALIZER_VERSION,
    RequestedArchiveObject,
    StrictPrefetchFetch,
    dumps_deterministic,
    expected_joint_funding_months,
    expected_joint_oi_days,
    frozen_requested_objects,
    retrying_urllib_fetch,
    run_materialization,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _prefetch(
    objects: list[RequestedArchiveObject],
    *,
    workers: int,
) -> StrictPrefetchFetch:
    urls: list[str] = []
    for item in objects:
        urls.append(item.zip_url)
        urls.append(item.checksum_url)
    cache: dict[str, tuple[bytes | None, int]] = {}
    errors: list[str] = []

    def one(url: str) -> tuple[str, tuple[bytes | None, int] | BaseException]:
        try:
            return url, retrying_urllib_fetch(url)
        except BaseException as exc:  # noqa: BLE001 - fail closed per URL
            return url, exc

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(one, url) for url in urls]
        for future in as_completed(futures):
            url, result = future.result()
            if isinstance(result, BaseException):
                errors.append(f"{url}: {result}")
                continue
            cache[url] = result
    if errors:
        preview = "; ".join(errors[:8])
        raise SystemExit(f"fail-closed prefetch errors ({len(errors)}): {preview}")
    missing = [url for url in urls if url not in cache]
    if missing:
        raise SystemExit(f"prefetch incomplete: {missing[:5]}")
    return StrictPrefetchFetch(cache)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the frozen Binance USD-M BTCUSDT OI/funding snapshot. "
            "Does not authorize B2-06 research."
        )
    )
    parser.add_argument("--allow-acquire", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--dataset-root", type=Path, default=None)
    parser.add_argument("--authority-commit", default=None)
    parser.add_argument("--authority-tree", default=None)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--copy-git-evidence", action="store_true", default=True)
    parser.add_argument("--no-copy-git-evidence", action="store_true")
    args = parser.parse_args(argv)

    if not args.allow_acquire:
        print(
            "refusing to download: pass --allow-acquire after reviewing the "
            "frozen joint period [2020-09-01, 2025-01-01)",
            file=sys.stderr,
        )
        return 2
    if hasattr(args, "period") or hasattr(args, "start") or hasattr(args, "end"):
        print("period override is forbidden", file=sys.stderr)
        return 2

    repo_root = args.repo_root.resolve()
    dataset_root = (
        args.dataset_root.resolve()
        if args.dataset_root is not None
        else (repo_root / DEFAULT_DATASET_ROOT).resolve()
    )
    commit = args.authority_commit or _git(repo_root, "rev-parse", "HEAD")
    tree = args.authority_tree or _git(repo_root, "rev-parse", "HEAD^{tree}")
    objects = frozen_requested_objects()
    if len(expected_joint_oi_days()) != 1583 or len(expected_joint_funding_months()) != 52:
        print("frozen joint coverage drifted", file=sys.stderr)
        return 2
    print(
        f"materializer {MATERIALIZER_VERSION}: prefetching {len(objects)} "
        f"archives + checksums against {commit}",
        file=sys.stderr,
    )
    fetch = _prefetch(objects, workers=args.workers)
    result = run_materialization(
        repo_root=repo_root,
        dataset_root=dataset_root,
        fetch=fetch,
        authority_commit_sha=commit,
        authority_tree_sha=tree,
        copy_git_evidence=not args.no_copy_git_evidence,
    )
    summary = {
        "snapshot_id": result["snapshot"]["snapshot_id"],
        "snapshot_manifest_sha256": result["hashes"]["snapshot_manifest_sha256"],
        "quality": {
            key: result["quality"][key]
            for key in (
                "expected_oi_objects",
                "expected_funding_objects",
                "fetched_oi_objects",
                "fetched_funding_objects",
                "accepted_oi_objects",
                "accepted_funding_objects",
                "rejected_oi_objects",
                "rejected_funding_objects",
                "raw_byte_total",
                "normalized_byte_total",
                "research_authorized",
                "outcome_access_authorized",
                "b2_06_evaluator_enabled",
                "funding_publication_semantics_status",
                "b2_06_inputs_legally_consumable",
            )
        },
        "git_commit": commit,
        "git_tree": tree,
    }
    print(dumps_deterministic(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
