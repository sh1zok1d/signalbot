"""D11 scheduled-FOMC unsigned 6h RV. Official Fed/FOMC sources only.

Feasibility may count pinned events and YEAR×WEEKDAY×UTC_HOUR control
support. It must not emit event RV, control RV, or their difference.
"""

from __future__ import annotations

import json
import math
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from scripts.research.discovery_sprint_03 import common as C


FED_ORIGIN = "https://www.federalreserve.gov"
CALENDAR_URL = f"{FED_ORIGIN}/monetarypolicy/fomccalendars.htm"
HIST_2020_URL = f"{FED_ORIGIN}/monetarypolicy/fomchistorical2020.htm"
POLICY_2013_URL = f"{FED_ORIGIN}/newsevents/pressreleases/monetary20130313a.htm"
USER_AGENT = "Signalbot D11 official-FOMC pin (outcome-blind; no third-party calendar)"

STATEMENT_A_RE = re.compile(r"/newsevents/pressreleases/monetary(\d{8})a\.htm")
RELEASE_RE = re.compile(
    r"For release at\s+(\d{1,2})(?::(\d{2}))?\s*(a\.m\.|p\.m\.)\s*"
    r"(EST|EDT|Eastern Time)\b",
    re.IGNORECASE,
)
EXCLUDED_HEADING_RE = re.compile(
    r"unscheduled|cancelled|canceled|notation vote|minutes|speech|"
    r"press conference|testimony",
    re.IGNORECASE,
)
FORBIDDEN_FAMILY_RE = re.compile(
    r"\b(CPI|NFP|ECB|nonfarm|consumer price|european central)\b",
    re.IGNORECASE,
)
HEADING_RE = re.compile(
    r"<h5 class=\"panel-heading[^\"]*\">([^<]+)</h5>",
    re.IGNORECASE,
)

NY_TZ = ZoneInfo("America/New_York")
EST_OFFSET = timedelta(hours=-5)
EDT_OFFSET = timedelta(hours=-4)


class D11SourceNotPinned(RuntimeError):
    """Official FOMC historical source could not be pinned adequately."""


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def parse_release_datetime(html: str, event_date: str) -> datetime:
    """Parse official 'For release at ...' into timezone-aware UTC datetime.

    Uses the stated EST/EDT offset. 'Eastern Time' falls back to America/New_York
    on the event date. Missing/ambiguous times fail closed.
    """

    if FORBIDDEN_FAMILY_RE.search(html):
        # Presence of those words in boilerplate is not automatically a family
        # substitution; family exclusion is enforced on event identity, not
        # statement body. Keep parsing.
        pass
    hits = RELEASE_RE.findall(html)
    if not hits:
        raise C.Sprint03IntegrityError(f"D11_NO_OFFICIAL_RELEASE_TIME:{event_date}")
    hour_s, minute_s, ampm, zone = hits[0]
    hour = int(hour_s)
    minute = int(minute_s or "0")
    ampm_n = ampm.lower()
    if hour == 12:
        hour = 0 if ampm_n.startswith("a") else 12
    elif ampm_n.startswith("p"):
        hour += 12
    year = int(event_date[0:4])
    month = int(event_date[4:6])
    day = int(event_date[6:8])
    naive = datetime(year, month, day, hour, minute)
    zone_u = zone.strip().upper()
    if zone_u == "EST":
        return naive.replace(tzinfo=timezone(EST_OFFSET)).astimezone(C.UTC)
    if zone_u == "EDT":
        return naive.replace(tzinfo=timezone(EDT_OFFSET)).astimezone(C.UTC)
    if "EASTERN" in zone_u:
        return naive.replace(tzinfo=NY_TZ).astimezone(C.UTC)
    raise C.Sprint03IntegrityError(f"D11_UNKNOWN_ZONE:{event_date}:{zone}")


