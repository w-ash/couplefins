from uuid import UUID

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.category_group import CategoryGroup, GroupKind
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdateCategoryGroupCommand:
    id: UUID
    name: str = field(validator=non_empty_string)
    # Required, not defaulted: a rename that forgot `kind` would silently
    # turn the Transfer group back into spending.
    kind: GroupKind
    icon: str | None = None


@define(frozen=True, slots=True)
class UpdateCategoryGroupResult:
    group: CategoryGroup


@define(slots=True)
class UpdateCategoryGroupUseCase:
    async def execute(
        self, command: UpdateCategoryGroupCommand, uow: UnitOfWorkProtocol
    ) -> UpdateCategoryGroupResult:
        async with uow:
            existing = await require_by_id(
                uow.category_groups.get_by_id, command.id, "Category group"
            )

            # Every budget on the group blocks the flip, including the
            # partner's personal ones — a transfer group carries none.
            if (
                command.kind == "transfer"
                and existing.kind != "transfer"
                and await uow.category_group_budgets.get_by_group_id(command.id)
            ):
                raise ValidationError(
                    "Remove this group's budgets (yours and your partner's) "
                    "before marking it as a transfer group"
                )

            updated = attrs.evolve(
                existing, name=command.name, icon=command.icon, kind=command.kind
            )
            saved = await uow.category_groups.save(updated)
            await uow.commit()
            return UpdateCategoryGroupResult(group=saved)
