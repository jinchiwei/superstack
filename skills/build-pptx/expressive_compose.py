"""expressive_compose.py — deterministic expressive-freeform composer.

Option B: the no-agent floor that guarantees every expressive deck renders as
*designed freeform* slides rather than named layouts, even when no Claude agent
is in the loop (raw `python build.py`, autoresearch's non-interactive
shell-out).

`compose_expressive_plan(slides, ...)` walks the SlideEntry list produced by
`_infer_default_plan` and, for each content slide (NOT section-divider),
rewrites it in place to `kind="freeform"` with a generated `code` snippet per
content archetype. Geometry is precomputed in Python; emitted code is flat
primitive calls using only the documented sandbox API, with ON_DARK-aware
colour EXPRESSIONS so one plan renders correctly on light AND dark themes.
Every emitted snippet is `ast.parse()`-checked as a self-check.

This is a post-step layered on top of the inferrer in expressive mode only.
Strict mode never calls it (named layouts, unchanged). Agent-authored sidecar
entries are preserved by the caller's gate.
"""

from __future__ import annotations

import ast
import math
from typing import Any

# Colour EXPRESSIONS (strings) evaluated inside the sandbox at render time.
# They are ON_DARK-aware so the same plan renders on light + dark themes.
_PRIMARY = "(WHITE_RGB if ON_DARK else INK_RGB)"
_SECOND = "(RULE_RGB if ON_DARK else MUTED_RGB)"
_PANEL = "(SURFACE_RGB if SURFACE_RGB else PAPER_RGB)"

# Brand-palette fallbacks (priority order) for card top-bands when the theme
# does not supply enough supplementary hues.
_BRAND = ["TURQUOISE_RGB", "DEEPPINK_RGB", "AMBER_RGB", "BLUEVIOLET_RGB"]

# Archetype groupings (mirror the named kinds the inferrer can produce).
_FIGURE_KINDS = {
    "figure-with-aside",
    "figure-with-aside-horizontal",
    "content-text-image",
    "content-image-only",
}
_CARDS_KINDS = {
    "cards-triple",
    "cards-grid",
    "cards-heterogeneous",
    "cards-with-takeaway",
    "conclusions",
    "three-pillars",
    "vertical-timeline",
    "stats-with-takeaway",
}
_TABLE_KINDS = {"table-with-takeaway"}


def _q(s: str) -> str:
    """repr() a string for safe embedding in emitted code."""
    return repr("" if s is None else str(s))


def _cpl_lines(s: str, cpl: int) -> int:
    return max(1, math.ceil(len(s or "") / cpl))


def _hue(i: int, fallback: str) -> str:
    """Theme hue expression with a brand fallback when the theme runs short."""
    return f"(THEME_RGBS[{i}] if len(THEME_RGBS) > {i} else {fallback})"


def _strip(html_or_text: str) -> str:
    """Plain text from a paragraph html string (lazy import to avoid cycles)."""
    from layouts._common import _strip_html
    return _strip_html(html_or_text or "")


def _para_text(p: Any) -> str:
    """Extract plain text from a body paragraph (dict with 'html' or a str)."""
    if isinstance(p, dict):
        return _strip(p.get("html", "") or "")
    return _strip(str(p))


def _para_is_bullet(p: Any) -> bool:
    if isinstance(p, dict):
        return p.get("kind") == "bullet"
    return str(p).strip().startswith(("•", "-"))


# ---------------------------------------------------------------------------
# Per-archetype code emitters
# ---------------------------------------------------------------------------

