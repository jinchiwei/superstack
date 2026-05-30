"""Static lint that flags low-contrast text-on-card patterns in freeform code.

Bespoke design slides build cards via `_add_rect(... fill_rgb=SURFACE_RGB)` and
then place body text inside with `_add_text(... color_rgb=...)`. A common bug is
using `MUTED_RGB` or `DIM_RGB` for that on-card text — both are muted grays,
which on a SURFACE card (also a muted gray) give poor contrast and look washed
out.

The doctrine (bespoke_design.md): MUTED/DIM are for tiny secondary captions on
the OPEN CANVAS only; body text on a card panel must be high-contrast — INK on
light themes, WHITE on dark themes (use `(WHITE_RGB if ON_DARK else INK_RGB)`),
or `_text_on(fill)` for filled accent zones.

This module scans the `params['code']` of every freeform slide in a sidecar
and warns when an `_add_text(...)` call uses MUTED_RGB / DIM_RGB. It's a
lint (warning, non-fatal) — not a hard gate — because there are legitimate
canvas-side uses; the warning lets the agent eyeball each case.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path


# Colors that are unsafe for body text on a SURFACE / PAPER card.
# Captured as the literal sandbox identifier the freeform code uses.
_UNSAFE_TEXT_COLORS = ("MUTED_RGB", "DIM_RGB")


def _find_unsafe_text_calls(code: str) -> list[tuple[int, str, str]]:
    """Return [(lineno, color_name, snippet), ...] for _add_text calls
    whose `color_rgb=` is one of the unsafe-on-card colors."""
    hits: list[tuple[int, str, str]] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return hits

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # _add_text(...)
        if isinstance(func, ast.Name) and func.id == "_add_text":
            for kw in node.keywords:
                if kw.arg != "color_rgb":
                    continue
                # Direct identifier?
                if isinstance(kw.value, ast.Name) and kw.value.id in _UNSAFE_TEXT_COLORS:
                    snippet = _snippet(code, node.lineno)
                    hits.append((node.lineno, kw.value.id, snippet))
                # Conditional like (MUTED_RGB if cond else ...) — also flag
                elif isinstance(kw.value, ast.IfExp):
                    for sub in (kw.value.body, kw.value.orelse):
                        if isinstance(sub, ast.Name) and sub.id in _UNSAFE_TEXT_COLORS:
                            snippet = _snippet(code, node.lineno)
                            hits.append((node.lineno, sub.id, snippet))
                            break
    return hits


def _snippet(code: str, lineno: int, ctx: int = 0) -> str:
    """Get a short text snippet for the offending line (first 100 chars)."""
    lines = code.splitlines()
    if lineno - 1 < 0 or lineno - 1 >= len(lines):
        return ""
    return lines[lineno - 1].strip()[:110]


def _is_on_card_call(snippet: str) -> bool:
    """Heuristic: is this _add_text likely on top of a SURFACE/PAPER card?

    Hard to know perfectly from a single line — but we can flag the higher-
    risk cases by spotting card-related geometry tokens in the snippet:
    nearby fill_rgb of SURFACE / PAPER, or x/y references that suggest the
    text is inside a card region. Default: warn anyway and let the agent
    judge — the lint is advisory.
    """
    return True  # conservative: warn on every MUTED/DIM text


def lint_sidecar(sidecar_path: Path) -> list[dict]:
    """Scan the freeform code in every slide. Return list of warning dicts.

    Each dict: {slide_index, slide_title, lineno, color_name, snippet}.
    """
    plan = json.loads(Path(sidecar_path).read_text())
    warnings: list[dict] = []
    for i, s in enumerate(plan.get("slides", []), 1):
        if s.get("kind") != "freeform":
            continue
        params = s.get("params", {})
        code = params.get("code", "")
        title = params.get("title", "")
        for lineno, color, snippet in _find_unsafe_text_calls(code):
            if _is_on_card_call(snippet):
                warnings.append({
                    "slide_index": i,
                    "slide_title": title,
                    "lineno": lineno,
                    "color_name": color,
                    "snippet": snippet,
                })
    return warnings


def format_warnings(warnings: list[dict]) -> str:
    """Human-readable summary for stderr."""
    if not warnings:
        return ""
    lines = [
        f"contrast lint: {len(warnings)} _add_text call(s) use MUTED_RGB/DIM_RGB",
        "  These are appropriate ONLY for tiny secondary captions on the OPEN CANVAS.",
        "  For text on SURFACE / PAPER / accent cards use (WHITE_RGB if ON_DARK else INK_RGB)",
        "  or _text_on(fill_rgb) for accent-filled zones (bespoke_design.md).",
        "",
    ]
    for w in warnings:
        lines.append(
            f"  slide {w['slide_index']:>2} ({w['slide_title'][:50]:<50}) "
            f"line {w['lineno']:>3}: {w['color_name']}"
        )
        lines.append(f"      {w['snippet']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not path:
        print("usage: contrast_lint.py <sidecar.md.layout.json>", file=sys.stderr)
        sys.exit(2)
    w = lint_sidecar(path)
    if w:
        print(format_warnings(w), file=sys.stderr)
        sys.exit(0)  # warning, not error
    else:
        print("contrast lint: clean")
