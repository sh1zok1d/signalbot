"""Build the Pulsy UX V2 gallery: one self-contained HTML file, Telegram-style bubbles at ~360 px and wide,
RU and EN, all three levels (L1 summary / L2 «Почему так?» / L3 «Данные»), with buttons that switch levels in-page.

Input:
- REAL: the owner's `/admin_export_views` JSON (`--export`), each state labelled with its snapshot time;
- SYNTHETIC: views from `tools/beta_user_sim` (`make_synthetic_bundle`), labelled synthetic.
Together 15–20 market states (`--states`).

Rendering is `beta.ux.render(screen, level, lang, facts)` (track A); until it lands, `beta.ux_preview.stub_render`.
Usage: python -m tools.ux_gallery.build [--export pulsy_views.json] [--out ux_gallery.html] [--states 18]
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Optional

from beta.ux_preview import LEVELS, renderer

LANGS = ("ru", "en")
MAX_REAL = 10


def real_states(doc: Optional[dict]) -> list:
    if not doc:
        return []
    out = []
    for v in doc.get("views") or []:
        out.append({"screen": "brief" if v.get("kind") == "brief" else "btc", "facts": v.get("payload") or {},
                    "label": f"REAL · view {v.get('kind', 'btc')} · {v.get('requested_at')}"})
    for a in doc.get("alerts") or []:
        out.append({"screen": "alert", "facts": {"kind": a.get("kind"), "payload": a.get("payload") or {}},
                    "label": f"REAL · alert {a.get('kind')} · {a.get('decision_ts')}"})
    for p in doc.get("pushes") or []:
        out.append({"screen": "push", "facts": {"gate": p.get("gate"), "episode": p.get("episode")},
                    "label": f"REAL · push {p.get('event_type')} · {p.get('decision_ts')}"})
    return out[:MAX_REAL]


def synthetic_states(n: int) -> list:
    if n <= 0:
        return []
    from beta.config import BetaConfig
    from tools.beta_user_sim.synthetic import make_synthetic_bundle
    views = [v for v in make_synthetic_bundle(BetaConfig.load(), langs=("ru",))["btc_views"]]
    step = max(1, len(views) // n)
    return [{"screen": "btc", "facts": v["payload"],
             "label": f"SYNTHETIC · tools/beta_user_sim · {v['payload'].get('as_of_bucket')}"}
            for v in views[::step][:n]]


def _bubble(sid: str, state: dict, lang: str, render) -> str:
    parts = []
    for level in LEVELS:
        text, buttons = render(state["screen"], level, lang, state["facts"])
        rows = "".join(
            "<div class='row'>" + "".join(
                f"<button onclick=\"show('{sid}-{lang}','{t}')\">{html.escape(label)}</button>"
                if t in LEVELS else f"<button disabled>{html.escape(label)}</button>"
                for label, t in row) + "</div>"
            for row in (buttons or []))
        hidden = "" if level == "l1" else " hidden"
        parts.append(f"<div class='lvl{hidden}' data-g='{sid}-{lang}' data-l='{level}'>"
                     f"<div class='msg'>{text}</div>{rows}</div>")
    return f"<div class='bubble'><div class='tag'>{lang.upper()}</div>{''.join(parts)}</div>"


PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pulsy UX V2 gallery</title><style>
:root{--bg:#e6ebee;--bubble:#fff;--ink:#111;--muted:#6b7a86;--btn:#f0f4f7;--accent:#2a7ab0}
@media (prefers-color-scheme:dark){:root{--bg:#0e1621;--bubble:#182533;--ink:#e8edf2;--muted:#8a9aa9;--btn:#24384b;--accent:#6ab3f3}}
body{margin:0;padding:16px;background:var(--bg);color:var(--ink);font:15px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}
h1{font-size:18px}.state{margin:24px 0;border-top:1px solid var(--muted);padding-top:12px}
.label{color:var(--muted);font-size:13px;margin-bottom:8px}.grid{display:flex;flex-wrap:wrap;gap:16px}
.col{flex:0 0 auto}.col.narrow .bubble{width:360px;max-width:100%}.col.wide .bubble{width:640px;max-width:100%}
.bubble{background:var(--bubble);border-radius:12px;padding:10px 12px;box-shadow:0 1px 2px #0002;box-sizing:border-box}
.tag{font-size:11px;color:var(--muted)}.msg{white-space:pre-wrap;word-wrap:break-word}
pre{white-space:pre-wrap;font-size:12px}.row{display:flex;gap:6px;margin-top:6px}
button{flex:1;border:0;border-radius:8px;padding:8px;background:var(--btn);color:var(--accent);font:inherit;cursor:pointer}
.hidden{display:none}</style></head><body><h1>Pulsy UX V2 gallery</h1>
<p class="label">L1 summary · L2 «Почему так?» · L3 «Данные». Renderer: __RENDERER__. __COUNTS__</p>
__BODY__
<script>function show(g,l){document.querySelectorAll('[data-g="'+g+'"]').forEach(function(e){
e.classList.toggle('hidden',e.dataset.l!==l)})}</script></body></html>"""


def build(states: list) -> str:
    render = renderer()
    body = []
    for i, st in enumerate(states):
        cols = []
        for width in ("narrow", "wide"):
            sid = f"s{i}{width[0]}"
            cols.append(f"<div class='col {width}'>" + "".join(_bubble(sid, st, lang, render) for lang in LANGS)
                        + "</div>")
        body.append(f"<section class='state'><div class='label'>{html.escape(st['label'])} · screen "
                    f"{html.escape(st['screen'])}</div><div class='grid'>{''.join(cols)}</div></section>")
    real = sum(1 for s in states if s["label"].startswith("REAL"))
    name = f"{render.__module__}.{render.__name__}"
    return (PAGE.replace("__RENDERER__", html.escape(name))
            .replace("__COUNTS__", f"{len(states)} states: {real} real, {len(states) - real} synthetic.")
            .replace("__BODY__", "\n".join(body)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", type=Path)
    ap.add_argument("--out", type=Path, default=Path("ux_gallery.html"))
    ap.add_argument("--states", type=int, default=18)
    a = ap.parse_args(argv)
    doc: Any = json.loads(a.export.read_text(encoding="utf-8")) if a.export else None
    real = real_states(doc)
    states = real + synthetic_states(max(0, a.states - len(real)))
    a.out.write_text(build(states), encoding="utf-8")
    print(f"{a.out}: {len(states)} states ({len(real)} real)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
