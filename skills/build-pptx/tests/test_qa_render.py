import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import qa


def _soffice_available() -> bool:
    return qa.find_soffice() is not None and shutil.which("pdftoppm") is not None


@pytest.mark.skipif(not _soffice_available(),
                    reason="LibreOffice/poppler not installed")
def test_render_to_images_produces_one_png_per_slide(tmp_path):
    sys.path.insert(0, str(ROOT))
    import build  # noqa
    from render import render_from_plan
    from plan import Plan, SlideEntry

    md = tmp_path / "deck.md"
    md.write_text("---\ntitle: T\n---\n\n# A\n\ntext a\n", encoding="utf-8")
    plan = Plan(mode="strict", slides=[
        SlideEntry(slide_id="h1-a", kind="content-text",
                   params={"title": "A", "body": "text a"}),
    ])
    pptx = tmp_path / "deck.pptx"
    render_from_plan(md_path=md, plan=plan, output_path=pptx, theme=None)

    out_dir = tmp_path / "qa_images"
    pngs = qa.render_to_images(pptx, out_dir)
    assert len(pngs) >= 1
    assert all(p.suffix == ".png" and p.exists() for p in pngs)


def test_find_soffice_returns_path_or_none():
    result = qa.find_soffice()
    assert result is None or Path(result).exists()
