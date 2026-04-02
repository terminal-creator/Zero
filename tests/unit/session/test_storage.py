"""Tests for session storage.

Verifies T6.1: save/load round-trip, missing session, corrupt data.
"""

from pathlib import Path

from cc.models.content_blocks import TextBlock, ToolResultBlock, ToolUseBlock
from cc.models.messages import AssistantMessage, CompactBoundaryMessage, Message, UserMessage
from cc.session.storage import list_sessions, load_session, save_session


class TestSessionStorage:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        messages: list[Message] = [
            UserMessage(content="hello"),
            AssistantMessage(content=[TextBlock(text="hi there")]),
            UserMessage(content="how are you"),
        ]
        save_session("test-1", messages, claude_dir=tmp_path)
        loaded = load_session("test-1", claude_dir=tmp_path)

        assert loaded is not None
        assert len(loaded) == 3
        assert isinstance(loaded[0], UserMessage)
        assert isinstance(loaded[1], AssistantMessage)

    def test_roundtrip_with_tool_use(self, tmp_path: Path) -> None:
        messages: list[Message] = [
            UserMessage(content="do it"),
            AssistantMessage(content=[
                TextBlock(text="ok"),
                ToolUseBlock(id="t1", name="bash", input={"command": "ls"}),
            ]),
            UserMessage(content=[
                ToolResultBlock(tool_use_id="t1", content="file1.py"),
            ]),
        ]
        save_session("test-2", messages, claude_dir=tmp_path)
        loaded = load_session("test-2", claude_dir=tmp_path)

        assert loaded is not None
        assert len(loaded) == 3

    def test_roundtrip_compact_boundary(self, tmp_path: Path) -> None:
        messages: list[Message] = [
            CompactBoundaryMessage(summary="Previous discussion about X."),
            UserMessage(content="continue"),
        ]
        save_session("test-3", messages, claude_dir=tmp_path)
        loaded = load_session("test-3", claude_dir=tmp_path)

        assert loaded is not None
        assert isinstance(loaded[0], CompactBoundaryMessage)
        assert loaded[0].summary == "Previous discussion about X."

    def test_missing_session_returns_none(self, tmp_path: Path) -> None:
        result = load_session("nonexistent", claude_dir=tmp_path)
        assert result is None

    def test_corrupt_line_skipped(self, tmp_path: Path) -> None:
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir(parents=True)
        path = sessions_dir / "corrupt.jsonl"
        path.write_text(
            '{"type":"user","content":"good","uuid":"1","timestamp":""}\n'
            "{bad json\n"
            '{"type":"user","content":"also good","uuid":"2","timestamp":""}\n'
        )
        loaded = load_session("corrupt", claude_dir=tmp_path)
        assert loaded is not None
        assert len(loaded) == 2

    def test_list_sessions(self, tmp_path: Path) -> None:
        save_session("a", [UserMessage(content="x")], claude_dir=tmp_path)
        save_session("b", [UserMessage(content="y")], claude_dir=tmp_path)
        sessions = list_sessions(claude_dir=tmp_path)
        assert len(sessions) == 2
        assert "a" in sessions
        assert "b" in sessions

    def test_load_does_not_mkdir(self, tmp_path: Path) -> None:
        """Regression: load_session must not create directories."""
        fake_claude = tmp_path / "nonexistent_claude"
        result = load_session("anything", claude_dir=fake_claude)
        assert result is None
        assert not (fake_claude / "sessions").exists()

    def test_list_sessions_nonexistent_dir(self, tmp_path: Path) -> None:
        """Regression: list_sessions must not crash or mkdir on missing dir."""
        fake_claude = tmp_path / "nonexistent_claude"
        sessions = list_sessions(claude_dir=fake_claude)
        assert sessions == []
        assert not (fake_claude / "sessions").exists()
