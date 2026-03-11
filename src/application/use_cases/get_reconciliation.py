from collections import Counter
import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.transactions import find_all_unmapped_categories
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import ReconciliationSummary, reconcile
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetReconciliationCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class UploadStatus:
    person_id: uuid.UUID
    person_name: str
    has_uploaded: bool
    upload_count: int


@define(frozen=True, slots=True)
class GetReconciliationResult:
    summary: ReconciliationSummary
    transactions: list[Transaction]
    upload_statuses: list[UploadStatus]
    unmapped_categories: list[str]
    persons: list[Person]


@define(slots=True)
class GetReconciliationUseCase:
    async def execute(
        self, command: GetReconciliationCommand, uow: UnitOfWorkProtocol
    ) -> GetReconciliationResult:
        async with uow:
            persons = await uow.persons.get_all()
            transactions = await uow.transactions.get_shared_by_period(
                command.year, command.month
            )
            category_mappings = await uow.category_mappings.get_all()
            category_groups = await uow.category_groups.get_all()
            person_ids = [p.id for p in persons]
            uploads = await uow.uploads.get_by_person_ids_with_transactions_in_period(
                person_ids, command.year, command.month
            )

            summary = reconcile(
                transactions,
                persons,
                category_mappings,
                category_groups,
                year=command.year,
                month=command.month,
            )

            upload_counts = Counter(u.person_id for u in uploads)
            upload_statuses = [
                UploadStatus(
                    person_id=p.id,
                    person_name=p.name,
                    has_uploaded=upload_counts[p.id] > 0,
                    upload_count=upload_counts[p.id],
                )
                for p in persons
            ]

            tx_categories = {tx.category for tx in transactions}
            unmapped = find_all_unmapped_categories(category_mappings, tx_categories)

            return GetReconciliationResult(
                summary=summary,
                transactions=transactions,
                upload_statuses=upload_statuses,
                unmapped_categories=unmapped,
                persons=persons,
            )
