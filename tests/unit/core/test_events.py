"""Tests for event types.

Verifies T1.3: QueryEvent types have meaningful repr.
"""

from cc.core.events import (
    CompactOccurred,
    ErrorEvent,
    TextDelta,
    ThinkingDelta,
    ToolResultReady,
    ToolUseStart,
    TurnComplete,
)
from cc.models.messages import Usage


class TestEventRepr:
    def test_text_delta_repr(self) -> None:
        e = TextDelta(text="hello")
        r = repr(e)
        assert "TextDelta" in r
        assert "hello" in r

    def test_thinking_delta_repr(self) -> None:
        e = ThinkingDelta(text="considering...")
        r = repr(e)
        assert "ThinkingDelta" in r
        assert "considering" in r

    def test_tool_use_start_repr(self) -> None:
        e = ToolUseStart(tool_name="bash", tool_id="tu_1", input={"command": "ls"})
        r = repr(e)
        assert "ToolUseStart" in r
        assert "bash" in r

    def test_tool_result_ready_repr(self) -> None:
        e = ToolResultReady(tool_id="tu_1", content="output")
        r = repr(e)
        assert "ToolResultReady" in r

    def test_compact_occurred_repr(self) -> None:
        e = CompactOccurred(summary_preview="Discussed file editing...")
        r = repr(e)
        assert "CompactOccurred" in r

    def test_turn_complete_repr(self) -> None:
        e = TurnComplete(stop_reason="end_turn", usage=Usage(input_tokens=100, output_tokens=50))
        r = repr(e)
        assert "TurnComplete" in r
        assert "end_turn" in r

    def test_error_event_repr(self) -> None:
        e = ErrorEvent(message="API timeout", is_recoverable=True)
        r = repr(e)
        assert "ErrorEvent" in r
        assert "API timeout" in r
