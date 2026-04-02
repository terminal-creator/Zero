"""Hook system — execute shell commands before/after tool use.

Corresponds to TS: hooks/ system.
Hooks are configured in settings.json and run as shell commands.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HOOK_TIMEOUT_S = 10.0


@dataclass
class HookConfig:
    """A configured hook."""

    event: str  # "PreToolUse" | "PostToolUse"
    command: str
    tool_name: str | None = None  # None = all tools


@dataclass
class HookResult:
    """Result of running a hook."""

    blocked: bool = False
    message: str = ""


def load_hooks(claude_dir: Path | None = None) -> list[HookConfig]:
    """Load hook configurations from settings.json.

    Corresponds to TS: hooks loading from settings.
    """
    settings_path = (claude_dir or Path.home() / ".claude") / "settings.json"
    if not settings_path.is_file():
        return []

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    hooks_config = settings.get("hooks", {})
    hooks: list[HookConfig] = []

    for event_name, event_hooks in hooks_config.items():
        if not isinstance(event_hooks, list):
            continue
        for hook_entry in event_hooks:
            if isinstance(hook_entry, dict):
                hooks.append(HookConfig(
                    event=event_name,
                    command=hook_entry.get("command", ""),
                    tool_name=hook_entry.get("tool_name"),
                ))
            elif isinstance(hook_entry, str):
                hooks.append(HookConfig(event=event_name, command=hook_entry))

    return hooks


async def run_hook(
    hook: HookConfig,
    context: dict[str, Any],
) -> HookResult:
    """Execute a hook command.

    Corresponds to TS: hooks execution.

    The hook receives JSON context via stdin.
    Exit code 0 = allow, exit code 2 = block, other = warning.
    """
    if not hook.command:
        return HookResult()

    try:
        proc = await asyncio.create_subprocess_shell(
            hook.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        context_json = json.dumps(context).encode("utf-8")

        try:
            stdout, _stderr = await asyncio.wait_for(
                proc.communicate(input=context_json),
                timeout=HOOK_TIMEOUT_S,
            )
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            logger.warning("Hook timed out: %s", hook.command)
            return HookResult()

        output = stdout.decode("utf-8", errors="replace").strip()

        if proc.returncode == 2:
            return HookResult(blocked=True, message=output or "Blocked by hook")
        if proc.returncode != 0:
            logger.warning("Hook exited with code %d: %s", proc.returncode, hook.command)

        return HookResult(message=output)

    except Exception as e:
        logger.warning("Hook failed: %s — %s", hook.command, e)
        return HookResult()


async def run_pre_tool_hooks(
    hooks: list[HookConfig],
    tool_name: str,
    tool_input: dict[str, Any],
) -> HookResult:
    """Run all PreToolUse hooks for a tool. Returns blocked if any hook blocks."""
    for hook in hooks:
        if hook.event != "PreToolUse":
            continue
        if hook.tool_name is not None and hook.tool_name != tool_name:
            continue

        result = await run_hook(hook, {"tool_name": tool_name, "input": tool_input})
        if result.blocked:
            return result

    return HookResult()


async def run_post_tool_hooks(
    hooks: list[HookConfig],
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: str,
) -> None:
    """Run all PostToolUse hooks for a tool."""
    for hook in hooks:
        if hook.event != "PostToolUse":
            continue
        if hook.tool_name is not None and hook.tool_name != tool_name:
            continue

        await run_hook(hook, {
            "tool_name": tool_name,
            "input": tool_input,
            "output": tool_output[:1000],
        })
