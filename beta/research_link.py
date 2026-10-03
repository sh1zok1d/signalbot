"""The bridge between the research record and the bot (PRODUCT_DECISION_V2 §2.4).

`config/beta_research_findings.yaml` lists closed research units in trader language: what was
tested, on which data, the frozen verdict, and the contexts where the result is relevant
(a 1h / 4h state label, a level kind, an event kind, a sharp move, the corridor, weekends …).
The bot shows one short "Проверено: …" line in the matching context and lists everything in
/research — the confirmed results, the beliefs that did not hold up, and the side findings of
hypotheses that missed their own target.

Rules: a finding's text states only what its record states; it carries its unit id so it can be
traced; it never turns a research null into a trade call. When a research unit closes, its
entry is added here (AGENTS.md).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import yaml

from .i18n import assert_descriptive, t

FINDINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "beta_research_findings.yaml"
REPO_ROOT = Path(__file__).resolve().parent.parent
# CONFIRMED: replicated on an independent surface; DISCOVERY: one run, not replicated; WEAK: the
# effect is there but below the frozen materiality bar; NOT_CONFIRMED: the tested belief failed;
# SIDE_FINDING: the hypothesis failed but the record states something else; UNDERPOWERED: too
# few cases for any verdict (shown only in /research, never as «Проверено»).
STATUSES = ("CONFIRMED", "DISCOVERY", "WEAK", "NOT_CONFIRMED", "SIDE_FINDING", "UNDERPOWERED")
CONTEXT_STATUSES = ("CONFIRMED", "DISCOVERY", "WEAK", "NOT_CONFIRMED", "SIDE_FINDING")
MAX_TEXT = 220


class FindingsError(ValueError):
    pass


@lru_cache(maxsize=2)
def _load(path: str, mtime: float) -> tuple:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    out = []
    for f in raw.get("findings") or ():
        rec = dict(f)
        if rec.get("status") not in STATUSES:
            raise FindingsError(f"{rec.get('id')}: unknown status {rec.get('status')!r}")
        for key in ("id", "text_ru", "text_en", "record", "data"):
            if not rec.get(key):
                raise FindingsError(f"{rec.get('id')}: missing {key}")
        rec["contexts"] = tuple(rec.get("contexts") or ())
        rec["priority"] = int(rec.get("priority", 50))
        out.append(rec)
    return tuple(out)


def load_findings(path: Optional[Path] = None) -> tuple:
    p = Path(path or FINDINGS_PATH)
    return _load(str(p), p.stat().st_mtime)


def validate(findings: Iterable[Mapping[str, Any]]) -> list:
    """Problems with the registry (empty when it is sound)."""
    problems, seen = [], set()
    for f in findings:
        fid = f["id"]
        if fid in seen:
            problems.append(f"{fid}: duplicate id")
        seen.add(fid)
        for lang in ("ru", "en"):
            text = f[f"text_{lang}"]
            if len(text) > MAX_TEXT:
                problems.append(f"{fid}: text_{lang} longer than {MAX_TEXT}")
            try:
                assert_descriptive(text, lang)
            except ValueError as exc:
                problems.append(f"{fid}: text_{lang} {exc}")
        if not f.get("pending_merge"):
            for rel in str(f["record"]).split(";"):
                if not (REPO_ROOT / rel.strip()).exists():
                    problems.append(f"{fid}: record {rel.strip()} not found")
    return problems


def for_context(context: str, findings: Optional[Iterable[Mapping[str, Any]]] = None) -> list:
    fs = load_findings() if findings is None else findings
    return sorted((f for f in fs if context in f["contexts"] and f["status"] in CONTEXT_STATUSES),
                  key=lambda f: (f["priority"], f["id"]))


def context_line(contexts: Iterable[str], lang: str,
                 findings: Optional[Iterable[Mapping[str, Any]]] = None) -> Optional[str]:
    """The single most relevant "Проверено: …" line for the first context that has one."""
    for c in contexts:
        hits = for_context(c, findings)
        if hits:
            f = hits[0]
            return t(lang, "rs_line", text=f[f"text_{lang}"], id=f["id"])
    return None


def label_contexts(window: str, key: Optional[str]) -> list:
    if not key:
        return []
    return [f"label:{window}:{key}", f"label:{key}"]


TELEGRAM_SAFE_CHARS = 3800          # Telegram's limit is 4096; leave room for entities


def format_research(lang: str, findings: Optional[Iterable[Mapping[str, Any]]] = None,
                    limit: int = TELEGRAM_SAFE_CHARS) -> list:
    """/research as one or more messages, each under `limit` characters, split between status
    groups (or between items of a long group); the title opens the first, the footer closes the last."""
    fs = list(load_findings() if findings is None else findings)
    blocks = []
    for status in STATUSES:
        group = sorted((f for f in fs if f["status"] == status), key=lambda f: (f["priority"], f["id"]))
        if group:
            blocks.append([t(lang, "rs_group_" + status.lower())] +
                          [t(lang, "rs_item", text=f[f"text_{lang}"], id=f["id"], data=f["data"]) for f in group])
    parts, cur = [], [t(lang, "rs_title")]

    def fits(lines):
        return len("\n".join(lines)) <= limit

    for block in blocks:
        head, items = block[0], block[1:]
        for k, line in enumerate(items):
            add = (["", head] if k == 0 else []) + [line]
            if fits(cur + add):
                cur += add
                continue
            parts.append(cur)                       # a new message; a split group says so
            cur = [head if k == 0 else f"{head} {t(lang, 'rs_continued')}", line]
    footer = t(lang, "rs_footer")
    if fits(cur + ["", footer]):
        cur += ["", footer]
    else:
        parts.append(cur)
        cur = [footer]
    parts.append(cur)
    return [assert_descriptive("\n".join(p), lang) for p in parts]
