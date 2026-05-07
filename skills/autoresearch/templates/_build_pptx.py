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
import json
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


def _load_author() -> dict:
    """Resolve author metadata for the deck byline.

    Resolution order:
      1. $AUTORESEARCH_AUTHOR_NAME / $AUTORESEARCH_AUTHOR_ORG env vars
      2. ~/.gstack/superstack/author.json (canonical config)
      3. {} (no byline)
    """
    name = os.environ.get("AUTORESEARCH_AUTHOR_NAME", "").strip()
    org = os.environ.get("AUTORESEARCH_AUTHOR_ORG", "").strip()
    email = os.environ.get("AUTORESEARCH_AUTHOR_EMAIL", "").strip()
    if name or org:
        return {"name": name, "org": org, "email": email}
    cfg = Path.home() / ".gstack" / "superstack" / "author.json"
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            return {
                "name":  (data.get("name")  or "").strip(),
                "org":   (data.get("org")   or "").strip(),
                "email": (data.get("email") or "").strip(),
            }
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _read_state(scope_slug: str) -> dict:
    """Best-effort: load the autoresearch state.json so we can populate
    the methods + results slides with axes, candidate count, and
    completed-iter metrics. Returns {} if state isn't found.

    Tries cwd-derived slug first (the canonical project key), then the scope
    slug as a fallback.
    """
    gstack_home = Path(os.environ.get("GSTACK_HOME", Path.home() / ".gstack"))
    cwd_slug = Path.cwd().resolve().name
    candidates = [
        gstack_home / "projects" / cwd_slug   / "autoresearch" / "state.json",
        gstack_home / "projects" / scope_slug / "autoresearch" / "state.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
    return {}


def _summarize_axes(axes: dict) -> list[tuple[str, str]]:
    """Turn an axes dict into [(name, "value, value, value")] tuples for
    display on the methods slide."""
    out = []
    for k, v in (axes or {}).items():
        if isinstance(v, (list, tuple)):
            out.append((k, ", ".join(str(x) for x in v)))
        else:
            out.append((k, str(v)))
    return out


def _top_results(results_history: list, *, op: str = "max", k: int = 3) -> list:
    """Return the top-k completed results by metric_value, descending if
    op='max' else ascending. Skips entries without a numeric metric_value."""
    valid = [r for r in (results_history or [])
             if isinstance(r.get("metric_value"), (int, float))
             and r.get("status") == "complete"]
    reverse = (op == "max")
    valid.sort(key=lambda r: r["metric_value"], reverse=reverse)
    return valid[:k]


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

    Deck structure (research-presentation flow):
      1. Title slide (auto from frontmatter — name, org, date)
      2. Background — scope + target metric + motivation
      3. Methods — axes / candidate count / cohort + CV summary from state.json
      4. Results — top candidates by metric (auto-ranked from results_history)
      5. Conclusions — best candidate + recommendations
      6. Iteration detail — one slide per iter with headline + figure
      7. Thanks (auto-added by build-pptx)

    Iter slides do NOT include tables, second figures, or multi-section H2
    bodies — those packed badly into content-text-image and frequently caused
    PowerPoint to flag the file for repair. Tables belong in scorecard.xlsx
    and the PDF/DOCX exports.
    """
    meta = _read_readme_meta(session_root)
    state = _read_state(scope)
    author = _load_author()
    pretty_scope = _humanize(scope)
    target_line = meta["target"] or state.get("scope") or "no explicit target — stop on exhaustion"

    parts: list[str] = []

    # ---- YAML frontmatter (build-pptx auto-renders the title slide) -------
    parts.append("---")
    parts.append(f'title: "{pretty_scope}"')
    parts.append(f'subtitle: "Autoresearch session report"')
    if author.get("name"):
        parts.append(f'name: "{author["name"]}"')
    if author.get("org"):
        parts.append(f'org: "{author["org"]}"')
    parts.append(f'date: "{date}"')
    parts.append("---")
    parts.append("")

    # ---- Background slide --------------------------------------------------
    parts.append("## Background")
    parts.append("")
    if meta["scope_text"]:
        parts.append(f"**Scope** — {meta['scope_text']}")
    else:
        parts.append(f"**Scope** — {pretty_scope}")
    parts.append("")
    parts.append(f"**Target** — {target_line}")
    parts.append("")
    n_iters_total = len(_iter_dirs(session_root))
    parts.append(f"**Iterations completed** — {n_iters_total}")
    parts.append("")

    # ---- Methods slide -----------------------------------------------------
    axes = _summarize_axes(state.get("axes") or {})
    n_candidates_planned = len(state.get("candidate_queue") or [])
    if axes or n_candidates_planned or state.get("axes_rationale"):
        parts.append("---")
        parts.append("")
        parts.append("## Methods")
        parts.append("")
        if axes:
            parts.append("**Search axes**")
            for name, vals in axes:
                parts.append(f"- `{name}` — {vals}")
            parts.append("")
        if n_candidates_planned:
            parts.append(f"**Candidates planned** — {n_candidates_planned} "
                         f"(Cartesian product of axes; pending replans)")
            parts.append("")
        rationale = state.get("axes_rationale") or ""
        if rationale and len(rationale) < 400:
            parts.append(rationale)
            parts.append("")

    # ---- Results slide -----------------------------------------------------
    target_op = "max"
    target_meta = state.get("target_metric") or {}
    if isinstance(target_meta, dict) and target_meta.get("op") in ("min", "max"):
        target_op = target_meta["op"]
    top = _top_results(state.get("results_history") or [], op=target_op, k=3)
    if top:
        parts.append("---")
        parts.append("")
        parts.append("## Results")
        parts.append("")
        op_label = "highest" if target_op == "max" else "lowest"
        parts.append(f"Top candidates by metric ({op_label} first):")
        parts.append("")
        parts.append("| Rank | Candidate | Metric |")
        parts.append("|---|---|---:|")
        for rank, r in enumerate(top, 1):
            cand_id = r.get("id", "—")
            metric = r.get("metric_value")
            parts.append(f"| {rank} | `{cand_id}` | {metric:.4f} |"
                         if isinstance(metric, (int, float))
                         else f"| {rank} | `{cand_id}` | — |")
        parts.append("")

    # ---- Conclusions slide -------------------------------------------------
    if top:
        parts.append("---")
        parts.append("")
        parts.append("## Conclusions")
        parts.append("")
        best = top[0]
        cand_id = best.get("id", "—")
        metric = best.get("metric_value")
        parts.append(f"**Best configuration** — `{cand_id}`"
                     + (f" (metric = {metric:.4f})"
                        if isinstance(metric, (int, float)) else ""))
        parts.append("")
        # Auto-fold the second + third place into a quick comparison line so
        # the slide isn't a one-liner.
        if len(top) >= 2:
            others = ", ".join(
                f"`{r['id']}` ({r['metric_value']:.4f})" for r in top[1:]
            )
            parts.append(f"Runners-up — {others}")
            parts.append("")
        parts.append("Per-iteration figures + tables follow. "
                     "Full data + bootstrap CIs in `scorecard.xlsx`.")
        parts.append("")

    # ---- Per-iteration detail slides --------------------------------------
    if n_iters_total:
        parts.append("---")
        parts.append("")
        parts.append("## Iteration detail")
        parts.append("")
        parts.append(f"{n_iters_total} iterations — one figure per slide, "
                     "headline metric as caption.")
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
    # automatically.

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
