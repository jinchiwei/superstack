"""freeform layout — runs Claude-written python in a sandbox to draw
arbitrary shapes on the slide. Chrome (title/lede/footer/accent bar) is
still drawn by _add_chrome so brand identity stays consistent."""

from __future__ import annotations

from layouts._common import (
    _add_chrome, _add_text, DEEPPINK_RGB,
)
from layouts._sandbox import run as run_sandboxed, SandboxError
import branding


def render(slide, *, params: dict, accent_rgb, footer_kwargs: dict) -> None:
    """params:
        title:         str
        lede:          str
        code:          str        # python snippet, runs in sandbox
        section_label: str|None   # informational
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    code = params.get("code", "")

    title_wraps = len(title) > 30

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide, title=title, lede=lede, footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=bool(title),
        title_wraps=title_wraps,
        use_side_by_side=False,
    )

    if not code.strip():
        return  # nothing to draw — chrome only

    # accent_rgb is a python-pptx RGBColor; convert back to "#xxxxxx"
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
        )
    except SandboxError as e:
        # Visible error chip — render an obvious deeppink message in the
        # body region. Whole deck continues to render.
        _add_text(slide,
                  f"[freeform code rejected: {e}]",
                  left=body_l, top=body_top,
                  width=body_w, height=0.5,
                  size=12, color_rgb=DEEPPINK_RGB,
                  font=branding.MONO_FONT, bold=True)
    except Exception as e:
        # Code passed validation but blew up at runtime (e.g., wrong arg
        # count to _add_text). Surface as an error chip too rather than
        # crashing the build.
        _add_text(slide,
                  f"[freeform runtime error: {type(e).__name__}: {e}]",
                  left=body_l, top=body_top,
                  width=body_w, height=0.5,
                  size=12, color_rgb=DEEPPINK_RGB,
                  font=branding.MONO_FONT, bold=True)
