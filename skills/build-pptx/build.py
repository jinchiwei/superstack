"""build-pptx — markdown → Jin-branded PPTX via python-pptx.

This file contains:
  - Slide master functions (add_title_slide, add_content_slide, etc.)
  - main() driver that parses markdown and dispatches to masters

Slide masters are independently callable from other Python code.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Wire imports to sibling _shared/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

import branding  # noqa: E402
import argparse  # noqa: E402
import datetime as dt  # noqa: E402
import re  # noqa: E402

from md_loader import load_markdown, extract_title  # noqa: E402

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Emu, Inches, Pt
except ImportError:
    raise SystemExit("python-pptx not installed. Run: pip install python-pptx")

# Re-export helpers and constants from layouts package so that any code that
# imported them directly from build still works.
from layouts._common import (  # noqa: E402
    _rgb,
    _HTML_TAG_RE,
    _WS_RUN_RE,
    INK_RGB,
    WHITE_RGB,
    TURQUOISE_RGB,
    DEEPPINK_RGB,
    AMBER_RGB,
    BLUEVIOLET_RGB,
    DIM_RGB,
    MUTED_RGB,
    RULE_RGB,
    DARK_BG_RGB,
    PAPER_RGB,
    _set_bg,
    _add_rect,
    _add_text,
    _blank,
    _add_card,
    _add_runs_from_html,
    _estimate_paragraph_height,
    _render_paragraph_block,
    _get_image_aspect,
    _add_table,
    _render_media_block,
    _strip_html,
    _split_slides,
    _parse_table,
    _DEFLIST_LABEL_MAX_LEN,
    _DEFLIST_BODY_MAX_LEN,
    _detect_def_cards_from_li_html,
    _parse_slide_chunk,
)

from layouts import catalog as _catalog  # noqa: E402


# === Public API ===
def new_presentation() -> "Presentation":
    """Create a 16:9 widescreen presentation."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    return prs


