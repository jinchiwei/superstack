---
name: build-figure
description: Generate Jin-branded matplotlib figures anywhere — notebooks, papers, reports, or standalone PNGs — using the same brand style, theme canvas, and QA checks that build-pptx uses for slide figures, but without the deck machinery. Import the `brandfig` module in a figure script or Jupyter notebook for branded live plots, or run the CLI to render a figure script with optional QA gating. Voice triggers: "branded figure", "brand figure", "make a figure in my style", "notebook plots in my style".
---

# /build-figure

Jin-branded matplotlib figures, standalone. Same foundation as build-pptx's slide
figures (`_shared/mpl_style.py`: themes, brand palette, save-time QA) — just decoupled
from the deck, so notebooks, papers, and one-off charts share one look.

## When to invoke

- You want a chart/diagram in Jin's brand (Geist Mono titles, turquoise/deeppink/amber/
  blueviolet palette, theme-matched canvas) outside a slide deck.
- You're adding **inline plots to a Jupyter notebook** and want them branded and
  canvas-matched (the MIT-6.S191 style: sample images, training curves, predictions).
- A figure script needs the same overflow / box-padding QA build-pptx figures get.

For figures destined for a **slide deck**, you can still use this — pass the deck's
theme name so the background matches — but build-pptx projects often keep a local
`figbase` that wraps this same module.

## The `brandfig` module (the core)

Put this skill dir on `sys.path` (or run via the CLI, which does it for you), then:

```python
import brandfig as bf
bf.use("bone")                       # apply brand style for a theme
fig, ax = bf.fig(figsize=(8, 4))     # styled figure, facecolor = theme canvas
ax.bar(["a", "b"], [3, 5], color=[bf.TURQUOISE, bf.DEEPPINK])
bf.figtitle(fig, "A branded chart")  # Geist Mono suptitle in theme ink
bf.save(fig, "out.png")              # canvas-matched save + QA warnings (stderr)
```

### Notebook (inline, live plots)

```python
import brandfig as bf
bf.use("bone")                       # inline plots now adopt the theme canvas
fig, ax = bf.fig(figsize=(6, 3))
ax.plot(history["loss"], color=bf.TURQUOISE, label="train")
ax.legend()
bf.show(fig)                         # canvas-matched inline display + QA
```

`bf.use(theme)` calls `apply_style`, which sets matplotlib's figure/savefig facecolor
to the theme canvas — so every inline plot after it is on the right background with no
extra work.

### API

- `use(theme="bone")` — apply the brand style; remember it as current. Returns ThemeColors.
- `fig(*args, theme=None, **kw)` — `plt.subplots` with the figure facecolor set to the
  canvas. Pass `theme=` for a one-off different theme.
- `figtitle(fig, text, *, color=None, y=1.03, size=16)` — Geist Mono suptitle.
- `save(fig, path, *, theme=None, dpi=200, qa=True, source=None)` — themed-canvas save,
  then run QA. Records issues in `brandfig.ISSUES`.
- `show(fig, *, qa=True)` — inline notebook display, canvas-matched + QA.
- `colors(theme=None)` / `canvas()` / `ink()` / `muted()` — theme lookups.
- `palette(n, kind="fills"|"lines")` — n brand colors.
- `txt_on(hex)` — high-contrast text color (black/white) for text on a brand fill.
- Constants: `TURQUOISE`, `DEEPPINK`, `AMBER`, `BLUEVIOLET`, `GOLD` (also under `bf.C`).
- Re-exports: `plt`, `np`.
- `ISSUES` — list of QA findings accumulated by `save`/`show` (for CI gating).

## Themes

| theme | canvas | use for |
|-------|--------|---------|
| `paper` | white | papers, docx, default |
| `bone` | warm off-white `#F6F4EE` | notebooks, reports, bone decks |
| `slate` / `midnight` / `forest` | dark | dark decks / dark backgrounds |

Brand accent colors are identical across themes; only text/spine/grid/canvas flip for
dark themes. When a figure is for a deck, pass the deck's theme (from
`<deck>.md.layout.json` `theme`) so the figure background matches the slide.

## CLI

```bash
python build_figure.py figs.py                  # run a figure script, warn on QA
python build_figure.py figs.py --theme bone      # set the default theme
python build_figure.py figs.py --strict          # exit 1 if any figure trips QA
python build_figure.py --demo out.png            # emit a sample figure
```

A figure script just imports `brandfig` and calls `bf.save(...)` per figure. The CLI
runs it with this dir on `sys.path` and `BRANDFIG_THEME` set, then reports QA issues;
`--strict` makes it a gate for pre-commit / CI. A script that calls `bf.use("...")`
explicitly overrides `--theme`.

See `examples/demo_figs.py`.

## QA checks (shared with build-pptx)

`save`/`show` run two checks from `_shared/mpl_style.py` and print warnings to stderr:

- **text overflow** (`check_text_overflow`) — text whose rendered bbox spills past its Axes.
- **box padding** (`check_box_padding`) — a number/label that hugs the top or bottom edge
  of a solid-filled box (poor interior padding). Skips intentional designs: tight header
  bands, corner badges, multi-line panel headers, and image/media cards.

Both are also collected in `brandfig.ISSUES` so a script or test can fail on them.

## Design principles

Keep figures legible and on-brand: Geist Mono for titles/labels, the brand-4 palette for
categorical fills, dark text on turquoise/amber and white on deeppink/blueviolet (use
`txt_on`), and a theme-matched canvas (never a stark white rectangle on a tinted page).
Prefer one clear idea per figure; let the caption carry the nuance.
