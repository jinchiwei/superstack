# build-pptx v2: Color Cohesion + Section Semantics Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Single-task / one-shot dispatch.

**Goal:** Refactor build-pptx so each section's brand color cascades through every accent on its slides — left bar, section divider colorblock, table headers, hairlines all match. Title + section dividers move to navy `#0E1A35` (DMG/funding_report aesthetic). Section colors auto-inferred from H1 section names via keyword matching. Bottom amber hairline added to title + closing slides. Tag: `build-skills-v2`.

**Architecture:** Auto-inference in markdown driver tracks "current section" by walking the rendered HTML. First H1 in a chunk decides the section; subsequent H2s under that H1 inherit. Each content slide carries its section's accent_color. Slide masters take accent_color as kwarg and use it for any brand-color element (left bar, table header fills, callout chips). End-slide and title-slide accents are fixed (turquoise + deeppink + amber bottom hairline).

**Tech Stack:** Python 3.12 in `deepdream` conda env. Existing deps (python-pptx, markdown, pyyaml). No new deps.

**Realistic effort: ~2-3 hr CC time** (one subagent, one task with many steps).

---

## File Structure (changes only — most files exist from build-skills-v1)

```
~/arcadia/superstack/skills/
├── _shared/
│   ├── branding.py              MODIFY: change DARK_BG to #0E1A35; add match_section_color()
│   └── tests/test_branding.py   MODIFY: update DARK_BG assertion; add tests for match_section_color()
└── build-pptx/
    ├── build.py                 MODIFY: rewrite all 4 user-facing master functions + main()
    ├── tests/test_masters.py    MODIFY: signatures changed; add accent_color tests
    └── tests/test_main.py       MODIFY: assert section→color mapping in rendered slides
```

---

## Section→color auto-inference rules

Match against lowercased section name (substring matching):

| Keyword present | → Accent |
|---|---|
| `background`, `motivation`, `introduction`, `intro`, `context`, `conclusion`, `next`, `future`, `overview`, `direction` | turquoise |
| `method`, `methodology`, `approach`, `design`, `framework`, `cohort`, `pipeline`, `architecture`, `model` | deeppink |
| `result`, `finding`, `performance`, `outcome`, `metric`, `headline` | amber |
| `validation`, `limitation`, `caveat`, `robust`, `external`, `sensitivity`, `discussion`, `replication`, `ablation` | blueviolet |
| (no match) | turquoise (default) |

---

## Single-Task Spec

All steps below are bite-sized but live under one task. Subagent should commit when each step's tests pass to keep the history clean. Final commit + push + tag at the end.

### Step 1: Update `branding.py` — change DARK_BG, add match_section_color

**File:** `~/arcadia/superstack/skills/_shared/branding.py`

Change `DARK_BG`:

```python
# Old
DARK_BG = "#14141C"
# New (matches DMG / funding_report aesthetic)
DARK_BG = "#0E1A35"
```

Append at end of file:

```python
# === Section→color auto-inference ===
_SECTION_KEYWORDS = (
    (("background", "motivation", "introduction", "intro", "context", "conclusion",
      "next", "future", "overview", "direction"), TURQUOISE),
    (("method", "methodology", "approach", "design", "framework", "cohort",
      "pipeline", "architecture", "model"), DEEPPINK),
    (("result", "finding", "performance", "outcome", "metric", "headline"), AMBER),
    (("validation", "limitation", "caveat", "robust", "external", "sensitivity",
      "discussion", "replication", "ablation"), BLUEVIOLET),
)


def match_section_color(name: str) -> str:
    """Infer the section's accent color from its name via keyword matching.

    Returns one of TURQUOISE / DEEPPINK / AMBER / BLUEVIOLET. Falls back to
    TURQUOISE if no keyword matches.
    """
    if not name:
        return TURQUOISE
    needle = name.lower()
    for keywords, color in _SECTION_KEYWORDS:
        for kw in keywords:
            if kw in needle:
                return color
    return TURQUOISE
```

### Step 2: Update `_shared/tests/test_branding.py`

**File:** `~/arcadia/superstack/skills/_shared/tests/test_branding.py`

Update existing test (find the test that asserts DARK_BG and update value):

