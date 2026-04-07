from uuid import UUID, uuid4

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.finalization import assert_period_not_finalized
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CopyBudgetsCommand:
    source_year: int = field(validator=positive_int)
    source_month: int = field(validator=month_range)
    target_year: int = field(validator=positive_int)
    target_month: int = field(validator=month_range)
    person_id: UUID = field()

    def __attrs_post_init__(self) -> None:
        if (self.source_year, self.source_month) == (
            self.target_year,
            self.target_month,
        ):
            raise ValidationError("Source and target month must differ")


@define(frozen=True, slots=True)
class CopyBudgetsResult:
    copied_count: int
    skipped_count: int


@define(slots=True)
class CopyBudgetsUseCase:
    async def execute(
        self, command: CopyBudgetsCommand, uow: UnitOfWorkProtocol
    ) -> CopyBudgetsResult:
        async with uow:
            await assert_period_not_finalized(
                uow, command.target_year, command.target_month
            )

            source_household = await uow.category_group_budgets.get_by_month(
                command.source_year, command.source_month, None
            )
            source_personal = await uow.category_group_budgets.get_by_month(
                command.source_year, command.source_month, command.person_id
            )

            target_household = await uow.category_group_budgets.get_by_month(
                command.target_year, command.target_month, None
            )
            target_personal = await uow.category_group_budgets.get_by_month(
                command.target_year, command.target_month, command.person_id
            )

            existing_household = {b.group_id for b in target_household}
            existing_personal = {b.group_id for b in target_personal}

            new_budgets: list[CategoryGroupBudget] = []
            skipped = 0

            for b in source_household:
                if b.group_id in existing_household:
                    skipped += 1
                    continue
                new_budgets.append(
                    CategoryGroupBudget(
                        id=uuid4(),
                        group_id=b.group_id,
                        monthly_amount=b.monthly_amount,
                        year=command.target_year,
                        month=command.target_month,
                        person_id=None,
                    )
                )

            for b in source_personal:
                if b.group_id in existing_personal:
                    skipped += 1
                    continue
                new_budgets.append(
                    CategoryGroupBudget(
                        id=uuid4(),
                        group_id=b.group_id,
                        monthly_amount=b.monthly_amount,
                        year=command.target_year,
                        month=command.target_month,
                        person_id=command.person_id,
                    )
                )

            if new_budgets:
                await uow.category_group_budgets.save_batch(new_budgets)
            await uow.commit()

            return CopyBudgetsResult(
                copied_count=len(new_budgets),
                skipped_count=skipped,
            )
