"""build-pdf — render a markdown file to a Jin-branded PDF.

Usage:
    python build.py --input doc.md --output doc.pdf
    python build.py --input doc.md --output doc.pdf --toc --watermark DRAFT

All branding (palette, fonts) comes from skills/_shared/branding.py.
Markdown → HTML via skills/_shared/md_loader.py (smartypants ON).
HTML → PDF via weasyprint.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as html_mod
import os
import sys
from pathlib import Path

# On macOS, weasyprint's cffi bindings need GTK/GLib from Homebrew.
# Set DYLD_LIBRARY_PATH before the import so dlopen() finds libgobject etc.
if sys.platform == "darwin" and not os.environ.get("DYLD_LIBRARY_PATH"):
    _brew_lib = "/opt/homebrew/lib"
    if Path(_brew_lib).is_dir():
        os.environ["DYLD_LIBRARY_PATH"] = _brew_lib

# Wire up imports to the sibling _shared/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))

import branding  # noqa: E402
from md_loader import extract_title, load_markdown  # noqa: E402

try:
    from weasyprint import CSS, HTML
except ImportError:
    raise SystemExit("weasyprint not installed. Run: pip install weasyprint")


def _css_template(*, watermark: str | None, running_header: str | None) -> str:
    """Generate the print CSS. Inlined into the rendered HTML."""
    wm_block = ""
    if watermark:
        wm_block = f"""
.watermark {{
  position: fixed;
  top: 5in; left: 1in;
  font-family: {branding.MONO_FONT_STACK};
  font-size: 80pt; font-weight: 700;
  color: {branding.RULE};
  opacity: 0.18;
  transform: rotate(-30deg);
  pointer-events: none;
  z-index: -1;
}}
"""
    rh_block = ""
    if running_header:
        safe_rh = html_mod.escape(running_header).replace('"', r'\"')
        rh_block = f"""
@page {{
  @top-center {{
    content: "{safe_rh}";
    font-family: {branding.MONO_FONT_STACK};
    font-size: 8pt; color: {branding.MUTED};
  }}
}}
@page :first {{ @top-center {{ content: ""; }} }}
"""

    return f"""
/* CJK glyph mapping: WeasyPrint's CSS font-family fallback is unreliable
 * for CJK characters — it tends to stay on the primary font even when
 * glyphs are missing.  Using @font-face with unicode-range tells the
 * engine explicitly to use PingFang TC (with Heiti TC fallback) for
 * CJK codepoints, regardless of which font-family is set elsewhere.
 *
 * Ranges covered:
 *   U+3000-303F  CJK Symbols and Punctuation (、。「」etc)
 *   U+3400-4DBF  CJK Extension A (rare hanzi)
 *   U+4E00-9FFF  CJK Unified Ideographs (main hanzi block)
 *   U+F900-FAFF  CJK Compatibility Ideographs
 *   U+FF00-FFEF  Halfwidth and Fullwidth Forms */
@font-face {{
  font-family: 'CJK';
  src: local('PingFang TC'), local('Heiti TC'), local('PingFang SC'),
       local('Hiragino Sans GB'), local('Noto Sans CJK TC');
  unicode-range: U+3000-303F, U+3400-4DBF, U+4E00-9FFF,
                 U+F900-FAFF, U+FF00-FFEF;
}}
@font-face {{
  font-family: 'CJK';
  font-weight: bold;
  src: local('PingFang TC Semibold'), local('PingFang TC Bold'),
       local('Heiti TC Medium'), local('PingFang SC Semibold'),
       local('Hiragino Sans GB W6'), local('Noto Sans CJK TC Bold');
  unicode-range: U+3000-303F, U+3400-4DBF, U+4E00-9FFF,
                 U+F900-FAFF, U+FF00-FFEF;
}}

@page {{
  size: Letter;
  margin: 1in;
  @bottom-center {{
    content: counter(page);
    font-family: {branding.MONO_FONT_STACK};
    font-size: 8pt; color: {branding.DIM};
  }}
}}
@page :first {{
  @bottom-center {{ content: ""; }}
}}
{rh_block}

* {{ box-sizing: border-box; }}

html, body {{
  font-family: {branding.SANS_FONT_STACK};
  color: {branding.INK};
  font-size: 11pt; line-height: 1.55;
}}

/* === Cover page === */
.cover {{ page-break-after: always; }}
.cover .eyebrow {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 10pt; color: {branding.EYEBROW_LIGHT};
  font-weight: 700; letter-spacing: 0.08em;
  margin: 0 0 8pt 0;
}}
.cover .title {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 28pt; font-weight: 700; color: {branding.INK};
  margin: 0 0 8pt 0; line-height: 1.15;
}}
.cover .subtitle {{
  font-family: {branding.SANS_FONT_STACK};
  font-size: 13pt; color: {branding.MUTED};
  margin: 0 0 14pt 0;
}}
.cover .name {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 12pt; font-weight: 700; color: {branding.NAME_COLOR};
  margin: 0 0 2pt 0;
}}
.cover .org {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 10pt; font-weight: 700; color: {branding.ORG_COLOR};
  margin: 0 0 14pt 0;
}}
.cover hr.cover-rule {{
  border: none; border-top: 0.5pt solid {branding.RULE};
  margin: 14pt 0; width: 40%;
}}
.cover .date {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 10pt; color: {branding.DIM}; margin: 0;
}}

