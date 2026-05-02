"""plan.py — slide-ID derivation + Plan JSON schema for build-pptx.

Data-layer only. Not wired into build.py yet (that happens in Task 5).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    """Lowercase, hyphen-separated slug. Strips non-alphanumeric runs."""
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------------------
# Slide-ID derivation
# ---------------------------------------------------------------------------

def derive_slide_id(*, h1: str | None, h2: str | None,
                    auto_index: int) -> str:
    """Hashable, stable ID from section context.

    Examples:
      h1='Executive summary', h2=None       -> 'h1-executive-summary'
      h1='Methods', h2='Cohorts'            -> 'h1-methods/h2-cohorts'
      h1=None, h2='Headline numbers'        -> 'h2-headline-numbers'
      h1=None, h2=None, auto_index=3        -> 'auto-3'

    Slide IDs need to be stable across markdown edits that don't touch the
    section structure, so the cache survives content tweaks but invalidates
    on intentional reorganizations."""
    parts = []
    if h1:
        parts.append(f"h1-{_slug(h1)}")
    if h2:
        parts.append(f"h2-{_slug(h2)}")
    if not parts:
        parts.append(f"auto-{auto_index}")
    return "/".join(parts)


def derive_slide_ids_from_chunks(chunks: list[str]) -> list[str]:
    """Walk a list of HTML chunks (output of _split_slides) and derive a
    stable slide ID for each. Tracks the most recent H1 across chunks so
    H2 children inherit the right parent in their ID. Disambiguates
    duplicate IDs by appending '-2', '-3' etc."""
    # Read each chunk, find the FIRST h1 or h2 element. The h1 sets the
    # current section; subsequent chunks without their own h1 attach to
    # that section's h1.
    ids: list[str] = []
    seen: dict[str, int] = {}
    current_h1: str | None = None
    auto_idx = 0
    for chunk in chunks:
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", chunk, re.DOTALL)
        h2_match = re.search(r"<h2[^>]*>(.*?)</h2>", chunk, re.DOTALL)
        from layouts._common import _strip_html
        chunk_h1 = _strip_html(h1_match.group(1)) if h1_match else None
        chunk_h2 = _strip_html(h2_match.group(1)) if h2_match else None
        if chunk_h1:
            current_h1 = chunk_h1
        # Build the ID
        if chunk_h1 and not chunk_h2:
            base_id = derive_slide_id(h1=chunk_h1, h2=None, auto_index=auto_idx)
        elif chunk_h2:
            base_id = derive_slide_id(h1=current_h1, h2=chunk_h2,
                                      auto_index=auto_idx)
        elif chunk_h1:
            base_id = derive_slide_id(h1=chunk_h1, h2=None, auto_index=auto_idx)
        else:
            auto_idx += 1
            base_id = derive_slide_id(h1=None, h2=None, auto_index=auto_idx)
        # Disambiguate
        n = seen.get(base_id, 0)
        seen[base_id] = n + 1
        slide_id = base_id if n == 0 else f"{base_id}-{n + 1}"
        ids.append(slide_id)
    return ids


# ---------------------------------------------------------------------------
# Plan dataclass + JSON round-trip
# ---------------------------------------------------------------------------

@dataclass
class SlideEntry:
    slide_id: str
    kind: str          # layout-catalog key, e.g. "content-text", "cards-grid"
    params: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""  # sha256 of the slide's source HTML chunk


@dataclass
class Plan:
    version: int = 1
    deck_md_hash: str = ""    # sha256 of the source markdown for staleness check
    shake_seed: str | None = None
    slides: list[SlideEntry] = field(default_factory=list)

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to JSON. Sorted keys for deterministic output."""
        return json.dumps(asdict(self), indent=indent, sort_keys=True,
                          ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Plan":
        """Parse from JSON; tolerates missing fields with defaults."""
        data = json.loads(s)
        slides_raw = data.pop("slides", [])
        slides = [SlideEntry(**e) for e in slides_raw]
        return cls(slides=slides, **data)


def hash_text(text: str) -> str:
    """Stable sha256 hash for content/markdown freshness detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
