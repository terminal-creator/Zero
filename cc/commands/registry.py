"""Slash command registry and built-in commands.

Corresponds to TS: commands.ts + commands/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SlashCommand:
    """A registered slash command."""

    name: str
    description: str
    handler: Any  # Callable — typed loosely to avoid complex generics


# Built-in commands
_commands: dict[str, SlashCommand] = {}


def register_command(name: str, description: str, handler: Any) -> None:
    """Register a slash command."""
    _commands[name] = SlashCommand(name=name, description=description, handler=handler)


def get_command(name: str) -> SlashCommand | None:
    """Look up a slash command by name."""
    return _commands.get(name)


def list_commands() -> list[SlashCommand]:
    """List all registered commands."""
    return list(_commands.values())


def is_slash_command(text: str) -> bool:
    """Check if input is a slash command."""
    return text.strip().startswith("/")


def parse_slash_command(text: str) -> tuple[str, str]:
    """Parse a slash command into (name, args)."""
    text = text.strip()
    if not text.startswith("/"):
        return "", text

    parts = text[1:].split(None, 1)
    name = parts[0] if parts else ""
    args = parts[1] if len(parts) > 1 else ""
    return name, args


# Register built-in commands
def _help_handler(**_kwargs: Any) -> str:
    """Show available commands."""
    lines = ["Available commands:"]
    for cmd in sorted(_commands.values(), key=lambda c: c.name):
        lines.append(f"  /{cmd.name} — {cmd.description}")
    return "\n".join(lines)


def _clear_handler(**_kwargs: Any) -> str:
    return "__CLEAR__"


def _compact_handler(**_kwargs: Any) -> str:
    return "__COMPACT__"


def _cost_handler(**kwargs: Any) -> str:
    total_in = kwargs.get("total_input_tokens", 0)
    total_out = kwargs.get("total_output_tokens", 0)
    return f"Session usage: {total_in} input tokens, {total_out} output tokens"


def _model_handler(**kwargs: Any) -> str:
    new_model = kwargs.get("args", "").strip()
    if not new_model:
        current = kwargs.get("current_model", "unknown")
        return f"Current model: {current}"
    return f"__MODEL__{new_model}"


register_command("help", "Show available commands", _help_handler)
register_command("clear", "Clear conversation history", _clear_handler)
register_command("compact", "Compact conversation context", _compact_handler)
register_command("cost", "Show token usage for this session", _cost_handler)
register_command("model", "Show or change the current model", _model_handler)
