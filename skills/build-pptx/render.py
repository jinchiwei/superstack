"""Deterministic render driver for v4 plan-based pptx generation.

Reads a Plan (from a sidecar JSON) + the markdown source, dispatches each
slide to its layout-catalog renderer, and writes the pptx. Pure Python; no
LLM in the loop. Same plan + same markdown → same pptx (modulo timestamp
metadata)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

# Wire imports
SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
sys.path.insert(0, str(SKILL_DIR.parent / "_shared"))

import branding  # noqa: E402
from md_loader import load_markdown, extract_title  # noqa: E402

from layouts import catalog  # noqa: E402
from layouts._common import (
    INK_RGB, WHITE_RGB, TURQUOISE_RGB, DEEPPINK_RGB, AMBER_RGB,
    BLUEVIOLET_RGB, _rgb, _split_slides, _estimate_paragraph_height,
    _strip_html,
)


def _accent_for_section(label: str) -> str:
    """Map a section label to an accent hex via branding's keyword classifier."""
    return branding.match_section_color(label)


# ---------------------------------------------------------------------------
# Fix: auto-split unreadable multi-image content-text-image slides
# ---------------------------------------------------------------------------

# Readability thresholds for per-figure rendered size.  A heatmap with ~10
# rows of labels is unreadable below these sizes.  3.5 in × 2.5 in was chosen
# as the smallest workable label-bearing figure; below that the layout module
# will auto-explode into multiple content-image-only slides.
_MIN_FIG_W_IN = 3.5   # per-image width threshold (inches)
_MIN_FIG_H_IN = 2.5   # per-image height threshold (inches)

# Standard chrome geometry constants (must match _add_chrome in _common.py)
_SLIDE_BODY_W    = 12.30   # body region width (inches)
_SLIDE_BODY_L    = 0.50
_SLIDE_BODY_BOT  = 6.85
_MEDIA_GUTTER    = 0.15    # gutter between sub-images in _render_media_block


def _estimate_body_top(params: dict) -> float:
    """Estimate body_top for a content-text-image slide's stacked layout.

    Mirrors the geometry in _add_chrome so we can predict the media-block
    top without actually rendering.  Conservative (tends to overestimate
    body_top → underestimate available height → triggers split more readily).
    """
    title = params.get("title", "")
    lede  = params.get("lede",  "")
    title_wraps = len(title) > 30 if title else False
    title_h     = 1.05 if title_wraps else 0.55
    hairline_top  = 0.30 + title_h + 0.10
    subtitle_top  = hairline_top + 0.10

    if lede:
        est_h = _estimate_paragraph_height(lede, width=_SLIDE_BODY_W,
                                           size=13, line_spacing=1.30)
        lede_h = min(1.0, max(0.40, est_h))
    else:
        lede_h = 0.40

    return subtitle_top + lede_h + 0.10   # body_top


def _per_image_dims(n_images: int, body_top_after_text: float
                    ) -> tuple[float, float]:
    """Return estimated (per_image_w, per_image_h) for n_images in the
    _render_media_block grid starting at body_top_after_text.

    The media block uses: cols=2 for n<=4, 3 otherwise; rows = ceil(n/cols).
    """
    cols = 2 if n_images <= 4 else 3
    rows = (n_images + cols - 1) // cols
    sub_w = (_SLIDE_BODY_W - _MEDIA_GUTTER * (cols - 1)) / cols
    remaining = _SLIDE_BODY_BOT - body_top_after_text
    sub_h = max(0.5, (remaining - _MEDIA_GUTTER * (rows - 1)) / rows)
    return sub_w, sub_h


def _should_explode(params: dict) -> bool:
    """Return True when a content-text-image entry should be exploded into
    separate content-image-only slides.

    Conditions (all must hold):
      - kind is content-text-image
      - use_side_by_side is False (stacked path)
      - N >= 2 images present
      - per-image rendered width < _MIN_FIG_W_IN OR height < _MIN_FIG_H_IN
    """
    if params.get("use_side_by_side"):
        return False
    images = list(params.get("images") or [])
    n = len(images)
    if n < 2:
        return False

    # Estimate where the media block starts (after chrome + body text)
    body_top = _estimate_body_top(params)
    body_items = list(params.get("body") or [])
    if body_items:
        est_h = sum(
            _estimate_paragraph_height(
                _strip_html(it.get("html", "") if isinstance(it, dict)
                            else str(it).lstrip("• ").strip()),
                width=_SLIDE_BODY_W, size=13)
            for it in body_items
        )
        est_h += (len(body_items) - 1) * (8 / 72.0)
        cap_h = min(1.6, max(0.4, est_h + 0.10))
        body_top += cap_h + 0.15

    sub_w, sub_h = _per_image_dims(n, body_top)
    return sub_w < _MIN_FIG_W_IN or sub_h < _MIN_FIG_H_IN


