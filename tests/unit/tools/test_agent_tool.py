"""Tests for AgentTool.

Verifies T4.9: Sub-agent spawning, tool pool inheritance, no recursion.
"""

from typing import Any

from cc.core.events import TextDelta, TurnComplete
from cc.models.messages import Usage
from cc.tools.agent.agent_tool import AGENT_TOOL_NAME, AgentTool
from cc.tools.base import Tool, ToolRegistry, ToolResult, ToolSchema


class DummyTool(Tool):
    def __init__(self, name: str = "dummy") -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    def get_schema(self) -> ToolSchema:
        return ToolSchema(name=self._name, description="", input_schema={"type": "object"})

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        return ToolResult(content="dummy result")


class TestAgentTool:
    async def test_agent_returns_text(self) -> None:
        """Mock API returns simple text → AgentTool returns that text."""
        registry = ToolRegistry()
        registry.register(DummyTool("bash"))

        # Mock call_model_factory that creates generators yielding mock events
        def factory(model: str = "") -> Any:
            async def call_model(**kwargs: Any) -> Any:
                yield TextDelta(text="Agent output here")
                yield TurnComplete(stop_reason="end_turn", usage=Usage())

            return call_model

        tool = AgentTool(parent_registry=registry, call_model_factory=factory)
        result = await tool.execute({"prompt": "Do something"})

        assert not result.is_error
        assert "Agent output here" in result.content

    async def test_agent_excludes_itself(self) -> None:
        """Agent's child registry should not contain AgentTool."""
        registry = ToolRegistry()
        registry.register(DummyTool("bash"))

        def factory(model: str = "") -> Any:
            async def call_model(**kwargs: Any) -> Any:
                # Check that the tools param doesn't contain Agent
                tools = kwargs.get("tools", [])
                if tools:
                    names = [t.get("name", "") for t in tools if isinstance(t, dict)]
                    assert AGENT_TOOL_NAME not in names
                yield TextDelta(text="ok")
                yield TurnComplete(stop_reason="end_turn", usage=Usage())

            return call_model

        agent_tool = AgentTool(parent_registry=registry, call_model_factory=factory)
        registry.register(agent_tool)  # Parent has AgentTool

        result = await agent_tool.execute({"prompt": "test"})
        assert not result.is_error

    async def test_empty_prompt_error(self) -> None:
        registry = ToolRegistry()

        def factory(model: str = "") -> Any:
            pass

        tool = AgentTool(parent_registry=registry, call_model_factory=factory)
        result = await tool.execute({"prompt": ""})
        assert result.is_error
