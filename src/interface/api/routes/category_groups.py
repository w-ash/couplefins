from uuid import UUID

from fastapi import APIRouter

from src.application.runner import execute_use_case
from src.application.use_cases.bulk_update_mappings import (
    BulkUpdateMappingsCommand,
    BulkUpdateMappingsUseCase,
    MappingEntry,
)
from src.application.use_cases.create_category_group import (
    CreateCategoryGroupCommand,
    CreateCategoryGroupUseCase,
)
from src.application.use_cases.delete_category_group import DeleteCategoryGroupUseCase
from src.application.use_cases.list_category_groups import list_category_groups
from src.application.use_cases.list_unmapped_categories import list_unmapped_categories
from src.application.use_cases.update_category_group import (
    UpdateCategoryGroupCommand,
    UpdateCategoryGroupUseCase,
)
from src.interface.api.schemas.category_groups import (
    BulkUpdateMappingsRequest,
    CategoryGroupResponse,
    CreateCategoryGroupRequest,
    UpdateCategoryGroupRequest,
)

router = APIRouter(tags=["category-groups"])


@router.get("/category-groups")
async def get_category_groups() -> list[CategoryGroupResponse]:
    items = await execute_use_case(list_category_groups)
    return [CategoryGroupResponse.from_domain(item) for item in items]


@router.post("/category-groups", status_code=201)
async def post_category_group(
    body: CreateCategoryGroupRequest,
) -> CategoryGroupResponse:
    command = CreateCategoryGroupCommand(name=body.name)
    group = await execute_use_case(
        lambda uow: CreateCategoryGroupUseCase(uow).execute(command)
    )
    return CategoryGroupResponse.from_group(group)


@router.put("/category-groups/{group_id}")
async def put_category_group(
    group_id: UUID, body: UpdateCategoryGroupRequest
) -> CategoryGroupResponse:
    command = UpdateCategoryGroupCommand(id=group_id, name=body.name)
    group = await execute_use_case(
        lambda uow: UpdateCategoryGroupUseCase(uow).execute(command)
    )
    return CategoryGroupResponse.from_group(group)


@router.delete("/category-groups/{group_id}", status_code=204)
async def delete_category_group(group_id: UUID) -> None:
    await execute_use_case(
        lambda uow: DeleteCategoryGroupUseCase(uow).execute(group_id)
    )


@router.put("/category-mappings")
async def put_category_mappings(body: BulkUpdateMappingsRequest) -> dict[str, int]:
    command = BulkUpdateMappingsCommand(
        mappings=[
            MappingEntry(category=m.category, group_id=m.group_id)
            for m in body.mappings
        ]
    )
    count = await execute_use_case(
        lambda uow: BulkUpdateMappingsUseCase(uow).execute(command)
    )
    return {"updated": count}


@router.get("/category-mappings/unmapped")
async def get_unmapped_categories() -> list[str]:
    return await execute_use_case(list_unmapped_categories)