def add_title_slide(prs, *, eyebrow: str = "", title: str, subtitle: str = "",
                    name: str = "", org: str = "", date: str = ""):
    """Title slide: navy bg, left double-rail (turquoise + deeppink), bottom amber hairline.
    Eyebrow turquoise, title white, name turquoise, org deeppink, date dim, all Geist Mono."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    # Left double-rail
    _add_rect(s, left=0, top=0, width=0.8, height=7.5, fill_rgb=TURQUOISE_RGB)
    _add_rect(s, left=0.8, top=0, width=0.25, height=7.5, fill_rgb=DEEPPINK_RGB)

    # Bottom amber hairline
    _add_rect(s, left=0, top=7.44, width=13.333, height=0.06, fill_rgb=AMBER_RGB)

    # Auto-shrink title font for long titles so a 3-line wrap doesn't run
    # into the subtitle. 60+ chars at 48pt regularly wraps to 3 lines.
    title_size = 48 if len(title) <= 50 else (40 if len(title) <= 80 else 32)
    title_h = 2.7 if len(title) > 50 else 2.0  # extra room for wraps

    if eyebrow:
        _add_text(s, eyebrow, left=1.3, top=1.4, width=11, height=0.4,
                  size=14, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, title, left=1.3, top=1.9, width=11.0, height=title_h,
              size=title_size, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)
    subtitle_top = 1.9 + title_h + 0.15
    if subtitle:
        _add_text(s, subtitle, left=1.3, top=subtitle_top, width=11.0, height=0.7,
                  size=18, color_rgb=_rgb("#E5E5EA"), font=branding.SANS_FONT)
        cursor_top = subtitle_top + 0.85
    else:
        cursor_top = subtitle_top
    if name:
        _add_text(s, name, left=1.3, top=cursor_top, width=11, height=0.4,
                  size=22, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.5
    if org:
        _add_text(s, org, left=1.3, top=cursor_top, width=11, height=0.35,
                  size=16, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.45

    # Hairline rule (white at low opacity — approximate as RULE_RGB)
    _add_rect(s, left=1.3, top=cursor_top + 0.1, width=4.0, height=0.005, fill_rgb=RULE_RGB)
    if date:
        _add_text(s, date, left=1.3, top=cursor_top + 0.25, width=11, height=0.3,
                  size=12, color_rgb=DIM_RGB, font=branding.MONO_FONT)
    return s


def add_content_slide(prs, *, title: str, body_paragraphs: list[str],
                      accent_color_hex: str | None = None,
                      images: list[Path] | None = None,
                      tables: list[list[list[str]]] | None = None,
                      cards: list[dict] | None = None,
                      name: str = "", org: str = "", deck_title: str = "",
                      date: str = ""):
    """Content slide. Dispatches to a layout renderer from layouts/catalog.

    Layout (16:9, 13.33×7.50):
      L=0      T=0    W=0.22 H=7.50  left accent bar (section color)
      L=0.50   T=0.30 W=12.30 H=0.55 title (28pt mono INK bold) — omitted if no title
      L=0.50   T=0.95 W=12.30 H=0.005 hairline rule (RULE color)
      L=0.50   T=1.05 W=12.30 H=0.40 subtitle (13pt sans MUTED) — first short paragraph
      L=0.50   T=1.55 W=12.30 H=5.30 body region — cards/media/text by content type
      L=0.50   T=7.12 W=10.00 H=0.30 footer (9pt mono MUTED): name · org · deck · date
    """
    accent_hex = accent_color_hex or branding.TURQUOISE
    accent = _rgb(accent_hex)
    images = images or []
    tables = tables or []
    cards = cards or []

    s = _blank(prs)

    body = list(body_paragraphs or [])

    has_cards = bool(cards)
    has_media = bool(images) or bool(tables)

    # Promote first paragraph to lede if it is prose and there is more below it.
    lede = ""
    has_more_below = (len(body) > 1) or has_media or has_cards
    if body and has_more_below:
        first = body[0]
        if isinstance(first, dict):
            is_bullet = first.get("kind") == "bullet"
            text = _strip_html(first.get("html", ""))
        else:
            is_bullet = first.startswith("•")
            text = first
        if not is_bullet and len(text) <= 350:
            lede = text
            body = body[1:]

    # Decide whether to use side-by-side layout.
    n_images_for_layout = len(images)
    aspect_for_layout = (_get_image_aspect(images[0])
                        if n_images_for_layout == 1 else None)
    use_side_by_side = (
        n_images_for_layout == 1
        and len(tables) == 0
        and not has_cards
        and aspect_for_layout is not None
        and aspect_for_layout <= 1.3
        and (bool(body) or bool(lede))
    )

    footer_kwargs = {
        "name": name,
        "org": org,
        "deck_title": deck_title,
        "date": date,
    }

    # Dispatch to the correct layout renderer.
    if has_cards:
        kind = "cards-grid"
        params = {
            "title": title,
            "lede": lede,
            "body": body,
            "cards": cards,
        }
    elif has_media:
        kind = "content-text-image"
        params = {
            "title": title,
            "lede": lede,
            "body": body,
            "images": images,
            "tables": tables,
            "use_side_by_side": use_side_by_side,
        }
    elif body:
        kind = "content-text"
        params = {
            "title": title,
            "lede": lede,
            "body": body,
        }
    else:
        # Nothing to render — but we still want the chrome (title + footer).
        # Use content-text with empty body.
        kind = "content-text"
        params = {
            "title": title,
            "lede": lede,
            "body": [],
        }

    _catalog.get(kind)(s, params=params, accent_rgb=accent,
                       footer_kwargs=footer_kwargs)

    return s


def add_section_divider(prs, *, label: str, index: int = 0,
                        accent_color_hex: str | None = None,
                        name: str = "", org: str = "", deck_title: str = ""):
    """Section divider: navy bg + full-height left colorblock + DMG-style top
    title block + bottom footer (name turquoise · org deeppink · deck muted).

    Color comes from `accent_color_hex` if provided, else from
    branding.pick_section_color(index) cycling.
    """
    bg_hex = accent_color_hex or branding.pick_section_color(index)
    accent = _rgb(bg_hex)
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    # Full-height left colorblock (results_overview style)
    _add_rect(s, left=0, top=0, width=0.6, height=7.5, fill_rgb=accent)

    # Small DMG-style accent bar at the top, just right of the colorblock.
    _add_rect(s, left=0.85, top=0.7, width=0.18, height=0.45, fill_rgb=accent)

    # Eyebrow = thematic category based on accent color.
    eyebrow_text = branding.category_for_accent(bg_hex)
    _add_text(s, eyebrow_text, left=1.15, top=0.7, width=11.0, height=0.4,
              size=14, color_rgb=accent, font=branding.MONO_FONT, bold=True)

    # Big section title — H1 text in ALL CAPS.
    _add_text(s, label.upper(), left=0.85, top=2.4, width=12.0, height=3.0,
              size=44, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)

    # Hairline rule
    _add_rect(s, left=0.85, top=5.6, width=2.0, height=0.02, fill_rgb=accent)

    # Bottom footer
    footer_top = 6.7
    cursor_left = 0.95
    if name:
        _add_text(s, name, left=cursor_left, top=footer_top, width=4.0, height=0.35,
                  size=11, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
        cursor_left += max(1.4, 0.11 * len(name))
    if org:
        if name:
            _add_text(s, "·", left=cursor_left, top=footer_top, width=0.2, height=0.35,
                      size=11, color_rgb=DIM_RGB, font=branding.MONO_FONT)
            cursor_left += 0.25
        _add_text(s, org, left=cursor_left, top=footer_top, width=5.0, height=0.35,
                  size=11, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
        cursor_left += max(1.4, 0.11 * len(org))
    if deck_title:
        if name or org:
            _add_text(s, "·", left=cursor_left, top=footer_top, width=0.2, height=0.35,
                      size=11, color_rgb=DIM_RGB, font=branding.MONO_FONT)
            cursor_left += 0.25
        _add_text(s, deck_title, left=cursor_left, top=footer_top, width=8.0, height=0.35,
                  size=11, color_rgb=DIM_RGB, font=branding.MONO_FONT)

    return s


def add_big_number_slide(prs, *, number: str, caption: str = ""):
    """White background. Giant deeppink number centered, caption underneath."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, number, left=0.5, top=2.4, width=12.3, height=2.2,
              size=120, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if caption:
        _add_text(s, caption, left=1.0, top=4.8, width=11.3, height=0.8,
                  size=18, color_rgb=MUTED_RGB, font=branding.SANS_FONT,
                  align=PP_ALIGN.CENTER)
    return s


