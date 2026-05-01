"""Build a session results pdf for an autoresearch session.

Reads:
  results/{date}_{scope}/README.md
  results/{date}_{scope}/iter-*/summary.md

Writes:
  docs/runs/{date}_{scope}/SESSION_REPORT.pdf

Branding: Geist + Geist Mono with the standard palette.
Uses weasyprint (markdown -> HTML -> PDF) so styling stays in CSS.

Run:
    python docs/_build_pdf.py --date 2026-04-30 --scope fw-arch-sweep
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

try:
    import markdown
    from weasyprint import CSS, HTML
except ImportError:
    raise SystemExit(
        "weasyprint + markdown not installed. Run: pip install weasyprint markdown"
    )


CSS_TEMPLATE = """
@page { size: Letter; margin: 0.75in 0.85in; }
* { box-sizing: border-box; }
html, body {
  font-family: 'Geist', -apple-system, system-ui, sans-serif;
  color: #111; font-size: 10.5pt; line-height: 1.5;
}
h1 { font-family: 'Geist', sans-serif; font-size: 26pt; font-weight: 700; color: #111; margin: 0 0 4pt 0; }
h2 { font-family: 'Geist', sans-serif; font-size: 14pt; font-weight: 700; color: #40E0D0; margin: 18pt 0 4pt 0; }
h3 { font-family: 'Geist Mono', monospace; font-size: 10pt; color: #555; margin: 12pt 0 2pt 0; font-weight: 600; }
p { margin: 4pt 0; }
.scope-text { color: #555; font-size: 11pt; }
.target { color: #FF1493; font-family: 'Geist Mono', monospace; font-size: 9.5pt; }
.date { color: #555; font-family: 'Geist Mono', monospace; font-size: 9pt; }
.summary { color: #8A2BE2; font-size: 14pt; font-weight: 700; margin-top: 24pt; }
pre, code { font-family: 'Geist Mono', monospace; font-size: 9pt; color: #111; }
.iter-block { margin: 8pt 0 18pt 0; }
.iter-path { font-family: 'Geist Mono', monospace; font-size: 7.5pt; color: #888; }
"""


def _read_session(date_str, scope):
    session_dir = Path("results") / f"{date_str}_{scope}"
    readme = session_dir / "README.md"
    if not readme.exists():
        raise SystemExit(f"no session at {session_dir}")
    text = readme.read_text()
    scope_text_m = re.search(r"\*\*Scope:\*\*\s*(.+)", text)
    target_m = re.search(r"\*\*Target metric:\*\*\s*(.+)", text)

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
        "scope_text": scope_text_m.group(1).strip() if scope_text_m else scope,
        "target": target_m.group(1).strip() if target_m else "(unspecified)",
        "candidates": candidates,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--scope", required=True)
    args = p.parse_args()

    s = _read_session(args.date, args.scope)
    out_dir = Path("docs") / "runs" / f"{args.date}_{args.scope}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "SESSION_REPORT.pdf"

    parts = [
        f"# {args.scope}",
        f"<p class='scope-text'>{s['scope_text']}</p>",
        f"<p class='target'>target: {s['target']}</p>",
        f"<p class='date'>date: {args.date}</p>",
    ]
    for c in s["candidates"]:
        parts.append(f"<div class='iter-block'>")
        parts.append(f"<h3>iter {c['iter']:02d}</h3>")
        parts.append(f"<h2>{c['candidate']}</h2>")
        parts.append(markdown.markdown(c["summary"]))
        parts.append(f"<p class='iter-path'>{c['dir']}</p>")
        parts.append("</div>")
    parts.append(f"<h2 class='summary'>summary</h2>")
    parts.append("<ul>")
    for c in s["candidates"]:
        parts.append(f"<li><code>{c['iter']:02d}. {c['candidate']}</code> — <span class='iter-path'>{c['dir']}</span></li>")
    parts.append("</ul>")
    html = "<html><body>" + "\n".join(parts) + "</body></html>"

    HTML(string=html).write_pdf(out, stylesheets=[CSS(string=CSS_TEMPLATE)])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
