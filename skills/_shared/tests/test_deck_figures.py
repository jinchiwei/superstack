"""Smoke tests for the figure archetype library.

These tests verify each archetype renders without crashing AND produces a non-empty PNG.
Visual quality is checked by manually rendering deck slides with these helpers; this test
file is the regression backstop."""
from __future__ import annotations

import sys
from pathlib import Path
import tempfile

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mpl_style import apply_style, TURQUOISE, DEEPPINK, AMBER, BLUEVIOLET
from deck_figures import (
    region_dot_strip,
    comparison_bars,
    aic_or_metric_curves,
    binary_grid,
    depth_schematic, DepthLayer,
    compartment_diagram, Compartment,
    pipeline_flow, FlowNode,
    four_panel_scorecard,
    save_with_transparent_bg,
    composite_onto_canvas,
)

apply_style(theme="slate")


def _save_and_check(fig, name):
    """Save figure to tempfile, verify it's a non-empty PNG."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / name
        save_with_transparent_bg(fig, out)
        plt.close(fig)
        assert out.exists(), f"{name} not written"
        assert out.stat().st_size > 1000, f"{name} suspiciously small ({out.stat().st_size}b)"


def test_region_dot_strip():
    fig, ax = plt.subplots(figsize=(8, 3))
    items = ["a","b","c","d","e","f","g","h","i","j","k"]
    rows = [
        ("10mm", [0.01, -0.02, 0.03, -0.01, 0.04, 0.02, 0.05, 0.01, 0.03, -0.01, 0.02]),
        ("2mm",  [0.005, -0.01, 0.02, -0.02, 0.03, 0.01, 0.04, -0.005, 0.02, -0.02, 0.01]),
    ]
    region_dot_strip(ax, items=items, rows=rows,
                     legend=[("positive", TURQUOISE), ("negative", DEEPPINK)],
                     theme="slate")
    _save_and_check(fig, "region_dot_strip.png")


def test_comparison_bars():
    fig, ax = plt.subplots(figsize=(8, 4))
    comparison_bars(ax,
        items=["item1", "item2"],
        cond_a=("A", [0.015, 0.013], [0.012, 0.021]),
        cond_b=("B", [0.003, 0.007], [0.63, 0.29]),
        theme="slate",
    )
    _save_and_check(fig, "comparison_bars.png")


def test_aic_curves():
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = np.linspace(0.5, 12, 24)
    ys_a = np.clip(2 * (xs - 1.5)**2 / 3 - 4.3, -4.5, 6)
    ys_b = np.full_like(xs, 1.5)
    aic_or_metric_curves(ax,
        curves=[("A", xs.tolist(), ys_a.tolist(), TURQUOISE),
                ("B", xs.tolist(), ys_b.tolist(), DEEPPINK)],
        theme="slate",
    )
    _save_and_check(fig, "aic_curves.png")


def test_binary_grid():
    fig, ax = plt.subplots(figsize=(10, 3))
    items = [f"r{i}" for i in range(11)]
    binary_grid(ax, items=items,
                rows=[("cond_a", [True]*10 + [False]),
                      ("cond_b", [True] + [False]*10)],
                theme="slate")
    _save_and_check(fig, "binary_grid.png")


def test_depth_schematic():
    fig, ax = plt.subplots(figsize=(10, 6))
    layers = [
        DepthLayer(depth_mm=-2,  color=TURQUOISE, label="−2mm",  long_label="juxtacortical"),
        DepthLayer(depth_mm=-10, color=DEEPPINK,  label="−10mm", long_label="deep WM"),
    ]
    depth_schematic(ax, layers=layers, theme="slate")
    _save_and_check(fig, "depth_schematic.png")


def test_compartment_diagram():
    fig, ax = plt.subplots(figsize=(10, 4))
    comps = [
        Compartment(label="U-fibers", short_label="A", description="juxtacortical",
                    color=TURQUOISE, fraction=0.3),
        Compartment(label="Major bundles", short_label="B", description="pyAFQ tracts",
                    color=DEEPPINK, fraction=0.5),
        Compartment(label="WM rim", short_label="C", description="residual",
                    color=AMBER, fraction=0.2),
    ]
    compartment_diagram(ax, compartments=comps, orientation="horizontal", theme="slate")
    _save_and_check(fig, "compartment_diagram.png")


def test_pipeline_flow():
    fig, ax = plt.subplots(figsize=(12, 3))
    nodes = [
        FlowNode(label="DWI", description="raw"),
        FlowNode(label="Preproc", description="QSI"),
        FlowNode(label="FERNET", description="FW fit"),
        FlowNode(label="Surface project", description="DKTatlas"),
    ]
    pipeline_flow(ax, nodes=nodes, theme="slate")
    _save_and_check(fig, "pipeline_flow.png")


def test_four_panel_scorecard():
    items = ["a","b","c","d","e","f","g","h","i","j","k"]
    def p1(ax): region_dot_strip(ax, items=items,
        rows=[("A", [0.1]*11), ("B", [-0.1]*11)], theme="slate")
    def p2(ax): comparison_bars(ax, items=["x","y"],
        cond_a=("A", [0.01, 0.02], [0.01, 0.02]),
        cond_b=("B", [0.005, 0.01], [0.1, 0.5]), theme="slate")
    def p3(ax): aic_or_metric_curves(ax,
        curves=[("A", [1,2,3,4], [-2,-4,-3,0], TURQUOISE)], theme="slate")
    def p4(ax): binary_grid(ax, items=items,
        rows=[("A", [True]*11), ("B", [True]+[False]*10)], theme="slate")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "scorecard.png"
        four_panel_scorecard(
            panels=[("1.", p1), ("2.", p2), ("3.", p3), ("4.", p4)],
            out_path=out, suptitle="test", theme="slate",
            save_data={"items": items},
        )
        assert out.exists() and out.stat().st_size > 5000
        # Raw JSON
        raw = out.parent / "raw" / "scorecard.json"
        assert raw.exists()


def test_composite_onto_canvas():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([1,2,3], [4,5,6])
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "transparent.png"
        save_with_transparent_bg(fig, src)
        plt.close(fig)
        dst = composite_onto_canvas(src, Path(td) / "composited.png", canvas_hex="#1E293B")
        assert dst.exists() and dst.stat().st_size > 500


if __name__ == "__main__":
    test_region_dot_strip()
    test_comparison_bars()
    test_aic_curves()
    test_binary_grid()
    test_depth_schematic()
    test_compartment_diagram()
    test_pipeline_flow()
    test_four_panel_scorecard()
    test_composite_onto_canvas()
    print("ALL TESTS PASS")
