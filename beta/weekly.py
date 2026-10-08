"""Weekly report (backlog B4; PRE_BETA_SCOPE_DECISION_V1 block B and §6.4).

How the bot's own estimates did over the last seven days: the corridors that matured
(share inside with its effective N, beside the designed share and the held-out year;
width; misses above and below), the touch chances the claim journal scored («говорили →
было» per probability bin, shown at effective N ≥ MIN_N_SHOWN), and how many market
messages went out.

- **One payload per week.** It is built once at the slot, stored append-only in
  `beta_weekly_reports` before any send, and rendered per language from the stored payload.
- **A push type of its own.** Outbox kind `weekly`, `/push weekly off`, activity
  `weekly_delivered`. The measurement contract counts it as a delivery (it opens the
  prompted window of U1b); its class is a contract amendment (decision §6.7).
- **Owner version.** The same text plus the operational breakdown of `/admin_stats`
  (backlog H6) and the journal's weekly counts, sent to the owner once per report.
- **Schedule.** `decision.weekly_report`: Sunday evening Kyiv by default, outside the U1a
  withdrawal weekdays (Mon–Fri) on the Kyiv clock. A participant whose night it is then gets it when
  their quiet hours end (review of #373); east of about UTC+5 that is their Monday morning, which may
  be a U1a withdrawal day on their clock (the measurement contract, X5, records it).
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone
from statistics import median
from typing import Any, Mapping, Optional, Sequence

from .config import WEEKDAYS, BetaConfig
from .i18n import KYIV, assert_descriptive, t

WEEKLY_VERSION = "BETA_WEEKLY_V1"
WEEK = timedelta(days=7)
HORIZONS = ("1h", "4h", "24h")
_H_S = {"1h": 3600, "4h": 14400, "24h": 86400}


def weekly_slot(now: datetime, weekday: str, time_kyiv: str):
    """(Kyiv date, UTC instant) of this week's slot once it has passed on its weekday, else None."""
    local = now.astimezone(KYIV)
    if local.weekday() != WEEKDAYS.index(weekday):
        return None
    slot = datetime.combine(local.date(), dtime(int(time_kyiv[:2]), int(time_kyiv[3:])), tzinfo=KYIV)
    if local < slot:
        return None
    return local.date(), slot.astimezone(timezone.utc)


