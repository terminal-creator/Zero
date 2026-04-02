"""Skills system — load and execute skill definitions.

Corresponds to TS: skills/loadSkillsDir.ts + skills/bundled/.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A loaded skill definition."""

    name: str
    description: str
    prompt: str
    trigger: str = ""  # Optional trigger pattern
    source_path: str = ""


def load_skills(cwd: str, claude_dir: Path | None = None) -> list[Skill]:
    """Load skill definitions from skill directories.

    Corresponds to TS: skills/loadSkillsDir.ts.

    Searches:
    1. ~/.claude/skills/
    2. .claude/skills/ in project
    """
    skills: list[Skill] = []
    base_dir = claude_dir or (Path.home() / ".claude")

    search_dirs = [
        base_dir / "skills",
        Path(cwd) / ".claude" / "skills",
    ]

    for skills_dir in search_dirs:
        if not skills_dir.is_dir():
            continue

        for skill_file in sorted(skills_dir.glob("*.md")):
            skill = _parse_skill_file(skill_file)
            if skill:
                skills.append(skill)

    return skills


def _parse_skill_file(path: Path) -> Skill | None:
    """Parse a skill markdown file with optional YAML frontmatter."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    name = path.stem
    description = ""
    trigger = ""
    prompt = text

    # Parse YAML frontmatter if present
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        prompt = fm_match.group(2).strip()

        for line in frontmatter.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("trigger:"):
                trigger = line.split(":", 1)[1].strip().strip("\"'")

    if not prompt.strip():
        return None

    return Skill(
        name=name,
        description=description or f"Skill: {name}",
        prompt=prompt,
        trigger=trigger,
        source_path=str(path),
    )


def get_skill_by_name(skills: list[Skill], name: str) -> Skill | None:
    """Find a skill by name (case-insensitive)."""
    name_lower = name.lower()
    for skill in skills:
        if skill.name.lower() == name_lower:
            return skill
    return None
