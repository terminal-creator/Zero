"""Tests for API client factory.

Verifies T2.1: Client creation, env var fallback, error on missing key.
"""

import os
from unittest.mock import patch

import pytest

from cc.api.client import create_client
from cc.utils.errors import ConfigError


class TestCreateClient:
    def test_with_explicit_key(self) -> None:
        client = create_client(api_key="test-key-123")
        assert client.api_key == "test-key-123"

    def test_with_env_var(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key-456"}):
            client = create_client()
            assert client.api_key == "env-key-456"

    def test_missing_key_raises_config_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # Ensure no ANTHROPIC_API_KEY
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(ConfigError, match="No API key found"):
                create_client()

    def test_custom_base_url(self) -> None:
        client = create_client(api_key="key", base_url="https://custom.api.com")
        assert str(client.base_url).rstrip("/") == "https://custom.api.com"

    def test_explicit_key_overrides_env(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            client = create_client(api_key="explicit-key")
            assert client.api_key == "explicit-key"
