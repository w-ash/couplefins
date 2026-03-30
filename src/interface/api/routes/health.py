from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from src.config.settings import get_settings
from src.infrastructure.persistence.database.db_connection import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database_host: str
    database_mode: str


@router.get("/health")
async def health_check() -> HealthResponse:
    settings = get_settings()
    parsed = urlparse(settings.database.url)
    host = parsed.hostname or "unknown"

    if "neon" in host:
        mode = (
            "Neon (pooled)" if settings.database.is_pooled_endpoint else "Neon (direct)"
        )
    else:
        mode = "Local PostgreSQL"

    async with get_session() as session:
        await session.execute(text("SELECT 1"))

    return HealthResponse(status="ok", database_host=host, database_mode=mode)
