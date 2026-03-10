from datetime import date
from decimal import Decimal
import uuid

from attrs import define, field
from loguru import logger

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.transactions import (
    count_shared,
    find_unmapped_categories,
)
from src.domain.exceptions import NotFoundError
from src.domain.parsing.monarch_csv import parse_monarch_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

_SENTINEL_UPLOAD_ID = uuid.UUID(int=0)


@define(frozen=True, slots=True)
class PreviewCsvCommand:
    csv_text: str = field(validator=non_empty_string)
    person_id: uuid.UUID


@define(frozen=True, slots=True)
class PreviewTransaction:
    date: date
    merchant: str
    category: str
    amount: Decimal
    is_shared: bool
    payer_percentage: int | None


@define(frozen=True, slots=True)
class PreviewCsvResult:
    transactions: list[PreviewTransaction]
    total_count: int
    shared_count: int
    personal_count: int
    unmapped_categories: list[str]


@define(slots=True)
class PreviewCsvUseCase:
    async def execute(
        self, command: PreviewCsvCommand, uow: UnitOfWorkProtocol
    ) -> PreviewCsvResult:
        async with uow:
            person = await uow.persons.get_by_id(command.person_id)
            if person is None:
                raise NotFoundError(f"Person {command.person_id} not found")

            transactions = parse_monarch_csv(
                command.csv_text, command.person_id, _SENTINEL_UPLOAD_ID
            )

            all_mappings = await uow.category_mappings.get_all()
            tx_categories = {tx.category for tx in transactions}
            unmapped = find_unmapped_categories(all_mappings, tx_categories)

            preview_transactions = [
                PreviewTransaction(
                    date=tx.date,
                    merchant=tx.merchant,
                    category=tx.category,
                    amount=tx.amount,
                    is_shared=tx.is_shared,
                    payer_percentage=tx.payer_percentage,
                )
                for tx in transactions
            ]

            shared_count, personal_count = count_shared(transactions)

            logger.info(
                "Previewed {} transactions ({} shared, {} personal) for person {}",
                len(transactions),
                shared_count,
                personal_count,
                person.name,
            )

            return PreviewCsvResult(
                transactions=preview_transactions,
                total_count=len(transactions),
                shared_count=shared_count,
                personal_count=personal_count,
                unmapped_categories=unmapped,
            )