def scheduled_2020_statement_dates(hist_html: str) -> list[str]:
    dates: list[str] = []
    matches = list(HEADING_RE.finditer(hist_html))
    for i, match in enumerate(matches):
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        if EXCLUDED_HEADING_RE.search(title):
            continue
        if "Meeting" not in title:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(hist_html)
        chunk = hist_html[match.end() : end]
        found = STATEMENT_A_RE.findall(chunk)
        if not found:
            raise C.Sprint03IntegrityError(f"D11_2020_MEETING_WITHOUT_STATEMENT:{title}")
        dates.append(found[0])
    return dates


def scheduled_calendar_statement_dates(calendar_html: str) -> list[str]:
    dates = sorted(set(STATEMENT_A_RE.findall(calendar_html)))
    legal = [d for d in dates if d.startswith(("2021", "2022", "2023", "2024"))]
    for d in dates:
        year = int(d[:4])
        if year >= 2025:
            continue
    return legal


def is_forbidden_event_identity(url: str, heading: str = "") -> bool:
    blob = f"{url} {heading}".lower()
    if "fomcminutes" in blob or "minutes" in Path(url).name.lower():
        return True
    if "presconf" in blob or "pressconf" in blob:
        return True
    if "speech" in blob or "testimony" in blob:
        return True
    if FORBIDDEN_FAMILY_RE.search(blob):
        return True
    if not STATEMENT_A_RE.search(url.replace(FED_ORIGIN, "")):
        # Implementation notes / b.htm / a1.htm are not the statement event.
        if re.search(r"monetary\d{8}(?:a1|b)\.htm", url):
            return True
        if "monetary" not in url:
            return True
    return False


def d11_source_dir(repo: Path | None = None) -> Path:
    return (repo or C.repo_root()) / C.D11_SOURCE_REL


