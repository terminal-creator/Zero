"""Tests for command history.

Verifies T6.2: History add/get, session priority, limit.
"""

import time
from pathlib import Path

from cc.session.history import HistoryEntry, add_to_history, get_history


class TestHistory:
    def test_add_and_get(self, tmp_path: Path) -> None:
        add_to_history(
            HistoryEntry(display="hello", timestamp=time.time(), project="/tmp", session_id="s1"),
            claude_dir=tmp_path,
        )
        entries = get_history(claude_dir=tmp_path)
        assert len(entries) == 1
        assert entries[0].display == "hello"

    def test_limit(self, tmp_path: Path) -> None:
        for i in range(10):
            add_to_history(
                HistoryEntry(display=f"msg{i}", timestamp=float(i), project="/tmp", session_id="s1"),
                claude_dir=tmp_path,
            )
        entries = get_history(limit=3, claude_dir=tmp_path)
        assert len(entries) == 3

    def test_session_priority(self, tmp_path: Path) -> None:
        add_to_history(
            HistoryEntry(display="other", timestamp=1.0, project="/tmp", session_id="other"),
            claude_dir=tmp_path,
        )
        add_to_history(
            HistoryEntry(display="mine-old", timestamp=2.0, project="/tmp", session_id="mine"),
            claude_dir=tmp_path,
        )
        add_to_history(
            HistoryEntry(display="other-new", timestamp=3.0, project="/tmp", session_id="other"),
            claude_dir=tmp_path,
        )
        entries = get_history(session_id="mine", claude_dir=tmp_path)
        # "mine" session entries come first
        assert entries[0].session_id == "mine"

    def test_empty_history(self, tmp_path: Path) -> None:
        entries = get_history(claude_dir=tmp_path)
        assert entries == []
