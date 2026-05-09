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
    # Strip trailing version markers like "_v2", "_v3_strat", "_rerun" that
    # bloat the rendered slide title and force figure-with-aside to wrap →
    # shrink the figure. The slug stays in the dir / state.json for ID
    # purposes; we just don't show it on the slide.
    slug = re.sub(r"_(v\d+(_\w+)?|rerun|retry|fix\d*)$", "", slug)
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


_PHASE_PURPOSES = {
    "per_site":       "How does the model perform on each individual site? Tests for site-specific failure modes that aggregate metrics hide.",
    "cohort_fair":    "Apples-to-apples comparison across cohorts using both standard CV and site-stratified CV — separates model quality from cohort difficulty.",
    "loso":           "Leave-one-site-out — does the model generalize to a held-out site it has never seen during training?",
    "fusion_variant": "Tab-only vs image-only vs early-concat vs late-fusion — which fusion strategy actually wins?",
    "calibration":    "Are the predicted probabilities trustworthy? Compares raw / Platt / isotonic / temperature-scaled outputs by ECE.",
    "stratified":     "Performance by patient subgroup (sex, age, centor, etc) — surfaces fairness or worst-case-stratum gaps.",
    "ablation":       "Which input feature or component is actually carrying the signal?",
    "hpo":            "Hyperparameter sweep — locates the operating point in axes-space.",
}


def _extract_secondary_metric(summary_text: str) -> str:
    """Pull a SECOND headline-style line from a summary (e.g., site-stratified
    AUC line that follows the standard CV one). Returns "" if none."""
    if not summary_text:
        return ""
    headlines = []
    for line in summary_text.splitlines():
        s = line.strip()
        # Match either "**Headline metric ...:** X" or "**Site-stratified ... AUC:** X"
        m = re.match(r"^\*\*([^*]+)\*\*\s*:?\s*(.*)$", s)
        if m and ("AUC" in s or "ECE" in s or "metric" in s.lower()):
            label = m.group(1).strip().rstrip(":").strip()
            value = m.group(2).strip().lstrip(":").strip()
            if value:  # only count lines that actually have a value
                headlines.append(f"{label}: {value}")
        if len(headlines) >= 2:
            return headlines[1]
    return ""


def _peer_comparison(results_history: list, axes_dict: dict, this_axes: dict,
                     this_metric, target_op: str = "max") -> str:
    """Find a peer iteration (same phase, different cohort) and produce a
    comparison string like "vs 5site: −0.043". Returns "" if no good peer."""
    if not isinstance(this_metric, (int, float)):
        return ""
    if not this_axes or "phase" not in this_axes or "cohort" not in this_axes:
        return ""
    peer = None
    for r in (results_history or []):
        if r.get("status") != "complete":
            continue
        rax = r.get("axes") or {}
        if (rax.get("phase") == this_axes.get("phase")
            and rax.get("cohort") != this_axes.get("cohort")
            and isinstance(r.get("metric_value"), (int, float))):
            peer = r
            break
    if peer is None:
        return ""
    peer_metric = peer["metric_value"]
    delta = this_metric - peer_metric
    sign = "+" if delta >= 0 else "−"
    return (f"vs {peer['axes']['cohort']}: {sign}{abs(delta):.4f}"
            + (" (better)" if (delta > 0) == (target_op == "max") else " (worse)"))


def _read_iter_metrics(iter_dir: Path) -> dict | None:
    """Load iter-NN/metrics.json if present. Returns the parsed dict or None."""
    p = iter_dir / "metrics.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _format_op_points(op: dict) -> list[str]:
    """Format an op_points dict (with youden / sens95 / spec95 sub-dicts) into
    short markdown bullet strings for the iter slide. Returns ≤2 bullets so
    they fit beside the figure in figure-with-aside."""
    if not op:
        return []
    bullets = []
    y = op.get("youden") or {}
    if y:
        sens, spec = y.get("sens", 0), y.get("spec", 0)
        ppv, npv = y.get("ppv", 0), y.get("npv", 0)
        bullets.append(
            f"- **Operating** — Youden sens {sens:.0%} · spec {spec:.0%} · "
            f"PPV {ppv:.2f} · NPV {npv:.2f}"
        )
    s95 = op.get("sens95") or {}
    sp95 = op.get("spec95") or {}
    extras = []
    if s95:
        extras.append(f"sens@95% spec → spec {s95.get('spec', 0):.2f}")
    if sp95:
        extras.append(f"spec@95% sens → sens {sp95.get('sens', 0):.2f}")
    if extras:
        bullets.append(f"- **Threshold** — {' · '.join(extras)}")
    return bullets


