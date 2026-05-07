"""Build a session results pptx for an autoresearch session.

Reads:
  results/{date}_{scope}/README.md          - session header + candidate table
  results/{date}_{scope}/iter-*/summary.md  - one slide per iteration
  results/{date}_{scope}/iter-*/fig_*.png   - auto-embedded on the iter slide

Writes:
  results/{date}_{scope}/_deck.md              - synthesized markdown source
  results/{date}_{scope}/_deck.md.layout.json  - layout sidecar (replayable)
  results/{date}_{scope}/SESSION_REPORT.pptx   - branded deck

Pipeline: this template synthesizes a markdown deck (with image refs to every
`fig_*.png` under the iter dirs) and then shells out to the `build-pptx` skill,
which dispatches to its full layout catalog (figure-with-aside,
content-text-image, cards-grid, etc) and applies the standard Jin branding.

Override the synthesized deck by editing `_deck.md` and re-running build-pptx
directly:
    python <superstack>/skills/build-pptx/build.py \\
        --input results/{date}_{scope}/_deck.md \\
        --output results/{date}_{scope}/SESSION_REPORT.pptx

Project-specific styling: extend or replace this template freely. The contract
is the `--date` + `--scope` CLI surface; everything else is replaceable.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Locate the build-pptx skill. Default: assume superstack at ~/arcadia/superstack;
# override via $SUPERSTACK_HOME.
# ---------------------------------------------------------------------------

def _find_build_pptx() -> Path:
    candidates = [
        Path(os.environ.get("SUPERSTACK_HOME", ""))
            / "skills" / "build-pptx" / "build.py",
        Path.home() / "arcadia" / "superstack" / "skills" / "build-pptx" / "build.py",
        Path.home() / ".claude" / "skills" / "build-pptx" / "build.py",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise SystemExit(
        "Could not locate build-pptx skill. Set SUPERSTACK_HOME or install the skill."
    )


# ---------------------------------------------------------------------------
# Markdown synthesis
# ---------------------------------------------------------------------------

def _humanize(slug: str) -> str:
    if not slug:
        return ""
    slug = re.sub(r"^iter-\d+_", "", slug)
    parts = re.split(r"[-_]+", slug)
    return " ".join(p[:1].upper() + p[1:] if p else "" for p in parts).strip()


def _read_iter_summary(iter_dir: Path) -> str:
    summary = iter_dir / "summary.md"
    if not summary.is_file():
        return ""
    text = summary.read_text(encoding="utf-8")
    # Strip leading h1 (we replace with our own iter title) — keep the rest verbatim.
    return re.sub(r"\A#\s+[^\n]*\n+", "", text).strip()


def _extract_headline(summary_text: str) -> str:
    """Pull the headline metric line out of a summary so we can use it as a
    short slide caption. Looks for the first line beginning with **Headline
    metric** or **<word> AUC** etc. Returns "" if nothing obvious."""
    if not summary_text:
        return ""
    for line in summary_text.splitlines():
        s = line.strip()
        if s.startswith("**Headline metric"):
            # Strip leading "**Headline metric (...):**" wrapper
            return re.sub(r"\*\*[^*]+\*\*\s*", "", s, count=1).strip()
        if s.startswith("**") and ("AUC" in s or "ECE" in s or "metric" in s.lower()):
            return re.sub(r"\*\*([^*]+)\*\*\s*:?\s*", r"\1: ", s, count=1).strip()
    # Fallback: first non-empty paragraph, capped
    for line in summary_text.splitlines():
        s = line.strip()
        if s and not s.startswith(("|", "#", "`")):
            return s[:160].rstrip()
    return ""


def _iter_figures(iter_dir: Path) -> list[Path]:
    """Return all fig_*.png files in the iter dir, sorted by name."""
    if not iter_dir.is_dir():
        return []
    return sorted(iter_dir.glob("fig_*.png"))


def _iter_dirs(session_root: Path) -> list[Path]:
    if not session_root.is_dir():
        return []
    return sorted([p for p in session_root.iterdir()
                   if p.is_dir() and p.name.startswith("iter-")])


def _read_readme_meta(session_root: Path) -> dict:
    """Pull scope text + target from results/<date>_<scope>/README.md if present."""
    readme = session_root / "README.md"
    meta = {"scope_text": "", "target": ""}
    if not readme.is_file():
        return meta
    text = readme.read_text(encoding="utf-8")
    scope_m = re.search(r"\*\*Scope:\*\*\s*(.+)", text)
    target_m = re.search(r"\*\*Target:\*\*\s*(.+)", text)
    if scope_m:
        meta["scope_text"] = scope_m.group(1).strip()
    if target_m:
        meta["target"] = target_m.group(1).strip()
    return meta


def synthesize_deck_md(session_root: Path, *, date: str, scope: str) -> str:
    """Build the markdown source for build-pptx.

    Slide policy: one clean slide per iteration. Each iter slide has:
      - title           "iter-N — <candidate humanized>"
      - lede            the headline metric line (one-liner)
      - one figure      first fig_*.png in the iter dir (build-pptx will pick
                        figure-with-aside / -horizontal based on aspect)

    Iter slides do NOT include tables, second figures, or multi-section H2
    bodies — those packed badly into content-text-image and frequently caused
    PowerPoint to flag the file for repair. Tables belong in scorecard.xlsx
    and the per-iter summary.md (and PDF/DOCX exports). Iters that produced
    no figure get a one-card slide with the headline as the card body.
    """
    meta = _read_readme_meta(session_root)
    pretty_scope = _humanize(scope)
    target_line = meta["target"] or "no explicit target — stop on exhaustion"

    parts: list[str] = []
    # YAML frontmatter — build-pptx renders this into the title slide. No
    # leading body H1 (that produces a duplicate title slide).
    parts.append("---")
    parts.append(f'title: "{pretty_scope} — Session Report"')
    parts.append(f'subtitle: "Autoresearch · {date}"')
    parts.append(f'date: "{date}"')
    parts.append("---")
    parts.append("")

    # Optional scope/target preamble as a single content slide.
    if meta["scope_text"] or meta["target"]:
        parts.append("## Session overview")
        parts.append("")
        if meta["scope_text"]:
            parts.append(meta["scope_text"])
            parts.append("")
        parts.append(f"Target — {target_line}")
        parts.append("")

    iters = _iter_dirs(session_root)
    for d in iters:
        m = re.match(r"iter-(\d+)_(.+)", d.name)
        if not m:
            continue
        iter_num = int(m.group(1))
        candidate = m.group(2)
        body = _read_iter_summary(d)
        headline = _extract_headline(body)
        figs = _iter_figures(d)

        parts.append("---")
        parts.append("")
        parts.append(f"## iter-{iter_num} — {_humanize(candidate)}")
        parts.append("")
        if headline:
            parts.append(headline)
            parts.append("")

        if figs:
            # First figure only — build-pptx picks figure-with-aside or
            # figure-with-aside-horizontal based on aspect ratio. Embedding a
            # second figure here forces the planner to fall back to
            # content-image-only (no caption) or splits to two slides
            # without a caption — neither matches the headline-aside pattern
            # we want.
            fig = figs[0]
            try:
                rel = fig.resolve().relative_to(session_root.resolve())
            except ValueError:
                rel = fig
            parts.append(f"![{fig.stem}]({rel})")
            parts.append("")
        elif not headline:
            # No figure AND no headline — emit a placeholder so the slide
            # isn't visually empty. The scorecard.xlsx still has the data.
            parts.append("(no figure produced — see scorecard.xlsx)")
            parts.append("")

    # No explicit closing slide — build-pptx adds its own "Thanks" end slide
    # automatically. Adding our own markdown closing produced two stacked
    # Thanks slides at the end of the deck.

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                   help="Session date (YYYY-MM-DD).")
    p.add_argument("--scope", required=True, help="Session scope slug.")
    p.add_argument("--output", default=None,
                   help="Output pptx path. Default: results/<date>_<scope>/SESSION_REPORT.pptx")
    args = p.parse_args()

    session_root = Path("results") / f"{args.date}_{args.scope}"
    if not session_root.is_dir():
        raise SystemExit(f"No session at {session_root}")

    deck_md = session_root / "_deck.md"
    deck_md.write_text(synthesize_deck_md(session_root, date=args.date, scope=args.scope),
                       encoding="utf-8")

    out_pptx = Path(args.output) if args.output else session_root / "SESSION_REPORT.pptx"
    out_pptx.parent.mkdir(parents=True, exist_ok=True)

    build_pptx = _find_build_pptx()
    cmd = [
        sys.executable, str(build_pptx),
        "--input", str(deck_md),
        "--output", str(out_pptx),
    ]
    subprocess.run(cmd, check=True)
    print(f"wrote {out_pptx}")


if __name__ == "__main__":
    main()
