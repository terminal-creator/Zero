"""Context compaction — summarize old messages to free context.

Corresponds to TS: services/compact/compact.ts + autoCompact.ts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cc.models.messages import (
    AssistantMessage,
    CompactBoundaryMessage,
    Message,
    UserMessage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from cc.core.events import QueryEvent

logger = logging.getLogger(__name__)

# Corresponds to TS: services/compact/autoCompact.ts thresholds
AUTO_COMPACT_BUFFER = 13_000  # tokens below context window to trigger
MAX_CONSECUTIVE_FAILURES = 3
POST_COMPACT_KEEP_TURNS = 4  # Keep last N user-assistant pairs


# Corresponds to TS: services/compact/compact.ts compaction prompt
COMPACT_SYSTEM_PROMPT = """You are a conversation summarizer. Given a conversation between a user and an assistant, create a concise summary that preserves:

1. Key decisions and outcomes
2. Important file paths, function names, and code changes
3. Current state of the task
4. Any unresolved issues or next steps

Be factual and specific. Include exact file paths, line numbers, and code identifiers mentioned. Do not editorialize or add opinions. Output only the summary text."""


async def compact_messages(
    messages: list[Message],
    call_model: Callable[..., AsyncIterator[QueryEvent]],
) -> list[Message]:
    """Compact a conversation by summarizing old messages.

    Corresponds to TS: services/compact/compact.ts core compaction logic.

    Keeps the last POST_COMPACT_KEEP_TURNS of conversation and summarizes
    the rest into a CompactBoundaryMessage.

    Args:
        messages: Full conversation messages.
        call_model: API call function for generating the summary.

    Returns:
        Compacted message list with summary boundary.
    """
    if len(messages) < POST_COMPACT_KEEP_TURNS * 2 + 2:
        # Not enough messages to compact
        return messages

    # Split into old (to summarize) and recent (to keep)
    keep_count = POST_COMPACT_KEEP_TURNS * 2  # user + assistant pairs
    old_messages = messages[:-keep_count]
    recent_messages = messages[-keep_count:]

    # Build conversation text for summarization
    conversation_text = _messages_to_text(old_messages)

    # Generate summary via API
    from cc.core.events import TextDelta, TurnComplete
    from cc.models.messages import normalize_messages_for_api

    summary_messages: list[Message] = [
        UserMessage(content=f"Summarize this conversation:\n\n{conversation_text}"),
    ]
    api_messages = normalize_messages_for_api(summary_messages)

    summary_parts: list[str] = []
    try:
        async for event in call_model(
            messages=api_messages,
            system=COMPACT_SYSTEM_PROMPT,
            tools=None,
        ):
            if isinstance(event, TextDelta):
                summary_parts.append(event.text)
            elif isinstance(event, TurnComplete):
                break
    except Exception as e:
        logger.warning("Compact failed: %s", e)
        return messages  # Return original on failure

    summary = "".join(summary_parts)
    if not summary.strip():
        logger.warning("Compact produced empty summary")
        return messages

    # Build compacted message list
    boundary = CompactBoundaryMessage(summary=summary)
    return [boundary, *recent_messages]


def should_auto_compact(
    estimated_tokens: int,
    context_window: int = 200_000,
    consecutive_failures: int = 0,
) -> bool:
    """Check if auto-compaction should trigger.

    Corresponds to TS: services/compact/autoCompact.ts shouldAutoCompact().
    """
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        return False

    threshold = context_window - AUTO_COMPACT_BUFFER
    return estimated_tokens >= threshold


def _messages_to_text(messages: list[Message]) -> str:
    """Convert messages to plain text for summarization.

    FIX (check.md #9): Include tool result details instead of folding to "[tool results]".
    """
    from cc.models.content_blocks import ToolResultBlock

    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            if isinstance(msg.content, str):
                parts.append(f"User: {msg.content}")
            else:
                # Extract tool results with details
                sub_parts = []
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        content_preview = block.content if isinstance(block.content, str) else "[structured]"
                        # Truncate long tool results to keep summary manageable
                        if len(content_preview) > 500:
                            content_preview = content_preview[:500] + "..."
                        sub_parts.append(f"  tool_result({block.tool_use_id}): {content_preview}")
                    else:
                        sub_parts.append(f"  {block}")
                parts.append("User (tool results):\n" + "\n".join(sub_parts))
        elif isinstance(msg, AssistantMessage):
            text = msg.get_text()
            tool_uses = msg.get_tool_use_blocks()
            lines = []
            if text:
                lines.append(text)
            for tu in tool_uses:
                lines.append(f"  [called {tu.name}({tu.input})]")
            if lines:
                parts.append("Assistant: " + "\n".join(lines))
        elif isinstance(msg, CompactBoundaryMessage):
            parts.append(f"[Previous summary: {msg.summary}]")
    return "\n\n".join(parts)
