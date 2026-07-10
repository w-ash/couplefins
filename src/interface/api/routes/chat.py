"""Chat endpoint — thin SSE bridge delegating to ChatUseCase."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
import json
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from structlog.stdlib import get_logger

from src.application.chat.events import TextDelta
from src.application.chat.pending_actions import pending_action_store
from src.application.chat.protocols import LLMClientProtocol
from src.application.chat.registry import TOOLS, execute_confirmed_action
from src.application.chat.system_prompt import build_system_prompt
from src.application.chat.use_case import ChatCommand, ChatUseCase
from src.application.runner import execute_use_case
from src.application.use_cases.list_category_groups import list_category_groups
from src.application.use_cases.list_persons import list_persons
from src.config.settings import get_settings
from src.domain.entities.person import Person
from src.infrastructure.events.event_bus import BroadcastEntity, event_bus
from src.interface.api.dependencies import get_current_user, get_llm_client
from src.interface.api.rate_limit import InMemoryRateLimiter
from src.interface.api.schemas.chat import ChatRequest
from src.interface.api.sse import QueueItem, stream_chat_response

logger = get_logger()

router = APIRouter(tags=["chat"])

_chat_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=60)


async def _handle_confirmation(
    body: ChatRequest,
    current_user: Person,
) -> str | None:
    """Process confirmation if present. Returns context string to append."""
    if body.confirmation is None:
        return None
    action_id = UUID(body.confirmation.action_id)
    if body.confirmation.approved:
        action = pending_action_store.claim(action_id, current_user.id)
        result_summary, entity = await execute_confirmed_action(action, current_user)
        if entity:
            event_bus.broadcast(cast(BroadcastEntity, entity))
        logger.info(
            "chat_action_confirmed",
            action_id=str(action_id),
            tool=action.tool_name,
        )
        return (
            f"[The user confirmed the proposed action. "
            f"Result: {json.dumps(result_summary)}. "
            f"Acknowledge the change briefly.]"
        )
    pending_action_store.cancel(action_id, current_user.id)
    logger.info("chat_action_cancelled", action_id=str(action_id))
    return (
        "[The user cancelled the proposed action. "
        "Acknowledge the cancellation briefly.]"
    )


async def _build_command(
    body: ChatRequest,
    current_user: Person,
    confirmation_context: str | None,
) -> ChatCommand:
    """Gather context and build the ChatCommand."""
    persons, category_groups = await asyncio.gather(
        _fetch_persons(), _fetch_category_group_names()
    )
    partner = _find_partner(current_user, persons)
    today = body.client_date or datetime.now(UTC).date()
    system = build_system_prompt(current_user, partner, today, category_groups)
    messages: list[dict[str, object]] = [
        {"role": m.role, "content": m.content} for m in body.messages
    ]
    if confirmation_context is not None:
        messages.append({"role": "user", "content": confirmation_context})
    settings = get_settings()
    return ChatCommand(
        messages=messages,
        system=system,
        tools=TOOLS,
        model_id=settings.chat.model_id,
        max_turns=settings.chat.max_turns,
        max_tokens=settings.chat.max_tokens,
        effort=settings.chat.effort,
        current_user=current_user,
        persons=persons,
    )


def _find_partner(current_user: Person, persons: list[Person]) -> Person:
    for p in persons:
        if p.id != current_user.id:
            return p
    return current_user


async def _fetch_persons() -> list[Person]:
    result = await execute_use_case(list_persons)
    return result.persons


async def _fetch_category_group_names() -> list[str]:
    result = await execute_use_case(list_category_groups)
    return [item.group.name for item in result.items]


def _bridge(
    use_case: ChatUseCase, command: ChatCommand
) -> Callable[[asyncio.Queue[QueueItem]], Awaitable[None]]:
    """Wrap the async generator into a queue-based run function for SSE."""

    async def _run(queue: asyncio.Queue[QueueItem]) -> None:
        async for event in use_case.execute(command):
            if isinstance(event, TextDelta):
                queue.put_nowait(event.text)
            else:
                queue.put_nowait(event)

    return _run


@router.post("/chat")
async def post_chat(
    body: ChatRequest,
    current_user: Person = Depends(get_current_user),
    llm: LLMClientProtocol = Depends(get_llm_client),
) -> StreamingResponse:
    _chat_limiter.check(current_user.id)
    confirmation_context = await _handle_confirmation(body, current_user)
    command = await _build_command(body, current_user, confirmation_context)
    return stream_chat_response(_bridge(ChatUseCase(llm), command))
