"""Causal replay timeline built from a bundle.

Two user-visible sources exist in current main:

* /btc views — `beta_btc_views.rendered_html` is byte-exactly what /btc showed at
  `requested_at` (PERSISTED_RENDERED). Their buttons are not persisted; they are
  rebuilt with the production `btc_buttons` from the persisted payload.
* pushes — the delivered text is not persisted. `format_push` reads only fields
  set once at the TRIGGERED transition (public id, event type, triggered_at,
  reference price/venues, rules version), so the text is rebuilt with the
  production template (RECONSTRUCTED_SET_ONCE_FIELDS). A push is exposed only when
  the decision was PUSH and at least one delivery reached SENT; it arrives at the
  first SENT time.

Anything that cannot be rebuilt without later state is recorded as unreplayable
and skipped. Nothing is silently rebuilt from later data.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Sequence

from beta.config import BetaConfig
from beta.formatter import btc_buttons, feedback_buttons, format_btc
from beta.formatter import format_push_v02 as format_push   # harness frozen at the V0.2 push text
from beta.models import TRIGGERED, Episode

from .bundle import ReplayBundle

PERSISTED_RENDERED = "PERSISTED_RENDERED"
RECONSTRUCTED_SET_ONCE_FIELDS = "RECONSTRUCTED_SET_ONCE_FIELDS"
KIND_BTC_VIEW = "BTC_VIEW"
KIND_PUSH = "PUSH"

# Fields format_push reads. All are set no later than the TRIGGERED transition and never changed after it.
PUSH_SET_ONCE_FIELDS = ("public_id", "event_type", "triggered_at", "reference_price", "reference_exchanges",
                        "rules_version")


@dataclass(frozen=True)
class ReplayItem:
    item_id: str
    kind: str
    at: datetime
    lang: str
    html: str
    buttons: Optional[Sequence[Sequence[tuple]]]
    provenance: str
    template_check: str
    source: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Skipped:
    source_id: str
    reason: str


@dataclass(frozen=True)
class Timeline:
    views: Sequence[ReplayItem]
    pushes: Sequence[ReplayItem]
    skipped: Sequence[Skipped]

    def input_ids(self) -> list:
        return [i.item_id for i in sorted([*self.views, *self.pushes], key=lambda i: (i.at, i.item_id))]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def push_episode_at_trigger(row: dict) -> Episode:
    """An Episode carrying only the set-once trigger fields. Every lifecycle field
    that can change after the trigger is a neutral placeholder; format_push does
    not read them (tests pin this)."""
    return Episode(
        episode_pk=row["episode_pk"], public_id=row["public_id"], symbol=row.get("symbol") or "BTCUSDT",
        event_type=row["event_type"], state=TRIGGERED, opened_bucket=row["opened_bucket"],
        opened_at=row["opened_at"], armed_at=None, triggered_at=row["triggered_at"], terminal_at=None,
        terminal_reason=None, rules_version=row["rules_version"], rules_digest=row["rules_digest"],
        code_version=row.get("code_version") or "", calculation_version=row.get("calculation_version") or "",
        opening_tape_digest=row.get("opening_tape_digest") or "0" * 64,
        trigger_tape_digest=row.get("trigger_tape_digest"), last_bucket=row["opened_bucket"], last_streak=0,
        reference_price=row.get("reference_price"),
        reference_exchanges=tuple(row.get("reference_exchanges") or ()),
        reference_dispersion_pct=None, reference_bucket=None, correction_flag=False, correction_note=None)


def _first_sent(bundle: ReplayBundle, episode_pk: int) -> Optional[datetime]:
    sent = [d["finished_at"] for d in bundle.deliveries
            if d["episode_pk"] == episode_pk and d["state"] == "SENT" and d.get("finished_at")]
    return min(sent) if sent else None


def build_timeline(bundle: ReplayBundle, cfg: BetaConfig, *, lang: str,
                   start: Optional[datetime] = None, end: Optional[datetime] = None) -> Timeline:
    def _in(at: datetime) -> bool:
        return (start is None or at >= start) and (end is None or at < end)

    views, pushes, skipped = [], [], []
    for v in sorted(bundle.btc_views, key=lambda r: (r["requested_at"], r["view_pk"])):
        sid = f"view:{v['view_pk']}"
        if not _in(v["requested_at"]):
            continue
        if (v.get("lang") or "ru") != lang:
            skipped.append(Skipped(sid, "LANG_MISMATCH"))
            continue
        if v.get("rendered_sha256") and v["rendered_sha256"] != _sha(v["rendered_html"]):
            skipped.append(Skipped(sid, "RENDERED_DIGEST_MISMATCH"))
            continue
        payload = v["payload"]
        try:
            check = "TEMPLATE_MATCH" if format_btc(cfg, payload, lang) == v["rendered_html"] else "TEMPLATE_DRIFT"
        except Exception:  # noqa: BLE001 - an older payload the current template cannot render
            check = "TEMPLATE_DRIFT"
        views.append(ReplayItem(item_id=sid, kind=KIND_BTC_VIEW, at=v["requested_at"], lang=lang,
                                html=v["rendered_html"], buttons=btc_buttons(payload, lang, v["view_pk"]),
                                provenance=PERSISTED_RENDERED, template_check=check,
                                source={"view_pk": v["view_pk"], "payload_digest": v.get("payload_digest")}))
    for ep in sorted(bundle.episodes, key=lambda e: (e.get("triggered_at") or e["opened_at"], e["episode_pk"])):
        sid = f"push:{ep['public_id']}"
        if ep.get("triggered_at") is None:
            continue
        decision = next((d for d in bundle.push_decisions if d["episode_pk"] == ep["episode_pk"]), None)
        if decision is None or decision["decision"] != "PUSH":
            continue
        at = _first_sent(bundle, ep["episode_pk"])
        if at is None:
            skipped.append(Skipped(sid, "NO_SENT_DELIVERY"))
            continue
        if not _in(at):
            continue
        if at < ep["triggered_at"]:
            skipped.append(Skipped(sid, "SENT_BEFORE_TRIGGER"))
            continue
        missing = [f for f in PUSH_SET_ONCE_FIELDS if f != "reference_price" and ep.get(f) in (None, "")]
        if missing:
            skipped.append(Skipped(sid, "MISSING_SET_ONCE_FIELDS:" + ",".join(missing)))
            continue
        episode = push_episode_at_trigger(ep)
        pushes.append(ReplayItem(item_id=sid, kind=KIND_PUSH, at=at, lang=lang,
                                 html=format_push(episode, lang=lang),
                                 buttons=feedback_buttons(ep["public_id"], lang),
                                 provenance=RECONSTRUCTED_SET_ONCE_FIELDS,
                                 template_check="NOT_VERIFIABLE_DELIVERED_TEXT_NOT_PERSISTED",
                                 source={"episode_pk": ep["episode_pk"], "public_id": ep["public_id"],
                                         "decision_ts": decision["decision_ts"]}))
    return Timeline(views=tuple(views), pushes=tuple(pushes), skipped=tuple(skipped))
