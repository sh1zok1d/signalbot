"""Owner usage report. Aggregates only; Telegram ids never leave this module.

Weeks are counted from the first external user's join (the owner is excluded).
Week 1 is the seven days that start at that join. A /btc open is unprompted
when no push_delivered for the same user falls in the 30 minutes before it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

WEEK = timedelta(days=7)
PROMPT_WINDOW = timedelta(minutes=30)
RETENTION_DAYS = (1, 7, 14, 28)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _median(values: Sequence[int]):
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _week_index(origin: datetime, at: datetime) -> Optional[int]:
    delta = _aware(at) - _aware(origin)
    if delta.total_seconds() < 0:
        return None
    return int(delta.total_seconds() // WEEK.total_seconds()) + 1


def _in_window(at: datetime, start: datetime, end: datetime) -> bool:
    at = _aware(at)
    return _aware(start) <= at < _aware(end)


def _unprompted(btc_at: datetime, pushes: Sequence[datetime]) -> bool:
    btc_at = _aware(btc_at)
    for pushed in pushes:
        delta = btc_at - _aware(pushed)
        if timedelta(0) <= delta <= PROMPT_WINDOW:
            return False
    return True


def _slice(activity: Sequence[dict], start: Optional[datetime], end: datetime) -> list:
    if start is None:
        return []
    return [row for row in activity if _in_window(row["at"], start, end)]


def _btc_stats(rows: Sequence[dict], active_pks: Sequence[int], pushes_by_user: dict) -> dict:
    counts = []
    unprompted = 0
    post_push = 0
    for pk in active_pks:
        opens = [r["at"] for r in rows if r["user_pk"] == pk and r["action"] == "cmd_btc"]
        counts.append(len(opens))
        for at in opens:
            if _unprompted(at, pushes_by_user.get(pk, ())):
                unprompted += 1
            else:
                post_push += 1
    return {"btc_per_active_median": _median(counts), "btc_per_active_max": max(counts) if counts else None,
            "unprompted_btc": unprompted, "post_push_btc": post_push}


def _tab_counts(rows: Sequence[dict]) -> dict:
    return {tab: sum(1 for r in rows if r["action"] == tab) for tab in ("tab_event", "tab_1h", "tab_24h")}


def _active_pks(rows: Sequence[dict]) -> list:
    return sorted({r["user_pk"] for r in rows})


def _window_block(rows: Sequence[dict], *, pushes_by_user: dict, stops: int, deletions: int) -> dict:
    active = _active_pks(rows)
    return {"active_users": len(active), **_btc_stats(rows, active, pushes_by_user),
            "tabs": _tab_counts(rows), "terms_opens": sum(1 for r in rows if r["action"] == "cmd_terms"),
            "stops": stops, "deletions": deletions}


def _retention(users: Sequence[dict], activity: Sequence[dict], now: datetime) -> dict:
    now = _aware(now)
    by_user: dict = {}
    for row in activity:
        by_user.setdefault(row["user_pk"], []).append(_aware(row["at"]))
    out = {}
    for day in RETENTION_DAYS:
        eligible = 0
        active = 0
        for user in users:
            joined = _aware(user["joined_at"])
            if joined + timedelta(days=day) > now:
                continue
            eligible += 1
            start = joined + timedelta(days=day - 1)
            end = joined + timedelta(days=day)
            if any(start <= at < end for at in by_user.get(user["user_pk"], ())):
                active += 1
        out[f"day_{day}"] = {"active": active, "eligible": eligible,
                             "share": None if eligible == 0 else active / eligible}
    return out


def _invite_block(users: Sequence[dict], activity: Sequence[dict], invites: Sequence[dict]) -> list:
    labels = {row["code"]: row["label"] for row in invites}
    grouped: dict = {}
    for user in users:
        code = user.get("invite_code")
        label = labels.get(code, "direct")
        bucket = grouped.setdefault(label, {"joins": 0, "active_users": 0, "pks": set()})
        bucket["joins"] += 1
        bucket["pks"].add(user["user_pk"])
    acted = {row["user_pk"] for row in activity}
    result = []
    for label in sorted(grouped):
        bucket = grouped[label]
        result.append({"label": label, "joins": bucket["joins"],
                       "active_users": len(bucket["pks"] & acted)})
    return result


def build_usage_report(facts: dict, *, now: datetime, owner_user_id: Optional[int]) -> dict:
    """Build the owner report. `facts` may contain Telegram ids; the result does not."""
    from beta.admin import fingerprint
    now = _aware(now)
    owner = None if owner_user_id is None else int(owner_user_id)
    users = [dict(u) for u in facts["users"] if owner is None or int(u["telegram_user_id"]) != owner]
    external_pks = {u["user_pk"] for u in users}
    activity = [dict(r) for r in facts["activity"] if r["user_pk"] in external_pks]
    pushes: dict = {}
    for row in activity:
        if row["action"] == "push_delivered":
            pushes.setdefault(row["user_pk"], []).append(_aware(row["at"]))
    origin = min((_aware(u["joined_at"]) for u in users), default=None)
    fp_of = {u["user_pk"]: fingerprint(int(u["telegram_user_id"])) for u in users}
    last_start = now - timedelta(days=7)
    # last-7-days is inclusive of `now`
    last_rows = [r for r in activity if last_start <= _aware(r["at"]) <= now]
    since_rows = [r for r in activity if origin is not None and _aware(r["at"]) >= origin and _aware(r["at"]) <= now]

    def _stops(rows):
        return sum(1 for r in rows if r["action"] == "cmd_stop")

    def _deletions(start, end, *, inclusive_end=False):
        n = 0
        for at in facts["deletions"]:
            at = _aware(at)
            if start is None:
                continue
            if inclusive_end:
                if start <= at <= end:
                    n += 1
            elif start <= at < end:
                n += 1
        return n

    weeks = []
    both = []
    if origin is not None:
        current = _week_index(origin, now) or 1
        week_pks = {}
        for index in range(1, current + 1):
            start = origin + WEEK * (index - 1)
            end = start + WEEK
            rows = _slice(activity, start, end)
            # an action exactly at the next boundary belongs to the next week
            active = _active_pks(rows)
            week_pks[index] = set(active)
            block = _window_block(rows, pushes_by_user=pushes, stops=_stops(rows), deletions=0)
            weeks.append({"week": index, "start": start, "end": end, **block,
                          "fingerprints": sorted(fp_of[pk] for pk in active)})
        both_pks = week_pks.get(3, set()) & week_pks.get(4, set())
        both = sorted(fp_of[pk] for pk in both_pks)
    lang = {"ru": 0, "en": 0}
    for user in users:
        lang[user.get("lang") or "ru"] = lang.get(user.get("lang") or "ru", 0) + 1
    rejected = []
    hash_days = {row["utc_day"]: int(row["n"]) for row in facts["rejected_hashes"]}
    count_days = {row["utc_day"]: int(row["attempt_count"]) for row in facts["rejected_counts"]}
    for day in sorted(set(hash_days) | set(count_days)):
        rejected.append({"utc_day": day, "distinct_hashes": hash_days.get(day),
                         "unsalted_count": count_days.get(day)})
    since_users = [u for u in users if origin is not None and _aware(u["joined_at"]) >= origin]
    last_users = [u for u in users if last_start <= _aware(u["joined_at"]) <= now]
    return {
        "generated_at": now,
        "first_external_join": origin,
        "last_7_days": {
            **_window_block(last_rows, pushes_by_user=pushes, stops=_stops(last_rows),
                            deletions=_deletions(last_start, now, inclusive_end=True)),
            "joins_by_invite": _invite_block(last_users, last_rows, facts["invites"]),
        },
        "since_first_external": {
            "active_users": len(_active_pks(since_rows)),
            "weeks": weeks,
            "weeks_3_active": next((w["active_users"] for w in weeks if w["week"] == 3), 0),
            "weeks_4_active": next((w["active_users"] for w in weeks if w["week"] == 4), 0),
            "weeks_3_and_4_active": len(both),
            "weeks_3_and_4_fingerprints": both,
            "tabs": _tab_counts(since_rows),
            "terms_opens": sum(1 for r in since_rows if r["action"] == "cmd_terms"),
            "stops": _stops(since_rows),
            "deletions": _deletions(origin, now + timedelta(microseconds=1), inclusive_end=True) if origin else 0,
            **_btc_stats(since_rows, _active_pks(since_rows), pushes),
            "joins_by_invite": _invite_block(since_users, since_rows, facts["invites"]),
        },
        "retention": _retention(users, activity, now),
        "language_split": lang,
        "waitlist_size": int(facts["waitlist_size"]),
        "rejected_starts_by_day": rejected,
    }


def _num(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _share(block: dict) -> str:
    if not block["eligible"]:
        return "n/a"
    return f"{block['active']}/{block['eligible']}"


def _tabs(tabs: dict) -> str:
    return f"event {tabs['tab_event']}, 1h {tabs['tab_1h']}, 24h {tabs['tab_24h']}"


def _invites(rows: Sequence[dict]) -> str:
    if not rows:
        return "none"
    return "; ".join(f"{r['label']}: joins {r['joins']}, active {r['active_users']}" for r in rows)


def format_usage_report(report: dict) -> str:
    """Plain text for /admin_stats. No Telegram ids."""
    last = report["last_7_days"]
    since = report["since_first_external"]
    origin = report["first_external_join"]
    origin_s = "none" if origin is None else _aware(origin).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "usage",
        "last 7 days",
        f"  active users: {last['active_users']}",
        f"  /btc per active user: median {_num(last['btc_per_active_median'])} max {_num(last['btc_per_active_max'])}",
        f"  unprompted /btc: {last['unprompted_btc']}",
        f"  post-push /btc: {last['post_push_btc']}",
        f"  tabs: {_tabs(last['tabs'])}",
        f"  /terms: {last['terms_opens']}",
        f"  stops: {last['stops']}",
        f"  deletions: {last['deletions']}",
        f"  invites: {_invites(last['joins_by_invite'])}",
        f"since first external user: {origin_s}",
        f"  active users: {since['active_users']}",
        f"  /btc per active user: median {_num(since['btc_per_active_median'])} max {_num(since['btc_per_active_max'])}",
        f"  unprompted /btc: {since['unprompted_btc']}",
        f"  post-push /btc: {since['post_push_btc']}",
        f"  tabs: {_tabs(since['tabs'])}",
        f"  /terms: {since['terms_opens']}",
        f"  stops: {since['stops']}",
        f"  deletions: {since['deletions']}",
        f"  invites: {_invites(since['joins_by_invite'])}",
        f"  week 3 active: {since['weeks_3_active']}",
        f"  week 4 active: {since['weeks_4_active']}",
        f"  weeks 3-4 both active: {since['weeks_3_and_4_active']}",
        "  weeks 3-4 fingerprints: " + (" ".join(since["weeks_3_and_4_fingerprints"]) or "none"),
    ]
    for week in since["weeks"]:
        lines.append(
            f"  week {week['week']} {_aware(week['start']).date().isoformat()}/{_aware(week['end']).date().isoformat()}"
            f" active {week['active_users']}"
            f" btc_median {_num(week['btc_per_active_median'])} btc_max {_num(week['btc_per_active_max'])}"
            f" unprompted {week['unprompted_btc']} post_push {week['post_push_btc']}"
        )
    ret = report["retention"]
    lines.append(
        "retention: " + " · ".join(f"d{day} {_share(ret[f'day_{day}'])}" for day in RETENTION_DAYS)
    )
    lang = report["language_split"]
    lines.append(f"language: ru {lang.get('ru', 0)}, en {lang.get('en', 0)}")
    lines.append(f"waitlist: {report['waitlist_size']}")
    if report["rejected_starts_by_day"]:
        for row in report["rejected_starts_by_day"]:
            day = row["utc_day"].isoformat() if hasattr(row["utc_day"], "isoformat") else str(row["utc_day"])
            parts = [f"rejected {day}"]
            if row["distinct_hashes"] is not None:
                parts.append(f"distinct {row['distinct_hashes']}")
            if row["unsalted_count"] is not None:
                parts.append(f"unsalted {row['unsalted_count']}")
            lines.append("  " + " ".join(parts))
    else:
        lines.append("  rejected: none")
    return "\n".join(lines)
