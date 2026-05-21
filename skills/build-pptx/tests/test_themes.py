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
        assert set(t.accent_order) <= BRAND4
        assert len(t.accent_order) == 4
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
    t = get_theme("does-not-exist")
    assert isinstance(t, Theme)


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