def _code_figure(image: str, items: list[str], lede: str = "") -> str:
    """Image on the left (via _fit_image) + a SURFACE panel aside on the right
    with an accent top-stripe and accent-square bulleted text."""
    L: list[str] = []
    L.append("fw = body_w*0.56")
    L.append(
        f"_fit_image(slide, {_q(image)}, left=body_l, top=body_top+0.10, "
        f"max_w=body_w*0.56, max_h=body_h-0.25)"
    )
    L.append("px = body_l + fw + 0.40")
    L.append("pw = body_w - fw - 0.40")
    # Surface panel behind the aside + accent top-stripe.
    L.append(
        f"_add_rect(slide, left=px, top=body_top+0.05, width=pw, "
        f"height=body_h-0.15, fill_rgb={_PANEL})"
    )
    L.append(
        "_add_rect(slide, left=px, top=body_top+0.05, width=pw, height=0.09, "
        "fill_rgb=accent_rgb)"
    )
    bullets = [b for b in (items or []) if b]
    if not bullets and lede:
        bullets = [lede]
    size = 13 if len(bullets) <= 4 else 12
    cpl = 40 if size == 13 else 44
    y = 0.30
    for it in bullets:
        h = _cpl_lines(it, cpl) * (0.215 if size == 13 else 0.20) + 0.06
        L.append(
            f"_add_rect(slide, left=px+0.22, top=body_top+{y + 0.07:.2f}, "
            f"width=0.10, height=0.10, fill_rgb=accent_rgb)"
        )
        L.append(
            f"_add_text(slide, {_q(it)}, left=px+0.44, top=body_top+{y:.2f}, "
            f"width=pw-0.62, height={h:.2f}, size={size}, "
            f"color_rgb={_PRIMARY}, font=SANS_FONT)"
        )
        y += h + 0.14
    return "\n".join(L)


def _code_cards(cards: list[dict]) -> str:
    """Grid of SURFACE panels, each with a theme-hue top band, MONO bold label,
    and SANS body."""
    L: list[str] = []
    n = len(cards)
    ncol = n if n <= 3 else math.ceil(n / 2)
    nrow = math.ceil(n / ncol)
    L.append("gap = 0.35")
    L.append(f"cw = (body_w - gap*{ncol - 1}) / {ncol}")
    L.append(f"ch = (body_h - gap*{max(0, nrow - 1)}) / {nrow}")
    for i, c in enumerate(cards):
        r = i // ncol
        col = i % ncol
        cc = _hue(i, _BRAND[i % 4])
        x = f"body_l+{col}*(cw+gap)"
        yv = f"body_top+{r}*(ch+gap)"
        label = c.get("label", "") or ""
        body = c.get("body", "") or ""
        if isinstance(body, list):
            body = " ".join(_para_text(b) for b in body)
        L.append(
            f"_add_rect(slide, left={x}, top={yv}, width=cw, height=ch, "
            f"fill_rgb={_PANEL})"
        )
        L.append(
            f"_add_rect(slide, left={x}, top={yv}, width=cw, height=0.10, "
            f"fill_rgb={cc})"
        )
        L.append(
            f"_add_text(slide, {_q(label)}, left=({x})+0.20, top=({yv})+0.26, "
            f"width=cw-0.40, height=0.7, size=15, color_rgb={_PRIMARY}, "
            f"font=MONO_FONT, bold=True)"
        )
        L.append(
            f"_add_text(slide, {_q(body)}, left=({x})+0.20, top=({yv})+1.05, "
            f"width=cw-0.40, height=ch-1.25, size=12, color_rgb={_SECOND}, "
            f"font=SANS_FONT)"
        )
    return "\n".join(L)


def _code_table(rows: list[list[str]]) -> str:
    """SURFACE panel behind a full-width accent-header table."""
    rl = "[" + ",".join(
        "[" + ",".join(_q(c) for c in row) + "]" for row in rows
    ) + "]"
    return (
        f"rows = {rl}\n"
        f"_add_rect(slide, left=body_l, top=body_top+0.05, width=body_w, "
        f"height=body_h-0.15, fill_rgb={_PANEL})\n"
        f"_add_table(slide, rows=rows, left=body_l+0.15, top=body_top+0.20, "
        f"width=body_w-0.30, max_height=body_h-0.45, header_rgb=accent_rgb)"
    )


