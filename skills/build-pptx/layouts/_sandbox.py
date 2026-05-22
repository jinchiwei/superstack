"""AST-validated, namespace-scoped exec sandbox for freeform layout snippets.

Threat model
------------
Claude (or a human editing the sidecar YAML) writes the freeform code.
The goal is to prevent ACCIDENTAL escapes — a malformed snippet should not be
able to read /etc/passwd, shell out, or walk the class hierarchy.  This is
NOT designed to defeat a determined adversary who can craft malicious ASTs or
abuse allowed Python builtins; it is a safety net for honest mistakes.

Two-layer defence:
  1. AST validation rejects obviously dangerous constructs before exec().
  2. A constrained globals() dict limits what names are visible at runtime,
     so even if something slips past the AST check the runtime environment
     exposes no escape hatches.

Never relax the validator or the globals dict without a security review.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Wire up the shared branding module and the layouts package
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

import branding  # noqa: E402

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from layouts._common import (  # noqa: E402
    AMBER_RGB,
    BLUEVIOLET_RGB,
    DARK_BG_RGB,
    DEEPPINK_RGB,
    DIM_RGB,
    INK_RGB,
    MUTED_RGB,
    PAPER_RGB,
    RULE_RGB,
    TURQUOISE_RGB,
    WHITE_RGB,
    _add_card,
    _add_flat_shape,
    _add_rect,
    _add_table,
    _add_text,
    _render_media_block,
    _render_paragraph_block,
    _rgb,
)


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class SandboxError(ValueError):
    """Raised when freeform code fails AST validation or cannot be parsed."""


# ---------------------------------------------------------------------------
# Forbidden name set
# ---------------------------------------------------------------------------

_FORBIDDEN_NAMES: frozenset[str] = frozenset({
    "exec",
    "eval",
    "compile",
    "open",
    "input",
    "__import__",
    "__builtins__",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
    "breakpoint",
    "help",
})


# ---------------------------------------------------------------------------
# AST validator
# ---------------------------------------------------------------------------

class _ForbiddenNodeVisitor(ast.NodeVisitor):
    """Walk the AST and raise SandboxError on any forbidden construct."""

    def visit_Import(self, node: ast.Import) -> None:
        raise SandboxError(
            f"freeform code contains an import statement "
            f"(line {node.lineno}): import is not allowed"
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise SandboxError(
            f"freeform code contains a from-import statement "
            f"(line {node.lineno}): import is not allowed"
        )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            raise SandboxError(
                f"freeform code accesses dunder attribute '{node.attr}' "
                f"(line {node.lineno}): dunder access is not allowed"
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _FORBIDDEN_NAMES:
            raise SandboxError(
                f"freeform code references forbidden name '{node.id}' "
                f"(line {node.lineno})"
            )
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        raise SandboxError(
            f"freeform code contains a try/except statement "
            f"(line {node.lineno}): try/with blocks are not allowed"
        )

    def visit_TryStar(self, node: ast.AST) -> None:  # Python 3.11+ ExceptionGroup
        raise SandboxError(
            "freeform code contains a try/except* statement: "
            "try/with blocks are not allowed"
        )

    def visit_With(self, node: ast.With) -> None:
        raise SandboxError(
            f"freeform code contains a with statement "
            f"(line {node.lineno}): try/with blocks are not allowed"
        )

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        raise SandboxError(
            f"freeform code contains an async with statement "
            f"(line {node.lineno}): try/with blocks are not allowed"
        )


def validate_code(code: str) -> None:
    """Parse and AST-validate a freeform snippet.

    Raises SandboxError if the code is unparseable or contains any forbidden
    construct (imports, dunder attribute access, forbidden builtins, try/with).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SandboxError(f"freeform code does not parse: {e}") from e

    _ForbiddenNodeVisitor().visit(tree)


# ---------------------------------------------------------------------------
# Safe globals builder
# ---------------------------------------------------------------------------

_SAFE_BUILTINS: dict = {
    # numeric
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    # iteration / functional
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    # type constructors
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "tuple": tuple,
    "dict": dict,
    "set": set,
    # singletons
    "True": True,
    "False": False,
    "None": None,
}


