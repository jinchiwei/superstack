# build-pptx Named-Layout Theming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ~18 named layout renderers honor the active theme (dark/tinted canvas, inverted text, themed card surfaces) so a dark expressive deck built from named layouts renders cohesively — without hand-authoring every slide as freeform.

**Architecture:** Introduce a per-deck `Palette` value object (canvas / text / muted / surface / rule colors + `on_dark`) resolved from the active `Theme`. Thread `palette` as a new keyword arg from `render_from_plan` through the catalog dispatch into every renderer, and into the shared helpers (`_set_bg` call sites, `_add_chrome`, `_add_card`, `_render_paragraph_block`). Renderers source colors from `palette` instead of hardcoded constants. A `LIGHT` default `Palette` equals today's exact constants, so strict mode and any no-theme render stay byte-identical.

**Tech Stack:** Python, python-pptx, the existing `themes.py` / `render.py` / `layouts/` infrastructure, pytest. Visual checks via the `--qa` loop (LibreOffice + poppler, already installed).

**Critical invariant:** Strict mode (and any render with no active dark/tinted theme) MUST stay byte-identical to tag `build-skills-v7.2-pre-expressive`. The `LIGHT` palette is the mechanism. Two tasks explicitly verify this with a slide-XML diff.

---

## File Structure

**New files:**
- `skills/build-pptx/palette.py` — `Palette` dataclass, `LIGHT` constant, `palette_for_theme(theme)`. Pure data; imports color constants from `layouts._common`.
- `skills/build-pptx/tests/test_palette.py`

**Modified files:**
- `skills/build-pptx/render.py` — resolve a `Palette` from the active theme; pass `palette` into every catalog renderer; paint canvas handled by renderers' own `_set_bg`.
- `skills/build-pptx/layouts/_common.py` — `_add_chrome` already has `on_dark`; add palette-aware behavior to `_add_card` and confirm `_render_paragraph_block` text color is parameterized.
- `skills/build-pptx/layouts/*.py` — all 18 named renderers gain a `palette` kwarg (default `LIGHT`) and use it for background + body text + card fills.
- `skills/build-pptx/tests/` — new theming assertions; existing suite must stay green.

**Key existing facts (verified):**
- All named renderers share `def render(slide, *, params, accent_rgb, footer_kwargs)`. Dispatch in `render.py`: `renderer(s, params=params, accent_rgb=_rgb(accent_hex), footer_kwargs=footer_kwargs)`.
- Each renderer calls `_set_bg(slide, WHITE_RGB)` then `_add_chrome(...)`. `_add_chrome` already takes `on_dark` (flips title/lede/footer text).
- Color constants live in `layouts/_common.py`: `INK_RGB`, `WHITE_RGB`, `MUTED_RGB`, `RULE_RGB`, `PAPER_RGB`, `DIM_RGB`, brand-4, `DARK_BG_RGB`. `_rgb(hex)` builds an `RGBColor`.
- `themes.py` `Theme` has `name, canvas("light"|"dark"|"tinted"), bg_hex, on_dark, accent_order, supplementary`.
- The 18 renderers: `content_text, content_text_image, content_image_only, cards_grid, cards_triple, cards_heterogeneous, cards_with_takeaway, figure_with_aside, figure_with_aside_horizontal, table_with_takeaway, stats_with_takeaway, stat_callouts_right, three_pillars, timeline, vertical_timeline, bg_flip, conclusions, composition`. (`freeform` already themed — leave it.)
- Color-heavy renderers (more than 2 hardcoded color refs): `stat_callouts_right, cards_heterogeneous, vertical_timeline, bg_flip, three_pillars, cards_triple, timeline`.

---

## Task 0: Branch checkpoint

**Files:** none (git)

- [ ] **Step 1: Confirm on the feature branch with clean tree**

Run: `git -C ~/arcadia/superstack status --short && git -C ~/arcadia/superstack branch --show-current`
Expected: clean tree, branch `exp/pptx-expressive-mode`. (Named-layout theming continues on the same branch so it merges together with expressive mode.)

- [ ] **Step 2: Tag the current expressive-complete state as a sub-checkpoint**

```bash
git -C ~/arcadia/superstack tag build-pptx-expressive-complete
```
This lets you diff named-layout-theming changes in isolation later.

---

## Task 1: `Palette` value object

