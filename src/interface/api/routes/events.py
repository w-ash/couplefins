from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent

from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user

router = APIRouter(tags=["events"], dependencies=[Depends(get_current_user)])


@router.get("/events", response_class=EventSourceResponse)
async def sse_events() -> AsyncIterable[ServerSentEvent]:
    queue = event_bus.subscribe()
    try:
        async for message in event_bus.stream(queue):
            yield ServerSentEvent(data=message)
    finally:
        event_bus.unsubscribe(queue)
