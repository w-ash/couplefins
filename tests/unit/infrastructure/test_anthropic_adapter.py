"""Content-block serialization must round-trip faithfully for the API.

Thinking blocks carry a `signature` that the API validates when the assistant
turn is echoed back on the next request of a tool loop. Lossy serialization
(e.g. reducing a block to `{"type": ...}`) degrades or 400s multi-turn chats
on models with adaptive thinking.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
)
from anthropic.types.beta import BetaServerToolUseBlock
from anthropic.types.parsed_message import ParsedContentBlock

from src.application.chat.events import ServerToolResultEvent, ServerToolStartEvent
from src.application.chat.protocols import LLMRequest
from src.infrastructure.chat.anthropic_adapter import (
    AnthropicAdapter,
    _AdapterStream,
    _content_block_to_dict,
    _server_tool_result_event,
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
        # Beta twin — the adapter streams via client.beta.messages, so beta
        # block classes are what actually arrive.
        block = BetaServerToolUseBlock(
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
        block = BetaServerToolUseBlock(
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


class TestBetaSurfaceParams:
    async def test_context_management_and_beta_header_sent(self) -> None:
        captured: dict[str, object] = {}

        @asynccontextmanager
        async def fake_stream(**kwargs: object) -> AsyncIterator[_StubSDKStream]:
            await asyncio.sleep(0)
            captured.update(kwargs)
            yield _StubSDKStream([])

        client = SimpleNamespace(
            beta=SimpleNamespace(messages=SimpleNamespace(stream=fake_stream))
        )
        adapter = AnthropicAdapter(client)
        request = LLMRequest(
            model="claude-opus-4-8",
            max_tokens=1024,
            effort="high",
            system=[],
            tools=[],
            messages=[{"role": "user", "content": "hi"}],
            container="cont_9",
        )

        async with adapter.stream(request):
            pass

        assert captured["betas"] == ["context-management-2025-06-27"]
        context_management = captured["context_management"]
        assert isinstance(context_management, dict)
        (edit,) = context_management["edits"]
        assert edit["type"] == "clear_tool_uses_20250919"
        assert edit["keep"] == {"type": "tool_uses", "value": 3}
        assert captured["container"] == "cont_9"
        assert captured["output_config"] == {"effort": "high"}
        assert captured["thinking"] == {"type": "adaptive"}
        # Automatic caching: the server places the incremental breakpoint and
        # skips blocks it rejects a stamp on, so messages go through untouched.
        assert captured["cache_control"] == {"type": "ephemeral"}
        assert captured["messages"] == [{"role": "user", "content": "hi"}]
