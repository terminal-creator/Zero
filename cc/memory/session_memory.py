"""Memory system — extract and persist memories from conversations.

Corresponds to TS: services/SessionMemory/prompts.ts + services/extractMemories/.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _project_id(cwd: str) -> str:
    """Deterministic project ID from cwd path.

    FIX: Uses hashlib.sha256 instead of hash() which is randomized per-process
    since Python 3.3 (PYTHONHASHSEED). This ensures the same cwd always maps
    to the same memory directory across process restarts.
    """
    return hashlib.sha256(cwd.encode("utf-8")).hexdigest()[:12]


def get_memory_dir(cwd: str, claude_dir: Path | None = None) -> Path:
    """Get the memory directory path for the current project.

    Does NOT create the directory — callers that need to write should mkdir themselves.
    """
    base = claude_dir or (Path.home() / ".claude")
    return base / "projects" / _project_id(cwd) / "memory"


def load_memories(cwd: str, claude_dir: Path | None = None) -> list[dict[str, str]]:
    """Load all saved memories for the current project.

    FIX: Does not mkdir on read. Returns empty list if directory doesn't exist.
    """
    mem_dir = get_memory_dir(cwd, claude_dir)
    if not mem_dir.is_dir():
        return []

    memories: list[dict[str, str]] = []
    for md_file in sorted(mem_dir.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
            memories.append({"name": md_file.stem, "content": text})
        except (OSError, UnicodeDecodeError):
            continue

    return memories


def save_memory(
    cwd: str,
    name: str,
    content: str,
    claude_dir: Path | None = None,
) -> Path:
    """Save a memory to the project memory directory.

    Creates the directory on write (not on read).
    """
    mem_dir = get_memory_dir(cwd, claude_dir)
    mem_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = mem_dir / f"{safe_name}.md"
    path.write_text(content, encoding="utf-8")
    return path


def delete_memory(
    cwd: str,
    name: str,
    claude_dir: Path | None = None,
) -> bool:
    """Delete a memory by name."""
    mem_dir = get_memory_dir(cwd, claude_dir)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = mem_dir / f"{safe_name}.md"
    if path.is_file():
        path.unlink()
        return True
    return False


def format_memories_for_prompt(memories: list[dict[str, str]]) -> str | None:
    """Format loaded memories into a system prompt section.

    DEPRECATED: Use build_memory_prompt() from cc.prompts.sections instead,
    which generates the full behavioral instructions. This function is kept
    for backward compatibility with tests.
    """
    if not memories:
        return None

    parts = ["# Memories\n\nThe following memories were saved from previous conversations:\n"]
    for mem in memories:
        parts.append(f"## {mem['name']}\n{mem['content']}")

    return "\n\n".join(parts)


def load_memory_index(cwd: str, claude_dir: Path | None = None) -> str | None:
    """Load the MEMORY.md index file content.

    Corresponds to TS: memdir/memdir.ts reading ENTRYPOINT_NAME in buildMemoryPrompt().

    Returns the content string if MEMORY.md exists and is non-empty, else None.
    """
    mem_dir = get_memory_dir(cwd, claude_dir)
    index_path = mem_dir / "MEMORY.md"
    if not index_path.is_file():
        return None
    try:
        content = index_path.read_text(encoding="utf-8").strip()
        return content if content else None
    except (OSError, UnicodeDecodeError):
        return None
