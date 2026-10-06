"""Owner usage report. Aggregates only; Telegram ids never leave this module.

Weeks are counted from the first external user's join (the owner is excluded).
Week 1 is the seven days that start at that join. A /btc open is unprompted
when no delivery (push, alert, brief, weekly) to the same user falls in the
10 minutes before it (`BETA_MEASUREMENT_CONTRACT_V1` §3; backlog F5, before
it 30 minutes and pushes and alerts only).

Implicit push metrics (backlog F5, `push_metrics`): per delivered message, how
many recipients pressed a button, did anything at all, or muted that type
within the same 10 minutes, and per type how long participants took to switch
it off. Read from the outbox (which message) and the activity rows (what
followed, with their `detail`).

The owner breakdown (backlog H6) uses the measurement contract's words instead:
the 10-minute window, every pull, delivery classes, known and unknown apart
(`BETA_MEASUREMENT_CONTRACT_V1` §2–§3). It is still an operational overview over
current rows, never the U1–U5 read (§0): no enrollment window, no Day 0, no
classification deadline.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from beta.i18n import KYIV

WEEK = timedelta(days=7)
PROMPT_WINDOW = timedelta(minutes=10)                     # BETA_MEASUREMENT_CONTRACT_V1 §3
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


DECISION_PULLS = ("cmd_catchup", "cmd_levels", "cmd_risk", "cmd_alert", "cmd_events", "cmd_accuracy",
                  "cmd_research", "btn_levels", "btn_risk")


def _window_block(rows: Sequence[dict], *, pushes_by_user: dict, stops: int, deletions: int) -> dict:
    active = _active_pks(rows)
    return {"active_users": len(active), **_btc_stats(rows, active, pushes_by_user),
            "tabs": _tab_counts(rows), "terms_opens": sum(1 for r in rows if r["action"] == "cmd_terms"),
            "pulls": {a: sum(1 for r in rows if r["action"] == a) for a in DECISION_PULLS},
            "alerts_delivered": sum(1 for r in rows if r["action"] == "alert_delivered"),
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


REACTION_WINDOW = timedelta(minutes=10)                  # BETA_MEASUREMENT_CONTRACT_V1 §3
# §2 pulls; /check stays a pull until the contract amendment fixes its class (scope decision §6.7)
PULL_ACTIONS = ("cmd_btc", "cmd_catchup", "cmd_levels", "cmd_risk", "cmd_events", "cmd_accuracy",
                "cmd_research", "cmd_history", "cmd_alert", "cmd_check")
DELIVERIES = ("push_delivered", "alert_delivered", "brief_delivered", "weekly_delivered")
# delivery type -> (activity action, its detail or None); `price` is the personal /alert
DELIVERY_TYPES = (("hour", "push_delivered", None), ("level", "alert_delivered", "level"),
                  ("event", "alert_delivered", "event"), ("move", "alert_delivered", "move"),
                  ("brief", "brief_delivered", None), ("weekly", "weekly_delivered", None),
                  ("price", "alert_delivered", "price"))
# delivery type -> (settings action, detail prefix): `/push levels off` is `cmd_push` `levels:off`
MUTES = {"hour": ("cmd_push", "hours:"), "level": ("cmd_push", "levels:"), "event": ("cmd_push", "events:"),
         "move": ("cmd_push", "moves:"), "brief": ("cmd_brief", ""), "weekly": ("cmd_push", "weekly:")}


def _kyiv_day(at: datetime):
    return _aware(at).astimezone(KYIV).date()


def _type_of(row: dict) -> Optional[str]:
    for name, action, detail in DELIVERY_TYPES:
        if row["action"] == action and (detail is None or row.get("detail") == detail):
            return name
    return None


def _follows(at: datetime, starts: Sequence[datetime]) -> bool:
    at = _aware(at)
    return any(timedelta(0) <= at - s <= REACTION_WINDOW for s in starts)


def _muted(rows: Sequence[dict], action: str, prefix: str) -> Optional[bool]:
    """The last on/off a participant chose for one type, from the settings history (None: never set)."""
    state = None
    for row in sorted(rows, key=lambda r: _aware(r["at"])):
        if row["action"] == action and row.get("detail") in (f"{prefix}on", f"{prefix}off"):
            state = row["detail"] == f"{prefix}off"
    return state


def _group_block(pks: set, activity: Sequence[dict], votes: Sequence[dict], *, start: datetime,
                 end: datetime) -> dict:
    """One group of participants in [start, end]; deliveries before `start` still prompt."""
    mine = [r for r in activity if r["user_pk"] in pks]
    by_user: dict = {}
    for row in mine:
        by_user.setdefault(row["user_pk"], []).append(row)
    inside = [r for r in mine if _aware(start) <= _aware(r["at"]) <= _aware(end)]
    organic = post_push = 0
    organic_days: dict = {}
    pulled_days: dict = {}
    for row in inside:
        if row["action"] not in PULL_ACTIONS:
            continue
        sent = [_aware(r["at"]) for r in by_user[row["user_pk"]] if r["action"] in DELIVERIES]
        day = _kyiv_day(row["at"])
        pulled_days.setdefault(row["user_pk"], set()).add(day)
        if _follows(row["at"], sent):
            post_push += 1
        else:
            organic += 1
            organic_days.setdefault(row["user_pk"], set()).add(day)
    check_days: dict = {}
    for row in inside:
        if row["action"] == "cmd_check":
            check_days.setdefault(row["user_pk"], set()).add(_kyiv_day(row["at"]))
    types = {}
    for name, _, _ in DELIVERY_TYPES:
        sent = [r for r in inside if _type_of(r) == name]
        reacted = 0
        for row in sent:
            buttons = [_aware(r["at"]) for r in by_user[row["user_pk"]]
                       if r["action"].startswith(("tab_", "btn_")) and _aware(r["at"]) >= _aware(row["at"])]
            reacted += any(b - _aware(row["at"]) <= REACTION_WINDOW for b in buttons)
        cast = [v for v in votes if v["user_pk"] in pks and v["kind"] == name
                and _aware(start) <= _aware(v["at"]) <= _aware(end)]
        block = {"delivered": len(sent), "reacted": reacted,
                 "useful": sum(1 for v in cast if v["vote"] == "USEFUL"),
                 "noise": sum(1 for v in cast if v["vote"] == "NOISE")}
        if name in MUTES:
            action, prefix = MUTES[name]
            block["mutes"] = sum(1 for r in inside if r["action"] == action and r.get("detail") == f"{prefix}off")
            block["muted_now"] = sum(1 for pk in pks if _muted(by_user.get(pk, ()), action, prefix))
        types[name] = block
    return {"users": len(pks),
            "pulls": {"organic": organic, "post_push": post_push},
            "organic_days": sum(len(d) for d in organic_days.values()),
            "post_push_only_days": sum(len(d - organic_days.get(pk, set())) for pk, d in pulled_days.items()),
            "returning_users": sum(1 for d in organic_days.values() if len(d) >= 2),
            "check": {"pulls": sum(1 for r in inside if r["action"] == "cmd_check"), "users": len(check_days),
                      "repeat_users": sum(1 for d in check_days.values() if len(d) >= 2),
                      "btn_check": sum(1 for r in inside if r["action"] == "btn_check"),
                      "btn_watch": sum(1 for r in inside if r["action"] == "btn_watch")},
            "types": types,
            "push_off_now": sum(1 for pk in pks if _muted(by_user.get(pk, ()), "cmd_push", ""))}


def owner_breakdown(users: Sequence[dict], activity: Sequence[dict], votes: Sequence[dict], *,
                    start: datetime, end: datetime) -> dict:
    """Backlog H6: organic versus post-push pulls, repeat /check and noise by type, known and
    unknown apart, and by trader type once onboarding records one (backlog E5)."""
    known = {u["user_pk"] for u in users if u.get("known_contact")}
    unknown = {u["user_pk"] for u in users} - known
    out = {"unknown": _group_block(unknown, activity, votes, start=start, end=end),
           "known": _group_block(known, activity, votes, start=start, end=end), "trader_types": None}
    if any(u.get("trader_type") for u in users):
        kinds = sorted({u.get("trader_type") or "none" for u in users})
        out["trader_types"] = {k: _group_block({u["user_pk"] for u in users if (u.get("trader_type") or "none") == k},
                                               activity, votes, start=start, end=end) for k in kinds}
    return out


# outbox kind -> delivery type of DELIVERY_TYPES (an alert's type is its own kind)
_OUTBOX_TYPE = {"push": "hour", "brief": "brief", "weekly": "weekly"}
_PUSH_TYPES = ("hour", "level", "event", "move")          # a global `/push off` mutes these too
PUSH_LIST_MAX = 20


def delivery_type(row: dict) -> Optional[str]:
    return row.get("alert_kind") if row["kind"] == "alert" else _OUTBOX_TYPE.get(row["kind"])


def _push_key(row: dict) -> str:
    ref = {"push": "decision_id", "alert": "alert_pk", "brief": "brief_date", "weekly": "weekly_pk"}[row["kind"]]
    return f"{row['kind']}:{row.get(ref)}"


def _mute_rows(rows: Sequence[dict], kind: str) -> list:
    """Times a participant switched `kind` off: its own setting, or `/push off` for a push type."""
    out = []
    action, prefix = MUTES.get(kind, (None, None))
    for r in rows:
        own = action is not None and r["action"] == action and r.get("detail") == f"{prefix}off"
        everything = kind in _PUSH_TYPES and r["action"] == "cmd_push" and r.get("detail") == "off"
        if own or everything:
            out.append(_aware(r["at"]))
    return sorted(out)


def _any_in(times: Sequence[datetime], at: datetime) -> bool:
    """A time in [at, at + REACTION_WINDOW] in a sorted list."""
    i = bisect_left(times, at)
    return i < len(times) and times[i] <= at + REACTION_WINDOW


def push_metrics(activity: Sequence[dict], deliveries: Sequence[dict], *, start: datetime, end: datetime) -> dict:
    """Implicit metrics per delivered message (backlog F5), the contract's 10-minute window:
    `button` a tab or button, `action` any recorded action (pull, button, setting), `muted` that
    type switched off, each by the same participant. `disable` per type: participants who switched
    it off after receiving it, the median hours from their first one to the switch and the median
    number they had received by then. The newest `PUSH_LIST_MAX` messages are listed."""
    by_user: dict = {}
    for r in activity:
        if r["action"] not in DELIVERIES and r["action"] != "brief_withheld":
            by_user.setdefault(r["user_pk"], []).append(r)
    buttons = {pk: sorted(_aware(r["at"]) for r in rows if r["action"].startswith(("tab_", "btn_")))
               for pk, rows in by_user.items()}
    actions = {pk: sorted(_aware(r["at"]) for r in rows) for pk, rows in by_user.items()}
    mutes = {}

    def muted_at(pk, kind):
        if (pk, kind) not in mutes:
            mutes[(pk, kind)] = _mute_rows(by_user.get(pk, ()), kind)
        return mutes[(pk, kind)]

    pushes: dict = {}
    firsts: dict = {}
    for d in deliveries:
        kind, at = delivery_type(d), _aware(d["at"])
        if kind is None or d.get("user_pk") is None:
            continue
        pk = d["user_pk"]
        firsts.setdefault((pk, kind), []).append(at)
        if not (_aware(start) <= at <= _aware(end)):
            continue
        p = pushes.setdefault(_push_key(d), {"type": kind, "at": at, "delivered": 0, "button": 0, "action": 0,
                                              "muted": 0})
        p["at"] = min(p["at"], at)
        p["delivered"] += 1
        p["button"] += _any_in(buttons.get(pk, ()), at)
        p["action"] += _any_in(actions.get(pk, ()), at)
        p["muted"] += _any_in(muted_at(pk, kind), at)
    types: dict = {}
    for p in pushes.values():
        t = types.setdefault(p["type"], {"messages": 0, "delivered": 0, "button": 0, "action": 0, "muted": 0})
        t["messages"] += 1
        for k in ("delivered", "button", "action", "muted"):
            t[k] += p[k]
    disable: dict = {}
    for (pk, kind), times in firsts.items():
        times.sort()
        offs = [m for m in muted_at(pk, kind) if m >= times[0] and _aware(start) <= m <= _aware(end)]
        if not offs:
            continue
        d = disable.setdefault(kind, {"hours": [], "received": []})
        d["hours"].append((offs[0] - times[0]).total_seconds() / 3600.0)
        d["received"].append(bisect_right(times, offs[0]))
    listed = sorted(pushes.values(), key=lambda p: p["at"], reverse=True)[:PUSH_LIST_MAX]
    return {"window_min": int(REACTION_WINDOW.total_seconds() // 60), "types": types,
            "pushes": listed,
            "disable": {k: {"n": len(v["hours"]), "median_h": _median(v["hours"]),
                            "received_median": _median(v["received"])} for k, v in disable.items()}}


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
        # every delivery prompts an open: a push, a market or personal alert, the brief, the weekly report
        if row["action"] in DELIVERIES:
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
    votes = [dict(v) for v in facts.get("votes", ()) if v["user_pk"] in external_pks]
    return {
        "generated_at": now,
        "first_external_join": origin,
        "last_7_days": {
            **_window_block(last_rows, pushes_by_user=pushes, stops=_stops(last_rows),
                            deletions=_deletions(last_start, now, inclusive_end=True)),
            "joins_by_invite": _invite_block(last_users, last_rows, facts["invites"]),
            "owner_breakdown": owner_breakdown(users, activity, votes, start=last_start, end=now),
            "push_metrics": push_metrics(activity, [d for d in facts.get("deliveries", ())
                                                    if d["user_pk"] in external_pks],
                                         start=last_start, end=now),
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
            "owner_breakdown": (owner_breakdown(users, activity, votes, start=origin, end=now)
                                if origin is not None else None),
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


def _breakdown_lines(name: str, block: dict) -> list:
    pulls = block["pulls"]
    chk = block["check"]
    lines = [f"  {name} ({block['users']} users): pulls organic {pulls['organic']}, post-push {pulls['post_push']}"
             f" · organic days {block['organic_days']}, post-push-only days {block['post_push_only_days']}"
             f" · returning {block['returning_users']}",
             f"    /check {chk['pulls']} by {chk['users']}, repeat {chk['repeat_users']}"
             f" · check button {chk['btn_check']} · watch button {chk['btn_watch']}"
             f" · push off now {block['push_off_now']}"]
    for kind, row in block["types"].items():
        parts = [f"sent {row['delivered']}", f"reacted {row['reacted']}",
                 f"useful {row['useful']}", f"noise {row['noise']}"]
        if "mutes" in row:
            parts.append(f"muted {row['mutes']} (now {row['muted_now']})")
        lines.append(f"    {kind}: " + ", ".join(parts))
    return lines


def _breakdown(title: str, data: Optional[dict]) -> list:
    if data is None:
        return []
    lines = [title]
    for name in ("unknown", "known"):
        lines += _breakdown_lines(name, data[name])
    if data["trader_types"] is None:
        lines.append("  trader type: not recorded")
    else:
        for kind, block in data["trader_types"].items():
            lines += _breakdown_lines(f"trader {kind}", block)
    return lines


def _push_metric_lines(m: Optional[dict]) -> list:
    if m is None:
        return []
    w = m["window_min"]
    lines = [f"pushes, last 7 days ({w}-min window: button / any action / muted that type)"]
    if not m["pushes"]:
        return lines + ["  none delivered"]
    for kind, t in sorted(m["types"].items()):
        lines.append(f"  {kind}: {t['messages']} messages, sent {t['delivered']} · button {t['button']}"
                     f" · action {t['action']} · muted {t['muted']}")
    for p in m["pushes"]:
        lines.append(f"  {p['type']} {_aware(p['at']).strftime('%m-%d %H:%M')} UTC: sent {p['delivered']}"
                     f" · button {p['button']} · action {p['action']} · muted {p['muted']}")
    for kind, d in sorted(m["disable"].items()):
        lines.append(f"  time to disable {kind}: N={d['n']} median {_num(round(d['median_h'], 1))} h after the first"
                     f" (median {_num(d['received_median'])} received)")
    return lines


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
    lines += _push_metric_lines(report["last_7_days"].get("push_metrics"))
    lines.append("owner breakdown (10-min window, all pulls; operational, not U1-U5)")
    lines += _breakdown("last 7 days", report["last_7_days"].get("owner_breakdown"))
    lines += _breakdown("since first external user", report["since_first_external"].get("owner_breakdown"))
    return "\n".join(lines)
