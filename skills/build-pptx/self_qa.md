# Self-QA — render, look, fix (every visual artifact, not just slides)

The same QA discipline applies to **every visual artifact** in a deck — slides, figures, charts, schematics, tables, embedded images. The loop is identical:

1. **Render the artifact.** Rasterize to PNG (or open the file).
2. **Look at it.** Don't read the source code; look at the pixels.
3. **Fix anything that looks wrong.** Iterate.
4. **Don't ship a deliverable you haven't looked at.**

This applies to both:
- **Slide composition** (mandated by [`bespoke_design.md`](bespoke_design.md))
- **Custom figures** generated via matplotlib (mandated by [`intro_figures.md`](intro_figures.md))

Catching these is YOUR responsibility — the user should not have to point at slide N or figure X and tell you something is squished. If you skipped the visual pass, you are not done.

## The render-look loop in practice

For a build-pptx deck:

```bash
# After --plan-only + handcraft pass + build:
soffice --headless --convert-to pdf deck.pptx
pdftoppm -r 80 -png deck.pdf q                    # one PNG per slide
montage q-*.png -tile 5x9 -geometry 210x118+2+2 \  # contact sheet for scan
        contact.png
# Open contact.png. Scan every slide. For any that look off,
# render at higher resolution (-r 150) and inspect.
```

For a figure:

```bash
# After running _make_figs.py:
# Just open the PNG. For multi-figure scripts, montage them:
montage figures/intro_*.png figures/methods_*.png \
        -tile 2x3 -geometry 560x320+8+8 _figs_qa.png
# Open _figs_qa.png and scan.
```

The agentic version: read the PNG file via your file-read tool, inspect visually, decide what's wrong, fix the source, regenerate.

## Common failures to catch (same list for slides and figures)

### Text issues

- **Overlap with data**: annotation text on top of a rising curve, label on top of a bar, callout covering a marker. Move the text to whitespace (typically lower-left/right corner if data clusters elsewhere). Arrow can still point from the safe location to the data feature.
- **Overlap with other text**: tick labels colliding, legend covering axis labels, two callouts on top of each other. Adjust position, change `loc=`, rotate ticks, or shorten the label.
- **Running off the edge** (truncation): title or caption extending past the right edge of the slide or page. Wrap, shrink, or shorten.
- **Clipped at top/bottom**: long body wrapping past the bottom of its box. Auto-shrink fontsize or split the content.
- **Squished**: text scaled down because the box is too small. Widen the box or shorten the text.

### Contrast / color

- **Low-contrast text on a fill**: hardcoded color that doesn't read against the actual fill. For slides use `_text_on(fill)` (the WCAG luminance helper). For figures, use the theme's `T.ink_text` / `T.muted_text` from `theme_colors()`.
- **Wrong text color for the theme**: black text on a dark canvas, white text on a light canvas. Always pass theme-aware colors, never hardcode `"black"` or `"white"` in figures.
- **Body text in muted/dim gray on a panel**: reads as washed out. Reserve muted only for tiny secondary captions on the open canvas.
- **Off-brand color on a data mark**: should be turquoise/deeppink/amber/blueviolet in priority order. Pink-yellow-blue would be a regression.

### Layout / spacing

- **Cramped figures**: thumbnail-sized when the slide centers on them. Enlarge until you can read the axes at a glance.
- **Uneven spacing**: stacked elements bunched at the top with empty space below; or evenly distributed when content varies. Match spacing to content, not template.
- **Empty bands**: a layout reserved space for an optional element (callout, takeaway) that wasn't filled. Either fill it or remove the slot.
- **Mismatched section accents**: divider in turquoise but content slides under it accidentally in deeppink. The section-color cycle should hold across the whole section.
- **Empty cells in a table** or empty cards in a grid that should have content.

### Figure-specific

- **Axis labels too small to read at slide-scale**: the figure looks fine at 100% but tiny on a projected slide. Bump fontsize on axis labels, ticks, and any data annotations to 11-13pt.
- **Legend covers data**: change `loc=` or move the legend outside the plot area.
- **Bars / markers cut off at axis edges**: extend `ylim` or `xlim` slightly past the data range.
- **Error bars invisible** because they're the same color as the background or too thin to see.
- **No citation in the title** when redrawing a published reference — see [`intro_figures.md`](intro_figures.md).

## You did NOT do self-QA if

- You wrote the design / figure code and called it done without rasterizing.
- You looked at one slide / figure and assumed the rest were fine.
- You re-rendered after a fix but didn't look at the result.
- You shipped a deck with figures you generated but never opened.

## The standard

If a reasonable reader would say "this is hard to read" or "this looks off" or "there's clearly text on top of a curve here" — that's a self-QA failure, not a stylistic preference. Catch it before delivery.

## Automated checks that fire during build

`build.py` runs a couple of non-fatal lints after rendering. Read their stderr output as a TODO list — they catch the most common regression classes:

- **Contrast lint** (`contrast_lint.py`) — scans every freeform slide's code for `_add_text(..., color_rgb=MUTED_RGB)` and `color_rgb=DIM_RGB`. These muted grays are appropriate ONLY for tiny secondary captions on the open canvas — on a SURFACE / PAPER / accent card they produce washed-out, low-contrast text. The lint prints `slide N (title) line L: MUTED_RGB` with the offending snippet so you can audit each call and either replace with `(WHITE_RGB if ON_DARK else INK_RGB)` (theme-aware ink) / `_text_on(fill_rgb)` (for accent fills), or confirm it's a legitimate canvas-side caption.
- **Missing notes lint** — see [`speaker_notes.md`](speaker_notes.md). Lists content slides without `params['notes']` so gaps are visible.

Automated lints catch known-pattern bugs; they DO NOT replace the visual pass. Things they can't catch include: text overlapping a data curve (geometric, not color), cramped figure layouts, mismatched accent colors that happen to satisfy contrast, off-edge clipping at render time. Eyes still required.
