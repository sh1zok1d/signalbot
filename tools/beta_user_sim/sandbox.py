"""Isolated in-memory store that runs the REAL beta bot handler for Role A actions.

`SandboxStore` implements only the BetaConn methods the replayable handler paths
use. Every market/episode read is answered as-of the replay clock from the
read-only bundle: a row is visible only once it was recorded (`recorded_at`,
`computed_at`, delivery timestamps) at or before the clock. Any other store method
— e.g. the live tape behind /btc or the Readiness button — raises `Unreplayable`,
so the handler can never be answered with later state. Nothing here opens a
database, a socket or Telegram.

The synthetic participant has a NEGATIVE Telegram id. The production schema
rejects it (`telegram_user_id > 0` on beta_allowlist / beta_users), so it cannot
be stored in, counted by, or delivered to through any production table.
"""
from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timezone
from typing import Optional

from beta.access import PRIVACY_NOTICE_VERSION
from beta.config import BetaConfig, BetaSwitches
from beta.models import TERMINAL_STATES, Episode

from .bundle import ReplayBundle

SIM_TELEGRAM_USER_ID = -7_311_000_001
SIM_CHAT_ID = SIM_TELEGRAM_USER_ID
SIM_SWITCHES = BetaSwitches(enabled=True, detection=True, push_hard=True, outcome_tracking=True)


class Unreplayable(RuntimeError):
    """The requested surface cannot be rebuilt as-of the replay clock."""


def _known(row: dict, key: str, clock: datetime) -> bool:
    at = row.get(key)
    if at is None:
        raise Unreplayable(f"row has no {key}; its as-of time is unknown")
    return at <= clock


