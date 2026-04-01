from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from attrs import define, evolve

from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from ._shared.transaction_pipeline import compute_edit, fetch_and_validate

if TYPE_CHECKING:
    from src.domain.entities.transaction import Transaction


class TagAction(StrEnum):
    ADD = "add"
    REMOVE = "remove"


@define(frozen=True, slots=True)
class BulkModifyTagsCommand:
    transaction_ids: list[UUID]
    action: TagAction
    tags: list[str]


@define(frozen=True, slots=True)
class BulkModifyTagsResult:
    updated_count: int


def _add_tags(existing: tuple[str, ...], new_tags: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*existing, *new_tags]))


def _remove_tags(existing: tuple[str, ...], remove: set[str]) -> tuple[str, ...]:
    return tuple(t for t in existing if t.lower() not in remove)


@define(slots=True)
class BulkModifyTagsUseCase:
    async def execute(
        self,
        command: BulkModifyTagsCommand,
        uow: UnitOfWorkProtocol,
    ) -> BulkModifyTagsResult:
        if not command.transaction_ids:
            raise ValidationError("At least one transaction ID is required")

        if not command.tags:
            raise ValidationError("At least one tag is required")

        async with uow:
            transactions = await fetch_and_validate(uow, command.transaction_ids)

            edits: list[TransactionEdit] = []
            now = datetime.now(UTC)
            updated_count = 0
            normalized_tags = [t.lower() for t in command.tags]
            remove_set = set(normalized_tags)

            for tx_id in command.transaction_ids:
                tx = transactions[tx_id]

                if command.action == TagAction.ADD:
                    new_tags = _add_tags(tx.tags, normalized_tags)
                else:
                    new_tags = _remove_tags(tx.tags, remove_set)

                edit = compute_edit(tx, "tags", tx.tags, new_tags, now)
                if edit is None:
                    continue

                edits.append(edit)
                updated: Transaction = evolve(tx, tags=new_tags)
                await uow.transactions.update_mutable_fields(updated)
                updated_count += 1

            if edits:
                await uow.transaction_edits.save_batch(edits)

            await uow.commit()
            return BulkModifyTagsResult(updated_count=updated_count)
