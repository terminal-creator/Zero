"""GlobTool implementation.

Corresponds to TS: tools/GlobTool/GlobTool.ts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

GLOB_TOOL_NAME = "Glob"
MAX_RESULTS = 100


class GlobTool(Tool):
    """Find files by glob pattern.

    Corresponds to TS: tools/GlobTool/GlobTool.ts.
    """

    def get_name(self) -> str:
        return GLOB_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=GLOB_TOOL_NAME,
            description="Fast file pattern matching tool that works with any codebase size.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files against",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (default: cwd)",
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

        if not pattern:
            return ToolResult(content="Error: pattern is required", is_error=True)

        base = Path(search_path).resolve()
        if not base.is_dir():
            return ToolResult(content=f"Error: Directory not found: {search_path}", is_error=True)

        try:
            matches = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            # Filter to files only
            matches = [m for m in matches if m.is_file()]
        except Exception as e:
            return ToolResult(content=f"Error: {e}", is_error=True)

        if not matches:
            return ToolResult(content="No files found")

        total = len(matches)
        truncated = matches[:MAX_RESULTS]
        result = "\n".join(str(m) for m in truncated)

        if total > MAX_RESULTS:
            result += f"\n\n(... {total - MAX_RESULTS} more files not shown)"

        return ToolResult(content=result)
