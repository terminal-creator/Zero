"""WebFetchTool — fetch web pages and convert to text.

Corresponds to TS: tools/WebFetchTool/WebFetchTool.ts.
"""

from __future__ import annotations

import logging
from typing import Any

from cc.tools.base import Tool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

WEB_FETCH_TOOL_NAME = "WebFetch"
MAX_CONTENT_BYTES = 100_000


class WebFetchTool(Tool):
    """Fetch a URL and return its content.

    Corresponds to TS: tools/WebFetchTool/WebFetchTool.ts.
    """

    def get_name(self) -> str:
        return WEB_FETCH_TOOL_NAME

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=WEB_FETCH_TOOL_NAME,
            description="Fetches a URL and returns its content as text or markdown.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch",
                    },
                },
                "required": ["url"],
            },
        )

    def is_concurrency_safe(self, tool_input: dict[str, Any]) -> bool:
        return True

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        url = tool_input.get("url", "")
        if not url:
            return ToolResult(content="Error: url is required", is_error=True)

        import httpx

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                body = response.text

                # Truncate if too large
                if len(body.encode("utf-8")) > MAX_CONTENT_BYTES:
                    body = body[:MAX_CONTENT_BYTES // 4]
                    body += f"\n\n... (content truncated, exceeded {MAX_CONTENT_BYTES} bytes)"

                # Try HTML → Markdown conversion
                if "text/html" in content_type:
                    try:
                        from markdownify import markdownify

                        body = markdownify(body, heading_style="ATX", strip=["script", "style"])
                    except ImportError:
                        pass  # markdownify not installed, return raw HTML

                return ToolResult(content=body)

        except httpx.HTTPStatusError as e:
            return ToolResult(content=f"HTTP error {e.response.status_code}: {e}", is_error=True)
        except httpx.ConnectError:
            return ToolResult(content=f"Error: Could not connect to {url}", is_error=True)
        except Exception as e:
            return ToolResult(content=f"Error fetching URL: {e}", is_error=True)
