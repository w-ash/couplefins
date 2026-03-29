from collections.abc import Awaitable, Callable
from uuid import UUID

from src.domain.exceptions import NotFoundError


async def require_by_id[T](
    fetch: Callable[[UUID], Awaitable[T | None]],
    id: UUID,
    label: str,
) -> T:
    """Fetch an entity by ID or raise NotFoundError."""
    entity = await fetch(id)
    if entity is None:
        raise NotFoundError(f"{label} {id} not found")
    return entity
