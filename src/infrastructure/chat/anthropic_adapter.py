"""Anthropic SDK adapter — implements LLMClientProtocol."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from anthropic import AsyncAnthropic
from anthropic.lib.streaming import AsyncMessageStream
from anthropic.types import (
    ContentBlock,
    MessageParam,
    TextBlockParam,
    ToolParam,
    ToolUseBlock as SDKToolUseBlock,
)

from src.application.chat.events import TextDelta
from src.application.chat.protocols import LLMResponse, ToolUseBlock
from src.config.settings import EffortLevel


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


def _with_incremental_cache(
    messages: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Copy messages with one cache breakpoint on the final content block.

    The tool loop re-sends the whole growing history every turn; stamping the
    last block turns all prior turns into cache reads (tools + system carry
    the other two breakpoints — 3 of the 4 allowed). Works on copies only:
    the use case reuses one list (and re-echoes raw_content on pause_turn),
    so stamps must never leak into or accumulate on the caller's dicts.
    Stripping stale stamps first makes this idempotent. The 20-block cache
    lookback is safe here — each turn appends at most 2 messages.
    """
    if not messages:
        return messages
    result = [
        {**message, "content": _strip_cache_control(message.get("content"))}
        for message in messages
    ]
    last_content = result[-1]["content"]
    if isinstance(last_content, str):
        result[-1]["content"] = [
            {
                "type": "text",
                "text": last_content,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    elif isinstance(last_content, list) and last_content:
        blocks = list(cast(list[object], last_content))
        last_block = blocks[-1]
        if isinstance(last_block, dict):
            blocks[-1] = {**last_block, "cache_control": {"type": "ephemeral"}}
        result[-1]["content"] = blocks
    return result


def _to_tool_params(tools: list[dict[str, object]]) -> list[ToolParam]:
    return cast(list[ToolParam], tools)


def _to_system_params(system: list[dict[str, object]]) -> list[TextBlockParam]:
    return cast(list[TextBlockParam], system)


def _content_block_to_dict(block: ContentBlock) -> dict[str, object]:
    """Serialize an Anthropic ContentBlock to a plain dict for round-tripping.

    Must preserve every block type byte-faithfully: thinking blocks carry a
    `signature` the API validates when the turn is echoed back, and server-tool
    blocks must survive pause_turn continuations. Lossy serialization here
    degrades or 400s multi-turn tool loops.
    """
    return cast(dict[str, object], block.model_dump(mode="json", exclude_none=True))


class _AdapterStream:
    """Wraps Anthropic's async message stream to implement LLMStream."""

    def __init__(self, stream: AsyncMessageStream[None]) -> None:
        self._stream = stream

    def __aiter__(self) -> AsyncIterator[TextDelta | ToolUseBlock]:
        return self._iter_events()

    async def _iter_events(self) -> AsyncIterator[TextDelta | ToolUseBlock]:
        async for event in self._stream:
            if event.type == "text":
                yield TextDelta(text=event.text)
            elif event.type == "content_block_stop":
                block = event.content_block
                if isinstance(block, SDKToolUseBlock):
                    yield ToolUseBlock(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    )

    async def get_final_response(self) -> LLMResponse:
        final = await self._stream.get_final_message()
        tool_blocks = [
            ToolUseBlock(id=b.id, name=b.name, input=b.input)
            for b in final.content
            if isinstance(b, SDKToolUseBlock)
        ]
        raw_content = [_content_block_to_dict(b) for b in final.content]
        return LLMResponse(
            stop_reason=final.stop_reason or "end_turn",
            content=tool_blocks,
            raw_content=raw_content,
        )


class AnthropicAdapter:
    """Adapts AsyncAnthropic to LLMClientProtocol."""

    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    @asynccontextmanager
    async def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        effort: EffortLevel,
        system: list[dict[str, object]],
        tools: list[dict[str, object]],
        messages: list[dict[str, object]],
    ) -> AsyncGenerator[_AdapterStream]:
        # Adaptive thinking must be explicit — Opus 4.8 runs without thinking
        # when the parameter is omitted.
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            system=_to_system_params(system),
            tools=_to_tool_params(tools),
            messages=_to_message_params(_with_incremental_cache(messages)),
        ) as sdk_stream:
            yield _AdapterStream(sdk_stream)
