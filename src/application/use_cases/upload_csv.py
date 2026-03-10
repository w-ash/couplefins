from datetime import UTC, datetime
import uuid

from attrs import define
from loguru import logger

from src.domain.entities.upload import Upload
from src.domain.exceptions import NotFoundError
from src.domain.parsing.monarch_csv import parse_monarch_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UploadCsvCommand:
    csv_text: str
    person_id: uuid.UUID
    filename: str
    year: int
    month: int


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


class UploadCsvUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self, command: UploadCsvCommand) -> UploadCsvResult:
        person = await self._uow.persons.get_by_id(command.person_id)
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

        transactions = parse_monarch_csv(command.csv_text, command.person_id, upload_id)

        await self._uow.uploads.save(upload)
        if transactions:
            await self._uow.transactions.save_batch(transactions)

        all_mappings = await self._uow.category_mappings.get_all()
        mapped_categories = {m.category for m in all_mappings}
        tx_categories = {tx.category for tx in transactions}
        unmapped = sorted(tx_categories - mapped_categories)

        await self._uow.commit()

        shared_count = sum(1 for tx in transactions if tx.is_shared)
        personal_count = len(transactions) - shared_count

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
