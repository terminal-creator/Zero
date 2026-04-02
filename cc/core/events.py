"""Query loop event types.

These are yielded by the query loop and consumed by the UI layer.
The core loop never directly writes to stdout — all output goes through events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cc.models.messages import Usage


@dataclass
class TextDelta:
    """Streaming text increment from the model."""

    text: str


@dataclass
class ThinkingDelta:
    """Streaming thinking text increment."""

    text: str


@dataclass
class ToolUseStart:
    """A tool call has been initiated."""

    tool_name: str
    tool_id: str
    input: dict[str, object]


@dataclass
class ToolResultReady:
    """A tool has finished execution."""

    tool_id: str
    content: str
    is_error: bool = False


@dataclass
class CompactOccurred:
    """Context was compacted (messages summarized)."""

    summary_preview: str


@dataclass
class TurnComplete:
    """The current turn has finished."""

    stop_reason: str  # "end_turn" | "tool_use" | "max_turns" | "aborted" | ...
    usage: Usage


@dataclass
class ErrorEvent:
    """An error occurred during the query loop."""

    message: str
    is_recoverable: bool = False


QueryEvent = TextDelta | ThinkingDelta | ToolUseStart | ToolResultReady | CompactOccurred | TurnComplete | ErrorEvent
