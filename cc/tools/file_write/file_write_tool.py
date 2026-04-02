"""FileWriteTool implementation.

Corresponds to TS: tools/FileWriteTool/FileWriteTool.ts.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

FILE_WRITE_TOOL_NAME = "Write"


class FileWriteTool(Tool):
    """Write files atomically.

    Corresponds to TS: tools/FileWriteTool/FileWriteTool.ts.
    """

    def get_name(self) -> str:
        return FILE_WRITE_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=FILE_WRITE_TOOL_NAME,
            description="Writes a file to the local filesystem.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The absolute path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
                "required": ["file_path", "content"],
            },
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")

        if not file_path:
            return ToolResult(content="Error: file_path is required", is_error=True)

        path = Path(file_path)

        # Create parent directories
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return ToolResult(content=f"Error creating directories: {e}", is_error=True)

        # Atomic write: write to temp file then rename
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, str(path))
            except Exception:
                # Clean up temp file on error
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
                raise
        except Exception as e:
            return ToolResult(content=f"Error writing file: {e}", is_error=True)

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return ToolResult(content=f"Successfully wrote {line_count} lines to {file_path}")
