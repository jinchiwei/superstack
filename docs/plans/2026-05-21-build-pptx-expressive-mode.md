# build-pptx Expressive Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two modes to build-pptx — `expressive` (new default: themed + guided-freeform, Anthropic-pptx aesthetic) and `strict` (byte-identical to today's rules-based named-layout behavior, the revert path) — plus a theme system with uncapped supplementary hues and a `--qa` visual-inspection loop.

**Architecture:** Gated single pipeline. A `--mode` flag (recorded in the `.layout.json` sidecar) selects behavior. Expressive-only logic lives in a new `expressive.py` module that strict mode never calls. Themes are resolved once at plan-generation, frozen in the sidecar, and realized through (a) a full-bleed canvas paint + chrome text-inversion on freeform slides, and (b) supplementary hue constants injected into the freeform AST sandbox namespace. Brand **fonts** (Geist / Geist Mono) and the brand-4 accents stay locked; themes only *add* hues. The engine remains python-pptx. Determinism is preserved because mode + theme + every freeform snippet are frozen in the sidecar.

**Tech Stack:** Python, python-pptx, the existing `plan.py` / `render.py` / `layouts/_sandbox.py` infrastructure, pytest. QA loop shells out to LibreOffice (`soffice --headless`) + poppler (`pdftoppm`).

**Key design decision (scope boundary):** Expressive mode *biases toward guided freeform* (per the user: "give it more freedom/leeway to do its own thing"). Because the dark-canvas / moody aesthetic the user liked is realized through freeform snippets (which can paint full-bleed backgrounds and use any exposed hue), we do **not** need to retrofit the 15 named layouts for dark canvases in v1. Dark-canvas support is wired through `_add_chrome` (one function) + the freeform path only. Named layouts keep their light-canvas design and remain the strict-mode workhorse and the expressive fast-floor for trivially-shaped slides. Full dark-canvas support for every named layout is explicitly deferred (see "Deferred / follow-up" at the end).

---

## File Structure

**New files:**
- `skills/build-pptx/themes.py` — `Theme` dataclass + `THEMES` registry + `pick_theme(seed)` / `get_theme(name)`. Pure data + selection; no rendering.
- `skills/build-pptx/expressive.py` — expressive-only glue: `resolve_theme(plan, shake)`. Strict mode never imports this.
- `skills/build-pptx/qa.py` — `render_to_images(pptx_path, out_dir)`: pptx → PDF (soffice) → per-slide PNGs (pdftoppm). Returns the list of PNG paths.
- `skills/build-pptx/tests/test_mode_flag.py`
- `skills/build-pptx/tests/test_themes.py`
- `skills/build-pptx/tests/test_qa_render.py`
- `skills/build-pptx/tests/test_plan_prompt_guidance.py`

**Modified files:**
- `skills/build-pptx/plan.py` — add `mode` + `theme` fields to `Plan`.
- `skills/build-pptx/build.py` — `--mode` arg, mode/theme resolution, thread into render.
- `skills/build-pptx/render.py` — accept resolved `Theme`; paint canvas + inject theme into freeform params.
- `skills/build-pptx/layouts/_sandbox.py` — inject `THEME_RGBS` / `THEME_HEXES` / `CANVAS_BG_RGB` / `ON_DARK` into the freeform globals.
- `skills/build-pptx/layouts/freeform.py` — read theme palette + on_dark from params, pass to sandbox + chrome.
- `skills/build-pptx/layouts/_common.py` — add `on_dark: bool=False` to `_add_chrome` (defaults preserve all existing callers).
- `skills/build-pptx/plan_prompt.md` — design-principles section + mode-aware rubric.
- `skills/build-pptx/SKILL.md` — document `--mode`, themes, `--qa` loop.

---

## Task 0: Preflight — branch + stable revert tag

**Files:** none (git only)

- [ ] **Step 1: Confirm clean tree on main**

Run: `git -C ~/arcadia/superstack status --short`
Expected: empty output (clean).

- [ ] **Step 2: Tag the current known-good state**

```bash
git -C ~/arcadia/superstack tag build-skills-v7.2-pre-expressive
```
This guarantees the strict-mode revert: `git checkout build-skills-v7.2-pre-expressive -- skills/build-pptx/` restores today's behavior wholesale.

- [ ] **Step 3: Create the feature branch**

```bash
git -C ~/arcadia/superstack checkout -b exp/pptx-expressive-mode
```
Expected: `Switched to a new branch 'exp/pptx-expressive-mode'`.

---

## Task 1: Mode flag + sidecar fields + isolation skeleton

**Files:**
- Modify: `skills/build-pptx/plan.py:101-127` (the `Plan` dataclass + `from_json`)
- Modify: `skills/build-pptx/build.py:1219-1322` (argparse + plan path)
- Create: `skills/build-pptx/expressive.py`
- Test: `skills/build-pptx/tests/test_mode_flag.py`

- [ ] **Step 1: Write the failing test**

Create `skills/build-pptx/tests/test_mode_flag.py`:

```python
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plan import Plan, SlideEntry


def test_plan_defaults_to_expressive():
    p = Plan(deck_md_hash="abc")
    assert p.mode == "expressive"
    assert p.theme is None


def test_plan_roundtrips_mode_and_theme():
    p = Plan(deck_md_hash="abc", mode="strict", theme="midnight",
             slides=[SlideEntry(slide_id="h1-x", kind="content-text")])
    restored = Plan.from_json(p.to_json())
    assert restored.mode == "strict"
    assert restored.theme == "midnight"
    assert restored.slides[0].slide_id == "h1-x"


def test_old_sidecar_without_mode_loads_with_defaults():
    # Sidecars written before this feature have no mode/theme keys.
    legacy = json.dumps({
        "version": 1, "deck_md_hash": "abc", "shake_seed": None,
        "slides": [{"slide_id": "h1-x", "kind": "content-text",
                    "params": {}, "content_hash": ""}],
    })
    restored = Plan.from_json(legacy)
    assert restored.mode == "expressive"
    assert restored.theme is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_mode_flag.py -v`
Expected: FAIL — `AttributeError: 'Plan' object has no attribute 'mode'`.

