from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.export.adjustments import compute_adjustments
from src.domain.export.csv_renderer import render_adjustment_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

_EXPECTED_PERSON_COUNT = 2


@define(frozen=True, slots=True)
class ExportAdjustmentsCommand:
    person_id: UUID
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class ExportAdjustmentsResult:
    csv_content: str
    filename: str
    person_name: str
    adjustment_count: int


@define(slots=True)
class ExportAdjustmentsUseCase:
    async def execute(
        self, command: ExportAdjustmentsCommand, uow: UnitOfWorkProtocol
    ) -> ExportAdjustmentsResult:
        async with uow:
            persons = await uow.persons.get_all()
            if len(persons) != _EXPECTED_PERSON_COUNT:
                raise ValidationError(
                    f"Expected {_EXPECTED_PERSON_COUNT} persons, found {len(persons)}"
                )

            target = next((p for p in persons if p.id == command.person_id), None)
            if target is None:
                raise NotFoundError(f"Person {command.person_id} not found")

            if not target.adjustment_account.strip():
                raise ValidationError(
                    f"Adjustment account not configured for {target.name}"
                )

            transactions = await uow.transactions.get_shared_by_period(
                command.year, command.month
            )
            adjustments = compute_adjustments(transactions, target)
            csv_content = render_adjustment_csv(adjustments)
            filename = (
                f"adjustments-{target.name.lower()}-"
                f"{command.year}-{command.month:02d}.csv"
            )

            return ExportAdjustmentsResult(
                csv_content=csv_content,
                filename=filename,
                person_name=target.name,
                adjustment_count=len(adjustments),
            )