In `test_neutrals` or wherever DARK_BG is asserted, change:
```python
assert branding.DARK_BG == "#14141C"
```
to:
```python
assert branding.DARK_BG == "#0E1A35"
```

(If no test currently asserts `DARK_BG`, you can add one. But check first — there might already be one.)

Append new tests for match_section_color:

```python
def test_match_section_color_methods():
    assert branding.match_section_color("Methods") == branding.DEEPPINK
    assert branding.match_section_color("Methodology") == branding.DEEPPINK
    assert branding.match_section_color("approach and design") == branding.DEEPPINK


def test_match_section_color_results():
    assert branding.match_section_color("Results") == branding.AMBER
    assert branding.match_section_color("Findings") == branding.AMBER
    assert branding.match_section_color("Headline Performance") == branding.AMBER


def test_match_section_color_big_picture():
    assert branding.match_section_color("Background") == branding.TURQUOISE
    assert branding.match_section_color("Motivation") == branding.TURQUOISE
    assert branding.match_section_color("Conclusions") == branding.TURQUOISE
    assert branding.match_section_color("Next Steps") == branding.TURQUOISE


def test_match_section_color_validation():
    assert branding.match_section_color("Validation") == branding.BLUEVIOLET
    assert branding.match_section_color("Limitations") == branding.BLUEVIOLET
    assert branding.match_section_color("External Replication") == branding.BLUEVIOLET
    assert branding.match_section_color("Discussion") == branding.BLUEVIOLET


def test_match_section_color_unknown_falls_back_to_turquoise():
    assert branding.match_section_color("Random Title") == branding.TURQUOISE
    assert branding.match_section_color("") == branding.TURQUOISE


def test_match_section_color_case_insensitive():
    assert branding.match_section_color("METHODS") == branding.DEEPPINK
    assert branding.match_section_color("results") == branding.AMBER
```

Run tests, expect failures. Implement (Step 1 already did the implementation). Re-run tests, expect pass. **Commit:** `feat(_shared): DARK_BG → #0E1A35 + match_section_color() keyword classifier`

### Step 3: Rewrite `add_title_slide` in build.py

**File:** `~/arcadia/superstack/skills/build-pptx/build.py`

Replace the existing `add_title_slide` function with this version. Composition:

- Bg `#0E1A35` (now from `branding.DARK_BG`)
- Left vertical double-rail: turquoise (0.8in × 7.5in) at x=0; deeppink (0.25in × 7.5in) at x=0.8
- Bottom horizontal amber hairline (13.33in × 0.06in) at y=7.44 (right above bottom edge)
- Eyebrow turquoise mono 14pt at x=1.2, y=1.5
- Big title white mono 48pt at x=1.2, y=2.0
- Subtitle off-white sans 18pt at x=1.2, y=4.1
- Name turquoise mono 22pt at x=1.2, y=5.4
- Org deeppink mono 16pt at x=1.2, y=5.9
- Hairline rule (white@30% — use `RULE_RGB` proxy) at x=1.2, y=6.5, width=4.0in
- Date dim mono 12pt at x=1.2, y=6.6

```python
def add_title_slide(prs, *, eyebrow: str = "", title: str, subtitle: str = "",
                    name: str = "", org: str = "", date: str = ""):
    """Title slide: navy bg, left double-rail (turquoise + deeppink), bottom amber hairline.
    Eyebrow turquoise, title white, name turquoise, org deeppink, date dim, all Geist Mono."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    # Left double-rail
    _add_rect(s, left=0, top=0, width=0.8, height=7.5, fill_rgb=TURQUOISE_RGB)
    _add_rect(s, left=0.8, top=0, width=0.25, height=7.5, fill_rgb=DEEPPINK_RGB)

    # Bottom amber hairline
    _add_rect(s, left=0, top=7.44, width=13.333, height=0.06, fill_rgb=AMBER_RGB)

    if eyebrow:
        _add_text(s, eyebrow, left=1.3, top=1.5, width=11, height=0.4,
                  size=14, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
    _add_text(s, title, left=1.3, top=2.0, width=11.0, height=2.0,
              size=48, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)
    if subtitle:
        _add_text(s, subtitle, left=1.3, top=4.1, width=11.0, height=1.0,
                  size=18, color_rgb=_rgb("#E5E5EA"), font=branding.SANS_FONT)
    cursor_top = 5.4
    if name:
        _add_text(s, name, left=1.3, top=cursor_top, width=11, height=0.4,
                  size=22, color_rgb=TURQUOISE_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.5
    if org:
        _add_text(s, org, left=1.3, top=cursor_top, width=11, height=0.35,
                  size=16, color_rgb=DEEPPINK_RGB, font=branding.MONO_FONT, bold=True)
        cursor_top += 0.45

    # Hairline rule (white at low opacity — approximate as RULE_RGB)
    _add_rect(s, left=1.3, top=cursor_top + 0.1, width=4.0, height=0.005, fill_rgb=RULE_RGB)
    if date:
        _add_text(s, date, left=1.3, top=cursor_top + 0.25, width=11, height=0.3,
                  size=12, color_rgb=DIM_RGB, font=branding.MONO_FONT)
    return s
```

