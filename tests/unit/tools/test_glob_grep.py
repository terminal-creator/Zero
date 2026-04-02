"""Tests for GlobTool and GrepTool.

Verifies T4.7, T4.8.
"""

from pathlib import Path

from cc.tools.glob_tool.glob_tool import GlobTool
from cc.tools.grep_tool.grep_tool import GrepTool


class TestGlobTool:
    async def test_find_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "b.py").write_text("# b")
        (tmp_path / "c.txt").write_text("c")
        tool = GlobTool()
        result = await tool.execute({"pattern": "*.py", "path": str(tmp_path)})
        assert "a.py" in result.content
        assert "b.py" in result.content
        assert "c.txt" not in result.content

    async def test_empty_dir(self, tmp_path: Path) -> None:
        tool = GlobTool()
        result = await tool.execute({"pattern": "*.py", "path": str(tmp_path)})
        assert "No files found" in result.content

    def test_is_concurrency_safe(self) -> None:
        tool = GlobTool()
        assert tool.is_concurrency_safe({}) is True


class TestGrepTool:
    async def test_find_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "test.py").write_text("def hello():\n    return 42\n")
        tool = GrepTool()
        result = await tool.execute({
            "pattern": "def hello",
            "path": str(tmp_path),
            "output_mode": "content",
        })
        assert "def hello" in result.content

    async def test_files_with_matches(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("hello world")
        (tmp_path / "b.py").write_text("goodbye")
        tool = GrepTool()
        result = await tool.execute({
            "pattern": "hello",
            "path": str(tmp_path),
            "output_mode": "files_with_matches",
        })
        assert "a.py" in result.content
        assert "b.py" not in result.content

    async def test_no_matches(self, tmp_path: Path) -> None:
        (tmp_path / "test.py").write_text("hello")
        tool = GrepTool()
        result = await tool.execute({
            "pattern": "nonexistent_string_xyz",
            "path": str(tmp_path),
        })
        assert "No matches" in result.content

    def test_is_concurrency_safe(self) -> None:
        tool = GrepTool()
        assert tool.is_concurrency_safe({}) is True