def _result_for_iter(results_history: list, iter_dir_name: str) -> dict | None:
    """Find the matching results_history entry for this iter dir.

    Match is loose: try exact id match first, then look for an entry whose
    axes match what _iter_dirs derives from the dir name."""
    # Strip "iter-NN_" prefix
    cand_slug = re.sub(r"^iter-\d+_", "", iter_dir_name)
    for r in results_history or []:
        if r.get("id") == cand_slug:
            return r
    return None


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
        post_iters_block: list[str] = []
    else:
        narrative = _render_auto_narrative(
            scope=scope, pretty_scope=pretty_scope,
            meta=meta, state=state, target_line=target_line,
            session_root=session_root,
        )
        # Split the narrative into pre-iters (Background / Methods / Results
        # header + analytical-results slides) and post-iters (Conclusions).
        # This way per-iter detail slides go INSIDE the Results section,
        # preserving the Results→iter→Conclusions reading order.
        post_marker = "# Conclusions"
        try:
            split_idx = narrative.index("---") if False else None  # noqa: keep linters happy
            for i, line in enumerate(narrative):
                if line == post_marker:
                    # Step backward to include the preceding "---" + blank.
                    # Narrative emits ["---", "", "# Conclusions", ...]
                    split_idx = i - 2 if i >= 2 and narrative[i - 2] == "---" else i
                    break
            else:
                split_idx = len(narrative)
        except ValueError:
            split_idx = len(narrative)
        parts.extend(narrative[:split_idx])
        post_iters_block = narrative[split_idx:]

    # ---- Per-iteration detail. section_label inherits from the prior # H1
    # ---- (= "Results" when auto-narrative is on, or whatever the user's
    # ---- findings.md ended on). Iter slides live UNDER Results, not in a
    # ---- separate "Iteration detail" section.
    iters = _iter_dirs(session_root)
    if iters:

        # Pre-pull state once so each iter slide can compute peer deltas.
        results_history = state.get("results_history") or []
        axes_dict = state.get("axes") or {}
        target_op = "max"
        target_meta = state.get("target_metric") or {}
        if isinstance(target_meta, dict) and target_meta.get("op") in ("min", "max"):
            target_op = target_meta["op"]

        for d in iters:
            m = re.match(r"iter-(\d+)_(.+)", d.name)
            if not m:
                continue
            iter_num = int(m.group(1))
            candidate = m.group(2)
            body = _read_iter_summary(d)
            headline = _extract_headline(body)
            secondary = _extract_secondary_metric(body)
            figs = _iter_figures(d)
            metrics = _read_iter_metrics(d)
            op = (metrics or {}).get("op_points") or {}
            op_bullets = _format_op_points(op)
            iter_result = _result_for_iter(results_history, d.name)
            this_axes = (iter_result or {}).get("axes") or {}
            this_metric = (iter_result or {}).get("metric_value")
            phase_name = this_axes.get("phase")
            purpose = _PHASE_PURPOSES.get(phase_name, "") if phase_name else ""
            peer_str = _peer_comparison(results_history, axes_dict, this_axes,
                                         this_metric, target_op=target_op)

            parts.append("---")
            parts.append("")
            parts.append(f"## iter-{iter_num} — {_humanize(candidate)}")
            parts.append("")

            # Lede sentence: what this iter tests (the "why"). Pull from the
            # phase description, fall back to a generic sentence built from
            # the iter's axes.
            if purpose:
                parts.append(purpose)
                parts.append("")
            elif this_axes:
                axes_descr = ", ".join(
                    f"`{k}={v}`" for k, v in this_axes.items()
                )
                parts.append(f"Iteration with {axes_descr}.")
                parts.append("")

            # Body bullets: result + comparison + secondary metric + op_points.
            bullets = []
            if headline:
                bullets.append(f"- **Result** — {headline}")
            if secondary:
                bullets.append(f"- **Also** — {secondary}")
            if peer_str:
                bullets.append(f"- **Comparison** — {peer_str}")
            bullets.extend(op_bullets)  # operating-point bullets when available
            if bullets:
                parts.extend(bullets)
                parts.append("")

            if figs:
                fig = figs[0]
                try:
                    rel = fig.resolve().relative_to(session_root.resolve())
                except ValueError:
                    rel = fig
                parts.append(f"![{fig.stem}]({rel})")
                parts.append("")
            elif not bullets:
                parts.append("(no figure produced — see scorecard.xlsx)")
                parts.append("")

    # Conclusions section comes AFTER iter detail slides — gives the deck a
    # Background → Methods → Results (analytical + iters) → Conclusions
    # reading flow. (When findings.md is provided, this is empty.)
    parts.extend(post_iters_block)

    # No explicit closing slide — build-pptx auto-adds Thanks.
    return "\n".join(parts)


