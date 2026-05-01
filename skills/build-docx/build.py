"""build-docx -- render a markdown file to a Jin-branded DOCX via pandoc.

Usage:
    python build.py --input doc.md --output doc.docx
    python build.py --input doc.md --output doc.docx --double-spaced --sections

Engine: pandoc (system-installed CLI). We pass --reference-doc=reference.docx
which contains all the branded styles. Pandoc applies them to the output.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent
REFERENCE_DOCX = SKILL_DIR / "reference.docx"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="markdown file to render")
    ap.add_argument("--output", required=True, help="output DOCX path")
    ap.add_argument("--double-spaced", dest="double_spaced", action="store_true",
                    help="2.0 line spacing for journal manuscripts")
    ap.add_argument("--sections", action="store_true",
                    help="number headings (1, 1.1, 1.1.1, ...)")
    ap.add_argument("--toc", action="store_true",
                    help="auto-generated TOC at start (right-click 'update field' in Word)")
    args = ap.parse_args()

    if not shutil.which("pandoc"):
        print("ERROR: pandoc not on PATH. Install via `brew install pandoc`.", file=sys.stderr)
        return 1
    if not REFERENCE_DOCX.is_file():
        print(f"ERROR: {REFERENCE_DOCX} missing. Run make_reference.py to generate.",
              file=sys.stderr)
        return 1

    cmd = [
        "pandoc",
        str(args.input),
        "-o", str(args.output),
        "--reference-doc", str(REFERENCE_DOCX),
        "--from", "markdown+yaml_metadata_block+smart",
        "--to", "docx",
    ]
    if args.toc:
        cmd.append("--toc")
    if args.sections:
        cmd.append("--number-sections")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"pandoc failed:\nSTDERR: {proc.stderr}\nSTDOUT: {proc.stdout}", file=sys.stderr)
        return proc.returncode

    if args.double_spaced:
        _apply_double_spacing(args.output)

    print(f"wrote {args.output}")
    return 0


def _apply_double_spacing(docx_path: str) -> None:
    """Override Normal paragraph spacing to 2.0 in the generated docx."""
    try:
        from docx import Document
    except ImportError:
        print("warning: python-docx not installed; --double-spaced no-op", file=sys.stderr)
        return
    doc = Document(docx_path)
    normal = doc.styles["Normal"]
    normal.paragraph_format.line_spacing = 2.0
    doc.save(docx_path)


if __name__ == "__main__":
    sys.exit(main())