def week_corridors(rows: Sequence[Mapping[str, Any]], *, start: datetime, end: datetime) -> dict:
    """Corridors issued in [start, end) and scored by `end`, by horizon. Pure."""
    out: dict = {}
    for h in HORIZONS:
        sel = [r for r in rows if r["horizon"] == h and start <= r["issued_at"] < end]
        if not sel:
            continue
        n = len(sel)
        up = [(r["realized_high"] / r["upper"] - 1) * 100 for r in sel
              if r["realized_high"] is not None and r["realized_high"] > r["upper"]]
        dn = [(1 - r["realized_low"] / r["lower"]) * 100 for r in sel
              if r["realized_low"] is not None and r["realized_low"] < r["lower"]]
        out[h] = {"n": n, "n_eff": len({int(r["issued_at"].timestamp()) // _H_S[h] for r in sel}),
                  "inside": sum(1 for r in sel if r["outcome"] == "INSIDE") / n,
                  "half_width_pct": sum((r["upper"] - r["lower"]) / 2 / r["anchor_price"] * 100 for r in sel) / n,
                  "miss_up": {"share": len(up) / n, "median_pct": median(up) if up else None},
                  "miss_down": {"share": len(dn) / n, "median_pct": median(dn) if dn else None}}
    return out


def week_touch(cells: Sequence[Mapping[str, Any]]) -> dict:
    """The scored L3 touch claims of the week per horizon and probability bin (the live calibration's
    own pooling, `claims.live_touch_bins`), without its interval."""
    from .claims import live_touch_bins
    return {h: [{k: b[k] for k in ("bin", "n", "n_eff", "predicted", "realized")}
                for b in live_touch_bins(cells, h, reps=1)] for h in HORIZONS}


async def build_weekly(conn, *, now: datetime) -> dict:
    """The payload of the week that ends at `now`. Everything in it was known at `now`."""
    from .claims import touch_classes
    from .decision import latest_stats
    from .rangecast import COVERAGE
    from .state_tape import iso
    start = now - WEEK
    model = ((await latest_stats(conn, now=now)) or {}).get("range_model") or {}
    cal = model.get("calibration") or {}
    rows = await conn.forecast_rows(since=start)
    cells = await conn.touch_claim_cells(since=start, classes=[c for h in HORIZONS for c in touch_classes(h)])
    return {"version": WEEKLY_VERSION, "from": iso(start), "to": iso(now),
            "coverage": model.get("coverage") or COVERAGE,
            "holdout": {h: (cal.get(h) or {}).get("coverage_realized") for h in HORIZONS},
            "corridors": week_corridors(rows, start=start, end=now),
            "touch": week_touch(cells),
            "alerts": await conn.market_alert_counts(since=start, until=now)}


def format_weekly(payload: Mapping[str, Any], lang: str) -> str:
    """The user text of one stored payload."""
    from .decision_format import MIN_N_SHOWN, _hz, _pct, fmt_share
    from .i18n import local, na
    d0 = local(datetime.fromisoformat(payload["from"]))           # the recipient's dates (C5)
    d1 = local(datetime.fromisoformat(payload["to"]))
    lines = [t(lang, "wk_title", d0=d0.strftime("%d.%m"), d1=d1.strftime("%d.%m")), t(lang, "wk_intro"),
             t(lang, "wk_cor_head", share=fmt_share(payload.get("coverage"), lang))]
    cors = payload.get("corridors") or {}
    for h in HORIZONS:
        rec = cors.get(h)
        if not rec:
            continue
        if rec["n_eff"] < MIN_N_SHOWN:
            lines.append(t(lang, "wk_cor_short", h=_hz(h, lang), n=rec["n_eff"]))
            continue
        lines.append(t(lang, "wk_cor_line", h=_hz(h, lang), p=fmt_share(rec["inside"], lang), n=rec["n_eff"],
                       hold=fmt_share((payload.get("holdout") or {}).get(h), lang),
                       width=_pct(rec["half_width_pct"], lang, 2)))
        mu, md = rec["miss_up"], rec["miss_down"]
        lines.append(t(lang, "wk_miss_line", up=fmt_share(mu["share"], lang), dn=fmt_share(md["share"], lang),
                       up_size=_pct(mu["median_pct"], lang, 2) if mu["median_pct"] is not None else na(lang),
                       dn_size=_pct(md["median_pct"], lang, 2) if md["median_pct"] is not None else na(lang)))
    if not cors:
        lines.append(t(lang, "wk_cor_none"))
    touch = payload.get("touch") or {}
    if any(touch.get(h) for h in HORIZONS):
        lines.append(t(lang, "wk_touch_head"))
        for h in HORIZONS:
            bins = touch.get(h) or []
            if not bins:
                continue
            shown = [b for b in bins if b["n_eff"] >= MIN_N_SHOWN]
            if not shown:
                lines.append(t(lang, "wk_touch_short", h=_hz(h, lang), n=max(b["n_eff"] for b in bins)))
                continue
            parts = " · ".join(t(lang, "ac_touch_part", p=fmt_share(b["predicted"], lang),
                                 r=fmt_share(b["realized"], lang), n=b["n_eff"]) for b in shown)
            lines.append(t(lang, "wk_touch_line", h=_hz(h, lang), parts=parts))
    al = payload.get("alerts") or {}
    lines.append(t(lang, "wk_alerts", level=al.get("level", 0), event=al.get("event", 0), move=al.get("move", 0)))
    lines.append(t(lang, "wk_footer"))
    return assert_descriptive("\n".join(lines), lang)


def format_weekly_owner(payload: Mapping[str, Any], *, breakdown: Optional[Mapping[str, Any]],
                        journal: Mapping[str, Any]) -> str:
    """Owner plain text: the operational breakdown of the same seven days and the journal's counts."""
    from .usage import _breakdown
    lines = [f"weekly report {payload['from'][:10]} .. {payload['to'][:10]} (owner part)"]
    lines += _breakdown("participants, last 7 days (10-min window; operational, not U1-U5)", breakdown)
    classes = (journal or {}).get("classes") or {}
    lines.append("claim journal, last 7 days: " + ("none" if not classes else ""))
    for cls, rec in classes.items():
        lines.append(f"  {cls}: written {rec.get('n', 0)}, scored {rec.get('scored', 0)}")
    return "\n".join(lines)


async def run_due_weekly(conn, cfg: BetaConfig, *, sender, clock, push_on: bool,
                         owner_user_id: Optional[int] = None, pacer=None) -> dict:
    """The weekly report inside the notifier cycle and the outbox, as the briefing: at most one send
    attempt per row, expired after `max_delay_min`, suppressed while messages are off."""
    from .delivery import SENT, SendPacer, count_outcome, send_one
    from .state_tape import sha256_json
    from .models import (D_EXPIRED, D_FAILED, D_PENDING, D_SUPPRESSED, DELIVERY_TOO_OLD, PUSH_DISABLED,
                         USER_INACTIVE)
    w = cfg.section("decision")["weekly_report"]
    out = {"built": False, "scheduled": 0, "sent": 0, "failed": 0, "unknown": 0, "throttled": 0, "expired": 0,
           "suppressed": 0}
    pacer = pacer if pacer is not None else SendPacer()
    max_delay = timedelta(minutes=int(w["max_delay_min"]))
    now = clock()
    slot = weekly_slot(now, w["weekday_kyiv"], w["time_kyiv"])
    if w["enabled"] and push_on and slot is not None and now - slot[1] <= max_delay:
        if await conn.weekly_report_pk(slot[0]) is None:
            payload = await build_weekly(conn, now=now)            # what is known now, nothing after it
            pk = await conn.insert_weekly_report(week_end=slot[0], built_at=now, payload=payload,
                                                 payload_digest=sha256_json(payload))
            if pk is not None:
                out["built"] = True
                out["scheduled"] = await conn.materialize_weekly_deliveries(weekly_pk=pk, decision_ts=slot[1])
        if sender is not None and owner_user_id is not None:
            out["owner"] = await _send_owner(conn, sender, pacer, slot[0], owner_user_id=int(owner_user_id),
                                             now=now)
    for row in await conn.fetch_pending_weekly_deliveries(cfg["notifications"]["max_deliveries_per_run"],
                                                          now=clock()):
        now = clock()
        did = row["delivery_id"]
        from .detector import quiet_end
        # the participant's night: the report waits for its end, and its delay counts from there
        due = quiet_end(cfg, row["decision_ts"], row.get("user_tz")) or row["decision_ts"]
        if now < due:
            continue
        if now - due > max_delay:
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_EXPIRED, now=now,
                                           suppression_reason=DELIVERY_TOO_OLD)
            out["expired"] += 1
            continue
        if not (w["enabled"] and push_on):
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason=PUSH_DISABLED)
            out["suppressed"] += 1
            continue
        if row["user_status"] != "ACTIVE" or not (row.get("push_enabled", True) and row.get("push_weekly", True)):
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason=USER_INACTIVE)
            out["suppressed"] += 1
            continue
        if sender is None:
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_FAILED, now=now,
                                           error_summary="sender unavailable (no bot token)")
            out["failed"] += 1
            continue
        if not pacer.may_send(row["chat_id"]):          # nothing is rendered for a row that waits
            pacer.deferred += 1
            continue
        lang = row.get("user_lang") or "ru"
        from .i18n import render_tz
        with render_tz(row.get("user_tz")):
            text = format_weekly(row["payload"], lang)
        from .formatter import mute_row, vote_row
        outcome, _mid, sent_at = await send_one(conn, sender, pacer, did, chat_id=row["chat_id"], html=text,
                                                buttons=[vote_row("weekly", row["weekly_pk"], lang),
                                                         mute_row("weekly", lang)], clock=clock)
        if outcome != SENT:
            count_outcome(out, outcome)
            continue
        if row.get("user_pk") is not None:
            await conn.record_activity(user_pk=row["user_pk"], action="weekly_delivered", lang=lang, at=sent_at)
        out["sent"] += 1
    return out


