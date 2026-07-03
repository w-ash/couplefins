from datetime import date
from decimal import Decimal
import uuid

from attrs import define, field
from structlog.stdlib import get_logger

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.transactions import (
    classify_against_existing,
    find_all_unmapped_categories,
    get_other_person_names,
)
from src.domain.dedup import FieldDiff
from src.domain.entities.transaction import Transaction
from src.domain.parsing.monarch_csv import parse_monarch_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

logger = get_logger()

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
    household: bool
    payer_percentage: int


@define(frozen=True, slots=True)
class ChangedTransaction:
    existing_id: uuid.UUID
    incoming: PreviewTransaction
    existing: PreviewTransaction
    diffs: list[FieldDiff]


@define(frozen=True, slots=True)
class PreviewCsvResult:
    new_transactions: list[PreviewTransaction]
    unchanged_count: int
    changed_transactions: list[ChangedTransaction]
    removed_transactions: list[PreviewTransaction]
    skipped_adjustment_count: int
    unmapped_categories: list[str]


def _to_preview(tx: Transaction) -> PreviewTransaction:
    return PreviewTransaction(
        date=tx.date,
        merchant=tx.merchant,
        category=tx.category,
        amount=tx.amount,
        household=tx.household,
        payer_percentage=tx.payer_percentage,
    )


@define(slots=True)
class PreviewCsvUseCase:
    async def execute(
        self, command: PreviewCsvCommand, uow: UnitOfWorkProtocol
    ) -> PreviewCsvResult:
        async with uow:
            person = await require_by_id(
                uow.persons.get_by_id, command.person_id, "Person"
            )

            other_names = await get_other_person_names(uow, command.person_id)
            parsed = parse_monarch_csv(
                command.csv_text,
                command.person_id,
                _SENTINEL_UPLOAD_ID,
                person_names=other_names,
            )
            incoming = parsed.transactions

            all_categories = await uow.categories.get_all()
            tx_categories = {tx.category for tx in incoming}
            unmapped = find_all_unmapped_categories(all_categories, tx_categories)

            if not incoming:
                logger.info("csv_previewed", transaction_count=0, person=person.name)
                return PreviewCsvResult(
                    new_transactions=[],
                    unchanged_count=0,
                    changed_transactions=[],
                    removed_transactions=[],
                    skipped_adjustment_count=parsed.skipped_adjustment_count,
                    unmapped_categories=unmapped,
                )

            classified, existing, removed = await classify_against_existing(
                incoming, command.person_id, uow
            )
            existing_by_id = {e.id: e for e in existing}

            new_txs = [_to_preview(c.incoming) for c in classified if c.status == "new"]
            unchanged_count = sum(1 for c in classified if c.status == "unchanged")
            changed_txs = [
                ChangedTransaction(
                    existing_id=c.existing_id,  # type: ignore[arg-type]
                    incoming=_to_preview(c.incoming),
                    existing=_to_preview(existing_by_id[c.existing_id]),  # type: ignore[index]
                    diffs=list(c.diffs),
                )
                for c in classified
                if c.status == "changed"
            ]

            logger.info(
                "csv_previewed",
                transaction_count=len(incoming),
                new=len(new_txs),
                unchanged=unchanged_count,
                changed=len(changed_txs),
                removed=len(removed),
                person=person.name,
            )

            return PreviewCsvResult(
                new_transactions=new_txs,
                unchanged_count=unchanged_count,
                changed_transactions=changed_txs,
                removed_transactions=[_to_preview(tx) for tx in removed],
                skipped_adjustment_count=parsed.skipped_adjustment_count,
                unmapped_categories=unmapped,
            )
