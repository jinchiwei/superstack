"""plan.py — slide-ID derivation + Plan JSON schema for build-pptx.

Data-layer only. Not wired into build.py yet (that happens in Task 5).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Ensure layouts package is importable when plan.py is run directly
sys.path.insert(0, str(Path(__file__).resolve().parent))


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
    mode: str = "expressive"  # "expressive" (themed+guided-freeform) | "strict" (rules-based, revert path)
    theme: str | None = None  # name of the chosen theme (expressive only); None in strict
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
        # Drop any unknown top-level keys so a future sidecar can't crash an
        # older Plan; known fields fall back to dataclass defaults if absent.
        known = {"version", "deck_md_hash", "shake_seed", "mode", "theme"}
        data = {k: v for k, v in data.items() if k in known}
        return cls(slides=slides, **data)


def hash_text(text: str) -> str:
    """Stable sha256 hash for content/markdown freshness detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Plan-generation prompt assembly
# ---------------------------------------------------------------------------

def assemble_plan_prompt(*, md_text: str, slide_records: list[dict]) -> str:
    """Build the prompt string that the slash command hands to Claude.

    Reads plan_prompt.md from disk, then appends a SLIDE INPUT section with
    one tuple per slide. The caller is responsible for passing this prompt
    into Claude (via the Skill, via in-session reasoning, etc.) and parsing
    the JSON response. This function is pure — it just stitches the parts.

    slide_records is a list of:
      {"slide_id": str, "content_hash": str, "h1": str|None, "h2": str|None, "chunk_html": str}
    """
    prompt_path = Path(__file__).resolve().parent / "plan_prompt.md"
    base = prompt_path.read_text(encoding="utf-8")
    deck_md_hash = hash_text(md_text)
    parts = [base, "", "---", "",
             "## Input for THIS deck", "",
             f"deck_md_hash: {deck_md_hash}", ""]
    for rec in slide_records:
        parts.append(f"### slide_id: {rec['slide_id']}")
        parts.append(f"content_hash: {rec['content_hash']}")
        if rec.get("h1"):
            parts.append(f"h1: {rec['h1']}")
        if rec.get("h2"):
            parts.append(f"h2: {rec['h2']}")
        parts.append("")
        parts.append("```html")
        parts.append(rec["chunk_html"])
        parts.append("```")
        parts.append("")
    parts.append("Output the JSON now. No commentary, no markdown fences around the output.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Cache-merge driver
# ---------------------------------------------------------------------------

def merge_with_existing(new_plan: Plan, existing_plan: Plan | None) -> Plan:
    """Combine a freshly-generated plan with an existing sidecar.

    For each slide_id in new_plan:
      - If existing_plan has that slide_id AND its content_hash matches:
        keep the EXISTING entry (preserves user's chosen layout across re-runs)
      - Otherwise: use the new entry
    Slides removed from the markdown drop from the merged plan automatically
    because we only iterate new_plan.slides.

    deck_md_hash and shake_seed come from new_plan."""
    if existing_plan is None:
        return new_plan
    by_id = {e.slide_id: e for e in existing_plan.slides}
    merged_slides = []
    for new_entry in new_plan.slides:
        old_entry = by_id.get(new_entry.slide_id)
        if old_entry is not None and old_entry.content_hash == new_entry.content_hash:
            merged_slides.append(old_entry)
        else:
            merged_slides.append(new_entry)
    return Plan(version=new_plan.version,
                deck_md_hash=new_plan.deck_md_hash,
                shake_seed=new_plan.shake_seed,
                slides=merged_slides)


# ---------------------------------------------------------------------------
# Slide record builder
# ---------------------------------------------------------------------------

def build_slide_records(*, chunks: list[str], slide_ids: list[str]) -> list[dict]:
    """Walk slide chunks and produce the slide_records list that
    assemble_plan_prompt expects. Extracts the H1/H2 for each slide and
    computes per-slide content_hash for cache invalidation."""
    from layouts._common import _strip_html
    records = []
    current_h1 = None
    for slide_id, chunk in zip(slide_ids, chunks):
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", chunk, re.DOTALL)
        h2_match = re.search(r"<h2[^>]*>(.*?)</h2>", chunk, re.DOTALL)
        chunk_h1 = _strip_html(h1_match.group(1)) if h1_match else None
        chunk_h2 = _strip_html(h2_match.group(1)) if h2_match else None
        if chunk_h1:
            current_h1 = chunk_h1
        records.append({
            "slide_id": slide_id,
            "content_hash": hash_text(chunk),
            "h1": chunk_h1 or current_h1,
            "h2": chunk_h2,
            "chunk_html": chunk.strip(),
        })
    return records