### Step 4: Rewrite `add_end_slide` to mirror title slide

```python
def add_end_slide(prs, *, message: str = "Thanks", contact: str = ""):
    """End slide: mirror title slide. Navy bg, left double-rail, bottom amber hairline.
    Big white "Thanks" centered, contact in dim mono below."""
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    # Left double-rail (mirror of title)
    _add_rect(s, left=0, top=0, width=0.8, height=7.5, fill_rgb=TURQUOISE_RGB)
    _add_rect(s, left=0.8, top=0, width=0.25, height=7.5, fill_rgb=DEEPPINK_RGB)

    # Bottom amber hairline (mirror of title)
    _add_rect(s, left=0, top=7.44, width=13.333, height=0.06, fill_rgb=AMBER_RGB)

    _add_text(s, message, left=1.3, top=2.7, width=11.0, height=2.0,
              size=64, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True,
              align=PP_ALIGN.CENTER)
    if contact:
        _add_text(s, contact, left=1.3, top=4.8, width=11.0, height=0.5,
                  size=14, color_rgb=DIM_RGB, font=branding.MONO_FONT,
                  align=PP_ALIGN.CENTER)
    return s
```

### Step 5: Rewrite `add_section_divider`

Combines results_overview big colorblock + DMG accents:

```python
def add_section_divider(prs, *, label: str, index: int = 0,
                        accent_color_hex: str | None = None):
    """Section divider: navy bg + full-height left colorblock + DMG-style accents.

    Color comes from `accent_color_hex` if provided, else from
    branding.pick_section_color(index) cycling.
    """
    bg_hex = accent_color_hex or branding.pick_section_color(index)
    accent = _rgb(bg_hex)
    s = _blank(prs)
    _set_bg(s, DARK_BG_RGB)

    # Big results_overview-style left colorblock (full height)
    _add_rect(s, left=0, top=0, width=0.6, height=7.5, fill_rgb=accent)

    # Small DMG-style accent bar — sits to the right of the colorblock,
    # at the eyebrow's vertical position (visual punctuation next to eyebrow)
    _add_rect(s, left=0.85, top=2.6, width=0.18, height=0.45, fill_rgb=accent)

    # Eyebrow ("PART I" — uppercase label) in brand color
    _add_text(s, label.upper(), left=1.15, top=2.6, width=11.0, height=0.45,
              size=14, color_rgb=accent, font=branding.MONO_FONT, bold=True)

    # Big section title (taking the label as the visible title)
    _add_text(s, label, left=0.85, top=3.15, width=11.5, height=1.6,
              size=44, color_rgb=WHITE_RGB, font=branding.MONO_FONT, bold=True)

    # Horizontal hairline rule below title in brand color
    _add_rect(s, left=0.85, top=4.85, width=2.0, height=0.02, fill_rgb=accent)

    return s
```

### Step 6: Rewrite `add_content_slide` with accent_color cohesion

