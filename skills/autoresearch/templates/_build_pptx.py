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

    Follows the canonical research-deck structure documented in
    skills/build-pptx/SKILL.md and exemplified by tests/fixture_realistic.md:

      # H1  — auto-emits a section-divider slide (navy background)
      ## H2 — content slide title under the previous H1's section

    Sections emitted:
      Title slide        (auto from YAML frontmatter — name, org, date)
      # Background       — scope + motivation + target
      # Methods          — search axes + CV / methodology
      # Results          — top-3 candidates + performance summary
      # Conclusions      — best config + recommendations
      # Iteration detail — one slide per iter (figure + headline metric)
      Thanks             (auto-added by build-pptx)

    Each section has multiple substantive H2 content slides — no one-liner
    sparse slides, no slides packed with table+image+text overflow.

    Optional override: if `<session_root>/findings.md` exists, its body
    replaces the auto-generated Background+Methods+Results+Conclusions block.
    The user is expected to author that file with proper section structure
    (H1 dividers + H2 content slides). Iter detail is always auto-generated.
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
    parts.append('subtitle: "Autoresearch session report"')
    parts.append('eyebrow: "AUTORESEARCH"')
    if author.get("name"):
        parts.append(f'name: "{author["name"]}"')
    if author.get("org"):
        parts.append(f'org: "{author["org"]}"')
    parts.append(f'date: "{date}"')
    parts.append("---")
    parts.append("")

    # ---- Body: user-provided narrative or auto-generated -------------------
    findings = session_root / "findings.md"
    if findings.is_file():
        # User has provided structured narrative — drop it in verbatim. They
        # are expected to use proper H1/H2 structure.
        parts.append(findings.read_text(encoding="utf-8").strip())
        parts.append("")
    else:
        parts.extend(_render_auto_narrative(
            scope=scope, pretty_scope=pretty_scope,
            meta=meta, state=state, target_line=target_line,
            session_root=session_root,
        ))

    # ---- Iteration detail section -----------------------------------------
    iters = _iter_dirs(session_root)
    if iters:
        parts.append("---")
        parts.append("")
        parts.append("# Iteration detail")
        parts.append("")

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
                fig = figs[0]
                try:
                    rel = fig.resolve().relative_to(session_root.resolve())
                except ValueError:
                    rel = fig
                parts.append(f"![{fig.stem}]({rel})")
                parts.append("")
            elif not headline:
                parts.append("(no figure produced — see scorecard.xlsx)")
                parts.append("")

    # No explicit closing slide — build-pptx auto-adds Thanks.
    return "\n".join(parts)