class SandboxConn:
    def __init__(self, store: "SandboxStore"):
        self._s = store

    # ---- transactions -------------------------------------------------------------
    @contextlib.asynccontextmanager
    async def _tx(self):
        s = self._s
        outer = s._depth == 0
        snap = copy.deepcopy(s._mutable()) if outer else None
        s._depth += 1
        try:
            yield
        except BaseException:
            if outer:
                s._restore(snap)
            raise
        finally:
            s._depth -= 1

    def transaction(self):
        return self._tx()

    def __getattr__(self, name: str):
        raise Unreplayable(f"store method {name} is not replayable as-of the replay clock")

    # ---- bot bookkeeping ------------------------------------------------------------
    async def get_last_update_id(self, bot_name: str):
        return self._s.last_update_id

    async def set_last_update_id(self, bot_name: str, update_id: int) -> None:
        self._s.last_update_id = max(self._s.last_update_id or 0, update_id)

    async def get_admin_push_enabled(self) -> bool:
        return True

    async def get_admin_d7_enabled(self) -> bool:
        return False

    # ---- participant (sandbox only) ------------------------------------------------
    async def allowlist_contains(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self._s.allowlist

    async def waitlist_contains(self, telegram_user_id: int) -> bool:
        return False

    async def get_user(self, telegram_user_id: int):
        u = self._s.users.get(telegram_user_id)
        return None if u is None else dict(u)

    async def join_user(self, *, telegram_user_id: int, chat_id: int, now: datetime, lang: str = "ru") -> int:
        users = self._s.users
        pk = users[telegram_user_id]["user_pk"] if telegram_user_id in users else len(users) + 1
        users[telegram_user_id] = {"user_pk": pk, "telegram_user_id": telegram_user_id, "chat_id": chat_id,
                                   "status": "ACTIVE", "joined_at": now, "stopped_at": None, "lang": lang,
                                   "invite_code": None, "privacy_notice_version": PRIVACY_NOTICE_VERSION}
        return pk

    async def stop_user(self, *, telegram_user_id: int, now: datetime) -> bool:
        u = self._s.users.get(telegram_user_id)
        if u is None or u["status"] != "ACTIVE":
            return False
        u.update(status="STOPPED", stopped_at=now)
        return True

    async def mark_privacy_notice_seen(self, telegram_user_id: int, version: int) -> None:
        if telegram_user_id in self._s.users:
            self._s.users[telegram_user_id]["privacy_notice_version"] = version

    async def record_activity(self, *, user_pk: int, action: str, lang: Optional[str], at: datetime,
                              detail: Optional[str] = None) -> bool:
        self._s.activity.append({"user_pk": user_pk, "action": action, "lang": lang, "at": at})
        return True

    async def record_rejected_start(self, telegram_user_id: int, now: datetime, salt) -> bool:
        return True

    async def count_feedback_messages_on_utc_day(self, user_pk: int, day) -> int:
        return sum(1 for f in self._s.feedback_messages
                   if f["user_pk"] == user_pk and f["created_at"].astimezone(timezone.utc).date() == day)

    async def insert_feedback_message(self, *, user_pk: int, text: str, lang: str, created_at: datetime) -> int:
        self._s.feedback_messages.append({"user_pk": user_pk, "text": text, "lang": lang,
                                          "created_at": created_at})
        return len(self._s.feedback_messages)

    async def upsert_feedback(self, *, user_pk: int, episode_pk: int, vote: str) -> None:
        self._s.votes[(user_pk, episode_pk)] = vote

    # ---- persisted /btc views (only those already shown to Role A) ----------------------
    async def fetch_btc_view(self, view_pk: int):
        v = self._s.exposed_views.get(int(view_pk))
        if v is None or v["requested_at"] > self._s.clock:
            return None
        return {"view_pk": v["view_pk"], "payload": copy.deepcopy(v["payload"]),
                "payload_digest": v.get("payload_digest"), "lang": v.get("lang") or "ru",
                "rendered_html": v["rendered_html"]}

    async def insert_details_open(self, *, view_pk: int, tab: str, lang: str, opened_at: datetime) -> None:
        self._s.details_opens.append({"view_pk": view_pk, "tab": tab, "lang": lang, "opened_at": opened_at})

    # ---- episodes / outcomes as-of the replay clock -------------------------------------
    async def fetch_episode_by_public_id(self, public_id: str):
        row = self._s.bundle.episode_by_public_id(public_id)
        return None if row is None else self._s.episode_as_of(row)

    async def fetch_episode_by_pk(self, episode_pk: int):
        row = self._s.bundle.episode(episode_pk)
        return None if row is None else self._s.episode_as_of(row)

    async def fetch_transitions(self, episode_pk: int) -> list:
        return [dict(t) for t in self._s.transitions_as_of(episode_pk)]

    async def fetch_outcomes(self, episode_pk: int) -> list:
        return self._s.outcomes_as_of(episode_pk)

    async def fetch_episode_history(self, *, symbol: str, limit: int) -> list:
        return self._s.history_as_of(limit)


class SandboxStore:
    """Holds sandbox participant state and the as-of view of the bundle."""

    def __init__(self, bundle: ReplayBundle, cfg: BetaConfig, *, start: datetime):
        self.bundle, self.cfg = bundle, cfg
        self.clock = start
        self.allowlist = {SIM_TELEGRAM_USER_ID}
        self.users: dict = {}
        self.activity: list = []
        self.feedback_messages: list = []
        self.votes: dict = {}
        self.details_opens: list = []
        self.exposed_views: dict = {}
        self.last_update_id: Optional[int] = None
        self._depth = 0

    def _mutable(self) -> dict:
        return {k: getattr(self, k) for k in ("users", "activity", "feedback_messages", "votes",
                                              "details_opens", "last_update_id")}

    def _restore(self, snap: dict) -> None:
        for k, v in snap.items():
            setattr(self, k, v)

    @contextlib.asynccontextmanager
    async def connect(self):
        yield SandboxConn(self)

    @contextlib.asynccontextmanager
    async def advisory_lock(self, key: int):
        raise Unreplayable("advisory locks belong to production runners")
        yield  # pragma: no cover

    def expose_view(self, view_row: dict) -> None:
        self.exposed_views[int(view_row["view_pk"])] = view_row

    # ---- as-of reconstruction --------------------------------------------------------
    def transitions_as_of(self, episode_pk: int) -> list:
        rows = [t for t in self.bundle.transitions if t["episode_pk"] == episode_pk]
        return sorted((t for t in rows if _known(t, "recorded_at", self.clock)), key=lambda t: t["seq"])

    def episode_as_of(self, row: dict) -> Optional[Episode]:
        if row.get("correction_flag"):
            raise Unreplayable("correction flag is set and the time it was set is not recorded")
        known = self.transitions_as_of(row["episode_pk"])
        if not known:
            return None
        by_state = {t["to_state"]: t for t in known}
        last = known[-1]
        trig = by_state.get("TRIGGERED")
        terminal = next((t for t in reversed(known) if t["to_state"] in TERMINAL_STATES), None)
        return Episode(
            episode_pk=row["episode_pk"], public_id=row["public_id"], symbol=row.get("symbol") or "BTCUSDT",
            event_type=row["event_type"], state=last["to_state"], opened_bucket=row["opened_bucket"],
            opened_at=row["opened_at"],
            armed_at=by_state["ARMED"]["decision_ts"] if "ARMED" in by_state else None,
            triggered_at=trig["decision_ts"] if trig else None,
            terminal_at=terminal["decision_ts"] if terminal else None,
            terminal_reason=terminal["reason"] if terminal else None,
            rules_version=row["rules_version"], rules_digest=row["rules_digest"],
            code_version=row.get("code_version") or "", calculation_version=row.get("calculation_version") or "",
            opening_tape_digest=row.get("opening_tape_digest") or "0" * 64,
            trigger_tape_digest=row.get("trigger_tape_digest") if trig else None,
            # Not read by the Details or /history templates; never the live value.
            last_bucket=row["opened_bucket"], last_streak=0,
            reference_price=row.get("reference_price") if trig else None,
            reference_exchanges=tuple(row.get("reference_exchanges") or ()) if trig else (),
            reference_dispersion_pct=row.get("reference_dispersion_pct") if trig else None,
            reference_bucket=row.get("reference_bucket") if trig else None,
            correction_flag=False, correction_note=None)

    def outcomes_as_of(self, episode_pk: int) -> list:
        best: dict = {}
        for o in self.bundle.outcomes:
            if o["episode_pk"] != episode_pk or not _known(o, "computed_at", self.clock):
                continue
            cur = best.get(o["horizon"])
            if cur is None or o["revision"] > cur["revision"]:
                best[o["horizon"]] = o
        keys = ("horizon", "status", "max_up_pct", "max_down_pct", "close_return_pct", "realized_range_pct",
                "time_to_max_up_s", "time_to_max_down_s", "revision", "correction_note")
        return [{k: best[h].get(k) for k in keys} for h in sorted(best)]

    def _delivery_state_as_of(self, d: dict) -> Optional[str]:
        c = self.clock
        if d.get("created_at") is None:
            raise Unreplayable("delivery row has no created_at")
        if d["created_at"] > c:
            return None
        if d.get("finished_at") is not None:
            if d["finished_at"] <= c:
                return d["state"]
            return "SENDING" if d.get("sending_at") is not None and d["sending_at"] <= c else "PENDING"
        if d["state"] in ("SUPPRESSED", "EXPIRED_UNDELIVERED"):
            return d["state"]
        if d["state"] == "SENDING":
            return "SENDING"
        if d["state"] == "PENDING":
            return "PENDING"
        raise Unreplayable(f"delivery in {d['state']} without finished_at")

    def history_as_of(self, limit: int) -> list:
        rows = []
        for e in self.bundle.episodes:
            ep = self.episode_as_of(e)
            if ep is None:
                continue
            dec = next((d for d in self.bundle.push_decisions if d["episode_pk"] == e["episode_pk"]), None)
            if dec is not None and not _known(dec, "recorded_at", self.clock):
                dec = None
            states = sorted({s for s in (self._delivery_state_as_of(d) for d in self.bundle.deliveries
                                         if d["episode_pk"] == e["episode_pk"]) if s})
            rows.append({**{f: getattr(ep, f) for f in Episode.__dataclass_fields__},
                         "reference_exchanges": list(ep.reference_exchanges),
                         "decision": None if dec is None else dec["decision"],
                         "suppression_reason": None if dec is None else dec.get("suppression_reason"),
                         "push_decision_ts": None if dec is None else dec["decision_ts"],
                         "delivery_states": states or None})
        rows.sort(key=lambda r: (r["opened_at"], r["episode_pk"]), reverse=True)
        if len(rows) < limit and self.bundle.episodes_since is not None:
            raise Unreplayable("history may include episodes opened before the bundle's episode window")
        return rows[:limit]


def sandbox_handler(store: SandboxStore, cfg: BetaConfig):
    """The production handler, wired to the sandbox: no owner, no salt, replay clock."""
    from runtime.beta_bot import BetaBotHandler
    return BetaBotHandler(store, cfg, switches=lambda: SIM_SWITCHES, owner_user_id=None,
                          clock=lambda: store.clock, bot_username=None, telemetry_salt=None)


def message_update(update_id: int, text: str) -> dict:
    return {"update_id": update_id, "message": {
        "from": {"id": SIM_TELEGRAM_USER_ID}, "chat": {"id": SIM_CHAT_ID, "type": "private"}, "text": text}}


def callback_update(update_id: int, data: str, message_id: int) -> dict:
    return {"update_id": update_id, "callback_query": {
        "id": f"sim-cb-{update_id}", "from": {"id": SIM_TELEGRAM_USER_ID},
        "message": {"chat": {"id": SIM_CHAT_ID}, "message_id": message_id}, "data": data}}
