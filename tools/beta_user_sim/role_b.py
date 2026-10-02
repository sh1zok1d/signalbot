"""Role B: delayed outcome auditor and blind A/B judge. A context separate from Role A.

Role B is called only after an item's horizons are mature (`OutcomeLedger.
require_matured`). Each call is a fresh two-message conversation: nothing from
Role A is passed in, and nothing Role B says is ever passed to Role A or to the
product. The deterministic claim results and outcome numbers are inputs; Role B
only answers four narrow subjective questions and never recomputes numbers.

The blind judge sees "Option A" / "Option B" text only. Sides are assigned with a
seeded RNG per (item, pair kind). Identical-pair controls (baseline vs baseline,
Signalbot vs Signalbot) measure side bias. No composite score is produced.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from typing import Mapping, Optional, Sequence

from beta.i18n import t

from .claims import CONTRADICTED, NO_DIRECTIONAL_CLAIM, Manifest
from .llm import ROLE_AUDITOR, ROLE_JUDGE, ChatModel
from .outcomes import Observation
from .prompts import JUDGE_SYSTEM, ROLE_B_SYSTEM
from .surface import html_to_text

INVALID = "INVALID_RESPONSE"
QUESTIONS = {
    "wording_stronger_than_evidence": ("YES", "NO", "UNCLEAR"),
    "adds_explanatory_value_over_baseline": ("YES", "NO", "UNCLEAR"),
    "understandable_without_hidden_knowledge": ("YES", "PARTLY", "NO"),
    "retrospective_usefulness": ("USEFUL", "SOMEWHAT", "NOT_USEFUL", "UNCLEAR"),
}
NOTES = ("wording_note", "retrospective_note")

PAIR_SIGNALBOT_VS_BASELINE = "SIGNALBOT_VS_BASELINE"
PAIR_BASELINE_VS_BASELINE = "CONTROL_BASELINE_VS_BASELINE"
PAIR_SIGNALBOT_VS_SIGNALBOT = "CONTROL_SIGNALBOT_VS_SIGNALBOT"
PAIR_KINDS = (PAIR_SIGNALBOT_VS_BASELINE, PAIR_BASELINE_VS_BASELINE, PAIR_SIGNALBOT_VS_SIGNALBOT)
SIGNALBOT, BASELINE, TIE = "SIGNALBOT", "BASELINE", "TIE"
_IDENTITY_WORDS = re.compile(r"(signalbot|baseline|бета|beta|BASELINE_SIMPLE)", re.IGNORECASE)


def message_body(html_text: str, lang: str) -> str:
    """User-visible text without the beta disclaimer line."""
    disc = html_to_text(t(lang, "disclaimer"))
    return html_to_text(html_text).replace(disc, "").strip()


def outcome_summary(obs: Sequence[Observation]) -> list:
    out = []
    for o in obs:
        row = {"horizon": o.horizon, "status": o.status}
        for k, v in o.fields.items():
            if k.endswith("_pct") and v is not None:
                row[k] = round(float(v), 2)
        out.append(row)
    return out


def _claim_view(m: Manifest) -> list:
    return [{"claim_type": c.claim_type, "evaluation_class": c.evaluation_class, "status": c.status,
             "fragment": c.rendered_text_fragment, "directional_claim": c.directional_claim,
             "horizon": c.horizon} for c in m.claims]


def forward_claim_present(m: Manifest) -> bool:
    return any(c.directional_claim for c in m.claims)


@dataclass(frozen=True)
class AuditResult:
    item_id: str
    answers: dict
    notes: dict
    forward_outcome_verdict: str
    contradicted_facts: int
    raw: str

    def as_dict(self) -> dict:
        return asdict(self)


class RoleBAuditor:
    def __init__(self, model: ChatModel):
        self.model = model
        self.calls = 0

    def request(self, *, item, text_html: str, manifest: Manifest, observations: Sequence[Observation],
                baseline: Optional[str]) -> dict:
        return {"time_T": item.at.isoformat(), "kind": item.kind,
                "original_message": message_body(text_html, item.lang),
                "claims": _claim_view(manifest), "what_followed": outcome_summary(observations),
                "baseline_message": baseline if baseline is not None else "NOT_AVAILABLE"}

    def audit(self, **kw) -> AuditResult:
        req = self.request(**kw)
        manifest: Manifest = kw["manifest"]
        messages = [{"role": "system", "content": ROLE_B_SYSTEM},
                    {"role": "user", "content": json.dumps(req, ensure_ascii=False, sort_keys=True)}]
        raw = self.model.complete(messages, role=ROLE_AUDITOR)
        self.calls += 1
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError
        except (TypeError, ValueError):
            data = {}
        answers = {q: (data.get(q) if data.get(q) in allowed else INVALID) for q, allowed in QUESTIONS.items()}
        notes = {n: str(data.get(n, ""))[:500] for n in NOTES}
        # Code, not the model, decides whether a later move can count against the message.
        verdict = "FORWARD_CLAIM_PRESENT_NOT_GRADED_V0" if forward_claim_present(manifest) else NO_DIRECTIONAL_CLAIM
        return AuditResult(kw["item"].item_id, answers, notes, verdict,
                           sum(1 for c in manifest.claims if c.status == CONTRADICTED), raw)


@dataclass(frozen=True)
class JudgeResult:
    item_id: str
    pair_kind: str
    a_identity: str
    b_identity: str
    preferred_side: str
    preferred_identity: str
    raw: str

    def as_dict(self) -> dict:
        return asdict(self)


class LeakToJudge(AssertionError):
    pass


def assert_blind(payload: Mapping) -> None:
    for k in ("option_a", "option_b"):
        if _IDENTITY_WORDS.search(payload[k]):
            raise LeakToJudge(f"{k} names its source")
    if set(payload) != {"option_a", "option_b", "what_followed"}:
        raise LeakToJudge("judge payload carries extra fields")


class BlindJudge:
    def __init__(self, model: ChatModel, *, seed: int):
        self.model, self.seed = model, seed
        self.calls = 0

    def assign(self, item_id: str, pair_kind: str) -> bool:
        """True when the first identity of the pair goes to side A."""
        return random.Random(f"{self.seed}:{item_id}:{pair_kind}").random() < 0.5

    def judge(self, *, item_id: str, pair_kind: str, signalbot: str, baseline: str,
              observations: Sequence[Observation]) -> JudgeResult:
        first, second = {PAIR_SIGNALBOT_VS_BASELINE: ((SIGNALBOT, signalbot), (BASELINE, baseline)),
                         PAIR_BASELINE_VS_BASELINE: ((BASELINE, baseline), (BASELINE, baseline)),
                         PAIR_SIGNALBOT_VS_SIGNALBOT: ((SIGNALBOT, signalbot), (SIGNALBOT, signalbot))}[pair_kind]
        a, b = (first, second) if self.assign(item_id, pair_kind) else (second, first)
        payload = {"option_a": a[1], "option_b": b[1], "what_followed": outcome_summary(observations)}
        assert_blind(payload)
        messages = [{"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}]
        raw = self.model.complete(messages, role=ROLE_JUDGE)
        self.calls += 1
        try:
            pref = json.loads(raw).get("preferred")
        except (TypeError, ValueError, AttributeError):
            pref = None
        side = pref if pref in ("A", "B", "TIE") else INVALID
        ident = {"A": a[0], "B": b[0], "TIE": TIE}.get(side, INVALID)
        return JudgeResult(item_id, pair_kind, a[0], b[0], side, ident, raw)


def summarize_judgements(results: Sequence[JudgeResult]) -> dict:
    out: dict = {}
    for kind in PAIR_KINDS:
        rs = [r for r in results if r.pair_kind == kind]
        sides = {s: sum(1 for r in rs if r.preferred_side == s) for s in ("A", "B", "TIE", INVALID)}
        decided = sides["A"] + sides["B"]
        row = {"n": len(rs), "side_counts": sides,
               "side_a_share_of_decided": None if decided == 0 else round(sides["A"] / decided, 3)}
        if kind == PAIR_SIGNALBOT_VS_BASELINE:
            row["identity_counts"] = {i: sum(1 for r in rs if r.preferred_identity == i)
                                      for i in (SIGNALBOT, BASELINE, TIE, INVALID)}
        else:
            row["non_tie_rate_on_identical_pair"] = None if not rs else round(decided / len(rs), 3)
        out[kind] = row
    allr = [r for r in results if r.preferred_side in ("A", "B")]
    out["side_bias_all_pairs"] = {"decided": len(allr), "side_a_share": None if not allr else
                                  round(sum(1 for r in allr if r.preferred_side == "A") / len(allr), 3)}
    out["note"] = ("Descriptive counts only; no composite score. A non-tie on an identical pair is "
                   "side or noise preference, so differences of that size are not interpretable.")
    return out


def summarize_audits(results: Sequence[AuditResult]) -> dict:
    out = {q: {v: sum(1 for r in results if r.answers[q] == v) for v in (*allowed, INVALID)}
           for q, allowed in QUESTIONS.items()}
    out["n"] = len(results)
    out["forward_outcome_verdicts"] = {v: sum(1 for r in results if r.forward_outcome_verdict == v)
                                       for v in sorted({r.forward_outcome_verdict for r in results})}
    return out
