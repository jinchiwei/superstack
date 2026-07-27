#!/usr/bin/env python3
"""bin/lit_snowball.py — citation-graph traversal (snowballing) on OpenAlex.

Highest-recall stage of the lit pipeline: instead of matching query strings, it
walks the citation graph outward from papers you already trust.

  BACKWARD ("reference"): the seed's own reference list — the intellectual
                          ancestry.  Read from ``referenced_works`` on the seed
                          work, then batch-hydrated via the pipe-separated OR
                          filter ``?filter=openalex_id:W1|W2|W3``.
  FORWARD  ("citation"):  everything that cites the seed — the descendants.
                          ``?filter=cites:<workid>``.

Library use:

    from lit_snowball import snowball
    papers = snowball(["10.1038/nature14539"], hops=1, max_per_hop=50)

Standalone use:

    lit_snowball.py --seed 10.1038/nature14539 --seed W2741809807 \\
                    --hops 1 --max-per-hop 50 [--direction both] [--verbose]

Output (stdout): JSON array of papers, same schema as ``bin/lit-search`` plus a
``relation`` key:

  [
    {
      "title":     "<paper title>",
      "authors":   ["<author 1>", ...],
      "year":      <int or null>,
      "abstract":  "<abstract text or empty>",
      "url":       "<canonical URL>",
      "source":    "openalex",
      "relation":  "reference" | "citation"
    },
    ...
  ]

Network failures never raise: they are logged to stderr and yield [].
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
from pathlib import Path
from typing import Any

logger = logging.getLogger("lit-snowball")

MAILTO = "mrjinch@gmail.com"
USER_AGENT = f"autoresearch-lit-search/2.0 (mailto:{MAILTO})"
DEFAULT_TIMEOUT = 45  # seconds per HTTP call

OPENALEX = "https://api.openalex.org"
WORKS = f"{OPENALEX}/works"

# OpenAlex accepts long OR filters, but URLs get unwieldy past ~50 ids.
BATCH_SIZE = 50
# per-page ceiling enforced by the API
MAX_PER_PAGE = 200
# Politeness: OpenAlex asks for <10 req/s. 0.15s between paged calls is ~7/s.
SLEEP_BETWEEN_CALLS = 0.15
# Only pull the fields we actually map — keeps payloads ~10x smaller.
SELECT_FIELDS = (
    "id,doi,title,display_name,publication_year,authorships,"
    "abstract_inverted_index,primary_location,referenced_works"
)

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _url(path: str, params: dict[str, str] | None = None) -> str:
    """Build an OpenAlex URL, always carrying mailto (polite pool)."""
    qs = dict(params or {})
    qs["mailto"] = MAILTO
    # safe="|:*/" keeps the OR-filter pipes, filter colons, and cursor=* legible
    return f"{path}?{urllib.parse.urlencode(qs, safe='|:*/')}"


def _http_get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> Any:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _get_json_or_none(url: str, what: str) -> Any | None:
    """GET + parse; log and return None on any network/parse failure.

    One retry on 429/5xx, because OpenAlex occasionally throttles bursts.
    """
    for attempt, delay in enumerate([0, 3]):
        if delay:
            time.sleep(delay)
        try:
            return _http_get_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt == 0:
                continue
            logger.warning("OpenAlex %s failed: HTTP %s (%s)", what, exc.code, url)
            return None
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
            logger.warning("OpenAlex %s failed: %s", what, exc)
            return None
    return None


# ---------------------------------------------------------------------------
# Shared helpers — prefer litsrc_openalex.py's versions when that module exists
# ---------------------------------------------------------------------------


def _short_id(work_id: str) -> str:
    """'https://openalex.org/W123' -> 'W123'. Already-short ids pass through."""
    if not work_id:
        return ""
    return work_id.rstrip("/").rsplit("/", 1)[-1].strip()


def _local_reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    """Rebuild plain text from OpenAlex's {token: [positions]} inverted index."""
    if not inverted:
        return ""
    slots: list[tuple[int, str]] = []
    for token, positions in inverted.items():
        for pos in positions or []:
            if isinstance(pos, int):
                slots.append((pos, token))
    if not slots:
        return ""
    slots.sort(key=lambda kv: kv[0])
    return " ".join(tok for _, tok in slots).strip()


