from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import uuid

import attrs
from attrs import define, field
from structlog.stdlib import get_logger

from src.application.use_cases._shared.command_validators import non_empty
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import assert_periods_not_finalized
from src.application.use_cases._shared.transactions import (
    classify_against_existing,
    delete_transactions_with_links,
    find_new_categories,
    find_unmapped_categories,
    parse_file,
)
from src.domain.dedup import ClassifiedTransaction
from src.domain.entities.category import Category
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import Upload
from src.domain.parsing.importer import Importer, accounts_named_by
from src.domain.parsing.monarch_csv import MonarchCsvImporter
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

logger = get_logger()

type ProgressCallback = Callable[[int, int, str], None]


def _noop_progress(_current: int, _total: int, _detail: str) -> None:
    pass


@define(frozen=True, slots=True)
class UploadCsvCommand:
    data: bytes = field(validator=non_empty)
    person_id: uuid.UUID
    filename: str = field(validator=non_empty)
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


@define(slots=True)
class UploadCsvUseCase:
    importer: Importer = field(factory=MonarchCsvImporter)

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
            accounts = await uow.accounts.get_all()
            parsed = await parse_file(
                uow,
                self.importer,
                command.data,
                person_id=command.person_id,
                upload_id=upload_id,
                accounts=accounts,
            )
            incoming = parsed.transactions

            classified, existing, removed = await classify_against_existing(
                incoming, command.person_id, accounts, uow
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
                importer=self.importer.name,
                content_sha256=hashlib.sha256(command.data).hexdigest(),
            )
            await uow.uploads.save(upload)

            new_txs = partition.new_txs
            updated_txs = partition.updated_txs
            skipped_count = partition.skipped_count
            if new_txs:
                await uow.accounts.add_missing(accounts_named_by(new_txs))
                await uow.transactions.save_batch(new_txs)
            if updated_txs:
                await uow.transactions.update_mutable_fields_batch(updated_txs)

            warnings = await delete_transactions_with_links(uow, removed)

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