**Files:**
- Create: `skills/build-pptx/palette.py`
- Test: `skills/build-pptx/tests/test_palette.py`

- [ ] **Step 1: Write the failing test**

Create `skills/build-pptx/tests/test_palette.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from palette import LIGHT, Palette, palette_for_theme
from themes import get_theme
from layouts._common import INK_RGB, WHITE_RGB, MUTED_RGB, RULE_RGB, PAPER_RGB


def test_light_palette_equals_todays_constants():
    # LIGHT must reproduce the exact colors used before theming existed.
    assert LIGHT.canvas_rgb == WHITE_RGB
    assert LIGHT.text_rgb == INK_RGB
    assert LIGHT.muted_rgb == MUTED_RGB
    assert LIGHT.surface_rgb == PAPER_RGB
    assert LIGHT.rule_rgb == RULE_RGB
    assert LIGHT.on_dark is False


def test_palette_for_none_theme_is_light():
    assert palette_for_theme(None) is LIGHT


def test_dark_theme_palette_inverts():
    p = palette_for_theme(get_theme("midnight"))  # canvas dark, on_dark True
    assert p.on_dark is True
    assert str(p.canvas_rgb) == "14141C"          # theme bg_hex
    assert p.text_rgb == WHITE_RGB                 # text inverts to white
    # card surface must be lighter than the canvas, not equal to it
    assert str(p.surface_rgb) != "14141C"


def test_light_theme_palette_keeps_dark_text():
    p = palette_for_theme(get_theme("paper"))      # canvas light, on_dark False
    assert p.on_dark is False
    assert p.text_rgb == INK_RGB
    assert str(p.canvas_rgb) == "FFFFFF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_palette.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'palette'`.

- [ ] **Step 3: Implement `palette.py`**

Create `skills/build-pptx/palette.py`:

```python
"""palette.py — per-deck color resolution for build-pptx.

A Palette is the set of *role* colors a slide renderer needs: the canvas
(slide background), primary text, muted/secondary text, card surface fill,
and hairline rule color, plus whether the canvas is dark (so chrome text
inverts). It is resolved once per deck from the active Theme.

LIGHT is the default and MUST equal the exact constants used before theming
existed, so strict mode / no-theme renders are byte-identical to the
pre-feature behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from layouts._common import (
    INK_RGB, WHITE_RGB, MUTED_RGB, RULE_RGB, PAPER_RGB, _rgb,
)


@dataclass(frozen=True)
class Palette:
    canvas_rgb: object      # RGBColor — slide background
    text_rgb: object        # RGBColor — primary body text
    muted_rgb: object       # RGBColor — secondary text / labels
    surface_rgb: object     # RGBColor — card fill
    rule_rgb: object        # RGBColor — hairlines
    on_dark: bool           # True -> chrome text inverts (passed to _add_chrome)


# Exactly today's colors. DO NOT change these values — strict parity depends on it.
LIGHT = Palette(
    canvas_rgb=WHITE_RGB,
    text_rgb=INK_RGB,
    muted_rgb=MUTED_RGB,
    surface_rgb=PAPER_RGB,
    rule_rgb=RULE_RGB,
    on_dark=False,
)


def palette_for_theme(theme) -> Palette:
    """Resolve a Palette from a Theme (or None -> LIGHT).

    Dark themes invert text to white, use a lighter-than-canvas card surface,
    and a dim rule. Light/tinted themes keep dark text but adopt the theme's
    canvas tint.
    """
    if theme is None:
        return LIGHT
    if theme.on_dark:
        return Palette(
            canvas_rgb=_rgb(theme.bg_hex),
            text_rgb=WHITE_RGB,
            muted_rgb=_rgb("#9FB3C8"),       # legible secondary on dark
            surface_rgb=_lighten(theme.bg_hex, 0.10),
            rule_rgb=_rgb("#33415C"),
            on_dark=True,
        )
    # Light / tinted canvas: keep dark text, adopt the tint.
    return Palette(
        canvas_rgb=_rgb(theme.bg_hex),
        text_rgb=INK_RGB,
        muted_rgb=MUTED_RGB,
        surface_rgb=PAPER_RGB,
        rule_rgb=RULE_RGB,
        on_dark=False,
    )


def _lighten(hex_str: str, amount: float):
    """Lighten a hex color toward white by `amount` (0..1). Used for card
    surfaces that must sit a step above a dark canvas."""
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return _rgb(f"#{r:02X}{g:02X}{b:02X}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_palette.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/palette.py skills/build-pptx/tests/test_palette.py
git commit -m "feat(build-pptx): add Palette value object resolving theme -> role colors"
```