def _code_bullets(items: list[str]) -> str:
    """Designed text block for bullets-only / prose slides."""
    L: list[str] = []
    y = 0.2
    items = [it for it in (items or []) if it] or [""]
    for it in items:
        h = _cpl_lines(it, 90) * 0.22 + 0.10
        L.append(
            f"_add_text(slide, {_q(it)}, left=body_l+0.1, top=body_top+{y:.2f}, "
            f"width=body_w-0.2, height={h:.2f}, size=14, color_rgb={_PRIMARY}, "
            f"font=SANS_FONT)"
        )
        y += h + 0.10
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _rows_from_params(rows: Any) -> list[list[str]]:
    """Normalize a 'rows' param into a flat list-of-rows of strings. Accepts
    both nested ([[...],[...]]) and the already-flat table shape."""
    if not rows:
        return []
    # Already list-of-list-of-cells.
    if isinstance(rows, list) and rows and isinstance(rows[0], list):
        return [[str(c) for c in row] for row in rows]
    return []


def _compose_one(entry) -> bool:
    """Rewrite a single SlideEntry to freeform in place. Returns True if the
    entry was rewritten, False if it was left as-is (section-divider, or a
    kind/params shape the composer cannot handle)."""
    kind = entry.kind
    if kind == "section-divider":
        return False
    if kind in ("freeform", "composition"):
        # Already a block layout (agent-authored or pre-existing) — leave it.
        return False

    pr = dict(entry.params or {})
    title = pr.get("title", "") or ""
    section_label = pr.get("section_label", "") or ""
    lede = pr.get("lede", "") or ""
    code: str | None = None

    if kind in _FIGURE_KINDS:
        image = pr.get("image")
        if not image:
            imgs = pr.get("images") or []
            image = imgs[0] if imgs else None
        if image:
            # Gather aside text: figure-with-aside stores {label, body};
            # content-text-image stores a body paragraph list.
            items: list[str] = []
            aside = pr.get("aside") or {}
            if aside:
                if aside.get("label"):
                    items.append(str(aside["label"]))
                if aside.get("body"):
                    items.append(str(aside["body"]))
            for b in pr.get("body") or []:
                t = _para_text(b)
                if t:
                    items.append(t)
            code = _code_figure(str(image), items, lede=lede)

    elif kind in _CARDS_KINDS:
        cards = pr.get("cards")
        if not cards and pr.get("stages"):
            cards = [{"label": s.get("label", ""), "body": s.get("body", "")}
                     for s in pr.get("stages")]
        if cards:
            code = _code_cards(cards)

    elif kind in _TABLE_KINDS:
        rows = _rows_from_params(pr.get("rows"))
        if rows:
            code = _code_table(rows)

    # Fallback: bullets / prose from whatever body/lede we have.
    if code is None:
        items = [_para_text(b) for b in (pr.get("body") or [])]
        items = [it for it in items if it]
        if not items and lede:
            items = [lede]
        code = _code_bullets(items)

    # Self-check: emitted code must parse.
    ast.parse(code)

    entry.kind = "freeform"
    entry.params = {
        "title": title,
        "lede": "",
        "section_label": section_label,
        "code": code,
    }
    return True


def compose_expressive_plan(slides, *, chunks_by_title=None, md_dir=None,
                            only_ids=None) -> int:
    """Rewrite content SlideEntries in `slides` to designed freeform layouts.

    Args:
        slides:      list[SlideEntry] — mutated in place.
        chunks_by_title / md_dir: accepted for API symmetry; unused (the
                     composer works purely off the inferrer's params).
        only_ids:    optional set/collection of slide_ids to rewrite. When
                     provided, slides whose slide_id is NOT in the set are
                     left untouched (used to preserve agent-authored sidecar
                     entries that merge_with_existing carried over). When None,
                     every content slide is eligible.

    Returns the list of slide_ids rewritten (the agentless "floor"). build.py
    uses this to enforce bespoke: a non-plan-only expressive render with any
    composed slide fails unless --allow-composed (see bespoke_design.md).
    """
    composed = []
    for entry in slides:
        if only_ids is not None and entry.slide_id not in only_ids:
            continue
        if _compose_one(entry):
            # Stamp provenance so the floor is auditable in the sidecar.
            entry.params["_provenance"] = "composer"
            composed.append(entry.slide_id)
    return composed
