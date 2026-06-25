# superstack/logos — institutional logos for build-pptx title slides

Any `.png` logos placed here are auto-embedded on the title slide of decks
built with build-pptx (lower-right paired block, vertical-center). The image
files + manifest are GITIGNORED — each machine populates its own set (UCSF +
Cal here; a CurieDx logo on the part-time-job machine, etc.). If the folder is
empty, logo embedding is silently skipped. Only this README is tracked in git.

## manifest.json (optional)

Controls order (left→right) and per-logo height scale. Scale compensates for
assets with canvas padding — e.g. the UCSF disc has ~30% transparent padding,
so it renders at 1.40× to visually match Cal's edge-to-edge mark.

```json
{
  "title": [
    {"file": "ucsf-logo.png", "scale": 1.40},
    {"file": "cal-logo.png",  "scale": 1.0}
  ]
}
```

Without a manifest: all PNGs in this folder, alphabetical order, equal height.

## Opt out per deck

A deck whose frontmatter has `logos: false` (e.g. personal / non-institutional
projects) skips logo embedding even when this folder exists.

## Other machines

Drop that machine's logo(s) here (e.g. a CurieDx logo on the part-time-job
machine) with a matching manifest. build-pptx picks them up automatically.