---

## Task 2: Thread `palette` plumbing (inert — defaults to LIGHT)

**Goal of this task:** Add the `palette` kwarg everywhere it needs to flow, defaulting to `LIGHT`, and have `render_from_plan` pass `LIGHT`. Nothing visual changes yet — this is pure plumbing so parity is trivially preserved and verifiable.

**Files:**
- Modify: `skills/build-pptx/render.py` (dispatch call + signature)
- Modify: all 18 renderers in `skills/build-pptx/layouts/*.py` (add `palette=LIGHT` kwarg, unused for now)
- Test: `skills/build-pptx/tests/test_palette_plumbing.py`

- [ ] **Step 1: Write the failing test**

Create `skills/build-pptx/tests/test_palette_plumbing.py`:

```python
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import layouts.catalog as catalog


def test_every_named_renderer_accepts_palette():
    # Every renderer in the catalog must accept a `palette` keyword.
    for kind, renderer in catalog.CATALOG.items():
        sig = inspect.signature(renderer)
        assert "palette" in sig.parameters, f"{kind} renderer missing palette kwarg"
```

(If the catalog exposes its mapping under a different name than `CATALOG`, read `layouts/catalog.py` and adjust the test to iterate the actual mapping. The renderer functions are the values.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_palette_plumbing.py -v`
Expected: FAIL — renderers don't accept `palette`.

- [ ] **Step 3: Add `palette=LIGHT` to every renderer signature**

For EACH of the 18 files in `skills/build-pptx/layouts/` listed below, change the `render` signature to add `palette=LIGHT` as the last keyword parameter, and add the import. The body does NOT use `palette` yet.

Files: `content_text.py, content_text_image.py, content_image_only.py, cards_grid.py, cards_triple.py, cards_heterogeneous.py, cards_with_takeaway.py, figure_with_aside.py, figure_with_aside_horizontal.py, table_with_takeaway.py, stats_with_takeaway.py, stat_callouts_right.py, three_pillars.py, timeline.py, vertical_timeline.py, bg_flip.py, conclusions.py, composition.py`.

In each, add to the existing `from ._common import (...)` block (or add a new import) the line importing LIGHT from palette — but note `palette.py` imports from `layouts._common`, so to avoid a circular import, import `LIGHT` lazily is unnecessary: `palette.py` imports `layouts._common` (leaf), and renderers import `palette` (higher). `layouts/*.py` importing `palette` is fine because `palette` does not import any `layouts/*` renderer, only `layouts._common`. Add at the top of each renderer file:

```python
from palette import LIGHT
```

And change the signature, e.g. for `content_text.py`:

```python
def render(slide, *, params: dict, accent_rgb: RGBColor, footer_kwargs: dict,
           palette=LIGHT) -> None:
```

Apply the identical signature change (append `, palette=LIGHT`) to all 18. For `composition.py` (multiline signature) append `palette=LIGHT` as the last keyword param likewise.

- [ ] **Step 4: Pass `palette` from `render_from_plan`**

In `skills/build-pptx/render.py`, add at the top of the function body (after `theme` is available — `render_from_plan` already takes `theme=None`):

```python
    from palette import palette_for_theme
    palette = palette_for_theme(theme)
```

Then change the catalog dispatch call from:

```python
        renderer(s, params=params, accent_rgb=_rgb(accent_hex),
                 footer_kwargs=footer_kwargs)
```
to:
```python
        renderer(s, params=params, accent_rgb=_rgb(accent_hex),
                 footer_kwargs=footer_kwargs, palette=palette)
```

(Leave the `freeform` path's `_theme` injection as-is; freeform's `render` must also accept `palette` per Step 3 if it's in the catalog — check whether `freeform` is dispatched through the same catalog. If `freeform.render` is in the catalog, add `palette=LIGHT` to its signature too and ignore it there, since freeform already themes via `_theme`.)

- [ ] **Step 5: Run the plumbing test + full suite**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_palette_plumbing.py -q && ~/miniconda3/envs/deepdream/bin/python -m pytest -q`
Expected: plumbing test passes; full suite still green. Restore mutated fixtures: `git checkout -- 'skills/build-pptx/tests/fixture_*' skills/build-pptx/tests/fixture.md.layout.json` (from repo root).

- [ ] **Step 6: Verify strict parity (plumbing must not change output)**

Run the parity harness (build same fixture from tag vs branch in strict mode, diff slide XML):
```bash
cd ~/arcadia/superstack
PY=~/miniconda3/envs/deepdream/bin/python
rm -rf /tmp/nlt_old /tmp/nlt_new /tmp/nlt_pretag
git worktree add -q --detach /tmp/nlt_pretag build-skills-v7.2-pre-expressive
( cd /tmp/nlt_pretag/skills/build-pptx && $PY build.py --input tests/fixture_named_v7.md --output /tmp/old.pptx >/dev/null 2>&1 )
( cd skills/build-pptx && $PY build.py --input tests/fixture_named_v7.md --output /tmp/new.pptx --mode strict >/dev/null 2>&1 )
git checkout -- skills/build-pptx/tests/fixture_named_v7.md.layout.json
( cd /tmp/nlt_pretag && git checkout -- skills/build-pptx/tests/fixture_named_v7.md.layout.json )
mkdir -p /tmp/nlt_old /tmp/nlt_new
unzip -oq /tmp/old.pptx 'ppt/slides/*.xml' -d /tmp/nlt_old
unzip -oq /tmp/new.pptx 'ppt/slides/*.xml' -d /tmp/nlt_new
diff -rq /tmp/nlt_old/ppt/slides /tmp/nlt_new/ppt/slides && echo "PARITY OK" || echo "PARITY DIFF"
git worktree remove --force /tmp/nlt_pretag
```
Expected: `PARITY OK`.

- [ ] **Step 7: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/render.py skills/build-pptx/layouts/*.py skills/build-pptx/tests/test_palette_plumbing.py
git commit -m "refactor(build-pptx): thread palette kwarg through renderers (inert, defaults LIGHT)"
```

---

## Task 3: Theme the shared helpers (`_set_bg` call sites, `_add_card`)

**Goal:** Make the shared drawing helpers palette-aware, so most renderers get themed for free once they pass `palette` into them. `_add_chrome` already inverts via `on_dark` — renderers will pass `on_dark=palette.on_dark`.

**Files:**
- Modify: `skills/build-pptx/layouts/_common.py` (`_add_card` to accept optional surface/text overrides)
- Test: `skills/build-pptx/tests/test_themed_helpers.py`

- [ ] **Step 1: Write the failing test**

Create `skills/build-pptx/tests/test_themed_helpers.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import inspect
from layouts import _common


def test_add_card_accepts_surface_and_text_overrides():
    sig = inspect.signature(_common._add_card)
    assert "surface_rgb" in sig.parameters
    assert "text_rgb" in sig.parameters
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_themed_helpers.py -v`
Expected: FAIL — `_add_card` has no `surface_rgb`/`text_rgb` params.

- [ ] **Step 3: Read `_add_card` then add optional palette overrides**

Read `skills/build-pptx/layouts/_common.py`'s `_add_card` to see its current signature and which constants it uses for the card fill and label/body text. Add two optional keyword params, defaulting to the current hardcoded values so existing callers are unchanged:

```python
def _add_card(slide, *, label, body, left, top, width, height, accent_rgb,
              icon_path=None, surface_rgb=PAPER_RGB, text_rgb=INK_RGB):
    # ... replace the hardcoded card-fill constant with surface_rgb,
    #     and the hardcoded body/label text constant with text_rgb ...
```

Keep label color logic that uses `accent_rgb` as-is (accents read on both canvases). Only the card *fill* (was `PAPER_RGB`) and the *body text* (was `INK_RGB`) become parameterized. Defaults preserve current output exactly.

- [ ] **Step 4: Run test to verify it passes + full suite for parity**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_themed_helpers.py -q && ~/miniconda3/envs/deepdream/bin/python -m pytest -q`
Expected: pass; full suite green (defaults unchanged). Restore fixtures (scoped).

- [ ] **Step 5: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/layouts/_common.py skills/build-pptx/tests/test_themed_helpers.py
git commit -m "feat(build-pptx): make _add_card accept palette surface/text overrides (defaults unchanged)"
```

---

## Task 4: Theme the simple renderers

**Goal:** Make the renderers that only set background + chrome + body text use the palette. Each change is the same shape: `_set_bg(slide, palette.canvas_rgb)`, `_add_chrome(..., on_dark=palette.on_dark)`, and body text via `palette.text_rgb`.

**Files (simple renderers):** `content_text.py, content_text_image.py, content_image_only.py, cards_grid.py, cards_triple.py, cards_with_takeaway.py, figure_with_aside.py, figure_with_aside_horizontal.py, table_with_takeaway.py, stats_with_takeaway.py, conclusions.py`
- Test: `skills/build-pptx/tests/test_named_layout_theming.py`

- [ ] **Step 1: Write the failing test (dark canvas on a named layout)**

Create `skills/build-pptx/tests/test_named_layout_theming.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pptx import Presentation
from pptx.util import Inches

import render as render_mod
from plan import Plan, SlideEntry
from themes import get_theme


def _full_bleed_fill_hexes(pptx_path):
    """Return fill hexes of full-bleed (~13.33x7.5in) rects on the first
    non-cover content slide."""
    prs = Presentation(str(pptx_path))
    hexes = []
    for s in prs.slides:
        for sh in s.shapes:
            try:
                w = sh.width / 914400.0
                h = sh.height / 914400.0
            except (TypeError, ValueError):
                continue
            if abs(w - 13.333) < 0.2 and abs(h - 7.5) < 0.2:
                try:
                    if int(sh.fill.type) == 1:
                        hexes.append(str(sh.fill.fore_color.rgb))
                except Exception:
                    pass
    return hexes


def test_content_text_named_layout_paints_dark_canvas(tmp_path):
    md = tmp_path / "deck.md"
    md.write_text("---\ntitle: T\n---\n\n# A\n\nsome body text here\n", encoding="utf-8")
    plan = Plan(mode="expressive", theme="midnight", slides=[
        SlideEntry(slide_id="h1-a", kind="content-text",
                   params={"title": "A", "body": [{"kind": "p", "html": "hi"}]}),
    ])
    out = tmp_path / "out.pptx"
    render_mod.render_from_plan(md_path=md, plan=plan, output_path=out,
                                theme=get_theme("midnight"))
    assert "14141C" in _full_bleed_fill_hexes(out)  # dark canvas painted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_named_layout_theming.py -v`
Expected: FAIL — content-text still paints `WHITE_RGB` (no `14141C` full-bleed rect).

- [ ] **Step 3: Update each simple renderer to use the palette**

For each simple renderer, apply this transformation (shown for `content_text.py`; the others follow the same pattern — each already calls `_set_bg(...)` and `_add_chrome(...)`):

In `content_text.py`, change:
```python
    _set_bg(slide, WHITE_RGB)

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide, title=title, lede=lede, footer_kwargs=footer_kwargs,
        accent=accent_rgb, title_present=title_present,
        title_wraps=title_wraps, use_side_by_side=False,
    )

    if body:
        _render_paragraph_block(slide, items=body, left=body_l, top=body_top,
                                width=body_w, height=body_h,
                                accent_rgb=accent_rgb, size=14, distribute=True)
```
to:
```python
    _set_bg(slide, palette.canvas_rgb)

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide, title=title, lede=lede, footer_kwargs=footer_kwargs,
        accent=accent_rgb, title_present=title_present,
        title_wraps=title_wraps, use_side_by_side=False,
        on_dark=palette.on_dark,
    )

    if body:
        _render_paragraph_block(slide, items=body, left=body_l, top=body_top,
                                width=body_w, height=body_h,
                                accent_rgb=accent_rgb, size=14, distribute=True,
                                text_rgb=palette.text_rgb)
```

For this to work, `_render_paragraph_block` must accept a `text_rgb` override (default = current body text color). Read it in `_common.py`; if it hardcodes the body text color, add a `text_rgb=<current default>` kwarg and use it. (This is a shared-helper change bundled into this task because the simple renderers depend on it.)

Apply the analogous edit to each simple renderer:
- Replace `_set_bg(slide, WHITE_RGB)` → `_set_bg(slide, palette.canvas_rgb)`.
- Add `on_dark=palette.on_dark` to its `_add_chrome(...)` call.
- For any body/paragraph text drawn via `_render_paragraph_block` or `_add_text` with `INK_RGB`, pass `palette.text_rgb` (or `text_rgb=palette.text_rgb`).
- For renderers that draw cards via `_add_card`, pass `surface_rgb=palette.surface_rgb, text_rgb=palette.text_rgb`.
- `table_with_takeaway.py`: the data table cell text should use `palette.text_rgb`; the dark-accent callout footer is already dark-on-accent and can stay.
- `conclusions.py`: it already renders a dark navy background per its own design — confirm it still looks right under a theme; if it hardcodes its own bg, leave that (it's intentionally dark) but ensure card text uses `palette.text_rgb` only if the palette is dark; simplest: leave `conclusions.py` as-is if it's already dark-canvas, and SKIP it here (note it in the report). Decide by reading the file.

- [ ] **Step 4: Run the theming test + full suite**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_named_layout_theming.py -q && ~/miniconda3/envs/deepdream/bin/python -m pytest -q`
Expected: dark-canvas test passes; full suite green. Restore fixtures (scoped).

- [ ] **Step 5: Verify strict parity STILL holds**

Re-run the parity harness from Task 2 Step 6. Expected: `PARITY OK` (LIGHT palette → `palette.canvas_rgb == WHITE_RGB`, `on_dark=False`, `text_rgb == INK_RGB` → identical output).

- [ ] **Step 6: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/layouts/*.py skills/build-pptx/tests/test_named_layout_theming.py
git commit -m "feat(build-pptx): theme simple named layouts via palette (canvas/text/surface)"
```

---

## Task 5: Theme the color-heavy renderers

**Goal:** The renderers with custom color usage need per-file attention: `stat_callouts_right, cards_heterogeneous, vertical_timeline, three_pillars, cards_triple, timeline, bg_flip`.

**Files:** the 7 listed renderers.
- Test: extend `tests/test_named_layout_theming.py`

- [ ] **Step 1: Add a failing test that each heavy renderer paints the dark canvas**

Append to `tests/test_named_layout_theming.py`:

```python
import pytest


@pytest.mark.parametrize("kind,params", [
    ("three-pillars", {"title": "T", "pillars": [
        {"label": "A", "body": "x"}, {"label": "B", "body": "y"},
        {"label": "C", "body": "z"}]}),
    ("stats-with-takeaway", {"title": "T", "stats": [
        {"value": "1", "label": "a"}, {"value": "2", "label": "b"}],
        "takeaway": "done"}),
    ("cards-grid", {"title": "T", "cards": [
        {"label": "A", "body": "x"}, {"label": "B", "body": "y"},
        {"label": "C", "body": "z"}]}),
])
def test_named_layout_dark_canvas(tmp_path, kind, params):
    md = tmp_path / "deck.md"
    md.write_text("---\ntitle: T\n---\n\n# A\n\nbody\n", encoding="utf-8")
    plan = Plan(mode="expressive", theme="midnight", slides=[
        SlideEntry(slide_id="h1-a", kind=kind, params=params),
    ])
    out = tmp_path / f"{kind}.pptx"
    render_mod.render_from_plan(md_path=md, plan=plan, output_path=out,
                                theme=get_theme("midnight"))
    assert "14141C" in _full_bleed_fill_hexes(out)
```

(Adjust each `params` dict to match what the renderer actually reads — read each renderer's `params.get(...)` keys first. The assertion is the invariant; the params just need to be valid enough to render.)

- [ ] **Step 2: Run to verify the heavy renderers fail the dark-canvas assertion**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_named_layout_theming.py -q`
Expected: the parametrized cases for heavy renderers FAIL (still white canvas) until fixed. (cards-grid may already pass from Task 4 if it's simple — fine.)

- [ ] **Step 3: Theme each heavy renderer**

For EACH of `stat_callouts_right.py, cards_heterogeneous.py, vertical_timeline.py, three_pillars.py, cards_triple.py, timeline.py, bg_flip.py`:
1. Read the file. Replace its `_set_bg(slide, WHITE_RGB)` (or equivalent background paint) with `_set_bg(slide, palette.canvas_rgb)`.
2. Add `on_dark=palette.on_dark` to its `_add_chrome(...)` call.
3. Replace hardcoded body/label text `INK_RGB` with `palette.text_rgb`, and hardcoded `MUTED_RGB` secondary text with `palette.muted_rgb`.
4. Replace hardcoded card/tile fills `PAPER_RGB` with `palette.surface_rgb`.
5. Leave brand-accent usage (`accent_rgb`, theme accents, the section-color cycle) untouched — accents read on both canvases.
6. Special cases:
   - `bg_flip.py` is *intentionally* a dark-inverted emphasis layout. Under a dark theme it should stay coherent: set its canvas from `palette` only if that keeps the inversion meaningful; if `bg_flip` already paints `DARK_BG_RGB` and white text, the simplest correct behavior is to leave its dark background but ensure it doesn't clash (it won't — it's dark). Decide by reading; if it already renders dark, only swap its text to `palette.text_rgb` when `palette.on_dark` is False is unnecessary — document the decision in the report.
   - `vertical_timeline.py` / `timeline.py`: the connector line/dots use a rule or muted color — map those to `palette.rule_rgb` / `palette.muted_rgb`.

- [ ] **Step 4: Run the theming tests + full suite**

Run: `cd ~/arcadia/superstack/skills/build-pptx && ~/miniconda3/envs/deepdream/bin/python -m pytest tests/test_named_layout_theming.py -q && ~/miniconda3/envs/deepdream/bin/python -m pytest -q`
Expected: all theming cases pass; full suite green. Restore fixtures (scoped).

- [ ] **Step 5: Verify strict parity STILL holds**

Re-run the Task 2 Step 6 parity harness. Expected: `PARITY OK`.

- [ ] **Step 6: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/layouts/*.py skills/build-pptx/tests/test_named_layout_theming.py
git commit -m "feat(build-pptx): theme color-heavy named layouts (stats/cards/timeline/pillars/bg-flip)"
```

---

## Task 6: `composition` layout + final theming sweep

**Goal:** Theme the `composition` fallback layout (arbitrary rows × blocks) and grep for any remaining hardcoded `WHITE_RGB` background / `INK_RGB` text in renderers.

**Files:** `composition.py` (+ any stragglers found by grep)

- [ ] **Step 1: Theme composition.py**

Read `skills/build-pptx/layouts/composition.py`. Apply the same transformation: `_set_bg(slide, palette.canvas_rgb)`, `on_dark=palette.on_dark` on chrome, block text/surface via `palette`. Composition draws blocks (text/card/image); route their fills/text through `palette.surface_rgb` / `palette.text_rgb`.

- [ ] **Step 2: Grep for stragglers**

Run:
```bash
cd ~/arcadia/superstack/skills/build-pptx/layouts
grep -nE "_set_bg\(slide, WHITE_RGB\)" *.py
grep -nE "color_rgb=INK_RGB" *.py
```
Expected: no `_set_bg(slide, WHITE_RGB)` remaining in any themed renderer (they should all use `palette.canvas_rgb`). For each remaining `color_rgb=INK_RGB` on body text (not on intentionally-fixed elements), decide whether it should be `palette.text_rgb`. Fix stragglers.

- [ ] **Step 3: Full suite + parity**

Run the full suite and the parity harness (Task 2 Step 6). Expected: green + `PARITY OK`. Restore fixtures (scoped).

- [ ] **Step 4: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/layouts/composition.py skills/build-pptx/layouts/*.py
git commit -m "feat(build-pptx): theme composition layout + sweep remaining hardcoded colors"
```

---

## Task 7: Real-deck smoke test — dark deck, named layouts only

**Goal:** Prove that a real research deck, built in expressive mode with a dark theme using ONLY named layouts (no freeform), renders cohesively dark.

**Files:** none (verification only); work on a `/tmp` copy so the source deck stays pristine.

- [ ] **Step 1: Copy the richest real markdown deck to /tmp**

The `pres/` dir the user mentioned has only a `.pptx`/`.pdf` (no markdown), so use the richest *markdown* deck: the RSNA comprehensive deck (23 slides, figures + tables + stat cards).

```bash
SRC=~/arcadia/brainlab/projects/ad/agf/results/2026-05-02_rsna-comprehensive
DST=/tmp/nlt_smoke
rm -rf $DST && mkdir -p $DST/deck
cp "$SRC/deck/deck.md" $DST/deck/deck.md
rm -f $DST/deck/deck.md.layout.json
cd "$SRC"
grep -oE '\]\(\.\./[^)]+\)' deck/deck.md | sed -E 's/^\]\(\.\.\///; s/\)$//' | while read f; do
  mkdir -p "$DST/$(dirname "$f")"; cp "$f" "$DST/$f"
done
```

- [ ] **Step 2: Build it expressive with a forced dark theme, NO freeform**

Generate the rule-based plan (named layouts only — no freeform), then force a dark theme into the sidecar, then render with QA:
```bash
cd ~/arcadia/superstack/skills/build-pptx
PY=~/miniconda3/envs/deepdream/bin/python
$PY build.py --input /tmp/nlt_smoke/deck/deck.md --output /tmp/nlt_smoke/deck.pptx --mode expressive --plan-only
$PY - <<'PY'
import json
p="/tmp/nlt_smoke/deck/deck.md.layout.json"
d=json.load(open(p)); d["theme"]="midnight"
# confirm there are NO freeform slides — this test is about NAMED layouts
assert all(s["kind"]!="freeform" for s in d["slides"]), "expected named layouts only"
json.dump(d, open(p,"w"), indent=2)
print("kinds:", sorted({s["kind"] for s in d["slides"]}))
PY
$PY build.py --input /tmp/nlt_smoke/deck/deck.md --output /tmp/nlt_smoke/deck.pptx --qa
```
Expected: `wrote ...deck.pptx` + `QA images (N)` under `/tmp/nlt_smoke/deck_qa/`.

- [ ] **Step 3: Visually confirm cohesive dark**

Read several QA PNGs (cover, a `content-text` slide, a `figure-with-aside` slide, a `table-with-takeaway` slide, a `cards`/`stats` slide, a section divider). Confirm: every content slide has the dark `#14141C` canvas, white/legible text, accent bars/hairlines visible, and figures/tables readable on dark. There should be NO white content slides. Note any slide where text is illegible or an element didn't invert, and fix the responsible renderer (loop back to Task 4/5/6 for that renderer, re-render, re-check).

- [ ] **Step 4: Final full suite + parity + commit any fixes**

Run the full suite and the parity harness one last time. Expected: green + `PARITY OK`. If Step 3 required renderer fixes, commit them:
```bash
cd ~/arcadia/superstack
git add skills/build-pptx/layouts/*.py
git commit -m "fix(build-pptx): named-layout theming polish from dark-deck smoke test"
```

---

## Self-Review

**Spec coverage:**
- `Palette` value object resolved from theme, LIGHT == today → Task 1. ✓
- Threaded through render_from_plan + all 18 renderers → Task 2. ✓
- Shared helpers palette-aware (`_add_card`, `_render_paragraph_block`, `_add_chrome` already has `on_dark`) → Tasks 3, 4. ✓
- Simple renderers themed → Task 4. ✓
- Color-heavy renderers themed → Task 5. ✓
- composition + straggler sweep → Task 6. ✓
- Canvas painted on every content slide under a non-light theme (via each renderer's `_set_bg(palette.canvas_rgb)`) → Tasks 4-6. ✓
- Strict-mode byte parity verified after plumbing and again at the end → Task 2 Step 6, Task 4 Step 5, Task 5 Step 5, Task 6 Step 3, Task 7 Step 4. ✓
- Real dark deck of NAMED layouts confirmed cohesive → Task 7. ✓

**Placeholder scan:** No TBD/TODO. Steps that say "read the file then apply" (Tasks 3/5/6) are necessary because the per-renderer color constants vary; each specifies the exact transformation (swap `_set_bg` arg, add `on_dark=palette.on_dark`, map INK/MUTED/PAPER → palette fields) rather than leaving it open.

**Type consistency:** `Palette` fields (`canvas_rgb, text_rgb, muted_rgb, surface_rgb, rule_rgb, on_dark`) are used consistently in `palette.py`, `render.py` (`palette_for_theme`), and every renderer. `palette=LIGHT` default matches the `LIGHT` constant defined in Task 1. `_add_card(surface_rgb=, text_rgb=)` and `_render_paragraph_block(text_rgb=)` overrides match how Task 4 calls them. The parity harness uses the existing tag `build-skills-v7.2-pre-expressive`.

**Circular-import check:** `palette.py` imports from `layouts._common` (a leaf). Renderers in `layouts/*.py` import `palette`. `palette` does NOT import any renderer, so no cycle. `render.py` imports `palette_for_theme` lazily inside the function (as Task 2 specifies), consistent with its existing lazy-import style.
