"""Tool orchestration — concurrent/serial dispatch with hooks integration.

Corresponds to TS: services/tools/toolOrchestration.ts + toolExecution.ts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .base import ToolRegistry, ToolResult

if TYPE_CHECKING:
    from cc.hooks.hook_runner import HookConfig
    from cc.models.content_blocks import ToolUseBlock

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 10


async def run_tools(
    tool_use_blocks: list[ToolUseBlock],
    registry: ToolRegistry,
    hooks: list[HookConfig] | None = None,
) -> list[tuple[str, ToolResult]]:
    """Execute tool calls, respecting concurrency safety and hooks.

    Corresponds to TS: services/tools/toolOrchestration.ts runTools().

    Hooks integration: PreToolUse hooks can block execution, PostToolUse hooks
    are called after each tool completes.
    """
    results: list[tuple[str, ToolResult]] = []
    batches = _partition_batches(tool_use_blocks, registry)

    for batch in batches:
        if len(batch) == 1:
            tu = batch[0]
            result = await _execute_one(tu, registry, hooks)
            results.append((tu.id, result))
        else:
            sem = asyncio.Semaphore(MAX_CONCURRENCY)
            batch_results = await asyncio.gather(
                *[_execute_with_sem(sem, b, registry, hooks) for b in batch]
            )
            results.extend(batch_results)

    return results


async def _execute_with_sem(
    sem: asyncio.Semaphore,
    block: ToolUseBlock,
    registry: ToolRegistry,
    hooks: list[HookConfig] | None,
) -> tuple[str, ToolResult]:
    """Execute a tool within a semaphore-bounded context."""
    async with sem:
        return (block.id, await _execute_one(block, registry, hooks))


def _partition_batches(
    blocks: list[ToolUseBlock],
    registry: ToolRegistry,
) -> list[list[ToolUseBlock]]:
    """Partition tool use blocks into execution batches."""
    batches: list[list[ToolUseBlock]] = []
    current_concurrent: list[ToolUseBlock] = []

    for block in blocks:
        tool = registry.get(block.name)
        is_safe = tool is not None and tool.is_concurrency_safe(block.input)

        if is_safe:
            current_concurrent.append(block)
        else:
            if current_concurrent:
                batches.append(current_concurrent)
                current_concurrent = []
            batches.append([block])

    if current_concurrent:
        batches.append(current_concurrent)

    return batches


async def _execute_one(
    block: ToolUseBlock,
    registry: ToolRegistry,
    hooks: list[HookConfig] | None,
) -> ToolResult:
    """Execute a single tool call with pre/post hooks."""
    tool = registry.get(block.name)
    if tool is None:
        return ToolResult(content=f"Error: Unknown tool '{block.name}'", is_error=True)

    # Run PreToolUse hooks
    if hooks:
        from cc.hooks.hook_runner import run_pre_tool_hooks

        hook_result = await run_pre_tool_hooks(hooks, block.name, block.input)
        if hook_result.blocked:
            return ToolResult(
                content=f"Blocked by hook: {hook_result.message}",
                is_error=True,
            )

    # Execute tool
    try:
        result = await tool.execute(block.input)
    except Exception as e:
        logger.warning("Tool %s failed: %s", block.name, e)
        result = ToolResult(content=f"Error: {e}", is_error=True)

    # Run PostToolUse hooks
    if hooks:
        from cc.hooks.hook_runner import run_post_tool_hooks

        await run_post_tool_hooks(hooks, block.name, block.input, result.text)

    return result
