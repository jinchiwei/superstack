# build-pptx v5: Freeform Creative Layouts via Sandboxed Code Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Multi-task plan, ~3-4 hr CC time.

**Goal:** Lift the layout ceiling from "9 prespecified templates" to "any layout Claude can imagine," while preserving v4's caching and brand identity. Add a `freeform` layout kind whose `params.code` is a python snippet that runs in a sandboxed namespace with only safe primitives exposed. Wire SKILL.md to auto-invoke Claude (the running agent) on missing sidecar or `--shake`, so the agent reads the markdown, writes the sidecar (using `freeform` for creative slides + named kinds for boilerplate), and proceeds to render.

**Architecture:** Two new pieces on top of v4:

1. **Freeform layout** — a new catalog entry `kind: "freeform"`. `params.code` is a string of python that draws the slide body. Renderer compiles it, AST-validates it, execs it with a constrained globals dict that exposes only safe primitives (`_add_rect`, `_add_text`, etc.) — no `os`, `sys`, `open`, `__import__`, attribute access to dunder methods. Chrome (title, lede, footer, accent bar) still drawn by `_add_chrome` outside Claude's code so brand identity is locked.

2. **Auto-invocation** — `SKILL.md` instructs the running Claude agent to detect missing sidecar / `--shake` and:
   - Run `python build.py --plan-only` to get the assembled prompt path
   - Read `plan_prompt.md` + the markdown chunks
   - Generate the JSON sidecar (using `freeform`/`params.code` for creative slides, named kinds for boilerplate)
   - Write the sidecar
   - Continue with `python build.py --input ... --output ...` to render

The first run is slower (~30-60s for Claude to write per-slide code); subsequent runs hit the cache and render in ~2 seconds.

**Tech Stack:** Python 3.12 in `deepdream`. New deps: none — `compile()` and `exec()` are stdlib. AST validation uses `ast` module.

**Realistic effort: ~3-4 hr CC time.** Bulk is the sandbox + AST validator + a few tested example layouts to seed Claude's pattern library.

---

## Determinism + cache invariants (preserved from v4)

