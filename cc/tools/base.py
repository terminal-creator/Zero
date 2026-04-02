"""Tool base class and types.

Corresponds to TS: Tool.ts (ToolDef, buildTool) + tools.ts (assembleToolPool).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSchema:
    """Tool schema for API registration."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolResult:
    """Result of a tool execution.

    FIX (check.md #5): content can be str or list of content block dicts
    to support images, structured MCP results, etc.
    """

    content: str | list[dict[str, Any]]
    is_error: bool = False

    @property
    def text(self) -> str:
        """Extract text content regardless of content type."""
        if isinstance(self.content, str):
            return self.content
        return "\n".join(
            block.get("text", str(block)) for block in self.content if isinstance(block, dict)
        )


class Tool(ABC):
    """Base class for all tools.

    Corresponds to TS: Tool.ts ToolDef interface.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return the tool name as registered with the API."""
        ...

    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """Return the tool's JSON schema for API registration."""
        ...

    @abstractmethod
    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given input.

        Args:
            tool_input: Validated input parameters.

        Returns:
            ToolResult with content and error status.
        """
        ...

    def is_concurrency_safe(self, tool_input: dict[str, Any]) -> bool:
        """Whether this tool can run concurrently with others.

        Corresponds to TS: Tool.ts isConcurrencySafe.
        Override in subclasses. Default: False (serial).
        """
        return False


@dataclass
class ToolRegistry:
    """Registry of available tools.

    Corresponds to TS: tools.ts assembleToolPool().
    """

    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        name = tool.get_name()
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_api_schemas(self) -> list[dict[str, Any]]:
        """Return all tool schemas in API format."""
        schemas = []
        for tool in self._tools.values():
            schema = tool.get_schema()
            schemas.append({
                "name": schema.name,
                "description": schema.description,
                "input_schema": schema.input_schema,
            })
        return schemas
