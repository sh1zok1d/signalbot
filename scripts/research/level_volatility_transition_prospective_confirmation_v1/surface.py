"""Prospective start is the first UTC midnight strictly after the design commit.

Resolution uses the commit timestamp only. No market bar is consulted.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1_DESIGN.md"
MANIFEST = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_SURFACE_V1.json"
RECOVERY_LOG = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_RECOVERY_V1.jsonl"
PEEK_FLAG = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_PEEK_V1.json"
PAIR_MAP = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_PAIR_MAP_V1.json"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1_RESULT.md"

UTC = dt.timezone.utc


def parse_utc(text: str) -> dt.datetime:
    stamp = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return stamp.astimezone(UTC)


def first_utc_midnight_after(commit_time: dt.datetime) -> dt.datetime:
    """First 00:00 UTC strictly later than the design commit."""
    commit_time = commit_time.astimezone(UTC)
    midnight = commit_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if midnight > commit_time:
        return midnight
    return midnight + dt.timedelta(days=1)


def to_iso(stamp: dt.datetime) -> str:
    return stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_ms(stamp: dt.datetime) -> int:
    return int(stamp.astimezone(UTC).timestamp() * 1000)


def canonical(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "manifest_digest"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_of(payload: dict) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def design_commit() -> tuple[str, dt.datetime]:
    sha = _git("log", "-1", "--format=%H", "--", str(DESIGN.relative_to(ROOT)))
    if not sha:
        raise RuntimeError("design note is not committed")
    raw = _git("log", "-1", "--format=%cI", sha)
    return sha, parse_utc(raw)


def build_manifest(design_sha: str, commit_time: dt.datetime, *, code_version: str) -> dict:
    start = first_utc_midnight_after(commit_time)
    if start <= commit_time:
        raise RuntimeError("prospective start is not strictly after the design commit")
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "accrual": K.ACCRUAL,
        "surface_evidence_class": K.SURFACE_EVIDENCE_CLASS,
        "claim_ceiling": K.CLAIM_CEILING,
        "design_sha": design_sha,
        "design_commit_time": to_iso(commit_time),
        "prospective_start_utc": to_iso(start),
        "prospective_start_ms": to_ms(start),
        "instrument": K.INSTRUMENT,
        "venue": K.VENUE,
        "dataset_id": K.DATASET_ID,
        "bar_semantics": (
            "complete UTC 5m bins aggregated from Binance USD-M BTCUSDT 1m klines "
            "by scripts.research.dh1.data.aggregate_1m_to_5m; five minutes present; no fill; "
            "RV uses close only"
        ),
        "warmup_policy": K.PRE_START_DATA_ROLE,
        "eligible_level_kinds": list(K.LEVEL_KINDS),
        "event_start_rule": "episode_active_start >= PROSPECTIVE_START_UTC",
        "checkpoint_weeks": list(K.CHECKPOINT_WEEKS),
        "min_matched_path_complete_pairs": K.MIN_MATCHED_PATH_COMPLETE_PAIRS,
        "min_completed_iso_weeks": K.MIN_COMPLETED_ISO_WEEKS,
        "max_accrual_weeks": K.MAX_ACCRUAL_WEEKS,
        "bootstrap_draws": K.BOOT_DRAWS,
        "bootstrap_seed": K.BOOT_SEED,
        "practical_bar_log": K.PRACTICAL_LOG,
        "practical_multiple": K.PRACTICAL_MULTIPLE,
        "code_version": code_version,
        "forward_panel_path": None,
        "exact_outcome_read": False,
        "pair_map_frozen": False,
        "cohort_closed": False,
    }
    payload["manifest_digest"] = digest_of(payload)
    return payload


def write_manifest(payload: dict, path: Path = MANIFEST) -> None:
    if path.exists():
        raise RuntimeError("surface manifest already exists and is immutable")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_manifest(path: Path = MANIFEST) -> dict:
    payload = json.loads(path.read_text())
    if digest_of(payload) != payload.get("manifest_digest"):
        raise RuntimeError("surface manifest digest mismatch")
    start = parse_utc(payload["prospective_start_utc"])
    commit_time = parse_utc(payload["design_commit_time"])
    if start != first_utc_midnight_after(commit_time):
        raise RuntimeError("prospective start does not match the design-commit rule")
    if start <= commit_time:
        raise RuntimeError("prospective start is not strictly after the design commit")
    if payload.get("exact_outcome_read"):
        raise RuntimeError("manifest claims an outcome read during setup")
    return payload


def assert_recovery_interval(start_ms: int, prospective_start_ms: int) -> None:
    if int(start_ms) < int(prospective_start_ms):
        raise RuntimeError("recovery before prospective start is backdating")


def append_recovery(record: dict, *, prospective_start_ms: int, path: Path = RECOVERY_LOG) -> None:
    assert_recovery_interval(int(record["start_ms"]), prospective_start_ms)
    if record.get("outcomes_consulted"):
        raise RuntimeError("recovery must not consult the transition")
    line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
