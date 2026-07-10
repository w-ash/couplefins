"""SSE keepalive behavior of the chat stream bridge."""

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from src.interface.api import sse
from src.interface.api.sse import QueueItem, stream_chat_response


async def _collect_chunks(
    run_fn: Callable[[asyncio.Queue[QueueItem]], Awaitable[None]],
) -> list[str]:
    response = stream_chat_response(run_fn)
    return [str(chunk) async for chunk in response.body_iterator]


async def test_keepalive_emitted_while_queue_is_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sse, "_KEEPALIVE_INTERVAL_SECONDS", 0.01)

    async def run_fn(queue: asyncio.Queue[QueueItem]) -> None:
        await asyncio.sleep(0.05)
        queue.put_nowait("hello")

    chunks = await _collect_chunks(run_fn)

    keepalive_index = chunks.index(": keepalive\n\n")
    token_index = next(i for i, c in enumerate(chunks) if '"token"' in c)
    assert keepalive_index < token_index
    assert '{"type": "done"}' in chunks[-1]


async def test_no_keepalive_when_stream_is_busy() -> None:
    async def run_fn(queue: asyncio.Queue[QueueItem]) -> None:
        await asyncio.sleep(0)
        queue.put_nowait("hello")

    chunks = await _collect_chunks(run_fn)

    assert all(not chunk.startswith(":") for chunk in chunks)
    assert '{"type": "done"}' in chunks[-1]
