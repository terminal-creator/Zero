"""Tests for MCP configuration loading.

Verifies T8.1: Config parsing from settings.json and .mcp.json.
"""

import json
from pathlib import Path

from cc.mcp.config import load_mcp_configs


class TestMcpConfig:
    def test_load_from_mcp_json(self, tmp_path: Path) -> None:
        mcp_json = {
            "mcpServers": {
                "filesystem": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                }
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_json))
        configs = load_mcp_configs(str(tmp_path))
        assert len(configs) == 1
        assert configs[0].name == "filesystem"
        assert configs[0].transport == "stdio"
        assert configs[0].command == "npx"

    def test_load_from_settings(self, tmp_path: Path) -> None:
        settings = {
            "mcpServers": {
                "myserver": {
                    "type": "sse",
                    "url": "http://localhost:3000/sse",
                }
            }
        }
        (tmp_path / "settings.json").write_text(json.dumps(settings))
        configs = load_mcp_configs(str(tmp_path / "project"), claude_dir=tmp_path)
        assert len(configs) == 1
        assert configs[0].transport == "sse"
        assert configs[0].url == "http://localhost:3000/sse"

    def test_skip_unknown_transport(self, tmp_path: Path) -> None:
        mcp_json = {
            "mcpServers": {
                "weird": {"type": "ftp", "url": "ftp://server"},
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_json))
        configs = load_mcp_configs(str(tmp_path))
        assert len(configs) == 0

    def test_missing_command_for_stdio(self, tmp_path: Path) -> None:
        mcp_json = {"mcpServers": {"bad": {"type": "stdio"}}}
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_json))
        configs = load_mcp_configs(str(tmp_path))
        assert len(configs) == 0

    def test_no_config_files(self, tmp_path: Path) -> None:
        configs = load_mcp_configs(str(tmp_path), claude_dir=tmp_path)
        assert configs == []

    def test_env_vars_passed(self, tmp_path: Path) -> None:
        mcp_json = {
            "mcpServers": {
                "server": {
                    "type": "stdio",
                    "command": "node",
                    "args": ["server.js"],
                    "env": {"API_KEY": "secret"},
                }
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_json))
        configs = load_mcp_configs(str(tmp_path))
        assert configs[0].env == {"API_KEY": "secret"}
