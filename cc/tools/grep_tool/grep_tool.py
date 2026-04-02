"""GrepTool implementation.

Corresponds to TS: tools/GrepTool/GrepTool.ts.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

GREP_TOOL_NAME = "Grep"
DEFAULT_HEAD_LIMIT = 250


class GrepTool(Tool):
    """Search file contents using ripgrep or Python re.

    Corresponds to TS: tools/GrepTool/GrepTool.ts.
    """

    def get_name(self) -> str:
        return GREP_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=GREP_TOOL_NAME,
            description="Search file contents using regex patterns.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (default: cwd)",
                    },
                    "glob": {
                        "type": "string",
                        "description": "File glob filter (e.g. '*.py')",
                    },
                    "output_mode": {
                        "type": "string",
                        "description": "Output mode: content, files_with_matches, count",
                    },
                },
                "required": ["pattern"],
            },
        )

    def is_concurrency_safe(self, tool_input: dict[str, Any]) -> bool:
        return True

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", ".")
        file_glob = tool_input.get("glob")
        output_mode = tool_input.get("output_mode", "files_with_matches")
        head_limit = int(tool_input.get("head_limit", DEFAULT_HEAD_LIMIT))

        if not pattern:
            return ToolResult(content="Error: pattern is required", is_error=True)

        # Try ripgrep first, fall back to Python
        rg_path = shutil.which("rg")
        if rg_path:
            return await self._run_ripgrep(rg_path, pattern, search_path, file_glob, output_mode, head_limit)
        return self._run_python_grep(pattern, search_path, file_glob, output_mode, head_limit)

    async def _run_ripgrep(
        self,
        rg_path: str,
        pattern: str,
        search_path: str,
        file_glob: str | None,
        output_mode: str,
        head_limit: int,
    ) -> ToolResult:
        args = [rg_path, "--no-heading", "-n"]

        if output_mode == "files_with_matches":
            args.append("-l")
        elif output_mode == "count":
            args.append("-c")

        if file_glob:
            args.extend(["--glob", file_glob])

        args.extend([pattern, search_path])

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            output = stdout.decode("utf-8", errors="replace")

            if not output.strip():
                return ToolResult(content="No matches found")

            lines = output.strip().split("\n")
            if len(lines) > head_limit:
                lines = lines[:head_limit]
                output = "\n".join(lines) + f"\n\n(... truncated at {head_limit} results)"
            else:
                output = "\n".join(lines)

            return ToolResult(content=output)

        except TimeoutError:
            return ToolResult(content="Error: Search timed out", is_error=True)
        except Exception as e:
            return ToolResult(content=f"Error running ripgrep: {e}", is_error=True)

    def _run_python_grep(
        self,
        pattern: str,
        search_path: str,
        file_glob: str | None,
        output_mode: str,
        head_limit: int,
    ) -> ToolResult:
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(content=f"Error: Invalid regex: {e}", is_error=True)

        base = Path(search_path).resolve()
        if not base.exists():
            return ToolResult(content=f"Error: Path not found: {search_path}", is_error=True)

        results: list[str] = []

        # FIX (check.md #6): Use rglob for recursive patterns, glob for simple ones.
        # Don't try to manipulate the glob string — just use the right method.
        if file_glob:
            if "**" in file_glob:
                # rglob expects the pattern without the leading **/ prefix
                rglob_pattern = file_glob.lstrip("*").lstrip("/") or "*"
                files = base.rglob(rglob_pattern)
            else:
                files = base.rglob(file_glob)
        else:
            files = base.rglob("*")

        for filepath in files:
            if not filepath.is_file():
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            if output_mode == "files_with_matches":
                if regex.search(text):
                    results.append(str(filepath))
            elif output_mode == "count":
                count = len(regex.findall(text))
                if count > 0:
                    results.append(f"{filepath}:{count}")
            else:
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        results.append(f"{filepath}:{i}:{line}")

            if len(results) >= head_limit:
                break

        if not results:
            return ToolResult(content="No matches found")

        output = "\n".join(results[:head_limit])
        if len(results) > head_limit:
            output += f"\n\n(... truncated at {head_limit} results)"

        return ToolResult(content=output)
