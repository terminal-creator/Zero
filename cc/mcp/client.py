"""MCP client — connect to MCP servers and register tools.

Corresponds to TS: services/mcp/client.ts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from cc.tools.base import Tool, ToolRegistry, ToolResult, ToolSchema

if TYPE_CHECKING:
    from .config import McpServerConfig

logger = logging.getLogger(__name__)

MCP_TOOL_NAME_PREFIX = "mcp__"


class McpToolProxy(Tool):
    """Proxy tool that delegates to an MCP server via RPC.

    Corresponds to TS: services/mcp/client.ts MCP tool execution.
    """

    def __init__(
        self, server_name: str, tool_name: str, description: str, input_schema: dict[str, Any], session: Any,
    ) -> None:
        self._server_name = server_name
        self._tool_name = tool_name
        self._description = description
        self._input_schema = input_schema
        self._session = session

    def get_name(self) -> str:
        return f"{MCP_TOOL_NAME_PREFIX}{self._server_name}__{self._tool_name}"

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.get_name(),
            description=self._description,
            input_schema=self._input_schema,
        )

    def is_concurrency_safe(self, tool_input: dict[str, Any]) -> bool:
        return True  # MCP tools are assumed safe

    async def execute(self, tool_input: dict[str, Any]) -> ToolResult:
        """Execute MCP tool, preserving structured content when possible."""
        try:
            result = await self._session.call_tool(self._tool_name, arguments=tool_input)
            if not hasattr(result, "content") or not result.content:
                return ToolResult(content="(no output)")

            # Build rich content blocks preserving structure
            rich_blocks: list[dict[str, Any]] = []
            text_parts: list[str] = []

            for block in result.content:
                if hasattr(block, "type"):
                    if block.type == "text" and hasattr(block, "text"):
                        rich_blocks.append({"type": "text", "text": block.text})
                        text_parts.append(block.text)
                    elif block.type == "image" and hasattr(block, "data"):
                        rich_blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": getattr(block, "mimeType", "image/png"),
                                "data": block.data,
                            },
                        })
                    else:
                        # Unknown block type — serialize as text
                        text_parts.append(str(block))
                elif hasattr(block, "text"):
                    text_parts.append(block.text)

            # Return rich content if we have non-text blocks, otherwise plain string
            if any(b.get("type") != "text" for b in rich_blocks):
                return ToolResult(content=rich_blocks)
            return ToolResult(content="\n".join(text_parts) if text_parts else "(no output)")

        except Exception as e:
            return ToolResult(content=f"MCP tool error: {e}", is_error=True)


async def connect_mcp_server(
    config: McpServerConfig,
    registry: ToolRegistry,
) -> Any:
    """Connect to an MCP server and register its tools.

    Corresponds to TS: services/mcp/client.ts connectToServer() + fetchToolsForClient().

    Returns the MCP session (or None on failure).
    """
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        logger.warning("MCP SDK not installed. Run: pip install mcp")
        return None

    if config.transport != "stdio":
        logger.warning("Only stdio transport is currently supported, got: %s", config.transport)
        return None

    try:
        params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env if config.env else None,
        )

        # Connect and register tools
        read_stream, write_stream = await asyncio.wait_for(
            stdio_client(params).__aenter__(),
            timeout=30.0,
        )

        session = await asyncio.wait_for(
            ClientSession(read_stream, write_stream).__aenter__(),
            timeout=10.0,
        )

        await session.initialize()

        # Fetch and register tools
        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            proxy = McpToolProxy(
                server_name=config.name,
                tool_name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {"type": "object"},
                session=session,
            )
            try:
                registry.register(proxy)
                logger.info("Registered MCP tool: %s", proxy.get_name())
            except ValueError:
                logger.warning("MCP tool already registered: %s", proxy.get_name())

        return session

    except ImportError:
        logger.warning("MCP SDK not installed")
        return None
    except TimeoutError:
        logger.warning("MCP server connection timed out: %s", config.name)
        return None
    except Exception as e:
        logger.warning("Failed to connect MCP server '%s': %s", config.name, e)
        return None
