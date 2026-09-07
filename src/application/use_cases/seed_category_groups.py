from pathlib import Path
from typing import NotRequired, TypedDict
import uuid

from attrs import define
from pydantic import TypeAdapter
from structlog.stdlib import get_logger

from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup, GroupKind
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

logger = get_logger()

# The taxonomy a brand-new database starts with: Monarch's default groups,
# shipped with the code so any fresh environment can boot.
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "seed_data" / "category_groups.json"
)

# An optional local override, gitignored because it mirrors one household's own
# Monarch settings. Present on the couple's laptops, absent everywhere else.
LOCAL_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "category_groups.json"
)


def _fixture_path() -> Path:
    if LOCAL_FIXTURE_PATH.is_file():
        return LOCAL_FIXTURE_PATH
    return DEFAULT_FIXTURE_PATH


class _CategoryGroupFixture(TypedDict):
    name: str
    icon: str
    categories: list[str]
    kind: NotRequired[GroupKind]


_fixture_adapter = TypeAdapter(list[_CategoryGroupFixture])


@define(frozen=True, slots=True)
class SeedCategoryGroupsCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class SeedCategoryGroupsResult:
    groups_created: int
    categories_created: int
    skipped: bool


@define(slots=True)
class SeedCategoryGroupsUseCase:
    async def execute(
        self, _command: SeedCategoryGroupsCommand, uow: UnitOfWorkProtocol
    ) -> SeedCategoryGroupsResult:
        async with uow:
            existing_count = await uow.category_groups.count()
            if existing_count > 0:
                logger.info("category_groups_skipped", existing_count=existing_count)
                return SeedCategoryGroupsResult(
                    groups_created=0, categories_created=0, skipped=True
                )

            fixture_text = _fixture_path().read_bytes()
            fixture_data = _fixture_adapter.validate_json(fixture_text)

            groups: list[CategoryGroup] = []
            categories: list[Category] = []

            for group_data in fixture_data:
                group_id = uuid.uuid4()
                groups.append(
                    CategoryGroup(
                        id=group_id,
                        name=group_data["name"],
                        icon=group_data["icon"],
                        kind=group_data.get("kind", "expense"),
                    )
                )
                categories.extend(
                    Category(id=uuid.uuid4(), name=category_name, group_id=group_id)
                    for category_name in group_data["categories"]
                )

            await uow.category_groups.save_batch(groups)
            await uow.categories.save_batch(categories)
            await uow.commit()
            logger.info(
                "category_groups_seeded",
                groups=len(groups),
                categories=len(categories),
            )
            return SeedCategoryGroupsResult(
                groups_created=len(groups),
                categories_created=len(categories),
                skipped=False,
            )


async def seed_category_groups(uow: UnitOfWorkProtocol) -> SeedCategoryGroupsResult:
    return await SeedCategoryGroupsUseCase().execute(SeedCategoryGroupsCommand(), uow)