def _explode_entry(entry) -> list:
    """Expand one content-text-image SlideEntry into N content-image-only
    SlideEntry objects (one per image).

    - The first exploded slide carries the original lede as its lede (context).
    - Subsequent slides have no lede.
    - Title = original title + ' · ' + image alt (or 'Figure N') when available.
    - slide_id = original slide_id + '--N' for uniqueness / stable caching.
    """
    from plan import SlideEntry

    params  = dict(entry.params or {})
    images  = list(params.get("images") or [])
    title   = params.get("title", "")
    lede    = params.get("lede", "")
    section_label = params.get("section_label", "")
    accent_override = params.get("accent_override")

    # Try to recover alt text from the sidecar's image_records if present;
    # fall back to "Figure N" numbering.
    image_records = params.get("image_records") or []
    alt_map: dict[str, str] = {}
    for rec in image_records:
        if isinstance(rec, dict):
            path_key = str(rec.get("path", ""))
            alt_val  = rec.get("alt", "")
            if path_key and alt_val:
                alt_map[path_key] = alt_val

    exploded = []
    for i, img in enumerate(images):
        alt = alt_map.get(str(img), "") or f"Figure {i + 1}"
        slide_title = f"{title} · {alt}" if title else alt
        slide_lede  = lede if i == 0 else ""

        new_params: dict = {
            "title":  slide_title,
            "lede":   slide_lede,
            "images": [img],
            "tables": [],
        }
        if section_label:
            new_params["section_label"] = section_label
        if accent_override:
            new_params["accent_override"] = accent_override

        new_id = f"{entry.slide_id}--{i + 1}"
        exploded.append(SlideEntry(
            slide_id=new_id,
            kind="content-image-only",
            params=new_params,
            content_hash=entry.content_hash,
        ))

    return exploded


def _preprocess_plan(plan) -> list:
    """Walk plan.slides; expand any content-text-image entries that would
    render below the readability threshold into N content-image-only slides.

    Returns a new list of SlideEntry objects (the original plan is not mutated).
    """
    result = []
    for entry in plan.slides:
        if (entry.kind == "content-text-image"
                and _should_explode(entry.params or {})):
            expanded = _explode_entry(entry)
            result.extend(expanded)
        else:
            result.append(entry)
    return result


def render_from_plan(*, md_path: Path, plan, output_path: Path,
                     no_cover: bool = False, no_end: bool = False,
                     theme=None) -> None:
    """Render markdown + Plan into pptx at output_path.

    The Plan dictates layout choice per slide; markdown supplies the actual
    text/images via layout params already populated in the Plan. Title slide,
    section dividers, and end slide come from build.py's existing helpers
    (we import them lazily to avoid circular imports)."""
    # Lazy imports to avoid the build.py<->render.py cycle
    from build import (
        add_title_slide, add_section_divider, add_end_slide, new_presentation,
    )

    loaded = load_markdown(str(md_path))
    meta = loaded["meta"]
    today = dt.date.today().isoformat()
    deck_title = extract_title(loaded) or md_path.stem
    deck_name = str(meta.get("name", ""))
    deck_org = str(meta.get("org", ""))
    deck_date = str(meta.get("date") or today)

    # Resolve relative image paths against the markdown file's directory so
    # `figures/foo.png` works regardless of CWD when the renderer was invoked.
    import os as _os
    _orig_cwd = _os.getcwd()
    _os.chdir(md_path.parent)

    prs = new_presentation()

    # Cover
    if not no_cover:
        add_title_slide(
            prs,
            eyebrow=str(meta.get("eyebrow", "")),
            title=deck_title,
            subtitle=str(meta.get("subtitle", "")),
            name=deck_name, org=deck_org, date=deck_date,
        )

    # Walk plan slides; track current section accent
    current_accent = branding.TURQUOISE
    # Expressive themes may reorder which brand-4 accent leads.
    if theme is not None and theme.accent_order:
        current_accent = theme.accent_order[0]
    footer_kwargs = {
        "name": deck_name, "org": deck_org,
        "deck_title": deck_title, "date": deck_date,
    }

    # Preprocessing pass: auto-split unreadable multi-image slides into
    # individual content-image-only slides before rendering.
    processed_slides = _preprocess_plan(plan)

    for entry in processed_slides:
        params = entry.params or {}

        # Inject the resolved theme into freeform slides only. This dict is
        # added by the renderer, never by the planner, and is not persisted.
        if theme is not None and entry.kind == "freeform":
            params = dict(params)
            params["_theme"] = {
                "on_dark": theme.on_dark,
                "bg_hex": theme.bg_hex,
                "supplementary": list(theme.supplementary),
            }

        if entry.kind == "section-divider":
            label = params.get("label", "")
            current_accent = _accent_for_section(label)
            add_section_divider(
                prs, label=label,
                accent_color_hex=current_accent,
                name=deck_name, org=deck_org, deck_title=deck_title,
            )
            continue

        # Update accent if the entry indicates a new section
        if "section_label" in params:
            current_accent = _accent_for_section(params["section_label"])

        accent_override = params.get("accent_override")
        if accent_override:
            accent_map = {
                "turquoise": branding.TURQUOISE,
                "deeppink": branding.DEEPPINK,
                "amber": branding.AMBER,
                "blueviolet": branding.BLUEVIOLET,
            }
            accent_hex = accent_map.get(accent_override, current_accent)
        else:
            accent_hex = current_accent

        # Render via catalog
        s = prs.slides.add_slide(prs.slide_layouts[6])
        renderer = catalog.get(entry.kind)
        renderer(s, params=params, accent_rgb=_rgb(accent_hex),
                 footer_kwargs=footer_kwargs)

    # End slide
    if not no_end:
        add_end_slide(prs, message="Thanks", contact=deck_name)

    prs.save(str(output_path))
    _os.chdir(_orig_cwd)
