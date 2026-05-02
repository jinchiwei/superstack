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
    # Paper background fill
    _add_rect(slide, left=left, top=top, width=width, height=height,
              fill_rgb=PAPER_RGB)
    # Accent top stripe
    _add_rect(slide, left=left, top=top, width=width, height=0.06,
              fill_rgb=accent_rgb)
    # Label in accent color, mono bold
    _add_text(slide, label, left=left + 0.18, top=top + 0.18,
              width=width - 0.36, height=0.4,
              size=13, color_rgb=accent_rgb, font=branding.MONO_FONT, bold=True)
    # Body in INK, sans
    _add_text(slide, body, left=left + 0.18, top=top + 0.65,
              width=width - 0.36, height=height - 0.75,
              size=12, color_rgb=INK_RGB, font=branding.SANS_FONT)


def add_content_slide(prs, *, title: str, body_paragraphs: list[str],
                      accent_color_hex: str | None = None,
                      images: list[Path] | None = None,
                      tables: list[list[list[str]]] | None = None,
                      cards: list[dict] | None = None):
    """Content slide: white bg + thin left vertical bar in section's accent color.

    Title, hairline, table header, and any future brand-color elements all
    inherit the same accent color so the whole slide reads as one identity.
    """
    accent_hex = accent_color_hex or branding.TURQUOISE
    accent = _rgb(accent_hex)
    images = images or []
    tables = tables or []
    cards = cards or []
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)

    # Thin vertical accent bar on left (funding_report style, full height)
    _add_rect(s, left=0, top=0, width=0.22, height=7.5, fill_rgb=accent)

    # Slide title in section's accent color
    _add_text(s, title, left=0.6, top=0.4, width=12.5, height=0.8,
              size=32, color_rgb=accent, font=branding.MONO_FONT, bold=True)

    # Hairline rule under title in same accent
    _add_rect(s, left=0.6, top=1.25, width=12.0, height=0.005, fill_rgb=accent)

    has_cards = bool(cards)
    has_text = bool(body_paragraphs)
    has_media = bool(images) or bool(tables)

    # Cards take over the slide (no media side-by-side). Body text shrinks to
    # an intro paragraph above the card grid.
    if has_cards:
        if has_text:
            body_text = "\n".join(body_paragraphs)
            _add_text(s, body_text, left=0.6, top=1.5, width=12.5, height=1.2,
                      size=16, color_rgb=MUTED_RGB, font=branding.SANS_FONT)
            grid_top = 2.85
        else:
            grid_top = 1.55
        n = len(cards)
        cols = 3 if n >= 3 else max(n, 1)
        rows = (n + cols - 1) // cols
        gutter = 0.25
        avail_w = 12.5
        card_w = (avail_w - gutter * (cols - 1)) / cols
        avail_h = 7.0 - grid_top
        card_h = (avail_h - gutter * (rows - 1)) / rows
        for i, card in enumerate(cards):
            r, c = divmod(i, cols)
            cx = 0.6 + c * (card_w + gutter)
            cy = grid_top + r * (card_h + gutter)
            _add_card(s, label=card["label"], body=card["body"],
                      left=cx, top=cy, width=card_w, height=card_h,
                      accent_rgb=accent)
        return s

    media_top = 1.5

    if has_text:
        text_width = 6.0 if has_media else 12.5
        body_text = "\n".join(body_paragraphs)
        _add_text(s, body_text, left=0.6, top=1.5, width=text_width, height=5.5,
                  size=18, color_rgb=INK_RGB, font=branding.SANS_FONT)

    if has_media:
        media_left = 7.0 if has_text else 0.6
        media_width = 6.0 if has_text else 12.5
        cursor = media_top
        for ti, tbl in enumerate(tables):
            # First table on the slide carries the accent (ties to slide identity);
            # subsequent tables drop to INK so they read as supporting data.
            header = accent if ti == 0 else INK_RGB
            cursor = _add_table(s, rows=tbl, left=media_left, top=cursor,
                                width=media_width, max_height=2.5,
                                header_rgb=header)
            cursor += 0.2
        for img_path in images:
            try:
                pic = s.shapes.add_picture(
                    str(img_path),
                    Inches(media_left), Inches(cursor),
                    width=Inches(media_width),
                )
                pic_h = pic.height / 914400
                if cursor + pic_h > 7.0:
                    overflow = (cursor + pic_h) - 7.0
                    new_h = pic_h - overflow
                    new_w = media_width * (new_h / pic_h)
                    pic.height = Inches(new_h)
                    pic.width = Inches(new_w)
                    pic_h = new_h
                cursor += pic_h + 0.2
            except Exception as e:
                _add_text(s, f"[image error: {img_path.name}: {e}]",
                          left=media_left, top=cursor, width=media_width, height=0.4,
                          size=11, color_rgb=DIM_RGB, font=branding.MONO_FONT)
                cursor += 0.5
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

    # Small DMG-style accent bar — top of the slide, just right of the colorblock
    _add_rect(s, left=0.95, top=0.7, width=0.18, height=0.45, fill_rgb=accent)

    # Eyebrow uppercase label, brand color, sits next to the small accent bar
    _add_text(s, label.upper(), left=1.25, top=0.7, width=11.0, height=0.45,
              size=14, color_rgb=accent, font=branding.MONO_FONT, bold=True)

    # Big section title — sits high, plenty of breathing room below the eyebrow
    _add_text(s, label, left=0.95, top=1.45, width=11.5, height=1.6,
              size=44, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)

    # Generous gap before the hairline rule below the title
    _add_rect(s, left=0.95, top=3.4, width=2.0, height=0.02, fill_rgb=accent)

    # Bottom footer — name turquoise · org deeppink · deck muted, all mono
    footer_top = 6.85
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
            date=str(meta.get("date") or today),
        )

    # Walk slide chunks; track current section accent.
    # When a chunk's title is from an H1, treat that H1 as a section divider:
    #   - emit a section_divider slide
    #   - update current accent
    # When a chunk's title is from an H2, emit a content slide using current accent.
    chunks = _split_slides(loaded["body_html"])
    current_accent = branding.TURQUOISE  # default if first slide is H2

    for chunk in chunks:
        # Detect whether the first heading in the chunk is H1 or H2
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", chunk)
        if h1_match:
            section_label = _strip_html(h1_match.group(1))
            current_accent = branding.match_section_color(section_label)
            add_section_divider(prs, label=section_label,
                                accent_color_hex=current_accent,
                                name=deck_name, org=deck_org,
                                deck_title=deck_title)
            # Strip the H1 from the chunk so its body (if any) becomes a content slide
            remaining = chunk[h1_match.end():].strip()
            if remaining:
                slide = _parse_slide_chunk(remaining, base_dir=md_dir)
                if any(slide.get(k) for k in ("title", "body", "images", "tables", "cards")):
                    add_content_slide(prs,
                                      title=slide["title"] or "(untitled)",
                                      body_paragraphs=slide["body"],
                                      images=slide["images"],
                                      tables=slide["tables"],
                                      cards=slide.get("cards"),
                                      accent_color_hex=current_accent)
        else:
            slide = _parse_slide_chunk(chunk, base_dir=md_dir)
            if slide["title"] or slide["body"] or slide["images"] or slide["tables"]:
                add_content_slide(prs,
                                  title=slide["title"] or "(untitled)",
                                  body_paragraphs=slide["body"],
                                  images=slide["images"],
                                  tables=slide["tables"],
                                  accent_color_hex=current_accent)

    if not args.no_end:
        add_end_slide(prs, message="Thanks",
                      contact=str(meta.get("name") or ""))

    prs.save(args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
