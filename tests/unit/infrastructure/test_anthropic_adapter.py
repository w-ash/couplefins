"""Content-block serialization must round-trip faithfully for the API.

Thinking blocks carry a `signature` that the API validates when the assistant
turn is echoed back on the next request of a tool loop. Lossy serialization
(e.g. reducing a block to `{"type": ...}`) degrades or 400s multi-turn chats
on models with adaptive thinking.
"""

import copy

from anthropic.types import (
    RedactedThinkingBlock,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)

from src.infrastructure.chat.anthropic_adapter import (
    _content_block_to_dict,
    _with_incremental_cache,
)


class TestContentBlockRoundTrip:
    def test_text_block(self) -> None:
        block = TextBlock(type="text", text="hello")
        assert _content_block_to_dict(block) == {"type": "text", "text": "hello"}

    def test_tool_use_block(self) -> None:
        block = ToolUseBlock(
            type="tool_use", id="tu_1", name="get_tags", input={"year": 2026}
        )
        assert _content_block_to_dict(block) == {
            "type": "tool_use",
            "id": "tu_1",
            "name": "get_tags",
            "input": {"year": 2026},
        }

    def test_thinking_block_preserves_signature(self) -> None:
        block = ThinkingBlock(
            type="thinking", thinking="let me reason...", signature="sig_abc123"
        )
        assert _content_block_to_dict(block) == {
            "type": "thinking",
            "thinking": "let me reason...",
            "signature": "sig_abc123",
        }

    def test_redacted_thinking_block_preserves_data(self) -> None:
        block = RedactedThinkingBlock(type="redacted_thinking", data="opaque")
        assert _content_block_to_dict(block) == {
            "type": "redacted_thinking",
            "data": "opaque",
        }


_EPHEMERAL = {"type": "ephemeral"}


class TestIncrementalCache:
    """One breakpoint on the last block of the last message, on copies only."""

    def test_string_content_wrapped_and_stamped(self) -> None:
        result = _with_incremental_cache([{"role": "user", "content": "hi"}])
        assert result == [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hi", "cache_control": _EPHEMERAL}
                ],
            }
        ]

    def test_only_last_block_of_last_message_stamped(self) -> None:
        result = _with_incremental_cache([
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "tool_use", "id": "tu_1", "name": "t", "input": {}},
                ],
            },
        ])
        assert result[0]["content"] == "hi"
        first_block, last_block = result[1]["content"]
        assert "cache_control" not in first_block
        assert last_block["cache_control"] == _EPHEMERAL

    def test_prior_stamps_are_stripped(self) -> None:
        stale = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "old", "cache_control": _EPHEMERAL}
                ],
            },
            {"role": "user", "content": [{"type": "text", "text": "new"}]},
        ]
        result = _with_incremental_cache(stale)
        assert "cache_control" not in result[0]["content"][0]
        assert result[1]["content"][0]["cache_control"] == _EPHEMERAL

    def test_caller_messages_are_not_mutated(self) -> None:
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [{"type": "text", "text": "a"}]},
        ]
        snapshot = copy.deepcopy(messages)
        _with_incremental_cache(messages)
        assert messages == snapshot

    def test_idempotent(self) -> None:
        once = _with_incremental_cache([
            {"role": "user", "content": [{"type": "text", "text": "hi"}]}
        ])
        twice = _with_incremental_cache(once)
        assert twice == once
        stamps = [
            block
            for message in twice
            for block in message["content"]
            if "cache_control" in block
        ]
        assert len(stamps) == 1

    def test_empty_messages_pass_through(self) -> None:
        assert _with_incremental_cache([]) == []
