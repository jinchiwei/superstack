"""palette.py — per-deck color resolution for build-pptx.

A Palette is the set of *role* colors a slide renderer needs: the canvas
(slide background), primary text, muted/secondary text, card surface fill,
and hairline rule color, plus whether the canvas is dark (so chrome text
inverts). It is resolved once per deck from the active Theme.

LIGHT is the default and MUST equal the exact constants used before theming
existed, so strict mode / no-theme renders are byte-identical to the
pre-feature behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from layouts._common import (
    INK_RGB, WHITE_RGB, MUTED_RGB, RULE_RGB, PAPER_RGB, _rgb,
)


@dataclass(frozen=True)
class Palette:
    canvas_rgb: object      # RGBColor — slide background
    text_rgb: object        # RGBColor — primary body text
    muted_rgb: object       # RGBColor — secondary text / labels
    surface_rgb: object     # RGBColor — card fill
    rule_rgb: object        # RGBColor — hairlines
    on_dark: bool           # True -> chrome text inverts (passed to _add_chrome)


# Exactly today's colors. DO NOT change these values — strict parity depends on it.
LIGHT = Palette(
    canvas_rgb=WHITE_RGB,
    text_rgb=INK_RGB,
    muted_rgb=MUTED_RGB,
    surface_rgb=PAPER_RGB,
    rule_rgb=RULE_RGB,
    on_dark=False,
)


def palette_for_theme(theme) -> Palette:
    """Resolve a Palette from a Theme (or None -> LIGHT).

    Dark themes invert text to white, use a lighter-than-canvas card surface,
    and a dim rule. Light/tinted themes keep dark text but adopt the theme's
    canvas tint.
    """
    if theme is None:
        return LIGHT
    if theme.on_dark:
        return Palette(
            canvas_rgb=_rgb(theme.bg_hex),
            text_rgb=WHITE_RGB,
            muted_rgb=_rgb("#9FB3C8"),
            surface_rgb=_lighten(theme.bg_hex, 0.10),
            rule_rgb=_rgb("#33415C"),
            on_dark=True,
        )
    return Palette(
        canvas_rgb=_rgb(theme.bg_hex),
        text_rgb=INK_RGB,
        muted_rgb=MUTED_RGB,
        surface_rgb=PAPER_RGB,
        rule_rgb=RULE_RGB,
        on_dark=False,
    )


def _lighten(hex_str: str, amount: float):
    """Lighten a hex color toward white by `amount` (0..1). Used for card
    surfaces that must sit a step above a dark canvas."""
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return _rgb(f"#{r:02X}{g:02X}{b:02X}")
