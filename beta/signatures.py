"""Owner-only signature index `/hypotheses` (PRE_BETA_SCOPE_DECISION_V1 §7; backlog K).

Research-supporting tooling, not a product feature: no participant ever sees it.

- **Signature.** The signature of a closed 5m bucket is a tuple of states the code already computes:
  - the 1h and 4h interpretation labels (`interpretation.interpret`);
  - the 1h and 4h range and volume bands (`context.level_label`);
  - the unusual-hour gate (`hour_gate.evaluate_hour`, with the bucket's own liquidation votes);
  - the D7 state of the last completed hour;
  - the liquidation-stress votes of the bucket (`rule_evaluations`);
  - the research evidence matches (`research_evidence`, the newest bucket only);
  - the C1 day type.

  There is no new threshold and no new detector (PRODUCT_DECISION_V2 §3). A state that could not be
  read is «?», never a guess.
- **Episodes.** Identical consecutive signatures (no gap) are one episode. The bucket rows are
  append-only, and an episode is the run that starts at a row marked `episode_start`.
- **NEW.** A signature is flagged NEW when it has at least 2 tail (non-neutral) states, at least 3
  separate episodes and at least 2 distinct UTC days. Its empirical frequency is shown beside it. There
  is no surprise ratio against independence: the states are dependent, so such a ratio inflates on
  known structure.
- **Blind review.** The owner decides «в research» or «отклонить» seeing only the signature, its
  frequency, episodes and days, never what followed. The hypothesis text and the generating window are
  frozen at that moment in the append-only `beta_hypothesis_reviews`, the bot-side exposure ledger.
  `--beta-hypotheses-export` prints it for a reviewed change of the atlas exposure ledger. Historical
  counts are read only after «в research», outside the bot. A historical check is discovery;
  replication is live and forward.
- **`/pin`.** It marks the current state by hand.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

logger = logging.getLogger("beta.signatures")

SIGNATURE_VERSION = "BETA_SIGNATURES_V1"
COMPONENTS = ("i1h", "i4h", "r1h", "v1h", "r4h", "v4h", "gate", "d7", "liq", "ev", "day")
UNKNOWN = "?"
NEW_MIN_TAIL, NEW_MIN_EPISODES, NEW_MIN_DAYS = 2, 3, 2       # §7, fixed
MAX_BUCKETS_PER_RUN = 288                                     # a day of catch-up after downtime
FIRST_RUN_BACK = timedelta(minutes=5)                         # the index starts at the newest bucket
EVIDENCE_MAX_AGE = timedelta(minutes=10)
BUCKET = timedelta(minutes=5)
_UNREADABLE_KEYS = ("venues_diverge", "insufficient", "missing")
_BANDS = ("elevated", "high", "extreme")


def _interp(cfg, ctx: Optional[Mapping[str, Any]], h: str, liq) -> str:
    from .interpretation import interpret
    if not ctx:
        return UNKNOWN
    key = (interpret(cfg, ctx, horizon=h, liquidation_episodes=liq) or {}).get("key")
    return UNKNOWN if not key or key in _UNREADABLE_KEYS else str(key)


def _band(cfg, ctx: Optional[Mapping[str, Any]], metric: str) -> str:
    from .context import level_label
    if not ctx:
        return UNKNOWN
    p = ((ctx.get("percentiles") or {}).get(metric)) or {}
    return level_label(cfg, p.get("rank"), p.get("tier")) or UNKNOWN


def _liq(rules: Optional[Mapping[str, Any]]) -> str:
    if not rules:
        return UNKNOWN
    status = {side: ((rules.get(f"LIQUIDATION_STRESS_{side.upper()}") or {}).get("status"))
              for side in ("long", "short")}
    if any(s is None or s == "NOT_EVALUABLE" for s in status.values()):
        return UNKNOWN
    hit = [side for side, s in status.items() if s == "QUALIFIES"]
    return "both" if len(hit) == 2 else (hit[0] if hit else "none")


def components(cfg, *, state: Optional[Mapping[str, Any]], rules: Optional[Mapping[str, Any]],
               d7: Optional[bool], evidence: Optional[Sequence[str]]) -> dict:
    """The signature components of one bucket from its stored readings. Pure. `evidence` None means
    not read for this bucket; an empty sequence means read, nothing matched."""
    from .hour_gate import evaluate_hour
    from .interpretation import liquidation_episodes
    state = state or {}
    c1, c4 = state.get("context_1h"), state.get("context_4h")
    liq_eps = liquidation_episodes(state)
    gate = evaluate_hour(cfg, c1, liquidation_episodes=liq_eps, snapshot={"rule_evaluations": rules or {}}) \
        if c1 else None
    status = (gate or {}).get("status")
    day = (c1 or {}).get("day_type")
    return {
        "i1h": _interp(cfg, c1, "1h", liq_eps), "i4h": _interp(cfg, c4, "4h", liq_eps),
        "r1h": _band(cfg, c1, "range_width_pct_median"), "v1h": _band(cfg, c1, "volume_notional_usd_sum"),
        "r4h": _band(cfg, c4, "range_width_pct_median"), "v4h": _band(cfg, c4, "volume_notional_usd_sum"),
        "gate": "Q" if status == "QUALIFIED" else "N" if status == "NOT_UNUSUAL" else UNKNOWN,
        "d7": UNKNOWN if d7 is None else ("on" if d7 else "off"),
        "liq": _liq(rules),
        "ev": UNKNOWN if evidence is None else "+".join(sorted(set(evidence))),
        "day": {"WEEKDAY": "WD", "WEEKEND": "WE"}.get(day, UNKNOWN),
    }


def tail_states(comp: Mapping[str, str]) -> list:
    """The components in a non-neutral state («?» and the calendar are never tail)."""
    out = []
    for k in ("i1h", "i4h"):
        if comp[k] not in ("normal", UNKNOWN):
            out.append(k)
    for k in ("r1h", "v1h", "r4h", "v4h"):
        if comp[k] in _BANDS:
            out.append(k)
    if comp["gate"] == "Q":
        out.append("gate")
    if comp["d7"] == "on":
        out.append("d7")
    if comp["liq"] in ("long", "short", "both"):
        out.append("liq")
    if comp["ev"] not in ("", UNKNOWN):
        out.append("ev")
    return out


def signature_key(comp: Mapping[str, str]) -> str:
    return "|".join(f"{k}={comp[k]}" for k in COMPONENTS)


def signature_id(key: str) -> str:
    return hashlib.sha256(f"{SIGNATURE_VERSION}:{key}".encode("utf-8")).hexdigest()[:8]


# ---- the notifier step -------------------------------------------------------------------------
def _evidence_ids(evidence: Optional[Mapping[str, Any]], bucket_close: datetime) -> Optional[list]:
    """The finding ids matched by the run's research evidence when it describes this bucket; None when
    it was not read here (another bucket, too old, or an error)."""
    if not evidence or evidence.get("error_type") or not evidence.get("as_of"):
        return None
    at = datetime.fromisoformat(str(evidence["as_of"]).replace("Z", "+00:00"))
    if not (bucket_close <= at <= bucket_close + EVIDENCE_MAX_AGE):
        return None
    return [str(m.get("finding_id")) for m in evidence.get("matches") or () if m.get("finding_id")]


async def record_signatures(conn, cfg, *, now: datetime, evidence: Optional[Mapping[str, Any]] = None) -> dict:
    """Sign every closed bucket since the last signed one (at most MAX_BUCKETS_PER_RUN). Append-only and
    idempotent per bucket; never raises into the notifier (the caller wraps it)."""
    from .context import episodization_digest
    from .regime_d7 import last_completed_hour
    rep = {"signed": 0}
    last = await conn.last_signature_bucket(version=SIGNATURE_VERSION)
    if last is None:
        newest = await conn.fetch_latest_context_state(symbol=cfg.symbol, episodization_digest=episodization_digest(cfg))
        if newest is None:
            return rep
        after = newest["bucket_ts"] - FIRST_RUN_BACK
        prev = None
    else:
        after = last["bucket_ts"]
        prev = last
    rows = await conn.context_buckets_after(symbol=cfg.symbol, episodization_digest=episodization_digest(cfg),
                                            after=after, limit=MAX_BUCKETS_PER_RUN)
    if not rows:
        return rep
    hours = sorted({last_completed_hour(r["bucket_ts"] + BUCKET) for r in rows})
    d7 = await conn.d7_states_asof(hours)
    newest_ts = rows[-1]["bucket_ts"]
    for r in rows:
        close = r["bucket_ts"] + BUCKET
        h = last_completed_hour(close)
        st = d7.get(h)
        d7_state = st["state"] if st and st.get("available_at") and st["available_at"] <= close else None
        comp = components(cfg, state=r["state"], rules=r.get("rules"), d7=d7_state,
                          evidence=_evidence_ids(evidence, close) if r["bucket_ts"] == newest_ts else None)
        key = signature_key(comp)
        start = prev is None or prev["bucket_ts"] != r["bucket_ts"] - BUCKET or prev["signature_key"] != key
        ok = await conn.insert_signature_bucket(bucket_ts=r["bucket_ts"], version=SIGNATURE_VERSION, key=key,
                                                sig_id=signature_id(key), components=comp,
                                                tail_count=len(tail_states(comp)), episode_start=start,
                                                context_pk=r.get("context_pk"), recorded_at=now)
        rep["signed"] += int(ok)
        prev = {"bucket_ts": r["bucket_ts"], "signature_key": key}
    return rep


# ---- owner surface ---------------------------------------------------------------------------------
def index_rows(stats: Sequence[Mapping[str, Any]], reviewed: Iterable[str], *, total: int) -> dict:
    """NEW (unreviewed) signatures and the reviewed ones from per-signature counts. Pure."""
    done = set(reviewed)
    new, seen = [], []
    for s in stats:
        row = {**s, "frequency": (int(s["n_buckets"]) / total) if total else None}
        if s["key"] in done:
            seen.append(row)
        elif int(s["tail_count"]) >= NEW_MIN_TAIL and int(s["n_episodes"]) >= NEW_MIN_EPISODES \
                and int(s["n_days"]) >= NEW_MIN_DAYS:
            new.append(row)
    new.sort(key=lambda r: (-int(r["tail_count"]), -int(r["n_episodes"]), r["sig_id"]))
    return {"new": new, "reviewed": seen}


def _comp_line(comp: Mapping[str, str]) -> str:
    return (f"1h {comp['i1h']} (range {comp['r1h']}, volume {comp['v1h']}) · 4h {comp['i4h']} "
            f"(range {comp['r4h']}, volume {comp['v4h']}) · gate {comp['gate']} · d7 {comp['d7']} · "
            f"liq {comp['liq']} · evidence {comp['ev'] or 'none'} · {comp['day']}")


def format_index(summary: Mapping[str, Any], idx: Mapping[str, Any], pins: Sequence[Mapping[str, Any]],
                 reviews: Sequence[Mapping[str, Any]]) -> str:
    """Owner plain text. It shows what was seen, never what followed (blind review)."""
    first = summary.get("first_bucket")
    lines = [f"signature index {SIGNATURE_VERSION} (owner only)",
             f"since {first.strftime('%Y-%m-%d %H:%M UTC') if first else 'none'} · buckets {summary.get('total', 0)}"
             f" · signatures {summary.get('signatures', 0)} · NEW {len(idx['new'])}",
             f"NEW = >= {NEW_MIN_TAIL} tail states, >= {NEW_MIN_EPISODES} episodes, >= {NEW_MIN_DAYS} UTC days; "
             "what followed is not shown"]
    for r in idx["new"][:10]:
        lines.append(f"[{r['sig_id']}] {r['frequency'] * 100:.2f}% of buckets (N {r['n_buckets']} of "
                     f"{summary.get('total', 0)}) · {r['n_episodes']} episodes · {r['n_days']} days · "
                     f"tail {r['tail_count']}")
        lines.append("  " + _comp_line(r["components"]))
    if len(idx["new"]) > 10:
        lines.append(f"... and {len(idx['new']) - 10} more")
    if idx["new"]:
        lines.append("review: /hypotheses research <id> <hypothesis text> · /hypotheses reject <id>")
    if reviews:
        lines.append("reviewed: " + " · ".join(f"[{r['sig_id']}] {r['decision']}" for r in reviews[-10:]))
    if pins:
        lines.append("pins: " + " · ".join(f"{p['bucket_ts'].strftime('%m-%d %H:%M')} [{p['sig_id']}]"
                                            + (f" {p['note']}" if p.get("note") else "") for p in pins[-5:]))
    return "\n".join(lines)


MIN_HYPOTHESIS_CHARS = 10


async def handle_owner_command(conn, cmd: str, args: str, *, now: datetime) -> str:
    """`/hypotheses`, `/hypotheses research <id> <text>`, `/hypotheses reject <id>`, `/pin [note]`."""
    parts = (args or "").strip().split(maxsplit=2)
    if cmd == "pin":
        last = await conn.last_signature_bucket(version=SIGNATURE_VERSION)
        if last is None:
            return "nothing to pin yet: no bucket is signed"
        note = (args or "").strip()[:200] or None
        await conn.insert_hypothesis_pin(bucket_ts=last["bucket_ts"], version=SIGNATURE_VERSION,
                                         key=last["signature_key"], sig_id=last["sig_id"], note=note, pinned_at=now)
        return f"pinned {last['bucket_ts'].strftime('%Y-%m-%d %H:%M UTC')} [{last['sig_id']}]"
    if parts and parts[0] in ("research", "reject"):
        if len(parts) < 2:
            return "usage: /hypotheses research <id> <hypothesis text> · /hypotheses reject <id>"
        stats = await conn.signature_stats(version=SIGNATURE_VERSION, sig_id=parts[1].lower())
        if stats is None:
            return f"unknown signature id {parts[1]}"
        text = parts[2].strip() if len(parts) > 2 else ""
        if parts[0] == "research" and len(text) < MIN_HYPOTHESIS_CHARS:
            return f"«в research» needs the hypothesis text (at least {MIN_HYPOTHESIS_CHARS} characters)"
        pk = await conn.insert_hypothesis_review(
            version=SIGNATURE_VERSION, key=stats["key"], sig_id=stats["sig_id"], components=stats["components"],
            decision="RESEARCH" if parts[0] == "research" else "REJECT", hypothesis=text or None,
            window_from=stats["first_bucket"], window_to=stats["last_bucket"] + BUCKET,
            seen={k: stats[k] for k in ("n_buckets", "n_episodes", "n_days", "tail_count")} | {"total": stats["total"]},
            decided_at=now)
        if pk is None:
            return f"[{stats['sig_id']}] was already reviewed; the first decision stands"
        return (f"[{stats['sig_id']}] {'в research' if parts[0] == 'research' else 'отклонено'}; frozen window "
                f"{stats['first_bucket'].strftime('%Y-%m-%d %H:%M')} .. "
                f"{(stats['last_bucket'] + BUCKET).strftime('%Y-%m-%d %H:%M')} UTC")
    summary = await conn.signature_summary(version=SIGNATURE_VERSION)
    reviews = await conn.hypothesis_reviews(version=SIGNATURE_VERSION)
    idx = index_rows(await conn.signature_stats_all(version=SIGNATURE_VERSION),
                     [r["key"] for r in reviews], total=int(summary.get("total") or 0))
    return format_index(summary, idx, await conn.hypothesis_pins(version=SIGNATURE_VERSION), reviews)


def export_reviews(reviews: Sequence[Mapping[str, Any]]) -> list:
    """The bot-side exposure ledger, shaped for a reviewed atlas change (`ATLAS_SURFACES_V1.yaml`
    `exposure:` entries). The owner names the surface; nothing here edits the atlas."""
    out = []
    for r in reviews:
        wf, wt = r["window_from"], r["window_to"]
        out.append({"signature_id": r["sig_id"], "version": r["version"], "decision": r["decision"],
                    "hypothesis": r.get("hypothesis"), "components": r["components"],
                    "decided_at": r["decided_at"].astimezone(timezone.utc).isoformat(),
                    "window": [wf.astimezone(timezone.utc).isoformat(), wt.astimezone(timezone.utc).isoformat()],
                    "seen_at_review": r["seen"],
                    "exposure_entry": {"period": f"{wf.date().isoformat()}..{wt.date().isoformat()}",
                                       "status": "EXPOSED",
                                       "note": f"/hypotheses [{r['sig_id']}] {r['decision']} "
                                               f"{r['decided_at'].date().isoformat()}: generating window of a "
                                               "live signature (discovery only; replication is live, forward)"}})
    return out
