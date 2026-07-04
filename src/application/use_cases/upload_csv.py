from collections.abc import Callable
from datetime import UTC, datetime
import uuid

import attrs
from attrs import define, field
from structlog.stdlib import get_logger

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import assert_periods_not_finalized
from src.application.use_cases._shared.transactions import (
    classify_against_existing,
    find_new_categories,
    find_unmapped_categories,
    get_other_person_names,
)
from src.domain.dedup import ClassifiedTransaction
from src.domain.entities.category import Category
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import Upload
from src.domain.parsing.monarch_csv import parse_monarch_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

logger = get_logger()

type ProgressCallback = Callable[[int, int, str], None]


def _noop_progress(_current: int, _total: int, _detail: str) -> None:
    pass


@define(frozen=True, slots=True)
class UploadCsvCommand:
    csv_text: str = field(validator=non_empty_string)
    person_id: uuid.UUID
    filename: str = field(validator=non_empty_string)
    accepted_change_ids: frozenset[uuid.UUID] = frozenset()


@define(frozen=True, slots=True)
class UploadCsvResult:
    upload_id: uuid.UUID
    filename: str
    new_count: int
    updated_count: int
    skipped_count: int
    removed_count: int
    skipped_adjustment_count: int
    unmapped_categories: list[str]
    warnings: list[str]


async def _ensure_categories(
    uow: UnitOfWorkProtocol, incoming: list[Transaction]
) -> list[str]:
    """Auto-create unknown categories (group_id=None); return unmapped names."""
    all_categories = await uow.categories.get_all()
    categories_in_csv = {tx.category for tx in incoming}
    auto_created = [
        Category(id=uuid.uuid4(), name=cat, group_id=None)
        for cat in find_new_categories(all_categories, categories_in_csv)
    ]
    if auto_created:
        await uow.categories.save_batch(auto_created)
        all_categories = [*all_categories, *auto_created]
    return find_unmapped_categories(all_categories, categories_in_csv)


@define(frozen=True, slots=True)
class _Partition:
    """Outcome of splitting classified rows for a re-upload.

    `updated_existing` carries the *stored* rows behind each accepted update —
    their current `date` (which may differ from the CSV date after an in-app
    edit) is needed to guard the right period against finalization.
    """

    new_txs: list[Transaction]
    updated_txs: list[Transaction]
    updated_existing: list[Transaction]
    skipped_count: int


def _partition_changes(
    classified: list[ClassifiedTransaction],
    accepted_change_ids: frozenset[uuid.UUID],
    upload_id: uuid.UUID,
    existing_by_id: dict[uuid.UUID, Transaction],
) -> _Partition:
    """Split classified rows into new / accepted-updates / skipped in one pass."""
    new_txs: list[Transaction] = []
    updated_txs: list[Transaction] = []
    updated_existing: list[Transaction] = []
    skipped_count = 0
    for c in classified:
        if c.status == "new":
            new_txs.append(c.incoming)
        elif c.status == "unchanged":
            skipped_count += 1
        else:  # changed
            existing = existing_by_id.get(c.existing_id) if c.existing_id else None
            if existing is not None and c.existing_id in accepted_change_ids:
                updated_txs.append(
                    attrs.evolve(c.incoming, id=c.existing_id, upload_id=upload_id)
                )
                updated_existing.append(existing)
            else:
                skipped_count += 1
    return _Partition(new_txs, updated_txs, updated_existing, skipped_count)


async def _delete_removed(
    uow: UnitOfWorkProtocol, removed: list[Transaction]
) -> list[str]:
    """Delete rows the new CSV no longer contains; unlink settlements first.

    Returns warnings for rows that were linked to a settlement — the link is
    removed but the settlement record itself stays.
    """
    if not removed:
        return []
    removed_ids = [tx.id for tx in removed]
    warnings: list[str] = []
    links = await uow.settlement_transaction_links.get_by_transaction_ids(removed_ids)
    if links:
        linked_ids = {link.transaction_id for link in links}
        warnings = [
            f"Removed transaction {tx.merchant} ({tx.date.isoformat()}) "
            "was linked to a settlement — the link was removed"
            for tx in removed
            if tx.id in linked_ids
        ]
        await uow.settlement_transaction_links.delete_by_transaction_ids(removed_ids)
    await uow.transaction_edits.delete_by_transaction_ids(removed_ids)
    await uow.transactions.delete_by_ids(removed_ids)
    return warnings


@define(slots=True)
class UploadCsvUseCase:
    async def execute(
        self,
        command: UploadCsvCommand,
        uow: UnitOfWorkProtocol,
        on_progress: ProgressCallback = _noop_progress,
    ) -> UploadCsvResult:
        async with uow:
            on_progress(1, 4, "Parsing CSV")

            person = await require_by_id(
                uow.persons.get_by_id, command.person_id, "Person"
            )

            upload_id = uuid.uuid4()
            other_names = await get_other_person_names(uow, command.person_id)
            parsed = parse_monarch_csv(
                command.csv_text, command.person_id, upload_id, person_names=other_names
            )
            incoming = parsed.transactions

            classified, existing, removed = await classify_against_existing(
                incoming, command.person_id, uow
            )
            partition = _partition_changes(
                classified,
                command.accepted_change_ids,
                upload_id,
                {e.id: e for e in existing},
            )

            # Guard every month the upload touches by the row's CURRENT date:
            # removed rows and in-app date-edited updates can live in a month
            # with no incoming rows (date moved across the period boundary).
            await assert_periods_not_finalized(
                uow,
                {
                    (tx.date.year, tx.date.month)
                    for tx in [*incoming, *removed, *partition.updated_existing]
                },
            )

            on_progress(2, 4, "Classifying transactions")

            unmapped = await _ensure_categories(uow, incoming)

            on_progress(3, 4, f"Saving {len(classified)} transactions")

            upload = Upload(
                id=upload_id,
                person_id=command.person_id,
                filename=command.filename,
                uploaded_at=datetime.now(UTC),
            )
            await uow.uploads.save(upload)

            new_txs = partition.new_txs
            updated_txs = partition.updated_txs
            skipped_count = partition.skipped_count
            if new_txs:
                await uow.transactions.save_batch(new_txs)
            if updated_txs:
                await uow.transactions.update_mutable_fields_batch(updated_txs)

            warnings = await _delete_removed(uow, removed)

            await uow.commit()
            on_progress(4, 4, "Complete")

            logger.info(
                "csv_uploaded",
                filename=command.filename,
                new=len(new_txs),
                updated=len(updated_txs),
                skipped=skipped_count,
                removed=len(removed),
                person=person.name,
            )

            return UploadCsvResult(
                upload_id=upload_id,
                filename=command.filename,
                new_count=len(new_txs),
                updated_count=len(updated_txs),
                skipped_count=skipped_count,
                removed_count=len(removed),
                skipped_adjustment_count=parsed.skipped_adjustment_count,
                unmapped_categories=unmapped,
                warnings=warnings,
            )