```python
def add_content_slide(prs, *, title: str, body_paragraphs: list[str],
                      accent_color_hex: str | None = None):
    """Content slide: white bg + thin left vertical bar in section's accent color.

    Title and any future brand-color elements (table headers, callout chips)
    inherit the same accent color so the whole slide reads as one identity.
    """
    accent_hex = accent_color_hex or branding.TURQUOISE
    accent = _rgb(accent_hex)
    s = _blank(prs)
    _set_bg(s, WHITE_RGB)

    # Thin vertical accent bar on left (funding_report style, full height)
    _add_rect(s, left=0, top=0, width=0.22, height=7.5, fill_rgb=accent)

    # Slide title in section's accent color
    _add_text(s, title, left=0.6, top=0.4, width=12.5, height=0.8,
              size=32, color_rgb=accent, font=branding.MONO_FONT, bold=True)

    # Hairline rule under title in same accent
    _add_rect(s, left=0.6, top=1.25, width=12.0, height=0.005, fill_rgb=accent)

    # Body
    body_text = "\n".join(body_paragraphs)
    _add_text(s, body_text, left=0.6, top=1.5, width=12.5, height=5.5,
              size=22, color_rgb=INK_RGB, font=branding.SANS_FONT)
    return s
```

### Step 7: Update markdown driver in `main()` to track section accent

In `main()`, after parsing the body chunks, walk through them and track the "current section accent" based on H1 occurrences:

```python
def main() -> int:
    ap = argparse.ArgumentParser(description="markdown → Jin-branded PPTX")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--no-cover", dest="no_cover", action="store_true",
                    help="suppress title slide")
    ap.add_argument("--no-end", dest="no_end", action="store_true",
                    help="suppress closing 'Thanks' slide")
    args = ap.parse_args()

    loaded = load_markdown(args.input)
    meta = loaded["meta"]
    today = dt.date.today().isoformat()

    prs = new_presentation()

    if not args.no_cover:
        add_title_slide(
            prs,
            eyebrow=str(meta.get("eyebrow", "")),
            title=extract_title(loaded) or Path(args.input).stem,
            subtitle=str(meta.get("subtitle", "")),
            name=str(meta.get("name", "")),
            org=str(meta.get("org", "")),
            date=str(meta.get("date") or today),
        )

    # Walk slide chunks; track current section accent.
    # When a chunk's title is from an H1, treat that H1 as a section divider:
    #   - emit a section_divider slide
    #   - update current accent
    # When a chunk's title is from an H2, emit a content slide using current accent.
    chunks = _split_slides(loaded["body_html"])
    current_accent = branding.TURQUOISE  # default if first slide is H2

    for chunk in chunks:
        # Detect whether the first heading in the chunk is H1 or H2
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", chunk)
        if h1_match:
            section_label = _strip_html(h1_match.group(1))
            current_accent = branding.match_section_color(section_label)
            add_section_divider(prs, label=section_label,
                                accent_color_hex=current_accent)
            # Strip the H1 from the chunk so its body (if any) becomes a content slide
            remaining = chunk[h1_match.end():].strip()
            if remaining:
                slide = _parse_slide_chunk(remaining)
                if slide["title"] or slide["body"]:
                    add_content_slide(prs,
                                      title=slide["title"] or "(untitled)",
                                      body_paragraphs=slide["body"],
                                      accent_color_hex=current_accent)
        else:
            slide = _parse_slide_chunk(chunk)
            if slide["title"] or slide["body"]:
                add_content_slide(prs,
                                  title=slide["title"] or "(untitled)",
                                  body_paragraphs=slide["body"],
                                  accent_color_hex=current_accent)

    if not args.no_end:
        add_end_slide(prs, message="Thanks",
                      contact=str(meta.get("name") or ""))

    prs.save(args.output)
    print(f"wrote {args.output}")
    return 0
```

### Step 8: Update `tests/test_masters.py` — adjust signatures, add cohesion tests

The 9 existing tests in `test_masters.py` mostly assert "function adds 1 slide." Those still pass. But `test_add_section_divider_cycles_color_by_index` needs adjusting since `add_section_divider`'s signature changed (now takes `accent_color_hex` kwarg too).

Append new tests at the end of `test_masters.py`:

