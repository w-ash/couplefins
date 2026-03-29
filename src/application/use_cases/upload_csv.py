from datetime import UTC, datetime
import uuid

import attrs
from attrs import define, field
from loguru import logger

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import assert_periods_not_finalized
from src.application.use_cases._shared.transactions import (
    classify_against_existing,
    find_new_categories,
    find_unmapped_categories,
    get_other_person_names,
)
from src.domain.entities.category import Category
from src.domain.entities.upload import Upload
from src.domain.parsing.monarch_csv import parse_monarch_csv
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


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
    unmapped_categories: list[str]


@define(slots=True)
class UploadCsvUseCase:
    async def execute(  # noqa: PLR0914
        self, command: UploadCsvCommand, uow: UnitOfWorkProtocol
    ) -> UploadCsvResult:
        async with uow:
            person = await require_by_id(
                uow.persons.get_by_id, command.person_id, "Person"
            )

            upload_id = uuid.uuid4()
            other_names = await get_other_person_names(uow, command.person_id)
            incoming = parse_monarch_csv(
                command.csv_text, command.person_id, upload_id, person_names=other_names
            )

            affected_periods = {(tx.date.year, tx.date.month) for tx in incoming}
            await assert_periods_not_finalized(uow, affected_periods)

            all_categories = await uow.categories.get_all()
            categories_in_csv = {tx.category for tx in incoming}

            # Auto-create Category(group_id=None) for previously unseen categories
            auto_created = [
                Category(id=uuid.uuid4(), name=cat, group_id=None)
                for cat in find_new_categories(all_categories, categories_in_csv)
            ]
            if auto_created:
                await uow.categories.save_batch(auto_created)
                all_categories = [*all_categories, *auto_created]

            unmapped = find_unmapped_categories(all_categories, categories_in_csv)

            classified, _ = await classify_against_existing(
                incoming, command.person_id, uow
            )

            upload = Upload(
                id=upload_id,
                person_id=command.person_id,
                filename=command.filename,
                uploaded_at=datetime.now(UTC),
            )
            await uow.uploads.save(upload)

            new_txs = [c.incoming for c in classified if c.status == "new"]
            if new_txs:
                await uow.transactions.save_batch(new_txs)

            updated_count = 0
            skipped_count = 0
            for c in classified:
                if c.status == "unchanged":
                    skipped_count += 1
                elif c.status == "changed":
                    if c.existing_id in command.accepted_change_ids:
                        updated_tx = attrs.evolve(
                            c.incoming,
                            id=c.existing_id,  # type: ignore[arg-type]
                            upload_id=upload_id,
                        )
                        await uow.transactions.update_mutable_fields(updated_tx)
                        updated_count += 1
                    else:
                        skipped_count += 1

            await uow.commit()

            logger.info(
                "Uploaded {} ({} new, {} updated, {} skipped) for person {}",
                command.filename,
                len(new_txs),
                updated_count,
                skipped_count,
                person.name,
            )

            return UploadCsvResult(
                upload_id=upload_id,
                filename=command.filename,
                new_count=len(new_txs),
                updated_count=updated_count,
                skipped_count=skipped_count,
                unmapped_categories=unmapped,
            )
