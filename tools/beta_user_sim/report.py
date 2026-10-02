"""Run manifest and descriptive summaries. No composite score, no significance tests.

Every report carries the SYNTHETIC / DESCRIPTIVE_MONITORING labels. It is not
research evidence, not RESEARCH_LEDGER confirmatory evidence, and not an input
to any product, detector, threshold, wording or promotion decision.
"""
from __future__ import annotations

import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .claims import STATUSES, Claim, Manifest
from .role_b import AuditResult, JudgeResult, summarize_audits, summarize_judgements

REPORT_VERSION = "SIM_REPORT_V0"
_KYIV = ZoneInfo("Europe/Kyiv")
_FORBIDDEN_REPORT = re.compile(r"(\bedge\b|predictive|\bPMF\b|product[- ]market fit|p-value|\bux score\b|"
                               r"overall score|willingness to pay|retention rate)", re.IGNORECASE)


class ReportWordingError(AssertionError):
    pass


def code_commit(repo: Optional[Path] = None) -> dict:
    root = repo or Path(__file__).resolve().parents[2]
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "UNKNOWN"
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True,
                                    timeout=10).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        head, dirty = "UNKNOWN", None
    return {"commit": head, "worktree_dirty": dirty}


def _manifests(result: dict) -> list:
    out = []
    for m in result["claim_manifests"]:
        man = Manifest(m["item_id"], m["kind"], m["manifest_version"])
        man.claims = [Claim(**c) for c in m["claims"]]
        out.append(man)
    return out


def claims_summary(result: dict) -> dict:
    total = Counter()
    by_type: dict = {}
    by_class: dict = {}
    for man in _manifests(result):
        for c in man.claims:
            total[c.status] += 1
            by_type.setdefault(c.claim_type, Counter())[c.status] += 1
            by_class.setdefault(c.evaluation_class, Counter())[c.status] += 1
    fill = lambda c: {s: c.get(s, 0) for s in STATUSES}  # noqa: E731
    return {"total_claims": sum(total.values()), **fill(total),
            "by_claim_type": {k: fill(v) for k, v in sorted(by_type.items())},
            "by_evaluation_class": {k: fill(v) for k, v in sorted(by_class.items())}}


def role_a_summary(result: dict) -> dict:
    turns = [e for e in result["transcript"] if e["event"] == "ROLE_A_TURN"]
    shown = result["shown"]
    journal_topics, excluded = Counter(), Counter()
    for d in result["role_a_decisions"]:
        journal_topics.update(d["journal"].keys())
        excluded.update(d["excluded_journal"].values())
    return {
        "turns": len(turns),
        "turns_by_reason": dict(Counter(t["reason"] for t in turns)),
        "actions": dict(Counter(t["action"] for t in turns if t["accepted"])),
        "commands": dict(Counter(t["command"] for t in turns if t["accepted"] and t["command"])),
        "clicks_by_callback_kind": dict(Counter((t["callback"] or "").split(":")[0] for t in turns
                                                if t["accepted"] and t["action"] == "CLICK_BUTTON")),
        "rejected_actions": dict(Counter(t["rejection"] for t in turns if not t["accepted"])),
        "messages_shown_by_kind": dict(Counter(s["kind"] for s in shown)),
        "messages_by_arrival_state": dict(Counter(s["arrived_while"] for s in shown)),
        "turns_with_backlog": sum(1 for t in turns if t["backlog"]),
        "pushes_undelivered": len(result["undelivered"]),
        "unreplayable_actions": dict(Counter(u["reason"].split(";")[0][:80] for u in result["unreplayable"])),
        "journal_topics": dict(journal_topics),
        "journal_excluded": dict(excluded),
        "note": "Synthetic usage of one simulated participant inside an isolated sandbox. Not beta usage.",
    }


def role_b_summary(result: dict) -> dict:
    audits = [AuditResult(**a) for a in result["role_b"]["audits"]]
    judgements = [JudgeResult(**j) for j in result["role_b"]["judgements"]]
    return {"audits": summarize_audits(audits), "blind_comparison": summarize_judgements(judgements),
            "deferred": len(result["role_b"]["deferred"]),
            "ab_not_evaluable": dict(Counter(x["reason"].split(":")[0] for x in result["role_b"]["ab_not_evaluable"])),
            "outcome_anomalies": result["role_b"]["anomalies"]}


