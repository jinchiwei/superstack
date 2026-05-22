import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import layouts.catalog as catalog


def test_every_named_renderer_accepts_palette():
    for kind, renderer in catalog.REGISTRY.items():
        sig = inspect.signature(renderer)
        assert "palette" in sig.parameters, f"{kind} renderer missing palette kwarg"
