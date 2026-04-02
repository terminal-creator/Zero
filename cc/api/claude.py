"""Streaming API interaction with Claude.

Corresponds to TS: services/api/claude.ts — queryModelWithStreaming(),
stream event parsing, and response assembly.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import anthropic

from cc.core.events import (
    ErrorEvent,
    QueryEvent,
    TextDelta,
    ThinkingDelta,
    ToolUseStart,
    TurnComplete,
)
from cc.models.content_blocks import (
    AssistantContentBlock,
    RedactedThinkingBlock,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)
from cc.models.messages import Usage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


async def stream_response(
    client: anthropic.AsyncAnthropic,
    *,
    messages: list[dict[str, Any]],
    system: str | list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 16384,
    thinking: dict[str, Any] | None = None,
) -> AsyncIterator[QueryEvent]:
    """Stream a response from the Claude API and yield QueryEvents.

    Corresponds to TS: services/api/claude.ts queryModelWithStreaming().

    Uses the raw stream API to process SSE events directly, avoiding
    type union issues with the high-level stream wrapper.

    Yields:
        QueryEvent instances (TextDelta, ToolUseStart, etc.).
    """
    # Build request parameters
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "system": system,
    }

    if tools:
        params["tools"] = tools

    if thinking:
        params["thinking"] = thinking
    else:
        params["temperature"] = 1.0

    # State for accumulating the streaming response
    content_blocks: dict[int, dict[str, Any]] = {}
    final_content: list[AssistantContentBlock] = []
    usage = Usage()
    stop_reason = "end_turn"

    try:
        async with client.messages.stream(**params) as stream:
            async for event in stream:
                event_type = getattr(event, "type", "")

                if event_type == "message_start":
                    msg = getattr(event, "message", None)
                    if msg:
                        msg_usage = getattr(msg, "usage", None)
                        if msg_usage:
                            usage.input_tokens = getattr(msg_usage, "input_tokens", 0)
                            usage.cache_creation_input_tokens = getattr(
                                msg_usage, "cache_creation_input_tokens", 0
                            )
                            usage.cache_read_input_tokens = getattr(
                                msg_usage, "cache_read_input_tokens", 0
                            )

                elif event_type == "content_block_start":
                    idx: int = getattr(event, "index", 0)
                    cb = getattr(event, "content_block", None)
                    if cb is None:
                        continue
                    block_type: str = getattr(cb, "type", "")

                    if block_type == "text":
                        content_blocks[idx] = {"type": "text", "text": ""}
                    elif block_type == "tool_use":
                        content_blocks[idx] = {
                            "type": "tool_use",
                            "id": getattr(cb, "id", ""),
                            "name": getattr(cb, "name", ""),
                            "input_json": "",
                        }
                    elif block_type == "thinking":
                        content_blocks[idx] = {"type": "thinking", "thinking": ""}
                    elif block_type == "redacted_thinking":
                        content_blocks[idx] = {
                            "type": "redacted_thinking",
                            "data": getattr(cb, "data", ""),
                        }

                elif event_type == "content_block_delta":
                    idx = getattr(event, "index", 0)
                    delta = getattr(event, "delta", None)
                    if delta is None or idx not in content_blocks:
                        continue

                    block = content_blocks[idx]
                    delta_type: str = getattr(delta, "type", "")

                    if delta_type == "text_delta":
                        text: str = getattr(delta, "text", "")
                        block["text"] += text
                        yield TextDelta(text=text)

                    elif delta_type == "input_json_delta":
                        block["input_json"] += getattr(delta, "partial_json", "")

                    elif delta_type == "thinking_delta":
                        thinking_text: str = getattr(delta, "thinking", "")
                        block["thinking"] += thinking_text
                        yield ThinkingDelta(text=thinking_text)

                elif event_type == "content_block_stop":
                    idx = getattr(event, "index", 0)
                    if idx not in content_blocks:
                        continue

                    block = content_blocks[idx]
                    finished_block: AssistantContentBlock

                    if block["type"] == "text":
                        finished_block = TextBlock(text=block["text"])
                    elif block["type"] == "tool_use":
                        try:
                            parsed_input = json.loads(block["input_json"]) if block["input_json"] else {}
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse tool input JSON: %s", block["input_json"][:200])
                            parsed_input = {}

                        finished_block = ToolUseBlock(
                            id=block["id"],
                            name=block["name"],
                            input=parsed_input,
                        )
                        yield ToolUseStart(
                            tool_name=block["name"],
                            tool_id=block["id"],
                            input=parsed_input,
                        )
                    elif block["type"] == "thinking":
                        finished_block = ThinkingBlock(thinking=block["thinking"])
                    elif block["type"] == "redacted_thinking":
                        finished_block = RedactedThinkingBlock(data=block.get("data", ""))
                    else:
                        continue

                    final_content.append(finished_block)

                elif event_type == "message_delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        stop_reason = getattr(delta, "stop_reason", "end_turn") or "end_turn"
                    evt_usage = getattr(event, "usage", None)
                    if evt_usage:
                        usage.output_tokens = getattr(evt_usage, "output_tokens", 0)

    except anthropic.APIStatusError as e:
        error_type = ""
        if hasattr(e, "body") and isinstance(e.body, dict):
            error_info = e.body.get("error", {})
            if isinstance(error_info, dict):
                error_type = error_info.get("type", "")

        yield ErrorEvent(
            message=str(e),
            is_recoverable=e.status_code in (429, 529) or error_type == "overloaded_error",
        )
        return

    except anthropic.APIConnectionError as e:
        yield ErrorEvent(message=f"Connection error: {e}", is_recoverable=True)
        return

    yield TurnComplete(stop_reason=stop_reason, usage=usage)
