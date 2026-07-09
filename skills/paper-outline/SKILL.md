---
name: paper-outline
description: Generate a detailed manuscript WRITING SCAFFOLD (paraphrasing outline) from a draft or results — paragraph-by-paragraph Points with inline (cite N) citation slots, italic Flow notes, a merged Citation Legend, embedded figures, and a pre-submission consistency checklist. NOT finished prose — the author writes the prose; this scaffolds what each paragraph must land, which reference goes where, and how it flows. Builds to a Jin-branded docx/pdf (turquoise H1 → deeppink H2 → amber H3 → blueviolet H4; author name turquoise). Use for "writing outline", "paper scaffold", "rewriting outline", "citation map", "paraphrasing guide", "how should I structure this paper". Voice triggers: "make a writing outline", "scaffold this paper", "outline with citations and figures".
---

# /paper-outline

Markdown → a detailed, author-facing manuscript writing scaffold (then a Jin-branded docx/pdf via build-docx / build-pdf).

## What this produces (and what it is NOT)

It produces a **paraphrasing scaffold**, per Jinchi's standing norm: *the AI builds the outline (bullets of exactly what each section must land, in order, with numbers and citation slots); Jinchi writes the prose.* Never write the finished paragraphs. Every bullet is a claim for the author to rewrite in their own voice.

The canonical reference implementation is `…/projects/cnsl/manuscript_bundle/branded/writing_outline.md` — match that depth and shape.

## When to invoke

User asks for a writing outline / scaffold / "rewriting outline" / "citation map" / paraphrasing guide for a manuscript (or wants help structuring a paper they're about to write). Distinct from `build-docx`/`build-pdf`, which only render a finished markdown — this GENERATES the scaffold content first, then renders it.

## Inputs

- A manuscript draft (`.docx` / `.md`) and/or the results (tables, figures, a finished prior draft). Read it to extract real numbers — never invent values.
- The figures directory (relative paths) and the reference list. If a finished draft exists, mine its numbered references for the Citation Legend.

## Required output structure (in this order)

1. **Front-matter** — `title`, `subtitle`, `name: "Jinchi Wei"` (renders turquoise), `org`, `date`, `eyebrow`.
2. **# How to use this document** — explain the three elements: **Points** (claims to paraphrase), **(cite N)** (maps to the Citation Legend), and ***Flow*** (italic hand-off notes). State that figures are embedded at first call-out and all numbers are the current results.
3. **# Citation Legend** — every reference, **ordered by first appearance**, one line each: `**N** Author Year — what it supports`. Mark which are already in the library vs to-add. Pull numbers from the draft's existing reference order; don't re-derive a new scheme unless asked.
4. **Resolved-method notes** — short callouts that pin down ambiguous tooling/decisions (e.g. "pyALFE is the pipeline; nnU-Net is the network inside it — cite both"), so the author doesn't re-litigate them while writing.
5. **Section scaffolds** — for **Introduction, Methods, Results, Discussion, Conclusions**, broken into the paragraphs/subsections that section should have. For each paragraph:
   - a bold paragraph label (e.g. `## Paragraph 3 — Imaging and the spatial-genotype precedent`),
   - **Points**: a bullet per substantive claim, in order, each ending with `(cite N)` or `(no cite)`,
   - an italic ***Flow*** line on how it connects to the next paragraph and hands off between sections.
   - Embed the relevant **figure inline** (`![caption](relpath)`) at the Results paragraph where it's first called out.
6. **# Quick consistency checklist** — `- [ ]` items: headline-number agreement across Abstract/Results/Tables/Conclusions, figure-numbering/call-out order, n-counts consistent everywhere, unit/typo checks, tool-citation reconciliation, and "re-run the regen/audit scripts after any analysis change."

## Rules

- **Scaffold, not prose.** Bullets and flow notes only. If you catch yourself writing a finished sentence the author would paste verbatim, compress it to a claim.
- **Real numbers only.** Bake in the actual values (AUROCs + CIs, Dice, n-counts, frequencies) from the results/draft. If a number isn't available, write a `*(fill in: …)*` placeholder — never fabricate.
- **Citations are slots.** `(cite N)` keyed to the Legend; `(no cite)` for the author's own gap statements / study description. Group multi-ref claims (`cite 5, 6, 7`).
- **Funnel the Intro, mirror Limitations↔Future** one-for-one, lead Discussion with the thesis, keep Conclusions citation-free.
- **Figures embedded** at first call-out, using the consistent brand figures (turquoise/deeppink data, Geist titles).
- **Hedge honestly** — hypothesis-generating framing, especially small-n.

## Branding (delegated to build-docx / build-pdf)

Header cascade is automatic via `branding.py`: **H1 turquoise, H2 deeppink, H3 amber, H4 blueviolet; document title black**. The **author name (`name:` frontmatter) renders turquoise** — for manuscript drafts, Jinchi's name is ALWAYS turquoise (see also the byline rule below).

## Manuscript byline — Jinchi's name is always turquoise

For any **manuscript draft** (scaffold, outline, or the paper itself), Jinchi Wei's name renders in **turquoise (#40E0D0)**:
- The cover/byline `name:` field already renders turquoise (build-docx `NAME_COLOR`, build-pdf `.name`).
- If the formal author list appears **inline in the body** (e.g. "Jinchi Wei¹,²\*, Co-Author¹, …"), wrap just his name so it stays turquoise: for build-pdf use `<span style="color:#40E0D0">Jinchi Wei</span>`; for build-docx (pandoc drops inline HTML), apply turquoise to that run in a short post-build python-docx pass, or keep the turquoise byline on the cover. Co-authors stay ink/black.

## Build

After writing `<name>_outline.md`, render both:

```
python ~/.claude/skills/build-docx/build.py --input <name>_outline.md --output <name>_outline.docx
python ~/.claude/skills/build-pdf/build.py  --input <name>_outline.md --output <name>_outline.pdf
```

(The PDF carries the embedded figures; expect a multi-MB file. Use `--double-spaced` only for the manuscript itself, not the scaffold.)

## Branding source of truth

`~/arcadia/superstack/skills/_shared/branding.py` (mirrored to `~/.claude/skills/_shared/branding.py`).
