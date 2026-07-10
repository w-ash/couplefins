"""Anthropic SDK adapter — implements LLMClientProtocol."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from anthropic import AsyncAnthropic
from anthropic.lib.streaming import AsyncMessageStream
from anthropic.types import (
    MessageParam,
    ServerToolUseBlock,
    TextBlockParam,
    ToolParam,
    ToolUseBlock as SDKToolUseBlock,
)
from pydantic import BaseModel

from src.application.chat.events import (
    ServerToolResultEvent,
    ServerToolStartEvent,
    TextDelta,
)
from src.application.chat.protocols import (
    LLMRequest,
    LLMResponse,
    LLMStreamEvent,
    ToolUseBlock,
)


def _to_message_params(messages: list[dict[str, object]]) -> list[MessageParam]:
    return cast(list[MessageParam], messages)


def _strip_cache_control(content: object) -> object:
    if not isinstance(content, list):
        return content
    stripped: list[object] = []
    for block in cast(list[object], content):
        if isinstance(block, dict):
            block_dict = cast(dict[str, object], block)
            stripped.append({
                k: v for k, v in block_dict.items() if k != "cache_control"
            })
        else:
            stripped.append(block)
    return stripped


# Block types that accept a cache_control stamp. Thinking and server-tool
# blocks reject it, and so do sandbox-called tool_use blocks and their
# tool_results (neither is rendered in model context) — live-verified 400s.
_STAMPABLE_BLOCK_TYPES = frozenset({"text", "tool_use", "tool_result"})


def _code_called_tool_ids(messages: list[dict[str, object]]) -> set[object]:
    """IDs of tool_use blocks invoked by the sandbox, not the model.

    Round-tripped assistant turns carry the API's `caller` field on each
    tool_use block; anything not explicitly direct came from code execution.
    """
    ids: set[object] = set()
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in cast(list[object], content):
            if not isinstance(block, dict):
                continue
            block_dict = cast(dict[str, object], block)
            if block_dict.get("type") != "tool_use":
                continue
            caller = block_dict.get("caller")
            if not isinstance(caller, dict):
                continue
            caller_dict = cast(dict[str, object], caller)
            if caller_dict.get("type") != "direct":
                ids.add(block_dict.get("id"))
    return ids


def _is_stampable(block_dict: dict[str, object], code_called: set[object]) -> bool:
    block_type = block_dict.get("type")
    if block_type not in _STAMPABLE_BLOCK_TYPES:
        return False
    if block_type == "tool_use":
        return block_dict.get("id") not in code_called
    if block_type == "tool_result":
        return block_dict.get("tool_use_id") not in code_called
    return True


def _with_incremental_cache(
    messages: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Copy messages with one cache breakpoint on the last stampable block.

    The tool loop re-sends the whole growing history every turn; stamping
    near the end turns all prior turns into cache reads (tools + system
    carry the other two breakpoints — 3 of the 4 allowed). The stamp walks
    backwards past blocks the API rejects cache_control on (thinking,
    server-tool blocks, tool_results for sandbox-called tools). Works on
    copies only: the use case reuses one list (and re-echoes raw_content on
    pause_turn), so stamps must never leak into or accumulate on the
    caller's dicts. Stripping stale stamps first makes this idempotent. The
    20-block cache lookback is safe here — each turn appends at most 2
    messages.
    """
    if not messages:
        return messages
    result = [
        {**message, "content": _strip_cache_control(message.get("content"))}
        for message in messages
    ]
    code_called = _code_called_tool_ids(result)
    for message in reversed(result):
        content = message["content"]
        if isinstance(content, str):
            message["content"] = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            return result
        if not isinstance(content, list):
            continue
        blocks = list(cast(list[object], content))
        for i in range(len(blocks) - 1, -1, -1):
            block = blocks[i]
            if not isinstance(block, dict):
                continue
            block_dict = cast(dict[str, object], block)
            if not _is_stampable(block_dict, code_called):
                continue
            blocks[i] = {**block_dict, "cache_control": {"type": "ephemeral"}}
            message["content"] = blocks
            return result
    return result


def _to_tool_params(tools: list[dict[str, object]]) -> list[ToolParam]:
    return cast(list[ToolParam], tools)


def _to_system_params(system: list[dict[str, object]]) -> list[TextBlockParam]:
    return cast(list[TextBlockParam], system)


def _content_block_to_dict(block: BaseModel) -> dict[str, object]:
    """Serialize an Anthropic content block to a plain dict for round-tripping.

    Must preserve every block type byte-faithfully: thinking blocks carry a
    `signature` the API validates when the turn is echoed back, and server-tool
    blocks must survive pause_turn continuations. Lossy serialization here
    degrades or 400s multi-turn tool loops. Typed as pydantic BaseModel (not
    the ContentBlock union) because the streaming path yields loosely
    constructed ParsedContentBlock instances whose extra fields still dump
    faithfully.
    """
    return cast(dict[str, object], block.model_dump(mode="json", exclude_none=True))


