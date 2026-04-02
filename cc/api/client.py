"""Anthropic API client factory.

Corresponds to TS: services/api/client.ts.
"""

from __future__ import annotations

import os

import anthropic

from cc.utils.errors import ConfigError


def create_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> anthropic.AsyncAnthropic:
    """Create an async Anthropic client.

    Corresponds to TS: services/api/client.ts client creation.

    Args:
        api_key: API key. Falls back to ANTHROPIC_API_KEY env var.
        base_url: Optional base URL override.

    Returns:
        Configured AsyncAnthropic client.

    Raises:
        ConfigError: If no API key is available.
    """
    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_key:
        raise ConfigError(
            "No API key found. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter."
        )

    if base_url:
        return anthropic.AsyncAnthropic(api_key=resolved_key, base_url=base_url)
    return anthropic.AsyncAnthropic(api_key=resolved_key)
