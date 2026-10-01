"""Focused checks for the deterministic D7 seed amendment. No target parse."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.d7_deterministic_fixed_seed_v1 import (
    CONFIRMATORY_SEED_DIGEST,
    SEED_MESSAGE_BYTES,
    SeedSourceAmendmentError,
    fixed_seed_digest,
    verify_seed_message,
)
from scripts.research.self_referential_contrast_v1.confirmatory_contract import (
    seed_sequence_from_confirmatory_digest,
)
from scripts.research.self_referential_contrast_v1 import seeds as seeds_module

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "scripts/research/d7_confirmatory_target_opening_v1.py"
CANONICAL = ROOT / "docs/research_data/D7_BITMEX_ACTIVITY_V0/canonical_5m.jsonl.gz"
CANONICAL_SHA = "33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c"
FORBIDDEN_SEED_FIELDS = (
    "target_source_digest",
    "adapter_digest",
    "freeze_manifest_sha256",
    "cell",
    "pi_s",
    "year_mass",
)


def test_exact_message_matches_the_required_digest() -> None:
    assert SEED_MESSAGE_BYTES.decode("utf-8") == (
        '{"hypothesis":"D7","profile":"SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1",'
        '"project":"signalbot","purpose":"CONFIRMATORY_DWB_MULTIPLIERS",'
        '"r_confirmatory":9999,"scheme":"DETERMINISTIC_FIXED_SEED_V1"}'
    )
    assert not SEED_MESSAGE_BYTES.endswith(b"\n")
    assert b"\n" not in SEED_MESSAGE_BYTES
    recomputed = hashlib.sha256(SEED_MESSAGE_BYTES).hexdigest()
    assert recomputed == CONFIRMATORY_SEED_DIGEST
    assert fixed_seed_digest().hex() == "5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e"
    text = SEED_MESSAGE_BYTES.decode("utf-8")
    for field in FORBIDDEN_SEED_FIELDS:
        assert field not in text


def test_one_byte_message_change_is_rejected() -> None:
    mutated = bytearray(SEED_MESSAGE_BYTES)
    mutated[-1] ^= 0x01
    with pytest.raises(SeedSourceAmendmentError) as raised:
        verify_seed_message(bytes(mutated))
    assert raised.value.code == "SEED_SOURCE_AMENDMENT_FAILED:MESSAGE_MISMATCH"


def test_all_256_digest_bits_enter_the_existing_seedsequence_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_generator(*_args, **_kwargs):
        raise AssertionError("confirmatory Generator must not be constructed")

    monkeypatch.setattr(seeds_module, "generator_from_digest", refuse_generator)
    digest = fixed_seed_digest()
    assert len(digest) == 32
    sequence = seed_sequence_from_confirmatory_digest(digest)
    words = [int(word) for word in sequence.entropy]
    assert len(words) == 8
    rebuilt = b"".join(word.to_bytes(4, "little") for word in words)
    assert rebuilt == digest


def test_driver_no_longer_requires_a_nist_pulse() -> None:
    tree = ast.parse(DRIVER.read_text(encoding="utf-8"))
    main_fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = [
        node.func.id
        for node in ast.walk(main_fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "_select_beacon" not in calls
    assert "_prepare_deterministic_seed" in calls
    assert "DETERMINISTIC_FIXED_SEED_V1" in DRIVER.read_text(encoding="utf-8")


def test_amendment_tests_leave_the_target_unopened() -> None:
    digest = hashlib.sha256()
    with CANONICAL.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    assert digest.hexdigest() == CANONICAL_SHA
    seed_source = (ROOT / "scripts/research/d7_deterministic_fixed_seed_v1.py").read_text(encoding="utf-8")
    assert "load_5m_bars" not in seed_source
    assert "indexed_epsilon_sampler" not in seed_source
    assert "generator_from_digest" not in seed_source
    amendment = json.loads(
        (ROOT / "docs/research/D7_CONFIRMATORY_SEED_SOURCE_AMENDMENT_V1.json").read_text(encoding="utf-8")
    )
    assert amendment["CONFIRMATORY_RNG_GENERATED"] is False
    assert amendment["D7_BITMEX_PRIMARY_TARGET_OPENED"] is False
    assert amendment["D7_PRIMARY_EFFECT_COMPUTED"] is False
    assert amendment["seed_message"] == SEED_MESSAGE_BYTES.decode("utf-8")
