"""Chat endpoint — agentic tool-use loop streaming over SSE."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import json
from typing import cast
from uuid import UUID

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolResultBlockParam
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from structlog.stdlib import get_logger

from src.application.chat.pending_actions import PendingAction, pending_action_store
from src.application.chat.system_prompt import build_system_prompt
from src.application.chat.tool_executor import execute_tool
from src.application.chat.tools import TOOLS
from src.application.runner import execute_use_case
from src.application.use_cases.bulk_modify_tags import (
    BulkModifyTagsCommand,
    BulkModifyTagsUseCase,
    TagAction,
)
from src.application.use_cases.bulk_update_transactions import (
    BulkUpdateTransactionsCommand,
    BulkUpdateTransactionsUseCase,
    Unset,
)
from src.application.use_cases.list_category_groups import (
    ListCategoryGroupsCommand,
    ListCategoryGroupsUseCase,
)
from src.application.use_cases.save_budget import (
    SaveBudgetCommand,
    SaveBudgetUseCase,
)
from src.application.use_cases.update_transaction_splits import (
    SplitEntry,
    UpdateTransactionSplitsCommand,
    UpdateTransactionSplitsUseCase,
)
from src.config.settings import get_settings
from src.domain.entities.person import Person
from src.domain.exceptions import MaxRoundsExceededError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.infrastructure.events.event_bus import BroadcastEntity, event_bus
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


# --- Confirmed action execution ---

_ACTION_ENTITY_MAP: dict[str, BroadcastEntity] = {
    "update_budget": "budgets",
    "update_transaction_split": "transactions",
    "bulk_update_transactions": "transactions",
}


async def _execute_confirmed_action(
    action: PendingAction,
    current_user: Person,
) -> dict[str, object]:
    """Execute a confirmed pending action via the appropriate use case."""
    if action.tool_name == "update_budget":
        return await _exec_budget(action)
    if action.tool_name == "update_transaction_split":
        return await _exec_split(action, current_user)
    if action.tool_name == "bulk_update_transactions":
        return await _exec_bulk(action, current_user)
    raise ValueError(f"Unknown mutation tool: {action.tool_name}")


async def _exec_budget(action: PendingAction) -> dict[str, object]:
    details = action.details
    group_id = UUID(cast(str, details["group_id"]))
    person_id = (
        UUID(cast(str, details["person_id"])) if details.get("person_id") else None
    )
    command = SaveBudgetCommand(
        group_id=group_id,
        monthly_amount=Decimal(str(details["amount"])),
        year=cast(int, details["year"]),
        month=cast(int, details["month"]),
        person_id=person_id,
    )
    result = await execute_use_case(
        lambda uow: SaveBudgetUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "budget_id": str(result.budget.id),
    }


async def _exec_split(action: PendingAction, current_user: Person) -> dict[str, object]:
    details = action.details
    command = UpdateTransactionSplitsCommand(
        splits=[
            SplitEntry(
                transaction_id=UUID(cast(str, details["transaction_id"])),
                payer_percentage=cast(int, details["payer_percentage"]),
            )
        ],
        edited_by_person_id=current_user.id,
    )
    result = await execute_use_case(
        lambda uow: UpdateTransactionSplitsUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "updated_count": result.updated_count,
    }


async def _exec_bulk(action: PendingAction, current_user: Person) -> dict[str, object]:
    details = action.details
    raw_ids = cast(list[str], details["transaction_ids"])
    transaction_ids = [UUID(tid) for tid in raw_ids]
    changes = cast(dict[str, object], details["changes"])

    results: list[dict[str, object]] = []

    # Handle tag changes separately via BulkModifyTagsUseCase
    if "tags" in changes:
        tag_info = cast(dict[str, object], changes["tags"])
        tag_command = BulkModifyTagsCommand(
            transaction_ids=transaction_ids,
            action=TagAction(cast(str, tag_info["action"])),
            tags=cast(list[str], tag_info["values"]),
            edited_by_person_id=current_user.id,
        )
        tag_result = await execute_use_case(
            lambda uow: BulkModifyTagsUseCase().execute(tag_command, uow)
        )
        results.append({"tags_updated": tag_result.updated_count})

    # Handle field changes via BulkUpdateTransactionsUseCase
    field_changes = {k: v for k, v in changes.items() if k != "tags"}
    if field_changes:
        field_command = BulkUpdateTransactionsCommand(
            transaction_ids=transaction_ids,
            edited_by_person_id=current_user.id,
            household=cast(bool, field_changes["household"])
            if "household" in field_changes
            else Unset.UNSET,
            payer_percentage=cast(int, field_changes["payer_percentage"])
            if "payer_percentage" in field_changes
            else Unset.UNSET,
            is_excluded=cast(bool, field_changes["is_excluded"])
            if "is_excluded" in field_changes
            else Unset.UNSET,
            category=cast(str, field_changes["category"])
            if "category" in field_changes
            else None,
        )
        field_result = await execute_use_case(
            lambda uow: BulkUpdateTransactionsUseCase().execute(field_command, uow)
        )
        results.append({"fields_updated": field_result.updated_count})

    total = sum(
        cast(int, r.get("tags_updated", 0)) + cast(int, r.get("fields_updated", 0))
        for r in results
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "updated_count": total,
    }


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

    # --- Confirmation interception ---
    confirmation_context: str | None = None
    if body.confirmation is not None:
        action_id = UUID(body.confirmation.action_id)
        if body.confirmation.approved:
            action = pending_action_store.claim(action_id, current_user.id)
            result_summary = await _execute_confirmed_action(action, current_user)
            entity = _ACTION_ENTITY_MAP.get(action.tool_name)
            if entity:
                event_bus.broadcast(entity)
            logger.info(
                "chat_action_confirmed",
                action_id=str(action_id),
                tool=action.tool_name,
            )
            confirmation_context = (
                f"[The user confirmed the proposed action. "
                f"Result: {json.dumps(result_summary)}. "
                f"Acknowledge the change briefly.]"
            )
        else:
            pending_action_store.cancel(action_id, current_user.id)
            logger.info("chat_action_cancelled", action_id=str(action_id))
            confirmation_context = (
                "[The user cancelled the proposed action. "
                "Acknowledge the cancellation briefly.]"
            )
        messages.append(MessageParam(role="user", content=confirmation_context))

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
                    error_summary: dict[str, object] = {"error": str(e)}
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
