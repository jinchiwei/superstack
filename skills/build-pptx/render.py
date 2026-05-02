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
    BLUEVIOLET_RGB, _rgb, _split_slides,
)


def _accent_for_section(label: str) -> str:
    """Map a section label to an accent hex via branding's keyword classifier."""
    return branding.match_section_color(label)


def render_from_plan(*, md_path: Path, plan, output_path: Path,
                     no_cover: bool = False, no_end: bool = False) -> None:
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
    footer_kwargs = {
        "name": deck_name, "org": deck_org,
        "deck_title": deck_title, "date": deck_date,
    }

    for entry in plan.slides:
        params = entry.params or {}

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
