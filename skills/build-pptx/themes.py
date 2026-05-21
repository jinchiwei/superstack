"""themes.py — named visual themes for build-pptx expressive mode.

A Theme controls the *canvas and supplementary palette*, never the brand
identity. Fonts are always Geist / Geist Mono (enforced elsewhere). The
brand-4 accents (turquoise/deeppink/amber/blueviolet) are always available;
`accent_order` only changes which leads. `supplementary` adds extra hues
(uncapped — planner's discretion) that read well on the theme's canvas.

Theme selection is deterministic: pick_theme(seed) hashes the seed so a
deck's theme is stable across re-renders and rerolls only on --shake.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

TURQUOISE = "#40E0D0"
DEEPPINK = "#FF1493"
AMBER = "#F0C840"
BLUEVIOLET = "#8A2BE2"


@dataclass(frozen=True)
class Theme:
    name: str
    canvas: str          # "light" | "dark" | "tinted"
    bg_hex: str          # full-bleed canvas color
    on_dark: bool        # True -> chrome text inverts to light
    accent_order: list[str] = field(default_factory=list)   # brand-4 permutation
    supplementary: list[str] = field(default_factory=list)  # extra hues (uncapped)


THEMES: dict[str, Theme] = {
    "midnight": Theme(
        name="midnight", canvas="dark", bg_hex="#14141C", on_dark=True,
        accent_order=[TURQUOISE, BLUEVIOLET, DEEPPINK, AMBER],
        supplementary=["#5EEAD4", "#A78BFA", "#FBCFE8"],
    ),
    "slate": Theme(
        name="slate", canvas="dark", bg_hex="#1E293B", on_dark=True,
        accent_order=[TURQUOISE, AMBER, DEEPPINK, BLUEVIOLET],
        supplementary=["#38BDF8", "#FB7185", "#FACC15"],
    ),
    "forest": Theme(
        name="forest", canvas="dark", bg_hex="#0F1E17", on_dark=True,
        accent_order=[AMBER, TURQUOISE, BLUEVIOLET, DEEPPINK],
        supplementary=["#34D399", "#A3E635", "#FDE68A"],
    ),
    "paper": Theme(
        name="paper", canvas="light", bg_hex="#FFFFFF", on_dark=False,
        accent_order=[DEEPPINK, TURQUOISE, BLUEVIOLET, AMBER],
        supplementary=["#0F766E", "#9D174D", "#6D28D9"],
    ),
    "bone": Theme(
        name="bone", canvas="tinted", bg_hex="#F6F4EE", on_dark=False,
        accent_order=[BLUEVIOLET, DEEPPINK, TURQUOISE, AMBER],
        supplementary=["#9A3412", "#1E3A8A", "#115E59"],
    ),
}

_DEFAULT = "midnight"


def get_theme(name: str | None) -> Theme:
    """Look up a theme by name; fall back to the default for unknown/None."""
    if name and name in THEMES:
        return THEMES[name]
    return THEMES[_DEFAULT]


def pick_theme(seed: str | None) -> Theme:
    """Deterministically choose a theme from the seed. None -> default."""
    if not seed:
        return THEMES[_DEFAULT]
    names = sorted(THEMES.keys())
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    return THEMES[names[h % len(names)]]