def add_two_column_slide(prs, *, title: str,
                         left_title: str, left_body: list[str],
                         right_title: str, right_body: list[str]):
    """White background. Title at top, two side-by-side columns."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, title, left=0.6, top=0.4, width=12.5, height=0.8,
              size=32, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    _add_rect(s, left=0.6, top=1.25, width=12.0, height=0.005, fill_rgb=RULE_RGB)

    # Left column
    _add_text(s, left_title, left=0.6, top=1.5, width=5.8, height=0.5,
              size=18, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, "\n".join(left_body), left=0.6, top=2.1, width=5.8, height=5.0,
              size=18, color_rgb=INK_RGB, font=branding.SANS_FONT)

    # Right column
    _add_text(s, right_title, left=6.95, top=1.5, width=5.8, height=0.5,
              size=18, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, "\n".join(right_body), left=6.95, top=2.1, width=5.8, height=5.0,
              size=18, color_rgb=INK_RGB, font=branding.SANS_FONT)

    # Vertical hairline between columns
    _add_rect(s, left=6.7, top=1.5, width=0.005, height=5.5, fill_rgb=RULE_RGB)
    return s


def add_quote_slide(prs, *, quote: str, attribution: str = ""):
    """White background. Quote centered in italic sans, attribution mono."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, f'"{quote}"', left=1.5, top=2.5, width=10.3, height=2.5,
              size=36, color_rgb=INK_RGB, font=branding.SANS_FONT, italic=True,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if attribution:
        _add_text(s, f"— {attribution}", left=1.5, top=5.3, width=10.3, height=0.4,
                  size=14, color_rgb=MUTED_RGB, font=branding.MONO_FONT,
                  align=PP_ALIGN.CENTER)
    return s


