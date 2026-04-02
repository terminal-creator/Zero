"""Tests for AskUserQuestionTool.

Verifies T4.11: Question display, answer capture.
"""

from cc.tools.ask_user.ask_user_tool import AskUserQuestionTool


class TestAskUserTool:
    async def test_no_input_fn_returns_message(self) -> None:
        """In non-interactive mode, returns a message instead of blocking."""
        tool = AskUserQuestionTool(input_fn=None)
        result = await tool.execute({"question": "What color?"})
        assert "non-interactive" in result.content.lower() or "Cannot" in result.content

    async def test_empty_question_error(self) -> None:
        tool = AskUserQuestionTool()
        result = await tool.execute({"question": ""})
        assert result.is_error

    def test_schema(self) -> None:
        tool = AskUserQuestionTool()
        schema = tool.get_schema()
        assert schema.name == "AskUserQuestion"
        assert "question" in schema.input_schema["properties"]
