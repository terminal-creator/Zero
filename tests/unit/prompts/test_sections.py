"""Tests for system prompt sections.

Verifies T3.1: Prompt text presence and key phrase checks.
"""

from cc.prompts.sections import (
    get_actions_section,
    get_doing_tasks_section,
    get_intro_section,
    get_output_efficiency_section,
    get_system_section,
    get_tone_style_section,
    get_using_tools_section,
)


class TestPromptSections:
    def test_intro_contains_claude_code(self) -> None:
        text = get_intro_section()
        assert len(text) > 0
        assert "software engineering" in text.lower() or "interactive agent" in text.lower()

    def test_system_section_mentions_tools(self) -> None:
        text = get_system_section()
        assert "tool" in text.lower()

    def test_doing_tasks_mentions_security(self) -> None:
        text = get_doing_tasks_section()
        assert "security" in text.lower()

    def test_actions_mentions_reversibility(self) -> None:
        text = get_actions_section()
        assert "reversibility" in text.lower()

    def test_using_tools_mentions_read_and_bash(self) -> None:
        text = get_using_tools_section()
        assert "Read" in text
        assert "Bash" in text

    def test_tone_style_mentions_emoji(self) -> None:
        text = get_tone_style_section()
        assert "emoji" in text.lower()

    def test_output_efficiency_not_empty(self) -> None:
        text = get_output_efficiency_section()
        assert len(text) > 100

    def test_all_sections_are_strings(self) -> None:
        sections = [
            get_intro_section(),
            get_system_section(),
            get_doing_tasks_section(),
            get_actions_section(),
            get_using_tools_section(),
            get_tone_style_section(),
            get_output_efficiency_section(),
        ]
        for s in sections:
            assert isinstance(s, str)
            assert len(s) > 50

    def test_total_prompt_length(self) -> None:
        total = sum(len(s) for s in [
            get_intro_section(),
            get_system_section(),
            get_doing_tasks_section(),
            get_actions_section(),
            get_using_tools_section(),
            get_tone_style_section(),
            get_output_efficiency_section(),
        ])
        assert total > 5000