def _render_auto_narrative(*, scope: str, pretty_scope: str, meta: dict,
                           state: dict, target_line: str,
                           session_root: Path) -> list[str]:
    """Auto-generate the Background / Methods / Results / Conclusions sections
    when no findings.md is present. Returns a list of markdown lines (no
    leading "---" — caller stitches sections together)."""
    iters = _iter_dirs(session_root)
    n_iters_total = len(iters)
    axes = _summarize_axes(state.get("axes") or {})
    n_candidates_planned = len(state.get("candidate_queue") or [])
    target_op = "max"
    target_meta = state.get("target_metric") or {}
    if isinstance(target_meta, dict) and target_meta.get("op") in ("min", "max"):
        target_op = target_meta["op"]
    top = _top_results(state.get("results_history") or [], op=target_op, k=3)
    op_label = "highest" if target_op == "max" else "lowest"
    all_metrics = [r.get("metric_value") for r in (state.get("results_history") or [])
                   if isinstance(r.get("metric_value"), (int, float))]

    out: list[str] = []

    # ===== Background section =====
    out += ["---", "", "# Background", ""]

    # H2 1: Scope + motivation
    out += ["---", "", "## Scope and motivation", ""]
    if meta["scope_text"]:
        out += [meta["scope_text"], ""]
    else:
        out += [f"Autoresearch session for `{scope}`. The session sweeps a "
                "configured search space across modeling axes, runs each "
                "candidate end-to-end, and ranks them by a target metric.", ""]
    if state.get("axes_rationale"):
        out += [state["axes_rationale"], ""]
    out += [f"This session ran **{n_iters_total} iterations** over "
            f"**{n_candidates_planned}** planned candidates, with results "
            f"persisted to `results/` and `scorecard.xlsx` for downstream "
            "analysis.", ""]

    # H2 2: Search target
    out += ["---", "", "## Search target", ""]
    out += [f"**Target** — {target_line}", ""]
    if isinstance(target_meta, dict) and target_meta.get("metric"):
        out += [f"Optimization direction: `{target_op}imize "
                f"{target_meta['metric']}`. Each iteration writes a "
                "`summary.md` whose first non-blank metric line is parsed "
                "and ranked.", ""]
    else:
        out += ["No explicit numeric target was set; the session ran until "
                "the candidate queue was exhausted, then ranked completed "
                "iterations by their reported metrics.", ""]

    # ===== Methods section =====
    out += ["---", "", "# Methods", ""]

    # H2 1: Search axes
    if axes:
        out += ["---", "", "## Search axes", ""]
        for name, vals in axes:
            out += [f"### `{name}`", "", vals, ""]
    else:
        out += ["---", "", "## Search structure", "",
                f"Single-track session with no branching axes. "
                f"{n_iters_total} iterations queued from project context.", ""]

    # H2 2: Pipeline / iteration loop
    out += ["---", "", "## Iteration loop", "",
            "Each candidate is run independently end-to-end with stdout "
            "captured to `last-iteration.log`. Results land in "
            "`$AUTORESEARCH_OUT_RESULTS/{summary.md, metrics.json, fig_*.png}`.",
            "",
            "After each iteration the autoresearch skill records the result "
            "in `state.json`, runs adaptive replanning, appends a block to "
            "the research-log entry, and schedules the next iteration. "
            "On error, the failure pipeline classifies and routes to retry, "
            "code-fix, or skip.", ""]

    # ===== Results section =====
    if top or all_metrics:
        out += ["---", "", "# Results", ""]

        # H2 1: Top candidates table
        if top:
            out += ["---", "", "## Top candidates", "",
                    f"Top candidates by metric ({op_label} first):", "",
                    "| Rank | Candidate | Metric |",
                    "|---|---|---:|"]
            for rank, r in enumerate(top, 1):
                cand_id = r.get("id", "—")
                metric = r.get("metric_value")
                if isinstance(metric, (int, float)):
                    out.append(f"| {rank} | `{cand_id}` | {metric:.4f} |")
                else:
                    out.append(f"| {rank} | `{cand_id}` | — |")
            out += [""]

        # H2 2: Headline numbers / spread
        if len(all_metrics) >= 2:
            out += ["---", "", "## Performance spread", ""]
            best_m = max(all_metrics) if target_op == "max" else min(all_metrics)
            worst_m = min(all_metrics) if target_op == "max" else max(all_metrics)
            spread = abs(best_m - worst_m)
            out += [f"Across {len(all_metrics)} completed iterations, the "
                    f"target metric ranged from **{worst_m:.4f}** "
                    f"(weakest) to **{best_m:.4f}** (strongest) — a spread "
                    f"of **{spread:.4f}**.", ""]
            if top and len(top) >= 2:
                m1 = top[0].get("metric_value")
                m2 = top[1].get("metric_value")
                if isinstance(m1, (int, float)) and isinstance(m2, (int, float)):
                    delta = abs(m1 - m2)
                    out += [f"The top two candidates differ by "
                            f"**{delta:.4f}** — see "
                            f"`scorecard.xlsx` for bootstrap CIs and "
                            "stratum-level breakdown.", ""]

    # ===== Conclusions section =====
    if top:
        out += ["---", "", "# Conclusions", ""]

        # H2 1: Best configuration
        best = top[0]
        out += ["---", "", "## Best configuration", ""]
        cand_id = best.get("id", "—")
        metric = best.get("metric_value")
        out += [f"**Configuration** — `{cand_id}`", ""]
        if isinstance(metric, (int, float)):
            out += [f"**Headline metric** — {metric:.4f}", ""]
        out += ["See the iteration-detail section for per-candidate ROC "
                "and calibration figures, or `scorecard.xlsx` for the full "
                "ranked matrix with bootstrap CIs.", ""]

        # H2 2: Recommendations
        out += ["---", "", "## Recommendations", ""]
        if len(top) >= 2:
            ru = ", ".join(f"`{r['id']}`" for r in top[1:])
            out += [f"- **Ship** `{cand_id}` for downstream evaluation.", ""]
            out += [f"- **Validate** the top configuration on held-out data "
                    "before locking it in for deployment.", ""]
            out += [f"- **Compare** against runners-up ({ru}) "
                    "if their tradeoffs (calibration, fairness, "
                    "interpretability) matter for the deployment context.", ""]
        else:
            out += [f"- Treat `{cand_id}` as the working best.", ""]
            out += ["- Validate on held-out data before deployment.", ""]
        out += ["- Open questions and follow-up axes belong in the "
                "research-log entry for this session.", ""]

    return out


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
