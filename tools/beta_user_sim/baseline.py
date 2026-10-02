"""Deterministic simple-context baseline (frozen, versioned).

A competent plain summary a trader could get from any chart at the same instant:
price, 1h and 24h change, 1h range against its usual size, volume against usual,
and the 24h high/low. It deliberately excludes OI, taker flow, liquidations and
any multi-venue interpretation. Inputs are the as-of fields already in the
persisted /btc view payload, so the baseline never sees anything later than T.

Pushes carry no as-of market context in the replay bundle, so a push baseline is
NOT_EVALUABLE rather than invented.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from beta.i18n import fmt_kyiv_hm, fmt_price, fmt_ratio, fmt_signed_pct

BASELINE_VERSION = "BASELINE_SIMPLE_V0"
BASELINE_INPUTS = ("now.reference_price", "data_through", "horizons.1h.price_move_pct",
                   "horizons.1h.range_width_pct", "horizons.1h.range_ratio", "horizons.1h.volume_ratio",
                   "horizons.24h.price_move_pct", "horizons.24h.high", "horizons.24h.low",
                   "horizons.24h.volume_ratio")
BASELINE_EXCLUDES = ("open interest", "taker flow", "liquidations", "multi-venue interpretation")

_S = {
    "data": {"ru": "данные {hm} (Киев)", "en": "data {hm} Kyiv"},
    "h1": {"ru": "1ч", "en": "1h"},
    "h24": {"ru": "24ч", "en": "24h"},
    "range": {"ru": "диапазон {pct}", "en": "range {pct}"},
    "usual": {"ru": "{ratio} от обычного", "en": "{ratio} of usual"},
    "volume": {"ru": "объём {ratio} от обычного", "en": "volume {ratio} of usual"},
    "hilo": {"ru": "макс {hi} / мин {lo}", "en": "high {hi} / low {lo}"},
    "no_data": {"ru": "нет данных", "en": "no data"},
}


def _s(lang: str, key: str, **kw) -> str:
    return _S[key]["ru" if lang == "ru" else "en"].format(**kw)


def _pct(v: Optional[float], lang: str) -> Optional[str]:
    return None if v is None else fmt_signed_pct(float(v), lang, nd=1)


def _plain_pct(v: float, lang: str) -> str:
    return fmt_signed_pct(float(v), lang, nd=1).lstrip("+")


def _block(payload: Mapping[str, Any], h: str) -> Mapping[str, Any]:
    return ((payload.get("horizons") or {}).get(h)) or {}


def baseline_text(payload: Mapping[str, Any], lang: str) -> Optional[str]:
    """None when the view has neither a price nor a data time (nothing honest to say)."""
    price = (payload.get("now") or {}).get("reference_price")
    through = payload.get("data_through")
    if price is None and through is None:
        return None
    head = ["BTC" + ("" if price is None else " " + fmt_price(price, lang))]
    if through:
        head.append(_s(lang, "data", hm=fmt_kyiv_hm(datetime.fromisoformat(through))))
    lines = [" · ".join(head)]

    b1 = _block(payload, "1h")
    parts = []
    if b1.get("complete") or b1.get("price_move_pct") is not None:
        if (p := _pct(b1.get("price_move_pct"), lang)) is not None:
            parts.append(p)
        if b1.get("range_width_pct") is not None:
            r = _s(lang, "range", pct=_plain_pct(b1["range_width_pct"], lang))
            if b1.get("range_ratio") is not None:
                r += f" ({_s(lang, 'usual', ratio=fmt_ratio(b1['range_ratio'], lang))})"
            parts.append(r)
        if b1.get("volume_ratio") is not None:
            parts.append(_s(lang, "volume", ratio=fmt_ratio(b1["volume_ratio"], lang)))
    lines.append(f"{_s(lang, 'h1')}: " + (", ".join(parts) if parts else _s(lang, "no_data")))

    b24 = _block(payload, "24h")
    parts = []
    if (p := _pct(b24.get("price_move_pct"), lang)) is not None:
        parts.append(p)
    if b24.get("high") is not None and b24.get("low") is not None:
        parts.append(_s(lang, "hilo", hi=fmt_price(b24["high"], lang), lo=fmt_price(b24["low"], lang)))
    if b24.get("volume_ratio") is not None:
        parts.append(_s(lang, "volume", ratio=fmt_ratio(b24["volume_ratio"], lang)))
    lines.append(f"{_s(lang, 'h24')}: " + (", ".join(parts) if parts else _s(lang, "no_data")))
    return "\n".join(lines)


def baseline_meta() -> dict:
    return {"baseline_version": BASELINE_VERSION, "inputs": list(BASELINE_INPUTS),
            "excludes": list(BASELINE_EXCLUDES), "push_baseline": "NOT_EVALUABLE_NO_AS_OF_CONTEXT"}
