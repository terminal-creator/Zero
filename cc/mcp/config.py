"""MCP server configuration loading.

Corresponds to TS: services/mcp/config.ts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class McpServerConfig:
    """Configuration for a single MCP server."""

    name: str
    transport: str  # "stdio" | "sse" | "http"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""


def load_mcp_configs(
    cwd: str,
    claude_dir: Path | None = None,
) -> list[McpServerConfig]:
    """Load MCP server configurations from settings and .mcp.json.

    Corresponds to TS: services/mcp/config.ts.

    Sources (in order):
    1. ~/.claude/settings.json → mcpServers
    2. .mcp.json in project root
    """
    configs: list[McpServerConfig] = []

    # User settings
    settings_path = (claude_dir or Path.home() / ".claude") / "settings.json"
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            mcp_servers = settings.get("mcpServers", {})
            for name, server_config in mcp_servers.items():
                cfg = _parse_server_config(name, server_config)
                if cfg:
                    configs.append(cfg)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load MCP config from settings: %s", e)

    # Project .mcp.json
    mcp_json = Path(cwd) / ".mcp.json"
    if mcp_json.is_file():
        try:
            data = json.loads(mcp_json.read_text(encoding="utf-8"))
            mcp_servers = data.get("mcpServers", {})
            for name, server_config in mcp_servers.items():
                cfg = _parse_server_config(name, server_config)
                if cfg:
                    configs.append(cfg)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load .mcp.json: %s", e)

    return configs


def _parse_server_config(name: str, raw: dict[str, Any]) -> McpServerConfig | None:
    """Parse a single MCP server config entry."""
    transport = raw.get("type", raw.get("transport", ""))

    if transport not in ("stdio", "sse", "http"):
        logger.warning("Skipping MCP server '%s': unknown transport '%s'", name, transport)
        return None

    if transport == "stdio":
        command = raw.get("command", "")
        if not command:
            logger.warning("Skipping MCP server '%s': missing command for stdio transport", name)
            return None
        return McpServerConfig(
            name=name,
            transport=transport,
            command=command,
            args=raw.get("args", []),
            env=raw.get("env", {}),
        )

    # SSE or HTTP
    url = raw.get("url", "")
    if not url:
        logger.warning("Skipping MCP server '%s': missing url for %s transport", name, transport)
        return None
    return McpServerConfig(
        name=name,
        transport=transport,
        url=url,
    )
