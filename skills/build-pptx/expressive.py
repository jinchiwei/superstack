"""expressive.py — expressive-mode-only glue for build-pptx.

Strict mode MUST NOT import or call anything in this module. Keeping the
expressive logic isolated here is the safety boundary: a bug in theming or
guided-freeform selection cannot affect a strict-mode render, which is the
byte-for-byte revert path.
"""

from __future__ import annotations

from plan import Plan
from themes import Theme, get_theme, pick_theme


def resolve_theme(plan: Plan) -> Theme | None:
    """Return the Theme for this plan, or None if not applicable.

    - strict mode -> always None (no theming).
    - expressive mode -> the theme named in the sidecar if present, else a
      deterministic pick seeded by shake_seed (so a deck's theme is stable
      across re-renders but rerolls on --shake).
    """
    if plan.mode != "expressive":
        return None
    if plan.theme:
        return get_theme(plan.theme)
    return pick_theme(plan.shake_seed)