```python
def test_add_content_slide_accepts_accent_color():
    """add_content_slide takes accent_color_hex; defaults to turquoise."""
    import branding as b
    prs = new_presentation()
    add_content_slide(prs, title="Section", body_paragraphs=["body"],
                      accent_color_hex=b.DEEPPINK)
    assert len(prs.slides) == 1
    # Find a deeppink-fill rect on the slide (the left bar)
    found_deeppink = False
    s = prs.slides[0]
    for shp in s.shapes:
        try:
            if shp.fill.type == 1 and str(shp.fill.fore_color.rgb).upper() == "FF1493":
                found_deeppink = True
                break
        except Exception:
            pass
    assert found_deeppink, "left bar in deeppink not found"


def test_add_section_divider_accepts_accent_color_override():
    """add_section_divider takes accent_color_hex overriding the index cycle."""
    import branding as b
    prs = new_presentation()
    add_section_divider(prs, label="Custom", accent_color_hex=b.AMBER)
    s = prs.slides[0]
    found_amber = False
    for shp in s.shapes:
        try:
            if shp.fill.type == 1 and str(shp.fill.fore_color.rgb).upper() == "F0C840":
                found_amber = True
                break
        except Exception:
            pass
    assert found_amber, "amber colorblock not found in section divider"


def test_title_slide_has_amber_bottom_hairline():
    """Title slide includes a thin amber bar at the bottom."""
    prs = new_presentation()
    add_title_slide(prs, eyebrow="X", title="T", date="2026-05-01")
    s = prs.slides[0]
    # Find any rect filled with amber #F0C840
    found_amber = False
    for shp in s.shapes:
        try:
            if shp.fill.type == 1 and str(shp.fill.fore_color.rgb).upper() == "F0C840":
                found_amber = True
                break
        except Exception:
            pass
    assert found_amber, "amber bottom hairline missing"


def test_end_slide_mirrors_title_amber_hairline():
    prs = new_presentation()
    add_end_slide(prs, message="Thanks", contact="me")
    s = prs.slides[0]
    found_amber = False
    for shp in s.shapes:
        try:
            if shp.fill.type == 1 and str(shp.fill.fore_color.rgb).upper() == "F0C840":
                found_amber = True
                break
        except Exception:
            pass
    assert found_amber, "amber bottom hairline missing on end slide"
```

### Step 9: Update `tests/test_main.py` — section→color cascade test

Append a new test that uses a multi-section fixture and verifies each content slide's left bar matches its section's expected color.

First, add a multi-section fixture at `~/arcadia/superstack/skills/build-pptx/tests/fixture_sections.md`:

```markdown
---
title: "Section Color Cascade Test"
eyebrow: "TEST"
name: "Jinchi Wei"
org: "UCSF"
date: "2026-05-01"
---

# Background

## Motivation slide

Body text here.

# Methods

## Pipeline overview

Body text here.

# Results

## Headline numbers

Body text here.

# Limitations

## What we couldn't measure

Body text here.

# Conclusions

## Next steps

Body text here.
```

Append this test:

```python
def test_section_color_cascade(tmp_path):
    """Each content slide's left bar matches its section's expected color."""
    fixture = SKILL_DIR / "tests" / "fixture_sections.md"
    out = tmp_path / "cascade.pptx"
    cmd = [sys.executable, str(BUILD_PY),
           "--input", str(fixture),
           "--output", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr

    from pptx import Presentation
    prs = Presentation(str(out))
    # Skip title slide (idx 0) and end slide (last). Slides between are:
    # divider(Background, turquoise) → content(Motivation slide, turquoise)
    # divider(Methods, deeppink)     → content(Pipeline overview, deeppink)
    # divider(Results, amber)        → content(Headline numbers, amber)
    # divider(Limitations, blueviolet) → content(What we couldn't measure, blueviolet)
    # divider(Conclusions, turquoise) → content(Next steps, turquoise)
    expected = [
        # (slide_idx, expected_brand_hex)
        (1, "40E0D0"),  # Background section divider
        (2, "40E0D0"),  # Motivation content slide
        (3, "FF1493"),  # Methods divider
        (4, "FF1493"),  # Pipeline content
        (5, "F0C840"),  # Results divider
        (6, "F0C840"),  # Headline content
        (7, "8A2BE2"),  # Limitations divider
        (8, "8A2BE2"),  # What we couldn't measure content
        (9, "40E0D0"),  # Conclusions divider
        (10, "40E0D0"), # Next steps content
    ]
    for slide_idx, hex_color in expected:
        slide = prs.slides[slide_idx]
        # Find any solid-filled rect on the slide that uses this brand color
        found = False
        for shp in slide.shapes:
            try:
                if shp.fill.type == 1 and str(shp.fill.fore_color.rgb).upper() == hex_color:
                    found = True
                    break
            except Exception:
                pass
        assert found, f"slide {slide_idx} missing expected brand color #{hex_color}"
```

