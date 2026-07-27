#!/usr/bin/env python3
"""lit_unpaywall.py — find a LEGAL open-access copy of a paywalled paper.

Two independent routes, both fully legitimate:

  1. Unpaywall  — DOI -> author-posted / repository / publisher OA location.
                  Free, no API key, just an identifying email.
  2. Preprint   — title -> the arXiv / bioRxiv / medRxiv version of the SAME work.
                  A large share of paywalled papers have a free preprint of record.

Ported from ~/arcadia/autofeeder/content.py (which used aiohttp) to stdlib urllib
so it carries no dependencies, matching bin/lit-search.

Deliberately NOT implemented: Sci-Hub / libgen (copyright infringement) and
archive.ph (ineffective for publisher PDFs and a circumvention route). Papers that
remain unreachable are reported as unavailable so the novelty report can state the
coverage gap plainly rather than silently degrade.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("lit-unpaywall")

EMAIL = "mrjinch@gmail.com"
UA = f"autoresearch-lit-search/2.0 (mailto:{EMAIL})"
TIMEOUT = 30

UNPAYWALL = "https://api.unpaywall.org/v2/"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ARXIV = "https://export.arxiv.org/api/query"


def _get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ------------------------------------------------------------- unpaywall ----
def find_oa_url(doi: str, email: str = EMAIL) -> dict | None:
    """DOI -> best legal OA location. Returns {url, is_pdf, version, host} or None."""
    if not doi:
        return None
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
    url = f"{UNPAYWALL}{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}"
    try:
        data = json.loads(_get(url))
    except (urllib.error.URLError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
        logger.debug("unpaywall lookup failed for %s: %s", doi, exc)
        return None

    loc = data.get("best_oa_location") or {}
    if not loc:
        for alt in data.get("oa_locations") or []:
            if alt.get("url_for_pdf") or alt.get("url"):
                loc = alt
                break
    if not loc:
        return None

    pdf, html = loc.get("url_for_pdf"), loc.get("url")
    target = pdf or html
    if not target:
        return None
    return {
        "url": target,
        "is_pdf": bool(pdf),
        "version": loc.get("version") or "",       # submittedVersion / acceptedVersion / publishedVersion
        "host": loc.get("host_type") or "",        # repository / publisher
        "route": "unpaywall",
    }


# -------------------------------------------------------------- preprint ----
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _title_match(a: str, b: str) -> bool:
    """Conservative match: normalized equality, or one containing the other (>=85% length)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    lo, hi = sorted([na, nb], key=len)
    return lo in hi and len(lo) >= 0.85 * len(hi)


def find_preprint(title: str, year: int | None = None) -> dict | None:
    """Title -> free preprint version (arXiv / bioRxiv / medRxiv) of the same work."""
    if not title:
        return None

    # --- Europe PMC preprint subset (covers bioRxiv + medRxiv) ---
    try:
        q = urllib.parse.quote(f'TITLE:"{title}" AND SRC:PPR')
        data = json.loads(_get(f"{EPMC}?query={q}&format=json&pageSize=5&resultType=lite"))
        for r in (data.get("resultList") or {}).get("result") or []:
            if _title_match(title, r.get("title", "")):
                doi = r.get("doi")
                return {
                    "url": f"https://doi.org/{doi}" if doi else
                           f"https://europepmc.org/article/PPR/{r.get('id','')}",
                    "is_pdf": False,
                    "version": "preprint",
                    "host": r.get("publisher") or "preprint-server",
                    "route": "europepmc-preprint",
                }
    except (urllib.error.URLError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
        logger.debug("europepmc preprint search failed: %s", exc)

    # --- arXiv ---
    try:
        import xml.etree.ElementTree as ET
        ns = {"a": "http://www.w3.org/2005/Atom"}
        q = urllib.parse.quote(f'ti:"{title}"')
        root = ET.fromstring(_get(f"{ARXIV}?search_query={q}&max_results=5"))
        for entry in root.findall("a:entry", ns):
            t_el = entry.find("a:title", ns)
            cand = " ".join((t_el.text or "").split()) if t_el is not None else ""
            if _title_match(title, cand):
                link = ""
                for ln in entry.findall("a:link", ns):
                    if ln.get("rel") in (None, "alternate"):
                        link = ln.get("href") or ""
                        break
                if link:
                    return {"url": link, "is_pdf": False, "version": "preprint",
                            "host": "arxiv", "route": "arxiv-preprint"}
    except Exception as exc:  # ET.ParseError included
        logger.debug("arxiv preprint search failed: %s", exc)

    return None


def resolve_open_access(doi: str = "", title: str = "", year: int | None = None) -> dict | None:
    """Try Unpaywall first (authoritative), then a preprint of the same work."""
    return find_oa_url(doi) or find_preprint(title, year)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Resolve a legal OA copy of a paper.")
    p.add_argument("--doi", default="")
    p.add_argument("--title", default="")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.WARNING)
    print(json.dumps(resolve_open_access(a.doi, a.title), indent=2))
