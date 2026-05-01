"""Build a session results docx for an autoresearch session.

Reads:
  results/{date}_{scope}/README.md
  results/{date}_{scope}/iter-*/summary.md

Writes:
  docs/runs/{date}_{scope}/SESSION_REPORT.docx

Branding: Geist + Geist Mono with the standard palette.

Run:
    python docs/_build_docx.py --date 2026-04-30 --scope fw-arch-sweep
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    raise SystemExit(
        "python-docx not installed. Run: pip install python-docx"
    )


TURQUOISE = RGBColor(0x40, 0xE0, 0xD0)
DEEPPINK = RGBColor(0xFF, 0x14, 0x93)
BLUEVIOLET = RGBColor(0x8A, 0x2B, 0xE2)
INK = RGBColor(0x11, 0x11, 0x11)
MUTED = RGBColor(0x55, 0x55, 0x55)

MONO = "Geist Mono"
BODY = "Geist"


def _styled(p, text, *, font=BODY, size=11, color=INK, bold=False):
    r = p.add_run(text)
    r.font.name = font
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.bold = bold
    return r


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
        summary = d / "summary.md"
        body = summary.read_text() if summary.exists() else "(no summary.md)"
        candidates.append({
            "iter": int(m.group(1)),
            "candidate": m.group(2),
            "summary": body,
            "dir": d,
        })

    return {
        "scope_text": scope_text.group(1).strip() if scope_text else scope,
        "target": target.group(1).strip() if target else "(unspecified)",
        "candidates": candidates,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--scope", required=True)
    args = p.parse_args()

    session = _read_session(args.date, args.scope)
    out_dir = Path("docs") / "runs" / f"{args.date}_{args.scope}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "SESSION_REPORT.docx"

    doc = Document()

    # Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _styled(title, "autoresearch session", font=MONO, size=10, color=MUTED)
    title2 = doc.add_paragraph()
    _styled(title2, args.scope, font=BODY, size=28, color=INK, bold=True)

    meta = doc.add_paragraph()
    _styled(meta, session["scope_text"] + "\n", font=BODY, size=11, color=MUTED)
    _styled(meta, f"target: {session['target']}\n", font=MONO, size=10, color=DEEPPINK)
    _styled(meta, f"date: {args.date}", font=MONO, size=10, color=MUTED)

    doc.add_paragraph()

    # Per-candidate sections
    for c in session["candidates"]:
        h = doc.add_paragraph()
        _styled(h, f"iter {c['iter']:02d}  ·  ", font=MONO, size=11, color=MUTED)
        _styled(h, c["candidate"], font=BODY, size=14, color=TURQUOISE, bold=True)
        body = doc.add_paragraph()
        _styled(body, c["summary"], font=MONO, size=10, color=INK)
        path = doc.add_paragraph()
        _styled(path, str(c["dir"]), font=MONO, size=8, color=MUTED)
        doc.add_paragraph()

    # Summary
    h = doc.add_paragraph()
    _styled(h, "summary", font=BODY, size=18, color=BLUEVIOLET, bold=True)
    for c in session["candidates"]:
        line = doc.add_paragraph()
        _styled(line, f"  {c['iter']:02d}. {c['candidate']} — {c['dir']}",
                font=MONO, size=10, color=INK)

    doc.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
