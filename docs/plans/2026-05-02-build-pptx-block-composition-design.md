# build-pptx block-composition design (v6 experiment)

> Experimental branch: `exp/block-composition`. Will not touch main until validated.

## Why

v4 named layouts each own the entire body region. A "results overview" slide is forced into one of `content-text`, `cards-grid`, `content-text-image`, etc. — when the actual content is `[2 stat tiles + 1 figure] over [paragraph + caption]`, the planner has no way to express that.

v5 freeform solved expressiveness at the cost of brand consistency: Claude writes raw python per slide, and across a 30-slide deck the styling drifts.

**Block composition** is the middle path: the slide body is a list of rows, each row is a list of blocks, each block is one of ~7 brand-locked primitives. The planner's job is structural decomposition (which blocks, in what arrangement) — not styling decisions.

## Schema

Sidecar entry:

```json
{
  "kind": "composition",
  "params": {
    "title": "...",
    "lede": "...",
    "section_label": "...",
    "rows": [
      {
        "height": 2.0,
        "blocks": [
          {"kind": "stat-tile", "weight": 1, "params": {...}},
          {"kind": "figure", "weight": 2, "params": {...}}
        ]
      },
      {
        "blocks": [
          {"kind": "paragraph", "weight": 1, "params": {...}}
        ]
      }
    ]
  }
}
```

**Row geometry:**
- `height` — fixed inches; if omitted, row gets equal share of remaining body height.
- A row is a horizontal strip; blocks inside it sit side-by-side.

**Block geometry:**
- `weight` — relative horizontal share within the row. `[1, 2]` → 1/3, 2/3 split.
- A block of weight 0 means "auto-size" (= shrink to its natural width); useful for icons or stat tiles next to a paragraph.

**Spacing defaults:**
- Inter-row gutter: 0.20 in
- Inter-block gutter (within row): 0.20 in
- Body padding: inherited from chrome (`body_l`, `body_w`, `body_top`, `body_h`)

## Block primitives

Each block has a `render(slide, *, left, top, width, height, params, accent_rgb)` signature.

### 1. `paragraph`
Wrapped prose, optionally with bullet leaders. Multi-paragraph supported.

```json
{"kind": "paragraph", "params": {"items": ["First sentence.", "Second.", "Third."], "size": 14, "bullets": false}}
```

### 2. `figure`
Image with optional caption. Aspect-aware: portrait/wide images are sized to fit the bbox, caption sits below.

```json
{"kind": "figure", "params": {"image_path": "fig1.png", "caption": "External validation AUC across 5 sites.", "alt": "Bar chart"}}
```

### 3. `card-row`
N cards side-by-side inside the block bbox. Each card has the standard `_add_card` styling (paper bg + accent top stripe). Cards inside a `card-row` block share the row's accent color by default but can override.

```json
{"kind": "card-row", "params": {"cards": [
  {"label": "UCSF", "body": "n=120, multi-MR", "icon": "FaUniversity"},
  {"label": "External", "body": "n=84, single MR", "icon": "FaGlobe"}
]}}
```

### 4. `stat-tile`
Big number + label + optional sublabel. Single-tile primitive (use `card-row` for grids of stats, or stack multiple `stat-tile`s in a row).

```json
{"kind": "stat-tile", "params": {"value": "0.91", "label": "Internal AUC", "sub": "5-seed mean"}}
```

### 5. `accent-callout`
Dark or accent-bg full-width callout bar with a single bold takeaway. The "section emphasis" pattern.

```json
{"kind": "accent-callout", "params": {"text": "Causal grounding remains an open question.", "tone": "dark"}}
```
`tone` ∈ `{"dark", "accent"}` — `dark` uses DARK_BG_RGB with white text, `accent` uses the row's accent_rgb at alpha with INK text.

### 6. `table`
Accent-headered data table. Same as the existing `_add_table` helper.

```json
{"kind": "table", "params": {"rows": [["Site", "n", "AUC"], ["UCSF", 120, 0.91], ...]}}
```

### 7. `quote`
Italic block quote with optional attribution.

```json
{"kind": "quote", "params": {"text": "...", "attribution": "Dr. Smith"}}
```

## Composition layout

`layouts/composition.py`:

```python
def render(slide, *, params, accent_rgb, footer_kwargs):
    title, lede = params["title"], params.get("lede", "")
    body_top, body_h, body_l, body_w, body_bottom = _add_chrome(slide, ...)
    rows = params["rows"]
    _layout_rows(slide, rows, body_top, body_l, body_w, body_h, accent_rgb)


def _layout_rows(slide, rows, body_top, body_l, body_w, body_h, accent_rgb):
    # Allocate vertical space: fixed-height rows first, then split remainder
    fixed = sum(r.get("height", 0) for r in rows if "height" in r)
    auto_rows = [r for r in rows if "height" not in r]
    auto_h = max(0.5, (body_h - fixed - 0.20 * (len(rows) - 1)) / max(1, len(auto_rows)))

    y = body_top
    for i, row in enumerate(rows):
        h = row.get("height", auto_h)
        _layout_row_blocks(slide, row["blocks"], left=body_l, top=y, width=body_w, height=h, accent_rgb=accent_rgb)
        y += h + 0.20  # row gutter
```

## Plan-prompt extension

Add a `### composition` section to `plan_prompt.md` that documents:
- The schema
- When to use composition vs named layouts (use composition when the content has 2+ structurally different chunks per slide; use a named layout when one template fits the whole slide)
- Per-block param tables
- 2-3 worked examples mapped to real DMG-style slides

## Determinism

Same as v4/v5: sidecar is committed alongside markdown. Same content_hash + same params → byte-identical output.

## Revertibility

- Lives entirely on `exp/block-composition` branch.
- Adds new layout kind `composition`; doesn't modify any existing named layout.
- If we abandon: `git branch -D exp/block-composition` and main is untouched.
- If we keep: merge after Jin signs off on the smoke comparison.

## Decisions (confirmed with Jin 2026-05-02)

1. **Row height — relative weights as default.** Fixed inches felt too constraining.
   - Omit both → `weight: 1` (rows split evenly)
   - `"weight": 2` → twice as tall as a `weight: 1` row
   - `"height": 1.5` (inches) → explicit-fixed escape hatch (overrides weight)
   - Inter-row gutter: 0.20 in
2. **Block kinds — 8 total.** `paragraph, figure, card-row, stat-tile, accent-callout, table, quote, left-accent-card` (the pattern-7 vertical-stripe variant).
3. **Glyph icons ship in v6.** `card-row` and `stat-tile` accept `icon: "FaDna"` (FA-Free name). Bundle ~40 SVGs under `skills/build-pptx/icons/svgs/`, render via cairosvg with brand color injection, cache PNGs by `hash(name, color, size)`. Also accept `icon_path` for raw image escape hatch.
4. **Per-row accent override.** Rows can set `"accent_hex": "#..."` (optional, defaults to slide accent). Enables two-tone slides.
