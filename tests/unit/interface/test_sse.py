"""SSE keepalive behavior and frame serialization of the chat stream bridge."""

import asyncio
from collections.abc import Awaitable, Callable
import json

import pytest

from src.application.chat.events import (
    ServerToolResultEvent,
    ServerToolStartEvent,
    ToolStartEvent,
)
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


async def test_server_tool_events_serialize_as_code_frames() -> None:
    async def run_fn(queue: asyncio.Queue[QueueItem]) -> None:
        await asyncio.sleep(0)
        queue.put_nowait(
            ServerToolStartEvent(
                name="code_execution",
                tool_use_id="srvtoolu_1",
                input={"code": "print(1)"},
            )
        )
        queue.put_nowait(
            ServerToolResultEvent(
                tool_use_id="srvtoolu_1", stdout="1\n", stderr="", return_code=0
            )
        )

    chunks = await _collect_chunks(run_fn)

    frames = [
        json.loads(chunk.removeprefix("data: "))
        for chunk in chunks
        if chunk.startswith("data: ")
    ]
    assert frames[0] == {
        "type": "code_start",
        "id": "srvtoolu_1",
        "command": "print(1)",
    }
    assert frames[1] == {
        "type": "code_result",
        "id": "srvtoolu_1",
        "stdout": "1\n",
        "stderr": "",
        "return_code": 0,
    }
    assert frames[-1] == {"type": "done"}


async def test_bash_server_tool_start_reads_command_key() -> None:
    """Bash server-tool blocks carry the script under "command", not "code"."""

    async def run_fn(queue: asyncio.Queue[QueueItem]) -> None:
        await asyncio.sleep(0)
        queue.put_nowait(
            ServerToolStartEvent(
                name="bash_code_execution",
                tool_use_id="srvtoolu_2",
                input={"command": "ls -la"},
            )
        )

    chunks = await _collect_chunks(run_fn)

    frames = [
        json.loads(chunk.removeprefix("data: "))
        for chunk in chunks
        if chunk.startswith("data: ")
    ]
    assert frames[0] == {
        "type": "code_start",
        "id": "srvtoolu_2",
        "command": "ls -la",
    }


async def test_tool_start_frames_carry_registry_kind() -> None:
    """The frontend styles read vs write indicators from the kind field."""

    async def run_fn(queue: asyncio.Queue[QueueItem]) -> None:
        await asyncio.sleep(0)
        queue.put_nowait(
            ToolStartEvent(name="get_settlement_balance", tool_use_id="toolu_1")
        )
        queue.put_nowait(
            ToolStartEvent(name="record_settlement", tool_use_id="toolu_2")
        )

    chunks = await _collect_chunks(run_fn)

    frames = [
        json.loads(chunk.removeprefix("data: "))
        for chunk in chunks
        if chunk.startswith("data: ")
    ]
    assert frames[0] == {
        "type": "tool_start",
        "name": "get_settlement_balance",
        "id": "toolu_1",
        "kind": "read",
    }
    assert frames[1] == {
        "type": "tool_start",
        "name": "record_settlement",
        "id": "toolu_2",
        "kind": "write",
    }
