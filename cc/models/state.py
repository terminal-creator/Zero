"""Application and query loop state types.

Corresponds to TS: bootstrap/state.ts + query.ts State type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from .messages import Message


@dataclass
class AutoCompactTracking:
    """Tracking state for auto-compaction.

    Corresponds to TS: query.ts autoCompactTracking in State.
    """

    consecutive_failures: int = 0
    last_compact_turn: int = -1


@dataclass
class QueryState:
    """Immutable state for each iteration of the query loop.

    Corresponds to TS: query.ts State type (lines 204-217).
    """

    messages: list[Message] = field(default_factory=list)
    turn_count: int = 0
    max_output_tokens_recovery_count: int = 0
    has_attempted_reactive_compact: bool = False
    auto_compact_tracking: AutoCompactTracking = field(default_factory=AutoCompactTracking)
    turn_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class ThinkingConfig:
    """Configuration for extended thinking.

    Corresponds to TS: utils/thinking.ts ThinkingConfig.
    """

    type: str = "enabled"
    budget_tokens: int = 10000


@dataclass
class AppConfig:
    """Global application configuration.

    Corresponds to TS: various settings sources.
    """

    # API
    api_key: str | None = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 16384

    # Behavior
    thinking: ThinkingConfig | None = None
    max_turns: int = 100
    verbose: bool = False

    # Paths
    cwd: Path = field(default_factory=Path.cwd)
    claude_dir: Path = field(default_factory=lambda: Path.home() / ".claude")

    # Session
    session_id: str = field(default_factory=lambda: str(uuid4()))
