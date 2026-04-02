"""Session persistence — save/load conversation to disk.

Corresponds to TS: utils/sessionStorage.ts + history.ts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from cc.models.messages import (
    AssistantMessage,
    CompactBoundaryMessage,
    Message,
    SystemMessage,
    Usage,
    UserMessage,
)

logger = logging.getLogger(__name__)


def get_sessions_dir(claude_dir: Path | None = None) -> Path:
    """Return the sessions directory path. Does NOT create it."""
    base = claude_dir or (Path.home() / ".claude")
    return base / "sessions"


def save_session(session_id: str, messages: list[Message], claude_dir: Path | None = None) -> Path:
    """Save a conversation session to JSONL.

    Corresponds to TS: utils/sessionStorage.ts transcript persistence.
    Creates the directory only on write.
    """
    sessions_dir = get_sessions_dir(claude_dir)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"{session_id}.jsonl"

    with path.open("w", encoding="utf-8") as f:
        for msg in messages:
            record = _message_to_record(msg)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return path


def load_session(session_id: str, claude_dir: Path | None = None) -> list[Message] | None:
    """Load a conversation session from JSONL.

    Corresponds to TS: utils/conversationRecovery.ts.
    Returns None if session not found.
    """
    sessions_dir = get_sessions_dir(claude_dir)
    path = sessions_dir / f"{session_id}.jsonl"

    if not path.exists():
        return None

    messages: list[Message] = []
    for line_num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            msg = _record_to_message(record)
            if msg is not None:
                messages.append(msg)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Skipping corrupt line %d in session %s: %s", line_num, session_id, e)
            continue

    return messages if messages else None


def list_sessions(claude_dir: Path | None = None) -> list[str]:
    """List available session IDs. Returns empty list if sessions dir doesn't exist."""
    sessions_dir = get_sessions_dir(claude_dir)
    if not sessions_dir.is_dir():
        return []
    return [p.stem for p in sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)]


def _message_to_record(msg: Message) -> dict[str, Any]:
    """Serialize a message to a JSON-safe dict."""
    if isinstance(msg, UserMessage):
        content: Any = (
            msg.content if isinstance(msg.content, str) else [b.to_api_dict() for b in msg.content]
        )
        return {
            "type": "user",
            "content": content,
            "uuid": msg.uuid,
            "timestamp": msg.timestamp,
        }

    if isinstance(msg, AssistantMessage):
        return {
            "type": "assistant",
            "content": [b.to_api_dict() for b in msg.content],
            "uuid": msg.uuid,
            "timestamp": msg.timestamp,
            "stop_reason": msg.stop_reason,
            "usage": {
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
            },
            "model": msg.model,
        }

    if isinstance(msg, CompactBoundaryMessage):
        return {
            "type": "compact_boundary",
            "summary": msg.summary,
            "uuid": msg.uuid,
            "timestamp": msg.timestamp,
        }

    if isinstance(msg, SystemMessage):
        return {
            "type": "system",
            "content": msg.content,
            "level": msg.level,
            "uuid": msg.uuid,
            "timestamp": msg.timestamp,
        }

    return {"type": "unknown"}


def _record_to_message(record: dict[str, Any]) -> Message | None:
    """Deserialize a message from a JSON record."""
    msg_type = record.get("type")

    if msg_type == "user":
        content = record["content"]
        if isinstance(content, str):
            user_content: str | list[Any] = content
        else:
            from cc.models.content_blocks import content_block_from_api_dict
            user_content = [content_block_from_api_dict(b) for b in content]
        return UserMessage(
            content=user_content,
            uuid=record.get("uuid", ""),
            timestamp=record.get("timestamp", ""),
        )

    if msg_type == "assistant":
        from cc.models.content_blocks import content_block_from_api_dict
        blocks = [content_block_from_api_dict(b) for b in record.get("content", [])]
        usage_data = record.get("usage", {})
        return AssistantMessage(
            content=blocks,  # type: ignore[arg-type]
            uuid=record.get("uuid", ""),
            timestamp=record.get("timestamp", ""),
            stop_reason=record.get("stop_reason"),
            usage=Usage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
            ),
            model=record.get("model", ""),
        )

    if msg_type == "compact_boundary":
        return CompactBoundaryMessage(
            summary=record["summary"],
            uuid=record.get("uuid", ""),
            timestamp=record.get("timestamp", ""),
        )

    if msg_type == "system":
        return SystemMessage(
            content=record.get("content", ""),
            level=record.get("level", "info"),
            uuid=record.get("uuid", ""),
            timestamp=record.get("timestamp", ""),
        )

    return None
