"""CLI entry point for cc-python-claude.

Corresponds to TS: main.tsx + entrypoints/cli.tsx.

All modules are wired into the runtime here — no dead code.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from collections.abc import AsyncIterator  # noqa: TC003
from pathlib import Path

import click

from cc.api.claude import stream_response
from cc.api.client import create_client
from cc.core.events import QueryEvent, TurnComplete
from cc.core.query_loop import query_loop
from cc.hooks.hook_runner import load_hooks
from cc.models.messages import Message, UserMessage
from cc.prompts.builder import build_system_prompt
from cc.prompts.claudemd import load_claude_md
from cc.session.history import HistoryEntry, add_to_history
from cc.session.storage import save_session
from cc.skills.loader import load_skills
from cc.tools.base import ToolRegistry
from cc.tools.bash.bash_tool import BashTool
from cc.tools.file_edit.file_edit_tool import FileEditTool
from cc.tools.file_read.file_read_tool import FileReadTool
from cc.tools.file_write.file_write_tool import FileWriteTool
from cc.tools.glob_tool.glob_tool import GlobTool
from cc.tools.grep_tool.grep_tool import GrepTool
from cc.ui.renderer import console, render_event

logger = logging.getLogger(__name__)


def _build_registry(cwd: str, call_model_factory: object | None = None, model: str = "") -> ToolRegistry:
    """Build the default tool registry with all tools."""
    registry = ToolRegistry()
    registry.register(BashTool(cwd=cwd))
    registry.register(FileReadTool())
    registry.register(FileEditTool())
    registry.register(FileWriteTool())
    registry.register(GlobTool())
    registry.register(GrepTool())

    from cc.tools.task_tools.task_tools import TaskCreateTool, TaskGetTool, TaskListTool, TaskUpdateTool

    registry.register(TaskCreateTool())
    registry.register(TaskGetTool())
    registry.register(TaskListTool())
    registry.register(TaskUpdateTool())

    from cc.tools.web_fetch.web_fetch_tool import WebFetchTool

    registry.register(WebFetchTool())

    from cc.tools.ask_user.ask_user_tool import AskUserQuestionTool

    registry.register(AskUserQuestionTool(input_fn=True))

    # AgentTool — requires call_model_factory to spawn sub-agents
    if call_model_factory is not None:
        from cc.tools.agent.agent_tool import AgentTool

        registry.register(AgentTool(
            parent_registry=registry,
            call_model_factory=call_model_factory,
            model=model,
        ))

    return registry


async def _connect_mcp_servers(cwd: str, registry: ToolRegistry) -> None:
    """Load MCP configs and connect servers."""
    from cc.mcp.client import connect_mcp_server
    from cc.mcp.config import load_mcp_configs

    configs = load_mcp_configs(cwd)
    for config in configs:
        logger.info("Connecting MCP server: %s", config.name)
        await connect_mcp_server(config, registry)


def _get_api_key() -> str | None:
    """Get API key from environment variable or project .env file.

    Priority:
    1. ANTHROPIC_API_KEY environment variable
    2. .env file in project root (cc-python-claude/)
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # Load from .env in project root
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()

    return None


def _make_call_model_factory(client: object) -> object:
    """Factory that creates call_model functions for a given model.

    Used by AgentTool to create call_model for sub-agents with different models.
    """

    def factory(model: str = "claude-sonnet-4-20250514", max_tokens: int = 16384) -> object:
        async def call_model(**kwargs: object) -> AsyncIterator[QueryEvent]:
            # Let query_loop override max_tokens (e.g. escalate to 64K on max_output_tokens recovery)
            effective_max: object = kwargs.pop("max_tokens", max_tokens)
            async for event in stream_response(client, model=model, max_tokens=effective_max, **kwargs):  # type: ignore[arg-type]
                yield event

        return call_model

    return factory


def _make_call_model(client: object, model: str, max_tokens: int = 16384) -> object:
    """Create a call_model function bound to a specific model."""

    async def call_model(**kwargs: object) -> AsyncIterator[QueryEvent]:
        # query_loop may pass max_tokens — use it if present, otherwise use the bound default
        effective_max: object = kwargs.pop("max_tokens", max_tokens)
        async for event in stream_response(client, model=model, max_tokens=effective_max, **kwargs):  # type: ignore[arg-type]
            yield event

    return call_model


