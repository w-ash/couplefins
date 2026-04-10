"""Chat endpoint — agentic tool-use loop streaming over SSE."""

import asyncio
from datetime import UTC, datetime
import json

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolResultBlockParam
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from structlog.stdlib import get_logger

from src.application.chat.system_prompt import build_system_prompt
from src.application.chat.tool_executor import execute_tool
from src.application.chat.tools import TOOLS
from src.application.runner import execute_use_case
from src.application.use_cases.list_category_groups import (
    ListCategoryGroupsCommand,
    ListCategoryGroupsUseCase,
)
from src.config.settings import get_settings
from src.domain.entities.person import Person
from src.domain.exceptions import MaxRoundsExceededError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.interface.api.dependencies import get_anthropic_client, get_current_user
from src.interface.api.schemas.chat import ChatRequest
from src.interface.api.sse import (
    QueueItem,
    ToolResultEvent,
    ToolStartEvent,
    stream_chat_response,
)

logger = get_logger()

router = APIRouter(tags=["chat"])


async def _fetch_persons() -> list[Person]:
    """Fetch all persons (for name resolution in tool results)."""

    async def _query(uow: UnitOfWorkProtocol) -> list[Person]:
        async with uow:
            return await uow.persons.get_all()

    return await execute_use_case(_query)


async def _fetch_partner(current_user: Person, persons: list[Person]) -> Person:
    """Find the partner (the other person)."""
    for p in persons:
        if p.id != current_user.id:
            return p
    return current_user


async def _fetch_category_group_names() -> list[str]:
    result = await execute_use_case(
        lambda uow: ListCategoryGroupsUseCase().execute(
            ListCategoryGroupsCommand(), uow
        )
    )
    return [item.group.name for item in result.items]


@router.post("/chat")
async def post_chat(
    body: ChatRequest,
    current_user: Person = Depends(get_current_user),
    anthropic: AsyncAnthropic = Depends(get_anthropic_client),
) -> StreamingResponse:
    settings = get_settings()
    persons, category_groups = await asyncio.gather(
        _fetch_persons(), _fetch_category_group_names()
    )
    partner = await _fetch_partner(current_user, persons)

    system = build_system_prompt(
        current_user, partner, datetime.now(UTC).date(), category_groups
    )
    messages: list[MessageParam] = [
        MessageParam(role=m.role, content=m.content) for m in body.messages
    ]

    async def run_chat(queue: asyncio.Queue[QueueItem]) -> None:
        nonlocal messages
        max_turns = settings.chat.max_turns

        for turn in range(max_turns):
            async with anthropic.messages.stream(
                model=settings.chat.model_id,
                max_tokens=8192,
                system=system,
                tools=TOOLS,
                messages=messages,
                extra_body={"output_config": {"effort": "medium"}},
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        queue.put_nowait(event.text)
                    elif event.type == "content_block_stop":
                        block = event.content_block
                        if block.type == "tool_use":
                            queue.put_nowait(
                                ToolStartEvent(
                                    name=block.name,
                                    tool_use_id=block.id,
                                )
                            )
                final = await stream.get_final_message()

            logger.info(
                "chat_turn",
                turn=turn,
                stop_reason=final.stop_reason,
                cache_read=getattr(final.usage, "cache_read_input_tokens", 0),
                cache_create=getattr(final.usage, "cache_creation_input_tokens", 0),
            )

            if final.stop_reason == "end_turn":
                return

            tool_use_blocks = [b for b in final.content if b.type == "tool_use"]
            if not tool_use_blocks:
                return

            tool_results: list[ToolResultBlockParam] = []
            for tu in tool_use_blocks:
                try:
                    summary = await execute_tool(
                        tu.name, tu.input, current_user, persons
                    )
                    queue.put_nowait(
                        ToolResultEvent(
                            name=tu.name, tool_use_id=tu.id, summary=summary
                        )
                    )
                    tool_results.append(
                        ToolResultBlockParam(
                            type="tool_result",
                            tool_use_id=tu.id,
                            content=json.dumps(summary),
                        )
                    )
                except Exception as e:
                    error_summary = {"error": str(e)}
                    queue.put_nowait(
                        ToolResultEvent(
                            name=tu.name,
                            tool_use_id=tu.id,
                            summary=error_summary,
                            is_error=True,
                        )
                    )
                    tool_results.append(
                        ToolResultBlockParam(
                            type="tool_result",
                            tool_use_id=tu.id,
                            content=str(e),
                            is_error=True,
                        )
                    )

            messages.append(
                MessageParam(
                    role="assistant",
                    content=final.content,
                )
            )
            messages.append(MessageParam(role="user", content=tool_results))

        raise MaxRoundsExceededError(f"Exceeded {max_turns} tool rounds")

    return stream_chat_response(run_chat)
