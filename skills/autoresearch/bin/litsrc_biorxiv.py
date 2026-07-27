#!/usr/bin/env python3
"""litsrc_biorxiv — bioRxiv + medRxiv preprint search for bin/lit-search.

Preprints scoop the published literature by 6-18 months, so they are the
highest-signal source for novelty checks. This module adds them.

Why Europe PMC and not api.biorxiv.org
--------------------------------------
The native bioRxiv/medRxiv details API (https://api.biorxiv.org/details/...)
has NO keyword search — it only enumerates by date interval or resolves a
known DOI. Keyword discovery there would mean crawling every preprint posted
in a window and grepping locally: thousands of calls for one query.

Europe PMC indexes both servers and exposes a real relevance-ranked query API.
Two candidate filters were benchmarked live against three real queries
("primary CNS lymphoma MRI radiomics", "free water diffusion MRI Alzheimer",
"amyloid related imaging abnormalities lecanemab"):

  A. `<q> AND (PUBLISHER:"bioRxiv" OR PUBLISHER:"medRxiv")`
  B. `<q> AND SRC:PPR`, then post-filter on publisher

`SRC:PPR` is the broad "any preprint" flag — it also drags in Research Square,
SSRN, Authorea, etc., which are NOT the servers we want. On all three queries
the two approaches produced an identical set of bioRxiv/medRxiv records
(symmetric difference 0), so filter A is both precise and complete while
spending none of the page budget on off-server preprints. Filter A is used.

Server attribution
------------------
`bookOrReportDetails.publisher` carries the literal string "bioRxiv" or
"medRxiv", so hits are labelled per-record: source is "biorxiv" or "medrxiv".
Do NOT infer the server from the DOI prefix — bioRxiv began issuing 10.64898
DOIs alongside the legacy 10.1101 prefix, and both servers share both
prefixes (a 10.64898 DOI can be medRxiv).

Public API
----------
    search_biorxiv(query, max_results)   -> list[dict]   # bioRxiv + medRxiv
    search_medrxiv(query, max_results)   -> list[dict]   # medRxiv only
    search_preprints(query, max_results, servers=None)   # servers=None => all SRC:PPR

Every returned dict is exactly:
    {"title": str, "authors": [str], "year": int|None,
     "abstract": str, "url": str, "source": str}

Network/parse failures never raise: they are logged to stderr via `logging`
and yield [] (or whatever pages had already been collected).

Standalone:
    python litsrc_biorxiv.py --query "free water diffusion MRI Alzheimer" \
        [--max-results N] [--server biorxiv|medrxiv|both|all] [--verbose]
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
from typing import Any, Iterable

logger = logging.getLogger("lit-search.biorxiv")

# OpenAlex / Crossref / Europe PMC all give priority "polite pool" service when
# a contact mailto is present in the User-Agent.
USER_AGENT = "autoresearch-lit-search/2.0 (mailto:mrjinch@gmail.com)"
DEFAULT_TIMEOUT = 45  # seconds per HTTP call

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PAGE_SIZE = 100      # Europe PMC allows up to 1000; 100 keeps pages small/polite
PAGE_SLEEP = 0.34    # etiquette pause between paged calls
MAX_PAGES = 20       # hard stop so a bad cursor can never spin forever

# Europe PMC `bookOrReportDetails.publisher` value -> our `source` label.
_SERVER_SOURCE = {"biorxiv": "biorxiv", "medrxiv": "medrxiv"}


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
# Record normalisation
# ---------------------------------------------------------------------------

def _authors(rec: dict[str, Any]) -> list[str]:
    """Author names as "Lastname II", matching the PubMed branch of lit-search."""
    names: list[str] = []
    for au in ((rec.get("authorList") or {}).get("author") or []):
        name = (au.get("fullName") or "").strip()
        if not name:
            last = (au.get("lastName") or "").strip()
            init = (au.get("initials") or "").strip()
            name = f"{last} {init}".strip()
        if name:
            names.append(name)
    if not names:
        # authorString is "Smith J, Doe A." — trailing period, comma separated.
        raw = (rec.get("authorString") or "").rstrip(".")
        names = [a.strip() for a in raw.split(",") if a.strip()]
    return names


def _year(rec: dict[str, Any]) -> int | None:
    for candidate in (
        rec.get("pubYear"),
        (rec.get("bookOrReportDetails") or {}).get("yearOfPublication"),
        (rec.get("firstPublicationDate") or "")[:4],
    ):
        if candidate in (None, ""):
            continue
        try:
            return int(str(candidate)[:4])
        except ValueError:
            continue
    return None


def _url(rec: dict[str, Any]) -> str:
    """Canonical link: server landing page > doi.org > Europe PMC record."""
    urls = [
        (u.get("url") or "")
        for u in ((rec.get("fullTextUrlList") or {}).get("fullTextUrl") or [])
    ]
    urls = [u for u in urls if u]
    for u in urls:
        low = u.lower()
        if ("biorxiv.org" in low or "medrxiv.org" in low) and not low.endswith(".pdf"):
            return u
    doi = (rec.get("doi") or "").strip()
    if doi:
        return f"https://doi.org/{doi}"
    for u in urls:  # a .pdf link beats nothing
        return u
    rec_id = (rec.get("id") or "").strip()
    return f"https://europepmc.org/article/PPR/{rec_id}" if rec_id else ""


def _publisher(rec: dict[str, Any]) -> str:
    return ((rec.get("bookOrReportDetails") or {}).get("publisher") or "").strip()


def _normalise(rec: dict[str, Any]) -> dict[str, Any]:
    publisher = _publisher(rec)
    source = _SERVER_SOURCE.get(publisher.lower(), "preprint")
    return {
        "title": (rec.get("title") or "").strip().rstrip("."),
        "authors": _authors(rec),
        "year": _year(rec),
        "abstract": " ".join((rec.get("abstractText") or "").split()),
        "url": _url(rec),
        "source": source,
    }


# ---------------------------------------------------------------------------
# Europe PMC query
# ---------------------------------------------------------------------------

def _epmc_search(query: str, max_results: int) -> list[dict[str, Any]]:
    """Cursor-paged Europe PMC search. Returns raw records, never raises."""
    out: list[dict[str, Any]] = []
    cursor = "*"
    for page in range(MAX_PAGES):
        want = max_results - len(out)
        if want <= 0:
            break
        qs = {
            "query": query,
            "format": "json",
            "resultType": "core",  # `core` is what carries abstractText + authorList
            "pageSize": str(min(want, PAGE_SIZE)),
            "cursorMark": cursor,
        }
        url = f"{EPMC}?{urllib.parse.urlencode(qs)}"
        try:
            data = json.loads(_http_get(url))
        except urllib.error.HTTPError as exc:
            logger.warning("Europe PMC preprint query failed: HTTP %s", exc.code)
            return out
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Europe PMC preprint query failed: %s", exc)
            return out
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Europe PMC returned unparseable JSON: %s", exc)
            return out

        hits = ((data.get("resultList") or {}).get("result")) or []
        if not hits:
            break
        out.extend(hits)

        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor:
            break  # Europe PMC drops nextCursorMark on the final page
        cursor = next_cursor
        if len(out) < max_results:
            time.sleep(PAGE_SLEEP)
    return out[:max_results]


def _publisher_clause(servers: Iterable[str]) -> str:
    terms = " OR ".join(f'PUBLISHER:"{s}"' for s in servers)
    return f"({terms})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_preprints(
    query: str,
    max_results: int,
    servers: Iterable[str] | None = ("bioRxiv", "medRxiv"),
) -> list[dict[str, Any]]:
    """Search preprint servers via Europe PMC.

    Args:
        query: free-text query (Europe PMC syntax is accepted verbatim).
        max_results: maximum papers to return.
        servers: publisher names to restrict to, e.g. ("bioRxiv", "medRxiv").
            Pass None to search *every* preprint server Europe PMC indexes
            (SRC:PPR — also Research Square, SSRN, Authorea, ...), in which
            case off-server hits carry source "preprint".

    Returns:
        List of paper dicts. Empty on any network/parse failure.
    """
    query = (query or "").strip()
    if not query or max_results <= 0:
        return []

    servers = list(servers) if servers is not None else []
    if servers:
        full_query = f"({query}) AND {_publisher_clause(servers)}"
    else:
        full_query = f"({query}) AND SRC:PPR"

    records = _epmc_search(full_query, max_results)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    wanted = {s.lower() for s in servers}
    for rec in records:
        # Defence in depth: the PUBLISHER filter is server-side, but a record
        # with missing/odd publisher metadata must not sneak through mislabelled.
        if wanted and _publisher(rec).lower() not in wanted:
            continue
        paper = _normalise(rec)
        dedup = (rec.get("doi") or rec.get("id") or paper["title"]).lower()
        if dedup in seen:
            continue
        seen.add(dedup)
        out.append(paper)
    return out


def search_biorxiv(query: str, max_results: int) -> list[dict[str, Any]]:
    """Search bioRxiv AND medRxiv. Hits are labelled per-record with
    source "biorxiv" or "medrxiv" (from Europe PMC's publisher field)."""
    return search_preprints(query, max_results, servers=("bioRxiv", "medRxiv"))


def search_medrxiv(query: str, max_results: int) -> list[dict[str, Any]]:
    """Search medRxiv only (clinical preprints). source is always "medrxiv"."""
    return search_preprints(query, max_results, servers=("medRxiv",))


# ---------------------------------------------------------------------------
# Standalone driver
# ---------------------------------------------------------------------------

_SERVER_CHOICES = {
    "both": ("bioRxiv", "medRxiv"),
    "biorxiv": ("bioRxiv",),
    "medrxiv": ("medRxiv",),
    "all": None,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Search bioRxiv/medRxiv preprints.")
    p.add_argument("--query", required=True)
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument(
        "--server",
        default="both",
        choices=sorted(_SERVER_CHOICES),
        help="both (default) | biorxiv | medrxiv | all (every preprint server)",
    )
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    papers = search_preprints(
        args.query, args.max_results, servers=_SERVER_CHOICES[args.server]
    )
    if not papers:
        logger.info("0 preprints for %r", args.query)
    sys.stdout.write(json.dumps(papers, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
