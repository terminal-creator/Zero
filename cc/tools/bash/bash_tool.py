"""BashTool implementation.

Corresponds to TS: tools/BashTool/BashTool.tsx.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

BASH_TOOL_NAME = "Bash"
MAX_OUTPUT_BYTES = 200_000  # 200KB output cap
DEFAULT_TIMEOUT_MS = 120_000  # 2 minutes

# Read-only single-word commands
_READ_ONLY_SINGLE = frozenset([
    "ls", "cat", "head", "tail", "wc", "du", "df", "file", "stat",
    "which", "whereis", "type", "echo", "printf", "date", "uname",
    "whoami", "id", "env", "printenv", "pwd", "hostname",
])

# Read-only two-word commands (checked as "word1 word2")
_READ_ONLY_TWO_WORD = frozenset([
    "git status", "git log", "git diff", "git show", "git branch",
    "git remote", "git tag", "git rev-parse", "git describe",
])


class BashTool(Tool):
    """Execute shell commands.

    Corresponds to TS: tools/BashTool/BashTool.tsx.
    """

    def __init__(self, cwd: str | None = None) -> None:
        self._cwd = cwd

    def get_name(self) -> str:
        return BASH_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=BASH_TOOL_NAME,
            description="Executes a given bash command and returns its output.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Optional timeout in milliseconds (max 600000)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Clear description of what the command does",
                    },
                },
                "required": ["command"],
            },
        )

    def is_concurrency_safe(self, tool_input: dict[str, Any]) -> bool:
        """Read-only commands are concurrency safe.

        FIX (check.md #2): Check both single-word and two-word command prefixes.
        """
        command = tool_input.get("command", "").strip()
        words = command.split()
        if not words:
            return False
        if words[0] in _READ_ONLY_SINGLE:
            return True
        return len(words) >= 2 and f"{words[0]} {words[1]}" in _READ_ONLY_TWO_WORD

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        command: str = tool_input.get("command", "")
        timeout_ms: int = min(tool_input.get("timeout", DEFAULT_TIMEOUT_MS), 600_000)
        timeout_s = timeout_ms / 1000.0

        if not command.strip():
            return ToolResult(content="Error: empty command", is_error=True)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_s
                )
            except TimeoutError:
                # Try graceful shutdown first
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.communicate(), timeout=2.0)
                except (TimeoutError, ProcessLookupError):
                    with contextlib.suppress(ProcessLookupError):
                        proc.kill()
                return ToolResult(
                    content=f"Command timed out after {timeout_ms}ms",
                    is_error=True,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Truncate if too large
            output = stdout
            if stderr:
                output = f"{stdout}\n{stderr}" if stdout else stderr

            if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
                truncated = output[:MAX_OUTPUT_BYTES // 4]  # rough char estimate
                output = f"{truncated}\n\n... (output truncated, exceeded {MAX_OUTPUT_BYTES} bytes)"

            exit_code = proc.returncode or 0
            if exit_code != 0:
                output = f"{output}\n\nExit code: {exit_code}" if output else f"Exit code: {exit_code}"

            return ToolResult(content=output or "(no output)", is_error=exit_code != 0)

        except Exception as e:
            return ToolResult(content=f"Error executing command: {e}", is_error=True)
