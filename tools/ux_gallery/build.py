"""Build the Pulsy UX V2 gallery: one self-contained HTML file, Telegram-style bubbles at ~360 px and wide,
RU and EN, all three levels (L1 summary / L2 «Почему так?» / L3 «Данные»), with buttons that switch levels in-page.

Input:
- REAL: the owner's `/admin_export_views` JSON (`--export`), each state labelled with its snapshot time;
- SYNTHETIC: views from `tools/beta_user_sim` (`make_synthetic_bundle`), labelled synthetic.
Together 15–20 market states (`--states`).

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
from beta.ux_preview import card_facts

LANGS = ("ru", "en")
MAX_REAL = 10


def _view_state(payload: dict, label: str, *, brief: bool = False) -> dict:
    f = from_view(payload)
    if brief:
        return {"label": label, "screens": {"brief": f}}
    screens = {"btc": f, "levels": f}
    card = card_facts(f)
    if card is not None:
        screens["level_card"] = card
    return {"label": label, "screens": screens}


def real_states(doc: Optional[dict]) -> list:
    """REAL states from the owner's export, each labelled with its snapshot time."""
    if not doc:
        return []
    out = []
    for v in doc.get("views") or []:
        out.append(_view_state(v.get("payload") or {}, f"REAL · view {v.get('kind', 'btc')} · {v.get('requested_at')}",
                               brief=v.get("kind") == "brief"))
    for a in doc.get("alerts") or []:
        if a.get("kind") in ("level", "move"):
            out.append({"label": f"REAL · alert {a['kind']} · {a.get('decision_ts')}",
                        "screens": {a["kind"]: from_alert(a["kind"], a.get("payload") or {})}})
    for p in doc.get("pushes") or []:
        if p.get("gate"):
            ep = p.get("episode") or {}
            out.append({"label": f"REAL · push {p.get('event_type')} · {p.get('decision_ts')}",
                        "screens": {"hour": from_hour_gate(ep.get("triggered_at"), p["gate"])}})
    return out[:MAX_REAL]


def synthetic_states(n: int) -> list:
    """SYNTHETIC states: views from tools/beta_user_sim (no market data)."""
    if n <= 0:
        return []
    from beta.config import BetaConfig
    from tools.beta_user_sim.synthetic import make_synthetic_bundle
    views = make_synthetic_bundle(BetaConfig.load(), langs=("ru",))["btc_views"]
    step = max(1, len(views) // n)
    return [_view_state(v["payload"], f"SYNTHETIC · tools/beta_user_sim · {v['payload'].get('as_of_bucket')}")
            for v in views[::step][:n]]


def _panels(gid: str, state: dict, lang: str) -> str:
    """Every (screen, level) of the state as a panel; a button whose `ux:<screen>:<level>` is in the state
    switches panels in-page, any other is shown disabled. A screen the render cannot draw is named, not hidden."""
    have = {(s, lv) for s in state["screens"] for lv in SCREENS[s]}
    first = min(have, key=lambda k: (list(state["screens"]).index(k[0]), k[1]))
    parts = []
    for screen, level in sorted(have, key=lambda k: (list(state["screens"]).index(k[0]), k[1])):
        try:
            text, buttons = render(screen, level, lang, state["screens"][screen])
        except Exception as exc:  # noqa: BLE001 - a P0 template gap stays visible in the gallery
            text, buttons = f"<i>{screen} L{level}: render failed ({html.escape(type(exc).__name__)})</i>", []
        rows = []
        for row in buttons or []:
            cells = []
            for label, data in row:
                key = tuple(str(data).split(":")[1:3]) if str(data).startswith("ux:") else None
                target = (key[0], int(key[1])) if key and key[1].isdigit() else None
                cells.append(f"<button onclick=\"show('{gid}','{target[0]}-{target[1]}')\">{html.escape(label)}</button>"
                             if target in have else f"<button disabled>{html.escape(label)}</button>")
            rows.append("<div class='row'>" + "".join(cells) + "</div>")
        hidden = "" if (screen, level) == first else " hidden"
        parts.append(f"<div class='lvl{hidden}' data-g='{gid}' data-l='{screen}-{level}'>"
                     f"<div class='scr'>{screen} · L{level}</div><div class='msg'>{text}</div>{''.join(rows)}</div>")
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
.tag,.scr{font-size:11px;color:var(--muted)}.msg{white-space:pre-wrap;word-wrap:break-word}
pre{white-space:pre-wrap;font-size:12px}.row{display:flex;gap:6px;margin-top:6px}
button{flex:1;border:0;border-radius:8px;padding:8px;background:var(--btn);color:var(--accent);font:inherit;cursor:pointer}
.hidden{display:none}</style></head><body><h1>Pulsy UX V2 gallery</h1>
<p class="label">L1 summary · L2 «Почему так?» · L3 «Данные». Renderer: __RENDERER__. __COUNTS__</p>
__BODY__
<script>function show(g,l){document.querySelectorAll('[data-g="'+g+'"]').forEach(function(e){
e.classList.toggle('hidden',e.dataset.l!==l)})}</script></body></html>"""


def build(states: list) -> str:
    body = []
    for i, st in enumerate(states):
        cols = []
        for width in ("narrow", "wide"):
            cols.append(f"<div class='col {width}'>" + "".join(_panels(f"s{i}{width[0]}{lang}", st, lang)
                                                               for lang in LANGS) + "</div>")
        body.append(f"<section class='state'><div class='label'>{html.escape(st['label'])}</div>"
                    f"<div class='grid'>{''.join(cols)}</div></section>")
    real = sum(1 for s in states if s["label"].startswith("REAL"))
    return (PAGE.replace("__RENDERER__", "beta.ux.render")
            .replace("__COUNTS__", f"{len(states)} states: {real} real, {len(states) - real} synthetic.")
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
    synthetic = synthetic_states(a.states)
    states = real + synthetic[:max(0, a.states - len(real))]
    a.out.write_text(build(states), encoding="utf-8")
    print(f"{a.out}: {len(states)} states ({len(real)} real)")
    if a.synthetic_out:
        a.synthetic_out.write_text(build(synthetic), encoding="utf-8")
        print(f"{a.synthetic_out}: {len(synthetic)} synthetic states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
