"""brandfig -- Jin-branded matplotlib figures, standalone.

Import this in any figure script OR notebook to get the brand style, a
theme-matched canvas, and the save-time QA checks (text overflow + box
padding), WITHOUT pulling in build-pptx. Decks, notebooks, papers, and reports
all share one figure foundation (the same `_shared/mpl_style.py` build-pptx uses).

Figure script:
    import brandfig as bf
    bf.use("bone")                      # apply brand style for a theme
    fig, ax = bf.fig(figsize=(8, 4))    # styled figure on the theme canvas
    ax.bar(["a", "b"], [3, 5], color=[bf.TURQUOISE, bf.DEEPPINK])
    bf.figtitle(fig, "A branded chart")
    bf.save(fig, "out.png")             # canvas-matched + QA warnings on stderr

Notebook (inline, MIT-style live plots):
    import brandfig as bf
    bf.use("bone")                      # %matplotlib inline plots adopt the canvas
    fig, ax = bf.fig(figsize=(6, 3))
    ax.plot(history["loss"])
    bf.show(fig)                        # canvas-matched inline display + QA

Themes: paper (white, default), bone (warm off-white), slate / midnight / forest
(dark). Pass the deck's theme name when a figure is destined for a slide so the
background matches; pass "paper" or "bone" for notebooks and documents.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Locate _shared/mpl_style.py: sibling in the superstack source tree, or the
# installed skills dir. Works whether this file is run from source or ~/.claude.
for _cand in (Path(__file__).resolve().parents[1] / "_shared",
              Path.home() / ".claude" / "skills" / "_shared"):
    if (_cand / "mpl_style.py").exists():
        sys.path.insert(0, str(_cand))
        break

import matplotlib  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402,F401  (re-exported)
import numpy as np  # noqa: E402,F401  (re-exported)

from mpl_style import (  # noqa: E402
    apply_style, theme_colors, text_on_brand_fill, palette,
    warn_text_overflow, check_text_overflow,
    TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET, GOLD,
)

# box-padding QA may be absent on an older _shared -- degrade gracefully.
try:
    from mpl_style import warn_box_padding, check_box_padding  # noqa: E402
except ImportError:  # pragma: no cover
    def warn_box_padding(fig, *, source="", **_k):
        return None

    def check_box_padding(fig, **_k):
        return []

# canonical contrast helper: ink on turquoise/amber, white on deeppink/blueviolet
txt_on = text_on_brand_fill

# brand colors, also grouped for convenience: bf.C.turquoise etc.
C = SimpleNamespace(turquoise=TURQUOISE, deeppink=DEEPPINK, amber=AMBER,
                    blueviolet=BLUEVIOLET, gold=GOLD)

# QA issues accumulate here so a CLI / test can gate on them after rendering.
ISSUES: list[dict] = []

_STATE = {"theme": os.environ.get("BRANDFIG_THEME", "paper")}


def use(theme: str = "bone"):
    """Apply the brand matplotlib style for `theme` and remember it as current.

    Because apply_style sets figure/savefig facecolor to the theme canvas,
    inline notebook plots created afterward render on the right background
    with no extra work.
    """
    apply_style(theme)
    _STATE["theme"] = theme
    return theme_colors(theme)


def colors(theme: str | None = None):
    """The ThemeColors for `theme` (or the current theme)."""
    return theme_colors(theme or _STATE["theme"])


def canvas(theme: str | None = None) -> str:
    """The canvas (facecolor) hex for `theme` (or the current theme)."""
    return colors(theme).canvas


# expose ink/muted of the current theme as attributes-on-call for scripts
def ink(theme: str | None = None) -> str:
    return colors(theme).ink_text


def muted(theme: str | None = None) -> str:
    return colors(theme).muted_text


def fig(*args, theme: str | None = None, **kwargs):
    """plt.subplots(...) with the figure facecolor set to the theme canvas.

    If `theme` is given it is applied globally first (so a one-off figure can
    differ from the script's default); otherwise the current theme is used.
    """
    if theme:
        use(theme)
    f, ax = plt.subplots(*args, **kwargs)
    f.set_facecolor(canvas(theme))
    return f, ax


def figtitle(fig, text: str, *, color: str | None = None, y: float = 1.03,
             size: int = 16) -> None:
    """A Geist Mono figure title (suptitle) in the theme ink color."""
    fig.suptitle(text, fontsize=size, fontweight="bold", family="Geist Mono",
                 color=color or colors().ink_text, y=y)


def _run_qa(fig, source: str):
    issues = check_text_overflow(fig)
    box = check_box_padding(fig)
    for w in issues:
        ISSUES.append({"kind": "overflow", "source": source, **w})
    for w in box:
        ISSUES.append({"kind": "box_padding", "source": source, **w})
    warn_text_overflow(fig, source=source)
    warn_box_padding(fig, source=source)


def save(fig, path, *, theme: str | None = None, dpi: int = 200,
         qa: bool = True, source: str | None = None):
    """Save `fig` with the theme canvas as background, then run QA checks.

    QA (overflow + box padding) prints warnings to stderr and records them in
    `brandfig.ISSUES` so a build/test can fail on them. Returns the path.
    """
    path = str(path)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=canvas(theme))
    if qa:
        _run_qa(fig, source or Path(path).name)
    return path


def show(fig, *, qa: bool = True):
    """Notebook inline display, canvas-matched, with optional QA warnings.

    Use in Jupyter for the MIT-style live plots (sample images, training
    curves, predictions). Requires `%matplotlib inline` (the default).
    """
    fig.set_facecolor(canvas())
    if qa:
        _run_qa(fig, "inline")
    plt.show()
