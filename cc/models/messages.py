"""Message types for the conversation system.

Corresponds to TS: types/message.ts (DCE'd) + utils/messages.ts.
Reconstructed from usage patterns in query.ts, utils/messages.ts, Tool.ts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from typing import Any, Literal
from uuid import uuid4

from .content_blocks import (
    AssistantContentBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserContentBlock,
)


@dataclass
class Usage:
    """Token usage statistics from API response.

    Corresponds to TS: @anthropic-ai/sdk BetaUsage.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class UserMessage:
    """A user message in the conversation.

    Corresponds to TS: types/message.ts UserMessage.
    """

    content: str | list[UserContentBlock]
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = ""
    type: Literal["user"] = "user"
    is_meta: bool = False
    is_compact_summary: bool = False

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to Anthropic API MessageParam format."""
        if isinstance(self.content, str):
            api_content: str | list[dict[str, Any]] = self.content
        else:
            api_content = [block.to_api_dict() for block in self.content]
        return {"role": "user", "content": api_content}


@dataclass
class AssistantMessage:
    """An assistant message in the conversation.

    Corresponds to TS: types/message.ts AssistantMessage.
    Contains the raw API response message plus metadata.
    """

    content: list[AssistantContentBlock] = field(default_factory=list)
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = ""
    type: Literal["assistant"] = "assistant"
    stop_reason: str | None = None
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    is_api_error: bool = False

    def to_api_dict(self) -> dict[str, Any]:
        """Convert to Anthropic API MessageParam format."""
        return {
            "role": "assistant",
            "content": [block.to_api_dict() for block in self.content],
        }

    def get_text(self) -> str:
        """Extract concatenated text from all text blocks."""
        return "".join(block.text for block in self.content if isinstance(block, TextBlock))

    def get_tool_use_blocks(self) -> list[ToolUseBlock]:
        """Extract all tool use blocks."""
        return [block for block in self.content if isinstance(block, ToolUseBlock)]


@dataclass
class SystemMessage:
    """A system-level message (informational, error, compact boundary, etc.).

    Corresponds to TS: types/message.ts SystemMessage union.
    """

    content: str
    level: Literal["info", "warning", "error"] = "info"
    type: Literal["system"] = "system"
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = ""


@dataclass
class CompactBoundaryMessage:
    """Marks a compaction boundary. Messages before this were summarized.

    Corresponds to TS: types/message.ts SystemCompactBoundaryMessage.
    """

    summary: str
    type: Literal["compact_boundary"] = "compact_boundary"
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = ""


# Union of all message types in the conversation
Message = UserMessage | AssistantMessage | SystemMessage | CompactBoundaryMessage


def normalize_messages_for_api(messages: list[Message]) -> list[dict[str, Any]]:
    """Normalize conversation messages into Anthropic API format.

    Corresponds to TS: utils/messages.ts normalizeMessagesForAPI().

    Ensures:
    - Only user and assistant messages are included
    - Messages alternate between user and assistant
    - tool_use / tool_result blocks are properly paired
    - No orphaned tool_results
    """
    api_messages: list[dict[str, Any]] = []

    for msg in messages:
        if isinstance(msg, (SystemMessage, CompactBoundaryMessage)):
            # System messages become user messages with the content
            if isinstance(msg, CompactBoundaryMessage):
                api_msg = {"role": "user", "content": f"[Previous conversation summary]\n{msg.summary}"}
            else:
                continue
        elif isinstance(msg, (UserMessage, AssistantMessage)):
            api_msg = msg.to_api_dict()
        else:
            continue

        # Ensure alternating roles
        if api_messages and api_messages[-1]["role"] == api_msg["role"]:
            if api_msg["role"] == "user":
                # Merge consecutive user messages
                _merge_user_messages(api_messages[-1], api_msg)
                continue
            else:
                # Insert empty user message between consecutive assistant messages
                api_messages.append({"role": "user", "content": "Continue."})

        api_messages.append(api_msg)

    # Ensure conversation starts with user message
    if api_messages and api_messages[0]["role"] == "assistant":
        api_messages.insert(0, {"role": "user", "content": "Begin."})

    # Ensure tool_use/tool_result pairing
    _ensure_tool_result_pairing(api_messages)

    return api_messages


def _merge_user_messages(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge source user message content into target."""
    target_content = target["content"]
    source_content = source["content"]

    # Normalize both to list format
    if isinstance(target_content, str):
        target_content = [{"type": "text", "text": target_content}]
    if isinstance(source_content, str):
        source_content = [{"type": "text", "text": source_content}]

    target["content"] = target_content + source_content


def _ensure_tool_result_pairing(messages: list[dict[str, Any]]) -> None:
    """Ensure every tool_result has a matching tool_use and vice versa.

    Corresponds to TS: utils/messages.ts ensureToolResultPairing().
    """
    # Collect all tool_use IDs from assistant messages
    tool_use_ids: set[str] = set()
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg["content"]
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_use_ids.add(block["id"])

    # Remove orphaned tool_results (no matching tool_use)
    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"]
            if isinstance(content, list):
                msg["content"] = [
                    block
                    for block in content
                    if not (
                        isinstance(block, dict)
                        and block.get("type") == "tool_result"
                        and block.get("tool_use_id") not in tool_use_ids
                    )
                ]
                # If content became empty after filtering, add placeholder
                if not msg["content"]:
                    msg["content"] = [{"type": "text", "text": "(tool results removed)"}]


def get_messages_after_compact_boundary(messages: list[Message]) -> list[Message]:
    """Return messages after the last compact boundary.

    Corresponds to TS: query.ts getMessagesAfterCompactBoundary().
    """
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], CompactBoundaryMessage):
            return messages[i:]
    return list(messages)


def create_user_message(content: str | list[UserContentBlock], **kwargs: Any) -> UserMessage:
    """Factory for creating user messages.

    Corresponds to TS: utils/messages.ts createUserMessage().
    """
    from datetime import datetime

    return UserMessage(
        content=content,
        timestamp=kwargs.get("timestamp", datetime.now(UTC).isoformat()),
        **{k: v for k, v in kwargs.items() if k != "timestamp"},
    )


def create_assistant_message(
    content: str | list[AssistantContentBlock],
    usage: Usage | None = None,
    stop_reason: str | None = None,
) -> AssistantMessage:
    """Factory for creating assistant messages.

    Corresponds to TS: utils/messages.ts createAssistantMessage().
    """
    from datetime import datetime

    if isinstance(content, str):
        blocks: list[AssistantContentBlock] = [TextBlock(text=content)]
    else:
        blocks = content

    return AssistantMessage(
        content=blocks,
        usage=usage or Usage(),
        stop_reason=stop_reason,
        timestamp=datetime.now(UTC).isoformat(),
    )


def create_tool_result_message(tool_use_id: str, content: str, is_error: bool = False) -> UserMessage:
    """Create a user message containing a tool result.

    Corresponds to TS pattern of wrapping tool_result in UserMessage.
    """
    return create_user_message(
        content=[ToolResultBlock(tool_use_id=tool_use_id, content=content, is_error=is_error)],
    )