_AXIS_DESCRIPTIONS = {
    "phase":    "Evaluation lens applied to the model — different phases stress different aspects (per-site discrimination, OOD generalization, calibration, fairness, etc).",
    "cohort":   "Patient population scope — which sites/groups are included for training and evaluation.",
    "arch":     "Model architecture variant under test.",
    "backbone": "Backbone encoder family (e.g., ResNet, ViT, ConvNeXt).",
    "loss":     "Training loss formulation.",
    "lr":       "Learning rate scan range or specific values.",
    "head":     "Classifier head topology (linear, MLP, attention pooling).",
    "input":    "Input modality / sequence (T1, T2, audio, image, etc).",
    "split":    "Cross-validation split strategy.",
}


def _group_results_by_axis(results: list, axis: str) -> dict:
    """Bucket results_history entries by a single axis value (e.g. 'phase')."""
    buckets: dict = {}
    for r in (results or []):
        if r.get("status") != "complete":
            continue
        key = (r.get("axes") or {}).get(axis)
        if key is None:
            continue
        buckets.setdefault(key, []).append(r)
    return buckets


def _phase_summary_rows(results: list) -> list[tuple[str, str, str]]:
    """For sessions with phase × cohort axes, produce a per-phase summary
    matrix: [(phase, "metric @ 3site", "metric @ 5site"), ...]. Falls back
    cleanly when one of the axes is missing."""
    by_phase = _group_results_by_axis(results, "phase")
    if not by_phase:
        return []
    cohorts = sorted({(r.get("axes") or {}).get("cohort") for r in results
                      if (r.get("axes") or {}).get("cohort") is not None
                      and r.get("status") == "complete"})
    rows = []
    for phase, entries in by_phase.items():
        per_cohort = {(r.get("axes") or {}).get("cohort"): r.get("metric_value")
                      for r in entries}
        cells = []
        for c in cohorts:
            v = per_cohort.get(c)
            cells.append(f"{v:.4f}" if isinstance(v, (int, float)) else "—")
        rows.append((phase, cells, cohorts))
    return rows


