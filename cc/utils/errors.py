"""Custom error types.

Corresponds to TS: various error handling patterns across the codebase.
"""

from __future__ import annotations


class CCError(Exception):
    """Base exception for all cc errors."""


class ConfigError(CCError):
    """Configuration error (missing API key, invalid config, etc.)."""


class APIError(CCError):
    """Anthropic API error."""

    def __init__(self, message: str, status_code: int = 0, error_type: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type


class ToolExecutionError(CCError):
    """Tool execution error."""

    def __init__(self, message: str, tool_name: str = "") -> None:
        super().__init__(message)
        self.tool_name = tool_name


class CompactError(CCError):
    """Context compaction failed."""


class AbortError(CCError):
    """User interrupted the operation."""