def pin_official_fomc_sources(*, repo: Path | None = None, retrieve: bool = True) -> dict[str, Any]:
    base = repo or C.repo_root()
    root = d11_source_dir(base)
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    retrieval_utc = datetime.now(tz=C.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def store(name: str, url: str, data: bytes | None = None) -> dict[str, str]:
        path = raw_dir / name
        if data is None:
            if retrieve:
                data = _http_get(url)
                path.write_bytes(data)
            elif path.is_file():
                data = path.read_bytes()
            else:
                raise D11SourceNotPinned(f"MISSING_SOURCE:{name}")
        elif retrieve or not path.is_file():
            path.write_bytes(data)
        digest = C.sha256_bytes(data)
        if C.sha256_file(path) != digest:
            raise D11SourceNotPinned(f"SOURCE_HASH_MISMATCH:{name}")
        return {
            "filename": name,
            "url": url,
            "sha256": digest,
            "bytes": str(len(data)),
        }

    calendar_bytes = _http_get(CALENDAR_URL) if retrieve else (raw_dir / "fomccalendars.htm").read_bytes()
    hist_bytes = _http_get(HIST_2020_URL) if retrieve else (raw_dir / "fomchistorical2020.htm").read_bytes()
    policy_bytes = _http_get(POLICY_2013_URL) if retrieve else (raw_dir / "monetary20130313a.htm").read_bytes()
    sources = [
        store("fomccalendars.htm", CALENDAR_URL, calendar_bytes),
        store("fomchistorical2020.htm", HIST_2020_URL, hist_bytes),
        store("monetary20130313a.htm", POLICY_2013_URL, policy_bytes),
    ]
    calendar_html = calendar_bytes.decode("utf-8", "replace")
    hist_html = hist_bytes.decode("utf-8", "replace")
    dates = scheduled_2020_statement_dates(hist_html) + scheduled_calendar_statement_dates(calendar_html)
    dates = sorted(set(dates))
    events: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for yyyymmdd in dates:
        year = int(yyyymmdd[:4])
        rel = f"/newsevents/pressreleases/monetary{yyyymmdd}a.htm"
        url = FED_ORIGIN + rel
        if year >= 2025:
            excluded.append({"date": yyyymmdd, "reason": "PROTECTED_YEAR"})
            continue
        if is_forbidden_event_identity(url):
            excluded.append({"date": yyyymmdd, "reason": "FORBIDDEN_IDENTITY"})
            continue
        name = f"monetary{yyyymmdd}a.htm"
        html_bytes = _http_get(url) if retrieve else (raw_dir / name).read_bytes()
        src = store(name, url, html_bytes)
        sources.append(src)
        html = html_bytes.decode("utf-8", "replace")
        try:
            released_utc = parse_release_datetime(html, yyyymmdd)
        except C.Sprint03IntegrityError as exc:
            excluded.append({"date": yyyymmdd, "reason": str(exc)})
            continue
        if released_utc >= C.PROTECTED_START:
            excluded.append({"date": yyyymmdd, "reason": "PROTECTED_BOUNDARY"})
            continue
        outcome_end = released_utc + timedelta(hours=C.D11_HORIZON_HOURS)
        if outcome_end >= C.PROTECTED_START:
            excluded.append({"date": yyyymmdd, "reason": "OUTCOME_CROSSES_PROTECTED"})
            continue
        zone_hit = RELEASE_RE.search(html)
        events.append(
            {
                "EVENT_DATE": f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}",
                "EVENT_ID": yyyymmdd,
                "STATEMENT_URL": url,
                "SOURCE_FILENAME": name,
                "SOURCE_SHA256": src["sha256"],
                "OFFICIAL_RELEASE_TEXT": zone_hit.group(0).strip() if zone_hit else None,
                "STATED_TIMEZONE": zone_hit.group(4) if zone_hit else None,
                "ANNOUNCEMENT_UTC": released_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ANNOUNCEMENT_UTC_MS": int(released_utc.timestamp() * 1000),
                "OUTCOME_END_UTC": outcome_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "YEAR": released_utc.year,
                "WEEKDAY": released_utc.weekday(),
                "UTC_HOUR": released_utc.hour,
                "EVENT_FAMILY": "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS",
            }
        )
    if len(events) < C.D11_MIN_EVENTS:
        status = "D11_SOURCE_NOT_PINNED"
    else:
        status = "OFFICIAL_SOURCE_PINNED"
    pin = {
        "DATASET_ID": "D11_FOMC_OFFICIAL_V0",
        "EVENT_FAMILY": "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS",
        "RETRIEVAL_UTC": retrieval_utc,
        "CALENDAR_URL": CALENDAR_URL,
        "HISTORICAL_2020_URL": HIST_2020_URL,
        "STANDING_RELEASE_TIME_POLICY_URL": POLICY_2013_URL,
        "STANDING_RELEASE_TIME_POLICY_NOTE": (
            "2013-03-13 official statement: regularly scheduled FOMC policy "
            "statements released at 2 p.m. Eastern Time. Per-event times still "
            "come from each statement's 'For release at ...' line, not from this "
            "standing policy alone."
        ),
        "NO_THIRD_PARTY_CALENDAR": True,
        "NO_CPI": True,
        "NO_NFP": True,
        "NO_ECB": True,
        "MINUTES_NOT_EVENTS": True,
        "SPEECHES_NOT_EVENTS": True,
        "PRESS_CONFERENCES_NOT_SEPARATE_EVENTS": True,
        "UNSCHEDULED_EMERGENCY_EXCLUDED": True,
        "NOTATION_VOTES_EXCLUDED": True,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "SOURCES": sources,
        "EVENTS": events,
        "EXCLUDED": excluded,
        "EVENT_N": len(events),
        "YEAR_COVERAGE": sorted({str(e["YEAR"]) for e in events}),
        "STATUS": status,
    }
    (root / "PIN.json").write_text(
        json.dumps(C.jsonable(pin), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if status != "OFFICIAL_SOURCE_PINNED":
        raise D11SourceNotPinned(f"D11_SOURCE_NOT_PINNED:n={len(events)}")
    return pin


def load_pinned_calendar(*, repo: Path | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    pin_path = d11_source_dir(base) / "PIN.json"
    if not pin_path.is_file():
        raise D11SourceNotPinned("D11_SOURCE_NOT_PINNED:missing_PIN.json")
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    raw_dir = d11_source_dir(base) / "raw"
    for src in pin.get("SOURCES") or []:
        path = raw_dir / src["filename"]
        C.assert_openable(path)
        if not path.is_file():
            raise D11SourceNotPinned(f"MISSING_PINNED_BYTES:{src['filename']}")
        digest = C.sha256_file(path)
        if digest != src["sha256"]:
            raise C.SnapshotIdentityError(f"D11_SOURCE_HASH_MISMATCH:{src['filename']}")
    events = []
    for event in pin.get("EVENTS") or []:
        if int(event["ANNOUNCEMENT_UTC_MS"]) >= C.PROTECTED_START_MS:
            raise C.ProtectedYearRefused(f"D11_PROTECTED_EVENT:{event['EVENT_ID']}")
        events.append(event)
    pin["EVENTS"] = events
    pin["IDENTITY_OK"] = True
    return pin


def first_hour_open_ms(announcement_ms: int) -> int:
    hour = (int(announcement_ms) + C.HOUR_MS - 1) // C.HOUR_MS * C.HOUR_MS
    if hour < announcement_ms:
        hour += C.HOUR_MS
    # If announcement falls exactly on an hour open, that hour is eligible.
    if announcement_ms % C.HOUR_MS == 0:
        hour = announcement_ms
    return int(hour)


def post_event_rv_6h(
    hour_returns: Mapping[int, float],
    announcement_ms: int,
) -> float:
    start = first_hour_open_ms(announcement_ms)
    acc = 0.0
    for k in range(C.D11_HORIZON_HOURS):
        hour_ms = start + k * C.HOUR_MS
        if hour_ms + C.HOUR_MS >= C.PROTECTED_START_MS:
            raise C.ProtectedYearRefused(f"D11_PROTECTED_RV_WINDOW:{hour_ms}")
        ret = hour_returns.get(hour_ms)
        if ret is None or not math.isfinite(ret):
            raise C.Sprint03IntegrityError(f"D11_MISSING_HOUR:{hour_ms}")
        acc += float(ret) * float(ret)
    return math.sqrt(acc)


def classify_d11_from_summary(summary: Mapping[str, Any]) -> str:
    if not summary.get("SUPPORT_PASS"):
        return "INCONCLUSIVE_DISCOVERY"
    if not summary.get("IDENTITY_OK", True):
        return "INVALID_DISCOVERY"
    promising = bool(
        summary.get("STATISTICAL_GATE")
        and summary.get("PRACTICAL_GATE")
        and summary.get("TEMPORAL_GATE")
    )
    if promising:
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def d11_statistical_gate(
    event_rv: Sequence[float],
    control_rv: Sequence[float],
    *,
    seed: int = C.D11_SEED,
    n: int = C.D11_N_RANDOMIZATIONS,
) -> dict[str, Any]:
    event = np.asarray(list(event_rv), dtype=np.float64)
    control = np.asarray(list(control_rv), dtype=np.float64)
    if event.size == 0 or control.size == 0:
        raise C.Sprint03IntegrityError("D11_EMPTY_RV_SAMPLE")
    if not np.all(np.isfinite(event)) or not np.all(np.isfinite(control)):
        raise C.Sprint03IntegrityError("D11_NONFINITE_RV")
    mean_event = float(event.mean())
    mean_control = float(control.mean())
    if mean_control <= 0.0:
        raise C.Sprint03IntegrityError("D11_CONTROL_RV_NONPOSITIVE")
    relative = mean_event / mean_control - 1.0
    pooled = np.concatenate([event, control])
    n_event = event.size
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n):
        rng.shuffle(pooled)
        fake_event = float(pooled[:n_event].mean())
        fake_control = float(pooled[n_event:].mean())
        if fake_control <= 0.0:
            continue
        fake = fake_event / fake_control - 1.0
        if fake >= relative:
            exceed += 1
    p_value = (1.0 + exceed) / (1.0 + n)
    return {
        "MEAN_EVENT_RV": mean_event,
        "MEAN_CONTROL_RV": mean_control,
        "RELATIVE": relative,
        "MC_P": p_value,
        "STATISTICAL_GATE": bool(p_value < C.D11_MC_ALPHA and relative > 0.0),
        "SEED": seed,
        "N_RANDOMIZATIONS": n,
    }


def evaluate_d11_scientific(
    event_rv: Sequence[float],
    control_rv: Sequence[float],
    yearly_event_rv: Mapping[str, Sequence[float]],
    yearly_control_rv: Mapping[str, Sequence[float]],
    *,
    support: Mapping[str, Any],
) -> dict[str, Any]:
    stats = d11_statistical_gate(event_rv, control_rv)
    practical = bool(stats["RELATIVE"] >= C.D11_PRACTICAL_RELATIVE)
    temporal_ok = 0
    yearly: dict[str, float | None] = {}
    for year in sorted(set(yearly_event_rv) | set(yearly_control_rv)):
        ev = list(yearly_event_rv.get(year) or [])
        ct = list(yearly_control_rv.get(year) or [])
        yearly[year] = None
        if len(ev) < 1 or len(ct) < 1:
            continue
        mean_c = float(np.mean(ct))
        if mean_c <= 0.0:
            continue
        rel_y = float(np.mean(ev) / mean_c - 1.0)
        yearly[year] = rel_y
        if stats["RELATIVE"] > 0 and rel_y > 0:
            temporal_ok += 1
    temporal = bool(temporal_ok >= C.D11_TEMPORAL_YEARS_REQUIRED)
    summary = {
        **stats,
        "PRACTICAL_GATE": practical,
        "TEMPORAL_GATE": temporal,
        "YEARLY_RELATIVE": yearly,
        "TEMPORAL_YEARS_OK": temporal_ok,
        "SUPPORT_PASS": bool(support.get("SUPPORT_PASS")),
        "IDENTITY_OK": bool(support.get("IDENTITY_OK", True)),
        "PRIMARY_STATISTIC": "RELATIVE_MEAN_POST_EVENT_RV_6H_VS_MATCHED_CONTROL",
        "DIRECTIONAL_SIGN_USED": False,
    }
    summary["CLASSIFICATION"] = classify_d11_from_summary(summary)
    return summary


def _hour_complete_for_rv(
    hour_returns: Mapping[int, float],
    start_ms: int,
) -> bool:
    if start_ms + C.D11_HORIZON_HOURS * C.HOUR_MS >= C.PROTECTED_START_MS:
        return False
    for k in range(C.D11_HORIZON_HOURS):
        hour_ms = start_ms + k * C.HOUR_MS
        ret = hour_returns.get(hour_ms)
        if ret is None or not math.isfinite(ret):
            return False
    return True


def d11_feasibility_census(
    events: Sequence[Mapping[str, Any]],
    hour_returns: Mapping[int, float],
) -> dict[str, Any]:
    """Count events and YEAR×WEEKDAY×UTC_HOUR controls. No RV values."""

    event_starts: list[int] = []
    event_by_year: dict[str, int] = {str(y): 0 for y in C.CONTROL_YEARS}
    timezone_coverage = {"EST": 0, "EDT": 0, "Eastern Time": 0, "OTHER": 0}
    event_cells: dict[str, int] = {}
    fomc_hours: set[int] = set()
    pinned_ok = 0
    for event in events:
        if event.get("EVENT_FAMILY") != "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS":
            continue
        announ = int(event["ANNOUNCEMENT_UTC_MS"])
        if announ >= C.PROTECTED_START_MS:
            raise C.ProtectedYearRefused(f"D11_PROTECTED_EVENT:{event.get('EVENT_ID')}")
        start = first_hour_open_ms(announ)
        if not _hour_complete_for_rv(hour_returns, start):
            continue
        pinned_ok += 1
        event_starts.append(start)
        year = datetime.fromtimestamp(start / 1000.0, tz=C.UTC).year
        weekday = datetime.fromtimestamp(start / 1000.0, tz=C.UTC).weekday()
        utc_hour = datetime.fromtimestamp(start / 1000.0, tz=C.UTC).hour
        event_by_year[str(year)] = event_by_year.get(str(year), 0) + 1
        cell = f"{year}:{weekday}:{utc_hour}"
        event_cells[cell] = event_cells.get(cell, 0) + 1
        zone = str(event.get("STATED_TIMEZONE") or "OTHER")
        timezone_coverage[zone] = timezone_coverage.get(zone, 0) + 1
        for k in range(C.D11_HORIZON_HOURS):
            fomc_hours.add(start + k * C.HOUR_MS)

    event_start_set = set(event_starts)
    control_by_cell: dict[str, int] = {cell: 0 for cell in event_cells}
    control_n = 0
    for start_ms, ret in hour_returns.items():
        if start_ms in event_start_set or start_ms in fomc_hours:
            continue
        if not math.isfinite(ret):
            continue
        if not _hour_complete_for_rv(hour_returns, start_ms):
            continue
        dt = datetime.fromtimestamp(start_ms / 1000.0, tz=C.UTC)
        cell = f"{dt.year}:{dt.weekday()}:{dt.hour}"
        if cell not in event_cells:
            continue
        control_by_cell[cell] += 1
        control_n += 1

    per_event_controls = []
    insufficient_events = 0
    for start in event_starts:
        dt = datetime.fromtimestamp(start / 1000.0, tz=C.UTC)
        cell = f"{dt.year}:{dt.weekday()}:{dt.hour}"
        n_ctrl = control_by_cell.get(cell, 0)
        per_event_controls.append(n_ctrl)
        if n_ctrl < C.D11_MIN_CONTROLS_PER_EVENT:
            insufficient_events += 1
    years_with_events = [y for y, n_y in event_by_year.items() if n_y > 0]
    support_pass = bool(
        pinned_ok >= C.D11_MIN_EVENTS
        and len(years_with_events) >= C.D11_MIN_YEARS
        and control_n >= C.D11_MIN_TOTAL_CONTROLS
        and insufficient_events == 0
    )
    if pinned_ok < C.D11_MIN_EVENTS or len(years_with_events) < C.D11_MIN_YEARS:
        status = "DEFERRED_INSUFFICIENT_EVENT_SUPPORT"
    elif insufficient_events or control_n < C.D11_MIN_TOTAL_CONTROLS:
        status = "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    else:
        status = "OUTCOME_BLIND_IMPLEMENTATION_READY"
    return {
        "PINNED_EVENT_N": len(events),
        "EVENT_N": pinned_ok,
        "CONTROL_N": control_n,
        "EVENT_BY_YEAR": event_by_year,
        "CONTROL_BY_CELL": control_by_cell,
        "TIMEZONE_COVERAGE": timezone_coverage,
        "YEARS_WITH_EVENTS": years_with_events,
        "EVENTS_WITH_INSUFFICIENT_CONTROLS": insufficient_events,
        "MIN_CONTROLS_AMONG_EVENTS": min(per_event_controls) if per_event_controls else 0,
        "MATCH_STRATA": ["YEAR", "WEEKDAY", "UTC_HOUR"],
        "SUPPORT_PASS": support_pass,
        "STATUS": status,
        "RV_VALUES_EMITTED": False,
        "DIRECTIONAL_SIGN_USED": False,
    }


def load_d11_inputs(*, repo: Path | None = None) -> tuple[list[dict[str, Any]], dict[int, float], dict[str, Any]]:
    base = repo or C.repo_root()
    pin = load_pinned_calendar(repo=base)
    log = C.OpenedFileLog()
    btc_checksums = C.btc_legal_parquet_checksums(base)
    btc = C.load_hourly_closes(
        dataset_id=C.CORE_BTC_DATASET_ID,
        snapshot_id=C.CORE_BTC_SNAPSHOT_ID,
        root_rel=C.CORE_BTC_ROOT_REL,
        checksums=btc_checksums,
        log=log,
        repo=base,
    )
    hour_returns = C.adjacent_hour_returns(btc)
    identity = {
        "OFFICIAL_SOURCE_PINNED": True,
        "EVENT_N_PINNED": len(pin["EVENTS"]),
        "YEAR_COVERAGE": pin.get("YEAR_COVERAGE"),
        "CORE_BTC_SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT_ID,
        "FILES_OPENED": log.files,
        "IDENTITY_OK": True,
        "PIN_STATUS": pin.get("STATUS"),
    }
    return list(pin["EVENTS"]), hour_returns, identity