def _render_auto_narrative(*, scope: str, pretty_scope: str, meta: dict,
                           state: dict, target_line: str,
                           session_root: Path) -> list[str]:
    """Auto-generate Background / Methods / Results / Conclusions sections
    when no findings.md is present. Returns a list of markdown lines.

    Each H2 content slide is structured as cards-grid (3-4 cards) or a
    multi-paragraph block — never a single sentence — so the rendered slide
    has visual + textual density.
    """
    iters = _iter_dirs(session_root)
    n_iters_total = len(iters)
    axes_dict = state.get("axes") or {}
    axes = _summarize_axes(axes_dict)
    n_candidates_planned = len(state.get("candidate_queue") or [])
    target_op = "max"
    target_meta = state.get("target_metric") or {}
    if isinstance(target_meta, dict) and target_meta.get("op") in ("min", "max"):
        target_op = target_meta["op"]
    results_history = state.get("results_history") or []
    top = _top_results(results_history, op=target_op, k=3)
    op_label = "highest" if target_op == "max" else "lowest"

    # Phase × cohort matrix when applicable (avoids the misleading
    # cross-metric "spread" calculation).
    phase_rows = _phase_summary_rows(results_history) if "phase" in axes_dict else []
    has_phase_grouping = bool(phase_rows) and len(axes_dict.get("phase") or []) > 1

    out: list[str] = []

    # ============================================================
    # # Background  — auto turquoise
    # ============================================================
    out += ["---", "", "# Background", ""]

    # ── ## Scope and motivation : cards-grid (4 cards) ──
    # Cards force visual structure even when the underlying content is
    # short. 4 short factual cards beat 2 dense sentences of plain prose.
    out += ["---", "", "## Scope and motivation", ""]
    if meta["scope_text"]:
        out += [meta["scope_text"], ""]
    elif state.get("axes_rationale"):
        out += [state["axes_rationale"], ""]
    out += ["### Scope", "",
            (meta["scope_text"] or pretty_scope), ""]
    out += ["### Iterations", "",
            f"{n_iters_total} runs · {n_candidates_planned} planned candidates", ""]
    if "cohort" in axes_dict:
        cohorts = ", ".join(str(c) for c in axes_dict["cohort"])
        out += ["### Cohorts", "", cohorts, ""]
    if "phase" in axes_dict:
        phases = ", ".join(str(p) for p in axes_dict["phase"])
        out += ["### Phases", "", phases, ""]
    out += ["### Output", "",
            "Per-iter `summary.md` + figures, `scorecard.xlsx` matrix, this deck.", ""]

    # ── ## Search target ──
    out += ["---", "", "## Search target", ""]
    if isinstance(target_meta, dict) and target_meta.get("metric"):
        out += [f"**Target** — `{target_op}imize {target_meta['metric']}`. "
                f"Each iteration writes a `summary.md` whose first metric "
                f"line is parsed, ranked, and persisted to `state.json`.", ""]
    else:
        out += [f"**Target** — {target_line}", "",
                "No single numeric target was set up-front. Each phase "
                "reports its own headline metric — AUC for discrimination "
                "phases, ECE for calibration, worst-stratum AUC for "
                "fairness — so cross-phase ranking is intentionally "
                "deferred to the per-phase results matrix below.", ""]
    if state.get("axes_rationale"):
        out += [state["axes_rationale"], ""]

    # ============================================================
    # # Methods  — auto deeppink
    # ============================================================
    out += ["---", "", "# Methods", ""]

    # ── ## Search axes  : cards-grid with descriptions ──
    if axes:
        out += ["---", "", "## Search axes", ""]
        out += [f"The session sweeps **{len(axes)} axes**: "
                f"{' × '.join('`' + n + '`' for n, _ in axes)}. "
                f"Cartesian product = {n_candidates_planned} candidates.", ""]
        for name, vals in axes:
            desc = _AXIS_DESCRIPTIONS.get(name, "Project-defined search dimension.")
            out += [f"### `{name}` — {vals}", "", desc, ""]
    else:
        out += ["---", "", "## Search structure", "",
                f"Single-track session with no branching axes. "
                f"{n_iters_total} iterations queued from project context.", ""]

    # ── ## Iteration loop ──
    out += ["---", "", "## Iteration loop", "",
            "Each candidate runs end-to-end as a separate process with "
            "stdout captured to `last-iteration.log`. Outputs land in "
            "`$AUTORESEARCH_OUT_RESULTS/{summary.md, metrics.json, "
            "fig_*.png}`; raw checkpoints in `$AUTORESEARCH_OUT_EXP/`.", "",
            "After each iteration the autoresearch skill parses the "
            "headline metric, records it in `state.json`, runs adaptive "
            "replanning over the remaining candidate queue, appends a "
            "block to the research-log entry, and schedules the next "
            "iteration. Failures route through a classifier (transient → "
            "retry, code_bug → stash + fix, infrastructure → halt-gate).", ""]

    # ============================================================
    # # Results  — auto amber
    # ============================================================
    # Always emit the # Results divider when we have iter dirs OR analytical
    # results. Per-iter detail slides emitted later by synthesize_deck_md
    # inherit this section context (and its amber accent).
    has_any_results = bool(top) or bool(phase_rows) or n_iters_total > 0
    if has_any_results:
        out += ["---", "", "# Results", ""]

        # ── ## Top candidates : table ──
        if top:
            out += ["---", "", "## Top candidates", "",
                    f"Top candidates by metric ({op_label} first). Each "
                    "row's metric is the headline value reported by the "
                    "iteration's `summary.md` — see iter detail slides for "
                    "bootstrap CIs and stratum-level breakdown.", "",
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

        # ── ## Phase × cohort matrix (when applicable) ──
        # Avoids the "spread across heterogeneous metrics" trap by showing
        # each phase as its own row with cohort-specific cells.
        if has_phase_grouping:
            cohorts = phase_rows[0][2]  # all phases share the same cohort columns
            out += ["---", "", "## Phase × cohort matrix", "",
                    f"Headline metric per phase × cohort. Metrics differ "
                    f"by phase — AUC for discrimination, ECE for "
                    f"calibration, worst-stratum AUC for stratified — so "
                    f"compare WITHIN a row, not across rows.", ""]
            header = "| Phase | " + " | ".join(cohorts) + " |"
            sep = "|---|" + "---:|" * len(cohorts)
            out += [header, sep]
            for phase, cells, _ in phase_rows:
                out.append(f"| `{phase}` | " + " | ".join(cells) + " |")
            out += [""]

    # ============================================================
    # # Conclusions  — auto turquoise
    # ============================================================
    if top:
        out += ["---", "", "# Conclusions", ""]

        # ── ## Best configuration : multi-paragraph ──
        best = top[0]
        out += ["---", "", "## Best configuration", ""]
        cand_id = best.get("id", "—")
        metric = best.get("metric_value")
        if isinstance(metric, (int, float)):
            out += [f"**`{cand_id}`** — headline metric **{metric:.4f}**.", ""]
        else:
            out += [f"**`{cand_id}`**.", ""]
        if len(top) >= 2:
            m1 = top[0].get("metric_value")
            m2 = top[1].get("metric_value")
            if isinstance(m1, (int, float)) and isinstance(m2, (int, float)):
                out += [f"The top two candidates differ by "
                        f"**{abs(m1 - m2):.4f}** — see `scorecard.xlsx` "
                        "for bootstrap CIs.", ""]
        out += ["See the iteration-detail section below for per-candidate "
                "ROC, calibration, and stratified figures. Per-phase "
                "context lives in the research-log entry; raw OOF "
                "predictions are saved as `oofs.npz` for replotting "
                "without retraining.", ""]

        # ── ## Recommendations : bullets ──
        out += ["---", "", "## Recommendations", ""]
        if len(top) >= 2:
            ru = ", ".join(f"`{r['id']}`" for r in top[1:])
            out += [f"- **Ship** `{cand_id}` for downstream evaluation.", ""]
            out += [f"- **Validate** on held-out data before locking it in "
                    "for deployment — the headline metric is from "
                    "in-distribution OOF, not external test.", ""]
            out += [f"- **Compare** against runners-up ({ru}) when "
                    "deployment tradeoffs (calibration, fairness, "
                    "interpretability, latency) matter beyond raw "
                    "discrimination.", ""]
        else:
            out += [f"- Treat `{cand_id}` as the working best.", ""]
            out += ["- Validate on held-out data before deployment.", ""]
        out += ["- **Document** open questions and follow-up axes in the "
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

    path_date = args.date.replace("-", "")
    session_root = Path("results") / f"{path_date}_{args.scope}"
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
