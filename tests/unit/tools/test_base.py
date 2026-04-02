"""Tests for tool base classes.

Verifies T4.1: Tool base, ToolRegistry.
"""

from typing import Any

import pytest

from cc.tools.base import Tool, ToolRegistry, ToolResult, ToolSchema


class MockTool(Tool):
    def __init__(self, name: str = "mock") -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self._name,
            description="A mock tool",
            input_schema={"type": "object", "properties": {}},
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        return ToolResult(content="mock result")


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = MockTool("test_tool")
        reg.register(tool)
        assert reg.get("test_tool") is tool

    def test_get_unknown_returns_none(self) -> None:
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_duplicate_registration_raises(self) -> None:
        reg = ToolRegistry()
        reg.register(MockTool("dup"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(MockTool("dup"))

    def test_list_tools(self) -> None:
        reg = ToolRegistry()
        reg.register(MockTool("a"))
        reg.register(MockTool("b"))
        assert len(reg.list_tools()) == 2

    def test_get_api_schemas(self) -> None:
        reg = ToolRegistry()
        reg.register(MockTool("test"))
        schemas = reg.get_api_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "test"
        assert "description" in schemas[0]
        assert "input_schema" in schemas[0]

    def test_schema_is_json_serializable(self) -> None:
        import json

        reg = ToolRegistry()
        reg.register(MockTool("test"))
        schemas = reg.get_api_schemas()
        json.dumps(schemas)  # Should not raise
