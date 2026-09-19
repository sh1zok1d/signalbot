"""Immutable session metadata, written before scientific data arrives."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

from scripts.research.forward_market_observability_v1.clock import capture_receipt
from scripts.research.forward_market_observability_v1.schemas import (
    SESSION_SCHEMA,
    assert_no_scientific_fields,
)
from scripts.research.forward_market_observability_v1.storage import atomic_write_json


SECRET_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "private_key",
    "authorization",
)


class SessionError(RuntimeError):
    """Session identity could not be created safely."""


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def capture_git_identity(repo: Path) -> dict[str, str]:
    return {
        "collector_git_head": _git(repo, "rev-parse", "HEAD"),
        "collector_git_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
    }


def config_sha256(config: Mapping[str, Any]) -> str:
    blob = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _reject_secrets(payload: Mapping[str, Any]) -> None:
    dumped = json.dumps(payload).lower()
    for fragment in SECRET_KEY_FRAGMENTS:
        if fragment in dumped:
            raise SessionError(f"SECRET_FIELD_FORBIDDEN:{fragment}")


def _clock_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "timezone": str(os.environ.get("TZ") or "unset"),
        "platform_time_ns_resolution": "time.time_ns",
        "monotonic": "time.monotonic_ns",
        "ntp_synchronized": None,
        "clocksource": None,
    }
    clocksource = Path("/sys/devices/system/clocksource/clocksource0/current_clocksource")
    if clocksource.is_file():
        status["clocksource"] = clocksource.read_text(encoding="utf-8").strip()
    try:
        ntp = subprocess.check_output(
            ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
            text=True,
            timeout=1,
            stderr=subprocess.DEVNULL,
        ).strip()
        status["ntp_synchronized"] = ntp
    except (OSError, subprocess.SubprocessError):
        pass
    return status


def _client_library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in ("websockets", "aiohttp"):
        try:
            module = __import__(name)
        except Exception:
            continue
        versions[name] = str(getattr(module, "__version__", "unknown"))
    return versions


def create_session(
    *,
    repo: Path,
    root: Path,
    config: Mapping[str, Any],
    infrastructure_label: str | None = None,
) -> dict[str, Any]:
    _reject_secrets(config)
    stamp = capture_receipt()
    git_ids = capture_git_identity(repo)
    session_id = str(uuid.uuid4())
    session = {
        "schema_version": SESSION_SCHEMA,
        "session_id": session_id,
        "collector_git_head": git_ids["collector_git_head"],
        "collector_git_tree": git_ids["collector_git_tree"],
        "collector_config_sha256": config_sha256(config),
        "instrument": config["instrument"],
        "source_definitions": list(config["sources"]),
        "process_start_utc": stamp.local_received_at_utc,
        "process_start_monotonic_ns": stamp.local_received_monotonic_ns,
        "hostname": socket.gethostname(),
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "client_library_versions": _client_library_versions(),
        "clock_timezone_configuration": _clock_status(),
        "infrastructure_label": infrastructure_label,
        "scientific_evidence": False,
        "authoritative_collection": False,
        "m04_fwd_created": False,
        "market_06_created": False,
    }
    if infrastructure_label == "INFRASTRUCTURE_SMOKE_TEST_ONLY":
        session["scientific_evidence"] = False
        session["smoke_data_scientifically_excluded"] = True
    assert_no_scientific_fields(session, where="session")
    session_dir = root / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(session_dir / "SESSION.json", session)
    return {"session": session, "session_dir": session_dir}
