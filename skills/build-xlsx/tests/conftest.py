"""pytest conftest for build-xlsx tests.

Adds the skill directory and shared directory to sys.path so imports work
regardless of which directory pytest is invoked from.
"""
import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parents[1]
_SKILLS_DIR = _SKILL_DIR.parent
_SHARED_DIR = _SKILLS_DIR / "_shared"

for _p in [str(_SKILL_DIR), str(_SHARED_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
