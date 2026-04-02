"""Tests for tool orchestration.

Verifies T4.2: Concurrent/serial batch dispatch.
"""

import asyncio
import time
from typing import Any

from cc.models.content_blocks import ToolUseBlock
from cc.tools.base import Tool, ToolRegistry, ToolResult, ToolSchema
from cc.tools.orchestration import run_tools


class SlowTool(Tool):
    def __init__(self, name: str, delay: float, concurrent: bool = True) -> None:
        self._name = name
        self._delay = delay
        self._concurrent = concurrent

    def get_name(self) -> str:
        return self._name

    def get_schema(self) -> ToolSchema:
        return ToolSchema(name=self._name, description="", input_schema={"type": "object"})

    def is_concurrency_safe(self, tool_input: dict[str, Any]) -> bool:
        return self._concurrent

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        await asyncio.sleep(self._delay)
        return ToolResult(content=f"{self._name} done")


class ErrorTool(Tool):
    def get_name(self) -> str:
        return "error_tool"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(name="error_tool", description="", input_schema={"type": "object"})

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        raise RuntimeError("Tool exploded")


class TestRunTools:
    async def test_concurrent_tools_parallel(self) -> None:
        """3 concurrent-safe tools should run in parallel."""
        reg = ToolRegistry()
        reg.register(SlowTool("a", 0.1, concurrent=True))
        reg.register(SlowTool("b", 0.1, concurrent=True))
        reg.register(SlowTool("c", 0.1, concurrent=True))

        blocks = [
            ToolUseBlock(id="1", name="a", input={}),
            ToolUseBlock(id="2", name="b", input={}),
            ToolUseBlock(id="3", name="c", input={}),
        ]

        start = time.monotonic()
        results = await run_tools(blocks, reg)
        elapsed = time.monotonic() - start

        assert len(results) == 3
        assert all(r[1].content.endswith("done") for r in results)
        # Should take ~0.1s not ~0.3s
        assert elapsed < 0.25

    async def test_serial_tool_runs_alone(self) -> None:
        """Non-concurrent tool runs serially."""
        reg = ToolRegistry()
        reg.register(SlowTool("serial", 0.05, concurrent=False))
        reg.register(SlowTool("parallel", 0.05, concurrent=True))

        blocks = [
            ToolUseBlock(id="1", name="serial", input={}),
            ToolUseBlock(id="2", name="parallel", input={}),
        ]

        results = await run_tools(blocks, reg)
        assert len(results) == 2

    async def test_tool_error_returns_is_error(self) -> None:
        """Tool exception → is_error=True, other tools unaffected."""
        reg = ToolRegistry()
        reg.register(ErrorTool())
        reg.register(SlowTool("ok", 0.0, concurrent=False))

        blocks = [
            ToolUseBlock(id="1", name="error_tool", input={}),
            ToolUseBlock(id="2", name="ok", input={}),
        ]

        results = await run_tools(blocks, reg)
        assert results[0][1].is_error is True
        assert "exploded" in results[0][1].content
        assert results[1][1].is_error is False

    async def test_unknown_tool(self) -> None:
        """Unknown tool name → error result."""
        reg = ToolRegistry()
        blocks = [ToolUseBlock(id="1", name="nonexistent", input={})]
        results = await run_tools(blocks, reg)
        assert results[0][1].is_error is True
        assert "Unknown tool" in results[0][1].content