- [ ] **Step 3: Add the fields to the `Plan` dataclass**

In `skills/build-pptx/plan.py`, modify the `Plan` dataclass (currently lines 109-127):

```python
@dataclass
class Plan:
    version: int = 1
    deck_md_hash: str = ""    # sha256 of the source markdown for staleness check
    shake_seed: str | None = None
    mode: str = "expressive"  # "expressive" (themed+guided-freeform) | "strict" (rules-based, revert path)
    theme: str | None = None  # name of the chosen theme (expressive only); None in strict
    slides: list[SlideEntry] = field(default_factory=list)

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to JSON. Sorted keys for deterministic output."""
        return json.dumps(asdict(self), indent=indent, sort_keys=True,
                          ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Plan":
        """Parse from JSON; tolerates missing fields with defaults."""
        data = json.loads(s)
        slides_raw = data.pop("slides", [])
        slides = [SlideEntry(**e) for e in slides_raw]
        # Drop any unknown top-level keys so a future sidecar can't crash an
        # older Plan; known fields fall back to dataclass defaults if absent.
        known = {"version", "deck_md_hash", "shake_seed", "mode", "theme"}
        data = {k: v for k, v in data.items() if k in known}
        return cls(slides=slides, **data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_mode_flag.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Create the expressive isolation module**

Create `skills/build-pptx/expressive.py`:

```python
"""expressive.py — expressive-mode-only glue for build-pptx.

Strict mode MUST NOT import or call anything in this module. Keeping the
expressive logic isolated here is the safety boundary: a bug in theming or
guided-freeform selection cannot affect a strict-mode render, which is the
byte-for-byte revert path.
"""

from __future__ import annotations

from plan import Plan
from themes import Theme, get_theme, pick_theme


def resolve_theme(plan: Plan) -> Theme | None:
    """Return the Theme for this plan, or None if not applicable.

    - strict mode -> always None (no theming).
    - expressive mode -> the theme named in the sidecar if present, else a
      deterministic pick seeded by shake_seed (so a deck's theme is stable
      across re-renders but rerolls on --shake).
    """
    if plan.mode != "expressive":
        return None
    if plan.theme:
        return get_theme(plan.theme)
    return pick_theme(plan.shake_seed)
```

Note: `themes.py` does not exist yet (Task 2). This import will fail until Task 2 lands. That is fine — `expressive.py` is only imported lazily inside the expressive branch of `build.py` (Step 6), and Task 1's tests do not import it. A guard test is added in Task 2.

- [ ] **Step 6: Add `--mode` to argparse and resolve effective mode**

In `skills/build-pptx/build.py`, add the argument after the `--use-blocks` block (after line 1247, before `args = ap.parse_args()`):

```python
    ap.add_argument(
        "--mode",
        dest="mode",
        choices=["expressive", "strict"],
        default=None,
        help=(
            "Deck construction mode. 'expressive' (default): themed + "
            "guided-freeform, Anthropic-pptx aesthetic. 'strict': rules-based "
            "named-layout behavior, the revert path. If omitted, an existing "
            "sidecar's recorded mode wins; otherwise defaults to expressive."
        ),
    )
```

Then in the plan path, immediately after `final_plan = merge_with_existing(default_plan, existing_plan)` (line 1287), insert mode resolution:

```python
    # Resolve effective mode: explicit flag > existing sidecar > default.
    effective_mode = (
        args.mode
        or (existing_plan.mode if existing_plan else None)
        or "expressive"
    )
    final_plan.mode = effective_mode
```

- [ ] **Step 7: Thread mode into the default-plan inference and render call**

Still in `build.py`, update the `_infer_default_plan(...)` call (line 1281) to pass mode, and update `render_from_plan(...)` (line 1317) to pass the resolved theme. Replace lines 1280-1320 region's render call so it reads:

```python
    # Build a default plan (rule-based layout choice from chunk content)
    default_plan = _infer_default_plan(
        md_text=md_text, chunks=chunks, slide_records=slide_records,
        deck_md_hash=deck_md_hash, base_dir=md_path.parent,
    )

    # Merge with existing
    final_plan = merge_with_existing(default_plan, existing_plan)

    # Resolve effective mode: explicit flag > existing sidecar > default.
    effective_mode = (
        args.mode
        or (existing_plan.mode if existing_plan else None)
        or "expressive"
    )
    final_plan.mode = effective_mode

    # Resolve theme (expressive only). Freeze the chosen theme name in the plan
    # so re-renders are deterministic.
    theme = None
    if effective_mode == "expressive":
        from expressive import resolve_theme
        theme = resolve_theme(final_plan)
        final_plan.theme = theme.name if theme else None
    else:
        final_plan.theme = None
```

Then update the existing `render_from_plan(...)` call (line 1317) to forward the theme:

```python
    # Render
    from render import render_from_plan
    render_from_plan(
        md_path=md_path, plan=final_plan, output_path=output_path,
        no_cover=args.no_cover, no_end=args.no_end, theme=theme,
    )
