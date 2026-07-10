"""Content-block serialization must round-trip faithfully for the API.

Thinking blocks carry a `signature` that the API validates when the assistant
turn is echoed back on the next request of a tool loop. Lossy serialization
(e.g. reducing a block to `{"type": ...}`) degrades or 400s multi-turn chats
on models with adaptive thinking.
"""

from collections.abc import AsyncIterator
import copy
from datetime import UTC, datetime
from types import SimpleNamespace

from anthropic._models import construct_type
from anthropic.types import (
    BashCodeExecutionResultBlock,
    BashCodeExecutionToolResultBlock,
    CodeExecutionResultBlock,
    CodeExecutionToolResultBlock,
    CodeExecutionToolResultError,
    Container,
    Message,
    RedactedThinkingBlock,
    ServerToolUseBlock,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
)
from anthropic.types.parsed_message import ParsedContentBlock

from src.application.chat.events import ServerToolResultEvent, ServerToolStartEvent
from src.infrastructure.chat.anthropic_adapter import (
    _AdapterStream,
    _content_block_to_dict,
    _server_tool_result_event,
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


def _code_result_block(
    *, stdout: str = "42\n", stderr: str = "", return_code: int = 0
) -> CodeExecutionToolResultBlock:
    return CodeExecutionToolResultBlock(
        type="code_execution_tool_result",
        tool_use_id="srvtoolu_1",
        content=CodeExecutionResultBlock(
            type="code_execution_result",
            content=[],
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
        ),
    )


class TestServerToolResultMapping:
    """SDK 0.97 block shapes → application events (pinned per v1.8.3).

    The mapper takes the dumped dict because the streaming accumulator
    materializes result blocks as loosely constructed ParsedTextBlock
    instances (the ParsedContentBlock union omits code-execution results);
    dumping real SDK blocks here pins the wire shapes either way.
    """

    def test_code_execution_result_maps_output(self) -> None:
        block = _code_result_block(stdout="42\n", stderr="warn", return_code=0)
        event = _server_tool_result_event(block.model_dump(mode="json"))
        assert event == ServerToolResultEvent(
            tool_use_id="srvtoolu_1", stdout="42\n", stderr="warn", return_code=0
        )

    def test_bash_variant_maps_output(self) -> None:
        block = BashCodeExecutionToolResultBlock(
            type="bash_code_execution_tool_result",
            tool_use_id="srvtoolu_2",
            content=BashCodeExecutionResultBlock(
                type="bash_code_execution_result",
                content=[],
                stdout="ok",
                stderr="",
                return_code=0,
            ),
        )
        event = _server_tool_result_event(block.model_dump(mode="json"))
        assert event.tool_use_id == "srvtoolu_2"
        assert event.stdout == "ok"

    def test_error_variant_maps_to_stderr(self) -> None:
        block = CodeExecutionToolResultBlock(
            type="code_execution_tool_result",
            tool_use_id="srvtoolu_1",
            content=CodeExecutionToolResultError(
                type="code_execution_tool_result_error",
                error_code="unavailable",
            ),
        )
        event = _server_tool_result_event(block.model_dump(mode="json"))
        assert event == ServerToolResultEvent(
            tool_use_id="srvtoolu_1", stdout="", stderr="unavailable", return_code=-1
        )

    def test_output_is_truncated(self) -> None:
        block = _code_result_block(stdout="x" * 5000)
        event = _server_tool_result_event(block.model_dump(mode="json"))
        assert len(event.stdout) < 3000
        assert event.stdout.endswith("[truncated]")


class _StubSDKStream:
    """Duck-typed stand-in for AsyncMessageStream event iteration."""

    def __init__(self, events: list[object], final: Message | None = None) -> None:
        self._events = events
        self._final = final

    def __aiter__(self) -> AsyncIterator[object]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[object]:
        for event in self._events:
            yield event

    async def get_final_message(self) -> Message:
        assert self._final is not None
        return self._final


def _stop_event(block: object) -> SimpleNamespace:
    return SimpleNamespace(type="content_block_stop", content_block=block)


async def _iter_adapter_events(blocks: list[object]) -> list[object]:
    stream = _AdapterStream(_StubSDKStream([_stop_event(b) for b in blocks]))
    return [event async for event in stream]


class TestStreamEventMapping:
    async def test_code_execution_server_tool_use_yields_start_event(self) -> None:
        block = ServerToolUseBlock(
            type="server_tool_use",
            id="srvtoolu_1",
            name="code_execution",
            input={"code": "print(1)"},
        )
        events = await _iter_adapter_events([block])
        assert events == [
            ServerToolStartEvent(
                name="code_execution",
                tool_use_id="srvtoolu_1",
                input={"code": "print(1)"},
            )
        ]

    async def test_tool_search_server_tool_use_is_silent(self) -> None:
        block = ServerToolUseBlock(
            type="server_tool_use",
            id="srvtoolu_3",
            name="tool_search_tool_bm25",
            input={"query": "budget"},
        )
        assert await _iter_adapter_events([block]) == []

    async def test_code_result_block_yields_result_event(self) -> None:
        events = await _iter_adapter_events([_code_result_block()])
        assert events == [
            ServerToolResultEvent(
                tool_use_id="srvtoolu_1", stdout="42\n", stderr="", return_code=0
            )
        ]

    async def test_parsed_fallback_result_block_yields_result_event(self) -> None:
        """Mirror the live streaming path: SDK 0.97 constructs result blocks
        through the ParsedContentBlock union, which lacks code-execution
        result types — they arrive as ParsedTextBlock instances carrying the
        real type string and payload as extra fields (live-verified)."""
        parsed = construct_type(
            type_=ParsedContentBlock,
            value={
                "type": "bash_code_execution_tool_result",
                "tool_use_id": "srvtoolu_9",
                "content": {
                    "type": "bash_code_execution_result",
                    "content": [],
                    "stdout": "396\n",
                    "stderr": "",
                    "return_code": 0,
                },
            },
        )
        events = await _iter_adapter_events([parsed])
        assert events == [
            ServerToolResultEvent(
                tool_use_id="srvtoolu_9", stdout="396\n", stderr="", return_code=0
            )
        ]

    async def test_container_id_captured_from_message_delta(self) -> None:
        """SDK 0.97 drops `container` during stream accumulation (it only
        arrives on message_delta), so the adapter captures it itself —
        without it, returning sandbox-called tool results 400s."""
        delta = SimpleNamespace(
            type="message_delta",
            delta=SimpleNamespace(
                container=Container(id="cont_1", expires_at=datetime.now(UTC))
            ),
        )
        final = Message(
            id="msg_1",
            content=[],
            model="claude-opus-4-8",
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=Usage(input_tokens=0, output_tokens=0),
        )
        stream = _AdapterStream(_StubSDKStream([delta], final=final))
        _ = [event async for event in stream]

        response = await stream.get_final_response()

        assert response.container_id == "cont_1"


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

    def test_sandbox_called_tool_blocks_are_never_stamped(self) -> None:
        """Live-verified 400s: neither a sandbox-called tool_use block nor
        its tool_result may carry cache_control ("not rendered in Claude's
        context"). The stamp walks back to the nearest stampable block."""
        result = _with_incremental_cache([
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "computing"},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "search_transactions",
                        "input": {},
                        "caller": {
                            "type": "code_execution_20260120",
                            "tool_id": "srvtoolu_1",
                        },
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "{}",
                    }
                ],
            },
        ])
        assert all("cache_control" not in block for block in result[1]["content"])
        text_block, tool_use_block = result[0]["content"]
        assert "cache_control" not in tool_use_block
        assert text_block["cache_control"] == _EPHEMERAL

    def test_direct_tool_result_still_stamped(self) -> None:
        result = _with_incremental_cache([
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "get_tags",
                        "input": {},
                        "caller": {"type": "direct"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "{}",
                    }
                ],
            },
        ])
        assert result[1]["content"][0]["cache_control"] == _EPHEMERAL

    def test_thinking_block_is_never_stamped(self) -> None:
        result = _with_incremental_cache([
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "answer"},
                    {"type": "thinking", "thinking": "…", "signature": "sig"},
                ],
            },
        ])
        text_block, thinking_block = result[0]["content"]
        assert "cache_control" not in thinking_block
        assert text_block["cache_control"] == _EPHEMERAL
