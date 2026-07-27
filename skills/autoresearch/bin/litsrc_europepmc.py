#!/usr/bin/env python3
"""litsrc_europepmc — Europe PMC literature source for bin/lit-search.

Importable module:

    from litsrc_europepmc import search_europepmc
    papers = search_europepmc("free water diffusion MRI Alzheimer", 25)

Each paper is a dict with exactly the lit-search schema:

  {
    "title":    "<paper title>",
    "authors":  ["<author 1>", ...],
    "year":     <int or null>,
    "abstract": "<abstract text or empty>",
    "url":      "<canonical URL>",
    "source":   "europepmc"
  }

Europe PMC indexes PubMed/MEDLINE *plus* preprints (bioRxiv/medRxiv, source
"PPR"), Agricola, patents and the ETH/Chinese biomedical collections, so it is
complementary to the PubMed source rather than redundant with it.

Standalone smoke test:

    python litsrc_europepmc.py --query "primary CNS lymphoma MRI radiomics" \
        --max-results 5 [--verbose]

Network / parse failures never raise: they are logged to stderr and yield [].
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
from typing import Any

logger = logging.getLogger("lit-search.europepmc")

# OpenAlex / Crossref / Europe PMC all reward a contactable UA with faster,
# less-throttled ("polite pool") service.
USER_AGENT = "autoresearch-lit-search/2.0 (mailto:mrjinch@gmail.com)"
DEFAULT_TIMEOUT = 45  # seconds per HTTP call

EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PAGE_SIZE_CAP = 100   # API allows up to 1000; 100 keeps single calls cheap
PAGE_SLEEP = 0.34     # etiquette: ~3 req/s max when walking cursorMark pages

SOURCE_NAME = "europepmc"

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _http_get(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

_BLOCK_CLOSE_RE = re.compile(r"</(h[1-6])\s*>", re.IGNORECASE)
_PARA_RE = re.compile(r"</(p|div|li|br)\s*/?\s*>", re.IGNORECASE)
# Deliberately requires a real tag name after "<". Abstracts routinely contain
# bare inequalities ("p < 0.001", "n > 20"); a lazy `<[^>]+>` swallows every
# character between such a "<" and the next ">", silently deleting results text.
_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?/?>")
_WS_RE = re.compile(r"\s+")


def _clean_abstract(raw: str) -> str:
    """Europe PMC `abstractText` is HTML, not plain text.

    Structured abstracts arrive as ``<h4>Background</h4>Primary CNS ...<h4>
    Methods</h4>...``; unstructured ones may still carry <i>/<sub>/<p> markup.
    Turn section headers into "Label: " (matching how lit-search flattens
    PubMed's labelled <AbstractText> chunks) and drop everything else.
    """
    if not raw:
        return ""
    text = _BLOCK_CLOSE_RE.sub(": ", raw)
    text = _PARA_RE.sub(" ", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("\u00a0", " ")
    return _WS_RE.sub(" ", text).strip()


def _clean_title(raw: str) -> str:
    if not raw:
        return ""
    text = _TAG_RE.sub("", raw)
    text = html.unescape(text).replace("\u00a0", " ")
    return _WS_RE.sub(" ", text).strip()


def _authors(rec: dict[str, Any]) -> list[str]:
    """Prefer the structured authorList; fall back to the flat authorString.

    Preprint (PPR) records occasionally ship only `authorString`.
    """
    author_list = (rec.get("authorList") or {}).get("author") or []
    names = []
    for au in author_list:
        name = (au.get("fullName") or "").strip()
        if not name:
            last = (au.get("lastName") or "").strip()
            init = (au.get("initials") or "").strip()
            name = f"{last} {init}".strip()
        if not name:
            name = (au.get("collectiveName") or "").strip()
        if name:
            names.append(name)
    if names:
        return names
    flat = (rec.get("authorString") or "").strip().rstrip(".")
    return [a.strip() for a in flat.split(",") if a.strip()] if flat else []


def _year(rec: dict[str, Any]) -> int | None:
    for key in ("pubYear", "firstPublicationDate", "electronicPublicationDate"):
        val = rec.get(key)
        if not val:
            continue
        try:
            return int(str(val)[:4])
        except ValueError:
            continue
    return None


def _url(rec: dict[str, Any]) -> str:
    doi = (rec.get("doi") or "").strip()
    if doi:
        return f"https://doi.org/{doi}"
    src = (rec.get("source") or "").strip()
    ident = (rec.get("id") or "").strip()
    if src and ident:
        return f"https://europepmc.org/article/{src}/{ident}"
    pmid = (rec.get("pmid") or "").strip()
    return f"https://europepmc.org/article/MED/{pmid}" if pmid else ""


def _to_paper(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _clean_title(rec.get("title") or ""),
        "authors": _authors(rec),
        "year": _year(rec),
        "abstract": _clean_abstract(rec.get("abstractText") or ""),
        "url": _url(rec),
        "source": SOURCE_NAME,
    }


# ---------------------------------------------------------------------------
# Europe PMC
# ---------------------------------------------------------------------------

def search_europepmc(query: str, max_results: int) -> list[dict[str, Any]]:
    """Search Europe PMC and return up to `max_results` papers.

    Uses resultType=core so abstracts come back inline (the default "lite"
    result type omits abstractText entirely). Pages via cursorMark when
    max_results exceeds PAGE_SIZE_CAP, sleeping between calls.

    Returns [] — never raises — on any network, HTTP or JSON failure.
    """
    if max_results <= 0 or not query.strip():
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = "*"

    while len(out) < max_results:
        want = min(PAGE_SIZE_CAP, max_results - len(out))
        qs = {
            "query": query,
            "format": "json",
            "pageSize": str(want),
            "resultType": "core",
            "cursorMark": cursor,
        }
        url = f"{EUROPEPMC}?{urllib.parse.urlencode(qs)}"
        try:
            data = json.loads(_http_get(url))
        except urllib.error.HTTPError as exc:
            logger.warning("Europe PMC query failed: HTTP %s %s", exc.code, exc.reason)
            break
        except (urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Europe PMC query failed: %s", exc)
            break

        records = (data.get("resultList") or {}).get("result") or []
        if not records:
            break

        for rec in records:
            if not isinstance(rec, dict):
                continue
            key = (rec.get("doi") or "").lower() or f"{rec.get('source')}:{rec.get('id')}"
            if key in seen:
                continue
            seen.add(key)
            out.append(_to_paper(rec))
            if len(out) >= max_results:
                break

        next_cursor = data.get("nextCursorMark") or ""
        # Europe PMC echoes the same cursorMark on the last page — that, a
        # short page, or a missing cursor all mean "no more results".
        if not next_cursor or next_cursor == cursor or len(records) < want:
            break
        cursor = next_cursor
        time.sleep(PAGE_SLEEP)

    logger.info("Europe PMC returned %d hits for %r", len(out), query)
    return out


# ---------------------------------------------------------------------------
# Standalone driver (smoke test)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Search Europe PMC; print JSON to stdout.")
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    papers = search_europepmc(args.query, args.max_results)
    if not papers:
        print("Europe PMC returned 0 results", file=sys.stderr)
    sys.stdout.write(json.dumps(papers, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0 if papers else 1


if __name__ == "__main__":
    sys.exit(main())
