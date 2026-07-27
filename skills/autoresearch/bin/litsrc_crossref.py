#!/usr/bin/env python3
"""litsrc_crossref — Crossref works search source for bin/lit-search.

Importable module:

    from litsrc_crossref import search_crossref
    papers = search_crossref("primary CNS lymphoma MRI radiomics", 10)

Each paper is a dict with exactly the lit-search schema:
  {
    "title":    "<paper title>",
    "authors":  ["<Given Family>", ...],
    "year":     <int or None>,
    "abstract": "<plain text, often empty>",
    "url":      "https://doi.org/<DOI>",
    "source":   "crossref"
  }

Crossref's value is breadth of DOI coverage (journals, books, conference
proceedings, preprint servers) — NOT abstracts. Only a minority of deposits
include an abstract, and the ones that do carry it as JATS XML, which we
flatten to plain text. An empty abstract is the normal case, not an error.

Standalone (for testing):
  python litsrc_crossref.py --query "free water diffusion MRI Alzheimer" \
                            [--max-results N] [--verbose]
prints a JSON array to stdout.

Network / API failures never raise: they are logged to stderr via `logging`
and the function returns [].
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger("lit-search.crossref")

USER_AGENT = "autoresearch-lit-search/2.0 (mailto:mrjinch@gmail.com)"
DEFAULT_TIMEOUT = 45  # seconds per HTTP call

CROSSREF = "https://api.crossref.org/works"

# Crossref allows rows<=1000, but etiquette (and response size) favours pages
# of 100. Anything larger than one page is fetched with a sleep in between.
ROWS_PER_PAGE = 100
PAGE_SLEEP = 0.5  # seconds between paged calls

# Only ask for the fields we actually map — smaller payloads are politer.
SELECT_FIELDS = "DOI,title,author,issued,abstract"

# JATS section labels Crossref deposits emit as <jats:title>; they are
# scaffolding, not abstract prose.
_JATS_LABELS = {
    "abstract", "summary", "background", "objective", "objectives", "purpose",
    "methods", "method", "materials and methods", "results", "conclusion",
    "conclusions", "introduction",
}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _http_get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> Any | None:
    """GET a JSON document. Returns None (already logged) on any failure.

    Crossref answers 429/503 when the pool is busy; one backoff retry clears
    the common case, a persistent failure means we skip the source cleanly.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    for attempt, delay in enumerate([0, 5]):
        if delay:
            time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt == 0:
                continue
            logger.warning("Crossref query failed: HTTP %s", exc.code)
            return None
        except (urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
            if attempt == 0:
                continue
            logger.warning("Crossref query failed: %s", exc)
            return None
        except Exception as exc:  # socket.timeout, ssl errors, ...
            logger.warning("Crossref query failed: %s", exc)
            return None
    return None


# ---------------------------------------------------------------------------
# JATS abstract -> plain text
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_jats(raw: str) -> str:
    """Flatten a Crossref JATS-XML abstract into plain text.

    Crossref abstracts arrive as a fragment like
        <jats:p>We studied ...</jats:p>
    often with <jats:title>Background</jats:title> section headers and
    undeclared `jats:` prefixes (so a bare ET.fromstring would raise). We wrap
    the fragment in a root that declares the prefix, parse it, drop generic
    section-label titles, and fall back to a regex tag strip if it is not
    well-formed at all.
    """
    if not raw:
        return ""
    text = ""
    wrapped = (
        '<root xmlns:jats="http://www.ncbi.nlm.nih.gov/JATS1" '
        'xmlns:mml="http://www.w3.org/1998/Math/MathML">'
        f"{raw}</root>"
    )
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError:
        text = html.unescape(_TAG_RE.sub(" ", raw))
    else:
        parts: list[str] = []

        def walk(el: ET.Element) -> None:
            tag = el.tag.rsplit("}", 1)[-1].lower()
            own = (el.text or "").strip()
            if tag == "title" and own.rstrip(":").strip().lower() in _JATS_LABELS:
                own = ""  # generic section header, not prose
            if own:
                parts.append(own)
            for child in el:
                walk(child)
                tail = (child.tail or "").strip()
                if tail:
                    parts.append(tail)

        walk(root)
        # Join with spaces, but glue trailing punctuation (JATS section titles
        # frequently leave the ":" as a separate tail node) back onto the word.
        buf = ""
        for part in parts:
            if buf and part[0] not in ",.;:)]}%":
                buf += " "
            buf += part
        text = buf

    text = _WS_RE.sub(" ", text).strip()
    # A leading bare "Abstract" survives the regex-fallback path.
    return re.sub(r"^abstract[:\s]+", "", text, flags=re.IGNORECASE).strip()


# ---------------------------------------------------------------------------
# Item -> paper dict
# ---------------------------------------------------------------------------

def _year_from_item(item: dict[str, Any]) -> int | None:
    """issued.date-parts[0][0], falling back to published/created."""
    for key in ("issued", "published", "published-print", "published-online", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                continue
    return None


def _authors_from_item(item: dict[str, Any]) -> list[str]:
    """author[] -> "Given Family"; consortia carry `name` instead."""
    authors: list[str] = []
    for au in item.get("author") or []:
        if not isinstance(au, dict):
            continue
        given = (au.get("given") or "").strip()
        family = (au.get("family") or "").strip()
        name = f"{given} {family}".strip() if (given or family) else (au.get("name") or "").strip()
        if name:
            authors.append(_WS_RE.sub(" ", name))
    return authors


def parse_crossref_item(item: dict[str, Any]) -> dict[str, Any]:
    """Map one Crossref message.items[] entry to the lit-search paper schema."""
    titles = item.get("title") or []
    title = ""
    if isinstance(titles, list) and titles:
        title = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", str(titles[0])))).strip()
    elif isinstance(titles, str):
        title = _WS_RE.sub(" ", titles).strip()

    doi = (item.get("DOI") or "").strip()
    return {
        "title": title,
        "authors": _authors_from_item(item),
        "year": _year_from_item(item),
        "abstract": strip_jats(item.get("abstract") or ""),
        "url": f"https://doi.org/{doi}" if doi else "",
        "source": "crossref",
    }


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

def search_crossref(query: str, max_results: int) -> list[dict[str, Any]]:
    """Search Crossref works. Returns [] on any failure (logged to stderr)."""
    if not query.strip() or max_results <= 0:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    offset = 0
    while len(out) < max_results:
        rows = min(ROWS_PER_PAGE, max_results - len(out))
        qs = {
            "query": query,
            "rows": str(rows),
            "offset": str(offset),
            "select": SELECT_FIELDS,
        }
        url = f"{CROSSREF}?{urllib.parse.urlencode(qs)}"
        data = _http_get_json(url)
        if data is None:
            break  # already logged; keep whatever earlier pages returned

        message = (data or {}).get("message") or {}
        items = message.get("items") or []
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            paper = parse_crossref_item(item)
            if not paper["title"]:
                continue  # Crossref indexes component/metadata records with no title
            dedup = paper["url"] or paper["title"].lower()
            if dedup in seen:
                continue
            seen.add(dedup)
            out.append(paper)

        offset += len(items)
        if len(items) < rows or offset >= int(message.get("total-results") or 0):
            break
        time.sleep(PAGE_SLEEP)  # etiquette between paged calls

    return out[:max_results]


# ---------------------------------------------------------------------------
# Standalone
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Search Crossref works.")
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    results = search_crossref(args.query, args.max_results)
    sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
