"""Outcome-blind Binance Vision spot USDT daily-panel acquisition.

Downloads monthly 1d kline zips for 2019-12..2024-12 only. Never fetches
2025/2026. Listing bytes are pinned. Import does not download.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

UTC = timezone.utc
S3_ENDPOINT = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
VISION_HOST = "https://data.binance.vision"
PREFIX_SYMBOLS = "data/spot/monthly/klines/"
OBJECT_RE = re.compile(
    r"^data/spot/monthly/klines/([A-Z0-9]+)/1d/\1-1d-(\d{4}-\d{2})\.zip$"
)
CHECKSUM_RE = re.compile(
    r"^data/spot/monthly/klines/([A-Z0-9]+)/1d/\1-1d-(\d{4}-\d{2})\.zip\.CHECKSUM$"
)
MONTH_MIN = "2019-12"
MONTH_MAX = "2024-12"
PROTECTED_MONTH_RE = re.compile(r"(?:^|/)(2025|2026)-\d{2}(?:/|\.zip)")
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
# Top-level symbol-prefix pages are tracked scientific enumeration authority.
SYMBOL_ENUMERATION_LISTING_DOCS_REL = (
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/listings"
)
# Per-symbol ListBucket XML is acquisition runtime, not D13 snapshot identity.
PER_SYMBOL_LISTING_ARTIFACT_REL = (
    "artifacts/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/listings/per_symbol_1d"
)


class ProtectedYearRefused(RuntimeError):
    pass


class AcquisitionError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refuse_protected_key(key: str) -> None:
    if PROTECTED_MONTH_RE.search(key) or "/2025-" in key or "/2026-" in key:
        raise ProtectedYearRefused(f"PROTECTED_KEY_REFUSED:{key}")
    match = OBJECT_RE.match(key) or CHECKSUM_RE.match(key)
    if match and match.group(2) >= "2025-01":
        raise ProtectedYearRefused(f"PROTECTED_MONTH_REFUSED:{key}")


def month_allowed(month: str) -> bool:
    return MONTH_MIN <= month <= MONTH_MAX


def _http_get(url: str, *, timeout: int = 60, retries: int = 6) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "signalbot-research/discovery-sprint-04"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            time.sleep(min(32.0, 0.4 * (2**attempt)))
    raise AcquisitionError(f"GET_FAILED:{url}:{last}")


def list_bucket_page(*, prefix: str, delimiter: str | None, marker: str) -> bytes:
    query = urllib.parse.urlencode(
        {
            "prefix": prefix,
            "max-keys": "1000",
            **({"delimiter": delimiter} if delimiter else {}),
            **({"marker": marker} if marker else {}),
        }
    )
    return _http_get(S3_ENDPOINT + "?" + query)


def parse_list_bucket(xml_bytes: bytes) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    prefixes = [el.text or "" for el in root.findall("s3:CommonPrefixes/s3:Prefix", NS)]
    keys = [el.text or "" for el in root.findall("s3:Contents/s3:Key", NS)]
    truncated = (root.findtext("s3:IsTruncated", default="false", namespaces=NS) or "").lower() == "true"
    next_marker = root.findtext("s3:NextMarker", default="", namespaces=NS) or ""
    if truncated and not next_marker:
        if prefixes:
            next_marker = prefixes[-1]
        elif keys:
            next_marker = keys[-1]
    return {
        "prefixes": prefixes,
        "keys": keys,
        "truncated": truncated,
        "next_marker": next_marker,
    }


def paginate_listings(
    *,
    prefix: str,
    delimiter: str | None,
    dest_dir: Path,
    stem: str,
) -> dict[str, Any]:
    """Page ListBucket XML to dest_dir.

    Symbol-prefix enumeration pages belong under the tracked docs listings
    directory. Per-symbol 1d pages must go to PER_SYMBOL_LISTING_ARTIFACT_REL
    (gitignored artifacts/), never docs/. Raw XML is not D13_SNAPSHOT_ID.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, Any]] = []
    marker = ""
    page_i = 0
    all_prefixes: list[str] = []
    all_keys: list[str] = []
    while True:
        raw = list_bucket_page(prefix=prefix, delimiter=delimiter, marker=marker)
        page_path = dest_dir / f"{stem}_page_{page_i:04d}.xml"
        page_path.write_bytes(raw)
        parsed = parse_list_bucket(raw)
        pages.append(
            {
                "page": page_i,
                "sha256": sha256_bytes(raw),
                "bytes": len(raw),
                "prefix": prefix,
                "delimiter": delimiter,
                "marker": marker,
                "n_prefixes": len(parsed["prefixes"]),
                "n_keys": len(parsed["keys"]),
                "truncated": parsed["truncated"],
            }
        )
        all_prefixes.extend(parsed["prefixes"])
        all_keys.extend(parsed["keys"])
        if not parsed["truncated"]:
            break
        marker = parsed["next_marker"]
        if not marker:
            raise AcquisitionError(f"LISTING_TRUNCATED_WITHOUT_MARKER:{prefix}")
        page_i += 1
    return {
        "prefix": prefix,
        "delimiter": delimiter,
        "pages": pages,
        "prefixes": all_prefixes,
        "keys": all_keys,
        "listing_digest": sha256_bytes(
            json.dumps(
                {"pages": [p["sha256"] for p in pages], "prefixes": all_prefixes, "keys": all_keys},
                sort_keys=True,
            ).encode("utf-8")
        ),
    }


def usdt_symbols_from_prefixes(prefixes: list[str]) -> list[str]:
    symbols: list[str] = []
    for prefix in prefixes:
        # data/spot/monthly/klines/BTCUSDT/
        parts = prefix.strip("/").split("/")
        if len(parts) >= 5 and parts[4].endswith("USDT"):
            symbols.append(parts[4])
    return sorted(set(symbols))


def vision_url(key: str) -> str:
    return f"{VISION_HOST}/{key}"


def parse_checksum_sidecar(text: str) -> str:
    token = text.strip().split()[0]
    if len(token) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in token):
        raise AcquisitionError(f"CHECKSUM_SIDECAR_MALFORMED:{text!r}")
    return token.lower()


def download_object(key: str, dest: Path) -> dict[str, Any]:
    refuse_protected_key(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = _http_get(vision_url(key), timeout=120)
    dest.write_bytes(body)
    return {
        "key": key,
        "bytes": len(body),
        "sha256": sha256_bytes(body),
        "url": vision_url(key),
    }
