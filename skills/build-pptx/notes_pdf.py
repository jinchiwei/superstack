"""Canonical presenter-handout PDF: each slide's image + its full speaker notes.

One landscape page per slide — slide thumbnail on top (so every figure/image on
the slide is included automatically), comprehensive notes below. Notes are read
from the rendered pptx's notes panes (populated by render.py from params['notes']),
so this stays in sync with the deck. Rasterization reuses qa.render_to_images
(LibreOffice + pdftoppm); if those are missing it degrades gracefully (returns
None) rather than failing the build.
"""
from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path


def _wrap(text: str, width: int = 116) -> str:
    out = []
    for para in (text or "").split("\n"):
        if not para.strip():
            out.append("")
            continue
        out.extend(textwrap.wrap(para, width=width) or [""])
    return "\n".join(out)


def build_notes_pdf(pptx_path, out_pdf=None, *, dpi: int = 130):
    """Build `<deck>_notes.pdf`. Returns the Path, or None if it couldn't run
    (e.g. no LibreOffice/pdftoppm, or the deck has no notes)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from PIL import Image
    from pptx import Presentation

    from qa import render_to_images

    pptx_path = Path(pptx_path)
    out_pdf = Path(out_pdf) if out_pdf else pptx_path.with_name(pptx_path.stem + "_notes.pdf")

    prs = Presentation(str(pptx_path))
    notes = []
    for s in prs.slides:
        t = ""
        if s.has_notes_slide:
            t = s.notes_slide.notes_text_frame.text or ""
        notes.append(t)
    if not any(n.strip() for n in notes):
        return None  # nothing to hand out

    with tempfile.TemporaryDirectory() as td:
        try:
            pngs = render_to_images(pptx_path, Path(td), dpi=dpi)
        except RuntimeError:
            return None  # no rasterizer — skip gracefully

        # Brand fonts if available (harmless fallback otherwise).
        try:
            import sys as _sys
            _sys.path.insert(0, "/home/jiwei/arcadia/superstack/skills/_shared")
            from mpl_style import FONT_BODY, FONT_TITLE
        except Exception:
            FONT_BODY, FONT_TITLE = ["DejaVu Sans"], ["DejaVu Sans Mono"]

        n = min(len(pngs), len(notes))
        with PdfPages(str(out_pdf)) as pdf:
            for i in range(n):
                note = notes[i].strip()
                lines = note.split("\n", 1)
                head = lines[0] if lines else f"Slide {i + 1}"
                body = lines[1].strip() if len(lines) > 1 else ""

                fig = plt.figure(figsize=(11, 8.5))  # landscape letter
                fig.patch.set_facecolor("white")

                # slide image — top 56%
                ax_img = fig.add_axes([0.04, 0.46, 0.92, 0.50])
                ax_img.axis("off")
                try:
                    ax_img.imshow(Image.open(pngs[i]))
                except Exception:
                    pass

                # header + notes — bottom
                fig.text(0.04, 0.40, f"Slide {i + 1} — {head}", ha="left", va="top",
                         fontsize=13, fontfamily=FONT_TITLE, fontweight="bold", color="#1A1A1A")
                fig.text(0.04, 0.355, _wrap(body), ha="left", va="top",
                         fontsize=10.5, fontfamily=FONT_BODY, color="#1A1A1A",
                         linespacing=1.45)
                pdf.savefig(fig, facecolor="white")
                plt.close(fig)

    return out_pdf


if __name__ == "__main__":
    import sys
    p = build_notes_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"wrote {p}" if p else "notes PDF skipped (no notes or no rasterizer)")
