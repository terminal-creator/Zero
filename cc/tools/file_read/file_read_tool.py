"""FileReadTool implementation.

Corresponds to TS: tools/FileReadTool/FileReadTool.ts.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

FILE_READ_TOOL_NAME = "Read"
DEFAULT_LIMIT = 2000
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico"}


class FileReadTool(Tool):
    """Read file contents.

    Corresponds to TS: tools/FileReadTool/FileReadTool.ts.
    """

    def get_name(self) -> str:
        return FILE_READ_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=FILE_READ_TOOL_NAME,
            description="Reads a file from the local filesystem.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The absolute path to the file to read",
                    },
                    "offset": {
                        "type": "number",
                        "description": "Line number to start reading from",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of lines to read",
                    },
                },
                "required": ["file_path"],
            },
        )

    def is_concurrency_safe(self, tool_input: dict[str, Any]) -> bool:
        return True  # Reading is always safe

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        file_path = tool_input.get("file_path", "")
        offset = int(tool_input.get("offset", 1))
        limit = int(tool_input.get("limit", DEFAULT_LIMIT))

        if not file_path:
            return ToolResult(content="Error: file_path is required", is_error=True)

        path = Path(file_path)
        if not path.exists():
            return ToolResult(content=f"Error: File does not exist: {file_path}", is_error=True)

        if not path.is_file():
            return ToolResult(content=f"Error: Not a file: {file_path}", is_error=True)

        # Check if image — return rich content block with base64 data
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            try:
                data = path.read_bytes()
                b64 = base64.b64encode(data).decode("ascii")
                media_type = mimetypes.guess_type(str(path))[0] or "image/png"
                return ToolResult(
                    content=[{
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    }],
                )
            except Exception as e:
                return ToolResult(content=f"Error reading image: {e}", is_error=True)

        # Read text file with line numbers (cat -n format)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(content=f"Error reading file: {e}", is_error=True)

        if not text:
            return ToolResult(content=f"(file is empty: {file_path})")

        lines = text.splitlines()
        total_lines = len(lines)

        # Apply offset (1-based) and limit
        start_idx = max(0, offset - 1)
        end_idx = min(total_lines, start_idx + limit)
        selected = lines[start_idx:end_idx]

        # Format with line numbers
        numbered = []
        for i, line in enumerate(selected, start=start_idx + 1):
            numbered.append(f"{i}\t{line}")

        result = "\n".join(numbered)

        if end_idx < total_lines:
            remaining = total_lines - end_idx
            result += f"\n\n(... {remaining} more lines not shown. Use offset/limit to read more.)"

        return ToolResult(content=result)
