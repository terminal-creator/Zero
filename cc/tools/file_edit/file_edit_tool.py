"""FileEditTool implementation.

Corresponds to TS: tools/FileEditTool/FileEditTool.ts.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

FILE_EDIT_TOOL_NAME = "Edit"


class FileEditTool(Tool):
    """Edit files via string replacement.

    Corresponds to TS: tools/FileEditTool/FileEditTool.ts.
    """

    def get_name(self) -> str:
        return FILE_EDIT_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=FILE_EDIT_TOOL_NAME,
            description="Performs exact string replacements in files.",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The absolute path to the file to modify",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The text to replace",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The replacement text",
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default false)",
                    },
                },
                "required": ["file_path", "old_string", "new_string"],
            },
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        file_path = tool_input.get("file_path", "")
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        replace_all = bool(tool_input.get("replace_all", False))

        if not file_path:
            return ToolResult(content="Error: file_path is required", is_error=True)

        path = Path(file_path)
        if not path.is_file():
            return ToolResult(content=f"Error: File does not exist: {file_path}", is_error=True)

        if old_string == new_string:
            return ToolResult(content="Error: old_string and new_string must be different", is_error=True)

        # FIX (check.md #8): Read in binary mode to preserve CRLF line endings.
        try:
            raw_bytes = path.read_bytes()
            content = raw_bytes.decode("utf-8")
        except Exception as e:
            return ToolResult(content=f"Error reading file: {e}", is_error=True)

        count = content.count(old_string)
        if count == 0:
            return ToolResult(content=f"Error: old_string not found in {file_path}", is_error=True)

        if count > 1 and not replace_all:
            return ToolResult(
                content=(
                    f"Error: old_string found {count} times in {file_path}."
                    " Use replace_all=true or provide more context to make it unique."
                ),
                is_error=True,
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # Write back in binary mode to preserve original line endings
        try:
            path.write_bytes(new_content.encode("utf-8"))
        except Exception as e:
            return ToolResult(content=f"Error writing file: {e}", is_error=True)

        # Generate diff
        old_lines = content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=file_path, tofile=file_path))

        return ToolResult(content=diff or "File updated (no visible diff)")
