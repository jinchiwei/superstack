"""build-figure CLI: render a brand-figure script, with optional QA gating.

A figure script just imports `brandfig`, builds figures, and calls
`brandfig.save(...)`. This runner executes such a script with a chosen default
theme and (optionally) fails when any figure trips the QA checks -- handy in a
build pipeline or pre-commit.

    python build_figure.py path/to/figs.py                 # run, warn on QA
    python build_figure.py path/to/figs.py --theme bone     # default theme
    python build_figure.py path/to/figs.py --strict         # exit 1 on any QA issue
    python build_figure.py --demo out.png                   # emit a sample figure

The script is run with this skill dir on sys.path, so `import brandfig` works
from anywhere. `--theme` sets BRANDFIG_THEME, which brandfig.use() reads as its
default; a script that calls brandfig.use("...") explicitly still wins.
"""
from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _demo(out_path: str, theme: str):
    import brandfig as bf
    bf.use(theme)
    fig, ax = bf.fig(figsize=(7, 3.6))
    vals = [3.7, 7.4, 15.8, 76.2]
    labels = ["low", "low-mid", "up-mid", "high"]
    ax.bar(labels, vals, color=[bf.DEEPPINK, bf.TURQUOISE, bf.TURQUOISE, bf.TURQUOISE])
    for x, v in enumerate(vals):
        ax.text(x, v + 1.5, f"{v:g}", ha="center", va="bottom",
                family="Geist Mono", fontweight="bold", color=bf.ink())
    ax.set_ylabel("per million")
    bf.figtitle(fig, "brand-figure demo")
    bf.save(fig, out_path)
    print(f"wrote {out_path}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a brand-figure script with QA.")
    ap.add_argument("script", nargs="?", help="figure script that imports brandfig")
    ap.add_argument("--theme", default="bone", help="default theme (paper/bone/slate/midnight/forest)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any QA issue is found")
    ap.add_argument("--demo", metavar="OUT.png", help="emit a sample figure and exit")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(HERE))
    os.environ["BRANDFIG_THEME"] = args.theme

    if args.demo:
        _demo(args.demo, args.theme)
        return 0
    if not args.script:
        ap.error("provide a figure script, or --demo OUT.png")

    import brandfig as bf
    bf.ISSUES.clear()
    runpy.run_path(args.script, run_name="__main__")

    n = len(bf.ISSUES)
    if n:
        print(f"\nbuild-figure: {n} QA issue(s) across the rendered figures.", file=sys.stderr)
        if args.strict:
            return 1
    else:
        print("build-figure: QA clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
