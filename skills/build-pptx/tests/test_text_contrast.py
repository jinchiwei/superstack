import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layouts._common import _text_on, _rgb, INK_RGB, WHITE_RGB


def test_dark_text_on_bright_accents():
    # Turquoise + amber read best with dark text.
    assert _text_on(_rgb("#40E0D0")) == INK_RGB   # turquoise
    assert _text_on(_rgb("#F0C840")) == INK_RGB   # amber
    assert _text_on(_rgb("#5EEAD4")) == INK_RGB   # midnight supplementary teal
    assert _text_on(_rgb("#FBCFE8")) == INK_RGB   # supplementary pink (non-brand → luminance)


def test_white_text_on_dark_fills():
    # deeppink + blueviolet are explicit light-text accents (per Jin's call).
    assert _text_on(_rgb("#FF1493")) == WHITE_RGB  # deeppink
    assert _text_on(_rgb("#8A2BE2")) == WHITE_RGB  # blueviolet
    assert _text_on(_rgb("#0E1A35")) == WHITE_RGB  # navy
    assert _text_on(_rgb("#14141C")) == WHITE_RGB  # ink canvas
