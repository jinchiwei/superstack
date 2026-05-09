"""Build a session results pdf for an autoresearch session.

Reads:
  results/{date}_{scope}/README.md
  results/{date}_{scope}/iter-*/summary.md

Writes:
  results/{date}_{scope}/SESSION_REPORT.pdf

Style: conservative, paper-like. Black body text on white. Brand-color accents
on H1 and section headings only. Geist for headings, Geist Mono for inline
code. Slugs humanized for display. No internal references — this is a
publication-style artifact.

Run:
    python docs/_build_pdf.py --date 2026-04-30 --scope fw-arch-sweep
"""
from __future__ import annotations

import argparse
import html as html_mod
import re
from datetime import datetime
from pathlib import Path

try:
    import markdown
    from weasyprint import CSS, HTML
except ImportError:
    raise SystemExit("weasyprint + markdown not installed. Run: pip install weasyprint markdown")


CSS_TEMPLATE = """
@page { size: Letter; margin: 0.85in 0.95in; @bottom-center { content: counter(page); font-family: 'Geist Mono', monospace; font-size: 8pt; color: #888; } }
* { box-sizing: border-box; }
html, body {
  font-family: 'Geist', -apple-system, system-ui, sans-serif;
  color: #111; font-size: 10.5pt; line-height: 1.55;
}

.eyebrow {
  font-family: 'Geist Mono', monospace;
  font-size: 9pt; color: #6B6B73; font-weight: 700;
  letter-spacing: 0.08em; margin: 0 0 4pt 0;
}
h1.title {
  font-family: 'Geist', sans-serif;
  font-size: 26pt; font-weight: 700; color: #40E0D0;
  margin: 0 0 6pt 0;
}
.scope-text { color: #14141C; font-size: 11pt; margin: 0 0 6pt 0; }
.target {
  font-family: 'Geist Mono', monospace; font-size: 9.5pt;
  margin: 0 0 4pt 0;
}
.target .label { color: #6B6B73; font-weight: 700; }
.target .value { color: #8A2BE2; font-weight: 700; }
.date {
  font-family: 'Geist Mono', monospace; font-size: 9pt; color: #6B6B73;
  margin: 0 0 18pt 0;
}
hr.rule { border: none; border-top: 0.5pt solid #DDDDDD; margin: 14pt 0; }

h2.section {
  font-family: 'Geist', sans-serif; font-size: 14pt; font-weight: 700;
  color: #FF1493; margin: 20pt 0 8pt 0;
  bookmark-level: 1; bookmark-label: content(text);
}

.iter-block { margin: 10pt 0 18pt 0; page-break-inside: avoid; }
.iter-block .candidate {
  font-family: 'Geist', sans-serif; font-size: 12pt; font-weight: 700;
  color: #14141C; margin: 0 0 2pt 0;
  bookmark-level: 2; bookmark-label: content(text);
}
.iter-block .meta {
  font-family: 'Geist Mono', monospace; font-size: 9pt;
  margin: 0 0 6pt 0; color: #14141C;
}
.iter-block .meta .label { color: #6B6B73; font-weight: 700; }
.iter-block .meta .metric { color: #8A2BE2; font-weight: 700; }
.iter-block pre {
  font-family: 'Geist Mono', monospace; font-size: 9pt; color: #14141C;
  background: #FAFAFC; border-left: 2pt solid #E5E5EA;
  padding: 6pt 10pt; margin: 4pt 0;
  white-space: pre-wrap; word-wrap: break-word;
}

.iter-block .body { font-size: 10pt; line-height: 1.5; }
.iter-block .body h1, .iter-block .body h2, .iter-block .body h3 {
  font-family: 'Geist', sans-serif; color: #14141C; font-weight: 700;
  margin: 8pt 0 4pt 0;
}
.iter-block .body h2 { font-size: 11pt; color: #6B6B73; letter-spacing: 0.04em; }
.iter-block .body h3 { font-size: 10pt; color: #6B6B73; }
.iter-block .body p { margin: 4pt 0; }
.iter-block .body strong { color: #14141C; }
.iter-block .body code {
  font-family: 'Geist Mono', monospace; font-size: 9pt;
  background: #F5F5F8; padding: 1pt 4pt; border-radius: 2pt;
}
.iter-block .body table {
  width: 100%; border-collapse: collapse; margin: 6pt 0;
  font-family: 'Geist Mono', monospace; font-size: 9pt;
  page-break-inside: avoid;
}
.iter-block .body table th {
  text-align: left; padding: 4pt 6pt;
  border-bottom: 1pt solid #14141C;
  color: #6B6B73; font-weight: 700;
}
.iter-block .body table td {
  padding: 3pt 6pt; border-bottom: 0.5pt solid #EEEEF2;
  color: #14141C;
}
.iter-block figure {
  margin: 8pt 0; page-break-inside: avoid; text-align: center;
}
.iter-block figure img {
  max-width: 100%; max-height: 4.5in; height: auto;
  border: 0.5pt solid #E5E5EA;
}
.iter-block figure figcaption {
  font-family: 'Geist Mono', monospace; font-size: 8pt;
  color: #6B6B73; margin-top: 3pt;
}

table.results {
  width: 100%; border-collapse: collapse; margin-top: 10pt;
  font-family: 'Geist Mono', monospace; font-size: 9pt;
}
table.results th {
  text-align: left; padding: 6pt 8pt;
  border-bottom: 1pt solid #14141C;
  color: #6B6B73; font-weight: 700;
  letter-spacing: 0.04em;
}
table.results td {
  padding: 5pt 8pt; border-bottom: 0.5pt solid #EEEEF2;
  color: #14141C;
}
table.results td.iter { color: #6B6B73; font-weight: 700; }
table.results td.candidate { font-family: 'Geist', sans-serif; font-size: 10pt; }
table.results td.metric { color: #8A2BE2; font-weight: 700; }
"""