def add_end_slide(prs, *, message: str = "Thanks", contact: str = ""):
    """End slide: mirror title slide. Navy bg, left double-rail, bottom amber hairline.
    Big white "Thanks" centered, contact in dim mono below."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    # Left double-rail (mirror of title)
    _add_rect(s, left=0, top=0, width=0.8, height=7.5, fill_rgb=TURQUOISE_RGB)
    _add_rect(s, left=0.8, top=0, width=0.25, height=7.5, fill_rgb=DEEPPINK_RGB)

    # Bottom amber hairline (mirror of title)
    _add_rect(s, left=0, top=7.44, width=13.333, height=0.06, fill_rgb=AMBER_RGB)

    _add_text(s, message, left=1.3, top=2.7, width=11.0, height=2.0,
              size=64, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True,
              align=PP_ALIGN.CENTER)
    if contact:
        # Name in turquoise (the end slide's primary accent — mirrors the
        # title slide's left double-rail and the section-divider footer
        # convention where Jin's name always appears in turquoise).
        _add_text(s, contact, left=1.3, top=4.8, width=11.0, height=0.5,
                  size=14, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT,
                  bold=True, align=PP_ALIGN.CENTER)
    return s


def _legacy_main(args) -> int:
    """The v3 rule-based render path. Preserved as the --no-plan fallback."""
    loaded = load_markdown(args.input)
    meta = loaded["meta"]
    today = dt.date.today().isoformat()

    deck_title = extract_title(loaded) or Path(args.input).stem
    deck_name = str(meta.get("name", ""))
    deck_org = str(meta.get("org", ""))
    deck_date = str(meta.get("date") or today)
    md_dir = Path(args.input).resolve().parent

    prs = new_presentation()

    if not args.no_cover:
        add_title_slide(
            prs,
            eyebrow=str(meta.get("eyebrow", "")),
            title=deck_title,
            subtitle=str(meta.get("subtitle", "")),
            name=deck_name,
            org=deck_org,
            date=deck_date,
        )

    def _emit_content(slide_data: dict, slide_title: str) -> None:
        """Emit a content slide with the section's current accent + deck footer.

        Auto-explode behavior: when a slide has 2+ images and no cards/tables,
        each image becomes its own full-bleed slide titled by its alt text,
        with the immediately preceding paragraph as its lede. Matches Jin's
        DMG v2 deck where each chart was on its own slide rather than three
        tiny figures crammed into a row."""
        image_records = slide_data.get("image_records") or []
        body_paras = slide_data.get("body", [])
        if (len(image_records) >= 2
                and not slide_data.get("cards")
                and not slide_data.get("tables")):
            # Walk by source position; pair each image with the most recent
            # preceding paragraph (consumed once it becomes a lede).
            text_items = sorted(
                [p for p in body_paras if p.get("pos") is not None],
                key=lambda p: p["pos"],
            )
            ti = 0
            consumed = set()
            for img_rec in image_records:
                lede_para = None
                while ti < len(text_items) and text_items[ti]["pos"] < img_rec["pos"]:
                    if id(text_items[ti]) not in consumed:
                        lede_para = text_items[ti]
                    ti += 1
                if lede_para is not None:
                    consumed.add(id(lede_para))
                sub_title = (img_rec["alt"] or slide_title or "").strip() or slide_title
                sub_body = [lede_para] if lede_para else []
                add_content_slide(
                    prs,
                    title=sub_title,
                    body_paragraphs=sub_body,
                    images=[img_rec["path"]],
                    tables=[],
                    cards=None,
                    accent_color_hex=current_accent,
                    name=deck_name, org=deck_org,
                    deck_title=deck_title, date=deck_date,
                )
            # Trailing paragraphs after the last image — render as a final
            # text-only slide using the parent title.
            trailing = [p for p in text_items
                        if p["pos"] > image_records[-1]["pos"]
                        and id(p) not in consumed]
            if trailing:
                add_content_slide(
                    prs,
                    title=slide_title,
                    body_paragraphs=trailing,
                    images=[],
                    tables=[],
                    cards=None,
                    accent_color_hex=current_accent,
                    name=deck_name, org=deck_org,
                    deck_title=deck_title, date=deck_date,
                )
            return
        add_content_slide(
            prs,
            title=slide_title,
            body_paragraphs=body_paras,
            images=slide_data["images"],
            tables=slide_data["tables"],
            cards=slide_data.get("cards"),
            accent_color_hex=current_accent,
            name=deck_name, org=deck_org,
            deck_title=deck_title, date=deck_date,
        )

    # Walk slide chunks; track current section accent.
    chunks = _split_slides(loaded["body_html"])
    current_accent = branding.TURQUOISE

    for chunk in chunks:
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", chunk)
        if h1_match:
            section_label = _strip_html(h1_match.group(1))
            current_accent = branding.match_section_color(section_label)
            add_section_divider(prs, label=section_label,
                                accent_color_hex=current_accent,
                                name=deck_name, org=deck_org,
                                deck_title=deck_title)
            remaining = chunk[h1_match.end():].strip()
            if remaining:
                slide = _parse_slide_chunk(remaining, base_dir=md_dir)
                if any(slide.get(k) for k in ("title", "body", "images", "tables", "cards")):
                    slide_title = slide["title"] or section_label
                    _emit_content(slide, slide_title)
        else:
            slide = _parse_slide_chunk(chunk, base_dir=md_dir)
            if any(slide.get(k) for k in ("title", "body", "images", "tables", "cards")):
                _emit_content(slide, slide["title"])

    if not args.no_end:
        add_end_slide(prs, message="Thanks",
                      contact=str(meta.get("name") or ""))

    prs.save(args.output)
    print(f"wrote {args.output}")
    return 0


_CONCLUSIONS_KEYWORDS = (
    "takeaways", "takeaway", "conclusions", "conclusion",
    "summary", "next steps", "key findings", "closing", "final thoughts",
)


def _looks_like_stat_label(label: str) -> bool:
    """True if a card label reads as a stat token (e.g. '0.91', 'OR = 2.44',
    'p < 0.001', 'r = +0.92', '68.5%'). Used to distinguish
    stats-with-takeaway from cards-grid.

    Heuristic: short (≤ 25 chars), contains at least one digit, and is
    dominated by digits relative to letters. Allows a small letter prefix
    (OR, AUC, p, n, r, β, ρ, Δ) and a trailing unit/operator.
    """
    if not label:
        return False
    s = label.strip()
    if len(s) > 25 or len(s) == 0:
        return False
    n_letters = sum(1 for c in s if c.isalpha())
    n_digits = sum(1 for c in s if c.isdigit())
    if n_digits == 0:
        return False
    if n_letters > 8:           # cap letter count — too wordy = categorical
        return False
    if n_letters > n_digits + 6:  # letters mustn't dominate digits too heavily
        return False
    return True


def _is_closing_slide(title: str, section_label: str | None) -> bool:
    """Return True when a slide title (or parent H1 section label) matches
    the closing-slide pattern — case-insensitive substring match."""
    candidates = [title or "", section_label or ""]
    for candidate in candidates:
        lower = candidate.lower()
        if any(kw in lower for kw in _CONCLUSIONS_KEYWORDS):
            return True
    return False


def _infer_default_plan(*, md_text: str, chunks: list[str],
                        slide_records: list[dict], deck_md_hash: str,
                        base_dir: Path):
    """Build a Plan from chunks using the same dispatch logic the legacy
    renderer uses. Lets the v4 path produce the same output as v3 when no
    Claude-generated plan exists yet (Task 6 will replace this with real
    layout-picking via in-session reasoning)."""
    from plan import Plan, SlideEntry

    slides: list[SlideEntry] = []
    current_h1: str | None = None
    for rec, chunk in zip(slide_records, chunks):
        slide_id = rec["slide_id"]
        content_hash = rec["content_hash"]

        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", chunk, re.DOTALL)
        if h1_match:
            section_label = _strip_html(h1_match.group(1))
            current_h1 = section_label
            accent_hex = branding.match_section_color(section_label)
            # Emit a section divider entry FIRST
            slides.append(SlideEntry(
                slide_id=f"divider-{slide_id}",
                kind="section-divider",
                params={"label": section_label, "accent_hex": accent_hex},
                content_hash=content_hash + "-divider",
            ))
            # If the chunk has body content beyond the H1, also emit a content slide
            remaining = chunk[h1_match.end():].strip()
            if not remaining:
                continue
            sd = _parse_slide_chunk(remaining, base_dir=base_dir)
            slide_title = sd["title"] or section_label
        else:
            sd = _parse_slide_chunk(chunk, base_dir=base_dir)
            slide_title = sd["title"]

        # Skip empty chunks
        if not any(sd.get(k) for k in ("title", "body", "images", "tables", "cards")):
            continue

        # Choose layout kind via the same heuristics as add_content_slide
        body = list(sd["body"])
        images = sd["images"]
        tables = sd["tables"]
        cards = sd["cards"]
        image_records = sd.get("image_records", [])

        # Lede extraction (mirrors add_content_slide logic)
        lede = ""
        has_more_below = (len(body) > 1) or bool(images) or bool(tables) or bool(cards)
        if body and has_more_below:
            first = body[0]
            text = _strip_html(first.get("html", ""))
            if first.get("kind") != "bullet" and len(text) <= 350:
                lede = text
                body = body[1:]

        # Multi-image auto-explode (mirrors _emit_content logic)
        if (len(image_records) >= 2 and not cards and not tables):
            text_items = sorted(
                [p for p in sd["body"] if p.get("pos") is not None],
                key=lambda p: p["pos"],
            )
            ti = 0
            consumed = set()
            for j, img_rec in enumerate(image_records):
                lede_para = None
                while ti < len(text_items) and text_items[ti]["pos"] < img_rec["pos"]:
                    if id(text_items[ti]) not in consumed:
                        lede_para = text_items[ti]
                    ti += 1
                if lede_para is not None:
                    consumed.add(id(lede_para))
                sub_lede = _strip_html(lede_para["html"]) if lede_para else ""
                sub_title = (img_rec["alt"] or slide_title or "").strip() or slide_title
                params = {
                    "title": sub_title, "lede": sub_lede,
                    "body": [],
                    "images": [str(img_rec["path"])],
                    "tables": [],
                    "section_label": current_h1 or "",
                }
                slides.append(SlideEntry(
                    slide_id=f"{slide_id}/img-{j}",
                    kind="content-image-only",
                    params=params,
                    content_hash=f"{content_hash}-img-{j}",
                ))
            # Trailing paragraphs after the last image
            trailing = [p for p in text_items
                        if p["pos"] > image_records[-1]["pos"]
                        and id(p) not in consumed]
            if trailing:
                params = {
                    "title": slide_title, "lede": "",
                    "body": trailing, "section_label": current_h1 or "",
                }
                slides.append(SlideEntry(
                    slide_id=f"{slide_id}/trailing",
                    kind="content-text",
                    params=params,
                    content_hash=f"{content_hash}-trailing",
                ))
            continue

        # Choose layout
        if cards and _is_closing_slide(slide_title, current_h1):
            # Auto-fire conclusions for closing slides with cards
            _CLOSING_ACCENTS = [
                branding.TURQUOISE, branding.DEEPPINK,
                branding.AMBER, branding.BLUEVIOLET,
            ]
            _CLOSING_ICONS = [
                "FaChartLine", "FaCheckCircle",
                "FaExclamationTriangle", "FaCrosshairs",
            ]
            card_list = []
            for i, c in enumerate(cards):
                card_entry = {
                    "label": c["label"],
                    "body": c["body"],
                    "icon": str(c["icon"]) if c.get("icon") else _CLOSING_ICONS[i % len(_CLOSING_ICONS)],
                    "accent_hex": _CLOSING_ACCENTS[i % len(_CLOSING_ACCENTS)],
                }
                card_list.append(card_entry)
            # Determine callout text: prefer trailing body paragraph; fall back
            # to lede (the lede-extractor may have consumed the "Path forward"
            # sentence before we got here). When lede becomes the callout we
            # clear it to avoid duplicate display.
            callout_text = ""
            if body:
                callout_text = " ".join(
                    _strip_html(b.get("html", "")) for b in body if b.get("html")
                ).strip()
            if not callout_text and lede:
                callout_text = lede
                lede = ""  # promote to callout; don't show as lede too

            kind = "conclusions"
            params = {
                "title": slide_title,
                "lede": lede,
                "section_label": current_h1 or "",
                "cards": card_list,
            }
            if callout_text:
                params["callout"] = {"text": callout_text, "tone": "dark"}
        elif cards:
            # If 2+ cards AND every label looks like a stat token, prefer
            # stats-with-takeaway (big-number tiles + dark callout footer)
            # over cards-grid. Trailing prose / lede promotes to callout.
            stat_eligible = (
                len(cards) >= 2
                and not images
                and not tables
                and all(_looks_like_stat_label(c.get("label", "")) for c in cards)
            )
            if stat_eligible:
                callout_text = ""
                if body:
                    callout_text = " ".join(
                        _strip_html(b.get("html", "")) for b in body if b.get("html")
                    ).strip()
                if not callout_text and lede:
                    callout_text = lede
                    lede = ""
                kind = "stats-with-takeaway"
                params = {
                    "title": slide_title,
                    "lede": lede,
                    "section_label": current_h1 or "",
                    "stats": [
                        {"value": c["label"], "label": "",
                         "sub": _strip_html(c.get("body", "") or "")}
                        for c in cards
                    ],
                }
                if callout_text:
                    params["callout"] = {"text": callout_text, "tone": "dark"}
            elif (
                len(cards) == 3
                and not images
                and not tables
                and not _is_closing_slide(slide_title, current_h1)
                and all(len((c.get("label") or "").strip()) <= 30 for c in cards)
            ):
                # 3-card non-closing, non-stat slide → three-pillars
                # (bigger, more visually prominent pillar cards) but with
                # show_arrows=False so we don't imply a false sequence.
                # cards-grid n=3 renders small uniform tiles which read as
                # half-empty on a 3-aim slide. To force arrows on for an
                # actual sequence, edit the sidecar manually.
                kind = "three-pillars"
                params = {
                    "title": slide_title,
                    "lede": lede,
                    "section_label": current_h1 or "",
                    "pillars": [
                        {"label": c["label"], "body": c["body"],
                         "color_role": None}
                        for c in cards
                    ],
                    "show_arrows": False,
                }
            else:
                kind = "cards-grid"
                params = {"title": slide_title, "lede": lede, "body": body,
                          "cards": [{"label": c["label"], "body": c["body"],
                                     "icon": str(c["icon"]) if c.get("icon") else None}
                                    for c in cards],
                          "section_label": current_h1 or ""}
        elif images or tables:
            n_images = len(images)
            aspect = _get_image_aspect(images[0]) if n_images == 1 else None
            use_side_by_side = (
                n_images == 1 and len(tables) == 0 and not cards
                and aspect is not None and aspect <= 1.3
                and (bool(body) or bool(lede))
            )
            # figure-with-aside: 1 wide image + light commentary (≤3 short
            # paragraphs/bullets, < 350 chars total). Heavy-caption slides
            # (long bullets, multi-paragraph captions) keep the centered
            # content-text-image layout because their text doesn't fit a
            # 1/3-width aside card.
            body_text = " ".join(
                _strip_html(b.get("html", "") or "") for b in (body or [])
            ).strip() if body else ""
            aside_eligible = (
                n_images == 1 and len(tables) == 0 and not cards
                and aspect is not None and aspect > 1.3
                and (bool(body) or bool(lede))
                and len(body or []) <= 6        # bullets pack fine in an aside
                and len(body_text) < 500        # generous chars; long captions stay centered
            )
            if aside_eligible:
                kind = "figure-with-aside"
                params = {
                    "title": slide_title,
                    "lede": lede,
                    "section_label": current_h1 or "",
                    "image": str(images[0]),
                    "alt": "",
                    "aside": {
                        "label": "",
                        "body": body_text or lede,
                        "icon": None,
                    },
                }
            else:
                kind = "content-text-image" if (body or lede) else "content-image-only"
                params = {"title": slide_title, "lede": lede,
                          "body": body if kind == "content-text-image" else [],
                          "images": [str(p) for p in images],
                          "tables": tables,
                          "use_side_by_side": use_side_by_side,
                          "section_label": current_h1 or ""}
        elif body:
            kind = "content-text"
            params = {"title": slide_title, "lede": lede, "body": body,
                      "section_label": current_h1 or ""}
        else:
            # Empty chunk — skip
            continue

        slides.append(SlideEntry(
            slide_id=slide_id, kind=kind, params=params,
            content_hash=content_hash,
        ))

    return Plan(version=1, deck_md_hash=deck_md_hash, slides=slides)


def main() -> int:
    ap = argparse.ArgumentParser(description="markdown → Jin-branded PPTX")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="suppress title slide")
    ap.add_argument("--no-end", dest="no_end", action="store_true",
                    help="suppress closing 'Thanks' slide")
    ap.add_argument("--shake", action="store_true",
                    help="regenerate the layout plan from scratch")
    ap.add_argument("--plan-only", dest="plan_only", action="store_true",
                    help="emit only the plan JSON; do not render pptx")
    ap.add_argument("--no-plan", dest="no_plan", action="store_true",
                    help="bypass v4 plan path; use legacy rule-based renderer")
    ap.add_argument(
        "--use-blocks",
        dest="use_blocks",
        choices=["auto", "never", "always"],
        default="auto",
        help=(
            "Control when composition/freeform layouts are admissible. "
            "'auto' (default): planner may pick composition/freeform when the "
            "decision rubric says appropriate. "
            "'never': forbid composition and freeform entirely; if a sidecar "
            "contains them the build is aborted with a clear error message. "
            "'always': signal that the agent should prefer composition/freeform "
            "(useful for explicit experiments; does not force-rewrite an existing "
            "sidecar, but informs inline plan generation when no sidecar exists)."
        ),
    )
    args = ap.parse_args()

    if args.no_plan:
        # Legacy path — current main() behavior
        return _legacy_main(args)

    # Plan path
    from plan import (
        Plan, SlideEntry, build_slide_records, derive_slide_ids_from_chunks,
        merge_with_existing, hash_text, assemble_plan_prompt,
    )

    md_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    sidecar_path = md_path.with_suffix(md_path.suffix + ".layout.json")

    md_text = md_path.read_text(encoding="utf-8")
    loaded = load_markdown(str(md_path))
    chunks = _split_slides(loaded["body_html"])
    slide_ids = derive_slide_ids_from_chunks(chunks)
    slide_records = build_slide_records(chunks=chunks, slide_ids=slide_ids)
    deck_md_hash = hash_text(md_text)

    # Read existing sidecar if present and not shaking
    existing_plan = None
    if sidecar_path.exists() and not args.shake:
        try:
            existing_plan = Plan.from_json(sidecar_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"warning: could not parse existing sidecar: {e}", file=sys.stderr)
            existing_plan = None

    # Build a default plan (rule-based layout choice from chunk content)
    default_plan = _infer_default_plan(
        md_text=md_text, chunks=chunks, slide_records=slide_records,
        deck_md_hash=deck_md_hash, base_dir=md_path.parent,
    )

    # Merge with existing
    final_plan = merge_with_existing(default_plan, existing_plan)

    # --use-blocks enforcement
    _BLOCK_KINDS = {"composition", "freeform"}
    use_blocks = getattr(args, "use_blocks", "auto")
    if use_blocks == "never":
        forbidden = [
            s.slide_id
            for s in final_plan.slides
            if s.kind in _BLOCK_KINDS
        ]
        if forbidden:
            print(
                f"error: --use-blocks=never rejects composition/freeform slides: "
                f"{', '.join(forbidden)}\n"
                f"Regenerate the sidecar (delete it or run with --shake) or pass "
                f"--use-blocks=auto to allow them.",
                file=sys.stderr,
            )
            return 1

    # Persist sidecar
    sidecar_path.write_text(final_plan.to_json(), encoding="utf-8")
    print(f"wrote plan: {sidecar_path}")

    if args.plan_only:
        return 0

    # Render
    from render import render_from_plan
    render_from_plan(
        md_path=md_path, plan=final_plan, output_path=output_path,
        no_cover=args.no_cover, no_end=args.no_end,
    )
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
