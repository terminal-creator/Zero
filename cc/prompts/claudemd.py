"""CLAUDE.md file loading.

Corresponds to TS: utils/claudemd.ts.
"""

from __future__ import annotations

import re
from pathlib import Path


def load_claude_md(cwd: str) -> str | None:
    """Load and merge CLAUDE.md files from the directory hierarchy.

    Corresponds to TS: utils/claudemd.ts loadClaudeMdFiles().

    Search order (lowest to highest priority):
    1. ~/.claude/CLAUDE.md (user global)
    2. From cwd up to root: CLAUDE.md, .claude/CLAUDE.md
    3. .claude/rules/*.md
    4. CLAUDE.local.md (private project-specific)

    Supports @path include directives with circular reference protection.
    """
    contents: list[str] = []

    # User global
    user_global = Path.home() / ".claude" / "CLAUDE.md"
    if user_global.is_file():
        text = _read_and_expand(user_global, set())
        if text:
            contents.append(text)

    # Walk from cwd upward
    current = Path(cwd).resolve()
    ancestors: list[Path] = []
    while True:
        ancestors.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Process ancestors from root to cwd (so cwd has highest priority)
    for ancestor in reversed(ancestors):
        for candidate in [
            ancestor / "CLAUDE.md",
            ancestor / ".claude" / "CLAUDE.md",
        ]:
            if candidate.is_file() and candidate != user_global:
                text = _read_and_expand(candidate, set())
                if text:
                    contents.append(text)

        # .claude/rules/*.md
        rules_dir = ancestor / ".claude" / "rules"
        if rules_dir.is_dir():
            for rule_file in sorted(rules_dir.glob("*.md")):
                if rule_file.is_file():
                    text = _read_and_expand(rule_file, set())
                    if text:
                        contents.append(text)

    # CLAUDE.local.md in cwd
    local_md = Path(cwd) / "CLAUDE.local.md"
    if local_md.is_file():
        text = _read_and_expand(local_md, set())
        if text:
            contents.append(text)

    if not contents:
        return None

    return "\n\n".join(contents)


def _read_and_expand(path: Path, seen: set[Path], max_depth: int = 10) -> str:
    """Read a file and expand @include directives.

    Args:
        path: File to read.
        seen: Set of already-visited paths (circular reference protection).
        max_depth: Maximum include nesting depth.
    """
    resolved = path.resolve()
    if resolved in seen or max_depth <= 0:
        return ""

    seen.add(resolved)

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""

    # Strip HTML block comments
    text = re.sub(r"<!--[\s\S]*?-->", "", text)

    # Expand @include directives
    def expand_include(match: re.Match[str]) -> str:
        include_path_str = match.group(1).strip()

        if include_path_str.startswith("~/"):
            include_path = Path.home() / include_path_str[2:]
        elif include_path_str.startswith("./") or not include_path_str.startswith("/"):
            include_path = path.parent / include_path_str
        else:
            include_path = Path(include_path_str)

        if include_path.is_file():
            return _read_and_expand(include_path, seen.copy(), max_depth - 1)
        return ""

    text = re.sub(r"^@(.+)$", expand_include, text, flags=re.MULTILINE)

    return text.strip()
