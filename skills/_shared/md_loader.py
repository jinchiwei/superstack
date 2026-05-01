"""Load a markdown file with optional YAML frontmatter, return parsed meta + HTML body.

Used by build-pdf and build-pptx. (build-docx uses pandoc directly.)
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import markdown as md_lib
import yaml


_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z",
    re.DOTALL,
)

_MD_EXTENSIONS = [
    "extra",       # tables, fenced code, footnotes, attr lists
    "smarty",      # smartypants: curly quotes + em-dash conversion (BOTH ON)
    "sane_lists",  # better list parsing
]


def load_markdown(path: str | Path) -> dict:
    """Read a markdown file. Return dict with `meta` (frontmatter dict) and
    `body_html` (rendered markdown).

    Frontmatter is YAML between `---` delimiters at the top of the file.
    If absent, `meta` is an empty dict and the entire file is treated as body.
    """
    text = Path(path).read_text()

    m = _FRONTMATTER_RE.match(text)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        body_md = m.group(2)
    else:
        meta = {}
        body_md = text

    body_html = html.unescape(md_lib.markdown(body_md, extensions=_MD_EXTENSIONS))
    return {"meta": meta, "body_html": body_html}


def extract_title(loaded: dict) -> str:
    """Pick the document title.

    Order of precedence:
      1. `title` field in frontmatter
      2. First H1 in the body
      3. Empty string (caller decides fallback)
    """
    title = loaded["meta"].get("title")
    if title:
        return str(title).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", loaded["body_html"])
    if m:
        # Strip any inline tags inside the H1
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""
