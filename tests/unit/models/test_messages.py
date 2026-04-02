"""Tests for message models and normalization.

Verifies T1.2: Message models, normalize_for_api, edge cases.
"""

from cc.models.content_blocks import TextBlock, ToolResultBlock, ToolUseBlock
from cc.models.messages import (
    AssistantMessage,
    CompactBoundaryMessage,
    SystemMessage,
    UserMessage,
    create_assistant_message,
    create_tool_result_message,
    create_user_message,
    get_messages_after_compact_boundary,
    normalize_messages_for_api,
)


class TestUserMessage:
    def test_string_content_to_api(self) -> None:
        msg = UserMessage(content="hello")
        api = msg.to_api_dict()
        assert api == {"role": "user", "content": "hello"}

    def test_block_content_to_api(self) -> None:
        msg = UserMessage(content=[TextBlock(text="hello"), TextBlock(text=" world")])
        api = msg.to_api_dict()
        assert api["role"] == "user"
        assert len(api["content"]) == 2


class TestAssistantMessage:
    def test_to_api(self) -> None:
        msg = AssistantMessage(content=[TextBlock(text="response")])
        api = msg.to_api_dict()
        assert api == {"role": "assistant", "content": [{"type": "text", "text": "response"}]}

    def test_get_text(self) -> None:
        msg = AssistantMessage(content=[
            TextBlock(text="hello "),
            TextBlock(text="world"),
        ])
        assert msg.get_text() == "hello world"

    def test_get_text_skips_non_text(self) -> None:
        msg = AssistantMessage(content=[
            TextBlock(text="before "),
            ToolUseBlock(id="1", name="bash", input={}),
            TextBlock(text="after"),
        ])
        assert msg.get_text() == "before after"

    def test_get_tool_use_blocks(self) -> None:
        tu1 = ToolUseBlock(id="1", name="bash", input={"command": "ls"})
        tu2 = ToolUseBlock(id="2", name="read", input={"file_path": "/tmp/x"})
        msg = AssistantMessage(content=[TextBlock(text="hi"), tu1, tu2])
        tool_uses = msg.get_tool_use_blocks()
        assert len(tool_uses) == 2
        assert tool_uses[0].name == "bash"
        assert tool_uses[1].name == "read"


