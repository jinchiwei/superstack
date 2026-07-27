#!/usr/bin/env python3
"""bin/litsrc_openalex.py — OpenAlex source module for lit-search.

Importable module:

    from litsrc_openalex import search_openalex, resolve_work_id

    search_openalex(query, max_results) -> list[dict]
        Each dict is exactly:
          {
            "title":    "<paper title>",
            "authors":  ["<author 1>", ...],
            "year":     <int or null>,
            "abstract": "<reconstructed abstract or empty>",
            "url":      "<DOI url, else OpenAlex work url>",
            "source":   "openalex"
          }

    resolve_work_id(doi_or_title) -> "W2741809807" | None
        DOI lookup first (/works/doi:<doi>), then a title search fallback.
        Used by the snowball (citation-chasing) module.

Standalone:
    python litsrc_openalex.py --query "free water diffusion MRI Alzheimer" --max-results 5
    python litsrc_openalex.py --resolve "10.1038/nature12373"

Network / parse failures never raise: they are logged to stderr via `logging`
and the function returns [] (or None for resolve_work_id).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("lit-search.openalex")

USER_AGENT = "autoresearch-lit-search/2.0 (mailto:mrjinch@gmail.com)"
MAILTO = "mrjinch@gmail.com"  # OpenAlex "polite pool" — faster, more reliable service
DEFAULT_TIMEOUT = 45  # seconds per HTTP call

OPENALEX = "https://api.openalex.org/works"
PER_PAGE_MAX = 200  # OpenAlex hard cap on per-page
PAGE_SLEEP = 0.2    # etiquette: small pause between paged calls

SOURCE_NAME = "openalex"

# Fields we actually consume — asking for a subset keeps payloads small and fast.
_SELECT = "id,doi,display_name,publication_year,authorships,abstract_inverted_index"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _http_get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> Any | None:
    """GET a URL and parse JSON. Returns None on any network/parse failure."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        # 404 on a /works/doi: lookup is an expected "not found", not a fault.
        level = logger.info if exc.code == 404 else logger.warning
        level("OpenAlex request failed: HTTP %s for %s", exc.code, url)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("OpenAlex request failed: %s", exc)
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("OpenAlex returned unparseable JSON: %s", exc)
        return None


def _qs(params: dict[str, str]) -> str:
    """Encode a query string, always including the polite-pool mailto."""
    params = dict(params)
    params.setdefault("mailto", MAILTO)
    return urllib.parse.urlencode(params)


# ---------------------------------------------------------------------------
# Abstract reconstruction
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    """Rebuild plain text from OpenAlex's `abstract_inverted_index`.

    The index maps each token to every position it occupies, e.g.
        {"Free": [0], "water": [1, 7], "imaging": [2]}
    -> "Free water imaging ... water ..."

    Positions can be sparse or non-contiguous (OpenAlex drops some tokens), so
    we build a position->token map and emit it in sorted position order rather
    than indexing into a pre-sized list. Malformed entries are skipped, never
    raised on.
    """
    if not inverted or not isinstance(inverted, dict):
        return ""
    slots: dict[int, str] = {}
    for word, positions in inverted.items():
        if not isinstance(positions, (list, tuple)):
            continue
        for pos in positions:
            if isinstance(pos, int) and not isinstance(pos, bool):
                slots[pos] = word
    if not slots:
        return ""
    return " ".join(slots[i] for i in sorted(slots)).strip()


# ---------------------------------------------------------------------------
# Record mapping
# ---------------------------------------------------------------------------

def _short_id(openalex_id: str | None) -> str | None:
    """'https://openalex.org/W2741809807' -> 'W2741809807'."""
    if not openalex_id:
        return None
    tail = str(openalex_id).rstrip("/").rsplit("/", 1)[-1].strip()
    return tail or None


