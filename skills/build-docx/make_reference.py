"""Generate reference.docx with Jin-branded styles defined.

Run once when the skill is set up. Commit the output reference.docx.
Regenerate if branding rules change.

Usage:
    python make_reference.py --output reference.docx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Wire imports to sibling _shared/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

import branding  # noqa: E402

try:
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.shared import Pt, RGBColor, Inches
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
except ImportError:
    raise SystemExit("python-docx not installed. Run: pip install python-docx")


def _hex_to_rgb(hex_str: str) -> RGBColor:
    """#FF1493 -> RGBColor(0xFF, 0x14, 0x93)"""
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _force_font_on_style(style, font_name: str) -> None:
    """Override Word's theme font fallback by setting w:rFonts attributes directly.

    python-docx's `style.font.name = X` writes only one rFonts attribute and leaves
    theme references (asciiTheme, hAnsiTheme) intact, so Word's heading styles still
    resolve to "+Headings" (Calibri by default). We explicitly set all four script
    attributes (ascii, hAnsi, cs, eastAsia) AND remove any theme attributes.
    """
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    # Set all script attributes explicitly
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), font_name)
    # Clear theme attributes that would otherwise win
    for theme_attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if rfonts.get(qn(theme_attr)) is not None:
            del rfonts.attrib[qn(theme_attr)]


def _style_run_font(style, *, font_name: str, size_pt: float, color_hex: str, bold: bool = False):
    style.font.name = font_name
    _force_font_on_style(style, font_name)
    style.font.size = Pt(size_pt)
    style.font.color.rgb = _hex_to_rgb(color_hex)
    style.font.bold = bold


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default=str(Path(__file__).resolve().parent / "reference.docx"))
    args = ap.parse_args()

    doc = Document()

    # Margins -- 1in all sides
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    # Normal -- body
    normal = doc.styles["Normal"]
    _style_run_font(normal, font_name=branding.SANS_FONT, size_pt=11, color_hex=branding.INK)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(8)

    # Heading 1
    h1 = doc.styles["Heading 1"]
    _style_run_font(h1, font_name=branding.MONO_FONT, size_pt=18,
                    color_hex=branding.HEADING_1, bold=True)
    h1.paragraph_format.space_before = Pt(24)
    h1.paragraph_format.space_after = Pt(8)

    # Heading 2
    h2 = doc.styles["Heading 2"]
    _style_run_font(h2, font_name=branding.MONO_FONT, size_pt=14,
                    color_hex=branding.HEADING_2, bold=True)
    h2.paragraph_format.space_before = Pt(18)
    h2.paragraph_format.space_after = Pt(6)

    # Heading 3
    h3 = doc.styles["Heading 3"]
    _style_run_font(h3, font_name=branding.MONO_FONT, size_pt=12,
                    color_hex=branding.HEADING_3, bold=True)
    h3.paragraph_format.space_before = Pt(14)
    h3.paragraph_format.space_after = Pt(4)

    # Title (cover) -- pandoc uses "Title" style for the document title
    style_names = [s.name for s in doc.styles]
    if "Title" in style_names:
        title = doc.styles["Title"]
        _style_run_font(title, font_name=branding.MONO_FONT, size_pt=28,
                        color_hex=branding.INK, bold=True)

    # Subtitle
    if "Subtitle" in style_names:
        subtitle = doc.styles["Subtitle"]
        _style_run_font(subtitle, font_name=branding.SANS_FONT, size_pt=13,
                        color_hex=branding.MUTED)

    # Source Code (pandoc uses this for fenced code blocks)
    try:
        sc = doc.styles["Source Code"]
    except KeyError:
        sc = doc.styles.add_style("Source Code", WD_STYLE_TYPE.PARAGRAPH)
    _style_run_font(sc, font_name=branding.MONO_FONT, size_pt=9.5, color_hex=branding.INK)

    # Verbatim Char (inline code)
    try:
        vb = doc.styles["Verbatim Char"]
    except KeyError:
        vb = doc.styles.add_style("Verbatim Char", WD_STYLE_TYPE.CHARACTER)
    _style_run_font(vb, font_name=branding.MONO_FONT, size_pt=10, color_hex=branding.INK)

    # Block Text (blockquotes)
    try:
        bt = doc.styles["Block Text"]
    except KeyError:
        bt = doc.styles.add_style("Block Text", WD_STYLE_TYPE.PARAGRAPH)
    _style_run_font(bt, font_name=branding.SANS_FONT, size_pt=11, color_hex=branding.INK)
    bt.font.italic = True
    bt.paragraph_format.left_indent = Inches(0.5)

    # Sample paragraph so the doc isn't empty (pandoc replaces these)
    doc.add_paragraph("Reference document for build-docx.", style="Normal")

    doc.save(args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
