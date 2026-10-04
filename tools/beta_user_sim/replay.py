"""Offline replay engine: Role A at time T, then Role B after the horizons mature.

Causal order:

1. Phase A walks forward in time over push arrivals, availability starts and idle
   ticks. Role A gets a turn only while AVAILABLE; messages that arrive while BUSY
   or SLEEPING wait in a backlog and are shown, with their original times, at the
   next AVAILABLE instant. Accepted actions run through the real `BetaBotHandler`
   against the isolated `SandboxStore`, whose reads are as-of the replay clock.
2. /btc cannot be rebuilt at an arbitrary instant (the live tape it reads is not
   versioned by ingestion time). When Role A sends /btc at T the engine serves the
   first persisted same-language /btc view requested in [T, T + max_wait] and
   moves the clock to its request time; otherwise the action is UNREPLAYABLE and
   Role A only gets the neutral "no visible reply" notice.
3. Phase B starts only after phase A. Each shown item is audited at its own
   maturity instant (`OutcomeLedger.audit_at`); nothing from phase B flows back.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from beta.config import BetaConfig

from . import HARNESS_VERSION, STATUS, STATUS_LABELS
from .attention import AttentionConfig, AttentionSchedule
from .baseline import baseline_meta, baseline_text
from .bundle import ReplayBundle
from .claims import Manifest, build_manifest, surface_manifest
from .llm import ROLE_AUDITOR, ROLE_JUDGE, ROLE_USER, aggregate_api_usage
from .outcomes import OUTCOME_LEDGER_VERSION, OutcomeLedger, observations_as_dicts
from .prompts import JUDGE_PROMPT_VERSION, ROLE_A_PROMPT_VERSION, ROLE_B_PROMPT_VERSION
from .role_a import CLICK_BUTTON, NO_ACTION, SEND_COMMAND, RoleAUser
from .role_b import (PAIR_KINDS, BlindJudge, LeakToJudge, RoleBAuditor, message_body)
from .sandbox import (SIM_CHAT_ID, SIM_TELEGRAM_USER_ID, SandboxStore, Unreplayable, callback_update,
                      message_update, sandbox_handler)
from .surface import (AVAILABLE, NOTICE_NO_REPLY, UserTurn, VisibleButton, VisibleMessage, html_to_text,
                      visible_time)
from .timeline import KIND_BTC_VIEW, KIND_PUSH, ReplayItem, build_timeline

REPLAY_ENGINE_VERSION = "SIM_REPLAY_ENGINE_V0"
_PRIORITY = {"PUSH": 0, "AVAILABLE": 1, "IDLE": 2}


@dataclass(frozen=True)
class ReplayConfig:
    lang: str = "ru"
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    btc_max_wait_min: int = 10
    max_chain: int = 3
    replay_seed: int = 1
    judge_seed: int = 11
    attention: AttentionConfig = field(default_factory=AttentionConfig)

    def as_dict(self) -> dict:
        return {"lang": self.lang, "start": None if self.start is None else self.start.isoformat(),
                "end": None if self.end is None else self.end.isoformat(),
                "btc_max_wait_min": self.btc_max_wait_min, "max_chain": self.max_chain,
                "replay_seed": self.replay_seed, "judge_seed": self.judge_seed,
                "attention": self.attention.as_dict()}


@dataclass
class Shown:
    num: int
    kind: str
    at: datetime
    html: str
    arrived_while: str
    callbacks: dict
    labels: dict
    item: Optional[ReplayItem] = None
    edit_of: Optional[str] = None

    @property
    def mid(self) -> str:
        return f"m{self.num}"


class ReplayEngine:
    def __init__(self, bundle: ReplayBundle, cfg: BetaConfig, models: dict, rcfg: ReplayConfig):
        self.bundle, self.cfg, self.models, self.rcfg = bundle, cfg, models, rcfg
        self.timeline = build_timeline(bundle, cfg, lang=rcfg.lang, start=rcfg.start, end=rcfg.end)
        items = [*self.timeline.views, *self.timeline.pushes]
        if not items:
            raise ValueError("the bundle has no replayable item in the requested window")
        self.start = rcfg.start or min(i.at for i in items) - timedelta(minutes=5)
        self.end = rcfg.end or max(i.at for i in items) + timedelta(minutes=1)
        self.clock = self.start
        self.store = SandboxStore(bundle, cfg, start=self.start)
        self.handler = sandbox_handler(self.store, cfg)
        self.schedule = AttentionSchedule(rcfg.attention, self.start, self.end)
        self.user = RoleAUser(models[ROLE_USER])
        self.shown: dict = {}
        self.inbox: list = []
        self.notices: list = []
        self.popups: list = []
        self.served_views: set = set()
        self.transcript: list = []
        self.unreplayable: list = []
        self.undelivered: list = []
        self._num = 0
        self._update_id = 0
        self._events: list = []

    # ---- helpers -----------------------------------------------------------------------------
    def _log(self, event: str, **kw) -> None:
        self.transcript.append({"t": self.clock.isoformat(), "event": event, **kw})

    def _set_clock(self, at: datetime) -> None:
        if at < self.clock:
            raise AssertionError("replay clock may never move backwards")
        self.clock = at
        self.store.clock = at

    def _next_update(self) -> int:
        self._update_id += 1
        return self._update_id

    def _show(self, *, kind: str, html: str, buttons, at: datetime, item: Optional[ReplayItem] = None,
              edit_of: Optional[Shown] = None) -> Shown:
        if edit_of is None:
            self._num += 1
            num = self._num
        else:
            num = edit_of.num
        callbacks, labels = {}, {}
        for row in buttons or ():
            for label, data in row:
                bid = f"m{num}.b{len(callbacks) + 1}"
                callbacks[bid], labels[bid] = data, label
        s = Shown(num, kind, at, html, self.schedule.state_at(at), callbacks, labels, item,
                  None if edit_of is None else edit_of.mid)
        self.shown[s.mid] = s
        self.inbox.append(s)
        return s

    def _visible(self, s: Shown) -> VisibleMessage:
        return VisibleMessage(message_id=s.mid, received_at=visible_time(s.at), arrived_while=s.arrived_while,
                              text=_text(s.html),
                              buttons=tuple(VisibleButton(b, s.labels[b]) for b in s.callbacks),
                              edit_of=s.edit_of)

    def _view_row(self, item: ReplayItem) -> dict:
        pk = item.source["view_pk"]
        return next(v for v in self.bundle.btc_views if v["view_pk"] == pk)

    def _participant_active(self) -> bool:
        u = self.store.users.get(SIM_TELEGRAM_USER_ID)
        return bool(u and u["status"] == "ACTIVE")

    # ---- handler path ----------------------------------------------------------------------
    async def _handle(self, update: dict, *, reply_kind: str, source_mid: Optional[str] = None) -> bool:
        try:
            out = await self.handler.handle(update)
        except Unreplayable as exc:
            self.unreplayable.append({"t": self.clock.isoformat(), "reason": str(exc), "update_kind":
                                      "callback" if "callback_query" in update else "message"})
            self._log("UNREPLAYABLE", reason=str(exc))
            return False
        produced = False
        for o in out:
            if o.kind == "answer":
                if o.html:
                    self.popups.append(_text(o.html))
                    produced = True
                continue
            if o.chat_id != SIM_CHAT_ID:
                raise AssertionError("handler addressed a chat other than the sandbox participant")
            if o.kind == "message":
                s = self._show(kind=reply_kind, html=o.html, buttons=o.buttons, at=self.clock)
            elif o.kind == "edit":
                target = self.shown.get(f"m{o.message_id}") if o.message_id is not None else None
                if target is None:
                    raise AssertionError("edit of a message the participant never saw")
                s = self._show(kind=reply_kind, html=o.html, buttons=o.buttons, at=self.clock, edit_of=target)
            else:
                raise AssertionError(f"unexpected outgoing kind {o.kind}")
            produced = True
            self._log("REPLY", message_id=s.mid, kind=s.kind, edit_of=s.edit_of, text=_text(s.html))
        return produced

    def _serve_btc(self) -> bool:
        """The first unserved persisted view in [clock, clock + max_wait]; see the module doc."""
        horizon = self.clock + timedelta(minutes=self.rcfg.btc_max_wait_min)
        view = next((v for v in self.timeline.views
                     if v.item_id not in self.served_views and self.clock <= v.at <= horizon), None)
        if view is None:
            self.unreplayable.append({"t": self.clock.isoformat(), "reason": "NO_PERSISTED_BTC_VIEW_IN_WAIT_WINDOW",
                                      "update_kind": "message"})
            self._log("UNREPLAYABLE", reason="NO_PERSISTED_BTC_VIEW_IN_WAIT_WINDOW")
            return False
        wait = int((view.at - self.clock).total_seconds())
        self._set_clock(view.at)
        self._flush_pushes()
        self.served_views.add(view.item_id)
        self.store.expose_view(self._view_row(view))
        s = self._show(kind=KIND_BTC_VIEW, html=view.html, buttons=view.buttons, at=view.at, item=view)
        self._log("SERVED_PERSISTED_VIEW", message_id=s.mid, item_id=view.item_id, wait_s=wait,
                  template_check=view.template_check, text=_text(view.html))
        return True

    async def _execute(self, decision) -> None:
        a = decision.action
        if a.kind == SEND_COMMAND:
            text = "/" + a.command + (" " + a.args if a.args else "")
            if a.command == "btc" and self._participant_active():
                # The live /btc path reads the unversioned live tape and raises Unreplayable
                # in the sandbox (tested); only a persisted view is ever shown.
                produced = self._serve_btc()
            else:
                produced = await self._handle(message_update(self._next_update(), text),
                                              reply_kind="REPLY_" + a.command.upper())
        else:
            s = self.shown[a.message_id]
            data = s.callbacks[a.button_id]
            produced = await self._handle(callback_update(self._next_update(), data, s.num),
                                          reply_kind=_callback_kind(data))
        if not produced:
            self.notices.append(NOTICE_NO_REPLY)

    # ---- Role A turns --------------------------------------------------------------------------
    async def _turn(self, reason: str) -> None:
        for _ in range(self.rcfg.max_chain):
            self._flush_pushes()
            new = sorted(self.inbox, key=lambda s: (s.at, s.num))
            turn = UserTurn(now=visible_time(self.clock), new_messages=tuple(self._visible(s) for s in new),
                            notices=tuple(self.notices), popups=tuple(self.popups))
            self.inbox, self.notices, self.popups = [], [], []
            visible = {mid: tuple(s.callbacks) for mid, s in self.shown.items()}
            backlog = [s.mid for s in new if s.arrived_while != AVAILABLE]
            d = self.user.decide(turn, visible)
            self._log("ROLE_A_TURN", reason=reason, shown=[s.mid for s in new], backlog=backlog,
                      notices=list(turn.notices), popups=list(turn.popups), action=d.action.kind,
                      command=d.action.command, args=d.action.args or None, message_id=d.action.message_id,
                      button_id=d.action.button_id,
                      callback=(self.shown[d.action.message_id].callbacks[d.action.button_id]
                                if d.accepted and d.action.kind == CLICK_BUTTON else None),
                      accepted=d.accepted, rejection=d.rejection, journal=dict(d.journal),
                      excluded_journal=dict(d.excluded_journal))
            if not d.accepted or d.action.kind == NO_ACTION:
                return
            await self._execute(d)
            reason = "ACTION_RESULT"

    def _flush_pushes(self) -> None:
        """Deliver every push whose arrival time has passed, in order (never later state).
        Availability and idle ticks already passed during an action chain are dropped."""
        while self._events and self._events[0][0] <= self.clock:
            at, kind, item = self._events.pop(0)
            if kind == "PUSH":
                self._deliver_push(at, item)

    def _deliver_push(self, at: datetime, item: ReplayItem) -> None:
        if not self._participant_active():
            self.undelivered.append({"item_id": item.item_id, "reason": "PARTICIPANT_NOT_ACTIVE"})
            return
        s = self._show(kind=KIND_PUSH, html=item.html, buttons=item.buttons, at=at, item=item)
        self.transcript.append({"t": at.isoformat(), "event": "PUSH_ARRIVED", "message_id": s.mid,
                                "item_id": item.item_id, "arrived_while": s.arrived_while,
                                "text": _text(item.html)})

    def _build_events(self) -> list:
        ev = [(p.at, "PUSH", p) for p in self.timeline.pushes]
        ev += [(t, "AVAILABLE", None) for t in self.schedule.available_starts() if self.start <= t < self.end]
        slot = timedelta(minutes=self.rcfg.attention.slot_minutes)
        by_slot: dict = {}
        for v in self.timeline.views:
            if self.schedule.state_at(v.at) == AVAILABLE:
                by_slot.setdefault(v.at - (v.at - self.start) % slot, []).append(v.at)
        for key in sorted(by_slot):
            ats = sorted(by_slot[key])
            ev.append((random.Random(f"{self.rcfg.replay_seed}:{key.isoformat()}").choice(ats), "IDLE", None))
        ev.sort(key=lambda e: (e[0], _PRIORITY[e[1]]))
        return ev

    async def _onboard(self) -> None:
        lang = self.rcfg.lang
        self._log("HARNESS_ONBOARDING", step="/start")
        await self._handle(message_update(self._next_update(), "/start"), reply_kind="ONBOARDING")
        for data in (f"pick:{lang}", f"join:{lang}"):
            mid = next((m for m, s in reversed(self.shown.items()) if data in s.callbacks.values()), None)
            if mid is None:
                raise Unreplayable(f"onboarding button {data} not offered by the handler")
            self._log("HARNESS_ONBOARDING", step=data)
            await self._handle(callback_update(self._next_update(), data, self.shown[mid].num),
                               reply_kind="ONBOARDING")
        if not self._participant_active():
            raise Unreplayable("sandbox onboarding did not produce an active participant")

    async def phase_a(self) -> None:
        await self._onboard()
        self._events = self._build_events()
        while self._events:
            at, kind, item = self._events.pop(0)
            if kind == "PUSH":
                if at > self.clock:
                    self._set_clock(at)
                self._deliver_push(at, item)
                if self.schedule.state_at(at) == AVAILABLE:
                    await self._turn("PUSH_WHILE_AVAILABLE")
                continue
            if at < self.clock:
                continue
            self._set_clock(at)
            if self.schedule.state_at(at) != AVAILABLE:
                continue
            if kind == "AVAILABLE" and (self.inbox or self.notices):
                await self._turn("BECAME_AVAILABLE_WITH_BACKLOG")
            elif kind == "IDLE":
                await self._turn("IDLE_WHILE_AVAILABLE")

    # ---- phase B --------------------------------------------------------------------------------
    def manifests(self) -> list:
        out = []
        for s in sorted(self.shown.values(), key=lambda s: s.num):
            if s.item is not None and s.kind == KIND_BTC_VIEW:
                out.append(build_manifest(self.cfg, s.item, payload=self._view_row(s.item)["payload"]))
            elif s.item is not None and s.kind == KIND_PUSH:
                out.append(build_manifest(self.cfg, s.item, episode=self.bundle.episode(s.item.source["episode_pk"])))
            else:
                out.append(surface_manifest(s.mid, s.kind, s.html, self.rcfg.lang))
        return out

    def phase_b(self, manifests: list) -> dict:
        ledger = OutcomeLedger(self.bundle, self.cfg)
        auditor = RoleBAuditor(self.models[ROLE_AUDITOR])
        judge = BlindJudge(self.models[ROLE_JUDGE], seed=self.rcfg.judge_seed)
        by_item = {m.item_id: m for m in manifests}
        audits, judgements, deferred, ab_not_evaluable, log = [], [], [], [], []
        items = sorted({s.item.item_id: s.item for s in self.shown.values()
                        if s.item is not None and s.kind in (KIND_BTC_VIEW, KIND_PUSH)}.values(),
                       key=lambda i: (ledger.audit_at(i), i.item_id))
        for item in items:
            if not ledger.matured_by_export(item):
                deferred.append({"item_id": item.item_id, "reason": "HORIZON_NOT_MATURE_AT_BUNDLE_EXPORT"})
                continue
            at = ledger.audit_at(item)
            ledger.require_matured(item, at)
            payload = self._view_row(item)["payload"] if item.kind == KIND_BTC_VIEW else None
            obs = ledger.available(item, at, payload=payload)
            log.append({"t": at.isoformat(), "event": "OUTCOME_UNLOCK", "item_id": item.item_id,
                        "observations": observations_as_dicts(obs)})
            base = baseline_text(payload, item.lang) if payload is not None else None
            manifest: Manifest = by_item[item.item_id]
            res = auditor.audit(item=item, text_html=item.html, manifest=manifest, observations=obs, baseline=base)
            audits.append(res)
            log.append({"t": at.isoformat(), "event": "ROLE_B_AUDIT", **res.as_dict()})
            if base is None:
                ab_not_evaluable.append({"item_id": item.item_id, "reason":
                                         "NO_AS_OF_BASELINE_FOR_PUSH" if item.kind == KIND_PUSH
                                         else "VIEW_HAS_NO_PRICE_OR_DATA_TIME"})
                continue
            body = message_body(item.html, item.lang)
            for kind in PAIR_KINDS:
                try:
                    j = judge.judge(item_id=item.item_id, pair_kind=kind, signalbot=body, baseline=base,
                                    observations=obs)
                except LeakToJudge as exc:
                    ab_not_evaluable.append({"item_id": item.item_id, "pair_kind": kind,
                                             "reason": f"IDENTITY_LEAK_GUARD:{exc}"})
                    continue
                judgements.append(j)
                log.append({"t": at.isoformat(), "event": "AB_JUDGE", **j.as_dict()})
        return {"audits": audits, "judgements": judgements, "deferred": deferred,
                "ab_not_evaluable": ab_not_evaluable, "log": log, "anomalies": ledger.anomalies,
                "auditor_calls": auditor.calls, "judge_calls": judge.calls}

    # ---- run ---------------------------------------------------------------------------------------
    def run(self) -> dict:
        asyncio.run(self.phase_a())
        manifests = self.manifests()
        b = self.phase_b(manifests)
        return {
            "harness_version": HARNESS_VERSION, "status": STATUS, "status_labels": list(STATUS_LABELS),
            "engine_version": REPLAY_ENGINE_VERSION, "replay_config": self.rcfg.as_dict(),
            "window": {"start": self.start.isoformat(), "end": self.end.isoformat()},
            "bundle": {"digest": self.bundle.digest, "provenance": self.bundle.provenance,
                       "exported_at": None if self.bundle.exported_at is None else self.bundle.exported_at.isoformat(),
                       "export": None if self.bundle.export is None else dict(self.bundle.export)},
            "replay_input_ids": self.timeline.input_ids(),
            "skipped_inputs": [{"source_id": s.source_id, "reason": s.reason} for s in self.timeline.skipped],
            "attention_schedule": self.schedule.as_list(),
            "models": {r: {"model_id": m.model_id, "settings": m.settings()} for r, m in self.models.items()},
            "api_usage": aggregate_api_usage(self.models),
            "prompt_versions": {ROLE_USER: ROLE_A_PROMPT_VERSION, ROLE_AUDITOR: ROLE_B_PROMPT_VERSION,
                                ROLE_JUDGE: JUDGE_PROMPT_VERSION},
            "outcome_version": self.cfg.outcome_version, "outcome_ledger_version": OUTCOME_LEDGER_VERSION,
            "baseline": baseline_meta(),
            "transcript": self.transcript,
            "role_a_decisions": [{"accepted": d.accepted, "rejection": d.rejection, "action": d.action.kind,
                                  "command": d.action.command, "journal": dict(d.journal),
                                  "excluded_journal": dict(d.excluded_journal)} for d in self.user.decisions],
            "unreplayable": self.unreplayable, "undelivered": self.undelivered,
            "shown": [{"message_id": s.mid, "kind": s.kind, "at": s.at.isoformat(), "arrived_while": s.arrived_while,
                       "item_id": None if s.item is None else s.item.item_id, "edit_of": s.edit_of}
                      for s in sorted(self.shown.values(), key=lambda s: s.num)],
            "claim_manifests": [m.as_dict() for m in manifests],
            "role_b": {"audits": [a.as_dict() for a in b["audits"]],
                       "judgements": [j.as_dict() for j in b["judgements"]],
                       "deferred": b["deferred"], "ab_not_evaluable": b["ab_not_evaluable"],
                       "anomalies": b["anomalies"], "auditor_calls": b["auditor_calls"],
                       "judge_calls": b["judge_calls"]},
            "phase_b_log": b["log"],
            "sandbox": {"activity_rows": len(self.store.activity), "votes": len(self.store.votes),
                        "feedback_messages": len(self.store.feedback_messages),
                        "details_opens": len(self.store.details_opens)},
        }


def _text(html_text: str) -> str:
    return html_to_text(html_text)


def _callback_kind(data: str) -> str:
    if data.startswith(("o:", "e:")):
        return "BTC_TAB"
    if data.startswith("d:"):
        return "DETAILS"
    if data.startswith(("u:", "n:")):
        return "VOTE_REPLY"
    if data.startswith(("pick:", "join")):
        return "ONBOARDING"
    if data == "terms":
        return "REPLY_TERMS"
    return "CALLBACK_REPLY"


def run_replay(bundle: ReplayBundle, cfg: BetaConfig, models: dict, rcfg: Optional[ReplayConfig] = None) -> dict:
    return ReplayEngine(bundle, cfg, models, rcfg or ReplayConfig()).run()
