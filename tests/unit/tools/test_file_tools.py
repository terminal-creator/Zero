"""Tests for FileReadTool, FileEditTool, FileWriteTool.

Verifies T4.4, T4.5, T4.6.
"""

from pathlib import Path

from cc.tools.file_edit.file_edit_tool import FileEditTool
from cc.tools.file_read.file_read_tool import FileReadTool
from cc.tools.file_write.file_write_tool import FileWriteTool


class TestFileReadTool:
    async def test_read_small_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")
        tool = FileReadTool()
        result = await tool.execute({"file_path": str(f)})
        assert "line1" in result.content
        assert "1\t" in result.content  # Line numbers

    async def test_read_with_offset_limit(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("\n".join(f"line{i}" for i in range(1, 11)))
        tool = FileReadTool()
        result = await tool.execute({"file_path": str(f), "offset": 3, "limit": 2})
        assert "line3" in result.content
        assert "line4" in result.content
        assert "line1" not in result.content

    async def test_nonexistent_file(self) -> None:
        tool = FileReadTool()
        result = await tool.execute({"file_path": "/nonexistent/file.txt"})
        assert result.is_error is True
        assert "does not exist" in result.content.lower()

    async def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        tool = FileReadTool()
        result = await tool.execute({"file_path": str(f)})
        assert "empty" in result.content.lower()

    async def test_large_file_truncated(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("\n".join(f"line{i}" for i in range(5000)))
        tool = FileReadTool()
        result = await tool.execute({"file_path": str(f)})
        assert "more lines" in result.content.lower()

    def test_is_concurrency_safe(self) -> None:
        tool = FileReadTool()
        assert tool.is_concurrency_safe({}) is True


class TestFileEditTool:
    async def test_replace_unique(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text('print("hello")\n')
        tool = FileEditTool()
        result = await tool.execute({
            "file_path": str(f),
            "old_string": '"hello"',
            "new_string": '"world"',
        })
        assert result.is_error is False
        assert f.read_text() == 'print("world")\n'

    async def test_not_unique_error(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("foo\nfoo\nbar\n")
        tool = FileEditTool()
        result = await tool.execute({
            "file_path": str(f),
            "old_string": "foo",
            "new_string": "baz",
        })
        assert result.is_error is True
        assert "2 times" in result.content

    async def test_replace_all(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("foo\nfoo\nbar\n")
        tool = FileEditTool()
        result = await tool.execute({
            "file_path": str(f),
            "old_string": "foo",
            "new_string": "baz",
            "replace_all": True,
        })
        assert result.is_error is False
        assert f.read_text() == "baz\nbaz\nbar\n"

    async def test_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello\n")
        tool = FileEditTool()
        result = await tool.execute({
            "file_path": str(f),
            "old_string": "nonexistent",
            "new_string": "x",
        })
        assert result.is_error is True
        assert "not found" in result.content.lower()

    async def test_same_string_error(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello\n")
        tool = FileEditTool()
        result = await tool.execute({
            "file_path": str(f),
            "old_string": "hello",
            "new_string": "hello",
        })
        assert result.is_error is True
        assert "different" in result.content.lower()

    async def test_diff_output(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("old_value\n")
        tool = FileEditTool()
        result = await tool.execute({
            "file_path": str(f),
            "old_string": "old_value",
            "new_string": "new_value",
        })
        assert "-old_value" in result.content or "old_value" in result.content


class TestFileWriteTool:
    async def test_write_new_file(self, tmp_path: Path) -> None:
        f = tmp_path / "new.txt"
        tool = FileWriteTool()
        result = await tool.execute({"file_path": str(f), "content": "hello world\n"})
        assert result.is_error is False
        assert f.read_text() == "hello world\n"

    async def test_overwrite_existing(self, tmp_path: Path) -> None:
        f = tmp_path / "existing.txt"
        f.write_text("old content")
        tool = FileWriteTool()
        result = await tool.execute({"file_path": str(f), "content": "new content"})
        assert result.is_error is False
        assert f.read_text() == "new content"

    async def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        f = tmp_path / "a" / "b" / "c" / "test.txt"
        tool = FileWriteTool()
        result = await tool.execute({"file_path": str(f), "content": "deep"})
        assert result.is_error is False
        assert f.read_text() == "deep"
