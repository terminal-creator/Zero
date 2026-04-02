"""Tests for Hooks system.

Verifies T10.2: Hook loading, execution, blocking.
"""

import json
from pathlib import Path

from cc.hooks.hook_runner import HookConfig, load_hooks, run_hook, run_pre_tool_hooks


class TestLoadHooks:
    def test_load_from_settings(self, tmp_path: Path) -> None:
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"command": "echo pre", "tool_name": "Bash"},
                ],
                "PostToolUse": [
                    {"command": "echo post"},
                ],
            }
        }
        (tmp_path / "settings.json").write_text(json.dumps(settings))
        hooks = load_hooks(claude_dir=tmp_path)
        assert len(hooks) == 2
        assert hooks[0].event == "PreToolUse"
        assert hooks[1].event == "PostToolUse"

    def test_empty_settings(self, tmp_path: Path) -> None:
        (tmp_path / "settings.json").write_text("{}")
        hooks = load_hooks(claude_dir=tmp_path)
        assert hooks == []

    def test_no_settings_file(self, tmp_path: Path) -> None:
        hooks = load_hooks(claude_dir=tmp_path)
        assert hooks == []


class TestRunHook:
    async def test_allow_hook(self) -> None:
        hook = HookConfig(event="PreToolUse", command="exit 0")
        result = await run_hook(hook, {"tool_name": "Bash"})
        assert not result.blocked

    async def test_block_hook(self) -> None:
        hook = HookConfig(event="PreToolUse", command='echo "blocked" && exit 2')
        result = await run_hook(hook, {"tool_name": "Bash"})
        assert result.blocked
        assert "blocked" in result.message

    async def test_timeout_hook(self) -> None:
        hook = HookConfig(event="PreToolUse", command="sleep 100")
        # Override timeout to be very short for test
        import cc.hooks.hook_runner as mod
        original = mod.HOOK_TIMEOUT_S
        mod.HOOK_TIMEOUT_S = 0.5
        try:
            result = await run_hook(hook, {})
            assert not result.blocked  # Timeout doesn't block
        finally:
            mod.HOOK_TIMEOUT_S = original


class TestRunPreToolHooks:
    async def test_matching_tool_blocks(self) -> None:
        hooks = [HookConfig(event="PreToolUse", command="exit 2", tool_name="Bash")]
        result = await run_pre_tool_hooks(hooks, "Bash", {"command": "ls"})
        assert result.blocked

    async def test_non_matching_tool_passes(self) -> None:
        hooks = [HookConfig(event="PreToolUse", command="exit 2", tool_name="Bash")]
        result = await run_pre_tool_hooks(hooks, "Read", {"file_path": "/tmp/x"})
        assert not result.blocked

    async def test_no_hooks(self) -> None:
        result = await run_pre_tool_hooks([], "Bash", {})
        assert not result.blocked
