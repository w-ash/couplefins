from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.domain.constants import CoupleDefaults
from src.domain.entities.person import Person
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.export.adjustments import Adjustment, compute_adjustments
from src.domain.export.csv_renderer import render_adjustment_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


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


@define(frozen=True, slots=True)
class PreviewAdjustmentsResult:
    adjustments: list[Adjustment]
    person_name: str
    adjustment_count: int


async def _load_adjustments(
    command: ExportAdjustmentsCommand, uow: UnitOfWorkProtocol
) -> tuple[Person, list[Adjustment]]:
    """Validate person, load transactions, compute adjustments."""
    persons = await uow.persons.get_all()
    if len(persons) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        raise ValidationError(
            f"Expected {CoupleDefaults.EXPECTED_PERSON_COUNT} persons, found {len(persons)}"
        )

    target = next((p for p in persons if p.id == command.person_id), None)
    if target is None:
        raise NotFoundError(f"Person {command.person_id} not found")

    if not target.adjustment_account.strip():
        raise ValidationError(f"Adjustment account not configured for {target.name}")

    transactions = await uow.transactions.get_shared_by_period(
        command.year, command.month
    )
    adjustments = compute_adjustments(transactions, target)
    return target, adjustments


@define(slots=True)
class ExportAdjustmentsUseCase:
    async def execute(
        self, command: ExportAdjustmentsCommand, uow: UnitOfWorkProtocol
    ) -> ExportAdjustmentsResult:
        async with uow:
            target, adjustments = await _load_adjustments(command, uow)
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


@define(slots=True)
class PreviewAdjustmentsUseCase:
    async def execute(
        self, command: ExportAdjustmentsCommand, uow: UnitOfWorkProtocol
    ) -> PreviewAdjustmentsResult:
        async with uow:
            target, adjustments = await _load_adjustments(command, uow)

            return PreviewAdjustmentsResult(
                adjustments=adjustments,
                person_name=target.name,
                adjustment_count=len(adjustments),
            )
