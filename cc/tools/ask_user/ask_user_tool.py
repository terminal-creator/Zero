"""AskUserQuestionTool — pause and ask the user a question.

Corresponds to TS: tools/AskUserQuestionTool/AskUserQuestionTool.tsx.
"""

from __future__ import annotations

from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

ASK_USER_TOOL_NAME = "AskUserQuestion"


class AskUserQuestionTool(Tool):
    """Ask the user a question and return their answer.

    Corresponds to TS: tools/AskUserQuestionTool/AskUserQuestionTool.tsx.
    The input_fn is injected by the REPL to handle actual user input.
    """

    def __init__(self, input_fn: Any = None) -> None:
        self._input_fn = input_fn

    def get_name(self) -> str:
        return ASK_USER_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=ASK_USER_TOOL_NAME,
            description="Ask the user a question and wait for their response.",
            input_schema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user",
                    },
                },
                "required": ["question"],
            },
        )

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        question = tool_input.get("question", "")
        if not question:
            return ToolResult(content="Error: question is required", is_error=True)

        if self._input_fn is None:
            # No input function — non-interactive mode
            return ToolResult(content="(Cannot ask user in non-interactive mode)")

        try:
            from rich.console import Console

            console = Console()
            console.print(f"\n[bold yellow]Question:[/] {question}")
            answer = console.input("[bold blue]Answer: [/]")
            return ToolResult(content=answer)
        except (EOFError, KeyboardInterrupt):
            return ToolResult(content="(User did not answer)")
