"""AgentTool — spawn a sub-agent with its own query loop.

Corresponds to TS: tools/AgentTool/AgentTool.tsx + runAgent.ts.
"""

from __future__ import annotations

import logging
from typing import Any

from cc.core.events import TextDelta, TurnComplete
from cc.models.messages import Message, UserMessage
from cc.prompts.sections import DEFAULT_AGENT_PROMPT
from cc.tools.base import Tool, ToolRegistry, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

AGENT_TOOL_NAME = "Agent"


class AgentTool(Tool):
    """Spawn a sub-agent to handle complex tasks.

    Corresponds to TS: tools/AgentTool/AgentTool.tsx.
    """

    def __init__(
        self,
        parent_registry: ToolRegistry,
        call_model_factory: Any,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self._parent_registry = parent_registry
        self._call_model_factory = call_model_factory
        self._model = model

    def get_name(self) -> str:
        return AGENT_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=AGENT_TOOL_NAME,
            description="Launch a sub-agent to handle complex, multi-step tasks autonomously.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The task for the agent to perform",
                    },
                    "description": {
                        "type": "string",
                        "description": "A short description of what the agent will do",
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model override for this agent",
                    },
                },
                "required": ["prompt"],
            },
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        from cc.core.query_loop import query_loop

        prompt = tool_input.get("prompt", "")
        agent_model = tool_input.get("model") or self._model

        if not prompt:
            return ToolResult(content="Error: prompt is required", is_error=True)

        # Build child registry — inherit parent tools but exclude AgentTool to prevent recursion
        child_registry = ToolRegistry()
        for tool in self._parent_registry.list_tools():
            if tool.get_name() != AGENT_TOOL_NAME:
                child_registry.register(tool)

        # Build agent system prompt
        system_prompt = DEFAULT_AGENT_PROMPT

        messages: list[Message] = [UserMessage(content=prompt)]

        # Create call_model for this agent
        call_model = self._call_model_factory(model=agent_model)

        # Run the agent's query loop and collect text output
        output_parts: list[str] = []
        try:
            async for event in query_loop(
                messages=messages,
                system_prompt=system_prompt,
                tools=child_registry,
                call_model=call_model,
                max_turns=30,
            ):
                if isinstance(event, TextDelta):
                    output_parts.append(event.text)
                elif isinstance(event, TurnComplete) and event.stop_reason == "end_turn":
                    break

        except Exception as e:
            logger.warning("Agent failed: %s", e)
            return ToolResult(content=f"Agent error: {e}", is_error=True)

        result_text = "".join(output_parts)
        if not result_text.strip():
            return ToolResult(content="(Agent produced no output)")

        return ToolResult(content=result_text)
