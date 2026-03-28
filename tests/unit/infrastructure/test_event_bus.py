import asyncio

import pytest

from src.infrastructure.events.event_bus import EventBus


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def test_subscribe_and_broadcast(bus: EventBus) -> None:
    queue = bus.subscribe()
    bus.broadcast("settlements")

    assert queue.get_nowait() == "settlements"


def test_broadcast_delivers_to_all_subscribers(bus: EventBus) -> None:
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.broadcast("transactions")

    for q in (q1, q2):
        assert q.get_nowait() == "transactions"


def test_unsubscribe_stops_delivery(bus: EventBus) -> None:
    queue = bus.subscribe()
    bus.unsubscribe(queue)
    bus.broadcast("uploads")

    assert queue.empty()


def test_unsubscribe_unknown_queue_is_safe(bus: EventBus) -> None:
    unknown: asyncio.Queue[str] = asyncio.Queue()
    bus.unsubscribe(unknown)  # should not raise


def test_broadcast_drops_message_on_full_queue(bus: EventBus) -> None:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    bus._subscribers.append(queue)
    queue.put_nowait("filler")

    bus.broadcast("settlements")  # should not raise
    assert queue.qsize() == 1  # only the filler, broadcast was dropped


async def test_stream_yields_entity_names(bus: EventBus) -> None:
    queue = bus.subscribe()
    bus.broadcast("reconciliation")

    entities: list[str] = []
    async for entity in bus.stream(queue):
        entities.append(entity)
        break  # only read one

    assert entities == ["reconciliation"]


def test_no_subscribers_broadcast_is_noop(bus: EventBus) -> None:
    bus.broadcast("settlements")  # should not raise
