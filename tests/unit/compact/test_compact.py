"""Tests for compact system.

Verifies T7.1: Compaction logic, threshold, circuit breaker.
"""

from cc.compact.compact import should_auto_compact


class TestShouldAutoCompact:
    def test_below_threshold(self) -> None:
        assert should_auto_compact(100_000, context_window=200_000) is False

    def test_above_threshold(self) -> None:
        # 200_000 - 13_000 = 187_000 threshold
        assert should_auto_compact(190_000, context_window=200_000) is True

    def test_exactly_at_threshold(self) -> None:
        assert should_auto_compact(187_000, context_window=200_000) is True

    def test_circuit_breaker_stops_after_3_failures(self) -> None:
        assert should_auto_compact(190_000, context_window=200_000, consecutive_failures=2) is True
        assert should_auto_compact(190_000, context_window=200_000, consecutive_failures=3) is False

    def test_circuit_breaker_at_max(self) -> None:
        assert should_auto_compact(190_000, context_window=200_000, consecutive_failures=5) is False
