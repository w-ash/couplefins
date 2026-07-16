"""Queue-bridge SSE streaming for the chat endpoint.

Ported from Mimir's sse.py — adapted for tool-use events.

Pattern: a background task puts items into an asyncio.Queue (text deltas,
tool events, or None sentinel), and an async generator reads items and
yields SSE-formatted lines.
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
import json

from fastapi.responses import StreamingResponse
from structlog.stdlib import get_logger

from src.application.chat.events import (
    ServerToolResultEvent,
    ServerToolStartEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from src.application.chat.registry import REGISTRY
from src.domain.exceptions import (
    ActionExpiredError,
    AnthropicApiError,
    ChatUnavailableError,
    MaxRoundsExceededError,
    RateLimitExceededError,
    ResponseTruncatedError,
    ToolExecutionError,
)

logger = get_logger()


type QueueItem = (
    str
    | ToolStartEvent
    | ToolResultEvent
    | ServerToolStartEvent
    | ServerToolResultEvent
    | None
)

# Adaptive thinking can run 30-90s with no stream events; without periodic
# bytes the connection looks dead to the browser and any proxy in between.
# SSE comment lines (leading ":") are ignored by parsers.
_KEEPALIVE_INTERVAL_SECONDS = 15.0


# Tool kind rides on the tool_start frame so the frontend never has to
# guess read-vs-write from tool names.
_TOOL_KINDS: dict[str, str] = {spec.name: spec.kind for spec in REGISTRY}


_ERROR_CODE_MAP: dict[type[Exception], str] = {
    ActionExpiredError: "ACTION_EXPIRED",
    RateLimitExceededError: "RATE_LIMIT_EXCEEDED",
    ChatUnavailableError: "CHAT_UNAVAILABLE",
    ToolExecutionError: "TOOL_EXECUTION_ERROR",
    MaxRoundsExceededError: "MAX_ROUNDS_EXCEEDED",
    ResponseTruncatedError: "RESPONSE_TRUNCATED",
    AnthropicApiError: "ANTHROPIC_API_ERROR",
}


def _map_error_code(exc: BaseException) -> str:
    for exc_type, code in _ERROR_CODE_MAP.items():
        if isinstance(exc, exc_type):
            return code
    return "INTERNAL_ERROR"


def _sse_line(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def stream_chat_response(
    run_fn: Callable[[asyncio.Queue[QueueItem]], Awaitable[None]],
) -> StreamingResponse:
    """Build an SSE StreamingResponse for a chat operation.

    ``run_fn`` receives a queue and puts text deltas (str), tool events,
    or None (completion sentinel) into it.  None is always put — on both
    success and error paths — so the generator always terminates.
    """
    queue: asyncio.Queue[QueueItem] = asyncio.Queue()

    async def _run_with_sentinel() -> None:
        try:
            await run_fn(queue)
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(_run_with_sentinel())

    async def event_generator() -> AsyncGenerator[str]:
        try:
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(), timeout=_KEEPALIVE_INTERVAL_SECONDS
                    )
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    exc = task.exception() if task.done() else None
                    if exc is not None:
                        logger.error("chat_stream_error", error=str(exc))
                        yield _sse_line({
                            "type": "error",
                            "code": _map_error_code(exc),
                            "message": str(exc),
                        })
                    else:
                        yield _sse_line({"type": "done"})
                    return
                if isinstance(item, ToolStartEvent):
                    yield _sse_line({
                        "type": "tool_start",
                        "name": item.name,
                        "id": item.tool_use_id,
                        "kind": _TOOL_KINDS.get(item.name, "read"),
                    })
                elif isinstance(item, ToolResultEvent):
                    yield _sse_line({
                        "type": "tool_result",
                        "name": item.name,
                        "id": item.tool_use_id,
                        "summary": item.summary,
                        "is_error": item.is_error,
                    })
                elif isinstance(item, ServerToolStartEvent):
                    yield _sse_line({
                        "type": "code_start",
                        "id": item.tool_use_id,
                        "command": str(
                            item.input.get("code") or item.input.get("command") or ""
                        ),
                    })
                elif isinstance(item, ServerToolResultEvent):
                    yield _sse_line({
                        "type": "code_result",
                        "id": item.tool_use_id,
                        "stdout": item.stdout,
                        "stderr": item.stderr,
                        "return_code": item.return_code,
                    })
                else:
                    yield _sse_line({"type": "token", "text": item})
        except asyncio.CancelledError:
            task.cancel()
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