def _build_system(cwd: str, model: str, claude_md: str | None) -> str:
    """Build the system prompt with memories and CLAUDE.md."""
    from cc.memory.session_memory import get_memory_dir, load_memory_index

    mem_dir = get_memory_dir(cwd)
    # Ensure memory dir exists so the model can write directly
    mem_dir.mkdir(parents=True, exist_ok=True)
    memory_index = load_memory_index(cwd)

    parts = build_system_prompt(
        cwd=cwd,
        model=model,
        claude_md_content=claude_md,
        memory_dir=str(mem_dir),
        memory_index_content=memory_index,
    )
    return "\n\n".join(parts)


def _read_multiline_input() -> str:
    """Read user input with multi-line support."""
    lines: list[str] = []
    try:
        first_line = console.input("[bold blue]> [/]")
    except EOFError:
        raise
    except KeyboardInterrupt:
        console.print()
        return ""

    lines.append(first_line)

    while _needs_continuation(lines):
        try:
            next_line = console.input("[dim]... [/]")
            lines.append(next_line)
        except (EOFError, KeyboardInterrupt):
            break

    return "\n".join(lines)


def _needs_continuation(lines: list[str]) -> bool:
    """Check if input needs more lines."""
    text = "\n".join(lines)
    if text.rstrip().endswith("\\"):
        return True
    open_count = text.count("(") + text.count("[") + text.count("{")
    close_count = text.count(")") + text.count("]") + text.count("}")
    if open_count > close_count:
        return True
    return text.count('"""') % 2 != 0 or text.count("'''") % 2 != 0


# ---------------------------------------------------------------------------
# --print mode
# ---------------------------------------------------------------------------


async def _run_print_mode(prompt: str, model: str) -> None:
    """Non-interactive mode: single prompt -> output -> exit.

    Wires: MCP, hooks, memory, skills — same as REPL.
    """
    api_key = _get_api_key()
    if not api_key:
        console.print("[red]Error: No API key found.[/]")
        sys.exit(1)

    client = create_client(api_key=api_key)
    cwd = str(Path.cwd())

    factory = _make_call_model_factory(client)
    registry = _build_registry(cwd, call_model_factory=factory, model=model)

    # MCP — same as REPL
    await _connect_mcp_servers(cwd, registry)

    # Hooks
    hooks = load_hooks()

    # System prompt with memory
    claude_md = load_claude_md(cwd)
    system = _build_system(cwd, model, claude_md)

    messages: list[Message] = [UserMessage(content=prompt)]

    async for event in query_loop(
        messages=messages,
        system_prompt=system,
        tools=registry,
        call_model=_make_call_model(client, model),  # type: ignore[arg-type]
        hooks=hooks,
        max_turns=20,
    ):
        render_event(event)


# ---------------------------------------------------------------------------
# REPL mode
# ---------------------------------------------------------------------------