class TestNormalizeMessagesForApi:
    def test_simple_conversation(self) -> None:
        messages = [
            UserMessage(content="hello"),
            AssistantMessage(content=[TextBlock(text="hi")]),
            UserMessage(content="how are you"),
        ]
        api = normalize_messages_for_api(messages)
        assert len(api) == 3
        assert api[0]["role"] == "user"
        assert api[1]["role"] == "assistant"
        assert api[2]["role"] == "user"

    def test_tool_use_and_result(self) -> None:
        messages = [
            UserMessage(content="list files"),
            AssistantMessage(content=[
                TextBlock(text="Let me check."),
                ToolUseBlock(id="tu_1", name="bash", input={"command": "ls"}),
            ]),
            UserMessage(content=[
                ToolResultBlock(tool_use_id="tu_1", content="file1.py\nfile2.py"),
            ]),
            AssistantMessage(content=[TextBlock(text="Found 2 files.")]),
        ]
        api = normalize_messages_for_api(messages)
        assert len(api) == 4
        # tool_result should be in user message
        user_with_result = api[2]
        assert user_with_result["role"] == "user"
        assert isinstance(user_with_result["content"], list)
        assert user_with_result["content"][0]["type"] == "tool_result"

    def test_consecutive_user_messages_merged(self) -> None:
        messages = [
            UserMessage(content="first"),
            UserMessage(content="second"),
            AssistantMessage(content=[TextBlock(text="ok")]),
        ]
        api = normalize_messages_for_api(messages)
        assert len(api) == 2  # merged user + assistant
        assert api[0]["role"] == "user"

    def test_consecutive_assistant_messages_get_separator(self) -> None:
        messages = [
            UserMessage(content="hi"),
            AssistantMessage(content=[TextBlock(text="a")]),
            AssistantMessage(content=[TextBlock(text="b")]),
        ]
        api = normalize_messages_for_api(messages)
        # Should have: user, assistant, user(separator), assistant
        assert len(api) == 4
        assert api[2]["role"] == "user"

    def test_starts_with_assistant_gets_user_prefix(self) -> None:
        messages = [
            AssistantMessage(content=[TextBlock(text="a")]),
        ]
        api = normalize_messages_for_api(messages)
        assert api[0]["role"] == "user"
        assert api[1]["role"] == "assistant"

    def test_orphaned_tool_result_removed(self) -> None:
        messages = [
            UserMessage(content=[
                ToolResultBlock(tool_use_id="nonexistent", content="data"),
            ]),
            AssistantMessage(content=[TextBlock(text="ok")]),
        ]
        api = normalize_messages_for_api(messages)
        user_msg = api[0]
        # Orphaned tool_result should be removed, replaced with placeholder
        content = user_msg["content"]
        assert isinstance(content, list)
        assert all(
            not (isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") == "nonexistent")
            for b in content
        )

    def test_system_messages_skipped(self) -> None:
        messages = [
            UserMessage(content="hi"),
            SystemMessage(content="system info"),
            AssistantMessage(content=[TextBlock(text="ok")]),
        ]
        api = normalize_messages_for_api(messages)
        assert len(api) == 2

    def test_compact_boundary_becomes_user_message(self) -> None:
        messages = [
            CompactBoundaryMessage(summary="Previous conversation discussed X and Y."),
            UserMessage(content="continue"),
            AssistantMessage(content=[TextBlock(text="ok")]),
        ]
        api = normalize_messages_for_api(messages)
        assert api[0]["role"] == "user"
        # Content may be string or list after merging
        content = api[0]["content"]
        if isinstance(content, str):
            text = content.lower()
        else:
            text = " ".join(
                b["text"].lower() if isinstance(b, dict) and "text" in b else str(b).lower() for b in content
            )
        assert "summary" in text or "previous" in text

    def test_three_tool_uses_three_results(self) -> None:
        """3 tool_use blocks in one assistant message → 3 tool_results in one user message."""
        messages = [
            UserMessage(content="do stuff"),
            AssistantMessage(content=[
                ToolUseBlock(id="t1", name="bash", input={"command": "ls"}),
                ToolUseBlock(id="t2", name="bash", input={"command": "pwd"}),
                ToolUseBlock(id="t3", name="bash", input={"command": "whoami"}),
            ]),
            UserMessage(content=[
                ToolResultBlock(tool_use_id="t1", content="file1"),
                ToolResultBlock(tool_use_id="t2", content="/home"),
                ToolResultBlock(tool_use_id="t3", content="user"),
            ]),
        ]
        api = normalize_messages_for_api(messages)
        assert len(api) == 3
        tool_results = api[2]["content"]
        assert len(tool_results) == 3


class TestGetMessagesAfterCompactBoundary:
    def test_no_boundary(self) -> None:
        messages = [UserMessage(content="a"), AssistantMessage(content=[TextBlock(text="b")])]
        result = get_messages_after_compact_boundary(messages)
        assert len(result) == 2

    def test_with_boundary(self) -> None:
        messages = [
            UserMessage(content="old"),
            AssistantMessage(content=[TextBlock(text="old response")]),
            CompactBoundaryMessage(summary="summary of old conversation"),
            UserMessage(content="new"),
            AssistantMessage(content=[TextBlock(text="new response")]),
        ]
        result = get_messages_after_compact_boundary(messages)
        assert len(result) == 3  # boundary + new messages
        assert isinstance(result[0], CompactBoundaryMessage)

    def test_multiple_boundaries_uses_last(self) -> None:
        messages = [
            CompactBoundaryMessage(summary="first"),
            UserMessage(content="mid"),
            CompactBoundaryMessage(summary="second"),
            UserMessage(content="latest"),
        ]
        result = get_messages_after_compact_boundary(messages)
        assert len(result) == 2
        assert isinstance(result[0], CompactBoundaryMessage)
        assert result[0].summary == "second"


class TestFactoryFunctions:
    def test_create_user_message(self) -> None:
        msg = create_user_message("hello")
        assert msg.type == "user"
        assert msg.content == "hello"
        assert msg.uuid  # non-empty
        assert msg.timestamp  # non-empty

    def test_create_assistant_message_from_string(self) -> None:
        msg = create_assistant_message("response text")
        assert msg.type == "assistant"
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)
        assert msg.content[0].text == "response text"

    def test_create_assistant_message_from_blocks(self) -> None:
        blocks = [TextBlock(text="a"), ToolUseBlock(id="1", name="bash", input={})]
        msg = create_assistant_message(blocks)
        assert len(msg.content) == 2

    def test_create_tool_result_message(self) -> None:
        msg = create_tool_result_message("tu_1", "output data")
        assert msg.type == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], ToolResultBlock)
        assert msg.content[0].tool_use_id == "tu_1"
        assert msg.content[0].content == "output data"

    def test_create_tool_result_message_error(self) -> None:
        msg = create_tool_result_message("tu_1", "failed", is_error=True)
        assert isinstance(msg.content, list)
        assert msg.content[0].is_error is True