- Sidecar at `<input>.layout.json` is the source of truth for reproducibility.
- Same sidecar + same markdown content → byte-identical pptx (modulo timestamp metadata).
- `--shake` regenerates the sidecar from scratch (Claude rewrites every slide's code).
- `--no-plan` skips the sidecar entirely and falls through to v3's rule-based path.
- Adding a new slide to the markdown invalidates only that slide's cache entry; existing slides keep their cached `freeform` code.

---

## File Structure (changes only)

```
~/arcadia/superstack/skills/build-pptx/
├── layouts/
│   ├── _sandbox.py                       CREATE: AST validator + safe-globals + exec
│   ├── freeform.py                       CREATE: freeform layout renderer
│   └── catalog.py                        MODIFY: register "freeform"
├── plan_prompt.md                        MODIFY: add freeform schema + examples
├── SKILL.md                              MODIFY: auto-invocation instructions
└── tests/
    ├── test_sandbox_security.py          CREATE: AST/exec tests (rejects bad code)
    ├── test_freeform_render.py           CREATE: round-trip tests
    └── fixture_freeform_demo.md          CREATE: 3-slide demo for smoke
```

---

## Sandbox spec (the load-bearing piece)

`layouts/_sandbox.py`:

```python
"""Validate-and-exec sandbox for v5 freeform layouts.

Each freeform slide's params.code is a python snippet that draws shapes onto
a slide. The snippet runs in a constrained globals dict that exposes only
safe primitives. We pre-validate via AST scan to reject dangerous nodes
(imports, attribute access to dunders, exec/eval, file I/O) before exec'ing.

Threat model: Claude (or a human editing the sidecar) writes the code. The
goal is to prevent ACCIDENTAL escapes (a malformed snippet shouldn't be able
to read /etc/passwd or shell out), not to defeat a determined adversary."""

from __future__ import annotations

import ast
from pathlib import Path

# === Forbidden AST node types ===
_FORBIDDEN_NAMES = {
    "exec", "eval", "compile", "open", "input",
    "__import__", "__builtins__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "hasattr",
    "breakpoint", "help",
}

# Attribute accesses to these prefixes are dunder-touching → reject.
_FORBIDDEN_ATTR_PREFIX = "__"


class SandboxError(ValueError):
    """Raised when freeform code fails validation."""


def validate_code(code: str) -> None:
    """AST-scan the snippet. Raise SandboxError if anything fishy is found.

    Rejects:
      - Any Import / ImportFrom node
      - Any Attribute access where the attr name starts with __
      - Any Name reference to a forbidden builtin (open, exec, eval, ...)
      - Any Call to a forbidden builtin
      - Any try/except (could swallow our enforcement errors)
      - With statements (could open files)
      - Lambda is OK; def is OK; class is OK as long as nested rules pass.
    """
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise SandboxError(f"freeform code does not parse: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxError(f"import statements forbidden in freeform code")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith(_FORBIDDEN_ATTR_PREFIX):
                raise SandboxError(
                    f"dunder attribute access forbidden: .{node.attr}"
                )
        if isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES:
                raise SandboxError(f"forbidden name: {node.id}")
        if isinstance(node, (ast.Try, ast.With)):
            raise SandboxError(
                f"try/with statements forbidden — they can swallow enforcement"
            )


def build_safe_globals(*, slide, accent_hex: str, body_top: float,
                      body_h: float, body_l: float, body_w: float,
                      body_bottom: float) -> dict:
    """Construct the globals dict for exec'ing freeform code.

    Exposes:
      - All branding colour constants (TURQUOISE, DEEPPINK, etc.) and font names
      - All safe drawing primitives from layouts._common (_add_rect, _add_text, _add_card, ...)
      - Geometry helpers: Inches, Pt, RGBColor, MSO_SHAPE
      - The slide object
      - body_top/h/l/w/bottom geometry tuple as locals
      - A minimal __builtins__: only safe pure functions

    Does NOT expose:
      - os, sys, pathlib, anything filesystem
      - import, exec, eval, open, __import__
      - Anything that could call out to the network or shell
    """
    from layouts._common import (
        _add_rect, _add_text, _add_card, _add_table,
        _render_paragraph_block, _render_media_block,
        INK_RGB, WHITE_RGB, TURQUOISE_RGB, DEEPPINK_RGB, AMBER_RGB,
        BLUEVIOLET_RGB, DIM_RGB, MUTED_RGB, RULE_RGB, DARK_BG_RGB,
        PAPER_RGB, _rgb,
    )
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    import branding

    # Minimal builtins: pure functions only, no I/O, no introspection.
    safe_builtins = {
        "abs": abs, "min": min, "max": max, "sum": sum,
        "len": len, "range": range, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter,
        "sorted": sorted, "reversed": reversed,
        "str": str, "int": int, "float": float, "bool": bool,
        "list": list, "tuple": tuple, "dict": dict, "set": set,
        "round": round,
        "True": True, "False": False, "None": None,
        # NO open, NO __import__, NO exec, NO eval, NO compile,
        # NO getattr/setattr, NO globals/locals/vars, NO input
    }

    return {
        "__builtins__": safe_builtins,
        # Slide + geometry
        "slide": slide,
        "accent_hex": accent_hex,
        "accent_rgb": _rgb(accent_hex),
        "body_top": body_top, "body_h": body_h,
        "body_l": body_l, "body_w": body_w, "body_bottom": body_bottom,
        # Drawing primitives
        "_add_rect": _add_rect,
        "_add_text": _add_text,
        "_add_card": _add_card,
        "_add_table": _add_table,
        "_render_paragraph_block": _render_paragraph_block,
        "_render_media_block": _render_media_block,
        "_rgb": _rgb,
        # Colours
        "INK_RGB": INK_RGB, "WHITE_RGB": WHITE_RGB,
        "TURQUOISE_RGB": TURQUOISE_RGB, "DEEPPINK_RGB": DEEPPINK_RGB,
        "AMBER_RGB": AMBER_RGB, "BLUEVIOLET_RGB": BLUEVIOLET_RGB,
        "DIM_RGB": DIM_RGB, "MUTED_RGB": MUTED_RGB,
        "RULE_RGB": RULE_RGB, "DARK_BG_RGB": DARK_BG_RGB,
        "PAPER_RGB": PAPER_RGB,
        # Geometry
        "Inches": Inches, "Pt": Pt, "Emu": Emu,
        "RGBColor": RGBColor,
        "MSO_SHAPE": MSO_SHAPE,
        "PP_ALIGN": PP_ALIGN, "MSO_ANCHOR": MSO_ANCHOR,
        # Brand
        "MONO_FONT": branding.MONO_FONT,
        "SANS_FONT": branding.SANS_FONT,
        "TURQUOISE": branding.TURQUOISE, "DEEPPINK": branding.DEEPPINK,
        "AMBER": branding.AMBER, "BLUEVIOLET": branding.BLUEVIOLET,
    }


def run(*, code: str, slide, accent_hex: str, body_top: float,
        body_h: float, body_l: float, body_w: float,
        body_bottom: float) -> None:
    """Validate and exec freeform code against `slide`.

    Validation runs first; if it raises, exec is skipped. Exec runs in the
    safe-globals namespace so the snippet can ONLY touch what we've exposed.
    """
    validate_code(code)
    g = build_safe_globals(
        slide=slide, accent_hex=accent_hex,
        body_top=body_top, body_h=body_h,
        body_l=body_l, body_w=body_w, body_bottom=body_bottom,
    )
    exec(code, g, {})
```

## Freeform layout

`layouts/freeform.py`:

```python
"""freeform — runs Claude-written python in a sandbox to draw arbitrary
shapes on the slide. Chrome (title/lede/footer/accent bar) still drawn by
_add_chrome so the brand stays consistent."""

from __future__ import annotations

from layouts._common import _add_chrome
from layouts._sandbox import run as run_sandboxed, SandboxError


def render(slide, *, params: dict, accent_rgb, footer_kwargs: dict) -> None:
    """params: {
        title: str, lede: str,
        code: str,                  # python snippet, runs in sandbox
        accent_hex: str | None,     # informational; passed into sandbox
        section_label: str | None,  # for accent inheritance
    }
    """
    title = params.get("title", "")
    lede = params.get("lede", "")
    code = params.get("code", "")

    # Determine if title wraps (same heuristic as other layouts).
    title_wraps = len(title) > 30

    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(
        slide, title=title, lede=lede, footer_kwargs=footer_kwargs,
        accent=accent_rgb,
        title_present=bool(title),
        title_wraps=title_wraps,
        use_side_by_side=False,
    )

    if not code.strip():
        return  # nothing to draw

    # Resolve accent hex from RGBColor for the sandbox namespace.
    # accent_rgb is a python-pptx RGBColor; turn it back into "#xxxxxx".
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
        )
    except SandboxError as e:
        # Render a visible error chip rather than crashing the whole deck.
        from layouts._common import _add_text, INK_RGB, DEEPPINK_RGB
        import branding
        _add_text(slide,
                  f"[freeform code rejected: {e}]",
                  left=body_l, top=body_top,
                  width=body_w, height=0.5,
                  size=12, color_rgb=DEEPPINK_RGB,
                  font=branding.MONO_FONT, bold=True)
```

Add to `catalog.REGISTRY`:
```python
"freeform": freeform.render,
```

---

## Phased Tasks

### Task 1: Sandbox + AST validator + tests (~1 hr)

**Files:**
- Create: `layouts/_sandbox.py`
- Test: `tests/test_sandbox_security.py`

- [ ] **Step 1.1:** Implement `validate_code` rejecting imports, dunder attrs, forbidden names, try/with.
- [ ] **Step 1.2:** Implement `build_safe_globals` exposing only the primitives listed above.
- [ ] **Step 1.3:** Implement `run` that validates then execs.
- [ ] **Step 1.4:** Tests:
  ```python
  def test_validates_safe_code():
      validate_code("_add_rect(slide, left=0, top=0, width=1, height=1, fill_rgb=accent_rgb)")
      # No exception

  def test_rejects_import():
      with pytest.raises(SandboxError):
          validate_code("import os\n_add_rect(slide, ...)")

  def test_rejects_open():
      with pytest.raises(SandboxError):
          validate_code("open('/tmp/foo').read()")

  def test_rejects_dunder_attr():
      with pytest.raises(SandboxError):
          validate_code("slide.__class__.__bases__")

  def test_rejects_eval():
      with pytest.raises(SandboxError):
          validate_code("eval('1+1')")

  def test_rejects_try_block():
      with pytest.raises(SandboxError):
          validate_code("try:\n    pass\nexcept:\n    pass")

  def test_run_executes_safe_code(tmp_path):
      from pptx import Presentation
      prs = Presentation()
      slide = prs.slides.add_slide(prs.slide_layouts[6])
      code = "_add_rect(slide, left=1, top=1, width=2, height=2, fill_rgb=accent_rgb)"
      run(code=code, slide=slide, accent_hex="#40E0D0",
          body_top=1.5, body_h=5.0, body_l=0.5, body_w=12.3, body_bottom=6.5)
      # The snippet ran without error and a shape was added
      assert len(slide.shapes) >= 1

  def test_run_blocks_filesystem_attempt(tmp_path):
      slide = ... # build minimal slide
      with pytest.raises(SandboxError):
          run(code="open('/etc/passwd').read()", slide=slide, accent_hex="#40E0D0", ...)
  ```

- [ ] **Commit:** `feat(build-pptx): _sandbox.py — AST-validated, namespace-scoped exec for freeform layouts`

### Task 2: Freeform layout + catalog registration + smoke (~1 hr)

**Files:**
- Create: `layouts/freeform.py`
- Modify: `layouts/catalog.py`
- Test: `tests/test_freeform_render.py`
- Test fixture: `tests/fixture_freeform_demo.md`

- [ ] **Step 2.1:** Implement `freeform.render` calling `_add_chrome` then `run_sandboxed`.
- [ ] **Step 2.2:** Register in catalog.
- [ ] **Step 2.3:** Build a 3-slide demo fixture exercising freeform:
  ```markdown
  ---
  title: "Freeform demo"
  name: "Jin"
  org: "UCSF"
  date: "2026-05-02"
  ---

  # Stat callout slide

  Headline number with custom layout.

  # Three pillars with arrows

  Compare three options side by side.

  # Background dashboard

  Bespoke single-slide overview.
  ```

  And a hand-written `fixture_freeform_demo.md.layout.json` that uses `kind: "freeform"` for each slide with bespoke `params.code`.

- [ ] **Step 2.4:** Round-trip test:
  ```python
  def test_freeform_renders_demo_fixture(tmp_path):
      # Render fixture_freeform_demo.md with its hand-written sidecar
      # Assert: pptx exists, shape counts > N per slide, no errors logged
  ```

- [ ] **Step 2.5:** Visible-error test: a sidecar with `params.code: "import os"` should NOT crash the build. Instead the slide gets a deeppink error chip. Renderer continues to next slide.

- [ ] **Commit:** `feat(build-pptx): freeform layout — sandboxed python per slide for unconstrained creative layouts`

### Task 3: plan_prompt.md update with freeform examples (~30 min)

**Files:**
- Modify: `plan_prompt.md`

Add to the catalog section:

````markdown
### freeform
Use this when none of the other layouts fit the content well. You write a
python snippet that draws the body region directly. Chrome (title, hairline,
lede, footer, accent bar) is drawn separately — your code only fills the
body region.

```json
{
  "title": "...",
  "lede": "...",
  "code": "<python source>"
}
```

Available in your sandbox:
- `slide` — python-pptx slide object you draw onto
- `body_top, body_h, body_l, body_w, body_bottom` — geometry of the body
  region in inches (typically L=0.50 W=12.30, T varies based on title length)
- `accent_rgb` — the section's accent color (already an RGBColor)
- `INK_RGB, WHITE_RGB, TURQUOISE_RGB, DEEPPINK_RGB, AMBER_RGB, BLUEVIOLET_RGB,
  DIM_RGB, MUTED_RGB, RULE_RGB, DARK_BG_RGB, PAPER_RGB` — brand colors as
  RGBColor instances
- `MONO_FONT, SANS_FONT` — Geist Mono and Geist Sans font names
- `_add_rect(slide, *, left, top, width, height, fill_rgb)` — filled rect
- `_add_text(slide, text, *, left, top, width, height, size, color_rgb,
  font, bold=False, italic=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)`
- `_add_card(slide, *, label, body, left, top, width, height, accent_rgb,
  icon_path=None)` — paper-bg tile
- `_add_table(slide, *, rows, left, top, width, max_height, header_rgb)`
- `_render_paragraph_block(slide, *, items, left, top, width, height,
  accent_rgb, size=14, distribute=False)` — bullet/paragraph block
- `Inches(x), Pt(x)` — geometry helpers
- `MSO_SHAPE.{RECTANGLE, OVAL, RIGHT_ARROW, ROUNDED_RECTANGLE, ...}` — shape types
- `slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))`
- `slide.shapes.add_picture(path, Inches(x), Inches(y), width=Inches(w))`

Forbidden: `import`, `open`, `eval`, `exec`, `getattr`/`setattr`, dunder
attribute access, `try`/`with` statements, filesystem/network/shell. Code
that uses any of those is rejected at validation time and the slide
renders with a visible deeppink error chip instead.

#### Freeform examples

Stat callout slide:
```python
# 1 chart-area placeholder + 4 big-number stat tiles on the right
chart_w = 7.0
chart_l = body_l
_add_rect(slide, left=chart_l, top=body_top, width=chart_w, height=body_h, fill_rgb=PAPER_RGB)
_add_text(slide, "[chart placeholder]", left=chart_l, top=body_top + body_h/2 - 0.2,
          width=chart_w, height=0.4, size=14, color_rgb=DIM_RGB, font=MONO_FONT,
          align=PP_ALIGN.CENTER)

stats = [("0.91", "Internal AUC"), ("0.85", "External"), ("0.88", "Sens@0.5"), ("0.84", "Spec@0.5")]
stat_l = body_l + chart_w + 0.30
stat_w = body_w - chart_w - 0.30
stat_h = (body_h - 0.45) / 4
for i, (value, label) in enumerate(stats):
    y = body_top + i * (stat_h + 0.15)
    _add_text(slide, value, left=stat_l, top=y, width=stat_w, height=stat_h * 0.55,
              size=24, color_rgb=accent_rgb, font=MONO_FONT, bold=True)
    _add_text(slide, label, left=stat_l, top=y + stat_h * 0.6, width=stat_w, height=stat_h * 0.4,
              size=12, color_rgb=MUTED_RGB, font=SANS_FONT)
```

Three pillars with arrows:
```python
pillars = [("Trial", "Controlled", TURQUOISE_RGB),
           ("Real-world", "?", DEEPPINK_RGB),
           ("Practice", "Patient-level", AMBER_RGB)]
n = len(pillars)
gutter = 0.20
col_w = (body_w - gutter * (n - 1)) / n
for i, (label, body_text, color) in enumerate(pillars):
    x = body_l + i * (col_w + gutter)
    _add_rect(slide, left=x, top=body_top, width=col_w, height=body_h, fill_rgb=PAPER_RGB)
    _add_rect(slide, left=x, top=body_top, width=col_w, height=0.06, fill_rgb=color)
    _add_text(slide, label, left=x + 0.18, top=body_top + 0.18, width=col_w - 0.36,
              height=0.5, size=15, color_rgb=color, font=MONO_FONT, bold=True)
    _add_text(slide, body_text, left=x + 0.18, top=body_top + 0.80,
              width=col_w - 0.36, height=body_h - 1.0,
              size=13, color_rgb=INK_RGB, font=SANS_FONT)
    if i < n - 1:
        arrow_x = x + col_w + gutter / 2 - 0.15
        slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW,
                               Inches(arrow_x), Inches(body_top + body_h / 2 - 0.15),
                               Inches(0.30), Inches(0.30))
```

Use freeform whenever named layouts would be wasteful. Be parsimonious about
when to invoke it — most slides should still be fine with `content-text` /
`cards-grid` / `content-text-image`.
````

- [ ] **Commit:** `docs(plan_prompt): freeform layout schema + sandbox API + 2 worked examples`

### Task 4: SKILL.md auto-invocation (~30 min)

`SKILL.md` instructs the running Claude agent on what to do when invoked. The new instructions:

````markdown
## When invoked: layout-plan auto-generation

When `/build-pptx <input.md>` runs, **before** invoking `python build.py`:

1. Compute the sidecar path: `<input>.layout.json`
2. Decide mode:
   - If `--no-plan` flag was passed → skip everything below; let `build.py --no-plan` handle it.
   - If sidecar exists AND `--shake` was NOT passed → skip auto-generation; let `build.py` replay cache.
   - Otherwise: GENERATE THE PLAN INLINE before rendering.

### Inline plan generation steps

When generating:

1. Read the markdown source.
2. Read `<skill_dir>/plan_prompt.md` (the layout catalog + decision rubric).
3. Walk slide chunks: split body HTML on `<hr>`, derive a stable `slide_id`
   per chunk via `plan.derive_slide_ids_from_chunks`, compute
   `content_hash` per chunk via `plan.hash_text`.
4. **Per slide:** decide a layout `kind`. Most slides are `content-text` /
   `cards-grid` / `content-text-image`. Reach for `freeform` when:
   - The slide should pair a chart with stat callouts on the right
   - The slide compares 3 things with arrows
   - The slide is a key-takeaway and deserves a bg flip
   - The slide has a heterogeneous card layout (1 large + 2 small)
   - Anything bespoke none of the named layouts captures
5. For each `freeform` slide, write a python snippet using ONLY the API in
   `plan_prompt.md`'s "Available in your sandbox" section. Test mentally:
   does this respect `body_top`/`body_h`/`body_l`/`body_w`? Does it use
   the brand colours and fonts? No `import`, no dunder access, no `try`.
6. Write the assembled JSON to the sidecar.
7. Then invoke `python build.py --input ... --output ...` to render.

When invoking with `--shake`, do steps 1-7 but ignore any existing sidecar
and overwrite it.

If a freeform snippet fails sandbox validation at render time, the deck
will render with a visible deeppink error chip on that slide. Read the
error message in the chip, fix the snippet in the sidecar, re-run.
````

- [ ] **Commit:** `docs(SKILL.md): instructions for inline plan generation on missing sidecar / --shake`

### Task 5: Smoke + tag (~30 min)

- [ ] **Step 5.1:** Render `fixture_freeform_demo.md` end-to-end with the hand-written sidecar. Open in PowerPoint, eyeball the 3 slides.
- [ ] **Step 5.2:** Render Jin's DMG v3 deck with `--shake` to upgrade it to v5 freeform. Compare visual output.
- [ ] **Step 5.3:** Run all tests. Should be ~60 passing.
- [ ] **Step 5.4:** Sync to `~/.claude/skills/`.
- [ ] **Step 5.5:** Commit + push + tag `build-skills-v5`.

---

## Self-Review Checklist

- [ ] Sandbox AST validator rejects all categories of dangerous code (test_sandbox_security.py covers each)
- [ ] `freeform` layout registered in catalog
- [ ] Failed sandbox validation renders a visible error chip, doesn't crash the deck
- [ ] `plan_prompt.md` documents the full sandbox API + 2 worked examples
- [ ] `SKILL.md` instructs the agent on auto-invocation flow
- [ ] All tests pass (~60 total)
- [ ] DMG v3 deck regenerated with `--shake` produces a v5-style sidecar with at least 2-3 `freeform` slides
- [ ] Tag `build-skills-v5` pushed

---

## Notes for the Implementer

- **Sandbox correctness > sandbox capability.** If you have to choose between exposing one more primitive and ensuring no escape, choose safety. Capability is additive later; security holes aren't.
- **The sidecar IS the trust boundary.** Anyone who can edit `<input>.md.layout.json` can run any code the sandbox allows — by design. If Jin commits the sidecar to git, treat it like committed code (review before merging).
- **`freeform` is a fallback, not a default.** If the named layouts cover the slide well, use them. The decision rubric in `plan_prompt.md` lists when to reach for freeform — keep it there.
- **Don't add eval/exec to the safe-globals dict ever.** Even with the AST validator above it, layered defense matters.
- **The "visible error chip" rendering on validation failure is load-bearing for UX.** Without it, a single bad snippet kills the whole deck and Jin sees nothing — much worse than a broken slide with a clear error message.
- **Unused future enhancement: per-slide content_hash drift detection.** v4 already invalidates the cache when content changes, but with freeform we might want to also invalidate when the SCHEMA of the rest of the markdown changes substantially (e.g., a referenced image was deleted). Punt for now.
