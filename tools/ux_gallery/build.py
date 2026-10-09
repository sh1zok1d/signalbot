"""Build the Pulsy UX V2 gallery: one self-contained HTML file, Telegram-style bubbles at ~360 px and wide,
RU and EN, all three levels (L1 summary / L2 «Почему так?» / L3 «Данные»), with buttons that switch levels in-page.

Input:
- REAL: the owner's `/admin_export_views` JSON (`--export`), each state labelled with its snapshot time;
- SYNTHETIC: the 18 named states of `tools/ux_gallery/states.py` (each with levels), labelled synthetic.
Each screen has a stable id (`S07-btc-L2-ru`); a contents list (state × screen) is at the top.

Rendering is track A's `beta.ux.render(screen, level, lang, facts)` on `from_view` / `from_alert` / `from_hour_gate`.
Usage: python -m tools.ux_gallery.build [--export pulsy_views.json] [--out ux_gallery.html] [--states 18]
       [--synthetic-out ux_gallery_synthetic.html]
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Optional

from beta.ux import SCREENS, from_alert, from_hour_gate, from_view, render
from tools.ux_gallery.states import named_states

LANGS = ("ru", "en")
MAX_REAL = 10


def _view_screens(payload: dict, *, brief: bool = False) -> dict:
    f = from_view(payload)
    if brief:
        return {"brief": f}
    return {"btc": f, "levels": f, "level_card": f}


def real_states(doc: Optional[dict]) -> list:
    """REAL states from the owner's export, each labelled with its snapshot time: [{sid, label, screens}]."""
    if not doc:
        return []
    out = []
    for v in doc.get("views") or []:
        out.append((f"REAL · view {v.get('kind', 'btc')} · {v.get('requested_at')}",
                    _view_screens(v.get("payload") or {}, brief=v.get("kind") == "brief")))
    for a in doc.get("alerts") or []:
        if a.get("kind") in ("level", "move"):
            out.append((f"REAL · alert {a['kind']} · {a.get('decision_ts')}",
                        {a["kind"]: from_alert(a["kind"], a.get("payload") or {})}))
    for p in doc.get("pushes") or []:
        if p.get("gate"):
            ep = p.get("episode") or {}
            out.append((f"REAL · push {p.get('event_type')} · {p.get('decision_ts')}",
                        {"hour": from_hour_gate(ep.get("triggered_at"), p["gate"])}))
    return [{"sid": f"R{i:02d}", "label": label, "screens": scr} for i, (label, scr) in enumerate(out[:MAX_REAL], 1)]


def synthetic_states(n: int = 18) -> list:
    return [{"sid": sid, "label": f"SYNTHETIC · {name}", "screens": scr} for sid, name, scr in named_states()[:n]]


def _keys(state: dict) -> list:
    order = list(state["screens"])
    return sorted({(s, lv) for s in state["screens"] for lv in SCREENS[s]}, key=lambda k: (order.index(k[0]), k[1]))


def panel_id(sid: str, screen: str, level: int, lang: str) -> str:
    return f"{sid}-{screen}-L{level}-{lang}"


def render_panels(state: dict, lang: str) -> list:
    """[(screen, level, panel id, html, buttons)] of a state in one language; a render failure stays visible."""
    out = []
    for screen, level in _keys(state):
        try:
            text, buttons = render(screen, level, lang, state["screens"][screen])
        except Exception as exc:  # noqa: BLE001 - a P0 template gap stays visible in the gallery
            text, buttons = f"<i>{screen} L{level}: render failed ({html.escape(type(exc).__name__)})</i>", []
        out.append((screen, level, panel_id(state["sid"], screen, level, lang), text, buttons or []))
    return out


def _bubble(state: dict, lang: str, width: str) -> str:
    have = set(_keys(state))
    first = _keys(state)[0]
    gid = f"{state['sid']}-{lang}-{width}"
    parts = []
    for screen, level, pid, text, buttons in render_panels(state, lang):
        rows = []
        for row in buttons:
            cells = []
            for label, data in row:
                key = tuple(str(data).split(":")[1:3]) if str(data).startswith("ux:") else None
                target = (key[0], int(key[1])) if key and key[1].isdigit() else None
                cells.append(f"<button onclick=\"show('{gid}','{target[0]}-{target[1]}')\">{html.escape(label)}</button>"
                             if target in have else f"<button disabled>{html.escape(label)}</button>")
            rows.append("<div class='row'>" + "".join(cells) + "</div>")
        hidden = "" if (screen, level) == first else " hidden"
        anchor = f" id='{pid}'" if width == "narrow" else f" id='{pid}-wide'"
        parts.append(f"<div class='lvl{hidden}'{anchor} data-g='{gid}' data-l='{screen}-{level}'>"
                     f"<div class='scr'>{pid}</div><div class='msg'>{text}</div>{''.join(rows)}</div>")
    return f"<div class='bubble'><div class='tag'>{lang.upper()} · {width}</div>{''.join(parts)}</div>"


PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pulsy UX V2 gallery</title><style>
:root{--bg:#e6ebee;--bubble:#fff;--ink:#111;--muted:#6b7a86;--btn:#f0f4f7;--accent:#2a7ab0}
@media (prefers-color-scheme:dark){:root{--bg:#0e1621;--bubble:#182533;--ink:#e8edf2;--muted:#8a9aa9;--btn:#24384b;--accent:#6ab3f3}}
body{margin:0;padding:16px;background:var(--bg);color:var(--ink);font:15px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}
h1{font-size:18px}.state{margin:24px 0;border-top:1px solid var(--muted);padding-top:12px}
.label{color:var(--muted);font-size:13px;margin-bottom:8px}.grid{display:flex;flex-wrap:wrap;gap:16px}
.col{flex:0 0 auto}.col{display:flex;flex-direction:column;gap:12px;min-width:0}.col.narrow{width:360px;max-width:100%}.col.wide{flex:1 1 480px;max-width:720px}
.bubble{max-width:100%;overflow-wrap:anywhere;background:var(--bubble);border-radius:12px;padding:10px 12px;box-shadow:0 1px 2px #0002;box-sizing:border-box}
.tag,.scr{font-size:11px;color:var(--muted)}.msg{white-space:pre-wrap;word-wrap:break-word}
pre{white-space:pre-wrap;font-size:12px}.toc{columns:2 260px;font-size:13px}.toc a{color:var(--accent)}.row{display:flex;gap:6px;margin-top:6px}
button{flex:1;border:0;border-radius:8px;padding:8px;background:var(--btn);color:var(--accent);font:inherit;cursor:pointer}
.hidden{display:none}</style></head><body><h1>Pulsy UX V2 gallery</h1>
<p class="label">L1 summary · L2 «Почему так?» · L3 «Данные». Renderer: __RENDERER__. __COUNTS__</p>
__TOC__
__BODY__
<script>function show(g,l){document.querySelectorAll('[data-g="'+g+'"]').forEach(function(e){
e.classList.toggle('hidden',e.dataset.l!==l)})}</script></body></html>"""


def build(states: list) -> str:
    body, toc = [], []
    for st in states:
        cols = []
        for width in ("narrow", "wide"):
            cols.append(f"<div class='col {width}'>" + "".join(_bubble(st, lang, width) for lang in LANGS) + "</div>")
        body.append(f"<section class='state' id='{st['sid']}'><div class='label'>{st['sid']} · "
                    f"{html.escape(st['label'])}</div><div class='grid'>{''.join(cols)}</div></section>")
        links = " ".join(f"<a href='#{panel_id(st['sid'], s, lv, 'ru')}'>{s} L{lv}</a>" for s, lv in _keys(st))
        toc.append(f"<li><a href='#{st['sid']}'>{st['sid']}</a> {html.escape(st['label'])}: {links}</li>")
    real = sum(1 for s in states if s["label"].startswith("REAL"))
    return (PAGE.replace("__RENDERER__", "beta.ux.render")
            .replace("__COUNTS__", f"{len(states)} states: {real} real, {len(states) - real} synthetic.")
            .replace("__TOC__", "<ul class='toc'>" + "".join(toc) + "</ul>")
            .replace("__BODY__", "\n".join(body)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", type=Path, help="the owner's /admin_export_views JSON (REAL states)")
    ap.add_argument("--out", type=Path, default=Path("ux_gallery.html"))
    ap.add_argument("--states", type=int, default=18)
    ap.add_argument("--synthetic-out", type=Path, help="also write a SYNTHETIC-only draft (internal style review)")
    a = ap.parse_args(argv)
    doc: Any = json.loads(a.export.read_text(encoding="utf-8")) if a.export else None
    real = real_states(doc)
    synthetic = synthetic_states()
    states = real + synthetic[:max(0, a.states - len(real))]
    a.out.write_text(build(states), encoding="utf-8")
    print(f"{a.out}: {len(states)} states ({len(real)} real)")
    if a.synthetic_out:
        a.synthetic_out.write_text(build(synthetic), encoding="utf-8")
        print(f"{a.synthetic_out}: {len(synthetic)} synthetic states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