OWNER_COPY = "weekly_owner"


async def _send_owner(conn, sender, pacer, week_end, *, owner_user_id: int, now: datetime) -> Optional[str]:
    """The owner version, under the run's pacer (A5 review): its parts go one by one, and a run
    that cannot send them all (pacer closed, flood control) leaves the rest to the next run within
    the report's sending window; the parts already sent are kept in the `weekly_owner` health row,
    so none is sent twice. An ambiguous part (Telegram may have delivered it) counts as sent and is
    never resent; a refused part ends the copy for this week (review of #345). None when it was
    already sent or ended."""
    import html
    from .admin import owner_parts
    from .claims import claims_report
    from .delivery import REJECTED, SENT, UNKNOWN, send_direct
    from .usage import as_setting, owner_breakdown
    rec = ((await conn.fetch_health([OWNER_COPY])).get(OWNER_COPY) or {}).get("detail") or {}
    done = int(rec.get("parts_sent") or 0) if rec.get("week_end") == week_end.isoformat() else 0
    if rec.get("week_end") == week_end.isoformat() and rec.get("done"):
        return None
    try:
        payload = await conn.weekly_report_payload(week_end)
        start, end = datetime.fromisoformat(payload["from"]), datetime.fromisoformat(payload["to"])
        facts = await conn.usage_facts()
        owner = int(owner_user_id)
        users = [u for u in facts["users"] if int(u["telegram_user_id"]) != owner]
        pks = {u["user_pk"] for u in users}
        # a one-tap mute counts as the setting it is, as on /admin_stats (review of #375)
        breakdown = owner_breakdown(users, [as_setting(dict(r)) for r in facts["activity"] if r["user_pk"] in pks],
                                    [v for v in facts.get("votes", ()) if v["user_pk"] in pks], start=start, end=end)
        journal = claims_report(await conn.fetch_claim_cohort(since=start))
        parts = [format_weekly(payload, "ru")] + [f"<pre>{html.escape(part, quote=False)}</pre>" for part in
                                                  owner_parts(format_weekly_owner(payload, breakdown=breakdown,
                                                                                  journal=journal))]
    except Exception as exc:  # noqa: BLE001 - the owner copy never blocks the participants' rows
        return f"error: {type(exc).__name__}"
    result, rejected = "sent", False
    for part in parts[done:]:
        res = await send_direct(sender, pacer, chat_id=owner, html=part)
        if res in (SENT, UNKNOWN):
            done += 1
            if res == UNKNOWN:
                result = "unknown"
            continue
        result, rejected = res.lower(), res == REJECTED
        break
    complete = done == len(parts)
    await conn.record_health(OWNER_COPY, now=now, success=complete, error_type=None if complete else result,
                             detail={"week_end": week_end.isoformat(), "parts_sent": done, "parts": len(parts),
                                     "done": complete or rejected, "rejected": rejected})
    return result
