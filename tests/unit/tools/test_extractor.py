"""Tests for memory extraction.

Verifies: automatic memory extraction from conversations.
"""

from pathlib import Path
from typing import Any

from cc.core.events import TextDelta, TurnComplete
from cc.memory.extractor import extract_memories
from cc.memory.session_memory import load_memories
from cc.models.content_blocks import TextBlock
from cc.models.messages import AssistantMessage, Message, Usage, UserMessage


class TestExtractMemories:
    async def test_extracts_user_preference(self, tmp_path: Path) -> None:
        """When conversation has a clear user preference, extraction saves it."""
        messages: list[Message] = [
            UserMessage(content="I'm a data scientist working on ML pipelines"),
            AssistantMessage(content=[TextBlock(text="Got it, I'll help with your ML work.")]),
            UserMessage(content="Always use pytest for testing, never unittest"),
            AssistantMessage(content=[TextBlock(text="Noted, I'll use pytest.")]),
            UserMessage(content="Can you fix the bug in data_loader.py?"),
            AssistantMessage(content=[TextBlock(text="Let me look at it.")]),
        ]

        async def mock_call_model(**kwargs: Any) -> Any:
            resp = (
                '{"memories": [{"name": "user_testing_pref", "type": "feedback",'
                ' "content": "---\\nname: user_testing_pref\\ndescription: User prefers'
                ' pytest\\ntype: feedback\\n---\\nAlways use pytest, never unittest."}]}'
            )
            yield TextDelta(text=resp)
            yield TurnComplete(stop_reason="end_turn", usage=Usage())

        saved = await extract_memories(
            messages, "/project", mock_call_model, claude_dir=tmp_path,
        )

        assert len(saved) == 1
        assert "user_testing_pref" in saved

        # Verify it was actually persisted
        loaded = load_memories("/project", claude_dir=tmp_path)
        assert len(loaded) == 1
        assert "pytest" in loaded[0]["content"]

    async def test_skips_short_conversations(self, tmp_path: Path) -> None:
        """Conversations shorter than MIN_NEW_MESSAGES are skipped."""
        messages: list[Message] = [
            UserMessage(content="hi"),
            AssistantMessage(content=[TextBlock(text="hello")]),
        ]

        call_count = 0

        async def mock_call_model(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            yield TurnComplete(stop_reason="end_turn", usage=Usage())

        saved = await extract_memories(
            messages, "/project", mock_call_model, claude_dir=tmp_path,
        )

        assert saved == []
        assert call_count == 0  # API should not have been called

    async def test_empty_extraction(self, tmp_path: Path) -> None:
        """When model finds nothing to save, no memories are created."""
        messages: list[Message] = [
            UserMessage(content="Fix the typo on line 5"),
            AssistantMessage(content=[TextBlock(text="Fixed.")]),
            UserMessage(content="Thanks"),
            AssistantMessage(content=[TextBlock(text="You're welcome.")]),
            UserMessage(content="Run the tests"),
            AssistantMessage(content=[TextBlock(text="All passing.")]),
        ]

        async def mock_call_model(**kwargs: Any) -> Any:
            yield TextDelta(text='{"memories": []}')
            yield TurnComplete(stop_reason="end_turn", usage=Usage())

        saved = await extract_memories(
            messages, "/project", mock_call_model, claude_dir=tmp_path,
        )

        assert saved == []
        assert load_memories("/project", claude_dir=tmp_path) == []

    async def test_handles_malformed_response(self, tmp_path: Path) -> None:
        """Malformed model response doesn't crash, returns empty."""
        messages: list[Message] = [
            UserMessage(content="a"), AssistantMessage(content=[TextBlock(text="b")]),
            UserMessage(content="c"), AssistantMessage(content=[TextBlock(text="d")]),
            UserMessage(content="e"), AssistantMessage(content=[TextBlock(text="f")]),
        ]

        async def mock_call_model(**kwargs: Any) -> Any:
            yield TextDelta(text="This is not valid JSON at all")
            yield TurnComplete(stop_reason="end_turn", usage=Usage())

        saved = await extract_memories(
            messages, "/project", mock_call_model, claude_dir=tmp_path,
        )

        assert saved == []

    async def test_handles_api_failure(self, tmp_path: Path) -> None:
        """API error during extraction doesn't crash."""
        messages: list[Message] = [
            UserMessage(content="a"), AssistantMessage(content=[TextBlock(text="b")]),
            UserMessage(content="c"), AssistantMessage(content=[TextBlock(text="d")]),
            UserMessage(content="e"), AssistantMessage(content=[TextBlock(text="f")]),
        ]

        async def mock_call_model(**kwargs: Any) -> Any:
            raise ConnectionError("Network down")
            yield  # Make it a generator  # type: ignore[misc]

        saved = await extract_memories(
            messages, "/project", mock_call_model, claude_dir=tmp_path,
        )

        assert saved == []

    async def test_json_in_code_block(self, tmp_path: Path) -> None:
        """Model wraps JSON in ```json``` blocks — still parses correctly."""
        messages: list[Message] = [
            UserMessage(content="I prefer tabs"), AssistantMessage(content=[TextBlock(text="ok")]),
            UserMessage(content="a"), AssistantMessage(content=[TextBlock(text="b")]),
            UserMessage(content="c"), AssistantMessage(content=[TextBlock(text="d")]),
        ]

        async def mock_call_model(**kwargs: Any) -> Any:
            resp = (
                '```json\n{"memories": [{"name": "tabs_pref", "type": "feedback",'
                ' "content": "---\\nname: tabs_pref\\ndescription: tabs\\ntype:'
                ' feedback\\n---\\nUse tabs."}]}\n```'
            )
            yield TextDelta(text=resp)
            yield TurnComplete(stop_reason="end_turn", usage=Usage())

        saved = await extract_memories(
            messages, "/project", mock_call_model, claude_dir=tmp_path,
        )

        assert "tabs_pref" in saved
