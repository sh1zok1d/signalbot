"""Precommitted D7 confirmatory seed message.

The message is exact UTF-8 bytes. This module does not read the BitMEX
target, construct a Generator, or draw a confirmatory bootstrap stream.
"""

from __future__ import annotations

import hashlib

SCHEME = "DETERMINISTIC_FIXED_SEED_V1"
SEED_MESSAGE_TEXT = (
    '{"hypothesis":"D7","profile":"SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1",'
    '"project":"signalbot","purpose":"CONFIRMATORY_DWB_MULTIPLIERS",'
    '"r_confirmatory":9999,"scheme":"DETERMINISTIC_FIXED_SEED_V1"}'
)
SEED_MESSAGE_BYTES = SEED_MESSAGE_TEXT.encode("utf-8")
CONFIRMATORY_SEED_DIGEST = "5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e"
SEED_MESSAGE_ENCODING = "UTF-8"
SEED_MESSAGE_TRAILING_NEWLINE = False
SEED_MESSAGE_CANONICALIZATION = "EXACT_BYTES_ABOVE"


class SeedSourceAmendmentError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def verify_seed_message(message: bytes) -> bytes:
    """Accept only the frozen message bytes and the frozen digest."""
    if message != SEED_MESSAGE_BYTES or message.endswith(b"\n"):
        raise SeedSourceAmendmentError("SEED_SOURCE_AMENDMENT_FAILED:MESSAGE_MISMATCH")
    digest = hashlib.sha256(message).digest()
    if digest.hex() != CONFIRMATORY_SEED_DIGEST:
        raise SeedSourceAmendmentError("SEED_SOURCE_AMENDMENT_FAILED:DIGEST_MISMATCH")
    return digest


def fixed_seed_digest() -> bytes:
    return verify_seed_message(SEED_MESSAGE_BYTES)
