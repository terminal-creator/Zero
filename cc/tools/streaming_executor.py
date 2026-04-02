"""Streaming tool executor — start executing tools before API response completes.

Corresponds to TS: services/tools/StreamingToolExecutor.ts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .base import ToolRegistry, ToolResult

if TYPE_CHECKING:
    from cc.models.content_blocks import ToolUseBlock

logger = logging.getLogger(__name__)


class StreamingToolExecutor:
    """Execute tool calls as they arrive during streaming.

    Corresponds to TS: services/tools/StreamingToolExecutor.ts.

    Tool_use blocks are added as they complete (content_block_stop).
    Execution starts immediately, in parallel with remaining API output.
    Results are collected and returned in order after the stream ends.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._pending: list[tuple[str, asyncio.Task[ToolResult]]] = []
        self._completed: dict[str, ToolResult] = {}

    def add_tool(self, block: ToolUseBlock) -> None:
        """Add a completed tool_use block for immediate execution."""
        task = asyncio.create_task(self._execute(block))
        self._pending.append((block.id, task))

    async def _execute(self, block: ToolUseBlock) -> ToolResult:
        """Execute a single tool."""
        tool = self._registry.get(block.name)
        if tool is None:
            return ToolResult(content=f"Error: Unknown tool '{block.name}'", is_error=True)

        try:
            return await tool.execute(block.input)
        except Exception as e:
            logger.warning("Streaming executor: tool %s failed: %s", block.name, e)
            return ToolResult(content=f"Error: {e}", is_error=True)

    async def get_results(self) -> list[tuple[str, ToolResult]]:
        """Wait for all pending tools and return results in order.

        Called after the API stream completes.
        """
        results: list[tuple[str, ToolResult]] = []
        for tool_id, task in self._pending:
            try:
                result = await task
            except Exception as e:
                result = ToolResult(content=f"Error: {e}", is_error=True)
            results.append((tool_id, result))
        return results

    @property
    def has_pending(self) -> bool:
        return len(self._pending) > 0
