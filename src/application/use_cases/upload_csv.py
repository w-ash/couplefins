from datetime import UTC, datetime
import uuid

from attrs import define, field
from loguru import logger

from src.application.use_cases._shared.command_validators import (
    month_range,
    non_empty_string,
    positive_int,
)
from src.application.use_cases._shared.transactions import (
    count_shared,
    find_unmapped_categories,
)
from src.domain.entities.upload import Upload
from src.domain.exceptions import NotFoundError
from src.domain.parsing.monarch_csv import parse_monarch_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UploadCsvCommand:
    csv_text: str = field(validator=non_empty_string)
    person_id: uuid.UUID
    filename: str = field(validator=non_empty_string)
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class UploadCsvResult:
    upload_id: uuid.UUID
    filename: str
    period_year: int
    period_month: int
    total_transactions: int
    shared_count: int
    personal_count: int
    unmapped_categories: list[str]


@define(slots=True)
class UploadCsvUseCase:
    async def execute(
        self, command: UploadCsvCommand, uow: UnitOfWorkProtocol
    ) -> UploadCsvResult:
        async with uow:
            person = await uow.persons.get_by_id(command.person_id)
            if person is None:
                raise NotFoundError(f"Person {command.person_id} not found")

            upload_id = uuid.uuid4()
            upload = Upload(
                id=upload_id,
                person_id=command.person_id,
                filename=command.filename,
                uploaded_at=datetime.now(UTC),
                period_year=command.year,
                period_month=command.month,
            )

            transactions = parse_monarch_csv(
                command.csv_text, command.person_id, upload_id
            )

            await uow.uploads.save(upload)
            if transactions:
                await uow.transactions.save_batch(transactions)

            all_mappings = await uow.category_mappings.get_all()
            tx_categories = {tx.category for tx in transactions}
            unmapped = find_unmapped_categories(all_mappings, tx_categories)

            await uow.commit()

            shared_count, personal_count = count_shared(transactions)

            logger.info(
                "Uploaded {} transactions ({} shared, {} personal) for person {}",
                len(transactions),
                shared_count,
                personal_count,
                person.name,
            )

            return UploadCsvResult(
                upload_id=upload_id,
                filename=command.filename,
                period_year=command.year,
                period_month=command.month,
                total_transactions=len(transactions),
                shared_count=shared_count,
                personal_count=personal_count,
                unmapped_categories=unmapped,
            )
