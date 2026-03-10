from uuid import UUID

from attrs import define

from src.domain.entities.category_mapping import CategoryMapping
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

            entities = [
                CategoryMapping(category=entry.category, group_id=entry.group_id)
                for entry in command.mappings
            ]
            await uow.category_mappings.save_batch(entities)
            await uow.commit()
            return BulkUpdateMappingsResult(updated_count=len(entities))
