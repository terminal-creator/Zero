"""Core conversation query loop.

Corresponds to TS: query.ts — the main while(true) state machine.
Includes error recovery (T5.3) and auto-compact integration (T5.4).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence  # noqa: TC003
from typing import TYPE_CHECKING

from cc.api.token_estimation import estimate_messages_tokens
from cc.compact.compact import should_auto_compact
from cc.core.events import (
    CompactOccurred,
    ErrorEvent,
    QueryEvent,
    TextDelta,
    ThinkingDelta,
    ToolResultReady,
    ToolUseStart,
    TurnComplete,
)
from cc.models.content_blocks import (
    AssistantContentBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from cc.models.messages import (
    AssistantMessage,
    Message,
    Usage,
    UserMessage,
    normalize_messages_for_api,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from cc.tools.base import ToolRegistry

logger = logging.getLogger(__name__)

# Corresponds to TS: query.ts error recovery constants
MAX_OUTPUT_TOKENS_RECOVERY = 3
ESCALATED_MAX_TOKENS = 65536
DEFAULT_CONTEXT_WINDOW = 200_000


async def query_loop(
    *,
    messages: list[Message],
    system_prompt: str,
    tools: ToolRegistry,
    call_model: Callable[..., AsyncIterator[QueryEvent]],
    max_turns: int = 100,
    auto_compact_fn: Callable[..., object] | None = None,
    context_window: int = DEFAULT_CONTEXT_WINDOW,
    hooks: Sequence[object] | None = None,  # Sequence[HookConfig] at runtime
) -> AsyncIterator[QueryEvent]:
    """Execute the core conversation loop.

    Corresponds to TS: query.ts:307-1728 (queryLoop main while(true)).

    Includes:
    - T5.3: Error recovery (prompt_too_long, max_output_tokens, retries)
    - T5.4: Auto-compact integration (token threshold detection)
    - Hooks: passed through to run_tools() for pre/post tool execution

    Bug fixes per check.md:
    - Recoverable errors no longer silently consume turns → tracked separately
    - Tool follow-up checks tool_use_blocks presence, not just stop_reason
    """
    turn_count = 0
    retry_count = 0  # Separate counter for retries — doesn't consume turns
    max_retry = 5  # Cap retries to prevent infinite recovery loops
    max_output_recovery_count = 0
    has_attempted_reactive_compact = False
    compact_consecutive_failures = 0
    current_max_tokens = 16384
    last_error: ErrorEvent | None = None  # Track last error for reporting

    while turn_count < max_turns:
        turn_count += 1

        # Phase 1: Prepare messages + auto-compact check
        api_messages = normalize_messages_for_api(messages)
        tool_schemas = tools.get_api_schemas()

        # T5.4: Auto-compact check before API call
        estimated_tokens = estimate_messages_tokens(api_messages)
        if (
            should_auto_compact(estimated_tokens, context_window, compact_consecutive_failures)
            and auto_compact_fn is not None
        ):
            try:
                from cc.compact.compact import compact_messages

                compacted = await compact_messages(messages, auto_compact_fn)  # type: ignore[arg-type]
                if len(compacted) < len(messages):
                    messages.clear()
                    messages.extend(compacted)
                    compact_consecutive_failures = 0
                    yield CompactOccurred(summary_preview="Context auto-compacted")
                    api_messages = normalize_messages_for_api(messages)
                else:
                    compact_consecutive_failures += 1
            except Exception as e:
                logger.warning("Auto-compact failed: %s", e)
                compact_consecutive_failures += 1

        # Phase 2: Call the model
        accumulated_text = ""
        usage = Usage()
        stop_reason = "end_turn"
        tool_use_blocks: list[ToolUseBlock] = []
        error_event: ErrorEvent | None = None

        async for event in call_model(
            messages=api_messages,
            system=system_prompt,
            tools=tool_schemas if tool_schemas else None,
            max_tokens=current_max_tokens,
        ):
            if isinstance(event, (TextDelta, ThinkingDelta)):
                if isinstance(event, TextDelta):
                    accumulated_text += event.text
                yield event

            elif isinstance(event, ToolUseStart):
                yield event
                tool_use_blocks.append(
                    ToolUseBlock(id=event.tool_id, name=event.tool_name, input=event.input)
                )

            elif isinstance(event, TurnComplete):
                stop_reason = event.stop_reason
                usage = event.usage

            elif isinstance(event, ErrorEvent):
                error_event = event

        # Phase 3: Error recovery
        # FIX (check.md #1): Recoverable errors don't consume turn_count.
        # We decrement turn_count on recovery so the retry doesn't eat a turn budget.
        if error_event is not None:
            last_error = error_event
            recovered = False

            # prompt_too_long → reactive compact
            if "413" in error_event.message or "prompt_too_long" in error_event.message:
                if not has_attempted_reactive_compact and auto_compact_fn is not None:
                    has_attempted_reactive_compact = True
                    try:
                        from cc.compact.compact import compact_messages

                        compacted = await compact_messages(messages, auto_compact_fn)  # type: ignore[arg-type]
                        if len(compacted) < len(messages):
                            messages.clear()
                            messages.extend(compacted)
                            yield CompactOccurred(summary_preview="Reactive compact after prompt_too_long")
                            recovered = True
                    except Exception as e:
                        logger.warning("Reactive compact failed: %s", e)

            # max_output_tokens → escalate or continue
            elif "max_output_tokens" in error_event.message or stop_reason == "max_tokens":
                if max_output_recovery_count == 0:
                    current_max_tokens = ESCALATED_MAX_TOKENS
                    max_output_recovery_count += 1
                    recovered = True
                elif max_output_recovery_count < MAX_OUTPUT_TOKENS_RECOVERY:
                    max_output_recovery_count += 1
                    if accumulated_text:
                        messages.append(AssistantMessage(
                            content=[TextBlock(text=accumulated_text)], usage=usage,
                        ))
                        messages.append(UserMessage(content="Please continue from where you left off."))
                    recovered = True

            # Recoverable API errors (429, 529) → retry
            elif error_event.is_recoverable and retry_count < max_retry:
                    retry_count += 1
                    await asyncio.sleep(min(2.0 * retry_count, 10.0))
                    recovered = True

            if recovered:
                turn_count -= 1  # Don't consume a turn for retries
                continue

            # Non-recoverable: yield the actual error, not "max turns"
            yield error_event
            return

        # Reset retry counter on successful API call
        retry_count = 0
        last_error = None

        # Handle max_tokens stop reason (normal stop, not error)
        if (
            stop_reason == "max_tokens"
            and max_output_recovery_count < MAX_OUTPUT_TOKENS_RECOVERY
            and accumulated_text
        ):
            messages.append(AssistantMessage(
                content=[TextBlock(text=accumulated_text)], usage=usage,
            ))
            messages.append(UserMessage(content="Please continue from where you left off."))
            max_output_recovery_count += 1
            if max_output_recovery_count == 1:
                current_max_tokens = ESCALATED_MAX_TOKENS
            yield TurnComplete(stop_reason="max_tokens", usage=usage)
            continue

        # Build assistant message from accumulated content
        assistant_blocks: list[AssistantContentBlock] = []
        if accumulated_text:
            assistant_blocks.append(TextBlock(text=accumulated_text))
        assistant_blocks.extend(tool_use_blocks)

        assistant_msg = AssistantMessage(
            content=assistant_blocks,
            usage=usage,
            stop_reason=stop_reason,
        )
        messages.append(assistant_msg)

        yield TurnComplete(stop_reason=stop_reason, usage=usage)

        # Phase 4: Tool execution
        # FIX (check.md #4): Check tool_use_blocks presence, not just stop_reason.
        # TS: src/query.ts:554-557 explicitly notes stop_reason=="tool_use" is unreliable.
        if tool_use_blocks:
            from cc.tools.orchestration import run_tools

            tool_results = await run_tools(tool_use_blocks, tools, hooks=hooks)  # type: ignore[arg-type]

            result_blocks: list[ToolResultBlock] = []
            for tool_id, result in tool_results:
                yield ToolResultReady(
                    tool_id=tool_id,
                    content=result.text[:500],
                    is_error=result.is_error,
                )
                # Preserve rich content (images, structured data) when available
                if isinstance(result.content, list):
                    from cc.models.content_blocks import ToolResultContent

                    rich = [ToolResultContent.from_api_dict(b) for b in result.content]
                    result_blocks.append(
                        ToolResultBlock(tool_use_id=tool_id, content=rich, is_error=result.is_error)
                    )
                else:
                    result_blocks.append(
                        ToolResultBlock(tool_use_id=tool_id, content=result.content, is_error=result.is_error)
                    )

            tool_result_msg = UserMessage(content=list(result_blocks))
            messages.append(tool_result_msg)
            continue

        # No tool use — conversation turn is complete
        return

    # FIX (check.md #1): If we hit max turns after retries, report the last real error
    if last_error is not None:
        yield ErrorEvent(message=f"Gave up after retries. Last error: {last_error.message}", is_recoverable=False)
    else:
        yield ErrorEvent(message=f"Max turns ({max_turns}) reached", is_recoverable=False)
