"""Pulsy UX V2 (docs/PULSY_UX_STANDARD_V2.md): three levels per screen on a deterministic
facts → salience → phrases → render pipeline. P0: not wired to any user surface; `ux.v2_enabled`
(config/beta_v0.yaml) is off. The stable API for track B is `render`."""
from .facts import FACTS_VERSION, facts_equivalent, from_alert, from_hour_gate, from_view
from .render import SCREENS, UX_VERSION, enabled, render

__all__ = ["FACTS_VERSION", "SCREENS", "UX_VERSION", "enabled", "facts_equivalent", "from_alert", "from_hour_gate",
           "from_view", "render"]
