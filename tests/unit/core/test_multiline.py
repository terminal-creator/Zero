"""Tests for multi-line input detection.

Verifies T9.2: _needs_continuation logic.
"""

from cc.main import _needs_continuation


class TestNeedsContinuation:
    def test_normal_line(self) -> None:
        assert _needs_continuation(["hello world"]) is False

    def test_trailing_backslash(self) -> None:
        assert _needs_continuation(["line 1 \\"]) is True

    def test_unclosed_paren(self) -> None:
        assert _needs_continuation(["def foo("]) is True
        assert _needs_continuation(["def foo(", "  x,"]) is True

    def test_closed_paren(self) -> None:
        assert _needs_continuation(["def foo(x)"]) is False

    def test_unclosed_bracket(self) -> None:
        assert _needs_continuation(["data = ["]) is True

    def test_unclosed_brace(self) -> None:
        assert _needs_continuation(["config = {"]) is True

    def test_unclosed_triple_quote(self) -> None:
        assert _needs_continuation(['text = """start']) is True

    def test_closed_triple_quote(self) -> None:
        assert _needs_continuation(['text = """hello"""']) is False

    def test_complete_multiline(self) -> None:
        assert _needs_continuation([
            "data = {",
            '  "key": "value"',
            "}",
        ]) is False
