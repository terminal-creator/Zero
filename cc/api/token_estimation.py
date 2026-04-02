"""Token estimation utilities.

Corresponds to TS: services/tokenEstimation.ts.
"""

from __future__ import annotations

BYTES_PER_TOKEN = 4
JSON_BYTES_PER_TOKEN = 2


def estimate_tokens(text: str, bytes_per_token: int = BYTES_PER_TOKEN) -> int:
    """Rough token count estimation.

    Corresponds to TS: services/tokenEstimation.ts roughTokenCountEstimation().

    Args:
        text: Input text to estimate.
        bytes_per_token: Bytes per token ratio (default 4, use 2 for JSON).

    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    return max(1, len(text.encode("utf-8")) // bytes_per_token)


async def count_tokens_api(
    client: object,
    messages: list[dict[str, object]],
    model: str = "claude-sonnet-4-20250514",
) -> int:
    """Count tokens using the Anthropic API's count_tokens endpoint.

    Corresponds to TS: services/tokenEstimation.ts countMessagesTokensWithAPI().
    """
    import anthropic

    if not isinstance(client, anthropic.AsyncAnthropic):
        raise TypeError("client must be an AsyncAnthropic instance")

    result = await client.messages.count_tokens(
        model=model,
        messages=messages,  # type: ignore[arg-type]
    )
    return result.input_tokens


def estimate_messages_tokens(messages: list[dict[str, object]]) -> int:
    """Estimate token count for a list of API messages.

    Args:
        messages: API-formatted messages.

    Returns:
        Estimated total token count.
    """
    import json

    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        else:
            total += estimate_tokens(json.dumps(content), bytes_per_token=JSON_BYTES_PER_TOKEN)
    return total
