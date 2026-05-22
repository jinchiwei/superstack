"""vertical-timeline layout: vertical left-rail with N stage dots, label + body
to the right of each dot.

Use for sequential pipeline / workflow / process slides — when the order matters
and you want the visual rhythm of a timeline rather than a flat card grid.

Sidecar entry shape:
{
  "kind": "vertical-timeline",
  "params": {
    "title": "Pipeline",
    "lede": "Three-stage analysis pipeline from raw DWI to per-region effects.",
    "section_label": "Methods",
    "stages": [
      {"label": "Acquisition",       "body": "ADNI single-shell DWI..."},
      {"label": "FW estimation",     "body": "DL model proxies multishell..."},
      {"label": "Cortical sampling", "body": "Surface-sampled across 11 regions..."},
      ...
    ]
  }
}

Geometry:
  - Vertical rail at left ~1.4in from slide edge
  - N dots evenly spaced along the rail, palette colors cycle
    (turquoise → deeppink → amber → blueviolet)
  - Stage label in Geist Mono right of dot, vertically aligned
  - Stage body in Geist sans, wrapping under the label
  - 3-7 stages supported
"""

from __future__ import annotations

import branding
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from palette import LIGHT

from ._common import (
    _add_chrome,
    _add_rect,
    _add_text,
    _set_bg,
    TURQUOISE_RGB,
    DEEPPINK_RGB,
    AMBER_RGB,
    BLUEVIOLET_RGB,
)


# Visual constants (inches)
_RAIL_WIDTH      = 0.025    # thin rail
_RAIL_LEFT_FRAC  = 0.05     # rail x position as fraction of body width from body_l
_DOT_DIAMETER    = 0.24
_LABEL_LEFT_FRAC = 0.10     # label starts 10% of body width right of rail
_LABEL_SIZE      = 16
_BODY_SIZE       = 12

_PALETTE_CYCLE = [TURQUOISE_RGB, DEEPPINK_RGB, AMBER_RGB, BLUEVIOLET_RGB]


def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict, palette=LIGHT) -> None:
    """Render a vertical-timeline content slide.

    params keys:
        title         (str)
        lede          (str)
        section_label (str)
        stages        list[{"label": str, "body": str}]  — 3-7 items
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    stages = list(params.get("stages") or [])

    title_present = bool(title)
    title_wraps = len(title) > 30 if title_present else False

    _set_bg(slide, palette.canvas_rgb)

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide,
        title=title,
        lede=lede,
        footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=title_present,
        title_wraps=title_wraps,
        use_side_by_side=False,
        on_dark=palette.on_dark,
    )

    n = len(stages)
    if n == 0:
        return
    n = min(n, 7)
    stages = stages[:n]

    # ── Rail geometry ────────────────────────────────────────────────────────
    rail_x = body_l + body_w * _RAIL_LEFT_FRAC
    rail_top = body_top + 0.15
    rail_bot = body_bottom - 0.15
    rail_height = rail_bot - rail_top

    # ── Draw rail ────────────────────────────────────────────────────────────
    _add_rect(
        slide,
        left=rail_x,
        top=rail_top,
        width=_RAIL_WIDTH,
        height=rail_height,
        fill_rgb=palette.rule_rgb,
    )

    # ── Stage spacing ───────────────────────────────────────────────────────
    # n=1 → centered; n>=2 → distributed top-to-bottom
    if n == 1:
        y_positions = [rail_top + rail_height / 2]
    else:
        step = rail_height / (n - 1) if n > 1 else 0
        y_positions = [rail_top + i * step for i in range(n)]

    # Slot height (used to vertically size each stage's text region)
    slot_h = rail_height / n

    # ── Label + body geometry ───────────────────────────────────────────────
    label_left = rail_x + body_w * _LABEL_LEFT_FRAC
    label_w = body_w - (label_left - body_l) - 0.1
    label_h = 0.4
    body_text_top_offset = 0.42  # body text sits this far below dot center
    body_text_h = max(0.3, slot_h - body_text_top_offset - 0.1)

    # ── Render each stage ───────────────────────────────────────────────────
    for i, stage in enumerate(stages):
        dot_color = _PALETTE_CYCLE[i % len(_PALETTE_CYCLE)]
        cy = y_positions[i]

        # Dot — centered on rail x, vertically on cy
        dot_left = rail_x + _RAIL_WIDTH / 2 - _DOT_DIAMETER / 2
        dot_top = cy - _DOT_DIAMETER / 2
        dot = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(dot_left),
            Inches(dot_top),
            Inches(_DOT_DIAMETER),
            Inches(_DOT_DIAMETER),
        )
        dot.line.fill.background()
        dot.fill.solid()
        dot.fill.fore_color.rgb = dot_color

        # Label — Geist Mono bold, vertically centered on the dot
        label_text = (stage.get("label") or "").strip()
        if label_text:
            _add_text(
                slide,
                label_text,
                left=label_left,
                top=cy - label_h / 2,
                width=label_w,
                height=label_h,
                size=_LABEL_SIZE,
                color_rgb=palette.text_rgb,
                font=branding.MONO_FONT,
                bold=True,
            )

        # Body — Geist sans, smaller, sits below label
        body_text = (stage.get("body") or "").strip()
        if body_text:
            _add_text(
                slide,
                body_text,
                left=label_left,
                top=cy + label_h / 2 - 0.05,
                width=label_w,
                height=body_text_h,
                size=_BODY_SIZE,
                color_rgb=palette.muted_rgb,
                font=branding.SANS_FONT,
            )
