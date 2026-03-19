import uuid
from uuid import UUID

import attrs
from attrs import define

from src.domain.entities.category import Category
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class MappingEntry:
    category: str
    group_id: UUID


@define(frozen=True, slots=True)
class BulkUpdateMappingsCommand:
    mappings: list[MappingEntry]


@define(frozen=True, slots=True)
class BulkUpdateMappingsResult:
    updated_count: int


@define(slots=True)
class BulkUpdateMappingsUseCase:
    async def execute(
        self, command: BulkUpdateMappingsCommand, uow: UnitOfWorkProtocol
    ) -> BulkUpdateMappingsResult:
        async with uow:
            group_ids = {entry.group_id for entry in command.mappings}
            for group_id in group_ids:
                group = await uow.category_groups.get_by_id(group_id)
                if group is None:
                    raise ValidationError(f"Category group {group_id} not found")

            all_categories = await uow.categories.get_all()
            by_name = {c.name: c for c in all_categories}

            updated: list[Category] = []
            for entry in command.mappings:
                existing = by_name.get(entry.category)
                if existing is None:
                    updated.append(
                        Category(
                            id=uuid.uuid4(),
                            name=entry.category,
                            group_id=entry.group_id,
                        )
                    )
                else:
                    updated.append(attrs.evolve(existing, group_id=entry.group_id))

            await uow.categories.save_batch(updated)
            await uow.commit()
            return BulkUpdateMappingsResult(updated_count=len(command.mappings))
