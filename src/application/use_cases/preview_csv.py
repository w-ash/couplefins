from datetime import date
from decimal import Decimal
import uuid

from attrs import define, field
from loguru import logger

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.transactions import (
    classify_against_existing,
    find_all_unmapped_categories,
)
from src.domain.dedup import FieldDiff
from src.domain.entities.transaction import Transaction
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
    unmapped_categories: list[str]


def _to_preview(tx: Transaction) -> PreviewTransaction:
    return PreviewTransaction(
        date=tx.date,
        merchant=tx.merchant,
        category=tx.category,
        amount=tx.amount,
        is_shared=tx.is_shared,
        payer_percentage=tx.payer_percentage,
    )


@define(slots=True)
class PreviewCsvUseCase:
    async def execute(
        self, command: PreviewCsvCommand, uow: UnitOfWorkProtocol
    ) -> PreviewCsvResult:
        async with uow:
            person = await uow.persons.get_by_id(command.person_id)
            if person is None:
                raise NotFoundError(f"Person {command.person_id} not found")

            incoming = parse_monarch_csv(
                command.csv_text, command.person_id, _SENTINEL_UPLOAD_ID
            )

            all_mappings = await uow.category_mappings.get_all()
            tx_categories = {tx.category for tx in incoming}
            unmapped = find_all_unmapped_categories(all_mappings, tx_categories)

            if not incoming:
                logger.info("Previewed 0 transactions for person {}", person.name)
                return PreviewCsvResult(
                    new_transactions=[],
                    unchanged_count=0,
                    changed_transactions=[],
                    unmapped_categories=unmapped,
                )

            classified, existing = await classify_against_existing(
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
                "Previewed {} transactions ({} new, {} unchanged, {} changed) for person {}",
                len(incoming),
                len(new_txs),
                unchanged_count,
                len(changed_txs),
                person.name,
            )

            return PreviewCsvResult(
                new_transactions=new_txs,
                unchanged_count=unchanged_count,
                changed_transactions=changed_txs,
                unmapped_categories=unmapped,
            )
