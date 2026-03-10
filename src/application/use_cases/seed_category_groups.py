from pathlib import Path
from typing import TypedDict
import uuid

from attrs import define
from loguru import logger
from pydantic import TypeAdapter

from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "category_groups.json"
)


class _CategoryGroupFixture(TypedDict):
    name: str
    categories: list[str]


_fixture_adapter = TypeAdapter(list[_CategoryGroupFixture])


@define(frozen=True, slots=True)
class SeedCategoryGroupsCommand:
    pass


@define(frozen=True, slots=True)
class SeedCategoryGroupsResult:
    groups_created: int
    mappings_created: int
    skipped: bool


class SeedCategoryGroupsUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(
        self, _command: SeedCategoryGroupsCommand | None = None
    ) -> SeedCategoryGroupsResult:
        existing_count = await self._uow.category_groups.count()
        if existing_count > 0:
            logger.info(
                "Category groups already seeded ({} groups), skipping", existing_count
            )
            return SeedCategoryGroupsResult(
                groups_created=0, mappings_created=0, skipped=True
            )

        fixture_text = FIXTURE_PATH.read_bytes()
        fixture_data = _fixture_adapter.validate_json(fixture_text)

        groups: list[CategoryGroup] = []
        mappings: list[CategoryMapping] = []

        for group_data in fixture_data:
            group_id = uuid.uuid4()
            groups.append(CategoryGroup(id=group_id, name=group_data["name"]))
            mappings.extend(
                CategoryMapping(category=category_name, group_id=group_id)
                for category_name in group_data["categories"]
            )

        await self._uow.category_groups.save_batch(groups)
        await self._uow.category_mappings.save_batch(mappings)
        await self._uow.commit()
        logger.info(
            "Seeded {} category groups with {} category mappings",
            len(groups),
            len(mappings),
        )
        return SeedCategoryGroupsResult(
            groups_created=len(groups),
            mappings_created=len(mappings),
            skipped=False,
        )


async def seed_category_groups(uow: UnitOfWorkProtocol) -> SeedCategoryGroupsResult:
    use_case = SeedCategoryGroupsUseCase(uow)
    return await use_case.execute()
