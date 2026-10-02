"""Read-only PRODUCT_FIRST U1a–U5 evaluator.

Scores a measurement snapshot against the frozen contract and a cutoff.
Missing evidence and an unfrozen choice that would change the cell return
MEASUREMENT_FAILURE. Product INCONCLUSIVE is only the cell named in the
decision table. This module does not read admin stats or the usage report.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

FREEZE = "REQUIRES_FREEZE_BEFORE_DAY0"
MF = "MEASUREMENT_FAILURE"
PASS = "PASS"
FAIL = "FAIL"
INC = "INCONCLUSIVE"
NOT_PASS = "NOT_PASS"
KYIV = ZoneInfo("Europe/Kyiv")
_PSEUDONYM = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_KEYS = frozenset({"telegram_user_id", "telegram_id", "chat_id", "user_pk"})
_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "config" / "measurement_contract_v1.json"

# Copied from PRODUCT_FIRST decision §7. The contract file must match.
DECISION_THRESHOLDS = {
    "U4_pass_min_unknown_joins": 8,
    "U4_window_days": 12,
    "U4_work_hours_max": 6,
    "U1a_pass_min_users": 4,
    "U1a_pass_min_days": 2,
    "U1a_withdrawal_day_count": 3,
    "U1a_brief_off_pass_max": 1,
    "U1a_fail_react_max": 2,
    "U1a_fail_brief_off_min": 3,
    "U1a_inconclusive_react": 3,
    "U1b_pass_min_users": 4,
    "U1b_min_days_per_week": 3,
    "U1b_fail_max_users": 2,
    "U1b_inconclusive_users": 3,
    "U2_pass_min_positive_users": 4,
    "U2_useful_share_min": 0.6,
    "U2_useful_votes_min": 5,
    "U2_click_share_min": 0.4,
    "U2_disabled_blocked_pass_max": 2,
    "U2_disabled_blocked_fail_min": 3,
    "U2_fail_positive_max": 2,
    "U2_push_floor": 15,
    "U3_offer_day_start": 21,
    "U3_offer_day_end": 25,
    "U3_pass_min_paid": 3,
    "U3_pass_min_rate": 0.25,
    "U3_fail_max_paid": 1,
    "U3_inconclusive_paid": 2,
    "U3_refund_within_days": 30,
    "U5_pass_min_users": 5,
    "U5_click_distinct_days": 2,
}

ACTIVITY_TAINTED = frozenset({"U1a", "U1b", "U2", "U5"})
_FORMULAS = {}


def load_contract(path: Path | None = None) -> dict:
    raw = json.loads((path or _CONTRACT_PATH).read_text(encoding="utf-8"))
    if raw.get("frozen", {}).get("thresholds") != DECISION_THRESHOLDS:
        raise ValueError("measurement contract thresholds diverge from the decision table")
    if raw.get("frozen", {}).get("timezone") != "Europe/Kyiv":
        raise ValueError("measurement contract timezone is not Europe/Kyiv")
    return raw


def evaluate(snapshot: dict, contract: dict, *, cutoff, overlay: dict | None = None) -> dict:
    """Score U1a–U5. `overlay` may fill REQUIRES_FREEZE keys only."""
    overlay = dict(overlay or {})
    unknown = sorted(set(overlay) - set(contract.get("requires_freeze_before_day0") or {}))
    if unknown:
        return _blank(cutoff, "OVERLAY_KEY_NOT_FREEZABLE", {"keys": unknown})
    if contract.get("frozen", {}).get("thresholds") != DECISION_THRESHOLDS:
        return _blank(cutoff, "THRESHOLDS_DIVERGE", {})
    if _has_identity(snapshot):
        return _blank(cutoff, "IDENTITY_IN_SNAPSHOT", {})
    bad_pseudo = [e.get("enrollment_pk") for e in snapshot.get("enrollments") or []
                  if not _PSEUDONYM.fullmatch(str(e.get("pseudonym") or ""))]
    if bad_pseudo:
        return _blank(cutoff, "PSEUDONYM_INVALID", {"enrollment_pk": bad_pseudo})
    cutoff_dt = _dt(cutoff)
    params = {key: _param(contract, overlay, key)
              for key in (contract.get("requires_freeze_before_day0") or {})}
    try:
        known = _classification_as_of(snapshot, cutoff_dt)
    except _Tie as exc:
        return _blank(cutoff_dt, "CLASSIFICATION_TIE", {"enrollment_pk": exc.enrollment_pk})
    if known is None:
        return _blank(cutoff_dt, "COHORT_CLASSIFICATION_MISSING", {})
    cohort, origin = _cohort(snapshot, known, cutoff_dt)
    excluded, exclusion_reason = _excluded_dates(snapshot, params, cohort, origin, cutoff_dt)
    if exclusion_reason:
        return _blank(cutoff_dt, exclusion_reason, {"origin": _iso(origin) if origin else None})
    ctx = _Ctx(snapshot, params, cohort, origin, cutoff_dt, excluded, contract)
    metrics = {
        "U1a": _u1a(ctx),
        "U1b": _u1b(ctx),
        "U2": _u2(ctx),
        "U3": _u3(ctx),
        "U4": _u4(ctx),
        "U5": _u5(ctx),
    }
    if _activity_tainted(snapshot, cutoff_dt):
        for code in ACTIVITY_TAINTED:
            metrics[code] = _cell(MF, "ACTIVITY_WRITE_FAILURE")
    return {
        "cutoff": _iso(cutoff_dt),
        "origin": None if origin is None else _iso(origin),
        "excluded_dates": [d.isoformat() for d in sorted(excluded)],
        "metrics": metrics,
        "decision": _decision(metrics, params),
        "unfrozen": [k for k, v in params.items() if v is None],
    }


class _Tie(Exception):
    def __init__(self, enrollment_pk):
        self.enrollment_pk = enrollment_pk


class _Ctx:
    def __init__(self, snapshot, params, cohort, origin, cutoff, excluded, contract):
        self.snapshot = snapshot
        self.params = params
        self.cohort = cohort
        self.origin = origin
        self.cutoff = cutoff
        self.excluded = excluded
        self.thresholds = contract["frozen"]["thresholds"]
        self.reaction = frozenset(contract["frozen"]["reaction_actions"])
        self.fake_door = contract["frozen"]["fake_door_action"]
        self.measurement = tuple(contract["frozen"]["measurement_days"])
        self.retention = tuple(contract["frozen"]["retention_days"])
        self.prompt_window_s = int(contract["frozen"]["push_reaction_window_s"])
        formula = params.get("delivery_failure_day")
        self.applies = set(formula.get("applies_to") or []) if isinstance(formula, dict) else set()


def _blank(cutoff, reason, detail) -> dict:
    cell = _cell(MF, reason, **detail)
    return {
        "cutoff": _iso(cutoff) if not isinstance(cutoff, str) else cutoff,
        "origin": None,
        "excluded_dates": [],
        "metrics": {code: dict(cell) for code in ("U1a", "U1b", "U2", "U3", "U4", "U5")},
        "decision": _cell(MF, reason),
        "unfrozen": [],
    }


def _cell(status, reason, **detail) -> dict:
    return {"status": status, "reason": reason, "detail": detail}


def _param(contract, overlay, key):
    if key in overlay and overlay[key] != FREEZE:
        return overlay[key]
    raw = (contract.get("requires_freeze_before_day0") or {}).get(key, FREEZE)
    if raw == FREEZE or raw is None:
        return None
    return raw


def _has_identity(obj) -> bool:
    if isinstance(obj, dict):
        if _IDENTITY_KEYS.intersection(obj):
            return True
        return any(_has_identity(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(_has_identity(v) for v in obj)
    return False


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(type(value).__name__)


def _iso(value) -> str:
    if value is None:
        return ""
    return _dt(value).astimezone(timezone.utc).isoformat()


def _day(value) -> date:
    if isinstance(value, datetime):
        return value.astimezone(KYIV).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(type(value).__name__)


def _kyiv_date(value) -> date:
    return _dt(value).astimezone(KYIV).date()


def _p25(values: list[float]) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * 0.25
    lo = int(math.floor(k))
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def volatility_bottom_quartile(prices, origin_date, formula_id):
    """Return True, False, SHORT, or UNKNOWN_FORMULA. Not selected by the contract."""
    fn = _FORMULAS.get(formula_id)
    if fn is None:
        return "UNKNOWN_FORMULA"
    return fn(prices, origin_date)


def _mean_sq(prices, origin_date):
    closes = {}
    for row in prices or []:
        closes[_day(row["date"])] = float(row["close"])
    day8 = origin_date + timedelta(days=7)
    day30 = origin_date + timedelta(days=29)
    first = day8 - timedelta(days=91)
    last = day30
    cursor = first
    while cursor <= last:
        if cursor not in closes or closes[cursor] <= 0:
            return "SHORT"
        cursor += timedelta(days=1)
    squares = {}
    cursor = first + timedelta(days=1)
    while cursor <= last:
        squares[cursor] = math.log(closes[cursor] / closes[cursor - timedelta(days=1)]) ** 2
        cursor += timedelta(days=1)
    prior = [squares[day8 - timedelta(days=offset)] for offset in range(90, 0, -1)]
    month = [squares[day8 + timedelta(days=offset)] for offset in range((day30 - day8).days + 1)]
    if len(prior) != 90 or not month:
        return "SHORT"
    return (sum(month) / len(month)) <= _p25(prior)


_FORMULAS["MEAN_SQUARED_LOG_RETURN_VS_P25_PRIOR_90"] = _mean_sq


def _classification_as_of(snapshot, cutoff):
    by_pk = {}
    for row in snapshot.get("classifications") or []:
        if _dt(row["recorded_at"]) <= cutoff:
            by_pk.setdefault(row["enrollment_pk"], []).append(row)
    known = {}
    enrollments = snapshot.get("enrollments") or []
    for enr in enrollments:
        if _dt(enr["joined_at"]) > cutoff:
            continue
        rows = by_pk.get(enr["enrollment_pk"]) or []
        if not rows:
            return None
        latest = max(_dt(r["recorded_at"]) for r in rows)
        values = {bool(r["known_contact"]) for r in rows if _dt(r["recorded_at"]) == latest}
        if len(values) != 1:
            raise _Tie(enr["enrollment_pk"])
        known[enr["enrollment_pk"]] = values.pop()
    return known


def _cohort(snapshot, known, cutoff):
    people = []
    for enr in snapshot.get("enrollments") or []:
        if _dt(enr["joined_at"]) > cutoff:
            continue
        if enr["enrollment_pk"] not in known:
            continue
        people.append({
            "enrollment_pk": enr["enrollment_pk"],
            "pseudonym": enr["pseudonym"],
            "joined_at": _dt(enr["joined_at"]),
            "invite_label": enr.get("invite_label"),
            "known": known[enr["enrollment_pk"]],
            "owner": bool(enr.get("owner_excluded")),
        })
    unknown = [p for p in people if not p["owner"] and not p["known"]]
    origin = min((p["joined_at"] for p in unknown), default=None)
    return {"all": people, "unknown": unknown}, origin


def _day_number(ctx, when) -> int | None:
    if ctx.origin is None:
        return None
    return (_kyiv_date(when) - _kyiv_date(ctx.origin)).days + 1


def _in_days(ctx, when, bounds) -> bool:
    n = _day_number(ctx, when)
    return n is not None and bounds[0] <= n <= bounds[1]


def _rows_at(rows, cutoff, key):
    out = []
    for row in rows or []:
        if row.get(key) is None:
            continue
        if _dt(row[key]) <= cutoff:
            out.append(row)
    return out


def _activity_tainted(snapshot, cutoff) -> bool:
    tel = snapshot.get("telemetry") or {}
    failures = int(tel.get("activity_write_failures") or 0)
    if failures <= 0:
        return False
    last = tel.get("last_failure_at")
    if last is None:
        return True
    return _dt(last) <= cutoff


def _needs_failure_formula(snapshot, cutoff) -> bool:
    for row in _rows_at(snapshot.get("briefs"), cutoff, "recorded_at"):
        if row.get("state") != "SENT":
            return True
    for row in _rows_at(snapshot.get("deliveries"), cutoff, "finished_at"):
        if row.get("state") != "SENT":
            return True
    return False


def _enrolled_unknown_on(ctx, day: date):
    as_of = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=KYIV)
    if as_of > ctx.cutoff:
        as_of = ctx.cutoff
    try:
        known = _classification_as_of(ctx.snapshot, as_of)
    except _Tie:
        return None
    if known is None:
        return None
    out = []
    for enr in ctx.snapshot.get("enrollments") or []:
        if bool(enr.get("owner_excluded")):
            continue
        if _dt(enr["joined_at"]) > as_of:
            continue
        if enr["enrollment_pk"] not in known or known[enr["enrollment_pk"]]:
            continue
        if _kyiv_date(enr["joined_at"]) <= day:
            out.append(enr["enrollment_pk"])
    return out


def _excluded_dates(snapshot, params, cohort, origin, cutoff):
    if origin is None:
        return set(), None
    if not _needs_failure_formula(snapshot, cutoff):
        return set(), None
    formula = params.get("delivery_failure_day")
    if not isinstance(formula, dict):
        return set(), "DELIVERY_FAILURE_DAY_UNFROZEN"
    needed = {"denominator", "brief_failure_states", "episodic_failure_states", "applies_to"}
    if set(formula) != needed or formula["denominator"] != "ENROLLED_UNKNOWN_AS_OF_DAY":
        return set(), "DELIVERY_FAILURE_DAY_UNFROZEN"
    tmp = SimpleNamespace(snapshot=snapshot, cutoff=cutoff, origin=origin)
    dates = set()
    for row in _rows_at(snapshot.get("briefs"), cutoff, "recorded_at"):
        dates.add(_day(row["brief_date"]))
    for row in _rows_at(snapshot.get("deliveries"), cutoff, "finished_at"):
        dates.add(_kyiv_date(row["finished_at"]))
    excluded = set()
    brief_bad = set(formula["brief_failure_states"])
    epi_bad = set(formula["episodic_failure_states"])
    for day in dates:
        members = _enrolled_unknown_on(tmp, day)
        if members is None:
            return set(), "CLASSIFICATION_TIE"
        if not members:
            continue
        failed = set()
        for row in _rows_at(snapshot.get("briefs"), cutoff, "recorded_at"):
            if _day(row["brief_date"]) == day and row.get("state") in brief_bad:
                if row["enrollment_pk"] in members:
                    failed.add(row["enrollment_pk"])
        for row in _rows_at(snapshot.get("deliveries"), cutoff, "finished_at"):
            if _kyiv_date(row["finished_at"]) == day and row.get("state") in epi_bad:
                if row["enrollment_pk"] in members:
                    failed.add(row["enrollment_pk"])
        if len(failed) / len(members) > 0.30:
            excluded.add(day)
    return excluded, None


def _sent_times(ctx, enrollment_pk):
    times = []
    for row in _rows_at(ctx.snapshot.get("deliveries"), ctx.cutoff, "finished_at"):
        if row.get("enrollment_pk") == enrollment_pk and row.get("state") == "SENT":
            times.append(_dt(row["finished_at"]))
    return times


def _prompted(at, sent_times, window_s) -> bool:
    stamp = _dt(at)
    return any(0 <= (stamp - sent).total_seconds() <= window_s for sent in sent_times)


def _drops(ctx, metric, day) -> bool:
    return metric in ctx.applies and day in ctx.excluded


def _setting_users(ctx, action, reading, metric):
    rows = [r for r in _rows_at(ctx.snapshot.get("activity"), ctx.cutoff, "at")
            if r.get("action") == action and r.get("enrollment_pk") in {p["enrollment_pk"] for p in ctx.cohort["unknown"]}]
    ids = {p["enrollment_pk"] for p in ctx.cohort["unknown"]}
    if reading is None:
        if not rows:
            return 0
        return None
    if reading == "OFF_EVENT_IN_MEASUREMENT_WINDOW":
        hit = set()
        for row in rows:
            if row.get("detail") == "off" and _in_days(ctx, row["at"], ctx.measurement):
                if not _drops(ctx, metric, _kyiv_date(row["at"])):
                    hit.add(row["enrollment_pk"])
        return len(hit)
    if reading == "OFF_AT_CUTOFF":
        hit = 0
        for pk in ids:
            mine = [r for r in rows if r["enrollment_pk"] == pk]
            if not mine:
                continue
            last = max(mine, key=lambda r: _dt(r["at"]))
            if last.get("detail") == "off":
                hit += 1
        return hit
    return None


def _u1a(ctx: _Ctx) -> dict:
    if ctx.origin is None:
        return _cell(MF, "NO_UNKNOWN_COHORT")
    dates = ctx.params.get("briefing_withdrawal_dates")
    agg = ctx.params.get("u1a_aggregation")
    if not isinstance(dates, list) or len(dates) != ctx.thresholds["U1a_withdrawal_day_count"]:
        return _cell(MF, "U1A_WITHDRAWAL_DATES_UNFROZEN")
    days = [_day(d) for d in dates]
    if len(set(days)) != len(days):
        return _cell(MF, "U1A_WITHDRAWAL_DATES_UNFROZEN")
    if any(_drops(ctx, "U1a", d) for d in days):
        return _cell(MF, "WITHDRAWAL_DAY_EXCLUDED")
    if agg not in ("PER_USER_AT_LEAST_2_OF_3_DAYS", "AT_LEAST_2_DAYS_WITH_AT_LEAST_4_USERS"):
        return _cell(MF, "U1A_AGGREGATION_UNFROZEN")
    question = ctx.params.get("u1a_verbal_question_id")
    interviews = _rows_at(ctx.snapshot.get("interviews"), ctx.cutoff, "answered_at")
    if question is None and _interview_in_windows(ctx, interviews, days):
        return _cell(MF, "U1A_VERBAL_QUESTION_UNFROZEN")
    brief_off = _setting_users(ctx, "cmd_brief", ctx.params.get("brief_off_reading"), "U1a")
    if brief_off is None:
        return _cell(MF, "BRIEF_OFF_READING_UNFROZEN")
    reacted = {p["enrollment_pk"]: set() for p in ctx.cohort["unknown"]}
    for pk, days_hit in reacted.items():
        for day in days:
            if _caught_up(ctx, pk, day) or _asked(ctx, pk, day, question, interviews):
                days_hit.add(day)
    qualifiers = [pk for pk, hits in reacted.items()
                  if len(hits) >= ctx.thresholds["U1a_pass_min_days"]]
    day_hits = 0
    for day in days:
        users = sum(1 for hits in reacted.values() if day in hits)
        if users >= ctx.thresholds["U1a_pass_min_users"]:
            day_hits += 1
    if agg == "PER_USER_AT_LEAST_2_OF_3_DAYS":
        react = len(qualifiers)
    else:
        react = day_hits
    return _u1a_cell(ctx, react, brief_off, len(ctx.cohort["unknown"]), agg)


def _interview_in_windows(ctx, interviews, days) -> bool:
    ids = {p["enrollment_pk"] for p in ctx.cohort["unknown"]}
    for row in interviews:
        if row.get("enrollment_pk") not in ids:
            continue
        for day in days:
            if _in_brief_window(row["answered_at"], day):
                return True
    return False


def _in_brief_window(at, day: date) -> bool:
    start = datetime(day.year, day.month, day.day, 8, 0, tzinfo=KYIV)
    return start <= _dt(at) < start + timedelta(hours=3)


def _caught_up(ctx, pk, day) -> bool:
    for row in _rows_at(ctx.snapshot.get("activity"), ctx.cutoff, "at"):
        if row.get("enrollment_pk") == pk and row.get("action") == "cmd_catchup" and _in_brief_window(row["at"], day):
            return True
    return False


def _asked(ctx, pk, day, question, interviews) -> bool:
    if not question:
        return False
    for row in interviews:
        if (row.get("enrollment_pk") == pk and row.get("question_id") == question
                and _in_brief_window(row["answered_at"], day)):
            return True
    return False


def _u1a_cell(ctx, react, brief_off, enrolled, aggregation) -> dict:
    t = ctx.thresholds
    detail = {"react": react, "brief_off": brief_off, "enrolled_unknown": enrolled}
    if aggregation == "PER_USER_AT_LEAST_2_OF_3_DAYS":
        pas = react >= t["U1a_pass_min_users"] and brief_off <= t["U1a_brief_off_pass_max"]
    else:
        pas = react >= t["U1a_pass_min_days"] and brief_off <= t["U1a_brief_off_pass_max"]
    fail = react <= t["U1a_fail_react_max"] or brief_off >= t["U1a_fail_brief_off_min"]
    inc = react == t["U1a_inconclusive_react"]
    return _resolve_shapes(pas, fail, inc, ctx.params.get("u1a_conflict_precedence"), "U1A_CELL_NOT_IN_CONTRACT", detail)


def _resolve_shapes(pas, fail, inc, precedence, missing_reason, detail) -> dict:
    shapes = {PASS: pas, FAIL: fail, INC: inc}
    hit = [name for name, on in shapes.items() if on]
    if len(hit) > 1:
        if precedence == "FAIL_WINS" and FAIL in hit:
            return _cell(FAIL, "CONFLICT_" + precedence, **detail)
        if precedence == "INCONCLUSIVE_WINS" and INC in hit:
            return _cell(INC, "CONFLICT_" + precedence, **detail)
        return _cell(MF, "CONFLICT_PRECEDENCE_UNFROZEN", **detail)
    if len(hit) == 1:
        return _cell(hit[0], hit[0], **detail)
    return _cell(MF, missing_reason, **detail)


def _u1b(ctx: _Ctx) -> dict:
    if ctx.origin is None:
        return _cell(MF, "NO_UNKNOWN_COHORT")
    actions = ctx.params.get("u1b_pull_actions")
    week = ctx.params.get("u1b_week_definition")
    if not isinstance(actions, list) or not actions:
        return _cell(MF, "U1B_PULL_ACTIONS_UNFROZEN")
    weeks = _weeks(week)
    if weeks is None:
        return _cell(MF, "U1B_WEEK_UNFROZEN")
    qualifiers = []
    for person in ctx.cohort["unknown"]:
        pk = person["enrollment_pk"]
        sent = _sent_times(ctx, pk)
        days = set()
        for row in _rows_at(ctx.snapshot.get("activity"), ctx.cutoff, "at"):
            if row.get("enrollment_pk") != pk or row.get("action") not in actions:
                continue
            if not _in_days(ctx, row["at"], ctx.retention):
                continue
            if _drops(ctx, "U1b", _kyiv_date(row["at"])):
                continue
            if _prompted(row["at"], sent, ctx.prompt_window_s):
                continue
            days.add(_day_number(ctx, row["at"]))
        if all(_count_in(days, lo, hi) >= ctx.thresholds["U1b_min_days_per_week"] for lo, hi in weeks):
            qualifiers.append(pk)
    n = len(qualifiers)
    t = ctx.thresholds
    detail = {"qualifiers": n, "enrolled_unknown": len(ctx.cohort["unknown"])}
    if n >= t["U1b_pass_min_users"]:
        return _cell(PASS, PASS, **detail)
    if n == t["U1b_inconclusive_users"]:
        return _cell(INC, INC, **detail)
    if n <= t["U1b_fail_max_users"]:
        return _cell(FAIL, FAIL, **detail)
    return _cell(MF, "U1B_CELL_NOT_IN_CONTRACT", **detail)


def _count_in(days, lo, hi) -> int:
    return sum(1 for n in days if lo <= n <= hi)


def _weeks(name):
    if name == "TWO_BLOCKS_18_24_AND_25_30":
        return [(18, 24), (25, 30)]
    if name == "ORIGIN_BLOCKS_OF_7_MIN3":
        blocks = []
        for start in range(1, 36, 7):
            end = start + 6
            overlap = [n for n in range(max(start, 18), min(end, 30) + 1)]
            if len(overlap) >= 3:
                blocks.append((overlap[0], overlap[-1]))
        return blocks or None
    return None


def _u2(ctx: _Ctx) -> dict:
    if ctx.origin is None:
        return _cell(MF, "NO_UNKNOWN_COHORT")
    scope = ctx.params.get("u2_push_floor_scope")
    if scope not in ("MEASUREMENT_WINDOW", "ALL_SENT"):
        return _cell(MF, "U2_PUSH_FLOOR_UNFROZEN")
    vol = _volatility(ctx)
    if vol == "UNFROZEN":
        return _cell(MF, "U2_VOLATILITY_UNFROZEN")
    if vol == "MISSING":
        return _cell(MF, "U2_VOLATILITY_INPUTS_MISSING")
    if vol == "SHORT":
        return _cell(MF, "U2_VOLATILITY_HISTORY_SHORT")
    if vol == "UNKNOWN_FORMULA":
        return _cell(MF, "U2_VOLATILITY_FORMULA_UNKNOWN")
    attribution = ctx.params.get("push_click_attribution")
    if attribution != "LATEST_SENT_WITHIN_WINDOW":
        return _cell(MF, "U2_CLICK_ATTRIBUTION_UNFROZEN")
    blocked, block_reason = _blocked_users(ctx)
    if block_reason:
        return _cell(MF, block_reason)
    if _setting_users(ctx, "cmd_push", ctx.params.get("u2_disable_reading"), "U2") is None:
        return _cell(MF, "U2_DISABLE_READING_UNFROZEN")
    positive = 0
    floor_breach = False
    try:
        for person in ctx.cohort["unknown"]:
            pushes = _push_rows(ctx, person["enrollment_pk"], scope)
            if len(pushes) < ctx.thresholds["U2_push_floor"]:
                floor_breach = True
            if _positive_user(ctx, person["enrollment_pk"], pushes):
                positive += 1
    except _Tie:
        return _cell(MF, "VOTE_TIE")
    disabled_blocked = len(blocked | _off_ids(ctx, "cmd_push", ctx.params.get("u2_disable_reading"), "U2"))
    t = ctx.thresholds
    detail = {
        "positive": positive,
        "disabled_or_blocked": disabled_blocked,
        "floor_breach": floor_breach,
        "volatility_bottom_quartile": bool(vol),
        "enrolled_unknown": len(ctx.cohort["unknown"]),
    }
    pas = positive >= t["U2_pass_min_positive_users"] and disabled_blocked <= t["U2_disabled_blocked_pass_max"]
    fail = disabled_blocked >= t["U2_disabled_blocked_fail_min"] or positive <= t["U2_fail_positive_max"]
    inc = bool(floor_breach) or bool(vol)
    return _resolve_shapes(pas, fail, inc, ctx.params.get("u2_conflict_precedence"),
                           "U2_CELL_NOT_IN_CONTRACT", detail)


def _off_ids(ctx, action, reading, metric):
    rows = [r for r in _rows_at(ctx.snapshot.get("activity"), ctx.cutoff, "at") if r.get("action") == action]
    ids = set()
    if reading == "OFF_EVENT_IN_MEASUREMENT_WINDOW":
        for row in rows:
            if row.get("detail") == "off" and _in_days(ctx, row["at"], ctx.measurement):
                if not _drops(ctx, metric, _kyiv_date(row["at"])) and _in_cohort(ctx, row.get("enrollment_pk")):
                    ids.add(row["enrollment_pk"])
    elif reading == "OFF_AT_CUTOFF":
        for person in ctx.cohort["unknown"]:
            mine = [r for r in rows if r.get("enrollment_pk") == person["enrollment_pk"]]
            if mine and max(mine, key=lambda r: _dt(r["at"])).get("detail") == "off":
                ids.add(person["enrollment_pk"])
    return ids


def _in_cohort(ctx, pk) -> bool:
    return any(p["enrollment_pk"] == pk for p in ctx.cohort["unknown"])


def _volatility(ctx):
    series = ctx.params.get("u2_volatility_series")
    formula = ctx.params.get("u2_volatility_formula")
    if not series or not formula:
        return "UNFROZEN"
    prices = ctx.snapshot.get("prices")
    if not prices:
        return "MISSING"
    return volatility_bottom_quartile(prices, _kyiv_date(ctx.origin), formula)


def _push_rows(ctx, pk, scope):
    rows = []
    for row in _rows_at(ctx.snapshot.get("deliveries"), ctx.cutoff, "finished_at"):
        if row.get("enrollment_pk") != pk or row.get("state") != "SENT":
            continue
        if scope == "MEASUREMENT_WINDOW" and not _in_days(ctx, row["finished_at"], ctx.measurement):
            continue
        if _drops(ctx, "U2", _kyiv_date(row["finished_at"])):
            continue
        rows.append(row)
    return rows


def _positive_user(ctx, pk, pushes) -> bool:
    if _useful_share(ctx, pk):
        return True
    if not pushes:
        return False
    clicked = _clicked_pushes(ctx, pk, pushes)
    return clicked / len(pushes) >= ctx.thresholds["U2_click_share_min"]


def _useful_share(ctx, pk) -> bool:
    latest = {}
    for row in _rows_at(ctx.snapshot.get("votes"), ctx.cutoff, "recorded_at"):
        if row.get("enrollment_pk") != pk:
            continue
        if not _in_days(ctx, row["recorded_at"], ctx.measurement):
            continue
        if _drops(ctx, "U2", _kyiv_date(row["recorded_at"])):
            continue
        key = row["episode_pk"]
        stamp = _dt(row["recorded_at"])
        prev = latest.get(key)
        if prev is None or stamp > prev[0]:
            latest[key] = (stamp, {row["vote"]})
        elif stamp == prev[0]:
            prev[1].add(row["vote"])
    if any(len(votes) != 1 for _, votes in latest.values()):
        raise _Tie(pk)
    if len(latest) < ctx.thresholds["U2_useful_votes_min"]:
        return False
    useful = sum(1 for _, votes in latest.values() if "USEFUL" in votes)
    return useful / len(latest) >= ctx.thresholds["U2_useful_share_min"]


def _clicked_pushes(ctx, pk, pushes) -> int:
    clicks = []
    for row in _rows_at(ctx.snapshot.get("activity"), ctx.cutoff, "at"):
        if row.get("enrollment_pk") == pk and row.get("action") in ctx.reaction:
            clicks.append(_dt(row["at"]))
    hit = set()
    for click in clicks:
        candidates = []
        for idx, push in enumerate(pushes):
            delta = (click - _dt(push["finished_at"])).total_seconds()
            if 0 <= delta <= ctx.prompt_window_s:
                candidates.append(( _dt(push["finished_at"]), idx))
        if candidates:
            hit.add(max(candidates)[1])
    return len(hit)


def _blocked_users(ctx):
    classifier = ctx.params.get("blocked_classifier")
    blocked = set()
    needs_classifier = False
    for row in _rows_at(ctx.snapshot.get("deliveries"), ctx.cutoff, "finished_at"):
        if not _in_cohort(ctx, row.get("enrollment_pk")):
            continue
        state = row.get("state")
        if state == "DELIVERY_UNKNOWN":
            continue
        if state != "FAILED":
            continue
        needs_classifier = True
        if not isinstance(classifier, list):
            continue
        if _matches(row.get("error_summary"), classifier):
            blocked.add(row["enrollment_pk"])
        elif not _matches(row.get("error_summary"), classifier):
            return set(), "U2_FAILURE_UNCLASSIFIED"
    for row in _rows_at(ctx.snapshot.get("briefs"), ctx.cutoff, "recorded_at"):
        if row.get("state") != "FAILED" or not _in_cohort(ctx, row.get("enrollment_pk")):
            continue
        klass = row.get("error_class")
        if klass == "BLOCKED":
            blocked.add(row["enrollment_pk"])
        elif klass == "NOT_BLOCKED":
            continue
        elif klass in ("AMBIGUOUS", "UNCLASSIFIED") or klass is None:
            if klass is None:
                needs_classifier = True
                if isinstance(classifier, list) and _matches(row.get("error_summary"), classifier):
                    blocked.add(row["enrollment_pk"])
                    continue
                if isinstance(classifier, list):
                    return set(), "U2_FAILURE_UNCLASSIFIED"
            else:
                return set(), "U2_FAILURE_UNCLASSIFIED"
    if needs_classifier and not isinstance(classifier, list):
        return set(), "BLOCKED_CLASSIFIER_UNFROZEN"
    return blocked, None


def _matches(summary, needles) -> bool:
    text = (summary or "").casefold()
    return any(str(n).casefold() in text for n in needles)


def _u3(ctx: _Ctx) -> dict:
    if ctx.origin is None:
        return _cell(MF, "NO_UNKNOWN_COHORT")
    offer_end = _kyiv_date(ctx.origin) + timedelta(days=ctx.thresholds["U3_offer_day_end"] - 1)
    by_end, by_cutoff = [], []
    for person in ctx.cohort["unknown"]:
        by_cutoff.append(person)
        if _kyiv_date(person["joined_at"]) <= offer_end:
            by_end.append(person)
    choice = ctx.params.get("u3_denominator")
    if {p["enrollment_pk"] for p in by_end} != {p["enrollment_pk"] for p in by_cutoff}:
        if choice == "ENROLLED_BY_OFFER_END":
            population = by_end
        elif choice == "ENROLLED_BY_CUTOFF":
            population = by_cutoff
        else:
            return _cell(MF, "U3_DENOMINATOR_UNFROZEN")
    else:
        population = by_cutoff
    if _kyiv_date(ctx.cutoff) < _kyiv_date(ctx.origin) + timedelta(days=ctx.thresholds["U3_offer_day_start"] - 1):
        return _cell(MF, "U3_WINDOW_NOT_OPEN")
    offers, payments, refunds = _commercial(ctx)
    missing = []
    for person in population:
        pk = person["enrollment_pk"]
        if not any(_offer_in_window(ctx, row) for row in offers.get(pk, [])):
            missing.append(pk)
    if missing:
        return _cell(MF, "U3_OFFER_MISSING", enrolled_unknown=len(population), missing=len(missing))
    paid = 0
    anchor = ctx.params.get("refund_anchor")
    for person in population:
        pk = person["enrollment_pk"]
        flag = _paid(ctx, pk, payments.get(pk), refunds.get(pk), offers.get(pk), anchor)
        if flag is None:
            return _cell(MF, "U3_REFUND_ANCHOR_UNFROZEN")
        paid += int(flag)
    rate = paid / len(population) if population else 0.0
    t = ctx.thresholds
    detail = {"paid": paid, "enrolled_unknown": len(population), "rate": rate}
    if paid >= t["U3_pass_min_paid"] and rate >= t["U3_pass_min_rate"]:
        return _cell(PASS, PASS, **detail)
    if paid <= t["U3_fail_max_paid"]:
        return _cell(FAIL, FAIL, **detail)
    if paid == t["U3_inconclusive_paid"]:
        return _cell(INC, INC, **detail)
    return _cell(MF, "U3_CELL_NOT_IN_CONTRACT", **detail)


def _commercial(ctx):
    offers, payments, refunds = {}, {}, {}
    buckets = {"OFFER": offers, "PAYMENT": payments, "REFUND": refunds}
    for row in _rows_at(ctx.snapshot.get("commercial"), ctx.cutoff, "recorded_at"):
        buckets.get(row.get("event_type"), {}).setdefault(row["enrollment_pk"], []).append(row)
    return offers, payments, refunds


def _offer_in_window(ctx, row) -> bool:
    n = _day_number(ctx, row["recorded_at"])
    return n is not None and ctx.thresholds["U3_offer_day_start"] <= n <= ctx.thresholds["U3_offer_day_end"]


def _paid(ctx, pk, payment_rows, refund_rows, offer_rows, anchor):
    payment_rows = payment_rows or []
    real = [r for r in payment_rows if _money_positive(r)]
    if not real:
        return False
    refunds = [r for r in (refund_rows or []) if _money_positive(r)]
    if not refunds:
        return True
    if anchor not in ("PAYMENT_PLUS_30D", "OFFER_PLUS_30D"):
        return None
    pay_at = min(_dt(r["recorded_at"]) for r in real)
    if anchor == "PAYMENT_PLUS_30D":
        limit = pay_at + timedelta(days=ctx.thresholds["U3_refund_within_days"])
    else:
        if not offer_rows:
            return None
        limit = min(_dt(r["recorded_at"]) for r in offer_rows) + timedelta(days=ctx.thresholds["U3_refund_within_days"])
    if any(_dt(r["recorded_at"]) <= limit for r in refunds):
        return False
    return True


def _money_positive(row) -> bool:
    try:
        return Decimal(str(row.get("amount"))) > 0 and bool(row.get("currency"))
    except Exception:
        return False


def _u4(ctx: _Ctx) -> dict:
    start = ctx.params.get("u4_window_start")
    work = ctx.params.get("u4_work_within_cap")
    if not isinstance(start, str) or work is None:
        return _cell(MF, "U4_WINDOW_OR_WORK_UNFROZEN")
    if work is not True:
        return _cell(MF, "U4_WORK_CAP")
    window_start = date.fromisoformat(start)
    window_end = window_start + timedelta(days=ctx.thresholds["U4_window_days"])
    joins = []
    labels = set()
    for person in ctx.cohort["unknown"]:
        joined = _kyiv_date(person["joined_at"])
        if _drops(ctx, "U4", joined):
            continue
        if window_start <= joined < window_end:
            joins.append(person["enrollment_pk"])
            if person.get("invite_label"):
                labels.add(person["invite_label"])
    detail = {"joins": len(joins), "channels": len(labels), "enrolled_unknown": len(ctx.cohort["unknown"])}
    if len(labels) < 2 and joins:
        return _cell(MF, "U4_CHANNELS", **detail)
    closed = _kyiv_date(ctx.cutoff) >= window_end
    if len(joins) >= ctx.thresholds["U4_pass_min_unknown_joins"]:
        return _cell(PASS, PASS, **detail)
    if not closed:
        return _cell(MF, "U4_WINDOW_OPEN", **detail)
    return _cell(FAIL, FAIL, **detail)


def _u5(ctx: _Ctx) -> dict:
    if ctx.origin is None:
        return _cell(MF, "NO_UNKNOWN_COHORT")
    clickers = set()
    for person in ctx.cohort["unknown"]:
        days = set()
        for row in _rows_at(ctx.snapshot.get("activity"), ctx.cutoff, "at"):
            if row.get("enrollment_pk") != person["enrollment_pk"] or row.get("action") != ctx.fake_door:
                continue
            if not _in_days(ctx, row["at"], ctx.measurement):
                continue
            if _drops(ctx, "U5", _kyiv_date(row["at"])):
                continue
            days.add(_kyiv_date(row["at"]))
        if len(days) >= ctx.thresholds["U5_click_distinct_days"]:
            clickers.add(person["enrollment_pk"])
    question = ctx.params.get("u5_verbal_question_id")
    verbal = set()
    if question:
        for row in _rows_at(ctx.snapshot.get("interviews"), ctx.cutoff, "answered_at"):
            if not row.get("spontaneous") or row.get("question_id") != question:
                continue
            if not _in_cohort(ctx, row.get("enrollment_pk")):
                continue
            if _in_days(ctx, row["answered_at"], ctx.measurement) and not _drops(ctx, "U5", _kyiv_date(row["answered_at"])):
                verbal.add(row["enrollment_pk"])
    qualifying = clickers | verbal
    detail = {"qualifying": len(qualifying), "clickers": len(clickers), "verbal": len(verbal)}
    if len(qualifying) >= ctx.thresholds["U5_pass_min_users"]:
        return _cell(PASS, PASS, **detail)
    if question is None:
        return _cell(MF, "U5_VERBAL_QUESTION_UNFROZEN", **detail)
    return _cell(NOT_PASS, NOT_PASS, **detail)


def _decision(metrics, params) -> dict:
    statuses = {code: metrics[code]["status"] for code in ("U4", "U1a", "U1b", "U2", "U3")}
    if any(status == MF for status in statuses.values()):
        return _cell(MF, "METRIC_MEASUREMENT_FAILURE")
    u4, u1a, u1b, u2, u3 = (statuses[c] for c in ("U4", "U1a", "U1b", "U2", "U3"))
    if u4 == FAIL:
        return _cell("STOP_DISTRIBUTION", "RULE_5")
    if u3 == PASS and any(s == PASS for s in (u1a, u1b, u2)):
        return _cell("CONTINUE", "RULE_1")
    value_pass = sum(s == PASS for s in (u1a, u1b, u2))
    if u3 != PASS and value_pass >= 2:
        direction = [name for name, status in (("U1a", u1a), ("U1b", u1b), ("U2", u2)) if status == PASS]
        scanner = metrics["U5"]["status"] == PASS
        return _cell("REPOSITION", "RULE_2", direction=direction, scanner_if_u5_pass=scanner)
    value_soft = all(s in (FAIL, INC) for s in (u1a, u1b, u2))
    if u4 == PASS and value_soft and u3 != PASS:
        shared = params.get("shared_missing_request")
        if shared is None:
            return _cell(MF, "SHARED_MISSING_REQUEST_UNFROZEN")
        if shared is True:
            return _cell("PIVOT", "RULE_3")
        if all(s == FAIL for s in (u1a, u1b, u2, u3)):
            return _cell("STOP_NO_VALUE", "RULE_4")
    return _cell(INC, "RULE_6")