def grouped(result: dict) -> dict:
    """Daily (Kyiv date) and ISO-week counts of what Role A saw and did."""
    days: dict = {}
    weeks: dict = {}
    for s in result["shown"]:
        local = datetime.fromisoformat(s["at"]).astimezone(_KYIV)
        for key, store in ((local.date().isoformat(), days), ("%d-W%02d" % local.isocalendar()[:2], weeks)):
            row = store.setdefault(key, {"messages": Counter(), "turns": 0, "actions": Counter()})
            row["messages"][s["kind"]] += 1
    for t in result["transcript"]:
        if t["event"] != "ROLE_A_TURN":
            continue
        local = datetime.fromisoformat(t["t"]).astimezone(_KYIV)
        for key, store in ((local.date().isoformat(), days), ("%d-W%02d" % local.isocalendar()[:2], weeks)):
            row = store.setdefault(key, {"messages": Counter(), "turns": 0, "actions": Counter()})
            row["turns"] += 1
            if t["accepted"]:
                row["actions"][t["action"]] += 1
    plain = lambda store: {k: {"messages": dict(v["messages"]), "turns": v["turns"],  # noqa: E731
                               "actions": dict(v["actions"])} for k, v in sorted(store.items())}
    return {"daily": plain(days), "weekly": plain(weeks)}


def build_report(result: dict, *, run_at: Optional[datetime] = None, commit: Optional[dict] = None) -> dict:
    manifest = {
        "report_version": REPORT_VERSION, "harness_version": result["harness_version"],
        "status": result["status"], "status_labels": result["status_labels"],
        "run_at": (run_at or datetime.now(timezone.utc)).isoformat(),
        "code": commit if commit is not None else code_commit(),
        "engine_version": result["engine_version"], "replay_config": result["replay_config"],
        "window": result["window"], "bundle": result["bundle"],
        "replay_input_ids": result["replay_input_ids"], "skipped_inputs": result["skipped_inputs"],
        "models": result["models"], "prompt_versions": result["prompt_versions"],
        "outcome_version": result["outcome_version"], "outcome_ledger_version": result["outcome_ledger_version"],
        "baseline": result["baseline"],
        "reproducibility": "Deterministic for the fake models. Real models are not bit-identical across runs.",
    }
    return {"manifest": manifest, "role_a": role_a_summary(result), "deterministic_audit": claims_summary(result),
            "role_b": role_b_summary(result), "grouped": grouped(result)}


def _kv(d: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in d.items()) or "none"


def _export_line(export: Optional[dict]) -> str:
    if export is None:
        return "- export scope: none (fully synthetic bundle)"
    return (f"- export scope {export['export_scope']}; authorization {export['authorization_ref'] or 'none'}"
            f" ({export['authority_doc'] or 'n/a'}); requested window {export['requested_start']} → "
            f"{export['requested_end']}; exported at {export['exported_at']}")


