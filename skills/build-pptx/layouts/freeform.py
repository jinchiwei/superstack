"""freeform layout — runs Claude-written python in a sandbox to draw
arbitrary shapes on the slide. Chrome (title/lede/footer/accent bar) is
still drawn by _add_chrome so brand identity stays consistent. In expressive
mode a theme may supply a dark canvas + supplementary hues."""

from __future__ import annotations

from layouts._common import (
    _add_chrome, _add_rect, _add_text, _rgb, DEEPPINK_RGB,
)
from layouts._sandbox import run as run_sandboxed, SandboxError
import branding


def render(slide, *, params: dict, accent_rgb, footer_kwargs: dict) -> None:
    """params:
        title:         str
        lede:          str
        code:          str        # python snippet, runs in sandbox
        section_label: str|None   # informational
        _theme:        dict|None  # injected by render_from_plan; never from the planner
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    code = params.get("code", "")

    theme = params.get("_theme") or {}
    on_dark = bool(theme.get("on_dark"))
    canvas_bg_hex = theme.get("bg_hex")
    theme_hexes = theme.get("supplementary") or []

    # Paint the full-bleed canvas FIRST so chrome + snippet draw on top.
    # Any non-white canvas (dark OR tinted) gets painted; on_dark separately
    # drives chrome text inversion (handled by _add_chrome below).
    if canvas_bg_hex and canvas_bg_hex.upper() != "#FFFFFF":
        _add_rect(slide, left=0, top=0, width=13.333, height=7.5,
                  fill_rgb=_rgb(canvas_bg_hex))

    title_wraps = len(title) > 30

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide, title=title, lede=lede, footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=bool(title),
        title_wraps=title_wraps,
        use_side_by_side=False,
        on_dark=on_dark,
    )

    if not code.strip():
        return  # nothing to draw — chrome only

    try:
        hex_part = str(accent_rgb)
    except Exception:
        hex_part = "40E0D0"
    accent_hex = "#" + hex_part.upper().lstrip("#")[:6]

    try:
        run_sandboxed(
            code=code, slide=slide, accent_hex=accent_hex,
            body_top=body_top, body_h=body_h,
            body_l=body_l, body_w=body_w, body_bottom=body_bottom,
            theme_hexes=theme_hexes, canvas_bg_hex=canvas_bg_hex,
            on_dark=on_dark,
        )
    except SandboxError as e:
        _add_text(slide,
                  f"[freeform code rejected: {e}]",
                  left=body_l, top=body_top,
                  width=body_w, height=0.5,
                  size=12, color_rgb=DEEPPINK_RGB,
                  font=branding.MONO_FONT, bold=True)
    except Exception as e:
        _add_text(slide,
                  f"[freeform runtime error: {type(e).__name__}: {e}]",
                  left=body_l, top=body_top,
                  width=body_w, height=0.5,
                  size=12, color_rgb=DEEPPINK_RGB,
                  font=branding.MONO_FONT, bold=True)