def _humanize(slug: str) -> str:
    if not slug:
        return ""
    slug = re.sub(r"^iter-\d+_", "", slug)
    parts = re.split(r"[-_]+", slug)
    return " ".join(p[:1].upper() + p[1:] if p else "" for p in parts).strip()


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
        body = summary.read_text() if summary.exists() else ""
        metric_m = re.search(r"^\s*metric\s*[:|]\s*(.+)$", body, re.MULTILINE | re.IGNORECASE)
        status_m = re.search(r"^\s*status\s*[:|]\s*(.+)$", body, re.MULTILINE | re.IGNORECASE)
        figs = sorted(d.glob("fig_*.png"))
        candidates.append({
            "iter": int(m.group(1)),
            "candidate": m.group(2),
            "summary": body,
            "metric": metric_m.group(1).strip() if metric_m else "—",
            "status": status_m.group(1).strip() if status_m else "—",
            "figures": figs,
        })

    return {
        "scope_text": scope_text_m.group(1).strip() if scope_text_m else _humanize(scope),
        "target": target_m.group(1).strip() if target_m else "",
        "candidates": candidates,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--scope", required=True)
    args = p.parse_args()

    path_date = args.date.replace("-", "")
    s = _read_session(path_date, args.scope)
    out_dir = Path("results") / f"{path_date}_{args.scope}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "SESSION_REPORT.pdf"

    parts = ["<html><body>"]
    parts.append('<p class="eyebrow">RESEARCH SESSION</p>')
    parts.append(f'<h1 class="title">{html_mod.escape(_humanize(args.scope))}</h1>')
    parts.append(f'<p class="scope-text">{html_mod.escape(s["scope_text"])}</p>')
    if s["target"]:
        parts.append(
            f'<p class="target"><span class="label">Target —</span> '
            f'<span class="value">{html_mod.escape(s["target"])}</span></p>'
        )
    parts.append(f'<p class="date">{html_mod.escape(args.date)}</p>')
    parts.append('<hr class="rule" />')

    parts.append('<h2 class="section">Iterations</h2>')
    for c in s["candidates"]:
        parts.append('<div class="iter-block">')
        parts.append(f'<p class="candidate">{html_mod.escape(_humanize(c["candidate"]))}</p>')
        parts.append(
            f'<p class="meta">'
            f'<span class="label">Status</span> {html_mod.escape(c["status"])}'
            f'&nbsp;&nbsp;&nbsp;<span class="label">Metric</span> '
            f'<span class="metric">{html_mod.escape(str(c["metric"]))}</span>'
            f'</p>'
        )
        body_text = (c["summary"] or "").strip()
        if body_text:
            # Render the iter summary as proper markdown (tables, headings,
            # inline code) instead of dumping a raw <pre>. Strip the leading
            # h1 since the iter-block already shows the candidate name.
            stripped = re.sub(r"\A#\s+[^\n]*\n+", "", body_text)
            html = markdown.markdown(stripped, extensions=["tables", "fenced_code"])
            parts.append(f'<div class="body">{html}</div>')
        for fig in c.get("figures", []):
            # Use absolute path so weasyprint resolves the image regardless of
            # cwd at render time.
            parts.append(
                f'<figure>'
                f'<img src="file://{fig.resolve()}" alt="{html_mod.escape(fig.stem)}" />'
                f'<figcaption>{html_mod.escape(fig.stem)}</figcaption>'
                f'</figure>'
            )
        parts.append('</div>')

    if s["candidates"]:
        parts.append('<hr class="rule" />')
        parts.append('<h2 class="section">Results</h2>')
        parts.append('<table class="results">')
        parts.append('<tr><th>ITER</th><th>CANDIDATE</th><th>STATUS</th><th>METRIC</th></tr>')
        for c in s["candidates"]:
            parts.append(
                '<tr>'
                f'<td class="iter">{c["iter"]:02d}</td>'
                f'<td class="candidate">{html_mod.escape(_humanize(c["candidate"]))}</td>'
                f'<td>{html_mod.escape(c["status"])}</td>'
                f'<td class="metric">{html_mod.escape(str(c["metric"]))}</td>'
                '</tr>'
            )
        parts.append('</table>')

    parts.append("</body></html>")
    html_str = "\n".join(parts)

    HTML(string=html_str).write_pdf(out, stylesheets=[CSS(string=CSS_TEMPLATE)])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