def _local_resolve_work_id(seed: str, *, quiet: bool = False) -> str | None:
    """Resolve a DOI / OpenAlex id / OpenAlex URL to a short 'W...' id."""
    s = (seed or "").strip()
    if not s:
        return None
    short = _short_id(s)
    if short.upper().startswith("W") and short[1:].isdigit():
        return short.upper()
    # DOI in any of its usual disguises
    low = s.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if low.startswith(prefix):
            s = s[len(prefix):]
            break
    if s.startswith("10."):
        lookup = _url(f"{WORKS}/https://doi.org/{s}", {"select": "id"})
    elif low.startswith("http"):
        lookup = _url(f"{WORKS}/{s}", {"select": "id"})
    else:
        if not quiet:
            logger.warning("unrecognised seed (want DOI or OpenAlex W-id): %r", seed)
        return None
    data = _get_json_or_none(lookup, f"resolve {seed!r}")
    if not isinstance(data, dict) or not data.get("id"):
        logger.warning("could not resolve seed %r to an OpenAlex work", seed)
        return None
    return _short_id(data["id"])


def _import_sibling_helpers() -> tuple[Any, Any]:
    """Borrow litsrc_openalex.py's helpers if that sibling module exists.

    It is owned by another agent and may not exist yet, so every failure path
    silently falls back to the local implementations above.
    """
    reconstruct, resolve = _local_reconstruct_abstract, None
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import litsrc_openalex as _oa  # type: ignore
    except Exception:
        return reconstruct, resolve
    for name in ("reconstruct_abstract", "invert_abstract", "_reconstruct_abstract"):
        fn = getattr(_oa, name, None)
        if callable(fn):
            reconstruct = fn
            break
    for name in ("resolve_work_id", "_resolve_work_id"):
        fn = getattr(_oa, name, None)
        if callable(fn):
            resolve = fn
            break
    return reconstruct, resolve


_reconstruct_abstract, _sibling_resolve = _import_sibling_helpers()


def reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    """Public wrapper: never let a sibling helper's failure kill a traversal."""
    try:
        return _reconstruct_abstract(inverted) or ""
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("abstract reconstruction failed (%s); falling back", exc)
        return _local_reconstruct_abstract(inverted)


def resolve_work_id(seed: str, *, allow_title_search: bool = False) -> str | None:
    """DOI / OpenAlex id / OpenAlex URL -> short 'W...' id, else None.

    Strict by design. litsrc_openalex.resolve_work_id() falls back to a fuzzy
    title search and returns the top hit for *any* string, which is right for a
    keyword search stage but wrong here: a mis-resolved seed does not merely
    return one bad row, it roots an entire high-recall traversal in the wrong
    neighbourhood of the graph. Junk in -> None out, and the seed is skipped.

    Pass allow_title_search=True to opt into the sibling's fuzzy behaviour when
    you genuinely have a paper *title* rather than an identifier.
    """
    wid = _local_resolve_work_id(seed, quiet=allow_title_search)
    if wid or not allow_title_search or _sibling_resolve is None:
        return _short_id(wid) if wid else None
    try:
        wid = _sibling_resolve(seed)
    except Exception as exc:
        logger.info("sibling resolve_work_id failed on %r: %s", seed, exc)
        return None
    return _short_id(wid) if wid else None


# ---------------------------------------------------------------------------
# Work -> paper dict
# ---------------------------------------------------------------------------


def _to_paper(work: dict[str, Any], relation: str) -> dict[str, Any]:
    authors = []
    for a in work.get("authorships") or []:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if name:
            authors.append(name)
    doi = work.get("doi") or ""
    url = doi or ((work.get("primary_location") or {}).get("landing_page_url") or "")
    if not url:
        url = work.get("id") or ""
    year = work.get("publication_year")
    if not isinstance(year, int):
        year = None
    return {
        "title": (work.get("title") or work.get("display_name") or "").strip(),
        "authors": authors,
        "year": year,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "url": url,
        "source": "openalex",
        "relation": relation,
        # Private bookkeeping: dedup key + next-hop frontier. Stripped before
        # a paper leaves snowball(), so the public schema stays exact.
        "_oa_id": _short_id(work.get("id") or ""),
    }


# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------


def fetch_work(work_id: str) -> dict[str, Any] | None:
    """Fetch one OpenAlex work by short id. None on failure."""
    wid = _short_id(work_id)
    if not wid:
        return None
    data = _get_json_or_none(_url(f"{WORKS}/{wid}", {"select": SELECT_FIELDS}), f"work {wid}")
    return data if isinstance(data, dict) else None


def fetch_works_batch(work_ids: list[str]) -> list[dict[str, Any]]:
    """Hydrate many works via the pipe-separated OR filter, BATCH_SIZE at a time.

    Ids that OpenAlex has merged or deleted simply do not come back; the caller
    gets fewer works than ids, which is expected and not an error.
    """
    ids = [_short_id(w) for w in work_ids if _short_id(w)]
    out: list[dict[str, Any]] = []
    for i in range(0, len(ids), BATCH_SIZE):
        chunk = ids[i:i + BATCH_SIZE]
        url = _url(WORKS, {
            "filter": f"openalex_id:{'|'.join(chunk)}",
            "per-page": str(min(len(chunk), MAX_PER_PAGE)),
            "select": SELECT_FIELDS,
        })
        data = _get_json_or_none(url, f"batch of {len(chunk)} works")
        if isinstance(data, dict):
            out.extend(r for r in (data.get("results") or []) if isinstance(r, dict))
        if i + BATCH_SIZE < len(ids):
            time.sleep(SLEEP_BETWEEN_CALLS)
    return out


def fetch_references(work_id: str, max_results: int = 50) -> list[dict[str, Any]]:
    """BACKWARD: papers the given work cites. Returns paper dicts (relation=reference)."""
    wid = _short_id(work_id)
    work = fetch_work(wid)
    if work is None:
        return []
    refs = [r for r in (work.get("referenced_works") or []) if r][:max(0, max_results)]
    if not refs:
        logger.info("%s lists no referenced_works", wid)
        return []
    time.sleep(SLEEP_BETWEEN_CALLS)
    return [_to_paper(w, "reference") for w in fetch_works_batch(refs)]


def fetch_citations(work_id: str, max_results: int = 50) -> list[dict[str, Any]]:
    """FORWARD: papers that cite the given work (relation=citation).

    Cursor-paginated, so max_results above the 200/page ceiling still works.
    """
    wid = _short_id(work_id)
    if not wid or max_results <= 0:
        return []
    out: list[dict[str, Any]] = []
    cursor = "*"
    while cursor and len(out) < max_results:
        url = _url(WORKS, {
            "filter": f"cites:{wid}",
            "per-page": str(min(max_results - len(out), MAX_PER_PAGE)),
            "select": SELECT_FIELDS,
            "cursor": cursor,
        })
        data = _get_json_or_none(url, f"citations of {wid}")
        if not isinstance(data, dict):
            break
        results = [r for r in (data.get("results") or []) if isinstance(r, dict)]
        if not results:
            break
        out.extend(_to_paper(w, "citation") for w in results)
        cursor = ((data.get("meta") or {}).get("next_cursor")) or ""
        if cursor and len(out) < max_results:
            time.sleep(SLEEP_BETWEEN_CALLS)
    return out[:max_results]


# ---------------------------------------------------------------------------
# Snowball
# ---------------------------------------------------------------------------


