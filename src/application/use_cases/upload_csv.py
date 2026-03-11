from datetime import UTC, datetime
import uuid

import attrs
from attrs import define, field
from loguru import logger

from src.application.use_cases._shared.command_validators import non_empty_string
from src.application.use_cases._shared.transactions import (
    classify_against_existing,
    find_new_categories,
    find_unmapped_categories,
)
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.upload import Upload
from src.domain.exceptions import NotFoundError
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
    async def execute(
        self, command: UploadCsvCommand, uow: UnitOfWorkProtocol
    ) -> UploadCsvResult:
        async with uow:
            person = await uow.persons.get_by_id(command.person_id)
            if person is None:
                raise NotFoundError(f"Person {command.person_id} not found")

            upload_id = uuid.uuid4()
            incoming = parse_monarch_csv(command.csv_text, command.person_id, upload_id)

            all_mappings = await uow.category_mappings.get_all()
            categories_in_csv = {tx.category for tx in incoming}

            # Auto-create CategoryMapping(group_id=None) for previously unseen categories
            auto_created = [
                CategoryMapping(category=cat, group_id=None)
                for cat in find_new_categories(all_mappings, categories_in_csv)
            ]
            if auto_created:
                await uow.category_mappings.save_batch(auto_created)
                all_mappings = [*all_mappings, *auto_created]

            unmapped = find_unmapped_categories(all_mappings, categories_in_csv)

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