### Step 10: Run all tests

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/_shared/tests/ -v
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && pytest ~/arcadia/superstack/skills/build-pptx/tests/ -v
```

Expected: _shared 24+ pass, build-pptx 16+ pass. (Existing test_masters' `test_add_section_divider_cycles_color_by_index` may need a small tweak since the function signature changed; verify it still works via `index=` and falls back to the cycle when `accent_color_hex` is None.)

### Step 11: Sync to ~/.claude/skills/

```bash
cp ~/arcadia/superstack/skills/_shared/branding.py ~/.claude/skills/_shared/
cp ~/arcadia/superstack/skills/_shared/tests/test_branding.py ~/.claude/skills/_shared/tests/
cp ~/arcadia/superstack/skills/build-pptx/build.py ~/.claude/skills/build-pptx/
cp ~/arcadia/superstack/skills/build-pptx/tests/*.py ~/.claude/skills/build-pptx/tests/
cp ~/arcadia/superstack/skills/build-pptx/tests/fixture_sections.md ~/.claude/skills/build-pptx/tests/
```

### Step 12: Smoke test

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate deepdream && \
  python ~/.claude/skills/build-pptx/build.py \
  --input ~/.claude/skills/build-pptx/tests/fixture_sections.md \
  --output /tmp/build-pptx-v2-smoke.pptx
ls -la /tmp/build-pptx-v2-smoke.pptx
```

Expected: PPTX generated, > 5KB. Don't `open` from the script; that's for Jin to inspect later.

### Step 13: Commit + push + tag

```bash
cd ~/arcadia/superstack
git add skills/_shared/ skills/build-pptx/ docs/plans/2026-05-01-build-pptx-v2-cohesion.md
git -c user.email="mrjinch@gmail.com" -c user.name="jinchiwei" commit -m "feat: build-pptx v2 — color cascade cohesion + navy backgrounds + section semantics" -m "Section colors auto-inferred from H1 names (background/methods/results/limitations → turquoise/deeppink/amber/blueviolet). Title and section divider backgrounds move to navy #0E1A35. Title slide adds bottom amber hairline. Content slides + section dividers carry the section's accent color through every brand-color element on the slide (left bar, title, hairline rule). Section dividers combine results_overview's full-height left colorblock with DMG's small accent bar, eyebrow, and brand-color hairline rule."
git push origin main
git tag build-skills-v2
git push origin build-skills-v2
```

---

## Self-Review Checklist

- [ ] DARK_BG = "#0E1A35" in branding.py and old #14141C is gone everywhere
- [ ] match_section_color works on lowercase substring matching, falls back to turquoise
- [ ] add_title_slide: navy bg + left double-rail + bottom amber hairline
- [ ] add_end_slide: mirrors title slide
- [ ] add_section_divider: navy bg + full-height left colorblock + small accent bar + eyebrow + title + hairline rule
- [ ] add_content_slide: takes accent_color_hex, renders left bar + title + hairline in that color
- [ ] markdown driver tracks current section, propagates accent to content slides
- [ ] All tests pass (existing + new); _shared has 24+ tests, build-pptx has 16+ tests
- [ ] Synced to ~/.claude/skills/
- [ ] Smoke test produces a valid pptx
- [ ] Tag `build-skills-v2` pushed

---

## Notes for the implementer

- `accent_color_hex` is the param name everywhere — keep it consistent
- The H1-as-section-divider parsing: when an H1 is found in a chunk, emit BOTH a section divider AND (if there's body content after the H1 in the same chunk) a content slide for the body
- For backward compatibility, `add_section_divider`'s `index=0` default + cycle behavior stays — only the new optional `accent_color_hex` overrides
- Don't worry about table headers / callout chips inheriting accent in this v2 — markdown driver doesn't render tables yet. The cohesion pattern is a public-API contract (Python callers get accent_color), not a fully-rendered feature for v2
- If `test_add_section_divider_cycles_color_by_index` already exists and passes through the new signature, leave it alone — the cycle still works when `accent_color_hex` is None
