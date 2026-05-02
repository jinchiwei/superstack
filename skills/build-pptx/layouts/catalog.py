"""Registry mapping layout-id strings to render functions. New layouts plug
in here without touching the dispatcher."""

from . import (content_text, content_text_image, content_image_only,
               cards_grid, cards_heterogeneous, three_pillars,
               stat_callouts_right, bg_flip, timeline, freeform,
               composition)

REGISTRY = {
    "content-text":         content_text.render,
    "content-text-image":   content_text_image.render,
    "content-image-only":   content_image_only.render,
    "cards-grid":           cards_grid.render,
    "cards-heterogeneous":  cards_heterogeneous.render,
    "three-pillars":        three_pillars.render,
    "stat-callouts-right":  stat_callouts_right.render,
    "bg-flip":              bg_flip.render,
    "timeline":             timeline.render,
    "freeform":             freeform.render,
    "composition":          composition.render,
}


def _section_divider_render(slide, *, params, accent_rgb, footer_kwargs):
    """Wrapper that renders the section-divider chrome onto a pre-created slide.

    The caller (render.py) adds a blank slide first; we draw on it here.
    Uses the cleaner accent_hex path so we can look up the category eyebrow
    without inverting the RGBColor back to hex."""
    from layouts._common import (
        DARK_BG_RGB, WHITE_RGB, TURQUOISE_RGB, DEEPPINK_RGB, DIM_RGB,
        _add_rect, _add_text, _set_bg, _rgb,
    )
    import branding as _branding

    label = params.get("label", "")
    # Prefer the stored accent_hex from _infer_default_plan; fall back to
    # re-inferring from the label so hand-edited sidecars also work.
    accent_hex = params.get("accent_hex") or _branding.match_section_color(label)
    accent = _rgb(accent_hex)
    eyebrow_text = _branding.category_for_accent(accent_hex)

    name = footer_kwargs.get("name", "")
    org = footer_kwargs.get("org", "")
    deck_title = footer_kwargs.get("deck_title", "")

    _set_bg(slide, DARK_BG_RGB)
    _add_rect(slide, left=0, top=0, width=0.6, height=7.5, fill_rgb=accent)
    _add_rect(slide, left=0.85, top=0.7, width=0.18, height=0.45, fill_rgb=accent)

    _add_text(slide, eyebrow_text, left=1.15, top=0.7, width=11.0, height=0.4,
              size=14, color_rgb=accent, font=_branding.MONO_FONT, bold=True)
    _add_text(slide, label.upper(), left=0.85, top=2.4, width=12.0, height=3.0,
              size=44, color_rgb=WHITE_RGB, font=_branding.MONO_FONT, bold=True)
    _add_rect(slide, left=0.85, top=5.6, width=2.0, height=0.02, fill_rgb=accent)

    footer_top = 6.7
    cursor_left = 0.95
    if name:
        _add_text(slide, name, left=cursor_left, top=footer_top, width=4.0, height=0.35,
                  size=11, color_rgb=TURQUOISE_RGB, font=_branding.MONO_FONT, bold=True)
        cursor_left += max(1.4, 0.11 * len(name))
    if org:
        if name:
            _add_text(slide, "·", left=cursor_left, top=footer_top, width=0.2, height=0.35,
                      size=11, color_rgb=DIM_RGB, font=_branding.MONO_FONT)
            cursor_left += 0.25
        _add_text(slide, org, left=cursor_left, top=footer_top, width=5.0, height=0.35,
                  size=11, color_rgb=DEEPPINK_RGB, font=_branding.MONO_FONT, bold=True)
        cursor_left += max(1.4, 0.11 * len(org))
    if deck_title:
        if name or org:
            _add_text(slide, "·", left=cursor_left, top=footer_top, width=0.2, height=0.35,
                      size=11, color_rgb=DIM_RGB, font=_branding.MONO_FONT)
            cursor_left += 0.25
        _add_text(slide, deck_title, left=cursor_left, top=footer_top, width=8.0, height=0.35,
                  size=11, color_rgb=DIM_RGB, font=_branding.MONO_FONT)


REGISTRY["section-divider"] = _section_divider_render


def get(kind: str):
    """Return the render function for a given layout kind. Raises KeyError
    on unknown kinds — callers should validate against REGISTRY first."""
    return REGISTRY[kind]