def snowball(
    seeds: list[str],
    hops: int = 1,
    max_per_hop: int = 50,
    *,
    direction: str = "both",
) -> list[dict[str, Any]]:
    """Traverse the OpenAlex citation graph outward from `seeds`.

    Args:
      seeds:       DOIs (``10.x/y``, ``https://doi.org/...``) and/or OpenAlex
                   work ids (``W2741809807``, ``https://openalex.org/W...``).
      hops:        1 = direct references + citers of the seeds. 2 = also the
                   neighbours of those neighbours. Larger values work but the
                   frontier is deliberately capped (below) to stay polite.
      max_per_hop: per frontier work, per direction, the cap on how many
                   neighbours to pull. It also caps how many newly-found works
                   are promoted into the next hop's frontier, which is what
                   keeps hops=2 from exploding combinatorially.
      direction:   "both" (default), "backward" (references only), or
                   "forward" (citations only).

    Returns:
      Paper dicts (schema in the module docstring) deduped by OpenAlex work id
      across all hops. Seeds themselves are never returned. Ordering is
      traversal order: hop 1 before hop 2, references before citations.
      Never raises on network failure — a dead API yields [].
    """
    if direction not in ("both", "backward", "forward"):
        logger.warning("unknown direction %r; using 'both'", direction)
        direction = "both"
    if max_per_hop <= 0 or hops <= 0:
        return []

    frontier: list[str] = []
    seen_ids: set[str] = set()
    for seed in seeds or []:
        wid = resolve_work_id(seed)
        if wid and wid not in seen_ids:
            seen_ids.add(wid)  # seeds are "seen" so we never revisit or emit them
            frontier.append(wid)
    if not frontier:
        logger.warning("no seeds resolved to OpenAlex works; nothing to traverse")
        return []
    logger.info("resolved %d seed(s): %s", len(frontier), ", ".join(frontier))

    collected: list[dict[str, Any]] = []
    for hop in range(1, hops + 1):
        next_frontier: list[str] = []
        for wid in frontier:
            neighbours: list[dict[str, Any]] = []
            if direction in ("both", "backward"):
                neighbours.extend(fetch_references(wid, max_per_hop))
                time.sleep(SLEEP_BETWEEN_CALLS)
            if direction in ("both", "forward"):
                neighbours.extend(fetch_citations(wid, max_per_hop))
                time.sleep(SLEEP_BETWEEN_CALLS)

            # Dedup first, so the next frontier only contains genuinely new
            # works and hop 2 never re-walks something hop 1 already covered.
            fresh = _dedup_extend(collected, neighbours, seen_ids)
            logger.info(
                "hop %d: %s -> %d neighbours, %d new", hop, wid, len(neighbours), len(fresh)
            )
            if len(next_frontier) < max_per_hop:
                room = max_per_hop - len(next_frontier)
                next_frontier.extend(fresh[:room])
        frontier = next_frontier
        if not frontier:
            break
    return collected


def _dedup_extend(
    collected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    seen_ids: set[str],
) -> list[str]:
    """Append not-yet-seen candidates to `collected`; return their short ids.

    The returned ids are exactly the works eligible to become the next hop's
    frontier. Private `_`-prefixed bookkeeping keys are stripped on the way in
    so `collected` only ever holds the public schema.
    """
    added: list[str] = []
    for paper in candidates:
        wid = paper.get("_oa_id") or ""
        if not wid or wid in seen_ids:
            continue
        seen_ids.add(wid)
        collected.append({k: v for k, v in paper.items() if not k.startswith("_")})
        added.append(wid)
    return added


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Snowball (citation-graph traversal) over OpenAlex."
    )
    p.add_argument(
        "--seed",
        action="append",
        default=[],
        metavar="DOI_OR_WID",
        help="DOI or OpenAlex work id; repeatable.",
    )
    p.add_argument("--hops", type=int, default=1)
    p.add_argument("--max-per-hop", type=int, default=50)
    p.add_argument(
        "--direction", default="both", choices=["both", "backward", "forward"]
    )
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    if not args.seed:
        print("at least one --seed required", file=sys.stderr)
        return 2

    papers = snowball(
        args.seed,
        hops=args.hops,
        max_per_hop=args.max_per_hop,
        direction=args.direction,
    )
    sys.stdout.write(json.dumps(papers, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0 if papers else 1


if __name__ == "__main__":
    sys.exit(main())
