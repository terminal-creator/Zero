"""Tests for query loop error recovery and auto-compact.

Verifies T5.3 and T5.4.
"""

from typing import Any

from cc.core.events import ErrorEvent, TextDelta, ToolResultReady, ToolUseStart, TurnComplete
from cc.core.query_loop import query_loop
from cc.models.messages import Message, Usage, UserMessage
from cc.tools.base import ToolRegistry


class TestQueryLoopTextOnly:
    async def test_simple_text_response(self) -> None:
        """T5.1: Mock text response → TextDelta + TurnComplete."""
        registry = ToolRegistry()
        messages: list[Message] = [UserMessage(content="hello")]

        call_count = 0

        async def mock_call_model(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            yield TextDelta(text="Hi there!")
            yield TurnComplete(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))

        events = [
            e
            async for e in query_loop(
                messages=messages,
                system_prompt="test",
                tools=registry,
                call_model=mock_call_model,
            )
        ]

        text_events = [e for e in events if isinstance(e, TextDelta)]
        turn_events = [e for e in events if isinstance(e, TurnComplete)]

        assert len(text_events) == 1
        assert text_events[0].text == "Hi there!"
        assert len(turn_events) == 1
        assert turn_events[0].stop_reason == "end_turn"


class TestQueryLoopMaxTokensRecovery:
    async def test_max_tokens_escalate(self) -> None:
        """T5.3: First max_tokens → escalate to 64K and retry."""
        registry = ToolRegistry()
        messages: list[Message] = [UserMessage(content="write long essay")]

        call_count = 0

        async def mock_call_model(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            max_tokens = kwargs.get("max_tokens", 16384)
            if call_count == 1:
                yield TextDelta(text="Start of essay...")
                yield TurnComplete(stop_reason="max_tokens", usage=Usage())
            else:
                # Second call should have escalated max_tokens
                assert max_tokens == 65536
                yield TextDelta(text="Continued essay...")
                yield TurnComplete(stop_reason="end_turn", usage=Usage())

        events = [
            e
            async for e in query_loop(
                messages=messages,
                system_prompt="test",
                tools=registry,
                call_model=mock_call_model,
                max_turns=5,
            )
        ]

        assert call_count == 2
        text_parts = [e.text for e in events if isinstance(e, TextDelta)]
        assert "Continued essay..." in text_parts

    async def test_max_tokens_gives_up_after_3(self) -> None:
        """T5.3: After 3 recovery attempts, stop."""
        registry = ToolRegistry()
        messages: list[Message] = [UserMessage(content="infinite")]

        call_count = 0

        async def mock_call_model(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            yield TextDelta(text=f"Chunk {call_count}")
            yield TurnComplete(stop_reason="max_tokens", usage=Usage())

        async for _event in query_loop(
            messages=messages,
            system_prompt="test",
            tools=registry,
            call_model=mock_call_model,
            max_turns=10,
        ):
            pass

        # Should stop after initial + 3 recoveries = 4 calls
        assert call_count <= 4


class TestQueryLoopRecoverableError:
    async def test_recoverable_error_retries(self) -> None:
        """T5.3: Recoverable API error → retry after sleep."""
        registry = ToolRegistry()
        messages: list[Message] = [UserMessage(content="test")]

        call_count = 0

        async def mock_call_model(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield ErrorEvent(message="429 rate limited", is_recoverable=True)
            else:
                yield TextDelta(text="Success!")
                yield TurnComplete(stop_reason="end_turn", usage=Usage())

        events = [
            e
            async for e in query_loop(
                messages=messages,
                system_prompt="test",
                tools=registry,
                call_model=mock_call_model,
                max_turns=5,
            )
        ]

        assert call_count == 2
        text_parts = [e.text for e in events if isinstance(e, TextDelta)]
        assert "Success!" in text_parts

    async def test_non_recoverable_error_stops(self) -> None:
        """Non-recoverable error → yield error and stop."""
        registry = ToolRegistry()
        messages: list[Message] = [UserMessage(content="test")]

        async def mock_call_model(**kwargs: Any) -> Any:
            yield ErrorEvent(message="Fatal error", is_recoverable=False)

        events = [
            e
            async for e in query_loop(
                messages=messages,
                system_prompt="test",
                tools=registry,
                call_model=mock_call_model,
            )
        ]

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1
        assert "Fatal" in error_events[0].message

    async def test_recoverable_error_does_not_consume_turns(self) -> None:
        """FIX check.md #1: Recoverable errors must not eat turn budget.

        Previously, a connection error would increment turn_count on each retry,
        eventually reporting "Max turns reached" instead of the real error.
        """
        registry = ToolRegistry()
        messages: list[Message] = [UserMessage(content="test")]

        call_count = 0

        async def mock_call_model(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            # Always fail with recoverable error
            yield ErrorEvent(message="Connection error: timeout", is_recoverable=True)

        events = [
            e
            async for e in query_loop(
                messages=messages,
                system_prompt="test",
                tools=registry,
                call_model=mock_call_model,
                max_turns=1,  # Only 1 real turn allowed
            )
        ]

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1
        # MUST report the actual error, NOT "Max turns (1) reached"
        assert "Connection error" in error_events[0].message or "Last error" in error_events[0].message
        assert "Max turns" not in error_events[0].message

    async def test_tool_follow_up_uses_blocks_not_just_stop_reason(self) -> None:
        """FIX check.md #4: Tool execution triggered by blocks presence, not stop_reason.

        TS: src/query.ts:554-557 explicitly notes stop_reason=="tool_use" is unreliable.
        If tool_use blocks were collected, execute them regardless of stop_reason.
        """
        registry = ToolRegistry()

        from cc.tools.bash.bash_tool import BashTool

        registry.register(BashTool())

        messages: list[Message] = [UserMessage(content="test")]

        async def mock_call_model(**kwargs: Any) -> Any:
            # Return a tool_use block but with stop_reason="end_turn" (unreliable)
            yield ToolUseStart(tool_name="Bash", tool_id="tu_1", input={"command": "echo fixed"})
            yield TurnComplete(stop_reason="end_turn", usage=Usage())

        events = [
            e
            async for e in query_loop(
                messages=messages,
                system_prompt="test",
                tools=registry,
                call_model=mock_call_model,
                max_turns=3,
            )
        ]

        # Tool should still have been executed even though stop_reason was "end_turn"

        tool_results = [e for e in events if isinstance(e, ToolResultReady)]
        assert len(tool_results) >= 1
