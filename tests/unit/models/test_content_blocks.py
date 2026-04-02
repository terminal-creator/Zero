"""Tests for content block models.

Verifies T1.1: ContentBlock types round-trip through API dict format.
"""

import pytest

from cc.models.content_blocks import (
    ImageBlock,
    ImageSource,
    RedactedThinkingBlock,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolResultContent,
    ToolUseBlock,
    content_block_from_api_dict,
)


class TestTextBlock:
    def test_roundtrip(self) -> None:
        block = TextBlock(text="hello world")
        api = block.to_api_dict()
        restored = TextBlock.from_api_dict(api)
        assert restored.text == "hello world"
        assert restored.type == "text"

    def test_empty_text(self) -> None:
        block = TextBlock(text="")
        api = block.to_api_dict()
        assert api == {"type": "text", "text": ""}
        restored = TextBlock.from_api_dict(api)
        assert restored.text == ""

    def test_unicode_text(self) -> None:
        block = TextBlock(text="你好世界 🌍")
        api = block.to_api_dict()
        restored = TextBlock.from_api_dict(api)
        assert restored.text == "你好世界 🌍"


class TestToolUseBlock:
    def test_roundtrip(self) -> None:
        block = ToolUseBlock(id="tu_123", name="bash", input={"command": "ls -la"})
        api = block.to_api_dict()
        restored = ToolUseBlock.from_api_dict(api)
        assert restored.id == "tu_123"
        assert restored.name == "bash"
        assert restored.input == {"command": "ls -la"}

    def test_complex_input(self) -> None:
        block = ToolUseBlock(
            id="tu_456",
            name="file_edit",
            input={"file_path": "/tmp/test.py", "old_string": 'print("hello")', "new_string": 'print("world")'},
        )
        api = block.to_api_dict()
        restored = ToolUseBlock.from_api_dict(api)
        assert restored.input["old_string"] == 'print("hello")'


class TestToolResultBlock:
    def test_string_content_roundtrip(self) -> None:
        block = ToolResultBlock(tool_use_id="tu_123", content="file1.py\nfile2.py")
        api = block.to_api_dict()
        restored = ToolResultBlock.from_api_dict(api)
        assert restored.content == "file1.py\nfile2.py"
        assert restored.is_error is False

    def test_error_result(self) -> None:
        block = ToolResultBlock(tool_use_id="tu_123", content="Command failed", is_error=True)
        api = block.to_api_dict()
        assert api["is_error"] is True
        restored = ToolResultBlock.from_api_dict(api)
        assert restored.is_error is True

    def test_non_error_omits_is_error(self) -> None:
        block = ToolResultBlock(tool_use_id="tu_123", content="ok")
        api = block.to_api_dict()
        assert "is_error" not in api or api["is_error"] is False

    def test_list_content_with_image(self) -> None:
        block = ToolResultBlock(
            tool_use_id="tu_123",
            content=[
                ToolResultContent(type="text", text="Here is the image:"),
                ToolResultContent(type="image", source={"type": "base64", "media_type": "image/png", "data": "abc123"}),
            ],
        )
        api = block.to_api_dict()
        assert len(api["content"]) == 2
        assert api["content"][0]["type"] == "text"
        assert api["content"][1]["type"] == "image"

        restored = ToolResultBlock.from_api_dict(api)
        assert isinstance(restored.content, list)
        assert len(restored.content) == 2
        assert restored.content[0].type == "text"
        assert restored.content[1].type == "image"


class TestThinkingBlock:
    def test_roundtrip(self) -> None:
        block = ThinkingBlock(thinking="Let me think about this...", signature="sig123")
        api = block.to_api_dict()
        restored = ThinkingBlock.from_api_dict(api)
        assert restored.thinking == "Let me think about this..."
        assert restored.signature == "sig123"


class TestRedactedThinkingBlock:
    def test_roundtrip(self) -> None:
        block = RedactedThinkingBlock(data="redacted_data")
        api = block.to_api_dict()
        restored = RedactedThinkingBlock.from_api_dict(api)
        assert restored.data == "redacted_data"


class TestImageBlock:
    def test_roundtrip(self) -> None:
        block = ImageBlock(source=ImageSource(type="base64", media_type="image/png", data="iVBOR..."))
        api = block.to_api_dict()
        restored = ImageBlock.from_api_dict(api)
        assert restored.source.media_type == "image/png"
        assert restored.source.data == "iVBOR..."


class TestContentBlockFromApiDict:
    def test_text(self) -> None:
        block = content_block_from_api_dict({"type": "text", "text": "hello"})
        assert isinstance(block, TextBlock)

    def test_tool_use(self) -> None:
        block = content_block_from_api_dict({"type": "tool_use", "id": "1", "name": "bash", "input": {}})
        assert isinstance(block, ToolUseBlock)

    def test_tool_result(self) -> None:
        block = content_block_from_api_dict({"type": "tool_result", "tool_use_id": "1", "content": "ok"})
        assert isinstance(block, ToolResultBlock)

    def test_thinking(self) -> None:
        block = content_block_from_api_dict({"type": "thinking", "thinking": "hmm"})
        assert isinstance(block, ThinkingBlock)

    def test_redacted_thinking(self) -> None:
        block = content_block_from_api_dict({"type": "redacted_thinking"})
        assert isinstance(block, RedactedThinkingBlock)

    def test_image(self) -> None:
        block = content_block_from_api_dict({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": "abc"},
        })
        assert isinstance(block, ImageBlock)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown content block type"):
            content_block_from_api_dict({"type": "unknown_block"})