def _map_work(work: dict[str, Any]) -> dict[str, Any]:
    """Map one OpenAlex work record onto the shared paper schema."""
    authors: list[str] = []
    for a in work.get("authorships") or []:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if name:
            authors.append(name)

    year = work.get("publication_year")
    if not isinstance(year, int) or isinstance(year, bool):
        try:
            year = int(year)  # some records ship the year as a string
        except (TypeError, ValueError):
            year = None

    doi = work.get("doi") or ""
    if doi and not doi.startswith("http"):
        doi = f"https://doi.org/{doi.lstrip('/')}"
    url = doi or work.get("id") or ""

    return {
        "title": (work.get("display_name") or "").strip(),
        "authors": authors,
        "year": year,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "url": url,
        "source": SOURCE_NAME,
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_openalex(query: str, max_results: int) -> list[dict[str, Any]]:
    """Search OpenAlex works for `query`, returning up to `max_results` papers.

    Pages transparently when max_results > 200 (the OpenAlex per-page cap).
    Never raises — logs to stderr and returns [] on failure.
    """
    query = (query or "").strip()
    if not query or max_results <= 0:
        return []

    # `page` is an offset in units of `per-page`, so the page size MUST stay
    # constant across calls — shrinking it on the last page re-serves rows we
    # already have. Fetch full pages and trim at the end instead.
    page_size = min(PER_PAGE_MAX, max_results)

    out: list[dict[str, Any]] = []
    page = 1
    while len(out) < max_results:
        url = f"{OPENALEX}?{_qs({'search': query, 'per-page': str(page_size), 'page': str(page), 'select': _SELECT})}"
        if page > 1:
            time.sleep(PAGE_SLEEP)  # API etiquette between paged calls
        data = _http_get_json(url)
        if not isinstance(data, dict):
            break  # already logged; keep whatever we have
        results = data.get("results")
        if not isinstance(results, list) or not results:
            break
        for work in results:
            if isinstance(work, dict):
                out.append(_map_work(work))
        if len(results) < page_size:
            break  # exhausted the result set
        page += 1

    return out[:max_results]


# ---------------------------------------------------------------------------
# Work-ID resolution (used by the snowball module)
# ---------------------------------------------------------------------------

def _clean_doi(text: str) -> str | None:
    """Extract a bare DOI ('10.xxxx/yyy') from a raw string, or None."""
    t = (text or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "DOI:"):
        if t.lower().startswith(prefix.lower()):
            t = t[len(prefix):].strip()
    return t if t.startswith("10.") and "/" in t else None


def resolve_work_id(doi_or_title: str) -> str | None:
    """Resolve a DOI or a paper title to an OpenAlex work ID ('W2741809807').

    Tries the DOI endpoint first (exact, cheap); falls back to a title search
    and takes the top hit. Returns None if nothing resolves.
    """
    text = (doi_or_title or "").strip()
    if not text:
        return None

    doi = _clean_doi(text)
    if doi:
        url = f"{OPENALEX}/doi:{urllib.parse.quote(doi, safe='')}?{_qs({'select': 'id'})}"
        data = _http_get_json(url)
        if isinstance(data, dict):
            wid = _short_id(data.get("id"))
            if wid:
                return wid
        logger.info("DOI lookup did not resolve (%s); falling back to title search", doi)
        time.sleep(PAGE_SLEEP)

    # Title search fallback — `title.search` filter is stricter than free `search`.
    for params in (
        {"filter": f"title.search:{text}", "per-page": "1", "select": "id"},
        {"search": text, "per-page": "1", "select": "id"},
    ):
        data = _http_get_json(f"{OPENALEX}?{_qs(params)}")
        if isinstance(data, dict):
            results = data.get("results") or []
            if results and isinstance(results[0], dict):
                wid = _short_id(results[0].get("id"))
                if wid:
                    return wid
        time.sleep(PAGE_SLEEP)

    logger.info("could not resolve OpenAlex work id for %r", text[:80])
    return None


# ---------------------------------------------------------------------------
# Standalone driver (testing)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Query OpenAlex works (lit-search source module).")
    p.add_argument("--query", help="Free-text search query.")
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--resolve", help="DOI or title to resolve to an OpenAlex work ID.")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    if not args.query and not args.resolve:
        p.error("one of --query or --resolve is required")

    if args.resolve:
        wid = resolve_work_id(args.resolve)
        print(json.dumps({"query": args.resolve, "work_id": wid}, ensure_ascii=False, indent=2))
        if not args.query:
            return 0 if wid else 1

    papers = search_openalex(args.query, args.max_results)
    print(json.dumps(papers, ensure_ascii=False, indent=2))
    return 0 if papers else 1


if __name__ == "__main__":
    sys.exit(main())
