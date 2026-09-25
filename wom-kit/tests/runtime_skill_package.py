"""v0.4.45: the helper-AI guidance is a short SKILL.md core card plus focused
references. Historical release tests keep bounding SKILL.md itself but look
for their operating tokens anywhere in the runtime package."""
from __future__ import annotations

from pathlib import Path


def package_text(skill_root: Path) -> str:
    root = Path(skill_root)
    parts = [root / "SKILL.md", *sorted((root / "references").glob("*.md"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in parts)
