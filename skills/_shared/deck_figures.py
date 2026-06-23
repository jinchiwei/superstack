"""Reusable figure archetypes for engaging deck slides.

ONE library of common figure patterns so we don't hand-roll the same archetypes
from scratch every deck. Pairs with `mpl_style.py` (brand lock) and the doctrine
in `skills/build-pptx/{intro,results,methods}_figures.md`.

Archetypes covered:
    region_dot_strip()       — N items × M conditions colored by sign/value
    comparison_bars()        — 2-condition paired horizontal bars with annotations
    aic_or_metric_curves()   — overlaid line curves with baseline/threshold band
    binary_grid()            — N×M sig/not grid (FDR survival, presence, etc.)
    depth_schematic()        — anatomical cross-section with sampling layers
    compartment_diagram()    — labeled partition of a region into compartments
    pipeline_flow()          — boxed flow diagram with arrows
    four_panel_scorecard()   — composite of any 4 figures with shared title

All archetypes:
    * accept theme-aware colors via mpl_style.theme_colors()
    * save with TRANSPARENT bg by default (composite onto deck slide canvas)
    * write a sibling CSV/JSON of plot data for re-themability
    * follow the brand lock (Geist Mono titles, brand-4 accents, no off-brand hexes)

Usage:
    import sys; sys.path.insert(0, "/home/jiwei/arcadia/superstack/skills/_shared")
    from deck_figures import region_dot_strip, four_panel_scorecard
    from mpl_style import apply_style, theme_colors, TURQUOISE, DEEPPINK
    apply_style(theme="slate"); T = theme_colors("slate")
    fig, ax = plt.subplots(...)
    region_dot_strip(ax, regions=[...], rows=[("10mm", values_10), ("2mm", values_2)],
                     color_fn=lambda v: TURQUOISE if v > 0 else DEEPPINK)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from mpl_style import (
    apply_style,
    theme_colors,
    TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET,
    text_on_brand_fill,
)


# ---------------------------------------------------------------------------
# 1. region_dot_strip — N items × M condition rows, colored dots
# ---------------------------------------------------------------------------

def region_dot_strip(
    ax,
    *,
    items: Sequence[str],
    rows: Sequence[tuple[str, Sequence[float]]],
    color_fn: Callable[[float], str] | None = None,
    theme: str | None = None,
    legend: Sequence[tuple[str, str]] | None = None,
    dot_radius: float = 0.38,
    row_spacing: float = 1.5,
) -> None:
    """One row of N colored dots per condition.

    Args:
        ax: matplotlib axes
        items: N item labels (regions, bundles, etc.)
        rows: list of (condition_label, values) — one row per condition.
              values has length N; color_fn(value) chooses dot color.
        color_fn: value → hex color. Default: TURQUOISE if v > 0 else DEEPPINK.
        legend: optional list of (label, color) for a manual legend at bottom.
        dot_radius: circle radius in axes units (use set_aspect('equal'))
        row_spacing: vertical spacing between condition rows

    Idiom: shows direction agreement across many items at two depths/conditions.
    """
    T = theme_colors(theme)
    if color_fn is None:
        color_fn = lambda v: TURQUOISE if v > 0 else DEEPPINK

    n_items = len(items)
    n_rows = len(rows)
    has_legend = legend is not None

    legend_band_height = 1.0 if has_legend else 0.0
    total_h = n_rows * row_spacing + legend_band_height + 0.5

    ax.set_xlim(-0.5, n_items + 0.5)
    ax.set_ylim(-legend_band_height - 0.5, n_rows * row_spacing + 0.5)
    ax.set_aspect('equal')
    ax.axis('off')

    # Plot rows top-down so the first row sits at top
    for row_idx, (cond_label, values) in enumerate(rows):
        y = (n_rows - 1 - row_idx) * row_spacing
        # row label on left
        ax.text(-0.3, y, cond_label, color=T.ink_text, fontsize=12, family="monospace",
                ha="right", va="center", weight="bold")
        # dots
        for i, v in enumerate(values):
            ax.add_patch(mpatches.Circle((i + 0.5, y), dot_radius,
                                          color=color_fn(v), alpha=0.92,
                                          edgecolor=T.canvas, linewidth=1.5))
        # right-side summary if signs
        n_pos = sum(1 for v in values if v > 0)
        ax.text(n_items + 0.1, y, f"{n_pos}/{n_items} +",
                color=TURQUOISE, fontsize=13, family="monospace",
                ha="left", va="center", weight="bold")

    if has_legend:
        legend_y = -0.7
        x_spacing = (n_items - 1) / max(1, len(legend) - 1) if len(legend) > 1 else 0
        for li, (lab, c) in enumerate(legend):
            x = 0.5 + li * x_spacing
            ax.add_patch(mpatches.Circle((x, legend_y), 0.22, color=c, alpha=0.92))
            ax.text(x + 0.4, legend_y, lab, color=T.ink_text, fontsize=10,
                    family="monospace", va="center")


# ---------------------------------------------------------------------------
# 2. comparison_bars — paired horizontal bars per item with annotations
# ---------------------------------------------------------------------------

def comparison_bars(
    ax,
    *,
    items: Sequence[str],
    cond_a: tuple[str, Sequence[float], Sequence[float] | None],
    cond_b: tuple[str, Sequence[float], Sequence[float] | None],
    theme: str | None = None,
    color: str | None = None,
    cond_b_alpha: float = 0.35,
    annot_fmt: str = "β={val:+.3f}, p={p:.3f}{sig}",
    sig_thresh: float = 0.05,
) -> None:
    """Per item, draw two bars (cond_a solid, cond_b faded) with annotations.

    Args:
        items: item labels
        cond_a / cond_b: tuple of (label, values, pvalues or None)
        annot_fmt: format string with {val}, {p}, {sig} (sig is " *" or " n.s.")

    Idiom: "same item across two conditions — direction holds, significance differs"
    """
    T = theme_colors(theme)
    color = color or TURQUOISE
    name_a, vals_a, ps_a = cond_a
    name_b, vals_b, ps_b = cond_b
    n = len(items)

    y_pos = np.arange(n) + 0.5
    bar_h = 0.30

    ax.set_facecolor("none")
    for i, item in enumerate(items):
        # cond_a bar — solid
        ax.barh(y_pos[i] + 0.18, vals_a[i], height=bar_h, color=color, alpha=1.0,
                edgecolor=T.canvas, linewidth=1.2,
                label=name_a if i == 0 else None)
        p = ps_a[i] if ps_a is not None else None
        sig = " *" if (p is not None and p < sig_thresh) else (" n.s." if p is not None else "")
        annot = annot_fmt.format(val=vals_a[i], p=p if p is not None else float('nan'), sig=sig)
        ax.text(vals_a[i] + 0.0008, y_pos[i] + 0.18, f"{name_a} {annot}",
                color=T.ink_text, fontsize=10, family="monospace", va="center")

        # cond_b bar — faded
        ax.barh(y_pos[i] - 0.18, vals_b[i], height=bar_h, color=color, alpha=cond_b_alpha,
                edgecolor=T.canvas, linewidth=1.2,
                label=name_b if i == 0 else None)
        p = ps_b[i] if ps_b is not None else None
        sig = " *" if (p is not None and p < sig_thresh) else (" n.s." if p is not None else "")
        annot = annot_fmt.format(val=vals_b[i], p=p if p is not None else float('nan'), sig=sig)
        ax.text(vals_b[i] + 0.0008, y_pos[i] - 0.18, f"{name_b} {annot}",
                color=T.muted_text, fontsize=10, family="monospace", va="center")

        # item label on left
        ax.text(-0.001, y_pos[i], item, color=T.ink_text, fontsize=11,
                family="monospace", ha="right", va="center", weight="bold")

    ax.set_xlim(left=ax.get_xlim()[0] - 0.001)
    ax.axvline(0, color=T.muted_text, lw=0.6)
    ax.set_yticks([])
    ax.set_ylim(0, n + 1)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(T.rule)
    ax.tick_params(axis="x", colors=T.muted_text, labelsize=9)
    ax.legend(loc="lower right", facecolor="none", edgecolor=T.rule, fontsize=9.5, frameon=True)


# ---------------------------------------------------------------------------
# 3. aic_or_metric_curves — overlaid curves vs a candidate-grid x-axis
# ---------------------------------------------------------------------------

def aic_or_metric_curves(
    ax,
    *,
    curves: Sequence[tuple[str, Sequence[float], Sequence[float], str]],
    baseline_y: float = 0.0,
    baseline_label: str = "linear baseline",
    xlabel: str = "candidate position",
    ylabel: str = "ΔAIC",
    shade_above_below: bool = True,
    above_label: str = "above = baseline preferred",
    below_label: str = "below = curve preferred",
    theme: str | None = None,
) -> None:
    """Overlaid curves with a horizontal baseline + optional preference shading.

    Args:
        curves: list of (label, x_values, y_values, color_hex)
        baseline_y: horizontal reference line (e.g. 0 for ΔAIC vs linear)
        shade_above_below: shade regions above and below the baseline differently

    Idiom: "model selection across a parameter grid — curve dips below = better"
    """
    T = theme_colors(theme)
    ax.set_facecolor("none")
    ax.axhline(baseline_y, color=AMBER, ls="--", lw=2, alpha=0.9, label=baseline_label)

    if shade_above_below and curves:
        x_lo = min(min(c[1]) for c in curves)
        x_hi = max(max(c[1]) for c in curves)
        y_lo, y_hi = ax.get_ylim() if ax.get_ylim()[1] > ax.get_ylim()[0] + 0.1 else (-10, 10)
        ax.fill_between([x_lo, x_hi], y_lo, baseline_y, color=TURQUOISE, alpha=0.06, zorder=0)
        ax.fill_between([x_lo, x_hi], baseline_y, y_hi, color=DEEPPINK, alpha=0.06, zorder=0)

    for label, xs, ys, color in curves:
        ax.plot(xs, ys, color=color, lw=2.5, marker="o", markersize=5,
                label=label, zorder=3)
        # Mark the best (min y for "below = preferred")
        i_min = int(np.argmin(ys))
        ax.scatter([xs[i_min]], [ys[i_min]], color=color, s=140, zorder=5,
                   edgecolor=T.canvas, linewidth=2)

    ax.set_xlabel(xlabel, color=T.ink_text, fontsize=10.5)
    ax.set_ylabel(ylabel, color=T.ink_text, fontsize=10.5)
    ax.legend(loc="upper right", facecolor="none", edgecolor=T.rule, fontsize=9.5)
    ax.tick_params(axis="both", colors=T.muted_text)
    ax.grid(True, color=T.rule, alpha=0.3, lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(T.rule)
    ax.spines["bottom"].set_color(T.rule)


# ---------------------------------------------------------------------------
# 4. binary_grid — N×M filled/empty squares
# ---------------------------------------------------------------------------

def binary_grid(
    ax,
    *,
    items: Sequence[str],
    rows: Sequence[tuple[str, Sequence[bool]]],
    fill_color: str | None = None,
    legend: tuple[str, str] = ("present", "absent"),
    theme: str | None = None,
    square_size: float = 0.85,
    row_spacing: float = 1.5,
) -> None:
    """One row of N squares per condition. Filled = present (e.g. FDR-sig), empty = absent.

    Args:
        items: N item labels
        rows: list of (cond_label, bool_values)
        fill_color: hex color for filled (default TURQUOISE)
        legend: (filled_label, empty_label)

    Idiom: "which regions survived FDR at each condition"
    """
    T = theme_colors(theme)
    fill_color = fill_color or TURQUOISE
    n_items = len(items)
    n_rows = len(rows)

    ax.set_xlim(-0.5, n_items + 1.5)
    ax.set_ylim(-1.5, n_rows * row_spacing + 0.5)
    ax.set_aspect('equal')
    ax.axis('off')

    for row_idx, (cond_label, sigs) in enumerate(rows):
        y = (n_rows - 1 - row_idx) * row_spacing + 0.1
        # row label
        ax.text(-0.3, y + square_size/2, cond_label, color=T.ink_text, fontsize=12,
                family="monospace", ha="right", va="center", weight="bold")
        for i, sig in enumerate(sigs):
            x = i + 0.05
            if sig:
                ax.add_patch(mpatches.Rectangle((x, y), square_size, square_size,
                                                color=fill_color, alpha=0.95))
            else:
                ax.add_patch(mpatches.Rectangle((x, y), square_size, square_size,
                                                fill=False, edgecolor=T.muted_text, linewidth=1.5))
        # right summary
        n_sig = sum(sigs)
        col = fill_color if n_sig > n_items / 2 else DEEPPINK
        ax.text(n_items + 0.3, y + square_size/2, f"{n_sig}/{n_items}",
                color=col, fontsize=12, family="monospace", ha="left", va="center", weight="bold")

    # Legend
    ax.add_patch(mpatches.Rectangle((0.5, -0.95), 0.35, 0.3, color=fill_color, alpha=0.95))
    ax.text(1.0, -0.80, legend[0], color=T.ink_text, fontsize=10, family="monospace", va="center")
    ax.add_patch(mpatches.Rectangle((n_items/2 + 0.5, -0.95), 0.35, 0.3, fill=False,
                                     edgecolor=T.muted_text, linewidth=1.5))
    ax.text(n_items/2 + 1.0, -0.80, legend[1], color=T.ink_text, fontsize=10,
            family="monospace", va="center")


# ---------------------------------------------------------------------------
# 5. depth_schematic — anatomical cross-section with sampling layers
# ---------------------------------------------------------------------------

@dataclass
class DepthLayer:
    """One sampling layer for the depth schematic."""
    depth_mm: float  # signed depth from boundary (negative = below)
    color: str
    label: str
    long_label: str | None = None


def depth_schematic(
    ax,
    *,
    layers: Sequence[DepthLayer],
    cortex_thickness_mm: float = 3.0,
    pia_color: str = "#FF6688",
    boundary_color: str | None = None,
    title_text: str = "Sampling depth schematic",
    caption: str | None = None,
    theme: str | None = None,
    x_extent: float = 10.0,
    show_anatomy_labels: bool = True,
) -> None:
    """Anatomical cross-section showing pia / WM-GM boundary / sampling depths.

    Args:
        layers: list of DepthLayer objects (depth_mm is signed; -2 means 2mm below)
        cortex_thickness_mm: typical cortical band thickness for the schematic
        pia_color: color of the pia surface (top of cortex)
        boundary_color: color of WM-GM boundary (default BLUEVIOLET)
        x_extent: schematic horizontal length

    Idiom: "where does our pipeline sample relative to anatomy"
    """
    T = theme_colors(theme)
    if boundary_color is None:
        boundary_color = BLUEVIOLET

    ax.set_facecolor("none")
    ax.set_xlim(-1, x_extent + 2)
    deepest = min(l.depth_mm for l in layers)
    ax.set_ylim(deepest - 3, cortex_thickness_mm + 3)

    xs = np.linspace(0, x_extent, 200)
    pia = cortex_thickness_mm * 0.5 + 1.2 * np.sin(xs * 0.6) - 0.3 * np.sin(xs * 1.6)
    gw = pia - cortex_thickness_mm

    # Gray matter band
    ax.fill_between(xs, gw, pia, color="#A0A0B0", alpha=0.85, zorder=2)
    # Deep WM background
    ax.fill_between(xs, deepest - 2, gw, color="#E8E8E8", alpha=0.35, zorder=1)
    if show_anatomy_labels:
        ax.text(x_extent / 2, deepest - 1.5,
                "deep white matter (bulk WM, periventricular)",
                ha="center", color=T.muted_text, fontsize=10, style="italic", family="sans-serif")

    # Pia line
    ax.plot(xs, pia, color=pia_color, lw=2.2)
    # WM/GM boundary
    ax.plot(xs, gw, color=boundary_color, lw=2.2)

    # Layer dashed lines
    for layer in layers:
        depth_y = gw + layer.depth_mm  # depth_mm is negative for below boundary
        ax.plot(xs, depth_y, color=layer.color, lw=2.5, linestyle="--", alpha=0.95)
        # subtle band shading
        if layer.depth_mm > deepest - 0.5:
            band_top = depth_y + 0.3
            band_bot = depth_y - 0.3
            ax.fill_between(xs, band_bot, band_top, color=layer.color, alpha=0.10, zorder=1)
        # Annotation arrow
        if layer.long_label:
            ax.annotate(layer.long_label,
                        xy=(x_extent * 0.9, depth_y[-30]),
                        xytext=(x_extent * 0.75, depth_y[-30] - 1.5),
                        fontsize=10.5, color=layer.color, family="monospace", weight="bold",
                        arrowprops=dict(arrowstyle="->", color=layer.color, lw=1.5))

    # Right depth axis
    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim())
    ticks = [0] + [l.depth_mm for l in layers]
    tlabels = ["WM/GM (0)"] + [l.label for l in layers]
    ax2.set_yticks(ticks)
    ax2.set_yticklabels(tlabels, color=T.ink_text, family="monospace", fontsize=10)
    ax2.tick_params(axis="y", colors=T.muted_text)
    ax2.set_ylabel("depth below WM/GM boundary", color=T.ink_text, fontsize=10.5)
    for s in ("top", "left"):
        ax2.spines[s].set_visible(False)
    ax2.spines["right"].set_color(T.rule)
    ax2.spines["bottom"].set_visible(False)

    ax.set_xticks([])
    ax.set_yticks([])
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)

    ax.set_title(title_text, color=T.ink_text,
                 fontfamily=["Geist Mono", "DejaVu Sans Mono"],
                 fontsize=13, weight="bold", loc="left", pad=14)

    if caption:
        ax.text(0.5, -0.08, caption, transform=ax.transAxes,
                ha="center", color=T.muted_text, fontsize=10, family="sans-serif")


# ---------------------------------------------------------------------------
# 6. compartment_diagram — labeled partition of a whole into compartments
# ---------------------------------------------------------------------------

@dataclass
class Compartment:
    """One labeled compartment in a partition diagram."""
    label: str
    short_label: str
    description: str
    color: str
    fraction: float  # fraction of the whole this compartment occupies (0-1)


def compartment_diagram(
    ax,
    *,
    compartments: Sequence[Compartment],
    title_text: str = "Compartment partition",
    theme: str | None = None,
    orientation: str = "horizontal",  # "horizontal" or "stacked"
) -> None:
    """Labeled partition diagram (horizontal or stacked rectangles).

    Each compartment shows: large letter/label, short title, description.
    Width/height proportional to `fraction`.

    Idiom: "this whole splits into 3 compartments: A (60%) B (30%) C (10%)"
    """
    T = theme_colors(theme)
    ax.set_facecolor("none")
    ax.axis('off')
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    fractions = np.array([c.fraction for c in compartments])
    fractions = fractions / fractions.sum()

    if orientation == "horizontal":
        cursor = 0
        for c, frac in zip(compartments, fractions):
            rect = mpatches.Rectangle((cursor, 0.15), frac, 0.7,
                                       color=c.color, alpha=0.90, edgecolor=T.canvas, linewidth=2)
            ax.add_patch(rect)
            cx = cursor + frac / 2
            ax.text(cx, 0.7, c.short_label, ha="center", va="center",
                    color=text_on_brand_fill(c.color), fontsize=16, family="monospace", weight="bold")
            ax.text(cx, 0.55, c.label, ha="center", va="center",
                    color=text_on_brand_fill(c.color), fontsize=12, family="monospace")
            ax.text(cx, 0.35, c.description, ha="center", va="center",
                    color=text_on_brand_fill(c.color), fontsize=9, family="sans-serif",
                    wrap=True)
            ax.text(cx, 0.08, f"{int(frac*100)}%", ha="center", va="center",
                    color=T.ink_text, fontsize=10, family="monospace")
            cursor += frac
    else:  # stacked
        cursor = 0
        for c, frac in zip(compartments, fractions):
            rect = mpatches.Rectangle((0.1, cursor), 0.8, frac,
                                       color=c.color, alpha=0.90, edgecolor=T.canvas, linewidth=2)
            ax.add_patch(rect)
            cy = cursor + frac / 2
            ax.text(0.5, cy + frac*0.15, c.short_label, ha="center", va="center",
                    color=text_on_brand_fill(c.color), fontsize=16, family="monospace", weight="bold")
            ax.text(0.5, cy - frac*0.15, c.description, ha="center", va="center",
                    color=text_on_brand_fill(c.color), fontsize=10, family="sans-serif")
            cursor += frac

    if title_text:
        ax.set_title(title_text, color=T.ink_text,
                     fontfamily=["Geist Mono", "DejaVu Sans Mono"],
                     fontsize=13, weight="bold", loc="left", pad=10)


# ---------------------------------------------------------------------------
# 7. pipeline_flow — boxed flow diagram with arrows
# ---------------------------------------------------------------------------

@dataclass
class FlowNode:
    """One node (box) in a pipeline flow diagram."""
    label: str
    description: str | None = None
    color: str | None = None
    x: float = 0.0   # 0-1 in axes coords
    y: float = 0.5
    width: float = 0.16
    height: float = 0.30


def pipeline_flow(
    ax,
    *,
    nodes: Sequence[FlowNode],
    arrows: Sequence[tuple[int, int]] | None = None,
    title_text: str = "Pipeline",
    theme: str | None = None,
) -> None:
    """Boxed flow diagram with arrows between nodes.

    Args:
        nodes: list of FlowNode (x, y in axes coords 0-1; auto-tiled left-right if x is default 0)
        arrows: list of (src_idx, dst_idx) pairs; default: linear chain 0→1→2→...

    Idiom: "preprocessing pipeline / decision flow / 3-stage analysis"
    """
    T = theme_colors(theme)
    palette_cycle = [TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET]
    ax.set_facecolor("none")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis('off')

    n = len(nodes)
    # Auto-tile if all x are 0
    if all(node.x == 0.0 for node in nodes) and n > 1:
        for i, node in enumerate(nodes):
            node.x = 0.05 + i * (0.9 / max(1, n - 1)) - node.width / 2

    # Draw boxes
    for i, node in enumerate(nodes):
        c = node.color or palette_cycle[i % len(palette_cycle)]
        box = FancyBboxPatch((node.x, node.y - node.height/2), node.width, node.height,
                              boxstyle="round,pad=0.01", linewidth=2,
                              facecolor=c, edgecolor=T.canvas, alpha=0.90)
        ax.add_patch(box)
        ax.text(node.x + node.width/2, node.y + 0.04, node.label, ha="center", va="center",
                color=text_on_brand_fill(c), fontsize=11.5, family="monospace", weight="bold")
        if node.description:
            ax.text(node.x + node.width/2, node.y - 0.07, node.description, ha="center", va="center",
                    color=text_on_brand_fill(c), fontsize=8.5, family="sans-serif")

    # Draw arrows
    if arrows is None:
        arrows = [(i, i+1) for i in range(n-1)]
    for src, dst in arrows:
        s = nodes[src]; d = nodes[dst]
        start = (s.x + s.width, s.y)
        end = (d.x, d.y)
        arr = FancyArrowPatch(start, end,
                              arrowstyle='-|>', mutation_scale=18, linewidth=2,
                              color=T.muted_text, shrinkA=2, shrinkB=2)
        ax.add_patch(arr)

    if title_text:
        ax.set_title(title_text, color=T.ink_text,
                     fontfamily=["Geist Mono", "DejaVu Sans Mono"],
                     fontsize=13, weight="bold", loc="left", pad=10)


# ---------------------------------------------------------------------------
# 8. four_panel_scorecard — composite of 4 panel-figure functions
# ---------------------------------------------------------------------------

def four_panel_scorecard(
    *,
    panels: Sequence[tuple[str, Callable[[plt.Axes], None]]],
    out_path: str | Path,
    suptitle: str | None = None,
    figsize: tuple[float, float] = (15, 11),
    theme: str | None = None,
    save_data: dict | None = None,
) -> Path:
    """Render a 4-panel composite figure. Each panel is (title, draw_fn).

    Args:
        panels: 4-element list of (panel_title, draw_function_taking_ax)
        suptitle: figure-level title
        save_data: optional dict to JSON-dump as sibling for re-themability

    Saves with transparent background (composite onto deck slide canvas).
    Returns the output path.

    Idiom: "TL;DR scorecard with 4 different visualizations of the same story"
    """
    T = theme_colors(theme)
    fig, axes = plt.subplots(2, 2, figsize=figsize, dpi=160,
                             gridspec_kw=dict(wspace=0.30, hspace=0.45))
    fig.patch.set_alpha(0)

    flat = axes.flatten()
    for i, (panel_title, draw_fn) in enumerate(panels[:4]):
        ax = flat[i]
        ax.set_facecolor("none")
        if panel_title:
            ax.set_title(panel_title, color=T.ink_text,
                         fontfamily=["Geist Mono", "DejaVu Sans Mono"],
                         fontsize=13, weight="bold", loc="left", pad=12)
        draw_fn(ax)

    if suptitle:
        fig.suptitle(suptitle, color=T.ink_text,
                     fontfamily=["Geist Mono", "DejaVu Sans Mono"],
                     fontsize=15.5, weight="bold", y=0.995)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight",
                facecolor="none", edgecolor="none", transparent=True)
    plt.close(fig)

    # Save raw data sibling
    if save_data is not None:
        raw_dir = out_path.parent / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        json_path = raw_dir / (out_path.stem + ".json")
        json_path.write_text(json.dumps(save_data, indent=2, default=str))

    return out_path


# ---------------------------------------------------------------------------
# 9. Helpers for common standalone figures
# ---------------------------------------------------------------------------

def save_with_transparent_bg(
    fig,
    out_path: str | Path,
    dpi: int = 200,
) -> Path:
    """Save a figure with transparent background — for composition onto deck canvas.

    Use this instead of `fig.savefig(..., facecolor=T.canvas)` for any figure
    that will be embedded in a deck slide. The slide background shows through.
    Standalone-preview viewers may show it on white/checkered — use
    `composite_onto_slate(out_path, slate_hex)` for standalone preview.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight",
                facecolor="none", edgecolor="none", transparent=True)
    return out_path


def composite_onto_canvas(
    src_path: str | Path,
    out_path: str | Path | None = None,
    canvas_hex: str = "#1E293B",
) -> Path:
    """Composite a transparent figure onto a solid canvas color for standalone preview.

    Useful when the user wants to preview a slide-embedded figure without
    re-rendering the whole deck. canvas_hex matches the deck theme bg.
    """
    from PIL import Image
    src_path = Path(src_path)
    out_path = Path(out_path or str(src_path).replace(".png", "_on_canvas.png"))
    img = Image.open(src_path)
    rgb = tuple(int(canvas_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    bg = Image.new("RGB", img.size, rgb)
    bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
    bg.save(out_path)
    return out_path