```

Note: `render_from_plan` does not yet accept `theme` — that parameter is added in Task 2 Step 6. To keep this task's commit runnable, add the parameter signature stub now: in `render.py` change the signature (line 202) to `def render_from_plan(*, md_path, plan, output_path, no_cover=False, no_end=False, theme=None):` and ignore `theme` for now (Task 2 wires it up).

- [ ] **Step 8: Verify strict mode is byte-identical to legacy on a fixture**

Run:
```bash
cd ~/arcadia/superstack/skills/build-pptx
python build.py --input tests/fixture_named_v7.md --output /tmp/strict.pptx --mode strict --shake
python -c "import json; d=json.load(open('tests/fixture_named_v7.md.layout.json')); print('mode=', d.get('mode'), 'theme=', d.get('theme'))"
```
Expected: prints `mode= strict theme= None`, and `wrote /tmp/strict.pptx`. (The fixture sidecar is regenerated; restore it with `git checkout -- tests/fixture_named_v7.md.layout.json` after eyeballing.)

- [ ] **Step 9: Run the full suite to confirm no regressions**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest -q`
Expected: all pass (themes/qa tests don't exist yet).

- [ ] **Step 10: Restore the fixture sidecar touched in Step 8 and commit**

```bash
cd ~/arcadia/superstack
git checkout -- skills/build-pptx/tests/fixture_named_v7.md.layout.json
git add skills/build-pptx/plan.py skills/build-pptx/build.py skills/build-pptx/render.py skills/build-pptx/expressive.py skills/build-pptx/tests/test_mode_flag.py
git commit -m "feat(build-pptx): add --mode expressive|strict with sidecar persistence and isolation skeleton"
```

---

## Task 2: Theme system + sandbox hue injection + dark-canvas freeform

**Files:**
- Create: `skills/build-pptx/themes.py`
- Test: `skills/build-pptx/tests/test_themes.py`
- Modify: `skills/build-pptx/layouts/_sandbox.py:201-303` (`build_safe_globals`, `run`)
- Modify: `skills/build-pptx/layouts/freeform.py` (whole file)
- Modify: `skills/build-pptx/layouts/_common.py:569` (`_add_chrome` signature — add `on_dark`)
- Modify: `skills/build-pptx/render.py:202-292` (`render_from_plan` theme plumbing)

- [ ] **Step 1: Write the failing test for `themes.py`**

Create `skills/build-pptx/tests/test_themes.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from themes import THEMES, Theme, get_theme, pick_theme

BRAND4 = {"#40E0D0", "#FF1493", "#F0C840", "#8A2BE2"}


def test_registry_nonempty_and_well_formed():
    assert len(THEMES) >= 4
    for name, t in THEMES.items():
        assert isinstance(t, Theme)
        assert t.name == name
        assert t.bg_hex.startswith("#") and len(t.bg_hex) == 7
        # accent_order must be a permutation drawn from the brand-4 palette
        assert set(t.accent_order) <= BRAND4
        assert len(t.accent_order) == 4
        # supplementary hues are uncapped but must be valid hex
        for h in t.supplementary:
            assert h.startswith("#") and len(h) == 7


def test_pick_theme_is_deterministic_by_seed():
    a = pick_theme("seed-123")
    b = pick_theme("seed-123")
    assert a.name == b.name


def test_pick_theme_none_seed_returns_a_theme():
    assert isinstance(pick_theme(None), Theme)


def test_get_theme_by_name():
    name = next(iter(THEMES))
    assert get_theme(name).name == name


def test_get_theme_unknown_falls_back_gracefully():
    # Unknown name should not crash a render; return a valid Theme.
    t = get_theme("does-not-exist")
    assert isinstance(t, Theme)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_themes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'themes'`.

- [ ] **Step 3: Implement `themes.py`**

Create `skills/build-pptx/themes.py`:

```python
"""themes.py — named visual themes for build-pptx expressive mode.

A Theme controls the *canvas and supplementary palette*, never the brand
identity. Fonts are always Geist / Geist Mono (enforced elsewhere). The
brand-4 accents (turquoise/deeppink/amber/blueviolet) are always available;
`accent_order` only changes which leads. `supplementary` adds extra hues
(uncapped — planner's discretion) that read well on the theme's canvas.

Theme selection is deterministic: pick_theme(seed) hashes the seed so a
deck's theme is stable across re-renders and rerolls only on --shake.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

TURQUOISE = "#40E0D0"
DEEPPINK = "#FF1493"
AMBER = "#F0C840"
BLUEVIOLET = "#8A2BE2"


@dataclass(frozen=True)
class Theme:
    name: str
    canvas: str          # "light" | "dark" | "tinted"
    bg_hex: str          # full-bleed canvas color
    on_dark: bool        # True -> chrome text inverts to light
    accent_order: list[str] = field(default_factory=list)   # brand-4 permutation
    supplementary: list[str] = field(default_factory=list)  # extra hues (uncapped)


# Inspired by Anthropic's pptx palettes, recolored to coexist with the brand-4
# accents and tuned so supplementary hues read on each theme's canvas.
THEMES: dict[str, Theme] = {
    "midnight": Theme(
        name="midnight", canvas="dark", bg_hex="#14141C", on_dark=True,
        accent_order=[TURQUOISE, BLUEVIOLET, DEEPPINK, AMBER],
        supplementary=["#5EEAD4", "#A78BFA", "#FBCFE8"],
    ),
    "slate": Theme(
        name="slate", canvas="dark", bg_hex="#1E293B", on_dark=True,
        accent_order=[TURQUOISE, AMBER, DEEPPINK, BLUEVIOLET],
        supplementary=["#38BDF8", "#FB7185", "#FACC15"],
    ),
    "forest": Theme(
        name="forest", canvas="dark", bg_hex="#0F1E17", on_dark=True,
        accent_order=[AMBER, TURQUOISE, BLUEVIOLET, DEEPPINK],
        supplementary=["#34D399", "#A3E635", "#FDE68A"],
    ),
    "paper": Theme(
        name="paper", canvas="light", bg_hex="#FFFFFF", on_dark=False,
        accent_order=[DEEPPINK, TURQUOISE, BLUEVIOLET, AMBER],
        supplementary=["#0F766E", "#9D174D", "#6D28D9"],
    ),
    "bone": Theme(
        name="bone", canvas="tinted", bg_hex="#F6F4EE", on_dark=False,
        accent_order=[BLUEVIOLET, DEEPPINK, TURQUOISE, AMBER],
        supplementary=["#9A3412", "#1E3A8A", "#115E59"],
    ),
}

_DEFAULT = "midnight"


def get_theme(name: str | None) -> Theme:
    """Look up a theme by name; fall back to the default for unknown/None."""
    if name and name in THEMES:
        return THEMES[name]
    return THEMES[_DEFAULT]


def pick_theme(seed: str | None) -> Theme:
    """Deterministically choose a theme from the seed. None -> default."""
    if not seed:
        return THEMES[_DEFAULT]
    names = sorted(THEMES.keys())
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    return THEMES[names[h % len(names)]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_themes.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Add a guard test that `expressive.resolve_theme` works end-to-end**

Append to `skills/build-pptx/tests/test_themes.py`:

```python
def test_resolve_theme_strict_is_none():
    from plan import Plan
    from expressive import resolve_theme
    assert resolve_theme(Plan(mode="strict")) is None


def test_resolve_theme_expressive_picks_and_is_stable():
    from plan import Plan
    from expressive import resolve_theme
    p = Plan(mode="expressive", shake_seed="abc")
    t1 = resolve_theme(p)
    t2 = resolve_theme(p)
    assert t1 is not None and t1.name == t2.name


def test_resolve_theme_honors_frozen_name():
    from plan import Plan
    from expressive import resolve_theme
    assert resolve_theme(Plan(mode="expressive", theme="forest")).name == "forest"
```

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_themes.py -v`
Expected: PASS (9 passed).

- [ ] **Step 6: Inject theme palette into the freeform sandbox**

In `skills/build-pptx/layouts/_sandbox.py`, modify `build_safe_globals` (line 201) to accept a theme palette and expose it. Change the signature and add entries to the returned dict:

```python
def build_safe_globals(
    *,
    slide,
    accent_hex: str,
    body_top: float,
    body_h: float,
    body_l: float,
    body_w: float,
    body_bottom: float,
    theme_hexes: list[str] | None = None,
    canvas_bg_hex: str | None = None,
    on_dark: bool = False,
) -> dict:
    """Return a constrained globals dict for exec()ing a freeform snippet.

    theme_hexes: supplementary palette hues (uncapped) for this deck's theme.
    canvas_bg_hex: the theme's full-bleed background color (None in strict).
    on_dark: True when the theme uses a dark canvas (snippets should use light
             text). Exposed so freeform code can branch on it.
    """
    accent_rgb = _rgb(accent_hex)
    theme_hexes = theme_hexes or []
    theme_rgbs = [_rgb(h) for h in theme_hexes]
    canvas_bg_rgb = _rgb(canvas_bg_hex) if canvas_bg_hex else None

    g = {
        # Slide object
        "slide": slide,
        # Accent colour
        "accent_hex": accent_hex,
        "accent_rgb": accent_rgb,
        # Geometry
        "body_top": body_top,
        "body_h": body_h,
        "body_l": body_l,
        "body_w": body_w,
        "body_bottom": body_bottom,
        # Colour constants (RGBColor)
        "INK_RGB": INK_RGB,
        "WHITE_RGB": WHITE_RGB,
        "TURQUOISE_RGB": TURQUOISE_RGB,
        "DEEPPINK_RGB": DEEPPINK_RGB,
        "AMBER_RGB": AMBER_RGB,
        "BLUEVIOLET_RGB": BLUEVIOLET_RGB,
        "DIM_RGB": DIM_RGB,
        "MUTED_RGB": MUTED_RGB,
        "RULE_RGB": RULE_RGB,
        "DARK_BG_RGB": DARK_BG_RGB,
        "PAPER_RGB": PAPER_RGB,
        # Theme palette (supplementary hues — uncapped; empty list in strict)
        "THEME_HEXES": list(theme_hexes),
        "THEME_RGBS": theme_rgbs,
        "CANVAS_BG_RGB": canvas_bg_rgb,
        "ON_DARK": on_dark,
        # Drawing primitives
        "_add_rect": _add_rect,
        "_add_text": _add_text,
        "_add_card": _add_card,
        "_add_table": _add_table,
        "_add_flat_shape": _add_flat_shape,
        "_render_paragraph_block": _render_paragraph_block,
        "_render_media_block": _render_media_block,
        "_rgb": _rgb,
        # pptx utilities
        "Inches": Inches,
        "Pt": Pt,
        "Emu": Emu,
        "RGBColor": RGBColor,
        "MSO_SHAPE": MSO_SHAPE,
        "PP_ALIGN": PP_ALIGN,
        "MSO_ANCHOR": MSO_ANCHOR,
        # Branding constants
        "MONO_FONT": branding.MONO_FONT,
        "SANS_FONT": branding.SANS_FONT,
        "TURQUOISE": branding.TURQUOISE,
        "DEEPPINK": branding.DEEPPINK,
        "AMBER": branding.AMBER,
        "BLUEVIOLET": branding.BLUEVIOLET,
        # Minimal builtins — no open, exec, eval, getattr, etc.
        "__builtins__": _SAFE_BUILTINS,
    }
    return g
```

Then thread the new kwargs through `run` (line 275):

```python
def run(
    *,
    code: str,
    slide,
    accent_hex: str,
    body_top: float,
    body_h: float,
    body_l: float,
    body_w: float,
    body_bottom: float,
    theme_hexes: list[str] | None = None,
    canvas_bg_hex: str | None = None,
    on_dark: bool = False,
) -> None:
    """Validate and execute a freeform snippet inside a constrained namespace."""
    validate_code(code)
    safe_globals = build_safe_globals(
        slide=slide,
        accent_hex=accent_hex,
        body_top=body_top,
        body_h=body_h,
        body_l=body_l,
        body_w=body_w,
        body_bottom=body_bottom,
        theme_hexes=theme_hexes,
        canvas_bg_hex=canvas_bg_hex,
        on_dark=on_dark,
    )
    exec(code, safe_globals)  # noqa: S102 — intentional, validated above
```

- [ ] **Step 7: Add `on_dark` to `_add_chrome`**

Read `skills/build-pptx/layouts/_common.py` around line 569 to see the full `_add_chrome` body and which color constants it uses for the title / lede / footer text. Add an `on_dark: bool = False` keyword parameter (default keeps every existing caller unchanged). Inside, when `on_dark` is True, swap the light-mode text colors for light ones:
- title text: use `WHITE_RGB` instead of `INK_RGB`
- lede text: use `WHITE_RGB` (or a light off-white) instead of its current dim/ink color
- footer text: use a light muted (e.g., `RULE_RGB`) instead of `DIM_RGB`
- keep the accent bar / hairline using the accent color (reads on both canvases)

Make the minimal edit: introduce locals at the top of `_add_chrome` like
`title_rgb = WHITE_RGB if on_dark else INK_RGB` and substitute them at the existing `_add_text(...)` chrome calls. Do not change geometry.

- [ ] **Step 8: Wire theme through `freeform.py`**

Replace `skills/build-pptx/layouts/freeform.py` with:

```python
"""freeform layout — runs Claude-written python in a sandbox to draw
arbitrary shapes on the slide. Chrome (title/lede/footer/accent bar) is
still drawn by _add_chrome so brand identity stays consistent. In expressive
mode a theme may supply a dark canvas + supplementary hues."""

from __future__ import annotations

from layouts._common import (
    _add_chrome, _add_rect, _add_text, DEEPPINK_RGB,
)
from layouts._sandbox import run as run_sandboxed, SandboxError
import branding


def render(slide, *, params: dict, accent_rgb, footer_kwargs: dict) -> None:
    """params:
        title:         str
        lede:          str
        code:          str        # python snippet, runs in sandbox
        section_label: str|None   # informational
        _theme:        dict|None  # injected by render_from_plan; never from the planner
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    code = params.get("code", "")

    theme = params.get("_theme") or {}
    on_dark = bool(theme.get("on_dark"))
    canvas_bg_hex = theme.get("bg_hex")
    theme_hexes = theme.get("supplementary") or []

    # Paint the full-bleed canvas FIRST so chrome + snippet draw on top.
    if on_dark and canvas_bg_hex:
        _add_rect(slide, left=0, top=0, width=13.333, height=7.5,
                  fill_rgb=_to_rgb(canvas_bg_hex))

    title_wraps = len(title) > 30

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide, title=title, lede=lede, footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=bool(title),
        title_wraps=title_wraps,
        use_side_by_side=False,
        on_dark=on_dark,
    )

    if not code.strip():
        return  # nothing to draw — chrome only

    try:
        hex_part = str(accent_rgb)
    except Exception:
        hex_part = "40E0D0"
    accent_hex = "#" + hex_part.upper().lstrip("#")[:6]

    try:
        run_sandboxed(
            code=code, slide=slide, accent_hex=accent_hex,
            body_top=body_top, body_h=body_h,
            body_l=body_l, body_w=body_w, body_bottom=body_bottom,
            theme_hexes=theme_hexes, canvas_bg_hex=canvas_bg_hex,
            on_dark=on_dark,
        )
    except SandboxError as e:
        _add_text(slide,
                  f"[freeform code rejected: {e}]",
                  left=body_l, top=body_top,
                  width=body_w, height=0.5,
                  size=12, color_rgb=DEEPPINK_RGB,
                  font=branding.MONO_FONT, bold=True)
    except Exception as e:
        _add_text(slide,
                  f"[freeform runtime error: {type(e).__name__}: {e}]",
                  left=body_l, top=body_top,
                  width=body_w, height=0.5,
                  size=12, color_rgb=DEEPPINK_RGB,
                  font=branding.MONO_FONT, bold=True)


def _to_rgb(hex_str: str):
    from layouts._common import _rgb
    return _rgb(hex_str)
```

- [ ] **Step 9: Thread the resolved theme through `render_from_plan`**

In `skills/build-pptx/render.py`, the signature was stubbed to accept `theme=None` in Task 1 Step 7. Now use it. Inside the slide loop (after `params = entry.params or {}`, around line 253), inject a serializable theme dict into freeform params so `freeform.py` can read it:

```python
        params = entry.params or {}

        # Inject the resolved theme into freeform slides only. This dict is
        # added by the renderer, never by the planner, and is not persisted.
        if theme is not None and entry.kind == "freeform":
            params = dict(params)
            params["_theme"] = {
                "on_dark": theme.on_dark,
                "bg_hex": theme.bg_hex,
                "supplementary": list(theme.supplementary),
            }
```

(Leave the rest of the loop unchanged — named layouts ignore `_theme`.)

Also, when an expressive theme defines an `accent_order`, let it influence the section accent cycle. Just below `current_accent = branding.TURQUOISE` (line 242), add:

```python
    # Expressive themes may reorder which brand-4 accent leads.
    if theme is not None and theme.accent_order:
        current_accent = theme.accent_order[0]
```

- [ ] **Step 10: Write a render test for dark-canvas freeform**

Create the test in `skills/build-pptx/tests/test_themes.py` (append):

```python
def test_freeform_dark_canvas_renders_without_error(tmp_path):
    """A freeform slide under a dark theme paints a bg and runs the snippet."""
    import render as render_mod
    from plan import Plan, SlideEntry
    from themes import get_theme

    md = tmp_path / "deck.md"
    md.write_text(
        "---\ntitle: T\n---\n\n# Results\n\n## Headline\n\nLede.\n",
        encoding="utf-8",
    )
    code = ("_add_rect(slide, left=body_l, top=body_top, width=4, height=2, "
            "fill_rgb=THEME_RGBS[0] if THEME_RGBS else accent_rgb)\n"
            "_add_text(slide, 'hi', left=body_l, top=body_top, width=4, "
            "height=1, size=20, color_rgb=WHITE_RGB if ON_DARK else INK_RGB, "
            "font=MONO_FONT)")
    plan = Plan(mode="expressive", theme="midnight", slides=[
        SlideEntry(slide_id="h1-results/h2-headline", kind="freeform",
                   params={"title": "Headline", "lede": "Lede.",
                           "section_label": "Results", "code": code}),
    ])
    out = tmp_path / "out.pptx"
    render_mod.render_from_plan(
        md_path=md, plan=plan, output_path=out,
        theme=get_theme("midnight"),
    )
    assert out.exists() and out.stat().st_size > 0
```

- [ ] **Step 11: Run the suite**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_themes.py tests/test_sandbox_security.py tests/test_freeform_render.py -v`
Expected: all PASS. The security test must still pass — confirming the new globals (`THEME_RGBS` etc.) add data, not escape hatches.

- [ ] **Step 12: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/themes.py skills/build-pptx/layouts/_sandbox.py skills/build-pptx/layouts/freeform.py skills/build-pptx/layouts/_common.py skills/build-pptx/render.py skills/build-pptx/tests/test_themes.py
git commit -m "feat(build-pptx): theme system with uncapped supplementary hues, dark-canvas freeform, and sandbox palette injection"
```

---

## Task 3: Design-taste guidance + mode-aware rubric in plan_prompt.md

**Files:**
- Modify: `skills/build-pptx/plan_prompt.md` (add a Design principles section; make the rubric + freeform "When to use" mode-aware)
- Test: `skills/build-pptx/tests/test_plan_prompt_guidance.py`

- [ ] **Step 1: Write the failing test**

Create `skills/build-pptx/tests/test_plan_prompt_guidance.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROMPT = (ROOT / "plan_prompt.md").read_text(encoding="utf-8")


def test_has_design_principles_section():
    assert "## Design principles" in PROMPT


def test_documents_both_modes():
    assert "expressive" in PROMPT.lower()
    assert "strict" in PROMPT.lower()


def test_lists_anti_patterns():
    low = PROMPT.lower()
    assert "anti-pattern" in low
    # a few concrete anti-patterns we ported
    assert "centered body text" in low or "center body text" in low
    assert "text-only" in low


def test_documents_supplementary_palette_in_sandbox():
    assert "THEME_RGBS" in PROMPT
    assert "ON_DARK" in PROMPT


def test_plan_prompt_still_assembles():
    from plan import assemble_plan_prompt
    out = assemble_plan_prompt(
        md_text="# A\n\ntext\n",
        slide_records=[{"slide_id": "h1-a", "content_hash": "x",
                        "h1": "A", "h2": None, "chunk_html": "<h1>A</h1>"}],
    )
    assert "## Design principles" in out
    assert "h1-a" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_plan_prompt_guidance.py -v`
Expected: FAIL — `## Design principles` not found.

- [ ] **Step 3: Add the Design principles section to plan_prompt.md**

Insert this section in `skills/build-pptx/plan_prompt.md` immediately before `## Decision rubric` (line 370). Write the prose (ported and adapted from Anthropic's pptx design guidance, kept brand-locked):

````markdown
## Design principles

These principles shape *how* you choose and fill layouts. They apply most
strongly in **expressive mode** (the default), where you have latitude to
design slides. In **strict mode** you ignore the freeform bias below and pick
named layouts only (see the rubric).

### Mode awareness

- **expressive (default):** Bias toward *guided freeform* for any slide whose
  point benefits from a custom composition. Named layouts are a fast floor for
  trivially-shaped slides (a plain bullet list, a single figure, a simple
  table). When in doubt and the content has visual structure, design it with
  `freeform`. A deck may also carry a **theme** (see below) — honor its canvas
  and palette.
- **strict:** Never emit `freeform` or `composition`. Pick the best-fitting
  named layout for every slide. This is the proven, brand-locked path.

### The theme (expressive only)

The deck is rendered with one theme. The renderer paints the theme's canvas
on freeform slides and inverts chrome text on dark canvases automatically. In
your freeform snippets:

- `ON_DARK` (bool) — true when the canvas is dark; use `WHITE_RGB` for primary
  text and light tints for secondary text.
- `CANVAS_BG_RGB` — the canvas color (already painted for you on freeform
  slides; use it if you draw panels that should blend).
- `THEME_RGBS` / `THEME_HEXES` — the theme's **supplementary hues** (uncapped).
  Use them freely *in addition to* the brand-4 accents to add variety, color
  zones, data-series colors, and depth. There is no limit on how many you use.
- The brand-4 accents (`TURQUOISE_RGB`, `DEEPPINK_RGB`, `AMBER_RGB`,
  `BLUEVIOLET_RGB`) remain available and lead the palette.

Fonts never change: `MONO_FONT` (Geist Mono) for structural elements, headings,
numbers, labels; `SANS_FONT` (Geist) for reading prose.

### Anti-patterns — avoid these

- **Text-only slides.** A wall of bullets is the most common bland failure.
  Give content visual structure: cards, columns, a stat row, a figure, color
  zones. If a slide is only prose, ask whether it should be a freeform layout
  with hierarchy instead.
- **Centered body text.** Left-align body copy and bullets. Centering is for
  big numbers, single statements, and section breaks only.
- **Accent line directly under the title.** The chrome already provides the
  title treatment; do not draw a decorative rule immediately beneath it.
- **Uniform gray everything.** Use the theme palette to create emphasis and
  grouping. Flat brand color zones beat undifferentiated gray.
- **Cramped margins.** Respect generous whitespace; keep to the body region.
- **More than ~2 type sizes competing for attention** on one slide. Establish
  one clear focal hierarchy.
- **Drop shadows, gradients on shapes, Office-theme fills.** Stay flat — always
  use `_add_flat_shape`, never raw `add_shape`.

### Composition guidance (what good looks like)

- Establish a clear focal point per slide (the headline number, the key figure,
  the one-sentence claim).
- Group related items into cards or columns; use color to signal grouping.
- Pair a visual (figure / chart / big number) with a tight aside instead of
  prose-only.
- Use the theme's supplementary hues for secondary data, sub-labels, and
  accent zones so the deck feels designed, not templated.
- Keep one consistent left margin and a predictable vertical rhythm.
````

- [ ] **Step 4: Make the freeform "When to use" section mode-aware**

In `skills/build-pptx/plan_prompt.md`, the `#### When to use freeform` block (lines 282-300) currently says "Reach for freeform only when..." and "Don't use freeform for slides that fit a named layout." Replace that block with mode-aware guidance:

````markdown
#### When to use freeform

**Expressive mode (default):** Reach for `freeform` whenever a custom
composition serves the slide better than a named layout — which is often.
Named layouts remain the fast floor for trivially-shaped slides (a plain
bullet list, a single figure with a caption, a simple table). Prefer freeform
when the slide has visual structure worth designing: stat arrangements, color
zones, paired figure+commentary with custom geometry, connectors/arrows,
big-number focal slides, or anything that would lose its point inside a
template. Honor the theme (`ON_DARK`, `CANVAS_BG_RGB`, `THEME_RGBS`).

**Strict mode:** Never emit `freeform`. Use named layouts only.

In both modes, a freeform slide must stay inside the body region the chrome
hands you (`body_l`, `body_top`, `body_w`, `body_h`) and use only the sandbox
API.
````

- [ ] **Step 5: Make the Decision rubric mode-aware**

Read the `## Decision rubric` section (starts line 370). Add a leading paragraph that forks on mode:

````markdown
## Decision rubric

**First, honor the mode.**

- In **strict mode**, choose exclusively from the named layouts. Never select
  `freeform` or `composition`. Apply the per-kind rules below.
- In **expressive mode**, apply the Design principles above: bias toward
  guided `freeform` for slides with visual structure, and fall back to named
  layouts for trivially-shaped slides. The per-kind rules below still describe
  when each named layout is the right floor.

(Keep the existing rubric content that follows.)
````

- [ ] **Step 6: Run the suite**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_plan_prompt_guidance.py -v`
Expected: PASS (5 passed).

- [ ] **Step 7: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/plan_prompt.md skills/build-pptx/tests/test_plan_prompt_guidance.py
git commit -m "docs(build-pptx): port design-taste principles + mode-aware rubric into plan_prompt"
```

---

## Task 4: `--qa` visual-inspection loop

**Files:**
- Create: `skills/build-pptx/qa.py`
- Modify: `skills/build-pptx/build.py` (add `--qa` flag; call `qa.render_to_images` after render)
- Test: `skills/build-pptx/tests/test_qa_render.py`

- [ ] **Step 1: Install LibreOffice (prerequisite — currently missing)**

`soffice` is not on this machine; `pdftoppm` (poppler) is. Install LibreOffice:

```bash
brew install --cask libreoffice
```
Verify:
```bash
ls /Applications/LibreOffice.app/Contents/MacOS/soffice && echo "soffice OK"
which pdftoppm && echo "pdftoppm OK"
```
Expected: both print OK.

**Running the QA loop on a cluster (FAC / SCS — no sudo, Linux):**
`brew` is mac-only and **LibreOffice is NOT on conda-forge** (verified 2026-05-21:
no `libreoffice` package for linux-64 or osx). Routes that work without root (module system confirmed NOT available on FAC/SCS):
- **AppImage (primary route):** download the official LibreOffice
  AppImage, extract without FUSE, and use the unpacked binary:
  ```bash
  ./LibreOffice-*.AppImage --appimage-extract
  # soffice is then at: ./squashfs-root/program/soffice
  ```
  **Location matters — do NOT use the home dir.** The extracted tree is
  ~700MB–1GB and cluster home dirs are usually small quota'd NFS. The setup
  must be an **interactive step** (document this in SKILL.md, not a hardcoded
  path): Claude inspects the cluster for roomy non-home space (e.g. `/scratch`,
  group/project space, `$TMPDIR`), checks free space (`df -h`, quota), proposes
  a specific location outside home, and asks the user to confirm — or asks the
  user to name a path. Download + extract there, then either export
  `<location>/squashfs-root/program` onto `PATH` or extend
  `_SOFFICE_CANDIDATES` in `qa.py` to point at it.
- **poppler / pdftoppm:** this half *is* conda-installable —
  `conda install -c conda-forge poppler` (or `module load poppler`).
- **Zero-install alternative:** generate decks on the cluster, `scp` the `.pptx`
  to the mac, and run `--qa` here.

`qa.find_soffice()` checks bare `soffice`/`libreoffice` on `PATH`, so a
module-loaded or PATH-exported AppImage binary is discovered automatically. If
the AppImage is unpacked to a non-PATH location, add its `program/` dir to
`PATH` (or extend `_SOFFICE_CANDIDATES` in `qa.py`).

**Python deps:** run all `python ...` commands in this plan inside the
`deepdream` conda env (never base/system Python): `conda activate deepdream`
first, or call `~/miniconda3/envs/deepdream/bin/python`. `python-pptx` is
already pip-installed there.

- [ ] **Step 2: Write the failing test**

Create `skills/build-pptx/tests/test_qa_render.py`:

```python
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
    # Build a tiny 2-slide deck first.
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
    # Pure-logic: must not raise regardless of install state.
    result = qa.find_soffice()
    assert result is None or Path(result).exists()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_qa_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qa'`.

- [ ] **Step 4: Implement `qa.py`**

Create `skills/build-pptx/qa.py`:

```python
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
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir",
         str(out_dir), str(pptx_path)],
        check=True, capture_output=True, timeout=180,
    )
    pdf_path = out_dir / (pptx_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"LibreOffice did not produce {pdf_path}")

    # 2) pdf -> png per page
    prefix = out_dir / "slide"
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
        check=True, capture_output=True, timeout=180,
    )
    return sorted(out_dir.glob("slide-*.png"))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest tests/test_qa_render.py -v`
Expected: PASS — `test_find_soffice_returns_path_or_none` passes always; the render test passes if LibreOffice installed (Step 1), else skips.

- [ ] **Step 6: Add the `--qa` flag to build.py**

In `skills/build-pptx/build.py`, add the argument after `--mode` (Task 1 Step 6):

```python
    ap.add_argument("--qa", action="store_true",
                    help="after rendering, emit per-slide PNGs for visual "
                         "inspection (requires LibreOffice + poppler)")
```

Then after the successful render (`print(f"wrote {output_path}")`, line 1321), add:

```python
    if args.qa:
        from qa import render_to_images
        qa_dir = output_path.with_suffix("").parent / (output_path.stem + "_qa")
        try:
            pngs = render_to_images(output_path, qa_dir)
            print(f"QA images ({len(pngs)}):")
            for p in pngs:
                print(f"  {p}")
        except RuntimeError as e:
            print(f"QA skipped: {e}", file=sys.stderr)
```

- [ ] **Step 7: Smoke-test the flag end-to-end** (only meaningful if Step 1 done)

Run:
```bash
cd ~/arcadia/superstack/skills/build-pptx
python build.py --input tests/fixture_named_v7.md --output /tmp/qa_demo.pptx --mode strict --qa --shake
git checkout -- tests/fixture_named_v7.md.layout.json
```
Expected: prints `wrote /tmp/qa_demo.pptx` then `QA images (N):` with PNG paths under `/tmp/qa_demo_qa/`. If LibreOffice absent, prints `QA skipped: ...` (non-fatal).

- [ ] **Step 8: Run the full suite**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest -q`
Expected: all pass (QA render test skips if LibreOffice unavailable).

- [ ] **Step 9: Document the QA loop in SKILL.md**

In `skills/build-pptx/SKILL.md`, add a `## Visual QA loop (--qa)` section documenting:
- `--qa` renders the deck, then converts to per-slide PNGs under `<output>_qa/`.
- The agent should Read each PNG, check it against the **Design principles / anti-patterns** in `plan_prompt.md` and theme cohesion, then edit the `.layout.json` sidecar to fix issues and re-run (`python build.py --input ... --output ... --qa`).
- The loop repeats until the slides pass inspection. Determinism holds: fixes are frozen in the sidecar.
- Note the dependency: LibreOffice (`brew install --cask libreoffice`) + poppler.

Also document `--mode=expressive|strict` and the theme system in the existing flags section: expressive is the default; strict reproduces the prior named-layout behavior; themes are auto-picked (seeded by `shake_seed`) and frozen in the sidecar as `"theme"`; supplementary hues are uncapped.

- [ ] **Step 10: Commit**

```bash
cd ~/arcadia/superstack
git add skills/build-pptx/qa.py skills/build-pptx/build.py skills/build-pptx/SKILL.md skills/build-pptx/tests/test_qa_render.py
git commit -m "feat(build-pptx): add --qa visual-inspection loop (soffice+poppler render-to-images) and document expressive mode"
```

---

## Final integration check

- [ ] **Step 1: Full suite green**

Run: `cd ~/arcadia/superstack/skills/build-pptx && python -m pytest -q`
Expected: all pass / skips only for missing LibreOffice.

- [ ] **Step 2: Strict mode unchanged vs the pre-feature tag**

```bash
cd ~/arcadia/superstack/skills/build-pptx
python build.py --input tests/fixture_named_v7.md --output /tmp/new_strict.pptx --mode strict --shake
git checkout -- tests/fixture_named_v7.md.layout.json
git stash 2>/dev/null || true
git checkout build-skills-v7.2-pre-expressive -- . 2>/dev/null || true
# (manual) build the same fixture from the tagged code to /tmp/old_strict.pptx, then:
git checkout exp/pptx-expressive-mode -- . 2>/dev/null || true
git stash pop 2>/dev/null || true
```
Expected: strict-mode slide structure matches the tagged behavior (spot-check via `--qa` images or unzipped XML). This validates the revert guarantee.

- [ ] **Step 3: Expressive smoke deck**

```bash
cd ~/arcadia/superstack/skills/build-pptx
python build.py --input tests/fixture_realistic.md --output /tmp/expressive.pptx --shake --qa
git checkout -- tests/fixture_realistic.md.layout.json
```
Expected: sidecar shows `"mode": "expressive"` + a `"theme"` name; QA images render. Eyeball them against the anti-patterns.

- [ ] **Step 4: Sync skill to live location**

```bash
cp -r ~/arcadia/superstack/skills/build-pptx/* ~/.claude/skills/build-pptx/ 2>/dev/null || true
```
(Only if a live `~/.claude/skills/build-pptx/` mirror exists; otherwise skip.)

---

## Deferred / follow-up (not in this plan)

- **Full dark-canvas support for all 15 named layouts.** v1 wires dark canvas through `_add_chrome` + the freeform path only. To let named layouts (`cards-grid`, `stats-with-takeaway`, etc.) render on a dark theme, each renderer needs to source its text/surface colors from a per-deck palette object rather than hardcoded `INK_RGB` / `PAPER_RGB`. That is a larger refactor (introduce a `Palette` context threaded through the catalog renderer signature) and should be its own plan.
- **Per-theme cover + section-divider treatments.** Cover/closing slides currently use the fixed navy treatment; theming them is a small follow-up.
- **Content-aware theme selection.** v1 picks the theme by seed. A future version could let the planner choose a theme that suits the deck's topic.

---

## Self-Review

**Spec coverage:**
- Mode flag `--mode=expressive|strict`, default expressive, recorded in sidecar → Task 1 (Steps 3, 6, 7). ✓
- Expressive logic isolated so strict bypasses it → `expressive.py` (Task 1 Step 5), gated import (Task 1 Step 7). ✓
- Theme system: canvas + neutrals + accent ordering + uncapped supplementary hues → `themes.py` (Task 2 Step 3). ✓
- Picked once at plan-gen, seeded by `shake_seed`, frozen in sidecar → `pick_theme` + `resolve_theme` + `final_plan.theme =` (Task 1 Step 7, Task 2 Steps 3/5). ✓
- Injected into renderer chrome (canvas + on_dark) and freeform sandbox namespace → Task 2 Steps 6-9. ✓
- Brand fonts locked → fonts never exposed as variable; only `MONO_FONT`/`SANS_FONT` constants (Task 2 Step 6, guidance Task 3 Step 3). ✓
- Port Anthropic design-taste prose + mode-aware rubric → Task 3 Steps 3-5. ✓
- `--qa` loop soffice→PDF→pdftoppm→inspect→fix→re-render → Task 4 (`qa.py` + flag + SKILL.md loop). ✓
- Tag stable state for revert → Task 0 Step 2. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. The two prose-edit steps that say "Read X to see the body" (Task 2 Step 7 `_add_chrome`, Task 3 Step 5 rubric) are necessary because those bodies are long and unchanged except for the additive edit described — the exact insertion and substitution rule is specified.

**Type consistency:** `Plan.mode` / `Plan.theme` (Task 1) match reads in `expressive.resolve_theme` (Task 2) and `build.py`. `Theme` fields (`name`, `canvas`, `bg_hex`, `on_dark`, `accent_order`, `supplementary`) are used consistently in `themes.py`, `expressive.py`, `render.py` (`theme.on_dark`, `theme.bg_hex`, `theme.supplementary`, `theme.accent_order`), and `freeform.py` (`_theme` dict keys `on_dark`/`bg_hex`/`supplementary`). Sandbox `run`/`build_safe_globals` kwargs (`theme_hexes`, `canvas_bg_hex`, `on_dark`) match the `run_sandboxed(...)` call in `freeform.py`. `render_from_plan(..., theme=None)` signature matches the call in `build.py`. `qa.find_soffice` / `qa.render_to_images` match the test. ✓
