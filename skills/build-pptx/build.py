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

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# === Color helpers ===
def _rgb(hex_str: str) -> RGBColor:
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# Frequently-used RGBColor instances
INK_RGB        = _rgb(branding.INK)
WHITE_RGB      = _rgb(branding.WHITE)
TURQUOISE_RGB  = _rgb(branding.TURQUOISE)
DEEPPINK_RGB   = _rgb(branding.DEEPPINK)
AMBER_RGB      = _rgb(branding.AMBER)
BLUEVIOLET_RGB = _rgb(branding.BLUEVIOLET)
DIM_RGB        = _rgb(branding.DIM)
MUTED_RGB      = _rgb(branding.MUTED)
RULE_RGB       = _rgb(branding.RULE)
DARK_BG_RGB    = _rgb(branding.DARK_BG)
PAPER_RGB      = _rgb(branding.PAPER)


# === Internal helpers ===
def _set_bg(slide, color_rgb: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color_rgb


def _add_rect(slide, *, left, top, width, height,
              fill_rgb: RGBColor | None = None) -> None:
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Inches(left), Inches(top),
                                 Inches(width), Inches(height))
    shp.shadow.inherit = False
    if fill_rgb is not None:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill_rgb
    else:
        shp.fill.background()
    shp.line.fill.background()


def _add_text(slide, text, *, left, top, width, height, size=18,
              color_rgb: RGBColor = INK_RGB, font: str = branding.SANS_FONT,
              bold=False, italic=False, align=PP_ALIGN.LEFT,
              anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top),
                                  Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.color.rgb = color_rgb
    r.font.bold = bold
    r.font.italic = italic
    return tb


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


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

    if eyebrow:
        _add_text(s, eyebrow, left=1.3, top=1.5, width=11, height=0.4,
                  size=14, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, title, left=1.3, top=2.0, width=11.0, height=2.0,
              size=48, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)
    if subtitle:
        _add_text(s, subtitle, left=1.3, top=4.1, width=11.0, height=1.0,
                  size=18, color_rgb=_rgb("#E5E5EA"), font=branding.SANS_FONT)
    cursor_top = 5.4
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


def _add_table(slide, *, rows: list[list[str]], left: float, top: float,
               width: float, max_height: float, header_rgb: RGBColor) -> float:
    """Draw a table with a colored header row. Header filled with header_rgb +
    white mono text; body rows white/paper zebra with INK sans. Returns bottom y."""
    if not rows:
        return top
    n_rows = len(rows)
    n_cols = max(len(r) for r in rows)
    row_h = min(0.5, max_height / max(n_rows, 1))
    height = row_h * n_rows
    tbl_shape = slide.shapes.add_table(n_rows, n_cols,
                                       Inches(left), Inches(top),
                                       Inches(width), Inches(height))
    tbl = tbl_shape.table
    for i, row in enumerate(rows):
        for j in range(n_cols):
            cell = tbl.cell(i, j)
            text = row[j] if j < len(row) else ""
            cell.fill.solid()
            if i == 0:
                cell.fill.fore_color.rgb = header_rgb
                color = WHITE_RGB
                font_name = branding.MONO_FONT
                bold = True
                size = 12
            else:
                cell.fill.fore_color.rgb = PAPER_RGB if i % 2 == 0 else WHITE_RGB
                color = INK_RGB
                font_name = branding.SANS_FONT
                bold = False
                size = 12
            cell.margin_left = Emu(60000)
            cell.margin_right = Emu(60000)
            cell.margin_top = Emu(30000)
            cell.margin_bottom = Emu(30000)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = ""
            r = p.add_run()
            r.text = text
            r.font.name = font_name
            r.font.size = Pt(size)
            r.font.color.rgb = color
            r.font.bold = bold
    return top + height