def build_safe_globals(
    *,
    slide,
    accent_hex: str,
    body_top: float,
    body_h: float,
    body_l: float,
    body_w: float,
    body_bottom: float,
    theme_hexes: list[str] | None = None,
    canvas_bg_hex: str | None = None,
    on_dark: bool = False,
    surface_hex: str | None = None,
) -> dict:
    """Return a constrained globals dict for exec()ing a freeform snippet.

    The dict exposes exactly the drawing primitives, colour constants, and
    geometry values that a freeform snippet needs.  No escape hatches.

    In expressive mode an optional theme palette is injected: THEME_HEXES /
    THEME_RGBS (supplementary hues), CANVAS_BG_RGB (full-bleed canvas),
    SURFACE_RGB (theme card surface, so hand-authored cards match named layouts), and
    ON_DARK (whether the canvas is dark). These are data only — they add no
    new callables and so cannot serve as escape hatches.
    """
    accent_rgb = _rgb(accent_hex)

    return {
        # Slide object
        "slide": slide,
        # Accent colour
        "accent_hex": accent_hex,
        "accent_rgb": accent_rgb,
        # Geometry
        "body_top": body_top,
        "body_h": body_h,
        "body_l": body_l,
        "body_w": body_w,
        "body_bottom": body_bottom,
        # Colour constants (RGBColor)
        "INK_RGB": INK_RGB,
        "WHITE_RGB": WHITE_RGB,
        "TURQUOISE_RGB": TURQUOISE_RGB,
        "DEEPPINK_RGB": DEEPPINK_RGB,
        "AMBER_RGB": AMBER_RGB,
        "BLUEVIOLET_RGB": BLUEVIOLET_RGB,
        "DIM_RGB": DIM_RGB,
        "MUTED_RGB": MUTED_RGB,
        "RULE_RGB": RULE_RGB,
        "DARK_BG_RGB": DARK_BG_RGB,
        "PAPER_RGB": PAPER_RGB,
        # Theme palette (expressive mode) — data only, no callables
        "THEME_HEXES": list(theme_hexes or []),
        "THEME_RGBS": [_rgb(h) for h in (theme_hexes or [])],
        "CANVAS_BG_RGB": _rgb(canvas_bg_hex) if canvas_bg_hex else None,
        "SURFACE_RGB": _rgb(surface_hex) if surface_hex else None,
        "ON_DARK": on_dark,
        # Drawing primitives
        "_add_rect": _add_rect,
        "_add_text": _add_text,
        "_add_card": _add_card,
        "_add_table": _add_table,
        "_add_flat_shape": _add_flat_shape,
        "_render_paragraph_block": _render_paragraph_block,
        "_render_media_block": _render_media_block,
        "_rgb": _rgb,
        # pptx utilities
        "Inches": Inches,
        "Pt": Pt,
        "Emu": Emu,
        "RGBColor": RGBColor,
        "MSO_SHAPE": MSO_SHAPE,
        "PP_ALIGN": PP_ALIGN,
        "MSO_ANCHOR": MSO_ANCHOR,
        # Branding constants
        "MONO_FONT": branding.MONO_FONT,
        "SANS_FONT": branding.SANS_FONT,
        "TURQUOISE": branding.TURQUOISE,
        "DEEPPINK": branding.DEEPPINK,
        "AMBER": branding.AMBER,
        "BLUEVIOLET": branding.BLUEVIOLET,
        # Minimal builtins — no open, exec, eval, getattr, etc.
        "__builtins__": _SAFE_BUILTINS,
    }


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

def run(
    *,
    code: str,
    slide,
    accent_hex: str,
    body_top: float,
    body_h: float,
    body_l: float,
    body_w: float,
    body_bottom: float,
    theme_hexes: list[str] | None = None,
    canvas_bg_hex: str | None = None,
    on_dark: bool = False,
    surface_hex: str | None = None,
) -> None:
    """Validate and execute a freeform snippet inside a constrained namespace.

    Raises SandboxError on validation failure.  Exec-time exceptions propagate
    as-is so the freeform renderer (Task 2) can catch them and render an
    error chip on the slide instead of crashing the whole build.
    """
    validate_code(code)
    safe_globals = build_safe_globals(
        slide=slide,
        accent_hex=accent_hex,
        body_top=body_top,
        body_h=body_h,
        body_l=body_l,
        body_w=body_w,
        body_bottom=body_bottom,
        theme_hexes=theme_hexes,
        canvas_bg_hex=canvas_bg_hex,
        on_dark=on_dark,
        surface_hex=surface_hex,
    )
    exec(code, safe_globals)  # noqa: S102 — intentional, validated above
