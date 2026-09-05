from uuid import UUID

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.category_group import (
    CategoryGroup,
    GroupKind,
    is_spending_kind,
)
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
            # partner's personal ones — only a spending group carries budgets.
            if (
                not is_spending_kind(command.kind)
                and is_spending_kind(existing.kind)
                and await uow.category_group_budgets.get_by_group_id(command.id)
            ):
                raise ValidationError(
                    "Remove this group's budgets (yours and your partner's) "
                    f"before marking it as {'an' if command.kind == 'income' else 'a'} "
                    f"{command.kind} group"
                )

            updated = attrs.evolve(
                existing, name=command.name, icon=command.icon, kind=command.kind
            )
            saved = await uow.category_groups.save(updated)
            await uow.commit()
            return UpdateCategoryGroupResult(group=saved)
