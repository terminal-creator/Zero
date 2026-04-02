"""Tests for token estimation.

Verifies T2.3: Token estimation logic.
"""

from cc.api.token_estimation import estimate_messages_tokens, estimate_tokens


class TestEstimateTokens:
    def test_hello_world(self) -> None:
        result = estimate_tokens("hello world")
        assert result > 0

    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_thousand_chars(self) -> None:
        text = "a" * 1000
        result = estimate_tokens(text)
        assert 200 <= result <= 300

    def test_unicode(self) -> None:
        result = estimate_tokens("你好世界")
        assert result > 0

    def test_json_ratio(self) -> None:
        text = '{"key": "value", "nested": {"a": 1}}'
        normal = estimate_tokens(text)
        json_est = estimate_tokens(text, bytes_per_token=2)
        assert json_est > normal  # JSON ratio gives more tokens


class TestEstimateMessagesTokens:
    def test_string_content(self) -> None:
        messages = [{"role": "user", "content": "hello world"}]
        result = estimate_messages_tokens(messages)
        assert result > 0

    def test_list_content(self) -> None:
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        ]
        result = estimate_messages_tokens(messages)
        assert result > 0

    def test_multiple_messages(self) -> None:
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "how are you"},
        ]
        result = estimate_messages_tokens(messages)
        single = estimate_messages_tokens([messages[0]])
        assert result > single
