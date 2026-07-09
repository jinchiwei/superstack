"""Runtime proportion QA — walks the rendered pptx and flags slides where
the chosen layout proportions probably don't match the slide's content.

What this catches:
- Figure-primary slides where the picture takes too small a share of the
  slide area (the cost is wasted content space; reader has to squint at the
  data). Triggered when a slide has a picture + bespoke aside card and the
  picture occupies < 0.45 of the chrome-adjusted content area.
- Aside cards consuming too much width when paired with a figure (> 0.45 of
  slide width). Implies the figure could be widened.
- Text widgets where the run-content character count cannot plausibly fit
  in the widget's geometric area at its font size (estimated line count
  exceeds the widget's height).

Does NOT prescribe a layout — only flags measurable mismatches between
chosen proportions and the content. The bespoke author still decides what
the slide looks like.

Same wire-in pattern as contrast_check.py: invoked from build.py after
rendering, emits non-fatal stderr warnings.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


# Standard 16:9 slide in EMU
EMU_PER_INCH = 914400
DEFAULT_SLIDE_W = 12192000  # 13.333"
DEFAULT_SLIDE_H = 6858000   # 7.5"

# Chrome margins eat from the slide perimeter — body content sits inside.
# Match build-pptx's _add_chrome defaults.
CHROME_TOP_FRAC = 0.18      # title band
CHROME_BOTTOM_FRAC = 0.07   # footer band
CHROME_SIDE_FRAC = 0.035    # left/right margins

# Thresholds — tunable. Heuristics tuned against the AGF deck slides.
FIGURE_PRIMARY_MIN_FRAC = 0.45   # picture-occupies-content-area threshold
ASIDE_TOO_WIDE_FRAC = 0.45       # aside card width / slide width
TEXT_OVERFLOW_LINE_BUDGET = 1.15  # estimated lines / capacity allowed before warning

# Approximate average character widths (in EMU) at common font sizes.
# Calibrated against Geist Mono + Geist Sans at typical run densities.
def _est_char_width_emu(font_pt: float) -> int:
    # Empirical: ~0.55 * font_pt * 12700 (12700 EMU = 1 pt) for sans body
    return int(0.55 * font_pt * 12700)


def _est_line_height_emu(font_pt: float) -> int:
    # Default line spacing ~1.2× font size
    return int(1.2 * font_pt * 12700)


@dataclass
class ProportionIssue:
    slide_id: int
    kind: str  # "figure_compressed" | "aside_too_wide" | "text_overflow"
    detail: str
    suggestion: str


# ---------------------------------------------------------------------------
# pptx XML parsing helpers
# ---------------------------------------------------------------------------

_XFRM_RE = re.compile(
    r'<a:xfrm[^>]*>\s*<a:off\s+x="(\d+)"\s+y="(\d+)"\s*/>\s*'
    r'<a:ext\s+cx="(\d+)"\s+cy="(\d+)"\s*/>',
    re.S,
)


def _slide_size(zf: zipfile.ZipFile) -> tuple[int, int]:
    try:
        pres = zf.read("ppt/presentation.xml").decode("utf-8", errors="ignore")
        m = re.search(r'<p:sldSz\s+cx="(\d+)"\s+cy="(\d+)"', pres)
        if m:
            return int(m.group(1)), int(m.group(2))
    except KeyError:
        pass
    return DEFAULT_SLIDE_W, DEFAULT_SLIDE_H


def _xfrm_at(start_pos: int, xml: str) -> tuple[int, int, int, int] | None:
    """Find the first <a:xfrm> with off+ext after start_pos. Returns (x,y,cx,cy)."""
    m = _XFRM_RE.search(xml, pos=start_pos)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))


def _iter_shapes(xml: str):
    """Yield (kind, x, y, cx, cy, content_text) per top-level shape/picture.

    kind in {"sp", "pic"}; content_text is concatenated <a:t> runs for "sp".
    """
    # Walk <p:sp>...</p:sp> and <p:pic>...</p:pic> ranges
    for tag_open, tag_close, kind in [
        (r"<p:sp\b", r"</p:sp>", "sp"),
        (r"<p:pic\b", r"</p:pic>", "pic"),
    ]:
        for m in re.finditer(tag_open, xml):
            close = xml.find(tag_close[2:], m.end())
            if close == -1:
                continue
            block = xml[m.start():close]
            xfrm = _xfrm_at(0, block)
            if not xfrm:
                continue
            # Skip background rect (covers the whole slide) — that's chrome paint
            x, y, cx, cy = xfrm
            text = ""
            if kind == "sp":
                # Collect all <a:t> runs
                runs = re.findall(r"<a:t>([^<]*)</a:t>", block)
                text = " ".join(runs).strip()
                # Also extract font size (max across runs) for density estimate
                sizes = [int(s) / 100.0 for s in re.findall(r'sz="(\d+)"', block)]
                font_pt = max(sizes) if sizes else 11.0
                yield (kind, x, y, cx, cy, text, font_pt)
            else:
                yield (kind, x, y, cx, cy, "", 0.0)


def _slide_xml_files(zf: zipfile.ZipFile) -> list[tuple[int, str]]:
    out = []
    for name in zf.namelist():
        m = re.match(r"ppt/slides/slide(\d+)\.xml$", name)
        if m:
            xml = zf.read(name).decode("utf-8", errors="ignore")
            out.append((int(m.group(1)), xml))
    out.sort()
    return out


# ---------------------------------------------------------------------------
# Per-slide checks
# ---------------------------------------------------------------------------

def _content_area(slide_w: int, slide_h: int) -> tuple[int, int, int, int]:
    """Chrome-adjusted content rectangle (x, y, w, h)."""
    cx = int(CHROME_SIDE_FRAC * slide_w)
    cy = int(CHROME_TOP_FRAC * slide_h)
    cw = slide_w - 2 * cx
    ch = int(slide_h - cy - CHROME_BOTTOM_FRAC * slide_h)
    return cx, cy, cw, ch


def _check_figure_compressed(slide_id, shapes, slide_w, slide_h) -> ProportionIssue | None:
    pics = [s for s in shapes if s[0] == "pic"]
    if not pics:
        return None
    cx_, cy_, cw, ch = _content_area(slide_w, slide_h)
    content_area = cw * ch
    biggest = max(pics, key=lambda s: s[3] * s[4])
    pic_area = biggest[3] * biggest[4]
    frac = pic_area / content_area
    if frac >= FIGURE_PRIMARY_MIN_FRAC:
        return None
    # Only flag when there's a SAME-ROW aside card hogging > 0.30 of slide width.
    # Vertical "figure-top + cards-below" layouts are an intentional alternative
    # to figure-aside and shouldn't trip this check.
    pic_y = biggest[2]
    pic_height = biggest[4]
    pic_v_center = pic_y + pic_height // 2
    asides_same_row = [
        s for s in shapes
        if s[0] == "sp" and s[5] and len(s[5]) > 40
        and s[3] > 0.30 * slide_w
        # Geometric vertical overlap with the picture (its center sits within
        # the picture's vertical band, or vice versa)
        and (pic_y <= s[2] + s[4] // 2 <= pic_y + pic_height
             or s[2] <= pic_v_center <= s[2] + s[4])
    ]
    if not asides_same_row:
        return None
    widest_aside = max(asides_same_row, key=lambda s: s[3])
    return ProportionIssue(
        slide_id=slide_id,
        kind="figure_compressed",
        detail=(
            f"picture occupies {frac:.2f} of content area, "
            f"same-row aside card is {widest_aside[3]/slide_w:.2f} wide "
            f"({widest_aside[3]/EMU_PER_INCH:.1f}\")"
        ),
        suggestion=(
            "consider shrinking the aside or switching to figure-top + "
            "content-row-below"
        ),
    )


def _check_figure_top_compressed(slide_id, shapes, slide_w, slide_h) -> ProportionIssue | None:
    """Figure-top + cards-below layouts where the figure is vertically squished.

    Catches the case where the slide is laid out vertically (figure spans most
    of the width, content cards below it) but the figure was given < 0.55 of
    body height — squishing it relative to its natural aspect ratio.
    """
    pics = [s for s in shapes if s[0] == "pic"]
    if not pics:
        return None
    biggest = max(pics, key=lambda s: s[3] * s[4])
    _, py, pw, ph = biggest[1], biggest[2], biggest[3], biggest[4]
    # Must be (a) wide (≥ 80% of slide width) and (b) in the upper half
    if pw < 0.80 * slide_w:
        return None
    if py > 0.40 * slide_h:
        return None
    # Must have substantial content (text cards) below the picture
    pic_bottom = py + ph
    below_shapes = [
        s for s in shapes
        if s[0] == "sp" and s[2] >= pic_bottom - 200000
        and s[5] and len(s[5]) > 30
        and s[3] * s[4] > 0.03 * slide_w * slide_h  # non-trivial area
    ]
    if not below_shapes:
        return None
    # Body height available after chrome
    _, _, _, body_h = _content_area(slide_w, slide_h)
    fig_frac_of_body = ph / body_h
    if fig_frac_of_body >= 0.55:
        return None
    return ProportionIssue(
        slide_id=slide_id,
        kind="figure_top_compressed",
        detail=(
            f"figure-top layout, figure height = {fig_frac_of_body:.2f} of body "
            f"({ph/EMU_PER_INCH:.1f}\" tall) with {len(below_shapes)} card(s) below"
        ),
        suggestion=(
            "consider raising fig_h to ~0.65-0.72 of body so the figure isn't "
            "vertically squished; shrink card row to compensate"
        ),
    )


def _check_aside_too_wide(slide_id, shapes, slide_w) -> ProportionIssue | None:
    pics = [s for s in shapes if s[0] == "pic"]
    if not pics:
        return None
    # Aside card heuristic: filled shape that is positioned to the RIGHT of the
    # largest picture and has substantial body text
    biggest_pic = max(pics, key=lambda s: s[3] * s[4])
    pic_right = biggest_pic[1] + biggest_pic[3]
    asides = [
        s for s in shapes
        if s[0] == "sp" and s[1] >= pic_right - 100000  # to the right of figure
        and s[5] and len(s[5]) > 60
        and s[3] > 0.20 * slide_w
    ]
    if not asides:
        return None
    widest = max(asides, key=lambda s: s[3])
    frac = widest[3] / slide_w
    if frac < ASIDE_TOO_WIDE_FRAC:
        return None
    return ProportionIssue(
        slide_id=slide_id,
        kind="aside_too_wide",
        detail=f"aside card width = {frac:.2f} of slide ({widest[3]/EMU_PER_INCH:.1f}\")",
        suggestion=(
            f"consider shrinking aside to ~0.30 of slide width "
            f"(currently {frac:.2f}) so the figure can grow"
        ),
    )


def _check_text_overflow(slide_id, shapes) -> list[ProportionIssue]:
    """Estimate whether widget text content actually fits its geometry.

    Important: long text (>=80 chars) inside a tiny widget is exactly the
    overflow case we want to flag — don't skip small widgets when the text
    is substantial. Only skip narrow widgets (likely labels) where we'd
    have noisy estimates.
    """
    issues = []
    for kind, x, y, cx, cy, text, font_pt in shapes:
        if kind != "sp" or not text or len(text) < 80:
            continue
        # Only skip if widget is narrow (label-like). Tiny height with long
        # text IS the overflow signal — never skip on cy.
        if cx < 1500000:  # < 1.6"
            continue
        char_w = _est_char_width_emu(font_pt)
        line_h = _est_line_height_emu(font_pt)
        chars_per_line = max(1, cx // char_w)
        capacity_lines = max(1, cy // line_h) if cy > line_h else 0
        n_chars = int(len(text) * 1.05)  # whitespace slack
        est_lines = (n_chars + chars_per_line - 1) // chars_per_line
        if capacity_lines == 0 or est_lines > capacity_lines * TEXT_OVERFLOW_LINE_BUDGET:
            cap_str = "0" if capacity_lines == 0 else str(int(capacity_lines))
            issues.append(ProportionIssue(
                slide_id=slide_id,
                kind="text_overflow",
                detail=(
                    f"text widget ~{len(text)} chars @ {font_pt:.0f}pt in "
                    f"{cx/EMU_PER_INCH:.1f}\" wide × {cy/EMU_PER_INCH:.1f}\" tall "
                    f"→ estimated {est_lines} lines, capacity {cap_str}"
                ),
                suggestion="trim text, increase widget height, or reduce font size",
            ))
    return issues


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def check_pptx(pptx_path) -> list[ProportionIssue]:
    pptx_path = Path(pptx_path)
    issues: list[ProportionIssue] = []
    with zipfile.ZipFile(pptx_path) as zf:
        slide_w, slide_h = _slide_size(zf)
        for slide_id, xml in _slide_xml_files(zf):
            shapes = list(_iter_shapes(xml))
            # Skip cover/end slides (low shape count usually) and section dividers
            if len(shapes) <= 3:
                continue
            for check in (_check_figure_compressed, _check_figure_top_compressed):
                r = check(slide_id, shapes, slide_w, slide_h)
                if r:
                    issues.append(r)
            r = _check_aside_too_wide(slide_id, shapes, slide_w)
            if r:
                issues.append(r)
            issues.extend(_check_text_overflow(slide_id, shapes))
    return issues


def format_issues(issues: list[ProportionIssue]) -> str:
    if not issues:
        return ""
    lines = ["", "PROPORTION QA — measurable layout mismatches (non-fatal):"]
    for it in sorted(issues, key=lambda i: (i.slide_id, i.kind)):
        lines.append(f"  slide {it.slide_id}: {it.kind}")
        lines.append(f"    {it.detail}")
        lines.append(f"    → {it.suggestion}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: proportion_check.py <path/to/deck.pptx>", file=sys.stderr)
        sys.exit(2)
    issues = check_pptx(sys.argv[1])
    out = format_issues(issues)
    if out:
        sys.stderr.write(out)
        sys.stderr.write("\n")
    else:
        print(f"proportion check: no issues flagged on {sys.argv[1]}")
