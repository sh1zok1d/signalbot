"""Point-in-time holiday calendars for GV0R01-C020 (data provenance only).

Pins three first-party calendars for discovery years 2020-2024:

- NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0
- US_OPM_FEDERAL_HOLIDAY_LIST_V0
- CN_STATE_COUNCIL_HOLIDAY_NOTICES_V0

No market prices, no session bounds, no C020 inference, no power.
``build`` and ``validate`` are offline and read retained raw bytes only.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
from html import unescape
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO / "docs" / "research_data"
RESEARCH = REPO / "docs" / "research"
CANONICAL_YEARS = (2020, 2021, 2022, 2023, 2024)
NYSE_ID = "NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0"
OPM_ID = "US_OPM_FEDERAL_HOLIDAY_LIST_V0"
CN_ID = "CN_STATE_COUNCIL_HOLIDAY_NOTICES_V0"
NYSE_URL = "https://www.nyse.com/markets/hours-calendars"
OPM_URL = "https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/"
WEEKDAYS = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
)
MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}
CN_NUM = "一二三四五六七"
FETCHED_AT = "2026-09-25T09:57:00Z"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()


def load_bytes(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw), "application/gzip"
    return raw, "text/html"


def html_text(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|tr|h\d|div|li|td|th)>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text


def ts_to_dt(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)


def weekday_name(iso: str) -> str:
    return WEEKDAYS[dt.date.fromisoformat(iso).weekday()]


def parse_english_date(text: str, default_year: int | None = None) -> str | None:
    m = re.search(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2})(?:,\s*(\d{4}))?",
        text,
    )
    if not m:
        return None
    year = int(m.group(3)) if m.group(3) else default_year
    if year is None:
        return None
    return dt.date(year, MONTHS[m.group(1)], int(m.group(2))).isoformat()


def stated_weekday(text: str) -> str | None:
    for name in WEEKDAYS:
        if re.search(rf"\b{name}\b", text):
            return name
    return None


# ---------------------------------------------------------------------------
# NYSE
# ---------------------------------------------------------------------------

def _nyse_tables(html: str) -> list[list[list[str]]]:
    tables = []
    for table in re.findall(r"<table[\s\S]*?</table>", html, flags=re.I):
        if not re.search(r"Holiday", table, flags=re.I):
            continue
        if not re.search(r"20\d\d", table):
            continue
        rows = []
        for tr in re.findall(r"<tr[\s\S]*?</tr>", table, flags=re.I):
            cells = re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", tr, flags=re.I)
            cleaned = []
            for cell in cells:
                bit = unescape(re.sub(r"<[^>]+>", " ", cell))
                bit = bit.replace("\u2014", "-").replace("\u2013", "-")
                bit = re.sub(r"\s+", " ", bit).strip()
                cleaned.append(bit)
            if cleaned:
                rows.append(cleaned)
        if rows:
            tables.append(rows)
    return tables


def _norm_label(label: str) -> str:
    label = label.replace("\u2019", "'").replace("\u2018", "'").replace("'", "")
    return re.sub(r"\s+", " ", label).strip()


def _nyse_early_closes(html: str) -> list[dict]:
    text = html_text(html)
    found = []
    for block in re.finditer(r"close early[\s\S]{0,900}?Eastern Time", text, flags=re.I):
        window = block.group(0)
        for m in re.finditer(
            r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
            r"(January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+(\d{1,2}),\s*(\d{4})",
            window,
        ):
            iso = dt.date(int(m.group(4)), MONTHS[m.group(2)], int(m.group(3))).isoformat()
            if weekday_name(iso) != m.group(1):
                raise SystemExit(f"NYSE early-close weekday mismatch {m.group(0)} vs {iso}")
            found.append({"EVENT_DATE": iso, "OFFICIAL_LABEL": "Early close", "RAW_CELL": m.group(0)})
    uniq = {}
    for row in found:
        uniq[row["EVENT_DATE"]] = row
    return list(uniq.values())


def parse_nyse_snapshot(html: str, capture_ts: str) -> list[dict]:
    rows_out = []
    for table in _nyse_tables(html):
        header = table[0]
        years = [int(c) for c in header if re.fullmatch(r"20\d\d", c)]
        if not years:
            continue
        for row in table[1:]:
            if len(row) < 2:
                continue
            label = _norm_label(row[0])
            if label == "Christmas":
                label = "Christmas Day"
            cells = row[1:1 + len(years)]
            for year, cell in zip(years, cells):
                star = "*" in cell
                body = cell.replace("*", "").strip()
                if body in {"-", "—", ""}:
                    rows_out.append({
                        "YEAR": year,
                        "OFFICIAL_LABEL": label,
                        "EVENT_DATE": None,
                        "EVENT_TYPE": "WEEKEND_HOLIDAY_WITH_NO_WEEKDAY_CLOSURE" if star else "OTHER",
                        "NOMINAL_DATE": None,
                        "RAW_CELL": cell,
                        "CAPTURE_TS": capture_ts,
                    })
                    continue
                event = parse_english_date(body, year)
                if event is None:
                    raise SystemExit(f"unparsed NYSE cell {year} {label!r} {cell!r}")
                wd = stated_weekday(body)
                if wd and wd != weekday_name(event):
                    raise SystemExit(f"NYSE weekday mismatch {cell} -> {event}")
                nominal = None
                m = re.search(
                    r"(January|February|March|April|May|June|July|August|September|"
                    r"October|November|December)\s+(\d{1,2})\s+holiday observed",
                    body,
                    flags=re.I,
                )
                if m:
                    nominal = dt.date(year, MONTHS[m.group(1)], int(m.group(2))).isoformat()
                rows_out.append({
                    "YEAR": year,
                    "OFFICIAL_LABEL": label,
                    "EVENT_DATE": event,
                    "EVENT_TYPE": "FULL_DAY_CLOSURE",
                    "NOMINAL_DATE": nominal,
                    "RAW_CELL": cell,
                    "CAPTURE_TS": capture_ts,
                })
    for early in _nyse_early_closes(html):
        rows_out.append({
            "YEAR": int(early["EVENT_DATE"][:4]),
            "OFFICIAL_LABEL": "Early close",
            "EVENT_DATE": early["EVENT_DATE"],
            "EVENT_TYPE": "EARLY_CLOSE",
            "NOMINAL_DATE": None,
            "RAW_CELL": early["RAW_CELL"],
            "CAPTURE_TS": capture_ts,
        })
    return rows_out


def merge_nyse(snapshots: list[tuple[str, str, list[dict]]]) -> tuple[list[dict], list[dict]]:
    """snapshots: (sha, capture_ts, parsed rows)."""
    grouped: dict[tuple, list[dict]] = {}
    for sha, ts, rows in snapshots:
        for row in rows:
            key = (row["YEAR"], row["OFFICIAL_LABEL"], row["EVENT_TYPE"], row["EVENT_DATE"])
            # group closures by year+label+type so conflicting dates surface
            if row["EVENT_TYPE"] == "FULL_DAY_CLOSURE":
                key = (row["YEAR"], row["OFFICIAL_LABEL"], "FULL_DAY_CLOSURE")
            elif row["EVENT_TYPE"] == "EARLY_CLOSE":
                key = ("EARLY", row["EVENT_DATE"])
            else:
                key = (row["YEAR"], row["OFFICIAL_LABEL"], "NO_WEEKDAY_CLOSURE")
            item = dict(row)
            item["SHA256"] = sha
            grouped.setdefault(key, []).append(item)
    canonical = []
    out_of_range = []
    for key, items in grouped.items():
        dates = {i["EVENT_DATE"] for i in items}
        status = "VERIFIED_PREANNOUNCED"
        if len(dates) > 1:
            status = "SOURCE_CONFLICT"
        earliest = min(items, key=lambda i: i["CAPTURE_TS"])
        event_date = earliest["EVENT_DATE"]
        event_type = earliest["EVENT_TYPE"]
        if any(i["EVENT_TYPE"] == "WEEKEND_HOLIDAY_WITH_NO_WEEKDAY_CLOSURE" for i in items):
            event_type = "WEEKEND_HOLIDAY_WITH_NO_WEEKDAY_CLOSURE"
        if status != "SOURCE_CONFLICT" and event_date:
            cap = ts_to_dt(earliest["CAPTURE_TS"]).date()
            ev = dt.date.fromisoformat(event_date)
            if cap >= ev:
                status = "UNRESOLVED_PUBLICATION_TIMING"
        elif status != "SOURCE_CONFLICT" and event_date is None:
            cap = ts_to_dt(earliest["CAPTURE_TS"]).date()
            year_start = dt.date(earliest["YEAR"], 1, 1)
            if cap >= year_start:
                status = "UNRESOLVED_PUBLICATION_TIMING"
        row = {
            "CALENDAR_ID": NYSE_ID,
            "EVENT_DATE": event_date,
            "YEAR": earliest["YEAR"],
            "EVENT_TYPE": event_type,
            "OFFICIAL_LABEL": earliest["OFFICIAL_LABEL"],
            "NOMINAL_DATE": earliest["NOMINAL_DATE"],
            "OBSERVED_OR_CLOSURE_DATE": event_date,
            "PUBLICATION_DATE": ts_to_dt(earliest["CAPTURE_TS"]).date().isoformat(),
            "PUBLICATION_TIMESTAMP_IF_AVAILABLE": ts_to_dt(earliest["CAPTURE_TS"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "SOURCE_URL": NYSE_URL,
            "ARCHIVE_CAPTURE_TIMESTAMP": earliest["CAPTURE_TS"],
            "SOURCE_DIGEST": earliest["SHA256"],
            "POINT_IN_TIME_STATUS": status,
            "PRIMARY_FOR_LEAD_ARM": earliest["EVENT_TYPE"] == "FULL_DAY_CLOSURE" and status == "VERIFIED_PREANNOUNCED",
            "RAW_CELL": earliest["RAW_CELL"],
            "ROLE": "PRIMARY_EVENT_DEFINITION",
        }
        row["EVENT_ID"] = "NYSE:{year}:{etype}:{date}:{label}".format(
            year=row["YEAR"],
            etype=row["EVENT_TYPE"],
            date=row["EVENT_DATE"] or "NONE",
            label=re.sub(r"[^A-Za-z0-9]+", "_", row["OFFICIAL_LABEL"]).strip("_"),
        )
        if row["YEAR"] in CANONICAL_YEARS:
            canonical.append(row)
        else:
            row["CANONICAL"] = False
            out_of_range.append(row)
    canonical.sort(key=lambda r: (r["EVENT_DATE"] or "9999", r["EVENT_TYPE"], r["OFFICIAL_LABEL"]))
    out_of_range.sort(key=lambda r: (r["YEAR"], r["EVENT_DATE"] or "", r["EVENT_TYPE"]))
    return canonical, out_of_range


# ---------------------------------------------------------------------------
# OPM
# ---------------------------------------------------------------------------

def parse_opm_snapshot(html: str, capture_ts: str) -> list[dict]:
    text = html_text(html)
    rows = []
    for m in re.finditer(r"(20\d\d) Holiday Schedule", text):
        year = int(m.group(1))
        nxt = re.search(r"20\d\d Holiday Schedule", text[m.end():])
        chunk = text[m.end(): m.end() + (nxt.start() if nxt else 2500)]
        # stop at the next caption-like year header already handled
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        # pair "Weekday, Month D" with the following holiday name
        i = 0
        pending = None
        footnotes = {}
        body_lines = []
        for ln in lines:
            if ln.startswith("*") or re.match(r"^[\*\*]+\s", ln) or "U.S.C" in ln or "legal public holiday" in ln:
                body_lines.append(ln)
            elif re.match(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),", ln):
                if pending:
                    rows.append(pending)
                pending = {"YEAR": year, "OBSERVED_CELL": ln, "LABEL": None, "CAPTURE_TS": capture_ts}
            elif pending and pending["LABEL"] is None and not ln.startswith("Date"):
                pending["LABEL"] = ln
                rows.append(pending)
                pending = None
        if pending and pending.get("LABEL"):
            rows.append(pending)
        note_blob = " ".join(body_lines)
        for star_n, note in re.findall(r"(\*+)\s*(.*?)(?=(?:\*+\s)|$)", note_blob):
            footnotes[len(star_n)] = note
        for row in rows:
            if row["YEAR"] != year or row.get("_noted"):
                continue
            cell = row["OBSERVED_CELL"]
            stars = cell.count("*")
            row["FOOTNOTE"] = footnotes.get(stars, "")
            row["_noted"] = True
    # The loop above attaches footnotes poorly because rows from all years share the list.
    # Re-parse per year more tightly.
    return _parse_opm_tight(html, capture_ts)


def _parse_opm_tight(html: str, capture_ts: str) -> list[dict]:
    out = []
    for tm in re.finditer(r"<table[\s\S]*?</table>", html, flags=re.I):
        table = tm.group(0)
        cap = re.search(r"<caption>\s*(20\d\d)\s+Holiday Schedule\s*</caption>", table, flags=re.I)
        if not cap:
            continue
        year = int(cap.group(1))
        after = html[tm.end():tm.end() + 5000]
        stop = re.search(r"<caption|<h1|<table", after, flags=re.I)
        if stop:
            after = after[:stop.start()]
        notes = {}
        for para in re.findall(r"<p[^>]*Footnote[^>]*>([\s\S]*?)</p>", after, flags=re.I):
            mark = re.search(r">(\*+)<", para)
            if not mark:
                mark = re.search(r"(\*+)", unescape(re.sub(r"<[^>]+>", "", para))[:8])
            if not mark:
                continue
            note = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", para))).strip()
            notes[len(mark.group(1))] = note[:800]
        for tr in re.findall(r"<tr[\s\S]*?</tr>", table, flags=re.I):
            cells = re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", tr, flags=re.I)
            if len(cells) < 2:
                continue
            date_cell = unescape(re.sub(r"<[^>]+>", " ", cells[0]))
            label = unescape(re.sub(r"<[^>]+>", " ", cells[1]))
            date_cell = re.sub(r"\s+", " ", date_cell).strip()
            label = _norm_label(re.sub(r"\s+", " ", label).strip())
            if not re.match(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),", date_cell):
                continue
            stars = date_cell.count("*")
            observed = parse_english_date(date_cell, year)
            if observed is None:
                raise SystemExit(f"unparsed OPM date {date_cell}")
            wd = stated_weekday(date_cell)
            if wd != weekday_name(observed):
                # The cell's weekday word and the caption year disagree.
                # Keep only cells that are internally consistent.
                continue
            note = notes.get(stars, "")
            nominal = observed
            scope = "NATIONWIDE"
            if "Washington, DC" in note or "Washington, D.C" in note:
                scope = "WASHINGTON_DC_AREA"
            legal = re.search(
                r"(January|February|March|April|May|June|July|August|September|"
                r"October|November|December)\s+(\d{1,2}),\s*(\d{4})",
                note,
            )
            if legal and "legal public holiday" in note and abs(int(legal.group(3)) - year) <= 1:
                candidate = dt.date(int(legal.group(3)), MONTHS[legal.group(1)], int(legal.group(2))).isoformat()
                gap = abs((dt.date.fromisoformat(candidate) - dt.date.fromisoformat(observed)).days)
                if gap <= 3:
                    nominal = candidate
            out.append({
                "YEAR": year,
                "OFFICIAL_LABEL": label,
                "OBSERVED_DATE": observed,
                "NOMINAL_DATE": nominal,
                "OBSERVED_DIFFERS_FROM_NOMINAL": nominal != observed,
                "GEOGRAPHIC_SCOPE": scope,
                "FOOTNOTE": note[:500],
                "CAPTURE_TS": capture_ts,
            })
    return out


def merge_opm(snapshots: list[tuple[str, str, list[dict]]]) -> tuple[list[dict], list[dict]]:
    grouped: dict[tuple, list[dict]] = {}
    for sha, ts, rows in snapshots:
        for row in rows:
            key = (row["YEAR"], row["OFFICIAL_LABEL"])
            item = dict(row)
            item["SHA256"] = sha
            grouped.setdefault(key, []).append(item)
    canonical, out_of_range = [], []
    for key, items in grouped.items():
        observed = {i["OBSERVED_DATE"] for i in items}
        legal_nominals = {i["NOMINAL_DATE"] for i in items if i["NOMINAL_DATE"] != i["OBSERVED_DATE"]}
        status = "VERIFIED_PREANNOUNCED"
        if len(observed) > 1 or len(legal_nominals) > 1:
            status = "SOURCE_CONFLICT"
        earliest = min(items, key=lambda i: i["CAPTURE_TS"])
        if len(legal_nominals) == 1:
            earliest = dict(earliest)
            earliest["NOMINAL_DATE"] = next(iter(legal_nominals))
            earliest["OBSERVED_DIFFERS_FROM_NOMINAL"] = True
        ev = dt.date.fromisoformat(earliest["OBSERVED_DATE"])
        cap = ts_to_dt(earliest["CAPTURE_TS"]).date()
        if status != "SOURCE_CONFLICT" and cap >= ev:
            status = "UNRESOLVED_PUBLICATION_TIMING"
        row = {
            "CALENDAR_ID": OPM_ID,
            "EVENT_DATE": earliest["OBSERVED_DATE"],
            "OBSERVED_DATE": earliest["OBSERVED_DATE"],
            "NOMINAL_DATE": earliest["NOMINAL_DATE"],
            "OBSERVED_DIFFERS_FROM_NOMINAL": earliest["OBSERVED_DIFFERS_FROM_NOMINAL"],
            "YEAR": earliest["YEAR"],
            "EVENT_TYPE": "OBSERVED_FEDERAL_HOLIDAY",
            "OFFICIAL_LABEL": earliest["OFFICIAL_LABEL"],
            "GEOGRAPHIC_SCOPE": earliest["GEOGRAPHIC_SCOPE"],
            "PUBLICATION_DATE": cap.isoformat(),
            "PUBLICATION_TIMESTAMP_IF_AVAILABLE": ts_to_dt(earliest["CAPTURE_TS"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "SOURCE_URL": OPM_URL,
            "ARCHIVE_CAPTURE_TIMESTAMP": earliest["CAPTURE_TS"],
            "SOURCE_DIGEST": earliest["SHA256"],
            "POINT_IN_TIME_STATUS": status,
            "DOES_NOT_PROVE_NYSE_CLOSURE": True,
            "ROLE": "OTHER_FALSIFIER_SPECIFICITY",
            "FOOTNOTE": earliest["FOOTNOTE"],
        }
        row["EVENT_ID"] = "OPM:{year}:{label}:{observed}".format(
            year=row["YEAR"],
            label=re.sub(r"[^A-Za-z0-9]+", "_", row["OFFICIAL_LABEL"]).strip("_"),
            observed=row["OBSERVED_DATE"],
        )
        if row["YEAR"] in CANONICAL_YEARS:
            canonical.append(row)
        else:
            row["CANONICAL"] = False
            out_of_range.append(row)
    canonical.sort(key=lambda r: (r["OBSERVED_DATE"], r["OFFICIAL_LABEL"]))
    out_of_range.sort(key=lambda r: (r["YEAR"], r["OBSERVED_DATE"] or ""))
    return canonical, out_of_range


# ---------------------------------------------------------------------------
# China
# ---------------------------------------------------------------------------

def _cn_body(html: str) -> str:
    text = html_text(html)
    i = text.find("经国务院批准")
    if i < 0:
        raise SystemExit("State Council notice body not found")
    j = text.find("节假日期间", i)
    body = text[i:j if j > i else i + 2500]
    tail = text[j if j > i else i: (j if j > i else i) + 800]
    date_m = re.search(r"(20\d\d)年(\d{1,2})月(\d{1,2})日", tail)
    if not date_m:
        date_m = re.search(r"(20\d\d)年(\d{1,2})月(\d{1,2})日", text[i:i + 4000])
    if not date_m:
        raise SystemExit("notice publication date not found")
    pub = dt.date(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3))).isoformat()
    return body, pub


def _cn_expand(notice_year: int, piece: str) -> list[str]:
    piece = piece.strip(" ，。；")
    m = re.match(
        r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日至(?:(\d{4})年)?(?:(\d{1,2})月)?(\d{1,2})日",
        piece,
    )
    if m:
        y1 = int(m.group(1) or notice_year)
        start = dt.date(y1, int(m.group(2)), int(m.group(3)))
        y2 = int(m.group(4) or y1)
        month2 = int(m.group(5) or start.month)
        end = dt.date(y2, month2, int(m.group(6)))
        days = []
        cur = start
        while cur <= end:
            days.append(cur.isoformat())
            cur += dt.timedelta(days=1)
        return days
    m = re.match(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日", piece)
    if not m:
        return []
    y = int(m.group(1) or notice_year)
    return [dt.date(y, int(m.group(2)), int(m.group(3))).isoformat()]


def parse_cn_snapshot(html: str, capture_ts: str, source_url: str) -> dict:
    body, pub = _cn_body(html)
    year_m = re.search(r"(20\d\d)年", body)
    notice_year = int(year_m.group(1))
    blocks = re.split(r"[一二三四五六七八]、", body)[1:]
    parsed_blocks = []
    for block in blocks:
        name_m = re.match(r"([^：:]{1,20})[：:]", block.strip())
        if not name_m:
            continue
        name = name_m.group(1).strip()
        rest = block[name_m.end():]
        encouraged = []
        if "鼓励" in rest:
            enc = rest.split("鼓励", 1)[1]
            for piece in re.findall(r"（(\d{1,2}月\d{1,2}日)）", enc):
                encouraged.extend(_cn_expand(notice_year, piece))
            rest = rest.split("鼓励", 1)[0]
        work = []
        nonwork_src = rest
        if "上班" in rest:
            left, right = rest.split("上班", 1)[0], ""
            # dates before 上班 that are in the 上班 clause: the clause starts after 。 
            parts = rest.split("。")
            nonwork_src = parts[0]
            work_src = "。".join(parts[1:])
            for piece in re.findall(r"(?:20\d\d年)?\d{1,2}月\d{1,2}日", work_src):
                work.extend(_cn_expand(notice_year, piece))
        nonworking = []
        # only the 放假 clause, not 与周末连休 expansion
        holiday_clause = nonwork_src.split("放假", 1)[0] + "放假" if "放假" in nonwork_src else nonwork_src
        # dates that are the object of 放假: text before 放假
        before = nonwork_src.split("放假", 1)[0] if "放假" in nonwork_src else ""
        for piece in re.findall(r"(?:20\d\d年)?\d{1,2}月\d{1,2}日至(?:20\d\d年)?(?:\d{1,2}月)?\d{1,2}日|(?:20\d\d年)?\d{1,2}月\d{1,2}日", before):
            nonworking.extend(_cn_expand(notice_year, piece))
        wd_checks = re.findall(r"(\d{1,2}月\d{1,2}日)（(星期[一二三四五六日])）", rest + (""))
        cn_wd = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}
        for piece, wd in wd_checks:
            dates = _cn_expand(notice_year, piece)
            if len(dates) == 1 and dt.date.fromisoformat(dates[0]).weekday() != cn_wd[wd[-1]]:
                raise SystemExit(f"China weekday mismatch {piece} {wd} {dates[0]}")
        parsed_blocks.append({
            "HOLIDAY_NAME": name,
            "NON_WORKING_DATES": nonworking,
            "COMPENSATING_WORKING_DATES": work,
            "ENCOURAGED_REST_DATES": encouraged,
            "NOTICE_PHRASE": re.sub(r"\s+", "", block.strip())[:240],
            "UNENUMERATED_WEEKEND_LINK": "与周末连休" in block,
        })
    return {
        "NOTICE_YEAR": notice_year,
        "NOTICE_PUBLICATION_DATE": pub,
        "SOURCE_URL": source_url,
        "CAPTURE_TS": capture_ts,
        "BLOCKS": parsed_blocks,
    }


def cn_rows(notice: dict, sha: str) -> tuple[list[dict], list[dict]]:
    canonical, out_of_range = [], []
    cap = ts_to_dt(notice["CAPTURE_TS"]).date()
    pub = dt.date.fromisoformat(notice["NOTICE_PUBLICATION_DATE"])
    for block in notice["BLOCKS"]:
        kinds = (
            ("NON_WORKING", block["NON_WORKING_DATES"]),
            ("COMPENSATING_WORKING", block["COMPENSATING_WORKING_DATES"]),
            ("ENCOURAGED_REST", block["ENCOURAGED_REST_DATES"]),
        )
        for kind, dates in kinds:
            for iso in dates:
                ev = dt.date.fromisoformat(iso)
                if cap < ev and pub < ev:
                    status = "VERIFIED_PREANNOUNCED"
                elif pub < ev:
                    status = "VERIFIED_BY_DATED_OFFICIAL_NOTICE"
                else:
                    status = "UNRESOLVED_PUBLICATION_TIMING"
                row = {
                    "CALENDAR_ID": CN_ID,
                    "HOLIDAY_NAME": block["HOLIDAY_NAME"],
                    "OFFICIAL_LABEL": block["HOLIDAY_NAME"],
                    "EVENT_DATE": iso,
                    "YEAR": ev.year,
                    "EVENT_TYPE": kind,
                    "NON_WORKING_DATE": iso if kind == "NON_WORKING" else None,
                    "COMPENSATING_WORKING_DATE": iso if kind == "COMPENSATING_WORKING" else None,
                    "NOTICE_PUBLICATION_DATE": notice["NOTICE_PUBLICATION_DATE"],
                    "PUBLICATION_DATE": notice["NOTICE_PUBLICATION_DATE"],
                    "PUBLICATION_TIMESTAMP_IF_AVAILABLE": None,
                    "NOTICE_SOURCE": notice["SOURCE_URL"],
                    "SOURCE_URL": notice["SOURCE_URL"],
                    "ARCHIVE_CAPTURE_TIMESTAMP": notice["CAPTURE_TS"],
                    "ARCHIVE_CAPTURE_DATE": cap.isoformat(),
                    "SOURCE_DIGEST": sha,
                    "POINT_IN_TIME_STATUS": status,
                    "UNENUMERATED_WEEKEND_LINK": block["UNENUMERATED_WEEKEND_LINK"],
                    "NOTICE_PHRASE": block["NOTICE_PHRASE"],
                    "ROLE": "CONTROL_CONTAMINATION_EXCLUSION_AND_NON_DECISIVE_EXTENSION",
                    "NOTICE_YEAR": notice["NOTICE_YEAR"],
                }
                row["EVENT_ID"] = f"CN:{notice['NOTICE_YEAR']}:{kind}:{iso}:{block['HOLIDAY_NAME']}"
                if ev.year in CANONICAL_YEARS:
                    canonical.append(row)
                else:
                    row["CANONICAL"] = False
                    out_of_range.append(row)
    return canonical, out_of_range


# ---------------------------------------------------------------------------
# Dataset write
# ---------------------------------------------------------------------------

def dataset_digest(events, oor, authority, ledger) -> str:
    payload = {
        "EVENTS": events,
        "OUT_OF_RANGE_INVENTORY": oor,
        "SOURCE_AUTHORITY": authority,
        "SNAPSHOT_LEDGER": ledger,
    }
    return sha256_hex(canonical_json(payload))


def write_dataset(dataset_id: str, events, oor, authority, ledger, readme: str) -> str:
    folder = DATA_ROOT / dataset_id
    folder.mkdir(parents=True, exist_ok=True)
    digest = dataset_digest(events, oor, authority, ledger)
    files = {
        "EVENTS.json": events,
        "OUT_OF_RANGE_INVENTORY.json": oor,
        "SOURCE_AUTHORITY.json": authority,
        "SNAPSHOT_LEDGER.json": ledger,
    }
    file_digests = {}
    for name, obj in files.items():
        blob = canonical_json(obj)
        (folder / name).write_bytes(blob)
        file_digests[name] = sha256_hex(blob)
    raw_digests = {}
    for path in sorted((folder / "raw").rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(folder))
            raw_digests[rel] = sha256_hex(path.read_bytes())
    manifest = {
        "CANONICAL_DATASET_DIGEST": digest,
        "CANONICAL_DATASET_DIGEST_RULE": (
            "sha256(canonical_json({EVENTS, OUT_OF_RANGE_INVENTORY, "
            "SOURCE_AUTHORITY, SNAPSHOT_LEDGER})) sort_keys separators=(',',':') ASCII"
        ),
        "CANONICAL_YEARS": list(CANONICAL_YEARS),
        "DATASET_ID": dataset_id,
        "EVENT_COUNT": len(events),
        "FILE_DIGESTS_SHA256": file_digests,
        "MARKET_DATA_PRESENT": False,
        "OUT_OF_RANGE_COUNT": len(oor),
        "RAW_FILE_DIGESTS_SHA256": raw_digests,
    }
    (folder / "MANIFEST.json").write_bytes(canonical_json(manifest))
    (folder / "README.md").write_text(readme)
    (folder / ".gitattributes").write_text("raw/wayback/*.bin binary\nraw/live/*.bin binary\n")
    return digest


def object_record(path: Path, original_url: str, archive_ts: str, archive_url: str) -> dict:
    data = path.read_bytes()
    return {
        "ARCHIVE_CAPTURE_TIMESTAMP": archive_ts,
        "ARCHIVE_DIGEST": None,
        "ARCHIVE_URL": archive_url,
        "BYTE_LENGTH": len(data),
        "CONTENT_TYPE": "text/html" if data[:2] != b"\x1f\x8b" else "application/gzip",
        "FETCHED_AT": FETCHED_AT,
        "LOCAL_SHA256": sha256_hex(data),
        "OBTAINED": True,
        "ORIGINAL_URL": original_url,
        "RELATIVE_PATH": str(path.name),
        "SOURCE_ID": sha256_hex(data),
    }


def store_raw(dataset_id: str, src: Path, original_url: str, archive_ts: str) -> tuple[Path, dict]:
    data = src.read_bytes()
    digest = sha256_hex(data)
    dest_dir = DATA_ROOT / dataset_id / "raw" / "wayback"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{digest}.bin"
    if not dest.exists():
        dest.write_bytes(data)
    archive_url = f"https://web.archive.org/web/{archive_ts}id_/{original_url}"
    rec = object_record(dest, original_url, archive_ts, archive_url)
    rec["RELATIVE_PATH"] = f"raw/wayback/{digest}.bin"
    return dest, rec


def build() -> dict:
    staging = Path("/tmp/c020_src")
    nyse_specs = [
        ("nyse_20191210153443.html", "20191210153443"),
        ("nyse_20200604065023.html", "20200604065023"),
        ("nyse_20210606021355.html", "20210606021355"),
        ("nyse_20211206135816.html", "20211206135816"),
        ("nyse_20220606133135.html", "20220606133135"),
        ("nyse_20230601084000.html", "20230601084000"),
        ("nyse_20241201171442.html", "20241201171442"),
    ]
    opm_specs = [
        ("opm_20191202170511.html", "20191202170511"),
        ("opm_20201212002756.html", "20201212002756"),
        ("opm_20210617185502.html", "20210617185502"),
        ("opm_20210705234447.html", "20210705234447"),
        ("opm_20211201170029.html", "20211201170029"),
    ]
    cn_specs = [
        ("cn2020_wb.html", "20191122024912", "http://www.gov.cn/zhengce/content/2019-11/21/content_5454164.htm"),
        ("cn2021_wb.html", "20201130203324", "http://www.gov.cn/zhengce/content/2020-11/25/content_5564127.htm"),
        ("cn2022_wb.html", "20211025160828", "https://www.gov.cn/zhengce/content/2021-10/25/content_5644835.htm"),
        ("cn2023_wb.html", "20221208155401", "https://www.gov.cn/zhengce/content/2022-12/08/content_5730844.htm"),
        ("cn2024_wb.html", "20240304143445", "https://www.gov.cn/zhengce/zhengceku/202310/content_6911528.htm"),
    ]
    nyse_snaps = []
    nyse_ledger = []
    for name, ts in nyse_specs:
        dest, rec = store_raw(NYSE_ID, staging / name, NYSE_URL, ts)
        raw, _ = load_bytes(dest)
        html = raw.decode("utf-8", "replace")
        parsed = parse_nyse_snapshot(html, ts)
        nyse_snaps.append((rec["LOCAL_SHA256"], ts, parsed))
        rec["PARSED_ROW_COUNT"] = len(parsed)
        nyse_ledger.append(rec)
    nyse_events, nyse_oor = merge_nyse(nyse_snaps)
    nyse_auth = {
        "CALENDAR_ID": NYSE_ID,
        "FIRST_PARTY": True,
        "ROLE": "PRIMARY_EVENT_DEFINITION",
        "ROLE_NOTE": "Lead arm is full weekday NYSE closures. Early closes are retained and are not primary.",
        "SOURCE_URL": NYSE_URL,
        "AUTHORITY": "NYSE / ICE hours-and-holidays page, dated Wayback captures",
        "THIRD_PARTY_USED_AS_CANONICAL": False,
    }
    nyse_digest = write_dataset(
        NYSE_ID, nyse_events, nyse_oor, nyse_auth,
        {"OBJECTS": nyse_ledger},
        nyse_readme(nyse_events),
    )

    opm_snaps = []
    opm_ledger = []
    for name, ts in opm_specs:
        dest, rec = store_raw(OPM_ID, staging / name, OPM_URL, ts)
        raw, _ = load_bytes(dest)
        html = raw.decode("utf-8", "replace")
        parsed = parse_opm_snapshot(html, ts)
        opm_snaps.append((rec["LOCAL_SHA256"], ts, parsed))
        rec["PARSED_ROW_COUNT"] = len(parsed)
        opm_ledger.append(rec)
    opm_events, opm_oor = merge_opm(opm_snaps)
    opm_auth = {
        "CALENDAR_ID": OPM_ID,
        "FIRST_PARTY": True,
        "ROLE": "OTHER_FALSIFIER_SPECIFICITY",
        "ROLE_NOTE": "Federal-office holidays. An OPM holiday does not prove NYSE closure. Nominal and observed dates are both stored.",
        "SOURCE_URL": OPM_URL,
        "AUTHORITY": "U.S. Office of Personnel Management federal holiday schedules, dated Wayback captures",
        "THIRD_PARTY_USED_AS_CANONICAL": False,
    }
    opm_digest = write_dataset(
        OPM_ID, opm_events, opm_oor, opm_auth,
        {"OBJECTS": opm_ledger},
        opm_readme(opm_events),
    )

    cn_events, cn_oor = [], []
    cn_ledger = []
    for name, ts, url in cn_specs:
        dest, rec = store_raw(CN_ID, staging / name, url, ts)
        raw, _ = load_bytes(dest)
        html = raw.decode("utf-8", "replace")
        notice = parse_cn_snapshot(html, ts, url)
        ev, oor = cn_rows(notice, rec["LOCAL_SHA256"])
        cn_events.extend(ev)
        cn_oor.extend(oor)
        rec["NOTICE_YEAR"] = notice["NOTICE_YEAR"]
        rec["NOTICE_PUBLICATION_DATE"] = notice["NOTICE_PUBLICATION_DATE"]
        cn_ledger.append(rec)
    # duplicate identity check happens in validate
    cn_events.sort(key=lambda r: (r["EVENT_DATE"], r["EVENT_TYPE"], r["HOLIDAY_NAME"]))
    cn_oor.sort(key=lambda r: (r["EVENT_DATE"], r["EVENT_TYPE"]))
    cn_auth = {
        "CALENDAR_ID": CN_ID,
        "FIRST_PARTY": True,
        "ROLE": "CONTROL_CONTAMINATION_EXCLUSION_AND_NON_DECISIVE_EXTENSION",
        "ROLE_NOTE": (
            "Annual State Council notices. Non-working days and compensating "
            "working days are separate. The China arm is a non-decisive search-surface "
            "extension. Makeup days are also the control-contamination exclusion. "
            "Neither use defines the NYSE lead arm."
        ),
        "AUTHORITY": "State Council / gov.cn annual holiday notices",
        "THIRD_PARTY_USED_AS_CANONICAL": False,
    }
    cn_digest = write_dataset(
        CN_ID, cn_events, cn_oor, cn_auth,
        {"OBJECTS": cn_ledger},
        cn_readme(cn_events),
    )
    summary = summarize(nyse_digest, nyse_events, opm_digest, opm_events, cn_digest, cn_events, nyse_oor, opm_oor, cn_oor, nyse_ledger, opm_ledger, cn_ledger)
    (RESEARCH / "GV0R01_C020_HOLIDAY_CALENDAR_PIN.json").write_bytes(canonical_json(summary))
    return summary


def nyse_readme(events) -> str:
    full = sum(1 for r in events if r["EVENT_TYPE"] == "FULL_DAY_CLOSURE")
    early = sum(1 for r in events if r["EVENT_TYPE"] == "EARLY_CLOSE")
    return (
        "# NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0\n\n"
        "First-party NYSE hours-and-holidays captures. Discovery years 2020-2024.\n"
        f"Full weekday closures: {full}. Early closes: {early}.\n"
        "Early closes are not the C020 lead arm. This file does not define a session,\n"
        "a share, or a test.\n"
    )


def opm_readme(events) -> str:
    return (
        "# US_OPM_FEDERAL_HOLIDAY_LIST_V0\n\n"
        "OPM federal holiday schedules for 2020-2024. Observed dates and nominal\n"
        "statutory dates are separate fields. An OPM holiday is not an NYSE closure.\n"
        f"Canonical rows: {len(events)}.\n"
    )


def cn_readme(events) -> str:
    nw = sum(1 for r in events if r["EVENT_TYPE"] == "NON_WORKING")
    cw = sum(1 for r in events if r["EVENT_TYPE"] == "COMPENSATING_WORKING")
    return (
        "# CN_STATE_COUNCIL_HOLIDAY_NOTICES_V0\n\n"
        "Annual State Council holiday notices. Non-working dates and compensating\n"
        f"working dates are separate. Non-working rows: {nw}. Compensating rows: {cw}.\n"
        "Weekend days that the notice only describes as 与周末连休 are not expanded.\n"
    )


def summarize(nyse_digest, nyse_events, opm_digest, opm_events, cn_digest, cn_events, nyse_oor, opm_oor, cn_oor, nyse_ledger, opm_ledger, cn_ledger) -> dict:
    def unresolved(rows):
        return sum(1 for r in rows if r["POINT_IN_TIME_STATUS"].startswith("UNRESOLVED") or r["POINT_IN_TIME_STATUS"] == "SOURCE_CONFLICT")
    raw_bytes = 0
    raw_n = 0
    for ledger in (nyse_ledger, opm_ledger, cn_ledger):
        for obj in ledger:
            raw_n += 1
            raw_bytes += obj["BYTE_LENGTH"]
    return {
        "UNIT": "GV0R01_C020_HOLIDAY_CALENDAR_PINNING",
        "NYSE_ROLE": "PRIMARY_EVENT_DEFINITION",
        "CN_STATE_COUNCIL_ROLE": "CONTROL_CONTAMINATION_EXCLUSION_AND_NON_DECISIVE_EXTENSION",
        "US_OPM_ROLE": "OTHER_FALSIFIER_SPECIFICITY",
        "NYSE_DATASET_ID": NYSE_ID,
        "NYSE_DATASET_PATH": f"docs/research_data/{NYSE_ID}",
        "NYSE_DATASET_DIGEST": nyse_digest,
        "NYSE_CANONICAL_ROW_COUNT": len(nyse_events),
        "NYSE_FULL_WEEKDAY_CLOSURE_COUNT": sum(1 for r in nyse_events if r["EVENT_TYPE"] == "FULL_DAY_CLOSURE"),
        "NYSE_EARLY_CLOSE_COUNT": sum(1 for r in nyse_events if r["EVENT_TYPE"] == "EARLY_CLOSE"),
        "NYSE_UNRESOLVED_COUNT": unresolved(nyse_events),
        "OPM_DATASET_ID": OPM_ID,
        "OPM_DATASET_PATH": f"docs/research_data/{OPM_ID}",
        "OPM_DATASET_DIGEST": opm_digest,
        "OPM_CANONICAL_ROW_COUNT": len(opm_events),
        "OPM_UNRESOLVED_COUNT": unresolved(opm_events),
        "CN_DATASET_ID": CN_ID,
        "CN_DATASET_PATH": f"docs/research_data/{CN_ID}",
        "CN_DATASET_DIGEST": cn_digest,
        "CN_NON_WORKING_ROW_COUNT": sum(1 for r in cn_events if r["EVENT_TYPE"] == "NON_WORKING"),
        "CN_COMPENSATING_WORKING_ROW_COUNT": sum(1 for r in cn_events if r["EVENT_TYPE"] == "COMPENSATING_WORKING"),
        "CN_UNRESOLVED_COUNT": unresolved(cn_events),
        "CN_ENCOURAGED_REST_ROW_COUNT": sum(1 for r in cn_events if r["EVENT_TYPE"] == "ENCOURAGED_REST"),
        "RAW_SOURCE_OBJECT_COUNT": raw_n,
        "RAW_SOURCE_BYTES_RETAINED": raw_bytes,
        "POINT_IN_TIME_STATUS_BY_DATASET": {
            NYSE_ID: sorted({r["POINT_IN_TIME_STATUS"] for r in nyse_events}),
            OPM_ID: sorted({r["POINT_IN_TIME_STATUS"] for r in opm_events}),
            CN_ID: sorted({r["POINT_IN_TIME_STATUS"] for r in cn_events}),
        },
        "OUT_OF_RANGE_ROW_COUNTS": {
            NYSE_ID: len(nyse_oor),
            OPM_ID: len(opm_oor),
            CN_ID: len(cn_oor),
        },
        "MARKET_DATA_OPENED_FOR_C020": False,
        "MARKET_OUTCOMES_COMPUTED": False,
        "C020_PRIMARY_TEST_EXECUTED": False,
        "POWER_SIMULATION_PERFORMED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "CANONICAL_YEARS": list(CANONICAL_YEARS),
        "CROSS_SOURCE_DIAGNOSTICS": "NON_AUTHORITATIVE",
        "UNRESOLVED_ROWS_NOT_FOR_PRIMARY_SAMPLE": [
            "NYSE 2021 Juneteenth cell is a dash first captured after 2021-06-19",
            "OPM 2021 Juneteenth observed date is first captured after 2021-06-18",
        ],
        "STATUS": "HOLIDAY_CALENDARS_PINNED",
        "NEXT_UNIT": "GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER_CONTINUATION",
        "SESSION_BOUNDS_FROZEN": False,
        "C020_ENDPOINT_FROZEN": False,
    }


def validate() -> None:
    for dataset_id in (NYSE_ID, OPM_ID, CN_ID):
        folder = DATA_ROOT / dataset_id
        manifest = json.loads((folder / "MANIFEST.json").read_text())
        events = json.loads((folder / "EVENTS.json").read_text())
        oor = json.loads((folder / "OUT_OF_RANGE_INVENTORY.json").read_text())
        authority = json.loads((folder / "SOURCE_AUTHORITY.json").read_text())
        ledger = json.loads((folder / "SNAPSHOT_LEDGER.json").read_text())
        digest = dataset_digest(events, oor, authority, ledger)
        if digest != manifest["CANONICAL_DATASET_DIGEST"]:
            raise SystemExit(f"digest mismatch {dataset_id}")
        for rel, expect in manifest["RAW_FILE_DIGESTS_SHA256"].items():
            got = sha256_hex((folder / rel).read_bytes())
            if got != expect:
                raise SystemExit(f"raw digest mismatch {rel}")
        years = {r.get("YEAR") or int(r["EVENT_DATE"][:4]) for r in events}
        if not years <= set(CANONICAL_YEARS):
            raise SystemExit(f"year leak {dataset_id} {years}")
        if any((r.get("YEAR") in (2025, 2026) or (r.get("EVENT_DATE") or "").startswith(("2025", "2026"))) for r in events):
            raise SystemExit("2025/2026 in canonical")
        ids = [r["EVENT_ID"] for r in events]
        if len(ids) != len(set(ids)):
            raise SystemExit(f"duplicate ids {dataset_id}")
        if not authority["FIRST_PARTY"]:
            raise SystemExit("authority")
    print("validate ok")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        summary = build()
        print(canonical_json(summary).decode())
    elif cmd == "validate":
        validate()
    else:
        raise SystemExit(cmd)