def _add_card(slide, *, label: str, body: str, left: float, top: float,
              width: float, height: float, accent_rgb: RGBColor) -> None:
    """A bordered tile (paper bg + thin accent top stripe) with label + body."""
    _add_rect(slide, left=left, top=top, width=width, height=height,
              fill_rgb=PAPER_RGB)
    _add_rect(slide, left=left, top=top, width=width, height=0.06,
              fill_rgb=accent_rgb)
    _add_text(slide, label, left=left + 0.18, top=top + 0.18,
              width=width - 0.36, height=0.4,
              size=13, color_rgb=accent_rgb, font=branding.MONO_FONT, bold=True)
    _add_text(slide, body, left=left + 0.18, top=top + 0.65,
              width=width - 0.36, height=height - 0.75,
              size=12, color_rgb=INK_RGB, font=branding.SANS_FONT)


def _render_paragraph_block(slide, *, items: list[str], left: float, top: float,
                            width: float, height: float, accent_rgb: RGBColor,
                            size: float = 14) -> None:
    """Render mixed paragraphs/bullets into one textbox.

    Items beginning with the bullet sentinel "•  " (added by _parse_slide_chunk
    for <li>) render with a colored ▸ prefix in the section accent and the
    text in INK sans. Plain paragraphs render in INK sans with paragraph
    spacing. Line-spacing 1.35 throughout for readability.
    """
    if not items:
        return
    tb = slide.shapes.add_textbox(Inches(left), Inches(top),
                                  Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)

    first = True
    for item in items:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
            p.space_before = Pt(8)
        p.line_spacing = 1.35
        is_bullet = item.startswith("•  ") or item.startswith("• ")
        if is_bullet:
            text = item.lstrip("• ").strip()
            r1 = p.add_run()
            r1.text = "▸  "
            r1.font.name = branding.MONO_FONT
            r1.font.size = Pt(size)
            r1.font.color.rgb = accent_rgb
            r1.font.bold = True
            r2 = p.add_run()
            r2.text = text
            r2.font.name = branding.SANS_FONT
            r2.font.size = Pt(size)
            r2.font.color.rgb = INK_RGB
        else:
            r = p.add_run()
            r.text = item
            r.font.name = branding.SANS_FONT
            r.font.size = Pt(size)
            r.font.color.rgb = INK_RGB


def _render_media_block(slide, *, images: list[Path], tables: list[list[list[str]]],
                        left: float, top: float, width: float, height: float,
                        accent: RGBColor) -> None:
    """Render any tables (first carries accent header, rest drop to INK) and
    images (single = full bleed; multi = grid). Aspect-correct image fit with
    floor of 0.5in to avoid python-pptx errors on extreme overflow."""
    cursor = top
    for ti, tbl in enumerate(tables):
        header = accent if ti == 0 else INK_RGB
        max_h = min(2.5, (height / max(len(tables), 1)))
        cursor = _add_table(slide, rows=tbl, left=left, top=cursor,
                            width=width, max_height=max_h,
                            header_rgb=header)
        cursor += 0.2

    if not images:
        return
    remaining = (top + height) - cursor
    if remaining < 0.5:
        return

    n = len(images)
    if n == 1:
        try:
            pic = slide.shapes.add_picture(str(images[0]),
                                           Inches(left), Inches(cursor),
                                           width=Inches(width))
            pw = pic.width / 914400
            ph = pic.height / 914400
            if ph > remaining:
                new_h = max(0.5, remaining)
                new_w = max(0.5, width * (new_h / ph))
                pic.width = Inches(new_w)
                pic.height = Inches(new_h)
                pic.left = Inches(left + (width - new_w) / 2)
        except Exception as e:
            _add_text(slide, f"[image error: {Path(str(images[0])).name}: {e}]",
                      left=left, top=cursor, width=width, height=0.4,
                      size=10, color_rgb=DIM_RGB, font=branding.MONO_FONT)
    else:
        cols = 2 if n <= 4 else 3
        rows = (n + cols - 1) // cols
        gutter = 0.15
        sub_w = (width - gutter * (cols - 1)) / cols
        sub_h = (remaining - gutter * (rows - 1)) / rows
        sub_h = max(sub_h, 0.5)
        for i, img in enumerate(images):
            r, c = divmod(i, cols)
            x = left + c * (sub_w + gutter)
            y = cursor + r * (sub_h + gutter)
            try:
                pic = slide.shapes.add_picture(str(img),
                                               Inches(x), Inches(y),
                                               width=Inches(sub_w))
                pw = pic.width / 914400
                ph = pic.height / 914400
                if ph > sub_h:
                    new_h = max(0.5, sub_h)
                    new_w = max(0.5, sub_w * (new_h / ph))
                    pic.width = Inches(new_w)
                    pic.height = Inches(new_h)
                    pic.left = Inches(x + (sub_w - new_w) / 2)
            except Exception as e:
                _add_text(slide, f"[image error: {img.name}: {e}]",
                          left=x, top=y, width=sub_w, height=0.4,
                          size=9, color_rgb=DIM_RGB, font=branding.MONO_FONT)


