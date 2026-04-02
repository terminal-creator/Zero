"""End-to-end CLI tests.

Verifies T9.1: CLI --print mode with real API, and --help.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).parent.parent.parent


def get_api_key() -> str | None:
    """Get API key from env var or project .env file."""
    import os

    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = PROJECT_DIR / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


class TestCLIHelp:
    def test_help(self) -> None:
        """python -m cc --help shows help."""
        result = subprocess.run(
            [sys.executable, "-m", "cc", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_DIR),
        )
        assert result.returncode == 0
        assert "cc-python-claude" in result.stdout


skip_no_key = pytest.mark.skipif(get_api_key() is None, reason="No API key")


@skip_no_key
class TestCLIPrintMode:
    def test_print_mode(self) -> None:
        """python -m cc -p 'prompt' produces output."""
        import os

        env = {**os.environ, "ANTHROPIC_API_KEY": get_api_key() or ""}
        result = subprocess.run(
            [sys.executable, "-m", "cc", "-p", "Say exactly one word: hello"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_DIR),
            env=env,
        )
        assert result.returncode == 0
        assert len(result.stdout.strip()) > 0
