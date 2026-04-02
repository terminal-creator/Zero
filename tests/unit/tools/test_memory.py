"""Tests for Memory system.

Verifies T10.4: Memory save, load, delete, format.
"""

from pathlib import Path

from cc.memory.session_memory import (
    delete_memory,
    format_memories_for_prompt,
    load_memories,
    save_memory,
)


class TestMemory:
    def test_save_and_load(self, tmp_path: Path) -> None:
        save_memory("/project", "user_prefs", "User prefers tabs over spaces.", claude_dir=tmp_path)
        memories = load_memories("/project", claude_dir=tmp_path)
        assert len(memories) == 1
        assert memories[0]["name"] == "user_prefs"
        assert "tabs" in memories[0]["content"]

    def test_save_multiple(self, tmp_path: Path) -> None:
        save_memory("/project", "pref1", "Use pytest.", claude_dir=tmp_path)
        save_memory("/project", "pref2", "Use black formatter.", claude_dir=tmp_path)
        memories = load_memories("/project", claude_dir=tmp_path)
        assert len(memories) == 2

    def test_delete(self, tmp_path: Path) -> None:
        save_memory("/project", "temp", "Temporary.", claude_dir=tmp_path)
        assert delete_memory("/project", "temp", claude_dir=tmp_path) is True
        memories = load_memories("/project", claude_dir=tmp_path)
        assert len(memories) == 0

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        assert delete_memory("/project", "nope", claude_dir=tmp_path) is False

    def test_format_for_prompt(self) -> None:
        memories = [
            {"name": "style", "content": "Use tabs."},
            {"name": "tools", "content": "Prefer ruff over flake8."},
        ]
        result = format_memories_for_prompt(memories)
        assert result is not None
        assert "tabs" in result
        assert "ruff" in result
        assert "Memories" in result

    def test_format_empty(self) -> None:
        result = format_memories_for_prompt([])
        assert result is None

    def test_empty_project(self, tmp_path: Path) -> None:
        memories = load_memories("/nonexistent_project", claude_dir=tmp_path)
        assert memories == []

    def test_project_id_deterministic(self) -> None:
        """FIX regression: project_id must be stable across calls (no hash randomization)."""
        from cc.memory.session_memory import _project_id

        id1 = _project_id("/some/project/path")
        id2 = _project_id("/some/project/path")
        assert id1 == id2
        assert len(id1) == 12
        # Different paths → different IDs
        id3 = _project_id("/other/path")
        assert id1 != id3

    def test_load_does_not_mkdir(self, tmp_path: Path) -> None:
        """FIX regression: load_memories must not create directories."""
        fake_claude = tmp_path / "dot_claude"
        # Don't create it — it shouldn't exist
        memories = load_memories("/project", claude_dir=fake_claude)
        assert memories == []
        # Verify no directory was created
        assert not (fake_claude / "projects").exists()
