"""CLI. Offline by default; the fake models need no network and no credentials.

    python -m tools.beta_user_sim make-synthetic-bundle --out /tmp/sim/bundle.json
    python -m tools.beta_user_sim replay --bundle /tmp/sim/bundle.json --out /tmp/sim/run --model fake
    python -m tools.beta_user_sim export --dsn-env BETA_SIM_EXPORT_DSN --start ... --end ... --out ... [--beta-live-window]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from beta.config import BetaConfig

from .attention import AttentionConfig
from .bundle import bundle_from_dict, canonical, load_bundle, parse_ts, write_bundle
from .llm import build_models
from .replay import ReplayConfig, run_replay
from .report import build_report, render_markdown, render_transcript


def _ts(s: str) -> datetime:
    return parse_ts(s)


def _make(args) -> int:
    from .synthetic import make_synthetic_bundle
    raw = make_synthetic_bundle(BetaConfig.load(), langs=tuple(args.langs.split(",")))
    bundle_from_dict(raw)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    write_bundle(raw, Path(args.out))
    print(f"wrote {args.out} (FULLY_SYNTHETIC)")
    return 0


def _replay(args) -> int:
    cfg = BetaConfig.load()
    bundle = load_bundle(Path(args.bundle))
    models = build_models(args.model, model_id=args.model_id, allow_network=args.allow_network, seed=args.model_seed)
    rcfg = ReplayConfig(lang=args.lang, start=_ts(args.start) if args.start else None,
                        end=_ts(args.end) if args.end else None, btc_max_wait_min=args.btc_max_wait_min,
                        replay_seed=args.replay_seed, judge_seed=args.judge_seed,
                        attention=AttentionConfig(seed=args.attention_seed))
    result = run_replay(bundle, cfg, models, rcfg)
    report = build_report(result)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(canonical(result), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True, default=str),
                                     encoding="utf-8")
    (out / "report.md").write_text(render_markdown(report), encoding="utf-8")
    (out / "transcript.md").write_text(render_transcript(result), encoding="utf-8")
    print(f"wrote {out}/run.json report.json report.md transcript.md ({result['status']})")
    return 0


def _export(args) -> int:
    from .export import ExportRefused, connect_kwargs, export_bundle, export_scope
    cfg = BetaConfig.load()
    start, end = _ts(args.start), _ts(args.end)
    try:
        scope = export_scope(start, end, allow_live_beta_window=args.allow_live_beta_window)
        kwargs = connect_kwargs(os.environ.get(args.dsn_env))
    except ExportRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    async def run():
        import asyncpg
        conn = await asyncpg.connect(**kwargs)
        try:
            return await export_bundle(conn, cfg, start=start, end=end,
                                       allow_live_beta_window=args.allow_live_beta_window)
        finally:
            await conn.close()

    raw = asyncio.run(run())
    bundle_from_dict(raw)
    write_bundle(raw, Path(args.out))
    print(f"wrote {args.out} (EXPORTED_READ_ONLY, {scope})")
    return 0


def main(argv=None) -> int:
    from beta.pseudonym import install_key, key_installed
    if not key_installed():                # synthetic participants only: a fixed simulation key, never the beta's
        import hashlib
        install_key(hashlib.sha256(b"SYNTHETIC_BETA_USER_V0 pseudonym key (no real participants)").digest())
    p = argparse.ArgumentParser(prog="python -m tools.beta_user_sim",
                                description="SYNTHETIC_BETA_USER_V0 (offline, SYNTHETIC / DESCRIPTIVE_MONITORING)")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make-synthetic-bundle")
    m.add_argument("--out", required=True)
    m.add_argument("--langs", default="ru,en")
    r = sub.add_parser("replay")
    r.add_argument("--bundle", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--lang", default="ru", choices=("ru", "en"))
    r.add_argument("--model", default="fake", choices=("fake", "openai"))
    r.add_argument("--model-id")
    r.add_argument("--model-seed", type=int)
    r.add_argument("--allow-network", action="store_true")
    r.add_argument("--start")
    r.add_argument("--end")
    r.add_argument("--btc-max-wait-min", type=int, default=10)
    r.add_argument("--replay-seed", type=int, default=1)
    r.add_argument("--attention-seed", type=int, default=7)
    r.add_argument("--judge-seed", type=int, default=11)
    e = sub.add_parser("export")
    e.add_argument("--dsn-env", required=True)
    e.add_argument("--start", required=True)
    e.add_argument("--end", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--beta-live-window", dest="allow_live_beta_window", action="store_true",
                   help="export scope LIVE_BETA_PROSPECTIVE: prospective private-beta operation from "
                        "2026-09-25 only; sealed 2025/2026 research data is never exportable")
    args = p.parse_args(argv)
    return {"make-synthetic-bundle": _make, "replay": _replay, "export": _export}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
