"""Command history — tracks user inputs per session.

Corresponds to TS: history.ts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_HISTORY_ITEMS = 100


@dataclass
class HistoryEntry:
    """A single history entry."""

    display: str
    timestamp: float
    project: str
    session_id: str = ""


def get_history_path(claude_dir: Path | None = None) -> Path:
    base = claude_dir or (Path.home() / ".claude")
    return base / "history.jsonl"


def add_to_history(
    entry: HistoryEntry,
    claude_dir: Path | None = None,
) -> None:
    """Append a history entry to the history file."""
    path = get_history_path(claude_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "display": entry.display,
        "timestamp": entry.timestamp,
        "project": entry.project,
        "sessionId": entry.session_id,
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_history(
    project: str | None = None,
    session_id: str | None = None,
    limit: int = MAX_HISTORY_ITEMS,
    claude_dir: Path | None = None,
) -> list[HistoryEntry]:
    """Read history entries, with current session prioritized.

    Corresponds to TS: history.ts getHistory().
    """
    path = get_history_path(claude_dir)
    if not path.exists():
        return []

    entries: list[HistoryEntry] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                entries.append(HistoryEntry(
                    display=record.get("display", ""),
                    timestamp=record.get("timestamp", 0),
                    project=record.get("project", ""),
                    session_id=record.get("sessionId", ""),
                ))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []

    # Filter by project if specified
    if project:
        entries = [e for e in entries if e.project == project]

    # Sort: current session first, then by timestamp descending
    if session_id:
        current = [e for e in entries if e.session_id == session_id]
        others = [e for e in entries if e.session_id != session_id]
        current.sort(key=lambda e: e.timestamp, reverse=True)
        others.sort(key=lambda e: e.timestamp, reverse=True)
        entries = current + others
    else:
        entries.sort(key=lambda e: e.timestamp, reverse=True)

    return entries[:limit]
