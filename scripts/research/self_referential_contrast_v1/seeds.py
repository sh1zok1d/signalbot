"""Domain-separated seeds.

Validation worlds are derived from the predeclared master validation seed.
The confirmatory beacon stream is a different purpose and is not fetched
or expanded into multiplier draws here.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Sequence

import numpy as np

from scripts.research.self_referential_contrast_v1.constants import (
    ADMISSION_SEED_PURPOSE,
    BEACON_ID,
    CONFIRMATORY_PROFILE_VERSION,
    CONFIRMATORY_PURPOSE,
    MASTER_SEED_CANONICAL,
    PROFILE_ID,
)


def master_validation_seed() -> bytes:
    return hashlib.sha256(MASTER_SEED_CANONICAL.encode("utf-8")).digest()


def world_entropy(
    *,
    suite_id: str,
    configuration_id: str,
    world_index: int,
    purpose: str,
    master_seed: bytes | None = None,
) -> bytes:
    """HMAC digest for one world. No worker id and no execution order."""
    key = master_validation_seed() if master_seed is None else master_seed
    message = (
        "v1\n"
        f"suite:{suite_id}\n"
        f"config:{configuration_id}\n"
        f"world:{int(world_index)}\n"
        f"purpose:{purpose}\n"
    ).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).digest()


def seed_sequence_from_digest(digest: bytes, spawn_key: Sequence[int] = ()) -> np.random.SeedSequence:
    if len(digest) != 32:
        raise ValueError("seed digest must be 32 bytes")
    words = [int.from_bytes(digest[i : i + 4], "little") for i in range(0, 32, 4)]
    return np.random.SeedSequence(words, spawn_key=tuple(int(part) for part in spawn_key))


def generator_from_digest(digest: bytes, spawn_key: Sequence[int] = ()) -> np.random.Generator:
    sequence = seed_sequence_from_digest(digest, spawn_key)
    return np.random.Generator(np.random.PCG64(sequence))


def confirmatory_hmac_digest(
    *,
    tree: str,
    adapter_digest: str,
    beacon_time: str,
    beacon_value: str,
    purpose: str = CONFIRMATORY_PURPOSE,
) -> bytes:
    """Message builder from the freeze amendment. Does not contact a beacon."""
    key = f"{PROFILE_ID}/{CONFIRMATORY_PROFILE_VERSION}".encode("utf-8")
    message = (
        "v1\n"
        f"tree:{tree}\n"
        f"adapter:{adapter_digest}\n"
        f"beacon_id:{BEACON_ID}\n"
        f"beacon_time:{beacon_time}\n"
        f"beacon_value:{beacon_value}\n"
        f"purpose:{purpose}\n"
    ).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).digest()


def admission_purpose() -> str:
    return ADMISSION_SEED_PURPOSE
