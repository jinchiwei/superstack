#!/usr/bin/env python3
"""bin/lit_fulltext.py — open-access full-text retrieval for lit-search papers.

Importable module + standalone CLI. Given a paper dict in the `lit-search`
schema:

    {"title": str, "authors": [str], "year": int|None,
     "abstract": str, "url": str, "source": str}

`fetch_fulltext(paper)` returns exactly:

    {"status": "ok" | "unavailable" | "error",
     "text":   "<plain text, <= max_chars>",
     "source": "<which route produced the text>",
     "chars":  <int len(text)>}

Resolution order
  1. Europe PMC full-text XML (`.../<PMCID>/fullTextXML`) for OA articles.
     The PMCID is resolved through the Europe PMC search API using, in order,
     DOI -> PMID -> title. JATS sections are flattened to text with `## Title`
     headings; back matter (references, funding, COI) is dropped. Methods /
     Materials sections are budgeted FIRST when truncation is needed, because
     that is where novelty is actually decided.
     -> source "europepmc-fulltext-xml"
  2. OpenAlex `best_oa_location.pdf_url` / `open_access.oa_url`. HTML is
     tag-stripped to text (source "openalex-oa-html"). A PDF target is NOT
     parsed — no PDF dependency is available — and is reported as
     status="unavailable", source="pdf-unparseable".
  3. Otherwise status="unavailable", source="paywalled".

Never bypasses a paywall and never sends credentials. Network/parse failures
are logged to stderr via `logging` and degrade to "unavailable"/"error" — they
never raise.

CLI:
  lit_fulltext.py --doi 10.3389/fbioe.2024.1392807
  lit_fulltext.py --title "..." [--url ...] [--max-chars 40000] [--preview 600]
  lit_fulltext.py --paper-json '{"title": ..., "url": ...}'
  lit_fulltext.py --papers-file hits.json --index 0
"""
from __future__ import annotations

import argparse
import hashlib
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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

logger = logging.getLogger("lit-fulltext")

USER_AGENT = "autoresearch-lit-search/2.0 (mailto:mrjinch@gmail.com)"
POLITE_MAILTO = "mrjinch@gmail.com"
DEFAULT_TIMEOUT = 45          # seconds per HTTP call
DEFAULT_MAX_CHARS = 40_000    # returned text ceiling
MAX_DOWNLOAD_BYTES = 12 << 20  # 12 MB read cap — full-text XML/HTML is smaller
POLITE_SLEEP = 0.25           # between paged/chained API calls
MIN_OA_HTML_CHARS = 3_000     # below this an OA HTML page is a stub, not full text

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
OPENALEX = "https://api.openalex.org/works"

# Sections whose titles mark the methods — budgeted first on truncation.
METHODS_RE = re.compile(
    r"^(materials?\s*(and|&)\s*methods?"
    r"|methods?\s*(and|&)\s*materials?"
    r"|methods?|methodology|methodological\s+\w+"
    r"|experimental(\s+(section|setup|set-up|procedures?|methods?|design|details))?"
    r"|(patients?|subjects?|participants?|data)\s*(and|&)\s*methods?"
    r"|study\s+(design|population|procedures?)"
    r"|statistical\s+analys[ei]s|data\s+(analysis|acquisition|collection|processing))\b"
)

# Back matter — dropped entirely; it is boilerplate and crowds out signal.
SKIP_SECTION_RE = re.compile(
    r"^(references?|bibliography|literature\s+cited"
    r"|acknowledge?ments?|acknowledgment"
    r"|(conflicts?\s+of\s+interest.*|competing\s+interests?.*|declaration\s+of\s+.*)"
    r"|author\s+(contributions?|information|note).*"
    r"|funding.*|financial\s+support.*|grant\s+support.*"
    r"|publisher.?s?\s+note|disclaimer"
    r"|supplement(al|ary)\s+(material|information|data|file).*"
    r"|abbreviations?|footnotes?)\b"
)

# Inline JATS elements whose text is citation/cross-ref noise, not prose.
_XML_SKIP_TAGS = {"xref", "ref-list", "ref", "graphic", "media", "inline-graphic",
                  "table-wrap-foot", "fn-group", "back", "front", "processing-meta"}