async def _run_repl(model: str, resume_id: str | None = None) -> None:
    """Interactive REPL mode.

    All modules wired: MCP, hooks, memory, skills, history, session, agent.
    """
    api_key = _get_api_key()
    if not api_key:
        console.print("[red]Error: No API key found. Set ANTHROPIC_API_KEY env var or add it to .env file.[/]")
        sys.exit(1)

    client = create_client(api_key=api_key)
    cwd = str(Path.cwd())

    factory = _make_call_model_factory(client)
    registry = _build_registry(cwd, call_model_factory=factory, model=model)

    # MCP
    await _connect_mcp_servers(cwd, registry)

    # Hooks
    hooks = load_hooks()

    # Skills — load and register as slash commands
    skills = load_skills(cwd)
    if skills:
        from cc.commands.registry import register_command

        for skill in skills:
            _name = skill.name

            def _make_skill_handler(name: str) -> object:
                def handler(**_kwargs: object) -> str:
                    return f"__SKILL__{name}"
                return handler

            register_command(skill.name, skill.description, _make_skill_handler(_name))

    # System prompt with memory + CLAUDE.md
    claude_md = load_claude_md(cwd)
    system = _build_system(cwd, model, claude_md)

    messages: list[Message] = []
    total_input_tokens = 0
    total_output_tokens = 0
    last_extraction_msg_count = 0  # Track for incremental extraction
    _bg_tasks: set[asyncio.Task[None]] = set()  # prevent GC of background tasks

    # Resume session
    if resume_id:
        from cc.session.storage import load_session

        loaded = load_session(resume_id)
        if loaded:
            messages = loaded
            console.print(f"[dim]Resumed session {resume_id} ({len(messages)} messages)[/]")
        else:
            console.print(f"[yellow]Session {resume_id} not found, starting fresh.[/]")

    from uuid import uuid4

    from cc.ui.renderer import print_welcome

    print_welcome()
    session_id = resume_id or str(uuid4())[:8]

    while True:
        try:
            user_input = _read_multiline_input()
        except EOFError:
            console.print("\nBye!")
            break

        if not user_input.strip():
            continue

        # Slash commands
        if user_input.strip().startswith("/"):
            from cc.commands.registry import get_command, parse_slash_command

            cmd_name, cmd_args = parse_slash_command(user_input)
            cmd = get_command(cmd_name)
            if cmd is None:
                console.print(f"[red]Unknown command: /{cmd_name}[/]")
                continue

            result = cmd.handler(
                args=cmd_args,
                current_model=model,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
            )

            if result == "__CLEAR__":
                messages.clear()
                console.print("[dim]Conversation cleared.[/]")
                continue
            elif result == "__COMPACT__":
                from cc.compact.compact import compact_messages

                messages = await compact_messages(
                    messages,
                    _make_call_model(client, model, max_tokens=4096),  # type: ignore[arg-type]
                )
                console.print("[yellow]Context compacted.[/]")
                continue
            elif isinstance(result, str) and result.startswith("__MODEL__"):
                model = result[len("__MODEL__"):]
                system = _build_system(cwd, model, claude_md)
                console.print(f"[dim]Model changed to: {model}[/]")
                continue
            elif isinstance(result, str) and result.startswith("__SKILL__"):
                # Skill injection — find skill and inject prompt
                from cc.skills.loader import get_skill_by_name

                skill_name = result[len("__SKILL__"):]
                found_skill = get_skill_by_name(skills, skill_name)
                if found_skill:
                    messages.append(UserMessage(content=found_skill.prompt))
                    console.print(f"[dim]Skill /{skill_name} activated[/]")
                    # Fall through to run the query loop with the injected prompt
                else:
                    console.print(f"[red]Skill not found: {skill_name}[/]")
                    continue
            else:
                console.print(result)
                continue
        else:
            # Regular message
            messages.append(UserMessage(content=user_input))

        # Record in history
        add_to_history(HistoryEntry(
            display=user_input[:200],
            timestamp=time.time(),
            project=cwd,
            session_id=session_id,
        ))

        try:
            async for event in query_loop(
                messages=messages,
                system_prompt=system,
                tools=registry,
                call_model=_make_call_model(client, model),  # type: ignore[arg-type]
                auto_compact_fn=_make_call_model(client, model, max_tokens=4096),  # type: ignore[arg-type]
                hooks=hooks,
                max_turns=50,
            ):
                render_event(event)
                if isinstance(event, TurnComplete):
                    total_input_tokens += event.usage.input_tokens
                    total_output_tokens += event.usage.output_tokens
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/]")
            continue

        # Auto-save session after every turn
        save_session(session_id, messages)

        # Background memory extraction — fire-and-forget, don't block the REPL
        from cc.memory.extractor import extract_memories

        current_visible = len([
            m for m in messages
            if isinstance(m, UserMessage) or (hasattr(m, "type") and m.type == "assistant")
        ])
        incremental_count = current_visible - last_extraction_msg_count
        # Capture loop variables for the background closure
        _msgs = messages
        _cwd = cwd
        _call = _make_call_model(client, model, max_tokens=1024)

        async def _bg_extract(
            msgs: list[Message], wd: str, call: object, inc: int, snap: int,
        ) -> None:
            nonlocal last_extraction_msg_count
            try:
                saved = await extract_memories(
                    msgs, wd,
                    call_model=call,
                    new_message_count=inc,
                )
                last_extraction_msg_count = snap
                if saved:
                    console.print(f"[dim]Saved {len(saved)} memory(s): {', '.join(saved)}[/]")
            except Exception as e:
                logger.debug("Memory extraction skipped: %s", e)

        # Fire as background task — does not block the next prompt
        task = asyncio.create_task(
            _bg_extract(_msgs, _cwd, _call, incremental_count, current_visible)
        )
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)


@click.command()
@click.option("-p", "--print", "print_mode", is_flag=True, help="Non-interactive mode")
@click.option("--model", default="claude-sonnet-4-20250514", help="Model to use")
@click.option("--verbose", is_flag=True, help="Verbose output")
@click.option("-c", "--resume", "resume_id", default=None, help="Resume session by ID")
@click.argument("prompt", required=False)
def main(
    print_mode: bool,
    model: str,
    verbose: bool,
    resume_id: str | None,
    prompt: str | None,
) -> None:
    """cc-python-claude -- Python reimplementation of Claude Code CLI."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    if print_mode:
        if not prompt:
            prompt = sys.stdin.read().strip()
        if not prompt:
            console.print("[red]Error: No prompt provided.[/]")
            sys.exit(1)
        asyncio.run(_run_print_mode(prompt, model))
    else:
        asyncio.run(_run_repl(model, resume_id=resume_id))


if __name__ == "__main__":
    main()