def add_content_slide(prs, *, title: str, body_paragraphs: list[str],
                      accent_color_hex: str | None = None,
                      images: list[Path] | None = None,
                      tables: list[list[list[str]]] | None = None,
                      cards: list[dict] | None = None,
                      name: str = "", org: str = "", deck_title: str = "",
                      date: str = ""):
    """Content slide. Geometry derived from funding_report + DMG canonical.

    Layout (16:9, 13.33×7.50):
      L=0      T=0    W=0.22 H=7.50  left accent bar (section color)
      L=0.50   T=0.30 W=12.30 H=0.55 title (28pt mono INK bold) — omitted if no title
      L=0.50   T=0.95 W=12.30 H=0.005 hairline rule (RULE color)
      L=0.50   T=1.05 W=12.30 H=0.40 subtitle (13pt sans MUTED) — first short paragraph
      L=0.50   T=1.55 W=12.30 H=5.30 body region — cards/media/text by content type
      L=0.50   T=7.12 W=10.00 H=0.30 footer (9pt mono MUTED): name · org · deck · date

    Title is INK (not accent) — accent color shows on the left bar, table
    headers, bullet markers, card stripes. The whole slide reads as one
    identity through those shared accent points.
    """
    accent_hex = accent_color_hex or branding.TURQUOISE
    accent = _rgb(accent_hex)
    images = images or []
    tables = tables or []
    cards = cards or []
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)

    # Left accent bar — funding_report cohesion
    _add_rect(s, left=0, top=0, width=0.22, height=7.5, fill_rgb=accent)

    # Title at top — INK 28pt mono bold (not accent)
    title_present = bool(title)
    if title_present:
        _add_text(s, title, left=0.50, top=0.30, width=12.30, height=0.55,
                  size=28, color_rgb=INK_RGB, font=branding.MONO_FONT, bold=True)
        _add_rect(s, left=0.50, top=0.95, width=12.30, height=0.005,
                  fill_rgb=RULE_RGB)

    has_cards = bool(cards)
    has_media = bool(images) or bool(tables)
    body = list(body_paragraphs or [])

    # Promote first paragraph to subtitle/lede if it is short, prose (not a
    # bullet), and there is more content below it on the slide.
    lede = ""
    has_more_below = (len(body) > 1) or has_media or has_cards
    if body and has_more_below:
        first = body[0]
        if not first.startswith("•") and len(first) <= 220:
            lede = first
            body = body[1:]

    if lede:
        _add_text(s, lede, left=0.50, top=1.05, width=12.30, height=0.40,
                  size=13, color_rgb=MUTED_RGB, font=branding.SANS_FONT)

    # Body region — top moves up if no title (handles former "(untitled)" case)
    body_top = 1.55 if title_present else 0.40
    body_bottom = 6.85
    body_h = body_bottom - body_top
    body_l = 0.50
    body_w = 12.30

    if has_cards:
        if body:
            _render_paragraph_block(s, items=body, left=body_l, top=body_top,
                                    width=body_w, height=1.0,
                                    accent_rgb=accent, size=13)
            grid_top = body_top + 1.10
        else:
            grid_top = body_top
        n = len(cards)
        cols = 3 if n >= 3 else max(n, 1)
        rows = (n + cols - 1) // cols
        gutter = 0.20
        card_w = (body_w - gutter * (cols - 1)) / cols
        avail_h = body_bottom - grid_top
        card_h = (avail_h - gutter * (rows - 1)) / rows
        for i, card in enumerate(cards):
            r, c = divmod(i, cols)
            cx = body_l + c * (card_w + gutter)
            cy = grid_top + r * (card_h + gutter)
            _add_card(s, label=card["label"], body=card["body"],
                      left=cx, top=cy, width=card_w, height=card_h,
                      accent_rgb=accent)
    elif has_media and body:
        # Side-by-side: text 5.6in left, gutter, media right
        text_w = 5.60
        media_l = body_l + text_w + 0.40
        media_w = body_w - text_w - 0.40
        _render_paragraph_block(s, items=body, left=body_l, top=body_top,
                                width=text_w, height=body_h,
                                accent_rgb=accent, size=13)
        _render_media_block(s, images=images, tables=tables,
                            left=media_l, top=body_top,
                            width=media_w, height=body_h,
                            accent=accent)
    elif has_media:
        _render_media_block(s, images=images, tables=tables,
                            left=body_l, top=body_top,
                            width=body_w, height=body_h,
                            accent=accent)
    elif body:
        _render_paragraph_block(s, items=body, left=body_l, top=body_top,
                                width=body_w, height=body_h,
                                accent_rgb=accent, size=14)

    # Footer (lower-left): name · org · deck-title · date in 9pt mono MUTED
    footer_parts = [p for p in (name, org, deck_title, date) if p]
    if footer_parts:
        _add_text(s, "  ·  ".join(footer_parts),
                  left=0.50, top=7.12, width=10.00, height=0.30,
                  size=9, color_rgb=MUTED_RGB, font=branding.MONO_FONT)

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
    # DMG uses L=0.70 (no colorblock); we push to L=0.85 to clear the 0.6in colorblock.
    _add_rect(s, left=0.85, top=0.7, width=0.18, height=0.45, fill_rgb=accent)

    # Eyebrow uppercase label, brand color (DMG: L=1.00, T=0.70, 14pt)
    _add_text(s, label.upper(), left=1.15, top=0.7, width=11.0, height=0.4,
              size=14, color_rgb=accent, font=branding.MONO_FONT, bold=True)

    # Big section title — DMG places this at T=2.40 with a tall H=3.00 box (slack
    # for multi-line section titles), top-anchored, 44pt
    _add_text(s, label, left=0.85, top=2.4, width=12.0, height=3.0,
              size=44, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)

    # Hairline rule sits LOW — matches DMG T=5.60
    _add_rect(s, left=0.85, top=5.6, width=2.0, height=0.02, fill_rgb=accent)

    # Bottom footer — DMG places this at T=6.70
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
    _add_text(s, f'“{quote}”', left=1.5, top=2.5, width=10.3, height=2.5,
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
        _add_text(s, contact, left=1.3, top=4.8, width=11.0, height=0.5,
                  size=14, color_rgb=DIM_RGB, font=branding.MONO_FONT,
                  align=PP_ALIGN.CENTER)
    return s


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string. Used to flatten rendered HTML back to plain text."""
    return _HTML_TAG_RE.sub("", text).strip()


def _split_slides(body_html: str) -> list[str]:
    """Split rendered body HTML on <hr> elements (which markdown's `---` becomes).
    Returns a list of HTML chunks, one per slide."""
    parts = re.split(r"<hr\s*/?>", body_html)
    return [p.strip() for p in parts if p.strip()]


def _parse_table(html_table: str) -> list[list[str]]:
    """Parse a rendered HTML <table> into a list of rows, each a list of cell strings.
    First row is the header (from <th>), subsequent rows are body (<td>)."""
    rows = []
    for tr_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", html_table, re.DOTALL):
        cells = []
        for cell_match in re.finditer(r"<t[hd][^>]*>(.*?)</t[hd]>",
                                       tr_match.group(1), re.DOTALL):
            cells.append(_strip_html(cell_match.group(1)))
        if cells:
            rows.append(cells)
    return rows


def _parse_slide_chunk(html_chunk: str, *, base_dir: Path | None = None) -> dict:
    """Extract a slide title, body paragraphs, images, tables, and h3-led cards."""
    title_match = re.search(r"<(h[12])[^>]*>(.*?)</\1>", html_chunk)
    if title_match:
        title = _strip_html(title_match.group(2))
        rest = html_chunk[title_match.end():]
    else:
        title = ""
        rest = html_chunk

    # Strip out tables and images first so they don't pollute the paragraph scan
    tables: list[list[list[str]]] = []
    for tbl_match in re.finditer(r"<table[^>]*>.*?</table>", rest, re.DOTALL):
        parsed = _parse_table(tbl_match.group(0))
        if parsed:
            tables.append(parsed)
    rest_no_tables = re.sub(r"<table[^>]*>.*?</table>", "", rest, flags=re.DOTALL)

    images: list[Path] = []
    for img_match in re.finditer(r'<img[^>]+src="([^"]+)"', rest_no_tables):
        src = img_match.group(1)
        path = Path(src)
        if not path.is_absolute() and base_dir is not None:
            path = (base_dir / path).resolve()
        if path.exists():
            images.append(path)
    rest_no_media = re.sub(r"<img[^>]*/?>", "", rest_no_tables)

    # Cards: h3-led blocks. Each h3 starts a card whose body is all <p>/<li>
    # content between this h3 and the next h3 (or end).
    cards: list[dict] = []
    h3_positions = [(m.start(), m.end(), _strip_html(m.group(1)))
                    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>", rest_no_media)]
    for i, (start, end, label) in enumerate(h3_positions):
        next_start = h3_positions[i + 1][0] if i + 1 < len(h3_positions) else len(rest_no_media)
        block = rest_no_media[end:next_start]
        body_lines = []
        for m in re.finditer(r"<(p|li)[^>]*>(.*?)</\1>", block, re.DOTALL):
            text = _strip_html(m.group(2)).strip()
            if text:
                body_lines.append(text)
        cards.append({"label": label, "body": " ".join(body_lines)})

    # Paragraphs OUTSIDE the cards (i.e., before the first h3) become the slide body
    body_region = rest_no_media[:h3_positions[0][0]] if h3_positions else rest_no_media
    paragraphs = []
    for m in re.finditer(r"<(p|li)[^>]*>(.*?)</\1>", body_region, re.DOTALL):
        text = _strip_html(m.group(2)).strip()
        if text:
            if m.group(1) == "li":
                paragraphs.append(f"•  {text}")
            else:
                paragraphs.append(text)
    return {"title": title, "body": paragraphs, "images": images,
            "tables": tables, "cards": cards}


def main() -> int:
    ap = argparse.ArgumentParser(description="markdown → Jin-branded PPTX")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="suppress title slide")
    ap.add_argument("--no-end", dest="no_end", action="store_true",
                    help="suppress closing 'Thanks' slide")
    args = ap.parse_args()

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
        """Emit a content slide with the section's current accent + deck footer."""
        add_content_slide(
            prs,
            title=slide_title,
            body_paragraphs=slide_data["body"],
            images=slide_data["images"],
            tables=slide_data["tables"],
            cards=slide_data.get("cards"),
            accent_color_hex=current_accent,
            name=deck_name, org=deck_org,
            deck_title=deck_title, date=deck_date,
        )

    # Walk slide chunks; track current section accent.
    # When a chunk starts with H1, emit a section divider AND, if the chunk has
    # body content but no H2 (Jin's common pattern), use the H1 verbatim as the
    # title for the content slide that follows. Avoids "(untitled)" slides.
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
                    # If chunk has body but no H2 title of its own, use the H1
                    # text verbatim — author intent is "this section's content
                    # is THIS slide", not "this is an unrelated untitled slide".
                    slide_title = slide["title"] or section_label
                    _emit_content(slide, slide_title)
        else:
            slide = _parse_slide_chunk(chunk, base_dir=md_dir)
            if any(slide.get(k) for k in ("title", "body", "images", "tables", "cards")):
                # Empty title is OK — add_content_slide renders without title region.
                _emit_content(slide, slide["title"])

    if not args.no_end:
        add_end_slide(prs, message="Thanks",
                      contact=str(meta.get("name") or ""))

    prs.save(args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
