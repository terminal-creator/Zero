"""Terminal UI renderer using Rich.

Corresponds to TS: components/ + screens/ (reimplemented with Rich).
Consumes QueryEvent stream and renders to terminal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.text import Text

if TYPE_CHECKING:
    from cc.core.events import QueryEvent

console = Console()


def render_event(event: QueryEvent) -> None:
    """Render a single query event to the terminal."""
    from cc.core.events import (
        CompactOccurred,
        ErrorEvent,
        TextDelta,
        ThinkingDelta,
        ToolResultReady,
        ToolUseStart,
        TurnComplete,
    )

    if isinstance(event, TextDelta):
        console.print(event.text, end="", highlight=False)

    elif isinstance(event, ThinkingDelta):
        console.print(Text(event.text, style="dim"), end="")

    elif isinstance(event, ToolUseStart):
        console.print()
        console.print(
            Text(f"  [{event.tool_name}] ", style="bold cyan"),
            end="",
        )
        # Show brief input summary
        input_preview = str(event.input)
        if len(input_preview) > 120:
            input_preview = input_preview[:120] + "..."
        console.print(Text(input_preview, style="dim"))

    elif isinstance(event, ToolResultReady):
        if event.is_error:
            console.print(Text(f"  Error: {event.content[:200]}", style="red"))
        else:
            preview = event.content[:200]
            if len(event.content) > 200:
                preview += "..."
            console.print(Text(f"  {preview}", style="dim green"))

    elif isinstance(event, CompactOccurred):
        console.print()
        console.print(Text("  [Context compacted]", style="bold yellow"))

    elif isinstance(event, TurnComplete):
        if event.stop_reason == "end_turn":
            console.print()  # Final newline after text
        usage = event.usage
        if usage.input_tokens > 0 or usage.output_tokens > 0:
            console.print(
                Text(
                    f"  ({usage.input_tokens} in / {usage.output_tokens} out tokens)",
                    style="dim",
                )
            )

    elif isinstance(event, ErrorEvent):
        console.print()
        console.print(Text(f"Error: {event.message}", style="bold red"))


def print_welcome() -> None:
    """Print the welcome banner."""
    console.print()
    console.print(Text("cc-python-claude v0.1.0", style="bold blue"))
    console.print(Text("Type your message, or /help for commands. Ctrl+C to interrupt, Ctrl+D to exit.", style="dim"))
    console.print()


def print_prompt() -> str:
    """Display the input prompt and read user input."""
    try:
        return console.input("[bold blue]> [/]")
    except EOFError:
        raise
    except KeyboardInterrupt:
        console.print()
        return ""
