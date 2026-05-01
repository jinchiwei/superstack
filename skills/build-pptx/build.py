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
    """Dark #14141C background. Eyebrow turquoise mono, title white mono,
    subtitle off-white sans, name turquoise mono, org deeppink mono, date dim mono."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    if eyebrow:
        _add_text(s, eyebrow, left=1.0, top=1.5, width=11, height=0.4,
                  size=14, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, title, left=1.0, top=2.0, width=11.3, height=2.0,
              size=48, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)
    if subtitle:
        _add_text(s, subtitle, left=1.0, top=4.1, width=11.3, height=1.0,
                  size=18, color_rgb=_rgb("#E5E5EA"), font=branding.SANS_FONT)
    cursor_top = 5.4
    if name:
        _add_text(s, name, left=1.0, top=cursor_top, width=11, height=0.4,
                  size=22, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.5
    if org:
        _add_text(s, org, left=1.0, top=cursor_top, width=11, height=0.35,
                  size=16, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.45

    # Hairline rule
    _add_rect(s, left=1.0, top=cursor_top + 0.1, width=4.0, height=0.005, fill_rgb=RULE_RGB)
    if date:
        _add_text(s, date, left=1.0, top=cursor_top + 0.25, width=11, height=0.3,
                  size=12, color_rgb=DIM_RGB, font=branding.MONO_FONT)
    return s


def add_content_slide(prs, *, title: str, body_paragraphs: list[str]):
    """White background. Title turquoise mono top-left, body Geist sans."""
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)
    _add_text(s, title, left=0.6, top=0.4, width=12.5, height=0.8,
              size=32, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    # Hairline rule under title
    _add_rect(s, left=0.6, top=1.25, width=12.0, height=0.005, fill_rgb=RULE_RGB)
    body_text = "\n".join(body_paragraphs)
    _add_text(s, body_text, left=0.6, top=1.5, width=12.5, height=5.5,
              size=22, color_rgb=INK_RGB, font=branding.SANS_FONT)
    return s


def add_section_divider(prs, *, label: str, index: int = 0):
    """Full-bleed brand color. Cycles through canonical priority order."""
    bg_hex = branding.pick_section_color(index)
    text_hex = branding.section_text_color(bg_hex)
    s = _blank(prs)
    _set_bg(s, _rgb(bg_hex))
    _add_text(s, label.upper(), left=1.0, top=3.2, width=11.5, height=1.6,
              size=44, color_rgb=_rgb(text_hex), font=branding.MONO_FONT, bold=True)
    # Subtle dash
    _add_text(s, "—", left=1.0, top=4.6, width=2, height=0.5,
              size=28, color_rgb=_rgb(text_hex), font=branding.MONO_FONT)
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
    """Dark #14141C background. Bookend match for title slide."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)
    _add_text(s, message, left=1.0, top=2.7, width=11.3, height=2.0,
              size=64, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True,
              align=PP_ALIGN.CENTER)
    if contact:
        _add_text(s, contact, left=1.0, top=4.8, width=11.3, height=0.5,
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


def _parse_slide_chunk(html_chunk: str) -> dict:
    """Extract a slide title (first H1 or H2) and body paragraphs from one HTML chunk."""
    title_match = re.search(r"<(h[12])[^>]*>(.*?)</\1>", html_chunk)
    if title_match:
        title = _strip_html(title_match.group(2))
        rest = html_chunk[title_match.end():]
    else:
        title = ""
        rest = html_chunk

    paragraphs = []
    for m in re.finditer(r"<(p|li)[^>]*>(.*?)</\1>", rest, re.DOTALL):
        text = _strip_html(m.group(2)).strip()
        if text:
            if m.group(1) == "li":
                paragraphs.append(f"•  {text}")
            else:
                paragraphs.append(text)
    return {"title": title, "body": paragraphs}


def main() -> int:
    ap = argparse.ArgumentParser(description="markdown → Jin-branded PPTX")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="suppress title slide (start with first content slide)")
    ap.add_argument("--no-end", dest="no_end", action="store_true",
                    help="suppress closing 'Thanks' slide")
    args = ap.parse_args()

    loaded = load_markdown(args.input)
    meta = loaded["meta"]
    today = dt.date.today().isoformat()

    prs = new_presentation()

    # Title slide
    if not args.no_cover:
        add_title_slide(
            prs,
            eyebrow=str(meta.get("eyebrow", "")),
            title=extract_title(loaded) or Path(args.input).stem,
            subtitle=str(meta.get("subtitle", "")),
            name=str(meta.get("name", "")),
            org=str(meta.get("org", "")),
            date=str(meta.get("date") or today),
        )

    # Content slides
    chunks = _split_slides(loaded["body_html"])
    for chunk in chunks:
        slide = _parse_slide_chunk(chunk)
        if slide["title"] or slide["body"]:
            add_content_slide(prs, title=slide["title"] or "(untitled)",
                              body_paragraphs=slide["body"])

    # End slide
    if not args.no_end:
        add_end_slide(prs, message="Thanks",
                      contact=str(meta.get("name") or ""))

    prs.save(args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