/* === Body headings === */
h1 {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 18pt; font-weight: 700;
  color: {branding.HEADING_1};
  margin: 24pt 0 8pt 0;
  bookmark-level: 1; bookmark-label: content(text);
  page-break-after: avoid;
}}
h2 {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 14pt; font-weight: 700;
  color: {branding.HEADING_2};
  margin: 18pt 0 6pt 0;
  bookmark-level: 2; bookmark-label: content(text);
  page-break-after: avoid;
}}
h3 {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 12pt; font-weight: 700;
  color: {branding.HEADING_3};
  margin: 14pt 0 4pt 0;
  page-break-after: avoid;
}}

/* === Body content === */
p, li {{
  font-family: {branding.SANS_FONT_STACK};
  color: {branding.INK};
}}
ul, ol {{ padding-left: 1.4em; }}
li {{ margin: 2pt 0; }}

/* Hyperlinks in turquoise — brand accent for clickable URLs in body text. */
a, a:link, a:visited {{
  color: {branding.TURQUOISE};
  text-decoration: underline;
}}

code {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 9.5pt; color: {branding.INK};
}}
pre {{
  font-family: {branding.MONO_FONT_STACK};
  font-size: 9.5pt; color: {branding.INK};
  background: {branding.PAPER};
  border-left: 2pt solid #E5E5EA;
  padding: 8pt 12pt; margin: 8pt 0;
  white-space: pre-wrap; word-wrap: break-word;
}}
pre code {{ background: transparent; padding: 0; }}

table {{
  width: 100%; border-collapse: collapse; margin: 10pt 0;
  font-family: {branding.MONO_FONT_STACK}; font-size: 9.5pt;
}}
th {{
  text-align: left; padding: 6pt 8pt;
  border-bottom: 1pt solid {branding.INK};
  color: {branding.MUTED}; font-weight: 700; letter-spacing: 0.04em;
}}
td {{
  padding: 5pt 8pt; border-bottom: 0.5pt solid #EEEEF2;
  color: {branding.INK};
}}

hr {{
  border: none; border-top: 0.5pt solid {branding.RULE};
  margin: 14pt 0;
}}

/* === Images === */
img {{
  max-width: 100%; height: auto;
  display: block; margin: 12pt auto;
}}

/* === TOC === */
.toc {{ page-break-after: always; }}
.toc h1 {{
  font-size: 16pt; color: {branding.INK}; margin-bottom: 14pt;
  bookmark-level: none;
}}
.toc ul {{ list-style: none; padding-left: 0; }}
.toc li {{ margin: 4pt 0; font-family: {branding.MONO_FONT_STACK}; font-size: 10pt; }}
.toc a {{ text-decoration: none; color: {branding.INK}; }}

{wm_block}
"""


def _render_cover(meta: dict, default_date: str) -> str:
    """Render the cover page HTML. Optional fields render only if present."""
    parts = ['<div class="cover">']
    if meta.get("eyebrow"):
        parts.append(f'<p class="eyebrow">{html_mod.escape(str(meta["eyebrow"]))}</p>')
    title = meta.get("title", "")
    parts.append(f'<h1 class="title">{html_mod.escape(str(title))}</h1>')
    if meta.get("subtitle"):
        parts.append(f'<p class="subtitle">{html_mod.escape(str(meta["subtitle"]))}</p>')
    if meta.get("name"):
        # Name field accepts raw HTML so a cover can inline-style portions
        # of the byline (e.g. a co-author in INK followed by your name in
        # the default turquoise: '<span style="color:#14141C">Cousin,</span> Self').
        # The default .name class colors everything turquoise; any inline
        # span with an explicit color wins.
        parts.append(f'<p class="name">{meta["name"]}</p>')
    if meta.get("org"):
        parts.append(f'<p class="org">{html_mod.escape(str(meta["org"]))}</p>')
    parts.append('<hr class="cover-rule" />')
    date = str(meta.get("date") or default_date)
    parts.append(f'<p class="date">{html_mod.escape(date)}</p>')
    parts.append('</div>')
    return "\n".join(parts)


def _render_toc_stub() -> str:
    """A simple visible TOC placeholder. The real navigation is via PDF outline
    (clickable bookmarks emitted by the body's bookmark-level CSS).
    """
    return (
        '<div class="toc">'
        '<h1>Contents</h1>'
        f'<p style="font-family: {branding.SANS_FONT_STACK}; '
        f'font-size: 10pt; color: {branding.MUTED};">'
        'See PDF outline pane for clickable navigation.</p>'
        '</div>'
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="markdown file to render")
    ap.add_argument("--output", required=True, help="output PDF path")
    ap.add_argument("--toc", action="store_true", help="include visible TOC page")
    ap.add_argument("--watermark", help="diagonal watermark text on every page")
    ap.add_argument("--running-header", dest="running_header",
                    help="text in top margin of every page after cover")
    ap.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="suppress cover page")
    args = ap.parse_args()

    loaded = load_markdown(args.input)
    meta = loaded["meta"]
    body_html = loaded["body_html"]

    if not extract_title(loaded):
        print("warning: document has no title (no frontmatter `title` and no H1)", file=sys.stderr)

    today = dt.date.today().isoformat()

    parts = ["<html><body>"]
    if args.watermark:
        parts.append(f'<div class="watermark">{html_mod.escape(args.watermark)}</div>')
    if not args.no_cover:
        parts.append(_render_cover(meta, default_date=today))
    if args.toc:
        parts.append(_render_toc_stub())
    parts.append('<div class="body">')
    parts.append(body_html)
    parts.append('</div>')
    parts.append("</body></html>")

    css = _css_template(watermark=args.watermark, running_header=args.running_header)
    # base_url so relative image paths in the markdown resolve against the
    # markdown's directory, not the cwd of the invocation.
    base_url = str(Path(args.input).resolve().parent)
    HTML(string="\n".join(parts), base_url=base_url).write_pdf(
        args.output, stylesheets=[CSS(string=css)])
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
