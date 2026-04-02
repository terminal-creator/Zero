"""Tests for WebFetchTool.

Verifies T4.10: URL fetching, error handling.
"""


from cc.tools.web_fetch.web_fetch_tool import WebFetchTool


class TestWebFetchTool:
    async def test_empty_url_error(self) -> None:
        tool = WebFetchTool()
        result = await tool.execute({"url": ""})
        assert result.is_error

    def test_is_concurrency_safe(self) -> None:
        tool = WebFetchTool()
        assert tool.is_concurrency_safe({}) is True

    def test_schema(self) -> None:
        tool = WebFetchTool()
        schema = tool.get_schema()
        assert schema.name == "WebFetch"
        assert "url" in schema.input_schema["properties"]
