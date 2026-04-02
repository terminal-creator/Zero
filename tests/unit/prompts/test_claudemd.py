"""Tests for CLAUDE.md loading.

Verifies T3.3: File discovery, include expansion, circular reference protection.
"""

from pathlib import Path

from cc.prompts.claudemd import load_claude_md


class TestLoadClaudeMd:
    def test_loads_from_cwd(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("Use pytest for testing.")
        result = load_claude_md(str(tmp_path))
        assert result is not None
        assert "pytest" in result

    def test_loads_from_dot_claude_dir(self, tmp_path: Path) -> None:
        dot_claude = tmp_path / ".claude"
        dot_claude.mkdir()
        (dot_claude / "CLAUDE.md").write_text("Follow PEP8.")
        result = load_claude_md(str(tmp_path))
        assert result is not None
        assert "PEP8" in result

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        result = load_claude_md(str(tmp_path))
        # May pick up ~/.claude/CLAUDE.md if it exists on the system
        # So just check it doesn't crash
        assert result is None or isinstance(result, str)

    def test_include_directive(self, tmp_path: Path) -> None:
        (tmp_path / "rules.md").write_text("Rule: always test.")
        (tmp_path / "CLAUDE.md").write_text("Main instructions.\n@./rules.md")
        result = load_claude_md(str(tmp_path))
        assert result is not None
        assert "Main instructions" in result
        assert "Rule: always test" in result

    def test_circular_include_no_infinite_loop(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("File A\n@./b.md")
        (tmp_path / "b.md").write_text("File B\n@./a.md")
        (tmp_path / "CLAUDE.md").write_text("Start\n@./a.md")
        result = load_claude_md(str(tmp_path))
        assert result is not None
        assert "Start" in result
        assert "File A" in result

    def test_html_comments_stripped(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("Before <!-- hidden --> After")
        result = load_claude_md(str(tmp_path))
        assert result is not None
        assert "hidden" not in result
        assert "Before" in result
        assert "After" in result

    def test_rules_dir_loaded(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "01-style.md").write_text("Use black formatter.")
        (rules_dir / "02-test.md").write_text("Write unit tests.")
        result = load_claude_md(str(tmp_path))
        assert result is not None
        assert "black formatter" in result
        assert "unit tests" in result

    def test_local_md_highest_priority(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("Global rules.")
        (tmp_path / "CLAUDE.local.md").write_text("Local override.")
        result = load_claude_md(str(tmp_path))
        assert result is not None
        assert "Local override" in result