def render_markdown(report: dict) -> str:
    m, a, c, b = report["manifest"], report["role_a"], report["deterministic_audit"], report["role_b"]
    bc = b["blind_comparison"]
    lines = [
        f"# Synthetic beta user run — {m['status']}",
        "",
        "Labels: " + ", ".join(m["status_labels"]) + ".",
        "",
        "## Run manifest",
        f"- harness {m['harness_version']}, engine {m['engine_version']}, report {m['report_version']}",
        f"- run at {m['run_at']}; code {m['code']['commit']} (dirty: {m['code']['worktree_dirty']})",
        f"- bundle {m['bundle']['provenance']} digest {m['bundle']['digest']}",
        _export_line(m["bundle"].get("export")),
        f"- window {m['window']['start']} → {m['window']['end']}; lang {m['replay_config']['lang']}",
        f"- seeds: replay {m['replay_config']['replay_seed']}, attention {m['replay_config']['attention']['seed']}, "
        f"judge {m['replay_config']['judge_seed']}",
        f"- models: " + "; ".join(f"{r} {x['model_id']}" for r, x in m["models"].items()),
        f"- prompts: {_kv(m['prompt_versions'])}",
        f"- outcome_version {m['outcome_version']}; baseline {m['baseline']['baseline_version']}",
        f"- replay inputs: {len(m['replay_input_ids'])} ordered ids; skipped {len(m['skipped_inputs'])}",
        f"- {m['reproducibility']}",
        "",
        "## Role A usage (one simulated participant, isolated sandbox)",
        f"- turns {a['turns']} ({_kv(a['turns_by_reason'])}); turns with backlog {a['turns_with_backlog']}",
        f"- accepted actions: {_kv(a['actions'])}; commands: {_kv(a['commands'])}; "
        f"clicks: {_kv(a['clicks_by_callback_kind'])}",
        f"- rejected actions: {_kv(a['rejected_actions'])}; unreplayable: {_kv(a['unreplayable_actions'])}",
        f"- messages shown: {_kv(a['messages_shown_by_kind'])}; by arrival state: {_kv(a['messages_by_arrival_state'])}",
        f"- journal topics: {_kv(a['journal_topics'])}; excluded: {_kv(a['journal_excluded'])}",
        "",
        "## Deterministic claim audit",
        f"- claims {c['total_claims']}: " + _kv({s: c[s] for s in STATUSES}),
        *[f"- {k}: {_kv(v)}" for k, v in c["by_evaluation_class"].items()],
        "",
        "| claim type | " + " | ".join(STATUSES) + " |",
        "|---|" + "---|" * len(STATUSES),
        *[f"| {k} | " + " | ".join(str(v[s]) for s in STATUSES) + " |" for k, v in c["by_claim_type"].items()],
        "",
        "## Role B (after horizons matured)",
        f"- audited {b['audits']['n']}; deferred (horizon not mature at export) {b['deferred']}",
        *[f"- {q}: {_kv(v)}" for q, v in b["audits"].items() if isinstance(v, dict)],
        f"- blind comparison Signalbot vs baseline: {_kv(bc['SIGNALBOT_VS_BASELINE'].get('identity_counts', {}))}",
        f"- control baseline vs baseline: sides {_kv(bc['CONTROL_BASELINE_VS_BASELINE']['side_counts'])}",
        f"- control Signalbot vs Signalbot: sides {_kv(bc['CONTROL_SIGNALBOT_VS_SIGNALBOT']['side_counts'])}",
        f"- side bias over all pairs: {_kv(bc['side_bias_all_pairs'])}",
        f"- A/B not evaluable: {_kv(b['ab_not_evaluable'])}",
        f"- {bc['note']}",
        "",
        "## By day (Kyiv)",
        *[f"- {d}: turns {r['turns']}; messages {_kv(r['messages'])}; actions {_kv(r['actions'])}"
          for d, r in report["grouped"]["daily"].items()],
        "",
        "Synthetic descriptive monitoring of presentation only. Not research evidence, not a ledger entry, "
        "not a basis for changing rules, thresholds, wording, push decisions or promotion.",
        "",
    ]
    text = "\n".join(lines)
    hit = _FORBIDDEN_REPORT.search(text)
    if hit:
        raise ReportWordingError(f"report contains forbidden wording {hit.group(0)!r}")
    return text


def render_transcript(result: dict) -> str:
    out = [f"# Synthetic transcript — {result['status']}", ""]
    for e in [*result["transcript"], *result["phase_b_log"]]:
        head = f"**{e['t']} · {e['event']}**"
        if e["event"] in ("PUSH_ARRIVED", "SERVED_PERSISTED_VIEW", "REPLY"):
            out += [head + f" `{e.get('message_id')}` {e.get('kind', '')} {e.get('arrived_while', '')}".rstrip(),
                    "", "```", e.get("text", ""), "```", ""]
        elif e["event"] == "ROLE_A_TURN":
            act = e["action"] + (f" /{e['command']}" if e.get("command") else "") + \
                (f" {e['button_id']} → {e['callback']}" if e.get("callback") else "")
            out += [head + f" reason {e['reason']}; shown {e['shown']}; backlog {e['backlog']}; "
                    f"notices {e['notices']}; action {act}; accepted {e['accepted']} {e['rejection'] or ''}",
                    *(f"  - journal {k}: {v}" for k, v in e["journal"].items()),
                    *(f"  - excluded {k}: {v}" for k, v in e["excluded_journal"].items()), ""]
        elif e["event"] == "OUTCOME_UNLOCK":
            out += [head + f" {e['item_id']}"]
            out += [f"  - {o['horizon']} {o['status']} range={_r(o['fields'].get('realized_range_pct'))} "
                    f"close={_r(o['fields'].get('close_return_pct'))} up={_r(o['fields'].get('max_up_pct'))} "
                    f"down={_r(o['fields'].get('max_down_pct'))}" for o in e["observations"]]
            out.append("")
        elif e["event"] == "ROLE_B_AUDIT":
            out += [head + f" {e['item_id']} forward verdict {e['forward_outcome_verdict']}; "
                    f"contradicted facts {e['contradicted_facts']}",
                    *(f"  - {k}: {v}" for k, v in e["answers"].items()), ""]
        elif e["event"] == "AB_JUDGE":
            out += [head + f" {e['item_id']} {e['pair_kind']}: A={e['a_identity']} B={e['b_identity']} "
                    f"→ {e['preferred_side']} ({e['preferred_identity']})", ""]
        else:
            out += [head + " " + _kv({k: v for k, v in e.items() if k not in ("t", "event")}), ""]
    return "\n".join(out)


def _r(v) -> str:
    return "n/a" if v is None else f"{v:.2f}%"
