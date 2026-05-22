"""qa.py — render a built .pptx to per-slide PNGs for visual inspection.

Pipeline: pptx --(LibreOffice headless)--> pdf --(poppler pdftoppm)--> png[].
The agent driving the QA loop calls render_to_images(), then visually
inspects each PNG against the design anti-patterns in plan_prompt.md, edits
the sidecar to fix issues, and re-renders.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "soffice",
    "libreoffice",
]


def find_soffice() -> str | None:
    """Return a usable soffice executable path, or None if not installed."""
    for cand in _SOFFICE_CANDIDATES:
        if cand.startswith("/"):
            if Path(cand).exists():
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def render_to_images(pptx_path: Path, out_dir: Path, *, dpi: int = 120) -> list[Path]:
    """Convert a .pptx to one PNG per slide in out_dir. Returns sorted paths.

    Raises RuntimeError with an actionable message if soffice is missing.
    """
    pptx_path = Path(pptx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # The QA loop reuses this dir across re-renders; clear prior outputs so a
    # render with fewer slides doesn't leave stale PNGs in the result.
    for old in out_dir.glob("slide-*.png"):
        old.unlink()
    (out_dir / (pptx_path.stem + ".pdf")).unlink(missing_ok=True)

    soffice = find_soffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice (soffice) not found. Install with "
            "`brew install --cask libreoffice`. pdftoppm (poppler) is also "
            "required: `brew install poppler`."
        )
    if not shutil.which("pdftoppm"):
        raise RuntimeError(
            "pdftoppm not found. Install poppler: `brew install poppler`."
        )

    # 1) pptx -> pdf
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir",
             str(out_dir), str(pptx_path)],
            check=True, capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"LibreOffice timed out converting {pptx_path.name} (>180s)")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice failed to convert {pptx_path.name}:\n{e.stderr}")
    pdf_path = out_dir / (pptx_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"LibreOffice did not produce {pdf_path}")

    # 2) pdf -> png per page
    prefix = out_dir / "slide"
    try:
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
            check=True, capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"pdftoppm timed out rasterizing {pdf_path.name} (>180s)")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"pdftoppm failed to rasterize {pdf_path.name}:\n{e.stderr}")
    return sorted(out_dir.glob("slide-*.png"))
