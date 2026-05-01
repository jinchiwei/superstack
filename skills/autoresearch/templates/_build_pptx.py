"""Build a session results pptx for an autoresearch session.

Reads:
  results/{date}_{scope}/README.md       - session header + candidate table
  results/{date}_{scope}/iter-*/summary.md - one slide per iteration

Writes:
  docs/runs/{date}_{scope}/SESSION_REPORT.pptx

Branding: Geist + Geist Mono with the standard palette
(turquoise / deeppink / amber #F0C840 / blueviolet). Widescreen 16:9.

Run:
    python docs/_build_pptx.py --date 2026-04-30 --scope fw-arch-sweep

Project-specific styling/layouts: extend or replace this template freely.
The autoresearch skill drops it in as a starting point on init-project.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt
except ImportError:
    raise SystemExit(
        "python-pptx not installed. Run: pip install python-pptx"
    )


# ----- Branding -----
TURQUOISE = RGBColor(0x40, 0xE0, 0xD0)
DEEPPINK = RGBColor(0xFF, 0x14, 0x93)
AMBER = RGBColor(0xF0, 0xC8, 0x40)
BLUEVIOLET = RGBColor(0x8A, 0x2B, 0xE2)
INK = RGBColor(0x11, 0x11, 0x11)
MUTED = RGBColor(0x55, 0x55, 0x55)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

MONO = "Geist Mono"
BODY = "Geist"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _set_bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_text(slide, text, *, left, top, width, height, size=18,
              color=INK, font=BODY, bold=False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.font.bold = bold
    return tb


def _title_slide(prs, *, scope, scope_text, date_str, target):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, WHITE)
    _add_text(s, "autoresearch session", left=0.7, top=2.2, width=12, height=0.5,
              size=14, color=MUTED, font=MONO)
    _add_text(s, scope, left=0.7, top=2.7, width=12, height=1.4,
              size=44, color=INK, font=BODY, bold=True)
    _add_text(s, scope_text, left=0.7, top=4.3, width=12, height=1.0,
              size=18, color=MUTED, font=BODY)
    _add_text(s, f"target: {target}", left=0.7, top=5.4, width=12, height=0.5,
              size=14, color=DEEPPINK, font=MONO)
    _add_text(s, date_str, left=0.7, top=6.7, width=12, height=0.4,
              size=12, color=MUTED, font=MONO)


def _candidate_slide(prs, *, iter_num, candidate, summary_text, results_dir):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, WHITE)
    _add_text(s, f"iter {iter_num:02d}", left=0.7, top=0.4, width=4, height=0.5,
              size=12, color=MUTED, font=MONO)
    _add_text(s, candidate, left=0.7, top=0.85, width=12, height=0.7,
              size=24, color=TURQUOISE, font=BODY, bold=True)
    body_lines = summary_text.strip().splitlines()
    body = "\n".join(body_lines[:30]) if body_lines else "(no summary)"
    _add_text(s, body, left=0.7, top=1.7, width=12, height=5.4,
              size=12, color=INK, font=MONO)
    _add_text(s, str(results_dir), left=0.7, top=7.0, width=12, height=0.3,
              size=9, color=MUTED, font=MONO, align=PP_ALIGN.LEFT)


def _summary_slide(prs, *, candidates):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, WHITE)
    _add_text(s, "summary", left=0.7, top=0.4, width=12, height=0.7,
              size=28, color=BLUEVIOLET, font=BODY, bold=True)
    rows = [f"{i+1:02d}. {c['candidate']}  ·  {c['status']}  ·  {c['metric']}"
            for i, c in enumerate(candidates)]
    body = "\n".join(rows) if rows else "(no completed iterations)"
    _add_text(s, body, left=0.7, top=1.4, width=12, height=5.6,
              size=14, color=INK, font=MONO)


def _read_session(date_str, scope):
    session_dir = Path("results") / f"{date_str}_{scope}"
    readme = session_dir / "README.md"
    if not readme.exists():
        raise SystemExit(f"no session at {session_dir}")
    text = readme.read_text()
    scope_text = re.search(r"\*\*Scope:\*\*\s*(.+)", text)
    target = re.search(r"\*\*Target metric:\*\*\s*(.+)", text)

    candidates = []
    for d in sorted(session_dir.glob("iter-*")):
        if not d.is_dir():
            continue
        m = re.match(r"iter-(\d+)_(.+)", d.name)
        if not m:
            continue
        iter_num = int(m.group(1))
        cand_slug = m.group(2)
        summary = d / "summary.md"
        body = summary.read_text() if summary.exists() else "(no summary.md)"
        # try to extract metric line
        metric_match = re.search(r"^\s*metric\s*[:|]\s*(.+)$", body, re.MULTILINE | re.IGNORECASE)
        status_match = re.search(r"^\s*status\s*[:|]\s*(.+)$", body, re.MULTILINE | re.IGNORECASE)
        candidates.append({
            "iter": iter_num,
            "candidate": cand_slug,
            "summary": body,
            "metric": metric_match.group(1).strip() if metric_match else "—",
            "status": status_match.group(1).strip() if status_match else "?",
            "dir": d,
        })

    return {
        "scope_text": scope_text.group(1).strip() if scope_text else scope,
        "target": target.group(1).strip() if target else "(unspecified)",
        "candidates": candidates,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                   help="Session date (YYYY-MM-DD).")
    p.add_argument("--scope", required=True, help="Session scope slug.")
    args = p.parse_args()

    session = _read_session(args.date, args.scope)
    out_dir = Path("docs") / "runs" / f"{args.date}_{args.scope}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "SESSION_REPORT.pptx"

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    _title_slide(prs, scope=args.scope, scope_text=session["scope_text"],
                 date_str=args.date, target=session["target"])
    for c in session["candidates"]:
        _candidate_slide(prs, iter_num=c["iter"], candidate=c["candidate"],
                         summary_text=c["summary"], results_dir=c["dir"])
    _summary_slide(prs, candidates=session["candidates"])

    prs.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
