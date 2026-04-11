import asyncio
from collections.abc import AsyncGenerator
import contextlib
import json
from typing import Literal

type BroadcastEntity = Literal[
    "settlements", "transactions", "uploads", "reconciliation", "budgets"
]


class EventBus:
    """In-memory SSE event bus. One asyncio.Queue per connected client."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[str]] = []

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        with contextlib.suppress(ValueError):
            self._subscribers.remove(queue)

    def _send(self, message: str) -> None:
        for queue in self._subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(message)

    def broadcast(self, entity: BroadcastEntity) -> None:
        self._send(json.dumps({"entity": entity}))

    def broadcast_progress(
        self,
        operation: str,
        current: int,
        total: int,
        detail: str,
    ) -> None:
        self._send(
            json.dumps({
                "type": "progress",
                "operation": operation,
                "current": current,
                "total": total,
                "detail": detail,
            })
        )

    @staticmethod
    async def stream(queue: asyncio.Queue[str]) -> AsyncGenerator[str]:
        try:
            while True:
                yield await queue.get()
        except asyncio.CancelledError:
            return


event_bus = EventBus()
