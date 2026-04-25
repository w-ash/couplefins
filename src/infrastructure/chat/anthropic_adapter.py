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


def _to_message_params(messages: list[dict[str, object]]) -> list[MessageParam]:
    return cast(list[MessageParam], messages)


def _to_tool_params(tools: list[dict[str, object]]) -> list[ToolParam]:
    return cast(list[ToolParam], tools)


def _to_system_params(system: list[dict[str, object]]) -> list[TextBlockParam]:
    return cast(list[TextBlockParam], system)


def _content_block_to_dict(block: ContentBlock) -> dict[str, object]:
    """Serialize an Anthropic ContentBlock to a plain dict for round-tripping."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {"type": block.type}


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
        system: list[dict[str, object]],
        tools: list[dict[str, object]],
        messages: list[dict[str, object]],
    ) -> AsyncGenerator[_AdapterStream]:
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=_to_system_params(system),
            tools=_to_tool_params(tools),
            messages=_to_message_params(messages),
            extra_body={"output_config": {"effort": "medium"}},
        ) as sdk_stream:
            yield _AdapterStream(sdk_stream)