# Server tools whose lifecycle the UI shows as a code card. Tool-search
# blocks are deliberately absent — discovery is fast and rendering it as
# code execution would only confuse the transcript.
_CODE_SERVER_TOOL_NAMES = frozenset({"code_execution", "bash_code_execution"})

# Sandbox output can be arbitrarily large; the UI only needs a preview and
# the full text still reaches the model server-side.
_OUTPUT_LIMIT_CHARS = 2048


def _truncate_output(text: str) -> str:
    if len(text) <= _OUTPUT_LIMIT_CHARS:
        return text
    return f"{text[:_OUTPUT_LIMIT_CHARS]}\n[truncated]"


# Result-block detection is by type string, not isinstance: SDK 0.97's
# streaming accumulator builds content blocks from the ParsedContentBlock
# union, which omits code-execution result types — those arrive as loosely
# constructed ParsedTextBlock instances whose `type` and payload fields are
# still correct (live-verified; model_dump round-trips them faithfully).
_CODE_RESULT_BLOCK_TYPES = frozenset({
    "code_execution_tool_result",
    "bash_code_execution_tool_result",
})


def _server_tool_result_event(block_dict: dict[str, object]) -> ServerToolResultEvent:
    tool_use_id = str(block_dict.get("tool_use_id", ""))
    content = block_dict.get("content")
    if isinstance(content, dict):
        content_dict = cast(dict[str, object], content)
        if "stdout" in content_dict:
            return_code = content_dict.get("return_code")
            return ServerToolResultEvent(
                tool_use_id=tool_use_id,
                stdout=_truncate_output(str(content_dict.get("stdout", ""))),
                stderr=_truncate_output(str(content_dict.get("stderr", ""))),
                return_code=return_code if isinstance(return_code, int) else 0,
            )
        if "error_code" in content_dict:
            return ServerToolResultEvent(
                tool_use_id=tool_use_id,
                stdout="",
                stderr=str(content_dict["error_code"]),
                return_code=-1,
            )
    # Encrypted results (PFC privacy mode) carry no readable output.
    return ServerToolResultEvent(
        tool_use_id=tool_use_id, stdout="", stderr="", return_code=0
    )


class _AdapterStream:
    """Wraps Anthropic's async message stream to implement LLMStream."""

    def __init__(self, stream: AsyncMessageStream[None]) -> None:
        self._stream = stream
        self._container_id: str | None = None

    def __aiter__(self) -> AsyncIterator[LLMStreamEvent]:
        return self._iter_events()

    async def _iter_events(self) -> AsyncIterator[LLMStreamEvent]:
        async for event in self._stream:
            if event.type == "text":
                yield TextDelta(text=event.text)
            elif event.type == "message_delta":
                # SDK 0.97 gap: container arrives on message_delta.delta but
                # the stream accumulator never copies it onto the final
                # Message, so it must be captured here (live-verified).
                if event.delta.container is not None:
                    self._container_id = event.delta.container.id
            elif event.type == "content_block_stop":
                block = event.content_block
                if isinstance(block, SDKToolUseBlock):
                    yield ToolUseBlock(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    )
                elif (
                    isinstance(block, ServerToolUseBlock)
                    and block.name in _CODE_SERVER_TOOL_NAMES
                ):
                    yield ServerToolStartEvent(
                        name=block.name,
                        tool_use_id=block.id,
                        input=block.input,
                    )
                elif block.type in _CODE_RESULT_BLOCK_TYPES:
                    yield _server_tool_result_event(_content_block_to_dict(block))

    async def get_final_response(self) -> LLMResponse:
        final = await self._stream.get_final_message()
        tool_blocks = [
            ToolUseBlock(
                id=b.id,
                name=b.name,
                input=b.input,
                caller=b.caller.type if b.caller else "direct",
            )
            for b in final.content
            if isinstance(b, SDKToolUseBlock)
        ]
        raw_content = [_content_block_to_dict(b) for b in final.content]
        container = final.container.id if final.container else self._container_id
        return LLMResponse(
            stop_reason=final.stop_reason or "end_turn",
            content=tool_blocks,
            raw_content=raw_content,
            container_id=container,
        )


class AnthropicAdapter:
    """Adapts AsyncAnthropic to LLMClientProtocol."""

    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    @asynccontextmanager
    async def stream(self, request: LLMRequest) -> AsyncGenerator[_AdapterStream]:
        # Adaptive thinking must be explicit — Opus 4.8 runs without thinking
        # when the parameter is omitted.
        async with self._client.messages.stream(
            model=request.model,
            max_tokens=request.max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": request.effort},
            system=_to_system_params(request.system),
            tools=_to_tool_params(request.tools),
            messages=_to_message_params(_with_incremental_cache(request.messages)),
            container=request.container,
        ) as sdk_stream:
            yield _AdapterStream(sdk_stream)