_HTML_SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "nav",
                   "footer", "header", "form", "aside", "iframe", "template"}
_HTML_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "section", "article",
                    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "td"}

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>&#?]+", re.I)
_PMID_URL_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)
_PMCID_RE = re.compile(r"(PMC\d+)", re.I)
_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s/?#]+?)(?:v\d+)?(?:\.pdf)?$", re.I)
_WS_RE = re.compile(r"[ \t\u00a0]+")
_NL_RE = re.compile(r"\n{3,}")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _http_get(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    accept: str = "*/*",
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> tuple[bytes, str, str]:
    """GET `url`. Returns (body, content_type, final_url). Raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read(max_bytes)
        ctype = (resp.headers.get("Content-Type") or "").lower()
        return body, ctype, resp.geturl()


def _get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> Any | None:
    """GET + parse JSON. Returns None (and warns) on any failure."""
    try:
        body, _, _ = _http_get(url, timeout=timeout, accept="application/json")
        return json.loads(body)
    except urllib.error.HTTPError as exc:
        logger.warning("GET %s failed: HTTP %s", url, exc.code)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("GET %s failed: %s", url, exc)
    except json.JSONDecodeError as exc:
        logger.warning("GET %s returned non-JSON: %s", url, exc)
    return None


# ---------------------------------------------------------------------------
# Identifier extraction
# ---------------------------------------------------------------------------

def extract_ids(paper: dict[str, Any]) -> dict[str, str]:
    """Pull {doi, pmid, pmcid, arxiv, title} out of a lit-search paper dict.

    The lit-search schema carries no explicit IDs, so everything is recovered
    from `url` (doi.org / pubmed / pmc / arxiv) plus the title as last resort.
    """
    url = (paper.get("url") or "").strip()
    title = (paper.get("title") or "").strip()
    ids: dict[str, str] = {"doi": "", "pmid": "", "pmcid": "", "arxiv": "", "title": title}

    m = _PMID_URL_RE.search(url)
    if m:
        ids["pmid"] = m.group(1)
    m = _PMCID_RE.search(url)
    if m:
        ids["pmcid"] = m.group(1).upper()
    m = _ARXIV_RE.search(url)
    if m:
        ids["arxiv"] = m.group(1)
    if "doi.org/" in url.lower() or "/10." in url:
        m = _DOI_RE.search(url)
        if m:
            ids["doi"] = m.group(0).rstrip(".,;)").lower()
    # Explicit keys win if a caller enriched the dict (e.g. from OpenAlex).
    for key in ("doi", "pmid", "pmcid"):
        val = str(paper.get(key) or "").strip()
        if val:
            ids[key] = val.lower() if key == "doi" else val.upper() if key == "pmcid" else val
    return ids


def _norm_title(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def _usable_title(title: str) -> bool:
    """A title shorter than 3 words cannot identify a paper — don't search on it."""
    return len(_norm_title(title).split()) >= 3


def _title_matches(want: str, got: str, threshold: float = 0.6) -> bool:
    """Token-overlap guard so a title search cannot silently return a different paper."""
    a = set(_norm_title(want).split())
    b = set(_norm_title(got).split())
    if not a or not b:
        return False
    return len(a & b) / len(a) >= threshold


def _lucene_escape(text: str) -> str:
    """Neutralise Lucene query syntax for Europe PMC TITLE:"..." searches."""
    return re.sub(r'["\\:()\[\]{}^~*?]', " ", text).strip()


def _openalex_search_escape(text: str) -> str:
    """Neutralise OpenAlex filter syntax.

    OpenAlex splits `filter=` values on `,` (AND) and `|` (OR) and treats `:`
    as the key separator — a title containing a comma yields HTTP 400.
    """
    return re.sub(r"\s+", " ", re.sub(r"[,|:+()\"]", " ", text)).strip()


# ---------------------------------------------------------------------------
# Europe PMC
# ---------------------------------------------------------------------------

def find_pmcid(
    *, doi: str = "", pmid: str = "", title: str = "", timeout: int = DEFAULT_TIMEOUT
) -> str:
    """Resolve a PMCID via the Europe PMC search API. Returns "" if not found."""
    # (query, is_title_query) — a title query's hits must be verified.
    queries: list[tuple[str, bool]] = []
    if doi:
        queries.append((f'DOI:"{doi}"', False))
    if pmid:
        queries.append((f"EXT_ID:{pmid} AND SRC:MED", False))
    if _usable_title(title):
        clean = _lucene_escape(title)
        if clean:
            queries.append((f'TITLE:"{clean}"', True))

    for i, (query, needs_check) in enumerate(queries):
        if i:
            time.sleep(POLITE_SLEEP)
        url = f"{EPMC}/search?" + urllib.parse.urlencode(
            {"query": query, "format": "json", "pageSize": "5", "resultType": "lite",
             "email": POLITE_MAILTO}
        )
        data = _get_json(url, timeout=timeout)
        if not data:
            continue
        results = ((data.get("resultList") or {}).get("result")) or []
        for rec in results:
            pmcid = (rec.get("pmcid") or "").upper()
            if not pmcid:
                continue
            # Europe PMC will happily return a near-miss for a fuzzy title, so
            # every title-derived hit is verified against the requested title —
            # including when an earlier DOI/PMID query simply came back empty.
            if needs_check and not _title_matches(title, rec.get("title") or ""):
                logger.info("Europe PMC title hit rejected (mismatch): %r", rec.get("title"))
                continue
            return pmcid
    return ""


def _strip_ns(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _node_text(node: ET.Element) -> str:
    """Recursive text extraction, skipping citation/figure-plumbing elements."""
    parts: list[str] = []
    for child in node:
        tag = child.tag if isinstance(child.tag, str) else ""
        if tag in _XML_SKIP_TAGS:
            if child.tail:
                parts.append(child.tail)
            continue
        if tag in ("p", "title", "sec", "list-item", "td", "caption", "abstract"):
            inner = _node_text(child)
            if inner:
                parts.append("\n" + inner + "\n")
        else:
            inner = _node_text(child)
            if inner:
                parts.append(inner)
        if child.tail:
            parts.append(child.tail)
    text = (node.text or "") + "".join(parts)
    return text


def _clean(text: str) -> str:
    text = text.replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _NL_RE.sub("\n\n", text).strip()


def _section_title(sec: ET.Element) -> str:
    t = sec.find("./title")
    if t is None:
        return ""
    return _clean(_node_text(t))


def _title_key(title: str) -> str:
    """Lowercase title with leading numbering stripped ('2.1 Methods' -> 'methods')."""
    return re.sub(r"^[\s\d.)IVXivx]+", "", (title or "")).strip().lower()


def parse_jats(xml_bytes: bytes, *, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Flatten Europe PMC JATS full text to plain text, prioritising Methods."""
    root = _strip_ns(ET.fromstring(xml_bytes))

    blocks: list[dict[str, Any]] = []

    abstract = root.find(".//front//abstract")
    if abstract is not None:
        abs_text = _clean(_node_text(abstract))
        # JATS abstracts often carry their own <title>Abstract</title>.
        abs_text = re.sub(r"^abstract\s*\n+", "", abs_text, flags=re.I)
        if abs_text:
            blocks.append({"title": "Abstract", "text": abs_text, "methods": False})

    body = root.find(".//body")
    secs = list(body.findall("./sec")) if body is not None else []
    if body is not None and not secs:
        # Some publishers deliver an unsectioned <body> of bare <p>.
        flat = _clean(_node_text(body))
        if flat:
            blocks.append({"title": "", "text": flat, "methods": False})
    for sec in secs:
        title = _section_title(sec)
        key = _title_key(title)
        if key and SKIP_SECTION_RE.match(key):
            continue
        text = _clean(_node_text(sec))
        if title and text.startswith(title):
            text = text[len(title):].lstrip()
        if not text:
            continue
        is_methods = bool(key and METHODS_RE.match(key)) or any(
            METHODS_RE.match(_title_key(_section_title(s))) for s in sec.findall("./sec")
        )
        blocks.append({"title": title, "text": text, "methods": is_methods})

    return _assemble(blocks, max_chars)


def _assemble(blocks: list[dict[str, Any]], max_chars: int) -> str:
    """Join blocks in document order; when over budget, keep Methods first."""
    rendered = [
        (f"## {b['title']}\n{b['text']}" if b["title"] else b["text"], b["methods"])
        for b in blocks
        if b["text"]
    ]
    if not rendered:
        return ""
    total = sum(len(t) for t, _ in rendered) + 2 * (len(rendered) - 1)
    if total <= max_chars:
        return "\n\n".join(t for t, _ in rendered)

    logger.info("full text %d chars > budget %d — prioritising Methods", total, max_chars)
    kept: dict[int, str] = {}
    used = 0
    # Pass 1: methods sections, up to 75% of the budget.
    methods_cap = int(max_chars * 0.75)
    for i, (text, is_methods) in enumerate(rendered):
        if not is_methods:
            continue
        room = min(methods_cap, max_chars) - used
        if room <= 200:
            break
        kept[i] = text if len(text) <= room else text[:room].rstrip() + "\n[...truncated]"
        used += len(kept[i]) + 2
    # Pass 2: everything else in document order.
    for i, (text, is_methods) in enumerate(rendered):
        if i in kept:
            continue
        room = max_chars - used
        if room <= 200:
            break
        kept[i] = text if len(text) <= room else text[:room].rstrip() + "\n[...truncated]"
        used += len(kept[i]) + 2

    out = "\n\n".join(kept[i] for i in sorted(kept))
    return out[:max_chars]


def europepmc_fulltext(
    pmcid: str, *, max_chars: int = DEFAULT_MAX_CHARS, timeout: int = DEFAULT_TIMEOUT
) -> str:
    """Fetch + flatten Europe PMC full-text XML. Returns "" when not OA/absent."""
    if not pmcid:
        return ""
    url = f"{EPMC}/{pmcid}/fullTextXML"
    try:
        body, ctype, _ = _http_get(url, timeout=timeout, accept="application/xml")
    except urllib.error.HTTPError as exc:
        # 404 = not in the OA subset. Entirely normal, not an error.
        logger.info("Europe PMC fullTextXML %s: HTTP %s", pmcid, exc.code)
        return ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("Europe PMC fullTextXML %s failed: %s", pmcid, exc)
        return ""
    if "xml" not in ctype and not body.lstrip().startswith(b"<"):
        logger.warning("Europe PMC fullTextXML %s returned %s, not XML", pmcid, ctype or "?")
        return ""
    try:
        return parse_jats(body, max_chars=max_chars)
    except ET.ParseError as exc:
        logger.warning("Europe PMC fullTextXML %s did not parse: %s", pmcid, exc)
        return ""


# ---------------------------------------------------------------------------
# OpenAlex OA location
# ---------------------------------------------------------------------------

def openalex_oa_url(
    *, doi: str = "", title: str = "", timeout: int = DEFAULT_TIMEOUT
) -> str:
    """Best open-access URL from OpenAlex (pdf_url preferred, then oa_url)."""
    work = None
    if doi:
        url = f"{OPENALEX}/doi:{urllib.parse.quote(doi, safe='')}?mailto={POLITE_MAILTO}"
        work = _get_json(url, timeout=timeout)
    if work is None and _usable_title(title):
        time.sleep(POLITE_SLEEP)
        url = f"{OPENALEX}?" + urllib.parse.urlencode(
            {"filter": f"title.search:{_openalex_search_escape(title)}",
             "per-page": "3", "mailto": POLITE_MAILTO}
        )
        data = _get_json(url, timeout=timeout)
        for cand in ((data or {}).get("results") or []):
            if _title_matches(title, cand.get("title") or cand.get("display_name") or ""):
                work = cand
                break
    if not isinstance(work, dict):
        return ""

    loc = work.get("best_oa_location") or {}
    oa = work.get("open_access") or {}
    candidates = [loc.get("pdf_url"), oa.get("oa_url")]
    # Only trust the landing page when OpenAlex says that location is itself OA
    # — otherwise it is just the publisher's paywall stub.
    if loc.get("is_oa"):
        candidates.append(loc.get("landing_page_url"))
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return ""


# ---------------------------------------------------------------------------
# HTML -> text
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._skip_tag = ""

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if self._skip_depth:
            if tag == self._skip_tag:
                self._skip_depth += 1
            return
        if tag in _HTML_SKIP_TAGS:
            self._skip_tag = tag
            self._skip_depth = 1
            return
        if tag in _HTML_BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            if tag == self._skip_tag:
                self._skip_depth -= 1
            return
        if tag in _HTML_BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def strip_html(markup: str) -> str:
    """Tag-strip an HTML document to readable plain text (stdlib only)."""
    parser = _TextExtractor()
    try:
        parser.feed(markup)
        parser.close()
    except Exception as exc:  # malformed markup — keep whatever we got
        logger.info("HTML parse ended early: %s", exc)
    return _clean(html.unescape("".join(parser.parts)))


def _looks_like_pdf(url: str, ctype: str, body: bytes) -> bool:
    return (
        "pdf" in ctype
        or body[:5] == b"%PDF-"
        or urllib.parse.urlparse(url).path.lower().endswith(".pdf")
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "autoresearch" / "lit-fulltext"


def cache_key(ids: dict[str, str], max_chars: int) -> str:
    canon = json.dumps(
        {"doi": ids.get("doi", ""), "pmid": ids.get("pmid", ""),
         "pmcid": ids.get("pmcid", ""), "t": _norm_title(ids.get("title", "")),
         "n": max_chars},
        sort_keys=True,
    )
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()


def _result(status: str, text: str, source: str) -> dict[str, Any]:
    return {"status": status, "text": text, "source": source, "chars": len(text)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_fulltext(
    paper: dict[str, Any],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    timeout: int = DEFAULT_TIMEOUT,
    cache_dir: str | Path | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Retrieve open-access full text for one lit-search paper dict.

    Returns {"status", "text", "source", "chars"}:
      status "ok"          — text retrieved (source "europepmc-fulltext-xml"
                             or "openalex-oa-html")
      status "unavailable" — no OA full text ("paywalled", "pdf-unparseable",
                             "no-identifier", "oa-html-empty")
      status "error"       — unexpected failure ("internal-error"); details on stderr

    Never raises, never bypasses a paywall, never sends credentials.
    """
    try:
        ids = extract_ids(paper if isinstance(paper, dict) else {})
        if not any((ids["doi"], ids["pmid"], ids["pmcid"], ids["title"])):
            return _result("unavailable", "", "no-identifier")

        cache_path = None
        if use_cache and cache_dir:
            cache_path = Path(cache_dir) / f"{cache_key(ids, max_chars)}.json"
            if cache_path.is_file():
                try:
                    cached = json.loads(cache_path.read_text())
                    if isinstance(cached, dict) and "status" in cached:
                        return cached
                except (OSError, json.JSONDecodeError):
                    pass  # fall through to a fresh fetch

        result = _fetch_uncached(ids, max_chars=max_chars, timeout=timeout)

        if cache_path is not None and result["status"] != "error":
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(result, ensure_ascii=False))
            except OSError as exc:
                logger.warning("could not write cache file %s: %s", cache_path, exc)
        return result
    except Exception as exc:  # belt and braces — this function must not raise
        logger.warning("fetch_fulltext failed unexpectedly: %s", exc)
        return _result("error", "", "internal-error")


def _fetch_uncached(
    ids: dict[str, str], *, max_chars: int, timeout: int
) -> dict[str, Any]:
    # --- Route 1: Europe PMC full-text XML -------------------------------
    pmcid = ids.get("pmcid") or ""
    if not pmcid:
        pmcid = find_pmcid(
            doi=ids["doi"], pmid=ids["pmid"], title=ids["title"], timeout=timeout
        )
        if pmcid:
            time.sleep(POLITE_SLEEP)
    if pmcid:
        text = europepmc_fulltext(pmcid, max_chars=max_chars, timeout=timeout)
        if text:
            return _result("ok", text, "europepmc-fulltext-xml")

    # --- Route 2: OpenAlex best OA location ------------------------------
    time.sleep(POLITE_SLEEP)
    oa_url = openalex_oa_url(doi=ids["doi"], title=ids["title"], timeout=timeout)
    if not oa_url:
        return _result("unavailable", "", "paywalled")

    if urllib.parse.urlparse(oa_url).path.lower().endswith(".pdf"):
        logger.info("OA location is a PDF (%s) — no PDF parser available", oa_url)
        return _result("unavailable", "", "pdf-unparseable")

    try:
        body, ctype, final_url = _http_get(oa_url, timeout=timeout, accept="text/html,*/*")
    except urllib.error.HTTPError as exc:
        logger.warning("OA fetch %s failed: HTTP %s", oa_url, exc.code)
        return _result("unavailable", "", "paywalled")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("OA fetch %s failed: %s", oa_url, exc)
        return _result("unavailable", "", "paywalled")

    if _looks_like_pdf(final_url, ctype, body):
        logger.info("OA location resolved to a PDF (%s) — not parsed", final_url)
        return _result("unavailable", "", "pdf-unparseable")

    text = strip_html(body.decode("utf-8", errors="replace"))[:max_chars]
    # A JS-shell or paywall-stub landing page yields a couple of KB of nav and
    # abstract text; that is not full text and pretending otherwise poisons
    # downstream novelty analysis.
    if len(text) < MIN_OA_HTML_CHARS:
        logger.info("OA HTML at %s yielded only %d chars — treating as unavailable",
                    final_url, len(text))
        return _result("unavailable", "", "oa-html-empty")
    return _result("ok", text, "openalex-oa-html")


def has_methods(text: str) -> bool:
    """True if the extracted text retained a Methods/Materials heading.

    Matches both the `## Title` headings emitted by the JATS route and the
    bare short heading lines left behind by the HTML route.
    """
    for line in (text or "").split("\n"):
        line = line.strip()
        if line.startswith("## "):
            line = line[3:].strip()
        elif len(line) > 80:
            continue
        if line and METHODS_RE.match(_title_key(line)):
            return True
    return False


def fetch_fulltext_batch(
    papers: list[dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    timeout: int = DEFAULT_TIMEOUT,
    sleep: float = 1.0,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """fetch_fulltext over a list, with a polite pause between papers."""
    out: list[dict[str, Any]] = []
    for i, paper in enumerate(papers):
        if i:
            time.sleep(sleep)
        out.append(fetch_fulltext(paper, max_chars=max_chars, timeout=timeout, **kwargs))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch open-access full text for a paper.")
    p.add_argument("--doi", default="")
    p.add_argument("--pmid", default="")
    p.add_argument("--pmcid", default="")
    p.add_argument("--title", default="")
    p.add_argument("--url", default="", help="Paper URL (DOI/PubMed/PMC/arXiv link).")
    p.add_argument("--paper-json", default="", help="A lit-search paper dict as JSON.")
    p.add_argument("--papers-file", default="", help="lit-search output JSON array.")
    p.add_argument("--index", type=int, default=0, help="Row of --papers-file to fetch.")
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    p.add_argument("--preview", type=int, default=0,
                   help="Print only the first N chars of text (0 = full text).")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    if args.papers_file:
        try:
            papers = json.loads(Path(args.papers_file).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"could not read --papers-file: {exc}", file=sys.stderr)
            return 2
        if not isinstance(papers, list) or not papers:
            print("--papers-file must contain a non-empty JSON array", file=sys.stderr)
            return 2
        if not 0 <= args.index < len(papers):
            print(f"--index out of range (0..{len(papers) - 1})", file=sys.stderr)
            return 2
        paper = papers[args.index]
    elif args.paper_json:
        try:
            paper = json.loads(args.paper_json)
        except json.JSONDecodeError as exc:
            print(f"bad --paper-json: {exc}", file=sys.stderr)
            return 2
    else:
        paper = {"title": args.title, "url": args.url or (
            f"https://doi.org/{args.doi}" if args.doi else "")}
        if args.doi:
            paper["doi"] = args.doi
        if args.pmid:
            paper["pmid"] = args.pmid
        if args.pmcid:
            paper["pmcid"] = args.pmcid

    if not isinstance(paper, dict):
        print("paper must be a JSON object", file=sys.stderr)
        return 2
    if not any(paper.get(k) for k in ("title", "url", "doi", "pmid", "pmcid")):
        print("need at least one of --doi/--pmid/--pmcid/--title/--url", file=sys.stderr)
        return 2

    result = fetch_fulltext(
        paper,
        max_chars=args.max_chars,
        cache_dir=None if args.no_cache else args.cache_dir,
        use_cache=not args.no_cache,
    )
    payload = dict(result)
    payload["methods_captured"] = has_methods(result["text"])
    payload["title"] = paper.get("title", "")
    if args.preview:
        payload["text"] = result["text"][:args.preview]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
