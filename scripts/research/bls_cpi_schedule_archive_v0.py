"""BLS CPI release-schedule archive V0 (data provenance only).

Builds a point-in-time CPI release *schedule* dataset from dated Wayback
captures of the first-party BLS page
``https://www.bls.gov/schedule/news_release/cpi.htm``.

Boundary: schedule metadata only. No CPI values, no market data, no
event-window returns, no protected 2025/2026 market values. Events whose
scheduled release falls outside 2020-01-01..2024-12-31 are inventoried
separately as metadata only.

Subcommands:
  acquire   network: CDX listing + exact archived bytes into ``raw/``
  build     offline, deterministic: ``raw/`` -> dataset JSON files
  validate  offline: recompute and check every dataset invariant
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[2]
DATASET_ID = "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0"
SCHEMA_VERSION = "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0.1"
DATASET_DIR = REPO / "docs/research_data" / DATASET_ID
RAW_DIR = DATASET_DIR / "raw"
DST_AUTHORITY_PATH = "docs/research/DISCOVERY_SPRINT_04.json"
DST_AUTHORITY_POINTER = "CARDS.D12.DATASET_OR_SOURCE_AUTHORITY.US_TRANSITION_DAYS"
SERIES = "CPI_ALL_ITEMS_US_CITY_AVERAGE"
TIMEZONE = "America/New_York"
SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"
RELEASE_ARCHIVE_URL = "https://www.bls.gov/bls/news-release/cpi.htm"
CDX_QUERY = (
    "http://web.archive.org/cdx/search/cdx?url=bls.gov/schedule/news_release/cpi.htm"
    "&from=2019&to=2024&output=json&fl=timestamp,original,statuscode,digest,length"
    "&filter=statuscode:200"
)
USER_AGENT = "signalbot-research-provenance (contact via repository)"
LEGAL_FIRST_DATE = "2020-01-01"
LEGAL_LAST_DATE = "2024-12-31"
WINDOWS_H = (6, 12, 24)
PROVENANCE_STATUSES = (
    "VERIFIED_PREANNOUNCED",
    "VERIFIED_RESCHEDULED",
    "UNRESOLVED_POINT_IN_TIME",
    "EXCLUDED_OTHER",
)
DATASET_FILES = (
    "EVENTS.json",
    "OUT_OF_RANGE_INVENTORY.json",
    "SOURCE_AUTHORITY.json",
    "SNAPSHOT_LEDGER.json",
)
EVENT_FIELDS = (
    "EVENT_ID",
    "SERIES",
    "REFERENCE_PERIOD",
    "SCHEDULED_RELEASE_DATE",
    "SCHEDULED_RELEASE_LOCAL",
    "TIMEZONE",
    "UTC_OFFSET",
    "LOCAL_ZONE_ABBREV",
    "SCHEDULED_RELEASE_UTC",
    "DST_CONVERSION_AUTHORITY",
    "EARLIEST_VERIFIED_PUBLICATION",
    "WINDOW_EVIDENCE",
    "SAFE_FOR_W6",
    "SAFE_FOR_W12",
    "SAFE_FOR_W24",
    "SCHEDULE_HISTORY",
    "PRIMARY_BLS_SOURCE",
    "ARCHIVE_EVIDENCE",
    "REALIZED_DATE_CROSSCHECK",
    "PROVENANCE_STATUS",
)
FORBIDDEN_KEY_TOKENS = (
    "VALUE", "INDEX_LEVEL", "PERCENT", "PCT", "CHANGE", "SURPRISE", "CONSENSUS",
    "ACTUAL", "FORECAST", "PRICE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME",
    "RETURN", "OHLC", "BTC", "PNL",
)

MONTHS_FULL = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)
MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "June": 6,
    "Jul": 7, "July": 7, "Aug": 8, "Sep": 9, "Sept": 9, "Oct": 10, "Nov": 11,
    "Dec": 12,
}
_ROW = re.compile(
    r"(" + "|".join(MONTHS_FULL) + r") (\d{4}) "
    r"(Jan|Feb|Mar|Apr|May|June|Jun|July|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.? "
    r"(\d{1,2}), (\d{4}) (\d{2}):(\d{2}) (AM|PM)"
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cdx_sha1_base32(data: bytes) -> str:
    """Wayback CDX ``digest``: base32 SHA-1 of the archived payload bytes."""
    return base64.b32encode(hashlib.sha1(data).digest()).decode()


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def dump_json(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=True) + "\n").encode()


def decode_payload(raw: bytes) -> bytes:
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def page_text(raw: bytes) -> str:
    s = decode_payload(raw).decode("utf-8", "replace")
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).replace("\xa0", " ")


def parse_schedule_rows(raw: bytes) -> list[tuple[str, str, str]]:
    """Return (reference_period YYYY-MM, release_date YYYY-MM-DD, local HH:MM)."""
    out = []
    for m in _ROW.findall(page_text(raw)):
        ref = f"{m[1]}-{MONTHS_FULL.index(m[0]) + 1:02d}"
        day = f"{m[4]}-{MONTH_ABBR[m[2]]:02d}-{int(m[3]):02d}"
        hour = int(m[5]) % 12 + (12 if m[7] == "PM" else 0)
        out.append((ref, day, f"{hour:02d}:{m[6]}"))
    return out


def wayback_ts_to_iso(ts: str) -> str:
    return dt.datetime.strptime(ts, "%Y%m%d%H%M%S").strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def iso_utc(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- DST -------------------------------------------------------------------

def load_us_transitions(repo: Path = REPO) -> dict[int, tuple[str, str]]:
    d = json.loads((repo / DST_AUTHORITY_PATH).read_text())
    days = d["CARDS"]["D12"]["DATASET_OR_SOURCE_AUTHORITY"]["US_TRANSITION_DAYS"]
    return {int(y): (v[0], v[1]) for y, v in days.items()}


def statutory_us_transitions(year: int) -> tuple[str, str]:
    """Energy Policy Act 2005: second Sunday of March, first Sunday of November."""
    def nth_sunday(month: int, n: int) -> dt.date:
        d = dt.date(year, month, 1)
        d += dt.timedelta(days=(6 - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)
    return nth_sunday(3, 2).isoformat(), nth_sunday(11, 1).isoformat()


def local_to_utc(day: str, hhmm: str, transitions: dict[int, tuple[str, str]]) -> tuple[str, str, str]:
    """Convert America/New_York wall time on a non-transition weekday to UTC.

    Uses only the frozen statutory transition table. Times between 00:00 and
    03:00 on a transition Sunday are ambiguous/non-existent and are refused.
    """
    year = int(day[:4])
    if year not in transitions:
        raise KeyError(f"no frozen US DST transitions for {year}")
    start, end = transitions[year]
    if day in (start, end) and hhmm < "03:00":
        raise ValueError(f"ambiguous wall time on transition day {day} {hhmm}")
    edt = start <= day < end
    offset = dt.timedelta(hours=-4 if edt else -5)
    local = dt.datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M")
    utc = (local - offset).replace(tzinfo=dt.timezone.utc)
    return iso_utc(utc), ("-04:00" if edt else "-05:00"), ("EDT" if edt else "EST")


def zoneinfo_utc(day: str, hhmm: str) -> str:
    local = dt.datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(TIMEZONE))
    return iso_utc(local)


# --- acquisition (network) -------------------------------------------------

def _curl(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["curl", "-s", "-m", "60", "-A", USER_AGENT, *args], capture_output=True)


def acquire(raw_dir: Path = RAW_DIR, sleep_s: float = 0.5) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "wayback").mkdir(exist_ok=True)
    (raw_dir / "live").mkdir(exist_ok=True)
    log_path = raw_dir / "ACQUISITION_LOG.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"CAPTURES": {}, "LIVE": {}}
    cdx_path = raw_dir / "cdx/bls_schedule_news_release_cpi_2019_2024.cdx.json"
    if not cdx_path.exists():
        cdx_path.parent.mkdir(exist_ok=True)
        r = _curl([CDX_QUERY])
        cdx_path.write_bytes(r.stdout)
        log["CDX"] = {"QUERY": CDX_QUERY, "RETRIEVED_AT_UTC": iso_utc(dt.datetime.now(dt.timezone.utc)),
                      "SHA256": sha256_hex(r.stdout)}
    rows = json.loads(cdx_path.read_bytes())[1:]
    for ts, original, _status, _digest, _length in rows:
        if ts in log["CAPTURES"]:
            continue
        url = f"https://web.archive.org/web/{ts}id_/{original}"
        tmp = raw_dir / "wayback/.partial"
        r = _curl(["-o", str(tmp), "-w", "%{http_code} %{redirect_url}", url])
        code, _, redirect = r.stdout.decode().partition(" ")
        entry = {"ARCHIVE_URL": url, "HTTP_STATUS": int(code or 0),
                 "RETRIEVED_AT_UTC": iso_utc(dt.datetime.now(dt.timezone.utc))}
        if code == "200" and tmp.exists() and tmp.stat().st_size > 0:
            data = tmp.read_bytes()
            h = sha256_hex(data)
            (raw_dir / f"wayback/{h}.bin").write_bytes(data)
            entry.update({"SHA256": h, "BYTE_LENGTH": len(data)})
        else:
            entry.update({"SHA256": None, "BYTE_LENGTH": 0, "REDIRECT_TARGET": redirect or None})
        tmp.unlink(missing_ok=True)
        log["CAPTURES"][ts] = entry
        log_path.write_bytes(dump_json(log))
        time.sleep(sleep_s)
    for role, url in (("CURRENT_SCHEDULE_PAGE", SCHEDULE_URL), ("RELEASE_ARCHIVE_PAGE", RELEASE_ARCHIVE_URL)):
        if role in log["LIVE"]:
            continue
        r = _curl([url])
        h = sha256_hex(r.stdout)
        (raw_dir / f"live/{h}.bin").write_bytes(r.stdout)
        log["LIVE"][role] = {"URL": url, "SHA256": h, "BYTE_LENGTH": len(r.stdout),
                             "RETRIEVED_AT_UTC": iso_utc(dt.datetime.now(dt.timezone.utc))}
    log_path.write_bytes(dump_json(log))


# --- build (offline, deterministic) ----------------------------------------

def realized_release_dates(raw: bytes) -> set[str]:
    links = re.findall(rb"archives/cpi_(\d{2})(\d{2})(\d{4})\.(?:htm|pdf)", raw)
    return {f"{y.decode()}-{m.decode()}-{d.decode()}" for m, d, y in links}


def event_id(ref: str) -> str:
    return f"BLS_CPI_REF_{ref.replace('-', '_')}"


def classify_event(ref: str, observations: list[tuple[str, str, str, str]],
                   transitions: dict[int, tuple[str, str]]) -> dict:
    """Classify one reference period from dated observations.

    ``observations``: (capture_iso_utc, snapshot_id, release_date, local_time),
    one per obtained capture that lists this reference period.
    """
    obs = sorted(observations)
    schedules = sorted({(o[2], o[3]) for o in obs})
    history = [{"FIRST_SEEN_UTC": min(o[0] for o in obs if (o[2], o[3]) == s),
                "LAST_SEEN_UTC": max(o[0] for o in obs if (o[2], o[3]) == s),
                "RELEASE_DATE": s[0], "RELEASE_LOCAL": s[1],
                "SNAPSHOT_COUNT": sum(1 for o in obs if (o[2], o[3]) == s)} for s in schedules]
    history.sort(key=lambda h: h["FIRST_SEEN_UTC"])

    # Candidate release instant: schedule in force at the latest capture before
    # each candidate's own T-6h. Iterate to a fixed point over observed schedules.
    def utc_of(s):
        return local_to_utc(s[0], s[1], transitions)[0]

    def latest_before(cutoff: dt.datetime):
        prior = [o for o in obs if parse_iso_utc(o[0]) < cutoff]
        return prior[-1] if prior else None

    final = None
    for s in schedules:
        t = parse_iso_utc(utc_of(s))
        lb = latest_before(t - dt.timedelta(hours=6))
        if lb is not None and (lb[2], lb[3]) == s:
            if final is None or t > parse_iso_utc(utc_of(final)):
                final = s
    base = {"REFERENCE_PERIOD": ref, "SCHEDULE_HISTORY_RAW": history}
    if final is None:
        return {**base, "FINAL": None, "WINDOWS": {}, "STATUS": "UNRESOLVED_POINT_IN_TIME"}
    t_utc = parse_iso_utc(utc_of(final))
    windows = {}
    for w in WINDOWS_H:
        cutoff = t_utc - dt.timedelta(hours=w)
        lb = latest_before(cutoff)
        safe = lb is not None and (lb[2], lb[3]) == final
        windows[f"W{w}"] = {
            "CUTOFF_UTC": iso_utc(cutoff),
            "LATEST_PRE_CUTOFF_SNAPSHOT_ID": lb[1] if lb else None,
            "LATEST_PRE_CUTOFF_CAPTURE_UTC": lb[0] if lb else None,
            "LATEST_PRE_CUTOFF_SCHEDULE": ({"RELEASE_DATE": lb[2], "RELEASE_LOCAL": lb[3]} if lb else None),
            "EVIDENCE_LEAD_HOURS": (round((cutoff - parse_iso_utc(lb[0])).total_seconds() / 3600, 3) if lb else None),
            "SCHEDULE_MATCHES_FINAL_PREWINDOW": safe,
        }
    w6 = windows["W6"]["SCHEDULE_MATCHES_FINAL_PREWINDOW"]
    w12 = w6 and windows["W12"]["SCHEDULE_MATCHES_FINAL_PREWINDOW"]
    w24 = w12 and windows["W24"]["SCHEDULE_MATCHES_FINAL_PREWINDOW"]
    post = [o for o in obs if parse_iso_utc(o[0]) >= t_utc - dt.timedelta(hours=6)]
    post_contradiction = any((o[2], o[3]) != final for o in post)
    if post_contradiction:
        status = "UNRESOLVED_POINT_IN_TIME"
        w6 = w12 = w24 = False
    elif len(schedules) > 1:
        status = "VERIFIED_RESCHEDULED" if w6 else "UNRESOLVED_POINT_IN_TIME"
    else:
        status = "VERIFIED_PREANNOUNCED" if w6 else "UNRESOLVED_POINT_IN_TIME"
    return {**base, "FINAL": final, "WINDOWS": windows, "SAFE": (w6, w12, w24),
            "POST_CUTOFF_CONTRADICTION": post_contradiction, "STATUS": status}


def build(raw_dir: Path = RAW_DIR, repo: Path = REPO) -> dict[str, dict]:
    log = json.loads((raw_dir / "ACQUISITION_LOG.json").read_bytes())
    cdx_bytes = (raw_dir / "cdx/bls_schedule_news_release_cpi_2019_2024.cdx.json").read_bytes()
    cdx_rows = json.loads(cdx_bytes)[1:]
    transitions = load_us_transitions(repo)
    dst_file_sha = sha256_hex((repo / DST_AUTHORITY_PATH).read_bytes())

    live = log["LIVE"]
    archive_raw = (raw_dir / f"live/{live['RELEASE_ARCHIVE_PAGE']['SHA256']}.bin").read_bytes()
    realized = realized_release_dates(archive_raw)

    by_ref: dict[str, list] = {}
    snapshots = []
    ts_counts: dict[str, int] = {}
    for row in cdx_rows:
        ts_counts[row[0]] = ts_counts.get(row[0], 0) + 1
    for ts, original, cdx_status, cdx_digest, cdx_length in sorted(cdx_rows):
        entry = dict(log["CAPTURES"][ts])
        sid = f"WB_{ts}" if ts_counts[ts] == 1 else f"WB_{ts}_{cdx_digest[:8]}"
        digest_match = None
        if entry["SHA256"] is not None:
            raw = (raw_dir / f"wayback/{entry['SHA256']}.bin").read_bytes()
            if sha256_hex(raw) != entry["SHA256"]:
                raise ValueError(f"raw bytes mismatch for {sid}")
            digest_match = cdx_sha1_base32(raw) == cdx_digest
            if ts_counts[ts] > 1 and not digest_match:
                entry.update({"SHA256": None, "BYTE_LENGTH": 0,
                              "REDIRECT_TARGET": None, "NOT_OBTAINED_REASON": "DUPLICATE_TIMESTAMP_OTHER_PAYLOAD_SERVED"})
                digest_match = None
        snap = {
            "SNAPSHOT_ID": sid,
            "SOURCE_URL": original,
            "ARCHIVE_URL": entry["ARCHIVE_URL"],
            "ARCHIVE_TIMESTAMP_UTC": wayback_ts_to_iso(ts),
            "PAGE_TIMESTAMP": None,
            "CDX_STATUS": cdx_status,
            "CDX_DIGEST_SHA1_BASE32": cdx_digest,
            "CDX_LENGTH": int(cdx_length),
            "HTTP_STATUS": entry["HTTP_STATUS"],
            "RETRIEVED_AT_UTC": entry["RETRIEVED_AT_UTC"],
            "OBTAINED": entry["SHA256"] is not None,
            "SHA256": entry["SHA256"],
            "BYTE_LENGTH": entry["BYTE_LENGTH"],
            "CDX_DIGEST_MATCH": digest_match,
        }
        if entry["SHA256"] is None:
            reason = entry.get("NOT_OBTAINED_REASON", "WAYBACK_REDIRECT_TO_OTHER_CAPTURE")
            snap.update({"ROLE": f"NOT_OBTAINED_{reason}", "REDIRECT_TARGET": entry.get("REDIRECT_TARGET"),
                         "RAW_PATH": None, "CONTENT_ENCODING_AS_SERVED": None, "DECODED_SHA256": None,
                         "PARSED_ROW_COUNT": 0, "SUPPORTED_EVENT_IDS": [], "OUT_OF_RANGE_REFERENCE_PERIODS": []})
            snapshots.append(snap)
            continue
        rows = parse_schedule_rows(raw)
        refs_in, refs_out = [], []
        for ref, day, hhmm in rows:
            (refs_in if LEGAL_FIRST_DATE <= day <= LEGAL_LAST_DATE else refs_out).append(ref)
            if digest_match:
                by_ref.setdefault(ref, []).append((wayback_ts_to_iso(ts), sid, day, hhmm))
        if not digest_match:
            role = "OBTAINED_CDX_DIGEST_MISMATCH_NOT_EVIDENCE"
            refs_in, refs_out = [], []
        else:
            role = "POINT_IN_TIME_SCHEDULE_EVIDENCE" if refs_in else "METADATA_ONLY_OUT_OF_RANGE"
        snap.update({
            "ROLE": role,
            "RAW_PATH": f"raw/wayback/{entry['SHA256']}.bin",
            "CONTENT_ENCODING_AS_SERVED": "gzip" if raw[:2] == b"\x1f\x8b" else "identity",
            "DECODED_SHA256": sha256_hex(decode_payload(raw)),
            "PARSED_ROW_COUNT": len(rows),
            "SUPPORTED_EVENT_IDS": sorted(event_id(r) for r in refs_in),
            "OUT_OF_RANGE_REFERENCE_PERIODS": sorted(refs_out),
        })
        snapshots.append(snap)
    for role, item in sorted(live.items()):
        snapshots.append({
            "SNAPSHOT_ID": f"LIVE_{role}",
            "SOURCE_URL": item["URL"],
            "ARCHIVE_URL": None,
            "ARCHIVE_TIMESTAMP_UTC": None,
            "PAGE_TIMESTAMP": None,
            "HTTP_STATUS": 200,
            "RETRIEVED_AT_UTC": item["RETRIEVED_AT_UTC"],
            "OBTAINED": True,
            "SHA256": item["SHA256"],
            "BYTE_LENGTH": item["BYTE_LENGTH"],
            "RAW_PATH": f"raw/live/{item['SHA256']}.bin",
            "ROLE": ("CURRENT_FIRST_PARTY_REFERENCE_NOT_POINT_IN_TIME" if role == "CURRENT_SCHEDULE_PAGE"
                     else "REALIZED_DATE_CROSSCHECK_NOT_POINT_IN_TIME_AUTHORITY"),
            "SUPPORTED_EVENT_IDS": [],
        })

    events, out_of_range = [], []
    for ref in sorted(by_ref):
        obs = by_ref[ref]
        days = {o[2] for o in obs}
        in_range = any(LEGAL_FIRST_DATE <= d <= LEGAL_LAST_DATE for d in days)
        if not in_range:
            out_of_range.append({
                "REFERENCE_PERIOD": ref,
                "SCHEDULES_OBSERVED": sorted({f"{o[2]} {o[3]}" for o in obs}),
                "FIRST_SEEN_UTC": min(o[0] for o in obs),
                "LAST_SEEN_UTC": max(o[0] for o in obs),
                "SNAPSHOT_COUNT": len(obs),
                "SCOPE": ("PRE_2020_METADATA_ONLY" if max(days) < LEGAL_FIRST_DATE
                          else "PROTECTED_2025_2026_METADATA_ONLY"),
            })
            continue
        c = classify_event(ref, obs, transitions)
        eid = event_id(ref)
        if c["FINAL"] is None:
            events.append({"EVENT_ID": eid, "SERIES": SERIES, "REFERENCE_PERIOD": ref,
                           "PROVENANCE_STATUS": c["STATUS"], "SAFE_FOR_W6": False, "SAFE_FOR_W12": False,
                           "SAFE_FOR_W24": False, "SCHEDULE_HISTORY": {"OBSERVED": c["SCHEDULE_HISTORY_RAW"]}})
            continue
        day, hhmm = c["FINAL"]
        utc, offset, abbrev = local_to_utc(day, hhmm, transitions)
        hist = c["SCHEDULE_HISTORY_RAW"]
        first = min(obs, key=lambda o: o[0]) if len(hist) == 1 else min(
            (o for o in obs if (o[2], o[3]) == c["FINAL"]), key=lambda o: o[0])
        pre_t = [o for o in obs if parse_iso_utc(o[0]) < parse_iso_utc(utc)]
        post_t = [o for o in obs if parse_iso_utc(o[0]) >= parse_iso_utc(utc)]
        w6, w12, w24 = c["SAFE"]
        events.append({
            "EVENT_ID": eid,
            "SERIES": SERIES,
            "REFERENCE_PERIOD": ref,
            "SCHEDULED_RELEASE_DATE": day,
            "SCHEDULED_RELEASE_LOCAL": hhmm,
            "TIMEZONE": TIMEZONE,
            "UTC_OFFSET": offset,
            "LOCAL_ZONE_ABBREV": abbrev,
            "SCHEDULED_RELEASE_UTC": utc,
            "DST_CONVERSION_AUTHORITY": f"{DST_AUTHORITY_PATH}#{DST_AUTHORITY_POINTER}@sha256:{dst_file_sha}",
            "EARLIEST_VERIFIED_PUBLICATION": {"CAPTURE_UTC": first[0], "SNAPSHOT_ID": first[1],
                                              "MEANING": "UPPER_BOUND_ON_FIRST_PUBLIC_AVAILABILITY"},
            "WINDOW_EVIDENCE": c["WINDOWS"],
            "SAFE_FOR_W6": w6,
            "SAFE_FOR_W12": w12,
            "SAFE_FOR_W24": w24,
            "SCHEDULE_HISTORY": {
                "ORIGINAL_SCHEDULE": {"RELEASE_DATE": hist[0]["RELEASE_DATE"], "RELEASE_LOCAL": hist[0]["RELEASE_LOCAL"],
                                      "FIRST_SEEN_UTC": hist[0]["FIRST_SEEN_UTC"]},
                "UPDATED_SCHEDULE": (None if len(hist) == 1 else
                                     {"RELEASE_DATE": hist[-1]["RELEASE_DATE"], "RELEASE_LOCAL": hist[-1]["RELEASE_LOCAL"]}),
                "UPDATE_PUBLICATION_TIME": None if len(hist) == 1 else {
                    "UPPER_BOUND_CAPTURE_UTC": hist[-1]["FIRST_SEEN_UTC"]},
                "FINAL_PREWINDOW_KNOWN_SCHEDULE": {"RELEASE_DATE": day, "RELEASE_LOCAL": hhmm},
                "DISTINCT_SCHEDULES_OBSERVED": len(hist),
                "OBSERVED": hist,
                "POST_CUTOFF_CONTRADICTION": c["POST_CUTOFF_CONTRADICTION"],
            },
            "PRIMARY_BLS_SOURCE": SCHEDULE_URL,
            "ARCHIVE_EVIDENCE": {
                "PRE_RELEASE_SNAPSHOT_COUNT": len(pre_t),
                "POST_RELEASE_CONFIRMING_SNAPSHOT_COUNT": len(post_t),
                "POST_RELEASE_SCHEDULE_CONSISTENT": all((o[2], o[3]) == c["FINAL"] for o in post_t),
                "LAST_PRE_RELEASE_SNAPSHOT_ID": pre_t[-1][1] if pre_t else None,
            },
            "REALIZED_DATE_CROSSCHECK": {
                "AUTHORITY": "NON_AUTHORITATIVE_DIAGNOSTIC_ONLY",
                "SOURCE_SNAPSHOT_ID": "LIVE_RELEASE_ARCHIVE_PAGE",
                "RELEASE_DATE_LISTED": day in realized,
            },
            "PROVENANCE_STATUS": c["STATUS"],
        })

    source_authority = {
        "DATASET_ID": DATASET_ID,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "SCOPE": "CPI release SCHEDULE metadata only. No CPI values. No market data. No outcomes.",
        "SERIES": SERIES,
        "SERIES_NOTE": "BLS Consumer Price Index news release (CPI-U, U.S. city average, all items) schedule.",
        "CANONICAL_SOURCE_AUTHORITY": {
            "PUBLISHER": "U.S. Bureau of Labor Statistics (first party)",
            "URL": SCHEDULE_URL,
            "PAGE_TITLE": "Schedule of Releases for the Consumer Price Index",
        },
        "ARCHIVE_METHOD": {
            "ROLE": "PUBLICATION_TIMING_AND_DATED_VERSION_RECOVERY_ONLY",
            "PROVIDER": "Internet Archive Wayback Machine (web.archive.org)",
            "LISTING": CDX_QUERY,
            "RETRIEVAL": "https://web.archive.org/web/<14-digit-ts>id_/<original> (exact archived payload, no Wayback rewriting)",
            "TIMESTAMP_SEMANTICS": "Wayback 14-digit capture timestamp, UTC",
            "REDIRECT_POLICY": "A 302 to a different capture is NOT_OBTAINED; the target capture is used only under its own timestamp.",
        },
        "NON_AUTHORITATIVE_SOURCES": {
            "RELEASE_ARCHIVE_PAGE": {"URL": RELEASE_ARCHIVE_URL,
                                     "USE": "Realized-date consistency diagnostic only; never point-in-time authority."},
            "CURRENT_SCHEDULE_PAGE": {"URL": SCHEDULE_URL,
                                      "USE": "Current first-party reference; retrieved after all windows; never point-in-time authority."},
            "THIRD_PARTY": "None used.",
        },
        "TIMEZONE_AUTHORITY": {
            "LOCAL_TIMEZONE": TIMEZONE,
            "OFFICIAL_LOCAL_TIME_SOURCE": "Release Time column of the archived BLS schedule page (Eastern Time)",
            "DST_AUTHORITY": "STATUTORY_DST_CALENDARS",
            "DST_AUTHORITY_PATH": DST_AUTHORITY_PATH,
            "DST_AUTHORITY_POINTER": DST_AUTHORITY_POINTER,
            "DST_AUTHORITY_FILE_SHA256": dst_file_sha,
            "US_TRANSITION_DAYS": {str(y): list(v) for y, v in sorted(transitions.items())},
            "RULE": "EDT (UTC-04:00) if second-Sunday-March <= date < first-Sunday-November, else EST (UTC-05:00)",
            "CROSSCHECKS": ["Energy Policy Act 2005 rule recomputation", "zoneinfo America/New_York"],
        },
        "POINT_IN_TIME_RULE": (
            "For window W in {6h,12h,24h}: SAFE_FOR_W iff the latest obtained capture with timestamp strictly before "
            "T-W lists the reference period with exactly the final pre-window schedule (date and local time), and no "
            "capture at/after T-6h contradicts it. SAFE_FOR_W24 => SAFE_FOR_W12 => SAFE_FOR_W6 enforced by conjunction. "
            "The realized release timestamp is never used to establish safety."
        ),
        "LEGAL_RANGE": {"SCHEDULED_RELEASE_DATE_FIRST": LEGAL_FIRST_DATE, "SCHEDULED_RELEASE_DATE_LAST": LEGAL_LAST_DATE},
        "EXCLUSIONS": [
            "Pre-2020 releases: OUT_OF_RANGE_INVENTORY.json, metadata only.",
            "Releases scheduled in 2025/2026 (incl. reference period 2024-12): OUT_OF_RANGE_INVENTORY.json, metadata only.",
            "No CPI index values, percent changes, consensus, or surprises.",
            "No BTC or other market data; no event-window returns.",
        ],
    }
    return {"EVENTS.json": {"DATASET_ID": DATASET_ID, "SCHEMA_VERSION": SCHEMA_VERSION, "EVENTS": events},
            "OUT_OF_RANGE_INVENTORY.json": {"DATASET_ID": DATASET_ID, "SCHEMA_VERSION": SCHEMA_VERSION,
                                            "CANONICAL": False, "REFERENCE_PERIODS": out_of_range},
            "SOURCE_AUTHORITY.json": source_authority,
            "SNAPSHOT_LEDGER.json": {"DATASET_ID": DATASET_ID, "SCHEMA_VERSION": SCHEMA_VERSION,
                                     "SNAPSHOTS": snapshots}}


def dataset_digest(files: dict[str, dict]) -> str:
    return sha256_hex(canonical_json({name: files[name] for name in DATASET_FILES}))


def manifest(files: dict[str, dict], raw_dir: Path = RAW_DIR) -> dict:
    events = files["EVENTS.json"]["EVENTS"]
    years: dict[str, int] = {}
    for e in events:
        y = (e.get("SCHEDULED_RELEASE_DATE") or e["REFERENCE_PERIOD"])[:4]
        years[y] = years.get(y, 0) + 1
    raw_files = sorted(p for p in raw_dir.rglob("*") if p.is_file())
    snaps = files["SNAPSHOT_LEDGER.json"]["SNAPSHOTS"]
    return {
        "DATASET_ID": DATASET_ID,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "EVENT_COUNT": len(events),
        "YEAR_COUNTS": dict(sorted(years.items())),
        "SAFE_W6": sum(e["SAFE_FOR_W6"] for e in events),
        "SAFE_W12": sum(e["SAFE_FOR_W12"] for e in events),
        "SAFE_W24": sum(e["SAFE_FOR_W24"] for e in events),
        "RESCHEDULED_COUNT": sum(e["PROVENANCE_STATUS"] == "VERIFIED_RESCHEDULED" for e in events),
        "UNRESOLVED_COUNT": sum(e["PROVENANCE_STATUS"] == "UNRESOLVED_POINT_IN_TIME" for e in events),
        "EXCLUDED_COUNT": sum(e["PROVENANCE_STATUS"] == "EXCLUDED_OTHER" for e in events),
        "OUT_OF_RANGE_METADATA_ONLY_COUNT": len(files["OUT_OF_RANGE_INVENTORY.json"]["REFERENCE_PERIODS"]),
        "SNAPSHOT_COUNT": len(snaps),
        "SNAPSHOTS_OBTAINED": sum(s["OBTAINED"] for s in snaps),
        "SNAPSHOTS_NOT_OBTAINED": sum(not s["OBTAINED"] for s in snaps),
        "RAW_SOURCE_BYTES_RETAINED": True,
        "FILE_DIGESTS_SHA256": {name: sha256_hex(dump_json(files[name])) for name in DATASET_FILES},
        "RAW_FILE_DIGESTS_SHA256": {p.relative_to(raw_dir.parent).as_posix(): sha256_hex(p.read_bytes())
                                    for p in raw_files},
        "CANONICAL_DATASET_DIGEST": dataset_digest(files),
        "CANONICAL_DATASET_DIGEST_RULE": "sha256(canonical_json({EVENTS, OUT_OF_RANGE_INVENTORY, SOURCE_AUTHORITY, SNAPSHOT_LEDGER})) with sort_keys, (',',':') separators, ASCII",
        "MARKET_DATA_PRESENT": False,
        "CPI_VALUES_PRESENT": False,
    }


def write(dataset_dir: Path = DATASET_DIR) -> dict:
    files = build(dataset_dir / "raw")
    for name, obj in files.items():
        (dataset_dir / name).write_bytes(dump_json(obj))
    m = manifest(files, dataset_dir / "raw")
    (dataset_dir / "MANIFEST.json").write_bytes(dump_json(m))
    return m


# --- validation ------------------------------------------------------------

def _walk_keys(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v, f"{prefix}.{k}")
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v, prefix)


def validate_events(events: list[dict], transitions: dict[int, tuple[str, str]]) -> list[str]:
    errors = []
    ids = [e["EVENT_ID"] for e in events]
    refs = [e["REFERENCE_PERIOD"] for e in events]
    if len(set(ids)) != len(ids):
        errors.append("duplicate EVENT_ID")
    if len(set(refs)) != len(refs):
        errors.append("duplicate REFERENCE_PERIOD")
    resolved = [e for e in events if e["PROVENANCE_STATUS"] in ("VERIFIED_PREANNOUNCED", "VERIFIED_RESCHEDULED")]
    utcs = [e["SCHEDULED_RELEASE_UTC"] for e in sorted(resolved, key=lambda e: e["REFERENCE_PERIOD"])]
    if any(a >= b for a, b in zip(utcs, utcs[1:])):
        errors.append("SCHEDULED_RELEASE_UTC not strictly monotonic in REFERENCE_PERIOD")
    for e in events:
        eid = e["EVENT_ID"]
        if e["PROVENANCE_STATUS"] not in PROVENANCE_STATUSES:
            errors.append(f"{eid}: bad PROVENANCE_STATUS")
        if e["SAFE_FOR_W24"] and not e["SAFE_FOR_W12"]:
            errors.append(f"{eid}: W24 without W12")
        if e["SAFE_FOR_W12"] and not e["SAFE_FOR_W6"]:
            errors.append(f"{eid}: W12 without W6")
        if e["PROVENANCE_STATUS"] in ("UNRESOLVED_POINT_IN_TIME", "EXCLUDED_OTHER") and e["SAFE_FOR_W6"]:
            errors.append(f"{eid}: unresolved/excluded marked safe")
        if e not in resolved:
            continue
        if set(e) != set(EVENT_FIELDS):
            errors.append(f"{eid}: field set/order mismatch")
        if not (LEGAL_FIRST_DATE <= e["SCHEDULED_RELEASE_DATE"] <= LEGAL_LAST_DATE):
            errors.append(f"{eid}: outside legal range")
        utc, offset, abbrev = local_to_utc(e["SCHEDULED_RELEASE_DATE"], e["SCHEDULED_RELEASE_LOCAL"], transitions)
        if (utc, offset, abbrev) != (e["SCHEDULED_RELEASE_UTC"], e["UTC_OFFSET"], e["LOCAL_ZONE_ABBREV"]):
            errors.append(f"{eid}: DST conversion mismatch")
        if zoneinfo_utc(e["SCHEDULED_RELEASE_DATE"], e["SCHEDULED_RELEASE_LOCAL"]) != utc:
            errors.append(f"{eid}: zoneinfo cross-check mismatch")
        t = parse_iso_utc(utc)
        final = e["SCHEDULE_HISTORY"]["FINAL_PREWINDOW_KNOWN_SCHEDULE"]
        for w in WINDOWS_H:
            we = e["WINDOW_EVIDENCE"][f"W{w}"]
            if parse_iso_utc(we["CUTOFF_UTC"]) != t - dt.timedelta(hours=w):
                errors.append(f"{eid}: W{w} cutoff mismatch")
            if e[f"SAFE_FOR_W{w}"]:
                cap = we["LATEST_PRE_CUTOFF_CAPTURE_UTC"]
                if cap is None or not parse_iso_utc(cap) < t - dt.timedelta(hours=w):
                    errors.append(f"{eid}: W{w} evidence does not precede cutoff")
                if we["LATEST_PRE_CUTOFF_SCHEDULE"] != final:
                    errors.append(f"{eid}: W{w} evidence schedule != final pre-window schedule")
        ev = e["EARLIEST_VERIFIED_PUBLICATION"]["CAPTURE_UTC"]
        if e["SAFE_FOR_W24"] and not parse_iso_utc(ev) < t - dt.timedelta(hours=24):
            errors.append(f"{eid}: earliest publication after W24 cutoff")
    return errors


def validate_boundary(files: dict[str, dict]) -> list[str]:
    errors = []
    for name in ("EVENTS.json", "OUT_OF_RANGE_INVENTORY.json"):
        for k in _walk_keys(files[name]):
            parts = k.upper().split("_")
            for tok in FORBIDDEN_KEY_TOKENS:
                if tok in parts or k.upper() == tok:
                    errors.append(f"{name}: forbidden key {k}")
    oor = files["OUT_OF_RANGE_INVENTORY.json"]
    if oor.get("CANONICAL") is not False:
        errors.append("out-of-range inventory must be non-canonical")
    for r in oor["REFERENCE_PERIODS"]:
        if set(r) != {"REFERENCE_PERIOD", "SCHEDULES_OBSERVED", "FIRST_SEEN_UTC", "LAST_SEEN_UTC",
                      "SNAPSHOT_COUNT", "SCOPE"}:
            errors.append(f"out-of-range {r.get('REFERENCE_PERIOD')}: unexpected fields")
    for e in files["EVENTS.json"]["EVENTS"]:
        if e.get("SCHEDULED_RELEASE_DATE", LEGAL_FIRST_DATE)[:4] in ("2025", "2026"):
            errors.append(f"{e['EVENT_ID']}: protected-year event in canonical set")
    return errors


def validate_ledger(files: dict[str, dict], raw_dir: Path) -> list[str]:
    errors = []
    snaps = {s["SNAPSHOT_ID"]: s for s in files["SNAPSHOT_LEDGER.json"]["SNAPSHOTS"]}
    for s in snaps.values():
        if s["OBTAINED"]:
            p = raw_dir.parent / s["RAW_PATH"]
            if not p.exists() or sha256_hex(p.read_bytes()) != s["SHA256"]:
                errors.append(f"{s['SNAPSHOT_ID']}: retained bytes missing or hash mismatch")
        elif s["SHA256"] is not None or s["RAW_PATH"] is not None:
            errors.append(f"{s['SNAPSHOT_ID']}: hash recorded for bytes not obtained")
    for e in files["EVENTS.json"]["EVENTS"]:
        for we in e.get("WINDOW_EVIDENCE", {}).values():
            sid = we["LATEST_PRE_CUTOFF_SNAPSHOT_ID"]
            if sid and (sid not in snaps or not snaps[sid]["OBTAINED"]
                        or snaps[sid].get("CDX_DIGEST_MATCH") is not True
                        or e["EVENT_ID"] not in snaps[sid]["SUPPORTED_EVENT_IDS"]):
                errors.append(f"{e['EVENT_ID']}: window evidence snapshot not in ledger/obtained/supporting")
    return errors


def validate(dataset_dir: Path = DATASET_DIR) -> list[str]:
    raw_dir = dataset_dir / "raw"
    files = build(raw_dir)
    errors = []
    for name, obj in files.items():
        if (dataset_dir / name).read_bytes() != dump_json(obj):
            errors.append(f"{name}: not reproducible from raw bytes")
    m = manifest(files, raw_dir)
    if (dataset_dir / "MANIFEST.json").read_bytes() != dump_json(m):
        errors.append("MANIFEST.json: not reproducible")
    if dataset_digest(build(raw_dir)) != m["CANONICAL_DATASET_DIGEST"]:
        errors.append("dataset digest not deterministic")
    errors += validate_events(files["EVENTS.json"]["EVENTS"], load_us_transitions())
    errors += validate_boundary(files)
    errors += validate_ledger(files, raw_dir)
    transitions = load_us_transitions()
    for y, v in transitions.items():
        if statutory_us_transitions(y) != v:
            errors.append(f"frozen DST table disagrees with statute for {y}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("acquire", "build", "validate"))
    args = ap.parse_args(argv)
    if args.command == "acquire":
        acquire()
        return 0
    if args.command == "build":
        m = write()
        print(json.dumps({k: v for k, v in m.items() if "DIGESTS" not in k}, indent=1, sort_keys=True))
        return 0
    errors = validate()
    print("\n".join(errors) if errors else "VALID")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
